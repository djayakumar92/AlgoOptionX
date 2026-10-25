"""Structural interfaces for read-only market-data providers.

Strategy and ingestion code depends on these methods, not on a broker SDK
class. Implementations must expose market-data methods only to research code.
"""
from __future__ import annotations

from collections.abc import Mapping
from typing import Any, Protocol


class MarketDataProvider(Protocol):
    def historical_daily_data(self, **kwargs: Any) -> Mapping[str, Any]: ...
    def intraday_minute_data(self, **kwargs: Any) -> Mapping[str, Any]: ...
    def expiry_list(self, **kwargs: Any) -> Mapping[str, Any]: ...
    def option_chain(self, **kwargs: Any) -> Mapping[str, Any]: ...
