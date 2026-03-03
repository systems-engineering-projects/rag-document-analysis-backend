"""
Pydantic request/response models for ingest, ask, and document listing.
"""

import uuid
from pydantic import BaseModel, Field, model_validator
from typing import Literal

class ChunkingOptions(BaseModel):
    strategy: Literal["chars", "sentences"] = "chars"
    chunk_size: int = Field(default=800, description= "Chunk size")
    chunk_overlap: int = Field(default=100, description="Chunk overlap")

    @model_validator(mode="after")
    def check_chunking_bounds(self)->"ChunkingOptions":
        if self.chunk_size <= 0:
            raise ValueError("chunk_size must be greater than 0")
        if self.chunk_overlap < 0:
            raise ValueError("chunk_overlap must be greater than or equal to 0")
        if self.chunk_overlap >= self.chunk_size:
            raise ValueError("chunk_overlap must be less than chunk_size")
        return self

class IngestRequest (BaseModel):
    text: str = Field(..., min_length=1,description="Text to ingest")
    doc_id: str | None = None
    title: str | None = None
    source: str | None = None
    chunking_options: ChunkingOptions | None = None

    @model_validator(mode="after")
    def set_defaults(self) -> "IngestRequest":
        doc_id = self.doc_id if self.doc_id is not None else str(uuid.uuid4())
        chunking_options = self.chunking_options if self.chunking_options is not None else ChunkingOptions()
        return self.model_copy(update={"doc_id":doc_id, "chunking_options":chunking_options})

class IngestResponse(BaseModel):
    doc_id: str = Field(..., description="doc_id")
    num_chunks: int = Field(..., description="Number of chunks")
    embedding_model: str = Field(..., description="Embedding model")
    dim: int = Field(..., description="Embedding vector dimension")


class AskRequest(BaseModel):
    question: str = Field(..., description="Question from user")
    top_k: int = Field(default=5, description="Will pull the top __ matches")
    doc_id: str | None = Field(default=None, description="If set, restrict search to this document")
    use_rag: bool = True

class RetrievedChunk(BaseModel):
    chunk_id: str = Field(..., description="chunk_id")
    doc_id: str = Field(..., description="doc_id")
    score: float = Field(..., description="score")
    content_snippet: str = Field(..., description="content_snippet")

class AskResponse(BaseModel):
    answer: str = Field(...,description="Answer from system")
    top_chunks: list[RetrievedChunk] = Field(..., description="top _ chunks")
    prompt_tokens_estimate: int | None = Field(default=None, description="Prompt tokens estimate (optional)")


class DocumentSummary(BaseModel):
    doc_id: str = Field(..., description="Document id")
    title: str | None = Field(default=None, description="Title")
    source: str | None = Field(default=None, description="Source")
    created_at: int = Field(..., description="Unix timestamp")
    num_chunks: int = Field(..., description="Number of chunks")
    snippet: str | None = Field(default=None, description="First ~250 chars of first chunk")


class DocumentsListResponse(BaseModel):
    documents: list[DocumentSummary] = Field(..., description="List of ingested documents")


class IngestGoogleDriveRequest(BaseModel):
    """Request to ingest documents from Google Drive (read-only)."""

    folder_id: str | None = Field(default=None, description="Limit to files in this folder")
    file_ids: list[str] | None = Field(default=None, description="If set, only these file IDs (folder_id ignored)")


class IngestGoogleDriveResponse(BaseModel):
    """Result of Google Drive sync."""

    ingested: int = Field(..., description="Number of documents ingested")
    skipped: int = Field(default=0, description="Number skipped (e.g. duplicate doc_id)")
    errors: list[str] = Field(default_factory=list, description="Error messages for failed docs")
    doc_ids: list[str] = Field(default_factory=list, description="doc_ids that were ingested")
