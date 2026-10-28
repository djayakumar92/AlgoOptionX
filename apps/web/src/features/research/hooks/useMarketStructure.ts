import { fetchMarketStructure } from "../api";
import type { MarketStructurePayload } from "../types";
import { type PollingHook, usePolling } from "./usePolling";

// Candles behind this only refresh every config/research.toml
// polling.historical_refresh_interval_sec (60s default) -- polling faster
// than that would just recompute on the same data.
const POLL_INTERVAL_MS = 60_000;

export function useMarketStructure(): PollingHook<MarketStructurePayload> {
  return usePolling(fetchMarketStructure, POLL_INTERVAL_MS);
}
