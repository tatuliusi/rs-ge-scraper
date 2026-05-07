"""
PDF text extraction using pdfplumber.
Falls back gracefully if the library is not installed.
"""
import io
import logging
from typing import Optional

logger = logging.getLogger(__name__)

try:
    import pdfplumber
    _AVAILABLE = True
except ImportError:
    _AVAILABLE = False
    logger.warning("pdfplumber not installed — PDF text extraction is disabled.")


def extract_text(content: bytes) -> Optional[str]:
    """
    Extract all text from a PDF given its raw bytes.
    Returns None if pdfplumber is unavailable or extraction fails.
    """
    if not _AVAILABLE:
        return None

    try:
        pages: list[str] = []
        with pdfplumber.open(io.BytesIO(content)) as pdf:
            for page in pdf.pages:
                text = page.extract_text()
                if text and text.strip():
                    pages.append(text.strip())
        return "\n\n".join(pages) if pages else None
    except Exception as exc:
        logger.warning("PDF extraction failed: %s", exc)
        return None
