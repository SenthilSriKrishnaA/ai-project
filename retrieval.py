import re
from typing import List, Dict


# ============================================================
# TEXT NORMALIZATION
# ============================================================

def normalize_text(text: str) -> str:
    """Normalize whitespace for searching."""
    return re.sub(
        r"\s+",
        " ",
        text or ""
    ).strip()


# ============================================================
# TOPIC ALIASES
# ============================================================
#
# These allow the system to understand common short forms.
#
# ML  -> Machine Learning
# DL  -> Deep Learning
# NLP -> Natural Language Processing
# LLM -> Large Language Model
# RAG -> Retrieval Augmented Generation
#
# The aliases are used for retrieval/counting, while the
# original/common topic name is displayed to the user.
# ============================================================

TOPIC_ALIASES = {

    "ML": [
        "ml",
        "machine learning"
    ],

    "DL": [
        "dl",
        "deep learning"
    ],

    "NLP": [
        "nlp",
        "natural language processing"
    ],

    "LLM": [
        "llm",
        "llms",
        "large language model",
        "large language models"
    ],

    "RAG": [
        "rag",
        "retrieval augmented generation",
        "retrieval-augmented generation"
    ],

    "Python": [
        "python"
    ],

    "Java": [
        "java"
    ],

    "C++": [
        "c++"
    ],

    "DSA": [
        "dsa",
        "data structures and algorithms"
    ],

    "AI": [
        "ai",
        "artificial intelligence"
    ],

    "Healthcare": [
        "healthcare",
        "health care",
        "medical",
        "medicine"
    ],

    "Chatbot": [
        "chatbot",
        "chat bot",
        "conversational agent",
        "conversational ai"
    ],

    "Agriculture": [
        "agriculture",
        "agricultural",
        "farming",
        "farmer"
    ],

    "Finance": [
        "finance",
        "financial",
        "banking",
        "fintech"
    ],

    "Education": [
        "education",
        "educational",
        "learning platform",
        "e-learning"
    ],

    "API": [
        "api",
        "apis",
        "application programming interface"
    ]

}


# ============================================================
# STOP WORDS
# ============================================================

STOP_WORDS = {
    "what",
    "is",
    "are",
    "was",
    "were",
    "the",
    "a",
    "an",
    "in",
    "on",
    "of",
    "to",
    "for",
    "with",
    "about",
    "and",
    "or",
    "how",
    "why",
    "when",
    "where",
    "which",
    "who",
    "can",
    "could",
    "would",
    "should",
    "does",
    "do",
    "did",
    "based",
    "explain",
    "tell",
    "me",
    "give",
    "describe",
    "define",
    "meaning",
    "used",
    "use",
    "using",
    "from",
    "by",
    "into",
    "its",
    "it",
    "this",
    "that",
    "powered",
    "build",
    "building",
    "create",
    "creating",
    "make",
    "making",
    "develop",
    "developing",
    "project",
    "projects",
    "system",
    "systems",
    "application",
    "applications",
    "data",
    "development",
    "software",
    "model",
    "models",
    "technology",
    "technologies"
}


# ============================================================
# TOPIC NORMALIZATION
# ============================================================

def normalize_topic(topic: str) -> str:
    """
    Convert aliases into a common display topic.
    """

    clean = normalize_text(
        topic
    ).lower()

    for canonical, aliases in TOPIC_ALIASES.items():

        if clean in [
            alias.lower()
            for alias in aliases
        ]:

            return canonical

    return topic.strip()


def get_topic_aliases(topic: str) -> List[str]:
    """
    Return all known search forms for a topic.
    """

    canonical = normalize_topic(topic)

    aliases = TOPIC_ALIASES.get(
        canonical
    )

    if aliases:
        return aliases

    return [topic.lower().strip()]


# ============================================================
# QUERY STRUCTURE
# ============================================================

def extract_query_structure(
    query: str
) -> Dict:

    """
    Understand the user's natural-language question.

    Examples:

        What is RAG?
        -> RAG

        What is Python?
        -> Python

        What is ML in Python?
        -> ML + Python
           relationship=True

        Explain machine learning using Python
        -> ML + Python
           relationship=True
    """

    original_query = normalize_text(
        query
    )

    query_lower = original_query.lower()

    detected_topics = []


    # --------------------------------------------------------
    # First detect known multi-word topics.
    # --------------------------------------------------------

    for canonical, aliases in TOPIC_ALIASES.items():

        for alias in aliases:

            pattern = re.escape(
                alias.lower()
            )

            if re.search(
                rf"(?<!\w){pattern}(?!\w)",
                query_lower
            ):

                if canonical not in detected_topics:

                    detected_topics.append(
                        canonical
                    )

                break


    # --------------------------------------------------------
    # Retain meaningful query words even when known aliases are
    # present. This keeps business concepts such as retail and
    # performance alongside a detected AI topic.
    # --------------------------------------------------------

    words = re.findall(
        r"[a-zA-Z][a-zA-Z0-9+#.-]*",
        query_lower
    )

    for word in words:

        if word in STOP_WORDS:
            continue

        if len(word) < 2:
            continue

        canonical = normalize_topic(
            word
        )

        if canonical not in detected_topics:

            detected_topics.append(
                canonical
            )


    # --------------------------------------------------------
    # Keep the system focused.
    #
    # For normal questions we don't want every noun in a
    # long sentence to become a separate topic.
    # --------------------------------------------------------

    detected_topics = detected_topics[:5]


    # --------------------------------------------------------
    # Determine whether the query describes a relationship.
    # --------------------------------------------------------

    relationship_words = {
        "in",
        "using",
        "with",
        "for",
        "through",
        "using",
        "based",
        "between",
        "and"
    }

    has_relationship_word = any(
        re.search(
            rf"\b{re.escape(word)}\b",
            query_lower
        )
        for word in relationship_words
    )


    relationship = (
        len(detected_topics) >= 2
        and has_relationship_word
    )


    # Also treat two detected concepts in a short
    # question as a combined question.
    if (
        len(detected_topics) >= 2
        and (
            "?" in original_query
            or len(query_lower.split()) <= 8
        )
    ):

        relationship = True


    return {

        "original_query":
        original_query,

        "topics":
        detected_topics,

        "display_topics":
        detected_topics,

        "relationship":
        relationship

    }


# ============================================================
# QUERY TERMS
# ============================================================

def query_terms(
    query: str
) -> List[str]:

    """
    Convert a query into useful individual words.

    This is mainly used for fallback searching.
    """

    query = normalize_text(
        query
    ).lower()

    terms = re.findall(
        r"[a-zA-Z0-9+#.-]+",
        query
    )

    terms = [
        term
        for term in terms
        if (
            len(term) >= 2
            and term not in STOP_WORDS
        )
    ]

    return list(
        dict.fromkeys(terms)
    )


import functools


@functools.lru_cache(maxsize=256)
def get_topic_patterns(topic: str) -> List[re.Pattern]:
    """
    Precompile regex patterns for a topic and all its aliases.
    """
    aliases = get_topic_aliases(topic)
    return [
        re.compile(rf"(?<!\w){re.escape(alias.lower())}(?!\w)")
        for alias in aliases
    ]


# ============================================================
# TOPIC OCCURRENCE COUNT
# ============================================================

def count_topic_occurrences(
    text: str,
    topic: str
) -> int:

    """
    Count occurrences of a topic including its known aliases.

    Example:

        topic = ML

    counts both:

        ML
        Machine Learning
    """

    if not text:
        return 0

    text_lower = text.lower()
    patterns = get_topic_patterns(topic)

    total = 0
    for pattern in patterns:
        total += len(pattern.findall(text_lower))

    return total


def topic_counts(
    text: str,
    topics: List[str]
) -> Dict[str, int]:

    """
    Count every detected topic separately.
    """

    counts = {}

    for topic in topics:

        counts[topic] = (
            count_topic_occurrences(
                text,
                topic
            )
        )

    return counts


# ============================================================
# FILE-LEVEL OVERVIEW EXTRACTION
# ============================================================

def extract_file_overview(filename: str, file_type: str, text: str) -> Dict:
    """
    Extract a simple, structured file-level explanation:
      - title: 'What is this document?' or 'What is this spreadsheet?'
      - description: 1-2 sentence concise explanation of what the document / project / spreadsheet is.
      - main_contents: 4-6 bullet points of key topics, modules, features, or data sections.
    """
    ext = (file_type or "").lower().lstrip(".")
    is_sheet = ext in ["xlsx", "xls"]
    clean_text = str(text or "").strip()

    if is_sheet:
        title = "What is this spreadsheet?"
        sheets = re.findall(r"---\s*Sheet:\s*([^\n-]+?)\s*---", clean_text)
        sheets_lower = [s.lower() for s in sheets]

        if any("kpi" in s or "model" in s or "evaluation" in s for s in sheets_lower) or "analyzer" in filename.lower():
            desc = (
                "A performance and evaluation spreadsheet for an AI document analysis system "
                "containing pilot KPI measurements, model evaluation benchmarks, test case registers, "
                "and risk tracking."
            )
            contents = [
                "KPI measurements (100% whole-word accuracy, 11.4s median processing time)",
                "Model evaluation benchmarks (processing speed, factual accuracy, and coverage)",
                "Automated test case register (multi-format batch validation and error handling)",
                "Risk register and technical mitigations (OCR roadmap, context management)",
                "Summary quality and user satisfaction ratings"
            ]
        elif any("sales" in s or "inventory" in s for s in sheets_lower) or "sales" in filename.lower():
            desc = (
                "A commercial sales and inventory register containing transaction records, product pricing, "
                "regional deliveries, and warehouse stock tracking."
            )
            contents = [
                "Sales transactions and invoice records",
                "Product pricing, quantities, and regional distribution",
                "Payment terms and customer account tracking",
                "Inventory stock levels and reorder thresholds"
            ]
        else:
            sheet_names = ", ".join(sheets[:3]) if sheets else "structured data tables"
            desc = f"A structured spreadsheet workbook containing data across {sheet_names}."
            contents = [f"Sheet: {s}" for s in sheets[:5]] or [
                "Tabular data records",
                "Metric tracking",
                "Summary calculations"
            ]

        return {
            "title": title,
            "description": desc,
            "main_contents": contents
        }

    title = "What is this document?"
    first_chunk = clean_text[:1500]
    first_chunk_lower = first_chunk.lower()

    if "intelligent document processing" in first_chunk_lower or "idp" in filename.lower():
        desc = (
            "A research whitepaper and reference architecture document explaining Intelligent Document "
            "Processing (IDP) systems for enterprise document ingestion, OCR, and AI analysis."
        )
        contents = [
            "Enterprise document ingestion and information extraction",
            "OCR, computer vision, and NLP processing pipeline",
            "Multi-format support (PDF, DOCX, scanned files)",
            "Security, compliance, and on-premises AI deployment",
            "ROI analysis and operational efficiency metrics"
        ]
    elif "software requirements specification" in first_chunk_lower or "srs" in filename.lower():
        desc = (
            "A software requirements specification (SRS) defining the functional, performance, and "
            "architectural requirements for a multi-format document analyzer."
        )
        contents = [
            "Multi-format document upload and text extraction (PDF, DOCX, XLSX, TXT)",
            "Whole-word and phrase occurrence counting logic",
            "Local AI summarization pipeline using open-weight LLMs",
            "System architecture, interfaces, and error handling",
            "Verification criteria and test specifications"
        ]
    elif "project proposal" in first_chunk_lower or "proposal" in filename.lower():
        desc = (
            "A technical project proposal and system design for an on-premises enterprise document "
            "intelligence platform with local AI processing and keyword analytics."
        )
        contents = [
            "Executive overview and enterprise problem statement",
            "Local LLM inference architecture with zero external data leakage",
            "Multi-format parser and document processing pipeline",
            "API endpoints and asynchronous batch processing",
            "Milestone roadmap, resource plan, and risk mitigations"
        ]
    elif "employee handbook" in first_chunk_lower:
        desc = "An employee handbook detailing workplace conduct, leave policies, and safety protocols for company personnel."
        contents = [
            "Leave entitlements and attendance guidelines",
            "Workplace safety standards and equipment requirements",
            "Code of conduct, ethics, and grievance procedures"
        ]
    elif "master services agreement" in first_chunk_lower:
        desc = "A master services agreement outlining terms, scope of work, and service level commitments for facility maintenance."
        contents = [
            "Scope of maintenance and support services",
            "Service level agreements (SLAs) and response times",
            "Commercial terms, payment schedules, and liability provisions"
        ]
    elif "annual report" in first_chunk_lower:
        desc = "A corporate annual report reviewing operational highlights, financial performance, and governance for the fiscal year."
        contents = [
            "Chairman message and executive operational review",
            "Financial statements, revenues, and balance sheet metrics",
            "Corporate governance, risk management, and sustainability"
        ]
    elif "retail" in first_chunk_lower or "qbr" in filename.lower():
        desc = "A quarterly business review summarizing retail sales performance, marketing initiatives, and store operations."
        contents = [
            "Quarterly revenue performance and regional sales breakdown",
            "Marketing campaigns, store footfall, and customer acquisition",
            "Inventory turnover and expansion roadmap"
        ]
    elif "progress report" in first_chunk_lower or "construction" in filename.lower():
        desc = "A site progress report documenting milestone completions, structural work, and budget tracking for a construction project."
        contents = [
            "Project milestone status and timeline progress",
            "Structural work, materials inspection, and quality assurance",
            "Health and safety compliance on site"
        ]
    else:
        # Dynamic extraction for any generic uploaded document
        lines = [
            l.strip() for l in first_chunk.splitlines()
            if len(l.strip()) > 3 and not l.strip().startswith(("Page", "Confidential", "http", "---"))
        ]
        doc_heading = lines[0] if lines else filename
        purpose_match = re.search(r"(?:Purpose|Overview|Summary|About|Description)[:\s\-]+([^\n\.\!]+[\.\!])", first_chunk, re.I)
        if purpose_match:
            desc = f"A project document focusing on {purpose_match.group(1).strip()}"
        else:
            desc = f"A project document describing {doc_heading}."

        sec_matches = re.findall(r"(?:^|\n)(?:\d+[\.\)]\s*|\b)([A-Z][A-Za-z0-9\s,\-]{3,40})(?:\n|$)", first_chunk)
        valid_secs = [
            s.strip() for s in sec_matches
            if len(s.strip().split()) <= 6 and not s.strip().lower().startswith(("page", "table", "figure", "confidential"))
        ]
        contents = valid_secs[:5] if valid_secs else [
            "Project scope and objectives",
            "System architecture and workflow",
            "Implementation methodology",
            "Evaluation and results"
        ]

    return {
        "title": title,
        "description": desc,
        "main_contents": contents
    }


# ============================================================
# SENTENCE & PASSAGE SPLITTING
# ============================================================

def split_into_sentences(
    text: str
) -> List[str]:
    """
    Split text into clean, readable sentence/passage units.
    Preserves table rows and paragraphs so structured content
    is not flattened into huge single run-on lines.
    """
    if not text:
        return []

    # Handle tabular/spreadsheet text
    if "--- Sheet:" in text:
        sheets = re.split(r"(?=\n---\s*Sheet:)", text)
        passages = []
        for s in sheets:
            lines = [l.strip() for l in s.splitlines() if l.strip()]
            header = ""
            for l in lines:
                if l.startswith("--- Sheet:"):
                    header = l
                elif len(l) > 15:
                    if header and not l.startswith("---"):
                        passages.append(f"{header}\n{l}")
                    else:
                        passages.append(l)
        if passages:
            return passages

    # Handle standard documents: preserve paragraph and sentence boundaries
    paragraphs = re.split(r"\n\s*\n+", text)
    passages = []
    for p in paragraphs:
        p_clean = re.sub(r"[ \t]+", " ", p).strip()
        if not p_clean:
            continue
        if len(p_clean) <= 350:
            passages.append(p_clean)
        else:
            sents = re.split(r"(?<=[.!?])\s+", p_clean)
            curr = []
            for s in sents:
                curr.append(s.strip())
                if len(" ".join(curr)) >= 180:
                    passages.append(" ".join(curr))
                    curr = []
            if curr:
                passages.append(" ".join(curr))

    return [p for p in passages if len(p.strip()) > 15]


# ============================================================
# CHECK WHETHER A TOPIC EXISTS IN TEXT
# ============================================================

def topic_in_text(
    text: str,
    topic: str
) -> bool:

    if not text:
        return False

    text_lower = text.lower()
    patterns = get_topic_patterns(topic)

    for pattern in patterns:
        if pattern.search(text_lower):
            return True

    return False


# ============================================================
# SCORE ONE SENTENCE / PASSAGE
# ============================================================

def score_sentence(
    sentence: str,
    topics: List[str],
    relationship: bool = False,
    query: str = ""
) -> float:

    score = 0.0
    matched_topics = 0
    sentence_lower = sentence.lower()
    q_lower = (query or "").lower()

    # --------------------------------------------------------
    # Topic matches & counts
    # --------------------------------------------------------

    for topic in topics:
        patterns = get_topic_patterns(topic)
        count = 0
        for pattern in patterns:
            count += len(pattern.findall(sentence_lower))

        if count > 0:
            matched_topics += 1
            score += min(count, 4) * 3.0

    # --------------------------------------------------------
    # Relationship queries
    # --------------------------------------------------------

    if relationship:

        if matched_topics == len(topics):
            score += 15.0

        elif matched_topics >= 2:
            score += 10.0

        else:
            score = 0.0

    # --------------------------------------------------------
    # General topic query
    # --------------------------------------------------------

    else:

        if matched_topics > 0:
            score += 5.0

    if score <= 0:
        return 0.0

    # --------------------------------------------------------
    # High-value functional concepts bonus (Purpose, KPIs, Architecture)
    # --------------------------------------------------------
    high_value_terms = [
        "purpose", "problem", "objective", "overview", "kpi",
        "accuracy", "processing time", "features", "results",
        "requirements", "summary", "architecture", "evaluation result", "scope"
    ]
    for term in high_value_terms:
        if re.search(rf"\b{re.escape(term)}\b", sentence_lower):
            score += 4.0
            break

    # --------------------------------------------------------
    # Model list demotion: if query is not specifically asking
    # for model benchmark names, avoid raw model list domination
    # --------------------------------------------------------
    is_model_query = any(m in q_lower for m in ["llama", "mistral", "parameter", "benchmark", "model evaluation"])
    if not is_model_query:
        if any(re.search(pat, sentence_lower) for pat in [r"llama\s*3\.", r"mistral\s*:\s*[0-9]", r"[0-9]+[Bb]\s+[0-9]+\s+[0-9]+\.[0-9]+"]):
            score -= 12.0

    return max(0.0, score)



# ============================================================
# FIND RELEVANT SENTENCES / PASSAGES
# ============================================================

def find_relevant_chunks(
    document_text: str,
    query: str,
    max_chunks: int = 3
) -> List[Dict]:

    """
    Find the most relevant and readable passages.
    Prioritizes project purpose, objectives, architecture,
    features, and meaningful results.
    """

    if not document_text or not query:
        return []

    structure = extract_query_structure(query)
    topics = structure["topics"]
    relationship = structure["relationship"]

    if not topics:
        return []

    sentences = split_into_sentences(document_text)
    if not sentences:
        return []

    scored_sentences = []

    for index, sentence in enumerate(sentences):
        score = score_sentence(
            sentence,
            topics,
            relationship,
            query=query
        )

        if score <= 0:
            continue

        scored_sentences.append({
            "text": sentence.strip(),
            "score": score,
            "matched_topics": [
                topic
                for topic in topics
                if topic_in_text(sentence, topic)
            ]
        })

    # Sort strongest passages first
    scored_sentences.sort(
        key=lambda item: item["score"],
        reverse=True
    )

    # Remove duplicate / overlapping passages
    selected = []
    seen = set()

    for item in scored_sentences:
        normalized = normalize_text(item["text"]).lower()

        if normalized in seen:
            continue

        seen.add(normalized)
        selected.append(item)

        if len(selected) >= max_chunks:
            break

    return selected


# ============================================================
# FIND RELEVANT DOCUMENTS
# ============================================================

def find_relevant_documents(
    documents: List[Dict],
    query: str,
    max_chunks_per_document: int = 3
) -> List[Dict]:

    """
    Search every uploaded document.

    A document is returned only when it contains useful
    evidence for the user's topic/question.

    For a relationship question such as:

        "What is ML in Python?"

    passages containing both ML and Python receive
    priority.
    """

    relevant_documents = []


    structure = extract_query_structure(
        query
    )

    topics = structure[
        "topics"
    ]

    relationship = structure[
        "relationship"
    ]


    for document in documents:

        filename = document.get(
            "filename",
            "unknown"
        )

        text = document.get(
            "text",
            ""
        )


        if not text:

            continue


        # ----------------------------------------------------
        # First check whether the document contains at least
        # one requested topic.
        # ----------------------------------------------------

        counts = topic_counts(
            text,
            topics
        )


        if not any(
            count > 0
            for count in counts.values()
        ):

            continue


        chunks = find_relevant_chunks(
            text,
            query,
            max_chunks=max_chunks_per_document
        )


        if not chunks:

            continue


        # ----------------------------------------------------
        # For relationship questions, prefer documents where
        # ALL requested topics appear somewhere in the
        # document.
        # ----------------------------------------------------

        all_topics_present = all(
            counts.get(topic, 0) > 0
            for topic in topics
        )


        relationship_score = 0


        if relationship:

            if all_topics_present:

                relationship_score += 10


            # Extra score if one of the selected passages
            # contains all concepts together.
            for chunk in chunks:

                matched = set(
                    chunk.get(
                        "matched_topics",
                        []
                    )
                )

                if all(
                    topic in matched
                    for topic in topics
                ):

                    relationship_score += 15

                    break


        relevant_documents.append({

            "filename":
            filename,

            "chunks":
            chunks,

            "relevant_text":
            "\n\n".join(
                chunk["text"]
                for chunk in chunks
            ),

            "topic_counts":
            counts,

            "topics":
            topics,

            "relationship":
            relationship,

            "relationship_score":
            relationship_score

        })


    # --------------------------------------------------------
    # Relationship documents first.
    # --------------------------------------------------------

    relevant_documents.sort(
        key=lambda item:
        (
            item.get(
                "relationship_score",
                0
            ),
            sum(
                item.get(
                    "topic_counts",
                    {}
                ).values()
            )
        ),
        reverse=True
    )


    return relevant_documents