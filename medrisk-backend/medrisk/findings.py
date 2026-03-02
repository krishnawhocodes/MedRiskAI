from __future__ import annotations

from typing import Any, Dict, List, Optional, Tuple

from .reference_ranges import get_reference_range, normalize_unit


_RISK_RANK = {"Low": 1, "Moderate": 2, "High": 3}


def _as_float(v: Any) -> Optional[float]:
    try:
        if v is None or isinstance(v, bool):
            return None
        if isinstance(v, (int, float)):
            return float(v)
        s = str(v).strip().replace(",", "")
        return float(s) if s else None
    except Exception:
        return None


def _fmt_range(low: Optional[float], high: Optional[float], unit: Optional[str]) -> str:
    if low is None or high is None:
        return "—"
    u = f" {unit}" if unit else ""
    return f"{low:g} – {high:g}{u}"


def _status(value: float, low: Optional[float], high: Optional[float]) -> str:
    if low is None or high is None:
        return "Unknown"
    if value < low:
        return "Low"
    if value > high:
        return "High"
    return "Normal"


def _ratio_outside(value: float, low: Optional[float], high: Optional[float]) -> float:
    if low is None or high is None:
        return 0.0
    if value < low:
        return (low - value) / max(abs(low), 1e-9)
    if value > high:
        return (value - high) / max(abs(high), 1e-9)
    return 0.0


def _severity_from_ratio(ratio: float) -> str:
    if ratio >= 0.35:
        return "High"
    if ratio >= 0.15:
        return "Moderate"
    return "Low"


def _get_details(structured: Dict[str, Any], key: str) -> Tuple[Optional[float], Optional[float], Optional[str], str]:
    ex = structured.get("extraction") if isinstance(structured.get("extraction"), dict) else {}
    details = ex.get("details") if isinstance(ex.get("details"), dict) else {}
    d = details.get(key) if isinstance(details.get(key), dict) else None

    low = _as_float(d.get("low")) if d else None
    high = _as_float(d.get("high")) if d else None
    unit = normalize_unit(d.get("unit")) if d else None
    source = str(d.get("source")) if d and d.get("source") else "report"

    if low is None or high is None:
        meta = ex.get("meta") if isinstance(ex.get("meta"), dict) else {}
        rr = get_reference_range(
            key,
            gender=meta.get("Gender"),
            pregnancy=str(meta.get("PregnancyPanel") or "").lower() == "true",
            trimester=meta.get("Trimester"),
        )
        if rr:
            low = _as_float(rr.get("low"))
            high = _as_float(rr.get("high"))
            unit = unit or normalize_unit(rr.get("unit"))
            source = "default"

    return low, high, unit, source


def build_findings(structured: Dict[str, Any]) -> List[Dict[str, Any]]:
    ex = structured.get("extraction") if isinstance(structured.get("extraction"), dict) else {}
    values = ex.get("values") if isinstance(ex.get("values"), dict) else {}
    qualitative = ex.get("qualitative") if isinstance(ex.get("qualitative"), dict) else {}

    findings: List[Dict[str, Any]] = []

    # ---- Qualitative urgent positives ----
    def add_reactive(test_key: str, name: str, specialties: List[str]) -> None:
        obj = qualitative.get(test_key) if isinstance(qualitative.get(test_key), dict) else None
        if not obj:
            return
        res = str(obj.get("result") or "").strip().lower().replace("-", "").replace(" ", "")
        if res in ("reactive", "positive"):
            findings.append(
                {
                    "biomarker": name,
                    "value": "Reactive",
                    "unit": "",
                    "normalRange": "Non-Reactive",
                    "status": "High",
                    "risk": "High",
                    "interpretation": f"{name} is Reactive. This is a screening result and requires confirmation and clinical correlation.",
                    "recommendation": "Consult a clinician promptly for confirmatory testing and next steps.",
                    "specialties": specialties,
                    "category": "Screening",
                }
            )

    add_reactive("HCV", "Hepatitis C (HCV)", ["General Physician", "Gastroenterologist", "Infectious Disease Specialist"])
    add_reactive("HBsAg", "Hepatitis B (HBsAg)", ["General Physician", "Gastroenterologist", "Infectious Disease Specialist"])
    add_reactive("HIV", "HIV Screening", ["General Physician", "Infectious Disease Specialist"])
    add_reactive("VDRL", "Syphilis Screening (VDRL/RPR)", ["General Physician", "Dermatologist", "Infectious Disease Specialist"])

    # ---- Numeric abnormalities ----
    def add_numeric(key: str, category: str, specialties: List[str]) -> None:
        if key not in values:
            return
        v = _as_float(values.get(key))
        if v is None:
            return

        low, high, unit, _src = _get_details(structured, key)
        st = _status(v, low, high)
        if st in ("Normal", "Unknown"):
            return

        ratio = _ratio_outside(v, low, high)
        risk = _severity_from_ratio(ratio)

        interp = f"{key} is {st.lower()} compared to the reference range."
        reco = "Discuss with a clinician for interpretation with your symptoms and history."

        # Higher-quality marker-specific guidance
        if key == "Hemoglobin" and st == "Low":
            risk = "High" if v < 8 else ("Moderate" if v < 10 else "Low")
            interp = "Hemoglobin is low, which can indicate anemia (iron deficiency, B12/folate deficiency, chronic disease, etc.)."
            reco = "Consider iron studies, B12/folate, and clinician evaluation—especially if tiredness/breathlessness."
        if key == "HbA1c":
            if v >= 6.5:
                risk = "High"
                interp = "HbA1c is in the diabetes range."
                reco = "Consult a clinician for diabetes confirmation and management; lifestyle and medication guidance may be needed."
            elif v >= 5.7:
                risk = "Moderate"
                interp = "HbA1c suggests prediabetes (increased diabetes risk)."
                reco = "Diet + activity changes help; repeat testing as advised by clinician."
        if key == "TSH":
            if st == "High":
                risk = "High" if v >= 10 else "Moderate"
                interp = "TSH is high which can suggest hypothyroidism (interpret with Free T4)."
                reco = "Discuss thyroid profile and symptoms with an endocrinologist/physician."
            if st == "Low":
                risk = "High" if v <= 0.1 else "Moderate"
                interp = "TSH is low which can suggest hyperthyroidism (interpret with Free T4/T3)."
                reco = "Consult an endocrinologist/physician for follow-up testing and management."
        if key == "Vitamin D (25-OH)" and st == "Low":
            risk = "High" if v < 20 else "Moderate"
            interp = "Vitamin D is low (deficiency/insufficiency)."
            reco = "Discuss supplementation and safe sun exposure with a clinician."
        if key == "Vitamin B12" and st == "Low":
            risk = "High" if v < 200 else "Moderate"
            interp = "Vitamin B12 is low/borderline. Low B12 can cause anemia and nerve symptoms."
            reco = "Discuss supplementation and evaluation of diet/absorption with a clinician."
        if key == "Triglycerides" and st == "High":
            risk = "High" if v >= 500 else "Moderate"
            interp = "Triglycerides are elevated."
            reco = "Reduce sugar/refined carbs, limit alcohol, and consult clinician especially if very high."
        if key == "LDL Cholesterol" and st == "High":
            risk = "High" if v >= 190 else "Moderate"
            interp = "LDL cholesterol is high."
            reco = "Heart-healthy diet + activity; consider clinician review for cardiovascular risk."

        findings.append(
            {
                "biomarker": key,
                "value": v,
                "unit": unit or "",
                "normalRange": _fmt_range(low, high, unit),
                "status": st,
                "risk": risk,
                "interpretation": interp,
                "recommendation": reco,
                "specialties": specialties,
                "category": category,
            }
        )

    # Core markers you want findings for
    cfg = [
        ("Hemoglobin", "CBC", ["General Physician", "Hematologist"]),
        ("WBC", "CBC", ["General Physician"]),
        ("Platelet Count", "CBC", ["General Physician", "Hematologist"]),
        ("TSH", "Thyroid", ["Endocrinologist", "General Physician"]),
        ("Free T4", "Thyroid", ["Endocrinologist", "General Physician"]),
        ("Free T3", "Thyroid", ["Endocrinologist", "General Physician"]),
        ("Glucose (Fasting)", "Diabetes", ["Diabetologist", "Endocrinologist", "General Physician"]),
        ("Glucose (Random)", "Diabetes", ["Diabetologist", "Endocrinologist", "General Physician"]),
        ("HbA1c", "Diabetes", ["Diabetologist", "Endocrinologist", "General Physician"]),
        ("LDL Cholesterol", "Lipids", ["Cardiologist", "General Physician"]),
        ("HDL Cholesterol", "Lipids", ["Cardiologist", "General Physician"]),
        ("Triglycerides", "Lipids", ["Cardiologist", "General Physician"]),
        ("Creatinine", "Kidney", ["Nephrologist", "General Physician"]),
        ("eGFR", "Kidney", ["Nephrologist", "General Physician"]),
        ("Urea", "Kidney", ["Nephrologist", "General Physician"]),
        ("ALT (SGPT)", "Liver", ["Gastroenterologist", "General Physician"]),
        ("AST (SGOT)", "Liver", ["Gastroenterologist", "General Physician"]),
        ("Total Bilirubin", "Liver", ["Gastroenterologist", "General Physician"]),
        ("Vitamin D (25-OH)", "Vitamins", ["General Physician"]),
        ("Vitamin B12", "Vitamins", ["General Physician", "Neurologist"]),
        ("CRP", "Inflammation", ["General Physician"]),
        ("ESR", "Inflammation", ["General Physician"]),
    ]

    for key, cat, specs in cfg:
        add_numeric(key, cat, specs)

    findings.sort(key=lambda f: _RISK_RANK.get(str(f.get("risk") or ""), 0), reverse=True)
    return findings
