import { fmtInt, fmtNum } from "../format";
import { useRisk } from "../hooks/useRisk";

const WINDOW_LABEL: Record<string, string> = {
  OPENING: "Opening (first 30 min)",
  MIDDAY: "Midday",
  CLOSING: "Closing (last 90 min)",
};

export function RiskPanel() {
  const { data, startingUp, fetchError } = useRisk();

  // fetchError takes priority -- startingUp alone never becomes false on a
  // hard failure (it's only cleared on a successful fetch), so gating this
  // behind "not startingUp" would silently hide a real connection error forever.
  if (fetchError) {
    return (
      <section className="panel">
        <h2>Risk &amp; Position Sizing</h2>
        <div className="banner banner-error">Connection error: {fetchError}</div>
      </section>
    );
  }
  if (startingUp || !data) return null;

  const { position_sizing: sizing, daily_risk: daily, leg_estimates: legs } = data;
  const assessment = sizing.risk_assessment;

  return (
    <section className="panel">
      <h2>Risk &amp; Position Sizing</h2>
      <p className="oi-strikes">
        Reference sizing only — never a guaranteed stop distance, since the real stop is a live rule
        (previous 5-minute candle), not fixed pre-market. This app never places orders.
      </p>

      <div className="metrics-row">
        <div className="metric">
          <span className="metric-label">Session Window</span>
          <span className="metric-value">{WINDOW_LABEL[assessment.window] ?? assessment.window}</span>
          {assessment.is_expiry_day && <span className="metric-sub">Expiry day</span>}
        </div>
        <div className="metric">
          <span className="metric-label">Size Multiplier</span>
          <span className={`metric-value ${assessment.size_multiplier < 1 ? "bias-neutral" : ""}`}>
            {assessment.size_multiplier}×
          </span>
        </div>
        <div className="metric">
          <span className="metric-label">Max Risk / Trade</span>
          <span className="metric-value">{fmtInt(sizing.max_risk_per_trade)}</span>
          <span className="metric-sub">Lot size {sizing.lot_size}</span>
        </div>
      </div>

      {assessment.avoid_new_entries && (
        <div className="banner banner-warning">Avoid new entries right now — {assessment.reasons.join(" ")}</div>
      )}
      {!assessment.avoid_new_entries && assessment.reasons.length > 0 && (
        <p className="not-an-order">{assessment.reasons.join(" ")}</p>
      )}

      {legs.length > 0 && (
        <>
          <h3 style={{ fontSize: 14, fontWeight: 600, margin: "14px 0 6px" }}>Today's Plan — Estimated Sizing</h3>
          <table className="chain-table">
            <thead>
              <tr>
                <th>Leg</th>
                <th>Est. Stop Distance</th>
                <th>Lots</th>
                <th>Quantity</th>
                <th>Risk if Stopped</th>
              </tr>
            </thead>
            <tbody>
              {legs.map((leg) => (
                <tr key={leg.option_type} title={leg.note}>
                  <td>{leg.option_type}</td>
                  <td>{fmtNum(leg.estimated_stop_distance)} pts</td>
                  <td>{leg.sizing?.lots ?? "-"}</td>
                  <td>{leg.sizing?.quantity ?? "-"}</td>
                  <td>{leg.sizing ? fmtInt(leg.sizing.risk_amount) : "-"}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </>
      )}

      <h3 style={{ fontSize: 14, fontWeight: 600, margin: "14px 0 6px" }}>Position Sizing Reference</h3>
      <table className="chain-table">
        <thead>
          <tr>
            <th>Stop Distance</th>
            <th>Lots</th>
            <th>Quantity</th>
            <th>Risk if Stopped</th>
          </tr>
        </thead>
        <tbody>
          {sizing.table.map((row) => (
            <tr key={row.stop_distance_points}>
              <td>{fmtNum(row.stop_distance_points, 0)} pts</td>
              <td>{row.lots}</td>
              <td>{row.quantity}</td>
              <td>{fmtInt(row.risk_amount)}</td>
            </tr>
          ))}
        </tbody>
      </table>

      <h3 style={{ fontSize: 14, fontWeight: 600, margin: "14px 0 6px" }}>Daily Risk</h3>
      {daily.as_of_trade_date ? (
        <div className="metrics-row">
          <div className="metric">
            <span className="metric-label">Last Graded Day</span>
            <span className="metric-value">{daily.as_of_trade_date}</span>
            <span className="metric-sub">{fmtNum(daily.realized_points)} pts realized</span>
          </div>
          <div className="metric">
            <span className="metric-label">Daily Loss Limit</span>
            <span className="metric-value">{fmtInt(daily.max_daily_loss)}</span>
          </div>
          <div className="metric">
            <span className="metric-label">Remaining Budget</span>
            <span className={`metric-value ${daily.locked ? "bias-bearish" : "bias-bullish"}`}>
              {fmtInt(daily.remaining_budget)}
            </span>
          </div>
        </div>
      ) : (
        <p className="not-an-order">No graded trading day yet to compute this from.</p>
      )}
      {daily.locked && (
        <div className="banner banner-error">
          Daily loss limit reached on {daily.as_of_trade_date} — this is a decision-support flag only, not
          an enforced lock (this app never places orders).
        </div>
      )}
      <p className="not-an-order">
        Reflects the most recently <em>graded</em> trading day, not a live running total — this app grades
        outcomes once, retrospectively, at the next session's rollover, not in real time during the day.
      </p>
    </section>
  );
}
