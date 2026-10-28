import { fmtNum } from "../format";
import type { MomentumSummary, SentimentSummary, TrendSummary } from "../types";

interface Props {
  trend: TrendSummary;
  momentum: MomentumSummary;
  sentiment: SentimentSummary;
}

function Metric({ label, value, sub }: { label: string; value: string; sub?: string }) {
  return (
    <div className="metric">
      <span className="metric-label">{label}</span>
      <span className="metric-value">{value}</span>
      {sub && <span className="metric-sub">{sub}</span>}
    </div>
  );
}

export function MetricsRow({ trend, momentum, sentiment }: Props) {
  return (
    <section className="panel metrics-row">
      <Metric label="VWAP" value={fmtNum(trend.vwap)} sub={trend.price_vs_vwap} />
      <Metric label="ADX" value={fmtNum(trend.adx)} sub={trend.trend_strength} />
      <Metric label="RSI" value={fmtNum(momentum.rsi)} sub={momentum.rsi_state} />
      <Metric label="PCR (OI)" value={fmtNum(sentiment.pcr_oi, 3)} />
      <Metric label="Max Pain" value={fmtNum(sentiment.max_pain_strike, 0)} />
    </section>
  );
}
