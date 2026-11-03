import { Link, Outlet, useLocation } from "react-router-dom";
import { useEffect } from "react";
import "../styles/product.css";
export default function PublicShell() {
  const { pathname, hash } = useLocation();
  useEffect(() => { document.title = `${pathname === "/walkthrough" ? "Product walkthrough" : pathname === "/app/start" ? "Get started" : "Options research & paper trading"} | AlgoOptionX`; if (hash) { let id = hash.slice(1); try { id = decodeURIComponent(id); } catch { /* Treat malformed encoding as a literal anchor. */ } document.getElementById(id)?.scrollIntoView(); } else { window.scrollTo(0, 0); } }, [pathname, hash]);
  return <div className="product-site"><a className="product-skip" href="#product-content">Skip to content</a><header className="public-header"><Link className="product-brand" to="/">AlgoOption<span>X</span></Link><nav aria-label="Public navigation"><Link to="/walkthrough">Product walkthrough</Link><Link className="product-button compact" to="/app/start">Explore the demo <span aria-hidden="true">→</span></Link></nav></header><Outlet /><footer className="public-footer"><Link className="product-brand" to="/">AlgoOption<span>X</span></Link><p>Local research software. Synthetic data. Virtual capital. No live execution.</p><Link to="/walkthrough#limitations">Simulation & limitations</Link></footer></div>;
}
