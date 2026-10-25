import { fmtNum } from "../format";
import type { ChainRow } from "../types";

const BAR_WIDTH = 14;
const BAR_GAP = 4;
const GROUP_GAP = 18;
const CHART_HEIGHT = 200;
const LABEL_HEIGHT = 26;
const GROUP_WIDTH = BAR_WIDTH * 2 + BAR_GAP;

// Plain SVG, no charting library -- this app deliberately stays framework-free
// (see App.tsx/App.css) and reusing lightweight-charts here would just be the
// same tool the user already said they don't like, for a completely different
// kind of chart (categorical bars by strike, not a time series).
export function OiChart({ rows }: { rows: ChainRow[] }) {
  if (rows.length === 0) return null;

  const maxOi = Math.max(1, ...rows.flatMap((r) => [r.ce_oi ?? 0, r.pe_oi ?? 0]));
  const chartWidth = rows.length * (GROUP_WIDTH + GROUP_GAP);

  return (
    <section className="panel chain-panel">
      <h2>Open Interest by Strike</h2>
      <div className="oi-chart-scroll">
        <svg
          width={chartWidth}
          height={CHART_HEIGHT + LABEL_HEIGHT}
          role="img"
          aria-label="Call and Put open interest by strike"
        >
          {rows.map((row, i) => {
            const x = i * (GROUP_WIDTH + GROUP_GAP);
            const ceOi = row.ce_oi ?? 0;
            const peOi = row.pe_oi ?? 0;
            const ceH = (ceOi / maxOi) * CHART_HEIGHT;
            const peH = (peOi / maxOi) * CHART_HEIGHT;
            return (
              <g key={row.strike}>
                {row.is_atm && (
                  <rect
                    className="oi-chart-atm-band"
                    x={x - GROUP_GAP / 2}
                    y={0}
                    width={GROUP_WIDTH + GROUP_GAP}
                    height={CHART_HEIGHT}
                  />
                )}
                <rect className="oi-chart-bar-ce" x={x} y={CHART_HEIGHT - ceH} width={BAR_WIDTH} height={ceH}>
                  <title>{`${fmtNum(row.strike, 0)} CE OI: ${fmtNum(ceOi, 0)}`}</title>
                </rect>
                <rect
                  className="oi-chart-bar-pe"
                  x={x + BAR_WIDTH + BAR_GAP}
                  y={CHART_HEIGHT - peH}
                  width={BAR_WIDTH}
                  height={peH}
                >
                  <title>{`${fmtNum(row.strike, 0)} PE OI: ${fmtNum(peOi, 0)}`}</title>
                </rect>
                <text className="oi-chart-strike-label" x={x + GROUP_WIDTH / 2} y={CHART_HEIGHT + 18}>
                  {fmtNum(row.strike, 0)}
                  {row.is_atm ? "*" : ""}
                </text>
              </g>
            );
          })}
        </svg>
      </div>
      <div className="oi-chart-legend">
        <span>
          <i className="oi-chart-swatch oi-chart-swatch-ce" /> Call OI (resistance)
        </span>
        <span>
          <i className="oi-chart-swatch oi-chart-swatch-pe" /> Put OI (support)
        </span>
        <span>* ATM strike</span>
      </div>
    </section>
  );
}
