import re
import requests
from requests.adapters import HTTPAdapter


# ============================================================
# OLLAMA CONFIGURATION & REUSABLE SESSION
# ============================================================

OLLAMA_URL = "http://localhost:11434/api/generate"
OLLAMA_MODEL = "llama3.2:3b"

# Keep prompts compact & fast for local Ollama
MAX_DOCUMENT_CHARS = 3500

# Maximum output tokens for 5 concise bullet points
MAX_OUTPUT_TOKENS = 120

# Reusable HTTP session with connection pooling for low-latency requests
_session = requests.Session()
_adapter = HTTPAdapter(pool_connections=10, pool_maxsize=10)
_session.mount("http://", _adapter)
_session.mount("https://", _adapter)


# ============================================================
# TEXT LIMITER
# ============================================================

def limit_text(text, max_chars=MAX_DOCUMENT_CHARS):
    """
    Prevent very large documents from overloading local Ollama context.
    """
    if not text:
        return ""

    text = str(text).strip()
    if len(text) <= max_chars:
        return text

    return text[:max_chars] + "\n\n[Document content truncated for AI processing.]"


# ============================================================
# FAST OLLAMA CALL WITH REUSED SESSION
# ============================================================

def call_ollama(prompt, temperature=0.1):
    if not prompt:
        return {
            "success": False,
            "message": "Empty prompt.",
            "response": ""
        }

    payload = {
        "model": OLLAMA_MODEL,
        "prompt": prompt,
        "stream": False,
        "keep_alive": "10m",
        "options": {
            "temperature": temperature,
            "num_predict": MAX_OUTPUT_TOKENS,
            "num_ctx": 2048
        }
    }

    try:
        response = _session.post(
            OLLAMA_URL,
            json=payload,
            timeout=(5, 120)
        )
        response.raise_for_status()

        data = response.json()
        generated_text = data.get("response", "").strip()

        if not generated_text:
            return {
                "success": False,
                "message": "Ollama returned an empty response.",
                "response": ""
            }

        return {
            "success": True,
            "response": generated_text
        }

    except requests.exceptions.ConnectionError:
        return {
            "success": False,
            "message": "Ollama is not running. Please start Ollama.",
            "response": ""
        }

    except requests.exceptions.Timeout:
        return {
            "success": False,
            "message": "Ollama took too long to generate the response. Please try again.",
            "response": ""
        }

    except requests.exceptions.HTTPError as error:
        return {
            "success": False,
            "message": f"Ollama HTTP error: {str(error)}",
            "response": ""
        }

    except Exception as error:
        return {
            "success": False,
            "message": f"Ollama error: {str(error)}",
            "response": ""
        }


# ============================================================
# CLEAN AI OUTPUT
# ============================================================

def clean_summary(text):
    if not text:
        return ""

    text = text.strip()

    # Remove markdown code blocks
    text = re.sub(
        r"```.*?```",
        "",
        text,
        flags=re.DOTALL
    )

    # Remove common introductory phrases
    text = re.sub(
        r"^(here is|here's|summary:|answer:|the answer is|based on the document:?)\s*",
        "",
        text,
        flags=re.IGNORECASE
    )

    # Remove markdown headings
    text = re.sub(
        r"^#+\s*.*$",
        "",
        text,
        flags=re.MULTILINE
    )

    lines = []
    for line in text.splitlines():
        line = line.strip()
        if not line:
            continue

        # Remove bullets and numbering
        line = re.sub(
            r"^[\-\*\•\d\.\)\:]+\s*",
            "",
            line
        ).strip()

        if line:
            lines.append(line)

    # Maximum 5 useful points
    lines = lines[:5]

    cleaned = []
    for line in lines:
        words = line.split()
        if len(words) > 20:
            line = " ".join(words[:20]).rstrip(".,;:") + "."
        cleaned.append(line)

    return "\n".join(
        f"{index}. {line}"
        for index, line in enumerate(cleaned, start=1)
    )


# ============================================================
# LEGACY AI SUMMARY
# ============================================================

def generate_ai_summary(
    text,
    search_word=""
):
    if not text:
        return {
            "success": False,
            "message": "No text available.",
            "summary": ""
        }

    safe_text = limit_text(text)

    prompt = f"""You are a document analysis assistant.

SEARCH TOPIC: {search_word}

DOCUMENT CONTENT:
{safe_text}

TASK: Give exactly 5 short points about the searched topic using only the document content.
RULES:
- Focus strictly on the searched topic.
- Maximum 20 words per point.
- Return only 5 numbered points without heading or introduction.
"""

    result = call_ollama(prompt, temperature=0.1)

    if not result["success"]:
        return {
            "success": False,
            "message": result["message"],
            "summary": ""
        }

    summary = clean_summary(result["response"])
    return {
        "success": True,
        "summary": summary
    }


# ============================================================
# GENERIC DOCUMENT SUMMARY
# ============================================================

def generate_summary(
    text,
    search_word=""
):
    return generate_ai_summary(
        text,
        search_word
    )


# ============================================================
# PDF / DOCUMENT STRICT SUMMARY
# ============================================================

def generate_relevant_summary(
    relevant_text,
    filename,
    question,
    topics=None,
    relationship=False
):
    """
    Generate a summary ONLY from retrieved document content.
    """
    if not relevant_text:
        return {
            "success": False,
            "message": "No relevant content found in this document.",
            "summary": ""
        }

    topics = topics or []
    topic_text = ", ".join(topics) if topics else question
    safe_relevant_text = limit_text(relevant_text)

    if relationship:
        focus_rule = f"Explain the relationship between: {topic_text}."
    else:
        focus_rule = f"Focus strictly on: {topic_text}."

    prompt = f"""You are a strict document-grounded AI analyzer.

QUESTION: {question}
DOCUMENT: {filename}
{focus_rule}

RETRIEVED CONTENT:
{safe_relevant_text}

TASK: Provide exactly 5 concise points answering the question using ONLY the retrieved content above.
RULES:
- Use only facts directly in the retrieved content.
- Maximum 20 words per point.
- Return exactly 5 numbered points.
- No intro, conclusion, or heading.
"""

    result = call_ollama(prompt, temperature=0.05)

    if not result["success"]:
        return {
            "success": False,
            "message": result["message"],
            "summary": ""
        }

    summary = clean_summary(result["response"])
    return {
        "success": True,
        "summary": summary
    }


# ============================================================
# GENERAL AI SUMMARY
# ============================================================

def generate_general_summary(
    question,
    topics=None,
    relationship=False
):
    """
    Generate ONE general AI answer for the user's complete question.
    """
    topics = topics or []
    topic_text = ", ".join(topics) if topics else question

    if relationship:
        focus_rule = f"Explain the combined concept / relationship: {topic_text}."
    else:
        focus_rule = f"Focus on: {topic_text}."

    prompt = f"""You are a general AI assistant.

QUESTION: {question}
{focus_rule}

TASK: Provide exactly 5 concise points that directly answer the question.
RULES:
- Maximum 20 words per point.
- Return exactly 5 numbered points.
- No intro, conclusion, or heading.
"""

    result = call_ollama(prompt, temperature=0.15)

    if not result["success"]:
        return {
            "success": False,
            "message": result["message"],
            "summary": ""
        }

    summary = clean_summary(result["response"])
    return {
        "success": True,
        "summary": summary
    }


# ============================================================
# COMBINED SUMMARY
# ============================================================

def generate_combined_summary(
    question,
    individual_summaries=None
):
    """
    Compatibility function.
    """
    return generate_general_summary(
        question
    )