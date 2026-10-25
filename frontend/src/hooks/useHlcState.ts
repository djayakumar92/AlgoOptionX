import { useCallback, useEffect, useRef, useState } from "react";
import { StartingUpError, fetchHlcState, triggerHlcRefresh } from "../api";
import type { HlcStatePayload } from "../types";

// The HLC read only changes once per trading-session close -- there's no
// background DhanHQ polling for it (see hlc_worker.py). This just polls our
// own local /api/hlc/state (cheap, no DhanHQ traffic): fast while a fetch is
// actively running so the "Fetch Latest" button feels responsive, slow
// otherwise since nothing changes without a manual click.
const ACTIVE_POLL_MS = 3000;
const IDLE_POLL_MS = 60_000;

interface HlcStateHook {
  data: HlcStatePayload | null;
  startingUp: boolean;
  fetchError: string | null;
  refresh: () => void;
  refreshRequestError: string | null;
}

export function useHlcState(): HlcStateHook {
  const [data, setData] = useState<HlcStatePayload | null>(null);
  const [startingUp, setStartingUp] = useState(true);
  const [fetchError, setFetchError] = useState<string | null>(null);
  const [refreshRequestError, setRefreshRequestError] = useState<string | null>(null);
  const pollNowRef = useRef<() => void>(() => {});

  useEffect(() => {
    let cancelled = false;
    let timeoutId: ReturnType<typeof setTimeout> | null = null;

    function scheduleNext(delayMs: number) {
      if (timeoutId) clearTimeout(timeoutId);
      timeoutId = setTimeout(poll, delayMs);
    }

    async function poll() {
      try {
        const payload = await fetchHlcState();
        if (cancelled) return;
        setData(payload);
        setStartingUp(false);
        setFetchError(null);
        scheduleNext(payload.refreshing ? ACTIVE_POLL_MS : IDLE_POLL_MS);
      } catch (err) {
        if (cancelled) return;
        if (err instanceof StartingUpError) {
          setStartingUp(true);
          scheduleNext(ACTIVE_POLL_MS);
        } else {
          setFetchError(err instanceof Error ? err.message : String(err));
          scheduleNext(IDLE_POLL_MS);
        }
      }
    }

    pollNowRef.current = () => scheduleNext(0);
    poll();

    return () => {
      cancelled = true;
      if (timeoutId) clearTimeout(timeoutId);
    };
  }, []);

  const refresh = useCallback(() => {
    setRefreshRequestError(null);
    triggerHlcRefresh()
      .then((res) => {
        if (!res.started) {
          setRefreshRequestError(res.reason ?? "Refresh already in progress.");
        }
        pollNowRef.current();
      })
      .catch((err) => {
        setRefreshRequestError(err instanceof Error ? err.message : String(err));
      });
  }, []);

  return { data, startingUp, fetchError, refresh, refreshRequestError };
}
