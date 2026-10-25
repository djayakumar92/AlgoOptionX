import { useEffect, useState } from "react";
import { fetchJournalEntries } from "../api";
import type { JournalEntry } from "../types";

interface JournalEntriesHook {
  entries: JournalEntry[];
  loading: boolean;
  error: string | null;
}

// One-shot fetch on mount -- entries only change once per session rollover
// (see hlc_worker.py), so there's nothing to gain from polling this like the
// Live page does.
export function useJournalEntries(limit = 30): JournalEntriesHook {
  const [entries, setEntries] = useState<JournalEntry[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    let cancelled = false;
    fetchJournalEntries(limit)
      .then((res) => {
        if (cancelled) return;
        setEntries(res.entries);
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
  }, [limit]);

  return { entries, loading, error };
}
