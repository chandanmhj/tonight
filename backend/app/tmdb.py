"""Thin TMDB client with retries. TMDB request URLs contain the API key, so errors are
cleaned before they are logged or stored."""
import random
import time

import requests

from . import config

_session = requests.Session()


def clean_error(e):
    text = f"{type(e).__name__}: {e}"
    for secret in (config.TMDB_API_KEY, config.GROQ_API_KEY, config.SUPABASE_SERVICE_KEY):
        if secret:
            text = text.replace(secret, "***")
    return text


def get(path, _retries=5, **params):
    """GET from TMDB. Retries timeouts, 429 and 5xx with backoff; 4xx raises HTTPError."""
    params["api_key"] = config.TMDB_API_KEY
    for attempt in range(_retries):
        try:
            r = _session.get(f"{config.TMDB_BASE}{path}", params=params, timeout=15)
        except (requests.ConnectionError, requests.Timeout):
            wait = 2 ** attempt
        else:
            if r.status_code == 429:
                wait = float(r.headers.get("Retry-After", 2 ** attempt))
            elif r.status_code >= 500:
                wait = 2 ** attempt
            else:
                r.raise_for_status()
                return r.json()
        if attempt < _retries - 1:
            time.sleep(min(wait, 60) + random.random())
    raise RuntimeError(f"TMDB request failed after {_retries} tries: {path}")


def movie_details(tmdb_id):
    """Details, rating and streaming providers in one request."""
    return get(f"/movie/{tmdb_id}", append_to_response="watch/providers")


def search(query, year=None):
    params = {"query": query, "include_adult": "false"}
    if year:
        params["year"] = year
    return get("/search/movie", **params).get("results", [])


def discover(year, page):
    return get("/discover/movie", watch_region=config.REGION,
               with_watch_monetization_types="flatrate",
               primary_release_year=year, sort_by="popularity.desc", page=page)


def all_providers():
    """Every streaming platform TMDB lists for the region."""
    out = []
    for p in get("/watch/providers/movie", watch_region=config.REGION).get("results", []):
        prio = (p.get("display_priorities") or {}).get(config.REGION, p.get("display_priority", 999))
        out.append({"provider_id": p["provider_id"], "name": p["provider_name"],
                    "logo_path": p.get("logo_path"), "display_priority": prio})
    return out
