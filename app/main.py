"""
Verbiage: RAG API for document ingest and question-answering. Ingest text or Google Drive docs;
ask questions; retrieval uses embeddings + pgvector. LLM and embeddings via OpenAI when OPENAI_API_KEY is set,
with optional fallback to Ollama; otherwise Ollama only.
"""
from contextlib import asynccontextmanager
from pathlib import Path

import asyncio
import logging
import time
from logging.handlers import RotatingFileHandler

from fastapi import FastAPI, File, Request, UploadFile, HTTPException
from fastapi.responses import JSONResponse, RedirectResponse, HTMLResponse
from fastapi.staticfiles import StaticFiles
import psycopg2
from psycopg2 import pool as psycopg2_pool

from app.db import (
    create_db,
    delete_by_doc_id,
    doc_exist,
    get_valid_conn,
    insert_chunk,
    insert_document,
    insert_embedding,
    is_connection_error,
    list_documents,
)
from app.models import (
    AskRequest,
    AskResponse,
    ChunkingOptions,
    DocumentSummary,
    DocumentsListResponse,
    IngestGoogleDriveRequest,
    IngestGoogleDriveResponse,
    IngestRequest,
    IngestResponse,
)
from app.rate_limit import TokenBucket
from app.chunking import chunk_text_chars
from app.embeddings import HttpEmbedder
from app.job_store import JobStore
from app.worker import worker_loop
from app.retrieval import retrieve_top_k
from app.errors import LLMRateLimitedError, LLMServiceError, LLMTimeoutError, LLMUpstreamTimeoutError
from app.drive_client import list_and_export_docs, DriveClientError
from app.pdf_extract import extract_text_from_pdf, sanitize_doc_id_from_filename
from app.config import (
    DATABASE_URL,
    GOOGLE_CLIENT_ID,
    GOOGLE_CLIENT_SECRET,
    GOOGLE_REDIRECT_URI,
)
from app import llm_client

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
)
logger = logging.getLogger(__name__)

# Rotating file log for app (rate limits, errors). Path: verbiage/logs/verbiage.log
_LOG_DIR = Path(__file__).resolve().parent.parent / "logs"
_LOG_DIR.mkdir(parents=True, exist_ok=True)
_FILE_LOG = _LOG_DIR / "verbiage.log"
_file_handler = RotatingFileHandler(_FILE_LOG, maxBytes=500_000, backupCount=3)
_file_handler.setFormatter(logging.Formatter("%(asctime)s [%(levelname)s] %(name)s: %(message)s"))
logging.getLogger("app").addHandler(_file_handler)
logger.info("App log file: %s", _FILE_LOG)



@asynccontextmanager
async def lifespan(app):
    if not DATABASE_URL:
        raise ValueError("DATABASE_URL must be set for Postgres connection")
    db_pool = psycopg2_pool.ThreadedConnectionPool(
        minconn=1,
        maxconn=10,
        dsn=DATABASE_URL,
    )
    app.state.db_pool = db_pool
    conn = db_pool.getconn()
    try:
        create_db(conn)
    finally:
        db_pool.putconn(conn)

    app.state.job_store = JobStore()
    job_store = app.state.job_store
    app.state.rate_limiter = TokenBucket()
    rate_limiter = app.state.rate_limiter
    task = asyncio.create_task(worker_loop(job_store, rate_limiter))
    logger.info("Work Started")

    yield

    task.cancel()
    try:
        await task
    except asyncio.CancelledError:
        pass
    db_pool.closeall()
    logger.info("Work has stopped")


app = FastAPI(lifespan=lifespan)


async def with_db_conn_retry(request: Request, async_fn):
    """
    Get a validated DB connection, run async_fn(conn). On connection-closed errors,
    discard the connection, get a new one, and retry once. Always returns the connection to the pool.
    """
    pool = request.app.state.db_pool
    conn = get_valid_conn(pool)
    try:
        return await async_fn(conn)
    except psycopg2.DatabaseError as e:
        if is_connection_error(e):
            pool.putconn(conn, close=True)
            conn = get_valid_conn(pool)
            try:
                return await async_fn(conn)
            finally:
                pool.putconn(conn)
                conn = None  # already returned
        else:
            raise
    finally:
        if conn is not None:
            pool.putconn(conn)


def with_db_conn_retry_sync(request: Request, sync_fn):
    """
    Same as with_db_conn_retry but for sync route handlers. Get validated conn, run sync_fn(conn);
    on connection-closed errors, retry once with a fresh connection.
    """
    pool = request.app.state.db_pool
    conn = get_valid_conn(pool)
    try:
        return sync_fn(conn)
    except psycopg2.DatabaseError as e:
        if is_connection_error(e):
            pool.putconn(conn, close=True)
            conn = get_valid_conn(pool)
            try:
                return sync_fn(conn)
            finally:
                pool.putconn(conn)
                conn = None
        else:
            raise
    finally:
        if conn is not None:
            pool.putconn(conn)


async def ingest_text(
    conn,
    doc_id: str,
    title: str | None,
    source: str | None,
    text: str,
    chunking_options: ChunkingOptions,
) -> IngestResponse:
    """
    Shared ingest: chunk text, insert document + chunks, embed, insert embeddings, commit.
    Raises ValueError('doc_id already exists') if doc_id is duplicate.
    Rollback (delete_by_doc_id) on embedding failure.
    """
    if doc_exist(conn, doc_id):
        raise ValueError("doc_id already exists")
    opts = chunking_options
    chunks = chunk_text_chars(text, opts.chunk_size, opts.chunk_overlap)
    insert_document(conn, doc_id, int(time.time()), title, source)
    for chunk in chunks:
        chunk_id = f"{doc_id}:{chunk.chunk_index}"
        insert_chunk(
            conn, chunk_id, doc_id, chunk.chunk_index, chunk.content,
            chunk.start_offset, chunk.end_offset,
        )
    embedder = HttpEmbedder()
    try:
        vectors = await embedder.embed_many([c.content for c in chunks])
    except Exception as e:
        delete_by_doc_id(conn, doc_id)
        logger.exception("embedding failed", exc_info=e)
        raise
    for chunk, vector in zip(chunks, vectors):
        chunk_id = f"{doc_id}:{chunk.chunk_index}"
        insert_embedding(conn, chunk_id, embedder.model, vector, embedder.dim)
    conn.commit()
    return IngestResponse(
        doc_id=doc_id,
        num_chunks=len(chunks),
        embedding_model=embedder.model,
        dim=embedder.dim,
    )


@app.post("/ingest", response_model=IngestResponse)
async def ingest(request: Request, ingest_request: IngestRequest):
    async def do_ingest(conn):
        try:
            return await ingest_text(
                conn,
                ingest_request.doc_id,
                ingest_request.title,
                ingest_request.source,
                ingest_request.text,
                ingest_request.chunking_options,
            )
        except ValueError as e:
            if "already exists" in str(e):
                raise HTTPException(
                    status_code=409,
                    detail="doc_id (document title) already exists. Use a different doc_id or delete the existing document first.",
                ) from e
            raise
        except Exception as e:
            raise HTTPException(status_code=503, detail="Embedding failed") from e

    return await with_db_conn_retry(request, do_ingest)


MAX_UPLOAD_PDF_BYTES = 50 * 1024 * 1024  # 50 MB
# Browsers often send PDFs as application/octet-stream; allow when filename is .pdf
ALLOWED_PDF_CONTENT_TYPES = {"application/pdf", "application/octet-stream"}
ALLOWED_PDF_EXTENSIONS = {".pdf"}


@app.post("/ingest/file", response_model=IngestResponse)
async def ingest_file(
    request: Request,
    file: UploadFile = File(..., description="PDF file to ingest"),
    doc_id: str | None = File(default=None),
    title: str | None = File(default=None),
    source: str | None = File(default=None),
    chunk_size: int = File(default=800),
    chunk_overlap: int = File(default=100),
):
    """
    Ingest a PDF file: extract text, then chunk, embed, and store (same as POST /ingest).
    Multipart form: required 'file' (PDF), optional doc_id, title, source, chunk_size, chunk_overlap.
    """
    filename = file.filename or "document.pdf"
    if not any(filename.lower().endswith(ext) for ext in ALLOWED_PDF_EXTENSIONS):
        raise HTTPException(
            status_code=400,
            detail="Only PDF files are accepted. Use a .pdf file.",
        )
    content_type = (file.content_type or "").strip().lower()
    if content_type and content_type not in ALLOWED_PDF_CONTENT_TYPES:
        raise HTTPException(
            status_code=400,
            detail=f"Unsupported file type: {content_type}. Only PDF (.pdf) is accepted.",
        )
    data = await file.read()
    if len(data) > MAX_UPLOAD_PDF_BYTES:
        raise HTTPException(
            status_code=400,
            detail=f"File too large (max {MAX_UPLOAD_PDF_BYTES // (1024*1024)} MB).",
        )
    try:
        text = extract_text_from_pdf(data)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e)) from e

    resolved_doc_id = (
        doc_id.strip() if doc_id and doc_id.strip() else sanitize_doc_id_from_filename(filename)
    )
    resolved_title = title.strip() if title and title.strip() else filename
    resolved_source = source.strip() if source and source.strip() else "uploaded_pdf"
    try:
        opts = ChunkingOptions(chunk_size=chunk_size, chunk_overlap=chunk_overlap)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e)) from e

    async def do_ingest_file(conn):
        try:
            return await ingest_text(
                conn,
                resolved_doc_id,
                resolved_title,
                resolved_source,
                text,
                opts,
            )
        except ValueError as e:
            if "already exists" in str(e):
                raise HTTPException(
                    status_code=409,
                    detail="doc_id (document title) already exists. Use a different doc_id or delete the existing document first.",
                ) from e
            raise
        except Exception as e:
            raise HTTPException(status_code=503, detail="Embedding failed") from e

    return await with_db_conn_retry(request, do_ingest_file)


@app.post("/ingest/google-drive", response_model=IngestGoogleDriveResponse)
async def ingest_google_drive(request: Request, body: IngestGoogleDriveRequest):
    """
    Ingest Google Docs from Drive (read-only). List/export then run shared ingest per doc.
    Duplicate doc_id is skipped and counted; other errors are recorded and processing continues.
    """
    try:
        docs = list_and_export_docs(folder_id=body.folder_id, file_ids=body.file_ids)
    except DriveClientError as e:
        raise HTTPException(status_code=503, detail=str(e)) from e
    default_opts = ChunkingOptions()
    ingested = 0
    skipped = 0
    errors: list[str] = []
    doc_ids: list[str] = []

    async def do_google_drive_ingest(conn):
        nonlocal ingested, skipped, errors, doc_ids
        for doc in docs:
            try:
                await ingest_text(
                    conn,
                    doc.doc_id,
                    doc.title,
                    doc.source,
                    doc.text,
                    default_opts,
                )
                ingested += 1
                doc_ids.append(doc.doc_id)
            except ValueError as e:
                if "already exists" in str(e):
                    skipped += 1
                else:
                    errors.append(f"{doc.doc_id} ({doc.title}): {e}")
            except Exception as e:
                errors.append(f"{doc.doc_id} ({doc.title}): {e}")
                logger.warning("Ingest failed for %s: %s", doc.doc_id, e)
        return IngestGoogleDriveResponse(
            ingested=ingested,
            skipped=skipped,
            errors=errors,
            doc_ids=doc_ids,
        )

    return await with_db_conn_retry(request, do_google_drive_ingest)


@app.post("/ask", response_model=AskResponse)
async def ask(request: Request, ask_request: AskRequest):
    async def do_ask(conn):
        rate_limiter = request.app.state.rate_limiter
        embedder = HttpEmbedder()
        logger.info("ask: embedding query (1 text)")
        query_vectors = await embedder.embed_many([ask_request.question])
        logger.info("ask: embedding succeeded")
        query_vec = query_vectors[0]

        top_chunks = retrieve_top_k(conn, query_vec, ask_request.top_k, ask_request.doc_id)

        MAX_CONTEXT_CHARS = 8000
        context_parts = []
        total_len = 0
        if not top_chunks:
            answer = "I don't have relevant context to answer that question."
            return AskResponse(answer=answer, top_chunks=[])
        for c in top_chunks:
            block = f"[doc_id={c.doc_id} chunk_id={c.chunk_id}]\n{c.content_snippet}\n"
            if total_len + len(block) > MAX_CONTEXT_CHARS:
                break
            context_parts.append(block)
            total_len += len(block)

        context_str = "\n".join(context_parts) if context_parts else "(No relevant context found.)"
        prompt = (
            "Answer using only the context below. If the context doesn't contain enough information, say so.\n\n"
            "Context:\n" + context_str + "\n\n"
            "Question: " + ask_request.question
        )
        logger.info("ask: acquiring rate limit token")
        await rate_limiter.acquire()
        logger.info("ask: rate limit acquired, calling LLM")
        answer = await llm_client.answer_with_context(prompt)
        logger.info("ask: LLM answered successfully")
        return AskResponse(answer=answer, top_chunks=top_chunks)

    return await with_db_conn_retry(request, do_ask)

@app.get("/documents", response_model=DocumentsListResponse)
def get_documents(request: Request):
    def do_list(conn):
        rows = list_documents(conn)
        return DocumentsListResponse(
            documents=[
                DocumentSummary(
                    doc_id=r[0],
                    title=r[1],
                    source=r[2],
                    created_at=r[3],
                    num_chunks=r[4],
                    snippet=r[5],
                )
                for r in rows
            ]
        )

    return with_db_conn_retry_sync(request, do_list)


@app.get("/health")
def health():
    return {"healthy": True}


@app.exception_handler(LLMTimeoutError)
async def timeout_handler(request: Request, exc: LLMTimeoutError):
    return JSONResponse(
        status_code=504,
        content={"detail": "LLM request timed out"},
    )

@app.exception_handler(LLMUpstreamTimeoutError)
async def timeout_handler(request: Request, exc: LLMUpstreamTimeoutError):
    return JSONResponse(
        status_code=504,
        content={"detail": "LLM request timed out"},
    )


@app.exception_handler(LLMServiceError)
async def service_error_handler(request: Request, exc: LLMServiceError):
    return JSONResponse(
        status_code=503,
        content={"detail": "LLM service unavailable"},
    )

@app.exception_handler(LLMRateLimitedError)
async def service_error_handler(request: Request, exc: LLMRateLimitedError):
    logger.warning("LLM rate limit (429): %s", exc)
    return JSONResponse(
        status_code=429,
        content={"detail": "LLM rate limit issue."},
    )


def _google_flow():
    """Build OAuth flow for Drive read-only (state will be set per-request)."""
    if not GOOGLE_CLIENT_ID or not GOOGLE_CLIENT_SECRET:
        raise ValueError("GOOGLE_CLIENT_ID and GOOGLE_CLIENT_SECRET must be set")
    from google_auth_oauthlib.flow import Flow

    client_config = {
        "web": {
            "client_id": GOOGLE_CLIENT_ID,
            "client_secret": GOOGLE_CLIENT_SECRET,
            "redirect_uris": [GOOGLE_REDIRECT_URI],
        }
    }
    return Flow.from_client_config(
        client_config,
        scopes=["https://www.googleapis.com/auth/drive.readonly"],
        redirect_uri=GOOGLE_REDIRECT_URI,
    )


@app.get("/auth/google")
async def auth_google(request: Request):
    """
    Start one-time OAuth: redirect to Google consent (Drive read-only).
    After approval, user is sent to /auth/google/callback.
    """
    try:
        flow = _google_flow()
    except ValueError as e:
        raise HTTPException(status_code=503, detail=str(e)) from e
    auth_url, state = flow.authorization_url(
        access_type="offline",
        prompt="consent",
        include_granted_scopes="false",
    )
    response = RedirectResponse(url=auth_url, status_code=302)
    response.set_cookie(key="oauth_state", value=state, max_age=600, httponly=True)
    return response


@app.get("/auth/google/callback", response_class=HTMLResponse)
async def auth_google_callback(request: Request):
    """
    OAuth callback: exchange code for tokens, show refresh token to set in .env.
    """
    state_cookie = request.cookies.get("oauth_state")
    state_query = request.query_params.get("state")
    code = request.query_params.get("code")
    if not code:
        raise HTTPException(status_code=400, detail="Missing code in callback")
    if not state_cookie or state_cookie != state_query:
        raise HTTPException(status_code=400, detail="Invalid or missing state")
    try:
        flow = _google_flow()
        flow._state = state_query
        flow.fetch_token(authorization_response=str(request.url))
    except Exception as e:
        logger.exception("OAuth fetch_token failed: %s", e)
        raise HTTPException(status_code=503, detail="Token exchange failed") from e
    refresh_token = flow.credentials.refresh_token
    if not refresh_token:
        raise HTTPException(
            status_code=503,
            detail="No refresh token; try revoking app access and re-authorizing with prompt=consent",
        )
    response = HTMLResponse(
        content=f"""
        <html><body style="font-family: sans-serif; padding: 2rem;">
        <h1>Google Drive auth complete</h1>
        <p>Add this to your <code>.env</code> (or set the env var):</p>
        <pre style="background: #eee; padding: 1rem; overflow-x: auto;">GOOGLE_REFRESH_TOKEN={refresh_token!r}</pre>
        <p>You already have <code>GOOGLE_CLIENT_ID</code> and <code>GOOGLE_CLIENT_SECRET</code> set (required for this flow).</p>
        <p>Then restart the app and use <b>POST /ingest/google-drive</b> to sync.</p>
        </body></html>
        """
    )
    response.delete_cookie("oauth_state")
    return response


# Mount static frontend last so API routes take precedence.
static_dir = Path(__file__).resolve().parent.parent / "static"
if static_dir.is_dir():
    app.mount("/", StaticFiles(directory=str(static_dir), html=True), name="static")

