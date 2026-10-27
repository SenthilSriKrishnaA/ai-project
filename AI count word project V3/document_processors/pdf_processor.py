"""
document_processors/pdf_processor.py
------------------------------------
High-performance text extraction module for PDF documents (.pdf).
Uses PyMuPDF (C++ backend) as the primary ultra-fast extractor with pypdf as a fallback.
"""

import io


def extract_pdf_text(file) -> str:
    """
    Extract all readable text from a PDF file.
    Accepts bytes, file-like object, Werkzeug FileStorage, or path string.
    """
    # Primary ultra-fast method: PyMuPDF
    try:
        import pymupdf

        doc = None
        if isinstance(file, (bytes, bytearray)):
            doc = pymupdf.open(stream=file, filetype="pdf")
        elif hasattr(file, "read"):
            if hasattr(file, "seek"):
                file.seek(0)
            file_bytes = file.read()
            if hasattr(file, "seek"):
                file.seek(0)
            doc = pymupdf.open(stream=file_bytes, filetype="pdf")
        elif isinstance(file, str):
            doc = pymupdf.open(file)
        else:
            raise TypeError("Unsupported file type for PDF processing.")

        text_pages = []
        for page in doc:
            page_text = page.get_text()
            if page_text:
                text_pages.append(page_text)
        doc.close()

        extracted = "\n".join(text_pages).strip()
        if extracted:
            return extracted
    except Exception:
        pass

    # Fallback method: pypdf
    try:
        from pypdf import PdfReader

        if hasattr(file, "seek"):
            file.seek(0)

        reader = PdfReader(file if not isinstance(file, (bytes, bytearray)) else io.BytesIO(file))
        text_pages = []
        for page in reader.pages:
            extracted_page = page.extract_text()
            if extracted_page:
                text_pages.append(extracted_page)

        if hasattr(file, "seek"):
            file.seek(0)

        return "\n".join(text_pages).strip()
    except Exception as err:
        if hasattr(file, "seek"):
            file.seek(0)
        raise err

