from __future__ import annotations

import re
from dataclasses import dataclass
from typing import Any, Dict, List, Optional, Tuple

from .biomarker_patterns import (
    BIOMARKERS_CANONICAL,
    LABEL_TO_CANONICAL,
    IGNORE_LABEL_RE,
    VALUE_RANGE_RE,
    VALUE_ONLY_RE,
    UNIT_ONLY_RE,
    RANGE_ONLY_RE,
)
from .text_utils import safe_float

# Optional default reference ranges (used when report does not print ranges)
try:
    from .reference_ranges import get_reference_range, normalize_unit  # type: ignore
except Exception:  # pragma: no cover
    get_reference_range = None  # type: ignore
    normalize_unit = lambda u: u  # type: ignore


@dataclass
class BiomarkerExtraction:
    """
    Extracts numeric biomarkers + qualitative screening tests.
    Numeric biomarkers are extracted when:
    - a label is detected, AND
    - we find a plausible value (and ideally a range nearby), OR
    - we can safely fall back to default reference ranges.
    """
    values: Dict[str, float]
    details: Dict[str, Dict[str, Any]]         # low/high/unit + source for numeric markers
    qualitative: Dict[str, Dict[str, Any]]     # e.g. {"HCV": {"result":"Reactive"}, ...}
    evidence: Dict[str, Dict[str, Any]]        # {"Hemoglobin": {"source":"regex","page":1,"snippet":"..."}}
    meta: Dict[str, str]
    missing: List[str]


# --------------------- META EXTRACTION ---------------------
_BP_RE = re.compile(r"(?i)\b(?:bp|blood\s*pressure)\b\s*[:=\-]?\s*(\d{2,3})\s*/\s*(\d{2,3})")
_GENDER_RE = re.compile(r"(?i)\b(gender|sex)\s*[:=\-]?\s*(male|female)\b")
_DATE_RE = re.compile(
    r"(?i)\b(released\s*on|reported\s*on|report\s*date|date)\s*[:=\-]?\s*"
    r"([0-3]?\d[\-/][01]?\d[\-/](?:\d{2,4}))\b"
)
_COLLECTED_RE = re.compile(
    r"(?i)\b(sample\s*collected\s*on|collection\s*date)\s*[:=\-]?\s*([0-3]?\d[\-/][01]?\d[\-/](?:\d{2,4}))\b"
)
_RECEIVED_RE = re.compile(
    r"(?i)\b(sample\s*received\s*on|received\s*on)\s*[:=\-]?\s*([0-3]?\d[\-/][01]?\d[\-/](?:\d{2,4}))\b"
)
_AGE_RE = re.compile(r"(?i)\b(age)\s*[:=\-]?\s*(\d{1,3})\s*(years|yrs|y)?\b")
_LAB_RE = re.compile(
    r"(?i)\b([A-Za-z0-9 .,&\-\(\)]{3,90}\b(?:Lab|Laboratory|Labs|Diagnostics)\b[A-Za-z0-9 .,&\-\(\)]{0,90})\b"
)

_PREG_RE = re.compile(r"(?i)\b(ante\s*natal|antenatal|pregnan|obstetric)\b")
_TRIM_RE = re.compile(r"(?i)\b(1st|first|2nd|second|3rd|third)\s*trimester\b")


# ---------------- QUALITATIVE TESTS ----------------
_REACTIVE_WORD = r"(Non\s*Reactive|Non-Reactive|Nonreactive|Reactive|Positive|Negative)"
_HCV_RE = re.compile(rf"(?is)\b(Hepatitis\s*C\s*Antibody|Anti\s*-?\s*HCV|HCV)\b.*?\b({_REACTIVE_WORD})\b")
_HBSAG_RE = re.compile(rf"(?is)\b(Hepatitis\s*B\s*Surface\s*Antigen|HBsAg)\b.*?\b({_REACTIVE_WORD})\b")
_HIV_RE = re.compile(rf"(?is)\bHIV\b.*?\b(Antibody|Ag/Ab|Rapid\s*Card)?\b.*?\b({_REACTIVE_WORD})\b")
_VDRL_RE = re.compile(rf"(?is)\b(VDRL|RPR)\b.*?\b({_REACTIVE_WORD})\b")
_VDRL_TITER_RE = re.compile(r"(?i)\b(titer|titre)\b\s*[:=\-]?\s*(1\s*:\s*\d+)\b")


# ----------------- PAGE HANDLING -----------------
_PAGE_MARKER_RE = re.compile(r"^<<<PAGE\s+(\d+)>>>$", re.I)


def _split_lines_with_pages(text: str) -> List[Tuple[Optional[int], str]]:
    """
    Convert big text into a list of (page_number, line) tuples.
    Page markers are formatted as: <<<PAGE N>>>
    """
    lines: List[Tuple[Optional[int], str]] = []
    current_page: Optional[int] = None

    for raw in (text or "").splitlines():
        raw = (raw or "").strip("\ufeff").rstrip()
        if not raw.strip():
            continue

        m = _PAGE_MARKER_RE.match(raw.strip())
        if m:
            try:
                current_page = int(m.group(1))
            except Exception:
                current_page = None
            continue

        lines.append((current_page, raw))
    return lines


def _match_label_line(line: str) -> Optional[str]:
    """
    Return canonical biomarker key if the line looks like a biomarker label.
    """
    if not line or IGNORE_LABEL_RE.match(line):
        return None
    for canonical_key, compiled_pattern in LABEL_TO_CANONICAL:
        if compiled_pattern.search(line):
            return canonical_key
    return None


def _clean_unit(u: Optional[str]) -> Optional[str]:
    if not u:
        return None
    u = str(u).strip()
    if not u:
        return None
    # Keep only short-ish tokens; reject obvious words
    if len(u) > 18:
        return None
    if re.match(r"(?i)^(high|low|normal|range|ref|reference)$", u):
        return None
    # Heuristic: must contain a non-letter or a capital pattern typical of units
    if not re.search(r"[%/\dµμ]", u) and not re.search(r"(?i)(mg|gm|g|iu|u|meq|mmol|pg|ng|fl|cells)", u):
        return None
    return u


def _numbers_in_text(s: str) -> List[float]:
    vals: List[float] = []
    for m in re.finditer(r"[-+]?\d+(?:\.\d+)?", s.replace(",", "")):
        fv = safe_float(m.group(0))
        if fv is not None:
            vals.append(float(fv))
    return vals


def _parse_inline_row(line: str, label_pattern: re.Pattern[str]) -> Optional[Tuple[float, Optional[str], Optional[float], Optional[float]]]:
    """
    Attempt to parse value/range/unit from the SAME line that contains the label.
    Works well for table rows like:
      Hemoglobin 12.6 g/dL 12.0 - 15.0
      TSH | 5.600 H | µIU/mL | 0.270 - 4.200
    """
    m = label_pattern.search(line)
    if not m:
        return None

    tail = line[m.end():].strip()
    if not tail:
        return None

    # 1) direct one-line value + range
    mm = VALUE_RANGE_RE.search(tail)
    if mm:
        v = safe_float(mm.group("value"))
        lo = safe_float(mm.group("low"))
        hi = safe_float(mm.group("high"))
        unit = _clean_unit(mm.group("unit") or mm.group("unit2"))
        if v is not None:
            return float(v), unit, float(lo) if lo is not None else None, float(hi) if hi is not None else None

    # 2) find range inside tail, then take closest value before the range
    rng = re.search(r"(?P<low>[-+]?\d+(?:\.\d+)?)\s*(?:-|–|—|to)\s*(?P<high>[-+]?\d+(?:\.\d+)?)", tail, re.I)
    if rng:
        lo = safe_float(rng.group("low"))
        hi = safe_float(rng.group("high"))
        if lo is None or hi is None:
            lo = None
            hi = None

        before = tail[: rng.start()].strip()
        after = tail[rng.end():].strip()

        before_nums = _numbers_in_text(before)
        after_nums = _numbers_in_text(after)

        value = before_nums[-1] if before_nums else (after_nums[0] if after_nums else None)
        if value is None:
            return None

        # unit heuristics: try token immediately after value, else token after range
        unit = None
        # token after value in before segment
        uv = re.search(r"[-+]?\d+(?:\.\d+)?\s*(?:\(?\s*[HL]\s*\)?)?\s*([A-Za-zµμ%/\.\^0-9]{1,18})", before, re.I)
        if uv:
            unit = _clean_unit(uv.group(1))
        if unit is None:
            ua = re.search(r"^([A-Za-zµμ%/\.\^0-9]{1,18})", after, re.I)
            if ua:
                unit = _clean_unit(ua.group(1))

        return float(value), unit, float(lo) if lo is not None else None, float(hi) if hi is not None else None

    # 3) value only in same line
    valm = re.search(r"(?P<prefix>[<>]?)\s*(?P<value>[-+]?\d+(?:\.\d+)?)\s*(?:\(?\s*[HL]\s*\)?)?\s*(?P<unit>[A-Za-zµμ%/\.\^0-9]{1,18})?", tail, re.I)
    if valm:
        v = safe_float(valm.group("value"))
        unit = _clean_unit(valm.group("unit"))
        if v is not None:
            return float(v), unit, None, None

    return None


def _parse_value_near_label(
    lines: List[Tuple[Optional[int], str]],
    label_index: int,
    lookahead: int = 18,
) -> Optional[Tuple[float, Optional[str], Optional[float], Optional[float], Optional[int], str]]:
    """
    Parses value/range in subsequent lines after a label line.
    Returns (value, unit, low, high, evidence_page, evidence_snippet).
    """
    start = label_index + 1
    end = min(len(lines), label_index + 1 + lookahead)

    # A) One-line value+range in next lines
    for j in range(start, end):
        pg, ln = lines[j]
        if IGNORE_LABEL_RE.match(ln):
            continue

        mm = VALUE_RANGE_RE.match(ln.strip())
        if not mm:
            continue
        v = safe_float(mm.group("value"))
        lo = safe_float(mm.group("low"))
        hi = safe_float(mm.group("high"))
        unit = _clean_unit(mm.group("unit") or mm.group("unit2"))
        if v is None:
            continue
        return float(v), unit, float(lo) if lo is not None else None, float(hi) if hi is not None else None, pg, ln

    # B) Multi-line parsing:
    # value line, optional unit line, then range line
    for j in range(start, end):
        pg_v, ln_v = lines[j]
        if IGNORE_LABEL_RE.match(ln_v):
            continue

        mv = VALUE_ONLY_RE.match(ln_v.strip())
        if not mv:
            continue

        v = safe_float(mv.group("value"))
        if v is None:
            continue

        unit = _clean_unit(mv.group("unit"))
        lo: Optional[float] = None
        hi: Optional[float] = None
        ev_pg = pg_v
        ev_snippet = ln_v

        for k in range(j + 1, min(end, j + 10)):
            pg_k, ln_k = lines[k]
            if IGNORE_LABEL_RE.match(ln_k):
                continue

            # try capture unit
            if unit is None:
                mu = UNIT_ONLY_RE.match(ln_k.strip())
                if mu:
                    unit = _clean_unit(mu.group("unit"))
                    if unit:
                        continue

            # capture range
            mr = RANGE_ONLY_RE.match(ln_k.strip())
            if mr:
                lo = safe_float(mr.group("low"))
                hi = safe_float(mr.group("high"))
                if unit is None:
                    unit = _clean_unit(mr.group("unit"))
                if lo is not None and hi is not None:
                    return float(v), unit, float(lo), float(hi), ev_pg, ev_snippet

        # If no range found, still accept value (details will be defaulted later)
        return float(v), unit, None, None, ev_pg, ev_snippet

    return None


# ----------------- PLAUSIBILITY CHECKS -----------------
_HARD_BOUNDS: Dict[str, Tuple[float, float]] = {
    # CBC
    "Hemoglobin": (1.0, 30.0),
    "WBC": (0.1, 300.0),
    "RBC": (0.1, 15.0),
    "Hematocrit": (1.0, 80.0),
    "MCV": (30.0, 200.0),
    "MCH": (5.0, 80.0),
    "MCHC": (10.0, 60.0),
    "RDW": (5.0, 40.0),
    "Platelet Count": (1.0, 5000.0),
    "MPV": (1.0, 50.0),
    # Thyroid
    "TSH": (0.001, 200.0),
    "Free T4": (0.1, 10.0),
    "Free T3": (0.1, 30.0),
    # Glucose / diabetes
    "Glucose (Fasting)": (10.0, 1200.0),
    "Glucose (Random)": (10.0, 1200.0),
    "HbA1c": (2.0, 20.0),
    # Lipids
    "Total Cholesterol": (10.0, 2000.0),
    "LDL Cholesterol": (5.0, 1500.0),
    "HDL Cholesterol": (5.0, 500.0),
    "Triglycerides": (5.0, 3000.0),
    # Kidney
    "Urea": (1.0, 500.0),
    "BUN": (1.0, 300.0),
    "Creatinine": (0.01, 30.0),
    "Uric Acid": (0.1, 30.0),
    "eGFR": (0.0, 200.0),
    "Sodium": (80.0, 200.0),
    "Potassium": (1.0, 10.0),
    "Chloride": (50.0, 200.0),
    "Calcium": (1.0, 20.0),
    # Liver
    "ALT (SGPT)": (0.0, 5000.0),
    "AST (SGOT)": (0.0, 5000.0),
    "Alkaline Phosphatase": (0.0, 5000.0),
    "Total Bilirubin": (0.0, 80.0),
    "Direct Bilirubin": (0.0, 50.0),
    "Indirect Bilirubin": (0.0, 80.0),
    "Albumin": (0.1, 10.0),
    "Total Protein": (0.1, 20.0),
    "Globulin": (0.1, 20.0),
    "A/G Ratio": (0.01, 10.0),
    # Vitamins / inflammation
    "Vitamin D (25-OH)": (0.0, 300.0),
    "Vitamin B12": (0.0, 5000.0),
    "Folate": (0.0, 100.0),
    "CRP": (0.0, 500.0),
    "ESR": (0.0, 200.0),
}


def _plausible_value(key: str, value: float) -> bool:
    if value is None:
        return False
    if not (value == value):  # NaN
        return False
    lo, hi = _HARD_BOUNDS.get(key, (-1e12, 1e12))
    return lo <= float(value) <= hi


def _plausible_range(key: str, low: Optional[float], high: Optional[float]) -> bool:
    if low is None or high is None:
        return True
    if high <= low:
        return False
    # keep range inside very broad bounds
    lo_b, hi_b = _HARD_BOUNDS.get(key, (-1e12, 1e12))
    if not (lo_b <= low <= hi_b and lo_b <= high <= hi_b):
        return False
    return True


def _default_details_if_missing(
    key: str,
    *,
    unit: Optional[str],
    gender: Optional[str],
    pregnancy: bool,
    trimester: Optional[str],
) -> Tuple[Optional[float], Optional[float], Optional[str]]:
    """
    When the report doesn't show a range, we try to attach a default reference range.
    """
    if get_reference_range is None:
        return None, None, unit

    ref = get_reference_range(key, gender=gender, pregnancy=pregnancy, trimester=trimester)  # type: ignore
    if not ref:
        return None, None, unit
    try:
        lo = float(ref.get("low"))
        hi = float(ref.get("high"))
    except Exception:
        lo = None
        hi = None
    u = unit or ref.get("unit")
    return lo, hi, normalize_unit(u)  # type: ignore


def _extract_qualitative(text: str) -> Dict[str, Dict[str, Any]]:
    out: Dict[str, Dict[str, Any]] = {}

    def add(key: str, m: re.Match) -> None:
        result = (m.group(m.lastindex or 0) or "").strip()
        if not result:
            return
        # normalize
        r = result.lower().replace(" ", "").replace("-", "")
        if r in ("nonreactive", "negative"):
            result_norm = "Non-Reactive"
        elif r in ("reactive", "positive"):
            result_norm = "Reactive"
        else:
            result_norm = result
        out[key] = {"result": result_norm}

    mh = _HCV_RE.search(text)
    if mh:
        add("HCV", mh)

    mb = _HBSAG_RE.search(text)
    if mb:
        add("HBsAg", mb)

    mi = _HIV_RE.search(text)
    if mi:
        add("HIV", mi)

    mv = _VDRL_RE.search(text)
    if mv:
        add("VDRL", mv)
        mt = _VDRL_TITER_RE.search(text)
        if mt:
            out["VDRL"]["titer"] = mt.group(2).replace(" ", "")

    return out


def extract_biomarkers_regex(text: str) -> BiomarkerExtraction:
    """
    Main extractor entrypoint.
    """
    values: Dict[str, float] = {}
    details: Dict[str, Dict[str, Any]] = {}
    qualitative: Dict[str, Dict[str, Any]] = {}
    evidence: Dict[str, Dict[str, Any]] = {}
    meta: Dict[str, str] = {}

    if not text:
        return BiomarkerExtraction(values, details, qualitative, evidence, meta, missing=list(BIOMARKERS_CANONICAL))

    # ---- Meta
    gm = _GENDER_RE.search(text)
    if gm:
        meta["Gender"] = gm.group(2).capitalize()

    dm = _DATE_RE.search(text)
    if dm:
        meta["ReportDate"] = dm.group(2).strip()
    else:
        # fallback to collected/received
        cm = _COLLECTED_RE.search(text)
        if cm:
            meta["ReportDate"] = cm.group(2).strip()
        else:
            rm = _RECEIVED_RE.search(text)
            if rm:
                meta["ReportDate"] = rm.group(2).strip()

    am = _AGE_RE.search(text)
    if am:
        meta["AgeYears"] = am.group(2).strip()

    lm = _LAB_RE.search(text)
    if lm:
        meta["LabName"] = lm.group(1).strip()

    if _PREG_RE.search(text):
        meta["PregnancyPanel"] = "true"
        tm = _TRIM_RE.search(text)
        if tm:
            meta["Trimester"] = tm.group(1).lower()

    gender = meta.get("Gender")
    pregnancy = str(meta.get("PregnancyPanel") or "").lower() == "true"
    trimester = meta.get("Trimester")

    # ---- Build (page, line) list
    lines = _split_lines_with_pages(text)

    # We'll keep the "best" match for each biomarker, based on a simple score
    # score +3 if range present, +1 if unit present
    best_score: Dict[str, int] = {}

    for idx, (pg, ln) in enumerate(lines):
        key = _match_label_line(ln)
        if not key:
            continue

        # Find the exact label pattern for this key
        label_pat = None
        for ck, cp in LABEL_TO_CANONICAL:
            if ck == key:
                label_pat = cp
                break
        if label_pat is None:
            continue

        # 1) Inline parsing on the same row
        inline = _parse_inline_row(ln, label_pat)
        if inline:
            v, unit, lo, hi = inline
            if _plausible_value(key, v) and _plausible_range(key, lo, hi):
                score = (3 if (lo is not None and hi is not None) else 0) + (1 if unit else 0)
                if key not in best_score or score > best_score[key]:
                    values[key] = float(v)
                    # default range if missing
                    src = "regex_inline"
                    if lo is None or hi is None:
                        dlo, dhi, dunit = _default_details_if_missing(
                            key, unit=unit, gender=gender, pregnancy=pregnancy, trimester=trimester
                        )
                        if dlo is not None and dhi is not None:
                            lo, hi = dlo, dhi
                            src = "default"
                        unit = dunit
                    details[key] = {
                        "unit": _clean_unit(unit) or unit,
                        "low": float(lo) if lo is not None else None,
                        "high": float(hi) if hi is not None else None,
                        "source": src,
                    }
                    evidence[key] = {"source": "regex", "page": pg, "snippet": ln[:240]}
                    best_score[key] = score
            continue

        # 2) Lookahead parsing (label line then value lines)
        parsed = _parse_value_near_label(lines, idx, lookahead=18)
        if not parsed:
            continue
        v, unit, lo, hi, ev_pg, ev_snippet = parsed

        if not _plausible_value(key, v):
            continue
        if not _plausible_range(key, lo, hi):
            continue

        score = (3 if (lo is not None and hi is not None) else 0) + (1 if unit else 0)
        if key in best_score and score <= best_score[key]:
            continue

        values[key] = float(v)
        src = "regex"
        if lo is None or hi is None:
            dlo, dhi, dunit = _default_details_if_missing(
                key, unit=unit, gender=gender, pregnancy=pregnancy, trimester=trimester
            )
            if dlo is not None and dhi is not None:
                lo, hi = dlo, dhi
                src = "default"
            unit = dunit

        details[key] = {
            "unit": _clean_unit(unit) or unit,
            "low": float(lo) if lo is not None else None,
            "high": float(hi) if hi is not None else None,
            "source": src,
        }
        evidence[key] = {"source": "regex", "page": ev_pg, "snippet": (ev_snippet or "")[:240]}
        best_score[key] = score


    # Blood pressure (if present in report header)
    bpm = _BP_RE.search(text)
    if bpm:
        try:
            sbp = float(bpm.group(1))
            dbp = float(bpm.group(2))
            values["Systolic BP"] = sbp
            values["Diastolic BP"] = dbp
            details["Systolic BP"] = {"unit": "mmHg", "low": None, "high": None, "source": "regex_meta"}
            details["Diastolic BP"] = {"unit": "mmHg", "low": None, "high": None, "source": "regex_meta"}
            evidence["Systolic BP"] = {"source": "regex", "page": None, "snippet": bpm.group(0)[:140]}
            evidence["Diastolic BP"] = {"source": "regex", "page": None, "snippet": bpm.group(0)[:140]}
        except Exception:
            pass

        
    # ---- Qualitative extraction
    qualitative = _extract_qualitative(text)

    # attach some evidence for qualitative (best-effort, no page)
    for qk, obj in qualitative.items():
        if qk in evidence:
            continue
        # find a snippet
        m = re.search(rf"(?i)\b{re.escape(qk)}\b.{0,120}", text)
        if m:
            evidence[qk] = {"source": "regex", "page": None, "snippet": m.group(0)[:240]}
        else:
            evidence[qk] = {"source": "regex", "page": None, "snippet": qk}

    missing = [k for k in BIOMARKERS_CANONICAL if k not in values]

    return BiomarkerExtraction(
        values=values,
        details=details,
        qualitative=qualitative,
        evidence=evidence,
        meta=meta,
        missing=missing,
    )
