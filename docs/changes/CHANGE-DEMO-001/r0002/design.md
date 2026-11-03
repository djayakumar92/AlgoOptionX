# First demo design addendum — revision 2

Retain the approved enterprise shell, nine routes, synthetic status bar, market
observations, option chain and strategy previews. Prior design and wireframe
states remain in revision 1. This revision adds the chart interaction specified
by DEMO-07; all other approved calculations and runtime boundaries remain intact.

Chart panel order: 5/30-minute switch; grouped navigation controls (Zoom in/out,
Pan left/right, Fit data); indicator toggles (Volume, EMA9, VWAP); readout of
selected timestamp/OHLCV; interactive candle surface with volume below price;
annotation toolbar; explanatory summary and expandable numerical candle table.
On mobile, tools wrap into named groups without page overflow. Theme colors use
existing tokens and pinned DejaVu Sans. Preserve user's viewport on unchanged
poll responses; refit only on initial data/timeframe/session or explicit Fit.

Crosshair follows pointer or Left/Right keys on the focused chart surface.
Keyboard +/− zooms and Shift+Left/Right pans. Readout identifies synthetic bar time;
no values are inferred when a point is not an observed candle. Indicators have
explicit model/warm-up explanations and do not authorize trading.

Horizontal annotation: choose mode and click a price or enter a positive price.
Trendline: choose two observed bar/price endpoints, or select both endpoints using
native fields. Show a pending-point instruction; Escape cancels pending drawing.
List stored annotations with exact values and named Remove controls. Clear removes
only view annotations. Changing scenario resets annotations; route navigation
between dashboard and market preserves them in the same synthetic session.

Loading/error/empty: preserve shell and explain recovery; empty chart disables
data-dependent tools. Stale: label last-valid data and permit inspection/drawing
without implying fresh prices; execution stays server-blocked. Disabled: explain
entry lock while analytical chart tools remain read-only. Chart and drawings must
never create an order, call a broker or alter strategy premiums.

Source boundary: demo chart/UI files, deterministic candle indicator output,
chart-specific Python tests, existing demo browser suite and presenter guide.
No research component/API files, governance enforcement, dependencies, credentials,
original paper engine or user history are modified. Rollback only these revision-2
chart/indicator/test hunks, preserving prior approved demo work and databases.
