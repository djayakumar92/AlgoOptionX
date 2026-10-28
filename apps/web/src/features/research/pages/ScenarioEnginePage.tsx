import { Cockpit, MarketBar } from "../components/Cockpit";
import { fmtNum } from "../format";
import { usePrediction } from "../hooks/usePrediction";
import type { PredictionPayload, Scenario, ScenarioSet } from "../types";

// Every figure here comes from signals/scenarios.py. The one number that
// needs care is the percentage on each scenario: it is the share of today's
// measurable evidence, not a probability. The mocked version of this page
// carried "62% / 24% / 14%" as static text, and replacing invented
// probabilities with different invented probabilities would have been the
// wrong reading of "make it real" -- so the label says "of today's evidence"
// everywhere it appears, and the caveat is printed rather than tucked away.

const VERDICT_LABEL: Record<ScenarioSet["verdict"], string> = {
  TRADE: "TRADE",
  WAIT: "WAIT",
  STAND_DOWN: "STAND DOWN",
};

const VERDICT_CLASS: Record<ScenarioSet["verdict"], string> = {
  TRADE: "bias-bullish",
  WAIT: "bias-neutral",
  STAND_DOWN: "bias-bearish",
};

const DIRECTION_CLASS: Record<Scenario["direction"], string> = {
  BULLISH: "bias-bullish",
  BEARISH: "bias-bearish",
  NEUTRAL: "bias-neutral",
};

function ScenarioCard({ scenario }: { scenario: Scenario }) {
  return (
    <article className="setup-card">
      <div className="setup-card-head">
        <span className={`setup-card-title ${DIRECTION_CLASS[scenario.direction]}`}>
          {scenario.name}
        </span>
        <span className={`setup-card-grade ${DIRECTION_CLASS[scenario.direction]}`}>
          {fmtNum(scenario.evidence_share, 0)}%
        </span>
      </div>
      <p className="metric-sub" style={{ marginTop: -6, marginBottom: 10 }}>
        of today's evidence
      </p>

      <div className="setup-field">
        <span className="setup-field-label">Happens when</span>
        {scenario.trigger}
      </div>
      <div className="setup-field">
        <span className="setup-field-label">Ruled out when</span>
        {scenario.invalidation}
      </div>
      {scenario.target_level !== null && (
        <div className="setup-field">
          <span className="setup-field-label">Plays for</span>
          {fmtNum(scenario.target_level, 0)}
        </div>
      )}
      <div className="setup-field">
        <span className="setup-field-label">What it means for you</span>
        {scenario.what_it_means}
      </div>

      <div className="setup-field">
        <span className="setup-field-label">Evidence pointing here</span>
        {scenario.evidence.length === 0 ? (
          <span className="metric-sub">Nothing currently points this way.</span>
        ) : (
          <div className="zone-factors evidence-bars">
            {scenario.evidence.map((e) => (
              <div className="score-bar-row" key={e.factor} title={e.detail}>
                <span className="score-bar-label">{e.factor}</span>
                <span className="score-bar-track">
                  <span className="score-bar-fill" style={{ width: "100%" }} />
                </span>
                <span className="score-bar-value">{fmtNum(e.weight, 0)}</span>
              </div>
            ))}
          </div>
        )}
      </div>

      {scenario.matching_setups.length > 0 && (
        <div className="setup-field">
          <span className="setup-field-label">Setups armed for this</span>
          {scenario.matching_setups.join(", ")}
        </div>
      )}
    </article>
  );
}

function Contents({ data }: { data: PredictionPayload }) {
  const set = data.scenarios;
  if (data.unavailable || !set) {
    return <div className="banner banner-info">{data.unavailable ?? "No reading available yet."}</div>;
  }

  return (
    <main className="cockpit-stack">
      <div className="recommendation-box">
        <div className="suggestion-headline">
          <span className={`bias-label ${VERDICT_CLASS[set.verdict]}`}>
            {VERDICT_LABEL[set.verdict]}
          </span>
          <span className="confidence">
            {set.checklist_passed} of {set.checklist_total} conditions met
          </span>
        </div>
        <p className="recommendation-reason">{set.verdict_note}</p>
      </div>

      <section className="panel">
        <h2>The three ways today can go</h2>
        <p className="disclaimer">
          Price can only take out the level above, take out the level below, or stay between them.
          Those are the three, always, with today's real levels attached. {set.caveat}
        </p>
        <div className="setup-grid">
          {set.scenarios.map((s) => (
            <ScenarioCard key={s.key} scenario={s} />
          ))}
        </div>
      </section>

      <section className="panel">
        <h2>Entry checklist</h2>
        <p className="disclaimer">
          The scenarios describe the market; this decides whether you act. A well-supported scenario
          with no entry trigger and a closed market is still not a trade.
        </p>
        <div className="checklist">
          {set.checklist.map((item) => (
            <div className="checklist-item" key={item.name}>
              <span className={`checklist-mark ${item.passed ? "pass" : "fail"}`}>
                {item.passed ? "✓" : "✗"}
              </span>
              <span>
                {item.name}
                <br />
                <span className="metric-sub">{item.detail}</span>
              </span>
            </div>
          ))}
        </div>
      </section>

      {data.best && (
        <section className="panel">
          <h2>Score behind today's setup</h2>
          <p className="disclaimer">
            {data.best.name} — {fmtNum(data.best.score, 0)} out of 100, broken down by what was
            actually present. Weights are the setup's own and always total 100.
          </p>
          <div className="zone-factors evidence-bars">
            {data.best.evidence.map((e) => (
              <div className="score-bar-row" key={e.name} title={e.detail}>
                <span className="score-bar-label">{e.name}</span>
                <span className="score-bar-track">
                  <span
                    className="score-bar-fill"
                    style={{ width: `${(e.earned / e.weight) * 100}%` }}
                  />
                </span>
                <span className="score-bar-value">
                  {fmtNum(e.earned, 0)}/{fmtNum(e.weight, 0)}
                </span>
              </div>
            ))}
          </div>
        </section>
      )}
    </main>
  );
}

export default function ScenarioEnginePage() {
  const { data, fetchError } = usePrediction();

  return (
    <Cockpit>
      <MarketBar title="Scenario Engine" data={data} />
      <p className="cockpit-lede">
        The ways this session can unfold, each with its own real trigger level and what would rule it
        out — plus the checklist that decides whether any of them is worth acting on.
      </p>

      {fetchError && <div className="banner banner-error">Connection error: {fetchError}</div>}
      {!data && !fetchError && <div className="banner banner-info">Working out the scenarios...</div>}
      {data && <Contents data={data} />}
    </Cockpit>
  );
}
