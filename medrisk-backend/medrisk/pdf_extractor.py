from __future__ import annotations

from dataclasses import dataclass
from typing import List, Optional, Tuple

import fitz  # PyMuPDF

from .config import MAX_PAGES, OCR_ENABLED, OCR_DPI, OCR_LANG
from .text_utils import normalize_text, text_quality, TextQuality


@dataclass
class PDFTextResult:
    text: str
    method: str  # "digital" | "ocr" | "mixed"
    pages: int
    quality: TextQuality
    warnings: List[str]


def _is_low_quality_text(page_text: str) -> bool:
    """
    Decide if page text is "too poor" and needs OCR.
    """
    t = (page_text or "").strip()
    if len(t) < 40:
        return True

    q = text_quality(t)

    # heuristics: too little content / too few keywords / too low overall score
    if q.char_count < 250:
        return True
    if q.keyword_hits == 0 and q.score < 0.35:
        return True
    if q.score < 0.28:
        return True

    return False


def _render_page_image(page: fitz.Page, dpi: int) -> "PIL.Image.Image":
    """
    Render a PDF page to a PIL image using PyMuPDF.
    """
    pix = page.get_pixmap(dpi=dpi, alpha=False)  # alpha False = RGB
    try:
        from PIL import Image  # type: ignore
    except Exception as e:
        raise RuntimeError("PIL (Pillow) not installed. Install: pip install pillow") from e

    img = Image.frombytes("RGB", (pix.width, pix.height), pix.samples)
    return img


def _ocr_with_pytesseract(img: "PIL.Image.Image", lang: str) -> Optional[str]:
    """
    OCR using pytesseract (requires external Tesseract installation).
    """
    try:
        import pytesseract  # type: ignore
    except Exception:
        return None

    try:
        # psm 6 is good for uniform blocks of text (typical reports)
        config = "--oem 3 --psm 6"
        return pytesseract.image_to_string(img, lang=lang, config=config) or ""
    except Exception:
        return None


_RAPID_OCR = None


def _ocr_with_rapidocr(img: "PIL.Image.Image") -> Optional[str]:
    """
    OCR using rapidocr_onnxruntime (no external tesseract required).
    """
    global _RAPID_OCR

    try:
        from rapidocr_onnxruntime import RapidOCR  # type: ignore
    except Exception:
        return None

    try:
        if _RAPID_OCR is None:
            _RAPID_OCR = RapidOCR()

        # RapidOCR expects ndarray (OpenCV style) but can work with PIL -> convert via numpy
        import numpy as np  # type: ignore

        arr = np.array(img)
        result, _ = _RAPID_OCR(arr)

        # result = list of (box, text, confidence)
        if not result:
            return ""

        lines: List[str] = []
        for item in result:
            if not item or len(item) < 2:
                continue
            text = str(item[1] or "").strip()
            if text:
                lines.append(text)

        return "\n".join(lines)
    except Exception:
        return None


def _ocr_page(page: fitz.Page, *, dpi: int, lang: str, warnings: List[str]) -> str:
    """
    OCR a single page. We try pytesseract first, then RapidOCR fallback.
    """
    img = _render_page_image(page, dpi=dpi)

    # Try pytesseract first
    txt = _ocr_with_pytesseract(img, lang=lang)
    if txt is not None:
        return txt

    warnings.append(
        "pytesseract OCR not available (Tesseract not installed or pytesseract missing). "
        "Falling back to RapidOCR."
    )

    txt2 = _ocr_with_rapidocr(img)
    if txt2 is not None:
        return txt2

    warnings.append("RapidOCR not available. Install: pip install rapidocr-onnxruntime numpy pillow")
    return ""


def extract_report_text(pdf_bytes: bytes) -> PDFTextResult:
    """
    Extract text from a PDF.
    - First tries digital extraction (PyMuPDF get_text)
    - If OCR_ENABLED and quality is poor, runs OCR on low-quality pages
    Returns a combined string with page markers:
        <<<PAGE 1>>>
        ...
        <<<PAGE 2>>>
        ...
    """
    warnings: List[str] = []
    if not pdf_bytes or not pdf_bytes.startswith(b"%PDF"):
        return PDFTextResult(
            text="",
            method="digital",
            pages=0,
            quality=text_quality(""),
            warnings=["Invalid PDF bytes."],
        )

    doc = fitz.open(stream=pdf_bytes, filetype="pdf")
    total_pages = doc.page_count

    if total_pages <= 0:
        return PDFTextResult(
            text="",
            method="digital",
            pages=0,
            quality=text_quality(""),
            warnings=["PDF had 0 pages."],
        )

    # Respect MAX_PAGES
    page_limit = total_pages
    if isinstance(MAX_PAGES, int) and MAX_PAGES > 0:
        page_limit = min(total_pages, MAX_PAGES)
    elif MAX_PAGES == 0:
        page_limit = total_pages

    used_digital = False
    used_ocr = False

    parts: List[str] = []

    for i in range(page_limit):
        page = doc.load_page(i)

        digital_text = page.get_text("text") or ""
        digital_text = digital_text.strip()

        need_ocr = OCR_ENABLED and _is_low_quality_text(digital_text)

        final_text = digital_text

        if need_ocr:
            used_ocr = True
            ocr_text = _ocr_page(page, dpi=OCR_DPI, lang=OCR_LANG, warnings=warnings)
            ocr_text = (ocr_text or "").strip()

            # choose whichever yields more useful content
            if len(ocr_text) > len(digital_text):
                final_text = ocr_text
            else:
                # still accept digital if it is better
                final_text = digital_text

        if final_text.strip():
            used_digital = used_digital or bool(digital_text.strip())
            parts.append(f"<<<PAGE {i+1}>>>")
            parts.append(final_text)

    combined = "\n".join(parts)
    combined = normalize_text(combined)

    method = "digital"
    if used_ocr and used_digital:
        method = "mixed"
    elif used_ocr and not used_digital:
        method = "ocr"

    q = text_quality(combined)

    # Extra warning if text still too low
    if q.char_count < 250:
        warnings.append(
            "Extracted text is still very low. The PDF may be blurry, handwritten, or highly compressed."
        )

    return PDFTextResult(
        text=combined,
        method=method,
        pages=page_limit,
        quality=q,
        warnings=warnings,
    )
