import { Cockpit, MarketBar } from "../components/Cockpit";
import { fmtHM, fmtNum } from "../format";
import { useMarketStructure } from "../hooks/useMarketStructure";
import { useSupportResistance } from "../hooks/useSupportResistance";
import type { DayType, StructureEvent, SwingPoint, Zone, ZoneClassification } from "../types";

const ZONE_CLASS_CSS: Record<ZoneClassification, string> = {
  INSTITUTIONAL: "zone-class-institutional",
  STRONG: "zone-class-strong",
  MODERATE: "zone-class-moderate",
  WEAK: "zone-class-weak",
  IGNORE: "zone-class-weak",
};

const ZONE_CLASS_LABEL: Record<ZoneClassification, string> = {
  INSTITUTIONAL: "Institutional Zone",
  STRONG: "Strong Zone",
  MODERATE: "Moderate Zone",
  WEAK: "Weak Zone",
  IGNORE: "Ignore",
};

function zoneRangeLabel(zone: Zone): string {
  return zone.low === zone.high ? fmtNum(zone.low) : `${fmtNum(zone.low)} – ${fmtNum(zone.high)}`;
}

const DAY_TYPE_LABEL: Record<DayType, string> = {
  NON_TREND: "Non-Trend Day (Range)",
  NORMAL_VARIATION: "Normal Variation Day",
  TREND: "Trend Day",
  NEUTRAL: "Neutral Day (Choppy)",
  FORMING: "Initial Balance Forming",
  INSUFFICIENT_DATA: "Not Enough Data Yet",
};

const DAY_TYPE_CLASS: Record<DayType, string> = {
  NON_TREND: "bias-neutral",
  NORMAL_VARIATION: "bias-neutral",
  TREND: "bias-bullish",
  NEUTRAL: "bias-neutral",
  FORMING: "bias-neutral",
  INSUFFICIENT_DATA: "bias-neutral",
};

const TIMEFRAME_LABEL: Record<string, string> = {
  BULLISH: "Bullish",
  BEARISH: "Bearish",
  UNCLEAR: "No clear trend",
  INSUFFICIENT_DATA: "Not enough data",
};

const TIMEFRAME_CLASS: Record<string, string> = {
  BULLISH: "bias-bullish",
  BEARISH: "bias-bearish",
  UNCLEAR: "bias-neutral",
  INSUFFICIENT_DATA: "bias-neutral",
};

const SWING_LABEL: Record<string, string> = {
  HH: "Higher High",
  HL: "Higher Low",
  LH: "Lower High",
  LL: "Lower Low",
  H: "First Swing High",
  L: "First Swing Low",
};

function swingDescription(swing: SwingPoint): string {
  return `${swing.label} — ${SWING_LABEL[swing.label] ?? swing.label} at ${fmtNum(swing.price)} (${fmtHM(swing.ts)})`;
}

function eventDescription(event: StructureEvent): string {
  const verb = event.kind === "BOS" ? "continuation" : "the first counter-trend break";
  const side = event.direction === "BULLISH" ? "above" : "below";
  return `${event.kind} — ${event.direction.toLowerCase()} ${verb}: price broke ${side} the prior swing at ${fmtNum(event.level)}, confirmed at ${fmtNum(event.price)} (${fmtHM(event.ts)}).`;
}

export default function MarketStructurePage() {
  const { data, startingUp, fetchError } = useMarketStructure();
  const { data: srData } = useSupportResistance();
  const zones = (srData?.zones ?? []).filter((z) => z.classification !== "IGNORE");

  return (
    <Cockpit>
      <MarketBar title="Market Structure" />
      <p className="cockpit-lede">
        Real price structure from today's 5-minute candles: swing highs/lows, break of structure, change of character, and an Initial-Balance day-type read (Steidlmayer/Market Profile) — the check the HLC trade plan doesn't currently make for whether today is actually behaving like a range day.
      </p>

      <main className="cockpit-stack">
        {startingUp && <div className="banner banner-info">Loading market structure...</div>}
        {fetchError && <div className="banner banner-error">Connection error: {fetchError}</div>}

        {data && (
          <>
            <section className="panel">
              <h2>Day Type</h2>
              <div className="metrics-row">
                <div className="metric">
                  <span className="metric-label">Regime</span>
                  <span className={`metric-value ${DAY_TYPE_CLASS[data.day_type.day_type]}`}>
                    {DAY_TYPE_LABEL[data.day_type.day_type]}
                  </span>
                </div>
                <div className="metric">
                  <span className="metric-label">Structure Trend</span>
                  <span
                    className={`metric-value ${
                      data.structure_trend === "BULLISH"
                        ? "bias-bullish"
                        : data.structure_trend === "BEARISH"
                          ? "bias-bearish"
                          : "bias-neutral"
                    }`}
                  >
                    {data.structure_trend}
                  </span>
                </div>
                <div className="metric">
                  <span className="metric-label">Initial Balance</span>
                  <span className="metric-value">
                    {data.day_type.ib_low !== null ? `${fmtNum(data.day_type.ib_low)} – ${fmtNum(data.day_type.ib_high)}` : "-"}
                  </span>
                  <span className="metric-sub">first 30 min</span>
                </div>
                <div className="metric">
                  <span className="metric-label">Session Range</span>
                  <span className="metric-value">
                    {data.day_type.session_low !== null
                      ? `${fmtNum(data.day_type.session_low)} – ${fmtNum(data.day_type.session_high)}`
                      : "-"}
                  </span>
                </div>
                <div className="metric">
                  <span className="metric-label">Choppiness (14)</span>
                  <span className="metric-value">{data.chop !== null ? data.chop : "-"}</span>
                  <span className="metric-sub">low = trending, high = choppy</span>
                </div>
              </div>
              <p className="oi-strikes">
                The HLC trade plan is a range-day strategy by construction — a Trend Day regime is exactly
                the condition where a level-anchored selling rule is most likely to get run over.
              </p>
            </section>

            <section className="panel">
              <h2>Structure Events</h2>
              {data.last_bos || data.last_choch ? (
                <div className="structure-list">
                  {data.last_choch && (
                    <div className="structure-event">
                      <span className="structure-event-tag">CHoCH</span>
                      <span>{eventDescription(data.last_choch)}</span>
                    </div>
                  )}
                  {data.last_bos && (
                    <div className="structure-event">
                      <span className="structure-event-tag">BOS</span>
                      <span>{eventDescription(data.last_bos)}</span>
                    </div>
                  )}
                </div>
              ) : (
                <p className="not-an-order">No confirmed break of structure or change of character yet in the available history.</p>
              )}
            </section>

            <section className="panel">
              <h2>Recent Swing Points</h2>
              {data.swings.length > 0 ? (
                <div className="structure-list">
                  {data.swings.map((s, i) => (
                    <div className="structure-event" key={`${s.ts}-${i}`}>
                      <span className="structure-event-tag">{s.label}</span>
                      <span>{swingDescription(s)}</span>
                    </div>
                  ))}
                </div>
              ) : (
                <p className="not-an-order">Not enough candle history yet to confirm a swing high/low.</p>
              )}
            </section>

            <section className="panel">
              <h2>Reference Levels</h2>
              <div className="metrics-row">
                <div className="metric">
                  <span className="metric-label">Previous Day</span>
                  <span className="metric-value">
                    {data.prev_day_low !== null ? `${fmtNum(data.prev_day_low)} – ${fmtNum(data.prev_day_high)}` : "-"}
                  </span>
                </div>
                <div className="metric">
                  <span className="metric-label">Previous Week</span>
                  <span className="metric-value">
                    {data.prev_week_low !== null ? `${fmtNum(data.prev_week_low)} – ${fmtNum(data.prev_week_high)}` : "-"}
                  </span>
                </div>
              </div>
            </section>

          <section className="panel">
            <h2>Multi-Timeframe Structure</h2>
            <p className="oi-strikes">
              The same swing-structure read as above, run on 5-minute bars folded up into 15-minute,
              hourly and daily candles. When the timeframes agree, a move has the higher ones behind
              it; when they disagree, the lower one is usually a pullback inside the higher one.
            </p>
            <div className="metrics-row">
              {(data.timeframes ?? []).map((tf) => (
                <div className="metric" key={tf.label} title={tf.note}>
                  <span className="metric-label">{tf.label}</span>
                  <span className={`metric-value ${TIMEFRAME_CLASS[tf.trend]}`}>
                    {TIMEFRAME_LABEL[tf.trend]}
                  </span>
                  <span className="metric-sub">
                    {tf.enough_data ? `${tf.swings} swings · ${tf.bars} bars` : `${tf.bars} bars stored`}
                  </span>
                </div>
              ))}
            </div>
            {(data.timeframes ?? []).some((tf) => !tf.enough_data) && (
              <p className="not-an-order">
                {(data.timeframes ?? []).filter((tf) => !tf.enough_data).map((tf) => tf.note).join(" ")}
              </p>
            )}
          </section>
          </>
        )}


        <section className="panel">
          <h2>Scored Support / Resistance Zones</h2>
          <p className="oi-strikes">
            Combines real swing points, previous day/week levels, the HLC engine's own bands, VWAP,
            classic pivots, and fresh/stale OI walls into one 0–100 strength score per zone. Not included:
            volume profile, anchored VWAP, and Fibonacci — see the migration requirements doc for why.
          </p>
          {zones.length > 0 ? (
            zones.map((zone, i) => (
              <div className="zone-card" key={`${zone.kind}-${zone.low}-${i}`}>
                <span className="zone-range">
                  {zone.kind === "SUPPORT" ? "Support" : "Resistance"} {zoneRangeLabel(zone)}
                </span>
                <span className={`zone-class ${ZONE_CLASS_CSS[zone.classification]}`}>
                  {ZONE_CLASS_LABEL[zone.classification]} · {zone.score}/100
                </span>
                <span className="zone-factors">{zone.factors.map((f) => f.label).join(", ")}</span>
              </div>
            ))
          ) : (
            <p className="not-an-order">No zone scored above "Weak" yet with the currently available data.</p>
          )}
        </section>
      </main>
    </Cockpit>
  );
}
