from __future__ import annotations

from typing import Any, Dict, Optional


def normalize_unit(unit: Optional[str]) -> Optional[str]:
    if unit is None:
        return None
    u = str(unit).strip()
    if not u:
        return None
    u = u.replace("µ", "u")
    u = u.replace("μ", "u")
    u = u.replace(" ", "")
    u = u.replace("mg/dl", "mg/dL").replace("mmol/l", "mmol/L")
    u = u.replace("iu/l", "IU/L").replace("u/l", "U/L").replace("iu", "IU")
    u = u.replace("pg/ml", "pg/mL").replace("ng/ml", "ng/mL")
    u = u.replace("g/dl", "g/dL")
    return u


# Fallback ranges ONLY when report doesn't show ranges.
REFERENCE_RANGES: Dict[str, Dict[str, Any]] = {
    # CBC
    "Hemoglobin": {
        "unit": "g/dL",
        "male": {"low": 13.0, "high": 17.0},
        "female": {"low": 12.0, "high": 15.5},
        "category": "CBC",
    },
    "WBC": {"low": 4.0, "high": 11.0, "unit": "x10^3/uL", "category": "CBC"},
    "Platelet Count": {"low": 150.0, "high": 450.0, "unit": "x10^3/uL", "category": "CBC"},
    "MCV": {"low": 80.0, "high": 100.0, "unit": "fL", "category": "CBC"},
    "MCH": {"low": 27.0, "high": 33.0, "unit": "pg", "category": "CBC"},
    "MCHC": {"low": 32.0, "high": 36.0, "unit": "g/dL", "category": "CBC"},
    "RDW": {"low": 11.5, "high": 14.5, "unit": "%", "category": "CBC"},

    # Thyroid
    "TSH": {
        "unit": "uIU/mL",
        "default": {"low": 0.27, "high": 4.20},
        "pregnancy": {
            "trimester1": {"low": 0.10, "high": 2.50},
            "trimester2": {"low": 0.20, "high": 3.00},
            "trimester3": {"low": 0.30, "high": 3.00},
        },
        "category": "Thyroid",
    },
    "Free T4": {"low": 0.8, "high": 1.8, "unit": "ng/dL", "category": "Thyroid"},
    "Free T3": {"low": 2.3, "high": 4.2, "unit": "pg/mL", "category": "Thyroid"},

    # Glucose
    "Glucose (Fasting)": {"low": 70.0, "high": 99.0, "unit": "mg/dL", "category": "Diabetes"},
    "Glucose (Random)": {"low": 70.0, "high": 140.0, "unit": "mg/dL", "category": "Diabetes"},
    "HbA1c": {"low": 4.0, "high": 5.6, "unit": "%", "category": "Diabetes"},

    # Lipids
    "Total Cholesterol": {"low": 0.0, "high": 200.0, "unit": "mg/dL", "category": "Lipids"},
    "LDL Cholesterol": {"low": 0.0, "high": 129.0, "unit": "mg/dL", "category": "Lipids"},
    "HDL Cholesterol": {"low": 40.0, "high": 999.0, "unit": "mg/dL", "category": "Lipids"},
    "Triglycerides": {"low": 0.0, "high": 149.0, "unit": "mg/dL", "category": "Lipids"},

    # Kidney
    "Urea": {"low": 15.0, "high": 40.0, "unit": "mg/dL", "category": "Kidney"},
    "BUN": {"low": 7.0, "high": 20.0, "unit": "mg/dL", "category": "Kidney"},
    "Creatinine": {
        "unit": "mg/dL",
        "male": {"low": 0.7, "high": 1.3},
        "female": {"low": 0.6, "high": 1.1},
        "category": "Kidney",
    },
    "eGFR": {"low": 60.0, "high": 200.0, "unit": "mL/min/1.73m2", "category": "Kidney"},
    "Uric Acid": {
        "unit": "mg/dL",
        "male": {"low": 3.5, "high": 7.2},
        "female": {"low": 2.6, "high": 6.0},
        "category": "Metabolic",
    },

    # Electrolytes
    "Sodium": {"low": 135.0, "high": 145.0, "unit": "mmol/L", "category": "Electrolytes"},
    "Potassium": {"low": 3.5, "high": 5.1, "unit": "mmol/L", "category": "Electrolytes"},
    "Chloride": {"low": 98.0, "high": 107.0, "unit": "mmol/L", "category": "Electrolytes"},
    "Calcium": {"low": 8.5, "high": 10.5, "unit": "mg/dL", "category": "Electrolytes"},

    # LFT
    "ALT (SGPT)": {"low": 0.0, "high": 55.0, "unit": "U/L", "category": "Liver"},
    "AST (SGOT)": {"low": 0.0, "high": 40.0, "unit": "U/L", "category": "Liver"},
    "Alkaline Phosphatase": {"low": 44.0, "high": 147.0, "unit": "U/L", "category": "Liver"},
    "Total Bilirubin": {"low": 0.1, "high": 1.2, "unit": "mg/dL", "category": "Liver"},
    "Direct Bilirubin": {"low": 0.0, "high": 0.3, "unit": "mg/dL", "category": "Liver"},
    "Albumin": {"low": 3.5, "high": 5.0, "unit": "g/dL", "category": "Liver"},
    "Total Protein": {"low": 6.0, "high": 8.3, "unit": "g/dL", "category": "Liver"},

    # Inflammation
    "CRP": {"low": 0.0, "high": 3.0, "unit": "mg/L", "category": "Inflammation"},
    "ESR": {"low": 0.0, "high": 20.0, "unit": "mm/hr", "category": "Inflammation"},

    # Vitamins
    "Vitamin D (25-OH)": {"low": 30.0, "high": 100.0, "unit": "ng/mL", "category": "Vitamins"},
    "Vitamin B12": {"low": 200.0, "high": 900.0, "unit": "pg/mL", "category": "Vitamins"},
    "Folate": {"low": 4.0, "high": 20.0, "unit": "ng/mL", "category": "Vitamins"},
}


def get_reference_range(
    biomarker: str,
    gender: Optional[str] = None,
    pregnancy: bool = False,
    trimester: Optional[str] = None,
) -> Optional[Dict[str, Any]]:
    b = REFERENCE_RANGES.get(biomarker)
    if not b:
        return None

    unit = normalize_unit(b.get("unit"))
    category = b.get("category")

    # Pregnancy-specific TSH
    if biomarker == "TSH" and pregnancy:
        preg = b.get("pregnancy") if isinstance(b.get("pregnancy"), dict) else {}
        t = str(trimester or "").strip().lower().replace(" ", "")
        if t in ("1", "t1", "trimester1", "first"):
            rr = preg.get("trimester1")
        elif t in ("2", "t2", "trimester2", "second"):
            rr = preg.get("trimester2")
        elif t in ("3", "t3", "trimester3", "third"):
            rr = preg.get("trimester3")
        else:
            rr = preg.get("trimester1") or preg.get("trimester2") or preg.get("trimester3")
        if isinstance(rr, dict):
            return {"low": rr.get("low"), "high": rr.get("high"), "unit": unit, "category": category}

    g = str(gender or "").strip().lower()
    if g in ("m", "male", "man"):
        rr = b.get("male")
        if isinstance(rr, dict):
            return {"low": rr.get("low"), "high": rr.get("high"), "unit": unit, "category": category}

    if g in ("f", "female", "woman"):
        rr = b.get("female")
        if isinstance(rr, dict):
            return {"low": rr.get("low"), "high": rr.get("high"), "unit": unit, "category": category}

    rr = b.get("default")
    if isinstance(rr, dict):
        return {"low": rr.get("low"), "high": rr.get("high"), "unit": unit, "category": category}

    if "low" in b and "high" in b:
        return {"low": b.get("low"), "high": b.get("high"), "unit": unit, "category": category}

    return None
