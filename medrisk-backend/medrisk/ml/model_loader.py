from __future__ import annotations

import json
import os
from dataclasses import dataclass
from typing import Any, Dict, List, Optional

import joblib
import numpy as np


@dataclass
class ModelBundle:
    kind: str  # "multilabel" | "multiclass" | "none"
    model: Any | None
    labels: List[str]
    feature_names: List[str]
    meta: Dict[str, Any]


_BUNDLE: Optional[ModelBundle] = None


def _repo_root() -> str:
    return os.path.abspath(os.path.join(os.path.dirname(__file__), "..", ".."))


def load_model_bundle() -> ModelBundle:
    global _BUNDLE
    if _BUNDLE is not None:
        return _BUNDLE

    root = _repo_root()

    # New multilabel model
    new_model = os.path.join(root, "models", "medrisk_risk_model.joblib")
    new_meta = os.path.join(root, "models", "medrisk_risk_meta.json")

    if os.path.exists(new_model):
        model = joblib.load(new_model)
        meta: Dict[str, Any] = {}
        if os.path.exists(new_meta):
            try:
                with open(new_meta, "r", encoding="utf-8") as f:
                    meta = json.load(f)
            except Exception:
                meta = {}

        _BUNDLE = ModelBundle(
            kind="multilabel",
            model=model,
            labels=list(meta.get("labels") or []),
            feature_names=list(meta.get("features") or []),
            meta=meta,
        )
        return _BUNDLE

    # Legacy support (optional)
    old_model = os.path.join(root, "AI", "disease_model.pkl")
    old_cfg = os.path.join(root, "AI", "model_config.json")

    if os.path.exists(old_model) and os.path.exists(old_cfg):
        try:
            model = joblib.load(old_model)
            with open(old_cfg, "r", encoding="utf-8") as f:
                cfg = json.load(f)
            _BUNDLE = ModelBundle(
                kind="multiclass",
                model=model,
                labels=list(cfg.get("classes") or []),
                feature_names=list(cfg.get("features") or []),
                meta={"source": "legacy", **cfg},
            )
            return _BUNDLE
        except Exception:
            pass

    _BUNDLE = ModelBundle(kind="none", model=None, labels=[], feature_names=[], meta={})
    return _BUNDLE


def _num(v: Any) -> float:
    if v is None:
        return float("nan")
    if isinstance(v, (int, float)):
        return float(v)
    try:
        return float(str(v).strip())
    except Exception:
        return float("nan")


def _gender_female(structured: Dict[str, Any]) -> float:
    g = (structured.get("Gender") or "").strip().lower()
    if g == "female":
        return 1.0
    if g == "male":
        return 0.0
    return float("nan")


def make_X_for_bundle(bundle: ModelBundle, structured: Dict[str, Any]) -> np.ndarray:
    """
    Builds 1xN numeric input aligned to bundle.feature_names.
    Expected to match training script feature names.
    """
    row: List[float] = []
    for name in bundle.feature_names:
        if name == "GenderFemale":
            row.append(_gender_female(structured))
        else:
            row.append(_num(structured.get(name)))
    return np.array([row], dtype=float)
