import Poster from "./Poster.jsx";
import { fmtRuntime, logoUrl } from "../utils.js";

export default function MovieDetail({ movie, reason }) {
  const changed = movie.freshness?.platforms_changed;
  return (
    <article className="detail">
      <Poster path={movie.poster_path} title={movie.title} size="w500" className="detail-poster" />
      <div className="detail-body">
        <h2>{movie.title}</h2>
        <ul className="meta">
          {movie.year && <li>{movie.year}</li>}
          {movie.runtime && <li>{fmtRuntime(movie.runtime)}</li>}
          {movie.rating != null && (
            <li>
              ★ {movie.rating.toFixed(1)}
              <span className="sr-only"> out of 10</span>
            </li>
          )}
        </ul>
        {movie.genres.length > 0 && <p className="genres">{movie.genres.join(", ")}</p>}

        {reason && <p className="reason">{reason}</p>}
        {movie.overview && <p className="overview">{movie.overview}</p>}

        <div className="streaming">
          <h3>Streaming on</h3>
          {movie.platforms.length > 0 ? (
            <ul className="badges">
              {movie.platforms.map((p) => (
                <li key={p.id} className="badge">
                  {logoUrl(p.logo_path) && <img src={logoUrl(p.logo_path)} alt="" width="24" height="24" />}
                  {p.name}
                </li>
              ))}
            </ul>
          ) : (
            <p className="muted">Not on any Indian streaming app right now.</p>
          )}
          {changed && <p className="note">Streaming info was just updated.</p>}
        </div>
      </div>
    </article>
  );
}
