import { useEffect, useRef, useState } from "react";
import { aiPicks, getMovie, getPlatforms } from "../api.js";
import { GENRES } from "../genres.js";
import { MOODS, RUNTIMES } from "../moods.js";
import { loadPrefs, prefersReducedMotion, savePrefs } from "../utils.js";
import MovieDetail from "./MovieDetail.jsx";
import PickGrid from "./PickGrid.jsx";
import PlatformPicker from "./PlatformPicker.jsx";
import SimilarGrid from "./SimilarGrid.jsx";

const COUNT = 6; // suggestions per request

export default function AiMode({ mood, setMood }) {
  const saved = useRef(loadPrefs()).current;
  const [platforms, setPlatforms] = useState(null);
  const [platformError, setPlatformError] = useState("");
  const [selected, setSelected] = useState(() => saved.platformIds || []);
  const [genres, setGenres] = useState(() =>
    Array.isArray(saved.genres) ? saved.genres.filter((g) => GENRES.includes(g)) : []
  );
  const [runtimeKey, setRuntimeKey] = useState(() =>
    RUNTIMES.some((r) => r.key === saved.runtimeKey) ? saved.runtimeKey : "u120"
  );

  const [phase, setPhase] = useState("idle"); // idle | loading | done | empty | error
  const [picks, setPicks] = useState([]);
  const [similar, setSimilar] = useState([]);
  const [lastSurprise, setLastSurprise] = useState(false);
  const [aiDown, setAiDown] = useState(false);
  const [loadingMore, setLoadingMore] = useState(false);
  const [noMore, setNoMore] = useState(false);
  const [message, setMessage] = useState("");
  const [opened, setOpened] = useState(null); // a movie opened for full details
  const [opening, setOpening] = useState(false);
  const resultsRef = useRef(null);

  const range = RUNTIMES.find((r) => r.key === runtimeKey) || RUNTIMES[1];

  useEffect(() => {
    getPlatforms()
      .then((list) => {
        setPlatforms(list);
        const known = new Set(list.map((p) => p.id));
        setSelected((sel) => sel.filter((id) => known.has(id)));
      })
      .catch((e) => setPlatformError(e.message));
  }, []);

  useEffect(() => {
    savePrefs({ platformIds: selected, mood, genres, runtimeKey });
  }, [selected, mood, genres, runtimeKey]);

  const scrollToResults = () =>
    resultsRef.current?.scrollIntoView({ behavior: prefersReducedMotion() ? "auto" : "smooth", block: "start" });

  const toggleGenre = (g) =>
    setGenres((cur) => (cur.includes(g) ? cur.filter((x) => x !== g) : [...cur, g]));

  // surprise=false asks the AI; surprise=true draws at random from the library.
  // append=true adds more movies below the ones already shown. Movies already on screen are
  // never suggested again.
  async function run(surprise, append = false) {
    // Only "Show more" avoids what is already on screen; a fresh run starts over.
    const exclude = append ? picks.map((p) => p.tmdb_id) : [];
    setMessage("");
    if (append) {
      setLoadingMore(true);
    } else {
      setPhase("loading");
      setOpened(null);
      scrollToResults();
    }
    try {
      const data = await aiPicks({
        platformIds: selected, mood, genres,
        minRuntime: range.min, maxRuntime: range.max,
        excludeIds: exclude, count: COUNT, surprise,
      });
      setAiDown(data.ai_unavailable);
      setSimilar(data.similar);
      setLastSurprise(surprise);
      if (append) {
        setPicks((prev) => [...prev, ...data.picks]);
        setNoMore(data.picks.length === 0);
      } else {
        setPicks(data.picks);
        setNoMore(false);
      }
      setPhase(!append && data.picks.length === 0 ? "empty" : "done");
    } catch (e) {
      if (append) {
        setMessage(e.message);
      } else {
        setPhase("error");
        setMessage(e.message);
      }
    } finally {
      setLoadingMore(false);
    }
  }

  // A suggestion already has fresh data. A movie from "more like these" is re-checked first.
  async function open(movie, fetchFresh = false) {
    setMessage("");
    if (!fetchFresh) {
      setOpened(movie);
      scrollToResults();
      return;
    }
    setOpening(true);
    try {
      const m = await getMovie(movie.tmdb_id);
      setOpened({ ...m, reason: null });
      scrollToResults();
    } catch (e) {
      setMessage(e.message);
    } finally {
      setOpening(false);
    }
  }

  const loading = phase === "loading";
  const shownIds = new Set(picks.map((p) => p.tmdb_id));

  return (
    <>
      <section className="hero" aria-labelledby="hero-title">
        <div className="hero-inner">
          <h1 id="hero-title" className="hero-line">Tonight I want something</h1>
          <div className="moods" role="group" aria-label="Kind of movie">
            {MOODS.map((m) => (
              <button
                key={m.key}
                type="button"
                className="mood"
                aria-pressed={mood === m.key}
                onClick={() => setMood(mood === m.key ? null : m.key)}
              >
                {m.key}
              </button>
            ))}
          </div>

          <p className="hero-line">from any of these genres, or all of them</p>
          <div className="platforms">
            <ul className="chips" aria-label="Genres">
              {GENRES.map((g) => (
                <li key={g}>
                  <button
                    type="button"
                    className="chip plain"
                    aria-pressed={genres.includes(g)}
                    onClick={() => toggleGenre(g)}
                  >
                    {g}
                  </button>
                </li>
              ))}
            </ul>
            {genres.length > 0 && (
              <div className="platform-more">
                <button type="button" className="textbtn" onClick={() => setGenres([])}>
                  Clear genres
                </button>
              </div>
            )}
          </div>

          <p className="hero-line">that runs</p>
          <div className="platforms">
            <div className="chips" role="radiogroup" aria-label="Movie length">
              {RUNTIMES.map((r) => (
                <button
                  key={r.key}
                  type="button"
                  role="radio"
                  className="chip plain"
                  aria-checked={runtimeKey === r.key}
                  onClick={() => setRuntimeKey(r.key)}
                >
                  {r.label}
                </button>
              ))}
            </div>
          </div>

          <p className="hero-line">and I have these apps</p>
          {platformError ? (
            <p className="hint" role="alert">{platformError}</p>
          ) : (
            <PlatformPicker platforms={platforms} selected={selected} onChange={setSelected} />
          )}

          <div className="go-row">
            <button type="button" className="go" disabled={!selected.length || loading} onClick={() => run(false)}>
              {loading ? "Choosing…" : "Suggest movies"}
            </button>
            <button type="button" className="go ghost" disabled={!selected.length || loading} onClick={() => run(true)}>
              Surprise me
            </button>
            {!selected.length && platforms && <p className="hint">Pick at least one app to start.</p>}
          </div>
          <p className="hint go-hint">
            Suggest movies asks the AI. Surprise me picks at random from well-rated movies in our library.
          </p>
        </div>
      </section>

      <main className="results" ref={resultsRef} aria-live="polite">
        {phase === "idle" && (
          <p className="empty">
            Choose a mood, genres, a length and your apps. You'll get {COUNT} movies at a time, and you can
            ask for more.
          </p>
        )}

        {loading && (
          <div className="picks" aria-label="Choosing movies for you">
            {Array.from({ length: COUNT }, (_, i) => (
              <div key={i} className="sk sk-card" />
            ))}
          </div>
        )}

        {phase === "error" && <p className="message" role="alert">{message}</p>}

        {phase === "empty" && (
          <p className="message" role="status">
            No movies matched those filters. Try more apps, more genres or a different length. Our library
            also grows every time someone looks up a movie.
          </p>
        )}

        {phase === "done" && opened && (
          <>
            <button type="button" className="back" onClick={() => { setOpened(null); scrollToResults(); }}>
              Back to suggestions
            </button>
            <MovieDetail movie={opened} reason={opened.reason} />
          </>
        )}

        {phase === "done" && !opened && (
          <>
            {aiDown && (
              <p className="note">The AI is busy right now, so some of these come from our library.</p>
            )}
            <PickGrid picks={picks} onOpen={(p) => open(p)} />
            <div className="more-row">
              <button type="button" className="secondary" disabled={loadingMore || noMore || !selected.length}
                onClick={() => run(lastSurprise, true)}>
                {loadingMore ? "Finding more…" : "Show more"}
              </button>
              {noMore && <p className="muted">That's everything we found for these filters.</p>}
              {opening && <p className="muted">Checking the latest streaming info…</p>}
              {message && <p className="message" role="alert">{message}</p>}
            </div>
            <SimilarGrid
              movies={similar.filter((m) => !shownIds.has(m.tmdb_id))}
              onOpen={(id) => open({ tmdb_id: id }, true)}
            />
          </>
        )}
      </main>
    </>
  );
}
