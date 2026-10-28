from __future__ import annotations

import logging
import time
from datetime import date

from dhanhq import dhanhq

from algooptionx.research.ingestion import option_chain
from algooptionx.research.ingestion.option_chain import OptionChainResult
from algooptionx.research.storage import repository

logger = logging.getLogger(__name__)


class OptionChainPoller:
    """Enforces DhanHQ's 1-request-per-3s limit per (underlying, expiry).

    Tracks last-call time per key with time.monotonic() and sleeps out the
    remainder before issuing the next call, padded above the raw 3.0s limit
    (via settings.polling.option_chain_interval_sec) to absorb clock drift.
    """

    def __init__(self, min_interval_sec: float):
        if min_interval_sec < 3.0:
            raise ValueError("min_interval_sec must be >= 3.0 (DhanHQ hard limit)")
        self._min_interval = min_interval_sec
        self._last_call: dict[tuple[str, str], float] = {}

    def poll(
        self,
        conn,
        client: dhanhq,
        underlying: str,
        under_security_id: str,
        under_segment: str,
        expiry: date,
    ) -> OptionChainResult:
        key = (underlying, expiry.isoformat())
        last = self._last_call.get(key)
        if last is not None:
            elapsed = time.monotonic() - last
            remaining = self._min_interval - elapsed
            if remaining > 0:
                time.sleep(remaining)

        result = option_chain.fetch_option_chain(client, under_security_id, under_segment, expiry)
        self._last_call[key] = time.monotonic()

        repository.insert_option_chain_snapshot(conn, underlying, expiry, result.ts, result.rows)
        logger.debug("Polled option chain: %s %s -> %d rows", underlying, expiry, len(result.rows))
        return result
