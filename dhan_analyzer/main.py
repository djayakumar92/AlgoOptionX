from __future__ import annotations

import logging
import sys
from datetime import datetime, timedelta

from dhan_analyzer import auth, instruments, pipeline
from dhan_analyzer.config import load_settings_or_exit
from dhan_analyzer.ingestion import historical, option_chain
from dhan_analyzer.ingestion.scheduler import OptionChainPoller
from dhan_analyzer.logging_setup import setup_logging
from dhan_analyzer.presentation.cli_dashboard import Dashboard, render
from dhan_analyzer.storage import db

logger = logging.getLogger(__name__)

# 5-min candles: enough bars in 5 trading days to warm up RSI(14)/ADX(14)/MA(21).
CANDLE_LOOKBACK_DAYS = 5
INSTRUMENT_TYPE_INDEX = "INDEX"


def run() -> None:
    settings = load_settings_or_exit()
    setup_logging(settings)

    client = auth.build_client(settings)
    conn = db.connect(settings.db_path, settings.retention_days)

    under_symbol = settings.underlying.symbol
    under_segment = settings.underlying.segment
    under_security_id = instruments.resolve_index_security_id(under_symbol)
    intraday_interval = settings.historical.intraday_interval_min

    expiries = option_chain.fetch_expiry_list(client, under_security_id, under_segment)
    if not expiries:
        print(f"No option expiries returned for {under_symbol}.", file=sys.stderr)
        raise SystemExit(1)
    # Phase 1 tracks only the nearest expiry (matches default settings.toml expiries_tracked=1).
    tracked_expiry = expiries[0]
    expiry_label = tracked_expiry.isoformat()

    logger.info("Tracking %s, nearest expiry %s", under_symbol, expiry_label)
    historical.catch_up_intraday(
        conn, client, under_symbol, under_security_id, under_segment, INSTRUMENT_TYPE_INDEX,
        intraday_interval, CANDLE_LOOKBACK_DAYS,
    )

    poller = OptionChainPoller(settings.polling.option_chain_interval_sec)
    iv_history: list[float] = []
    last_historical_refresh = datetime.min

    print(f"Starting {under_symbol} analyzer (expiry {expiry_label}). Ctrl+C to stop.")

    with Dashboard() as dashboard:
        try:
            while True:
                cycle = pipeline.run_cycle(
                    conn, client, poller, under_symbol, under_security_id, under_segment,
                    tracked_expiry, expiry_label, intraday_interval, iv_history,
                )
                if cycle is None:
                    continue

                dashboard.update(
                    render(
                        under_symbol, cycle.spot_price, cycle.chain, settings.underlying.strike_window,
                        cycle.sentiment, cycle.oi_behavior, cycle.trend, cycle.momentum, cycle.suggestion,
                    )
                )

                if datetime.now() - last_historical_refresh > timedelta(
                    seconds=settings.polling.historical_refresh_interval_sec
                ):
                    try:
                        historical.catch_up_intraday(
                            conn, client, under_symbol, under_security_id, under_segment,
                            INSTRUMENT_TYPE_INDEX, intraday_interval, CANDLE_LOOKBACK_DAYS,
                        )
                    except Exception:
                        logger.exception("Historical refresh failed; continuing with existing candles")
                    last_historical_refresh = datetime.now()
        except KeyboardInterrupt:
            print("\nStopping.")

    conn.close()


if __name__ == "__main__":
    run()
