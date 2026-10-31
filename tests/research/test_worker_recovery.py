"""Recovery is independent of analysis success; no broker or real waits."""
from datetime import date
from types import SimpleNamespace
import sqlite3

import pytest

from algooptionx.research.api import worker
from algooptionx.research.api.state import LiveState
from algooptionx.research.ingestion.quality import DataQualityError
from algooptionx.research.ingestion.option_chain import OptionChainError


@pytest.mark.parametrize('failure', [DataQualityError, OptionChainError, RuntimeError])
def test_refresh_recovers_after_repeated_analysis_failures(monkeypatch, tmp_path, failure):
    run_case(monkeypatch, tmp_path, failure)


def run_case(monkeypatch, tmp_path, failure=DataQualityError, cancel='none', refresh_fails=False, healthy=False):
    clock = [0.0]
    calls = {'refresh': [], 'prediction': [], 'cycles': 0, 'grades': 0}
    conn = sqlite3.connect(tmp_path / 'research.db')
    conn.execute('CREATE TABLE freshness(valid INTEGER)')
    conn.execute('INSERT INTO freshness VALUES(?)', (int(healthy),))

    class Stop:
        stopped = False
        def is_set(self): return self.stopped
        def wait(self, interval):
            clock[0] += interval
            if clock[0] >= 130: self.stopped = True
            return self.stopped
    stop = Stop()
    if cancel == 'before': stop.stopped = True

    def refresh(*args):
        calls['refresh'].append(clock[0])
        if cancel == 'refresh': stop.stopped = True
        if refresh_fails: raise RuntimeError('synthetic provider failure')
        if len(calls['refresh']) >= 2:
            conn.execute('UPDATE freshness SET valid=1')

    def cycle(*args):
        calls['cycles'] += 1
        clock[0] += 3.5  # fake provider pacing, never a real sleep
        if cancel == 'cycle': stop.stopped = True
        if not conn.execute('SELECT valid FROM freshness').fetchone()[0]:
            raise failure('synthetic rejected cycle')
        return SimpleNamespace(spot_price=24000)

    def predict(*args, **kwargs):
        assert conn.execute('SELECT valid FROM freshness').fetchone()[0] == 1
        calls['prediction'].append(clock[0])
        stop.stopped = True

    monkeypatch.setattr(worker.time, 'monotonic', lambda: clock[0])
    monkeypatch.setattr(worker.historical, 'catch_up_intraday', refresh)
    monkeypatch.setattr(worker.pipeline, 'run_cycle', cycle)
    monkeypatch.setattr(worker.prediction, 'evaluate_and_record', predict)
    monkeypatch.setattr(worker.prediction, 'grade_finished_sessions', lambda *a, **k: calls.__setitem__('grades', calls['grades'] + 1))
    monkeypatch.setattr(worker, 'OptionChainPoller', lambda *a: object())
    settings = SimpleNamespace(historical=SimpleNamespace(intraday_interval_min=5), polling=SimpleNamespace(option_chain_interval_sec=3.5, historical_refresh_interval_sec=60))
    state = LiveState()
    try:
        worker.run_worker(state, settings, object(), conn, 'NIFTY', '13', 'IDX_I', date(2026, 11, 3), 'fixture', stop)
        if cancel == 'before':
            assert calls['refresh'] == [] and calls['cycles'] == 0
        elif cancel == 'refresh':
            assert len(calls['refresh']) == 1 and calls['cycles'] == 0
        elif cancel == 'cycle':
            assert calls['prediction'] == []
        elif refresh_fails:
            assert calls['prediction'] == []
            assert state.snapshot()[1] is not None
            assert len(calls['refresh']) == 3
        elif healthy:
            assert len(calls['refresh']) == 1 and len(calls['prediction']) == 1
            assert state.snapshot()[1] is None
            assert calls['grades'] == 0  # prediction requested cancellation
        else:
            assert len(calls['refresh']) == 2
            assert calls['prediction'] and calls['cycles'] > 1
        assert all(b-a >= 60 for a,b in zip(calls['refresh'], calls['refresh'][1:]))
    finally:
        conn.close()


@pytest.mark.parametrize('cancel', ['before', 'refresh', 'cycle'])
def test_cancellation_at_operation_boundaries(monkeypatch, tmp_path, cancel):
    run_case(monkeypatch, tmp_path, cancel=cancel)


def test_failed_refresh_never_predicts_or_retries_immediately(monkeypatch, tmp_path):
    run_case(monkeypatch, tmp_path, refresh_fails=True)


def test_healthy_cycle_publishes_and_predicts(monkeypatch, tmp_path):
    run_case(monkeypatch, tmp_path, healthy=True)
