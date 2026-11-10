"""Vercel entrypoint: exposes the FastAPI instance from app/main.py at the project root."""
from app.main import app  # noqa: F401
