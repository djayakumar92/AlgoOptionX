import type { Workspace } from "../types";
import { Icon, Badge, Panel } from "../../../shared/ui";
import { RiskPanel } from "../components";

export function DecisionEnginePage({
  state,
  act,
  busy,
}: {
  state: Workspace;
  act: (action: string, fields?: object) => void;
  busy: boolean;
}) {
  return (
    <div className="ax-split">
      <Panel
        title="A decision you can inspect."
        eyebrow="RULE-BASED · NOT A TRAINED AI MODEL"
        className="ax-decision-panel"
      >
        <div className="ax-decision-symbol">
          <Icon name="spark" size={28} />
        </div>
        <Badge tone={state.decision.action === "WAIT" ? "" : "green"}>
          {state.decision.action}
        </Badge>
        <h3>
          {state.decision.action === "WAIT"
            ? "Wait for a clearer move."
            : "Synthetic momentum detected."}
        </h3>
        <p>{state.decision.explanation}</p>
        <div className="ax-signal-grid">
          <div>
            <span>5-bar spot change</span>
            <strong>
              {state.decision.change > 0 ? "+" : ""}
              {state.decision.change} pts
            </strong>
          </div>
          <div>
            <span>Evaluation cadence</span>
            <strong>Every 6 bars</strong>
          </div>
          <div>
            <span>Trade size</span>
            <strong>1 fixture lot</strong>
          </div>
        </div>
        <button
          className={`ax-button ${state.account.autonomous ? "subtle" : "primary"}`}
          disabled={busy || !!state.account.killed}
          onClick={() =>
            act("control", { autonomous: !state.account.autonomous })
          }
        >
          {state.account.autonomous
            ? "Disable autonomous entries"
            : "Enable autonomous paper entries"}
          <Icon name="arrow" size={16} />
        </button>
        <p className="ax-footnote">
          Playback must be running, or bars advanced manually. Existing stops
          and targets remain active when entries are disabled.
        </p>
      </Panel>
      <div className="ax-stack">
        <RiskPanel state={state} />
        <Panel title="The decision contract">
          <ol className="ax-steps">
            <li>
              <span>01</span>
              <div>
                <strong>Observe</strong>
                <p>
                  Read only synthetic bars available at this point in the
                  session.
                </p>
              </div>
            </li>
            <li>
              <span>02</span>
              <div>
                <strong>Propose</strong>
                <p>
                  Follow a five-bar move of at least 5 points. Otherwise, wait.
                </p>
              </div>
            </li>
            <li>
              <span>03</span>
              <div>
                <strong>Validate & execute</strong>
                <p>
                  Check cash, exposure, loss limits and duplicates before each
                  virtual fill.
                </p>
              </div>
            </li>
          </ol>
        </Panel>
      </div>
    </div>
  );
}
