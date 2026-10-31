from __future__ import annotations

from algooptionx.research.diagnostics import message, provider_boundary

import logging
from dataclasses import dataclass
from datetime import date, datetime

from algooptionx.research.ingestion.providers import MarketDataProvider
from algooptionx.research.ingestion.quality import validate_option_chain

logger = logging.getLogger(__name__)


class OptionChainError(RuntimeError):
    pass


@dataclass(frozen=True)
class OptionChainResult:
    ts: int
    spot_price: float
    rows: list[dict]  # matches storage.repository.insert_option_chain_snapshot row shape


@provider_boundary(OptionChainError, "CHAIN_FETCH_FAILED")
def fetch_expiry_list(client: MarketDataProvider, under_security_id: str, under_segment: str) -> list[date]:
    resp = client.expiry_list(under_security_id=int(under_security_id), under_exchange_segment=under_segment)
    if resp.get("status") != "success":
        raise OptionChainError(message("CHAIN_FETCH_FAILED"))
    # The SDK wraps the raw HTTP body (itself shaped {"data": [...], "status": ...})
    # inside its own {"status", "remarks", "data"} envelope, so the real list is
    # one level deeper than the DhanHQ docs example suggests: resp["data"]["data"].
    dates = resp["data"]["data"]
    return [datetime.strptime(d, "%Y-%m-%d").date() for d in dates]


@provider_boundary(OptionChainError, "CHAIN_FETCH_FAILED")
def fetch_option_chain(
    client: MarketDataProvider, under_security_id: str, under_segment: str, expiry: date
) -> OptionChainResult:
    """Single option-chain poll. Caller (scheduler) is responsible for the 3s/request throttle."""
    resp = client.option_chain(
        under_security_id=int(under_security_id),
        under_exchange_segment=under_segment,
        expiry=expiry.isoformat(),
    )
    if resp.get("status") != "success":
        raise OptionChainError(message("CHAIN_FETCH_FAILED"))

    # Same double-wrapping as expiry_list: resp["data"] is the raw HTTP body,
    # which itself has a "data" key holding {last_price, oc}.
    data = resp["data"]["data"]
    ts = int(datetime.now().timestamp())
    rows: list[dict] = []

    for strike_str, sides in data["oc"].items():
        strike = float(strike_str)
        for option_type, key in (("CE", "ce"), ("PE", "pe")):
            leg = sides.get(key)
            if leg is None:
                continue
            greeks = leg.get("greeks", {})
            rows.append(
                {
                    "strike": strike,
                    "option_type": option_type,
                    "ltp": leg.get("last_price"),
                    "oi": leg.get("oi"),
                    "prev_day_oi": leg.get("previous_oi"),
                    "volume": leg.get("volume"),
                    "iv": leg.get("implied_volatility"),
                    "delta": greeks.get("delta"),
                    "theta": greeks.get("theta"),
                    "gamma": greeks.get("gamma"),
                    "vega": greeks.get("vega"),
                    "bid": leg.get("top_bid_price"),
                    "ask": leg.get("top_ask_price"),
                    "bid_qty": leg.get("top_bid_quantity"),
                    "ask_qty": leg.get("top_ask_quantity"),
                }
            )

    spot_price = validate_option_chain(data.get("last_price"), rows)
    return OptionChainResult(ts=ts, spot_price=spot_price, rows=rows)
