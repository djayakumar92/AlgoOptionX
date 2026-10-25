"""Background polling loop that feeds LiveState, run in a daemon thread.

Same loop shape as dhan_analyzer/main.py and the retired web_dashboard.py: poll
-> pipeline.run_cycle -> store result; on a failed poll, log the error into
LiveState (so the frontend can show a banner) and keep going rather than
crashing the whole process, exactly like web_dashboard.py's retry-and-continue.
"""

from __future__ import annotations

import logging
import threading
import time
from datetime import date, datetime, timedelta

from dhanhq import dhanhq

from dhan_analyzer import pipeline
from dhan_analyzer.api import prediction
from dhan_analyzer.api.state import LiveState
from dhan_analyzer.config import Settings
from dhan_analyzer.ingestion import historical
from dhan_analyzer.ingestion.quality import DataQualityError
from dhan_analyzer.ingestion.option_chain import OptionChainError
from dhan_analyzer.ingestion.scheduler import OptionChainPoller

logger = logging.getLogger(__name__)

CANDLE_LOOKBACK_DAYS = 5
INSTRUMENT_TYPE_INDEX = "INDEX"

# How often the prediction engine re-evaluates and writes to the learning
# ledger. Far slower than the option-chain poll on purpose: the ledger records
# the moment a setup first arms, and re-running it every 3.5 seconds would
# burn CPU re-deriving a read that changes on the timescale of 5-minute
# candles. The unique key on (trade_date, setup_key) means a missed tick
# costs nothing -- the next one records the same arming.
PREDICTION_INTERVAL_SEC = 60

# How often finished sessions are graded. Once every few minutes is ample --
# it only ever has work to do after a day rolls over.
GRADING_INTERVAL_SEC = 600


def run_worker(
    state: LiveState,
    settings: Settings,
    client: dhanhq,
    conn,
    under_symbol: str,
    under_security_id: str,
    under_segment: str,
    tracked_expiry: date,
    expiry_label: str,
    stop_event: threading.Event,
) -> None:
    intraday_interval = settings.historical.intraday_interval_min
    poller = OptionChainPoller(settings.polling.option_chain_interval_sec)
    iv_history: list[float] = []
    last_historical_refresh = datetime.min
    last_prediction = datetime.min
    last_grading = datetime.min

    while not stop_event.is_set():
        try:
            cycle = pipeline.run_cycle(
                conn, client, poller, under_symbol, under_security_id, under_segment,
                tracked_expiry, expiry_label, intraday_interval, iv_history,
            )
        except OptionChainError as exc:
            logger.warning("Poll failed, retrying: %s", exc)
            state.set_error(str(exc), int(time.time()))
            stop_event.wait(settings.polling.option_chain_interval_sec)
            continue
        except DataQualityError as exc:
            logger.warning("Market-data quality gate blocked a cycle: %s", exc)
            state.set_error(str(exc), int(time.time()))
            stop_event.wait(settings.polling.option_chain_interval_sec)
            continue
        except Exception:
            # A daemon thread that dies from an uncaught exception fails silently --
            # the Live page would show "waiting for the first cycle" forever with no
            # indication anything went wrong. Log the full traceback and keep going
            # instead of letting the loop (and the thread) die here.
            logger.exception("Poll cycle crashed unexpectedly, retrying")
            state.set_error("Unexpected error -- check logs/dhan_analyzer.log", int(time.time()))
            stop_event.wait(settings.polling.option_chain_interval_sec)
            continue

        if cycle is not None:
            state.set_result(cycle)

        # The prediction engine and the ledger are deliberately downstream of
        # the poll and wrapped in their own try/except: a failure to evaluate
        # or record must never take down the market-data loop that the whole
        # app depends on.
        if cycle is not None and datetime.now() - last_prediction > timedelta(
            seconds=PREDICTION_INTERVAL_SEC
        ):
            try:
                prediction.evaluate_and_record(
                    conn,
                    under_symbol=under_symbol,
                    tracked_expiry=tracked_expiry,
                    intraday_interval=intraday_interval,
                    spot_price=cycle.spot_price,
                )
            except Exception:
                logger.exception("Prediction/ledger update failed; continuing to poll")
            last_prediction = datetime.now()

        if datetime.now() - last_grading > timedelta(seconds=GRADING_INTERVAL_SEC):
            try:
                prediction.grade_finished_sessions(
                    conn, under_symbol=under_symbol, intraday_interval=intraday_interval
                )
            except Exception:
                logger.exception("Grading pass failed; continuing to poll")
            last_grading = datetime.now()

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
