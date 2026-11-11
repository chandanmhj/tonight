# Tonight

Pick a movie for tonight from the streaming apps you actually have in India.

Choose the kind of film you want (funny, emotional, thrilling...), how long you have, and your apps.
An AI suggests one movie, then you get a list of similar movies from your own database.
There is also a plain search to look up any title and see where it streams.

```
React (Vite)  ->  FastAPI backend  ->  Supabase (Postgres)   storage
 frontend/        backend/             supabase/schema.sql
                    |-> Groq           picks the movie
                    |-> TMDB           movie data + streaming availability (JustWatch)
```

The browser only talks to your backend. Your TMDB, Groq and Supabase keys never reach the browser.

## What you need

- Python 3.10+ and Node 18+
- A free [Supabase](https://supabase.com) project
- A free [TMDB API key](https://www.themoviedb.org/settings/api)
- A free [Groq API key](https://console.groq.com/keys)

## Setup

### 1. Supabase (storage)

1. Create a project.
2. Open **SQL Editor -> New query**, paste all of `supabase/schema.sql`, click **Run**. Running it again is safe, and it is also how you upgrade an existing database to this version.
3. Open **Project Settings -> API** and copy the **Project URL** and the **secret / service_role key**.
   This key must stay on the server. Never put it in the frontend or commit it.

The tables have row level security on and no public policies, so the public `anon` key can read nothing.

### 2. Backend

```bash
cd backend
python -m venv .venv
source .venv/bin/activate          # Windows: .venv\Scripts\activate
pip install -r requirements.txt
cp .env.example .env               # then fill in the keys
uvicorn app.main:app --reload --port 8000
```

Check `http://localhost:8000/api/health`. It shows which of TMDB, Groq and Supabase are configured.

### 3. Frontend

```bash
cd frontend
npm install
npm run dev                        # http://localhost:5173
```

In development, `/api` calls are forwarded to the backend on port 8000.

### 4. Fill the library (optional but recommended)

The library also grows by itself: every movie someone opens or the AI picks is saved. To load many
movies up front, run the fetcher from the `backend` folder:

```bash
python fetcher.py run --from-year 2015     # one full pass
python fetcher.py run --forever            # keep going: new releases, plus re-check anything older than 24h
python fetcher.py status                   # progress and recent failures
```

It is built to survive crashes: progress is saved in Supabase after every page and every movie, requests
are paced (0.3 s apart, a 30 s pause every 100 movies), and failures are retried and then skipped.
Stop it any time with Ctrl+C and run it again to resume. Tune it with `--gap`, `--batch-size` and `--batch-pause`.

## How it works

- **Suggest movies:** you choose a mood, any genres, a length (under 90 min, under 2 h, 2 to 2.5 h, over 2.5 h, or
  any) and your apps. The model proposes several titles at once; each is confirmed on TMDB (models sometimes invent
  films), checked against your apps, length and genres, and any shortfall is topped up from your library.
  **Show more** adds another batch without repeating movies already on screen.
- **Surprise me:** a random pick from well-rated movies in your library (`match_movies` orders by `random()`),
  using the same filters. No AI call.
- **More like these:** a Postgres function (`similar_movies`) returns movies from your database that share genres
  with the suggestions, stream on your apps and fit your length.
- **24-hour rule:** each movie has `last_checked_at`. When a movie is shown and that is over 24 hours old, its
  streaming info is re-checked on TMDB. Only the platform rows that changed are inserted or deleted.
  In "more like this", at most 5 stale movies are re-checked per request.
- **If Groq is down:** the app fills the list from your library and says so.
- **Moods** are the kind of film wanted. Each maps to TMDB genres (`backend/app/moods.py`). For better tags later,
  have the model label each movie once and store the result in `movies.mood_tags`.

### Groq models

Checked against Groq's model list in November 2026. Production chat models: `openai/gpt-oss-120b`,
`openai/gpt-oss-20b`, `llama-3.3-70b-versatile`, `llama-3.1-8b-instant`.

- Main model: `openai/gpt-oss-120b` with strict JSON-schema output (`GROQ_MODEL`).
- Fallback: `llama-3.3-70b-versatile` in JSON mode (`GROQ_FALLBACK_MODEL`).
- To spend less, set `GROQ_MODEL=openai/gpt-oss-20b`. Groq's list changes, so see https://console.groq.com/docs/models.

## Settings (backend/.env)

| Name | Purpose |
|---|---|
| `TMDB_API_KEY` | TMDB v3 API key |
| `GROQ_API_KEY` | Groq key |
| `GROQ_MODEL`, `GROQ_FALLBACK_MODEL` | Models to use (optional) |
| `SUPABASE_URL`, `SUPABASE_SERVICE_KEY` | Your project URL and secret key |
| `CORS_ORIGINS` | Website addresses allowed to call the API (comma separated) |
| `AI_REQUESTS_PER_MINUTE` | Per-IP limit on AI picks, default 20 |

## Deploying

- **Frontend:** `cd frontend && npm run build`, then host the `dist` folder (Netlify, Vercel, Cloudflare Pages).
  Set `VITE_API_URL` to your API address when building.
- **Backend:** any host that runs Python (Render, Railway, Fly.io):
  `uvicorn app.main:app --host 0.0.0.0 --port $PORT`. Set the `.env` values as environment variables, and set
  `CORS_ORIGINS` to your website address.
- The per-IP limit reads the connection address. Behind a proxy, every user may look like one address, so run
  uvicorn with `--proxy-headers` and your proxy's address in `--forwarded-allow-ips`.
- Run the fetcher with `--forever` on any always-on machine, or as a scheduled job.

## Credits

Movie data from [TMDB](https://www.themoviedb.org/). Streaming availability from [JustWatch](https://www.justwatch.com/).
This product uses the TMDB API but is not endorsed or certified by TMDB. Keep both credits in the app (they are in the footer).
