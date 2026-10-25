import { Cockpit, MarketBar } from "../components/Cockpit";
import { fmtNum } from "../format";
import { useJournalEntries } from "../hooks/useJournalEntries";
import type { JournalOutcome } from "../types";

const OUTCOME_LABEL: Record<JournalOutcome, string> = {
  PENDING: "Pending",
  NOT_TRIGGERED: "Not Triggered",
  TARGET_HIT: "Target Hit",
  STOP_HIT: "Stop Hit",
  OPEN_AT_CLOSE: "Open at Close",
  NO_TRADE: "Sat Out",
};

const OUTCOME_COLOR: Record<JournalOutcome, string> = {
  PENDING: "var(--neutral)",
  NOT_TRIGGERED: "var(--neutral)",
  TARGET_HIT: "var(--bullish)",
  STOP_HIT: "var(--bearish)",
  OPEN_AT_CLOSE: "var(--neutral)",
  NO_TRADE: "var(--neutral)",
};

export default function JournalPage() {
  const { entries, loading, error } = useJournalEntries();

  return (
    <Cockpit>
      <MarketBar title="Journal" />
      <p className="cockpit-lede">
        Every trading day's HLC-based plan (see the HLC page) — built from the previous session's close, meant to be acted on the trade date shown here — and whether it actually worked out, graded once that trade date's own session is fully closed by replaying its real 5-minute candles against the planned entry/target/stop. A record of what already happened, not a live view.
      </p>
      <main className="cockpit-stack">
        {loading && <div className="banner banner-info">Loading journal...</div>}
        {error && <div className="banner banner-error">Connection error: {error}</div>}
        {!loading && !error && entries.length === 0 && (
          <p className="not-an-order">No journal entries yet — one gets logged the next time the HLC page fetches a new session's plan.</p>
        )}
        {entries.length > 0 && (
          <section className="panel chain-panel">
            <table className="chain-table">
              <thead>
                <tr>
                  <th>Trade Date</th>
                  <th>Based On</th>
                  <th>Signal</th>
                  <th>Leg</th>
                  <th>Strike</th>
                  <th>Entry</th>
                  <th>Target</th>
                  <th>Points</th>
                  <th>Outcome</th>
                  <th>Realized</th>
                </tr>
              </thead>
              <tbody>
                {entries.map((entry) => (
                  <tr key={entry.id} title={entry.note ?? undefined}>
                    <td>{entry.trade_date}</td>
                    <td>{entry.session_date}</td>
                    <td>{entry.combined_signal}</td>
                    <td>{entry.option_type ?? "-"}</td>
                    <td className="strike-cell">{entry.strike !== null ? fmtNum(entry.strike, 0) : "-"}</td>
                    <td>{fmtNum(entry.entry_trigger)}</td>
                    <td>{fmtNum(entry.target)}</td>
                    <td>{fmtNum(entry.target_points)}</td>
                    <td style={{ color: OUTCOME_COLOR[entry.outcome] }}>{OUTCOME_LABEL[entry.outcome]}</td>
                    <td>{fmtNum(entry.realized_points)}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </section>
        )}
      </main>
    </Cockpit>
  );
}
