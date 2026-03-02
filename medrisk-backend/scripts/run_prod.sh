#!/usr/bin/env bash
set -euo pipefail

# Production-ish runner (no reload). For real production, use Docker/Kubernetes.
# Usage: UVICORN_WORKERS=2 ./scripts/run_prod.sh

export PYTHONUNBUFFERED=1
WORKERS="${UVICORN_WORKERS:-2}"
uvicorn main:app --host 0.0.0.0 --port 8000 --proxy-headers --workers "$WORKERS"