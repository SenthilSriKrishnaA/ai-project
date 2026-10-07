
"""
ai_summary.py
-------------
AI-powered document summarization using local Ollama.
"""

import ollama

OLLAMA_MODEL = "llama3.2:3b"


def clean_summary(text: str) -> str:
    """
    Clean the AI response and return exactly 5 points.
    """

    lines = []

    for line in text.splitlines():

        line = line.strip()

        # Remove Markdown characters
        line = line.replace("*", "")
        line = line.replace("#", "")
        line = line.replace("\\", "")

        # Remove existing numbering
        if len(line) > 2 and line[0].isdigit():
            if line[1] in ".):":
                line = line[2:].strip()

        # Ignore empty lines
        if not line:
            continue

        # Ignore unwanted introductory text
        unwanted = [
            "here is",
            "complete book",
            "complete document",
            "book content",
            "document content",
            "summary:",
            "key points:"
        ]

        if any(word in line.lower() for word in unwanted):
            continue

        lines.append(line)

    # Take only first 5 useful lines
    lines = lines[:5]

    # Create clean numbered output
    result = []

    for i, line in enumerate(lines, 1):
        result.append(f"{i}. {line}")

    return "\n".join(result)


def prepare_document_context(text: str, max_chars: int = 10000) -> str:
    """
    Safely prepare document text for the AI.
    For large documents, extract key representative sections (head, middle, tail)
    to prevent exceeding LLM context and avoid timeout issues.
    """
    cleaned = text.strip()
    if len(cleaned) <= max_chars:
        return cleaned

    head_size = int(max_chars * 0.50)
    tail_size = int(max_chars * 0.35)
    mid_size = max_chars - head_size - tail_size

    mid_start = (len(cleaned) // 2) - (mid_size // 2)

    head = cleaned[:head_size]
    mid = cleaned[mid_start:mid_start + mid_size]
    tail = cleaned[-tail_size:]

    return (
        f"{head}\n\n"
        f"[... Content omitted ({len(cleaned) - max_chars} characters) for summary brevity ...]\n\n"
        f"{mid}\n\n"
        f"[...]\n\n"
        f"{tail}"
    )


def generate_ai_summary(text: str) -> dict:
    """
    Generate a short 5-point summary using local Ollama.
    """

    if not text or not text.strip():
        return {
            "success": False,
            "message": "Please upload a document first."
        }

    # Safe handling for large documents
    cleaned_text = prepare_document_context(text, max_chars=6000)

    prompt = f"""
You are a document summarizer.

Read the document below and identify the FIVE most important ideas.

IMPORTANT:
Return ONLY FIVE SHORT SENTENCES.

Do NOT return:
- the original document
- paragraphs
- introduction
- explanation
- headings
- table of contents
- index
- glossary
- references
- author information
- book metadata

Each sentence must:
- describe an important idea from the document
- be short and clear
- contain maximum 20 words
- contain no Markdown
- contain no numbering
- contain no bullet symbols

Your response must look EXACTLY like this:

Sentence about important idea
Sentence about important idea
Sentence about important idea
Sentence about important idea
Sentence about important idea

DOCUMENT:
{cleaned_text}
"""

    try:

        response = ollama.chat(
            model=OLLAMA_MODEL,
            messages=[
                {
                    "role": "user",
                    "content": prompt
                }
            ],
            options={
                "temperature": 0.0,
                "num_predict": 150
            }
        )

        raw_summary = response["message"]["content"].strip()

        if not raw_summary:
            return {
                "success": False,
                "message": "Unable to generate summary."
            }

        summary = clean_summary(raw_summary)

        # Make sure we received at least some valid summary points
        lines = summary.splitlines()
        if not lines:
            return {
                "success": False,
                "message": "AI could not generate a proper summary. Please try again."
            }

        # If slightly fewer than 5 points produced by the LLM, pad or return what we have cleanly
        return {
            "success": True,
            "summary": summary
        }

    except Exception as error:

        print(f"[Ollama AI Summary Error]: {error}")

        return {
            "success": False,
            "message": f"Local AI is not available or encountered an issue: {str(error)}"
        }


# Conceptual function alias requested by specification
def generate_summary(document_text: str) -> dict:
    """
    Alias for generate_ai_summary(text) for one document's text at a time.
    """
    return generate_ai_summary(document_text)
