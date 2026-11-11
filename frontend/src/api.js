// All calls to the Python backend. Errors are turned into plain sentences the UI can show.
const BASE = import.meta.env.VITE_API_URL || "";

async function request(path, options = {}) {
  let res;
  try {
    res = await fetch(BASE + path, {
      headers: { "Content-Type": "application/json" },
      ...options,
    });
  } catch (e) {
    if (e.name === "AbortError") throw e;
    throw new Error("Can't reach the server. Check that the backend is running.");
  }
  if (!res.ok) {
    let message = "Something went wrong. Try again.";
    try {
      const body = await res.json();
      if (typeof body.detail === "string") message = body.detail;
    } catch {
      /* keep the default message */
    }
    throw new Error(message);
  }
  return res.json();
}

export const getPlatforms = () => request("/api/platforms");

export const searchMovies = (q, signal) =>
  request(`/api/search?q=${encodeURIComponent(q)}`, { signal });

export const getMovie = (id) => request(`/api/movie/${id}`);

// Several movies at once. surprise=true draws at random from the library first.
export const aiPicks = ({ platformIds, mood, genres, minRuntime, maxRuntime, excludeIds, count, surprise }) =>
  request("/api/ai/picks", {
    method: "POST",
    body: JSON.stringify({
      platform_ids: platformIds,
      mood,
      genres,
      min_runtime: minRuntime,
      max_runtime: maxRuntime,
      exclude_ids: excludeIds,
      count,
      surprise,
    }),
  });
