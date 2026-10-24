# Vercel entry point. Vercel runs anything in /api as a serverless function,
# so we just point it at the same FastAPI app the Docker image uses.
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "backend"))

from app.main import app  # noqa: E402,F401
