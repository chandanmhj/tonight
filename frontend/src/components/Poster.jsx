import { posterUrl } from "../utils.js";

export default function Poster({ path, title, size = "w342", className = "" }) {
  const src = posterUrl(path, size);
  if (!src) {
    return (
      <div className={`poster poster-missing ${className}`} role="img" aria-label={`${title}, no poster available`}>
        <span>{title}</span>
      </div>
    );
  }
  return <img className={`poster ${className}`} src={src} alt={`Poster for ${title}`} loading="lazy" />;
}
