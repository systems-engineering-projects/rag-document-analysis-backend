# Verbiage

RAG-backed report verbiage for storm damage reports. Ingest documents, then ask questions and get overview and detailed copy suggested from similar cases. Built with **FastAPI**, **Postgres + pgvector**, and **OpenAI** (or **Ollama** when `OPENAI_API_KEY` is not set).

*From field notes to finished copy.*

---

## What it does

- **Ingest** — Store report text and metadata. Chunk, embed (OpenAI or Ollama), and index in Postgres with pgvector.
- **List documents** — See what’s ingested: doc_id, title, source, chunk count, and a short snippet.
- **Ask** — Describe the case (symptom, damage type, etc.). The app retrieves similar chunks (vector similarity in Postgres), then uses the LLM to suggest **overview** and **detailed image** verbiage.

When `OPENAI_API_KEY` is set, embeddings and the LLM use OpenAI by default. Optional: set `EMBED_FALLBACK_TO_LOCAL` and/or `LLM_FALLBACK_TO_LOCAL` to use Ollama when OpenAI is unavailable. Without the key, the app uses Ollama only.

Optional: ingest from **Google Drive** (read-only OAuth), and a simple **web UI** (tabs for Ingest / Ask, documents drawer). You can **upload a PDF** or paste text to ingest.

---

## Google Drive and Phase X

- **Current:** Google Drive ingest is available for **Google Docs** only. Use OAuth (`/auth/google`) then **POST /ingest/google-drive** with optional `folder_id` (ingest all Docs in that folder) or `file_ids`. See [setup_and_testing.md](setup_and_testing.md).
- **Phase X (later):** Possible extensions: ingest **PDFs and other files from Drive**, or "watch a folder" / auto-sync when new files appear.

---

## Why it’s relevant for AI deployment

- **RAG pipeline in production shape:** embedding service (OpenAI or Ollama) + vector DB (Postgres/pgvector) + LLM (OpenAI or Ollama). Default is OpenAI when `OPENAI_API_KEY` is set; optional fallback to local Ollama.
- **Config-driven:** Database URL, OpenAI API key, embedding/LLM URLs, timeouts, and rate limits come from environment variables—no hardcoded secrets; ready for 12-factor deployment.
- **Stateless API with connection pooling:** Postgres pool per process; endpoints acquire/return a connection per request. Fits horizontal scaling behind a load balancer.
- **Local or cloud:** Use OpenAI for speed and quality, or leave the key unset for Ollama-only (local) mode.

---

## Tech stack

| Layer        | Choice                          |
|-------------|----------------------------------|
| API         | FastAPI, Pydantic                |
| Database    | Postgres + pgvector (vector similarity in-DB) |
| Embeddings  | OpenAI `text-embedding-3-small` (768 dim) or Ollama `nomic-embed-text` |
| LLM         | OpenAI (e.g. `gpt-4o-mini`) or Ollama `llama3.1:8b` |
| Optional    | Google Drive OAuth for ingest; Ollama fallback when OpenAI fails |

---

## Quick start

**Prerequisites:** Python 3.9+, Postgres with pgvector (or [Supabase](https://supabase.com)). For OpenAI: set `OPENAI_API_KEY` in `.env`. For Ollama-only: install [Ollama](https://ollama.ai) and leave the key unset.

```bash
cd verbiage
python3 -m venv .venv
source .venv/bin/activate   # Windows: .venv\Scripts\activate
pip install -r requirements.txt
cp .env.example .env
# Edit .env: set DATABASE_URL (required) and OPENAI_API_KEY for OpenAI; or leave key unset for Ollama-only
uvicorn app.main:app --reload
```

Open **http://localhost:8000/** for the web UI. Full setup (Postgres/Supabase, OpenAI or Ollama, env vars): see **[setup.md](setup.md)**.

---

## API summary

| Method | Path | Description |
|--------|------|-------------|
| GET | `/health` | Health check |
| POST | `/ingest` | Ingest text (body: `text`, optional `doc_id`, `title`, `source`, `chunking_options`) |
| POST | `/ingest/file` | Ingest PDF file (multipart: `file`, optional `doc_id`, `title`, `source`, `chunk_size`, `chunk_overlap`) |
| GET | `/documents` | List ingested documents |
| POST | `/ask` | RAG query (body: `question`, optional `top_k`, `doc_id`) |
| POST | `/ingest/google-drive` | Ingest Google Docs (body: optional `folder_id`, `file_ids`) |
| GET | `/auth/google` | Start Google OAuth; callback at `/auth/google/callback` |

---

## Logging

App logs (including LLM rate-limit / 429 events) are written to a rotating file so they don’t grow without bound:

- **Path:** `verbiage/logs/verbiage.log` (relative to the project root; when you run from inside `verbiage/`, the file is `logs/verbiage.log`).
- **Rotation:** Max 500 KB per file, up to 3 backup files (`verbiage.log.1`, `verbiage.log.2`, `verbiage.log.3`).
- At startup the server logs the exact path, e.g. `App log file: .../verbiage/logs/verbiage.log`.

---

## Docs

- **[setup.md](setup.md)** — Environment, Postgres, Ollama, install and run, troubleshooting.
- **[supabase_migration.md](supabase_migration.md)** — Schema and migration for Supabase/Postgres.
- **[setup_and_testing.md](setup_and_testing.md)** — Detailed testing, curl examples, web UI, Google Drive.
- **[overview.md](overview.md)** — Product overview and roadmap.
