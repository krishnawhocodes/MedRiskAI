from __future__ import annotations

from typing import Dict, List


# Multi-risk labels (predicted independently).
CONDITIONS: List[str] = [
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


# Suggested specialties for each risk.
SPECIALTIES_MAP: Dict[str, List[str]] = {
    "Anemia": ["General Physician", "Hematologist"],
    "Infection": ["General Physician"],
    "Inflammation": ["General Physician"],
    "Hypothyroidism": ["Endocrinologist", "General Physician"],
    "Hyperthyroidism": ["Endocrinologist", "General Physician"],
    "Low Platelets": ["Hematologist", "General Physician"],
    "High Platelets": ["Hematologist", "General Physician"],
    "Diabetes": ["Diabetologist", "Endocrinologist", "General Physician"],
    "Dyslipidemia": ["Cardiologist", "General Physician"],
}


# Probability thresholds to bucket severity.
P_HIGH = 0.80
P_MODERATE = 0.55
P_LOW = 0.40
