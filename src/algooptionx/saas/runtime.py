"""Tenant-owned local engines; no caller-supplied filesystem or account selector."""
from pathlib import Path
import re
import threading
from algooptionx.paper.engine import Engine, PaperError
from algooptionx.demo.engine import DemoEngine
from algooptionx.paper.orderbook import ExecutionBook


class TenantRuntime:
    def __init__(self, folder: Path):
        self.folder = folder
        self.lock = threading.Lock()
        self.engines = {}
        self.errors = {}
        self.market_locks = {}
        self.execution_books = {}
        self.execution_errors = {}

    def get(self, tenant_id: str):
        if not re.fullmatch(r"[a-f0-9]{32}", tenant_id):
            raise ValueError("Invalid internal tenant identity.")
        with self.lock:
            if tenant_id not in self.engines:
                folder = self.folder / tenant_id
                folder.mkdir(parents=True,exist_ok=True,mode=0o700)
                # Tenant IDs come exclusively from authenticated membership records.
                paper = Engine(folder / "paper.db")
                demo = DemoEngine(folder / "demo.db", forbidden_paths=[folder / "paper.db"])
                self.engines[tenant_id] = (paper, demo)
            return self.engines[tenant_id]

    def pulse(self):
        with self.lock:
            engines = list(self.engines.items())
        for tenant_id, (paper, _) in engines:
            if tenant_id in self.errors:
                continue
            try:
                paper.pulse()
            except Exception:
                self.errors[tenant_id] = "Tenant playback stopped after an engine error. Preserve history and diagnose before restarting."

    def market_lock(self, tenant_id):
        with self.lock:
            if tenant_id not in self.market_locks:self.market_locks[tenant_id]=threading.RLock()
            return self.market_locks[tenant_id]

    def recover(self, tenant_ids):
        """Restore persisted execution workers before accepting requests."""
        for tenant_id in tenant_ids:
            folder = self.folder / tenant_id
            if not (folder / 'execution.db').exists():
                continue
            try:
                if folder.is_symlink() or any((folder / name).is_symlink() for name in ('paper.db','demo.db','execution.db')):
                    raise PaperError('Symlinked tenant storage requires operator diagnosis.')
                if not (folder / 'demo.db').is_file() or not (folder / 'paper.db').is_file():
                    raise PaperError('Execution history requires its original source and paper databases.')
                restored = self.execution(tenant_id)
                active = restored.history()['active_account_id']
                if not restored.audit(active)['reconciled']:
                    raise PaperError('Persisted account did not reconcile.')
            except Exception:
                self.execution_errors[tenant_id] = 'Persisted execution recovery failed. Preserve all tenant databases for diagnosis; matching remains stopped.'

    def execution(self, tenant_id):
        if tenant_id in self.execution_errors and tenant_id not in self.execution_books:
            raise PaperError(self.execution_errors[tenant_id])
        _,demo=self.get(tenant_id)
        with self.lock:
            if tenant_id not in self.execution_books:
                self.execution_books[tenant_id]=ExecutionBook(self.folder/tenant_id/'execution.db',demo.state)
            return self.execution_books[tenant_id]

    def has_execution_exposure(self, tenant_id):
        if tenant_id not in self.execution_books and not (self.folder/tenant_id/'execution.db').exists():return False
        return self.execution(tenant_id).has_exposure()

    def process_execution(self):
        with self.lock:books=list(self.execution_books.items())
        for tenant_id,book in books:
            if tenant_id in self.execution_errors:continue
            try:
                with self.market_lock(tenant_id):book.process()
            except Exception:
                self.execution_errors[tenant_id]='Execution worker stopped after an accounting, quote or storage error. Preserve history and reconcile before restarting.'
