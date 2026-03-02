from __future__ import annotations

import re
from typing import List, Tuple, Pattern

"""
biomarker_patterns.py

This file contains:
- Canonical biomarker keys used across the system
- Regex patterns to detect biomarker labels (with synonyms)
- Helper regex patterns to parse numeric values / units / reference ranges

It is designed to be permissive (supports OCR noise). The extractor applies
additional plausibility checks to reduce false positives.
"""

# -------------------------------------------------------------------
# Canonical biomarker keys used everywhere in the system
# (numeric biomarkers only)
# -------------------------------------------------------------------
BIOMARKERS_CANONICAL: List[str] = [
    # CBC
    "Hemoglobin",
    "WBC",
    "RBC",
    "Hematocrit",
    "MCV",
    "MCH",
    "MCHC",
    "RDW",
    "Platelet Count",
    "MPV",
    # Thyroid
    "TSH",
    "Free T4",
    "Free T3",
    # Glucose / Diabetes
    "Glucose (Fasting)",
    "Glucose (Random)",
    "HbA1c",
    # Lipids
    "Total Cholesterol",
    "LDL Cholesterol",
    "HDL Cholesterol",
    "Triglycerides",
    # Kidney (KFT)
    "Urea",
    "BUN",
    "Creatinine",
    "Uric Acid",
    "eGFR",
    "Sodium",
    "Potassium",
    "Chloride",
    "Calcium",
    # Liver (LFT)
    "ALT (SGPT)",
    "AST (SGOT)",
    "Alkaline Phosphatase",
    "Total Bilirubin",
    "Direct Bilirubin",
    "Indirect Bilirubin",
    "Albumin",
    "Total Protein",
    "Globulin",
    "A/G Ratio",
    # Vitamins
    "Vitamin D (25-OH)",
    "Vitamin B12",
    "Folate",
    # Inflammation
    "CRP",
    "ESR",
]


# -------------------------------------------------------------------
# Ignore lines that look like headings / metadata / non-result rows
# -------------------------------------------------------------------
IGNORE_LABEL_RE = re.compile(
    r"(?i)^(?:"
    r"sample|specimen|method|reference|range|units?|comment|remarks?|interpretation|"
    r"clinical|note|doctor|pathologist|laboratory|signature|report|page|"
    r"patient|name|age|gender|sex|collection|received|released|"
    r"address|phone|email|barcode|sr\.?no|invoice|test\s*name|test\s*code|"
    r"department|investigation|parameter|result|bio\s*ref|biological\s*ref|"
    r"flag|status|normal\s*range|range\s*values?|technology"
    r")\b"
)


def _label_pattern(raw: str) -> Pattern[str]:
    """
    Compile a biomarker label regex.
    raw should already include word boundaries when appropriate.
    """
    return re.compile(raw, re.IGNORECASE)


# -------------------------------------------------------------------
# Label -> canonical key matchers (synonym aware)
# -------------------------------------------------------------------
LABEL_TO_CANONICAL: List[Tuple[str, Pattern[str]]] = [
    # CBC
    ("Hemoglobin", _label_pattern(r"\b(hemoglobin|haemoglobin|hb|hgb)\b")),
    ("WBC", _label_pattern(r"\b(wbc|total\s*leucocyte\s*count|total\s*leukocyte\s*count|tlc)\b")),
    ("RBC", _label_pattern(r"\b(rbc|red\s*blood\s*cell(?:s)?\s*count)\b")),
    ("Hematocrit", _label_pattern(r"\b(hematocrit|haematocrit|hct|pcv)\b")),
    ("MCV", _label_pattern(r"\b(mcv|mean\s*corpuscular\s*volume)\b")),
    ("MCH", _label_pattern(r"\b(mch|mean\s*corpuscular\s*hemoglobin)\b")),
    ("MCHC", _label_pattern(r"\b(mchc|mean\s*corpuscular\s*hemoglobin\s*concentration)\b")),
    ("RDW", _label_pattern(r"\b(rdw(?:-cv)?|red\s*cell\s*distribution\s*width)\b")),
    ("Platelet Count", _label_pattern(r"\b(platelet(?:\s*count)?|plt)\b")),
    ("MPV", _label_pattern(r"\b(mpv|mean\s*platelet\s*volume)\b")),
    # Thyroid
    ("TSH", _label_pattern(r"\b(tsh(?:\s*3rd\s*generation)?|thyroid\s*stimulating\s*hormone)\b")),
    ("Free T4", _label_pattern(r"\b(free\s*t4|ft4)\b")),
    ("Free T3", _label_pattern(r"\b(free\s*t3|ft3)\b")),
    # Glucose / Diabetes  ✅ (includes “Glucose (Fasting)” formats)
    ("Glucose (Fasting)", _label_pattern(r"\b(fasting\s*(?:plasma\s*)?glucose|fasting\s*blood\s*sugar|fbs|glucose\s*\(?\s*fasting\s*\)?|glucose\s*[-:]\s*fasting)\b")),
    ("Glucose (Random)", _label_pattern(r"\b(random\s*(?:plasma\s*)?glucose|random\s*blood\s*sugar|rbs|glucose\s*\(?\s*random\s*\)?|glucose\s*[-:]\s*random)\b")),
    ("HbA1c", _label_pattern(r"\b(hba1c|hb\s*a1c|glycated\s*hemoglobin)\b")),
    # Lipids
    ("Total Cholesterol", _label_pattern(r"\b(total\s*cholesterol|cholesterol\s*total)\b")),
    ("LDL Cholesterol", _label_pattern(r"\b(ldl(?:\s*cholesterol)?|ldl\-?c)\b")),
    ("HDL Cholesterol", _label_pattern(r"\b(hdl(?:\s*cholesterol)?|hdl\-?c)\b")),
    ("Triglycerides", _label_pattern(r"\b(triglycerides?|tg)\b")),
    # Kidney
    ("Urea", _label_pattern(r"\b(urea|blood\s*urea|serum\s*urea)\b")),
    ("BUN", _label_pattern(r"\b(bun|blood\s*urea\s*nitrogen)\b")),
    ("Creatinine", _label_pattern(r"\b(creatinine|serum\s*creatinine)\b")),
    ("Uric Acid", _label_pattern(r"\b(uric\s*acid)\b")),
    ("eGFR", _label_pattern(r"\b(egfr|estimated\s*gfr|estimated\s*glomerular\s*filtration\s*rate)\b")),
    ("Sodium", _label_pattern(r"\b(sodium|na\+?)\b")),
    ("Potassium", _label_pattern(r"\b(potassium|k\+?)\b")),
    ("Chloride", _label_pattern(r"\b(chloride|cl\-?)\b")),
    ("Calcium", _label_pattern(r"\b(calcium)\b")),
    # Liver
    ("ALT (SGPT)", _label_pattern(r"\b(alt|sgpt|alanine\s*aminotransferase)\b")),
    ("AST (SGOT)", _label_pattern(r"\b(ast|sgot|aspartate\s*aminotransferase)\b")),
    ("Alkaline Phosphatase", _label_pattern(r"\b(alk(?:aline)?\s*phosphatase|alp)\b")),
    ("Total Bilirubin", _label_pattern(r"\b(total\s*bilirubin|bilirubin\s*total)\b")),
    ("Direct Bilirubin", _label_pattern(r"\b(direct\s*bilirubin|bilirubin\s*direct)\b")),
    ("Indirect Bilirubin", _label_pattern(r"\b(indirect\s*bilirubin|bilirubin\s*indirect)\b")),
    ("Albumin", _label_pattern(r"\b(albumin)\b")),
    ("Total Protein", _label_pattern(r"\b(total\s*protein|protein\s*total)\b")),
    ("Globulin", _label_pattern(r"\b(globulin)\b")),
    ("A/G Ratio", _label_pattern(r"\b(a\s*/\s*g\s*ratio|albumin\s*/\s*globulin\s*ratio)\b")),
    # Vitamins
    ("Vitamin D (25-OH)", _label_pattern(r"\b(25\s*oh\s*vitamin\s*d|25\-?hydroxy\s*vitamin\s*d|vitamin\s*d\s*\(25\-?oh\)|vit(?:amin)?\s*d3?)\b")),
    ("Vitamin B12", _label_pattern(r"\b(vit(?:amin)?\s*b\s*12|b12|cobalamin)\b")),
    ("Folate", _label_pattern(r"\b(folate|folic\s*acid)\b")),
    # Inflammation
    ("CRP", _label_pattern(r"\b(crp|c\s*reactive\s*protein)\b")),
    ("ESR", _label_pattern(r"\b(esr|erythrocyte\s*sedimentation\s*rate)\b")),
]


# -------------------------------------------------------------------
# Numeric parsing building blocks
# -------------------------------------------------------------------
_NUMBER = r"[-+]?\d+(?:\.\d+)?"
_RANGE_SEP = r"(?:-|–|—|to)"
_PIPE = r"(?:\s*\|\s*|\s{2,}|\t+)"  # pipe / multi-space / tabs

# Matches lines like:
#   12.6 gm/dL 12.0 - 15.0
#   5.600 H µIU/mL 0.270 - 4.200
#   88 | mg/dL | 74 - 99
VALUE_RANGE_RE = re.compile(
    rf"^\s*(?P<value>{_NUMBER})\s*(?:\(?\s*[HL]\s*\)?)?\s*"
    rf"(?:(?P<unit>[A-Za-zµμ%/\.\^0-9]+)\s*)?"
    rf"(?:{_PIPE}|\s+)"
    rf"(?P<low>{_NUMBER})\s*{_RANGE_SEP}\s*(?P<high>{_NUMBER})"
    rf"(?:\s*(?P<unit2>[A-Za-zµμ%/\.\^0-9]+))?\s*$",
    re.IGNORECASE,
)

# Matches value only line like:
#   12.6
#   5.600 H
#   <0.01
VALUE_ONLY_RE = re.compile(
    rf"^\s*(?P<prefix>[<>]?)\s*(?P<value>{_NUMBER})\s*(?:\(?\s*[HL]\s*\)?)?\s*(?P<unit>[A-Za-zµμ%/\.\^0-9]+)?\s*$",
    re.IGNORECASE,
)

# Matches unit only line like:
#   gm/dL
#   mg/dL
#   µIU/mL
UNIT_ONLY_RE = re.compile(
    r"^\s*(?P<unit>[A-Za-zµμ%/\.\^0-9]{1,18})\s*$",
    re.IGNORECASE,
)

# Matches range only line like:
#   12.0 - 15.0
#   0.27 - 4.2
#   12.0-15.0 g/dL
RANGE_ONLY_RE = re.compile(
    rf"^\s*(?P<low>{_NUMBER})\s*{_RANGE_SEP}\s*(?P<high>{_NUMBER})\s*(?P<unit>[A-Za-zµμ%/\.\^0-9]+)?\s*$",
    re.IGNORECASE,
)
