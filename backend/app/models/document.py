"""Document and EmbeddingMetadata models for RAG pipeline tracking."""

from __future__ import annotations

import uuid

from sqlalchemy import BigInteger, ForeignKey, Integer, String, Text
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.models.base import TenantModel


class Document(TenantModel):
    """Represents an uploaded document processed for RAG.

    Tracks the document metadata, processing status, and relationships
    to generated embeddings.
    """

    __tablename__ = "documents"

    filename: Mapped[str] = mapped_column(String(500), nullable=False)
    original_filename: Mapped[str] = mapped_column(String(500), nullable=False)
    file_type: Mapped[str] = mapped_column(String(20), nullable=False)
    file_size_bytes: Mapped[int] = mapped_column(BigInteger, nullable=False)
    file_path: Mapped[str] = mapped_column(String(1000), nullable=False)

    # Processing status
    status: Mapped[str] = mapped_column(
        String(30), nullable=False, default="pending"
    )  # pending, processing, completed, failed
    error_message: Mapped[str | None] = mapped_column(Text, nullable=True)

    # Content metadata
    page_count: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    chunk_count: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    character_count: Mapped[int] = mapped_column(Integer, default=0, nullable=False)

    # ChromaDB collection name for this document's embeddings
    collection_name: Mapped[str | None] = mapped_column(String(255), nullable=True)

    # Content hash for deduplication
    content_hash: Mapped[str | None] = mapped_column(String(64), nullable=True, index=True)

    # Foreign keys
    uploaded_by: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("users.id", ondelete="SET NULL"),
        nullable=True,
    )

    # Relationships
    uploaded_by_user: Mapped["User"] = relationship(  # type: ignore[name-defined]  # noqa: F821
        back_populates="documents"
    )
    embeddings: Mapped[list["EmbeddingMetadata"]] = relationship(
        back_populates="document",
        cascade="all, delete-orphan",
    )

    def __repr__(self) -> str:
        return f"<Document(filename='{self.original_filename}', status='{self.status}')>"


class EmbeddingMetadata(TenantModel):
    """Tracks individual embedding chunks generated from documents.

    Each record corresponds to a chunk stored in ChromaDB, linking
    the vector store back to the source document and page.
    """

    __tablename__ = "embedding_metadata"

    # ChromaDB identifiers
    collection_name: Mapped[str] = mapped_column(String(255), nullable=False)
    chunk_id: Mapped[str] = mapped_column(
        String(255), nullable=False, unique=True, index=True
    )

    # Source location
    chunk_index: Mapped[int] = mapped_column(Integer, nullable=False)
    page_number: Mapped[int | None] = mapped_column(Integer, nullable=True)
    start_char: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    end_char: Mapped[int] = mapped_column(Integer, default=0, nullable=False)

    # Chunk content preview (first 500 chars for quick display)
    content_preview: Mapped[str | None] = mapped_column(String(500), nullable=True)

    # Embedding metadata
    embedding_model: Mapped[str] = mapped_column(String(100), nullable=False)
    token_count: Mapped[int] = mapped_column(Integer, default=0, nullable=False)

    # Parent-child chunking support
    parent_chunk_id: Mapped[str | None] = mapped_column(String(255), nullable=True)
    is_parent: Mapped[bool | None] = mapped_column(default=False, nullable=True)

    # Foreign keys
    document_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("documents.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )

    # Relationships
    document: Mapped["Document"] = relationship(back_populates="embeddings")

    def __repr__(self) -> str:
        return f"<EmbeddingMetadata(chunk_id='{self.chunk_id}', doc_id='{self.document_id}')>"
