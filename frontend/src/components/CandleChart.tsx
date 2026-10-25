import {
  CandlestickSeries,
  ColorType,
  createChart,
  type CandlestickData,
  type IChartApi,
  type IPriceLine,
  type ISeriesApi,
  type MouseEventParams,
  type Time,
  type UTCTimestamp,
} from "lightweight-charts";
import { forwardRef, useEffect, useImperativeHandle, useRef } from "react";
import type { Candle } from "../types";

export interface ChartLevel {
  price: number;
  label: string;
  color: string;
}

export interface ChartHandle {
  setCrosshair: (time: Time, price: number) => void;
  clearCrosshair: () => void;
}

/** The bar under the cursor, for the readout in the pane header. */
export interface HoveredBar {
  open: number;
  high: number;
  low: number;
  close: number;
}

interface Props {
  candles: Candle[];
  levels: ChartLevel[];
  loading: boolean;
  error: string | null;
  onCrosshairMove?: (time: Time | null, price: number | null) => void;
  onHoverBar?: (bar: HoveredBar | null) => void;
}

// This component is now just the chart surface: no title, no controls. Those
// moved into the pane header (ChartPane), where they belong -- previously the
// pane rendered a symbol dropdown and then this component printed the same
// symbol name again immediately below it, and both sat above the card rather
// than inside it. The result was three rows of chrome above every chart, on
// the one page where vertical space is the scarce resource.
export const CandleChart = forwardRef<ChartHandle, Props>(function CandleChart(
  { candles, levels, loading, error, onCrosshairMove, onHoverBar },
  ref
) {
  const containerRef = useRef<HTMLDivElement>(null);
  const chartRef = useRef<IChartApi | null>(null);
  const seriesRef = useRef<ISeriesApi<"Candlestick"> | null>(null);
  const priceLinesRef = useRef<IPriceLine[]>([]);
  const onCrosshairMoveRef = useRef(onCrosshairMove);
  const onHoverBarRef = useRef(onHoverBar);
  const suppressNextRef = useRef(false);

  useEffect(() => {
    onCrosshairMoveRef.current = onCrosshairMove;
    onHoverBarRef.current = onHoverBar;
  }, [onCrosshairMove, onHoverBar]);

  // Create the chart once per mount.
  useEffect(() => {
    if (!containerRef.current) return;

    const chart = createChart(containerRef.current, {
      layout: { background: { type: ColorType.Solid, color: "transparent" }, textColor: "#888" },
      grid: {
        vertLines: { color: "rgba(128,128,128,0.12)" },
        horzLines: { color: "rgba(128,128,128,0.12)" },
      },
      // autoSize manages width/height itself via its own internal ResizeObserver
      // -- more reliable than sizing off containerRef.current.clientWidth at
      // creation time, which can still be 0 before a CSS grid layout settles.
      autoSize: true,
      timeScale: { timeVisible: true, secondsVisible: false },
    });
    const series = chart.addSeries(CandlestickSeries, {
      upColor: "#16803c",
      downColor: "#c62828",
      borderVisible: false,
      wickUpColor: "#16803c",
      wickDownColor: "#c62828",
    });

    chartRef.current = chart;
    seriesRef.current = series;

    const handleCrosshairMove = (param: MouseEventParams<Time>) => {
      const point = seriesRef.current
        ? (param.seriesData.get(seriesRef.current) as CandlestickData<Time> | undefined)
        : undefined;

      // The readout is updated even for a synced move from another pane --
      // that is the whole point of syncing the crosshair, and unlike the
      // broadcast below it cannot loop.
      onHoverBarRef.current?.(
        point
          ? { open: point.open, high: point.high, low: point.low, close: point.close }
          : null
      );

      // A move caused by another pane's sync call (via setCrosshair below)
      // still fires this same handler -- swallow exactly one such event so
      // it doesn't re-broadcast and loop back into the other panes.
      if (suppressNextRef.current) {
        suppressNextRef.current = false;
        return;
      }
      if (!onCrosshairMoveRef.current) return;
      if (param.time === undefined || !seriesRef.current) {
        onCrosshairMoveRef.current(null, null);
        return;
      }
      onCrosshairMoveRef.current(param.time, point ? point.close : null);
    };
    chart.subscribeCrosshairMove(handleCrosshairMove);

    return () => {
      chart.unsubscribeCrosshairMove(handleCrosshairMove);
      chart.remove();
      chartRef.current = null;
      seriesRef.current = null;
      priceLinesRef.current = [];
    };
  }, []);

  // Update candle data.
  useEffect(() => {
    if (!seriesRef.current) return;
    seriesRef.current.setData(
      candles.map((c) => ({
        time: c.ts as UTCTimestamp,
        open: c.open,
        high: c.high,
        low: c.low,
        close: c.close,
      }))
    );
    chartRef.current?.timeScale().fitContent();
  }, [candles]);

  // Update level lines: clear old ones, draw the new set.
  useEffect(() => {
    const series = seriesRef.current;
    if (!series) return;

    for (const line of priceLinesRef.current) {
      series.removePriceLine(line);
    }
    priceLinesRef.current = levels.map((level) =>
      series.createPriceLine({
        price: level.price,
        color: level.color,
        title: level.label,
        lineWidth: 1,
      })
    );
  }, [levels]);

  useImperativeHandle(ref, () => ({
    setCrosshair: (time, price) => {
      if (!chartRef.current || !seriesRef.current) return;
      suppressNextRef.current = true;
      chartRef.current.setCrosshairPosition(price, time, seriesRef.current);
    },
    clearCrosshair: () => {
      if (!chartRef.current) return;
      suppressNextRef.current = true;
      chartRef.current.clearCrosshairPosition();
    },
  }), []);

  const empty = !loading && !error && candles.length === 0;

  return (
    <div className="candle-chart-canvas-wrap">
      <div ref={containerRef} className="candle-chart-canvas" />

      {/* Overlaid rather than stacked above the canvas. As sibling blocks
          these pushed the chart down and then let it snap back when they
          cleared, so every pane jumped on load and on every timeframe
          change. */}
      {(loading || error || empty) && (
        <div className="chart-overlay">
          {error ? (
            <>
              <span className="chart-overlay-title">Chart unavailable</span>
              <span className="chart-overlay-detail">{error}</span>
            </>
          ) : loading ? (
            <span className="chart-overlay-detail">Loading…</span>
          ) : (
            <>
              <span className="chart-overlay-title">No candles for this timeframe</span>
              <span className="chart-overlay-detail">
                The broker returned no bars — usually because the market has not traded this
                contract yet today.
              </span>
            </>
          )}
        </div>
      )}
    </div>
  );
});
