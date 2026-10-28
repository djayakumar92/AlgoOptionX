"""Reads the learning ledger back: what has each setup actually done, in
which conditions, and how many times -- so the engine's displayed confidence
comes from its own record instead of from its own opinion.

Three questions this answers, in order of how much they matter:

1. **Is this setup any good?** Hit rate, average points, and -- always
   printed alongside, never omitted -- the sample size behind them.
2. **When is it good?** The same numbers sliced by the regime that was live
   when the setup armed. A setup with a mediocre overall hit rate that is
   strong in one specific regime is a useful setup being misapplied, and
   that distinction is invisible in an aggregate.
3. **Is the engine's own regime read meaningful?** `regime_report()` checks
   whether sessions the engine called trending actually moved further than
   the ones it called contained. If they did not, the regime layer is
   decorative and should be treated as such.

## The rule that governs everything below

No number is reported without its sample size attached, and no hit rate is
described as reliable below `MIN_RELIABLE_SAMPLE` outcomes. This is not
excessive caution -- with a handful of trades, a 100% hit rate and a 0% hit
rate are both entirely consistent with a setup that is worthless, and
presenting either as a finding would be the single most expensive kind of
mistake this project could make.
"""

from __future__ import annotations

import sqlite3
from collections import defaultdict
from dataclasses import dataclass, field

from algooptionx.research.signals.setups import CalibrationRead
from algooptionx.research.storage import repository

WIN, LOSS, FLAT, NOT_TRIGGERED = "WIN", "LOSS", "FLAT", "NOT_TRIGGERED"

# Below this many graded, triggered outcomes, a hit rate is reported but
# explicitly labelled as not yet meaningful, and setups.py caps the grade.
MIN_RELIABLE_SAMPLE = 20


@dataclass(frozen=True)
class SliceStats:
    """Performance within one condition (a regime, a day type, a window)."""

    label: str
    sample: int
    wins: int
    losses: int
    hit_rate: float | None
    avg_points: float | None


@dataclass(frozen=True)
class SetupRecord:
    setup_key: str
    armed: int  # times the setup fired at all
    triggered: int  # times its entry condition actually occurred
    wins: int
    losses: int
    flats: int
    not_triggered: int
    hit_rate: float | None  # wins / (wins + losses), as a percentage
    avg_points: float | None
    best_points: float | None
    worst_points: float | None
    avg_mae: float | None  # how far it went against you before working
    reliable: bool
    by_regime: list[SliceStats] = field(default_factory=list)
    by_day_type: list[SliceStats] = field(default_factory=list)
    by_pricing: list[SliceStats] = field(default_factory=list)
    verdict: str = ""


@dataclass(frozen=True)
class RegimeReport:
    """Did the engine's own regime labels correspond to anything real?"""

    sessions: int
    by_regime: list[SliceStats]
    trend_avg_range: float | None
    range_avg_range: float | None
    separation_points: float | None
    verdict: str


def _mean(values: list[float]) -> float | None:
    usable = [v for v in values if v is not None]
    return round(sum(usable) / len(usable), 1) if usable else None


def _slice(label: str, rows: list[sqlite3.Row]) -> SliceStats:
    wins = sum(1 for r in rows if r["result"] == WIN)
    losses = sum(1 for r in rows if r["result"] == LOSS)
    decided = wins + losses
    return SliceStats(
        label=label,
        sample=len(rows),
        wins=wins,
        losses=losses,
        hit_rate=round(wins / decided * 100, 1) if decided else None,
        avg_points=_mean([r["underlying_points"] for r in rows]),
    )


def _group(rows: list[sqlite3.Row], column: str) -> list[SliceStats]:
    buckets: dict[str, list[sqlite3.Row]] = defaultdict(list)
    for row in rows:
        key = row[column] or "UNKNOWN"
        buckets[key].append(row)
    return sorted(
        (_slice(str(k).replace("_", " ").title(), v) for k, v in buckets.items()),
        key=lambda s: -s.sample,
    )


def _verdict(record_wins: int, record_losses: int, sample: int, hit_rate: float | None) -> str:
    if sample == 0:
        return (
            "No graded outcomes yet. This setup has never been tested on real sessions, so nothing "
            "is known about whether it works."
        )
    if sample < 5:
        return (
            f"Only {sample} graded outcome(s). At this size the result is indistinguishable from "
            "chance -- it is a record being started, not evidence."
        )
    if sample < MIN_RELIABLE_SAMPLE:
        return (
            f"{record_wins} wins and {record_losses} losses across {sample} graded outcomes. Still "
            f"below the {MIN_RELIABLE_SAMPLE} needed before a hit rate means much, so treat this as "
            "a direction of travel rather than a finding."
        )
    if hit_rate is None:
        return f"{sample} graded outcomes, but none of them resolved decisively enough to score."
    if hit_rate >= 60:
        return (
            f"{hit_rate:.0f}% of {sample} graded outcomes went the setup's way. That is a real "
            "sample and a genuinely favourable one."
        )
    if hit_rate >= 45:
        return (
            f"{hit_rate:.0f}% across {sample} graded outcomes -- roughly a coin flip on direction. "
            "Whether it is worth trading depends entirely on the size of the wins against the losses."
        )
    return (
        f"{hit_rate:.0f}% across {sample} graded outcomes. On this record the setup is losing more "
        "often than it wins, and the conditions slices below are worth reading before trusting it again."
    )


def setup_record(conn: sqlite3.Connection, setup_key: str) -> SetupRecord:
    rows = repository.get_setup_outcomes(conn, setup_key)
    triggered_rows = [r for r in rows if r["triggered"]]

    wins = sum(1 for r in triggered_rows if r["result"] == WIN)
    losses = sum(1 for r in triggered_rows if r["result"] == LOSS)
    flats = sum(1 for r in triggered_rows if r["result"] == FLAT)
    not_triggered = sum(1 for r in rows if not r["triggered"])
    decided = wins + losses
    hit_rate = round(wins / decided * 100, 1) if decided else None

    points = [r["underlying_points"] for r in triggered_rows if r["underlying_points"] is not None]

    return SetupRecord(
        setup_key=setup_key,
        armed=len(rows),
        triggered=len(triggered_rows),
        wins=wins,
        losses=losses,
        flats=flats,
        not_triggered=not_triggered,
        hit_rate=hit_rate,
        avg_points=_mean(points),
        best_points=round(max(points), 1) if points else None,
        worst_points=round(min(points), 1) if points else None,
        avg_mae=_mean([r["mae_points"] for r in triggered_rows]),
        reliable=decided >= MIN_RELIABLE_SAMPLE,
        by_regime=_group(triggered_rows, "structure_regime"),
        by_day_type=_group(triggered_rows, "day_type"),
        by_pricing=_group(triggered_rows, "premium_pricing"),
        verdict=_verdict(wins, losses, decided, hit_rate),
    )


def all_setup_records(conn: sqlite3.Connection) -> list[SetupRecord]:
    keys = {row["setup_key"] for row in repository.get_setup_outcomes(conn)}
    return sorted((setup_record(conn, k) for k in keys), key=lambda r: -r.armed)


def calibration_map(conn: sqlite3.Connection) -> dict[str, CalibrationRead]:
    """What `setups.py` consumes: one `CalibrationRead` per setup key.

    Returning an empty dict is normal and correct on a fresh install -- every
    setup then reports "never graded" and has its grade capped, which is the
    intended behaviour rather than a degraded one.
    """
    result: dict[str, CalibrationRead] = {}
    for record in all_setup_records(conn):
        decided = record.wins + record.losses
        result[record.setup_key] = CalibrationRead(
            sample_size=decided,
            wins=record.wins,
            hit_rate=record.hit_rate,
            avg_points=record.avg_points,
            note=record.verdict,
        )
    return result


def journal_by_regime(conn: sqlite3.Connection) -> list[SliceStats]:
    """The HLC rule's own graded trades, sliced by the market regime the
    engine recorded that day.

    Separate from `setup_record().by_regime`, which slices the *setup engine's*
    outcomes. This one answers the question the Analytics page asks: does the
    spreadsheet rule you actually trade do better in some conditions than
    others. Entries from before the regime engine existed carry no label and
    are grouped as "Not recorded" rather than dropped or guessed at.
    """
    rows = repository.get_journal_entries_with_regime(conn)
    graded = [r for r in rows if r["outcome"] in ("TARGET_HIT", "STOP_HIT")]
    if not graded:
        return []

    buckets: dict[str, list[sqlite3.Row]] = defaultdict(list)
    for row in graded:
        buckets[row["structure_regime"] or "NOT_RECORDED"].append(row)

    stats: list[SliceStats] = []
    for key, entries in buckets.items():
        wins = sum(1 for r in entries if r["outcome"] == "TARGET_HIT")
        losses = len(entries) - wins
        points = [r["realized_points"] for r in entries if r["realized_points"] is not None]
        stats.append(
            SliceStats(
                label="Not recorded" if key == "NOT_RECORDED" else key.replace("_", " ").title(),
                sample=len(entries),
                wins=wins,
                losses=losses,
                hit_rate=round(wins / len(entries) * 100, 1) if entries else None,
                avg_points=_mean(points),
            )
        )
    return sorted(stats, key=lambda s: -s.sample)


def regime_report(conn: sqlite3.Connection) -> RegimeReport:
    """Check the regime labels against what the sessions actually did.

    The test is deliberately blunt: sessions the engine called trending
    should, on average, have travelled further than the ones it called
    contained. If that separation is absent, the label is not measuring
    anything and every setup gated on it inherits the problem.
    """
    rows = [r for r in repository.get_daily_features(conn, limit=500) if r["range_points"] is not None]
    if not rows:
        return RegimeReport(
            0, [], None, None, None,
            "No completed sessions recorded yet. The regime read cannot be checked until the app has "
            "watched some full trading days.",
        )

    buckets: dict[str, list[float]] = defaultdict(list)
    for row in rows:
        buckets[row["structure_regime"] or "UNKNOWN"].append(float(row["range_points"]))

    slices = sorted(
        (
            SliceStats(
                label=key.replace("_", " ").title(),
                sample=len(values),
                wins=0,
                losses=0,
                hit_rate=None,
                avg_points=round(sum(values) / len(values), 1),
            )
            for key, values in buckets.items()
        ),
        key=lambda s: -s.sample,
    )

    trend_avg = _mean(buckets.get("TRENDING", []))
    range_avg = _mean(buckets.get("RANGING", []))
    separation = round(trend_avg - range_avg, 1) if (trend_avg and range_avg) else None

    if separation is None:
        verdict = (
            f"{len(rows)} session(s) recorded, but not yet enough of both kinds to compare trending "
            "days against contained ones."
        )
    elif separation > 20:
        verdict = (
            f"Sessions the engine called trending moved {separation:.0f} points more than the ones it "
            f"called contained ({trend_avg:.0f} against {range_avg:.0f} points of range). The label is "
            "tracking something real."
        )
    elif separation > 0:
        verdict = (
            f"Trending sessions moved only {separation:.0f} points more than contained ones "
            f"({trend_avg:.0f} against {range_avg:.0f}). The separation is in the right direction but "
            "too small to lean on yet."
        )
    else:
        verdict = (
            f"Sessions labelled trending have not moved further than the ones labelled contained "
            f"({trend_avg:.0f} against {range_avg:.0f} points). On this record the regime label is not "
            "yet earning its place, and setups gated on it should be read with that in mind."
        )

    return RegimeReport(len(rows), slices, trend_avg, range_avg, separation, verdict)
