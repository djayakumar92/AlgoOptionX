import { useState } from "react";
import { useEffect } from "react";
import type { Workspace, Contract } from "../types";
import { money, number, contractName } from "../lib/format";
import { Icon, Badge, Panel, LineChart } from "../../../shared/ui";
import { RiskPanel } from "../components";

export function MarketTerminalPage({
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
        <RiskPanel state={state} />
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
