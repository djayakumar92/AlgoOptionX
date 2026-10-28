"""Thread-safe in-memory store for the latest result of a background worker cycle.

Each background worker thread (worker.py, hlc_worker.py) is the sole writer of its
own state; FastAPI route handlers are readers only. This is what keeps HTTP request
latency independent of the DhanHQ poll cadence -- routes never touch the DhanHQ
client directly.
"""

from __future__ import annotations

import threading
from dataclasses import dataclass
from typing import Generic, TypeVar

from algooptionx.research.pipeline import CycleResult
from algooptionx.research.signals.hlc_strategy import HlcResult

T = TypeVar("T")


class ResultState(Generic[T]):
    def __init__(self) -> None:
        self._lock = threading.Lock()
        self._result: T | None = None
        self._error: str | None = None
        self._error_ts: int | None = None

    def set_result(self, result: T) -> None:
        with self._lock:
            self._result = result
            self._error = None
            self._error_ts = None

    def set_error(self, message: str, ts: int) -> None:
        with self._lock:
            self._error = message
            self._error_ts = ts

    def snapshot(self) -> tuple[T | None, str | None, int | None]:
        with self._lock:
            return self._result, self._error, self._error_ts


LiveState = ResultState[CycleResult]
HlcState = ResultState[HlcResult]


@dataclass(frozen=True)
class BacktestProgress:
    status: str  # RUNNING | DONE | FAILED | IDLE
    current: int
    total: int
    current_date: str | None


class BacktestState:
    """Progress + result of the in-flight (or most recent) backtest run.
    Deliberately separate from ResultState -- a backtest needs live progress
    updates *during* a long-running pass, not just a final result/error, and
    a completed run's summary is also persisted to backtest_runs (see
    repository.py) for history across restarts; this only tracks the
    currently-running (or just-finished) one in memory."""

    def __init__(self) -> None:
        self._lock = threading.Lock()
        self._progress = BacktestProgress("IDLE", 0, 0, None)
        self._result: dict | None = None
        self._error: str | None = None

    def start(self, total: int) -> None:
        with self._lock:
            self._progress = BacktestProgress("RUNNING", 0, total, None)
            self._result = None
            self._error = None

    def update(self, current: int, current_date: str) -> None:
        with self._lock:
            total = self._progress.total
            self._progress = BacktestProgress("RUNNING", current, total, current_date)

    def finish(self, result: dict) -> None:
        with self._lock:
            total = self._progress.total
            self._progress = BacktestProgress("DONE", total, total, None)
            self._result = result
            self._error = None

    def fail(self, message: str) -> None:
        with self._lock:
            current, total = self._progress.current, self._progress.total
            self._progress = BacktestProgress("FAILED", current, total, None)
            self._error = message

    def snapshot(self) -> tuple[BacktestProgress, dict | None, str | None]:
        with self._lock:
            return self._progress, self._result, self._error
