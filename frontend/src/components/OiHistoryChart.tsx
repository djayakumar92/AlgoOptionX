import { fmtHM, fmtNum } from "../format";
import type { OiHistoryPoint } from "../types";

const POINT_SPACING = 14;
const CHART_HEIGHT = 200;
const LABEL_HEIGHT = 26;
const LABEL_EVERY = 6; // ~30 minutes apart at 5-minute buckets

function pathFor(points: OiHistoryPoint[], value: (p: OiHistoryPoint) => number, maxVal: number): string {
  return points
    .map((p, i) => {
      const x = i * POINT_SPACING;
      const y = CHART_HEIGHT - (value(p) / maxVal) * CHART_HEIGHT;
      return `${i === 0 ? "M" : "L"}${x},${y}`;
    })
    .join(" ");
}

// Plain SVG, no charting library -- same reasoning as OiChart.tsx.
export function OiHistoryChart({ points }: { points: OiHistoryPoint[] }) {
  if (points.length === 0) return null;

  const maxVal = Math.max(1, ...points.flatMap((p) => [p.ce_oi, p.pe_oi]));
  const chartWidth = Math.max(1, points.length - 1) * POINT_SPACING;
  const cePath = pathFor(points, (p) => p.ce_oi, maxVal);
  const pePath = pathFor(points, (p) => p.pe_oi, maxVal);
  const latest = points[points.length - 1];

  return (
    <section className="panel chain-panel">
      <div className="oi-history-head">
        <h2>Open Interest Over Time</h2>
        <span className="oi-history-latest">
          Latest -- CE {fmtNum(latest.ce_oi, 0)} / PE {fmtNum(latest.pe_oi, 0)}
        </span>
      </div>
      <div className="oi-chart-scroll">
        <svg
          width={chartWidth}
          height={CHART_HEIGHT + LABEL_HEIGHT}
          role="img"
          aria-label="Total Call and Put open interest through today's session"
        >
          <path d={pePath} className="oi-history-line-pe" fill="none" />
          <path d={cePath} className="oi-history-line-ce" fill="none" />
          {points.map((p, i) =>
            i % LABEL_EVERY === 0 ? (
              <text key={p.ts} className="oi-chart-strike-label" x={i * POINT_SPACING} y={CHART_HEIGHT + 18}>
                {fmtHM(p.ts)}
              </text>
            ) : null
          )}
        </svg>
      </div>
      <div className="oi-chart-legend">
        <span>
          <i className="oi-chart-swatch oi-chart-swatch-ce" /> Call OI
        </span>
        <span>
          <i className="oi-chart-swatch oi-chart-swatch-pe" /> Put OI
        </span>
      </div>
    </section>
  );
}
