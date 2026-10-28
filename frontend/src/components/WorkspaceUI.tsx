import { useState } from "react";
import type { ReactNode } from "react";
import { NavLink } from "react-router-dom";
import { contractName, money, number } from "../workspace";
import type { Workspace } from "../workspace";

export type IconName =
  | "grid"
  | "chart"
  | "wallet"
  | "spark"
  | "replay"
  | "journal"
  | "settings"
  | "shield"
  | "arrow"
  | "play"
  | "pause"
  | "close"
  | "menu";
export function Icon({ name, size = 19 }: { name: IconName; size?: number }) {
  const paths: Record<IconName, ReactNode> = {
    grid: (
      <>
        <rect x="3" y="3" width="7" height="7" rx="1.5" />
        <rect x="14" y="3" width="7" height="7" rx="1.5" />
        <rect x="3" y="14" width="7" height="7" rx="1.5" />
        <rect x="14" y="14" width="7" height="7" rx="1.5" />
      </>
    ),
    chart: (
      <>
        <path d="M3 3v18h18M6 15l5-6 4 4 6-9" />
      </>
    ),
    wallet: (
      <>
        <rect x="3" y="5" width="18" height="15" rx="3" />
        <path d="M3 8V5a2 2 0 0 1 2-2h12M16 11h5v5h-5z" />
      </>
    ),
    spark: (
      <>
        <path d="m12 3 2.5 6.5L21 12l-6.5 2.5L12 21l-2.5-6.5L3 12l6.5-2.5z" />
      </>
    ),
    replay: (
      <>
        <path d="M3 11a9 9 0 1 1 2 7M3 4v7h7" />
        <path d="m10 8 6 4-6 4z" />
      </>
    ),
    journal: (
      <>
        <path d="M5 3h14v18H5zM8 7h8M8 11h8M8 15h5" />
      </>
    ),
    settings: (
      <>
        <path d="M4 6h16M4 12h16M4 18h16" />
        <circle cx="9" cy="6" r="2" />
        <circle cx="15" cy="12" r="2" />
        <circle cx="9" cy="18" r="2" />
      </>
    ),
    shield: (
      <>
        <path d="M12 3 4 6v6c0 5 8 9 8 9s8-4 8-9V6zM8 12l3 3 5-6" />
      </>
    ),
    arrow: <path d="M5 12h14m-5-5 5 5-5 5" />,
    play: <path d="m8 4 12 8-12 8z" />,
    pause: (
      <>
        <path d="M8 4v16M16 4v16" />
      </>
    ),
    close: <path d="m6 6 12 12M6 18 18 6" />,
    menu: <path d="M3 6h18M3 12h18M3 18h18" />,
  };
  return (
    <svg
      width={size}
      height={size}
      viewBox="0 0 24 24"
      fill="none"
      stroke="currentColor"
      strokeWidth="1.6"
      strokeLinecap="round"
      strokeLinejoin="round"
      aria-hidden="true"
    >
      {paths[name]}
    </svg>
  );
}
export function Badge({
  children,
  tone = "",
}: {
  children: ReactNode;
  tone?: string;
}) {
  return <span className={`ax-badge ${tone}`}>{children}</span>;
}
export function Panel({
  title,
  eyebrow,
  action,
  children,
  className = "",
}: {
  title: string;
  eyebrow?: string;
  action?: ReactNode;
  children: ReactNode;
  className?: string;
}) {
  return (
    <section className={`ax-panel ${className}`}>
      <div className="ax-panel-head">
        <div>
          {eyebrow && <span className="ax-eyebrow">{eyebrow}</span>}
          <h2>{title}</h2>
        </div>
        {action}
      </div>
      {children}
    </section>
  );
}
export function Empty({ title, text }: { title: string; text: string }) {
  return (
    <div className="ax-empty">
      <Icon name="wallet" size={28} />
      <h3>{title}</h3>
      <p>{text}</p>
    </div>
  );
}
export function LineChart({
  values,
  label,
  color = "#4ddbb0",
}: {
  values: number[];
  label: string;
  color?: string;
}) {
  if (values.length < 2)
    return (
      <Empty
        title="Your session starts here"
        text="Advance a bar or start playback to build the chart."
      />
    );
  const low = Math.min(...values),
    high = Math.max(...values),
    spread = Math.max(high - low, 1);
  const points = values
    .map(
      (v, i) =>
        `${30 + (i / (values.length - 1)) * 710},${195 - ((v - low) / spread) * 150}`,
    )
    .join(" ");
  return (
    <div className="ax-chart">
      <svg
        viewBox="0 0 800 235"
        role="img"
        aria-label={`${label}. Low ${number(low)}, high ${number(high)}, latest ${number(values.at(-1)!)}`}
      >
        <defs>
          <linearGradient
            id={`fill-${label.replace(/\W/g, "")}`}
            x1="0"
            y1="0"
            x2="0"
            y2="1"
          >
            <stop offset="0%" stopColor={color} stopOpacity=".22" />
            <stop offset="100%" stopColor={color} stopOpacity="0" />
          </linearGradient>
        </defs>
        {[45, 95, 145, 195].map((y) => (
          <line
            key={y}
            x1="30"
            x2="740"
            y1={y}
            y2={y}
            stroke="#ffffff09"
            strokeDasharray="4 5"
          />
        ))}
        <polygon
          points={`30,215 ${points} 740,215`}
          fill={`url(#fill-${label.replace(/\W/g, "")})`}
        />
        <polyline
          points={points}
          fill="none"
          stroke={color}
          strokeWidth="2.5"
          strokeLinejoin="round"
        />
        <text x="750" y="49" fill="#7e879a" fontSize="10">
          {number(high)}
        </text>
        <text x="750" y="199" fill="#7e879a" fontSize="10">
          {number(low)}
        </text>
        <text x="30" y="231" fill="#7e879a" fontSize="10">
          SESSION START
        </text>
        <text x="698" y="231" fill="#7e879a" fontSize="10">
          LATEST
        </text>
      </svg>
    </div>
  );
}
export function Stats({ state }: { state: Workspace }) {
  const a = state.account;
  return (
    <div className="ax-stats">
      {[
        {
          label: "Total equity",
          value: money(a.equity, 0),
          detail: "₹5,00,000 virtual starting capital",
          icon: "wallet" as IconName,
        },
        {
          label: "Session P&L",
          value: money(a.pnl),
          detail: `${a.pnl >= 0 ? "+" : ""}${((a.pnl / a.capital) * 100).toFixed(2)}% · marked at mid price`,
          icon: "chart" as IconName,
          tone: a.pnl >= 0 ? "positive" : "negative",
        },
        {
          label: "Available cash",
          value: money(a.cash, 0),
          detail: `${money(a.exposure, 0)} premium deployed`,
          icon: "grid" as IconName,
        },
        {
          label: "Open positions",
          value: String(state.positions.length).padStart(2, "0"),
          detail: `of ${state.risk.max_positions} permitted · long options only`,
          icon: "shield" as IconName,
        },
      ].map((s) => (
        <div className="ax-stat" key={s.label}>
          <div className="ax-stat-label">
            {s.label}
            <Icon name={s.icon} />
          </div>
          <div className={`ax-stat-value ${s.tone || ""}`}>{s.value}</div>
          <div className="ax-stat-detail">{s.detail}</div>
        </div>
      ))}
    </div>
  );
}
export function Positions({
  state,
  act,
  busy,
}: {
  state: Workspace;
  act: (action: string, fields?: object) => void;
  busy: boolean;
}) {
  return (
    <Panel
      title="Open positions"
      action={<Badge>{state.positions.length} active</Badge>}
    >
      {state.positions.length ? (
        <div className="ax-table-wrap">
          <table>
            <thead>
              <tr>
                <th>Contract</th>
                <th>Qty</th>
                <th>Entry</th>
                <th>Mark</th>
                <th>Exit P&L estimate</th>
                <th>Action</th>
              </tr>
            </thead>
            <tbody>
              {state.positions.map((p) => (
                <tr key={p.id}>
                  <td>
                    <strong>{contractName(p.instrument)}</strong>
                    <small>
                      Stop {money(p.stop)} · Target {money(p.target)}
                    </small>
                  </td>
                  <td>{p.quantity}</td>
                  <td>{money(p.entry)}</td>
                  <td>{money(p.mark)}</td>
                  <td className={p.unrealized >= 0 ? "positive" : "negative"}>
                    {money(p.unrealized)}
                  </td>
                  <td>
                    <button
                      className="ax-button subtle"
                      disabled={busy}
                      onClick={() => act("close", { position_id: p.id })}
                    >
                      Close position
                    </button>
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      ) : (
        <Empty
          title="A clean slate. A clear plan."
          text="Choose a contract in the market terminal, or enable the decision engine for autonomous virtual entries."
        />
      )}
    </Panel>
  );
}
export function Risk({ state }: { state: Workspace }) {
  const used = (state.account.exposure / state.risk.max_exposure) * 100;
  return (
    <Panel title="Risk guardrails" action={<Icon name="shield" />}>
      <div className="ax-risk-list">
        <div className="ax-risk-status">
          <span className={`ax-dot ${state.account.killed ? "red" : ""}`} />
          {state.account.killed
            ? "Entries blocked · kill switch active"
            : "Deterministic risk checks active"}
        </div>
        <div className="ax-risk-row">
          <span>Premium exposure</span>
          <strong>{used.toFixed(1)}%</strong>
        </div>
        <div className="ax-meter">
          <i style={{ width: `${Math.min(used, 100)}%` }} />
        </div>
        <div className="ax-risk-caption">
          {money(state.account.exposure, 0)} /{" "}
          {money(state.risk.max_exposure, 0)}
        </div>
        <div className="ax-risk-row">
          <span>Per-trade stop-risk cap</span>
          <strong>{money(state.risk.max_trade_risk, 0)}</strong>
        </div>
        <div className="ax-risk-row">
          <span>Daily entry lock threshold</span>
          <strong>{money(state.risk.max_daily_loss, 0)}</strong>
        </div>
        <div className="ax-risk-row">
          <span>Maximum open positions</span>
          <strong>03</strong>
        </div>
        <div className="ax-risk-row">
          <span>Execution mode</span>
          <Badge tone="green">PAPER ONLY</Badge>
        </div>
        <p className="ax-note">
          Stops are virtual exit triggers. Gaps may exceed their planned loss.
          No broker orders are sent.
        </p>
      </div>
    </Panel>
  );
}
export function Activity({
  state,
  full = false,
}: {
  state: Workspace;
  full?: boolean;
}) {
  const [filter, setFilter] = useState("ALL");
  const events = state.events
    .filter((e) => filter === "ALL" || e.kind === filter)
    .slice(0, full ? 150 : 5);
  return (
    <Panel
      title={full ? "Session audit trail" : "Recent activity"}
      action={
        full ? (
          <a href="/api/audit/export" className="ax-button subtle" download>
            Export JSON ↓
          </a>
        ) : (
          <NavLink className="ax-text-link" to="/journal">
            View all <Icon name="arrow" size={14} />
          </NavLink>
        )
      }
    >
      {full && (
        <div className="ax-filters">
          {["ALL", "BUY", "SELL", "REJECTED", "DECISION", "CONTROL"].map(
            (f) => (
              <button
                key={f}
                className={filter === f ? "active" : ""}
                onClick={() => setFilter(f)}
              >
                {f === "ALL" ? "All events" : f.toLowerCase()}
              </button>
            ),
          )}
        </div>
      )}
      {!events.length && (
        <Empty
          title="No matching events"
          text="Events appear here as your paper session progresses."
        />
      )}
      <div className="ax-activity">
        {events.map((e) => (
          <div className="ax-event" key={e.seq}>
            <div
              className={`ax-event-icon ${e.kind === "REJECTED" ? "warn" : ""}`}
            >
              <Icon
                name={
                  e.kind === "BUY" || e.kind === "SELL"
                    ? "wallet"
                    : e.kind === "FUNDING"
                      ? "spark"
                      : "shield"
                }
                size={16}
              />
            </div>
            <div>
              <strong>{e.payload.message || e.kind}</strong>
              <span>
                Bar {e.tick} · {e.kind}
                {full && ` · ${e.hash.slice(0, 16)}…`}
              </span>
            </div>
            <span className="ax-event-seq">
              #{String(e.seq).padStart(3, "0")}
            </span>
          </div>
        ))}
      </div>
      {full && (
        <p className="ax-footnote">
          Showing the latest 150 events. Export includes the complete session
          hash chain. Local hashes detect accidental changes; they are not
          independently anchored attestations.
        </p>
      )}
    </Panel>
  );
}
