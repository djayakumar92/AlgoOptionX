import { number } from "../lib/format";
import { EmptyState } from "./EmptyState";

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
      <EmptyState
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
