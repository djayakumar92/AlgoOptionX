"""Synthetic provider failures must not escape into diagnostic sinks."""
import logging
import socket
import traceback
from datetime import date, datetime
from types import SimpleNamespace

import pytest
from fastapi.testclient import TestClient

from algooptionx.research import auth
from algooptionx.research.api import app as api, backtest_worker
from algooptionx.research.api.state import BacktestState
from algooptionx.research.diagnostics import message, ProviderLogFilter
from algooptionx.research.ingestion import option_chain, option_ohlc, chart_candles, historical
from algooptionx.research.ingestion.live_feed import LiveFeed

MARKER = 'SYNTHETIC-PRIVATE-ACCOUNT-TOKEN-COOKIE'


@pytest.fixture(autouse=True)
def no_network(monkeypatch):
    def denied(*a, **k): raise AssertionError('Real network forbidden in diagnostic fixtures')
    monkeypatch.setattr(socket.socket, 'connect', denied)
    monkeypatch.setattr(socket, 'create_connection', denied)


class Provider:
    def __init__(self, mode): self.mode = mode
    def call(self, **kwargs):
        if self.mode == 'exception': raise RuntimeError(MARKER)
        return {'status':'failure', 'remarks': {'Authorization': MARKER, 'Cookie': MARKER}, 'data': {'client_id':MARKER}}
    expiry_list = option_chain = historical_daily_data = intraday_minute_data = call


@pytest.mark.parametrize('mode', ['payload', 'exception'])
@pytest.mark.parametrize('operation', ['expiry', 'chain', 'ohlc', 'chart', 'daily', 'intraday'])
def test_ingestion_failures_have_safe_domain_types(mode, operation, tmp_path, caplog):
    p = Provider(mode)
    operations = {
        'expiry': (option_chain.OptionChainError, lambda: option_chain.fetch_expiry_list(p,'13','IDX_I')),
        'chain': (option_chain.OptionChainError, lambda: option_chain.fetch_option_chain(p,'13','IDX_I',date(2026,11,3))),
        'ohlc': (option_ohlc.OptionOhlcError, lambda: option_ohlc.fetch_session_ohlc(p,'13',date(2026,10,30))),
        'chart': (chart_candles.ChartCandlesError, lambda: chart_candles.fetch_candles(p,'13','IDX_I','INDEX','5')),
        'daily': (historical.HistoricalDataError, lambda: historical.fetch_daily(None,p,'NIFTY','13','IDX_I','INDEX',date(2026,10,29),date(2026,10,30))),
        'intraday': (historical.HistoricalDataError, lambda: historical.backfill_intraday(None,p,'NIFTY','13','IDX_I','INDEX',5,datetime(2026,10,29),datetime(2026,10,30))),
    }
    kind,call=operations[operation]
    with pytest.raises(kind) as caught: call()
    formatted=''.join(traceback.format_exception(caught.type,caught.value,caught.tb))
    assert MARKER not in str(caught.value) + formatted + caplog.text
    assert 'FAILED' in str(caught.value)


@pytest.mark.parametrize('mode', ['payload','exception','success'])
def test_authentication_diagnostics_and_success_hide_identity(monkeypatch, caplog, mode):
    monkeypatch.setattr(auth, 'DhanContext', lambda *a: object())
    def positions():
        if mode=='exception': raise RuntimeError(MARKER)
        return {'status': 'success' if mode=='success' else 'failure', 'remarks': MARKER}
    monkeypatch.setattr(auth,'dhanhq',lambda *a: SimpleNamespace(get_positions=positions))
    settings=SimpleNamespace(client_id=MARKER,access_token=MARKER)
    with caplog.at_level(logging.INFO):
        if mode=='success': assert auth.build_client(settings) is not None
        else:
            with pytest.raises(auth.AuthError) as caught:auth.build_client(settings)
            assert MARKER not in ''.join(traceback.format_exception(caught.type,caught.value,caught.tb))
    assert MARKER not in caplog.text


def test_arbitrary_live_feed_error_is_never_formatted(caplog):
    class Unsafe:
        def __str__(self): raise AssertionError('Must not stringify provider error')
        __repr__=__str__
    LiveFeed._on_error(object(),object(),Unsafe())
    assert 'LIVE_FEED_FAILED' in caplog.text
    assert message(Unsafe()).startswith('RESEARCH_JOB_FAILED')


def test_provider_logger_denied_without_formatting():
    record=logging.LogRecord('dhanhq.transport',logging.ERROR,'',0,'%s',(MARKER,),None)
    assert not ProviderLogFilter().filter(record)
    safe=logging.LogRecord('algooptionx.research',logging.ERROR,'',0,'safe',(),None)
    assert ProviderLogFilter().filter(safe)


def test_chart_api_failure_is_safe_without_research_startup(monkeypatch):
    for name,value in {'under_security_id':'13','under_segment':'IDX_I','client':Provider('exception')}.items():
        monkeypatch.setattr(api.app.state,name,value,raising=False)
    client=TestClient(api.app)  # no lifespan context: no credentials, workers or provider startup
    response=client.get('/api/chart/candles?instrument=spot&interval=5')
    assert response.status_code==502
    assert MARKER not in response.text
    assert response.json()['detail'].startswith('CANDLE_FETCH_FAILED')
    assert client.get('/api/chart/candles?instrument=spot&interval=bad').status_code==400


def test_backtest_failure_persists_safe_error(monkeypatch, tmp_path, caplog):
    import sqlite3,json
    conn=sqlite3.connect(tmp_path/'failures.db')
    conn.execute('CREATE TABLE failures(payload TEXT)')
    def fail(*a,**k):raise RuntimeError(MARKER)
    monkeypatch.setattr(backtest_worker.repository,'has_journal_entries_for_trade_date',lambda *a:False)
    monkeypatch.setattr(backtest_worker,'backfill_journal',fail)
    monkeypatch.setattr(backtest_worker.repository,'insert_backtest_run',lambda c,row:c.execute('INSERT INTO failures VALUES(?)',(json.dumps(row),)))
    state=BacktestState()
    backtest_worker.run_backtest(state,object(),object(),conn,'NIFTY','13','IDX_I',date(2026,11,3),date(2026,10,29),date(2026,10,30))
    stored=conn.execute('SELECT payload FROM failures').fetchone()[0]
    assert MARKER not in stored + caplog.text + str(state.snapshot())
    assert 'BACKTEST_FAILED' in stored
    conn.close()


def test_sdk_root_log_origin_filtered_at_configured_handlers(tmp_path, caplog):
    import io
    from algooptionx.research.logging_setup import setup_logging
    root = logging.getLogger()
    stream = io.StringIO()
    handler = logging.StreamHandler(stream)
    original = {h: list(h.filters) for h in root.handlers}
    root.addHandler(handler)
    try:
        setup_logging(SimpleNamespace(log_dir=tmp_path, log_level=logging.INFO))
        # Root logging from an SDK source path bypasses name-only filters.
        exec(compile("import logging; logging.error('unsafe %s', marker)", '/installed/dhanhq/dhan_http.py', 'exec'), {'marker': MARKER})
        logging.getLogger('algooptionx.research').warning(message('CHAIN_FETCH_FAILED'))
        assert MARKER not in stream.getvalue() + caplog.text
        assert 'CHAIN_FETCH_FAILED' in stream.getvalue()
    finally:
        root.removeHandler(handler)
        handler.close()
        for h, filters in original.items(): h.filters[:] = filters


def test_live_feed_thread_and_lifecycle_failures_are_safe(monkeypatch, capsys, caplog):
    import threading
    from algooptionx.research.ingestion import live_feed
    uncaught = []
    monkeypatch.setattr(threading, 'excepthook', lambda args: uncaught.append(args))
    class Feed:
        def __init__(self, *args, **kwargs): assert kwargs['version'] == 'v2'
        def run(self): raise RuntimeError(MARKER)
        def close_connection(self): raise RuntimeError(MARKER)
    monkeypatch.setattr(live_feed, 'MarketFeed', Feed)
    feed = live_feed.LiveFeed(object(), [])
    thread = feed.start()
    thread.join(timeout=2)
    assert not thread.is_alive() and not uncaught
    with pytest.raises(RuntimeError) as caught: feed.stop()
    assert MARKER not in ''.join(traceback.format_exception(caught.type, caught.value, caught.tb))
    captured = capsys.readouterr()
    assert MARKER not in captured.out + captured.err + caplog.text
    assert 'LIVE_FEED_FAILED' in caplog.text


def test_structured_fields_are_allowlisted():
    from algooptionx.research.diagnostics import details
    assert details('CHAIN_FETCH_FAILED', attempt=2) == {'diagnostic_code':'CHAIN_FETCH_FAILED','retryable':True,'attempt':2}
    assert details(MARKER, attempt=MARKER) == {'diagnostic_code':'RESEARCH_JOB_FAILED','retryable':True}
