import type { ReactNode } from "react";
import "../cockpit.css";
import { fmtNum } from "../format";
import { usePrediction } from "../hooks/usePrediction";
import type { PredictionPayload, PremiumStance, Readiness } from "../types";

// The shared cockpit shell. Every screen used with the market open is built
// from these four pieces, so the same information sits in the same place on
// every page and moving between them costs no re-orientation.
//
// Extracted from AiAnalystPage rather than invented: that page proved the
// layout, and copying its markup onto eight more pages is how the CSS in this
// project grew to 1,300 lines of near-duplicates in the first place.

const STANCE_LABEL: Record<PremiumStance, string> = {
  BUY_FAVORED: "BUY OPTIONS",
  SELL_FAVORED: "SELL OPTIONS",
  NEUTRAL: "NO EDGE EITHER WAY",
};

const STANCE_CLASS: Record<PremiumStance, string> = {
  BUY_FAVORED: "bias-bullish",
  SELL_FAVORED: "bias-bearish",
  NEUTRAL: "bias-neutral",
};

export const READINESS_LABEL: Record<Readiness, string> = {
  NOW: "ACT NOW",
  WAIT: "WAIT",
  MISSED: "TOO LATE",
  NA: "SEE TRIGGER",
};

export const READINESS_CLASS: Record<Readiness, string> = {
  NOW: "bias-bullish",
  WAIT: "bias-neutral",
  MISSED: "bias-bearish",
  NA: "bias-neutral",
};

/** Page wrapper. Opts the page out of the app-wide 1200px reading column --
 *  see the `:has()` rule in cockpit.css for how. */
export function Cockpit({ children }: { children: ReactNode }) {
  return <div className="cockpit">{children}</div>;
}

interface MarketBarProps {
  title: string;
  /** Marks the bar on a page whose content is still a static example.
   *  The live figures stay -- those are real and correctly labelled -- but
   *  the frame is tinted and tagged, because a production-looking trading
   *  chrome around placeholder content is exactly the confusion the DEMO
   *  tags exist to prevent. */
  demo?: boolean;
  /** Pass the page's own prediction data when it already has it, so the bar
   *  does not open a second poll for the same payload. Omit it and the bar
   *  fetches its own -- which is what every page that does not otherwise
   *  need the prediction does. */
  data?: PredictionPayload | null;
  /** Page-specific status to sit on the right of the shared figures. */
  children?: ReactNode;
}

/**
 * The strip that never scrolls away.
 *
 * The point of putting it on every page is continuity: you can go and read
 * the option chain or last month's journal without losing sight of what the
 * market is doing and whether the day's setup has come live. Before this,
 * navigating away from the analyst page meant navigating away from the
 * decision.
 */
export function MarketBar({ title, demo = false, data: provided, children }: MarketBarProps) {
  const own = usePrediction();
  // Deliberately not `provided ?? own.data`: a page that passes data is
  // saying "I own this poll", and falling back to a second one would quietly
  // reintroduce the duplicate fetch this prop exists to avoid.
  const data = provided !== undefined ? provided : own.data;
  const regime = data?.regime ?? null;

  return (
    <div className={`cockpit-bar${demo ? " is-demo" : ""}`}>
      <span className="cockpit-bar-title">{title}</span>
      {demo && <span className="cockpit-bar-demo">DEMO PAGE</span>}

      <div className="cockpit-spot">
        <span className="cockpit-spot-label">NIFTY</span>
        <span className="cockpit-spot-value">
          {data?.spot_price != null ? fmtNum(data.spot_price, 2) : "—"}
        </span>
      </div>

      {regime && (
        <span className={`cockpit-call ${STANCE_CLASS[regime.premium_stance]}`}>
          {STANCE_LABEL[regime.premium_stance]}
        </span>
      )}

      {data?.best && (
        <span className={`cockpit-call ${READINESS_CLASS[data.best.readiness]}`}>
          {READINESS_LABEL[data.best.readiness]}
          {data.best.readiness === "WAIT" && data.best.distance_points !== null
            ? ` · ${fmtNum(data.best.distance_points, 0)} pts away`
            : ""}
        </span>
      )}

      <div className="cockpit-bar-right">
        {children}
        {regime?.is_expiry_day && <span className="bias-bearish">EXPIRY DAY</span>}
        {regime && <span>{regime.session_window.toLowerCase()} session</span>}
        {regime && <span>{new Date(regime.as_of).toLocaleTimeString()}</span>}
      </div>
    </div>
  );
}

/** Two columns: what you act on, and the context around it. Collapses to one
 *  below 1150px. Pages with nothing to put beside the main content simply
 *  don't use this. */
export function CockpitGrid({ main, aside }: { main: ReactNode; aside: ReactNode }) {
  return (
    <div className="cockpit-grid">
      <div>{main}</div>
      <aside className="cockpit-aside">{aside}</aside>
    </div>
  );
}

/** Reference material, folded away by default. With the market open this is
 *  what keeps the decision above the fold. */
export function CockpitDetail({
  summary,
  children,
  open = false,
}: {
  summary: string;
  children: ReactNode;
  open?: boolean;
}) {
  return (
    <details className="cockpit-detail" open={open}>
      <summary>{summary}</summary>
      <div className="cockpit-detail-body">{children}</div>
    </details>
  );
}
