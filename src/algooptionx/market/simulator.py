"""Deterministic synthetic market fixtures; no account or broker dependency."""

import math
from datetime import datetime, timedelta
from zoneinfo import ZoneInfo

LOT = 65
MAX_TICK = 374


def market(tick: int, seed: int = 17) -> dict:
    spot = round(
        24_400
        + 65 * math.sin(tick / 13 + seed / 10)
        + 22 * math.sin(tick / 3.5)
        + tick * 0.18,
        2,
    )
    contracts = []
    for strike in range(24300, 24551, 50):
        for right in ("CE", "PE"):
            intrinsic = max(0, (spot - strike) if right == "CE" else (strike - spot))
            premium = max(
                2000,
                round(
                    (
                        85
                        + intrinsic * 0.65
                        + 12 * math.sin(tick / 9 + strike / 100)
                        - tick * 0.04
                    )
                    * 100
                ),
            )
            contracts.append(
                {
                    "id": f"SIM-20261103-{strike}-{right}",
                    "strike": strike,
                    "right": right,
                    "bid": premium - 40,
                    "ask": premium + 40,
                    "mark": premium,
                    "oi": 120000
                    + (strike % 300) * 120
                    + round(9000 * math.sin(tick / 20 + strike)),
                    "volume": 15000 + tick * 43 + strike % 1000,
                    "iv": round(
                        12.5 + abs(spot - strike) / 100 + math.sin(tick / 12), 2
                    ),
                    "lot_size": LOT,
                }
            )
    return {
        "tick": tick,
        "spot": spot,
        "contracts": contracts,
        "time": (
            datetime(2026, 11, 2, 9, 15, tzinfo=ZoneInfo("Asia/Kolkata"))
            + timedelta(minutes=tick)
        ).isoformat(),
        "source": "SYNTHETIC",
        "seed": seed,
    }
