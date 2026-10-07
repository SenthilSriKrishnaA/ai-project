# AI-Powered Multi-Format Document Analyzer

## Project Overview

**AI-Powered Multi-Format Document Analyzer** is an intelligent, high-performance web application that enables users to upload multiple documents simultaneously across diverse formats (PDF, Word, Excel, and Text). 

For every uploaded document, the application performs independent text extraction, searches for a user-specified word or phrase using accurate whole-word matching, and generates an individual 5-point executive summary using a local Large Language Model (Ollama with `llama3.2:3b`).

Documents are **never combined or merged**. Each document maintains its own dedicated extraction lifecycle, word frequency count, AI summary, and processing status.

---

## Features

- **Single & Multi-Document Upload**: Upload a single document or multiple documents simultaneously with drag-and-drop support.
- **Independent Document Processing**: Every document is processed in strict isolation.
- **Comprehensive Format Support**:
  - **PDF Documents**: `.pdf`
  - **Microsoft Word**: `.docx` and legacy `.doc` (Word 97–2003 binary format)
  - **Microsoft Excel**: `.xlsx` and legacy `.xls`
  - **Plain Text**: `.txt`
- **Smart Whole-Word Counting**: Uses boundary-aware matching (e.g., searching for `"AI"` matches `"AI"` but correctly ignores `"TRAIN"`, `"CLAIM"`, or `"MAIN"`).
- **Individual AI Summaries**: Generates independent, clean 5-point summaries for each document using local Ollama.
- **Real-Time Live Progress Tracker**: Displays real-time progress for each document (Waiting ○, Processing ⏳, Completed ✓, Failed ❌).
- **Fault-Tolerant Error Handling**: If one document fails (e.g., corrupted file or unsupported format), all other documents continue processing without interruption.
- **Backward Compatibility**: Fully preserves legacy single-file API routes (`/search` and `/summarize`) and extraction functions.
- **Safe Temporary Storage**: Uploaded files are safely handled using secure temporary files and automatically cleaned up immediately after processing.

---

## How It Works

```
                        User
                         │
           Upload Multiple Documents & Enter Word
                         │
             Validate Files & Search Word
                         │
       ┌─────────────────┼─────────────────┐
       ▼                 ▼                 ▼
   Document 1        Document 2        Document 3
   (.pdf)            (.docx)           (.xlsx)
       │                 │                 │
  Extract Text      Extract Text      Extract Text
  (Independent)     (Independent)     (Independent)
       │                 │                 │
  Count Word        Count Word        Count Word
  (Independent)     (Independent)     (Independent)
       │                 │                 │
  Generate AI       Generate AI       Generate AI
    Summary           Summary           Summary
       │                 │                 │
       └─────────────────┼─────────────────┘
                         │
            Assemble Individual Results
                         │
             Display Independent Cards
```

1. **Upload multiple documents**: User selects or drags files into the upload area.
2. **Extract text independently**: The backend dispatcher identifies each file's extension and calls the corresponding format processor.
3. **Search word independently**: The search word is evaluated against each document's extracted text.
4. **Count word independently**: Whole-word boundaries calculate the isolated occurrence count for that document.
5. **Generate individual AI summary**: Only that document's text is passed to Ollama for an isolated 5-point summary.
6. **Display individual results**: The frontend renders an independent result card for each document showing filename, format badge, word occurrence count, AI summary, and status.

---

## Supported Formats

| Format | Extension | Extractor Engine |
| :--- | :--- | :--- |
| **Portable Document Format** | `.pdf` | `pypdf` + `PyMuPDF` |
| **Word Document (OpenXML)** | `.docx` | `python-docx` |
| **Word Document (Legacy 97-2003)** | `.doc` | `PyMuPDF` + `olefile` / `striprtf` |
| **Excel Workbook (OpenXML)** | `.xlsx` | `pandas` + `openpyxl` |
| **Excel Workbook (Legacy 97-2003)** | `.xls` | `pandas` + `xlrd` |
| **Plain Text** | `.txt` | UTF-8 Stream Reader |

---

## Project Structure

The following represents the actual file and folder structure of the project:

```text
AI count words project V1/
│
├── app.py                          # Main Flask application and API endpoints (/analyze, /search, /summarize)
├── ai_summary.py                   # Ollama AI summarization module with large-text chunking
├── requirements.txt                # Locked dependencies
│
├── templates/                      # Frontend HTML templates
│   └── index.html                  # Multi-document UI with drag-and-drop, progress, & result cards
│
├── document_processors/            # [NEW] Modular document extraction engines
│   ├── __init__.py                 # [NEW] Central extract_text dispatcher & count_word_occurrences
│   ├── pdf_processor.py            # [NEW] Dedicated PDF text extractor
│   ├── word_processor.py           # [NEW] Dedicated Word (.docx and legacy .doc) text extractor
│   └── excel_processor.py          # [NEW] Dedicated Excel (.xlsx and legacy .xls) text extractor
│
├── uploads/                        # [NEW] Secure temporary processing directory
│   └── .gitkeep                    # [NEW] Directory placeholder (auto-cleaned after uploads)
│
├── test_docs/                      # Sample test files generated for automated validation
│   ├── document1.pdf
│   ├── document2.pdf
│   ├── report.docx
│   ├── data.xlsx
│   ├── legacy_note.doc
│   └── corrupted.pdf
│
├── test_suite.py                   # Automated end-to-end test suite
├── venv/                           # Python virtual environment
└── README.md                       # [NEW] Comprehensive documentation
```

### Files Added and Upgraded:
- **`document_processors/`** (NEW): Created modular, reusable text extractors for PDF, Word (.doc & .docx), and Excel (.xls & .xlsx).
- **`uploads/`** (NEW): Safe folder for temporary file handling during stream parsing.
- **`app.py`** (MODIFIED): Added `/analyze` multi-file endpoint and preserved legacy single-file `/search` and `/summarize` routes.
- **`ai_summary.py`** (MODIFIED): Added `generate_summary(document_text)` alias and context protection for large documents.
- **`templates/index.html`** (MODIFIED): Added multi-file selection, queue management, live progress tracker, and individual result cards.
- **`requirements.txt`** (MODIFIED): Explicitly locked `ollama`, `pymupdf`, `olefile`, and `striprtf`.
- **`README.md`** (NEW): Full project documentation.

---

## Installation

### 1. Prerequisites
- **Python 3.10+** (Tested on Python 3.11)
- **Ollama**: Download and install from [ollama.com](https://ollama.com)

Pull the local LLM model:
```bash
ollama pull llama3.2:3b
```

### 2. Setup Virtual Environment (Windows PowerShell)

Open PowerShell in the project root directory:

```powershell
# Create virtual environment
python -m venv venv

# Activate virtual environment
.\venv\Scripts\Activate.ps1

# Upgrade pip
python -m pip install --upgrade pip

# Install dependencies
pip install -r requirements.txt
```

---

## Environment Variables

By default, the application runs with local Ollama (`llama3.2:3b`) and requires **no external cloud API keys**.

Optional environment variables:

| Variable | Description | Default |
| :--- | :--- | :--- |
| `OLLAMA_HOST` | Custom Ollama host/port if running on remote server | `http://127.0.0.1:11434` |
| `FLASK_PORT` | Port for Flask web server | `5000` |
| `GEMINI_API_KEY` | Optional fallback if configuring Gemini Cloud AI | *(None)* |

---

## Running the Application

### 1. Ensure Ollama is Running
Make sure the Ollama service is active:
```powershell
ollama list
```
*(Verify `llama3.2:3b` appears in the list).*

### 2. Start the Backend Web Server
With the virtual environment activated:
```powershell
python app.py
```

Output:
```text
 * Serving Flask app 'app'
 * Debug mode: on
 * Running on http://127.0.0.1:5000
```

### 3. Access the Application
Open your web browser and navigate to:
```
http://127.0.0.1:5000
```

---

## Usage

1. **Open the Website**: Navigate to `http://127.0.0.1:5000`.
2. **Upload Documents**:
   - Drag and drop one or multiple files into the dropzone, or click to browse.
   - You can upload PDFs, DOCX, DOC, XLSX, XLS, and TXT files together.
   - Selected files will display in the queue with file type badges and sizes.
   - Click the **✕** button on any file item to remove it from the queue.
3. **Enter Search Word**:
   - Type a search word or phrase in the search box (e.g., `AI`).
4. **Click "Analyze Documents"**:
   - Watch the live progress indicator track each document in real time:
     - `✓ document1.pdf — Completed`
     - `⏳ report.docx — Processing`
     - `○ data.xlsx — Waiting`
5. **View Independent Results**:
   - Each document displays its own card containing:
     - Document icon, name, and format badge.
     - Search word occurrence count (using whole-word matching).
     - AI 5-point executive summary generated exclusively from that document.
     - Processing status badge.

---

## Example Execution

### Search Word: `AI`

**Document 1 (`research_paper.pdf`)**:
- **Format**: PDF
- **Word**: AI
- **Occurrences**: 5
- **AI Summary**:
  1. AI is transforming medical diagnostic procedures across hospitals.
  2. Neural networks detect anomalies in imaging data with high accuracy.
  3. Patient outcome predictions have improved significantly through AI algorithms.
  4. Clinical integration requires adherence to strict patient privacy standards.
  5. Continued validation trials will ensure safe deployment in clinical settings.
- **Status**: ✓ Successfully processed

**Document 2 (`quarterly_report.docx`)**:
- **Format**: DOCX
- **Word**: AI
- **Occurrences**: 3
- **AI Summary**:
  1. Enterprise adoption of automated workflow solutions increased this quarter.
  2. Cloud infrastructure investment grew to accommodate computational demands.
  3. Operations efficiency improved across software engineering departments.
  4. Cost optimizations balanced hardware procurement expenditures.
  5. Next quarter goals focus on scaling user capacity and reliability.
- **Status**: ✓ Successfully processed

**Document 3 (`budget_data.xlsx`)**:
- **Format**: XLSX
- **Word**: AI
- **Occurrences**: 2
- **AI Summary**:
  1. Department budgets allocate substantial resources to research initiatives.
  2. Software licensing accounts for the largest fixed expense category.
  3. Machine learning infrastructure expenditures rose by fifteen percent.
  4. Team training and talent acquisition showed steady quarterly allocation.
  5. Remaining budget reserves will fund upcoming fourth-quarter tooling upgrades.
- **Status**: ✓ Successfully processed

---

## Troubleshooting

| Problem | Cause | Solution |
| :--- | :--- | :--- |
| **"Local AI is not available"** | Ollama is not running or model not pulled | Run `ollama serve` in a terminal and ensure `ollama pull llama3.2:3b` has completed. |
| **"Address already in use" (Port 5000)** | Another Python/Flask process is running on port 5000 | In PowerShell: `Get-Process python \| Stop-Process -Force` or specify another port in `app.py`. |
| **"Unsupported file format"** | An unsupported extension was uploaded (e.g. `.exe`, `.zip`) | Upload only supported documents: `.pdf`, `.docx`, `.doc`, `.xlsx`, `.xls`, `.txt`. |
| **"Document contains no readable text"** | Empty document or image-only scanned document | Ensure the document contains text content or selectable text. |
| **"Unable to extract text from .doc"** | Corrupted or non-standard legacy Word file | The system uses `PyMuPDF` and `olefile`/`striprtf` fallbacks; verify the file opens in Word/WordPad. |
| **Missing Python package** | Package not installed in virtual environment | Run `pip install -r requirements.txt` within the active venv. |

---

## Future Improvements

- **Export Results**: Export summaries and occurrence counts to CSV, JSON, or downloadable PDF reports.
- **Document History & Database**: Store previous analysis sessions in SQLite or PostgreSQL.
- **Interactive Document Chat**: Ask follow-up questions about individual documents directly.
- **OCR Support**: Add Tesseract OCR for scanned PDF images and photo documents.
- **User Authentication**: Secure multi-tenant user accounts with personal document libraries.
