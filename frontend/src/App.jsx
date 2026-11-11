import { useState } from "react";
import AiMode from "./components/AiMode.jsx";
import SearchMode from "./components/SearchMode.jsx";
import { NEUTRAL, moodByKey } from "./moods.js";
import { loadPrefs } from "./utils.js";

export default function App() {
  const [tab, setTab] = useState("ai");
  const [mood, setMood] = useState(() => loadPrefs().mood || null);

  // The chosen mood sets the colour of the whole top of the page.
  const stage = tab === "ai" && mood ? moodByKey(mood) : NEUTRAL;

  return (
    <div className="app" style={{ "--stage": stage.color, "--on-stage": stage.ink }}>
      <header className="topbar">
        <a className="wordmark" href="/">Tonight</a>
        <div className="tabs" role="tablist" aria-label="How do you want to find a movie?">
          <button
            type="button"
            role="tab"
            id="tab-ai"
            aria-selected={tab === "ai"}
            aria-controls="panel"
            onClick={() => setTab("ai")}
          >
            Pick for me
          </button>
          <button
            type="button"
            role="tab"
            id="tab-search"
            aria-selected={tab === "search"}
            aria-controls="panel"
            onClick={() => setTab("search")}
          >
            Look up a title
          </button>
        </div>
      </header>

      <div id="panel" role="tabpanel" aria-labelledby={`tab-${tab}`}>
        {tab === "ai" ? <AiMode mood={mood} setMood={setMood} /> : <SearchMode />}
      </div>

      <footer className="footer">
        <p>
          Movie data from <a href="https://www.themoviedb.org/">TMDB</a>. Streaming availability from{" "}
          <a href="https://www.justwatch.com/">JustWatch</a>. This product uses the TMDB API but is not
          endorsed or certified by TMDB.
        </p>
      </footer>
    </div>
  );
}
