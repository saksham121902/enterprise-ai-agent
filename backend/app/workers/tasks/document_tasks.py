"""Background tasks for document processing.

Handles PDF/DOCX/TXT text extraction, chunking, and embedding
generation as background jobs via Celery.
"""

from __future__ import annotations

import hashlib
import time
from typing import Any

from celery import shared_task
from celery.utils.log import get_task_logger

from app.core.constants import CELERY_QUEUE_DOCUMENTS, TASK_DLQ_ROUTING_KEY

logger = get_task_logger(__name__)


@shared_task(
    bind=True,
    name="app.workers.tasks.document_tasks.process_document",
    queue=CELERY_QUEUE_DOCUMENTS,
    max_retries=3,
    default_retry_delay=30,
    acks_late=True,
)
def process_document(
    self: Any,
    document_id: str,
    tenant_id: str,
    file_path: str,
    file_type: str,
) -> dict[str, Any]:
    """Process an uploaded document: extract text, chunk, and embed.

    This is the main document processing pipeline. It:
    1. Extracts text from the document (PDF, DOCX, TXT, etc.)
    2. Splits text into chunks with overlap
    3. Generates embeddings and stores in ChromaDB
    4. Updates the document record with metadata

    Args:
        document_id: UUID of the Document record.
        tenant_id: Tenant UUID for scoping.
        file_path: Path to the uploaded file.
        file_type: Document type (pdf, docx, txt, etc.).

    Returns:
        Processing result with chunk count and metadata.
    """
    start_time = time.time()

    try:
        logger.info(
            "Processing document",
            extra={"document_id": document_id, "file_type": file_type},
        )

        # Step 1: Extract text
        text = _extract_text(file_path, file_type)
        if not text:
            return {
                "status": "failed",
                "document_id": document_id,
                "error": "No text could be extracted",
            }

        # Step 2: Compute content hash for deduplication
        content_hash = hashlib.sha256(text.encode()).hexdigest()

        # Step 3: Chunk the text
        chunks = _chunk_text(text)

        # Step 4: Generate embeddings (placeholder — implemented in Phase 9)
        # For now, we mark the document as processed
        duration_ms = int((time.time() - start_time) * 1000)

        result = {
            "status": "completed",
            "document_id": document_id,
            "content_hash": content_hash,
            "character_count": len(text),
            "chunk_count": len(chunks),
            "duration_ms": duration_ms,
        }

        logger.info(
            "Document processed successfully",
            extra={
                "document_id": document_id,
                "chunk_count": len(chunks),
                "duration_ms": duration_ms,
            },
        )

        return result

    except Exception as exc:
        logger.error(
            "Document processing failed",
            extra={"document_id": document_id, "error": str(exc)},
            exc_info=True,
        )

        # Retry with exponential backoff
        if self.request.retries < self.max_retries:
            raise self.retry(exc=exc, countdown=30 * (2 ** self.request.retries))

        # Max retries exhausted — send to DLQ
        _send_to_dlq(self, document_id, str(exc))
        return {
            "status": "failed",
            "document_id": document_id,
            "error": str(exc),
        }


def _extract_text(file_path: str, file_type: str) -> str:
    """Extract text content from a document file.

    Args:
        file_path: Path to the file.
        file_type: Document type.

    Returns:
        Extracted text content.
    """
    ft = file_type.lower()
    if ft == "pdf":
        from pypdf import PdfReader

        reader = PdfReader(file_path)
        return "\n".join(
            page.extract_text() or "" for page in reader.pages
        )
    elif ft == "docx":
        import docx

        doc = docx.Document(file_path)
        return "\n".join(para.text for para in doc.paragraphs if para.text)
    elif ft in ("txt", "csv"):
        with open(file_path, encoding="utf-8") as f:
            return f.read()
    elif ft == "xlsx":
        import openpyxl

        wb = openpyxl.load_workbook(file_path, data_only=True)
        text_parts: list[str] = []
        for sheet in wb.worksheets:
            for row in sheet.iter_rows(values_only=True):
                row_text = "\t".join(str(cell) for cell in row if cell is not None)
                if row_text:
                    text_parts.append(row_text)
        return "\n".join(text_parts)
    else:
        raise ValueError(f"Unsupported file type: {file_type}")


def _chunk_text(
    text: str,
    chunk_size: int = 1000,
    chunk_overlap: int = 200,
) -> list[str]:
    """Split text into overlapping chunks.

    Uses a simple character-based splitter with paragraph-aware
    boundary detection.

    Args:
        text: The full text to chunk.
        chunk_size: Target chunk size in characters.
        chunk_overlap: Overlap between consecutive chunks.

    Returns:
        List of text chunks.
    """
    if len(text) <= chunk_size:
        return [text]

    chunks: list[str] = []
    start = 0

    while start < len(text):
        end = start + chunk_size

        # Try to break at paragraph or sentence boundary
        if end < len(text):
            for sep in ["\n\n", "\n", ". ", "! ", "? "]:
                last_sep = text.rfind(sep, start, end)
                if last_sep > start + chunk_size // 2:
                    end = last_sep + len(sep)
                    break

        chunk = text[start:end].strip()
        if chunk:
            chunks.append(chunk)

        start = end - chunk_overlap

    return chunks


def _send_to_dlq(task: Any, document_id: str, error: str) -> None:
    """Send a permanently failed task to the Dead Letter Queue."""
    from app.workers.celery_app import celery_app

    celery_app.send_task(
        "app.workers.tasks.document_tasks.handle_dlq",
        args=[document_id, error],
        queue=TASK_DLQ_ROUTING_KEY,
    )
    logger.warning(
        "Task sent to DLQ",
        extra={"document_id": document_id, "error": error},
    )


@shared_task(
    name="app.workers.tasks.document_tasks.handle_dlq",
    queue=TASK_DLQ_ROUTING_KEY,
)
def handle_dlq(document_id: str, error: str) -> dict[str, str]:
    """Handle a permanently failed document processing task.

    Logs the failure for manual investigation.
    """
    logger.error(
        "DLQ: Document permanently failed",
        extra={"document_id": document_id, "error": error},
    )
    return {"status": "dlq", "document_id": document_id, "error": error}
