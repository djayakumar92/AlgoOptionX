import { Cockpit, MarketBar } from "../components/Cockpit";
import { fmtNum } from "../format";
import { useLearning } from "../hooks/useLearning";
import type { LearningPayload, SetupRecord, SliceStats } from "../types";

// Nothing on this page is generated or estimated. Every figure comes from
// setup_outcomes -- setups the engine actually armed on a real session, graded
// afterwards against that session's own candles. Where there is no record, the
// page says there is no record instead of showing a placeholder.

const SETUP_LABEL: Record<string, string> = {
  IB_BREAKOUT_LONG: "Opening-range breakout (up)",
  IB_BREAKOUT_SHORT: "Opening-range breakout (down)",
  IB_FAILURE_FADE_LONG: "Failed break of the opening range (downside rejection)",
  IB_FAILURE_FADE_SHORT: "Failed break of the opening range (upside rejection)",
  WALL_FADE_CALL: "Fade the call wall",
  WALL_FADE_PUT: "Fade the put wall",
  TREND_PULLBACK_LONG: "Trend pullback (long)",
  TREND_PULLBACK_SHORT: "Trend pullback (short)",
  RANGE_SHORT_STRADDLE: "Sell both sides into a contained session",
  EXPIRY_PIN_FADE: "Expiry hedging-flow fade",
};

function SliceTable({ title, slices }: { title: string; slices: SliceStats[] }) {
  if (slices.length === 0) return null;
  return (
    <div className="setup-field">
      <span className="setup-field-label">{title}</span>
      <table className="chain-table">
        <thead>
          <tr>
            <th>Condition</th>
            <th>Times</th>
            <th>Won</th>
            <th>Lost</th>
            <th>Hit rate</th>
            <th>Avg points</th>
          </tr>
        </thead>
        <tbody>
          {slices.map((slice) => (
            <tr key={slice.label}>
              <td>{slice.label}</td>
              <td>{slice.sample}</td>
              <td>{slice.wins}</td>
              <td>{slice.losses}</td>
              <td>{slice.hit_rate === null ? "-" : `${fmtNum(slice.hit_rate, 0)}%`}</td>
              <td>{fmtNum(slice.avg_points, 1)}</td>
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
}

function RecordCard({ record }: { record: SetupRecord }) {
  return (
    <article className="setup-card">
      <div className="setup-card-head">
        <span className="setup-card-title">{SETUP_LABEL[record.setup_key] ?? record.setup_key}</span>
        <span className={`setup-card-grade ${record.reliable ? "bias-bullish" : "bias-neutral"}`}>
          {record.reliable ? "Proven" : "Too early to judge"}
        </span>
      </div>

      <p className="recommendation-reason">{record.verdict}</p>

      <div className="metrics-row">
        <div className="metric">
          <span className="metric-label">Times it appeared</span>
          <span className="metric-value">{record.armed}</span>
          <span className="metric-sub">
            {record.not_triggered} never reached its entry condition
          </span>
        </div>
        <div className="metric">
          <span className="metric-label">Won / lost</span>
          <span className="metric-value">
            {record.wins} / {record.losses}
          </span>
          <span className="metric-sub">{record.flats} finished flat</span>
        </div>
        <div className="metric">
          <span className="metric-label">Average result</span>
          <span className="metric-value">{fmtNum(record.avg_points, 1)}</span>
          <span className="metric-sub">NIFTY points, not rupees — see the note below</span>
        </div>
        <div className="metric">
          <span className="metric-label">Worst it went against you</span>
          <span className="metric-value">{fmtNum(record.avg_mae, 1)}</span>
          <span className="metric-sub">average, before it resolved either way</span>
        </div>
      </div>

      <SliceTable title="By market regime at the time" slices={record.by_regime} />
      <SliceTable title="By type of day" slices={record.by_day_type} />
      <SliceTable title="By how options were priced" slices={record.by_pricing} />
    </article>
  );
}

function Contents({ data }: { data: LearningPayload }) {
  return (
    <>
      <section className="panel">
        <h2>Is the engine's read of the market worth anything?</h2>
        <p className="disclaimer">
          A check the engine runs on itself. Days it called trending should, on average, have travelled
          further than days it called contained. If they did not, the label is decoration and the
          setups built on it inherit the problem.
        </p>
        <div className="recommendation-box">
          <p className="recommendation-reason">{data.regime_check.verdict}</p>
        </div>
        {data.regime_check.by_regime.length > 0 && (
          <table className="chain-table">
            <thead>
              <tr>
                <th>The engine called it</th>
                <th>Sessions</th>
                <th>Average range travelled</th>
              </tr>
            </thead>
            <tbody>
              {data.regime_check.by_regime.map((slice) => (
                <tr key={slice.label}>
                  <td>{slice.label}</td>
                  <td>{slice.sample}</td>
                  <td>{fmtNum(slice.avg_points, 0)} pts</td>
                </tr>
              ))}
            </tbody>
          </table>
        )}
      </section>

      <section className="panel">
        <h2>What each setup has actually done</h2>
        <p className="disclaimer">
          Results are graded against NIFTY's own five-minute candles: did the level hold, did the break
          extend, did the day stay inside its expected range. That grades the setup's reasoning, which
          is what these numbers are for. It is not a profit-and-loss figure, and it is deliberately not
          presented as one — reconstructing what an option was actually worth on a past expiry is not
          something this data can do honestly.
        </p>
        {data.setups.length === 0 ? (
          <div className="banner banner-info">
            No graded outcomes yet. The record starts the first time a setup arms during a live session
            and that session finishes. Until then every setup's grade stays capped, which is the
            intended behaviour rather than a fault.
          </div>
        ) : (
          <div className="setup-grid">
            {data.setups.map((record) => (
              <RecordCard key={record.setup_key} record={record} />
            ))}
          </div>
        )}
      </section>
    </>
  );
}

export default function LearningLabPage() {
  const { data, fetchError } = useLearning();

  return (
    <Cockpit>
      <MarketBar title="Learning Lab" />
      <p className="cockpit-lede">
        The engine's own track record, built one session at a time. Every setup it arms is written
        down before the outcome is known and graded after the close, so its confidence has to be
        earned rather than claimed.
      </p>

      <div className="cockpit-stack">
        {fetchError && <div className="banner banner-error">Connection error: {fetchError}</div>}
        {!data && !fetchError && <div className="banner banner-info">Reading the record...</div>}
        {data && <Contents data={data} />}
      </div>
    </Cockpit>
  );
}
