from __future__ import annotations

import re
from dataclasses import dataclass


@dataclass
class TextQuality:
    char_count: int
    line_count: int
    alpha_ratio: float
    digit_ratio: float
    alnum_ratio: float
    keyword_hits: int
    score: float


_KEYWORDS = [
    # common report anchors
    "hemoglobin", "haemoglobin", "hb", "hgb",
    "wbc", "tlc", "rbc", "platelet", "plt",
    "mcv", "mch", "mchc", "mpv",
    "tsh", "thyroid",
    "glucose", "fasting", "random", "fbs", "rbs",
    "cholesterol", "hdl", "ldl", "triglycer",
    "patient", "report", "reference", "range", "method",
    # units hints
    "g/dl", "mg/dl", "uiu/ml", "miu/l", "fl", "pg",
]


def normalize_text(text: str) -> str:
    if not text:
        return ""
    text = text.replace("\r\n", "\n").replace("\r", "\n")
    text = re.sub(r"[\t\f\v]+", " ", text)
    text = text.replace("\u00a0", " ")
    text = re.sub(r"[ ]{2,}", " ", text)
    text = re.sub(r"\n{3,}", "\n\n", text)
    return text.strip()


def text_quality(text: str) -> TextQuality:
    t = text or ""
    chars = len(t)
    if chars == 0:
        return TextQuality(0, 0, 0.0, 0.0, 0.0, 0, 0.0)

    lines = len([ln for ln in t.split("\n") if ln.strip()])

    alpha = sum(1 for c in t if c.isalpha())
    digit = sum(1 for c in t if c.isdigit())
    alnum = sum(1 for c in t if c.isalnum())

    alpha_ratio = alpha / chars
    digit_ratio = digit / chars
    alnum_ratio = alnum / chars

    lower = t.lower()
    keyword_hits = sum(1 for k in _KEYWORDS if k in lower)

    # Medical reports often have lots of digits. So alnum ratio matters.
    score = 0.0
    score += min(chars / 2500.0, 1.0) * 0.40
    score += min(lines / 60.0, 1.0) * 0.15
    score += min(keyword_hits / 7.0, 1.0) * 0.40
    score += max(0.0, min(alnum_ratio / 0.55, 1.0)) * 0.05

    return TextQuality(
        char_count=chars,
        line_count=lines,
        alpha_ratio=round(alpha_ratio, 3),
        digit_ratio=round(digit_ratio, 3),
        alnum_ratio=round(alnum_ratio, 3),
        keyword_hits=keyword_hits,
        score=round(score, 3),
    )


def extract_relevant_lines(text: str, *, max_chars: int = 9000) -> str:
    """
    Used for Gemini fallback: keep only the most relevant lines
    so we don't waste tokens on irrelevant report parts.
    """
    if not text:
        return ""

    keep: list[str] = []
    keys = [k.lower() for k in _KEYWORDS]

    for ln in text.split("\n"):
        s = ln.strip()
        if not s:
            continue
        low = s.lower()
        if any(k in low for k in keys):
            keep.append(s)
        elif any(x in low for x in ("name", "age", "sex", "gender", "patient", "reported", "collected", "lab")):
            keep.append(s)

    # If too little matched, keep first few lines instead
    if len("\n".join(keep)) < 450:
        keep = [ln.rstrip() for ln in text.split("\n") if ln.strip()][:220]

    out = "\n".join(keep)
    if len(out) > max_chars:
        out = out[:max_chars]
    return out


def safe_float(s: str) -> float | None:
    """
    Convert a numeric string to float safely.
    Handles common OCR noise:
      - 13.2*, 13.2(H), 13.2 H
      - 1O.2 (O instead of 0)
      - 1l.5 (l instead of 1)
    """
    if s is None:
        return None

    s = str(s).strip()
    if not s:
        return None

    s = s.replace(",", "")

    # OCR confusions
    s = re.sub(r"(?<=\d)[Oo](?=\d)", "0", s)
    s = re.sub(r"(?<=\d)[Il](?=\d)", "1", s)
    s = s.replace("—", "-").replace("–", "-")

    # Remove symbols around values
    s = re.sub(r"[\*\(\)\[\]↑↓HhLl]", " ", s)
    s = re.sub(r"\s{2,}", " ", s).strip()

    m = re.search(r"-?\d+(?:\.\d+)?", s)
    if not m:
        return None

    try:
        return float(m.group(0))
    except ValueError:
        return None
