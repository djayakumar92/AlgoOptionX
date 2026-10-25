import type { Time } from "lightweight-charts";
import { forwardRef, useState } from "react";
import { levelsFor } from "../chartLevels";
import { fmtNum } from "../format";
import { useCandles } from "../hooks/useCandles";
import type { ChartInstrument, ChartInterval, HlcStatePayload } from "../types";
import { CandleChart, type ChartHandle, type HoveredBar } from "./CandleChart";

const INSTRUMENTS: { value: ChartInstrument; label: string }[] = [
  { value: "spot", label: "Spot (NIFTY)" },
  { value: "ce", label: "ATM Call (CE)" },
  { value: "pe", label: "ATM Put (PE)" },
];

const TIMEFRAMES: { value: ChartInterval; label: string }[] = [
  { value: "1", label: "1m" },
  { value: "5", label: "5m" },
  { value: "15", label: "15m" },
  { value: "day", label: "Day" },
];

interface Props {
  instrument: ChartInstrument;
  interval: ChartInterval;
  onInstrumentChange: (v: ChartInstrument) => void;
  onIntervalChange: (v: ChartInterval) => void;
  hlcData: HlcStatePayload | null;
  onCrosshairMove?: (time: Time | null, price: number | null) => void;
  style?: React.CSSProperties;
}

/**
 * One chart, and everything that belongs to it, in a single card.
 *
 * The controls used to float above the card while the card printed the symbol
 * name again inside it -- three rows of chrome for one chart. They are now one
 * row, inside the card, sharing space with the price readout.
 *
 * The readout is the piece that was missing outright. Every trading chart
 * shows the open/high/low/close of whatever bar you are pointing at; without
 * it you can see the shape of a move but cannot read a number off it, which
 * is most of what a chart is for. It falls back to the latest bar when the
 * cursor is elsewhere, so the card always states a price rather than going
 * blank.
 */
export const ChartPane = forwardRef<ChartHandle, Props>(function ChartPane(
  { instrument, interval, onInstrumentChange, onIntervalChange, hlcData, onCrosshairMove, style },
  ref
) {
  const { candles, loading, error } = useCandles(instrument, interval);
  const [hovered, setHovered] = useState<HoveredBar | null>(null);
  const levels = levelsFor(instrument, hlcData);

  const latest = candles.length > 0 ? candles[candles.length - 1] : null;
  const bar = hovered ?? latest;
  const rising = bar ? bar.close >= bar.open : true;

  return (
    <div className="chart-pane" style={style}>
      <div className="chart-pane-head">
        <select
          className="chart-pane-select"
          value={instrument}
          onChange={(e) => onInstrumentChange(e.target.value as ChartInstrument)}
          aria-label="Chart symbol"
        >
          {INSTRUMENTS.map((i) => (
            <option key={i.value} value={i.value}>
              {i.label}
            </option>
          ))}
        </select>

        {bar && (
          <div className={`chart-ohlc ${rising ? "is-up" : "is-down"}`}>
            {/* O/H/L drop away first when the pane is narrow -- see the
                container queries in App.css. The close is what stays. */}
            <span className="chart-ohlc-hide-narrow">
              O <b>{fmtNum(bar.open, 2)}</b>
            </span>
            <span className="chart-ohlc-hide-narrow">
              H <b>{fmtNum(bar.high, 2)}</b>
            </span>
            <span className="chart-ohlc-hide-narrow">
              L <b>{fmtNum(bar.low, 2)}</b>
            </span>
            <span>
              C <b>{fmtNum(bar.close, 2)}</b>
            </span>
            {!hovered && <span className="chart-ohlc-note chart-ohlc-hide-narrow">latest</span>}
          </div>
        )}

        <div className="timeframe-selector">
          {TIMEFRAMES.map((tf) => (
            <button
              key={tf.value}
              className={tf.value === interval ? "timeframe-button active" : "timeframe-button"}
              onClick={() => onIntervalChange(tf.value)}
            >
              {tf.label}
            </button>
          ))}
        </div>
      </div>

      <CandleChart
        ref={ref}
        candles={candles}
        levels={levels}
        loading={loading}
        error={error}
        onCrosshairMove={onCrosshairMove}
        onHoverBar={setHovered}
      />
    </div>
  );
});
