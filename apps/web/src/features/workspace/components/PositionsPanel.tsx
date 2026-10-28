import type { Workspace } from "../types";
import { money, contractName } from "../lib/format";
import { Badge } from "../../../shared/ui/Badge";
import { Panel } from "../../../shared/ui/Panel";
import { EmptyState } from "../../../shared/ui/EmptyState";

export function PositionsPanel({
  state,
  act,
  busy,
}: {
  state: Workspace;
  act: (action: string, fields?: object) => void;
  busy: boolean;
}) {
  return (
    <Panel
      title="Open positions"
      action={<Badge>{state.positions.length} active</Badge>}
    >
      {state.positions.length ? (
        <div className="ax-table-wrap">
          <table>
            <thead>
              <tr>
                <th>Contract</th>
                <th>Qty</th>
                <th>Entry</th>
                <th>Mark</th>
                <th>Exit P&L estimate</th>
                <th>Action</th>
              </tr>
            </thead>
            <tbody>
              {state.positions.map((p) => (
                <tr key={p.id}>
                  <td>
                    <strong>{contractName(p.instrument)}</strong>
                    <small>
                      Stop {money(p.stop)} · Target {money(p.target)}
                    </small>
                  </td>
                  <td>{p.quantity}</td>
                  <td>{money(p.entry)}</td>
                  <td>{money(p.mark)}</td>
                  <td className={p.unrealized >= 0 ? "positive" : "negative"}>
                    {money(p.unrealized)}
                  </td>
                  <td>
                    <button
                      className="ax-button subtle"
                      disabled={busy}
                      onClick={() => act("close", { position_id: p.id })}
                    >
                      Close position
                    </button>
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      ) : (
        <EmptyState
          title="A clean slate. A clear plan."
          text="Choose a contract in the market terminal, or enable the decision engine for autonomous virtual entries."
        />
      )}
    </Panel>
  );
}
