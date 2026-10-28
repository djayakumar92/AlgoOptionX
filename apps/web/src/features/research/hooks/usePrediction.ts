import { fetchPrediction } from "../api";
import type { PredictionPayload } from "../types";
import { type PollingHook, usePolling } from "./usePolling";

// The engine's inputs move on 5-minute-candle time, and the ledger is written
// by the backend worker on its own schedule -- polling faster than this would
// re-render the same read against the same candles.
const POLL_INTERVAL_MS = 30_000;

export function usePrediction(): PollingHook<PredictionPayload> {
  return usePolling(fetchPrediction, POLL_INTERVAL_MS);
}
