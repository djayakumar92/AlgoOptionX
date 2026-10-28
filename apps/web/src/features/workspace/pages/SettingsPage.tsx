import { useState } from "react";
import type { Workspace } from "../types";
import { Icon, Panel } from "../../../shared/ui";
import { RiskPanel } from "../components";

export function SettingsPage({
  state,
  act,
  busy,
  fresh,
}: {
  state: Workspace;
  act: (action: string, fields?: object) => void;
  busy: boolean;
  fresh: () => void;
}) {
  const [confirm, setConfirm] = useState(false);
  return (
    <div className="ax-split">
      <div className="ax-stack">
        <Panel title="Your AlgoOptionX workspace" eyebrow="LOCAL & PRIVATE">
          <div className="ax-risk-list">
            {[
              ["Application", "AlgoOptionX"],
              ["Environment", "Local synthetic market"],
              ["Execution", "Paper only · no broker connection"],
              ["Session ID", state.account.id.slice(0, 18) + "…"],
              ["Market clock", "02 Nov 2026 · Asia/Kolkata"],
              [
                "Fixture lot size",
                "65 units · not a live exchange specification",
              ],
              ["Market seed", "17 · deterministic"],
            ].map(([label, value]) => (
              <div className="ax-risk-row" key={label}>
                <span>{label}</span>
                <strong>{value}</strong>
              </div>
            ))}
          </div>
        </Panel>
        <Panel title="Start a fresh session">
          <p className="ax-body-text">
            Create a new ₹5,00,000 virtual account and reset the synthetic
            market clock. Prior accounts and their event history remain stored.
            Close all positions first.
          </p>
          {confirm ? (
            <div className="ax-actions">
              <button
                className="ax-button primary"
                disabled={busy}
                onClick={() => {
                  fresh();
                  setConfirm(false);
                }}
              >
                Create new paper session
              </button>
              <button
                className="ax-button subtle"
                onClick={() => setConfirm(false)}
              >
                Cancel
              </button>
            </div>
          ) : (
            <button
              className="ax-button subtle"
              disabled={busy || state.positions.length > 0}
              onClick={() => setConfirm(true)}
            >
              New paper session <Icon name="arrow" size={16} />
            </button>
          )}
        </Panel>
      </div>
      <div className="ax-stack">
        <RiskPanel state={state} />
        <Panel title="Emergency controls">
          <p className="ax-body-text">
            The kill switch immediately closes all virtual positions at the
            synthetic bid with slippage, disables autonomous entries, and blocks
            new buys. Playback can continue.
          </p>
          <button
            className={`ax-button ${state.account.killed ? "subtle" : "danger"}`}
            disabled={busy}
            onClick={() => act("control", { killed: !state.account.killed })}
          >
            <Icon name="shield" />
            {state.account.killed
              ? "Release kill switch"
              : "Activate kill switch"}
          </button>
          <p className="ax-footnote">
            This local workspace has no hosted authentication or multi-tenant
            isolation. Live trading is not available.
          </p>
        </Panel>
      </div>
    </div>
  );
}
