import { fetchLearning } from "../api";
import type { LearningPayload } from "../types";
import { type PollingHook, usePolling } from "./usePolling";

// The record only changes when a session is graded, which happens once a day
// after the close. A slow poll is plenty.
const POLL_INTERVAL_MS = 120_000;

export function useLearning(): PollingHook<LearningPayload> {
  return usePolling(fetchLearning, POLL_INTERVAL_MS);
}
