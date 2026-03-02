# MedRisk AI Backend (FastAPI)

## What this service does
- Accepts lab report PDFs
- Extracts text using PyMuPDF (digital extraction) with OCR fallback (pytesseract / RapidOCR)
- Extracts biomarkers using robust regex patterns
- Optionally calls **Gemini** to fill missing biomarkers (only for fields mentioned in text)
- Predicts risk signals with a **multi-label ML model** (joblib) with a safe rule-based fallback
- Returns a frontend-friendly JSON payload
- Provides a doctor discovery endpoint (Google Places if configured, otherwise OpenStreetMap)

> ⚠️ This is a demo/portfolio project and is **not** a medical diagnosis.

---

## Run locally
```bash
python -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
cp .env.example .env

./scripts/run_local.sh