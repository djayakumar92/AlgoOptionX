import { useEffect, useRef, useState } from "react";
import { Link, NavLink, useLocation } from "react-router-dom";
import { Icon } from "./Icon";
const items = [
  ["/app/overview", "Markets", "Overview"],
  ["/app/market", "Trade", "Market terminal"],
  ["/app/strategy", "Strategies", "Decision engine"],
  ["/app/paper", "Portfolio", "Paper portfolio"],
  ["/app/backtest", "Research", "Replay lab"],
];
export default function PrimaryNavigation() {
  const [open, setOpen] = useState(false);
  const trigger = useRef<HTMLButtonElement>(null);
  const { pathname } = useLocation();
  useEffect(() => { setOpen(false); }, [pathname]);
  return <header className="product-app-header" onKeyDown={event => { if (event.key === "Escape" && open) { setOpen(false); trigger.current?.focus(); } }}><Link to="/" className="product-app-brand">AlgoOption<span>X</span></Link><button ref={trigger} type="button" className="product-nav-toggle ax-button subtle" aria-label="Toggle navigation" aria-controls="product-main-navigation" aria-expanded={open} onClick={() => setOpen(!open)}><Icon name={open ? "close" : "menu"} /></button><nav id="product-main-navigation" className={open ? "is-open" : ""} aria-label="Main navigation">{items.map(([to, label, accessible]) => <NavLink key={to} to={to} aria-label={`${label} — ${accessible}`}>{label}</NavLink>)}<span className="product-nav-divider" /><NavLink to="/app/analytics">Performance</NavLink><NavLink to="/app/journal">Activity &amp; audit</NavLink><NavLink to="/app/settings">Settings</NavLink><NavLink to="/account">Account</NavLink></nav><span className="product-paper-label">PAPER / SYNTHETIC</span></header>;
}
