import { useEffect, useState } from "react";
import { api, contractName, money, number } from "../workspace";
import type { Workspace, ReplayResult, Contract } from "../workspace";
import {
  Icon,
  Badge,
  Panel,
  LineChart,
  Empty,
  Stats,
  Risk,
  Activity,
} from "../components/WorkspaceUI";

export function Terminal({
  state,
  act,
  busy,
}: {
  state: Workspace;
  act: (action: string, fields?: object) => void;
  busy: boolean;
}) {
  const [right, setRight] = useState("ALL");
  const [selection, setSelection] = useState<Contract | null>(null);
  const [lots, setLots] = useState(1);
  const selected = state.market.contracts.find((q) => q.id === selection?.id);
  useEffect(() => {
    if (!selection) return;
    const previous = document.activeElement as HTMLElement | null;
    const oldOverflow = document.body.style.overflow;
    document.body.style.overflow = "hidden";
    document.querySelector<HTMLElement>('[role="dialog"] button')?.focus();
    const handler = (event: KeyboardEvent) => {
      if (event.key === "Escape") {
        setSelection(null);
        return;
      }
      if (event.key !== "Tab") return;
      const nodes = [
        ...document.querySelectorAll<HTMLElement>(
          '[role="dialog"] button:not(:disabled), [role="dialog"] select:not(:disabled)',
        ),
      ];
      const first = nodes[0],
        last = nodes.at(-1);
      if (event.shiftKey && document.activeElement === first) {
        event.preventDefault();
        last?.focus();
      } else if (!event.shiftKey && document.activeElement === last) {
        event.preventDefault();
        first?.focus();
      }
    };
    document.addEventListener("keydown", handler);
    return () => {
      document.body.style.overflow = oldOverflow;
      document.removeEventListener("keydown", handler);
      previous?.focus();
    };
  }, [selection]);
  return (
    <>
      <div className="ax-split">
        <Panel
          title="NIFTY 50"
          eyebrow="SYNTHETIC INDEX"
          action={<Badge>1 MIN BARS</Badge>}
        >
          <div className="ax-quote">
            {number(state.market.spot)}
            <span>INR · simulated</span>
          </div>
          <LineChart
            values={state.history.map((p) => p.spot)}
            label="NIFTY price"
          />
        </Panel>
        <Risk state={state} />
      </div>
      <Panel
        title="Options chain"
        eyebrow="FIXTURE EXPIRY · 03 NOV 2026"
        action={
          <div className="ax-filters compact">
            {["ALL", "CE", "PE"].map((t) => (
              <button
                key={t}
                className={right === t ? "active" : ""}
                onClick={() => setRight(t)}
              >
                {t === "ALL" ? "All contracts" : t === "CE" ? "Calls" : "Puts"}
              </button>
            ))}
          </div>
        }
      >
        <div className="ax-table-wrap">
          <table>
            <thead>
              <tr>
                <th>Contract</th>
                <th>Bid</th>
                <th>Ask</th>
                <th>IV</th>
                <th>Open interest</th>
                <th>Volume</th>
                <th>Action</th>
              </tr>
            </thead>
            <tbody>
              {state.market.contracts
                .filter((q) => right === "ALL" || q.right === right)
                .map((q) => (
                  <tr key={q.id}>
                    <td>
                      <strong>
                        NIFTY {q.strike}{" "}
                        <span
                          className={`ax-contract ${q.right === "CE" ? "call" : "put"}`}
                        >
                          {q.right}
                        </span>
                      </strong>
                      <small>{q.lot_size} units / fixture lot</small>
                    </td>
                    <td>{money(q.bid)}</td>
                    <td>{money(q.ask)}</td>
                    <td>{q.iv}%</td>
                    <td>{number(q.oi)}</td>
                    <td>{number(q.volume)}</td>
                    <td>
                      <button
                        className="ax-button subtle"
                        disabled={busy || !!state.account.killed}
                        onClick={() => {
                          setSelection(q);
                          setLots(1);
                        }}
                      >
                        Buy paper
                      </button>
                    </td>
                  </tr>
                ))}
            </tbody>
          </table>
        </div>
      </Panel>
      {selected && (
        <div className="ax-modal-backdrop" onClick={() => setSelection(null)}>
          <section
            className="ax-modal"
            role="dialog"
            aria-modal="true"
            aria-labelledby="order-title"
            onClick={(e) => e.stopPropagation()}
          >
            <button
              className="ax-icon-button ax-modal-close"
              aria-label="Close order ticket"
              onClick={() => setSelection(null)}
            >
              <Icon name="close" />
            </button>
            <Badge tone="green">VIRTUAL BUY</Badge>
            <h2 id="order-title">{contractName(selected.id)}</h2>
            <p>Long option · synthetic expiry 03 Nov 2026</p>
            <label className="ax-field">
              Number of lots
              <select
                value={lots}
                onChange={(e) => setLots(Number(e.target.value))}
              >
                {[1, 2, 3, 4, 5].map((n) => (
                  <option key={n} value={n}>
                    {n} lot{n > 1 ? "s" : ""} · {n * selected.lot_size} units
                  </option>
                ))}
              </select>
            </label>
            <div className="ax-risk-list">
              <div className="ax-risk-row">
                <span>Indicative buy fill</span>
                <strong>{money(selected.ask + 5)}</strong>
              </div>
              <div className="ax-risk-row">
                <span>Premium + entry fee</span>
                <strong>
                  {money(
                    (selected.ask + 5) * lots * selected.lot_size +
                      state.risk.fee_per_fill,
                  )}
                </strong>
              </div>
              <div className="ax-risk-row">
                <span>Stop / target</span>
                <strong>−8% / +12%</strong>
              </div>
            </div>
            <p className="ax-note">
              Execution adds ₹0.05 slippage to the ask and ₹20 per fill. Final
              quote and risk limits are checked when submitted.
            </p>
            <button
              className="ax-button primary full"
              disabled={busy}
              onClick={() => {
                act("buy", { instrument: selected.id, lots });
                setSelection(null);
              }}
            >
              Confirm virtual buy <Icon name="arrow" size={16} />
            </button>
            <button
              className="ax-button full subtle"
              onClick={() => setSelection(null)}
            >
              Cancel
            </button>
          </section>
        </div>
      )}
    </>
  );
}
export function Decision({
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
        <Risk state={state} />
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
export function ReplayLab() {
  const [bars, setBars] = useState(120),
    [result, setResult] = useState<ReplayResult | null>(null),
    [loading, setLoading] = useState(false),
    [error, setError] = useState("");
  async function run() {
    setLoading(true);
    setError("");
    try {
      setResult(await api<ReplayResult>("replay", { bars }));
    } catch (e) {
      setError((e as Error).message);
    } finally {
      setLoading(false);
    }
  }
  return (
    <>
      <div className="ax-research-banner">
        <Icon name="replay" size={25} />
        <div>
          <h2>Rewind. Replay. Understand.</h2>
          <p>
            A deterministic experiment in a separate account. Your active
            portfolio stays untouched.
          </p>
        </div>
        <Badge>SEED 17</Badge>
      </div>
      <Panel title="Configure a replay" eyebrow="SYNTHETIC MOMENTUM V1">
        <div className="ax-replay-controls">
          <label className="ax-field">
            Session length
            <select
              value={bars}
              onChange={(e) => setBars(Number(e.target.value))}
            >
              <option value={60}>60 one-minute bars</option>
              <option value={120}>120 one-minute bars</option>
              <option value={240}>240 one-minute bars</option>
              <option value={374}>Full synthetic session</option>
            </select>
          </label>
          <div className="ax-replay-assumptions">
            <span>
              Starting capital <strong>₹5,00,000</strong>
            </span>
            <span>
              Fees <strong>₹20 / fill</strong>
            </span>
            <span>
              Slippage <strong>₹0.05 / unit</strong>
            </span>
          </div>
          <button
            className="ax-button primary"
            disabled={loading}
            onClick={run}
          >
            <Icon name="play" size={16} />
            {loading ? "Running replay…" : "Run experiment"}
          </button>
        </div>
        {error && (
          <p role="alert" className="negative">
            {error}
          </p>
        )}
      </Panel>
      {result ? (
        <>
          <div className="ax-stats">
            {[
              ["Net result", money(result.pnl)],
              ["Closed trades", result.trades],
              ["Total fees", money(result.fees)],
              ["Max equity drawdown", money(result.max_drawdown)],
            ].map(([label, value]) => (
              <div className="ax-stat" key={label}>
                <div className="ax-stat-label">{label}</div>
                <div className="ax-stat-value">{value}</div>
              </div>
            ))}
          </div>
          <Panel
            title="Replay equity curve"
            action={<Badge tone="green">COMPLETED · {result.bars} BARS</Badge>}
          >
            <LineChart
              values={result.curve.map((r) => r.equity / 100)}
              label="Replay equity"
              color="#a89aff"
            />
            <p className="ax-footnote">
              {result.disclaimer} All remaining positions are closed at the end
              of the experiment.
            </p>
          </Panel>
        </>
      ) : (
        <Panel title="Experiment results">
          <Empty
            title="Every result needs evidence."
            text="Run an experiment to see the actual synthetic equity curve, closed trades, fees and drawdown."
          />
        </Panel>
      )}
    </>
  );
}
export function Performance({ state }: { state: Workspace }) {
  const exits = state.events.filter((e) => e.kind === "SELL");
  const wins = exits.filter((e) => (e.payload.pnl || 0) > 0).length;
  return (
    <>
      <Stats state={state} />
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
        <Risk state={state} />
      </div>
      <Activity state={state} />
    </>
  );
}
export function Settings({
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
        <Risk state={state} />
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
