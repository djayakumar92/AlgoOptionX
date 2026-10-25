from __future__ import annotations

import logging
import threading

from dhanhq import DhanContext, MarketFeed

logger = logging.getLogger(__name__)


class LiveFeed:
    """Thin wrapper around the official SDK's WebSocket marketfeed client.

    Ticks are cached in memory only (keyed by security_id) to drive dashboard
    responsiveness between option-chain polls -- they are NOT persisted or used
    for signal computation. That keeps the binary-protocol parsing (handled by
    the SDK) isolated from the analytical core, which reads SQLite snapshots.
    """

    def __init__(self, context: DhanContext, instruments: list[tuple[int, str, int]]):
        self._cache: dict[str, dict] = {}
        self._lock = threading.Lock()
        self._feed = MarketFeed(
            context, instruments, version="v2", on_message=self._on_message, on_error=self._on_error
        )

    def _on_message(self, feed: MarketFeed, data: dict) -> None:
        if not data or "security_id" not in data:
            return
        with self._lock:
            self._cache[str(data["security_id"])] = data

    def _on_error(self, feed: MarketFeed, error: Exception) -> None:
        logger.warning("Live feed error: %s", error)

    def start(self) -> threading.Thread:
        return self._feed.start()

    def stop(self) -> None:
        self._feed.close_connection()

    def get_ltp(self, security_id: str) -> float | None:
        with self._lock:
            entry = self._cache.get(str(security_id))
        if entry and "LTP" in entry:
            try:
                return float(entry["LTP"])
            except (TypeError, ValueError):
                return None
        return None

    def snapshot(self) -> dict[str, dict]:
        with self._lock:
            return dict(self._cache)
