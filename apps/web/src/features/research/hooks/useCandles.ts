import { useEffect, useState } from "react";
import { fetchCandles } from "../api";
import type { Candle, ChartInstrument, ChartInterval } from "../types";

interface CandlesHook {
  candles: Candle[];
  loading: boolean;
  error: string | null;
}

// One-shot fetch per instrument/interval selection -- not polled. The user
// explicitly picks a timeframe; there's no need to keep re-fetching a chart
// they're not actively watching update tick-by-tick (that's what the Live page
// is for). Re-fetches whenever instrument or interval changes.
export function useCandles(instrument: ChartInstrument, interval: ChartInterval): CandlesHook {
  const [candles, setCandles] = useState<Candle[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    let cancelled = false;
    setLoading(true);
    setError(null);

    fetchCandles(instrument, interval)
      .then((res) => {
        if (cancelled) return;
        setCandles(res.candles);
        setLoading(false);
      })
      .catch((err) => {
        if (cancelled) return;
        setError(err instanceof Error ? err.message : String(err));
        setLoading(false);
      });

    return () => {
      cancelled = true;
    };
  }, [instrument, interval]);

  return { candles, loading, error };
}
