from __future__ import annotations

from typing import Any, Dict, List, Optional

from .clinical_interference import infer_probable_conditions


def _safe_float(x: Any) -> Optional[float]:
    try:
        if isinstance(x, (int, float)):
            return float(x)
        return None
    except Exception:
        return None


def _clamp(x: float, lo: float = 0.0, hi: float = 100.0) -> float:
    return max(lo, min(hi, x))


def _risk_from_score(score: float) -> str:
    if score >= 70:
        return "High"
    if score >= 35:
        return "Moderate"
    return "Low"


def _status_from_range(value: float, low: Optional[float], high: Optional[float]) -> str:
    if low is not None and value < low:
        return "low"
    if high is not None and value > high:
        return "high"
    return "normal"


def _build_biomarker_table(structured: Dict[str, Any]) -> List[Dict[str, Any]]:
    extraction = structured.get("extraction") or {}
    details = extraction.get("details") or {}

    if not isinstance(details, dict) or not details:
        return []

    rows: List[Dict[str, Any]] = []

    for key, meta in details.items():
        if not isinstance(meta, dict):
            continue

        value = _safe_float(structured.get(key))
        low = meta.get("low")
        high = meta.get("high")
        unit = meta.get("unit")

        low_f = _safe_float(low)
        high_f = _safe_float(high)

        status = "unknown"
        if value is not None:
            status = _status_from_range(value, low_f, high_f)

        rows.append(
            {
                "key": str(key),
                "value": value,
                "unit": unit,
                "low": low_f,
                "high": high_f,
                "status": status,
                "source": "details",
            }
        )

    def _sort_key(r: Dict[str, Any]):
        st = r.get("status")
        pr = {"high": 0, "low": 1, "normal": 2, "unknown": 3}.get(st, 9)
        return (pr, str(r.get("key", "")))

    rows.sort(key=_sort_key)
    return rows


def _build_top_conditions(prediction: Dict[str, Any], limit: int = 4) -> List[Dict[str, Any]]:
    risk_scores = prediction.get("riskScores") or {}
    if not isinstance(risk_scores, dict):
        return []

    items = []
    for k, v in risk_scores.items():
        if not isinstance(v, dict):
            continue
        score = v.get("score", 0)
        level = v.get("level", "Low")
        reasons = v.get("reasons", []) or []
        try:
            score_f = float(score)
        except Exception:
            score_f = 0.0

        items.append(
            {
                "key": str(k),
                "score": _clamp(score_f),
                "level": str(level),
                "reasons": reasons if isinstance(reasons, list) else [],
            }
        )

    items.sort(key=lambda x: x.get("score", 0), reverse=True)
    return items[: max(1, min(limit, 8))]


def _count_markers_checked(biomarker_table: List[Dict[str, Any]], qualitative: Dict[str, Any]) -> int:
    numeric_count = sum(1 for r in biomarker_table if r.get("value") is not None)
    qual_count = 0
    if isinstance(qualitative, dict):
        for _, v in qualitative.items():
            if isinstance(v, dict):
                if v.get("result") or v.get("titer"):
                    qual_count += 1
    return numeric_count + qual_count


def finalize_report_payload(
    structured: Dict[str, Any],
    findings: List[Dict[str, Any]],
    prediction: Dict[str, Any],
) -> Dict[str, Any]:
    extraction = structured.get("extraction") or {}
    qualitative = extraction.get("qualitative") or {}

    biomarker_table = _build_biomarker_table(structured)
    top_conditions = _build_top_conditions(prediction, limit=4)

    overall_score = prediction.get("overall", {}).get("score")
    overall_level = prediction.get("overall", {}).get("level")

    if isinstance(overall_score, (int, float)):
        overall_score_f = _clamp(float(overall_score))
    else:
        overall_score_f = _clamp(float(top_conditions[0]["score"])) if top_conditions else 0.0

    if isinstance(overall_level, str) and overall_level.strip():
        overall_level_str = overall_level.strip().title()
    else:
        overall_level_str = _risk_from_score(overall_score_f)

    primary_condition = prediction.get("overall", {}).get("primaryCondition")
    if not primary_condition and top_conditions:
        primary_condition = str(top_conditions[0]["key"]).replace(" Risk", "")
    if not primary_condition:
        primary_condition = "General Health"

    abnormal_count = sum(1 for r in biomarker_table if r.get("status") in ("high", "low"))
    reactive_count = 0
    if isinstance(qualitative, dict):
        for _, v in qualitative.items():
            if isinstance(v, dict):
                res = str(v.get("result", "")).strip().lower()
                if res.startswith("reactive"):
                    reactive_count += 1

    issues_found = max(len(findings), abnormal_count + reactive_count)
    markers_checked = _count_markers_checked(biomarker_table, qualitative)

    # ✅ NEW: Combination pattern inference
    clinical_inference = infer_probable_conditions(structured)

    lab_name = structured.get("LabName") or structured.get("Laboratory") or "Unknown Lab"
    report_date = structured.get("ReportDate") or structured.get("Date") or "Unknown"

    extraction_meta = {
        "method": extraction.get("method", "digital"),
        "pages": extraction.get("pages", None),
        "warnings": extraction.get("warnings", []) or [],
        "used_llm": extraction.get("used_llm", False),
    }

    payload = {
        "date": report_date,
        "labName": lab_name,
        "overallRisk": overall_level_str,
        "primaryCondition": primary_condition,
        "issuesFound": int(issues_found),
        "markersChecked": int(markers_checked),

        "findings": findings if isinstance(findings, list) else [],

        "prediction": prediction,
        "topConditions": top_conditions,
        "biomarkerTable": biomarker_table,
        "qualitative": qualitative if isinstance(qualitative, dict) else {},

        # ✅ NEW fields for frontend
        "clinicalInference": clinical_inference,
        "probableConditions": clinical_inference.get("conditions", []),

        "extraction": extraction_meta,
    }

    return payload