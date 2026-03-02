from __future__ import annotations

from medrisk.ml.predictor import predict_health_risks
from medrisk.ml.constants import CONDITIONS


def test_predictor_shape_minimal():
    structured = {
        "Hemoglobin": 9.8,
        "WBC": 12.5,
        "Platelet Count": 180.0,
        "MPV": 10.5,
        "TSH": 6.2,
        "Glucose (Fasting)": 132.0,
        "Glucose (Random)": 210.0,
        "Total Cholesterol": 240.0,
        "LDL Cholesterol": 160.0,
        "HDL Cholesterol": 35.0,
        "Gender": "Female",
    }

    out = predict_health_risks(structured)

    assert "overall" in out
    assert "riskScores" in out
    assert isinstance(out["riskScores"], dict)

    # all condition keys present
    for c in CONDITIONS:
        assert f"{c} Risk" in out["riskScores"]
        item = out["riskScores"][f"{c} Risk"]
        assert "score" in item and "level" in item
        assert 0.0 <= float(item["score"]) <= 100.0