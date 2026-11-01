"""Transactional offline demo: fixed fixtures, bounded spreads and separate history."""
from __future__ import annotations

from contextlib import closing, contextmanager
from datetime import timedelta
import hashlib
import json
from pathlib import Path
import sqlite3
import uuid

from . import market
from .pricing import STRATEGIES, VERSION, FEE, LOT, fill, strategy_value

CAPITAL = 50_000_000


class DemoError(ValueError):
    pass


def encoded(value):
    return json.dumps(value,sort_keys=True,separators=(',',':'),allow_nan=False)


class DemoEngine:
    def __init__(self, path, forbidden_paths=()):
        destination=Path(path)
        for other in forbidden_paths:
            other=Path(other)
            if destination.resolve()==other.resolve() or destination.exists() and other.exists() and destination.samefile(other):
                raise DemoError('Demo storage must not alias paper or research history.')
        self.path=str(destination)
        destination.parent.mkdir(parents=True,exist_ok=True)
        with closing(sqlite3.connect(self.path,timeout=15,isolation_level=None)) as c:
            tables={row[0] for row in c.execute("SELECT name FROM sqlite_master WHERE type='table'")}
            if tables-{'demo_accounts','demo_active','demo_positions','demo_events','demo_commands','sqlite_sequence'}:
                raise DemoError('Existing non-demo database rejected; no history was migrated.')
            c.executescript('''BEGIN IMMEDIATE;
            CREATE TABLE IF NOT EXISTS demo_accounts(id TEXT PRIMARY KEY, scenario TEXT NOT NULL,
              tick INTEGER NOT NULL, quote_tick INTEGER NOT NULL, connected INTEGER NOT NULL,
              killed INTEGER NOT NULL DEFAULT 0, kill_error TEXT NOT NULL DEFAULT '',
              cash INTEGER NOT NULL, realized INTEGER NOT NULL DEFAULT 0, fees INTEGER NOT NULL DEFAULT 0);
            CREATE TABLE IF NOT EXISTS demo_active(id INTEGER PRIMARY KEY CHECK(id=1),account_id TEXT NOT NULL);
            CREATE TABLE IF NOT EXISTS demo_positions(id TEXT PRIMARY KEY, account_id TEXT NOT NULL,
              data TEXT NOT NULL,status TEXT NOT NULL, opened_tick INTEGER NOT NULL, closed_tick INTEGER,
              pnl INTEGER, note TEXT NOT NULL DEFAULT '', category TEXT NOT NULL DEFAULT 'Plan followed');
            CREATE TABLE IF NOT EXISTS demo_events(seq INTEGER PRIMARY KEY AUTOINCREMENT,account_id TEXT NOT NULL,
              tick INTEGER NOT NULL,kind TEXT NOT NULL,payload TEXT NOT NULL,previous_hash TEXT NOT NULL,hash TEXT NOT NULL);
            CREATE TABLE IF NOT EXISTS demo_commands(account_id TEXT NOT NULL,key TEXT NOT NULL,
              request TEXT NOT NULL,response TEXT NOT NULL,PRIMARY KEY(account_id,key));
            COMMIT;''')
        with self.tx() as c:
            active=c.execute('SELECT account_id FROM demo_active WHERE id=1').fetchone()
            if active is None:
                if c.execute('SELECT 1 FROM demo_accounts').fetchone():
                    raise DemoError('Incomplete demo funding state; preserve database for diagnosis.')
                self._new(c,'bullish')
            else:
                a=self._account(c)
                if not a or c.execute("SELECT count(*) FROM demo_events WHERE account_id=? AND kind='FUNDING'",(a['id'],)).fetchone()[0]!=1:
                    raise DemoError('Invalid demo funding history; no balance was inferred.')

    @contextmanager
    def tx(self):
        c=sqlite3.connect(self.path,timeout=15,isolation_level=None);c.row_factory=sqlite3.Row
        try:
            c.execute('BEGIN IMMEDIATE');yield c;c.commit()
        except BaseException:
            c.rollback();raise
        finally:c.close()

    def _account(self,c):
        row=c.execute('SELECT * FROM demo_accounts WHERE id=(SELECT account_id FROM demo_active WHERE id=1)').fetchone()
        return dict(row) if row else None

    def _event(self,c,a,kind,payload):
        row=c.execute('SELECT hash FROM demo_events WHERE account_id=? ORDER BY seq DESC LIMIT 1',(a['id'],)).fetchone()
        previous=row[0] if row else ''
        body={'account_id':a['id'],'tick':a['tick'],'kind':kind,'payload':payload}
        sha=hashlib.sha256((previous+encoded(body)).encode()).hexdigest()
        c.execute('INSERT INTO demo_events(account_id,tick,kind,payload,previous_hash,hash) VALUES(?,?,?,?,?,?)',
                  (a['id'],a['tick'],kind,encoded(payload),previous,sha))

    def _new(self,c,scenario):
        if scenario not in market.SCENARIOS:raise DemoError('Unknown deterministic scenario.')
        identity=str(uuid.uuid4());connected=scenario!='disconnection'
        c.execute('INSERT INTO demo_accounts(id,scenario,tick,quote_tick,connected,cash) VALUES(?,?,?,?,?,?)',
                  (identity,scenario,60,60,int(connected),CAPITAL))
        c.execute('INSERT OR REPLACE INTO demo_active VALUES(1,?)',(identity,))
        a=self._account(c);self._event(c,a,'FUNDING',{'amount':CAPITAL,'scenario':scenario,'message':'New preserved synthetic session: ₹5,00,000 virtual capital.'})
        return identity

    def _positions(self,c,a):
        return [dict(row)|{'data':json.loads(row['data'])} for row in c.execute("SELECT * FROM demo_positions WHERE account_id=? AND status='OPEN' ORDER BY rowid",(a['id'],))]

    def _closing(self,p,quotes):
        by_id={q['id']:q for q in quotes};data=p['data']
        legs=[{**leg,'exit':fill(by_id[leg['instrument']],-leg['side'])} for leg in data['legs']]
        flow=sum(leg['side']*leg['exit']*leg['quantity'] for leg in legs)-len(legs)*FEE
        return flow,legs

    def _accounting(self,c,a,quotes):
        positions=self._positions(c,a);by_id={q['id']:q for q in quotes}
        mark=sum(leg['side']*by_id[leg['instrument']]['mark']*leg['quantity'] for p in positions for leg in p['data']['legs'])
        liquidation=a['cash']+sum(self._closing(p,quotes)[0] for p in positions)
        equity=a['cash']+mark;reserve=sum(p['data']['reserve'] for p in positions)
        return {'capital':CAPITAL,'cash':a['cash'],'equity':equity,'liquidation_equity':liquidation,
            'pnl':equity-CAPITAL,'realized':a['realized'],'unrealized':equity-CAPITAL-a['realized'],
            'fees':a['fees'],'reserve':reserve,'available_risk_capital':max(0,CAPITAL-reserve),
            'daily_loss':max(0,CAPITAL-liquidation),'open_count':len(positions)}

    def _limits(self,a):
        return {'max_positions':3,'trade_reserve_limit':1 if a['scenario']=='risk-rejection' else CAPITAL//100,
                'aggregate_reserve_limit':CAPITAL*40//100,'daily_loss_limit':CAPITAL*2//100}

    def _preview(self,c,a,draft):
        strategy=draft.get('strategy','bull-put');lots=draft.get('lots',1);expiry=draft.get('expiry',market.EXPIRIES[0])
        atm=round(market.spot(a['scenario'],a['quote_tick'])/5000)*50
        defaults={'bull-put':[atm-50,atm-100],'bear-call':[atm+50,atm+100],'iron-condor':[atm-50,atm-100,atm+50,atm+100]}
        strikes=draft.get('strikes') or defaults.get(strategy,[])
        quotes=market.chain(a['scenario'],a['quote_tick'])
        result=strategy_value(strategy,strikes,lots,quotes,expiry)
        identity={'session_id':a['id'],'scenario':a['scenario'],'revision':market.REVISION,'tick':a['tick'],
            'quote_tick':a['quote_tick'],'pricing':VERSION,'strategy':strategy,'lots':lots,'expiry':expiry,
            'strikes':strikes,'legs':result['legs'],'entry_fees':result['entry_fees'],'exit_fees':result['exit_fees'],
            'exit_friction':result['exit_friction']}
        result['quote_token']=hashlib.sha256(encoded(identity).encode()).hexdigest()
        accounting=self._accounting(c,a,quotes);limits=self._limits(a);errors=[]
        if a['killed']:errors.append('Emergency stop is latched; create a new flat session.')
        if not a['connected']:errors.append('Synthetic data disconnected; new entries are blocked.')
        if a['tick']>=market.MAX_TICK:errors.append('Synthetic session ended; create a new flat session.')
        if result['max_profit']<=0:errors.append('Round-trip costs leave no positive maximum profit.')
        if result['reserve']>limits['trade_reserve_limit']:errors.append(f"Strategy reserve {result['reserve']/100:.2f} exceeds per-trade limit {limits['trade_reserve_limit']/100:.2f} rupees.")
        if accounting['open_count']>=limits['max_positions']:errors.append('Maximum three open strategies.')
        if accounting['reserve']+result['reserve']>min(limits['aggregate_reserve_limit'],max(0,accounting['liquidation_equity'])):errors.append('Aggregate reserves exceed the capital/liquidation-equity limit.')
        if accounting['daily_loss']>=limits['daily_loss_limit']:errors.append('Daily loss limit reached; new entries locked.')
        result.update(errors=errors,valid=not errors,limits=limits,session_id=a['id'],tick=a['tick'],quote_tick=a['quote_tick'])
        return result

    def preview(self,draft):
        with self.tx() as c:return self._preview(c,self._account(c),draft)

    def _exit(self,c,a,p,quotes,reason):
        flow,legs=self._closing(p,quotes);pnl=p['data']['entry_net_credit']+flow
        c.execute('UPDATE demo_accounts SET cash=cash+?,realized=realized+?,fees=fees+? WHERE id=?',
                  (flow,pnl,len(legs)*FEE,a['id']))
        data={**p['data'],'exit_legs':legs,'exit_cashflow':flow,'exit_reason':reason,
              'quote_source':'CURRENT_SYNTHETIC' if a['connected'] else 'LAST_VALID_SYNTHETIC',
              'exit_quote_tick':a['quote_tick']}
        c.execute("UPDATE demo_positions SET status='CLOSED',closed_tick=?,pnl=?,data=? WHERE id=?",(a['tick'],pnl,encoded(data),p['id']))
        self._event(c,a,'CLOSE',{'position_id':p['id'],'pnl':pnl,'reason':reason,'quote_tick':a['quote_tick'],'quote_source':data['quote_source'],'message':'All strategy legs closed atomically.'})
        return pnl

    def _perform(self,c,a,body):
        action=body['action'];quotes=market.chain(a['scenario'],a['quote_tick'])
        if action=='open':
            result=self._preview(c,a,body.get('draft') or {})
            if result['quote_token']!=body.get('quote_token'):raise DemoError('Quote is stale; refresh preview and confirm again.')
            if result['errors']:raise DemoError(' '.join(result['errors']))
            identity=str(uuid.uuid4());result['entry_reason']=body.get('reason') or 'User-confirmed defined-risk synthetic strategy.'
            c.execute("INSERT INTO demo_positions(id,account_id,data,status,opened_tick) VALUES(?,?,?,'OPEN',?)",(identity,a['id'],encoded(result),a['tick']))
            c.execute('UPDATE demo_accounts SET cash=cash+?,fees=fees+? WHERE id=?',(result['entry_net_credit'],result['entry_fees'],a['id']))
            self._event(c,a,'OPEN',{'position_id':identity,'strategy':result['strategy'],'entry_net_credit':result['entry_net_credit'],'reserve':result['reserve'],'message':'All defined-risk legs filled atomically at synthetic executable quotes.'})
            return {'position_id':identity,'message':'Simulated strategy filled.'}
        if action=='close':
            if not a['connected']:raise DemoError('Reconnect first or use emergency close with labeled last-valid quotes.')
            p=next((p for p in self._positions(c,a) if p['id']==body.get('position_id')),None)
            if p is None:raise DemoError('Open strategy not found in the active session.')
            return {'pnl':self._exit(c,a,p,quotes,'User-confirmed paper exit.'),'message':'Strategy closed and recorded.'}
        if action=='step':
            tick=min(market.MAX_TICK,a['tick']+body.get('steps',5))
            c.execute('UPDATE demo_accounts SET tick=?,quote_tick=? WHERE id=?',(tick,tick if a['connected'] else a['quote_tick'],a['id']))
            self._event(c,{**a,'tick':tick},'STEP',{'message':'Synthetic timeline advanced. Quotes remain frozen while disconnected.'})
        elif action in ('reconnect','disconnect'):
            connected=action=='reconnect'
            c.execute('UPDATE demo_accounts SET connected=?,quote_tick=? WHERE id=?',(int(connected),a['tick'] if connected else a['quote_tick'],a['id']))
            self._event(c,a,'CONNECTION',{'connected':connected,'message':'Synthetic fixture reconnected.' if connected else 'Synthetic fixture disconnected; last-valid quotes retained.'})
        elif action=='session':
            if self._positions(c,a):raise DemoError('Close all strategies before changing scenario; history is preserved.')
            return {'session_id':self._new(c,body.get('scenario','bullish')),'message':'New synthetic session created; previous history preserved.'}
        elif action=='note':
            p=c.execute('SELECT * FROM demo_positions WHERE id=?',(body.get('position_id'),)).fetchone()
            if p is None:raise DemoError('Journal trade not found.')
            note=body.get('note','');category=body.get('category','Plan followed')
            if not isinstance(note,str) or len(note)>2000 or category not in ('Plan followed','Sizing','Timing','Other'):raise DemoError('Invalid journal note or mistake category.')
            c.execute('UPDATE demo_positions SET note=?,category=? WHERE id=?',(note,category,p['id']))
            self._event(c,a,'NOTE',{'position_id':p['id'],'category':category,'message':'Review note saved; economic history unchanged.'})
        else:raise DemoError('Unsupported demo command.')
        return {'message':'Synthetic session updated.'}

    def command(self,body):
        # A kill latch commits before flattening and survives any subsequent failure.
        if body['action']=='kill':return self._kill(body)
        with self.tx() as c:
            a=self._account(c);saved=self._duplicate(c,body)
            if saved is not None:return saved
            if body['session_id']!=a['id']:raise DemoError('Active session changed; reload before submitting.')
            # Savepoint ensures a late audit/storage failure cannot commit part of an economic effect.
            c.execute('SAVEPOINT economic_effect')
            try:
                result=self._perform(c,a,body);response={'ok':True,**result}
                c.execute('RELEASE economic_effect')
            except (ValueError,sqlite3.Error) as error:
                c.execute('ROLLBACK TO economic_effect');c.execute('RELEASE economic_effect')
                if isinstance(error,sqlite3.Error):raise
                response={'ok':False,'error':str(error)}
                self._event(c,a,'REJECTED',{'action':body['action'],'message':str(error)})
            self._save_command(c,body,response)
            return response

    def _duplicate(self,c,body):
        previous=c.execute('SELECT request,response FROM demo_commands WHERE account_id=? AND key=?',(body['session_id'],body['key'])).fetchone()
        if previous:
            if previous['request']!=encoded(body):raise DemoError('Idempotency key was reused with different fields.')
            return json.loads(previous['response'])
        return None

    def _save_command(self,c,body,response):
        c.execute('INSERT INTO demo_commands VALUES(?,?,?,?)',(body['session_id'],body['key'],encoded(body),encoded(response)))

    def _kill(self,body):
        with self.tx() as c:
            a=self._account(c);saved=self._duplicate(c,body)
            if saved is not None:return saved
            if body['session_id']!=a['id']:raise DemoError('Active session changed; reload before emergency stop.')
            c.execute('UPDATE demo_accounts SET killed=1,kill_error=? WHERE id=?',('Emergency flatten pending.',a['id']))

        try:
            with self.tx() as c:
                a=self._account(c)
                saved=self._duplicate(c,body)
                if saved is not None:return saved
                if a['id']!=body['session_id']:raise DemoError('Session changed after emergency latch; prior session remains locked.')
                self._event(c,a,'KILL_LATCH',{'message':'Emergency stop was durably latched before flattening.'})
                quotes=market.chain(a['scenario'],a['quote_tick'])
                for p in self._positions(c,a):self._exit(c,a,p,quotes,'Simulation emergency stop.')
                c.execute("UPDATE demo_accounts SET kill_error='' WHERE id=?",(a['id'],))
                response={'ok':True,'message':'Simulation stopped; all legs closed atomically. Entries remain locked.'}
                self._save_command(c,body,response)
                return response
        except Exception:
            with self.tx() as c:
                c.execute('UPDATE demo_accounts SET kill_error=? WHERE id=?',('Emergency flatten failed; entries remain locked. Retry emergency close after diagnosis.',body['session_id']))
            raise

    def state(self):
        with self.tx() as c:
            a=self._account(c);quotes=market.chain(a['scenario'],a['quote_tick']);accounting=self._accounting(c,a,quotes)
            positions=[]
            for p in self._positions(c,a):
                flow,_=self._closing(p,quotes)
                positions.append({**p,'liquidation_pnl':p['data']['entry_net_credit']+flow})
            journal=[dict(row)|{'data':json.loads(row['data'])} for row in c.execute('SELECT p.*,a.scenario FROM demo_positions p JOIN demo_accounts a ON a.id=p.account_id ORDER BY p.rowid DESC LIMIT 50')]
            events=[dict(row)|{'payload':json.loads(row['payload'])} for row in c.execute('SELECT * FROM demo_events WHERE account_id=? ORDER BY seq DESC LIMIT 150',(a['id'],))]
            return {'mode':'DEMO','source':'SYNTHETIC','revision':market.REVISION,'pricing_version':VERSION,
                'session':{**a,'time':(market.START+timedelta(minutes=a['tick'])).isoformat(),'quote_time':(market.START+timedelta(minutes=a['quote_tick'])).isoformat()},
                'scenarios':[{'id':key,'label':value[0]} for key,value in market.SCENARIOS.items()],
                'account':accounting,'limits':self._limits(a),'spot':market.spot(a['scenario'],a['quote_tick'])/100,
                'expiries':list(market.EXPIRIES),'contracts':quotes,
                'candles':{'5':market.candles(a['scenario'],a['quote_tick'],5),'30':market.candles(a['scenario'],a['quote_tick'],30)},
                'analysis':market.analysis(a['scenario'],a['quote_tick']),'positions':positions,'journal':journal,'events':events,
                'assumptions':{'rate':.06,'iv':.18,'lot_size':LOT,'fee_per_leg_fill':FEE,'spread':80,'slippage':5,
                    'disclaimer':'Synthetic European fixture only. No real market data, trained prediction, broker margin or live execution.'}}

    def audit(self):
        with self.tx() as c:
            return {'source':'SYNTHETIC','integrity':'Local hash chains only, not externally anchored attestations.',
                'sessions':[dict(r) for r in c.execute('SELECT id,scenario,tick,killed FROM demo_accounts')],
                'events':[dict(r)|{'payload':json.loads(r['payload'])} for r in c.execute('SELECT * FROM demo_events ORDER BY seq')],
                'trades':[dict(r)|{'data':json.loads(r['data'])} for r in c.execute('SELECT * FROM demo_positions ORDER BY rowid')]}
