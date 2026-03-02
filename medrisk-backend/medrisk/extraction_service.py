from __future__ import annotations

from dataclasses import asdict
from typing import Any, Dict, List

from .biomarker_extractor import extract_biomarkers_regex
from .biomarker_patterns import LABEL_TO_CANONICAL, BIOMARKERS_CANONICAL
from .config import GEMINI_API_KEY
from .gemini_reader import gemini_extract_values, GeminiError
from .pdf_extractor import extract_report_text
from .reference_ranges import get_reference_range, normalize_unit
from .text_utils import extract_relevant_lines


def _missing_keys_mentioned_in_text(full_text: str, missing_candidates: List[str]) -> List[str]:
    if not full_text or not missing_candidates:
        return []

    mentioned: List[str] = []
    for missing_key in missing_candidates:
        for canon, pattern in LABEL_TO_CANONICAL:
            if canon == missing_key and pattern.search(full_text):
                mentioned.append(missing_key)
                break

    seen = set()
    out: List[str] = []
    for k in mentioned:
        if k not in seen:
            seen.add(k)
            out.append(k)
    return out


def _to_float(v: Any) -> float | None:
    try:
        if v is None:
            return None
        if isinstance(v, bool):
            return None
        if isinstance(v, (int, float)):
            return float(v)
        s = str(v).strip()
        if not s:
            return None
        s = s.replace(",", "")
        return float(s)
    except Exception:
        return None


async def extract_structured_report(pdf_bytes: bytes) -> Dict[str, Any]:
    text_result = extract_report_text(pdf_bytes)
    full_text = text_result.text or ""
    if not full_text.strip():
        raise ValueError("No text could be extracted from the PDF. Try enabling OCR or use a clearer report.")

    regex = extract_biomarkers_regex(full_text)
    values = dict(regex.values)
    details = dict(regex.details)
    qualitative = dict(regex.qualitative)
    evidence = dict(regex.evidence)
    meta = dict(regex.meta)

    used_llm = False
    llm_errors: List[str] = []
    conflicts: List[dict] = []

    missing_candidates = list(regex.missing)
    missing_mentioned = _missing_keys_mentioned_in_text(full_text, missing_candidates)
    missing_for_llm = list(missing_mentioned)

    if GEMINI_API_KEY and full_text and missing_for_llm:
        used_llm = True
        relevant = extract_relevant_lines(full_text)

        try:
            llm_out = await gemini_extract_values(relevant, missing_keys=missing_for_llm, prefilled=values)
            llm_values = llm_out.get("values") if isinstance(llm_out, dict) else {}
            llm_evidence = llm_out.get("evidence") if isinstance(llm_out, dict) else {}

            if isinstance(llm_values, dict):
                for k in missing_for_llm:
                    fv = _to_float(llm_values.get(k))
                    if fv is None:
                        continue

                    if k not in values:
                        values[k] = fv

                        if k not in details:
                            ref = get_reference_range(
                                k,
                                gender=meta.get("Gender"),
                                pregnancy=(str(meta.get("PregnancyPanel") or "")).lower() == "true",
                                trimester=meta.get("Trimester"),
                            )
                            if ref:
                                details[k] = {
                                    "unit": normalize_unit(ref.get("unit")) or (ref.get("unit") or ""),
                                    "low": float(ref["low"]),
                                    "high": float(ref["high"]),
                                    "source": "default",
                                }

                        snippet = llm_evidence.get(k) if isinstance(llm_evidence, dict) else None
                        if isinstance(snippet, str) and snippet.strip():
                            evidence[k] = {"source": "llm", "page": None, "snippet": snippet.strip()[:240]}
                    else:
                        try:
                            if abs(float(values[k]) - fv) > max(0.05, abs(float(values[k])) * 0.02):
                                conflicts.append({"key": k, "regex": float(values[k]), "llm": fv})
                        except Exception:
                            pass

            if isinstance(llm_out, dict):
                for mk in ("Gender", "ReportDate", "LabName", "PregnancyPanel", "Trimester"):
                    mv = llm_out.get(mk)
                    if mk not in meta and isinstance(mv, str) and mv.strip():
                        meta[mk] = mv.strip()
                age = _to_float(llm_out.get("AgeYears"))
                if age is not None and "AgeYears" not in meta:
                    meta["AgeYears"] = str(int(round(age))) if age >= 0 else str(age)

        except GeminiError as e:
            llm_errors.append(str(e))
        except Exception as e:
            llm_errors.append(f"{type(e).__name__}: {e}")

    missing_after = [k for k in missing_for_llm if k not in values]

    out: Dict[str, Any] = {}
    out.update(values)
    out.update({k: v for k, v in meta.items() if v})

    out["extraction"] = {
        "method": text_result.method,
        "pages": text_result.pages,
        "quality": asdict(text_result.quality),
        "warnings": text_result.warnings,
        "used_llm": used_llm,
        "llm_errors": llm_errors,
        "conflicts": conflicts,
        "missing_after": missing_after,
        "missing_candidates": missing_candidates,
        "missing_mentioned": missing_mentioned,
        "evidence": evidence,
        "details": details,
        "qualitative": qualitative,
        "values": values,
        "meta": meta,
        "canonical": list(BIOMARKERS_CANONICAL),
    }

    return out
