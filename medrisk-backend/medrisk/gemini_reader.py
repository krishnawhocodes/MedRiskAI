from __future__ import annotations

import json
import httpx

from .biomarker_patterns import BIOMARKERS_CANONICAL
from .config import GEMINI_API_KEY, GEMINI_MODEL


class GeminiError(RuntimeError):
    pass


def _gemini_url() -> str:
    if not GEMINI_API_KEY:
        raise GeminiError("GEMINI_API_KEY is not set")

    # Allow either 'gemini-2.5-flash' or 'models/gemini-2.5-flash'
    model = (GEMINI_MODEL or '').strip()
    if model.startswith('models/'):
        model_path = model
    else:
        model_path = f"models/{model}"

    return (
        f"https://generativelanguage.googleapis.com/v1beta/{model_path}:generateContent"
        f"?key={GEMINI_API_KEY}"
    )


async def gemini_extract_values(
    relevant_text: str,
    *,
    missing_keys: list[str] | None = None,
    prefilled: dict | None = None,
) -> dict:
    requested_keys = [k for k in (missing_keys or []) if k in BIOMARKERS_CANONICAL]
    prefilled = prefilled or {}

    value_props = {k: {"type": "NUMBER"} for k in requested_keys}
    evidence_props = {k: {"type": "STRING"} for k in requested_keys}

    schema = {
        "type": "OBJECT",
        "properties": {
            "values": {"type": "OBJECT", "properties": value_props},
            "evidence": {"type": "OBJECT", "properties": evidence_props},
            "Gender": {"type": "STRING", "enum": ["Male", "Female", "Unknown"]},
            "AgeYears": {"type": "NUMBER"},
            "ReportDate": {"type": "STRING"},
            "LabName": {"type": "STRING"},
            "PregnancyPanel": {"type": "STRING", "enum": ["true", "false", "unknown"]},
            "Trimester": {"type": "STRING"},
        },
    }

    system_prompt = (
        "You are an expert medical report data extraction assistant. "
        "Extract numeric lab values from the provided report text. "
        "Return STRICT JSON that matches the provided schema. "
        "Rules: "
        "1) Only fill numeric values that are explicitly present in the text. "
        "2) If you are not certain, omit the key. "
        "3) Prefer the most specific value and most recent result if multiple. "
        "4) Evidence: provide a short verbatim snippet (<=120 chars)."
    )

    user_prompt = {
        "requestedKeys": requested_keys,
        "prefilled": {k: prefilled.get(k) for k in requested_keys if k in prefilled},
        "reportText": relevant_text[:12000],
    }

    payload = {
        "contents": [{"parts": [{"text": json.dumps(user_prompt, ensure_ascii=False)}]}],
        "systemInstruction": {"parts": [{"text": system_prompt}]},
        "generationConfig": {
            "responseMimeType": "application/json",
            "responseSchema": schema,
            "temperature": 0.0,
        },
    }

    try:
        async with httpx.AsyncClient(timeout=40.0) as client:
            resp = await client.post(_gemini_url(), headers={"Content-Type": "application/json"}, json=payload)
        resp.raise_for_status()
        data = resp.json()
        txt = (
            data.get("candidates", [{}])[0]
            .get("content", {})
            .get("parts", [{}])[0]
            .get("text", "{}")
        )
        out = json.loads(txt) if isinstance(txt, str) else {}
        return out if isinstance(out, dict) else {}
    except httpx.HTTPStatusError as e:
        raise GeminiError(f"Gemini HTTP error: {e.response.text}")
    except Exception as e:
        raise GeminiError(f"Gemini parse error: {type(e).__name__}: {e}")