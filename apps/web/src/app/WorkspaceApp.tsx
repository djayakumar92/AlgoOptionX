import { useCallback, useEffect, useState } from "react";
import { NavLink, useLocation } from "react-router-dom";
import { api, command } from "../features/workspace/api/client";
import { number } from "../features/workspace/lib/format";
import type { Workspace } from "../features/workspace/types";
import { Icon, Badge } from "../shared/ui";
import type { IconName } from "../shared/ui";
import {
  AccountSummary,
  PositionsPanel,
  RiskPanel,
  ActivityPanel,
} from "../features/workspace/components";
import {
  OverviewPage,
  MarketTerminalPage,
  DecisionEnginePage,
  ReplayLabPage,
  PerformancePage,
  SettingsPage,
} from "../features/workspace/pages";
import "../features/workspace/styles/workspace.css";

const links: { to: string; label: string; icon: IconName; group?: string }[] = [
  { to: "/", label: "Overview", icon: "grid" },
  { to: "/market", label: "Market terminal", icon: "chart" },
  { to: "/paper", label: "Paper portfolio", icon: "wallet" },
  {
    to: "/strategy",
    label: "Decision engine",
    icon: "spark",
    group: "RESEARCH",
  },
  { to: "/backtest", label: "Replay lab", icon: "replay" },
  { to: "/analytics", label: "Performance", icon: "chart" },
  {
    to: "/journal",
    label: "Activity & audit",
    icon: "journal",
    group: "WORKSPACE",
  },
  { to: "/settings", label: "Settings", icon: "settings" },
];
const aliases: Record<string, string> = {
  "/live": "/market",
  "/chart": "/market",
  "/option-intelligence": "/market",
  "/ai-analyst": "/strategy",
  "/scenario-engine": "/strategy",
  "/market-structure": "/strategy",
  "/hlc": "/strategy",
  "/learning-lab": "/backtest",
  "/guide": "/settings",
};
export default function WorkspaceApp() {
  const location = useLocation();
  const path = aliases[location.pathname] || location.pathname;
  const [state, setState] = useState<Workspace | null>(null),
    [error, setError] = useState(""),
    [notice, setNotice] = useState(""),
    [busy, setBusy] = useState(false),
    [menu, setMenu] = useState(false),
    [connection, setConnection] = useState(true);
  const refresh = useCallback(async () => {
    const data = await api<Workspace>("workspace");
    setState(data);
    setConnection(true);
  }, []);
  useEffect(() => {
    let active = true;
    let timer: ReturnType<typeof setTimeout>;
    const poll = async () => {
      try {
        const data = await api<Workspace>("workspace");
        if (active) {
          setState(data);
          setConnection(true);
        }
      } catch {
        if (active) setConnection(false);
      } finally {
        if (active) timer = setTimeout(poll, 1500);
      }
    };
    void poll();
    return () => {
      active = false;
      clearTimeout(timer);
    };
  }, []);
  useEffect(() => {
    if (notice) {
      const timer = setTimeout(() => setNotice(""), 5000);
      return () => clearTimeout(timer);
    }
  }, [notice]);
  async function act(action: string, fields: object = {}) {
    if (busy) return;
    setBusy(true);
    setError("");
    try {
      await command(action, fields);
      await refresh();
      setNotice(
        action === "buy"
          ? "Virtual buy filled. Your position is now protected by stop and target rules."
          : action === "close"
            ? "Virtual position closed and recorded in your audit trail."
            : "Session updated.",
      );
    } catch (e) {
      setError((e as Error).message);
    } finally {
      setBusy(false);
    }
  }
  async function fresh() {
    setBusy(true);
    setError("");
    try {
      await api("sessions", {});
      await refresh();
      setNotice("New paper session created. Previous history is preserved.");
    } catch (e) {
      setError((e as Error).message);
    } finally {
      setBusy(false);
    }
  }
  const current = links.find((l) => l.to === path);
  const titles: Record<string, [string, string]> = {
    "/": [
      "Your market. Your edge.",
      "A focused workspace for research, disciplined decisions and paper execution.",
    ],
    "/market": [
      "The market, in focus.",
      "Explore synthetic NIFTY options. Test an idea without risking real capital.",
    ],
    "/paper": [
      "Practice with purpose.",
      "Your positions, capital and risk — in one clear view.",
    ],
    "/strategy": [
      "Clarity before conviction.",
      "Inspect the rule, understand the evidence, and let risk have the final word.",
    ],
    "/backtest": [
      "Ideas meet evidence.",
      "Repeatable synthetic experiments. Transparent assumptions. No hindsight.",
    ],
    "/analytics": [
      "Measure what matters.",
      "A clear accounting of your virtual capital, costs and outcomes.",
    ],
    "/journal": [
      "Every decision leaves a trail.",
      "Follow the complete story from funding to decisions, fills and exits.",
    ],
    "/settings": [
      "A workspace on your terms.",
      "Understand your environment, manage sessions and stay in control.",
    ],
  };
  const title = titles[path];
  return (
    <div className="ax-app">
      <a className="ax-skip" href="#workspace">
        Skip to workspace
      </a>
      <aside className={`ax-sidebar ${menu ? "is-open" : ""}`}>
        <NavLink to="/" className="ax-brand" onClick={() => setMenu(false)}>
          <span className="ax-brand-symbol">
            A<span>×</span>
          </span>
          <span>
            AlgoOption<span className="ax-brand-x">X</span>
            <small>THE RESEARCH WORKSPACE</small>
          </span>
        </NavLink>
        <div className="ax-workspace-chip">
          <span className="ax-workspace-avatar">P</span>
          <div>
            Personal workspace<small>Local environment</small>
          </div>
          <Badge>PAPER</Badge>
        </div>
        <nav aria-label="Main navigation">
          {links.map((l, i) => (
            <div key={l.to}>
              {l.group && <span className="ax-nav-group">{l.group}</span>}
              {i === 0 && <span className="ax-nav-group">TERMINAL</span>}
              <NavLink
                to={l.to}
                end={l.to === "/"}
                className={`ax-nav-link ${path === l.to ? "selected" : ""}`}
                onClick={() => setMenu(false)}
              >
                <Icon name={l.icon} />
                {l.label}
                {l.to === "/paper" && (
                  <span className="ax-nav-count">
                    {state?.positions.length || 0}
                  </span>
                )}
              </NavLink>
            </div>
          ))}
        </nav>
        <div className="ax-sidebar-bottom">
          <div className="ax-sandbox-card">
            <Icon name="shield" />
            <strong>Room to experiment.</strong>
            <p>
              Virtual capital. Real discipline.
              <br />
              No live orders. Ever.
            </p>
            <NavLink to="/settings" onClick={() => setMenu(false)}>
              About this workspace <Icon name="arrow" size={14} />
            </NavLink>
          </div>
          <div className="ax-profile">
            <span>AX</span>
            <div>
              Research workspace<small>AlgoOptionX · v0.2</small>
            </div>
            <span className="ax-dot" />
          </div>
        </div>
      </aside>
      {menu && (
        <button
          className="ax-menu-overlay"
          aria-label="Close navigation"
          onClick={() => setMenu(false)}
        />
      )}
      <div className="ax-main">
        <header className="ax-topbar">
          <div className="ax-breadcrumb">
            <button
              className="ax-icon-button ax-menu-toggle"
              aria-label="Toggle navigation"
              onClick={() => setMenu(!menu)}
            >
              <Icon name="menu" />
            </button>
            <span>Workspace</span>
            <span>/</span>
            <strong>{current?.label || "Page"}</strong>
          </div>
          <div className="ax-topbar-right">
            <span className="ax-connection">
              <i className={`ax-dot ${!connection ? "red" : ""}`} />
              {connection ? "Local engine connected" : "Connection lost"}
            </span>
            <Badge tone="purple">PAPER ENVIRONMENT</Badge>
          </div>
        </header>
        <main id="workspace" className="ax-content">
          <div className="ax-page-head">
            <div>
              <div className="ax-eyebrow">
                ALGOOPTIONX / {current?.label.toUpperCase() || "WORKSPACE"}
              </div>
              <h1>{title?.[0] || "Page not found"}</h1>
              <p>
                {title?.[1] || "Choose a page from the workspace navigation."}
              </p>
            </div>
            <div className="ax-head-meta">
              <span className="ax-session-label">
                <span className="ax-dot" />
                SYNTHETIC SESSION
              </span>
              <span>
                {state
                  ? new Date(state.market.time).toLocaleTimeString("en-IN", {
                      timeZone: "Asia/Kolkata",
                      hour: "2-digit",
                      minute: "2-digit",
                      hour12: false,
                    })
                  : "09:15"}{" "}
                IST <span className="ax-muted">· 02 NOV 2026</span>
              </span>
            </div>
          </div>
          {!connection && (
            <div className="ax-alert" role="alert">
              Cannot reach the AlgoOptionX backend. Displayed values may be
              stale. Start the paper workspace server and reconnect before
              trading.
              <button
                onClick={() => {
                  void refresh().catch(() => setConnection(false));
                }}
              >
                Retry
              </button>
            </div>
          )}
          {(error || state?.worker_error) && (
            <div className="ax-alert" role="alert">
              {error || state?.worker_error}
              <button aria-label="Dismiss error" onClick={() => setError("")}>
                <Icon name="close" size={16} />
              </button>
            </div>
          )}
          {notice && (
            <div className="ax-toast" role="status">
              <Icon name="shield" size={17} />
              {notice}
              <button
                aria-label="Dismiss notification"
                onClick={() => setNotice("")}
              >
                <Icon name="close" size={14} />
              </button>
            </div>
          )}
          {state ? (
            <>
              <div className="ax-session-bar">
                <div>
                  <span className="ax-sim-icon">
                    <Icon name="chart" size={18} />
                  </span>
                  <strong>NIFTY 50</strong>
                  <span className="ax-spot">{number(state.market.spot)}</span>
                  <Badge>SYNTHETIC DATA</Badge>
                  <span className="ax-muted ax-bar-count">
                    Bar {state.market.tick} / 374
                  </span>
                </div>
                <div>
                  <button
                    className="ax-button subtle"
                    disabled={busy || !connection}
                    onClick={() => void act("advance")}
                  >
                    +1 bar
                  </button>
                  <button
                    className="ax-button play"
                    disabled={busy || !connection}
                    onClick={() =>
                      void act("control", { running: !state.account.running })
                    }
                  >
                    <Icon
                      name={state.account.running ? "pause" : "play"}
                      size={14}
                    />
                    {state.account.running ? "Pause" : "Start playback"}
                  </button>
                </div>
              </div>
              <fieldset
                className="ax-workspace-fieldset"
                disabled={!connection || busy}
              >
                {path === "/" && (
                  <OverviewPage state={state} act={act} busy={busy} />
                )}
                {path === "/market" && (
                  <MarketTerminalPage state={state} act={act} busy={busy} />
                )}
                {path === "/paper" && (
                  <>
                    <AccountSummary state={state} />
                    <PositionsPanel state={state} act={act} busy={busy} />
                    <div className="ax-split">
                      <RiskPanel state={state} />
                      <ActivityPanel state={state} />
                    </div>
                  </>
                )}
                {path === "/strategy" && (
                  <DecisionEnginePage state={state} act={act} busy={busy} />
                )}
                {path === "/backtest" && <ReplayLabPage />}
                {path === "/journal" && <ActivityPanel state={state} full />}
                {path === "/analytics" && <PerformancePage state={state} />}
                {path === "/settings" && (
                  <SettingsPage
                    state={state}
                    act={act}
                    busy={busy}
                    fresh={() => void fresh()}
                  />
                )}
                {!title && (
                  <NavLink to="/" className="ax-button primary">
                    Return to overview
                  </NavLink>
                )}
              </fieldset>
            </>
          ) : (
            <div className="ax-loading">
              <span className="ax-loader" />
              <h2>Preparing your workspace</h2>
              <p>Connecting to the local AlgoOptionX paper engine…</p>
            </div>
          )}
          <footer className="ax-footer">
            <span>
              <Icon name="shield" size={13} />
              Built for research. Designed for discipline.
            </span>
            <span>Synthetic prices · Virtual capital · No live execution</span>
          </footer>
        </main>
      </div>
    </div>
  );
}
