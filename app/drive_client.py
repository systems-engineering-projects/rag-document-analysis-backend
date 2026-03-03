"""
Google Drive read-only client for ingestion.
Uses OAuth2 with drive.readonly scope. Lists and exports Google Docs as plain text.
"""

import logging
from dataclasses import dataclass

from google.oauth2.credentials import Credentials
from google.auth.transport.requests import Request
from googleapiclient.discovery import build

from app.config import GOOGLE_CLIENT_ID, GOOGLE_CLIENT_SECRET, GOOGLE_REFRESH_TOKEN

logger = logging.getLogger(__name__)

# v1: only Google Docs (export as text/plain)
GOOGLE_DOCS_MIME = "application/vnd.google-apps.document"
EXPORT_MIME_PLAIN = "text/plain"


@dataclass
class DriveDoc:
    """A document fetched from Drive, ready for ingest."""

    doc_id: str  # Drive file id (used as doc_id for idempotency)
    title: str
    text: str
    source: str = "google_drive"


class DriveClientError(Exception):
    """Raised when Drive API calls fail (auth, export, etc.)."""

    pass


def _get_credentials() -> Credentials:
    """Build Credentials from config; refresh if needed. Raises if config missing."""
    if not GOOGLE_CLIENT_ID or not GOOGLE_CLIENT_SECRET or not GOOGLE_REFRESH_TOKEN:
        raise DriveClientError(
            "Google Drive credentials not configured. Set GOOGLE_CLIENT_ID, "
            "GOOGLE_CLIENT_SECRET, and GOOGLE_REFRESH_TOKEN (run one-time OAuth first)."
        )
    creds = Credentials(
        token=None,
        refresh_token=GOOGLE_REFRESH_TOKEN,
        token_uri="https://oauth2.googleapis.com/token",
        client_id=GOOGLE_CLIENT_ID,
        client_secret=GOOGLE_CLIENT_SECRET,
        scopes=["https://www.googleapis.com/auth/drive.readonly"],
    )
    creds.refresh(Request())
    return creds


def list_and_export_docs(
    folder_id: str | None = None,
    file_ids: list[str] | None = None,
) -> list[DriveDoc]:
    """
    List Drive files (optionally in folder_id or only file_ids) and export
    Google Docs to plain text. Returns list of DriveDoc for ingest.

    - If file_ids is provided, only those files are considered (folder_id ignored).
    - If folder_id is provided and file_ids is None, list files in that folder.
    - If both None, list from root (q not restricted by parent).
    """
    creds = _get_credentials()
    service = build("drive", "v3", credentials=creds)

    if file_ids:
        files_to_export = []
        for fid in file_ids:
            try:
                meta = service.files().get(fileId=fid, fields="id,name,mimeType").execute()
                if meta.get("mimeType") == GOOGLE_DOCS_MIME:
                    files_to_export.append((meta["id"], meta.get("name", fid)))
                else:
                    logger.warning("Skipping non-Doc file %s (mimeType=%s)", fid, meta.get("mimeType"))
            except Exception as e:
                logger.warning("Could not get file %s: %s", fid, e)
    else:
        # Build query: only Google Docs; optionally in folder
        q_parts = [f"mimeType = '{GOOGLE_DOCS_MIME}'"]
        if folder_id:
            q_parts.append(f"'{folder_id}' in parents")
        q = " and ".join(q_parts)

        files_to_export = []
        page_token = None
        while True:
            resp = (
                service.files()
                .list(
                    q=q,
                    pageSize=100,
                    fields="nextPageToken, files(id, name)",
                    pageToken=page_token,
                )
                .execute()
            )
            for f in resp.get("files", []):
                files_to_export.append((f["id"], f.get("name", f["id"])))
            page_token = resp.get("nextPageToken")
            if not page_token:
                break

    result: list[DriveDoc] = []
    for file_id, name in files_to_export:
        try:
            content = service.files().export_media(fileId=file_id, mimeType=EXPORT_MIME_PLAIN).execute()
            text = content.decode("utf-8") if isinstance(content, bytes) else content
            text = text.strip()
            if not text:
                logger.warning("Empty export for %s (%s); skipping", file_id, name)
                continue
            result.append(DriveDoc(doc_id=file_id, title=name or file_id, text=text, source="google_drive"))
        except Exception as e:
            logger.warning("Export failed for %s (%s): %s", file_id, name, e)
            raise DriveClientError(f"Export failed for {name}: {e}") from e

    return result
