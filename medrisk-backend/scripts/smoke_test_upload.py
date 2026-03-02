"""Quick smoke test for /api/upload.

Usage:
  python scripts/smoke_test_upload.py path/to/report.pdf

Assumes backend is running on http://127.0.0.1:8000
"""

from __future__ import annotations

import sys
import httpx


def main() -> int:
    if len(sys.argv) < 2:
        print("Usage: python scripts/smoke_test_upload.py /path/to/report.pdf")
        return 2

    pdf_path = sys.argv[1]

    with open(pdf_path, "rb") as f:
        files = {"file": (pdf_path.split("/")[-1], f, "application/pdf")}
        r = httpx.post("http://127.0.0.1:8000/api/upload", files=files, timeout=120.0)

    print("Status:", r.status_code)
    if r.headers.get("content-type", "").startswith("application/json"):
        print(r.json())
    else:
        print(r.text)

    return 0 if r.status_code == 200 else 1


if __name__ == "__main__":
    raise SystemExit(main())