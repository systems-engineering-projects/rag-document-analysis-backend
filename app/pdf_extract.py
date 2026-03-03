"""
Extract plain text from PDF bytes for ingest.
Uses pypdf; raises ValueError on empty output or unreadable/encrypted PDFs.
"""

import re
from io import BytesIO

from pypdf import PdfReader


def extract_text_from_pdf(data: bytes) -> str:
    """
    Extract full text from PDF bytes. Returns stripped string.

    Raises:
        ValueError: If PDF is encrypted, unreadable, or yields no text.
    """
    if not data or len(data) < 100:
        raise ValueError("File too small or empty to be a valid PDF")
    try:
        reader = PdfReader(BytesIO(data))
        if reader.is_encrypted:
            raise ValueError("PDF is encrypted; cannot extract text")
        parts = []
        for page in reader.pages:
            text = page.extract_text()
            if text:
                parts.append(text)
        text = "\n".join(parts).strip()
        if not text or len(text) < 10:
            raise ValueError(
                "PDF produced no extractable text (may be image-only or empty)"
            )
        return text
    except ValueError:
        raise
    except Exception as e:
        raise ValueError(f"Could not read PDF: {e}") from e


def sanitize_doc_id_from_filename(filename: str) -> str:
    """
    Derive a safe doc_id from a filename (e.g. "Report 2024.pdf" -> "report-2024").
    Replaces non-alphanumeric with a single hyphen and lowercases.
    """
    stem = filename
    if filename.lower().endswith(".pdf"):
        stem = filename[:-4]
    # Replace non-alphanumeric with hyphen, collapse multiple hyphens, strip
    safe = re.sub(r"[^a-zA-Z0-9]+", "-", stem).strip("-").lower()
    return safe or "uploaded-pdf"
