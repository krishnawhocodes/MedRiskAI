from __future__ import annotations

from medrisk.findings import build_findings


def test_build_findings_smoke():
    structured = {
        "Hemoglobin": 9.5,
        "WBC": 7.5,
        "Platelet Count": 480.0,
        "TSH": 9.0,
        "extraction": {
            "details": {
                "Hemoglobin": {"low": 12.0, "high": 16.0, "unit": "g/dL"},
                "WBC": {"low": 4.0, "high": 11.0, "unit": "x10^3/uL"},
                "Platelet Count": {"low": 150.0, "high": 450.0, "unit": "x10^3/uL"},
                "TSH": {"low": 0.4, "high": 4.2, "unit": "µIU/mL"},
            },
            "values": {"Hemoglobin": 9.5, "WBC": 7.5, "Platelet Count": 480.0, "TSH": 9.0},
            "qualitative": {},
            "meta": {"Gender": "Female"},
        },
    }

    findings = build_findings(structured)
    assert isinstance(findings, list)
    # should find at least some abnormalities
    assert any(f.get("biomarker") == "Hemoglobin" for f in findings)