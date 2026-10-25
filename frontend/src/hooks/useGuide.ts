import { fetchGuide } from "../api";
import type { GuidePayload } from "../types";
import { type PollingHook, usePolling } from "./usePolling";

// The guide is a file on disk that changes only when it is edited. Polled
// slowly rather than fetched once so an edit shows up without restarting the
// app -- useful while the document is still being revised.
const POLL_INTERVAL_MS = 300_000;

export function useGuide(): PollingHook<GuidePayload> {
  return usePolling(fetchGuide, POLL_INTERVAL_MS);
}
