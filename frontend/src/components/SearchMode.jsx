import { useEffect, useState } from "react";
import { getMovie, searchMovies } from "../api.js";
import MovieDetail from "./MovieDetail.jsx";
import Poster from "./Poster.jsx";

export default function SearchMode() {
  const [query, setQuery] = useState("");
  const [results, setResults] = useState([]);
  const [searching, setSearching] = useState(false);
  const [movie, setMovie] = useState(null);
  const [loadingMovie, setLoadingMovie] = useState(false);
  const [error, setError] = useState("");

  // Search as the person types, after a short pause, and drop answers that arrive late.
  useEffect(() => {
    const q = query.trim();
    if (q.length < 2) {
      setResults([]);
      setSearching(false);
      return;
    }
    const controller = new AbortController();
    const timer = setTimeout(async () => {
      setSearching(true);
      setError("");
      try {
        setResults(await searchMovies(q, controller.signal));
      } catch (e) {
        if (e.name !== "AbortError") setError(e.message);
      } finally {
        if (!controller.signal.aborted) setSearching(false);
      }
    }, 300);
    return () => {
      clearTimeout(timer);
      controller.abort();
    };
  }, [query]);

  async function open(id) {
    setLoadingMovie(true);
    setError("");
    try {
      setMovie(await getMovie(id));
      window.scrollTo({ top: 0 });
    } catch (e) {
      setError(e.message);
    } finally {
      setLoadingMovie(false);
    }
  }

  const noResults = query.trim().length >= 2 && !searching && results.length === 0 && !error;

  return (
    <>
      <section className="hero" aria-labelledby="search-title">
        <div className="hero-inner">
          <h1 id="search-title" className="hero-line">Look up any movie</h1>
          <input
            className="search-input"
            type="search"
            autoFocus
            placeholder="Type a movie name"
            aria-label="Movie name"
            value={query}
            onChange={(e) => setQuery(e.target.value)}
          />
          <p className="hint">We'll show where it streams in India and its rating.</p>
        </div>
      </section>

      <main className="results" aria-live="polite">
        {error && <p className="message" role="alert">{error}</p>}
        {loadingMovie && <p className="muted">Checking the latest streaming info…</p>}

        {movie && !loadingMovie && <MovieDetail movie={movie} />}

        {results.length > 0 && (
          <ul className="rows" aria-label="Search results">
            {results.map((r) => (
              <li key={r.tmdb_id}>
                <button type="button" className="row" onClick={() => open(r.tmdb_id)}>
                  <Poster path={r.poster_path} title={r.title} size="w92" className="row-poster" />
                  <span className="row-title">{r.title}</span>
                  <span className="row-meta">
                    {r.year && <span>{r.year}</span>}
                    {r.rating != null && <span>★ {r.rating.toFixed(1)}</span>}
                  </span>
                </button>
              </li>
            ))}
          </ul>
        )}

        {noResults && <p className="empty">No movie found for “{query.trim()}”. Check the spelling or try fewer words.</p>}
        {!movie && !query.trim() && (
          <p className="empty">Start typing a title. Every movie you open is saved, so the library grows.</p>
        )}
      </main>
    </>
  );
}
