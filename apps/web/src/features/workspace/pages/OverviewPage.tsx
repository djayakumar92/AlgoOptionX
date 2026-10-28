import { NavLink } from "react-router-dom";
import type { Workspace } from "../types";
import { number } from "../../../shared/lib/format";
import { Icon, Badge, Panel, LineChart } from "../../../shared/ui";
import {
  AccountSummary,
  PositionsPanel,
  RiskPanel,
  ActivityPanel,
} from "../components";

export function OverviewPage({
  state,
  act,
  busy,
}: {
  state: Workspace;
  act: (action: string, fields?: object) => void;
  busy: boolean;
}) {
  return (
    <>
      <AccountSummary state={state} />
      <div className="ax-split">
        <Panel
          title="Market overview"
          eyebrow="NIFTY 50 · SYNTHETIC INDEX"
          action={
            <NavLink to="/market" className="ax-text-link">
              Open terminal <Icon name="arrow" size={14} />
            </NavLink>
          }
        >
          <div className="ax-chart-heading">
            <div className="ax-quote">
              {number(state.market.spot)}
              <span
                className={state.decision.change >= 0 ? "positive" : "negative"}
              >
                {state.decision.change >= 0 ? "+" : ""}
                {state.decision.change.toFixed(2)} <small>over 5 bars</small>
              </span>
            </div>
            <div className="ax-chart-legend">
              <i className="ax-dot" />
              NIFTY 50 <span>1m</span>
            </div>
          </div>
          <LineChart
            values={state.history.map((p) => p.spot)}
            label="NIFTY price"
          />
          <div className="ax-chart-footer">
            <span>02 NOV 2026 · SIMULATED</span>
            <span>Seed 17 · no market-data credentials required</span>
          </div>
        </Panel>
        <div className="ax-engine-card">
          <div className="ax-engine-head">
            <span className="ax-engine-icon">
              <Icon name="spark" size={23} />
            </span>
            <Badge tone={state.account.autonomous ? "green" : "purple"}>
              {state.account.autonomous ? "ENABLED" : "STANDBY"}
            </Badge>
          </div>
          <div className="ax-eyebrow">DECISION ENGINE</div>
          <h2>
            Reason first. <br />
            Act with discipline.
          </h2>
          <p>
            A transparent fixture rule. Deterministic risk checks. Every virtual
            action recorded.
          </p>
          <div className="ax-engine-signal">
            <span>Current signal</span>
            <strong>{state.decision.action}</strong>
          </div>
          <NavLink to="/strategy" className="ax-button primary full">
            Explore the engine <Icon name="arrow" size={16} />
          </NavLink>
          <small>Research rules, not validated predictions.</small>
        </div>
      </div>
      <PositionsPanel state={state} act={act} busy={busy} />
      <div className="ax-split">
        <ActivityPanel state={state} />
        <RiskPanel state={state} />
      </div>
    </>
  );
}
