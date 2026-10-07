"""
document_processors/word_processor.py
-------------------------------------
Text extraction module for Microsoft Word documents:
- .docx (Word 2007+ OpenXML format) using python-docx
- .doc (Word 97-2003 OLE binary format) using PyMuPDF / olefile / striprtf
"""

import io
import re
from docx import Document


def extract_docx_text(file) -> str:
    """
    Extract all readable text from a .docx file (paragraphs and tables).
    Accepts a file-like object, Werkzeug FileStorage, or path string.
    """
    if hasattr(file, "seek"):
        file.seek(0)

    doc = Document(file)
    text_chunks = []

    # Extract paragraphs
    for paragraph in doc.paragraphs:
        if paragraph.text.strip():
            text_chunks.append(paragraph.text.strip())

    # Extract tables
    for table in doc.tables:
        for row in table.rows:
            row_text = [cell.text.strip() for cell in row.cells if cell.text.strip()]
            if row_text:
                text_chunks.append(" | ".join(row_text))

    if hasattr(file, "seek"):
        file.seek(0)

    return "\n".join(text_chunks).strip()


def extract_doc_text(file) -> str:
    """
    Extract all readable text from a legacy .doc file.
    Handles OLE2 WordDocument streams, RTF formats, and PyMuPDF document streams.
    """
    if hasattr(file, "seek"):
        file.seek(0)
        content_bytes = file.read()
        file.seek(0)
    elif isinstance(file, str):
        with open(file, "rb") as f:
            content_bytes = f.read()
    else:
        raise ValueError("Unsupported file input for .doc processing.")

    if not content_bytes:
        return ""

    # Check 1: Disguised DOCX (ZIP archive starting with PK)
    if content_bytes.startswith(b"PK\x03\x04"):
        return extract_docx_text(io.BytesIO(content_bytes))

    # Check 2: Disguised RTF format
    if content_bytes.startswith(b"{\\rtf"):
        try:
            from striprtf.striprtf import rtf_to_text
            rtf_str = content_bytes.decode("utf-8", errors="ignore")
            text = rtf_to_text(rtf_str)
            if text and text.strip():
                return text.strip()
        except Exception:
            pass

    # Check 3: PyMuPDF extraction
    try:
        import fitz
        doc = fitz.open(stream=content_bytes, filetype="doc")
        text = ""
        for page in doc:
            text += page.get_text() + "\n"
        doc.close()
        if text.strip():
            return text.strip()
    except Exception:
        pass

    # Check 4: OLE2 Compound File parser (Word 97-2003 Binary)
    try:
        import olefile
        if olefile.isOleFile(io.BytesIO(content_bytes)):
            ole = olefile.OleFileIO(io.BytesIO(content_bytes))
            
            # Read WordDocument stream
            stream_data = b""
            if ole.exists("WordDocument"):
                stream_data += ole.openstream("WordDocument").read()
            if ole.exists("1Table"):
                stream_data += ole.openstream("1Table").read()
            if ole.exists("0Table"):
                stream_data += ole.openstream("0Table").read()

            ole.close()

            if stream_data:
                # Extract text chunks from binary stream (printable UTF-16LE and ASCII sequences)
                # Filter out control codes and extract runs of printable text
                text_runs = []
                
                # Try UTF-16LE runs (common in Word 97-2003 for Unicode characters)
                utf16_matches = re.findall(rb'(?:[\x20-\x7e\r\n\t]\x00){3,}', stream_data)
                for match in utf16_matches:
                    try:
                        decoded = match.decode('utf-16le', errors='ignore').strip()
                        if len(decoded) > 2:
                            text_runs.append(decoded)
                    except Exception:
                        pass

                # Try ASCII / latin-1 runs
                ascii_matches = re.findall(rb'[\x20-\x7e\r\n\t]{4,}', stream_data)
                for match in ascii_matches:
                    try:
                        decoded = match.decode('latin-1', errors='ignore').strip()
                        # Filter out common binary header artifacts
                        if len(decoded) > 2 and not any(k in decoded.lower() for k in ["times new roman", "calibri", "normal.dotm"]):
                            text_runs.append(decoded)
                    except Exception:
                        pass

                if text_runs:
                    # Deduplicate while preserving order
                    seen = set()
                    cleaned_runs = []
                    for t in text_runs:
                        if t not in seen:
                            seen.add(t)
                            cleaned_runs.append(t)
                    return "\n".join(cleaned_runs).strip()
    except Exception:
        pass

    # Fallback: Extract ASCII strings from raw bytes
    ascii_strings = re.findall(rb'[\x20-\x7e\r\n\t]{4,}', content_bytes)
    extracted = [s.decode('latin-1', errors='ignore').strip() for s in ascii_strings if len(s.strip()) > 3]
    return "\n".join(extracted).strip()
