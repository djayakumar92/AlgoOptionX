"""Quote-driven virtual orders with atomic cash, reservations, fills and audit.

This model uses synthetic quote cycles and declared one-lot liquidity. It does
not infer exchange queue position, fills from candles, or actual broker margin.
"""
from __future__ import annotations
from contextlib import contextmanager
import hashlib
import hmac
import secrets
import os
import json
from pathlib import Path
import sqlite3
import time
import uuid
from algooptionx.paper.engine import PaperError

MODEL = 'SYNTHETIC-QUOTE-CYCLE-1'
CHARGES = 'FIXTURE-INR20-PER-LEG-FILL-1'
LOT = 65
FEE = 2000
SLIPPAGE = 5
TERMINAL = {'FILLED','CANCELED','REJECTED','EXPIRED'}


def canonical(value):
    return json.dumps(value, sort_keys=True, separators=(',', ':'), allow_nan=False)


class ExecutionBook:
    def __init__(self, path, provider):
        self.path, self.provider = Path(path), provider
        self.path.parent.mkdir(parents=True, exist_ok=True, mode=0o700)
        if not self.path.exists():
            fd=os.open(self.path,os.O_CREAT|os.O_EXCL|os.O_WRONLY,0o600);os.close(fd)
        os.chmod(self.path,0o600)
        with self.tx() as c:
            for statement in (
                "CREATE TABLE IF NOT EXISTS settings(key TEXT PRIMARY KEY,value TEXT NOT NULL)",
                "CREATE TABLE IF NOT EXISTS accounts(id TEXT PRIMARY KEY,capital INTEGER NOT NULL,cash INTEGER NOT NULL,realized INTEGER NOT NULL DEFAULT 0,fees INTEGER NOT NULL DEFAULT 0,killed INTEGER NOT NULL DEFAULT 0,created_at INTEGER NOT NULL)",
                "CREATE TABLE IF NOT EXISTS active(singleton INTEGER PRIMARY KEY CHECK(singleton=1),account_id TEXT NOT NULL REFERENCES accounts(id))",
                "CREATE TABLE IF NOT EXISTS cycle(singleton INTEGER PRIMARY KEY CHECK(singleton=1),number INTEGER NOT NULL)",
                "CREATE TABLE IF NOT EXISTS orders(id TEXT PRIMARY KEY,account_id TEXT NOT NULL REFERENCES accounts(id),source_session TEXT NOT NULL,kind TEXT NOT NULL,legs TEXT NOT NULL,lots INTEGER NOT NULL,filled INTEGER NOT NULL DEFAULT 0,status TEXT NOT NULL,limit_price INTEGER,stop_price INTEGER,trigger_direction TEXT NOT NULL,triggered INTEGER NOT NULL DEFAULT 0,accepted_cycle INTEGER NOT NULL,revision INTEGER NOT NULL DEFAULT 1,close_position TEXT,reserve_per_lot INTEGER NOT NULL,risk_per_lot INTEGER NOT NULL,created_at INTEGER NOT NULL)",
                "CREATE TABLE IF NOT EXISTS positions(id TEXT PRIMARY KEY,account_id TEXT NOT NULL REFERENCES accounts(id),legs TEXT NOT NULL,source_session TEXT NOT NULL,reserve_per_lot INTEGER NOT NULL)",
                "CREATE TABLE IF NOT EXISTS position_lots(id TEXT PRIMARY KEY,position_id TEXT NOT NULL REFERENCES positions(id),entry_debit INTEGER NOT NULL,entry_fee INTEGER NOT NULL,risk_per_lot INTEGER NOT NULL,entry_cycle INTEGER NOT NULL,open INTEGER NOT NULL DEFAULT 1)",
                "CREATE TABLE IF NOT EXISTS fills(id TEXT PRIMARY KEY,order_id TEXT NOT NULL REFERENCES orders(id),cycle INTEGER NOT NULL,lots INTEGER NOT NULL,net_debit INTEGER NOT NULL,fee INTEGER NOT NULL,quotes TEXT NOT NULL,created_at INTEGER NOT NULL,UNIQUE(order_id,cycle))",
                "CREATE TABLE IF NOT EXISTS commands(account_id TEXT NOT NULL,request_key TEXT NOT NULL,request TEXT NOT NULL,result TEXT NOT NULL,PRIMARY KEY(account_id,request_key))",
                "CREATE TABLE IF NOT EXISTS journal_transactions(id TEXT PRIMARY KEY,account_id TEXT NOT NULL REFERENCES accounts(id),kind TEXT NOT NULL,reference TEXT UNIQUE NOT NULL,created_at INTEGER NOT NULL)",
                "CREATE TABLE IF NOT EXISTS journal_entries(transaction_id TEXT NOT NULL REFERENCES journal_transactions(id),account TEXT NOT NULL,amount INTEGER NOT NULL,PRIMARY KEY(transaction_id,account))",
                "CREATE TABLE IF NOT EXISTS events(sequence INTEGER PRIMARY KEY AUTOINCREMENT,account_id TEXT NOT NULL,kind TEXT NOT NULL,payload TEXT NOT NULL,previous_hash TEXT NOT NULL,hash TEXT NOT NULL)",
            ):
                c.execute(statement)
            c.execute("INSERT OR IGNORE INTO settings VALUES('preview_key',?)",(secrets.token_hex(32),))
            columns={row['name'] for row in c.execute('PRAGMA table_info(position_lots)')}
            for column in ('risk_per_lot','entry_cycle'):
                if column not in columns:c.execute(f'ALTER TABLE position_lots ADD COLUMN {column} INTEGER NOT NULL DEFAULT 0')
            c.execute('INSERT OR IGNORE INTO cycle VALUES(1,0)')
            if not c.execute('SELECT 1 FROM active').fetchone():
                if c.execute('SELECT 1 FROM accounts').fetchone():
                    raise PaperError('Incomplete execution-account state. Preserve the database for reconciliation.')
                self._new(c,50_000_000)

    @contextmanager
    def tx(self):
        c=sqlite3.connect(self.path,timeout=15,isolation_level=None);c.row_factory=sqlite3.Row
        c.execute('PRAGMA foreign_keys=ON')
        try:
            c.execute('BEGIN IMMEDIATE');yield c;c.commit()
        except BaseException:
            c.rollback();raise
        finally:c.close()

    def _account(self,c):
        return c.execute('SELECT a.* FROM accounts a JOIN active p ON p.account_id=a.id WHERE p.singleton=1').fetchone()

    def _event(self,c,a,kind,payload):
        previous=c.execute('SELECT hash FROM events WHERE account_id=? ORDER BY sequence DESC LIMIT 1',(a,)).fetchone()
        previous=previous[0] if previous else '0'*64
        text=canonical(payload);hashed=hashlib.sha256((previous+kind+text).encode()).hexdigest()
        c.execute('INSERT INTO events(account_id,kind,payload,previous_hash,hash) VALUES(?,?,?,?,?)',(a,kind,text,previous,hashed))

    def _post(self,c,a,kind,reference,entries):
        if sum(entries.values())!=0 or any(type(value) is not int for value in entries.values()):
            raise PaperError('Unbalanced or invalid virtual financial posting.')
        transaction_id=uuid.uuid4().hex
        c.execute('INSERT INTO journal_transactions VALUES(?,?,?,?,?)',(transaction_id,a,kind,reference,int(time.time())))
        c.executemany('INSERT INTO journal_entries VALUES(?,?,?)',[(transaction_id,key,value) for key,value in entries.items()])

    def _new(self,c,capital):
        if type(capital) is not int or not 1_000_000<=capital<=1_000_000_000:
            raise PaperError('Virtual starting capital must be ₹10,000–₹1,00,00,000 in integer paise.')
        a=uuid.uuid4().hex
        c.execute('INSERT INTO accounts(id,capital,cash,created_at) VALUES(?,?,?,?)',(a,capital,capital,int(time.time())))
        c.execute('INSERT OR REPLACE INTO active VALUES(1,?)',(a,))
        self._post(c,a,'FUNDING','funding:'+a,{'cash':capital,'virtual_funding':-capital})
        self._event(c,a,'FUNDING',{'amount':capital,'mode':'PAPER','source':'SYNTHETIC','model':MODEL})
        return a

    def _quotes(self,source):
        result={}
        for q in source['contracts']:
            if type(q['bid']) is not int or type(q['ask']) is not int or not 0<=q['bid']<=q['ask'] or q['lot_size']!=LOT:
                raise PaperError('Invalid source quote or fixture instrument specification.')
            result[q['id']]=q|{'_source_session':source['session']['id']}
        return result

    def _legs(self,legs,quotes):
        if not isinstance(legs,list) or not 1<=len(legs)<=4:
            raise PaperError('Use one to four option legs.')
        result=[];seen=set()
        for leg in legs:
            instrument,side=leg.get('instrument'),leg.get('side')
            if instrument not in quotes or type(side) is not int or side not in (-1,1) or instrument in seen:
                raise PaperError('Select distinct supported instruments and BUY/SELL sides.')
            seen.add(instrument);q=quotes[instrument]
            result.append({'instrument':instrument,'side':side,'strike':q['strike'],'right':q['right'],'expiry':q['expiry']})
        if len({leg['expiry'] for leg in result})!=1:
            raise PaperError('All legs must share one supported expiry.')
        for right in ('CE','PE'):
            if sum(leg['side'] for leg in result if leg['right']==right)<0:
                raise PaperError('Naked short legs are not supported; hedge each option right.')
        return result

    def _debit(self,legs,quotes):
        if any(leg['instrument'] not in quotes for leg in legs):
            raise PaperError('Required instrument quotes are unavailable.')
        return sum(leg['side']*(quotes[leg['instrument']]['ask']+SLIPPAGE if leg['side']==1 else max(0,quotes[leg['instrument']]['bid']-SLIPPAGE)) for leg in legs)

    def _risk(self,legs,quotes):
        debit=self._debit(legs,quotes);fees=FEE*len(legs)
        knots={0,*[leg['strike'] for leg in legs],max(leg['strike'] for leg in legs)+100000}
        payoff=lambda spot:sum(leg['side']*max(0,(spot-leg['strike']) if leg['right']=='CE' else (leg['strike']-spot))*100*LOT for leg in legs)
        values=[payoff(spot)-debit*LOT-2*fees for spot in knots]
        friction=(40+SLIPPAGE)*LOT*len(legs)
        values=[value-friction for value in values]
        risk=max(0,-min(values))
        collateral=max(0,-min(payoff(spot) for spot in knots))+fees+friction if any(leg['side']==-1 for leg in legs) else 0
        reserve=max(0,debit*LOT)+fees+collateral
        return {'net_debit_paise':debit,'entry_fee_paise':fees,'worst_loss_paise':risk,'max_profit_paise':None if sum(leg['side'] for leg in legs if leg['right']=='CE')>0 else max(values),'collateral_paise':collateral,'reserve_paise':reserve}

    def _reservations(self,c,a):
        pending=c.execute("SELECT COALESCE(SUM((lots-filled)*reserve_per_lot),0) FROM orders WHERE account_id=? AND close_position IS NULL AND status NOT IN ('FILLED','CANCELED','REJECTED','EXPIRED')",(a,)).fetchone()[0]
        collateral=c.execute('SELECT COALESCE(SUM(p.reserve_per_lot),0) FROM position_lots l JOIN positions p ON p.id=l.position_id WHERE p.account_id=? AND l.open=1',(a,)).fetchone()[0]
        return pending+collateral

    def _mark(self,c,account,quotes):
        value=0;cost=0
        for lot in c.execute('SELECT l.entry_debit,p.legs,p.source_session FROM position_lots l JOIN positions p ON p.id=l.position_id WHERE p.account_id=? AND l.open=1',(account['id'],)):
            legs=json.loads(lot['legs'])
            if any(leg['instrument'] not in quotes or quotes[leg['instrument']]['_source_session']!=lot['source_session'] for leg in legs):
                return None
            value+=sum(leg['side']*((quotes[leg['instrument']]['bid']+quotes[leg['instrument']]['ask'])//2)*LOT for leg in legs)
            cost+=lot['entry_debit']*LOT
        return {'equity':account['cash']+value,'unrealized':value-cost}

    def _validate_entry(self,c,account,legs,lots,risk,quotes,exclude=None):
        if account['killed']:
            raise PaperError('Emergency stop is latched. New entries are blocked.')
        mark=self._mark(c,account,quotes)
        if mark is None:
            raise PaperError('Positions cannot be valued from current quotes. Entries are blocked.')
        if mark['equity']<=account['capital']*98//100:
            raise PaperError('The 2% account loss limit blocks new entries.')
        filled_risk=c.execute('SELECT COALESCE(SUM(risk_per_lot),0) FROM position_lots WHERE position_id=? AND open=1',(exclude,)).fetchone()[0] if exclude else 0
        if filled_risk+risk['worst_loss_paise']*lots>account['capital']//100:
            raise PaperError('Order worst-case risk exceeds 1% of starting capital.')
        count=c.execute('SELECT COUNT(DISTINCT p.id) FROM positions p JOIN position_lots l ON l.position_id=p.id WHERE p.account_id=? AND l.open=1 AND (? IS NULL OR p.id!=?)',(account['id'],exclude,exclude)).fetchone()[0]
        pending=c.execute("SELECT COUNT(*) FROM orders WHERE account_id=? AND close_position IS NULL AND status NOT IN ('FILLED','CANCELED','REJECTED','EXPIRED') AND (? IS NULL OR id!=?)",(account['id'],exclude,exclude)).fetchone()[0]
        if count+pending>=3:
            raise PaperError('At most three open/pending strategies are supported.')
        reserved=self._reservations(c,account['id'])
        if exclude:
            old=c.execute('SELECT lots,filled,reserve_per_lot FROM orders WHERE id=?',(exclude,)).fetchone()
            reserved-=(old['lots']-old['filled'])*old['reserve_per_lot']
        if reserved+risk['reserve_paise']*lots>account['cash'] or reserved+risk['reserve_paise']*lots>account['capital']*40//100:
            raise PaperError('Available cash or the conservative 40% reservation cap is insufficient.')
        debit=max(0,risk['net_debit_paise']*LOT)*lots
        existing_debit=c.execute('SELECT COALESCE(SUM(MAX(0,l.entry_debit)),0) FROM position_lots l JOIN positions p ON p.id=l.position_id WHERE p.account_id=? AND l.open=1',(account['id'],)).fetchone()[0]*LOT
        for pending_order in c.execute("SELECT id,legs,lots,filled FROM orders WHERE account_id=? AND close_position IS NULL AND status NOT IN ('FILLED','CANCELED','REJECTED','EXPIRED') AND (? IS NULL OR id!=?)",(account['id'],exclude,exclude)):
            existing_debit+=max(0,self._debit(json.loads(pending_order['legs']),quotes))*LOT*(pending_order['lots']-pending_order['filled'])
        if existing_debit+debit>account['capital']//5:
            raise PaperError('Premium exposure exceeds 20% of starting capital.')

    def _preview_token(self,c,account,body,source):
        fields={key:body.get(key) for key in ('kind','legs','lots','limit_paise','stop_paise','trigger_direction')}
        payload={'request':fields,'account':dict(account),'reserved':self._reservations(c,account['id']),
                 'source_session':source['session']['id'],'quote_tick':source['session']['quote_tick'],
                 'quotes':[(q['id'],q['bid'],q['ask']) for q in source['contracts']],'model':MODEL,'charges':CHARGES}
        key=c.execute("SELECT value FROM settings WHERE key='preview_key'").fetchone()[0]
        return hmac.new(bytes.fromhex(key),canonical(payload).encode(),hashlib.sha256).hexdigest()

    def preview(self,body):
        source=self.provider();quotes=self._quotes(source);legs=self._legs(body['legs'],quotes);risk=self._risk(legs,quotes)
        errors=[]
        with self.tx() as c:
            account=self._account(c)
            if body.get('expected_account_id')!=account['id']:raise PaperError('The active execution account changed. Refresh and review again.')
            try:self._validate_entry(c,account,legs,body['lots'],risk,quotes)
            except PaperError as error:errors.append(str(error))
            token=self._preview_token(c,account,body,source)
        if not source['session']['connected'] or source['session']['quote_tick']!=source['session']['tick']:
            errors.append('Source quotes are disconnected/stale.')
        if source['session']['killed'] or source['session']['tick']>=180:errors.append('The synthetic source is stopped or past the entry cutoff.')
        return risk|{'preview_token':token,'legs':legs,'lots':body['lots'],'valid':not errors,'errors':errors,'source':'SYNTHETIC','model_version':MODEL,'charge_version':CHARGES,'lot_size':LOT,'liquidity':'One modeled lot per instrument/side every quote cycle; not observed queue or depth.'}

    def command(self,key,action,body):
        source=self.provider();quotes=self._quotes(source)
        with self.tx() as c:
            account=self._account(c)
            if body.get('expected_account_id')!=account['id']:raise PaperError('The active execution account changed. Refresh and review again.')
            request=canonical({'action':action,'body':body})
            old=c.execute('SELECT * FROM commands WHERE account_id=? AND request_key=?',(account['id'],key)).fetchone()
            if old:
                if old['request']!=request:raise PaperError('Command key was reused with different instructions.')
                return json.loads(old['result'])
            if action=='place':result=self._place(c,account,body,source,quotes)
            elif action=='cancel':result=self._cancel(c,account,body)
            elif action=='modify':result=self._modify(c,account,body,source,quotes)
            elif action=='close':result=self._close(c,account,body,source,quotes)
            elif action=='kill':result=self._kill(c,account,source,quotes)
            else:raise PaperError('Unknown execution command.')
            c.execute('INSERT INTO commands VALUES(?,?,?,?)',(account['id'],key,request,canonical(result)))
            return result

    def _place(self,c,account,body,source,quotes):
        token=body.get('preview_token','')
        if not isinstance(token,str) or not hmac.compare_digest(token,self._preview_token(c,account,body,source)):raise PaperError('Preview expired or account/quotes changed. Review a fresh preview before placing the order.')
        if not source['session']['connected'] or source['session']['quote_tick']!=source['session']['tick'] or source['session']['killed']:
            raise PaperError('Fresh connected source quotes are required for entries.')
        if source['session']['tick']>=180:raise PaperError('The synthetic entry session has ended.')
        legs=self._legs(body['legs'],quotes);lots=body['lots'];risk=self._risk(legs,quotes)
        if type(lots) is not int or not 1<=lots<=5:raise PaperError('Use one to five integer fixture lots.')
        self._validate_entry(c,account,legs,lots,risk,quotes)
        if body['kind'] not in {'MARKET','LIMIT','STOP','STOP_LIMIT'} or body.get('trigger_direction','above') not in {'above','below'}:raise PaperError('Invalid order type or trigger direction.')
        kind=body['kind'];limit=body.get('limit_paise');stop=body.get('stop_paise')
        if kind in ('LIMIT','STOP_LIMIT') and type(limit) is not int:raise PaperError('A net-debit limit price in integer paise is required.')
        if kind in ('STOP','STOP_LIMIT') and type(stop) is not int:raise PaperError('A stop trigger in integer paise is required.')
        order_id=uuid.uuid4().hex;cycle=c.execute('SELECT number FROM cycle WHERE singleton=1').fetchone()[0]
        c.execute('INSERT INTO orders VALUES(?,?,?,?,?,?,0,?,?,?,?,0,?,1,NULL,?,?,?)',(order_id,account['id'],source['session']['id'],kind,canonical(legs),lots,'WORKING',limit,stop,body.get('trigger_direction','above'),cycle,risk['reserve_paise'],risk['worst_loss_paise'],int(time.time())))
        self._event(c,account['id'],'ORDER_ACCEPTED',{'order_id':order_id,'lots':lots,'kind':kind,'model':MODEL,'risk':risk})
        return {'order_id':order_id,'status':'WORKING'}

    def _owned_order(self,c,account,body):
        order=c.execute('SELECT * FROM orders WHERE id=? AND account_id=?',(body['order_id'],account['id'])).fetchone()
        if not order:raise PaperError('Order not found in the active account.')
        if order['revision']!=body['expected_revision']:raise PaperError('Order changed. Refresh before modifying it.')
        if order['status'] in TERMINAL:raise PaperError('This order is already terminal.')
        return order

    def _cancel(self,c,account,body):
        order=self._owned_order(c,account,body)
        c.execute("UPDATE orders SET status='CANCELED',revision=revision+1 WHERE id=?",(order['id'],))
        self._event(c,account['id'],'ORDER_CANCELED',{'order_id':order['id'],'filled_lots':order['filled']})
        return {'order_id':order['id'],'status':'CANCELED'}

    def _modify(self,c,account,body,source,quotes):
        order=self._owned_order(c,account,body)
        if order['close_position']:raise PaperError('Cancel and recreate a closing order instead of modifying it.')
        if not source['session']['connected'] or source['session']['quote_tick']!=source['session']['tick']:raise PaperError('Fresh quotes are required to modify an entry.')
        lots=body.get('lots',order['lots'])
        if type(lots) is not int or not 1<=lots<=5:raise PaperError('Use one to five integer fixture lots.')
        if lots<=order['filled']:raise PaperError('Total lots must exceed already filled lots; cancel remaining quantity instead.')
        risk=self._risk(json.loads(order['legs']),quotes)
        self._validate_entry(c,account,json.loads(order['legs']),lots-order['filled'],risk,quotes,exclude=order['id'])
        limit=body.get('limit_paise',order['limit_price']);stop=body.get('stop_paise',order['stop_price'])
        if order['kind'] in ('LIMIT','STOP_LIMIT') and type(limit) is not int:raise PaperError('A net-debit limit in integer paise is required.')
        if order['kind'] in ('STOP','STOP_LIMIT') and type(stop) is not int:raise PaperError('A stop trigger in integer paise is required.')
        c.execute('UPDATE orders SET lots=?,limit_price=?,stop_price=?,reserve_per_lot=?,risk_per_lot=?,revision=revision+1,accepted_cycle=(SELECT number FROM cycle WHERE singleton=1) WHERE id=?',(lots,limit,stop,risk['reserve_paise'],risk['worst_loss_paise'],order['id']))
        self._event(c,account['id'],'ORDER_MODIFIED',{'order_id':order['id'],'lots':lots,'limit_paise':limit,'stop_paise':stop})
        return {'order_id':order['id'],'status':order['status']}

    def _close(self,c,account,body,source,quotes):
        position=c.execute('SELECT p.*,COUNT(l.id) lots FROM positions p JOIN position_lots l ON l.position_id=p.id WHERE p.id=? AND p.account_id=? AND l.open=1 GROUP BY p.id',(body['position_id'],account['id'])).fetchone()
        if not position:raise PaperError('Open position not found.')
        pending=c.execute("SELECT id FROM orders WHERE close_position=? AND status NOT IN ('FILLED','CANCELED','REJECTED','EXPIRED')",(position['id'],)).fetchone()
        if pending:return {'order_id':pending['id'],'status':'WORKING'}
        c.execute("UPDATE orders SET status='CANCELED',revision=revision+1 WHERE id=? AND status NOT IN ('FILLED','CANCELED','REJECTED','EXPIRED')",(position['id'],))
        legs=[leg|{'side':-leg['side']} for leg in json.loads(position['legs'])]
        order_id=uuid.uuid4().hex;cycle=c.execute('SELECT number FROM cycle WHERE singleton=1').fetchone()[0]
        c.execute("INSERT INTO orders VALUES(?,?,?,?,?,?,0,'WORKING',NULL,NULL,'above',0,?,1,?,0,0,?)",(order_id,account['id'],position['source_session'],'MARKET',canonical(legs),position['lots'],cycle,position['id'],int(time.time())))
        self._event(c,account['id'],'CLOSE_REQUESTED',{'order_id':order_id,'position_id':position['id']})
        return {'order_id':order_id,'status':'WORKING'}

    def _kill(self,c,account,source,quotes):
        c.execute('UPDATE accounts SET killed=1 WHERE id=?',(account['id'],))
        c.execute("UPDATE orders SET status='CANCELED',revision=revision+1 WHERE account_id=? AND close_position IS NULL AND status NOT IN ('FILLED','CANCELED','REJECTED','EXPIRED')",(account['id'],))
        positions=c.execute('SELECT DISTINCT p.id FROM positions p JOIN position_lots l ON l.position_id=p.id WHERE p.account_id=? AND l.open=1',(account['id'],)).fetchall()
        orders=[self._close(c,account,{'position_id':position['id']},source,quotes)['order_id'] for position in positions]
        self._event(c,account['id'],'EMERGENCY_STOP',{'close_orders':orders,'notice':'Entries are latched off. Residual exposure remains until fresh modeled liquidity permits fills.'})
        return {'killed':True,'close_orders':orders}

    def process(self):
        source=self.provider()
        if not source['session']['connected'] or source['session']['quote_tick']!=source['session']['tick']:return
        quotes=self._quotes(source)
        with self.tx() as c:
            account=self._account(c);cycle=c.execute('SELECT number FROM cycle WHERE singleton=1').fetchone()[0]+1
            c.execute('UPDATE cycle SET number=? WHERE singleton=1',(cycle,));used={}
            orders=c.execute("SELECT * FROM orders WHERE account_id=? AND status NOT IN ('FILLED','CANCELED','REJECTED','EXPIRED') ORDER BY close_position IS NULL,created_at,rowid",(account['id'],)).fetchall()
            for order in orders:
                if order['accepted_cycle']>=cycle:continue
                if order['source_session']!=source['session']['id'] or source['session']['tick']>=180 and not order['close_position']:
                    c.execute("UPDATE orders SET status='EXPIRED',revision=revision+1 WHERE id=?",(order['id'],));self._event(c,account['id'],'ORDER_EXPIRED',{'order_id':order['id']});continue
                legs=json.loads(order['legs'])
                if any(leg['instrument'] not in quotes for leg in legs):continue
                debit=self._debit(legs,quotes)
                if order['kind'] in ('STOP','STOP_LIMIT') and not order['triggered']:
                    hit=debit>=order['stop_price'] if order['trigger_direction']=='above' else debit<=order['stop_price']
                    if not hit:continue
                    c.execute('UPDATE orders SET triggered=1,revision=revision+1 WHERE id=?',(order['id'],));self._event(c,account['id'],'STOP_TRIGGERED',{'order_id':order['id'],'net_debit':debit})
                if order['kind'] in ('LIMIT','STOP_LIMIT') and debit>order['limit_price']:continue
                if any(used.get((leg['instrument'],leg['side']),0)>=1 for leg in legs):continue
                if not order['close_position']:
                    account=self._account(c)
                    if account['killed'] or source['session']['killed']:
                        c.execute("UPDATE orders SET status='REJECTED',revision=revision+1 WHERE id=?",(order['id'],));self._event(c,account['id'],'ORDER_REJECTED',{'order_id':order['id'],'reason':'Emergency source/account entry lock.'});continue
                    risk=self._risk(legs,quotes)
                    try:
                        # The remaining quantity plus existing reservation is rechecked
                        # at the transaction-time quote. No UI/AI can bypass this gate.
                        self._validate_entry(c,account,legs,order['lots']-order['filled'],risk,quotes,exclude=order['id'])
                    except PaperError as error:
                        c.execute("UPDATE orders SET status='REJECTED',revision=revision+1 WHERE id=?",(order['id'],));self._event(c,account['id'],'ORDER_REJECTED',{'order_id':order['id'],'reason':str(error)});continue
                    c.execute('UPDATE orders SET reserve_per_lot=?,risk_per_lot=? WHERE id=?',(risk['reserve_paise'],risk['worst_loss_paise'],order['id']))
                fee=FEE*len(legs);cash_delta=-debit*LOT-fee;gross_realized=0
                if order['close_position']:
                    lot=c.execute('SELECT * FROM position_lots WHERE position_id=? AND open=1 ORDER BY entry_cycle,id LIMIT 1',(order['close_position'],)).fetchone()
                    if not lot:
                        c.execute("UPDATE orders SET status='CANCELED',revision=revision+1 WHERE id=?",(order['id'],));continue
                    gross_realized=-(lot['entry_debit']+debit)*LOT
                    c.execute('UPDATE position_lots SET open=0 WHERE id=?',(lot['id'],))
                    entries={'cash':cash_delta,'inventory':-lot['entry_debit']*LOT,'fee_expense':fee,'realized_trading_pnl':-gross_realized}
                else:
                    collateral=risk['collateral_paise']
                    c.execute('INSERT OR IGNORE INTO positions VALUES(?,?,?,?,?)',(order['id'],account['id'],order['legs'],order['source_session'],collateral))
                    c.execute('UPDATE positions SET reserve_per_lot=MAX(reserve_per_lot,?) WHERE id=?',(collateral,order['id']))
                    c.execute('INSERT INTO position_lots(id,position_id,entry_debit,entry_fee,risk_per_lot,entry_cycle,open) VALUES(?,?,?,?,?,?,1)',(uuid.uuid4().hex,order['id'],debit,fee,risk['worst_loss_paise'],cycle))
                    entries={'cash':cash_delta,'inventory':debit*LOT,'fee_expense':fee}
                fill_id=uuid.uuid4().hex
                quote_record=[{'instrument':leg['instrument'],'side':leg['side'],'bid':quotes[leg['instrument']]['bid'],'ask':quotes[leg['instrument']]['ask'],'cycle':cycle,'source_time':source['session']['quote_time'],'liquidity':'MODELED_ONE_LOT'} for leg in legs]
                c.execute('INSERT INTO fills VALUES(?,?,?,?,?,?,?,?)',(fill_id,order['id'],cycle,1,debit,fee,canonical(quote_record),int(time.time())))
                self._post(c,account['id'],'FILL',fill_id,entries)
                c.execute('UPDATE accounts SET cash=cash+?,realized=realized+?,fees=fees+? WHERE id=?',(cash_delta,gross_realized-fee,fee,account['id']))
                status='FILLED' if order['filled']+1==order['lots'] else 'PARTIALLY_FILLED'
                c.execute('UPDATE orders SET filled=filled+1,status=?,revision=revision+1 WHERE id=?',(status,order['id']))
                for leg in legs:used[(leg['instrument'],leg['side'])]=1
                self._event(c,account['id'],'FILL',{'fill_id':fill_id,'order_id':order['id'],'net_debit_paise':debit,'lots':1,'fee_paise':fee,'quotes':quote_record,'model':MODEL,'charges':CHARGES})

    def has_exposure(self):
        with self.tx() as c:
            a=self._account(c)['id']
            return bool(c.execute('SELECT 1 FROM position_lots l JOIN positions p ON p.id=l.position_id WHERE p.account_id=? AND l.open=1 LIMIT 1',(a,)).fetchone() or c.execute("SELECT 1 FROM orders WHERE account_id=? AND status NOT IN ('FILLED','CANCELED','REJECTED','EXPIRED') LIMIT 1",(a,)).fetchone())

    def new_account(self,capital,expected_account_id):
        with self.tx() as c:
            a=self._account(c)['id']
            if a!=expected_account_id:raise PaperError('The active execution account changed. Refresh before resetting virtual capital.')
            if c.execute('SELECT 1 FROM position_lots l JOIN positions p ON p.id=l.position_id WHERE p.account_id=? AND l.open=1 LIMIT 1',(a,)).fetchone() or c.execute("SELECT 1 FROM orders WHERE account_id=? AND status NOT IN ('FILLED','CANCELED','REJECTED','EXPIRED') LIMIT 1",(a,)).fetchone():
                raise PaperError('Close positions and cancel working orders before starting a new virtual account.')
            return {'account_id':self._new(c,capital)}

    def history(self):
        with self.tx() as c:
            active = self._account(c)['id']
            rows = c.execute('SELECT id,capital,cash,realized,fees,killed,created_at FROM accounts ORDER BY created_at DESC,id').fetchall()
        return {'active_account_id': active, 'accounts': [dict(row) for row in rows]}

    def audit(self, account_id):
        """Reconcile persisted economics without changing balances or history."""
        with self.tx() as c:
            account = c.execute('SELECT * FROM accounts WHERE id=?', (account_id,)).fetchone()
            if not account:
                raise PaperError('Execution account not found.')
            errors = []
            totals = {row['account']: row['amount'] for row in c.execute('SELECT e.account,SUM(e.amount) amount FROM journal_entries e JOIN journal_transactions t ON t.id=e.transaction_id WHERE t.account_id=? GROUP BY e.account', (account_id,))}
            unbalanced = c.execute('SELECT t.id FROM journal_transactions t LEFT JOIN journal_entries e ON e.transaction_id=t.id WHERE t.account_id=? GROUP BY t.id HAVING SUM(e.amount)!=0 OR COUNT(e.account)<2', (account_id,)).fetchall()
            if unbalanced:
                errors.append('Unbalanced or incomplete journal transactions.')
            inventory = c.execute('SELECT COALESCE(SUM(l.entry_debit),0) FROM position_lots l JOIN positions p ON p.id=l.position_id WHERE p.account_id=? AND l.open=1', (account_id,)).fetchone()[0] * LOT
            expected = {'cash': account['cash'], 'fee_expense': account['fees'], 'inventory': inventory, 'virtual_funding': -account['capital']}
            for key, value in expected.items():
                if totals.get(key, 0) != value:
                    errors.append(f'{key} does not reconcile to account state.')
            if -totals.get('realized_trading_pnl', 0) - account['fees'] != account['realized']:
                errors.append('Realized P&L does not reconcile to the journal.')
            fees = c.execute('SELECT COALESCE(SUM(f.fee),0) FROM fills f JOIN orders o ON o.id=f.order_id WHERE o.account_id=?', (account_id,)).fetchone()[0]
            if fees != account['fees']:
                errors.append('Fill fees do not reconcile to account fees.')
            previous = '0' * 64
            event_count = 0
            for event in c.execute('SELECT * FROM events WHERE account_id=? ORDER BY sequence', (account_id,)):
                event_count += 1
                hashed = hashlib.sha256((previous + event['kind'] + event['payload']).encode()).hexdigest()
                if event['previous_hash'] != previous or event['hash'] != hashed:
                    errors.append('Execution audit hash chain is invalid.')
                    break
                previous = event['hash']
            if not event_count:
                errors.append('Funding audit history is missing.')
        return {'account_id': account_id, 'reconciled': not errors, 'errors': errors, 'journal_totals': totals, 'event_count': event_count, 'last_event_hash': previous, 'model_version': MODEL, 'charge_version': CHARGES, 'notice': 'Reconciliation is a consistency check, not independent release approval.'}

    def export(self, account_id):
        audit = self.audit(account_id)
        with self.tx() as c:
            account = dict(c.execute('SELECT * FROM accounts WHERE id=?', (account_id,)).fetchone())
            orders = [dict(row) for row in c.execute('SELECT * FROM orders WHERE account_id=? ORDER BY created_at,id', (account_id,))]
            fills = [dict(row) for row in c.execute('SELECT f.* FROM fills f JOIN orders o ON o.id=f.order_id WHERE o.account_id=? ORDER BY f.created_at,f.id', (account_id,))]
            events = [dict(row) for row in c.execute('SELECT * FROM events WHERE account_id=? ORDER BY sequence', (account_id,))]
            journal = [dict(row) for row in c.execute('SELECT t.id,t.kind,t.reference,t.created_at,e.account,e.amount FROM journal_transactions t JOIN journal_entries e ON e.transaction_id=t.id WHERE t.account_id=? ORDER BY t.created_at,t.id,e.account', (account_id,))]
        return {'mode': 'PAPER', 'source': 'SYNTHETIC', 'account': account, 'orders': orders, 'fills': fills, 'events': events, 'journal': journal, 'audit': audit}

    def state(self):
        source=self.provider();quotes=self._quotes(source)
        with self.tx() as c:
            account=self._account(c);mark=self._mark(c,account,quotes);reserve=self._reservations(c,account['id'])
            orders=[dict(row)|{'legs':json.loads(row['legs'])} for row in c.execute('SELECT * FROM orders WHERE account_id=? ORDER BY created_at DESC,id LIMIT 200',(account['id'],))]
            positions=[dict(row)|{'legs':json.loads(row['legs'])} for row in c.execute('SELECT p.*,COUNT(l.id) lots FROM positions p JOIN position_lots l ON l.position_id=p.id WHERE p.account_id=? AND l.open=1 GROUP BY p.id',(account['id'],))]
            events=[dict(row)|{'payload':json.loads(row['payload'])} for row in c.execute('SELECT * FROM events WHERE account_id=? ORDER BY sequence DESC LIMIT 100',(account['id'],))]
            fills=[dict(row)|{'quotes':json.loads(row['quotes'])} for row in c.execute('SELECT f.* FROM fills f JOIN orders o ON o.id=f.order_id WHERE o.account_id=? ORDER BY f.created_at DESC LIMIT 200',(account['id'],))]
        return {'mode':'PAPER','source':'SYNTHETIC','model_version':MODEL,'charge_version':CHARGES,'account':dict(account)|{'equity':mark['equity'] if mark else None,'unrealized':mark['unrealized'] if mark else None,'reserved':reserve,'available_cash':max(0,account['cash']-reserve)},'orders':orders,'positions':positions,'fills':fills,'events':events,'connected':bool(source['session']['connected']),'source_session':source['session']['id'],'contracts':source['contracts'],'notice':'One modeled lot per instrument/side per two-second quote cycle; atomic multi-leg batches, not exchange queue/depth. ₹20 per leg per fill plus fixed slippage. Broker taxes, authoritative margin and settlement are not configured.'}
