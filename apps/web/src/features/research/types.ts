export interface SentimentSummary {
  pcr_oi: number | null;
  pcr_volume: number | null;
  max_pain_strike: number | null;
  call_iv_atm: number | null;
  put_iv_atm: number | null;
  iv_skew: number | null;
  top_call_oi_strikes: number[];
  top_put_oi_strikes: number[];
  bias_lean: string;
}

export interface OiBehaviorSummary {
  call_long_buildup_count: number;
  put_long_buildup_count: number;
  call_short_buildup_count: number;
  put_short_buildup_count: number;
  bias_lean: string;
}

export interface TrendSummary {
  vwap: number | null;
  price_vs_vwap: string;
  ma_fast: number | null;
  ma_slow: number | null;
  ma_crossover: string;
  adx: number | null;
  trend_strength: string;
  bias_lean: string;
}

export interface MomentumSummary {
  rsi: number | null;
  rsi_state: string;
  roc: number | null;
  iv_rank: number | null;
  bias_lean: string;
}

export interface Suggestion {
  timestamp: string;
  spot_price: number;
  bias: "BULLISH" | "BEARISH" | "NEUTRAL";
  confidence: number;
  contributing_signals: Record<string, string>;
  suggested_instrument: string | null;
  entry_zone: string | null;
  stop_loss: string | null;
  watch_level: string | null;
  rationale: string;
}

export interface ChainRow {
  strike: number;
  is_atm: boolean;
  ce_oi: number | null;
  ce_ltp: number | null;
  pe_ltp: number | null;
  pe_oi: number | null;
  // Per-strike depth used by the Option Intelligence page -- not rendered on
  // the Live page's compact chain table.
  ce_iv: number | null;
  pe_iv: number | null;
  ce_volume: number | null;
  pe_volume: number | null;
  ce_delta: number | null;
  pe_delta: number | null;
  ce_bid: number | null;
  ce_ask: number | null;
  pe_bid: number | null;
  pe_ask: number | null;
}

export interface LiveStatePayload {
  ts?: number;
  spot_price?: number;
  atm_strike?: number | null;
  sentiment?: SentimentSummary;
  oi_behavior?: OiBehaviorSummary;
  trend?: TrendSummary;
  momentum?: MomentumSummary;
  suggestion?: Suggestion;
  chain?: ChainRow[];
  error: string | null;
  error_ts: number | null;
}

export interface HealthPayload {
  status: string;
  symbol: string;
  expiry: string;
}

export interface SessionOhlc {
  high: number;
  close: number;
  low: number;
}

export interface HlcStrikeQuote {
  strike: number;
  ce: SessionOhlc | null;
  pe: SessionOhlc | null;
}

export interface HlcLegAnalysis {
  high: number;
  close: number;
  low: number;
  close_high_diff: number;
  close_low_diff: number;
  domination: "Buyer" | "Seller" | "Indecision";
  market_type: "Panic" | "Profit Booking" | "Sideways";
}

export interface RangeBand {
  close: number;
  low_strike: number;
  high_strike: number;
  low_premium: number;
  high_premium: number;
  sell_low: number;
  sell_high: number;
  buy_low: number;
  buy_high: number;
}

export interface TradeLeg {
  option_type: "CE" | "PE";
  action: "SELL";
  strike: number;
  entry_trigger: number;
  stop_rule: string;
  target: number;
  target_points: number;
}

export interface TradePlan {
  session_date: string; // the completed session this plan's numbers were built from
  trade_date: string; // the next trading session this plan is meant to be acted on
  legs: TradeLeg[];
  note: string;
}

export interface HlcStatePayload {
  session_date?: string;
  nifty_close?: number;
  candidates?: HlcStrikeQuote[];
  atm_strike?: number;
  atm_ce_close?: number;
  atm_pe_close?: number;
  max_resistance?: number;
  min_resistance?: number;
  min_support?: number;
  max_support?: number;
  ce?: HlcLegAnalysis;
  pe?: HlcLegAnalysis;
  combined_signal?: string;
  weekly?: RangeBand | null;
  monthly?: RangeBand | null;
  trade_plan?: TradePlan | null;
  refreshing?: boolean;
  error: string | null;
  error_ts: number | null;
}

export type JournalOutcome = "PENDING" | "NOT_TRIGGERED" | "TARGET_HIT" | "STOP_HIT" | "OPEN_AT_CLOSE" | "NO_TRADE";

export interface JournalEntry {
  id: number;
  session_date: string; // the completed session the plan's numbers were built from
  trade_date: string; // the trading session the plan was meant to be acted on
  option_type: "CE" | "PE" | null;
  strike: number | null;
  entry_trigger: number | null;
  target: number | null;
  target_points: number | null;
  combined_signal: string;
  note: string | null;
  outcome: JournalOutcome;
  realized_points: number | null;
  created_ts: number;
  resolved_ts: number | null;
}

export interface JournalEntriesResponse {
  entries: JournalEntry[];
}

export interface HlcRefreshResponse {
  started: boolean;
  reason?: string;
}

export type ChartInstrument = "spot" | "ce" | "pe";
export type ChartInterval = "1" | "5" | "15" | "day";

export interface Candle {
  ts: number;
  open: number;
  high: number;
  low: number;
  close: number;
  volume: number;
  oi: number | null;
}

export interface CandlesResponse {
  candles: Candle[];
}

export interface OiHistoryPoint {
  ts: number;
  ce_oi: number;
  pe_oi: number;
}

export interface OiHistoryResponse {
  points: OiHistoryPoint[];
}

export interface SwingPoint {
  ts: number;
  price: number;
  kind: "high" | "low";
  label: string; // HH | HL | LH | LL | H | L
}

export interface StructureEvent {
  kind: "BOS" | "CHOCH";
  direction: "BULLISH" | "BEARISH";
  ts: number;
  price: number;
  level: number;
}

export type DayType = "NON_TREND" | "NORMAL_VARIATION" | "TREND" | "NEUTRAL" | "FORMING" | "INSUFFICIENT_DATA";

export interface DayTypeResult {
  day_type: DayType;
  ib_high: number | null;
  ib_low: number | null;
  session_high: number | null;
  session_low: number | null;
}

export interface TimeframeStructure {
  label: string;
  trend: "BULLISH" | "BEARISH" | "UNCLEAR" | "INSUFFICIENT_DATA";
  bars: number;
  swings: number;
  enough_data: boolean;
  note: string;
}

export interface MarketStructurePayload {
  swings: SwingPoint[];
  structure_trend: "BULLISH" | "BEARISH" | "UNCLEAR";
  last_bos: StructureEvent | null;
  last_choch: StructureEvent | null;
  day_type: DayTypeResult;
  chop: number | null;
  prev_day_high: number | null;
  prev_day_low: number | null;
  prev_week_high: number | null;
  prev_week_low: number | null;
  timeframes: TimeframeStructure[];
}

export interface ZoneFactor {
  label: string;
  points: number;
}

export type ZoneClassification = "INSTITUTIONAL" | "STRONG" | "MODERATE" | "WEAK" | "IGNORE";

export interface Zone {
  low: number;
  high: number;
  kind: "SUPPORT" | "RESISTANCE";
  score: number;
  classification: ZoneClassification;
  factors: ZoneFactor[];
}

export interface OiWall {
  strike: number;
  option_type: "CE" | "PE";
  oi: number;
  oi_change: number;
  oi_change_pct: number | null;
  volume: number;
  freshness: "FRESH" | "STALE";
  unwinding_warning: boolean;
}

export interface SupportResistancePayload {
  zones: Zone[];
  call_walls: OiWall[];
  put_walls: OiWall[];
}

export type RiskWindow = "OPENING" | "MIDDAY" | "CLOSING";

export interface RiskAssessment {
  window: RiskWindow;
  is_expiry_day: boolean;
  size_multiplier: number;
  avoid_new_entries: boolean;
  reasons: string[];
}

export interface PositionSizeRow {
  stop_distance_points: number;
  lots: number;
  quantity: number;
  risk_amount: number;
}

export interface PositionSizing {
  capital: number;
  max_risk_per_trade: number;
  lot_size: number;
  risk_assessment: RiskAssessment;
  table: PositionSizeRow[];
  estimated: PositionSizeRow | null;
}

export interface DailyRiskStatus {
  as_of_trade_date: string | null;
  realized_points: number | null;
  realized_amount: number | null;
  max_daily_loss: number;
  remaining_budget: number;
  locked: boolean;
}

export interface LegEstimate {
  option_type: "CE" | "PE";
  estimated_stop_distance: number;
  note: string;
  sizing: PositionSizeRow | null;
}

export interface RiskPayload {
  daily_risk: DailyRiskStatus;
  position_sizing: PositionSizing;
  leg_estimates: LegEstimate[];
}

export type BacktestRunStatus = "IDLE" | "RUNNING" | "DONE" | "FAILED";

export interface BacktestProgress {
  status: BacktestRunStatus;
  current: number;
  total: number;
  current_date: string | null;
}

export interface BacktestResult {
  start_date: string;
  end_date: string;
  status: string;
  created_ts: number;
  completed_ts: number | null;
  total_days: number | null;
  graded_trades: number | null;
  no_trade_days: number | null;
  not_triggered: number | null;
  net_points: number | null;
  win_rate: number | null;
  profit_factor: number | null;
  expectancy_points: number | null;
  avg_r: number | null;
  max_drawdown_points: number | null;
  largest_win: number | null;
  largest_loss: number | null;
  max_consecutive_losses: number | null;
  error: string | null;
}

export interface BacktestRunRow extends BacktestResult {
  id: number;
}

export interface BacktestStatusResponse {
  progress: BacktestProgress;
  result: BacktestResult | null;
  error: string | null;
}

export interface BacktestRunsResponse {
  runs: BacktestRunRow[];
}

export interface BacktestStartResponse {
  started: boolean;
  reason?: string;
}

export interface SettingsPayload {
  underlying: {
    symbol: string;
    segment: string;
    expiries_tracked: number;
    strike_window: number;
  };
  polling: {
    option_chain_interval_sec: number;
    historical_refresh_interval_sec: number;
  };
  historical: {
    intraday_interval_min: number;
    backfill_days: number;
  };
  hlc: {
    threshold_points: number;
  };
  trade_plan: {
    target_points_per_day: number;
    max_trades_per_day: number;
  };
  risk: {
    capital: number;
    max_risk_pct_per_trade: number;
    max_daily_loss_pct: number;
    lot_size: number;
  };
}

// ---- prediction engine (GET /api/prediction) ---------------------------
// Mirrors src/algooptionx/research/signals/{regime,setups,gex}.py. Every field the
// engine can show a number for also carries the sentence that explains it --
// the backend builds those strings deliberately so the UI never has to
// invent an interpretation of a score it did not compute.

export type PremiumStance = "BUY_FAVORED" | "SELL_FAVORED" | "NEUTRAL";
export type PremiumPricing = "RICH" | "FAIR" | "CHEAP" | "UNKNOWN";
export type StructureRegime = "TRENDING" | "RANGING" | "TRANSITIONAL" | "UNKNOWN";
export type GammaRegime = "POSITIVE_GAMMA" | "NEGATIVE_GAMMA" | "UNKNOWN";
export type SetupStatus = "ARMED" | "BLOCKED";
export type SetupGrade = "A" | "B" | "C" | "D";
export type SetupSide = "BUY_PREMIUM" | "SELL_PREMIUM";

export interface RegimeReason {
  factor: string;
  reading: string;
  points: number;
  explanation: string;
}

export interface RegimeSummary {
  as_of: string;
  atm_strike: number | null;
  straddle_price: number | null;
  days_to_expiry: number | null;
  implied_daily_move_points: number | null;
  realized_daily_move_points: number | null;
  realized_daily_range_points: number | null;
  realized_sample_days: number;
  move_edge_ratio: number | null;
  premium_pricing: PremiumPricing;
  structure_regime: StructureRegime;
  day_type: DayType;
  gamma_regime: GammaRegime;
  gamma_flip_strike: number | null;
  iv_percentile: number | null;
  adx: number | null;
  chop: number | null;
  session_window: string;
  is_expiry_day: boolean;
  premium_stance: PremiumStance;
  stance_score: number;
  stance_confidence: number;
  reasons: RegimeReason[];
  warnings: string[];
}

export interface GexSummary {
  net_gex: number;
  regime: GammaRegime;
  gamma_flip_strike: number | null;
  call_wall_strike: number | null;
  put_wall_strike: number | null;
  largest_gamma_strike: number | null;
  note: string;
}

export interface SetupGate {
  name: string;
  passed: boolean;
  detail: string;
}

export interface SetupEvidence {
  name: string;
  reading: string;
  earned: number;
  weight: number;
  detail: string;
}

export interface CalibrationRead {
  sample_size: number;
  wins: number;
  hit_rate: number | null;
  avg_points: number | null;
  note: string;
}

export interface SetupSignal {
  key: string;
  name: string;
  action: string;
  side: SetupSide;
  direction: "BULLISH" | "BEARISH" | "NEUTRAL";
  status: SetupStatus;
  gates: SetupGate[];
  blocked_by: string[];
  blocked_reasons: string[];
  evidence: SetupEvidence[];
  score: number;
  grade: SetupGrade;
  assumption: string;
  trigger: string;
  invalidation: string;
  strike: number | null;
  entry_reference: number | null;
  stop_reference: number | null;
  target_reference: number | null;
  expected_premium_points: number | null;
  readiness: Readiness;
  distance_points: number | null;
  readiness_note: string;
  historical: CalibrationRead | null;
  warnings: string[];
  narrative: string;
}

export type Readiness = "WAIT" | "NOW" | "MISSED" | "NA";

export interface KeyLevel {
  label: string;
  price: number;
  kind: "SPOT" | "RESISTANCE" | "SUPPORT" | "TRIGGER" | "STOP" | "TARGET" | "REFERENCE";
  detail: string;
  distance_points: number;
}

export interface ScenarioEvidence {
  factor: string;
  reading: string;
  weight: number;
  detail: string;
}

export interface Scenario {
  key: "UPSIDE" | "RANGE" | "DOWNSIDE";
  name: string;
  direction: "BULLISH" | "BEARISH" | "NEUTRAL";
  /** Share of today's measurable evidence, NOT a probability. */
  evidence_share: number;
  trigger_level: number | null;
  trigger: string;
  invalidation: string;
  target_level: number | null;
  what_it_means: string;
  evidence: ScenarioEvidence[];
  matching_setups: string[];
}

export interface ChecklistItem {
  name: string;
  passed: boolean;
  detail: string;
}

export interface ScenarioSet {
  spot_price: number;
  scenarios: Scenario[];
  checklist: ChecklistItem[];
  checklist_passed: number;
  checklist_total: number;
  verdict: "TRADE" | "WAIT" | "STAND_DOWN";
  verdict_note: string;
  caveat: string;
}

export interface PredictionPayload {
  as_of: string;
  spot_price: number | null;
  unavailable: string | null;
  regime: RegimeSummary | null;
  structure: MarketStructurePayload | null;
  gex: GexSummary | null;
  risk: {
    window: string;
    is_expiry_day: boolean;
    size_multiplier: number;
    avoid_new_entries: boolean;
    reasons: string[];
  } | null;
  signals: SetupSignal[];
  best: SetupSignal | null;
  key_levels: KeyLevel[];
  scenarios: ScenarioSet | null;
}

// ---- learning ledger (GET /api/learning) -------------------------------

export interface SliceStats {
  label: string;
  sample: number;
  wins: number;
  losses: number;
  hit_rate: number | null;
  avg_points: number | null;
}

export interface SetupRecord {
  setup_key: string;
  armed: number;
  triggered: number;
  wins: number;
  losses: number;
  flats: number;
  not_triggered: number;
  hit_rate: number | null;
  avg_points: number | null;
  best_points: number | null;
  worst_points: number | null;
  avg_mae: number | null;
  reliable: boolean;
  by_regime: SliceStats[];
  by_day_type: SliceStats[];
  by_pricing: SliceStats[];
  verdict: string;
}

export interface RegimeCheck {
  sessions: number;
  by_regime: SliceStats[];
  trend_avg_range: number | null;
  range_avg_range: number | null;
  separation_points: number | null;
  verdict: string;
}

export interface GuidePayload {
  markdown: string;
}

export interface AnalyticsByRegimePayload {
  by_regime: SliceStats[];
}

export interface LearningPayload {
  setups: SetupRecord[];
  regime_check: RegimeCheck;
}
