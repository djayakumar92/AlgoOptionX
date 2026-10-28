import type { Workspace } from "../types";
import { money } from "../lib/format";
import { Icon } from "../../../shared/ui/Icon";
import { Badge } from "../../../shared/ui/Badge";
import { Panel } from "../../../shared/ui/Panel";

export function RiskPanel({ state }: { state: Workspace }) {
  const used = (state.account.exposure / state.risk.max_exposure) * 100;
  return (
    <Panel title="Risk guardrails" action={<Icon name="shield" />}>
      <div className="ax-risk-list">
        <div className="ax-risk-status">
          <span className={`ax-dot ${state.account.killed ? "red" : ""}`} />
          {state.account.killed
            ? "Entries blocked · kill switch active"
            : "Deterministic risk checks active"}
        </div>
        <div className="ax-risk-row">
          <span>Premium exposure</span>
          <strong>{used.toFixed(1)}%</strong>
        </div>
        <div className="ax-meter">
          <i style={{ width: `${Math.min(used, 100)}%` }} />
        </div>
        <div className="ax-risk-caption">
          {money(state.account.exposure, 0)} /{" "}
          {money(state.risk.max_exposure, 0)}
        </div>
        <div className="ax-risk-row">
          <span>Per-trade stop-risk cap</span>
          <strong>{money(state.risk.max_trade_risk, 0)}</strong>
        </div>
        <div className="ax-risk-row">
          <span>Daily entry lock threshold</span>
          <strong>{money(state.risk.max_daily_loss, 0)}</strong>
        </div>
        <div className="ax-risk-row">
          <span>Maximum open positions</span>
          <strong>03</strong>
        </div>
        <div className="ax-risk-row">
          <span>Execution mode</span>
          <Badge tone="green">PAPER ONLY</Badge>
        </div>
        <p className="ax-note">
          Stops are virtual exit triggers. Gaps may exceed their planned loss.
          No broker orders are sent.
        </p>
      </div>
    </Panel>
  );
}
