import type {
  BacktestRunsResponse,
  BacktestStartResponse,
  BacktestStatusResponse,
  CandlesResponse,
  ChartInstrument,
  ChartInterval,
  HealthPayload,
  HlcRefreshResponse,
  HlcStatePayload,
  JournalEntriesResponse,
  LiveStatePayload,
  MarketStructurePayload,
  AnalyticsByRegimePayload,
  GuidePayload,
  LearningPayload,
  OiHistoryResponse,
  PredictionPayload,
  RiskPayload,
  SettingsPayload,
  SupportResistancePayload,
} from "./types";

export class StartingUpError extends Error {}

async function errorDetail(res: Response): Promise<string> {
  try {
    const body = await res.json();
    if (body && typeof body.detail === "string") return body.detail;
  } catch {
    // response wasn't JSON -- fall through to the generic message
  }
  // Status codes are meaningless to a reader who is not a developer, so the
  // common ones get a sentence. The number is kept on the end for anything
  // that does need diagnosing from a screenshot.
  if (res.status === 404) return "That data is not available in this version of the app.";
  if (res.status === 429) return "The broker is rate-limiting requests. This clears on its own in a few seconds.";
  if (res.status >= 500) return `The analyzer hit an error working that out (${res.status}). Check the log file if it keeps happening.`;
  return `Request failed (${res.status}).`;
}

async function getJson<T>(url: string): Promise<T> {
  let res: Response;
  try {
    res = await fetch(url);
  } catch {
    // The fetch itself failed -- the server is down, or the machine went to
    // sleep. The browser's own message here ("Failed to fetch") tells a
    // non-technical reader nothing.
    throw new Error("Could not reach the analyzer. Check that the app window is still running.");
  }

  if (!res.ok) {
    throw new Error(await errorDetail(res));
  }

  try {
    return (await res.json()) as T;
  } catch {
    // A 200 that is not JSON means the request fell through to the
    // single-page app's catch-all and came back as index.html -- i.e. that
    // endpoint does not exist on this build. Before this, the browser's raw
    // parser message ("Unexpected token '<', \"<!doctype \"... is not valid
    // JSON") was rendered verbatim inside the chart panes.
    throw new Error("The analyzer sent back something unexpected. Restarting the app usually clears this.");
  }
}

async function getPollableJson<T>(url: string, notReadyMessage: string): Promise<T> {
  const res = await fetch(url);
  if (res.status === 503) {
    throw new StartingUpError(notReadyMessage);
  }
  if (!res.ok) {
    throw new Error(`${url} -> HTTP ${res.status}`);
  }
  return (await res.json()) as T;
}

export function fetchHealth(): Promise<HealthPayload> {
  return getJson<HealthPayload>("/api/health");
}

export function fetchLiveState(): Promise<LiveStatePayload> {
  return getPollableJson<LiveStatePayload>("/api/live/state", "First poll cycle not complete yet.");
}

export function fetchHlcState(): Promise<HlcStatePayload> {
  return getPollableJson<HlcStatePayload>("/api/hlc/state", "First HLC cycle not complete yet.");
}

export async function triggerHlcRefresh(): Promise<HlcRefreshResponse> {
  const res = await fetch("/api/hlc/refresh", { method: "POST" });
  if (!res.ok) {
    throw new Error(await errorDetail(res));
  }
  return (await res.json()) as HlcRefreshResponse;
}

export async function fetchCandles(instrument: ChartInstrument, interval: ChartInterval): Promise<CandlesResponse> {
  return getJson<CandlesResponse>(`/api/chart/candles?instrument=${instrument}&interval=${interval}`);
}

export function fetchJournalEntries(limit = 30): Promise<JournalEntriesResponse> {
  return getJson<JournalEntriesResponse>(`/api/journal/entries?limit=${limit}`);
}

export function fetchOiHistory(): Promise<OiHistoryResponse> {
  return getJson<OiHistoryResponse>("/api/live/oi-history");
}

export function fetchSettings(): Promise<SettingsPayload> {
  return getJson<SettingsPayload>("/api/settings");
}

export function fetchMarketStructure(): Promise<MarketStructurePayload> {
  return getJson<MarketStructurePayload>("/api/market-structure");
}

export function fetchSupportResistance(): Promise<SupportResistancePayload> {
  return getJson<SupportResistancePayload>("/api/support-resistance");
}

export function fetchRisk(): Promise<RiskPayload> {
  return getJson<RiskPayload>("/api/risk");
}

export async function startBacktest(startDate: string, endDate: string): Promise<BacktestStartResponse> {
  const res = await fetch(
    `/api/backtest/run?start_date=${encodeURIComponent(startDate)}&end_date=${encodeURIComponent(endDate)}`,
    { method: "POST" },
  );
  if (!res.ok) {
    throw new Error(await errorDetail(res));
  }
  return (await res.json()) as BacktestStartResponse;
}

export function fetchBacktestStatus(): Promise<BacktestStatusResponse> {
  return getJson<BacktestStatusResponse>("/api/backtest/status");
}

export function fetchBacktestRuns(limit = 10): Promise<BacktestRunsResponse> {
  return getJson<BacktestRunsResponse>(`/api/backtest/runs?limit=${limit}`);
}

export function fetchPrediction(): Promise<PredictionPayload> {
  return getJson<PredictionPayload>("/api/prediction");
}

export function fetchGuide(): Promise<GuidePayload> {
  return getJson<GuidePayload>("/api/guide");
}

export function fetchAnalyticsByRegime(): Promise<AnalyticsByRegimePayload> {
  return getJson<AnalyticsByRegimePayload>("/api/analytics/by-regime");
}

export function fetchLearning(): Promise<LearningPayload> {
  return getJson<LearningPayload>("/api/learning");
}
