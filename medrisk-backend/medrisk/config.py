from __future__ import annotations

import os
from typing import List, Optional


def _env(name: str, default: Optional[str] = None) -> Optional[str]:
    val = os.getenv(name)
    if val is None or val == "":
        return default
    return val


def _env_int(name: str, default: int) -> int:
    v = _env(name)
    if v is None:
        return default
    try:
        return int(v)
    except Exception:
        return default


def _env_float(name: str, default: float) -> float:
    v = _env(name)
    if v is None:
        return default
    try:
        return float(v)
    except Exception:
        return default


def _env_list(name: str, default: List[str]) -> List[str]:
    raw = _env(name)
    if not raw:
        return default
    parts = [p.strip() for p in raw.split(",")]
    return [p for p in parts if p]


# --- Core ---
APP_TITLE = _env("MEDRISK_APP_TITLE", "MedRisk AI Backend") or "MedRisk AI Backend"
ENV = _env("MEDRISK_ENV", "dev") or "dev"  # dev|prod

# --- CORS ---
CORS_ORIGINS = _env_list(
    "MEDRISK_CORS_ORIGINS",
    [
        "http://localhost:5173",
        "http://127.0.0.1:5173",
        "http://localhost:3000",
        "http://127.0.0.1:3000",
    ],
)

# --- PDF ingestion ---
MAX_PDF_MB = _env_float("MEDRISK_MAX_PDF_MB", 15.0)

# ✅ IMPORTANT: page limit for speed. Set 0 only if you want ALL pages.
MAX_PAGES = _env_int("MEDRISK_MAX_PAGES", 6)

# --- OCR ---
OCR_ENABLED = (_env("MEDRISK_OCR_ENABLED", "1") or "1") == "1"
OCR_DPI = _env_int("MEDRISK_OCR_DPI", 220)
OCR_LANG = _env("MEDRISK_OCR_LANG", "eng") or "eng"

# --- Gemini ---
GEMINI_API_KEY = _env("GEMINI_API_KEY")
GEMINI_MODEL = _env("GEMINI_MODEL", "gemini-2.5-flash") or "gemini-2.5-flash"