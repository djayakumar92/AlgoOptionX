import { Link } from "react-router-dom";
import { Cockpit, MarketBar, READINESS_CLASS, READINESS_LABEL } from "../components/Cockpit";
import { fmtNum, fmtTime } from "../format";
import { useHealth } from "../hooks/useHealth";
import { useHlcState } from "../hooks/useHlcState";
import { useJournalEntries } from "../hooks/useJournalEntries";
import { useLiveState } from "../hooks/useLiveState";
import { usePrediction } from "../hooks/usePrediction";

const BIAS_CLASS: Record<string, string> = {
  BULLISH: "bias-bullish",
  BEARISH: "bias-bearish",
  NEUTRAL: "bias-neutral",
};

// Turns the already-real trend signals (VWAP position, MA crossover, ADX
// strength) into one plain-language sentence -- not invented text, just a
// readable summary of numbers the Live page already computes.
function structureSummary(trend?: { price_vs_vwap: string; ma_crossover: string; trend_strength: string }) {
  if (!trend) return null;
  const parts: string[] = [];
  if (trend.ma_crossover === "BULLISH") parts.push("fast MA above slow MA");
  if (trend.ma_crossover === "BEARISH") parts.push("fast MA below slow MA");
  if (trend.price_vs_vwap !== "AT") parts.push(`price ${trend.price_vs_vwap.toLowerCase()} VWAP`);
  if (trend.trend_strength !== "NONE") parts.push(`${trend.trend_strength.toLowerCase()} trend (ADX)`);
  return parts.length > 0 ? parts.join(", ") : "No clear structure yet.";
}

export default function CommandCenterPage() {
  const health = useHealth();
  const { data: prediction } = usePrediction();
  const { data: live, fetchError: liveFetchError } = useLiveState();
  const { data: hlc, fetchError: hlcFetchError } = useHlcState();
  const { entries } = useJournalEntries();

  const graded = entries.filter((e) => e.outcome === "TARGET_HIT" || e.outcome === "STOP_HIT");
  const wins = graded.filter((e) => e.outcome === "TARGET_HIT").length;
  const winRate = graded.length > 0 ? Math.round((wins / graded.length) * 100) : null;

  const dataHealthy = !liveFetchError && !hlcFetchError && !live?.error && !hlc?.error;
  const bias = live?.suggestion?.bias;

  const regime = prediction?.regime;
  const best = prediction?.best;

  return (
    <Cockpit>
      <MarketBar title="Command Center" data={prediction}>
        {health && <span>expiry {health.expiry}</span>}
      </MarketBar>

      <p className="cockpit-lede">
        The day's situation in one screen: what to do right now, your HLC support/resistance, today's
        trade plan, and recent journal performance. Analytical output only — this never places an order.
      </p>

      <div className="command-center-header">
        <div className="command-stat">
          <span className="command-stat-label">Today's Trade</span>
          <span className={`command-stat-value ${best ? READINESS_CLASS[best.readiness] : "bias-neutral"}`}>
            {best ? READINESS_LABEL[best.readiness] : "STAND DOWN"}
          </span>
          <span className="command-stat-sub">
            {best ? best.name : "no setup worth taking"}
          </span>
        </div>
        <div className="command-stat">
          <span className="command-stat-label">Bias</span>
          <span className={`command-stat-value ${bias ? BIAS_CLASS[bias] : ""}`}>{bias ?? "-"}</span>
          {live?.ts && <span className="command-stat-sub">updated {fmtTime(live.ts)}</span>}
        </div>
        <div className="command-stat">
          <span className="command-stat-label">Confidence</span>
          <span className="command-stat-value">
            {live?.suggestion?.confidence !== undefined ? `${live.suggestion.confidence}%` : "-"}
          </span>
        </div>
        {/* Was a hardcoded "Trending" demo tile. The regime engine computes
            this for real now, so it reads from that instead. */}
        <div className="command-stat">
          <span className="command-stat-label">Market Regime</span>
          <span className="command-stat-value">
            {regime ? regime.structure_regime.toLowerCase() : "-"}
          </span>
          <span className="command-stat-sub">
            {regime ? regime.day_type.replace(/_/g, " ").toLowerCase() : "waiting for data"}
          </span>
        </div>
        {/* Was a hardcoded India VIX demo tile. VIX still isn't ingested, but
            the realized-vs-implied comparison answers the same question --
            is movement cheap or expensive -- from data we actually have. */}
        <div className="command-stat">
          <span className="command-stat-label">Option Pricing</span>
          <span className="command-stat-value">
            {regime ? regime.premium_pricing.toLowerCase() : "-"}
          </span>
          <span className="command-stat-sub">
            {regime?.implied_daily_move_points != null && regime?.realized_daily_move_points != null
              ? `${fmtNum(regime.implied_daily_move_points, 0)} priced vs ${fmtNum(regime.realized_daily_move_points, 0)} real`
              : "needs a live chain"}
          </span>
        </div>
        <div className="command-stat">
          <span className="command-stat-label">Data Health</span>
          <span className={`command-stat-value ${dataHealthy ? "bias-bullish" : "bias-bearish"}`}>
            {dataHealthy ? "OK" : "Degraded"}
          </span>
        </div>
      </div>

      <main className="dashboard-grid">
        <section className="panel dashboard-card">
          <h2>AI Market Summary</h2>
          {live?.suggestion ? (
            <>
              <div className="suggestion-headline">
                <span className={`bias-label ${BIAS_CLASS[live.suggestion.bias] ?? ""}`}>{live.suggestion.bias}</span>
                <span className="confidence">{live.suggestion.confidence}% confidence</span>
              </div>
              {live.trend && <p className="oi-strikes">Structure: {structureSummary(live.trend)}</p>}
              {live.suggestion.watch_level && <p className="oi-strikes">Watch: {live.suggestion.watch_level}</p>}
              <p className="rationale">{live.suggestion.rationale}</p>
            </>
          ) : (
            <p className="not-an-order">Waiting for the first live poll cycle.</p>
          )}
          <Link className="dashboard-card-link" to="/live">
            View Live Market &rarr;
          </Link>
        </section>

        <section className="panel dashboard-card">
          <h2>Support &amp; Resistance</h2>
          {hlc?.max_resistance !== undefined ? (
            <>
              <div className="metrics-row">
                <div className="metric">
                  <span className="metric-label">Resistance Band</span>
                  <span className="metric-value">
                    {fmtNum(hlc.min_resistance)} – {fmtNum(hlc.max_resistance)}
                  </span>
                </div>
                <div className="metric">
                  <span className="metric-label">Support Band</span>
                  <span className="metric-value">
                    {fmtNum(hlc.min_support)} – {fmtNum(hlc.max_support)}
                  </span>
                </div>
              </div>
              <p className="oi-strikes">
                From the HLC engine's last completed session ({hlc.session_date}) — not the doc's scored,
                multi-source zone model yet, see Market Structure.
              </p>
            </>
          ) : (
            <p className="not-an-order">No HLC range available yet — fetch the latest session on Trade Setups.</p>
          )}
          <Link className="dashboard-card-link" to="/hlc">
            View Trade Setups &rarr;
          </Link>
        </section>

        <section className="panel dashboard-card">
          <h2>Today's Plan</h2>
          {hlc?.trade_plan ? (
            <>
              <p className="oi-strikes">
                Plan for <strong>{hlc.trade_plan.trade_date}</strong> — built from the{" "}
                {hlc.trade_plan.session_date} close.
              </p>
              {hlc.trade_plan.legs.length > 0 ? (
                <table className="chain-table">
                  <thead>
                    <tr>
                      <th>Leg</th>
                      <th>Strike</th>
                      <th>Entry</th>
                      <th>Target</th>
                    </tr>
                  </thead>
                  <tbody>
                    {hlc.trade_plan.legs.map((leg) => (
                      <tr key={leg.option_type}>
                        <td>{leg.option_type}</td>
                        <td className="strike-cell">{fmtNum(leg.strike, 0)}</td>
                        <td>{fmtNum(leg.entry_trigger)}</td>
                        <td>{fmtNum(leg.target)}</td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              ) : (
                <p className="not-an-order">{hlc.trade_plan.note}</p>
              )}
            </>
          ) : (
            <p className="not-an-order">No plan available yet — fetch the latest session on Trade Setups.</p>
          )}
          <Link className="dashboard-card-link" to="/hlc">
            View Trade Setups &rarr;
          </Link>
        </section>

        <section className="panel dashboard-card">
          <h2>Journal Snapshot</h2>
          {entries.length > 0 ? (
            <>
              <div className="metrics-row">
                <div className="metric">
                  <span className="metric-label">Win Rate</span>
                  <span className="metric-value">{winRate !== null ? `${winRate}%` : "-"}</span>
                  <span className="metric-sub">{graded.length} graded trades</span>
                </div>
              </div>
              <table className="chain-table">
                <thead>
                  <tr>
                    <th>Trade Date</th>
                    <th>Leg</th>
                    <th>Outcome</th>
                  </tr>
                </thead>
                <tbody>
                  {entries.slice(0, 5).map((entry) => (
                    <tr key={entry.id}>
                      <td>{entry.trade_date}</td>
                      <td>{entry.option_type ?? "-"}</td>
                      <td>{entry.outcome}</td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </>
          ) : (
            <p className="not-an-order">No journal entries yet.</p>
          )}
          <Link className="dashboard-card-link" to="/journal">
            View Journal &rarr;
          </Link>
        </section>
      </main>
    </Cockpit>
  );
}
