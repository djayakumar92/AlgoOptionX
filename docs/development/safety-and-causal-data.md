# History safety and causal candle foundation

Implemented batch: **SAFE-01, SAFE-02, DATA-01, DATA-02**, authorized by the user's “ok” after the concrete first-batch plan was presented. This records conversation context, not cryptographic human identity or production deployment approval. Integration/evidence is tracked in the batch PR. Later strategy/risk/model/hosting tasks retain their own scope and gates.

## SAFE-01: journal preservation

Research startup no longer drops an old `journal_entries` table. Supported automatic migration is deliberately narrow: the known compatible schema missing only nullable `note` is upgraded by `ALTER TABLE ADD COLUMN`. Existing values, IDs, optional extra columns and other tables remain intact. Composite keys, required unknown columns without defaults, unsupported types/nullability and layouts missing `trade_date` are refused before journal mode, schema installation or retention changes. No historical trade date is guessed, and no unsupported table is deleted.

Before a supported upgrade, SQLite writer exclusion covers both a consistent backup snapshot and the transactional schema change. A separate read-only connection supplies the backup while the upgrading connection holds `BEGIN IMMEDIATE`; backing up that same write connection would block. The backup includes committed WAL data, is created exclusively with private POSIX permissions (other platforms inherit their directory ACLs), is checked before modification, and uses a unique `<database>.pre-journal-note-<id>.db` filename. A committed `journal-note-v1` migration record names the backup. Failure rolls back the column/marker changes and preserves the original and backup for diagnosis.

New and already-current databases do not need a backup migration. Unknown old schemas require a separately reviewed lossless mapping; refusal is a preservation safeguard, not a completed conversion of every legacy layout. Generated backups contain real historical data and should be protected like the original database.

For recovery, stop writers, verify the backup's integrity/content and determine whether any later writes need reconciliation before restoring it. The backup represents the pre-upgrade snapshot; it does not contain writes made after migration commits. Restore to a temporary path first and compare rows/IDs/schema. Do not blindly overwrite a running database or copy only its main file while WAL writers are active.

## SAFE-02: atomic initial funding

Schema installation is a separate transaction. Account creation, active pointer and initial FUNDING event then run in a single explicit economic transaction. An injected failure before/after any bootstrap effect leaves no funded account/pointer/event; restarting creates exactly one complete funding history. Concurrent starts serialize and do not fund multiple active accounts. A normal existing account retains its cash, positions and events; restart still pauses playback.

An existing database with an orphan active pointer or missing/duplicate active-account FUNDING history is refused for reconciliation. The code does not manufacture an event to repair a past partial startup, create replacement funding over an orphan account, or erase records. Preserve affected files and inspect verified backup/source evidence before a separately reviewed repair.

## DATA-01: explicit immutable contracts

`algooptionx.market.contracts` adds frozen `Session` and `Candle` records and `validate_batch`. Times must be aware datetimes and normalize to UTC. Sessions last 1–1440 whole minutes. OHLC is positive integer paise with consistent high/low bounds; volume is nonnegative integer **incremental units**, not a cumulative counter. Booleans, floats/nonfinite prices, naive times, inconsistent intervals, premature availability and invalid hashes are rejected. Source/instrument/data/calendar/session identities are explicit.

`validate_batch` checks an already available ordered batch against a specific session/as-of. Duplicate, overlapping/out-of-order, off-grid, cross-session and mixed instrument/source/version data fail; gaps are left explicit for aggregation. It never sorts, forward-fills or guesses metadata. A SHA-256 field validates provenance shape, not the truth of a provider's data or its license.

## DATA-02: completed windows only

`algooptionx.market.aggregation.aggregate_completed(candles, session, as_of=..., minutes=5|30)` accepts one-minute contracts. The aggregation boundary is a pure replay/research function with no network, account mutation or execution authority. It uses only records available by as-of; future or unreceived records are invisible. Strict batch validation can instead be called directly to reject future/unavailable records in an ingestion batch.

Windows anchor to the supplied session open. With the 09:15 IST fixture session, the first 30-minute window is 09:15–09:45 and is eligible only after every constituent minute closes and is received. Open/close derive from first/last child, high/low from actual extremes, volume is summed, availability is the maximum child availability, and the output hash binds child content/provenance. Simulator spot marks are not converted into pretend traded OHLCV.

`AggregationResult.status` is READY only when at least one whole expected window exists and every whole expected window in the session prefix is complete. Missing/late minutes produce INSUFFICIENT_DATA plus explicit missing-minute windows. Previously complete bars remain available in `bars` but must not be reused as a valid current confirmation when status is insufficient. Unfinished trailing buckets, including a short end-of-session tail, never become short “30-minute” candles.

This is a completeness/availability contract, not an execution freshness/market-open gate. Querying a historical session after its close can return READY; a future decision composer must separately enforce quote age, proposal TTL, current session, policy and kill checks. No autonomous paper strategy was switched to this helper in the approved batch.

```python
from datetime import datetime, timedelta
from zoneinfo import ZoneInfo
from algooptionx.market.contracts import Session, Candle
from algooptionx.market.aggregation import aggregate_completed

# Synthetic engineering fixture only; not actual traded data or an exchange calendar.
start = datetime(2026, 11, 2, 9, 15, tzinfo=ZoneInfo("Asia/Kolkata"))
session = Session("sim-20261102", "fixture-calendar-v1", start, start + timedelta(minutes=375))
minutes = [Candle(
    instrument_id="SIM-NIFTY", source_id="fixture", data_version="v1",
    calendar_version=session.calendar_version, session_id=session.session_id,
    source_hash="a" * 64,
    open_at=start + timedelta(minutes=i), close_at=start + timedelta(minutes=i+1),
    available_at=start + timedelta(minutes=i+1),
    open_paise=100, high_paise=110, low_paise=90, close_paise=105, volume=1,
) for i in range(30)]
result = aggregate_completed(minutes, session, as_of=start + timedelta(minutes=30), minutes=30)
assert result.status == "READY" and len(result.bars) == 1
```

## Validation and next boundary

Focused tests live in `tests/research/test_migrations.py`, `tests/paper/test_bootstrap.py` and `tests/market/test_causal_data.py`. They cover compatible/refused schemas, row/backup restore, failed migration rollback, concurrent writer exclusion, bootstrap fault/restart/concurrency, malformed OHLCV/times/metadata, session anchoring, missing/late minutes, partial tails and property-based future perturbation. Source-bound full validation, original research/paper regressions and functional browser checks remain required before merge; reports and the independent handoff are retained by the harness/PR.

The previously audited AUD-01/AUD-08 behaviors are addressed for the tested scope; historical audit reports remain unchanged. Existing unsupported/corrupt databases are preserved and refused, not silently repaired. Original five-bar fixture decisions, risk limits, costs, lot fixtures and order semantics remain unchanged. Next tasks are OBS-01/OBS-02 observation/decision contracts and shadow-only integration; live execution, risk-policy changes and models are outside this batch.
