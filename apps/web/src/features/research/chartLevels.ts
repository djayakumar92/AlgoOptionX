import type { ChartLevel } from "./components/CandleChart";
import type { ChartInstrument, HlcStatePayload } from "./types";

const OWN_COLOR = "#1e40af";
const OPPONENT_COLOR = "#7c3aed";
const ENTRY_COLOR = "#0891b2";
const TARGET_COLOR = "#16803c";

export function levelsFor(instrument: ChartInstrument, data: HlcStatePayload | null): ChartLevel[] {
  if (!data) return [];

  if (instrument === "spot") {
    const levels: ChartLevel[] = [];
    if (data.max_resistance !== undefined) levels.push({ price: data.max_resistance, label: "Max Resistance", color: "#c62828" });
    if (data.min_resistance !== undefined) levels.push({ price: data.min_resistance, label: "Min Resistance", color: "#e57373" });
    if (data.min_support !== undefined) levels.push({ price: data.min_support, label: "Min Support", color: "#81c784" });
    if (data.max_support !== undefined) levels.push({ price: data.max_support, label: "Max Support", color: "#16803c" });
    if (data.atm_strike !== undefined) levels.push({ price: data.atm_strike, label: "ATM", color: "#888888" });
    return levels;
  }

  if (!data.ce || !data.pe) return [];

  const own = instrument === "ce" ? data.ce : data.pe;
  const opponent = instrument === "ce" ? data.pe : data.ce;
  const ownLabel = instrument === "ce" ? "CE" : "PE";
  const opponentLabel = instrument === "ce" ? "PE" : "CE";
  const leg = data.trade_plan?.legs.find((l) => l.option_type === (instrument === "ce" ? "CE" : "PE"));

  return [
    { price: own.high, label: `${ownLabel} High`, color: OWN_COLOR },
    { price: own.close, label: `${ownLabel} Close`, color: OWN_COLOR },
    { price: own.low, label: `${ownLabel} Low`, color: OWN_COLOR },
    { price: opponent.high, label: `${opponentLabel} High (opp.)`, color: OPPONENT_COLOR },
    { price: opponent.close, label: `${opponentLabel} Close (opp.)`, color: OPPONENT_COLOR },
    { price: opponent.low, label: `${opponentLabel} Low (opp.)`, color: OPPONENT_COLOR },
    ...(leg
      ? [
          { price: leg.entry_trigger, label: "Plan: Sell Entry", color: ENTRY_COLOR },
          { price: leg.target, label: "Plan: Target", color: TARGET_COLOR },
        ]
      : []),
  ];
}
