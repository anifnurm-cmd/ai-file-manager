# AI File Manager

A local-first Windows document assistant that can read mixed files, remember their contents, search semantically, answer questions, and safely rename files.

## Rebuilt architecture

- PDF, DOCX, XLSX/XLSM, PPTX, TXT/CSV/JSON/XML/LOG and common images.
- SQLite + FTS5 keyword index.
- Optional Ollama embeddings for semantic retrieval.
- Hybrid keyword + semantic search instead of relying on the whole question matching every keyword.
- Optional Ollama metadata extraction and natural-language answers.
- Explicit rename only; no automatic destructive renaming during indexing.
- OCR is optional. The application remains usable when Windows Tesseract is absent.
- No paid API is required for the core indexing and keyword search workflow.

## Windows

Python 3.13 is the primary target.

1. Download/clone this repository.
2. Delete any old `.venv` created by an earlier release.
3. Double-click `start.bat`.
4. The launcher creates a Python 3.13 virtual environment, installs dependencies, checks them, compiles the app, starts the server, and opens `http://127.0.0.1:8787`.

If startup fails, keep the server window open and use the displayed error.

## Optional Ollama AI

Install Ollama locally and run a chat model plus an embedding model. Suggested defaults:

```text
OLLAMA_URL=http://127.0.0.1:11434
OLLAMA_CHAT_MODEL=qwen3:8b
OLLAMA_EMBED_MODEL=nomic-embed-text
```

Without Ollama, the app still provides local document extraction and keyword search. With Ollama, semantic retrieval, AI metadata and file-grounded answers are enabled.

## Optional OCR

Install Windows Tesseract OCR and ensure `tesseract.exe` is available on PATH. Image OCR will then be used automatically. OCR failure does not prevent other document types from being indexed.

## Test

```powershell
py -3.13 -m venv .venv
.venv\Scripts\python.exe -m pip install -r requirements.txt
.venv\Scripts\python.exe -m pytest -q
```

The test suite exercises the complete scan → parse → index → keyword search → AI retrieval mock → rename pipeline.
