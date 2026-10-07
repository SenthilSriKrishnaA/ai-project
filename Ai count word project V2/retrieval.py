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
    "that"
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
    # Detect remaining meaningful words.
    # --------------------------------------------------------

    if not detected_topics:

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
# SENTENCE SPLITTING
# ============================================================

def split_into_sentences(
    text: str
) -> List[str]:

    """
    Split text into readable sentence-sized units.
    """

    text = normalize_text(
        text
    )

    if not text:
        return []

    sentences = re.split(
        r"(?<=[.!?])\s+",
        text
    )

    return [
        sentence.strip()
        for sentence in sentences
        if sentence.strip()
    ]


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
# SCORE ONE SENTENCE
# ============================================================

def score_sentence(
    sentence: str,
    topics: List[str],
    relationship: bool = False
) -> float:

    score = 0.0
    matched_topics = 0
    sentence_lower = sentence.lower()

    # --------------------------------------------------------
    # Topic matches & counts in a single pass
    # --------------------------------------------------------

    for topic in topics:
        patterns = get_topic_patterns(topic)
        count = 0
        for pattern in patterns:
            count += len(pattern.findall(sentence_lower))

        if count > 0:
            matched_topics += 1
            score += min(count, 5) * 3

    # --------------------------------------------------------
    # Relationship queries
    # --------------------------------------------------------

    if relationship:

        if matched_topics == len(topics):

            score += 15

        elif matched_topics >= 2:

            score += 10

        else:

            score -= 2

    # --------------------------------------------------------
    # General topic query
    # --------------------------------------------------------

    else:

        if matched_topics > 0:

            score += 5

    return score



# ============================================================
# FIND RELEVANT SENTENCES
# ============================================================

def find_relevant_chunks(
    document_text: str,
    query: str,
    max_chunks: int = 5
) -> List[Dict]:

    """
    Find the most relevant passages.

    Important difference from the old version:

    The complete user sentence is NOT treated as a list
    of search words.

    The query is first converted into topics.

    Relationship questions require the concepts to appear
    together in useful passages.
    """

    if not document_text or not query:

        return []


    structure = extract_query_structure(
        query
    )

    topics = structure[
        "topics"
    ]

    relationship = structure[
        "relationship"
    ]


    if not topics:

        return []


    sentences = split_into_sentences(
        document_text
    )


    if not sentences:

        return []


    scored_sentences = []


    # --------------------------------------------------------
    # Score individual sentences
    # --------------------------------------------------------

    for index, sentence in enumerate(
        sentences
    ):

        score = score_sentence(
            sentence,
            topics,
            relationship
        )


        if score <= 0:

            continue


        # ----------------------------------------------------
        # Add neighboring sentence context.
        #
        # This allows the AI to understand the matching
        # sentence without sending the whole document.
        # ----------------------------------------------------

        start = max(
            0,
            index - 1
        )

        end = min(
            len(sentences),
            index + 2
        )

        context = " ".join(
            sentences[start:end]
        )


        scored_sentences.append({

            "text":
            context,

            "score":
            score,

            "matched_topics": [
                topic
                for topic in topics
                if topic_in_text(
                    sentence,
                    topic
                )
            ]

        })


    # --------------------------------------------------------
    # Sort strongest passages first.
    # --------------------------------------------------------

    scored_sentences.sort(
        key=lambda item:
        item["score"],
        reverse=True
    )


    # --------------------------------------------------------
    # Remove duplicate passages.
    # --------------------------------------------------------

    selected = []

    seen = set()


    for item in scored_sentences:

        normalized = normalize_text(
            item["text"]
        ).lower()


        if normalized in seen:

            continue


        seen.add(
            normalized
        )

        selected.append(
            item
        )


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