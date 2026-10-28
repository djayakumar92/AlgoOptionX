import { Cockpit, MarketBar } from "../components/Cockpit";
import { DemoBanner } from "../components/DemoBanner";
import { OptionDepthTable } from "../components/OptionDepthTable";
import { fmtInt, fmtNum } from "../format";
import { useLiveState } from "../hooks/useLiveState";
import { useSupportResistance } from "../hooks/useSupportResistance";
import type { OiWall } from "../types";

const CALL_PRESSURE = [
  { strike: 25500, score: 91 },
  { strike: 25550, score: 76 },
  { strike: 25600, score: 52 },
];

const PUT_PRESSURE = [
  { strike: 25400, score: 84 },
  { strike: 25350, score: 71 },
  { strike: 25300, score: 43 },
];

function PressureBar({ strike, score, side }: { strike: number; score: number; side: "bullish" | "bearish" }) {
  return (
    <div className="score-bar-row">
      <span className="score-bar-label">{fmtNum(strike, 0)}</span>
      <div className="score-bar-track">
        <div className={`score-bar-fill ${side}`} style={{ width: `${score}%` }} />
      </div>
      <span className="score-bar-value">{score}</span>
    </div>
  );
}

function WallRow({ wall }: { wall: OiWall }) {
  const changeLabel = wall.oi_change_pct !== null ? `${wall.oi_change_pct >= 0 ? "+" : ""}${(wall.oi_change_pct * 100).toFixed(1)}% vs yesterday` : "no prior-day OI on record";
  return (
    <div className="structure-event">
      <span className="structure-event-tag">{wall.freshness}</span>
      <span>
        {fmtNum(wall.strike, 0)} {wall.option_type} — OI {fmtInt(wall.oi)} ({changeLabel}), Volume {fmtInt(wall.volume)}
        {wall.unwinding_warning && " — aggressive unwinding, this wall may be about to break"}
      </span>
    </div>
  );
}

export default function OptionIntelligencePage() {
  const { data } = useLiveState();
  const { data: srData } = useSupportResistance();
  const hasChain = Boolean(data?.chain && data.chain.length > 0);
  const hasWalls = Boolean(srData && (srData.call_walls.length > 0 || srData.put_walls.length > 0));

  return (
    <Cockpit>
      <MarketBar title="Option Intelligence" />
      <p className="cockpit-lede">
        The per-strike detail Live Market doesn't show — IV, delta, volume, and bid/ask spread for each contract — plus a preview of the seller-pressure and OI-wall analysis the requirement doc describes. For overall bias, PCR, and max pain, see Live Market instead.
      </p>

      <main className="cockpit-stack">
        {hasChain ? (
          <OptionDepthTable rows={data!.chain!} />
        ) : (
          <p className="not-an-order">Waiting for the first live poll cycle.</p>
        )}

        <section className="panel">
          <h2>Option Seller Pressure</h2>
          <DemoBanner text="Seller-pressure scoring isn't computed yet — these bars are a static example, not from today's real OI." />
          <p className="oi-strikes">Call Seller Pressure</p>
          {CALL_PRESSURE.map((r) => (
            <PressureBar key={r.strike} strike={r.strike} score={r.score} side="bearish" />
          ))}
          <p className="oi-strikes" style={{ marginTop: 12 }}>
            Put Seller Pressure
          </p>
          {PUT_PRESSURE.map((r) => (
            <PressureBar key={r.strike} strike={r.strike} score={r.score} side="bullish" />
          ))}
        </section>

        <section className="panel">
          <h2>OI Wall Detection</h2>
          <p className="oi-strikes">
            Top Call/Put OI strikes near spot, weighted by today's OI change and volume — a wall with
            volume/OI activity and rising OI is "fresh" conviction; falling OI with heavy volume warns the
            wall may be about to break. Full zone scoring that combines these with price structure lives on
            the Market Structure page.
          </p>
          {hasWalls ? (
            <div className="structure-list">
              {srData!.call_walls.map((w) => (
                <WallRow wall={w} key={`ce-${w.strike}`} />
              ))}
              {srData!.put_walls.map((w) => (
                <WallRow wall={w} key={`pe-${w.strike}`} />
              ))}
            </div>
          ) : (
            <p className="not-an-order">Waiting for the first live poll cycle.</p>
          )}
        </section>
      </main>
    </Cockpit>
  );
}
