import { fetchOiHistory } from "../api";
import type { OiHistoryResponse } from "../types";
import { type PollingHook, usePolling } from "./usePolling";

// The chart buckets to 5 minutes server-side, so there's nothing new to show
// on a 3.5s cadence like the rest of the Live page -- 30s keeps the chart
// current without re-scanning the day's snapshot history too often.
const POLL_INTERVAL_MS = 30_000;

export function useOiHistory(): PollingHook<OiHistoryResponse> {
  return usePolling(fetchOiHistory, POLL_INTERVAL_MS);
}
