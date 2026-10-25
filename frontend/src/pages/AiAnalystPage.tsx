import {
  Cockpit,
  CockpitDetail,
  CockpitGrid,
  MarketBar,
  READINESS_CLASS,
  READINESS_LABEL,
} from "../components/Cockpit";
import { fmtNum } from "../format";
import { usePrediction } from "../hooks/usePrediction";
import type {
  KeyLevel,
  PredictionPayload,
  PremiumPricing,
  RegimeSummary,
  SetupGrade,
  SetupSignal,
} from "../types";

// A trading screen, not a report. The order of everything below follows the
// order a decision actually gets made with the market open: what is price
// doing, what is the call, do I act now, at what levels, and only then why.
//
// Every explanatory sentence comes from the backend, which builds it next to
// the number it explains (see signals/regime.py and signals/setups.py). This
// file formats; it never invents an interpretation of a score it did not
// compute.

const PRICING_LABEL: Record<PremiumPricing, string> = {
  RICH: "Options are expensive against how much NIFTY is actually moving",
  CHEAP: "Options are cheap against how much NIFTY is actually moving",
  FAIR: "Options are priced about right for how much NIFTY is moving",
  UNKNOWN: "Not enough data to compare priced movement against real movement",
};

const GRADE_CLASS: Record<SetupGrade, string> = {
  A: "bias-bullish",
  B: "bias-bullish",
  C: "bias-neutral",
  D: "bias-bearish",
};

const ACTION_LABEL: Record<string, string> = {
  BUY_CE: "BUY CALL",
  BUY_PE: "BUY PUT",
  SELL_CE: "SELL CALL",
  SELL_PE: "SELL PUT",
  SELL_STRADDLE: "SELL CALL + PUT",
};

const LADDER_CLASS: Record<KeyLevel["kind"], string> = {
  SPOT: "is-spot",
  RESISTANCE: "is-resistance",
  SUPPORT: "is-support",
  TRIGGER: "is-trigger",
  STOP: "is-stop",
  TARGET: "is-target",
  REFERENCE: "is-reference",
};

function signedPoints(value: number): string {
  return `${value > 0 ? "+" : ""}${fmtNum(value, 0)}`;
}

/* --- the live trade ----------------------------------------------------- */

function TradeCard({ best }: { best: SetupSignal | null }) {
  if (!best) {
    return (
      <div className="trade-card is-standdown">
        <div className="trade-headline">
          <span className="trade-action bias-neutral">STAND DOWN</span>
        </div>
        <p className="trade-setup-name">
          No setup is worth taking right now. Every one either failed a hard condition or scored too
          low. Doing nothing is a real answer, and it is the common one — the ruled-out list below
          shows exactly what was considered and why it was rejected.
        </p>
      </div>
    );
  }

  // On a breakout the trigger level and the invalidation level are the same
  // price -- you enter on a close through it and you leave on a close back
  // through it. That is correct, but printing the identical number in two
  // large tiles reads as a bug, so the second tile explains the overlap
  // instead of silently repeating it.
  const stopIsTrigger =
    best.stop_reference !== null &&
    best.entry_reference !== null &&
    Math.abs(best.stop_reference - best.entry_reference) < 0.5;

  return (
    <div className="trade-card">
      <div className="trade-headline">
        <span className="trade-action">
          {ACTION_LABEL[best.action] ?? best.action}
          {best.strike !== null ? ` ${fmtNum(best.strike, 0)}` : ""}
        </span>
        <span className={`trade-grade ${GRADE_CLASS[best.grade]}`}>
          Grade {best.grade} · {fmtNum(best.score, 0)}/100
        </span>
      </div>
      <p className="trade-setup-name">{best.name}</p>

      <div className={`trade-readiness ${READINESS_CLASS[best.readiness]}`}>
        <span className="trade-readiness-tag">{READINESS_LABEL[best.readiness]}</span>
        <span className="trade-readiness-note">{best.readiness_note}</span>
      </div>

      <div className="trade-levels">
        <div className="trade-level">
          <span className="trade-level-label">Trigger</span>
          <span className="trade-level-value">{fmtNum(best.entry_reference, 0)}</span>
          <span className="trade-level-sub">
            {best.distance_points === null
              ? "no single level — see the trigger rule"
              : `${fmtNum(best.distance_points, 0)} points from here`}
          </span>
        </div>
        <div className="trade-level">
          <span className="trade-level-label">Get out</span>
          <span className="trade-level-value">{fmtNum(best.stop_reference, 0)}</span>
          <span className="trade-level-sub">
            {stopIsTrigger
              ? "same level — you enter on a close through it and leave on a close back through it"
              : "a close back through this kills the trade"}
          </span>
        </div>
        <div className="trade-level">
          <span className="trade-level-label">Target</span>
          <span className="trade-level-value">{fmtNum(best.target_reference, 0)}</span>
          <span className="trade-level-sub">
            {best.expected_premium_points === null
              ? "no fixed target — manage against the level"
              : `about ${fmtNum(best.expected_premium_points, 0)} points of premium`}
          </span>
        </div>
      </div>

      <div className="trade-why">
        <div>
          <span className="trade-why-label">Enter only when</span>
          {best.trigger}
        </div>
        <div>
          <span className="trade-why-label">You are assuming</span>
          {best.assumption}
        </div>
        <div>
          <span className="trade-why-label">Track record</span>
          {best.historical
            ? best.historical.note
            : "Never graded on a finished session, so its grade is capped no matter how good today looks."}
        </div>
      </div>

      {best.warnings.map((warning) => (
        <div className="banner banner-warning" key={warning}>
          {warning}
        </div>
      ))}
    </div>
  );
}

/* --- the market around it ----------------------------------------------- */

function Ladder({ levels }: { levels: KeyLevel[] }) {
  return (
    <section className="panel">
      <h2>Levels that matter</h2>
      <div>
        {levels.map((level) => (
          <div
            className={`ladder-row ${LADDER_CLASS[level.kind]}`}
            key={`${level.kind}-${level.price}-${level.label}`}
            title={level.detail}
          >
            <span className="ladder-mark" />
            <span className="ladder-label">{level.label}</span>
            <span className="ladder-price">{fmtNum(level.price, 0)}</span>
            <span className="ladder-distance">
              {level.kind === "SPOT" ? "" : signedPoints(level.distance_points)}
            </span>
          </div>
        ))}
      </div>
    </section>
  );
}

function MovementPanel({ regime }: { regime: RegimeSummary }) {
  return (
    <section className="panel">
      <h2>What options are charging</h2>
      <div className="metrics-row">
        <div className="metric">
          <span className="metric-label">Priced move</span>
          <span className="metric-value">
            {regime.implied_daily_move_points === null
              ? "-"
              : fmtNum(regime.implied_daily_move_points, 0)}
          </span>
          <span className="metric-sub">points a session</span>
        </div>
        <div className="metric">
          <span className="metric-label">Real move</span>
          <span className="metric-value">
            {regime.realized_daily_move_points === null
              ? "-"
              : fmtNum(regime.realized_daily_move_points, 0)}
          </span>
          <span className="metric-sub">across {regime.realized_sample_days} sessions</span>
        </div>
      </div>
      <p className="disclaimer">{PRICING_LABEL[regime.premium_pricing]}.</p>
    </section>
  );
}

function FactorPanel({ regime }: { regime: RegimeSummary }) {
  return (
    <section className="panel">
      <h2>Why that call ({signedPoints(regime.stance_score)})</h2>
      <div>
        {regime.reasons.map((reason) => (
          <div className="factor-row" key={reason.factor} title={reason.explanation}>
            <span
              className={`factor-points ${
                reason.points > 0 ? "bias-bullish" : reason.points < 0 ? "bias-bearish" : ""
              }`}
            >
              {signedPoints(reason.points)}
            </span>
            <span>
              {reason.factor}
              <br />
              <span className="factor-reading">{reason.reading}</span>
            </span>
          </div>
        ))}
      </div>
      <p className="disclaimer">
        Plus points argue for buying, minus for selling. Hover any row for the reasoning.
      </p>
    </section>
  );
}

/* --- reference material, folded away by default ------------------------- */

function SetupCard({ signal }: { signal: SetupSignal }) {
  const armed = signal.status === "ARMED";
  return (
    <article className={`setup-card${armed ? " is-armed" : ""}`}>
      <div className="setup-card-head">
        <span className="setup-card-title">{signal.name}</span>
        <span
          className={`setup-card-grade ${armed ? READINESS_CLASS[signal.readiness] : "bias-neutral"}`}
        >
          {armed
            ? `${READINESS_LABEL[signal.readiness]} · ${fmtNum(signal.score, 0)}/100`
            : "Not available"}
        </span>
      </div>

      <div className="setup-field">
        <span className="setup-field-label">What it would be</span>
        {ACTION_LABEL[signal.action] ?? signal.action}
        {signal.strike === null ? "" : ` at ${fmtNum(signal.strike, 0)}`}
      </div>

      {armed ? (
        <>
          <div className="setup-field">
            <span className="setup-field-label">Right now</span>
            {signal.readiness_note}
          </div>
          <div className="setup-field">
            <span className="setup-field-label">You are assuming</span>
            {signal.assumption}
          </div>
          <div className="setup-field">
            <span className="setup-field-label">Get out when</span>
            {signal.invalidation}
          </div>
        </>
      ) : (
        <div className="setup-field">
          <span className="setup-field-label">Why it is off</span>
          <ul>
            {signal.blocked_reasons.map((reason) => (
              <li key={reason}>{reason}</li>
            ))}
          </ul>
        </div>
      )}

      <div className="setup-field">
        <span className="setup-field-label">Track record</span>
        {signal.historical
          ? signal.historical.note
          : "No graded outcomes yet — never tested on a finished session."}
      </div>
    </article>
  );
}

function Contents({ data }: { data: PredictionPayload }) {
  if (data.unavailable || !data.regime) {
    return <div className="banner banner-info">{data.unavailable ?? "No reading available yet."}</div>;
  }

  const others = data.signals.filter((s) => s.key !== data.best?.key);
  const armedOthers = others.filter((s) => s.status === "ARMED");
  const blocked = others.filter((s) => s.status === "BLOCKED");

  return (
    <>
      {data.risk?.avoid_new_entries && (
        <div className="banner banner-warning">
          {data.risk.reasons.join(" ") || "This is a higher-risk window for opening a new position."}
        </div>
      )}

      <CockpitGrid
        main={
          <>
            <TradeCard best={data.best} />
            {armedOthers.length > 0 && (
              <section className="panel" style={{ marginTop: 16 }}>
                <h2>Also available</h2>
                <div className="setup-grid">
                  {armedOthers.map((s) => (
                    <SetupCard key={s.key} signal={s} />
                  ))}
                </div>
              </section>
            )}
          </>
        }
        aside={
          <>
            <Ladder levels={data.key_levels} />
            <MovementPanel regime={data.regime} />
            <FactorPanel regime={data.regime} />
          </>
        }
      />

      {data.regime.warnings.length > 0 && (
        <div style={{ marginTop: 16 }}>
          {data.regime.warnings.map((warning) => (
            <div className="banner banner-warning" key={warning}>
              {warning}
            </div>
          ))}
        </div>
      )}

      <CockpitDetail summary={`Setups the engine ruled out (${blocked.length})`}>
        <p className="disclaimer">
          Shown rather than hidden. Knowing why a trade is off is worth as much as knowing which is
          on, and it means the engine can be checked rather than trusted.
        </p>
        <div className="setup-grid">
          {blocked.map((s) => (
            <SetupCard key={s.key} signal={s} />
          ))}
        </div>
      </CockpitDetail>

      {data.gex && (
        <CockpitDetail summary="Where the big hedging flow sits">
          <p className="disclaimer">{data.gex.note}</p>
          <div className="metrics-row">
            <div className="metric">
              <span className="metric-label">Acting as a ceiling</span>
              <span className="metric-value">{fmtNum(data.gex.call_wall_strike, 0)}</span>
            </div>
            <div className="metric">
              <span className="metric-label">Acting as a floor</span>
              <span className="metric-value">{fmtNum(data.gex.put_wall_strike, 0)}</span>
            </div>
            <div className="metric">
              <span className="metric-label">Hedging flips sides</span>
              <span className="metric-value">{fmtNum(data.gex.gamma_flip_strike, 0)}</span>
              <span className="metric-sub">above it moves get damped, below it amplified</span>
            </div>
          </div>
        </CockpitDetail>
      )}
    </>
  );
}

export default function AiAnalystPage() {
  const { data, fetchError } = usePrediction();

  return (
    <Cockpit>
      <MarketBar title="AI Analyst" data={data} />
      {fetchError && <div className="banner banner-error">Connection error: {fetchError}</div>}
      {!data && !fetchError && <div className="banner banner-info">Working out today's read...</div>}
      {data && <Contents data={data} />}
      <p className="disclaimer" style={{ marginTop: 20 }}>
        Analytical output only — this never places an order.
      </p>
    </Cockpit>
  );
}
