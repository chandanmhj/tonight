"""HTTP API for the React frontend. Run from the backend folder:
    uvicorn app.main:app --reload --port 8000
"""
import logging
import re
import time
from collections import defaultdict, deque

import requests
from fastapi import FastAPI, HTTPException, Query, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse, Response
from pydantic import BaseModel, Field, field_validator, model_validator

from . import config, service, tmdb
from .moods import GENRES, MOODS

logging.basicConfig(level=logging.INFO)
log = logging.getLogger("tonight")

app = FastAPI(title="Tonight API")
app.add_middleware(CORSMiddleware, allow_origins=config.CORS_ORIGINS,
                   allow_methods=["GET", "POST"], allow_headers=["Content-Type"])

# ---------- tiny per-IP limiter so strangers can't burn your Groq quota ----------
_hits = defaultdict(deque)


def _limit_ai(request: Request):
    # Behind Vercel the real visitor is the first address in X-Forwarded-For.
    fwd = request.headers.get("x-forwarded-for", "").split(",")[0].strip()
    ip = fwd or (request.client.host if request.client else "unknown")
    now, q = time.time(), _hits[ip]
    while q and now - q[0] > 60:
        q.popleft()
    if len(q) >= config.AI_REQUESTS_PER_MINUTE:
        raise HTTPException(429, "That's a lot of picks. Wait a minute, then try again.")
    q.append(now)


@app.exception_handler(Exception)
async def unexpected(request: Request, exc: Exception):
    log.error("unhandled error on %s: %s", request.url.path, tmdb.clean_error(exc))
    return JSONResponse({"detail": "Something went wrong on our side. Try again in a moment."},
                        status_code=500)


def _upstream(e: Exception):
    """Map TMDB failures to friendly API errors."""
    if isinstance(e, requests.HTTPError) and e.response is not None and e.response.status_code == 404:
        return HTTPException(404, "We couldn't find that movie.")
    return HTTPException(502, "The movie data service isn't responding. Try again in a minute.")


# ---------- routes ----------
@app.get("/api/health")
def health():
    return {"ok": True, "configured": {
        "tmdb": bool(config.TMDB_API_KEY), "groq": bool(config.GROQ_API_KEY),
        "supabase": bool(config.SUPABASE_URL and config.SUPABASE_SERVICE_KEY)},
        "model": config.GROQ_MODEL}


@app.get("/api/platforms")
def platforms():
    try:
        return service.platforms()
    except (requests.RequestException, RuntimeError) as e:
        raise _upstream(e)


@app.get("/api/search")
def search(q: str = Query(min_length=2, max_length=100)):
    try:
        return service.search(q)
    except (requests.RequestException, RuntimeError) as e:
        raise _upstream(e)


@app.get("/api/movie/{tmdb_id}")
def movie(tmdb_id: int):
    try:
        m, info = service.get_movie(tmdb_id)
    except (requests.RequestException, RuntimeError) as e:
        raise _upstream(e)
    return {**m, "freshness": info}


class PicksRequest(BaseModel):
    platform_ids: list[int] = Field(min_length=1, max_length=300)
    mood: str | None = None
    genres: list[str] = Field(default_factory=list, max_length=len(GENRES))
    min_runtime: int = Field(default=0, ge=0, le=399)
    max_runtime: int = Field(default=120, ge=30, le=400)
    count: int = Field(default=6, ge=1, le=10)
    surprise: bool = False                        # True: draw at random from the library first
    exclude_ids: list[int] = Field(default_factory=list, max_length=300)

    @field_validator("mood")
    @classmethod
    def known_mood(cls, v):
        if v is not None and v not in MOODS:
            raise ValueError("unknown mood")
        return v

    @field_validator("genres")
    @classmethod
    def known_genres(cls, v):
        if any(g not in GENRES for g in v):
            raise ValueError("unknown genre")
        return v

    @model_validator(mode="after")
    def runtime_range(self):
        if self.min_runtime >= self.max_runtime:
            raise ValueError("min_runtime must be less than max_runtime")
        return self


@app.post("/api/ai/picks")
def ai_picks(body: PicksRequest, request: Request):
    _limit_ai(request)
    try:
        return service.ai_picks(body.platform_ids, body.mood, body.genres, body.min_runtime,
                                body.max_runtime, body.exclude_ids, body.count, body.surprise)
    except (requests.RequestException, RuntimeError) as e:
        raise _upstream(e)


# ---------- poster / logo proxy ----------
# image.tmdb.org is blocked on some Indian networks. The browser asks this server for images
# and this server fetches them from TMDB, so posters load wherever the API itself works.
_IMG_SIZES = {"w45", "w92", "w185", "w342", "w500"}
_IMG_PATH = re.compile(r"^[A-Za-z0-9_-]{5,60}\.(jpg|jpeg|png)$")
_img_session = requests.Session()


@app.get("/api/img/{size}/{name}")
def image(size: str, name: str):
    if size not in _IMG_SIZES or not _IMG_PATH.match(name):
        raise HTTPException(404, "No such image.")
    try:
        r = _img_session.get(f"https://image.tmdb.org/t/p/{size}/{name}", timeout=10)
    except requests.RequestException as e:
        log.warning("image fetch failed: %s", tmdb.clean_error(e))
        raise HTTPException(502, "Image unavailable.")
    if r.status_code != 200 or not r.headers.get("content-type", "").startswith("image/"):
        raise HTTPException(404, "No such image.")
    return Response(r.content, media_type=r.headers["content-type"],
                    headers={"Cache-Control": "public, max-age=604800, immutable"})