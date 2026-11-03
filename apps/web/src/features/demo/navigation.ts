export const demoRoutes = [
  ["", "Command Center", "COMMAND"],
  ["market", "Market Intelligence", "MARKET"],
  ["options", "Options Intelligence", "OPTIONS"],
  ["strategy", "Strategy Builder", "STRATEGY"],
  ["paper", "Paper Trading", "PAPER"],
  ["risk", "Risk Monitor", "RISK"],
  ["journal", "Trading Journal", "JOURNAL"],
  ["research", "Research & Backtesting", "RESEARCH"],
  ["insights", "AI Insights & Governance", "INSIGHTS"],
] as const;
const key = "algooptionx.demo.last-route.v1";
export function isDemoRoute(value: unknown): value is string {
  return typeof value === "string" && demoRoutes.some(([slug]) => value === (slug ? `/demo/${slug}` : "/demo"));
}
export function readLastDemoRoute(): string | null {
  try { const value = localStorage.getItem(key); return isDemoRoute(value) ? value : null; }
  catch { return null; }
}
export function rememberDemoRoute(value: string) {
  if (!isDemoRoute(value)) return;
  try { localStorage.setItem(key, value); } catch { /* Navigation remains available without storage. */ }
}
export function demoRouteLabel(value: string) {
  return demoRoutes.find(([slug]) => value === (slug ? `/demo/${slug}` : "/demo"))?.[1] || "Demo";
}
