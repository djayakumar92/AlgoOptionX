export type Experience = "guided" | "experienced";
const key = "algooptionx.start";
export function readExperience(): Experience { try { return localStorage.getItem(key) === "experienced" ? "experienced" : "guided"; } catch { return "guided"; } }
export function saveExperience(value: Experience): boolean { try { localStorage.setItem(key, value); return true; } catch { return false; } }
