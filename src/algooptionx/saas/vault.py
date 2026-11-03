"""Versioned server-side encryption. Secrets never have a read-back API."""
import json
import os
from pathlib import Path
from cryptography.fernet import Fernet, InvalidToken
from .identity import IdentityError


class SecretVault:
    def __init__(self,path:Path,required:bool=False):
        self.version=os.environ.get('ALGOOPTIONX_SECRET_KEY_VERSION','1')
        try:keys=json.loads(os.environ.get('ALGOOPTIONX_SECRET_KEYS','{}'))
        except ValueError:raise IdentityError('Secret-key configuration is invalid.',503) from None
        if not isinstance(keys,dict):raise IdentityError('Secret-key configuration is invalid.',503)
        direct=os.environ.get('ALGOOPTIONX_SECRET_KEY')
        if direct:keys[self.version]=direct
        if self.version not in keys:
            if required:raise IdentityError('Configure the server encryption key before enabling MFA or broker connections.',503)
            path.parent.mkdir(parents=True,exist_ok=True,mode=0o700)
            try:
                fd=os.open(path,os.O_CREAT|os.O_EXCL|os.O_WRONLY,0o600)
                with os.fdopen(fd,'wb') as stream:stream.write(Fernet.generate_key())
            except FileExistsError:pass
            keys[self.version]=path.read_bytes()
        try:self.keys={version:Fernet(value.encode() if isinstance(value,str) else value) for version,value in keys.items()}
        except (ValueError,TypeError):raise IdentityError('Secret-key configuration is invalid.',503) from None

    def encrypt(self,value):
        return json.dumps({'version':self.version,'ciphertext':self.keys[self.version].encrypt(json.dumps(value,separators=(',',':')).encode()).decode()},separators=(',',':'))

    def decrypt(self,value):
        try:
            envelope=json.loads(value);key=self.keys[envelope['version']]
            return json.loads(key.decrypt(envelope['ciphertext'].encode()))
        except (ValueError,KeyError,TypeError,InvalidToken):
            raise IdentityError('Stored credentials are unavailable. Reauthorize using a valid encryption key.',503) from None
