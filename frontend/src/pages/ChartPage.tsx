import { Cockpit, MarketBar } from "../components/Cockpit";
import type { Time } from "lightweight-charts";
import { useRef, useState } from "react";
import { LAYOUT_OPTIONS, type LayoutId } from "../chartLayouts";
import type { ChartHandle } from "../components/CandleChart";
import { ChartPane } from "../components/ChartPane";
import { LayoutIcon } from "../components/LayoutIcon";
import { useHlcState } from "../hooks/useHlcState";
import type { ChartInstrument, ChartInterval } from "../types";

interface PaneConfig {
  instrument: ChartInstrument;
  interval: ChartInterval;
}

const DEFAULT_PANES: PaneConfig[] = [
  { instrument: "spot", interval: "5" },
  { instrument: "spot", interval: "15" },
  { instrument: "ce", interval: "5" },
  { instrument: "pe", interval: "5" },
];

export default function ChartPage() {
  const { data } = useHlcState();
  const [layoutId, setLayoutId] = useState<LayoutId>("4-grid");
  const [panes, setPanes] = useState<PaneConfig[]>(DEFAULT_PANES);
  const [layoutOpen, setLayoutOpen] = useState(false);
  const [syncSymbol, setSyncSymbol] = useState(false);
  const [syncInterval, setSyncInterval] = useState(false);
  const [syncCrosshair, setSyncCrosshair] = useState(true);

  const paneRefs = useRef<Array<ChartHandle | null>>([]);
  const broadcastingRef = useRef(false);

  const layout = LAYOUT_OPTIONS.find((o) => o.id === layoutId) ?? LAYOUT_OPTIONS[0];

  function updatePane(index: number, patch: Partial<PaneConfig>) {
    setPanes((prev) => {
      if (syncSymbol && patch.instrument !== undefined) {
        return prev.map((p) => ({ ...p, instrument: patch.instrument! }));
      }
      if (syncInterval && patch.interval !== undefined) {
        return prev.map((p) => ({ ...p, interval: patch.interval! }));
      }
      return prev.map((p, i) => (i === index ? { ...p, ...patch } : p));
    });
  }

  function handleCrosshairMove(sourceIndex: number, time: Time | null, price: number | null) {
    if (!syncCrosshair || broadcastingRef.current) return;
    broadcastingRef.current = true;
    paneRefs.current.forEach((api, i) => {
      if (i === sourceIndex || !api) return;
      if (time !== null && price !== null) {
        api.setCrosshair(time, price);
      } else {
        api.clearCrosshair();
      }
    });
    broadcastingRef.current = false;
  }

  return (
    <Cockpit>
      {/* The layout picker moves into the bar rather than sitting in a header
          row of its own. Charts are the one page where vertical space is the
          scarce resource, so the sticky strip has to pay for itself by
          absorbing the controls it replaces. */}
      <MarketBar title="Charts">
        <div className="layout-picker">
            <button className="fetch-latest-button" onClick={() => setLayoutOpen((o) => !o)}>
              <LayoutIcon id={layoutId} /> Layout
            </button>
            {layoutOpen && (
              <>
                <div className="layout-popover-backdrop" onClick={() => setLayoutOpen(false)} />
                <div className="layout-popover">
                <div className="layout-popover-grid">
                  {LAYOUT_OPTIONS.map((option) => (
                    <button
                      key={option.id}
                      className={option.id === layoutId ? "layout-option active" : "layout-option"}
                      onClick={() => {
                        setLayoutId(option.id);
                        setLayoutOpen(false);
                      }}
                      title={option.label}
                    >
                      <LayoutIcon id={option.id} />
                      <span>{option.label}</span>
                    </button>
                  ))}
                </div>
                <div className="layout-popover-sync">
                  <div className="sync-heading">Sync across panes</div>
                  <label className="sync-toggle">
                    <span>Symbol</span>
                    <span className="switch">
                      <input type="checkbox" checked={syncSymbol} onChange={(e) => setSyncSymbol(e.target.checked)} />
                      <span className="switch-track" />
                    </span>
                  </label>
                  <label className="sync-toggle">
                    <span>Timeframe</span>
                    <span className="switch">
                      <input
                        type="checkbox"
                        checked={syncInterval}
                        onChange={(e) => setSyncInterval(e.target.checked)}
                      />
                      <span className="switch-track" />
                    </span>
                  </label>
                  <label className="sync-toggle">
                    <span>Crosshair</span>
                    <span className="switch">
                      <input
                        type="checkbox"
                        checked={syncCrosshair}
                        onChange={(e) => setSyncCrosshair(e.target.checked)}
                      />
                      <span className="switch-track" />
                    </span>
                  </label>
                </div>
                </div>
              </>
            )}
        </div>
      </MarketBar>

      {/* Deliberately one line. The grid below sizes itself against the
          window, so every extra line here comes straight out of the charts. */}
      <p className="cockpit-lede">
        Spot, ATM Call and ATM Put against your HLC levels — each pane picks its own symbol and
        timeframe. Analytical output only; this never places an order.
      </p>

      <main className={`chart-grid ${layout.gridClassName}`}>
        {panes.slice(0, layout.paneCount).map((pane, i) => (
          <ChartPane
            key={i}
            ref={(el) => {
              paneRefs.current[i] = el;
            }}
            instrument={pane.instrument}
            interval={pane.interval}
            onInstrumentChange={(v) => updatePane(i, { instrument: v })}
            onIntervalChange={(v) => updatePane(i, { interval: v })}
            hlcData={data}
            onCrosshairMove={(time, price) => handleCrosshairMove(i, time, price)}
            style={layout.areas ? { gridArea: layout.areas[i] } : undefined}
          />
        ))}
      </main>
    </Cockpit>
  );
}
