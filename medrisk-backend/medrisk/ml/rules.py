from __future__ import annotations

from typing import Any, Dict, List

from .constants import CONDITIONS, SPECIALTIES_MAP


def get_gender(structured: Dict[str, Any]) -> str:
    g = (structured.get("Gender") or "").strip().lower()
    if g in ("male", "female"):
        return g
    return "unknown"


def _num(v: Any) -> float | None:
    if v is None:
        return None
    if isinstance(v, (int, float)):
        return float(v)
    try:
        return float(str(v).strip())
    except Exception:
        return None


def rule_scores(structured: Dict[str, Any]) -> Dict[str, float]:
    """Return deterministic risk scores in [0,1] based on clinical-style thresholds."""
    gender = get_gender(structured)

    hgb = _num(structured.get("Hemoglobin"))
    wbc = _num(structured.get("WBC"))  # expected x10^3/uL scale after your scaling
    tsh = _num(structured.get("TSH"))
    mpv = _num(structured.get("MPV"))
    plt = _num(structured.get("Platelet Count"))  # x10^3/uL scale after scaling
    g_f = _num(structured.get("Glucose (Fasting)"))
    g_r = _num(structured.get("Glucose (Random)"))
    chol = _num(structured.get("Total Cholesterol"))
    ldl = _num(structured.get("LDL Cholesterol"))
    hdl = _num(structured.get("HDL Cholesterol"))

    out = {c: 0.0 for c in CONDITIONS}

    # --- Anemia ---
    if hgb is not None:
        thr = 12.0 if gender == "female" else (13.5 if gender == "male" else 12.5)
        if hgb < thr:
            delta = thr - hgb
            out["Anemia"] = min(1.0, 0.55 + delta * 0.15)

    # --- Infection / inflammation ---
    if wbc is not None:
        if wbc >= 20:
            out["Infection"] = 1.0
        elif wbc >= 11:
            out["Infection"] = min(1.0, 0.55 + (wbc - 11) * 0.06)

        if wbc >= 10:
            out["Inflammation"] = min(1.0, 0.45 + (wbc - 10) * 0.05)

    if mpv is not None:
        if mpv >= 12:
            out["Inflammation"] = max(out["Inflammation"], 0.75)
        elif mpv >= 10:
            out["Inflammation"] = max(out["Inflammation"], 0.55)

    # --- Thyroid ---
    if tsh is not None:
        if tsh > 10:
            out["Hypothyroidism"] = 1.0
        elif tsh > 4.2:
            out["Hypothyroidism"] = min(1.0, 0.55 + (tsh - 4.2) * 0.06)

        if tsh < 0.1:
            out["Hyperthyroidism"] = 1.0
        elif tsh < 0.4:
            out["Hyperthyroidism"] = min(1.0, 0.55 + (0.4 - tsh) * 0.9)

    # --- Platelets ---
    if plt is not None:
        if plt < 50:
            out["Low Platelets"] = 1.0
        elif plt < 150:
            out["Low Platelets"] = min(1.0, 0.55 + (150 - plt) * 0.004)

        if plt > 800:
            out["High Platelets"] = 1.0
        elif plt > 450:
            out["High Platelets"] = min(1.0, 0.55 + (plt - 450) * 0.0015)

    # --- Diabetes ---
    if g_f is not None or g_r is not None:
        if g_f is not None and g_f >= 126:
            out["Diabetes"] = max(out["Diabetes"], min(1.0, 0.55 + (g_f - 126) * 0.008))
        if g_r is not None and g_r >= 200:
            out["Diabetes"] = max(out["Diabetes"], min(1.0, 0.55 + (g_r - 200) * 0.004))

        if out["Diabetes"] == 0.0:
            if g_f is not None and 100 <= g_f < 126:
                out["Diabetes"] = max(out["Diabetes"], 0.35)
            if g_r is not None and 140 <= g_r < 200:
                out["Diabetes"] = max(out["Diabetes"], 0.35)

    # --- Dyslipidemia ---
    dys_score = 0.0
    if chol is not None and chol >= 200:
        dys_score = max(dys_score, min(1.0, 0.55 + (chol - 200) * 0.003))
    if ldl is not None and ldl >= 130:
        dys_score = max(dys_score, min(1.0, 0.55 + (ldl - 130) * 0.004))
    if hdl is not None:
        thr_hdl = 50 if gender == "female" else (40 if gender == "male" else 45)
        if hdl < thr_hdl:
            dys_score = max(dys_score, min(1.0, 0.55 + (thr_hdl - hdl) * 0.03))
    out["Dyslipidemia"] = dys_score

    return {k: float(max(0.0, min(1.0, v))) for k, v in out.items()}


def explain(condition: str, structured: Dict[str, Any]) -> List[str]:
    """Human explanation for why a condition was flagged."""
    gender = get_gender(structured)

    hgb = _num(structured.get("Hemoglobin"))
    wbc = _num(structured.get("WBC"))
    tsh = _num(structured.get("TSH"))
    plt = _num(structured.get("Platelet Count"))
    g_f = _num(structured.get("Glucose (Fasting)"))
    g_r = _num(structured.get("Glucose (Random)"))

    bullets: List[str] = []

    if condition == "Anemia" and hgb is not None:
        thr = 12.0 if gender == "female" else (13.5 if gender == "male" else 12.5)
        bullets.append(f"Hemoglobin = {hgb:.2f} g/dL (threshold ≈ {thr:.1f}).")

    if condition == "Infection" and wbc is not None:
        bullets.append(f"WBC = {wbc:.2f} (normal ≈ 4–11).")

    if condition in ("Hypothyroidism", "Hyperthyroidism") and tsh is not None:
        bullets.append(f"TSH = {tsh:.2f} µIU/mL (normal ≈ 0.4–4.2).")

    if condition in ("Low Platelets", "High Platelets") and plt is not None:
        bullets.append(f"Platelets = {plt:.0f} (normal ≈ 150–450).")

    if condition == "Diabetes":
        if g_f is not None:
            bullets.append(f"Fasting glucose = {g_f:.0f} mg/dL.")
        if g_r is not None:
            bullets.append(f"Random glucose = {g_r:.0f} mg/dL.")

    if not bullets:
        bullets.append("Not enough biomarkers available to explain clearly.")

    return bullets


def specialties_for(condition: str) -> List[str]:
    return list(SPECIALTIES_MAP.get(condition, ["General Physician"]))
