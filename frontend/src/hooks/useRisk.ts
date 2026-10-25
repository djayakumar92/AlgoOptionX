import { fetchRisk } from "../api";
import type { RiskPayload } from "../types";
import { type PollingHook, usePolling } from "./usePolling";

// Session-window classification can change minute to minute near a
// boundary (e.g. crossing into the closing-risk window) -- 60s keeps this
// reasonably current without polling harder than anything else on this page.
const POLL_INTERVAL_MS = 60_000;

export function useRisk(): PollingHook<RiskPayload> {
  return usePolling(fetchRisk, POLL_INTERVAL_MS);
}
