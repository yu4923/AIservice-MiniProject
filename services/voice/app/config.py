"""Load local configuration before importing routers or API clients."""
import os
from pathlib import Path
from dotenv import load_dotenv

APP_DIR = Path(__file__).resolve().parent
load_dotenv(APP_DIR.parent / ".env")


def required_env(name: str) -> str:
    value = os.getenv(name)
    if not value or not value.strip():
        raise RuntimeError(f"Required environment variable is missing: {name}")
    return value


JWT_SECRET = required_env("JWT_SECRET")

UPLOAD_DIR = Path(os.getenv("VOICE_UPLOAD_DIR", str(APP_DIR.parent.parent.parent / "data" / "voice" / "uploads")))
