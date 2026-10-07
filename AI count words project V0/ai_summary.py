
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


def generate_ai_summary(text: str) -> dict:
    """
    Generate a short 5-point summary using local Ollama.
    """

    if not text or not text.strip():
        return {
            "success": False,
            "message": "Please upload a document first."
        }

    cleaned_text = text.strip()

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

        # Make sure we actually received 5 points
        if len(summary.splitlines()) != 5:
            return {
                "success": False,
                "message": "AI could not generate a proper 5-point summary. Please try again."
            }

        return {
            "success": True,
            "summary": summary
        }

    except Exception as error:

        print(f"[Ollama AI Summary Error]: {error}")

        return {
            "success": False,
            "message": "Local AI is not available. Please make sure Ollama is running."
        }
