import os
import re
import tempfile
from concurrent.futures import ThreadPoolExecutor, as_completed

from flask import Flask, jsonify, render_template, request
from werkzeug.utils import secure_filename

from retrieval import (
    find_relevant_chunks,
    query_terms,
)

from document_processors import (
    extract_text,
    count_word_occurrences,
    extract_pdf_text,
    extract_docx_text,
    extract_doc_text,
    extract_xlsx_text,
    extract_xls_text,
)

from project_matcher import (
    find_similar_projects,
    get_repository_files,
    read_project_file,
    calculate_similarity,
    classify_similarity,
    _explain_overlap,
    MEANINGFUL_SCORE,
    MAX_REPOSITORY_FILES,
    SUPPORTED_EXTENSIONS,
)

from ai_summary import (
    call_ollama,
    limit_text,
    generate_summary,
    generate_relevant_summary,
    generate_why_relevant,
    generate_project_exploration,
)

from database import (
    init_database,
    save_search,
    get_search_history,
)


# ============================================================
# FLASK APP
# ============================================================

app = Flask(__name__)

init_database()


# ============================================================
# UPLOAD CONFIGURATION
# ============================================================

UPLOAD_FOLDER = os.path.join(
    os.path.dirname(os.path.abspath(__file__)),
    "uploads"
)

os.makedirs(UPLOAD_FOLDER, exist_ok=True)

app.config["UPLOAD_FOLDER"] = UPLOAD_FOLDER

# Maximum request size = 100 MB
app.config["MAX_CONTENT_LENGTH"] = 100 * 1024 * 1024

# Maximum documents per analysis
MAX_FILES_PER_ANALYSIS = 10


# ============================================================
# QUERY / TOPIC HELPERS
# ============================================================

STOP_WORDS = {
    "a", "an", "the", "is", "are", "am", "was", "were",
    "be", "been", "being", "what", "why", "how", "when",
    "where", "who", "which", "does", "do", "did", "can",
    "could", "would", "should", "will", "may", "might",
    "to", "of", "in", "on", "for", "from", "with",
    "about", "and", "or", "as", "at", "by", "into",
    "through", "using", "use", "used", "this", "that",
    "these", "those", "it", "its", "project", "system",
    "based", "provide", "develop", "create", "build"
}


ALIASES = {
    "machine learning": [
        "machine learning",
        "ml",
    ],
    "deep learning": [
        "deep learning",
        "dl",
    ],
    "natural language processing": [
        "natural language processing",
        "nlp",
    ],
    "large language model": [
        "large language model",
        "large language models",
        "llm",
        "llms",
    ],
    "retrieval augmented generation": [
        "retrieval augmented generation",
        "retrieval-augmented generation",
        "rag",
    ],
    "artificial intelligence": [
        "artificial intelligence",
        "ai",
    ],
    "computer vision": [
        "computer vision",
    ],
    "object detection": [
        "object detection",
    ],
    "data science": [
        "data science",
    ],
    "python": [
        "python",
    ],
    "java": [
        "java",
    ],
    "javascript": [
        "javascript",
        "js",
    ],
    "sql": [
        "sql",
    ],
    "flask": [
        "flask",
    ],
    "django": [
        "django",
    ],
    "pandas": [
        "pandas",
    ],
    "numpy": [
        "numpy",
    ],
    "healthcare": [
        "healthcare",
        "health care",
        "medical",
    ],
    "chatbot": [
        "chatbot",
        "chat bot",
        "conversational agent",
    ],
}


DISPLAY_NAMES = {
    "machine learning": "ML",
    "deep learning": "DL",
    "natural language processing": "NLP",
    "large language model": "LLM",
    "retrieval augmented generation": "RAG",
    "artificial intelligence": "AI",
    "computer vision": "Computer Vision",
    "object detection": "Object Detection",
    "data science": "Data Science",
    "python": "Python",
    "java": "Java",
    "javascript": "JavaScript",
    "sql": "SQL",
    "flask": "Flask",
    "django": "Django",
    "pandas": "Pandas",
    "numpy": "NumPy",
    "healthcare": "Healthcare",
    "chatbot": "Chatbot",
}


def normalize_text(text):
    return re.sub(r"\s+", " ", str(text or "")).strip()


def count_term(text, term):
    if not text or not term:
        return 0

    text = str(text)
    term = str(term).strip()

    if not term:
        return 0

    if re.fullmatch(r"[a-zA-Z0-9]+", term):
        return len(
            re.findall(
                rf"\b{re.escape(term)}\b",
                text,
                flags=re.IGNORECASE,
            )
        )

    return len(
        re.findall(
            re.escape(term),
            text,
            flags=re.IGNORECASE,
        )
    )


def canonical_topic(topic):
    topic = str(topic or "").strip().lower()

    for canonical, aliases in ALIASES.items():
        if topic == canonical:
            return canonical

        if topic in [a.lower() for a in aliases]:
            return canonical

    return topic


def topic_aliases(topic):
    canonical = canonical_topic(topic)
    return ALIASES.get(canonical, [canonical])


def extract_query_structure(query):
    """
    Convert the user's project/problem statement into
    deterministic searchable concepts.

    No Ollama call is made here.
    """

    normalized = normalize_text(query).lower()

    topics = []

    # Detect known multi-word concepts first.
    found = []

    for canonical, aliases in ALIASES.items():
        for alias in aliases:

            pattern = re.escape(alias.lower())

            match = re.search(
                rf"(?<!\w){pattern}(?!\w)",
                normalized,
            )

            if match:
                found.append(
                    (
                        match.start(),
                        canonical,
                    )
                )
                break

    found.sort(key=lambda item: item[0])

    for _, canonical in found:
        if canonical not in topics:
            topics.append(canonical)

    # If no known concept was found, use meaningful words.
    if not topics:

        words = re.findall(
            r"[a-zA-Z][a-zA-Z0-9+#.-]*",
            normalized,
        )

        for word in words:

            if (
                len(word) >= 2
                and word not in STOP_WORDS
            ):
                if word not in topics:
                    topics.append(word)

            if len(topics) >= 8:
                break

    display_topics = [
        DISPLAY_NAMES.get(
            topic,
            topic.title(),
        )
        for topic in topics
    ]

    return {
        "query": query,
        "topics": topics,
        "display_topics": display_topics,
    }


def topic_counts(text, topics):
    """
    Count actual occurrences in the document.

    Alias-aware:
    RAG counts both:
    - RAG
    - Retrieval Augmented Generation
    """

    counts = {}

    for topic in topics:

        aliases = topic_aliases(topic)

        total = 0

        for alias in aliases:
            total += count_term(
                text,
                alias,
            )

        display_name = DISPLAY_NAMES.get(
            canonical_topic(topic),
            str(topic),
        )

        counts[display_name] = total

    return counts


def extract_file_overview(filename, file_type, text):
    """
    Lightweight local document overview.

    Does NOT call Ollama.
    """

    clean_text = normalize_text(text)

    words = clean_text.split()

    return {
        "filename": filename,
        "file_type": file_type,
        "characters": len(clean_text),
        "words": len(words),
        "preview": clean_text[:500],
    }


# ============================================================
# RELEVANT CONTENT
# ============================================================

def fallback_relevant_chunks(
    document_text,
    query,
    max_chunks=3,
):
    """
    Additional local retrieval fallback.

    This is used only when the existing retrieval.py
    returns no chunks.

    It does NOT use Ollama.
    """

    if not document_text or not query:
        return []

    text = normalize_text(document_text)

    if not text:
        return []

    # Use meaningful query terms.
    terms = query_terms(query)

    if not terms:
        structure = extract_query_structure(query)
        terms = structure["topics"]

    terms = [
        str(term).lower()
        for term in terms
        if str(term).lower() not in STOP_WORDS
        and len(str(term)) >= 2
    ]

    if not terms:
        return []

    # Split into moderately sized chunks.
    chunk_size = 1200
    overlap = 200

    chunks = []

    start = 0

    while start < len(text):

        end = min(
            start + chunk_size,
            len(text),
        )

        chunk = text[start:end].strip()

        if chunk:
            chunks.append(chunk)

        if end >= len(text):
            break

        start = max(
            end - overlap,
            start + 1,
        )

    scored = []

    for chunk in chunks:

        lower_chunk = chunk.lower()

        score = 0

        for term in terms:

            occurrences = len(
                re.findall(
                    rf"\b{re.escape(term)}\b",
                    lower_chunk,
                )
            )

            score += min(
                occurrences,
                5,
            ) * 2

        # Full query match bonus.
        if (
            normalize_text(query).lower()
            in lower_chunk
        ):
            score += 10

        if score > 0:

            scored.append(
                {
                    "text": chunk,
                    "score": float(score),
                }
            )

    scored.sort(
        key=lambda item: item["score"],
        reverse=True,
    )

    return scored[:max_chunks]


def get_relevant_chunks(
    document_text,
    query,
    max_chunks=3,
):
    """
    First use the existing retrieval.py implementation.

    If it produces nothing, use a local deterministic fallback.
    """

    try:

        chunks = find_relevant_chunks(
            document_text,
            query,
            max_chunks=max_chunks,
        )

        if chunks:
            return chunks

    except Exception as error:

        print(
            f"Primary retrieval warning: {error}"
        )

    return fallback_relevant_chunks(
        document_text,
        query,
        max_chunks=max_chunks,
    )


# ============================================================
# LEGACY WORD COUNT
# ============================================================

def count_occurrences(text, search_word):
    return count_word_occurrences(
        text,
        search_word,
    )


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
            sheet_name=sheet_name,
        )

        text += (
            dataframe.to_string()
            + "\n"
        )

    return text


# ============================================================
# FILE TEXT EXTRACTION
# ============================================================

def extract_text_from_file(file):

    filename = getattr(
        file,
        "filename",
        "",
    ) or ""

    filename_lower = filename.lower()

    if filename_lower.endswith(".pdf"):
        return read_pdf(file)

    if filename_lower.endswith(".docx"):
        return read_docx(file)

    if filename_lower.endswith(".doc"):
        return extract_doc_text(file)

    if filename_lower.endswith(".xlsx"):
        return extract_xlsx_text(file)

    if filename_lower.endswith(".xls"):
        return extract_xls_text(file)

    if filename_lower.endswith(".txt"):

        if hasattr(file, "seek"):
            file.seek(0)

        content = file.read()

        if hasattr(file, "seek"):
            file.seek(0)

        if isinstance(content, bytes):
            return content.decode(
                "utf-8",
                errors="ignore",
            )

        return str(content)

    return None


def deduplicate_guidance_sections(text):
    """
    Ensures that each major heading / section in the guidance appears only once.
    Removes accidental duplicate sections if the LLM generated them twice.
    """
    if not text:
        return ""

    text = str(text).strip()
    pattern = r"(?=(?:^|\n)(?:\*\*(?:\d+[\.\)]\s*)?[^*]+?\*\*|#{1,4}\s+|(?:(?:\d+[\.\)]\s*)?[A-Z][A-Za-z\s/&,\-–—]{3,50}:)))"
    parts = re.split(pattern, text, flags=re.MULTILINE)

    seen_headings = set()
    cleaned_parts = []

    for part in parts:
        trimmed = part.strip()
        if not trimmed:
            continue

        lines = trimmed.splitlines()
        first_line = lines[0].strip()
        norm_key = re.sub(r"^(?:[\s*#\-•]|\d+[\.\):\-]\s*)+", "", first_line).strip().rstrip(":*").lower()
        norm_key = re.sub(r"\s+", " ", norm_key)

        if len(norm_key) >= 3 and len(lines) > 1 and norm_key in seen_headings:
            continue

        if len(norm_key) >= 3 and len(lines) > 1:
            seen_headings.add(norm_key)

        cleaned_parts.append(trimmed)

    return "\n\n".join(cleaned_parts)


# ============================================================
# PROJECT ASSISTANT
# ============================================================

def _project_assistant(
    idea,
    matches,
):
    """
    Generate project guidance ONLY when meaningful
    repository matches exist.

    This function must never be called for a no-match case.
    """

    if not matches:
        return ""

    evidence_lines = []
    for m in matches[:3]:
        fname = m.get("filename", "")
        mscore = m.get("score", 0)
        msummary = m.get("summary", "")
        summary_snippet = msummary[:350].strip() if msummary else ""
        evidence_lines.append(f"- Project: {fname} (Match: {mscore}%)\n  Key Points: {summary_snippet}")
    evidence_text = "\n\n".join(evidence_lines)

    prompt = f"""You are an AI project advisor.

Student project idea:
{idea}

Relevant repository project evidence:
{evidence_text}

TASK:
Provide fast, practical project development guidance based on the repository evidence above.

FORMAT RULES:
- Use bold headings in the format: **Heading Name**
- Under each heading, provide 2-3 concise, high-impact bullet points.
- Provide each section ONCE. Do NOT repeat sections or instructions.
- Keep the response fast, focused, and directly actionable.

Sections to include:
1. Related Project Insight
2. Proposed Solution & Architecture
3. Main Modules & Technologies
4. Suggested Development Roadmap
"""

    response = call_ollama(
        prompt,
        temperature=0.1,
        num_predict=350,
        num_ctx=1024,
    )

    if response.get("success"):
        raw_text = response.get(
            "response",
            "",
        ).strip()
        return deduplicate_guidance_sections(raw_text)

    return ""


# ============================================================
# PROJECT FOLLOW-UP ASSISTANT
# ============================================================

def generate_follow_up_guidance(
    project_idea,
    additional_information,
):
    """
    This is the ONLY AI path for a project with no
    repository match.

    Only the original idea and additional information
    are sent to Ollama.
    """

    prompt = f"""You are an AI project advisor helping a student.

Project idea:
{project_idea}

Additional details provided:
{additional_information}

TASK:
Provide fast, practical, and structured project guidance.
Keep each section concise (2-3 clear bullet points). Do not write essays or repeat instructions.

FORMAT RULES:
- Use bold headings in the format: **Heading Name**
- Provide each section ONCE.

Sections:
1. Refined Problem Statement
2. Project Objective
3. Proposed Solution
4. Main Modules & Technologies
5. Next Steps
"""

    response = call_ollama(
        prompt,
        temperature=0.1,
        num_predict=350,
        num_ctx=1024,
    )

    if response.get("success"):
        raw_text = response.get(
            "response",
            "",
        ).strip()
        response["response"] = deduplicate_guidance_sections(raw_text)

    return response


# ============================================================
# HOME
# ============================================================

@app.route("/")
def home():

    return render_template(
        "index.html"
    )


# ============================================================
# LEGACY SEARCH API
# ============================================================

@app.route(
    "/search",
    methods=["POST"],
)
def search():

    search_word = (
        request.form.get("search_word")
        or request.form.get("word")
        or ""
    ).strip()

    uploaded_files = (
        request.files.getlist("files[]")
        or request.files.getlist("files")
    )

    single_file = request.files.get(
        "file"
    )

    if not single_file and not uploaded_files:

        return jsonify(
            {
                "success": False,
                "message": "Please upload a file.",
            }
        )

    if not search_word:

        return jsonify(
            {
                "success": False,
                "message": "Please enter a word or text.",
            }
        )

    # Legacy single-file behavior.
    if single_file and not uploaded_files:

        try:

            text = extract_text_from_file(
                single_file
            )

            if text is None:

                return jsonify(
                    {
                        "success": False,
                        "message": "Unsupported file type.",
                    }
                )

            count = count_occurrences(
                text,
                search_word,
            )

            return jsonify(
                {
                    "success": True,
                    "found": count > 0,
                    "count": count,
                    "message": (
                        f'"{search_word}" found '
                        f"{count} time(s)"
                        if count > 0
                        else
                        f'"{search_word}" not found'
                    ),
                }
            )

        except Exception as error:

            return jsonify(
                {
                    "success": False,
                    "message": f"Error: {error}",
                }
            )

    return analyze()


# ============================================================
# SUMMARY API
# ============================================================

@app.route(
    "/summarize",
    methods=["POST"],
)
def summarize():

    text = (
        request.form.get("text")
        or ""
    ).strip()

    search_word = (
        request.form.get("search_word")
        or request.form.get("word")
        or ""
    ).strip()

    if not text:

        return jsonify(
            {
                "success": False,
                "summary": "",
                "message": "Please provide text to summarize.",
            }
        ), 400

    try:

        result = generate_summary(
            text,
            search_word,
        )

        return jsonify(
            {
                "success": bool(
                    result.get("success")
                    or result.get("summary")
                ),
                "summary": result.get(
                    "summary",
                    "",
                ),
                "message": result.get(
                    "message",
                    "",
                ),
            }
        )

    except Exception as error:

        return jsonify(
            {
                "success": False,
                "summary": "",
                "message": str(error),
            }
        ), 500


# ============================================================
# SEARCH HISTORY
# ============================================================

@app.route(
    "/search-history",
    methods=["GET"],
)
def search_history():

    try:

        history = get_search_history(
            10
        )

        return jsonify(
            {
                "success": True,
                "history": history,
            }
        )

    except Exception as error:

        return jsonify(
            {
                "success": False,
                "history": [],
                "message": (
                    f"Unable to load search history: "
                    f"{error}"
                ),
            }
        ), 500


# ============================================================
# UNIFIED DOCUMENT ANALYSIS
# ============================================================

def run_document_analysis(
    query,
    uploaded_files=None,
    allow_repository_fallback=False,
):

    search_query = str(
        query or ""
    ).strip()

    if not search_query:

        return {
            "success": False,
            "message": (
                "Please enter a question, "
                "word, or phrase."
            ),
            "results": [],
            "total_files": 0,
        }, 400

    # Save search history.
    try:
        save_search(
            search_query
        )
    except Exception as error:
        print(
            f"Search history warning: {error}"
        )

    # --------------------------------------------------------
    # Query structure
    # --------------------------------------------------------

    query_structure = extract_query_structure(
        search_query
    )

    topics = query_structure.get(
        "topics",
        [],
    )

    display_topics = query_structure.get(
        "display_topics",
        [],
    )

    if not topics:

        topics = query_terms(
            search_query
        )

        display_topics = topics[:]

    if not topics:

        topics = [
            search_query
        ]

        display_topics = [
            search_query
        ]

    # --------------------------------------------------------
    # Determine uploaded files
    # --------------------------------------------------------

    valid_files = [
        file
        for file in (uploaded_files or [])
        if (
            file
            and getattr(
                file,
                "filename",
                None,
            )
            and file.filename.strip()
        )
    ]

    if (
        valid_files
        and len(valid_files)
        > MAX_FILES_PER_ANALYSIS
    ):

        return {
            "success": False,
            "message": (
                f"You can upload a maximum of "
                f"{MAX_FILES_PER_ANALYSIS} files at a time. "
                f"You selected {len(valid_files)} files."
            ),
            "max_files": MAX_FILES_PER_ANALYSIS,
            "selected_files": len(valid_files),
            "results": [],
        }, 400

    docs_to_analyze = []

    # --------------------------------------------------------
    # Uploaded document extraction
    # --------------------------------------------------------

    def extract_one_uploaded(
        uploaded_file
    ):

        raw_filename = (
            secure_filename(
                uploaded_file.filename
            )
            or uploaded_file.filename
            or "unknown_file"
        )

        ext = os.path.splitext(
            raw_filename
        )[1].lower()

        file_type = (
            ext.lstrip(".")
            if ext
            else "unknown"
        )

        if ext not in SUPPORTED_EXTENSIONS:

            return {
                "filename": raw_filename,
                "file_type": file_type,
                "text": "",
                "error": (
                    f"Unsupported file format '{ext}'. "
                    "Supported formats: "
                    "PDF, DOC, DOCX, XLS, XLSX, TXT."
                ),
            }

        temp_path = None

        try:

            temp_fd, temp_path = tempfile.mkstemp(
                suffix=ext,
                dir=app.config[
                    "UPLOAD_FOLDER"
                ],
            )

            os.close(
                temp_fd
            )

            uploaded_file.seek(0)

            uploaded_file.save(
                temp_path
            )

            with open(
                temp_path,
                "rb",
            ) as file:

                text = extract_text(
                    file,
                    raw_filename,
                )

            if not text or not text.strip():

                return {
                    "filename": raw_filename,
                    "file_type": file_type,
                    "text": "",
                    "error": (
                        "Unable to extract text "
                        "(document appears empty "
                        "or contains no readable text)."
                    ),
                }

            return {
                "filename": raw_filename,
                "file_type": file_type,
                "text": text,
                "error": None,
            }

        except Exception as error:

            return {
                "filename": raw_filename,
                "file_type": file_type,
                "text": "",
                "error": (
                    f"Processing failed: {error}"
                ),
            }

        finally:

            if (
                temp_path
                and os.path.exists(
                    temp_path
                )
            ):

                try:
                    os.remove(
                        temp_path
                    )
                except Exception:
                    pass

    if valid_files:

        max_workers = min(
            len(valid_files),
            4,
        )

        futures = {}

        with ThreadPoolExecutor(
            max_workers=max_workers
        ) as pool:

            for file in valid_files:

                futures[
                    pool.submit(
                        extract_one_uploaded,
                        file,
                    )
                ] = file.filename

            result_map = {}

            for future in as_completed(
                futures
            ):

                filename = futures[
                    future
                ]

                result_map[
                    filename
                ] = future.result()

        # Preserve upload order.
        for file in valid_files:

            filename = file.filename

            if filename in result_map:

                docs_to_analyze.append(
                    result_map[
                        filename
                    ]
                )

    # --------------------------------------------------------
    # Repository fallback
    # --------------------------------------------------------

    elif allow_repository_fallback:

        repository_files = get_repository_files(
            app.config["UPLOAD_FOLDER"]
        )

        if not repository_files:

            return {
                "success": True,
                "message": (
                    "Repository is empty. "
                    "Please upload documents."
                ),
                "results": [],
                "matches": [],
                "all_results": [],
                "total_files": 0,
                "total_projects": 0,
                "processed": 0,
                "failed": 0,
                "relevant_documents": 0,
                "has_matches": False,
                "query": search_query,
                "project_idea": search_query,
                "topics": display_topics,
                "assistant": "",
                "general_summary": "",
                "needs_more_information": True,
            }, 200

        for filepath in repository_files:

            filename = os.path.basename(
                filepath
            )

            ext = os.path.splitext(
                filename
            )[1].lower()

            file_type = (
                ext.lstrip(".")
                if ext
                else "unknown"
            )

            try:

                text = read_project_file(
                    filepath
                )

                if not text or not text.strip():

                    docs_to_analyze.append(
                        {
                            "filename": filename,
                            "file_type": file_type,
                            "text": "",
                            "error": (
                                "Unable to extract text."
                            ),
                        }
                    )

                else:

                    docs_to_analyze.append(
                        {
                            "filename": filename,
                            "file_type": file_type,
                            "text": text,
                            "error": None,
                        }
                    )

            except Exception as error:

                docs_to_analyze.append(
                    {
                        "filename": filename,
                        "file_type": file_type,
                        "text": "",
                        "error": str(error),
                    }
                )

    else:

        return {
            "success": False,
            "message": (
                "Please upload at least "
                "one document."
            ),
            "results": [],
            "total_files": 0,
        }, 400

    # ========================================================
    # ANALYZE DOCUMENTS
    # ========================================================

    all_results = []
    matches = []

    for item in docs_to_analyze:

        filename = item[
            "filename"
        ]

        file_type = item[
            "file_type"
        ]

        text = item[
            "text"
        ]

        error = item[
            "error"
        ]

        # ----------------------------------------------------
        # Extraction error
        # ----------------------------------------------------

        if error or not text:

            all_results.append(
                {
                    "filename": filename,
                    "file_type": file_type,
                    "word": (
                        display_topics[0]
                        if display_topics
                        else search_query
                    ),
                    "query": search_query,
                    "topics": display_topics,
                    "topic_counts": {
                        topic: 0
                        for topic in display_topics
                    },
                    "word_count": 0,
                    "total_occurrences": 0,
                    "text": "",
                    "relevant": False,
                    "relevant_content": (
                        "No relevant content found."
                    ),
                    "chunks": [],
                    "overview": {},
                    "summary": "",
                    "score": 0.0,
                    "match_percentage": 0.0,
                    "classification": "low",
                    "overlap": [],
                    "relationship": (
                        "No conceptual overlap."
                    ),
                    "status": "error",
                    "error": error
                    or "Document contains no extractable text.",
                }
            )

            continue

        # ----------------------------------------------------
        # Count concepts
        # ----------------------------------------------------

        counts = topic_counts(
            text,
            topics,
        )

        primary_count = (
            next(
                iter(counts.values()),
                0,
            )
        )

        total_occurrences = sum(
            counts.values()
        )

        # ----------------------------------------------------
        # Similarity score (MASTER relevance gate)
        # A document is ONLY relevant if its semantic score
        # meets the meaningful threshold — NOT just because
        # it returned text chunks.
        # ----------------------------------------------------

        score = calculate_similarity(
            search_query,
            text,
        )

        classification = classify_similarity(
            score
        )

        # Gate relevance strictly on the similarity score.
        relevant = score >= MEANINGFUL_SCORE

        print(
            f"MATCH: {filename} | score={score} | "
            f"classification={classification} | relevant={relevant}"
        )

        # Retrieve content passages only for relevant docs.
        if relevant:
            chunks = get_relevant_chunks(
                text,
                search_query,
                max_chunks=3,
            )
            if chunks:
                relevant_content = "\n\n".join(
                    chunk.get("text", "")
                    for chunk in chunks
                    if chunk.get("text")
                )
            else:
                relevant_content = text[:2000].strip()
        else:
            chunks = []
            relevant_content = "No relevant content found."

        try:
            overlap_data = _explain_overlap(
                search_query,
                text,
            )
            overlap = overlap_data.get("overlap", [])
        except Exception:
            overlap = []

        overview = extract_file_overview(
            filename,
            file_type,
            text,
        )

        # ----------------------------------------------------
        # AI summary and why-relevant — ONLY for relevant docs
        # ----------------------------------------------------

        ai_summary = ""
        why_relevant = ""
        ai_available = False

        if relevant:
            print(f"AI SUMMARY: starting | document = {filename}")
            summary_result = generate_relevant_summary(
                text,
                filename,
                question=search_query,
                topics=display_topics,
            )
            ai_summary = summary_result.get("summary", "")
            ai_available = summary_result.get("ai_available", False)
            print(
                f"AI SUMMARY: completed | "
                f"source={summary_result.get('summary_source', 'unknown')} | "
                f"points={len([l for l in ai_summary.splitlines() if l.strip()])}"
            )

            why_relevant = ""

        result_item = {
            "filename": filename,
            "file_type": file_type,
            "word": (
                display_topics[0]
                if display_topics
                else search_query
            ),
            "query": search_query,
            "topics": display_topics,
            "topic_counts": counts,
            "word_count": primary_count,
            "total_occurrences": total_occurrences,
            "text": "",
            "relevant": relevant,
            "relevant_content": relevant_content,
            "chunks": chunks,
            "overview": overview,
            "summary": ai_summary,
            "ai_available": ai_available,
            "why_relevant": why_relevant,
            "score": score,
            "match_percentage": score,
            "classification": classification,
            "overlap": overlap,
            "relationship": (
                f"{classification.title()} conceptual relationship."
            ),
            "status": "success",
            "error": None,
        }

        all_results.append(
            result_item
        )

        # Meaningful repository match.
        if relevant:
            matches.append(
                result_item
            )

    # ========================================================
    # SORT MATCHES
    # ========================================================

    matches.sort(
        key=lambda item: item[
            "score"
        ],
        reverse=True,
    )

    processed_count = sum(
        1
        for result in all_results
        if result["status"] == "success"
    )

    failed_count = sum(
        1
        for result in all_results
        if result["status"] == "error"
    )

    relevant_count = sum(
        1
        for result in all_results
        if result["relevant"]
    )

    # ========================================================
    # PROJECT ASSISTANT
    #
    # VERY IMPORTANT:
    #
    # NO MATCH = NO OLLAMA PROJECT GUIDANCE
    # ========================================================

    if matches:

        assistant = _project_assistant(
            search_query,
            matches,
        )

        needs_more_information = False

    else:

        assistant = ""

        needs_more_information = True

    # ========================================================
    # RESPONSE
    # ========================================================

    return {
        "success": True,
        "search_word": search_query,
        "query": search_query,
        "project_idea": search_query,

        "topics": display_topics,
        "display_topics": display_topics,

        "total_files": len(
            all_results
        ),

        "total_projects": len(
            all_results
        ),

        "processed": processed_count,
        "failed": failed_count,

        "relevant_documents": (
            relevant_count
        ),

        "has_matches": bool(
            matches
        ),

        # no_match = True triggers the no-match UI prompt
        "no_match": not bool(matches),

        "results": all_results,

        "matches": matches,

        "assistant": assistant,

        "general_summary": assistant,

        "needs_more_information": (
            needs_more_information
        ),

        "message": (
            f"{len(matches)} document(s) "
            "are meaningfully relevant to your query."
            if matches
            else
            "No relevant content was found in the uploaded project repository for this query."
        ),

    }, 200


# ============================================================
# ANALYZE API
# ============================================================

@app.route(
    "/analyze",
    methods=["POST"],
)
def analyze():

    search_word = (
        request.form.get("search_word")
        or request.form.get("word")
        or request.form.get("project_idea")
        or ""
    ).strip()

    uploaded_files = (
        request.files.getlist("files[]")
        or request.files.getlist("files")
    )

    if not uploaded_files:

        single_file = request.files.get(
            "file"
        )

        if single_file:
            uploaded_files = [
                single_file
            ]

    allow_repo = (
        request.form.get(
            "repository"
        )
        == "true"
    )

    data, status_code = run_document_analysis(
        search_word,
        uploaded_files=uploaded_files,
        allow_repository_fallback=allow_repo,
    )

    return jsonify(
        data
    ), status_code


# ============================================================
# PROJECT ANALYSIS API
# ============================================================

@app.route(
    "/project-analysis",
    methods=["POST"],
)
def project_analysis():

    idea = (
        request.form.get("project_idea")
        or request.form.get("search_word")
        or request.form.get("word")
        or ""
    ).strip()

    uploaded_files = (
        request.files.getlist("files[]")
        or request.files.getlist("files")
    )

    if not uploaded_files:

        single_file = request.files.get(
            "file"
        )

        if single_file:
            uploaded_files = [
                single_file
            ]

    data, status_code = run_document_analysis(
        idea,
        uploaded_files=uploaded_files,
        allow_repository_fallback=True,
    )

    return jsonify(
        data
    ), status_code


# ============================================================
# PROJECT MATCH API
# ============================================================

@app.route(
    "/project-match",
    methods=["POST"],
)
def project_match():

    idea = (
        request.form.get("project_idea")
        or request.form.get("idea")
        or ""
    ).strip()

    if not idea:

        return jsonify(
            {
                "success": False,
                "message": (
                    "Please enter a project idea "
                    "or problem statement."
                ),
            }
        ), 400

    match_data = find_similar_projects(
        idea,
        upload_folder=app.config[
            "UPLOAD_FOLDER"
        ],
    )

    matches = match_data.get(
        "results",
        [],
    )

    # --------------------------------------------------------
    # CRITICAL FIX:
    #
    # NEVER call project assistant when there
    # are no meaningful repository matches.
    # --------------------------------------------------------

    if matches:

        assistant = _project_assistant(
            idea,
            matches,
        )

        needs_more_information = False

    else:

        assistant = ""

        needs_more_information = True

    return jsonify(
        {
            "success": True,

            "total_projects": match_data.get(
                "total_projects",
                0,
            ),

            "matches": matches,

            "has_matches": bool(
                matches
            ),

            "assistant": assistant,

            "general_summary": assistant,

            "needs_more_information": (
                needs_more_information
            ),

            "message": (
                "Meaningful project matches found."
                if matches
                else
                "No matching project found."
            ),
        }
    )


# ============================================================
# PROJECT FOLLOW-UP API
# ============================================================

@app.route(
    "/project-follow-up",
    methods=["POST"],
)
def project_follow_up():

    data = (
        request.get_json(
            silent=True
        )
        or {}
    )

    project_idea = (
        data.get("project_idea")
        or request.form.get("project_idea")
        or request.form.get("idea")
        or ""
    ).strip()

    additional_information = (
        data.get(
            "additional_information"
        )
        or request.form.get(
            "additional_information"
        )
        or request.form.get(
            "more_information"
        )
        or ""
    ).strip()

    if not project_idea:

        return jsonify(
            {
                "success": False,
                "message": (
                    "Please provide the "
                    "original project idea."
                ),
            }
        ), 400

    if not additional_information:

        return jsonify(
            {
                "success": False,
                "message": (
                    "Please provide additional "
                    "information about the project."
                ),
            }
        ), 400

    # Only here is Ollama called for a no-match
    # project guidance request.

    response = generate_follow_up_guidance(
        project_idea,
        additional_information,
    )

    if response.get("success"):

        assistant = (
            response.get(
                "response",
                "",
            )
            or ""
        ).strip()

        return jsonify(
            {
                "success": True,
                "project_idea": project_idea,
                "additional_information": (
                    additional_information
                ),
                "assistant": assistant,
                "general_summary": assistant,
                "needs_more_information": False,
                "message": (
                    "Project guidance generated successfully."
                ),
            }
        )

    return jsonify(
        {
            "success": False,
            "project_idea": project_idea,
            "additional_information": (
                additional_information
            ),
            "assistant": "",
            "general_summary": "",
            "needs_more_information": False,
            "message": response.get(
                "message",
                "Unable to generate project guidance.",
            ),
        }
    ), 502


# ============================================================
# PROJECT EXPLORATION API
# ============================================================

@app.route(
    "/project-exploration",
    methods=["POST"],
)
def project_exploration():
    data = request.get_json(silent=True) or {}

    project_idea = (
        data.get("project_idea")
        or request.form.get("project_idea")
        or ""
    ).strip()

    categories = (
        data.get("categories")
        or request.form.getlist("categories[]")
        or request.form.getlist("categories")
        or []
    )

    document_text = (
        data.get("document_text")
        or request.form.get("document_text")
        or ""
    ).strip()

    if not project_idea:
        return jsonify({
            "success": False,
            "message": "Please provide the project idea."
        }), 400

    if not categories:
        return jsonify({
            "success": False,
            "message": "Please select at least one exploration category."
        }), 400

    # If document text was not passed from client, gather repository content
    if not document_text:
        repo_files = get_repository_files(app.config["UPLOAD_FOLDER"])
        combined_texts = []
        for filepath in repo_files:
            t = read_project_file(filepath)
            if t:
                combined_texts.append(f"--- File: {os.path.basename(filepath)} ---\n{t}")
        document_text = "\n\n".join(combined_texts)

    exploration_result = generate_project_exploration(
        project_idea=project_idea,
        document_text=document_text,
        categories=categories
    )

    if exploration_result.get("success"):
        return jsonify({
            "success": True,
            "project_idea": project_idea,
            "categories": categories,
            "exploration": exploration_result.get("response", ""),
            "message": "Project exploration generated successfully."
        })

    return jsonify({
        "success": False,
        "message": exploration_result.get("message", "Unable to generate project exploration.")
    }), 502


# ============================================================
# ERROR HANDLER
# ============================================================

@app.errorhandler(413)
def request_too_large(error):

    return jsonify(
        {
            "success": False,
            "message": (
                "The uploaded files are too large. "
                "Maximum request size is 100 MB."
            ),
        }
    ), 413


# ============================================================
# START APPLICATION
# ============================================================

if __name__ == "__main__":

    app.run(
        debug=True,
        port=5000,
    )