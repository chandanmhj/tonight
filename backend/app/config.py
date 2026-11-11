"""All settings come from environment variables (see backend/.env.example)."""
import os

from dotenv import load_dotenv

load_dotenv()

TMDB_API_KEY = os.environ.get("TMDB_API_KEY", "")
TMDB_BASE = os.environ.get("TMDB_BASE_URL", "https://api.themoviedb.org/3")
REGION = os.environ.get("TMDB_REGION", "IN")

GROQ_API_KEY = os.environ.get("GROQ_API_KEY", "")
# Groq production chat models (checked against console.groq.com/docs/models, Nov 2026):
#   openai/gpt-oss-120b, openai/gpt-oss-20b, llama-3.3-70b-versatile, llama-3.1-8b-instant
# The two gpt-oss models support strict JSON-schema output. If the main model errors,
# the fallback model is used in plain JSON mode.
GROQ_MODEL = os.environ.get("GROQ_MODEL", "openai/gpt-oss-120b")
GROQ_FALLBACK_MODEL = os.environ.get("GROQ_FALLBACK_MODEL", "llama-3.3-70b-versatile")

SUPABASE_URL = os.environ.get("SUPABASE_URL", "")
SUPABASE_SERVICE_KEY = os.environ.get("SUPABASE_SERVICE_KEY", "")

CORS_ORIGINS = [o.strip() for o in
                os.environ.get("CORS_ORIGINS", "http://localhost:5173").split(",") if o.strip()]

STALE_HOURS = 24            # re-check a movie's platforms when older than this
AI_REQUESTS_PER_MINUTE = int(os.environ.get("AI_REQUESTS_PER_MINUTE", "20"))   # per IP
