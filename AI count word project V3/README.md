# DocuMind AI

DocuMind AI is a Flask web application for analyzing multiple project
documents, counting words or phrases, extracting relevant content, comparing
project ideas with a local document repository, and generating AI-assisted
reports.

The browser interface is served from `templates/index.html`. Document
extraction and deterministic matching run locally. AI reports and project
guidance use a locally running Ollama server over HTTP.

## Problem statement

Reviewing a project repository manually makes it difficult to:

- Search several document formats consistently.
- Count a word or phrase without opening every document.
- Identify document passages relevant to a project idea.
- Compare a new project idea with existing repository material.
- Produce a concise technical report from the relevant content.

DocuMind AI provides one local workflow for these tasks while preserving the
original documents in the repository and reporting file-level processing
errors separately.

## Features

- Upload and analyze up to 10 documents in one request.
- Enforce a 100 MB maximum request size.
- Extract text from PDF, DOC, DOCX, XLS, XLSX, and TXT files.
- Count case-insensitive word or phrase occurrences.
- Use whole-word matching for single word searches.
- Use case-insensitive substring matching for phrases and punctuation-containing
  searches.
- Show relevant excerpts and per-document processing status.
- Generate document analysis reports with a local Ollama model.
- Continue processing other files when one file fails.
- Compare a project idea with supported documents already in `uploads`.
- Classify project similarity as high, related, or low.
- Generate project exploration reports for selected categories:
  Key Features, Advantages, Disadvantages, Improvements, Technology Stack,
  System Architecture, and Development Roadmap.
- Generate follow-up guidance when a project comparison has no meaningful
  match.
- Save recent searches in a local SQLite database.
- Reuse a successful project exploration report in the current browser session
  when the project idea and selected categories are unchanged.
- Preserve legacy search and summary endpoints.

## How the system works

### Normal document analysis

1. The browser sends the project idea or search query and uploaded files to
   `/project-analysis`.
2. Flask validates the query, file count, extensions, and request size.
3. Each file is temporarily stored in `uploads`.
4. The document processor dispatcher selects the extractor for the file
   extension.
5. Files are extracted concurrently using up to four workers.
6. Query terms and relevant content are identified.
7. Results are returned to the browser in upload order.
8. Temporary uploaded files are removed after processing.
9. The browser displays counts, excerpts, summaries, and project exploration
   controls.

The legacy `/analyze` endpoint uses the same unified analysis workflow.

### Project comparison and exploration

The project-analysis workflow can compare the submitted idea with supported
documents already present in `uploads`. Similarity is calculated using
normalized concepts, aliases, keywords, and important phrases.

When the user requests project exploration:

1. The browser collects the selected categories and current project idea.
2. The browser sends relevant document text to `/project-exploration`.
3. Flask validates the idea and category list.
4. The server generates an exploration report through Ollama.
5. The browser renders the returned Markdown report.

The frontend keeps one in-memory exploration result for the current page
session. The cache matches both the project idea and the selected categories;
category order does not matter. A changed category selection or a new analysis
causes a new request. The cache is cleared by `resetResults()` and disappears
when the page is refreshed. It is not stored in localStorage, sessionStorage,
IndexedDB, or the database.

### Word and phrase counting

Single word searches use case-insensitive whole-word matching. For example,
`AI` matches `AI` but not `TRAIN`, `CLAIM`, or `MAIN`.

Multi-word phrases and searches containing special punctuation use
case-insensitive substring matching.

## Technologies

- Python
- Flask 3.1.3
- HTML, CSS, and browser JavaScript
- SQLite
- PyMuPDF
- `python-docx`
- pandas
- openpyxl
- xlrd
- olefile
- striprtf
- Ollama HTTP API
- Ollama model `qwen2.5:7b` as configured in `ai_summary.py`

The exact Python packages pinned by the project are listed in
[`requirements.txt`](requirements.txt).

## Project structure

```text
.
├── app.py
├── ai_summary.py
├── database.py
├── project_matcher.py
├── retrieval.py
├── requirements.txt
├── documind.db
├── uploads/
├── document_processors/
│   ├── __init__.py
│   ├── excel_processor.py
│   ├── pdf_processor.py
│   └── word_processor.py
├── templates/
│   └── index.html
├── test_docs/
├── test_project_matcher.py
├── test_suite.py
└── README.md
```

### Main modules

- [`app.py`](app.py): Flask application, upload validation, API routes,
  orchestration, and response formatting.
- [`ai_summary.py`](ai_summary.py): Ollama requests, prompt construction,
  response handling, report generation, and project exploration generation.
- [`document_processors/__init__.py`](document_processors/__init__.py):
  extraction dispatch and word-count logic.
- [`document_processors/pdf_processor.py`](document_processors/pdf_processor.py):
  PDF extraction.
- [`document_processors/word_processor.py`](document_processors/word_processor.py):
  DOC and DOCX extraction.
- [`document_processors/excel_processor.py`](document_processors/excel_processor.py):
  XLS and XLSX extraction.
- [`retrieval.py`](retrieval.py): query terms, topic matching, and relevant
  content extraction.
- [`project_matcher.py`](project_matcher.py): repository scanning, aliases,
  similarity scoring, and project relationship analysis.
- [`database.py`](database.py): SQLite search-history initialization and
  persistence.
- [`templates/index.html`](templates/index.html): complete browser UI and
  frontend workflow.

## Requirements

- Python with support for the pinned dependencies in
  [`requirements.txt`](requirements.txt).
- Ollama for AI-generated reports, project guidance, and project exploration.
- The configured Ollama model: `qwen2.5:7b`.

Document extraction, validation, and deterministic matching can run without a
working Ollama service. AI-dependent operations require Ollama to be running.

## Installation

From the project directory, create and activate a virtual environment:

### Windows PowerShell

```powershell
python -m venv venv
.\venv\Scripts\Activate.ps1
python -m pip install --upgrade pip
python -m pip install -r requirements.txt
```

If PowerShell script activation is restricted, use the virtual environment
interpreter directly:

```powershell
.\venv\Scripts\python.exe app.py
```

Install Ollama separately and make the configured model available:

```powershell
ollama pull qwen2.5:7b
```

## Configuration

The current AI configuration is defined directly in
[`ai_summary.py`](ai_summary.py):

| Setting | Value |
| --- | --- |
| Ollama URL | `http://localhost:11434/api/generate` |
| Ollama model | `qwen2.5:7b` |
| Default document input limit | 3,500 characters |
| Default output limit | 300 tokens |
| Default context size | 1,536 tokens |

The Flask application configuration in [`app.py`](app.py) includes:

| Setting | Value |
| --- | --- |
| Upload directory | `uploads` beside `app.py` |
| Maximum request size | 100 MB |
| Maximum files per analysis | 10 |
| Extraction worker limit | 4 |
| Development server port | 5000 |

No `.env` file or project-specific environment variable is required by the
current source code.

## Running the application

Start Ollama first if AI output is needed, then run Flask:

```powershell
.\venv\Scripts\Activate.ps1
python app.py
```

Open the application at:

```text
http://127.0.0.1:5000
```

The application uses Flask's development server. The current source enables
debug mode, so it should not be exposed directly to the public internet.

## Using the application

1. Open the web interface.
2. Select or drag supported files into the upload area.
3. Enter a word, phrase, question, or project problem statement.
4. Select **Analyze Documents**.
5. Review the per-document counts, excerpts, statuses, and analysis reports.
6. Use **Explore This Project** to select one or more exploration categories.
7. Select **Next** to generate the exploration report.
8. Use **Back to Analysis Results** to return to the normal results view.
9. If the project comparison has no meaningful match, provide additional
   information to request follow-up guidance.
10. Use the recent-search controls to reuse a previous search query.

## Supported file formats

| Extension | Extraction behavior |
| --- | --- |
| `.pdf` | Extracted with the PDF processor based on PyMuPDF |
| `.docx` | Extracted with `python-docx` |
| `.doc` | Processed with the legacy Word extraction fallbacks |
| `.xlsx` | Read with pandas and openpyxl |
| `.xls` | Read with pandas and xlrd |
| `.txt` | Read as UTF-8; invalid bytes are ignored |

Scanned or image-only documents may produce little or no text because OCR is
not implemented.

## API reference

The JSON endpoints return a `success` field where applicable. Upload
endpoints use multipart form data unless noted otherwise.

### `GET /`

Returns the browser interface.

### `POST /project-analysis`

Runs the main browser analysis workflow.

Accepted project idea fields:

- `project_idea`
- `search_word`
- `word`

Accepted file fields:

- `files[]`
- `files`
- `file` for a single file

If no files are supplied, supported repository files in `uploads` may be used.
The response contains document results, processing counts, relevant content,
and project comparison data when applicable.

### `POST /project-exploration`

Generates an exploration report.

JSON request fields:

```json
{
  "project_idea": "AI document analyzer for enterprise repositories",
  "categories": ["Key Features", "Advantages"],
  "document_text": "Relevant extracted document content"
}
```

`project_idea` and at least one category are required. If `document_text` is
empty, the server gathers supported repository documents from `uploads`.

Successful responses include:

- `success`
- `project_idea`
- `categories`
- `exploration`
- `message`

### `POST /project-follow-up`

Generates guidance after a no-match project result.

Required fields:

- `project_idea`
- `additional_information` or `more_information`

The request may be JSON or form data.

### `POST /analyze`

Runs the unified document analysis workflow with compatibility fields:

- Query: `search_word`, `word`, or `project_idea`
- Files: `files[]`, `files`, or `file`
- Optional `repository=true` to use repository files when no upload is given

### `POST /search`

Legacy-compatible search endpoint.

For a single file, send `file` and `search_word` or `word`. The response
includes `found`, `count`, and `message`. Multiple-file requests use the
unified analysis workflow.

### `POST /summarize`

Generates a summary from submitted text.

Required field:

- `text`

Optional compatibility field:

- `search_word` or `word`

### `POST /project-match`

Compares a project idea with repository documents in `uploads`.

Accepted fields:

- `project_idea`
- `idea`

The response includes the match list, `has_matches`, assistant output, and
whether more information is needed.

### `GET /search-history`

Returns up to 10 recent search records from the local SQLite database.

## Database and local storage

The application uses SQLite through [`database.py`](database.py).

- Database file: `documind.db`
- Table: `search_history`
- Stored fields: search ID, query text, and timestamp
- Duplicate queries are removed before a new matching query is inserted
- The table is created automatically when the Flask application starts

The `uploads` directory serves two purposes:

1. Temporary storage for files submitted during normal analysis.
2. Local repository storage for project matching and exploration when files are
   already present there.

The browser exploration cache is separate from SQLite and exists only in
frontend memory for the current page session.

## Error and edge-case behavior

- Empty queries are rejected.
- Empty category selections are rejected by both the browser and exploration
  API.
- Unsupported file extensions are rejected or reported per file.
- Requests larger than 100 MB return HTTP `413`.
- More than 10 analysis files are rejected.
- A file that cannot be read is reported as a per-file processing failure; other
  files continue.
- If no meaningful project match is found, the project assistant is not called
  for that comparison; the browser can request follow-up guidance separately.
- If Ollama is unavailable or returns an error, AI-dependent operations report
  an error. Workflows that support deterministic fallback can still return a
  non-AI report.
- AI input is truncated to configured limits before it is sent to Ollama.
- The project exploration cache is cleared when a new analysis calls
  `resetResults()` and is lost on browser refresh.

## Testing

Run the end-to-end extraction and API checks:

```powershell
.\venv\Scripts\Activate.ps1
python test_suite.py
```

Run the project matcher example:

```powershell
python test_project_matcher.py
```

The test suite creates or uses sample files in `test_docs`, checks mixed-format
processing and per-file failures, verifies word counting, and exercises the
legacy search workflow. AI-dependent checks may require Ollama and the
configured model.

## Limitations

- OCR for scanned PDFs and images is not implemented.
- Similarity matching is deterministic concept and phrase matching, not
  embedding-based semantic search.
- AI quality and response time depend on local hardware and the Ollama model.
- The current Flask server is a development server and is not a production
  deployment configuration.
- Search history is stored locally and is not user-scoped.
- The exploration cache is session-only and is not shared across browser tabs,
  page refreshes, users, or server processes.

## Future improvements

Potential improvements consistent with the current architecture include:

- Add OCR support for scanned documents.
- Add automated coverage for every API response schema and AI fallback path.
- Add authentication and user-scoped history.
- Add report export and persistent project history.
- Evaluate embedding-based retrieval alongside deterministic matching.
- Provide a production WSGI deployment configuration and structured logging.

## Project information

Project name: **DocuMind AI**  
Application type: Local Flask web application  
Primary purpose: Multi-format document analysis and project intelligence

The source code does not identify an individual author, organization, license,
or production deployment target. Those details should be added only when they
are confirmed by the project owner.
