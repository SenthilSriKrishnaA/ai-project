# Document Search and AI Word Counter

An intelligent desktop web tool designed to search, count word occurrences, and generate automated executive summaries across various document types.

---

## Overview

Document Search and AI Word Counter provides a simple, modern interface to inspect document contents quickly. Users can upload various everyday document formats, count occurrences of specific keywords or phrases in real time, and request a concise five-point summary powered by local artificial intelligence.

All processing occurs directly on your local system, ensuring complete data privacy with no external cloud data transmission required.

---

## Key Features

### 1. Document Word and Phrase Search
- Instantly searches through text within uploaded files.
- Accurately counts every occurrence of a specified search query.
- Performs case-insensitive matching so variations in capitalization are automatically included.
- Displays immediate visual feedback indicating whether the term was located and the exact count.

### 2. Five-Point AI Document Summary
- Extracts the core ideas and key takeaways from long documents.
- Produces exactly five clear, concise, numbered sentences.
- Eliminates unnecessary introductions, author notes, glossaries, table of contents, and clutter.
- Runs entirely on local artificial intelligence models for speed and confidentiality.

### 3. Broad Format Compatibility
- PDF Documents
- Microsoft Word Documents
- Microsoft Excel Workbooks and Spreadsheets
- Plain Text Files

### 4. User-Centric Design
- Clean and modern layout with an intuitive user interface.
- Drag-and-drop document upload area.
- Instant file selection preview with an option to remove or switch files with a single click.
- Visual status indicators for searches, processing progress, and results.

---

## Supported File Formats

- **PDF (.pdf)**: Extracts readable text across all pages in the document.
- **Word (.docx)**: Reads full body text and paragraphs from standard Microsoft Word files.
- **Excel (.xlsx, .xls)**: Processes tabular information across sheets.
- **Text (.txt)**: Reads standard plain text files directly.

---

## User Guide

### Searching for Words
1. **Upload a File**: Drag your document onto the designated upload box or click to select a file from your file explorer.
2. **Review File Selection**: Confirm that your file name is shown in the file banner.
3. **Enter Keyword**: Type the target word or phrase in the search box.
4. **Click Search**: Select the search button to initiate the count.
5. **View Results**: The application will display an alert highlighting whether the phrase was found and the exact number of occurrences.

### Generating an AI Summary
1. **Ensure File is Loaded**: Make sure your target document is uploaded.
2. **Request Summary**: Click the Generate AI Summary button.
3. **Wait for Analysis**: The local AI engine reads and digests the document contents.
4. **Read Key Points**: A clean, five-point summary of the most essential ideas appears directly on screen.

### Clearing and Switching Documents
- Click the cross icon next to the active file name to clear the current file and reset the search results.
- Select or drag a new file at any time to begin another analysis.

---

## How the AI Summarizer Works

The built-in document summarizer uses a locally hosted artificial intelligence language model. When an AI summary is requested:

1. The application extracts the full text from the uploaded document.
2. The extracted text is processed through a structured instruction set designed to identify high-impact concepts.
3. The AI filters out metadata, headers, acknowledgments, and conversational filler.
4. The output is standardized into five distinct, high-level summary points.
5. The processed summary is delivered back to your screen within seconds.

---

## Privacy and Security

- **Local Execution**: Document text stays entirely on your computer during search and summarization.
- **No Cloud Uploads**: The AI system communicates with a local language model runner without transmitting data over the internet.
- **Temporary In-Memory Processing**: Uploaded documents are read in memory for processing and are not stored permanently in remote databases.

---

## Troubleshooting and Tips

- **File Contains No Text**: If you upload a scanned image inside a PDF, the text reader may not detect readable characters. Ensure documents have selectable text.
- **AI Summary Waiting Time**: Summarization duration depends on the length of the document and your computer hardware. Larger documents take a few extra moments.
- **Local AI Service**: Ensure your local AI background service is started before requesting an AI summary. If the service is stopped, a helpful warning prompt will notify you.
- **Multiple Occurrences**: The search tool counts exact matching strings. For example, searching for a partial term will also match words containing that segment.
