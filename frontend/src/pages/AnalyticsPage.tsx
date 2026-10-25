import { Cockpit, MarketBar } from "../components/Cockpit";
import { useAnalyticsByRegime } from "../hooks/useAnalyticsByRegime";
import { fmtNum } from "../format";
import { useJournalEntries } from "../hooks/useJournalEntries";
import type { JournalEntry } from "../types";

function average(values: number[]): number | null {
  if (values.length === 0) return null;
  return values.reduce((a, b) => a + b, 0) / values.length;
}

function computeStats(entries: JournalEntry[]) {
  const graded = entries.filter((e) => e.outcome === "TARGET_HIT" || e.outcome === "STOP_HIT");
  const wins = graded.filter((e) => e.outcome === "TARGET_HIT");
  const losses = graded.filter((e) => e.outcome === "STOP_HIT");
  const noTrade = entries.filter((e) => e.outcome === "NO_TRADE").length;

  const winPoints = wins.map((e) => e.realized_points ?? 0);
  const lossPoints = losses.map((e) => Math.abs(e.realized_points ?? 0));

  const avgWin = average(winPoints);
  const avgLoss = average(lossPoints);
  const totalWinPoints = winPoints.reduce((a, b) => a + b, 0);
  const totalLossPoints = lossPoints.reduce((a, b) => a + b, 0);
  const profitFactor = totalLossPoints > 0 ? totalWinPoints / totalLossPoints : null;

  const byLeg: Record<string, { wins: number; losses: number }> = {};
  for (const e of graded) {
    const leg = e.option_type ?? "-";
    byLeg[leg] ??= { wins: 0, losses: 0 };
    if (e.outcome === "TARGET_HIT") byLeg[leg].wins += 1;
    else byLeg[leg].losses += 1;
  }

  return {
    totalGraded: graded.length,
    winRate: graded.length > 0 ? Math.round((wins.length / graded.length) * 100) : null,
    avgWin,
    avgLoss,
    profitFactor,
    noTrade,
    byLeg,
  };
}

export default function AnalyticsPage() {
  const { entries, loading, error } = useJournalEntries(200);
  const stats = computeStats(entries);
  const byRegime = useAnalyticsByRegime().data?.by_regime ?? [];

  return (
    <Cockpit>
      <MarketBar title="Analytics" />
      <p className="cockpit-lede">
        Real performance numbers computed from your Journal history, plus a preview of the deeper breakdown (regime performance, Sharpe/drawdown) the requirement doc calls for once Backtest exists.
      </p>

      <main className="cockpit-stack">
        {loading && <div className="banner banner-info">Loading journal history...</div>}
        {error && <div className="banner banner-error">Connection error: {error}</div>}

        <section className="panel">
          <h2>Journal Performance (real)</h2>
          {stats.totalGraded > 0 ? (
            <>
              <div className="metrics-row">
                <div className="metric">
                  <span className="metric-label">Graded Trades</span>
                  <span className="metric-value">{stats.totalGraded}</span>
                </div>
                <div className="metric">
                  <span className="metric-label">Win Rate</span>
                  <span className="metric-value">{stats.winRate}%</span>
                </div>
                <div className="metric">
                  <span className="metric-label">Avg Win</span>
                  <span className="metric-value">{stats.avgWin !== null ? fmtNum(stats.avgWin) : "-"} pts</span>
                </div>
                <div className="metric">
                  <span className="metric-label">Avg Loss</span>
                  <span className="metric-value">{stats.avgLoss !== null ? fmtNum(stats.avgLoss) : "-"} pts</span>
                </div>
                <div className="metric">
                  <span className="metric-label">Profit Factor</span>
                  <span className="metric-value">{stats.profitFactor !== null ? fmtNum(stats.profitFactor) : "-"}</span>
                </div>
                <div className="metric">
                  <span className="metric-label">No-Trade Days</span>
                  <span className="metric-value">{stats.noTrade}</span>
                </div>
              </div>
              <table className="chain-table" style={{ marginTop: 14 }}>
                <thead>
                  <tr>
                    <th>Leg</th>
                    <th>Wins</th>
                    <th>Losses</th>
                  </tr>
                </thead>
                <tbody>
                  {Object.entries(stats.byLeg).map(([leg, s]) => (
                    <tr key={leg}>
                      <td>{leg}</td>
                      <td>{s.wins}</td>
                      <td>{s.losses}</td>
                    </tr>
                  ))}
                </tbody>
              </table>
              <p className="not-an-order">
                Computed directly from real Journal rows — small sample sizes early on can be misleading;
                see the requirement doc's note on always showing sample size alongside any win rate.
              </p>
            </>
          ) : (
            <p className="not-an-order">Not enough graded journal entries yet to compute real stats.</p>
          )}
        </section>

        <section className="panel">
          <h2>Strategy Performance by Market Regime</h2>
          <p className="oi-strikes">
            Your graded journal trades, split by the market regime the engine recorded for that
            trading day. Trades taken before the regime engine existed have no label and are grouped
            as "Not recorded" rather than guessed at.
          </p>
          {byRegime.length === 0 ? (
            <p className="not-an-order">
              No graded trades yet. This fills in as the journal accumulates days.
            </p>
          ) : (
            <table className="chain-table">
              <thead>
                <tr>
                  <th>Regime</th>
                  <th>Trades</th>
                  <th>Won</th>
                  <th>Lost</th>
                  <th>Win Rate</th>
                  <th>Avg Points</th>
                </tr>
              </thead>
              <tbody>
                {byRegime.map((row) => (
                  <tr key={row.label}>
                    <td>{row.label}</td>
                    <td>{row.sample}</td>
                    <td>{row.wins}</td>
                    <td>{row.losses}</td>
                    <td>{row.hit_rate === null ? "-" : `${fmtNum(row.hit_rate, 0)}%`}</td>
                    <td>{fmtNum(row.avg_points, 1)}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          )}
        </section>
      </main>
    </Cockpit>
  );
}
