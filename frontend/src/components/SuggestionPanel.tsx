import type { Suggestion } from "../types";

const BIAS_CLASS: Record<string, string> = {
  BULLISH: "bias-bullish",
  BEARISH: "bias-bearish",
  NEUTRAL: "bias-neutral",
};

export function SuggestionPanel({ suggestion }: { suggestion: Suggestion }) {
  return (
    <section className="panel suggestion-panel">
      <div className={`suggestion-headline ${BIAS_CLASS[suggestion.bias] ?? ""}`}>
        <span className="bias-label">{suggestion.bias}</span>
        <span className="confidence">confidence {suggestion.confidence}%</span>
      </div>
      <div className="suggestion-grid">
        <div>
          <span className="field-label">Instrument</span>
          <span>{suggestion.suggested_instrument ?? "-"}</span>
        </div>
        <div>
          <span className="field-label">Entry zone</span>
          <span>{suggestion.entry_zone ?? "-"}</span>
        </div>
        <div>
          <span className="field-label">Stop loss</span>
          <span>{suggestion.stop_loss ?? "-"}</span>
        </div>
        <div>
          <span className="field-label">Watch level</span>
          <span>{suggestion.watch_level ?? "-"}</span>
        </div>
      </div>
      <p className="rationale">{suggestion.rationale}</p>
      <p className="not-an-order">Analytical output — not an order.</p>
    </section>
  );
}
