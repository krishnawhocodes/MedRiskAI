from __future__ import annotations

from typing import Any, Dict, List, Optional

import numpy as np

from .constants import CONDITIONS, P_HIGH, P_LOW, P_MODERATE, SPECIALTIES_MAP
from .model_loader import load_model_bundle, make_X_for_bundle
from .rules import explain, rule_scores


def _clamp(x: float, lo: float = 0.0, hi: float = 100.0) -> float:
    return max(lo, min(hi, x))


def _level_from_prob(p: float) -> str:
    if p >= P_HIGH:
        return "High"
    if p >= P_MODERATE:
        return "Moderate"
    if p >= P_LOW:
        return "Low"
    return "Low"


def _prob_to_score(p: float) -> float:
    return _clamp(float(p) * 100.0)


def _as_float(x: Any) -> Optional[float]:
    try:
        if isinstance(x, (int, float)):
            return float(x)
        return None
    except Exception:
        return None


def _safe_proba_matrix(pred_proba: Any, labels: List[str]) -> Dict[str, float]:
    """Normalize various sklearn predict_proba shapes into {label: p1}."""
    if pred_proba is None:
        return {}

    # Common case: ndarray shape (1, n_labels)
    if isinstance(pred_proba, np.ndarray):
        arr = pred_proba
        if arr.ndim == 2 and arr.shape[0] >= 1 and arr.shape[1] == len(labels):
            return {labels[i]: float(arr[0, i]) for i in range(len(labels))}

    # Some multilabel estimators return list of arrays per label (n_samples, 2)
    if isinstance(pred_proba, list) and len(pred_proba) == len(labels):
        out: Dict[str, float] = {}
        for i, a in enumerate(pred_proba):
            try:
                aa = np.asarray(a)
                # pick probability of positive class
                if aa.ndim == 2 and aa.shape[0] >= 1:
                    if aa.shape[1] == 2:
                        out[labels[i]] = float(aa[0, 1])
                    else:
                        out[labels[i]] = float(aa[0, 0])
            except Exception:
                continue
        return out

    return {}


def _actions_for(condition: str) -> List[str]:
    base = [
        "Consult a clinician for interpretation with your symptoms and history.",
        "Repeat testing if advised, especially if values are borderline or symptoms persist.",
    ]

    extras: Dict[str, List[str]] = {
        "Anemia": ["Consider iron studies (ferritin), B12 and folate if hemoglobin is low."],
        "Diabetes": ["Consider repeat fasting glucose / HbA1c and lifestyle changes (diet, activity)."],
        "Hypothyroidism": ["Consider thyroid panel (TSH + Free T4) and follow-up if symptomatic."],
        "Hyperthyroidism": ["Consider thyroid panel (TSH + Free T4/T3) and follow-up if symptomatic."],
        "Dyslipidemia": ["Consider cardiovascular risk discussion (lipids + BP + lifestyle)."],
        "Low Platelets": ["If very low platelets or bleeding, seek urgent medical care."],
        "High Platelets": ["Discuss repeat CBC and possible secondary causes with a clinician."],
        "Infection": ["If fever or acute symptoms, seek medical evaluation."],
        "Inflammation": ["Inflammation signals are non-specific; correlate clinically."],
    }

    return base + extras.get(condition, [])


def predict_health_risks(structured: Dict[str, Any]) -> Dict[str, Any]:
    """Hybrid risk prediction.

    Priority order:
    1) If a trained sklearn bundle exists (models/medrisk_risk_model.joblib), use it.
    2) Otherwise, fall back to deterministic rules (no model required).

    Output schema is stable and frontend-friendly:
    {
      overall: {score, level, primaryCondition},
      riskScores: {"Anemia Risk": {score, level, reasons, actions, specialties, probability}},
      flags: {},
      engine: {...},
      raw_probabilities: {...}  # removed by main.py to keep response small
    }
    """

    bundle = load_model_bundle()

    probabilities: Dict[str, float] = {}
    engine_name = "rules_v1"
    engine_meta: Dict[str, Any] = {"kind": bundle.kind}

    if bundle.kind in ("multilabel", "multiclass") and bundle.model is not None:
        try:
            X = make_X_for_bundle(bundle, structured)

            if bundle.kind == "multilabel":
                pred_proba = None
                # Pipeline supports predict_proba; if not, fallback
                if hasattr(bundle.model, "predict_proba"):
                    pred_proba = bundle.model.predict_proba(X)
                probabilities = _safe_proba_matrix(pred_proba, bundle.labels)
                # Keep only known CONDITIONS (safe for frontend)
                probabilities = {k: float(v) for k, v in probabilities.items() if k in CONDITIONS}

                engine_name = "ml_logreg_multilabel_v1"
                engine_meta.update({
                    "trained_on": bundle.meta.get("trained_on"),
                    "samples": bundle.meta.get("samples"),
                    "metrics": bundle.meta.get("metrics"),
                    "features": bundle.feature_names,
                    "labels": bundle.labels,
                })

            elif bundle.kind == "multiclass":
                # legacy model: predict one class
                if hasattr(bundle.model, "predict_proba"):
                    proba = bundle.model.predict_proba(X)
                    if isinstance(proba, np.ndarray) and proba.ndim == 2 and proba.shape[0] >= 1:
                        for i, lab in enumerate(bundle.labels):
                            if lab in CONDITIONS:
                                probabilities[lab] = float(proba[0, i])
                engine_name = "ml_legacy_multiclass"
                engine_meta.update({"source": bundle.meta.get("source", "legacy")})

        except Exception:
            # Don't fail the whole request if model predict fails
            probabilities = {}

    # Fallback if no model probs
    if not probabilities:
        p = rule_scores(structured)
        probabilities = {k: float(p.get(k, 0.0)) for k in CONDITIONS}
        engine_name = "rules_v1"
        engine_meta.update({"source": "deterministic_thresholds"})

    # Build riskScores payload
    risk_scores: Dict[str, Dict[str, Any]] = {}
    best_condition: Optional[str] = None
    best_score: float = -1.0

    for cond in CONDITIONS:
        prob = float(probabilities.get(cond, 0.0))
        score = _prob_to_score(prob)
        level = _level_from_prob(prob)

        if score > best_score:
            best_score = score
            best_condition = cond

        risk_scores[f"{cond} Risk"] = {
            "key": f"{cond} Risk",
            "score": score,
            "level": level,
            "probability": prob,
            "reasons": explain(cond, structured),
            "actions": _actions_for(cond),
            "specialties": list(SPECIALTIES_MAP.get(cond, ["General Physician"])),
        }

    overall_score = _clamp(best_score if best_score >= 0 else 0.0)
    best_prob = float(probabilities.get(best_condition, 0.0)) if best_condition else 0.0
    overall_level = _level_from_prob(best_prob)

    return {
        "overall": {
            "score": float(overall_score),
            "level": overall_level,
            "primaryCondition": best_condition or "General Health",
        },
        "riskScores": risk_scores,
        "flags": {},
        "engine": {
            "name": engine_name,
            "meta": engine_meta,
            "notes": "Model outputs are probabilistic. This is not a medical diagnosis.",
        },
        "raw_probabilities": probabilities,
    }