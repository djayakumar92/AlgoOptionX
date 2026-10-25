import { fetchSupportResistance } from "../api";
import type { SupportResistancePayload } from "../types";
import { type PollingHook, usePolling } from "./usePolling";

// Same cadence as market structure -- depends on the same 60s-refreshed
// candles plus the live chain poll, no point recomputing faster than either updates.
const POLL_INTERVAL_MS = 60_000;

export function useSupportResistance(): PollingHook<SupportResistancePayload> {
  return usePolling(fetchSupportResistance, POLL_INTERVAL_MS);
}
