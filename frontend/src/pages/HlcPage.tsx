import { Cockpit, MarketBar } from "../components/Cockpit";
import { useNavigate } from "react-router-dom";
import { RiskPanel } from "../components/RiskPanel";
import { fmtNum, fmtTime } from "../format";
import { useHlcState } from "../hooks/useHlcState";
import type { HlcLegAnalysis, HlcStatePayload, HlcStrikeQuote, RangeBand, TradePlan } from "../types";

const SIGNAL_CLASS: Record<string, string> = {
  "Strong Bullish (Panic Buying)": "bias-bullish",
  "Strong Bearish (Profit Booking)": "bias-bearish",
};

function CandidatesTable({ candidates, atmStrike }: { candidates: HlcStrikeQuote[]; atmStrike?: number }) {
  return (
    <section className="panel chain-panel">
      <h2>Candidate Strikes</h2>
      <table className="chain-table">
        <thead>
          <tr>
            <th>CE High</th>
            <th>CE Close</th>
            <th>CE Low</th>
            <th>Strike</th>
            <th>PE High</th>
            <th>PE Close</th>
            <th>PE Low</th>
            <th>|CE−PE|</th>
          </tr>
        </thead>
        <tbody>
          {candidates.map((row) => (
            <tr key={row.strike} className={row.strike === atmStrike ? "atm-row" : ""}>
              <td>{fmtNum(row.ce?.high)}</td>
              <td>{fmtNum(row.ce?.close)}</td>
              <td>{fmtNum(row.ce?.low)}</td>
              <td className="strike-cell">
                {fmtNum(row.strike, 0)}
                {row.strike === atmStrike && " (ATM)"}
              </td>
              <td>{fmtNum(row.pe?.high)}</td>
              <td>{fmtNum(row.pe?.close)}</td>
              <td>{fmtNum(row.pe?.low)}</td>
              <td>
                {row.ce && row.pe ? fmtNum(Math.abs(row.ce.close - row.pe.close)) : "-"}
              </td>
            </tr>
          ))}
        </tbody>
      </table>
    </section>
  );
}

function LevelsPanel({ data }: { data: HlcStatePayload }) {
  return (
    <section className="panel metrics-row">
      <div className="metric">
        <span className="metric-label">ATM Strike</span>
        <span className="metric-value">{fmtNum(data.atm_strike, 0)}</span>
      </div>
      <div className="metric">
        <span className="metric-label">Max Resistance</span>
        <span className="metric-value">{fmtNum(data.max_resistance)}</span>
      </div>
      <div className="metric">
        <span className="metric-label">Min Resistance</span>
        <span className="metric-value">{fmtNum(data.min_resistance)}</span>
      </div>
      <div className="metric">
        <span className="metric-label">Min Support</span>
        <span className="metric-value">{fmtNum(data.min_support)}</span>
      </div>
      <div className="metric">
        <span className="metric-label">Max Support</span>
        <span className="metric-value">{fmtNum(data.max_support)}</span>
      </div>
    </section>
  );
}

function LegColumn({ title, leg }: { title: string; leg: HlcLegAnalysis }) {
  return (
    <div className="hlc-leg-column">
      <h3>{title}</h3>
      <div className="hlc-leg-grid">
        <span className="field-label">High</span>
        <span>{fmtNum(leg.high)}</span>
        <span className="field-label">Close</span>
        <span>{fmtNum(leg.close)}</span>
        <span className="field-label">Low</span>
        <span>{fmtNum(leg.low)}</span>
        <span className="field-label">Close−High Diff</span>
        <span>{fmtNum(leg.close_high_diff)}</span>
        <span className="field-label">Close−Low Diff</span>
        <span>{fmtNum(leg.close_low_diff)}</span>
        <span className="field-label">Domination</span>
        <span className="hlc-domination">{leg.domination}</span>
        <span className="field-label">Market Type</span>
        <span>{leg.market_type}</span>
      </div>
    </div>
  );
}

function RangeBandPanel({ title, band }: { title: string; band: RangeBand | null | undefined }) {
  return (
    <section className="panel">
      <h2>{title}</h2>
      {band ? (
        <>
          <p className="oi-strikes">
            Close: <strong>{fmtNum(band.close)}</strong>
          </p>
          <table className="chain-table">
            <thead>
              <tr>
                <th>Strike</th>
                <th>Combined Premium</th>
                <th>Sell</th>
                <th>Buy</th>
              </tr>
            </thead>
            <tbody>
              <tr>
                <td className="strike-cell">{fmtNum(band.low_strike, 0)}</td>
                <td>{fmtNum(band.low_premium)}</td>
                <td>{fmtNum(band.sell_low)}</td>
                <td>{fmtNum(band.buy_low)}</td>
              </tr>
              <tr>
                <td className="strike-cell">{fmtNum(band.high_strike, 0)}</td>
                <td>{fmtNum(band.high_premium)}</td>
                <td>{fmtNum(band.sell_high)}</td>
                <td>{fmtNum(band.buy_high)}</td>
              </tr>
            </tbody>
          </table>
        </>
      ) : (
        <p className="not-an-order">Not available yet.</p>
      )}
    </section>
  );
}

function TradePlanPanel({ plan }: { plan: TradePlan }) {
  return (
    <section className="panel">
      <h2>Plan for {plan.trade_date}</h2>
      <p className="oi-strikes">
        Built from the {plan.session_date} close. {plan.note}
      </p>
      {plan.legs.length > 0 && (
        <table className="chain-table">
          <thead>
            <tr>
              <th>Leg</th>
              <th>Action</th>
              <th>Strike</th>
              <th>Entry (sell at)</th>
              <th>Target</th>
              <th>Points</th>
              <th>Stop</th>
            </tr>
          </thead>
          <tbody>
            {plan.legs.map((leg) => (
              <tr key={leg.option_type}>
                <td>{leg.option_type}</td>
                <td>{leg.action}</td>
                <td className="strike-cell">{fmtNum(leg.strike, 0)}</td>
                <td>{fmtNum(leg.entry_trigger)}</td>
                <td>{fmtNum(leg.target)}</td>
                <td>{fmtNum(leg.target_points)}</td>
                <td>{leg.stop_rule}</td>
              </tr>
            ))}
          </tbody>
        </table>
      )}
      <p className="not-an-order">
        Analytical output — not an order. Entry/target are fixed from the last completed session; the
        stop is a live rule (previous 5-minute candle), not a fixed number, so it isn't shown as one here.
      </p>
    </section>
  );
}

export default function HlcPage() {
  const { data, startingUp, fetchError, refresh, refreshRequestError } = useHlcState();
  const hasResult = Boolean(data?.ce && data?.pe && data?.candidates);
  const refreshing = Boolean(data?.refreshing);
  const navigate = useNavigate();

  return (
    <Cockpit>
      {/* The bar shows the live price; this page's own numbers come from the
          last *completed* session, so that distinction is spelled out in the
          bar rather than left for the reader to trip over. */}
      <MarketBar title="Trade Setups">
        {data?.session_date && <span>based on {data.session_date} close</span>}
        {data?.nifty_close !== undefined && (
          <span>
            that close <strong>{fmtNum(data.nifty_close)}</strong>
          </span>
        )}
        <button className="fetch-latest-button" onClick={refresh} disabled={refreshing}>
          {refreshing ? "Fetching..." : "Fetch Latest"}
        </button>
        <button
          className="start-trading-button"
          onClick={() => navigate("/chart")}
          disabled={!hasResult}
          title={hasResult ? "" : "Fetch the HLC range first"}
        >
          Start Trading
        </button>
      </MarketBar>

      <p className="cockpit-lede">
        Your ATM-by-premium-symmetry / support-resistance / buyer-seller-domination rule, automated
        from your spreadsheet. Uses the last <em>completed</em> trading session's High/Close/Low —
        same as filling the sheet in after the market closes, not a live-updating intraday range.
        Fetched once when the app starts; click Fetch Latest any time you want the newest completed
        session's numbers. Analytical output only — this never places an order.
      </p>

      <>
        {startingUp && (
          <div className="banner banner-info">
            Loading last session's data — this can take up to a minute, since it fetches option contracts
            one at a time to stay within DhanHQ's rate limit. No need to click anything.
          </div>
        )}
        {!startingUp && refreshing && (
          <div className="banner banner-info">
            Fetching the latest completed session's data — this can take up to a minute. Showing the
            previous result below until it's done.
          </div>
        )}
        {refreshRequestError && <div className="banner banner-warning">{refreshRequestError}</div>}
        {fetchError && <div className="banner banner-error">Connection error: {fetchError}</div>}
        {data?.error && (
          <div className="banner banner-warning">
            HLC cycle failed: {data.error}
            {data.error_ts ? ` (as of ${fmtTime(data.error_ts)})` : ""}
          </div>
        )}
      </>

      {hasResult && data && (
        <main className="cockpit-stack">
          <CandidatesTable candidates={data.candidates!} atmStrike={data.atm_strike} />
          <LevelsPanel data={data} />
          <section className="panel">
            <h2>Buyer / Seller Activity (ATM Strike)</h2>
            <div className="hlc-legs">
              <LegColumn title="Call Option (CE)" leg={data.ce!} />
              <LegColumn title="Put Option (PE)" leg={data.pe!} />
            </div>
          </section>
          <section className={`panel suggestion-panel ${SIGNAL_CLASS[data.combined_signal ?? ""] ?? "bias-neutral"}`}>
            <div className="suggestion-headline">
              <span className="bias-label">{data.combined_signal}</span>
            </div>
          </section>
          {data.trade_plan && <TradePlanPanel plan={data.trade_plan} />}
          <RiskPanel />
          <RangeBandPanel title="Weekly Range" band={data.weekly} />
          <RangeBandPanel title="Monthly Range" band={data.monthly} />
        </main>
      )}
    </Cockpit>
  );
}
