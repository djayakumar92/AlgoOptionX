import { useEffect, useState } from "react";
import type { ChartAnnotation } from "./types";

export type ChartVisibility = { volume: boolean; ema: boolean; vwap: boolean };
type Settings = {
  timeframe: "5" | "30";
  visibility: ChartVisibility;
  annotations: ChartAnnotation[];
};
type StoredState = { sessionId: string | undefined; settings: Settings };
const prefix = "algooptionx.demo.chart.v1:";
const defaults = (): Settings => ({
  timeframe: "5",
  visibility: { volume: true, ema: true, vwap: true },
  annotations: [],
});
const object = (value: unknown): value is Record<string, unknown> =>
  !!value && typeof value === "object" && !Array.isArray(value);
const positive = (value: unknown): value is number =>
  typeof value === "number" && Number.isFinite(value) && value > 0;
const timestamp = (value: unknown): value is string =>
  typeof value === "string" && value.length <= 40 &&
  /^\d{4}-\d{2}-\d{2}T/.test(value) && Number.isFinite(Date.parse(value));

function decode(raw: string | null, sessionId: string): Settings {
  if (!raw || raw.length > 32768) return defaults();
  const data: unknown = JSON.parse(raw);
  if (!object(data) || data.version !== 1 || data.sessionId !== sessionId ||
      !object(data.settings)) return defaults();
  const settings = data.settings;
  if ((settings.timeframe !== "5" && settings.timeframe !== "30") ||
      !object(settings.visibility) ||
      typeof settings.visibility.volume !== "boolean" ||
      typeof settings.visibility.ema !== "boolean" ||
      typeof settings.visibility.vwap !== "boolean" ||
      !Array.isArray(settings.annotations) || settings.annotations.length > 32) return defaults();
  const annotations: ChartAnnotation[] = [];
  const identities = new Set<string>();
  for (const item of settings.annotations) {
    if (!object(item) || typeof item.id !== "string" || !item.id || item.id.length > 80 ||
        identities.has(item.id)) return defaults();
    identities.add(item.id);
    if (item.kind === "horizontal" && positive(item.price)) {
      annotations.push({ id: item.id, kind: "horizontal", price: item.price });
    } else if (item.kind === "trend" && positive(item.startPrice) && positive(item.endPrice) &&
        timestamp(item.startTime) && timestamp(item.endTime) &&
        Math.floor(Date.parse(item.startTime) / 1000) !== Math.floor(Date.parse(item.endTime) / 1000)) {
      annotations.push({ id: item.id, kind: "trend", startTime: item.startTime,
        endTime: item.endTime, startPrice: item.startPrice, endPrice: item.endPrice });
    } else return defaults();
  }
  return {
    timeframe: settings.timeframe,
    visibility: { volume: settings.visibility.volume as boolean,
      ema: settings.visibility.ema as boolean, vwap: settings.visibility.vwap as boolean },
    annotations,
  };
}

export function useChartWorkspace(sessionId: string | undefined) {
  const [stored, setStored] = useState<StoredState>({ sessionId: undefined, settings: defaults() });
  const [temporary, setTemporary] = useState(false);
  // Hydrate first. A session mismatch is never written back, preventing the
  // previous session's drawings from being saved under a new session identity.
  useEffect(() => {
    if (!sessionId) return;
    let settings = defaults();
    try { settings = decode(localStorage.getItem(prefix + sessionId), sessionId); }
    catch { /* Corrupt or unavailable storage never blocks chart use. */ }
    setStored({ sessionId, settings });
  }, [sessionId]);
  useEffect(() => {
    if (!sessionId || stored.sessionId !== sessionId) return;
    try {
      localStorage.setItem(prefix + sessionId, JSON.stringify({ version: 1, sessionId, settings: stored.settings }));
      setTemporary(false);
    } catch { setTemporary(true); }
  }, [sessionId, stored]);
  const settings = stored.sessionId === sessionId ? stored.settings : defaults();
  function update(patch: Partial<Settings>) {
    if (!sessionId) return;
    setStored(current => ({ sessionId, settings: {
      ...(current.sessionId === sessionId ? current.settings : defaults()), ...patch,
    } }));
  }
  return {
    ...settings,
    setTimeframe: (timeframe: Settings["timeframe"]) => update({ timeframe }),
    setAnnotations: (annotations: ChartAnnotation[]) => update({ annotations }),
    setVisibility: (visibility: ChartVisibility) => update({ visibility }),
    persistenceNotice: temporary
      ? "Chart settings are temporary because browser storage is unavailable."
      : stored.sessionId !== sessionId
        ? "Loading saved chart settings…"
        : "Chart settings and drawings are saved in this browser for this demo session.",
  };
}
