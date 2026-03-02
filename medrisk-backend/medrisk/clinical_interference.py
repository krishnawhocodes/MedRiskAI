from __future__ import annotations

"""
clinical_inference.py

- Explainable, rule-based "pattern inference" on top of biomarker highs/lows.
- Suggests possible conditions based on *combinations* of markers.
- Provides ranked candidates + suggested specialties + next steps.

⚠️ NOT a diagnosis. Screening-style only.
"""

from dataclasses import dataclass
from typing import Any, Dict, List, Optional, Tuple

from .reference_ranges import get_reference_range, normalize_unit


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


def _clamp(x: float, lo: float = 0.0, hi: float = 1.0) -> float:
    return max(lo, min(hi, x))


def _get_identity(structured: Dict[str, Any]) -> Tuple[Optional[str], bool, Optional[str]]:
    ex = structured.get("extraction") if isinstance(structured.get("extraction"), dict) else {}
    meta = ex.get("meta") if isinstance(ex.get("meta"), dict) else {}

    gender = structured.get("Gender") or meta.get("Gender") or meta.get("gender")
    pregnancy_panel = structured.get("PregnancyPanel") or meta.get("PregnancyPanel") or meta.get("pregnancy")
    trimester = structured.get("Trimester") or meta.get("Trimester") or meta.get("trimester")

    preg_str = str(pregnancy_panel or "").strip().lower()
    pregnancy = preg_str in ("true", "yes", "1", "y")

    return (str(gender).strip() if gender else None, pregnancy, str(trimester).strip() if trimester else None)


def _get_range_from_details(structured: Dict[str, Any], key: str) -> Tuple[Optional[float], Optional[float], Optional[str]]:
    ex = structured.get("extraction") if isinstance(structured.get("extraction"), dict) else {}
    details = ex.get("details") if isinstance(ex.get("details"), dict) else {}
    d = details.get(key) if isinstance(details.get(key), dict) else None
    if not d:
        return (None, None, None)
    low = _as_float(d.get("low"))
    high = _as_float(d.get("high"))
    unit = normalize_unit(d.get("unit"))
    return (low, high, unit)


def _get_range(structured: Dict[str, Any], key: str) -> Tuple[Optional[float], Optional[float], Optional[str], str]:
    low, high, unit = _get_range_from_details(structured, key)
    if low is not None or high is not None:
        return (low, high, unit, "details")

    gender, pregnancy, trimester = _get_identity(structured)
    rr = get_reference_range(key, gender=gender, pregnancy=pregnancy, trimester=trimester)
    if not rr:
        return (None, None, None, "none")

    return (_as_float(rr.get("low")), _as_float(rr.get("high")), normalize_unit(rr.get("unit")), "fallback")


def _status(value: float, low: Optional[float], high: Optional[float]) -> str:
    if low is None and high is None:
        return "unknown"
    if low is not None and value < low:
        return "low"
    if high is not None and value > high:
        return "high"
    return "normal"


def _outside_ratio(value: float, low: Optional[float], high: Optional[float]) -> float:
    if low is None and high is None:
        return 0.0
    if low is not None and value < low:
        return (low - value) / max(abs(low), 1e-9)
    if high is not None and value > high:
        return (value - high) / max(abs(high), 1e-9)
    return 0.0


def _sev_label(r: float) -> str:
    if r >= 0.50:
        return "High"
    if r >= 0.20:
        return "Moderate"
    if r > 0:
        return "Low"
    return "Normal"


def _marker(structured: Dict[str, Any], key: str) -> Optional[Dict[str, Any]]:
    val = _as_float(structured.get(key))
    if val is None:
        return None
    low, high, unit, source = _get_range(structured, key)
    st = _status(val, low, high)
    rr = _outside_ratio(val, low, high)
    return {
        "key": key,
        "value": val,
        "unit": unit,
        "low": low,
        "high": high,
        "status": st,
        "severity": _sev_label(rr),
        "source": source,
    }


def _v(structured: Dict[str, Any], key: str) -> Optional[float]:
    return _as_float(structured.get(key))


def _high(structured: Dict[str, Any], key: str) -> bool:
    m = _marker(structured, key)
    return bool(m and m["status"] == "high")


def _low(structured: Dict[str, Any], key: str) -> bool:
    m = _marker(structured, key)
    return bool(m and m["status"] == "low")


@dataclass
class Candidate:
    name: str
    confidence: float
    severity: str
    why: List[str]
    supporting_markers: List[Dict[str, Any]]
    suggested_specialties: List[str]
    urgency: str  # routine | soon | urgent
    next_steps: List[str]
    tags: List[str]


def _candidate(
    name: str,
    confidence: float,
    severity: str,
    why: List[str],
    markers: List[Optional[Dict[str, Any]]],
    specialties: List[str],
    urgency: str,
    next_steps: List[str],
    tags: List[str],
) -> Candidate:
    return Candidate(
        name=name,
        confidence=_clamp(confidence, 0.0, 0.99),
        severity=severity,
        why=[w for w in why if w],
        supporting_markers=[m for m in markers if isinstance(m, dict)],
        suggested_specialties=specialties,
        urgency=urgency,
        next_steps=next_steps,
        tags=tags,
    )


def infer_probable_conditions(structured: Dict[str, Any]) -> Dict[str, Any]:
    candidates: List[Candidate] = []

    # -----------------------------
    # Diabetes / glycemic patterns
    # -----------------------------
    fg = _v(structured, "Glucose (Fasting)")
    rg = _v(structured, "Glucose (Random)")
    a1c = _v(structured, "HbA1c")

    fg_m = _marker(structured, "Glucose (Fasting)")
    rg_m = _marker(structured, "Glucose (Random)")
    a1c_m = _marker(structured, "HbA1c")

    diabetes_hits = 0
    if fg is not None and fg >= 126:
        diabetes_hits += 1
    if a1c is not None and a1c >= 6.5:
        diabetes_hits += 1
    if rg is not None and rg >= 200:
        diabetes_hits += 1

    if diabetes_hits >= 2:
        candidates.append(
            _candidate(
                name="Possible Diabetes (screening pattern)",
                confidence=0.88,
                severity="High",
                why=["Two or more glucose indicators are in a diabetes-range pattern (needs confirmation)."],
                markers=[fg_m, a1c_m, rg_m],
                specialties=["Endocrinologist", "Diabetologist", "General Physician"],
                urgency="soon",
                next_steps=[
                    "Discuss with a clinician; consider repeat fasting glucose and/or HbA1c for confirmation.",
                    "If symptoms (excess thirst/urination, weight loss), seek prompt medical advice.",
                ],
                tags=["diabetes", "glycemic"],
            )
        )
    else:
        pre_hits = 0
        if fg is not None and 100 <= fg <= 125:
            pre_hits += 1
        if a1c is not None and 5.7 <= a1c <= 6.4:
            pre_hits += 1
        if pre_hits >= 1:
            candidates.append(
                _candidate(
                    name="Possible Prediabetes / impaired glucose regulation",
                    confidence=0.72 if pre_hits == 1 else 0.80,
                    severity="Moderate",
                    why=["Glucose pattern suggests impaired regulation (confirm with clinician)."],
                    markers=[fg_m, a1c_m],
                    specialties=["Endocrinologist", "General Physician"],
                    urgency="routine",
                    next_steps=[
                        "Consider repeating fasting glucose/HbA1c in 3–6 months as advised.",
                        "Lifestyle: balanced diet and regular exercise.",
                    ],
                    tags=["prediabetes", "glycemic"],
                )
            )

    if fg is not None and fg < 70:
        candidates.append(
            _candidate(
                name="Low blood glucose pattern (possible hypoglycemia)",
                confidence=0.70,
                severity="Moderate",
                why=["Fasting glucose is below typical range; correlate with symptoms/medications."],
                markers=[fg_m],
                specialties=["General Physician", "Endocrinologist"],
                urgency="soon",
                next_steps=[
                    "If dizzy/confused/sweaty, take quick sugar and seek medical help.",
                    "Review medications/fasting with your clinician.",
                ],
                tags=["hypoglycemia", "glycemic"],
            )
        )

    # -----------------------------
    # Thyroid patterns
    # -----------------------------
    tsh = _v(structured, "TSH")
    ft4 = _v(structured, "Free T4")
    ft3 = _v(structured, "Free T3")
    tsh_m = _marker(structured, "TSH")
    ft4_m = _marker(structured, "Free T4")
    ft3_m = _marker(structured, "Free T3")

    if tsh is not None:
        if tsh > 4.2 and (ft4 is not None and ft4 < 0.8):
            candidates.append(
                _candidate(
                    name="Possible Hypothyroidism pattern",
                    confidence=0.84,
                    severity="Moderate",
                    why=["TSH is high and Free T4 is low (pattern consistent with hypothyroidism)."],
                    markers=[tsh_m, ft4_m],
                    specialties=["Endocrinologist"],
                    urgency="routine",
                    next_steps=["Discuss thyroid panel with a clinician; repeat testing may be needed."],
                    tags=["thyroid", "hypothyroidism"],
                )
            )
        elif tsh > 4.2:
            candidates.append(
                _candidate(
                    name="Possible Subclinical hypothyroidism pattern",
                    confidence=0.70,
                    severity="Low",
                    why=["TSH is high while Free T4 is not clearly low (may be subclinical)."],
                    markers=[tsh_m, ft4_m],
                    specialties=["Endocrinologist", "General Physician"],
                    urgency="routine",
                    next_steps=["Consider repeat TSH/Free T4 in 6–12 weeks as advised."],
                    tags=["thyroid", "subclinical"],
                )
            )
        elif tsh < 0.27 and ((ft4 is not None and ft4 > 1.8) or (ft3 is not None and ft3 > 4.2)):
            candidates.append(
                _candidate(
                    name="Possible Hyperthyroidism pattern",
                    confidence=0.80,
                    severity="Moderate",
                    why=["TSH is low with elevated thyroid hormone level(s)."],
                    markers=[tsh_m, ft4_m, ft3_m],
                    specialties=["Endocrinologist"],
                    urgency="soon",
                    next_steps=["Consult a clinician for confirmation and cause evaluation."],
                    tags=["thyroid", "hyperthyroidism"],
                )
            )

    # -----------------------------
    # Anemia patterns (CBC combos)
    # -----------------------------
    hb = _v(structured, "Hemoglobin")
    mcv = _v(structured, "MCV")
    mch = _v(structured, "MCH")
    rdw = _v(structured, "RDW")
    hb_m = _marker(structured, "Hemoglobin")
    mcv_m = _marker(structured, "MCV")
    mch_m = _marker(structured, "MCH")
    rdw_m = _marker(structured, "RDW")

    if hb is not None and _low(structured, "Hemoglobin"):
        if mcv is not None and mcv < 80:
            conf = 0.78
            why = ["Hemoglobin is low with low MCV (microcytic anemia pattern)."]
            if rdw is not None and rdw > 14.5:
                conf += 0.08
                why.append("RDW is high, which can be seen with iron deficiency.")
            if mch is not None and mch < 27:
                conf += 0.05
                why.append("MCH is low, supporting microcytosis.")
            candidates.append(
                _candidate(
                    name="Possible Iron deficiency anemia pattern",
                    confidence=conf,
                    severity="Moderate",
                    why=why,
                    markers=[hb_m, mcv_m, rdw_m, mch_m],
                    specialties=["General Physician", "Hematologist"],
                    urgency="routine",
                    next_steps=["Discuss iron studies (ferritin, iron/TIBC) with a clinician."],
                    tags=["anemia", "iron_deficiency"],
                )
            )
        elif mcv is not None and mcv > 100:
            candidates.append(
                _candidate(
                    name="Possible B12/Folate deficiency anemia pattern",
                    confidence=0.74,
                    severity="Moderate",
                    why=["Hemoglobin is low with high MCV (macrocytic anemia pattern)."],
                    markers=[hb_m, mcv_m, _marker(structured, "Vitamin B12"), _marker(structured, "Folate")],
                    specialties=["General Physician", "Hematologist"],
                    urgency="routine",
                    next_steps=["Discuss B12/folate evaluation with a clinician."],
                    tags=["anemia", "b12_folate"],
                )
            )
        else:
            candidates.append(
                _candidate(
                    name="Possible anemia pattern (non-specific)",
                    confidence=0.60,
                    severity="Low",
                    why=["Hemoglobin is below range; indices help determine cause."],
                    markers=[hb_m, mcv_m, rdw_m],
                    specialties=["General Physician"],
                    urgency="routine",
                    next_steps=["Discuss CBC with a clinician; additional tests may be needed."],
                    tags=["anemia"],
                )
            )

        if hb is not None and hb < 7.0:
            candidates.append(
                _candidate(
                    name="Severely low hemoglobin (urgent evaluation)",
                    confidence=0.85,
                    severity="High",
                    why=["Hemoglobin is very low; urgent evaluation is recommended if symptomatic."],
                    markers=[hb_m],
                    specialties=["Emergency Care", "Hematologist"],
                    urgency="urgent",
                    next_steps=["Seek urgent medical evaluation, especially if shortness of breath/chest pain."],
                    tags=["urgent", "anemia"],
                )
            )

    # -----------------------------
    # Kidney pattern
    # -----------------------------
    cr = _v(structured, "Creatinine")
    egfr = _v(structured, "eGFR")
    cr_m = _marker(structured, "Creatinine")
    egfr_m = _marker(structured, "eGFR")

    kidney_hits = 0
    if egfr is not None and egfr < 60:
        kidney_hits += 1
    if cr is not None and _high(structured, "Creatinine"):
        kidney_hits += 1

    if kidney_hits >= 1:
        candidates.append(
            _candidate(
                name="Possible reduced kidney function pattern",
                confidence=0.70 + 0.10 * (kidney_hits - 1),
                severity="Moderate" if (egfr is not None and egfr < 45) else "Low",
                why=["Kidney function markers are outside reference range."],
                markers=[egfr_m, cr_m, _marker(structured, "BUN"), _marker(structured, "Urea")],
                specialties=["Nephrologist", "General Physician"],
                urgency="soon" if (egfr is not None and egfr < 45) else "routine",
                next_steps=["Discuss creatinine/eGFR with a clinician; repeat tests may be advised."],
                tags=["kidney"],
            )
        )

    # -----------------------------
    # Liver pattern
    # -----------------------------
    alt = _v(structured, "ALT (SGPT)")
    ast = _v(structured, "AST (SGOT)")
    alp = _v(structured, "Alkaline Phosphatase")
    tb = _v(structured, "Total Bilirubin")

    liver_hits = 0
    if alt is not None and _high(structured, "ALT (SGPT)"):
        liver_hits += 1
    if ast is not None and _high(structured, "AST (SGOT)"):
        liver_hits += 1
    if tb is not None and _high(structured, "Total Bilirubin"):
        liver_hits += 1
    if alp is not None and _high(structured, "Alkaline Phosphatase"):
        liver_hits += 1

    if liver_hits >= 2:
        candidates.append(
            _candidate(
                name="Possible liver injury / cholestasis pattern",
                confidence=0.76 + 0.05 * (liver_hits - 2),
                severity="High" if ((alt or 0) > 200 or (ast or 0) > 200 or (tb or 0) > 3) else "Moderate",
                why=["Multiple liver-related markers are elevated; correlate with symptoms/history."],
                markers=[_marker(structured, "ALT (SGPT)"), _marker(structured, "AST (SGOT)"), _marker(structured, "Alkaline Phosphatase"),
                         _marker(structured, "Total Bilirubin"), _marker(structured, "Direct Bilirubin")],
                specialties=["Gastroenterologist", "Hepatologist", "General Physician"],
                urgency="soon" if ((alt or 0) > 200 or (ast or 0) > 200 or (tb or 0) > 3) else "routine",
                next_steps=["Discuss LFTs with a clinician; repeat tests/ultrasound may be needed."],
                tags=["liver"],
            )
        )

    # -----------------------------
    # Inflammation / infection
    # -----------------------------
    infl_hits = 0
    if _v(structured, "WBC") is not None and _high(structured, "WBC"):
        infl_hits += 1
    if _v(structured, "CRP") is not None and _high(structured, "CRP"):
        infl_hits += 1
    if _v(structured, "ESR") is not None and _high(structured, "ESR"):
        infl_hits += 1
    if infl_hits >= 2:
        candidates.append(
            _candidate(
                name="Possible infection/inflammation pattern",
                confidence=0.72 + 0.06 * (infl_hits - 2),
                severity="Moderate",
                why=["Two or more inflammation markers are elevated (non-specific)."],
                markers=[_marker(structured, "WBC"), _marker(structured, "CRP"), _marker(structured, "ESR")],
                specialties=["General Physician"],
                urgency="soon",
                next_steps=["If fever/pain/cough/urinary symptoms exist, seek evaluation."],
                tags=["inflammation"],
            )
        )

    # -----------------------------
    # Cardiometabolic combo pattern
    # -----------------------------
    cardio_hits = 0
    if _v(structured, "Triglycerides") is not None and _high(structured, "Triglycerides"):
        cardio_hits += 1
    if _v(structured, "HDL Cholesterol") is not None and _low(structured, "HDL Cholesterol"):
        cardio_hits += 1
    if _v(structured, "LDL Cholesterol") is not None and _high(structured, "LDL Cholesterol"):
        cardio_hits += 1
    if (fg is not None and fg >= 100) or (a1c is not None and a1c >= 5.7):
        cardio_hits += 1

    if cardio_hits >= 3:
        candidates.append(
            _candidate(
                name="Cardiometabolic risk pattern (lipids + glucose combination)",
                confidence=0.78,
                severity="Moderate",
                why=["Combination of dyslipidemia markers + impaired glucose markers increases cardiometabolic risk."],
                markers=[_marker(structured, "Triglycerides"), _marker(structured, "HDL Cholesterol"), _marker(structured, "LDL Cholesterol"),
                         fg_m, a1c_m],
                specialties=["General Physician", "Endocrinologist", "Cardiologist"],
                urgency="routine",
                next_steps=["Discuss overall risk (BP, family history, weight) with a clinician."],
                tags=["cardiometabolic"],
            )
        )

    # -----------------------------
    # Blood pressure patterns (if provided)
    # -----------------------------
    sbp = _v(structured, "Systolic BP")
    dbp = _v(structured, "Diastolic BP")

    if sbp is not None or dbp is not None:
        sbp_m = {"key": "Systolic BP", "value": sbp, "unit": "mmHg", "low": None, "high": None, "status": "unknown", "severity": "Normal", "source": "manual"} if sbp is not None else None
        dbp_m = {"key": "Diastolic BP", "value": dbp, "unit": "mmHg", "low": None, "high": None, "status": "unknown", "severity": "Normal", "source": "manual"} if dbp is not None else None

        if (sbp is not None and sbp >= 180) or (dbp is not None and dbp >= 120):
            candidates.append(
                _candidate(
                    name="Very high blood pressure pattern (urgent evaluation)",
                    confidence=0.85,
                    severity="High",
                    why=["Blood pressure is in a very high range; urgent assessment recommended, especially with symptoms."],
                    markers=[sbp_m, dbp_m],
                    specialties=["Emergency Care"],
                    urgency="urgent",
                    next_steps=["Seek urgent care if chest pain, breathlessness, weakness, vision changes, severe headache."],
                    tags=["urgent", "blood_pressure"],
                )
            )
        elif (sbp is not None and sbp >= 130) or (dbp is not None and dbp >= 80):
            candidates.append(
                _candidate(
                    name="High blood pressure screening pattern",
                    confidence=0.70,
                    severity="Moderate" if ((sbp or 0) >= 140 or (dbp or 0) >= 90) else "Low",
                    why=["BP above normal range; repeated measurements needed for diagnosis."],
                    markers=[sbp_m, dbp_m],
                    specialties=["General Physician", "Cardiologist"],
                    urgency="routine",
                    next_steps=["Measure BP on multiple days/home monitoring; discuss trends with clinician."],
                    tags=["blood_pressure"],
                )
            )
        elif (sbp is not None and sbp < 90) or (dbp is not None and dbp < 60):
            candidates.append(
                _candidate(
                    name="Low blood pressure pattern",
                    confidence=0.60,
                    severity="Low",
                    why=["BP on the lower side; correlate with symptoms (dizziness/fainting)."],
                    markers=[sbp_m, dbp_m],
                    specialties=["General Physician"],
                    urgency="routine",
                    next_steps=["If dizziness/fainting, seek evaluation; hydration and medication review may help."],
                    tags=["blood_pressure"],
                )
            )

    # -----------------------------
    # Electrolyte urgent patterns
    # -----------------------------
    k = _v(structured, "Potassium")
    na = _v(structured, "Sodium")
    if k is not None and k >= 6.0:
        candidates.append(
            _candidate(
                name="High potassium (urgent evaluation)",
                confidence=0.85,
                severity="High",
                why=["Potassium is very high; can affect heart rhythm."],
                markers=[_marker(structured, "Potassium")],
                specialties=["Emergency Care"],
                urgency="urgent",
                next_steps=["Seek urgent medical evaluation, especially if weakness/palpitations or kidney disease."],
                tags=["urgent", "electrolytes"],
            )
        )
    if na is not None and na <= 125:
        candidates.append(
            _candidate(
                name="Low sodium (urgent evaluation)",
                confidence=0.80,
                severity="High",
                why=["Sodium is very low; severe hyponatremia can be dangerous."],
                markers=[_marker(structured, "Sodium")],
                specialties=["Emergency Care"],
                urgency="urgent",
                next_steps=["Seek urgent evaluation if confusion, seizures, severe headache, persistent vomiting."],
                tags=["urgent", "electrolytes"],
            )
        )

    # Vitamins
    if _v(structured, "Vitamin D (25-OH)") is not None and _low(structured, "Vitamin D (25-OH)"):
        candidates.append(
            _candidate(
                name="Vitamin D deficiency/insufficiency pattern",
                confidence=0.70,
                severity="Low",
                why=["Vitamin D is below reference range; common and treatable."],
                markers=[_marker(structured, "Vitamin D (25-OH)")],
                specialties=["General Physician"],
                urgency="routine",
                next_steps=["Discuss supplementation dose/duration with clinician; recheck as advised."],
                tags=["vitamin_d"],
            )
        )

    # Rank
    urgency_rank = {"urgent": 0, "soon": 1, "routine": 2}
    sev_rank = {"High": 0, "Moderate": 1, "Low": 2, "Normal": 3}

    candidates.sort(
        key=lambda c: (
            urgency_rank.get(c.urgency, 9),
            -c.confidence,
            sev_rank.get(c.severity, 9),
            c.name,
        )
    )

    out = []
    for c in candidates[:8]:
        out.append(
            {
                "name": c.name,
                "confidence": round(float(c.confidence), 2),
                "severity": c.severity,
                "urgency": c.urgency,
                "why": c.why,
                "suggestedSpecialties": c.suggested_specialties,
                "nextSteps": c.next_steps,
                "supportingMarkers": c.supporting_markers,
                "tags": c.tags,
            }
        )

    return {
        "top": out[0] if out else None,
        "conditions": out,
        "notes": [
            "This is an automated screening-style interpretation, not a diagnosis.",
            "Confirm abnormal results with a qualified clinician who knows your symptoms and history.",
        ],
    }