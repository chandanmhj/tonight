export function fmtRuntime(minutes) {
  if (!minutes) return "";
  const h = Math.floor(minutes / 60);
  const m = minutes % 60;
  if (h === 0) return `${m}m`;
  return m === 0 ? `${h}h` : `${h}h ${m}m`;
}

// Images go through our own backend (/api/img) because image.tmdb.org is blocked on some
// Indian networks. TMDB paths look like "/abc123.jpg", so drop the leading slash.
const BASE = import.meta.env.VITE_API_URL || "";
const img = (size, path) => `${BASE}/api/img/${size}/${path.replace(/^\//, "")}`;
export const posterUrl = (path, size = "w342") => (path ? img(size, path) : null);
export const logoUrl = (path) => (path ? img("w45", path) : null);

// Remember the viewer's choices between visits. Storage can be blocked, so never trust it.
const KEY = "tonight.prefs";
export function loadPrefs() {
  try {
    return JSON.parse(localStorage.getItem(KEY)) || {};
  } catch {
    return {};
  }
}
export function savePrefs(prefs) {
  try {
    localStorage.setItem(KEY, JSON.stringify(prefs));
  } catch {
    /* ignore */
  }
}

export const prefersReducedMotion = () =>
  typeof window !== "undefined" &&
  window.matchMedia &&
  window.matchMedia("(prefers-reduced-motion: reduce)").matches;