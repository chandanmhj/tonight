import Poster from "./Poster.jsx";
import { fmtRuntime } from "../utils.js";

// Several suggestions at once. Each card opens the full details.
export default function PickGrid({ picks, onOpen }) {
  return (
    <ul className="picks" aria-label="Suggested movies">
      {picks.map((p) => (
        <li key={p.tmdb_id}>
          <button type="button" className="pick" onClick={() => onOpen(p)}>
            <Poster path={p.poster_path} title={p.title} className="pick-poster" />
            <span className="pick-body">
              <span className="pick-title">{p.title}</span>
              <span className="pick-meta">
                {p.year && <span>{p.year}</span>}
                {p.runtime && <span>{fmtRuntime(p.runtime)}</span>}
                {p.rating != null && (
                  <span>
                    ★ {p.rating.toFixed(1)}
                    <span className="sr-only"> out of 10</span>
                  </span>
                )}
              </span>
              {p.genres.length > 0 && <span className="pick-genres">{p.genres.slice(0, 3).join(", ")}</span>}
              {p.reason && <span className="pick-reason">{p.reason}</span>}
              <span className="pick-apps">
                {p.platforms.length > 0 ? `Streaming on ${p.platforms.map((x) => x.name).join(", ")}` : ""}
              </span>
            </span>
          </button>
        </li>
      ))}
    </ul>
  );
}
