import { fetchLiveState } from "../api";
import type { LiveStatePayload } from "../types";
import { type PollingHook, usePolling } from "./usePolling";

// Matches the backend's option-chain poll cadence (config/research.toml:
// polling.option_chain_interval_sec, default 3.5s) -- polling faster than the
// source updates would just be wasted requests.
const POLL_INTERVAL_MS = 3500;

export function useLiveState(): PollingHook<LiveStatePayload> {
  return usePolling(fetchLiveState, POLL_INTERVAL_MS);
}
