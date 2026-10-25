from __future__ import annotations

import pandas as pd
from rich.console import Group
from rich.live import Live
from rich.panel import Panel
from rich.table import Table
from rich.text import Text

from dhan_analyzer.signals.combine import Suggestion
from dhan_analyzer.signals.momentum import MomentumSummary
from dhan_analyzer.signals.oi_behavior import OiBehaviorSummary
from dhan_analyzer.signals.sentiment import SentimentSummary
from dhan_analyzer.signals.trend import TrendSummary

BIAS_STYLE = {"BULLISH": "bold green", "BEARISH": "bold red", "NEUTRAL": "bold yellow"}


def _bias_text(label: str) -> Text:
    return Text(label, style=BIAS_STYLE.get(label, ""))


def _trend_panel(symbol: str, spot: float, trend: TrendSummary, momentum: MomentumSummary) -> Panel:
    table = Table.grid(padding=(0, 2))
    table.add_column(justify="right", style="dim")
    table.add_column()

    table.add_row("Spot", f"{spot:g}")
    table.add_row("VWAP", f"{trend.vwap:g} ({trend.price_vs_vwap})" if trend.vwap else "-")
    table.add_row("MA(9/21)", f"{trend.ma_fast:g} / {trend.ma_slow:g}  [{trend.ma_crossover}]" if trend.ma_fast else "-")
    table.add_row("ADX", f"{trend.adx:g} ({trend.trend_strength})" if trend.adx else "-")
    table.add_row("RSI", f"{momentum.rsi:g} ({momentum.rsi_state})" if momentum.rsi else "-")
    table.add_row("ROC", f"{momentum.roc:g}%" if momentum.roc is not None else "-")
    table.add_row("IV rank (session)", f"{momentum.iv_rank}" if momentum.iv_rank is not None else "-")

    return Panel(table, title=f"[bold]{symbol} Trend & Momentum[/bold]", border_style="blue")


def _sentiment_panel(sentiment: SentimentSummary, oi_behavior: OiBehaviorSummary) -> Panel:
    table = Table.grid(padding=(0, 2))
    table.add_column(justify="right", style="dim")
    table.add_column()

    table.add_row("PCR (OI)", f"{sentiment.pcr_oi}" if sentiment.pcr_oi is not None else "-")
    table.add_row("PCR (Volume)", f"{sentiment.pcr_volume}" if sentiment.pcr_volume is not None else "-")
    table.add_row("Max Pain", f"{sentiment.max_pain_strike:g}" if sentiment.max_pain_strike else "-")
    table.add_row(
        "ATM IV (C/P)",
        f"{sentiment.call_iv_atm:.1f} / {sentiment.put_iv_atm:.1f}"
        if sentiment.call_iv_atm is not None and sentiment.put_iv_atm is not None
        else "-",
    )
    table.add_row("IV skew", f"{sentiment.iv_skew}" if sentiment.iv_skew is not None else "-")
    table.add_row("Top Call OI", ", ".join(f"{s:g}" for s in sentiment.top_call_oi_strikes) or "-")
    table.add_row("Top Put OI", ", ".join(f"{s:g}" for s in sentiment.top_put_oi_strikes) or "-")
    table.add_row(
        "OI buildup (CE/PE long)",
        f"{oi_behavior.call_long_buildup_count} / {oi_behavior.put_long_buildup_count}",
    )

    return Panel(table, title="[bold]Sentiment & OI[/bold]", border_style="magenta")


def _chain_table(chain: pd.DataFrame, spot: float, window: int, oi_behavior_df: pd.DataFrame) -> Panel:
    strikes = sorted(chain["strike"].unique())
    atm = min(strikes, key=lambda s: abs(s - spot)) if strikes else None
    if atm is not None:
        idx = strikes.index(atm)
        strikes = strikes[max(0, idx - window) : idx + window + 1]

    behavior_lookup = {}
    if not oi_behavior_df.empty:
        for _, row in oi_behavior_df.iterrows():
            behavior_lookup[(row["strike"], row["option_type"])] = row["behavior"]

    table = Table(border_style="cyan")
    table.add_column("CE OI", justify="right")
    table.add_column("CE LTP", justify="right")
    table.add_column("Strike", justify="center", style="bold")
    table.add_column("PE LTP", justify="right")
    table.add_column("PE OI", justify="right")

    for strike in strikes:
        ce = chain[(chain["strike"] == strike) & (chain["option_type"] == "CE")]
        pe = chain[(chain["strike"] == strike) & (chain["option_type"] == "PE")]

        ce_oi = f"{int(ce.iloc[0]['oi']):,}" if not ce.empty and pd.notna(ce.iloc[0]["oi"]) else "-"
        ce_ltp = f"{ce.iloc[0]['ltp']:g}" if not ce.empty and pd.notna(ce.iloc[0]["ltp"]) else "-"
        pe_ltp = f"{pe.iloc[0]['ltp']:g}" if not pe.empty and pd.notna(pe.iloc[0]["ltp"]) else "-"
        pe_oi = f"{int(pe.iloc[0]['oi']):,}" if not pe.empty and pd.notna(pe.iloc[0]["oi"]) else "-"

        ce_tag = behavior_lookup.get((strike, "CE"))
        pe_tag = behavior_lookup.get((strike, "PE"))
        if ce_tag and ce_tag != "NEUTRAL":
            ce_oi += f" [{ce_tag[:2]}]"
        if pe_tag and pe_tag != "NEUTRAL":
            pe_oi += f" [{pe_tag[:2]}]"

        strike_label = f"*{strike:g}*" if strike == atm else f"{strike:g}"
        table.add_row(ce_oi, ce_ltp, strike_label, pe_ltp, pe_oi)

    return Panel(table, title="[bold]Option Chain (ATM +/- window)[/bold]", border_style="cyan")


def _suggestion_panel(suggestion: Suggestion) -> Panel:
    table = Table.grid(padding=(0, 2))
    table.add_column(justify="right", style="dim")
    table.add_column()

    table.add_row("Bias", _bias_text(suggestion.bias))
    table.add_row("Confidence", f"{suggestion.confidence}%")
    table.add_row("Instrument", suggestion.suggested_instrument or "-")
    table.add_row("Entry zone", suggestion.entry_zone or "-")
    table.add_row("Stop loss", suggestion.stop_loss or "-")
    table.add_row("Watch level", suggestion.watch_level or "-")
    table.add_row("Rationale", suggestion.rationale)

    return Panel(
        table,
        title="[bold]Suggestion (analytical output - not an order)[/bold]",
        border_style=BIAS_STYLE.get(suggestion.bias, "white"),
    )


def render(
    symbol: str,
    spot: float,
    chain: pd.DataFrame,
    strike_window: int,
    sentiment: SentimentSummary,
    oi_behavior: OiBehaviorSummary,
    trend: TrendSummary,
    momentum: MomentumSummary,
    suggestion: Suggestion,
) -> Group:
    return Group(
        _trend_panel(symbol, spot, trend, momentum),
        _sentiment_panel(sentiment, oi_behavior),
        _chain_table(chain, spot, strike_window, oi_behavior.per_contract),
        _suggestion_panel(suggestion),
    )


class Dashboard:
    """Wraps rich.Live so main.py can just call .update(renderable) each cycle."""

    def __init__(self) -> None:
        self._live = Live(refresh_per_second=2, screen=False)

    def __enter__(self) -> "Dashboard":
        self._live.__enter__()
        return self

    def __exit__(self, *exc) -> None:
        self._live.__exit__(*exc)

    def update(self, renderable) -> None:
        self._live.update(renderable)
