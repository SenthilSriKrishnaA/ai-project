"""
document_processors/pdf_processor.py
------------------------------------
Text extraction module for PDF documents (.pdf).
Uses pypdf as the primary extractor with PyMuPDF as a robust fallback.
"""

import io
from pypdf import PdfReader


def extract_pdf_text(file) -> str:
    """
    Extract all readable text from a PDF file.
    Accepts a file-like object, Werkzeug FileStorage, or path string.
    """
    text = ""
    
    # Check if file has a read/seek method
    if hasattr(file, "seek"):
        file.seek(0)
    
    # Primary method: pypdf
    try:
        reader = PdfReader(file)
        for page in reader.pages:
            extracted = page.extract_text()
            if extracted:
                text += extracted + "\n"
    except Exception as err:
        # Fallback to PyMuPDF if pypdf encounters an issue
        try:
            import fitz  # PyMuPDF
            if hasattr(file, "seek"):
                file.seek(0)
                file_bytes = file.read()
                doc = fitz.open(stream=file_bytes, filetype="pdf")
            elif isinstance(file, str):
                doc = fitz.open(file)
            else:
                raise err
            
            text = ""
            for page in doc:
                text += page.get_text() + "\n"
            doc.close()
        except Exception:
            # Re-raise original error if fallback also fails
            raise err

    # Reset file pointer if file is reusable
    if hasattr(file, "seek"):
        file.seek(0)

    return text.strip()
