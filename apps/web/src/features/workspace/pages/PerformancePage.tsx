import type { Workspace } from "../types";
import { money } from "../lib/format";
import { Panel } from "../../../shared/ui";
import { AccountSummary, RiskPanel, ActivityPanel } from "../components";

export function PerformancePage({ state }: { state: Workspace }) {
  const exits = state.events.filter((e) => e.kind === "SELL");
  const wins = exits.filter((e) => (e.payload.pnl || 0) > 0).length;
  return (
    <>
      <AccountSummary state={state} />
      <div className="ax-split">
        <Panel
          title="Performance breakdown"
          eyebrow="CURRENT SYNTHETIC SESSION"
        >
          <div className="ax-risk-list">
            {[
              [
                "Realized P&L · all fees included",
                money(state.account.realized),
              ],
              [
                "Unrealized P&L · mid-price mark",
                money(state.account.unrealized),
              ],
              ["Fees paid", money(state.account.fees)],
              ["Closed trades in recent 150 events", exits.length],
              [
                "Wins / closed trades in recent feed",
                exits.length ? `${wins} / ${exits.length}` : "Not enough data",
              ],
            ].map(([label, value]) => (
              <div className="ax-risk-row" key={label}>
                <span>{label}</span>
                <strong>{value}</strong>
              </div>
            ))}
          </div>
          <p className="ax-footnote">
            Session equity = cash + positions valued at synthetic mid prices.
            Exit estimates include the bid spread, slippage and exit fee.
            Results are simulated, not evidence of real-world returns.
          </p>
        </Panel>
        <RiskPanel state={state} />
      </div>
      <ActivityPanel state={state} />
    </>
  );
}
