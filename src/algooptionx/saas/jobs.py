"""Durable, tenant-owned synthetic rule replays; never inferred historical fills."""
import hashlib
import json
import operator
import time
import uuid
from datetime import datetime
from fastapi import APIRouter, HTTPException, Request
from pydantic import Field
from algooptionx.demo import market
from .api import TenantContext, principal, require_tenant_context
from .resources import StrategyDocument

router = APIRouter(prefix='/api/jobs')
MODEL = 'CAUSAL-RULE-REPLAY-1'
NOTICE = 'Synthetic rule observations only. No historical dataset, fills, return, win rate or profitability is inferred. This job consumes no paid credits.'


class ReplayJob(TenantContext):
    version_id: str = Field(pattern=r'^[a-f0-9]{32}$')
    key: str = Field(min_length=8, max_length=160)
    expected_source_session: str = Field(min_length=1, max_length=160)


def encoded(value):
    return json.dumps(value, sort_keys=True, separators=(',', ':'), allow_nan=False)


def evaluate(snapshot):
    document = StrategyDocument.model_validate(snapshot['strategy'])
    if not document.groups:
        return {'evaluations': [], 'matched': 0, 'unavailable': 0, 'notice': 'This version has no entry rules. Manual templates do not generate automated signals.'}
    comparisons = {'gt': operator.gt, 'gte': operator.ge, 'lt': operator.lt, 'lte': operator.le, 'eq': operator.eq}
    rows = []
    # Only completed observations in the captured prefix are visible at each decision.
    for decision in snapshot['bars']['5']:
        available = {key: [bar for bar in bars if bar['time'] <= decision['time']] for key, bars in snapshot['bars'].items()}
        groups = []
        evidence = []
        for group in document.groups:
            conditions = []
            for condition in group.conditions:
                bars = available[condition.timeframe]
                observed = None
                if bars:
                    last = bars[-1]
                    if condition.field in ('close', 'volume', 'vwap'):
                        observed = last[condition.field]
                    elif condition.field == 'ema9':
                        observed = last['ema9'] if last['ema_warmup'] >= 9 else None
                    elif condition.field == 'gap':
                        observed = snapshot['opening_gap_points']
                    else:
                        count = 30 // int(condition.timeframe)
                        recent = bars[-count:]
                        if len(recent) == count and (datetime.fromisoformat(recent[-1]['time']) - datetime.fromisoformat(recent[0]['time'])).total_seconds() == (count - 1) * int(condition.timeframe) * 60:
                            change = recent[-1]['close'] - recent[0]['open']
                            observed = ('BULLISH' if change > 10 else 'BEARISH' if change < -10 else 'SIDEWAYS') if condition.field == 'direction' else change
                result = None if observed is None else comparisons[condition.operator](observed, condition.value)
                conditions.append(result)
                evidence.append({'field': condition.field, 'timeframe': condition.timeframe, 'operator': condition.operator, 'threshold': condition.value, 'observed': observed, 'matched': result})
            # Incomplete inputs fail closed even in an OR group.
            groups.append(None if any(value is None for value in conditions) else (all(conditions) if group.operator == 'AND' else any(conditions)))
        matched = None if any(value is None for value in groups) else (all(groups) if document.group_operator == 'AND' else any(groups))
        rows.append({'as_of': decision['time'], 'matched': matched, 'evidence': evidence})
    return {'evaluations': rows, 'matched': sum(row['matched'] is True for row in rows), 'unavailable': sum(row['matched'] is None for row in rows), 'notice': NOTICE}


class JobStore:
    def __init__(self, identity):
        self.identity = identity
        with identity.tx() as c:
            c.execute('CREATE TABLE IF NOT EXISTS research_jobs(id TEXT PRIMARY KEY,tenant_id TEXT NOT NULL REFERENCES tenants(id),created_by TEXT NOT NULL REFERENCES users(id),request_key TEXT NOT NULL,version_id TEXT NOT NULL,status TEXT NOT NULL,snapshot TEXT NOT NULL,input_hash TEXT NOT NULL,result TEXT,attempts INTEGER NOT NULL DEFAULT 0,created_at INTEGER NOT NULL,updated_at INTEGER NOT NULL,UNIQUE(tenant_id,request_key))')
            # Single-process local worker: interrupted jobs resume from immutable input.
            c.execute("UPDATE research_jobs SET status='queued' WHERE status='running' AND attempts<3")
            c.execute("UPDATE research_jobs SET status='failed' WHERE status='running' AND attempts>=3")

    def create(self, user, body, state):
        with self.identity.tx() as c:
            old = c.execute('SELECT id,version_id,snapshot FROM research_jobs WHERE tenant_id=? AND request_key=?', (user['tenant_id'], body.key)).fetchone()
            if old:
                if old['version_id'] != body.version_id or json.loads(old['snapshot'])['source_session'] != body.expected_source_session:
                    raise HTTPException(409, 'This request key belongs to a different replay.')
                return {'id': old['id']}
            if state['session']['id'] != body.expected_source_session:
                raise HTTPException(409, 'The source session changed. Review it before starting a replay.')
            version = c.execute('SELECT v.document,v.content_hash FROM strategy_versions v JOIN saved_strategies s ON s.id=v.strategy_id AND s.tenant_id=v.tenant_id WHERE v.id=? AND v.tenant_id=? AND s.archived=0', (body.version_id, user['tenant_id'])).fetchone()
            if not version:
                raise HTTPException(404, 'Strategy version not found.')
            if c.execute("SELECT COUNT(*) FROM research_jobs WHERE tenant_id=? AND status IN ('queued','running')", (user['tenant_id'],)).fetchone()[0] >= 5:
                raise HTTPException(409, 'Five research jobs are already pending.')
            if c.execute('SELECT COUNT(*) FROM research_jobs WHERE tenant_id=?', (user['tenant_id'],)).fetchone()[0] >= 1000:
                raise HTTPException(409, 'The local research history limit is reached. Export and configure retention before adding jobs.')
            scenario, tick = state['session']['scenario'], state['session']['quote_tick']
            snapshot = {'model': MODEL, 'source': 'SYNTHETIC', 'source_version': market.REVISION, 'source_session': state['session']['id'], 'quote_tick': tick, 'strategy': json.loads(version['document']), 'strategy_hash': version['content_hash'], 'opening_gap_points': market.SCENARIOS[scenario][2], 'bars': {str(interval): market.candles(scenario, tick, interval) for interval in (5,30)}}
            payload = encoded(snapshot)
            job_id = uuid.uuid4().hex
            now = int(time.time())
            c.execute("INSERT INTO research_jobs VALUES(?,?,?,?,?,'queued',?,?,NULL,0,?,?)", (job_id, user['tenant_id'], user['user_id'], body.key, body.version_id, payload, hashlib.sha256(payload.encode()).hexdigest(), now, now))
            self.identity.event(c, user['user_id'], 'RESEARCH_REPLAY_QUEUED')
        return {'id': job_id}

    def process(self):
        with self.identity.tx() as c:
            row = c.execute("SELECT id,snapshot,input_hash FROM research_jobs WHERE status='queued' ORDER BY created_at,id LIMIT 1").fetchone()
            if not row:
                return
            c.execute("UPDATE research_jobs SET status='running',attempts=attempts+1,updated_at=? WHERE id=?", (int(time.time()), row['id']))
        try:
            if hashlib.sha256(row['snapshot'].encode()).hexdigest() != row['input_hash']:
                raise ValueError('Input hash mismatch')
            result = encoded(evaluate(json.loads(row['snapshot'])))
            status = 'completed'
        except Exception:
            result, status = encoded({'notice': 'Replay failed. Preserve the immutable input for diagnosis; no result was inferred.'}), 'failed'
        with self.identity.tx() as c:
            c.execute("UPDATE research_jobs SET status=?,result=?,updated_at=? WHERE id=? AND status='running'", (status, result, int(time.time()), row['id']))


@router.get('')
def jobs(request: Request):
    user = principal(request)
    with request.app.state.identity.tx() as c:
        rows = c.execute('SELECT id,version_id,status,input_hash,attempts,created_at,updated_at FROM research_jobs WHERE tenant_id=? ORDER BY created_at DESC,id DESC LIMIT 100', (user['tenant_id'],)).fetchall()
    return {'jobs': [dict(row) for row in rows], 'notice': NOTICE}


@router.post('')
def create(body: ReplayJob, request: Request):
    user = principal(request)
    require_tenant_context(request, body.expected_tenant_id)
    if user['role'] == 'viewer':
        raise HTTPException(403, 'This membership cannot start research jobs.')
    request.app.state.identity.rate_limit('research-jobs:' + user['tenant_id'], 30, 3600)
    with request.app.state.tenants.market_lock(user['tenant_id']):
        state = request.app.state.tenants.get(user['tenant_id'])[1].state()
        return request.app.state.jobs.create(user, body, state)


@router.get('/{job_id}')
def detail(job_id: str, request: Request):
    user = principal(request)
    with request.app.state.identity.tx() as c:
        row = c.execute('SELECT * FROM research_jobs WHERE id=? AND tenant_id=?', (job_id, user['tenant_id'])).fetchone()
    if not row:
        raise HTTPException(404, 'Research job not found.')
    snapshot = json.loads(row['snapshot'])
    return {key: row[key] for key in ('id','version_id','status','input_hash','attempts','created_at','updated_at')} | {'input': snapshot, 'result': json.loads(row['result']) if row['result'] else None, 'notice': NOTICE}


@router.post('/{job_id}/cancel')
def cancel(job_id: str, body: TenantContext, request: Request):
    user = principal(request)
    require_tenant_context(request, body.expected_tenant_id)
    if user['role'] == 'viewer':
        raise HTTPException(403, 'This membership cannot cancel research jobs.')
    with request.app.state.identity.tx() as c:
        row = c.execute('SELECT status FROM research_jobs WHERE id=? AND tenant_id=?', (job_id,user['tenant_id'])).fetchone()
        if not row:
            raise HTTPException(404, 'Research job not found.')
        if row['status'] in ('queued','running'):
            c.execute("UPDATE research_jobs SET status='cancelled',updated_at=? WHERE id=? AND tenant_id=?", (int(time.time()), job_id, user['tenant_id']))
            request.app.state.identity.event(c, user['user_id'], 'RESEARCH_REPLAY_CANCELLED')
    return {'id': job_id, 'status': 'cancelled' if row['status'] in ('queued','running') else row['status']}
