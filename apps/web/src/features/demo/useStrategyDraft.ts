import { useEffect, useState } from "react";
import type { SetStateAction } from "react";
import type { Draft } from "./types";

type SavedDraft = { draft: Draft; optionsExpiry: string };
type StoredDraft = SavedDraft & { sessionId: string | undefined; expirySignature: string };
const prefix = "algooptionx.demo.draft.v1:";
const defaults = (expiry: string): SavedDraft => ({
  draft: { strategy: "bull-put", lots: 1, expiry, strikes: [] }, optionsExpiry: expiry,
});
const object = (value: unknown): value is Record<string, unknown> =>
  !!value && typeof value === "object" && !Array.isArray(value);

function decode(raw: string | null, sessionId: string, expiries: string[]): SavedDraft {
  const fallback = defaults(expiries[0] || "");
  if (!raw || raw.length > 4096) return fallback;
  const value: unknown = JSON.parse(raw);
  if (!object(value) || value.version !== 1 || value.sessionId !== sessionId || !object(value.draft)) return fallback;
  const draft = value.draft;
  if ((draft.strategy !== "bull-put" && draft.strategy !== "bear-call" && draft.strategy !== "iron-condor") ||
      typeof draft.lots !== "number" || !Number.isInteger(draft.lots) || draft.lots < 1 || draft.lots > 5 ||
      typeof draft.expiry !== "string" || !expiries.includes(draft.expiry) ||
      !Array.isArray(draft.strikes) ||
      (draft.strikes.length !== 0 && draft.strikes.length !== (draft.strategy === "iron-condor" ? 4 : 2)) ||
      !draft.strikes.every(strike => typeof strike === "number" && Number.isFinite(strike) && strike > 0)) return fallback;
  return {
    draft: { strategy: draft.strategy, lots: draft.lots, expiry: draft.expiry, strikes: [...draft.strikes] },
    optionsExpiry: typeof value.optionsExpiry === "string" && expiries.includes(value.optionsExpiry)
      ? value.optionsExpiry : fallback.optionsExpiry,
  };
}

export function useStrategyDraft(sessionId: string | undefined, expiries: string[]) {
  const expirySignature = expiries.join("|");
  const defaultExpiry = expiries[0] || "";
  const [stored, setStored] = useState<StoredDraft>({ sessionId: undefined, expirySignature: "", ...defaults("") });
  const [temporary, setTemporary] = useState(false);
  useEffect(() => {
    if (!sessionId || !expirySignature) return;
    let saved = defaults(defaultExpiry);
    try { saved = decode(localStorage.getItem(prefix + sessionId), sessionId, expirySignature.split("|")); }
    catch { /* Invalid saved content never becomes an executable command. */ }
    setStored({ sessionId, expirySignature, ...saved });
  }, [sessionId, expirySignature, defaultExpiry]);
  const ready = !!sessionId && !!expirySignature && stored.sessionId === sessionId && stored.expirySignature === expirySignature;
  useEffect(() => {
    if (!ready) return;
    try {
      // Only authoring inputs are persisted. No preview, quote token, risk result,
      // confirmation, idempotency key, credential or economic state is stored.
      localStorage.setItem(prefix + sessionId, JSON.stringify({ version: 1, sessionId,
        draft: stored.draft, optionsExpiry: stored.optionsExpiry }));
      setTemporary(false);
    } catch { setTemporary(true); }
  }, [ready, sessionId, stored]);
  const selected = ready ? stored : defaults(defaultExpiry);
  function setDraft(action: SetStateAction<Draft>) {
    if (!sessionId || !expirySignature) return;
    setStored(current => {
      const previous = current.sessionId === sessionId && current.expirySignature === expirySignature
        ? current : { sessionId, expirySignature, ...defaults(defaultExpiry) };
      return { ...previous, draft: typeof action === "function" ? action(previous.draft) : action };
    });
  }
  function setExpiry(optionsExpiry: string) {
    if (!sessionId || !expiries.includes(optionsExpiry)) return;
    setStored(current => ({
      ...(current.sessionId === sessionId && current.expirySignature === expirySignature
        ? current : { sessionId, expirySignature, ...defaults(defaultExpiry) }), optionsExpiry,
    }));
  }
  return {
    draft: selected.draft, setDraft, expiry: selected.optionsExpiry, setExpiry, draftReady: ready,
    resetDraft: () => setDraft(defaults(defaultExpiry).draft),
    draftNotice: !ready ? "Loading strategy draft…" : temporary
      ? "Draft changes are temporary because browser storage is unavailable."
      : "Draft saved in this browser for this demo session. Quotes and risk checks are refreshed; confirmation is never restored.",
  };
}
