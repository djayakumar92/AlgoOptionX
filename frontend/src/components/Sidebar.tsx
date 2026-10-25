import { NavLink } from "react-router-dom";

function navClass({ isActive }: { isActive: boolean }) {
  return isActive ? "nav-link active" : "nav-link";
}

// "DEMO" pages have no backend engine behind them yet -- see DemoBanner.tsx
// and STRIKELINE_AI_MIGRATION_REQUIREMENTS.md's status table. Tagged here too
// so it's visible before you even click in.
function NavItem({ to, label, demo }: { to: string; label: string; demo?: boolean }) {
  return (
    <div className="nav-link-row">
      <NavLink to={to} className={navClass} end={to === "/"}>
        <span className="nav-link-text">{label}</span>
        {demo && <span className="nav-demo-tag">DEMO</span>}
      </NavLink>
    </div>
  );
}

export function Sidebar() {
  return (
    <aside className="sidebar">
      <div className="brand">
        <span className="brand-mark">SL</span>
        <div className="brand-text">
          <span className="brand-name">StrikeLine</span>
          <span className="brand-tagline">Make Plan Easy</span>
        </div>
      </div>

      <nav className="sidebar-nav">
        <NavItem to="/" label="Command Center" />

        <div className="nav-group-label">Market</div>
        <NavItem to="/live" label="Live Market" />
        <NavItem to="/market-structure" label="Market Structure" />
        <NavItem to="/option-intelligence" label="Option Intelligence" />
        <NavItem to="/chart" label="Charts" />

        <div className="nav-group-label">Intelligence</div>
        <NavItem to="/ai-analyst" label="AI Analyst" />
        <NavItem to="/scenario-engine" label="Scenario Engine" />

        <div className="nav-group-label">Trading</div>
        <NavItem to="/hlc" label="Trade Setups" />
        <NavItem to="/journal" label="Journal" />
        <NavItem to="/analytics" label="Analytics" />

        <div className="nav-group-label">Research</div>
        <NavItem to="/backtest" label="Backtest" />
        <NavItem to="/learning-lab" label="Learning Lab" />

        <div className="nav-group-label">System</div>
        <NavItem to="/guide" label="How to Trade" />
        <NavItem to="/settings" label="Settings" />
      </nav>

      <div className="sidebar-footer">Analytical tool only — never places an order.</div>
    </aside>
  );
}
