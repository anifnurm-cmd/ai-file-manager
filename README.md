# AI File Manager

A local-first AI assistant for ordinary Windows folders.

## Current release

- Indexes mixed PDFs, DOCX, XLSX/XLSM, PPTX, text/CSV/JSON/XML/log files, and common images.
- Extracts searchable content into local SQLite + FTS5.
- Generates deterministic local title/type/summary metadata even without an AI service.
- Optional Ollama integration for richer metadata and natural-language answers.
- Search by document content, title, summary, and type.
- Safe explicit file renaming with Windows filename validation and collision checks.
- No cloud service is required for the core indexing/search workflow.

## Windows quick start

1. Install Python 3.12 or later.
2. Double-click `start.bat`.
3. Open `http://127.0.0.1:8787` in Chrome/Edge.
4. Enter a folder such as `C:\Users\YourName\Documents` and click **Scan**.

The launcher creates a virtual environment and installs the Python dependencies automatically.

### Optional local AI

Install Ollama and run a local model, for example `qwen3:8b`. Keep Ollama running on its default address. The app will detect it automatically.

Environment variables:

```text
OLLAMA_URL=http://127.0.0.1:11434
OLLAMA_MODEL=qwen3:8b
PORT=8787
```

### Optional OCR

Install Tesseract OCR on Windows and ensure `tesseract.exe` is on PATH. Image files can then be indexed through OCR.

## Important safety behavior

The first release does **not** auto-rename files during indexing. Rename is an explicit action from the UI and rejects invalid Windows filenames and existing destination names.

## Architecture

The application is intentionally compact: `app.py` contains the API, document parsers, local SQLite/FTS index, optional Ollama client, and browser UI. This keeps installation and troubleshooting simple on Windows.
