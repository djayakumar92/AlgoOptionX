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
export const money = (paise: number, decimals = 2) =>
  new Intl.NumberFormat("en-IN", {
    style: "currency",
    currency: "INR",
    maximumFractionDigits: decimals,
    minimumFractionDigits: decimals,
  }).format(paise / 100);
export const number = (value: number) =>
  new Intl.NumberFormat("en-IN", { maximumFractionDigits: 2 }).format(value);
export const contractName = (id: string) => {
  const parts = id.split("-");
  return `NIFTY ${parts[2]} ${parts[3]}`;
};
export async function api<T>(path: string, body?: unknown): Promise<T> {
  const response = await fetch(
    `/api/${path}`,
    body === undefined
      ? undefined
      : {
          method: "POST",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify(body),
        },
  );
  const payload = await response.json();
  if (!response.ok)
    throw new Error(
      typeof payload.detail === "string"
        ? payload.detail
        : "The request could not be completed. Check your inputs.",
    );
  return payload;
}
export function command(action: string, fields: object = {}) {
  return api("commands", { key: crypto.randomUUID(), action, ...fields });
}
