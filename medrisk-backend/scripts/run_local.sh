#!/usr/bin/env bash
set -euo pipefail

# Local dev runner (hot reload)
# Usage: ./scripts/run_local.sh

export PYTHONUNBUFFERED=1
uvicorn main:app --host 127.0.0.1 --port 8000 --reload