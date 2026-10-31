from __future__ import annotations

from algooptionx.research.diagnostics import message, details, provider_boundary

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

    @provider_boundary(RuntimeError, "LIVE_FEED_FAILED")
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
        logger.warning(message("LIVE_FEED_FAILED"), extra=details("LIVE_FEED_FAILED"))

    def _run(self) -> None:
        # SDK start() uses an unguarded thread. Own the target so credentials
        # in connection exceptions never reach threading.excepthook/stderr.
        try:
            self._feed.run()
        except Exception:
            self._on_error(self._feed, None)

    def start(self) -> threading.Thread:
        thread = threading.Thread(target=self._run, daemon=True)
        thread.start()
        return thread

    @provider_boundary(RuntimeError, "LIVE_FEED_FAILED")
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
