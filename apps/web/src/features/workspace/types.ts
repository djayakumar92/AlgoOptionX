export type Contract = {
  id: string;
  strike: number;
  right: string;
  bid: number;
  ask: number;
  mark: number;
  oi: number;
  volume: number;
  iv: number;
  lot_size: number;
};
export type Position = {
  id: string;
  instrument: string;
  quantity: number;
  entry: number;
  stop: number;
  target: number;
  mark: number;
  unrealized: number;
  opened_tick: number;
};
export type AuditEvent = {
  seq: number;
  tick: number;
  kind: string;
  hash: string;
  previous_hash: string;
  payload: {
    message?: string;
    instrument?: string;
    price?: number;
    quantity?: number;
    pnl?: number;
    fee?: number;
    reason?: string;
    origin?: string;
  };
};
export type Workspace = {
  market: {
    tick: number;
    spot: number;
    time: string;
    contracts: Contract[];
    seed: number;
    source: string;
  };
  history: { tick: number; spot: number }[];
  account: {
    id: string;
    capital: number;
    cash: number;
    equity: number;
    pnl: number;
    realized: number;
    unrealized: number;
    fees: number;
    exposure: number;
    running: boolean;
    autonomous: boolean;
    killed: boolean;
  };
  positions: Position[];
  events: AuditEvent[];
  worker_error: string | null;
  decision: {
    action: string;
    change: number;
    explanation: string;
    version: string;
  };
  risk: {
    max_positions: number;
    max_exposure: number;
    max_trade_risk: number;
    max_daily_loss: number;
    fee_per_fill: number;
    lot_size: number;
  };
};
export type ReplayResult = {
  bars: number;
  pnl: number;
  fees: number;
  trades: number;
  wins: number;
  max_drawdown: number;
  curve: { tick: number; equity: number }[];
  disclaimer: string;
};
