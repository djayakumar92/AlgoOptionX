import { useEffect, useState } from "react";
import { fetchHealth } from "../api";
import type { HealthPayload } from "../types";

export function useHealth(): HealthPayload | null {
  const [health, setHealth] = useState<HealthPayload | null>(null);

  useEffect(() => {
    let cancelled = false;
    fetchHealth()
      .then((h) => {
        if (!cancelled) setHealth(h);
      })
      .catch(() => {
        // Startup race before the lifespan finishes; the live-state poller
        // will keep retrying and surface a proper error if it's persistent.
      });
    return () => {
      cancelled = true;
    };
  }, []);

  return health;
}
