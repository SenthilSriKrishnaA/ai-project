"""
document_processors/__init__.py
-------------------------------
Central entry point and dispatcher for multi-format document text extraction
and word occurrence counting.
"""

import os
import re
from .pdf_processor import extract_pdf_text
from .word_processor import extract_docx_text, extract_doc_text
from .excel_processor import extract_xlsx_text, extract_xls_text


def count_word_occurrences(text: str, search_word: str) -> int:
    """
    Count occurrences of a search word in text.
    - Case-insensitive
    - Whole-word matching for word-like inputs (e.g. 'AI' matches 'AI', not 'CLAIM' or 'TRAIN')
    - Substring matching for phrases containing whitespace or special punctuation
    """
    if not text or not search_word:
        return 0

    stripped_word = search_word.strip()
    if not stripped_word:
        return 0

    # If it is a single word (alphanumeric/underscore), use regex word boundaries
    if re.match(r"^\w+$", stripped_word, flags=re.UNICODE):
        pattern = rf"\b{re.escape(stripped_word)}\b"
        return len(re.findall(pattern, text, flags=re.IGNORECASE))
    else:
        # Multi-word phrase or special characters: count substring occurrences (case-insensitive)
        return text.lower().count(stripped_word.lower())


def extract_text(file, filename: str = None) -> str:
    """
    Unified dispatcher to extract text from an uploaded document based on file extension.
    Supported extensions: .pdf, .docx, .doc, .xlsx, .xls, .txt
    """
    if filename is None:
        filename = getattr(file, "filename", "") or ""

    ext = os.path.splitext(filename)[1].lower()

    if ext == ".pdf":
        return extract_pdf_text(file)
    elif ext == ".docx":
        return extract_docx_text(file)
    elif ext == ".doc":
        return extract_doc_text(file)
    elif ext == ".xlsx":
        return extract_xlsx_text(file)
    elif ext == ".xls":
        return extract_xls_text(file)
    elif ext == ".txt":
        if hasattr(file, "read"):
            if hasattr(file, "seek"):
                file.seek(0)
            raw = file.read()
            if hasattr(file, "seek"):
                file.seek(0)
            if isinstance(raw, bytes):
                return raw.decode("utf-8", errors="ignore")
            return str(raw)
        elif isinstance(file, str):
            with open(file, "r", encoding="utf-8", errors="ignore") as f:
                return f.read()
        return ""
    else:
        raise ValueError(f"Unsupported file format: {ext if ext else 'unknown'}")


__all__ = [
    "extract_text",
    "count_word_occurrences",
    "extract_pdf_text",
    "extract_docx_text",
    "extract_doc_text",
    "extract_xlsx_text",
    "extract_xls_text",
]
