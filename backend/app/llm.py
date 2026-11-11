"""Movie suggestions from Groq, several at a time.

Main model: openai/gpt-oss-120b with strict JSON-schema output.
If that call fails for any reason, the fallback model (llama-3.3-70b-versatile) is used in
plain JSON mode. Suggestions are only titles: the service verifies each one exists on TMDB.
"""
import json

from groq import Groq

from . import config
from .moods import MOODS

_client = None

PICK_SCHEMA = {
    "type": "object",
    "properties": {
        "title": {"type": "string"},
        "year": {"type": "integer"},
        "reason": {"type": "string"},
    },
    "required": ["title", "year", "reason"],
    "additionalProperties": False,
}

MANY_SCHEMA = {
    "type": "object",
    "properties": {"movies": {"type": "array", "items": PICK_SCHEMA}},
    "required": ["movies"],
    "additionalProperties": False,
}

SYSTEM = (
    "You recommend movies to a viewer in India. Suggest the requested number of DIFFERENT real, "
    "released feature films that you are certain exist and that are likely to stream in India on "
    "one of the viewer's platforms. Mix well-known films with good lesser-known ones, and mix "
    "languages (Hindi, English and other Indian languages) where they fit. Give each film's exact "
    "original release year. Each reason is one friendly sentence, under 20 words, saying why it fits "
    'tonight. Reply with JSON only: {"movies": [{"title": string, "year": integer, "reason": string}]}.'
)


def client():
    global _client
    if _client is None:
        _client = Groq(api_key=config.GROQ_API_KEY)
    return _client


def _runtime_text(min_runtime, max_runtime):
    if min_runtime > 0 and max_runtime < 400:
        return f"between {min_runtime} and {max_runtime} minutes"
    if min_runtime > 0:
        return f"{min_runtime} minutes or longer"
    if max_runtime < 400:
        return f"{max_runtime} minutes or less"
    return "any length"


def _prompt(platform_names, mood, genres, min_runtime, max_runtime, avoid, n, surprise):
    kind = MOODS[mood]["hint"] if mood in MOODS else "any kind of movie"
    lines = [
        f"Suggest {n} movies.",
        f"Kind of movie wanted: {kind}.",
        f"Genres wanted (any of these): {', '.join(genres) if genres else 'any genre'}.",
        f"Runtime: {_runtime_text(min_runtime, max_runtime)}.",
        f"Viewer's platforms: {', '.join(platform_names) or 'any Indian streaming service'}.",
    ]
    if surprise:
        lines.append("Surprise the viewer: favour hidden gems and a spread of decades.")
    if avoid:
        lines.append("Do not suggest any of these: " + "; ".join(avoid[:60]) + ".")
    return "\n".join(lines)


def _clean(data):
    items = data.get("movies") if isinstance(data, dict) else data
    out = []
    for it in items if isinstance(items, list) else []:
        if isinstance(it, dict) and isinstance(it.get("title"), str) and it["title"].strip():
            year = it.get("year")
            out.append({"title": it["title"].strip(),
                        "year": year if isinstance(year, int) else None,
                        "reason": str(it.get("reason") or "").strip()})
    return out


def suggest_many(platform_names, mood, genres, min_runtime, max_runtime, avoid, n, surprise=False):
    """Returns a list of {"title", "year", "reason"} (possibly empty if the reply was unusable).
    Raises if both models fail, so the caller can fall back to the library."""
    messages = [{"role": "system", "content": SYSTEM},
                {"role": "user", "content": _prompt(platform_names, mood, genres, min_runtime,
                                                    max_runtime, avoid, n, surprise)}]
    try:
        extra = {"reasoning_effort": "low"} if "gpt-oss" in config.GROQ_MODEL else {}
        resp = client().chat.completions.create(
            model=config.GROQ_MODEL, messages=messages, temperature=1.0,
            max_completion_tokens=4000,
            response_format={"type": "json_schema", "json_schema": {
                "name": "movie_picks", "strict": True, "schema": MANY_SCHEMA}},
            **extra)
    except Exception:
        resp = client().chat.completions.create(
            model=config.GROQ_FALLBACK_MODEL, messages=messages, temperature=1.0,
            max_completion_tokens=1500, response_format={"type": "json_object"})
    try:
        return _clean(json.loads(resp.choices[0].message.content))
    except (ValueError, TypeError, IndexError, AttributeError):
        return []
