import Poster from "./Poster.jsx";
import { fmtRuntime } from "../utils.js";

export default function SimilarGrid({ movies, onOpen }) {
  return (
    <section className="similar" aria-labelledby="similar-title">
      <h2 id="similar-title">More like these</h2>
      {movies.length === 0 ? (
        <p className="muted">
          Nothing similar in our library yet. It grows every time someone looks up or picks a movie.
        </p>
      ) : (
        <ul className="grid">
          {movies.map((m) => (
            <li key={m.tmdb_id}>
              <button type="button" className="tile" onClick={() => onOpen(m.tmdb_id)}>
                <Poster path={m.poster_path} title={m.title} />
                <span className="tile-title">{m.title}</span>
                <span className="tile-meta">
                  {m.year && <span>{m.year}</span>}
                  {m.runtime && <span>{fmtRuntime(m.runtime)}</span>}
                </span>
              </button>
            </li>
          ))}
        </ul>
      )}
    </section>
  );
}
