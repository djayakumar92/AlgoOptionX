import { fetchAnalyticsByRegime } from "../api";
import type { AnalyticsByRegimePayload } from "../types";
import { type PollingHook, usePolling } from "./usePolling";

// Journal outcomes only change when a session is graded, once a day.
const POLL_INTERVAL_MS = 120_000;

export function useAnalyticsByRegime(): PollingHook<AnalyticsByRegimePayload> {
  return usePolling(fetchAnalyticsByRegime, POLL_INTERVAL_MS);
}
