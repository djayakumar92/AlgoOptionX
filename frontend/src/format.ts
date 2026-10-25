export function fmtNum(value: number | null | undefined, digits = 2): string {
  if (value === null || value === undefined || Number.isNaN(value)) return "-";
  return value.toLocaleString(undefined, { maximumFractionDigits: digits });
}

export function fmtInt(value: number | null | undefined): string {
  if (value === null || value === undefined || Number.isNaN(value)) return "-";
  return value.toLocaleString();
}

export function fmtTime(epochSeconds: number | null | undefined): string {
  if (!epochSeconds) return "-";
  return new Date(epochSeconds * 1000).toLocaleTimeString();
}

export function fmtHM(epochSeconds: number): string {
  const d = new Date(epochSeconds * 1000);
  return d.toLocaleTimeString(undefined, { hour: "2-digit", minute: "2-digit" });
}
