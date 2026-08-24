# AI File Manager

Windows local-first document AI with semantic search, AI reranking, document chat, and safe renaming.

## One-click setup

Double-click `start.bat`. It installs/checks Python 3.13, Ollama, downloads the default models, creates the Python environment, installs dependencies, verifies Python syntax, starts the server, and opens the browser.

Default AI models:
- Chat/vision: `qwen3-vl:8b`
- Embeddings: `qwen3-embedding:0.6b`

## Search architecture

Search is semantic-first. Exact keyword matching is only a small additional signal. Semantic candidates are filtered by relative relevance and then reranked by the local chat model. Low-relevance candidates are discarded rather than shown merely because a generic keyword matched.

Embeddings are stored with the embedding-model name so incompatible vector sets are never silently mixed.

## Supported files

PDF, DOCX, XLSX/XLSM, PPTX, TXT, MD, CSV, JSON, XML, LOG, and common images. Image OCR is attempted when Tesseract is available.

## Safety

Indexing never renames files. Rename is an explicit action with Windows filename validation and collision checks.
