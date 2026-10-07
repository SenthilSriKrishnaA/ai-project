import os
import re
from typing import Dict, List

from document_processors import extract_text


SUPPORTED_EXTENSIONS = {
    ".pdf", ".doc", ".docx", ".txt", ".xls", ".xlsx"
}
MAX_REPOSITORY_FILES = 10
MEANINGFUL_SCORE = 30

_ALIASES = {
    "rag": ("rag", "retrieval augmented generation", "retrieval-augmented generation"),
    "ai": ("ai", "artificial intelligence"),
    "ml": ("ml", "machine learning"),
    "nlp": ("nlp", "natural language processing"),
    "llm": ("llm", "llms", "large language model", "large language models"),
    "chatbot": ("chatbot", "chat bot", "conversational agent"),
    "healthcare": ("healthcare", "health care", "medical"),
}
_STOP_WORDS = {
    "a", "an", "and", "are", "as", "based", "be", "by", "can", "for",
    "from", "in", "into", "is", "of", "on", "or", "project", "system",
    "the", "this", "that", "to", "use", "used", "using", "with",
}


def normalize_text(text: str) -> str:
    return re.sub(r"\s+", " ", str(text or "").lower()).strip()


def _concepts(text: str) -> set:
    normalized = normalize_text(text)
    concepts = {
        word for word in re.findall(r"[a-z0-9]+", normalized)
        if len(word) >= 3 and word not in _STOP_WORDS
    }
    for canonical, aliases in _ALIASES.items():
        if any(re.search(rf"(?<!\w){re.escape(alias)}(?!\w)", normalized)
               for alias in aliases):
            concepts.add(canonical)
    return concepts


def get_keywords(text: str) -> set:
    """Return normalized concepts retained for compatibility with older callers."""
    return _concepts(text)


def calculate_similarity(project_idea: str, document_text: str) -> float:
    """Score idea coverage in a document using words plus known concept aliases."""
    idea_concepts = _concepts(project_idea)
    document_concepts = _concepts(document_text)
    if not idea_concepts or not document_concepts:
        return 0.0

    overlap = idea_concepts & document_concepts
    coverage = len(overlap) / len(idea_concepts)
    shared_density = len(overlap) / max(len(document_concepts), 1)
    score = (coverage * 85) + (min(shared_density * 100, 15))
    return round(min(score, 100), 2)


def classify_similarity(score: float) -> str:
    if score >= 70:
        return "high"
    if score >= MEANINGFUL_SCORE:
        return "related"
    return "low"


def get_repository_files(upload_folder: str = "uploads") -> List[str]:
    if not os.path.isdir(upload_folder):
        return []
    files = []
    for filename in sorted(os.listdir(upload_folder)):
        path = os.path.join(upload_folder, filename)
        if os.path.isfile(path) and os.path.splitext(filename)[1].lower() in SUPPORTED_EXTENSIONS:
            files.append(path)
    return files[:MAX_REPOSITORY_FILES]


def read_project_file(filepath: str) -> str:
    try:
        with open(filepath, "rb") as file:
            return extract_text(file, os.path.basename(filepath)) or ""
    except (OSError, ValueError, RuntimeError):
        return ""


def _explain_overlap(idea: str, text: str) -> Dict[str, List[str]]:
    overlap = _concepts(idea) & _concepts(text)
    ordered = sorted(overlap)
    technologies = [item for item in ordered if item in {
        "ai", "ml", "nlp", "llm", "rag", "python", "java", "api"
    }]
    return {
        "overlap": ordered[:12],
        "common_objectives": ordered[:8],
        "common_technologies": technologies[:8],
        "common_methodology": [
            item for item in ordered
            if item in {"rag", "ml", "nlp", "llm", "classification", "prediction"}
        ][:8],
    }


def find_similar_projects(project_idea: str, upload_folder: str = "uploads") -> Dict:
    repository_files = get_repository_files(upload_folder)
    results = []
    for filepath in repository_files:
        document_text = read_project_file(filepath)
        if not document_text.strip():
            continue
        score = calculate_similarity(project_idea, document_text)
        result = {
            "filename": os.path.basename(filepath),
            "score": score,
            "classification": classify_similarity(score),
        }
        result.update(_explain_overlap(project_idea, document_text))
        results.append(result)
    results.sort(key=lambda item: item["score"], reverse=True)
    return {
        "total_projects": len(repository_files),
        "results": [item for item in results if item["score"] >= MEANINGFUL_SCORE],
        "all_results": results,
    }
