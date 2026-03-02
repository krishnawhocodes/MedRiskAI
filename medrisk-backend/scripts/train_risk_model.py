from __future__ import annotations

import json
import os
from typing import Dict, Tuple

import numpy as np
import pandas as pd
import joblib

from sklearn.model_selection import train_test_split
from sklearn.pipeline import Pipeline
from sklearn.impute import SimpleImputer
from sklearn.preprocessing import StandardScaler
from sklearn.multiclass import OneVsRestClassifier
from sklearn.linear_model import LogisticRegression
from sklearn.metrics import f1_score, roc_auc_score, classification_report


# Must match backend predictor labels
LABELS = [
    "Anemia",
    "Infection",
    "Inflammation",
    "Hypothyroidism",
    "Hyperthyroidism",
    "Low Platelets",
    "High Platelets",
    "Diabetes",
    "Dyslipidemia",
]

FEATURES = [
    "Hemoglobin",
    "WBC",                 # expected x10^3/uL scale
    "Platelet Count",      # expected x10^3/uL scale
    "MPV",
    "TSH",
    "Glucose (Fasting)",
    "Glucose (Random)",
    "Total Cholesterol",
    "LDL Cholesterol",
    "HDL Cholesterol",
    "GenderFemale",        # 1 female, 0 male, NaN unknown
]


def repo_root() -> str:
    # scripts/ -> medrisk-backend/
    return os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))


def sigmoid(x: np.ndarray) -> np.ndarray:
    # safe sigmoid
    with np.errstate(over="ignore"):
        return 1.0 / (1.0 + np.exp(-x))


def make_synthetic(n: int = 20000, seed: int = 7) -> Tuple[pd.DataFrame, pd.DataFrame]:
    """
    Generate synthetic labs with realistic-ish distributions and label them with soft probabilities.
    This is a strong baseline model UNTIL you train on real labeled clinical data.
    """
    rng = np.random.default_rng(seed)

    gender_female = rng.choice([0.0, 1.0, np.nan], size=n, p=[0.47, 0.47, 0.06])

    # Hemoglobin (g/dL)
    hb = rng.normal(loc=13.5, scale=1.8, size=n)
    hb = np.clip(hb, 6.0, 20.0)

    # WBC (x10^3/uL)
    wbc = rng.normal(loc=7.0, scale=2.2, size=n)
    spikes = rng.random(n) < 0.10
    wbc[spikes] += rng.normal(7.0, 3.0, spikes.sum())
    wbc = np.clip(wbc, 0.5, 35.0)

    # Platelets (x10^3/uL)
    plt = rng.normal(loc=280.0, scale=85.0, size=n)
    low_spike = rng.random(n) < 0.06
    high_spike = rng.random(n) < 0.05
    plt[low_spike] -= rng.normal(140.0, 40.0, low_spike.sum())
    plt[high_spike] += rng.normal(250.0, 120.0, high_spike.sum())
    plt = np.clip(plt, 20.0, 1200.0)

    # MPV (fL)
    mpv = rng.normal(loc=9.5, scale=1.2, size=n)
    mpv = np.clip(mpv, 6.0, 15.5)

    # TSH (µIU/mL) - log-normal-ish
    tsh = np.exp(rng.normal(loc=np.log(2.0), scale=0.65, size=n))

    # ✅ FIXED: generate mask ONCE and use same mask for the multiplier size
    mask_hypo_tail = rng.random(n) < 0.06
    tsh[mask_hypo_tail] *= rng.uniform(2.0, 5.0, size=mask_hypo_tail.sum())

    mask_hyper_tail = rng.random(n) < 0.03
    tsh[mask_hyper_tail] *= rng.uniform(0.02, 0.25, size=mask_hyper_tail.sum())

    tsh = np.clip(tsh, 0.01, 80.0)

    # Glucose (mg/dL)
    gf = rng.normal(loc=95.0, scale=18.0, size=n)     # fasting
    gr = rng.normal(loc=115.0, scale=28.0, size=n)    # random
    diab = rng.random(n) < 0.12
    gf[diab] += rng.normal(55.0, 25.0, diab.sum())
    gr[diab] += rng.normal(85.0, 35.0, diab.sum())
    gf = np.clip(gf, 55.0, 320.0)
    gr = np.clip(gr, 60.0, 450.0)

    # Lipids (mg/dL)
    chol = rng.normal(loc=185.0, scale=35.0, size=n)
    ldl = rng.normal(loc=110.0, scale=28.0, size=n)
    hdl = rng.normal(loc=46.0, scale=12.0, size=n)

    dys = rng.random(n) < 0.20
    chol[dys] += rng.normal(55.0, 25.0, dys.sum())
    ldl[dys] += rng.normal(45.0, 20.0, dys.sum())
    hdl[dys] -= rng.normal(8.0, 5.0, dys.sum())

    chol = np.clip(chol, 90.0, 420.0)
    ldl = np.clip(ldl, 40.0, 320.0)
    hdl = np.clip(hdl, 15.0, 110.0)

    X = pd.DataFrame(
        {
            "Hemoglobin": hb,
            "WBC": wbc,
            "Platelet Count": plt,
            "MPV": mpv,
            "TSH": tsh,
            "Glucose (Fasting)": gf,
            "Glucose (Random)": gr,
            "Total Cholesterol": chol,
            "LDL Cholesterol": ldl,
            "HDL Cholesterol": hdl,
            "GenderFemale": gender_female,
        }
    )

    # Soft label probabilities (smooth rules)
    thr_hb = np.where(np.isnan(gender_female), 12.5, np.where(gender_female == 1.0, 12.0, 13.5))
    p_anemia = sigmoid((thr_hb - hb) * 1.5)

    p_infection = sigmoid((wbc - 11.0) * 0.7)
    p_inflammation = np.maximum(sigmoid((wbc - 10.0) * 0.55), sigmoid((mpv - 10.5) * 1.0))

    p_hypo = sigmoid((tsh - 4.2) * 0.6)
    p_hyper = sigmoid((0.4 - tsh) * 4.0)

    p_lowplt = sigmoid((150.0 - plt) * 0.03)
    p_highplt = sigmoid((plt - 450.0) * 0.01)

    p_diabetes = np.maximum(sigmoid((gf - 126.0) * 0.06), sigmoid((gr - 200.0) * 0.04))
    p_diabetes = np.maximum(p_diabetes, sigmoid((gf - 100.0) * 0.05) * 0.4)

    thr_hdl = np.where(np.isnan(gender_female), 45.0, np.where(gender_female == 1.0, 50.0, 40.0))
    p_dys = np.maximum.reduce(
        [
            sigmoid((chol - 200.0) * 0.03),
            sigmoid((ldl - 130.0) * 0.04),
            sigmoid((thr_hdl - hdl) * 0.09),
        ]
    )

    P = np.vstack(
        [
            p_anemia,
            p_infection,
            p_inflammation,
            p_hypo,
            p_hyper,
            p_lowplt,
            p_highplt,
            p_diabetes,
            p_dys,
        ]
    ).T

    # Convert to binary with randomness
    Y = (rng.random(P.shape) < P).astype(int)
    Y = pd.DataFrame(Y, columns=LABELS)

    # Add missingness
    miss_cols = ["TSH", "LDL Cholesterol", "HDL Cholesterol", "Glucose (Fasting)", "Glucose (Random)"]
    for c in miss_cols:
        mask = rng.random(n) < 0.18
        X.loc[mask, c] = np.nan

    return X[FEATURES], Y[LABELS]


def train_and_save(out_dir: str, n: int = 20000) -> Dict:
    X, Y = make_synthetic(n=n)

    X_train, X_test, Y_train, Y_test = train_test_split(
        X, Y, test_size=0.20, random_state=42
    )

    model = Pipeline(
        steps=[
            ("imputer", SimpleImputer(strategy="median")),
            ("scaler", StandardScaler()),
            (
                "clf",
                OneVsRestClassifier(
                    LogisticRegression(
                        solver="saga",
                        max_iter=4000,
                        n_jobs=-1,
                        class_weight="balanced",
                    )
                ),
            ),
        ]
    )

    model.fit(X_train, Y_train)

    Y_pred = model.predict(X_test)

    metrics = {
        "f1_micro": float(f1_score(Y_test, Y_pred, average="micro")),
        "f1_macro": float(f1_score(Y_test, Y_pred, average="macro")),
        "per_label_report": classification_report(Y_test, Y_pred, target_names=LABELS, output_dict=True),
    }

    # ROC-AUC (optional but useful)
    try:
        Y_proba = model.predict_proba(X_test)
        aucs = {}
        for i, lab in enumerate(LABELS):
            try:
                aucs[lab] = float(roc_auc_score(Y_test.iloc[:, i], Y_proba[:, i]))
            except Exception:
                aucs[lab] = None
        metrics["roc_auc"] = aucs
    except Exception:
        pass

    os.makedirs(out_dir, exist_ok=True)
    model_path = os.path.join(out_dir, "medrisk_risk_model.joblib")
    meta_path = os.path.join(out_dir, "medrisk_risk_meta.json")

    joblib.dump(model, model_path)

    meta = {
        "labels": LABELS,
        "features": FEATURES,
        "trained_on": "synthetic_generator_v1",
        "samples": int(n),
        "metrics": metrics,
    }

    with open(meta_path, "w", encoding="utf-8") as f:
        json.dump(meta, f, indent=2)

    return {"model_path": model_path, "meta_path": meta_path, "metrics": metrics}


if __name__ == "__main__":
    out = train_and_save(out_dir=os.path.join(repo_root(), "models"), n=20000)
    print("Saved:", out["model_path"])
    print("Saved:", out["meta_path"])
    print("F1 micro:", out["metrics"]["f1_micro"])
    print("F1 macro:", out["metrics"]["f1_macro"])
