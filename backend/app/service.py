"""The app's logic: keep movies fresh (24-hour rule), suggest several movies at once
(by AI or at random from the library), and find similar ones."""
import difflib
import logging
import re
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timedelta, timezone

from . import config, llm, store, tmdb
from .moods import tags_for

log = logging.getLogger("tonight")
STALE_AFTER = timedelta(hours=config.STALE_HOURS)
MAX_REFRESH_IN_LIST = 5     # cap on TMDB calls when refreshing the "more like these" list
PARALLEL = 6                # TMDB calls made side by side


# ---------- freshness ----------
def _parse(ts):
    """Read a Postgres timestamp. Python before 3.11 only accepts 3 or 6 fractional digits,
    and Postgres drops trailing zeros (e.g. .35529), so pad the fraction to 6 digits."""
    if not ts:
        return None
    ts = ts.strip().replace("Z", "+00:00")
    ts = re.sub(r"\.(\d+)", lambda m: "." + m.group(1)[:6].ljust(6, "0"), ts, count=1)
    parsed = datetime.fromisoformat(ts)
    return parsed if parsed.tzinfo else parsed.replace(tzinfo=timezone.utc)


def is_stale(row):
    ts = _parse(row.get("last_checked_at"))
    return ts is None or datetime.now(timezone.utc) - ts > STALE_AFTER


def fetch_remote(tmdb_id):
    """Network only: one TMDB call returning (movie row, streaming providers in India)."""
    d = tmdb.movie_details(tmdb_id)
    genres = [g["name"] for g in d.get("genres", [])]
    release = d.get("release_date") or ""
    row = {
        "tmdb_id": d["id"],
        "title": d["title"],
        "year": int(release[:4]) if release[:4].isdigit() else None,
        "runtime": d.get("runtime") or None,
        "rating": round(d["vote_average"], 1) if d.get("vote_average") else None,
        "vote_count": d.get("vote_count") or 0,
        "genres": genres,
        "mood_tags": tags_for(genres),
        "overview": d.get("overview") or None,
        "poster_path": d.get("poster_path"),
        "last_checked_at": datetime.now(timezone.utc).isoformat(),
    }
    flat = d.get("watch/providers", {}).get("results", {}).get(config.REGION, {}).get("flatrate", [])
    providers = [{"provider_id": p["provider_id"], "name": p["provider_name"],
                  "logo_path": p.get("logo_path"), "display_priority": p.get("display_priority", 999)}
                 for p in flat]
    return row, providers


def save_remote(row, providers):
    """Write to Supabase. Only the platform rows that differ are inserted or deleted.
    Returns True if the movie's platforms changed."""
    store.upsert_providers(providers)
    store.upsert_movie(row)
    return store.set_movie_providers(row["tmdb_id"], {p["provider_id"] for p in providers})


def refresh_movie(tmdb_id):
    row, providers = fetch_remote(tmdb_id)
    return save_remote(row, providers)


def _refresh_parallel(ids):
    """Re-check movies on TMDB. The TMDB calls run side by side and the database writes run one
    after another. A failure skips that movie instead of raising. Returns how many refreshed."""
    ids = list(ids)
    if not ids:
        return 0

    def grab(tid):
        try:
            return fetch_remote(tid)
        except Exception as e:
            log.warning("refresh of %s failed: %s", tid, tmdb.clean_error(e))
            return None

    with ThreadPoolExecutor(max_workers=min(PARALLEL, len(ids))) as ex:
        fetched = [f for f in ex.map(grab, ids) if f]
    for row, providers in fetched:
        save_remote(row, providers)
    return len(fetched)


def get_movie(tmdb_id, force=False):
    """The movie from our database, re-checked against TMDB first if it is missing or
    older than 24 hours. Returns (movie, {"refreshed", "platforms_changed"})."""
    row = store.get_movie(tmdb_id)
    info = {"refreshed": False, "platforms_changed": False}
    if row is None or force or is_stale(row):
        had_row = row is not None
        changed = refresh_movie(tmdb_id)
        info = {"refreshed": True, "platforms_changed": changed and had_row}
        row = store.get_movie(tmdb_id)
    return hydrate([row])[0], info


def ensure_movies(ids):
    """{tmdb_id: movie} for several movies at once. Any that are missing from the database, or
    last checked over 24 hours ago, are re-checked on TMDB first."""
    ids = list(dict.fromkeys(ids))
    if not ids:
        return {}
    rows = {r["tmdb_id"]: r for r in store.get_movies(ids)}
    need = [i for i in ids if i not in rows or is_stale(rows[i])]
    if _refresh_parallel(need):
        rows = {r["tmdb_id"]: r for r in store.get_movies(ids)}
    return {m["tmdb_id"]: m for m in hydrate([rows[i] for i in ids if i in rows])}


# ---------- shaping rows for the frontend ----------
def hydrate(rows):
    plats = store.platforms_for([r["tmdb_id"] for r in rows])
    return [{
        "tmdb_id": r["tmdb_id"], "title": r["title"], "year": r["year"], "runtime": r["runtime"],
        "rating": float(r["rating"]) if r["rating"] is not None else None,
        "genres": r["genres"] or [], "overview": r["overview"], "poster_path": r["poster_path"],
        "platforms": plats.get(r["tmdb_id"], []), "last_checked_at": r["last_checked_at"],
    } for r in rows]


# ---------- platforms list ----------
def platforms():
    rows = store.list_providers()
    if not rows:                                   # first run: load the list from TMDB once
        store.upsert_providers(tmdb.all_providers())
        rows = store.list_providers()
    return [{"id": r["provider_id"], "name": r["name"], "logo_path": r["logo_path"]} for r in rows]


# ---------- search mode ----------
def search(query):
    out = []
    for r in tmdb.search(query)[:8]:
        date = r.get("release_date") or ""
        out.append({"tmdb_id": r["id"], "title": r["title"],
                    "year": int(date[:4]) if date[:4].isdigit() else None,
                    "poster_path": r.get("poster_path"),
                    "rating": round(r["vote_average"], 1) if r.get("vote_average") else None})
    return out


# ---------- several picks at once ----------
def _norm(s):
    return re.sub(r"[^a-z0-9]+", "", s.lower())


def verify_on_tmdb(suggestion):
    """The model can invent films. Accept a suggestion only if TMDB has a close title match."""
    want = _norm(suggestion["title"])
    for year in ([suggestion["year"]] if suggestion.get("year") else []) + [None]:
        for r in tmdb.search(suggestion["title"], year)[:5]:
            for name in (r.get("title"), r.get("original_title")):
                if name and difflib.SequenceMatcher(None, want, _norm(name)).ratio() >= 0.8:
                    return r["id"]
    return None


def _safe_verify(suggestion):
    try:
        return verify_on_tmdb(suggestion)
    except Exception as e:                  # a TMDB hiccup drops one suggestion, not all of them
        log.warning("could not verify %r: %s", suggestion.get("title"), tmdb.clean_error(e))
        return None


def _fits(movie, wanted, min_runtime, max_runtime, genres):
    if not ({p["id"] for p in movie["platforms"]} & wanted):
        return False
    if not movie["runtime"] or not (min_runtime <= movie["runtime"] <= max_runtime):
        return False
    return not genres or bool(set(movie["genres"]) & set(genres))


def ai_picks(platform_ids, mood, genres, min_runtime, max_runtime, exclude_ids, count, surprise):
    """Up to `count` movies that fit the filters and that the viewer has not seen in this session.

    Normal mode asks the AI first and tops up from the library. Surprise mode draws at random
    from the library first (the database returns matches in random order) and tops up with the AI.
    Every movie is re-checked on TMDB first when it is older than 24 hours."""
    wanted, exclude = set(platform_ids), set(exclude_ids)
    picks, rejected, state = [], [], {"ai_down": False}

    def add(movie, reason, source):
        picks.append({**movie, "reason": reason, "source": source})
        exclude.add(movie["tmdb_id"])

    def from_llm():
        names = store.provider_names(platform_ids)
        for _ in range(2):                  # a second round replaces suggestions that did not fit
            need = count - len(picks)
            if need <= 0:
                return
            avoid = store.titles_for(list(exclude)) + rejected
            try:
                suggestions = llm.suggest_many(names, mood, genres, min_runtime, max_runtime,
                                               avoid, need + 3, surprise)
            except Exception as e:          # Groq down or out of quota: fall back to the library
                log.warning("AI suggestions failed: %s", tmdb.clean_error(e))
                state["ai_down"] = True
                return
            with ThreadPoolExecutor(max_workers=PARALLEL) as ex:
                tids = list(ex.map(_safe_verify, suggestions))
            pairs, seen = [], set()
            for tid, s in zip(tids, suggestions):
                if tid is None or tid in exclude or tid in seen:
                    rejected.append(s["title"])
                    continue
                seen.add(tid)
                pairs.append((tid, s))
            movies = ensure_movies([t for t, _ in pairs])
            for tid, s in pairs:
                m = movies.get(tid)
                if m and len(picks) < count and _fits(m, wanted, min_runtime, max_runtime, genres):
                    add(m, s.get("reason") or None, "ai")
                else:
                    rejected.append(s["title"])

    def from_library():
        def candidates(with_mood):
            return store.match_movies(platform_ids, min_runtime, max_runtime,
                                      mood if with_mood else None, genres, list(exclude), 60)
        pool = [r["tmdb_id"] for r in candidates(True)]    # already in random order
        if len(pool) < count - len(picks) and mood:        # too few for this mood: relax it
            pool += [r["tmdb_id"] for r in candidates(False) if r["tmdb_id"] not in pool]
        for _ in range(3):
            need = count - len(picks)
            if need <= 0 or not pool:
                return
            batch, pool = pool[: need + 2], pool[need + 2:]
            movies = ensure_movies(batch)       # re-checks stale ones, which may leave the user's apps
            for tid in batch:
                m = movies.get(tid)
                if m and len(picks) < count and tid not in exclude \
                        and _fits(m, wanted, min_runtime, max_runtime, genres):
                    add(m, None, "library")

    for step in ((from_library, from_llm) if surprise else (from_llm, from_library)):
        if len(picks) < count:
            step()

    return {"picks": picks, "ai_unavailable": state["ai_down"],
            "similar": similar_to([p["tmdb_id"] for p in picks], platform_ids, min_runtime, max_runtime)}


def similar_to(anchor_ids, platform_ids, min_runtime, max_runtime):
    """'More like these': movies from our library sharing genres with any of the anchors."""
    if not anchor_ids:
        return []
    rows = store.similar_movies(anchor_ids, platform_ids, min_runtime, max_runtime, 12)
    stale = [r["tmdb_id"] for r in rows if is_stale(r)][:MAX_REFRESH_IN_LIST]
    if _refresh_parallel(stale):         # platforms may have changed: apply the filters again
        rows = store.similar_movies(anchor_ids, platform_ids, min_runtime, max_runtime, 12)
    return hydrate(rows)