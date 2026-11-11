import { useState } from "react";
import { logoUrl } from "../utils.js";

const VISIBLE = 10; // the most popular platforms in India come first from the API

export default function PlatformPicker({ platforms, selected, onChange }) {
  const [expanded, setExpanded] = useState(false);
  const [filter, setFilter] = useState("");

  if (!platforms) return <p className="hint">Loading streaming apps…</p>;

  const chosen = new Set(selected);
  const toggle = (id) =>
    onChange(chosen.has(id) ? selected.filter((x) => x !== id) : [...selected, id]);

  let shown;
  if (!expanded) {
    shown = platforms.filter((p, i) => i < VISIBLE || chosen.has(p.id));
  } else if (filter.trim()) {
    shown = platforms.filter((p) => p.name.toLowerCase().includes(filter.trim().toLowerCase()));
  } else {
    shown = platforms;
  }

  return (
    <div className="platforms">
      <ul className="chips" aria-label="Streaming apps you have">
        {shown.map((p) => (
          <li key={p.id}>
            <button
              type="button"
              className="chip"
              aria-pressed={chosen.has(p.id)}
              onClick={() => toggle(p.id)}
            >
              {logoUrl(p.logo_path) && <img src={logoUrl(p.logo_path)} alt="" width="22" height="22" />}
              {p.name}
            </button>
          </li>
        ))}
      </ul>
      {platforms.length > VISIBLE && (
        <div className="platform-more">
          <button type="button" className="textbtn" onClick={() => setExpanded(!expanded)}>
            {expanded ? "Show fewer apps" : `Show all ${platforms.length} apps`}
          </button>
          {expanded && (
            <input
              className="platform-filter"
              type="search"
              placeholder="Find an app"
              aria-label="Find a streaming app"
              value={filter}
              onChange={(e) => setFilter(e.target.value)}
            />
          )}
        </div>
      )}
    </div>
  );
}
