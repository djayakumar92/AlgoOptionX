import { useEffect, useState } from "react";
import { fetchSettings } from "../api";
import type { SettingsPayload } from "../types";

// One-shot fetch -- config only changes if the app is restarted with a
// different config/research.toml, same reasoning as useJournalEntries.
export function useSettings(): { settings: SettingsPayload | null; error: string | null } {
  const [settings, setSettings] = useState<SettingsPayload | null>(null);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    let cancelled = false;
    fetchSettings()
      .then((s) => {
        if (!cancelled) setSettings(s);
      })
      .catch((err) => {
        if (!cancelled) setError(err instanceof Error ? err.message : String(err));
      });
    return () => {
      cancelled = true;
    };
  }, []);

  return { settings, error };
}
