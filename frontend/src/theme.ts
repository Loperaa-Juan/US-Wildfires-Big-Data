import { useEffect, useState } from "react";

export type Theme = "light" | "dark";

const KEY = "wildfires-theme";
const media = () => window.matchMedia("(prefers-color-scheme: dark)");

function stored(): Theme | null {
  try {
    const value = localStorage.getItem(KEY);
    return value === "light" || value === "dark" ? value : null;
  } catch {
    return null; // storage can be blocked (private mode); the OS setting is used instead
  }
}

/**
 * Light or dark: the viewer's choice if they made one, otherwise the OS setting. The choice
 * is written to <html data-theme> so the CSS tokens (and the map colors read from them) follow.
 */
export function useTheme() {
  const [choice, setChoice] = useState<Theme | null>(stored);
  const [system, setSystem] = useState<Theme>(() => (media().matches ? "dark" : "light"));

  useEffect(() => {
    const query = media();
    const onChange = () => setSystem(query.matches ? "dark" : "light");
    query.addEventListener("change", onChange);
    return () => query.removeEventListener("change", onChange);
  }, []);

  const theme = choice ?? system;

  // Applied before paint of the children that read the CSS variables (the map)
  if (document.documentElement.dataset.theme !== theme) {
    document.documentElement.dataset.theme = theme;
  }

  const toggle = () => {
    const next: Theme = theme === "dark" ? "light" : "dark";
    setChoice(next);
    try {
      localStorage.setItem(KEY, next);
    } catch {
      // not remembered, still applied
    }
  };

  return { theme, toggle };
}
