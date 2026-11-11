"""Everything that talks to Supabase. The rest of the backend never touches the database
directly, so this is the only file to change if you ever swap storage."""
from . import config

_client = None


def sb():
    global _client
    if _client is None:
        from supabase import create_client
        _client = create_client(config.SUPABASE_URL, config.SUPABASE_SERVICE_KEY)
    return _client


# ---------- movies ----------
def get_movie(tmdb_id):
    rows = sb().table("movies").select("*").eq("tmdb_id", tmdb_id).limit(1).execute().data
    return rows[0] if rows else None


def get_movies(ids):
    ids = list(ids)
    if not ids:
        return []
    return sb().table("movies").select("*").in_("tmdb_id", ids).execute().data


def upsert_movie(row):
    sb().table("movies").upsert(row, on_conflict="tmdb_id").execute()


def titles_for(ids):
    if not ids:
        return []
    rows = sb().table("movies").select("title").in_("tmdb_id", list(ids)).execute().data
    return [r["title"] for r in rows]


def similar_movies(tmdb_ids, provider_ids, min_runtime, max_runtime, limit=12):
    return sb().rpc("similar_movies", {"p_ids": list(tmdb_ids), "p_providers": list(provider_ids),
                                        "p_min_runtime": min_runtime, "p_max_runtime": max_runtime,
                                        "p_limit": limit}).execute().data


def match_movies(provider_ids, min_runtime, max_runtime, mood, genres, exclude_ids, limit=10):
    return sb().rpc("match_movies", {"p_providers": list(provider_ids), "p_min_runtime": min_runtime,
                                      "p_max_runtime": max_runtime, "p_mood": mood,
                                      "p_genres": list(genres), "p_exclude": list(exclude_ids),
                                      "p_limit": limit}).execute().data


# ---------- platforms ----------
def upsert_providers(rows):
    if rows:
        # sorted so that parallel requests always lock rows in the same order (no deadlocks)
        rows = sorted(rows, key=lambda r: r["provider_id"])
        sb().table("providers").upsert(rows, on_conflict="provider_id").execute()


def list_providers():
    return (sb().table("providers").select("provider_id,name,logo_path,display_priority")
            .order("display_priority").order("name").execute().data)


def provider_names(ids):
    if not ids:
        return []
    rows = sb().table("providers").select("name").in_("provider_id", list(ids)).execute().data
    return [r["name"] for r in rows]


def platforms_for(ids):
    """{tmdb_id: [{id, name, logo_path}, ...]} for a list of movies, in one query."""
    ids = list(ids)
    out = {i: [] for i in ids}
    if not ids:
        return out
    rows = (sb().table("movie_providers")
            .select("tmdb_id, providers(provider_id, name, logo_path)")
            .in_("tmdb_id", ids).execute().data)
    for r in rows:
        p = r.get("providers")
        if p:
            out[r["tmdb_id"]].append({"id": p["provider_id"], "name": p["name"],
                                      "logo_path": p["logo_path"]})
    return out


def set_movie_providers(tmdb_id, new_ids):
    """Change only the rows that differ. Returns True if anything changed."""
    new_ids = set(new_ids)
    old = {r["provider_id"] for r in
           sb().table("movie_providers").select("provider_id").eq("tmdb_id", tmdb_id).execute().data}
    add, drop = new_ids - old, old - new_ids
    if add:
        sb().table("movie_providers").upsert(
            [{"tmdb_id": tmdb_id, "provider_id": p} for p in add],
            on_conflict="tmdb_id,provider_id", ignore_duplicates=True).execute()
    if drop:
        sb().table("movie_providers").delete().eq("tmdb_id", tmdb_id).in_("provider_id", list(drop)).execute()
    return bool(add or drop)


# ---------- bulk fetcher bookkeeping ----------
def job_get(job):
    rows = sb().table("fetch_jobs").select("*").eq("job", job).limit(1).execute().data
    return rows[0] if rows else None


def job_save(job, **fields):
    sb().table("fetch_jobs").upsert({"job": job, **fields}, on_conflict="job").execute()


def jobs_reset(jobs):
    for j in jobs:
        job_save(j, next_page=1, status="pending")


def queue_add(ids):
    rows = [{"tmdb_id": i} for i in ids]
    if rows:
        sb().table("fetch_queue").upsert(rows, on_conflict="tmdb_id", ignore_duplicates=True).execute()


def queue_next(limit, max_attempts):
    q = sb().table("fetch_queue")
    rows = q.select("tmdb_id,attempts").eq("status", "pending").order("tmdb_id").limit(limit).execute().data
    if len(rows) < limit:
        rows += (sb().table("fetch_queue").select("tmdb_id,attempts").eq("status", "failed")
                 .lt("attempts", max_attempts).order("attempts").limit(limit - len(rows)).execute().data)
    return rows


def queue_set(tmdb_id, **fields):
    sb().table("fetch_queue").update(fields).eq("tmdb_id", tmdb_id).execute()


def queue_counts():
    out = {}
    for status in ("pending", "done", "failed"):
        out[status] = (sb().table("fetch_queue").select("tmdb_id", count="exact")
                       .eq("status", status).limit(1).execute().count or 0)
    return out


def queue_failures(limit=5):
    return (sb().table("fetch_queue").select("tmdb_id,attempts,last_error")
            .eq("status", "failed").limit(limit).execute().data)


def requeue_stale(cutoff_iso):
    return sb().rpc("requeue_stale", {"p_cutoff": cutoff_iso}).execute().data


def count_movies():
    return sb().table("movies").select("tmdb_id", count="exact").limit(1).execute().count or 0
