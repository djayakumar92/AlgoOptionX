import { useCallback, useEffect, useRef, useState } from "react";
import { fetchBacktestStatus, startBacktest } from "../api";
import type { BacktestStatusResponse } from "../types";

// Same fast-while-active/slow-while-idle pattern as useHlcState -- this only
// polls our own local /api/backtest/status (a cheap DB/memory read), never
// DhanHQ directly, so polling fast while a run is in progress is free.
const ACTIVE_POLL_MS = 2000;
const IDLE_POLL_MS = 30_000;

interface BacktestHook {
  status: BacktestStatusResponse | null;
  fetchError: string | null;
  run: (startDate: string, endDate: string) => void;
  runError: string | null;
  running: boolean;
}

export function useBacktest(): BacktestHook {
  const [status, setStatus] = useState<BacktestStatusResponse | null>(null);
  const [fetchError, setFetchError] = useState<string | null>(null);
  const [runError, setRunError] = useState<string | null>(null);
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
        const payload = await fetchBacktestStatus();
        if (cancelled) return;
        setStatus(payload);
        setFetchError(null);
        scheduleNext(payload.progress.status === "RUNNING" ? ACTIVE_POLL_MS : IDLE_POLL_MS);
      } catch (err) {
        if (cancelled) return;
        setFetchError(err instanceof Error ? err.message : String(err));
        scheduleNext(IDLE_POLL_MS);
      }
    }

    pollNowRef.current = () => scheduleNext(0);
    poll();

    return () => {
      cancelled = true;
      if (timeoutId) clearTimeout(timeoutId);
    };
  }, []);

  const run = useCallback((startDate: string, endDate: string) => {
    setRunError(null);
    startBacktest(startDate, endDate)
      .then((res) => {
        if (!res.started) {
          setRunError(res.reason ?? "A run is already in progress.");
        }
        pollNowRef.current();
      })
      .catch((err) => {
        setRunError(err instanceof Error ? err.message : String(err));
      });
  }, []);

  return {
    status,
    fetchError,
    run,
    runError,
    running: status?.progress.status === "RUNNING",
  };
}
