import { useState } from "react";
import type { ReplayResult } from "../types";
import { money } from "../lib/format";
import { api } from "../api/client";
import { Icon, Badge, Panel, EmptyState, LineChart } from "../../../shared/ui";

export function ReplayLabPage() {
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
              color="var(--ax-purple)"
            />
            <p className="ax-footnote">
              {result.disclaimer} All remaining positions are closed at the end
              of the experiment.
            </p>
          </Panel>
        </>
      ) : (
        <Panel title="Experiment results">
          <EmptyState
            title="Every result needs evidence."
            text="Run an experiment to see the actual synthetic equity curve, closed trades, fees and drawdown."
          />
        </Panel>
      )}
    </>
  );
}
