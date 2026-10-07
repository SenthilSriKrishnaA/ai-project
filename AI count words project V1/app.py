from flask import Flask, render_template, request, jsonify
from pypdf import PdfReader
from docx import Document
import os
import io
import tempfile
from werkzeug.utils import secure_filename

# Import AI Document Summary module
from ai_summary import generate_ai_summary, generate_summary

# Import Document Processors
from document_processors import (
    extract_text,
    count_word_occurrences,
    extract_pdf_text,
    extract_docx_text,
    extract_doc_text,
    extract_xlsx_text,
    extract_xls_text
)


app = Flask(__name__)

# Configure upload folder for safe temporary handling
UPLOAD_FOLDER = os.path.join(os.path.dirname(os.path.abspath(__file__)), "uploads")
os.makedirs(UPLOAD_FOLDER, exist_ok=True)
app.config["UPLOAD_FOLDER"] = UPLOAD_FOLDER
app.config["MAX_CONTENT_LENGTH"] = 100 * 1024 * 1024  # 100MB max total payload


# Count how many times the text appears (legacy whole-word / substring counter)
def count_occurrences(text, search_word):
    """
    Preserved legacy word occurrence counter.
    Uses whole-word matching via document_processors when applicable.
    """
    return count_word_occurrences(text, search_word)


# Read PDF (legacy function preserved for backward compatibility)
def read_pdf(file):
    return extract_pdf_text(file)


# Read DOCX (legacy function preserved for backward compatibility)
def read_docx(file):
    return extract_docx_text(file)


# Read Excel (legacy function preserved for backward compatibility)
def read_excel(file):
    import pandas as pd

    excel = pd.ExcelFile(file)
    text = ""
    for sheet_name in excel.sheet_names:
        dataframe = pd.read_excel(file, sheet_name=sheet_name)
        text += dataframe.to_string()
    return text


# Helper function to extract text from an uploaded file using existing readers
def extract_text_from_file(file):
    filename = getattr(file, "filename", "") or ""
    filename_lower = filename.lower()

    if filename_lower.endswith(".pdf"):
        return read_pdf(file)
    elif filename_lower.endswith(".docx"):
        return read_docx(file)
    elif filename_lower.endswith(".doc"):
        return extract_doc_text(file)
    elif filename_lower.endswith(".xlsx"):
        return extract_xlsx_text(file)
    elif filename_lower.endswith(".xls"):
        return extract_xls_text(file)
    elif filename_lower.endswith(".txt"):
        if hasattr(file, "seek"):
            file.seek(0)
        content = file.read()
        if hasattr(file, "seek"):
            file.seek(0)
        return content.decode("utf-8", errors="ignore") if isinstance(content, bytes) else str(content)
    else:
        return None


# Helper to process a single document independently
def process_single_document(uploaded_file, search_word):
    """
    Independently process one uploaded document:
    1. Validate filename
    2. Extract text
    3. Count search word
    4. Generate independent AI summary
    5. Return independent result object
    """
    raw_filename = uploaded_file.filename or "unknown_file"
    safe_name = secure_filename(raw_filename) or "uploaded_doc"
    ext = os.path.splitext(raw_filename)[1].lower()
    file_type = ext.lstrip(".") if ext else "unknown"

    result = {
        "filename": raw_filename,
        "file_type": file_type,
        "word": search_word,
        "word_count": 0,
        "summary": "",
        "status": "error",
        "error": None
    }

    # Verify supported extension
    allowed_extensions = {".pdf", ".doc", ".docx", ".xls", ".xlsx", ".txt"}
    if ext not in allowed_extensions:
        result["error"] = f"Unsupported file format '{ext}'. Supported formats: PDF, DOC, DOCX, XLS, XLSX, TXT."
        return result

    # Save to a temporary file safely for robust stream reading
    temp_path = None
    try:
        temp_fd, temp_path = tempfile.mkstemp(suffix=ext, dir=app.config["UPLOAD_FOLDER"])
        os.close(temp_fd)
        if hasattr(uploaded_file, "seek"):
            uploaded_file.seek(0)
        uploaded_file.save(temp_path)

        # 1. Extract text
        with open(temp_path, "rb") as f_in:
            text = extract_text(f_in, raw_filename)

        if not text or not text.strip():
            result["error"] = "Unable to extract text (document appears empty or contains no readable text)."
            result["status"] = "error"
            return result

        # 2. Count search word independently
        count = count_word_occurrences(text, search_word)
        result["word_count"] = count

        # 3. Generate independent AI summary
        ai_res = generate_summary(text)
        if ai_res.get("success"):
            result["summary"] = ai_res.get("summary", "")
            result["status"] = "success"
        else:
            # Word count succeeded, but AI summary failed or was unavailable
            result["summary"] = ai_res.get("message", "AI summary unavailable.")
            result["status"] = "warning"
            result["error"] = ai_res.get("message", "AI summary could not be generated.")

        return result

    except Exception as err:
        result["error"] = f"Processing failed: {str(err)}"
        result["status"] = "error"
        return result

    finally:
        # Clean up temporary file safely
        if temp_path and os.path.exists(temp_path):
            try:
                os.remove(temp_path)
            except Exception:
                pass


# Main page
@app.route("/")
def home():
    return render_template("index.html")


# Search API (Backward-compatible single-file search + multi-file support)
@app.route("/search", methods=["POST"])
def search():
    search_word = request.form.get("search_word") or request.form.get("word")

    # Check for multi-file upload under 'files' or 'files[]'
    uploaded_files = request.files.getlist("files[]") or request.files.getlist("files")

    # If single file is provided via 'file' parameter
    single_file = request.files.get("file")

    if not single_file and not uploaded_files:
        return jsonify({
            "message": "Please upload a file",
            "success": False
        })

    if not search_word or not search_word.strip():
        return jsonify({
            "message": "Please enter a word or text",
            "success": False
        })

    # If single file parameter was passed, maintain exact legacy single-file response
    if single_file and not uploaded_files:
        filename = single_file.filename.lower()
        try:
            text = extract_text_from_file(single_file)
            if text is None:
                return jsonify({"message": "Unsupported file type"})

            count = count_occurrences(text, search_word)
            if count > 0:
                return jsonify({
                    "found": True,
                    "count": count,
                    "message": f'"{search_word}" found {count} time(s)'
                })
            else:
                return jsonify({
                    "found": False,
                    "count": 0,
                    "message": f'"{search_word}" not found'
                })
        except Exception as error:
            return jsonify({"message": f"Error: {str(error)}"})

    # If multiple files provided, route to multi-document analyzer
    return analyze()


# Multi-Document Upload & Analysis API Endpoint
@app.route("/analyze", methods=["POST"])
def analyze():
    search_word = request.form.get("search_word") or request.form.get("word")
    if search_word:
        search_word = search_word.strip()

    # Collect files from any accepted parameter names
    files = request.files.getlist("files[]") or request.files.getlist("files")
    if not files:
        single_file = request.files.get("file")
        if single_file:
            files = [single_file]

    # Filter out empty file inputs
    valid_files = [f for f in files if f and f.filename and f.filename.strip()]

    # Validation: Documents
    if not valid_files:
        return jsonify({
            "success": False,
            "message": "Please upload at least one document.",
            "results": []
        }), 400

    # Validation: Search Word
    if not search_word:
        return jsonify({
            "success": False,
            "message": "Please enter a word or phrase to search.",
            "results": []
        }), 400

    results = []
    processed_count = 0
    failed_count = 0

    # Process each file completely independently
    for doc_file in valid_files:
        doc_result = process_single_document(doc_file, search_word)
        results.append(doc_result)
        if doc_result["status"] in ("success", "warning"):
            processed_count += 1
        else:
            failed_count += 1

    return jsonify({
        "success": True,
        "results": results,
        "total_files": len(results),
        "processed": processed_count,
        "failed": failed_count,
        "search_word": search_word
    })


# AI Document Summary API endpoint (preserved for backward compatibility)
@app.route("/summarize", methods=["POST"])
def summarize():
    file = request.files.get("file")

    if not file or file.filename == "":
        return jsonify({
            "success": False,
            "message": "Please upload a document first."
        })

    try:
        text = extract_text_from_file(file)

        if text is None:
            return jsonify({
                "success": False,
                "message": "Unsupported file type"
            })

        if not text.strip():
            return jsonify({
                "success": False,
                "message": "Document contains no readable text."
            })

        result = generate_ai_summary(text)
        return jsonify(result)

    except Exception as error:
        return jsonify({
            "success": False,
            "message": f"Error: {str(error)}"
        })


if __name__ == "__main__":
    app.run(
        debug=True,
        port=5000
    )