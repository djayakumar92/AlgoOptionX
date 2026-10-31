"""Application-owned diagnostic vocabulary. Provider payloads are never formatted."""
from functools import wraps
import logging

_MESSAGES = {
    'AUTH_REJECTED': 'Broker authentication rejected; check local credentials.',
    'AUTH_PROVIDER_FAILURE': 'Broker authentication unavailable; retry after checking connectivity.',
    'CHAIN_FETCH_FAILED': 'Option-chain request failed; retry later.',
    'CANDLE_FETCH_FAILED': 'Historical candle request failed; retry later.',
    'MARKET_DATA_INVALID': 'Market data rejected by quality checks.',
    'LIVE_FEED_FAILED': 'Live feed failed; check connectivity.',
    'HISTORY_REFRESH_FAILED': 'Historical refresh failed; existing data remains subject to quality checks.',
    'PREDICTION_FAILED': 'Prediction evaluation failed; no successful result asserted.',
    'GRADING_FAILED': 'Retrospective grading failed; retry later.',
    'HLC_FAILED': 'HLC analysis failed; retry later.',
    'JOURNAL_BACKFILL_FAILED': 'Journal backfill failed; retry later.',
    'BACKTEST_FAILED': 'Backtest failed; inspect the retained safe failure record.',
    'RESEARCH_JOB_FAILED': 'Research operation failed; retry or inspect safe diagnostic codes.',
}


def message(code):
    # Unknown inputs do not become diagnostic content.
    if type(code) is not str or code not in _MESSAGES:
        code = 'RESEARCH_JOB_FAILED'
    return f'{code}: {_MESSAGES[code]}'


def provider_boundary(error_type, code):
    """Preserve the domain exception type while discarding untrusted SDK text.

    Cancellation/SystemExit are not swallowed. Suppress exception context in
    formatted tracebacks; callers must never inspect/render raw context/locals.
    """
    def decorate(fn):
        @wraps(fn)
        def call(*args, **kwargs):
            try:
                return fn(*args, **kwargs)
            except Exception as exc:
                from algooptionx.research.ingestion.quality import DataQualityError
                if isinstance(exc, DataQualityError):
                    raise DataQualityError(message('MARKET_DATA_INVALID')) from None
                # Preserve an application-owned safe category without formatting
                # arbitrary error objects or trusting provider-supplied fields.
                safe = message(code)
                if type(exc) is error_type and len(exc.args) == 1 and type(exc.args[0]) is str:
                    if exc.args[0] in {message(c) for c in _MESSAGES}:
                        safe = exc.args[0]
                raise error_type(safe) from None
        return call
    return decorate


class ProviderLogFilter(logging.Filter):
    """Deny third-party transport/SDK records at application output handlers.

    Message regexes cannot establish safety of arbitrary provider payloads.
    """
    def filter(self, record):
        # The SDK also emits through logging.error(), whose logger name is root.
        # Use origin metadata, without formatting the message or its arguments.
        pathname = record.pathname
        if type(pathname) is not str:
            return False
        origin = '/' + pathname.replace('\\', '/').lower().lstrip('/')
        if any('/' + package + '/' in origin for package in ('dhanhq', 'urllib3', 'requests', 'websocket', 'websockets', 'httpx', 'httpcore')):
            return False
        return not record.name.lower().startswith(('dhanhq', 'urllib3', 'requests', 'websocket', 'httpx', 'httpcore'))


def details(code, *, attempt=None):
    """Allowlisted structured fields; never accepts provider objects/payloads."""
    safe = code if type(code) is str and code in _MESSAGES else 'RESEARCH_JOB_FAILED'
    result = {'diagnostic_code': safe, 'retryable': safe != 'AUTH_REJECTED'}
    if type(attempt) is int and 1 <= attempt <= 100:
        result['attempt'] = attempt
    return result
