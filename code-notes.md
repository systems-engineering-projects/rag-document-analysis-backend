# Verbiage — Code Notes & Prompts

Implementation decisions and prompts for building the app. Use this when implementing ingest, extraction, or RAG.

---

## Data sources: PDF and .docx only

**Decision:** Ingest report text from **PDF** and **.docx** only. Do not support **.pages** for the pipeline.

**Rationale:**

- We have a PDF (or .docx) for every report; .pages is redundant for ingestion.
- **PDF / .docx** have mature Python libraries (pypdf, PyMuPDF, python-docx); **.pages** requires unzipping and parsing Apple’s XML with no standard library and possible format changes.
- One pipeline (PDF + .docx) is simpler to build and maintain.

**Libraries:**

- **PDF:** `pypdf` or `PyMuPDF` (fitz) for text extraction. For scanned/image PDFs, add `pdf2image` + `pytesseract` (OCR) later if needed.
- **.docx:** `python-docx` — extract paragraphs/runs as plain text.

**Implementation prompt (for ingest-from-files):**

- Accept a path or list of paths (PDF and/or .docx).
- Per file: extract full text (and optionally title/source from filename or metadata).
- Call existing POST /ingest with that `text` (and metadata) so chunk → embed → store runs as already designed.

**PDF: data only, no structure.** We need the data from the PDF, not the layout or structure. Current pipeline: extract plain text (all pages), chunk, embed, store. No need to preserve sections, tables, or formatting. **Later:** tools to grab specially formatted areas (e.g. tables, defined regions) and image extraction/OCR can be added when needed.

---

## Models (local, for client-name privacy)

- **This phase:** **Llama 3.1 8B** via Ollama for POST /ask (text/RAG). Run with `ollama run llama3.1:8b`; point LLM client at `http://localhost:11434`.
- **Next phase:** **LLaVA** via Ollama for “look at this job’s images and see what is wrong and write report text.” Run with `ollama run llava` (or `llava:13b` for better quality). Same Ollama base URL; different model name and request shape (vision API accepts images).

---

## Placeholder for future notes

- Chunking strategy for reports (by section? by chars?)
- Verbiage-specific system prompt for POST /ask
- Any env vars or config for embed/LLM (see Models above)
