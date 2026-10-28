import { Cockpit, MarketBar } from "../components/Cockpit";
import { useHealth } from "../hooks/useHealth";
import { useSettings } from "../hooks/useSettings";

export default function SettingsPage() {
  const health = useHealth();
  const { settings, error } = useSettings();

  return (
    <Cockpit>
      <MarketBar title="Settings" />
      <p className="cockpit-lede">
        The real configuration this run of the app is using — read-only. To change any of these, edit{" "}
        <code>config/research.toml</code> and restart the app.
      </p>

      <main className="cockpit-stack">
        {error && <div className="banner banner-error">Connection error: {error}</div>}

        <section className="panel">
          <h2>Underlying</h2>
          <div className="metrics-row">
            <div className="metric">
              <span className="metric-label">Symbol</span>
              <span className="metric-value">{settings?.underlying.symbol ?? health?.symbol ?? "-"}</span>
            </div>
            <div className="metric">
              <span className="metric-label">Segment</span>
              <span className="metric-value">{settings?.underlying.segment ?? "-"}</span>
            </div>
            <div className="metric">
              <span className="metric-label">Tracked Expiry</span>
              <span className="metric-value">{health?.expiry ?? "-"}</span>
            </div>
            <div className="metric">
              <span className="metric-label">Strike Window</span>
              <span className="metric-value">{settings?.underlying.strike_window ?? "-"}</span>
            </div>
          </div>
        </section>

        <section className="panel">
          <h2>Polling &amp; Historical</h2>
          <div className="metrics-row">
            <div className="metric">
              <span className="metric-label">Option Chain Poll</span>
              <span className="metric-value">{settings?.polling.option_chain_interval_sec ?? "-"}s</span>
            </div>
            <div className="metric">
              <span className="metric-label">Intraday Candle</span>
              <span className="metric-value">{settings?.historical.intraday_interval_min ?? "-"}m</span>
            </div>
            <div className="metric">
              <span className="metric-label">Backfill Days</span>
              <span className="metric-value">{settings?.historical.backfill_days ?? "-"}</span>
            </div>
          </div>
        </section>

        <section className="panel">
          <h2>HLC Trade Rule</h2>
          <div className="metrics-row">
            <div className="metric">
              <span className="metric-label">Domination Threshold</span>
              <span className="metric-value">{settings?.hlc.threshold_points ?? "-"} pts</span>
            </div>
            <div className="metric">
              <span className="metric-label">Target / Day</span>
              <span className="metric-value">{settings?.trade_plan.target_points_per_day ?? "-"} pts</span>
            </div>
            <div className="metric">
              <span className="metric-label">Max Trades / Day</span>
              <span className="metric-value">{settings?.trade_plan.max_trades_per_day ?? "-"}</span>
            </div>
          </div>
          <p className="not-an-order">
            The 35-point threshold and its flex-vs-fixed question are still an open item — see the
            migration requirements document.
          </p>
        </section>

        <section className="panel">
          <h2>Risk &amp; Position Sizing</h2>
          <div className="metrics-row">
            <div className="metric">
              <span className="metric-label">Capital</span>
              <span className="metric-value">{settings ? `₹${settings.risk.capital.toLocaleString()}` : "-"}</span>
            </div>
            <div className="metric">
              <span className="metric-label">Max Risk / Trade</span>
              <span className="metric-value">{settings ? `${(settings.risk.max_risk_pct_per_trade * 100).toFixed(1)}%` : "-"}</span>
            </div>
            <div className="metric">
              <span className="metric-label">Max Daily Loss</span>
              <span className="metric-value">{settings ? `${(settings.risk.max_daily_loss_pct * 100).toFixed(1)}%` : "-"}</span>
            </div>
            <div className="metric">
              <span className="metric-label">Lot Size</span>
              <span className="metric-value">{settings?.risk.lot_size ?? "-"}</span>
              <span className="metric-sub">read live from DhanHQ, not configured</span>
            </div>
          </div>
          <p className="not-an-order">
            Capital and risk percentages are for the position-sizing reference on the Trade Setups page —
            update them in <code>config/research.toml</code> to match your real trading capital.
          </p>
        </section>
      </main>
    </Cockpit>
  );
}
