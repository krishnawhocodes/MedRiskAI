from __future__ import annotations

import logging
import time
from typing import Any, Dict, List, Optional

from dotenv import load_dotenv
from fastapi import FastAPI, File, HTTPException, Query, UploadFile
from fastapi.middleware.cors import CORSMiddleware
from starlette.requests import Request
from starlette.responses import JSONResponse

load_dotenv()

from medrisk.config import APP_TITLE, CORS_ORIGINS, ENV, MAX_PDF_MB
from medrisk.extraction_service import extract_structured_report
from medrisk.findings import build_findings
from medrisk.ml.predictor import predict_health_risks
from medrisk.risk_finalize import finalize_report_payload
from medrisk.doctor_service import search_nearby_doctors

logger = logging.getLogger("medrisk")


def _configure_logging() -> None:
    # Uvicorn config usually sets handlers; this makes local python main.py nicer.
    if logger.handlers:
        return
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s %(levelname)s %(name)s - %(message)s",
    )


_configure_logging()

app = FastAPI(title=APP_TITLE)

allow_all = len(CORS_ORIGINS) == 1 and CORS_ORIGINS[0] == "*"
app.add_middleware(
    CORSMiddleware,
    allow_origins=CORS_ORIGINS,
    allow_credentials=False if allow_all else True,
    allow_methods=["*"],
    allow_headers=["*"]
)


# --------- Middleware: request timing + basic request id ---------
@app.middleware("http")
async def timing_middleware(request: Request, call_next):
    start = time.perf_counter()
    try:
        response = await call_next(request)
    finally:
        elapsed_ms = (time.perf_counter() - start) * 1000.0
        # Keep logs lightweight and privacy-friendly (no body logging)
        logger.info("%s %s -> %.1fms", request.method, request.url.path, elapsed_ms)
    return response


@app.exception_handler(HTTPException)
async def http_exception_handler(_request: Request, exc: HTTPException):
    # Ensure consistent JSON error structure
    return JSONResponse(status_code=exc.status_code, content={"detail": exc.detail})


# --------- Helpers ---------
async def _read_upload_limited(file: UploadFile, *, max_mb: float) -> bytes:
    """Read UploadFile safely with a hard size limit."""
    max_bytes = int(max_mb * 1024 * 1024)
    if max_bytes <= 0:
        max_bytes = 15 * 1024 * 1024

    buf = bytearray()
    chunk_size = 1024 * 1024  # 1 MB

    while True:
        chunk = await file.read(chunk_size)
        if not chunk:
            break
        buf.extend(chunk)
        if len(buf) > max_bytes:
            raise HTTPException(
                status_code=413,
                detail=f"PDF too large. Max allowed is {max_mb:g} MB.",
            )

    return bytes(buf)


def _ensure_pdf(content_type: Optional[str], filename: str) -> None:
    ct = (content_type or "").lower()
    # Some browsers use application/octet-stream; accept if filename ends with .pdf
    if ct not in ("application/pdf", "application/x-pdf", "application/octet-stream") and not filename.lower().endswith(
        ".pdf"
    ):
        raise HTTPException(status_code=400, detail="Invalid file type. Please upload a PDF.")


# --------- Routes ---------
@app.get("/api/health")
async def api_health() -> Dict[str, Any]:
    return {"status": "ok", "env": ENV}


@app.post("/api/upload")
async def api_upload_report(file: UploadFile = File(...)) -> Dict[str, Any]:
    _ensure_pdf(file.content_type, file.filename or "")

    pdf_bytes = await _read_upload_limited(file, max_mb=MAX_PDF_MB)

    try:
        structured = await extract_structured_report(pdf_bytes)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"PDF extraction failed: {type(e).__name__}: {e}")

    extracted_values = {k: v for k, v in structured.items() if isinstance(v, (int, float))}
    if not extracted_values:
        raise HTTPException(status_code=400, detail="Could not detect any biomarkers. Try a clearer PDF or enable OCR.")

    findings = build_findings(structured)

    prediction = predict_health_risks(structured)
    # keep payload small for frontend
    prediction.pop("raw_probabilities", None)

    return finalize_report_payload(structured, findings, prediction)


@app.post("/api/extract-only")
async def api_extract_only(file: UploadFile = File(...)) -> Dict[str, Any]:
    _ensure_pdf(file.content_type, file.filename or "")
    pdf_bytes = await _read_upload_limited(file, max_mb=MAX_PDF_MB)
    return await extract_structured_report(pdf_bytes)

from fastapi import Query
from typing import Optional, Dict, Any
from medrisk.doctor_service import search_nearby_doctors

@app.get("/api/nearby-doctors")
async def api_nearby_doctors(
    lat: float = Query(..., ge=-90.0, le=90.0),
    lng: float = Query(..., ge=-180.0, le=180.0),
    specialty: Optional[str] = Query(None),
    radius_km: float = Query(12.0, ge=2.0, le=25.0),
    limit: int = Query(30, ge=1, le=60),
) -> Dict[str, Any]:
    doctors, meta = await search_nearby_doctors(
        lat=lat,
        lng=lng,
        specialty=specialty,
        radius_km=radius_km,
        limit=limit,
    )
    return {"doctors": doctors, "meta": meta}


if __name__ == "__main__":
    import uvicorn

    print("Starting MedRisk AI backend server...")
    print("API docs: http://127.0.0.1:8000/docs")
    uvicorn.run("main:app", host="127.0.0.1", port=8000, reload=True)