from __future__ import annotations

import logging
from dataclasses import dataclass
from datetime import date, datetime, timedelta
from pathlib import Path

import pandas as pd
import requests

from algooptionx.research.config import PROJECT_ROOT

logger = logging.getLogger(__name__)

SCRIP_MASTER_URL = "https://images.dhan.co/api-data/api-scrip-master.csv"
CACHE_PATH = PROJECT_ROOT / "data" / "scrip_master.csv"
CACHE_MAX_AGE = timedelta(days=1)

# Column names as published by DhanHQ (compact scrip master).
COL_EXCH = "SEM_EXM_EXCH_ID"
COL_SEGMENT = "SEM_SEGMENT"
COL_SECURITY_ID = "SEM_SMST_SECURITY_ID"
COL_INSTRUMENT = "SEM_INSTRUMENT_NAME"
COL_TRADING_SYMBOL = "SEM_TRADING_SYMBOL"
COL_EXPIRY_DATE = "SEM_EXPIRY_DATE"
COL_STRIKE = "SEM_STRIKE_PRICE"
COL_OPTION_TYPE = "SEM_OPTION_TYPE"
COL_SYMBOL_NAME = "SM_SYMBOL_NAME"
COL_LOT_UNITS = "SEM_LOT_UNITS"


@dataclass(frozen=True)
class OptionContract:
    security_id: str
    trading_symbol: str
    expiry: date
    strike: float
    option_type: str  # "CE" or "PE"


def _download_scrip_master() -> None:
    CACHE_PATH.parent.mkdir(parents=True, exist_ok=True)
    logger.info("Downloading DhanHQ scrip master to %s", CACHE_PATH)
    response = requests.get(SCRIP_MASTER_URL, timeout=60)
    response.raise_for_status()
    CACHE_PATH.write_bytes(response.content)


def _load_scrip_master(force_refresh: bool = False) -> pd.DataFrame:
    is_stale = (
        not CACHE_PATH.exists()
        or datetime.fromtimestamp(CACHE_PATH.stat().st_mtime) < datetime.now() - CACHE_MAX_AGE
    )
    if force_refresh or is_stale:
        _download_scrip_master()
    return pd.read_csv(CACHE_PATH, low_memory=False)


class InstrumentResolutionError(RuntimeError):
    pass


def resolve_index_security_id(symbol: str, force_refresh: bool = False) -> str:
    """Resolve an index's security id (e.g. NIFTY -> '13') for option-chain requests."""
    df = _load_scrip_master(force_refresh)
    matches = df[
        (df[COL_EXCH] == "NSE")
        & (df[COL_INSTRUMENT] == "INDEX")
        & (df[COL_SYMBOL_NAME].astype(str) == symbol)
    ]
    if matches.empty:
        raise InstrumentResolutionError(
            f"No NSE index found for symbol '{symbol}' in the scrip master."
        )
    return str(matches.iloc[0][COL_SECURITY_ID])


def list_expiries(symbol: str, force_refresh: bool = False) -> list[date]:
    """Distinct expiry dates available for a symbol's option contracts (from cached master).

    Prefer the live expiry_list API call for accuracy close to rollover; this is a local
    fallback/cross-check derived from the same scrip master used for security-id lookups.
    """
    df = _load_scrip_master(force_refresh)
    opts = df[(df[COL_INSTRUMENT] == "OPTIDX") & (df[COL_TRADING_SYMBOL].str.startswith(f"{symbol}-"))]
    expiries = pd.to_datetime(opts[COL_EXPIRY_DATE]).dt.date.unique()
    return sorted(expiries)


def lot_size_for_expiry(symbol: str, expiry: date, force_refresh: bool = False) -> int:
    """Real, current lot size from DhanHQ's own scrip master -- deliberately
    not a hardcoded/configured number, since NSE lot sizes change
    periodically (e.g. NIFTY has been resized more than once) and a stale
    constant would silently misprice position sizing."""
    df = _load_scrip_master(force_refresh)
    opts = df[(df[COL_INSTRUMENT] == "OPTIDX") & (df[COL_TRADING_SYMBOL].str.startswith(f"{symbol}-"))].copy()
    opts[COL_EXPIRY_DATE] = pd.to_datetime(opts[COL_EXPIRY_DATE]).dt.date
    opts = opts[opts[COL_EXPIRY_DATE] == expiry]
    if opts.empty:
        raise InstrumentResolutionError(f"No option contracts found for {symbol} expiry {expiry} to read lot size from.")
    return int(opts.iloc[0][COL_LOT_UNITS])


def option_contracts_for_expiry(
    symbol: str, expiry: date, force_refresh: bool = False
) -> list[OptionContract]:
    """All CE/PE contracts for a symbol+expiry, used to map option-chain strikes to security ids."""
    df = _load_scrip_master(force_refresh)
    opts = df[(df[COL_INSTRUMENT] == "OPTIDX") & (df[COL_TRADING_SYMBOL].str.startswith(f"{symbol}-"))].copy()
    opts[COL_EXPIRY_DATE] = pd.to_datetime(opts[COL_EXPIRY_DATE]).dt.date
    opts = opts[opts[COL_EXPIRY_DATE] == expiry]

    if opts.empty:
        raise InstrumentResolutionError(
            f"No option contracts found for {symbol} expiry {expiry}."
        )

    return [
        OptionContract(
            security_id=str(row[COL_SECURITY_ID]),
            trading_symbol=str(row[COL_TRADING_SYMBOL]),
            expiry=row[COL_EXPIRY_DATE],
            strike=float(row[COL_STRIKE]),
            option_type=str(row[COL_OPTION_TYPE]),
        )
        for _, row in opts.iterrows()
    ]
