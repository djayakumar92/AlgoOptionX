import { useEffect, useRef, useState } from "react";
import { StartingUpError } from "../api";

export interface PollingHook<T> {
  data: T | null;
  startingUp: boolean;
  fetchError: string | null;
}

export function usePolling<T>(fetchFn: () => Promise<T>, intervalMs: number): PollingHook<T> {
  const [data, setData] = useState<T | null>(null);
  const [startingUp, setStartingUp] = useState(true);
  const [fetchError, setFetchError] = useState<string | null>(null);
  const cancelled = useRef(false);

  useEffect(() => {
    cancelled.current = false;

    async function poll() {
      try {
        const payload = await fetchFn();
        if (cancelled.current) return;
        setData(payload);
        setStartingUp(false);
        setFetchError(null);
      } catch (err) {
        if (cancelled.current) return;
        if (err instanceof StartingUpError) {
          setStartingUp(true);
        } else {
          setFetchError(err instanceof Error ? err.message : String(err));
        }
      }
    }

    poll();
    const id = setInterval(poll, intervalMs);
    return () => {
      cancelled.current = true;
      clearInterval(id);
    };
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [intervalMs]);

  return { data, startingUp, fetchError };
}
