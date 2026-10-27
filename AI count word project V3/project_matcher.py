import os
import re
from typing import Dict, List, Set


from document_processors import extract_text


# ============================================================
# CONFIGURATION
# ============================================================

SUPPORTED_EXTENSIONS = {
    ".pdf",
    ".doc",
    ".docx",
    ".txt",
    ".xls",
    ".xlsx",
}

MAX_REPOSITORY_FILES = 10

# Minimum score required for a project to be considered meaningful.
MEANINGFUL_SCORE = 30


# ============================================================
# CONCEPT ALIASES
# ============================================================

_ALIASES = {
    "rag": (
        "rag",
        "retrieval augmented generation",
        "retrieval-augmented generation",
    ),
    "ai": (
        "ai",
        "artificial intelligence",
    ),
    "ml": (
        "ml",
        "machine learning",
    ),
    "dl": (
        "dl",
        "deep learning",
    ),
    "nlp": (
        "nlp",
        "natural language processing",
    ),
    "llm": (
        "llm",
        "llms",
        "large language model",
        "large language models",
    ),
    "chatbot": (
        "chatbot",
        "chat bot",
        "conversational agent",
        "conversational ai",
    ),
    "healthcare": (
        "healthcare",
        "health care",
        "medical",
        "medicine",
    ),
    "education": (
        "education",
        "educational",
        "learning platform",
        "e-learning",
    ),
    "finance": (
        "finance",
        "financial",
        "banking",
        "fintech",
    ),
    "agriculture": (
        "agriculture",
        "agricultural",
        "farming",
        "farmer",
    ),
    "document": (
        "document",
        "documents",
        "document analysis",
        "document analyzer",
    ),
    "api": (
        "api",
        "apis",
        "application programming interface",
    ),
    "python": (
        "python",
    ),
    "java": (
        "java",
    ),
    "javascript": (
        "javascript",
        "js",
    ),
    "react": (
        "react",
        "reactjs",
        "react.js",
    ),
    "flask": (
        "flask",
    ),
    "django": (
        "django",
    ),
    "fastapi": (
        "fastapi",
    ),
    "classification": (
        "classification",
        "classify",
        "classifier",
    ),
    "prediction": (
        "prediction",
        "predict",
        "predictive",
    ),
    "recommendation": (
        "recommendation",
        "recommend",
        "recommender",
    ),
    "sentiment": (
        "sentiment",
        "sentiment analysis",
    ),
    "computer_vision": (
        "computer vision",
        "image recognition",
        "image classification",
        "object detection",
    ),
}


# ============================================================
# STOP WORDS
# ============================================================

_STOP_WORDS = {
    "a",
    "an",
    "and",
    "are",
    "as",
    "at",
    "based",
    "be",
    "by",
    "can",
    "could",
    "do",
    "does",
    "for",
    "from",
    "how",
    "i",
    "idea",
    "in",
    "into",
    "is",
    "it",
    "me",
    "my",
    "of",
    "on",
    "or",
    "our",
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
    "technologies",
    "powered",
    "that",
    "the",
    "their",
    "this",
    "to",
    "use",
    "used",
    "using",
    "want",
    "what",
    "which",
    "with",
    "would",
}


# ============================================================
# NORMALIZATION
# ============================================================

def normalize_text(text: str) -> str:
    """
    Normalize text for matching.
    """
    text = str(text or "").lower()

    # Replace special characters with spaces.
    text = re.sub(r"[^a-z0-9\s\-]", " ", text)

    # Normalize whitespace.
    text = re.sub(r"\s+", " ", text)

    return text.strip()


# ============================================================
# CONCEPT EXTRACTION
# ============================================================

def _concepts(text: str) -> Set[str]:
    """
    Extract meaningful concepts from text.

    Returns:
        Set of normalized concepts.
    """

    normalized = normalize_text(text)

    if not normalized:
        return set()

    concepts = set()

    # --------------------------------------------------------
    # Normal individual words
    # --------------------------------------------------------

    words = re.findall(r"[a-z0-9]+", normalized)

    for word in words:
        if len(word) >= 3 and word not in _STOP_WORDS:
            concepts.add(word)

    # --------------------------------------------------------
    # Known domain / technology concepts
    # --------------------------------------------------------

    for canonical, aliases in _ALIASES.items():

        for alias in aliases:

            alias_normalized = normalize_text(alias)

            if not alias_normalized:
                continue

            pattern = rf"(?<!\w){re.escape(alias_normalized)}(?!\w)"

            if re.search(pattern, normalized):
                concepts.add(canonical)
                break

    return concepts


def get_keywords(text: str) -> set:
    """
    Compatibility function for older callers.
    """
    return _concepts(text)


# ============================================================
# CONCEPT CATEGORY HELPERS
# ============================================================

_TECHNOLOGY_CONCEPTS = {
    "ai",
    "ml",
    "dl",
    "nlp",
    "llm",
    "rag",
    "api",
    "python",
    "java",
    "javascript",
    "react",
    "flask",
    "django",
    "fastapi",
}


_DOMAIN_CONCEPTS = {
    "healthcare",
    "education",
    "finance",
    "agriculture",
}


_METHOD_CONCEPTS = {
    "classification",
    "prediction",
    "recommendation",
    "sentiment",
    "computer_vision",
    "rag",
    "nlp",
    "llm",
}


# ============================================================
# PHRASE DETECTION
# ============================================================

def _contains_phrase(text: str, phrase: str) -> bool:
    normalized_text = normalize_text(text)
    normalized_phrase = normalize_text(phrase)

    if not normalized_text or not normalized_phrase:
        return False

    return bool(
        re.search(
            rf"(?<!\w){re.escape(normalized_phrase)}(?!\w)",
            normalized_text,
        )
    )


def _important_phrases(text: str) -> Set[str]:
    """
    Extract important multi-word phrases from the query.
    """

    normalized = normalize_text(text)

    phrases = set()

    for canonical, aliases in _ALIASES.items():

        for alias in aliases:

            if " " in alias and _contains_phrase(normalized, alias):
                phrases.add(canonical)

    return phrases


# ============================================================
# SIMILARITY CALCULATION
# ============================================================

def calculate_similarity(project_idea: str, document_text: str) -> float:
    """
    Calculate similarity while preventing generic AI/ML terminology
    from making unrelated documents appear relevant.

    The score prioritizes:
    - Specific query concepts
    - Domain concepts
    - Technology concepts
    - Methodology concepts
    - Multi-word phrase evidence

    Generic concepts alone should not produce a strong score.
    """

    idea_concepts = _concepts(project_idea)
    document_concepts = _concepts(document_text)

    if not idea_concepts or not document_concepts:
        return 0.0

    overlap = idea_concepts & document_concepts

    if not overlap:
        return 0.0

    # --------------------------------------------------------
    # Generic concepts
    # These are too broad to establish relevance by themselves.
    # --------------------------------------------------------

    generic_concepts = {
        "ai",
        "ml",
        "dl",
        "nlp",
        "llm",
        "api",
        "data",
        "model",
        "models",
        "system",
        "systems",
        "application",
        "applications",
        "software",
        "technology",
        "technologies",
        "development",
        "prediction",
        "classification",
    }

    # Only specific concepts are allowed to drive the main score.
    specific_idea_concepts = idea_concepts - generic_concepts
    specific_overlap = overlap - generic_concepts

    # If the query contains specific concepts but the document
    # only matches generic AI/ML terminology, it is not relevant.
    if specific_idea_concepts and not specific_overlap:
        return 0.0

    # --------------------------------------------------------
    # 1. Specific concept coverage
    # --------------------------------------------------------

    if specific_idea_concepts:
        specific_coverage = (
            len(specific_overlap) /
            len(specific_idea_concepts)
        )
    else:
        specific_coverage = 0.0

    coverage_score = specific_coverage * 60

    # --------------------------------------------------------
    # 2. Technology overlap
    # --------------------------------------------------------

    idea_technologies = (
        idea_concepts &
        _TECHNOLOGY_CONCEPTS
    )

    document_technologies = (
        document_concepts &
        _TECHNOLOGY_CONCEPTS
    )

    technology_overlap = (
        idea_technologies &
        document_technologies
    )

    if idea_technologies:
        technology_score = (
            len(technology_overlap) /
            len(idea_technologies)
        ) * 15
    else:
        technology_score = 0

    # --------------------------------------------------------
    # 3. Domain overlap
    # --------------------------------------------------------

    idea_domains = (
        idea_concepts &
        _DOMAIN_CONCEPTS
    )

    document_domains = (
        document_concepts &
        _DOMAIN_CONCEPTS
    )

    domain_overlap = (
        idea_domains &
        document_domains
    )

    if idea_domains:
        domain_score = (
            len(domain_overlap) /
            len(idea_domains)
        ) * 15
    else:
        domain_score = 0

    # --------------------------------------------------------
    # 4. Methodology overlap
    # --------------------------------------------------------

    idea_methods = (
        idea_concepts &
        _METHOD_CONCEPTS
    )

    document_methods = (
        document_concepts &
        _METHOD_CONCEPTS
    )

    method_overlap = (
        idea_methods &
        document_methods
    )

    if idea_methods:
        method_score = (
            len(method_overlap) /
            len(idea_methods)
        ) * 10
    else:
        method_score = 0

    # --------------------------------------------------------
    # 5. Multi-word phrase evidence
    # --------------------------------------------------------

    important_phrases = _important_phrases(project_idea)

    phrase_bonus = 0

    for phrase in important_phrases:
        if phrase in document_concepts:
            phrase_bonus += 3

    phrase_bonus = min(phrase_bonus, 10)

    # --------------------------------------------------------
    # Final score
    # --------------------------------------------------------

    score = (
        coverage_score
        + technology_score
        + domain_score
        + method_score
        + phrase_bonus
    )

    return round(min(score, 100), 2)


# ============================================================
# CLASSIFICATION
# ============================================================

def classify_similarity(score: float) -> str:
    """
    Convert percentage into a meaningful classification.
    """

    if score >= 75:
        return "high"

    if score >= 55:
        return "related"

    if score >= MEANINGFUL_SCORE:
        return "partial"

    return "low"


# ============================================================
# REPOSITORY FILES
# ============================================================

def get_repository_files(upload_folder: str = "uploads") -> List[str]:
    """
    Return supported repository files.

    Maximum repository size is intentionally limited to 10.
    """

    if not os.path.isdir(upload_folder):
        return []

    files = []

    for filename in sorted(os.listdir(upload_folder)):

        path = os.path.join(upload_folder, filename)

        if not os.path.isfile(path):
            continue

        extension = os.path.splitext(filename)[1].lower()

        if extension in SUPPORTED_EXTENSIONS:
            files.append(path)

    return files[:MAX_REPOSITORY_FILES]


# ============================================================
# READ PROJECT FILE
# ============================================================

def read_project_file(filepath: str) -> str:
    """
    Extract readable text from a repository document.
    """

    try:

        with open(filepath, "rb") as file:

            text = extract_text(
                file,
                os.path.basename(filepath),
            )

            return text or ""

    except (
        OSError,
        ValueError,
        RuntimeError,
        TypeError,
    ):

        return ""


# ============================================================
# OVERLAP EXPLANATION
# ============================================================

def _explain_overlap(
    idea: str,
    text: str,
) -> Dict[str, List[str]]:
    """
    Explain what the project idea and repository document
    have in common.
    """

    idea_concepts = _concepts(idea)
    document_concepts = _concepts(text)

    overlap = idea_concepts & document_concepts

    ordered = sorted(overlap)

    technologies = [
        item
        for item in ordered
        if item in _TECHNOLOGY_CONCEPTS
    ]

    domains = [
        item
        for item in ordered
        if item in _DOMAIN_CONCEPTS
    ]

    methodology = [
        item
        for item in ordered
        if item in _METHOD_CONCEPTS
    ]

    return {
        "overlap": ordered[:15],

        "common_objectives": ordered[:10],

        "common_technologies": technologies[:10],

        "common_domains": domains[:10],

        "common_methodology": methodology[:10],
    }


# ============================================================
# MATCH EXPLANATION
# ============================================================

def _build_relationship(
    score: float,
    overlap: Dict[str, List[str]],
) -> str:
    """
    Create a short machine-readable relationship explanation.
    """

    technologies = overlap.get("common_technologies", [])
    domains = overlap.get("common_domains", [])
    methodology = overlap.get("common_methodology", [])

    parts = []

    if technologies:
        parts.append(
            "technology: " + ", ".join(technologies[:4])
        )

    if domains:
        parts.append(
            "domain: " + ", ".join(domains[:3])
        )

    if methodology:
        parts.append(
            "methodology: " + ", ".join(methodology[:4])
        )

    if not parts:
        return "Limited conceptual overlap."

    if score >= 75:
        prefix = "Strong relationship based on"
    elif score >= 55:
        prefix = "Good relationship based on"
    else:
        prefix = "Partial relationship based on"

    return prefix + " " + "; ".join(parts) + "."


# ============================================================
# MAIN PROJECT MATCHER
# ============================================================

def find_similar_projects(
    project_idea: str,
    upload_folder: str = "uploads",
) -> Dict:
    """
    Search the repository and find meaningfully related projects.

    Returns:
        total_projects
        results
        all_results
    """

    repository_files = get_repository_files(upload_folder)

    results = []
    all_results = []

    for filepath in repository_files:

        document_text = read_project_file(filepath)

        if not document_text.strip():
            continue

        score = calculate_similarity(
            project_idea,
            document_text,
        )

        classification = classify_similarity(score)

        overlap_data = _explain_overlap(
            project_idea,
            document_text,
        )

        relationship = _build_relationship(
            score,
            overlap_data,
        )

        result = {
            "filename": os.path.basename(filepath),

            # Keep both names for compatibility.
            "score": score,
            "match_percentage": score,

            "classification": classification,

            "overlap": overlap_data["overlap"],

            "common_objectives": overlap_data[
                "common_objectives"
            ],

            "common_technologies": overlap_data[
                "common_technologies"
            ],

            "common_domains": overlap_data[
                "common_domains"
            ],

            "common_methodology": overlap_data[
                "common_methodology"
            ],

            "relationship": relationship,
        }

        all_results.append(result)

        if score >= MEANINGFUL_SCORE:
            results.append(result)

    # Highest matching project first.
    results.sort(
        key=lambda item: item["score"],
        reverse=True,
    )

    all_results.sort(
        key=lambda item: item["score"],
        reverse=True,
    )

    return {
        "total_projects": len(repository_files),

        # Meaningfully related projects.
        "results": results,

        # All scanned projects, including low matches.
        "all_results": all_results,
    }