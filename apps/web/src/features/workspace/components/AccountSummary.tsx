import type { Workspace } from "../types";
import { money } from "../lib/format";
import { Icon } from "../../../shared/ui/Icon";
import type { IconName } from "../../../shared/ui/Icon";

export function AccountSummary({ state }: { state: Workspace }) {
  const a = state.account;
  return (
    <div className="ax-stats">
      {[
        {
          label: "Total equity",
          value: money(a.equity, 0),
          detail: "₹5,00,000 virtual starting capital",
          icon: "wallet" as IconName,
        },
        {
          label: "Session P&L",
          value: money(a.pnl),
          detail: `${a.pnl >= 0 ? "+" : ""}${((a.pnl / a.capital) * 100).toFixed(2)}% · marked at mid price`,
          icon: "chart" as IconName,
          tone: a.pnl >= 0 ? "positive" : "negative",
        },
        {
          label: "Available cash",
          value: money(a.cash, 0),
          detail: `${money(a.exposure, 0)} premium deployed`,
          icon: "grid" as IconName,
        },
        {
          label: "Open positions",
          value: String(state.positions.length).padStart(2, "0"),
          detail: `of ${state.risk.max_positions} permitted · long options only`,
          icon: "shield" as IconName,
        },
      ].map((s) => (
        <div className="ax-stat" key={s.label}>
          <div className="ax-stat-label">
            {s.label}
            <Icon name={s.icon} />
          </div>
          <div className={`ax-stat-value ${s.tone || ""}`}>{s.value}</div>
          <div className="ax-stat-detail">{s.detail}</div>
        </div>
      ))}
    </div>
  );
}
