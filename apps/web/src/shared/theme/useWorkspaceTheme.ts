import { useEffect, useState } from "react";

export type ThemePreference = "light" | "dark" | "system";
const storageKey = "algooptionx.theme";

function readPreference(): ThemePreference {
  try {
    const saved = localStorage.getItem(storageKey);
    if (saved === "light" || saved === "dark" || saved === "system") return saved;
  } catch { /* Storage can be unavailable in private or restricted browsers. */ }
  return "dark";
}

export function useWorkspaceTheme() {
  const [theme, setTheme] = useState<ThemePreference>(readPreference);
  useEffect(() => {
    const media = window.matchMedia("(prefers-color-scheme: dark)");
    const apply = () => {
      const resolved = theme === "system" ? (media.matches ? "dark" : "light") : theme;
      document.documentElement.dataset.workspaceTheme = resolved;
      document.querySelector('meta[name="theme-color"]')?.setAttribute(
        "content", resolved === "dark" ? "#0d1017" : "#f5f6fa",
      );
    };
    apply();
    media.addEventListener("change", apply);
    const sync = (event: StorageEvent) => {
      if (event.key === storageKey || event.key === null) setTheme(readPreference());
    };
    window.addEventListener("storage", sync);
    return () => {
      media.removeEventListener("change", apply);
      window.removeEventListener("storage", sync);
    };
  }, [theme]);
  const changeTheme = (preference: ThemePreference) => {
    try { localStorage.setItem(storageKey, preference); } catch { /* Retain in memory. */ }
    setTheme(preference);
  };
  return { theme, changeTheme };
}
