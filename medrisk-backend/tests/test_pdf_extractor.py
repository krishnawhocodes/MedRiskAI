from __future__ import annotations

from medrisk.pdf_extractor import extract_report_text


def test_invalid_pdf_bytes():
    res = extract_report_text(b"not a pdf")
    assert res.pages == 0
    assert res.text == ""
    assert res.warnings