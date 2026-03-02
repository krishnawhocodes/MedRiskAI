FROM python:3.12-slim

# ---- System deps ----
# tesseract-ocr: optional OCR backend (pytesseract)
# libglib2.0-0/libgomp1: commonly needed by opencv/numpy wheels
RUN apt-get update \
  && apt-get install -y --no-install-recommends \
       tesseract-ocr \
       libglib2.0-0 \
       libgomp1 \
  && rm -rf /var/lib/apt/lists/*

# ---- App user ----
RUN useradd -m -u 10001 appuser
WORKDIR /app

# ---- Python deps ----
COPY requirements.txt ./
RUN pip install --no-cache-dir -r requirements.txt

# ---- Copy source ----
COPY . ./

# Drop privileges
USER appuser

EXPOSE 8000

# ---- Production server ----
# You can override workers via UVICORN_WORKERS env var.
ENV UVICORN_WORKERS=2
CMD ["sh", "-c", "uvicorn main:app --host 0.0.0.0 --port ${PORT:-8000} --proxy-headers --workers ${UVICORN_WORKERS:-2}"]