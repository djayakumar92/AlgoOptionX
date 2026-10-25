import { fmtNum } from "../format";
import type { OiBehaviorSummary, SentimentSummary } from "../types";

interface Props {
  sentiment: SentimentSummary;
  oiBehavior: OiBehaviorSummary;
}

export function SentimentPanel({ sentiment, oiBehavior }: Props) {
  return (
    <section className="panel sentiment-panel">
      <h2>Sentiment &amp; OI</h2>
      <div className="metrics-row">
        <div className="metric">
          <span className="metric-label">PCR (Volume)</span>
          <span className="metric-value">{fmtNum(sentiment.pcr_volume, 3)}</span>
        </div>
        <div className="metric">
          <span className="metric-label">IV skew (P-C)</span>
          <span className="metric-value">{fmtNum(sentiment.iv_skew, 3)}</span>
        </div>
        <div className="metric">
          <span className="metric-label">OI long-buildup CE</span>
          <span className="metric-value">{oiBehavior.call_long_buildup_count}</span>
        </div>
        <div className="metric">
          <span className="metric-label">OI long-buildup PE</span>
          <span className="metric-value">{oiBehavior.put_long_buildup_count}</span>
        </div>
      </div>
      <p className="oi-strikes">
        Top Call OI strikes: {sentiment.top_call_oi_strikes.map((s) => fmtNum(s, 0)).join(", ") || "-"}
        <br />
        Top Put OI strikes: {sentiment.top_put_oi_strikes.map((s) => fmtNum(s, 0)).join(", ") || "-"}
      </p>
    </section>
  );
}
