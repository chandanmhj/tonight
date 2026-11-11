"""Vercel entry point: serves the FastAPI app in backend/app as a serverless function.
Every /api/* request is rewritten here by vercel.json."""
import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "backend"))

from app.main import app  # noqa: E402,F401  (Vercel looks for a variable named `app`)