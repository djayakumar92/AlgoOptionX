import { useState } from "react";
import { Cockpit, MarketBar } from "../components/Cockpit";
import { fmtNum } from "../format";
import { useBacktest } from "../hooks/useBacktest";
import type { BacktestResult } from "../types";

function isoDaysAgo(days: number): string {
  const d = new Date();
  d.setDate(d.getDate() - days);
  return d.toISOString().slice(0, 10);
}

function pct(v: number | null): string {
  return v === null ? "-" : `${(v * 100).toFixed(1)}%`;
}

function ResultMetrics({ result }: { result: BacktestResult }) {
  if (result.error) {
    return <div className="banner banner-error">Run failed: {result.error}</div>;
  }
  return (
    <>
      <div className="metrics-row">
        <div className="metric">
          <span className="metric-label">Trading Days</span>
          <span className="metric-value">{result.total_days}</span>
        </div>
        <div className="metric">
          <span className="metric-label">Graded Trades</span>
          <span className="metric-value">{result.graded_trades}</span>
          <span className="metric-sub">{result.no_trade_days} sat out, {result.not_triggered} never triggered</span>
        </div>
        <div className="metric">
          <span className="metric-label">Net Points</span>
          <span className={`metric-value ${(result.net_points ?? 0) >= 0 ? "bias-bullish" : "bias-bearish"}`}>
            {fmtNum(result.net_points)}
          </span>
        </div>
        <div className="metric">
          <span className="metric-label">Win Rate</span>
          <span className="metric-value">{pct(result.win_rate)}</span>
        </div>
        <div className="metric">
          <span className="metric-label">Profit Factor</span>
          <span className="metric-value">{result.profit_factor !== null ? fmtNum(result.profit_factor) : "-"}</span>
        </div>
        <div className="metric">
          <span className="metric-label">Expectancy</span>
          <span className="metric-value">{result.expectancy_points !== null ? `${fmtNum(result.expectancy_points)} pts` : "-"}</span>
        </div>
        <div className="metric">
          <span className="metric-label">Average R</span>
          <span className="metric-value">{result.avg_r !== null ? fmtNum(result.avg_r) : "-"}</span>
        </div>
        <div className="metric">
          <span className="metric-label">Max Drawdown</span>
          <span className="metric-value">{result.max_drawdown_points !== null ? `${fmtNum(result.max_drawdown_points)} pts` : "-"}</span>
        </div>
        <div className="metric">
          <span className="metric-label">Largest Win</span>
          <span className="metric-value">{result.largest_win !== null ? fmtNum(result.largest_win) : "-"}</span>
        </div>
        <div className="metric">
          <span className="metric-label">Largest Loss</span>
          <span className="metric-value">{result.largest_loss !== null ? fmtNum(result.largest_loss) : "-"}</span>
        </div>
        <div className="metric">
          <span className="metric-label">Consecutive Losses</span>
          <span className="metric-value">{result.max_consecutive_losses}</span>
        </div>
      </div>
      <p className="not-an-order">
        {result.graded_trades !== null && result.graded_trades < 15
          ? `Only ${result.graded_trades} graded trades — treat every ratio above as indicative, not proof, at this sample size.`
          : `Based on ${result.graded_trades} graded trades across ${result.total_days} trading days.`}{" "}
        Sharpe/Sortino aren't shown — this app has no real basis (risk-free rate, consistent return period) to
        compute them honestly yet.
      </p>
    </>
  );
}

export default function BacktestPage() {
  const [from, setFrom] = useState(isoDaysAgo(9));
  const [to, setTo] = useState(isoDaysAgo(2));
  const { status, fetchError, run, runError, running } = useBacktest();

  const progress = status?.progress;
  const result = status?.result;

  return (
    <Cockpit>
      <MarketBar title="Backtest" />
      <p className="cockpit-lede">
        Runs your real HLC trade rule across a range of past trading days — replaying each day's actual 5-minute candles against the plan the rule would have produced, the same mechanism the Journal uses for one day at a time. Analytical output only — this never places an order.
      </p>

      <main className="cockpit-stack">
        <div className="banner banner-warning">
          Every day in a run is priced using the <strong>currently tracked option expiry</strong>, not the
          expiry that was actually active on that historical date. This is accurate for the last week or so;
          going back further than the current weekly cycle mixes in contracts that didn't really exist at
          that price on that day. Keep ranges short (recent trading days) until this is resolved.
        </div>

        <section className="panel">
          <h2>Backtest Configuration</h2>
          <div className="replay-controls">
            <label>
              From{" "}
              <input type="date" value={from} onChange={(e) => setFrom(e.target.value)} disabled={running} />
            </label>
            <label>
              To{" "}
              <input type="date" value={to} onChange={(e) => setTo(e.target.value)} disabled={running} />
            </label>
            <label>
              Strategy{" "}
              <select defaultValue="hlc" disabled>
                <option value="hlc">HLC Trade Plan (current)</option>
              </select>
            </label>
            <button className="fetch-latest-button" onClick={() => run(from, to)} disabled={running}>
              {running ? "Running..." : "Run Backtest"}
            </button>
          </div>
          <p className="oi-strikes">
            Each new (not-already-graded) day makes real, rate-limited DhanHQ calls — a multi-week range can
            take several minutes. Days already in your Journal are skipped, so re-running an overlapping
            range only pays for the new days.
          </p>
          {runError && <div className="banner banner-warning">{runError}</div>}
          {fetchError && <div className="banner banner-error">Connection error: {fetchError}</div>}
        </section>

        {progress && progress.status === "RUNNING" && (
          <section className="panel">
            <h2>Progress</h2>
            <input
              className="replay-scrubber"
              type="range"
              min={0}
              max={Math.max(1, progress.total)}
              value={progress.current}
              disabled
            />
            <p className="oi-strikes">
              Day {progress.current} of {progress.total}
              {progress.current_date ? ` — currently on ${progress.current_date}` : ""}
            </p>
          </section>
        )}

        {progress && progress.status === "FAILED" && status?.error && (
          <div className="banner banner-error">Backtest failed: {status.error}</div>
        )}

        {result && (
          <section className="panel">
            <h2>
              Result — {result.start_date} to {result.end_date}
            </h2>
            <ResultMetrics result={result} />
          </section>
        )}
      </main>
    </Cockpit>
  );
}
