import { Link } from "react-router-dom";

const steps = [
  ["01", "Set your starting point", "Choose the guided Command Center or go straight to Market Intelligence. These presentation preferences do not alter capital or risk limits."],
  ["02", "Inspect before acting", "Explore completed 5/30-minute candles, chart tools and synthetic option quotes. Build a bull put spread, bear call spread or iron condor."],
  ["03", "Review, then practice", "Inspect payoff, modeled costs and conservative risk reserves before explicitly confirming a simulated multi-leg order. Monitor positions and emergency controls."],
  ["04", "Close the loop", "Review fills, costs and journal notes. Run illustrative research separately from your active account. These experiments do not establish historical options performance."],
];

export default function WalkthroughPage() {
  return (
    <main id="product-content" className="walkthrough">
      <span className="product-eyebrow">PRODUCT WALKTHROUGH</span>
      <h1>A clearer path through<br />your research.</h1>
      <p className="product-lead">Explore the current local demo before you begin. These are synthetic experiments, not historical options performance.</p>
      <div className="walkthrough-steps">
        {steps.map(([n, title, body]) => (
          <article key={n}><span>{n}</span><div><h2>{title}</h2><p>{body}</p></div></article>
        ))}
      </div>
      <section id="limitations" className="limitations">
        <span className="product-eyebrow">SIMULATION &amp; LIMITATIONS</span>
        <h2>Know what the demo represents.</h2>
        <ul>
          <li>Deterministic synthetic prices, instruments and model Greeks; no exchange-data entitlement is implied.</li>
          <li>₹5,00,000 starting virtual capital, integer-paise accounting and defined-risk multi-leg strategies. The demo account is separate from the original long-only workspace.</li>
          <li>Template demo legs fill atomically; quote-driven paper orders fill in atomic one-lot baskets. That does not represent guaranteed atomic exchange or broker execution.</li>
          <li>Fixture spread, slippage and ₹20 per leg/fill. These are not a complete Indian broker tax or fee schedule.</li>
          <li>Conservative capital reserves are simulation risk controls, not exchange margin. The separate paper order workspace models pending orders and one-lot partial fills; it does not model real exchange settlement.</li>
          <li>Market observations are rule-based. Insights use pre-authored commentary, not live AI predictions or calibrated probabilities.</li>
          <li>Optional accounts support private workspaces and security settings. Commercial activation, production hosting and real-money execution remain unavailable.</li>
        </ul>
        <p>The original long-only workspace remains available with its own preserved account history. The separate Dhan research workflow requires its existing launcher and credentials; the demo does not connect to it.</p>
        <Link className="product-text-link" to="/app/overview">Open original workspace →</Link>
      </section>
      <Link className="product-button" to="/app/start">Explore the demo →</Link>
    </main>
  );
}
