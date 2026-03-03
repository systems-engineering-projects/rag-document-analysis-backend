# Verbiage — Setup and Testing

## Prerequisites: OpenAI or Ollama

When **OPENAI_API_KEY** is set in `.env`, the app uses **OpenAI** for embeddings (`text-embedding-3-small`, 768 dim) and for the LLM (e.g. `gpt-4o-mini`). Optional: set `EMBED_FALLBACK_TO_LOCAL` or `LLM_FALLBACK_TO_LOCAL` to true to use Ollama when OpenAI fails.

When **OPENAI_API_KEY** is not set, the app uses **Ollama** only. Default config expects:

- **LLM:** `llama3.1:8b` at `http://localhost:11434`
- **Embeddings:** `nomic-embed-text` at the same base URL

### Start Ollama and pull models (Ollama-only or fallback)

```bash
# Start the Ollama server (if not already running as a service)
ollama serve
```

In another terminal, pull the models so the API can load them when using Ollama:

```bash
# LLM used by POST /ask when using Ollama (see app/config.py: LLM_MODEL)
ollama pull llama3.1:8b

# Embedding model used for ingest and ask when using Ollama (EMBED_MODEL)
ollama pull nomic-embed-text
```

Optional: run the LLM interactively (also pulls if needed):

```bash
ollama run llama3.1:8b
```

---

## App setup

```bash
cd verbiage
python3 -m venv .venv
source .venv/bin/activate   # Windows: .venv\Scripts\activate
pip install -r requirements.txt
```

Copy `.env.example` to `.env`. **Required:** set `DATABASE_URL` to your Postgres connection URI (e.g. from Supabase: Project Settings → Database → Connection string; see `supabase_migration.md`). The app will not start without it. For OpenAI: set `OPENAI_API_KEY`. For Ollama-only: leave the key unset and set `LLM_BASE_URL` / `EMBED_BASE_URL` if not using defaults.

Start the API:

```bash
uvicorn app.main:app --reload
```

Default: `http://localhost:8000`. The same server serves the **web UI** at the root URL (see below).

---

## Web UI

After starting the API with `uvicorn app.main:app --reload`, open a browser at:

**http://localhost:8000/**

You get a single-page UI with **menu/tabs** so you can focus on one task at a time.

### Tabs

- **Ingest** — Paste report text or upload a PDF; optionally set doc ID, title, source, and chunk size/overlap. Submit to run ingest. Success or error message appears below the form.
- **Ask** — Enter a question (e.g. for overview or detailed verbiage). Optionally limit the search to one document (dropdown). Submit to get an answer and expandable “Source chunks.” The document dropdown is filled from the list of ingested documents and is refreshed after each ingest.

The last selected tab is remembered in the browser (localStorage) for the next visit.

### Documents list (on demand)

Click **Documents** in the header to open a **drawer** from the right. It calls `GET /documents` and shows ingested docs: doc_id, title, source, chunk count, and a short snippet. Close the drawer with the × or by clicking the overlay. The list is not visible until you open it, so the main view stays focused on Ingest or Ask.

### Quick test flow

1. Open http://localhost:8000/.
2. Switch to the **Ingest** tab, paste some text, set a title and doc_id if you like, then submit.
3. Click **Documents** to confirm the new doc appears in the list; close the drawer.
4. Switch to the **Ask** tab, type a question that relates to the ingested text, then submit. Check the answer and “Source chunks.”

---

## curl commands

Base URL assumed: `http://localhost:8000`. Use `-s` for quieter output.

### Health check

```bash
curl -s "http://localhost:8000/health"
```

### List documents (GET)

Returns ingested documents (doc_id, title, source, created_at, num_chunks, optional snippet). Same data used by the Web UI “Documents” drawer.

```bash
curl -s "http://localhost:8000/documents"
```

### Ingest (POST)

Requires a JSON body with at least `text`. Optional: `doc_id`, `title`, `source`, `chunking_options`.

```bash
curl -s -X POST "http://localhost:8000/ingest" \
  -H "Content-Type: application/json" \
  -d '{"text": "Your document content here. Latency alerts trigger when response time exceeds 500ms for 3 consecutive checks.", "title": "Runbook", "doc_id": "runbook-1"}'
```

Minimal (server generates `doc_id`):

```bash
curl -s -X POST "http://localhost:8000/ingest" \
  -H "Content-Type: application/json" \
  -d '{"text": "Short document to ingest."}'
```

### Ingest PDF (POST /ingest/file)

Accepts multipart form data: required `file` (PDF), optional `doc_id`, `title`, `source`, `chunk_size`, `chunk_overlap`. Text is extracted from the PDF, then chunked and embedded like **POST /ingest**.

```bash
curl -s -X POST "http://localhost:8000/ingest/file" \
  -F "file=@/path/to/report.pdf" \
  -F "title=Report 2024" \
  -F "source=uploaded_pdf"
```

### Ask (POST)

Requires a JSON body with `question`. Optional: `top_k`, `doc_id`, `use_rag`.

After ingesting the test playbook (e.g. content from `payload.json` with `doc_id` `edge-rel-playbook-v1`), these questions verify RAG:

```bash
# Answerable from the playbook: Preflight Validator checks are listed in section 4
curl -s -X POST "http://localhost:8000/ask" \
  -H "Content-Type: application/json" \
  -d '{"question": "What does the Preflight Validator check?"}'
```

```bash
# Answerable from the playbook: latency alert condition is stated in section 7
curl -s -X POST "http://localhost:8000/ask" \
  -H "Content-Type: application/json" \
  -d '{"question": "What conditions trigger a latency alert?"}'
```

With options (e.g. restrict to one document):

```bash
curl -s -X POST "http://localhost:8000/ask" \
  -H "Content-Type: application/json" \
  -d '{"question": "What does the Preflight Validator check?", "top_k": 5, "doc_id": "edge-rel-playbook-v1"}'
```

**Note:** `GET /ask?question=...` is not supported; the endpoint expects **POST** with a JSON body.

---

## Google Drive ingest (read-only)

You can ingest **Google Docs** from Drive by authorizing once with OAuth, then calling **POST /ingest/google-drive**. The app only requests read-only access (`drive.readonly`).

### 1. Google Cloud project and OAuth client

1. Go to [Google Cloud Console](https://console.cloud.google.com/).
2. Create a project (or pick an existing one) and enable **Google Drive API** (APIs & Services → Library → search “Google Drive API” → Enable).
3. Create OAuth credentials: **APIs & Services → Credentials → Create Credentials → OAuth client ID**.
4. If prompted, configure the **OAuth consent screen** (e.g. External, add your email as test user).
5. For **Application type** choose **Web application**.
6. Under **Authorized redirect URIs** add:  
   `http://localhost:8000/auth/google/callback`  
   (or the same URL with your host/port if you run the app elsewhere).
7. Copy the **Client ID** and **Client secret**.

### 2. Set env and run one-time OAuth

In your `.env` (or environment), set:

```bash
GOOGLE_CLIENT_ID=your_client_id
GOOGLE_CLIENT_SECRET=your_client_secret
```

Optional: if the app is not on port 8000, set the callback URL to match what you registered:

```bash
GOOGLE_REDIRECT_URI=http://localhost:8000/auth/google/callback
```

Start the app (`uvicorn app.main:app --reload`), then in a browser open:

**http://localhost:8000/auth/google**

Sign in with the Google account that has access to the Drive files you want to ingest. After you approve, you are redirected to a page that shows a line like:

```bash
GOOGLE_REFRESH_TOKEN="1//0abc..."
```

Add that line to your `.env` (or set the env var), then restart the app.

### 3. Ingest from Drive

**POST /ingest/google-drive** lists and exports Google Docs, then ingests them (chunk + embed + store). Request body (all optional):

- **folder_id** — only list files in this Drive folder.
- **file_ids** — only these file IDs (Google Doc IDs). If set, `folder_id` is ignored.

If both are omitted, the app lists Google Docs from the root of the authenticated user’s Drive.

Example (ingest all Docs in a folder):

```bash
curl -s -X POST "http://localhost:8000/ingest/google-drive" \
  -H "Content-Type: application/json" \
  -d '{"folder_id": "YOUR_DRIVE_FOLDER_ID"}'
```

Example (ingest specific Docs by ID):

```bash
curl -s -X POST "http://localhost:8000/ingest/google-drive" \
  -H "Content-Type: application/json" \
  -d '{"file_ids": ["id1", "id2"]}'
```

Response shape: `{"ingested": N, "skipped": M, "errors": [...], "doc_ids": [...]}`. Duplicate `doc_id` (same file already ingested) is counted as skipped; other failures are listed in `errors`.
