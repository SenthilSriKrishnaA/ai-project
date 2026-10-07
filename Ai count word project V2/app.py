from flask import Flask, render_template, request, jsonify
import os
import tempfile
import json
import re
from werkzeug.utils import secure_filename

from ai_summary import (
    generate_ai_summary,
    generate_summary,
    generate_relevant_summary,
    generate_general_summary
)

from retrieval import (
    find_relevant_documents,
    extract_query_structure,
    topic_counts
)

from document_processors import (
    extract_text,
    count_word_occurrences,
    extract_pdf_text,
    extract_docx_text,
    extract_doc_text,
    extract_xlsx_text,
    extract_xls_text
)
from project_matcher import (
    find_similar_projects,
    get_repository_files,
    read_project_file,
    MAX_REPOSITORY_FILES,
    SUPPORTED_EXTENSIONS
)
from ai_summary import call_ollama, limit_text


app = Flask(__name__)


# ============================================================
# UPLOAD CONFIGURATION
# ============================================================

UPLOAD_FOLDER = os.path.join(
    os.path.dirname(os.path.abspath(__file__)),
    "uploads"
)

os.makedirs(UPLOAD_FOLDER, exist_ok=True)

app.config["UPLOAD_FOLDER"] = UPLOAD_FOLDER

# Maximum total upload request size: 100 MB
app.config["MAX_CONTENT_LENGTH"] = 100 * 1024 * 1024

# Maximum number of files allowed in one analysis
MAX_FILES_PER_ANALYSIS = 10


def _project_assistant(idea, matches):
    """Generate recommendations without making repository facts up on failure."""
    prompt = f"""You are an AI project assistant.
Student project idea: {idea}
Repository matches: {limit_text(str(matches), 2200)}
Return concise sections for Features, Modules, Technologies, Architecture,
Datasets, Evaluation, Testing, Limitations, Future scope, and Challenges.
Do not claim the project is completely new. Use only the supplied context."""
    response = call_ollama(prompt, temperature=0.15)
    if response.get("success"):
        return response["response"]
    return (
        "Features: define the core user workflow and measurable outcomes.\n"
        "Modules: separate ingestion, matching, reporting, and evaluation.\n"
        "Technologies: reuse the existing Flask, document processors, and Ollama stack.\n"
        "Architecture: keep extraction, similarity scoring, and AI explanation isolated.\n"
        "Evaluation: measure precision/recall of matches and response quality.\n"
        "Testing: cover highly similar, related, unrelated, and paraphrased ideas.\n"
        "Limitations: results are limited to the uploaded repository and local model.\n"
        "Future scope: add reviewed embeddings and repository versioning."
    )


def _identify_project_concepts(idea):
    """Use Ollama to identify a searchable theme, with a deterministic fallback."""
    prompt = f"""Analyze this student project idea:
{idea}
Return JSON only with this exact shape:
{{"main_theme":"short searchable phrase","supporting_concepts":["concept 1","concept 2"]}}
The main theme must be a concrete 1-5 word project topic, not a sentence."""
    response = call_ollama(prompt, temperature=0.05)
    if response.get("success"):
        try:
            parsed = json.loads(response["response"])
            theme = str(parsed.get("main_theme", "")).strip()
            concepts = parsed.get("supporting_concepts", [])
            if theme and isinstance(concepts, list):
                return {
                    "main_theme": theme,
                    "supporting_concepts": [
                        str(item).strip() for item in concepts if str(item).strip()
                    ][:10]
                }
        except (TypeError, ValueError, json.JSONDecodeError):
            pass

    structure = extract_query_structure(idea)
    topics = structure.get("display_topics", [])
    if topics:
        return {
            "main_theme": topics[0],
            "supporting_concepts": topics[1:]
        }
    words = [
        word for word in re.findall(r"[A-Za-z0-9]+", idea)
        if len(word) >= 3
    ]
    return {
        "main_theme": " ".join(words[:5]) or idea,
        "supporting_concepts": words[5:10]
    }


# ============================================================
# LEGACY WORD COUNT
# ============================================================

def count_occurrences(text, search_word):
    """
    Preserved legacy word occurrence counter.
    """
    return count_word_occurrences(text, search_word)


def read_pdf(file):
    return extract_pdf_text(file)


def read_docx(file):
    return extract_docx_text(file)


def read_excel(file):
    import pandas as pd

    excel = pd.ExcelFile(file)

    text = ""

    for sheet_name in excel.sheet_names:

        dataframe = pd.read_excel(
            file,
            sheet_name=sheet_name
        )

        text += dataframe.to_string()

    return text


# ============================================================
# FILE TEXT EXTRACTION
# ============================================================

def extract_text_from_file(file):

    filename = getattr(
        file,
        "filename",
        ""
    ) or ""

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

        if isinstance(content, bytes):
            return content.decode(
                "utf-8",
                errors="ignore"
            )

        return str(content)

    else:

        return None


# ============================================================
# PROCESS ONE DOCUMENT
# ============================================================

def process_single_document(
    uploaded_file,
    search_word,
    query_structure=None
):

    raw_filename = uploaded_file.filename or "unknown_file"

    ext = os.path.splitext(
        raw_filename
    )[1].lower()

    file_type = (
        ext.lstrip(".")
        if ext
        else "unknown"
    )

    structure = (
        query_structure
        or extract_query_structure(search_word)
    )

    display_topics = structure.get(
        "display_topics",
        []
    )

    result = {
        "filename": raw_filename,

        "file_type": file_type,

        "word": (
            display_topics[0]
            if display_topics
            else search_word
        ),

        "query": search_word,

        "topics": display_topics,

        "topic_counts": {},

        "word_count": 0,

        "text": "",

        "summary": "",

        "relevant": False,

        "status": "error",

        "error": None
    }

    allowed_extensions = {
        ".pdf",
        ".doc",
        ".docx",
        ".xls",
        ".xlsx",
        ".txt"
    }

    if ext not in allowed_extensions:

        result["error"] = (
            f"Unsupported file format '{ext}'. "
            "Supported formats: "
            "PDF, DOC, DOCX, XLS, XLSX, TXT."
        )

        return result

    temp_path = None

    try:

        temp_fd, temp_path = tempfile.mkstemp(
            suffix=ext,
            dir=app.config["UPLOAD_FOLDER"]
        )

        os.close(temp_fd)

        if hasattr(uploaded_file, "seek"):
            uploaded_file.seek(0)

        uploaded_file.save(temp_path)

        with open(
            temp_path,
            "rb"
        ) as f_in:

            text = extract_text(
                f_in,
                raw_filename
            )

        if not text or not text.strip():

            result["error"] = (
                "Unable to extract text "
                "(document appears empty "
                "or contains no readable text)."
            )

            return result

        # Count every detected topic.
        counts = topic_counts(
            text,
            structure["topics"]
        )

        result["topic_counts"] = counts

        # Keep backward-compatible primary count.
        if display_topics:

            result["word_count"] = counts.get(
                display_topics[0],
                0
            )

        result["text"] = text

        result["status"] = "success"

        return result

    except Exception as err:

        result["error"] = (
            f"Processing failed: {str(err)}"
        )

        return result

    finally:

        if (
            temp_path
            and os.path.exists(temp_path)
        ):

            try:
                os.remove(temp_path)

            except Exception:
                pass


# ============================================================
# HOME PAGE
# ============================================================

@app.route("/")
def home():

    return render_template(
        "index.html"
    )


# ============================================================
# BACKWARD-COMPATIBLE SEARCH API
# ============================================================

@app.route(
    "/search",
    methods=["POST"]
)
def search():

    search_word = (
        request.form.get("search_word")
        or request.form.get("word")
    )

    uploaded_files = (
        request.files.getlist("files[]")
        or request.files.getlist("files")
    )

    single_file = request.files.get(
        "file"
    )

    if (
        not single_file
        and not uploaded_files
    ):

        return jsonify({
            "message": "Please upload a file",
            "success": False
        })

    if (
        not search_word
        or not search_word.strip()
    ):

        return jsonify({
            "message": "Please enter a word or text",
            "success": False
        })

    # --------------------------------------------------------
    # Legacy single-file mode
    # --------------------------------------------------------

    if (
        single_file
        and not uploaded_files
    ):

        try:

            text = extract_text_from_file(
                single_file
            )

            if text is None:

                return jsonify({
                    "message": "Unsupported file type",
                    "success": False
                })

            count = count_occurrences(
                text,
                search_word
            )

            if count > 0:

                return jsonify({
                    "found": True,
                    "count": count,
                    "message": (
                        f'"{search_word}" '
                        f"found {count} time(s)"
                    )
                })

            else:

                return jsonify({
                    "found": False,
                    "count": 0,
                    "message": (
                        f'"{search_word}" '
                        "not found"
                    )
                })

        except Exception as error:

            return jsonify({
                "message": f"Error: {str(error)}",
                "success": False
            })

    # Multiple files
    return analyze()


# ============================================================
# V2 MULTI-DOCUMENT ANALYZER
# ============================================================

@app.route(
    "/analyze",
    methods=["POST"]
)
def analyze():

    search_word = (
        request.form.get("search_word")
        or request.form.get("word")
        or ""
    ).strip()

    files = (
        request.files.getlist("files[]")
        or request.files.getlist("files")
    )

    if not files:

        single_file = request.files.get(
            "file"
        )

        if single_file:
            files = [single_file]

    valid_files = [
        f
        for f in files
        if (
            f
            and f.filename
            and f.filename.strip()
        )
    ]

    if not valid_files:

        return jsonify({
            "success": False,
            "message": (
                "Please upload at least "
                "one document."
            ),
            "results": []
        }), 400

    # ========================================================
    # FILE COUNT LIMIT
    # ========================================================

    if len(valid_files) > MAX_FILES_PER_ANALYSIS:

        return jsonify({
            "success": False,
            "message": (
                f"You can upload a maximum of "
                f"{MAX_FILES_PER_ANALYSIS} files at a time. "
                f"You selected {len(valid_files)} files."
            ),
            "max_files": MAX_FILES_PER_ANALYSIS,
            "selected_files": len(valid_files),
            "results": []
        }), 400

    if not search_word:

        return jsonify({
            "success": False,
            "message": (
                "Please enter a question, "
                "word, or phrase."
            ),
            "results": []
        }), 400

    # ========================================================
    # STEP 1
    # UNDERSTAND NATURAL-LANGUAGE QUERY
    # ========================================================

    query_structure = extract_query_structure(
        search_word
    )

    # ========================================================
    # STEP 2
    # EXTRACT + COUNT TOPICS
    # ========================================================

    all_results = []

    for doc_file in valid_files:

        all_results.append(
            process_single_document(
                doc_file,
                search_word,
                query_structure
            )
        )

    # ========================================================
    # STEP 3
    # PREPARE DOCUMENTS FOR RETRIEVAL
    # ========================================================

    documents_for_search = []

    for result in all_results:

        if (
            result["status"] == "success"
            and any(
                result["topic_counts"].values()
            )
        ):

            documents_for_search.append({

                "filename":
                result["filename"],

                "text":
                result["text"]

            })

    # ========================================================
    # STEP 4
    # FIND ONLY RELEVANT DOCUMENTS
    # ========================================================

    relevant_documents = (
        find_relevant_documents(
            documents_for_search,
            search_word,
            max_chunks_per_document=3
        )
        if documents_for_search
        else []
    )

    relevant_lookup = {
        d["filename"]: d
        for d in relevant_documents
    }

    relevant_results = []

    individual_summaries = []

    # ========================================================
    # STEP 5
    # PDF/DOCUMENT-BASED AI SUMMARY
    # ========================================================

    for result in all_results:

        filename = result["filename"]

        relevant_document = (
            relevant_lookup.get(filename)
        )

        if not relevant_document:
            continue

        summary_result = (
            generate_relevant_summary(
                relevant_document["relevant_text"],
                filename,
                question=search_word,
                topics=query_structure[
                    "display_topics"
                ],
                relationship=query_structure[
                    "relationship"
                ]
            )
        )

        result["relevant"] = True

        if summary_result.get("success"):

            result["summary"] = (
                summary_result.get(
                    "summary",
                    ""
                )
            )

        else:

            result["summary"] = (
                summary_result.get(
                    "message",
                    "Unable to generate summary."
                )
            )

        # Never send complete document
        # text to browser.

        result["text"] = ""

        relevant_results.append(
            result
        )

        individual_summaries.append({

            "filename":
            filename,

            "summary":
            result["summary"],

            "success":
            summary_result.get(
                "success",
                False
            )

        })

    # ========================================================
    # STEP 6
    # GENERAL AI SUMMARY
    # ========================================================

    general_summary_result = (
        generate_general_summary(
            search_word,
            topics=query_structure[
                "display_topics"
            ],
            relationship=query_structure[
                "relationship"
            ]
        )
    )

    if general_summary_result.get(
        "success"
    ):

        general_summary = (
            general_summary_result.get(
                "summary",
                ""
            )
        )

    else:

        general_summary = ""

    # ========================================================
    # STEP 7
    # PROCESSING COUNTS
    # ========================================================

    processed_count = sum(
        1
        for r in all_results
        if r["status"]
        in (
            "success",
            "warning"
        )
    )

    failed_count = sum(
        1
        for r in all_results
        if r["status"] == "error"
    )

    # ========================================================
    # FINAL RESPONSE
    # ========================================================

    return jsonify({

        "success":
        True,

        "search_word":
        search_word,

        "query":
        search_word,

        "topics":
        query_structure[
            "display_topics"
        ],

        "relationship":
        query_structure[
            "relationship"
        ],

        "total_files":
        len(all_results),

        "processed":
        processed_count,

        "failed":
        failed_count,

        "relevant_documents":
        len(relevant_results),

        # IMPORTANT:
        # Only relevant documents are returned.

        "results":
        relevant_results,

        "individual_summaries":
        individual_summaries,

        "pdf_combined_summary":
        "",

        "final_summary":
        general_summary,

        "general_summary":
        general_summary

    })


# ============================================================
# UNIFIED PROJECT ANALYSIS API
# ============================================================

@app.route("/project-analysis", methods=["POST"])
def project_analysis():
    idea = (
        request.form.get("project_idea")
        or request.form.get("search_word")
        or ""
    ).strip()
    uploaded_files = request.files.getlist("files[]") or request.files.getlist("files")
    valid_files = [
        file for file in uploaded_files
        if file and file.filename and file.filename.strip()
    ]

    if not idea:
        return jsonify({
            "success": False,
            "message": "Please enter a project problem statement or idea."
        }), 400
    if len(valid_files) > MAX_REPOSITORY_FILES:
        return jsonify({
            "success": False,
            "message": f"You can upload a maximum of {MAX_REPOSITORY_FILES} repository documents.",
            "max_files": MAX_REPOSITORY_FILES
        }), 400

    if valid_files:
        for filename in os.listdir(app.config["UPLOAD_FOLDER"]):
            path = os.path.join(app.config["UPLOAD_FOLDER"], filename)
            if os.path.isfile(path) and os.path.splitext(filename)[1].lower() in SUPPORTED_EXTENSIONS:
                os.remove(path)
        for uploaded_file in valid_files:
            filename = secure_filename(uploaded_file.filename)
            extension = os.path.splitext(filename)[1].lower()
            if filename and extension in SUPPORTED_EXTENSIONS:
                uploaded_file.save(os.path.join(app.config["UPLOAD_FOLDER"], filename))

    concepts = _identify_project_concepts(idea)
    theme = concepts["main_theme"]
    match_data = find_similar_projects(
        idea,
        upload_folder=app.config["UPLOAD_FOLDER"]
    )
    documents_by_name = {}
    occurrence_results = []

    for filepath in get_repository_files(app.config["UPLOAD_FOLDER"]):
        filename = os.path.basename(filepath)
        text = read_project_file(filepath)
        if not text:
            continue
        count = count_occurrences(text, theme)
        documents_by_name[filename] = text
        occurrence_results.append({
            "filename": filename,
            "file_type": os.path.splitext(filename)[1].lstrip("."),
            "word": theme,
            "query": idea,
            "topics": [theme] + concepts["supporting_concepts"],
            "topic_counts": {theme: count},
            "word_count": count,
            "text": "",
            "status": "success",
            "relevant": False,
            "summary": ""
        })

    matches = []
    for match in match_data["results"]:
        text = documents_by_name.get(match["filename"], "")
        summary_result = generate_relevant_summary(
            limit_text(text, 3500),
            match["filename"],
            question=idea,
            topics=concepts["supporting_concepts"],
            relationship=True
        )
        enriched = dict(match)
        enriched["summary"] = summary_result.get("summary", "") if summary_result.get("success") else ""
        matches.append(enriched)
        for result in occurrence_results:
            if result["filename"] == match["filename"]:
                result["relevant"] = True
                result["summary"] = enriched["summary"]
                break

    assistant = _project_assistant(idea, matches)
    has_high_match = any(item["classification"] == "high" for item in matches)
    return jsonify({
        "success": True,
        "project_idea": idea,
        "main_theme": theme,
        "supporting_concepts": concepts["supporting_concepts"],
        "total_projects": len(occurrence_results),
        "processed": len(occurrence_results),
        "failed": 0,
        "results": occurrence_results,
        "matches": matches,
        "relevant_documents": len(matches),
        "assistant": assistant,
        "general_summary": assistant,
        "message": (
            "Highly similar project(s) found in the available repository."
            if has_high_match
            else "No highly similar project was found in the available repository."
        )
    })


# ============================================================
# LEGACY PROJECT REPOSITORY MATCHING API
# ============================================================

@app.route("/project-match", methods=["POST"])
def project_match():
    idea = (
        request.form.get("project_idea")
        or request.form.get("idea")
        or ""
    ).strip()
    uploaded_files = (
        request.files.getlist("files[]")
        or request.files.getlist("files")
    )
    valid_files = [
        file for file in uploaded_files
        if file and file.filename and file.filename.strip()
    ]

    if not idea:
        return jsonify({
            "success": False,
            "message": "Please enter a project idea or problem statement."
        }), 400
    if len(valid_files) > MAX_REPOSITORY_FILES:
        return jsonify({
            "success": False,
            "message": f"You can upload a maximum of {MAX_REPOSITORY_FILES} repository documents.",
            "max_files": MAX_REPOSITORY_FILES
        }), 400

    if valid_files:
        for filename in os.listdir(app.config["UPLOAD_FOLDER"]):
            path = os.path.join(app.config["UPLOAD_FOLDER"], filename)
            if os.path.isfile(path) and os.path.splitext(filename)[1].lower() in SUPPORTED_EXTENSIONS:
                os.remove(path)
        for uploaded_file in valid_files:
            filename = secure_filename(uploaded_file.filename)
            extension = os.path.splitext(filename)[1].lower()
            if not filename or extension not in SUPPORTED_EXTENSIONS:
                continue
            uploaded_file.save(os.path.join(app.config["UPLOAD_FOLDER"], filename))

    match_data = find_similar_projects(
        idea,
        upload_folder=app.config["UPLOAD_FOLDER"]
    )
    matches = match_data["results"]
    assistant = _project_assistant(idea, matches)
    return jsonify({
        "success": True,
        "total_projects": match_data["total_projects"],
        "matches": matches,
        "assistant": assistant,
        "message": (
            "No highly similar project was found in the available repository."
            if not any(item["classification"] == "high" for item in matches)
            else "Highly similar project(s) found in the available repository."
        )
    })


# ============================================================
# START APPLICATION
# ============================================================

if __name__ == "__main__":

    app.run(
        debug=True,
        port=5000
    )