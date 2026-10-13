"""Document upload and management API endpoints.

Handles file uploads, triggers background processing (via Celery in full mode
or FastAPI BackgroundTasks in lite mode), and provides document CRUD.
"""

from __future__ import annotations

import hashlib
import uuid

from fastapi import APIRouter, BackgroundTasks, Depends, File, UploadFile
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import get_current_user, get_db
from app.core.config import get_settings
from app.core.exceptions import NotFoundError, ValidationError
from app.core.logging import get_logger
from app.models.document import Document
from app.schemas.auth import MessageResponse

logger = get_logger(__name__)

router = APIRouter()


@router.post(
    "/upload",
    status_code=202,
    summary="Upload a document for RAG processing",
)
async def upload_document(
    background_tasks: BackgroundTasks,
    file: UploadFile = File(...),
    user: dict = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> dict:
    """Upload a document for text extraction and embedding generation.

    The file is saved to disk and processing is triggered in the background.
    In lite mode, uses FastAPI BackgroundTasks; otherwise uses Celery workers.

    Supported formats: PDF, DOCX, TXT, XLSX, CSV.
    """
    settings = get_settings()

    # Validate file extension
    if not file.filename:
        raise ValidationError(message="Filename is required")

    ext = "." + file.filename.rsplit(".", 1)[-1].lower() if "." in file.filename else ""
    if ext not in settings.allowed_upload_extensions:
        raise ValidationError(
            message=f"File type '{ext}' not allowed",
            field_errors={"file": f"Allowed types: {', '.join(settings.allowed_upload_extensions)}"},
        )

    # Read file content
    content = await file.read()
    if len(content) > settings.max_upload_size_bytes:
        raise ValidationError(
            message=f"File too large (max {settings.max_upload_size_mb}MB)",
        )

    # Generate unique filename
    content_hash = hashlib.sha256(content).hexdigest()
    stored_filename = f"{uuid.uuid4().hex}{ext}"
    file_path = settings.upload_path / stored_filename

    # Save file
    file_path.write_bytes(content)

    # Create document record
    user_id = uuid.UUID(user["sub"])
    tenant_id = uuid.UUID(user.get("tenant_id", ""))

    doc = Document(
        filename=stored_filename,
        original_filename=file.filename,
        file_type=ext.lstrip("."),
        file_size_bytes=len(content),
        file_path=str(file_path),
        status="processing",
        content_hash=content_hash,
        uploaded_by=user_id,
        tenant_id=tenant_id,
    )
    db.add(doc)
    await db.flush()

    # Trigger background processing
    if settings.lite_mode:
        # Use FastAPI BackgroundTasks in lite mode
        from app.services.document_service import process_document_async

        import asyncio

        def _run_async_processing():
            loop = asyncio.new_event_loop()
            try:
                loop.run_until_complete(process_document_async(
                    document_id=str(doc.id),
                    tenant_id=str(tenant_id),
                    file_path=str(file_path),
                    file_type=ext.lstrip("."),
                ))
            finally:
                loop.close()

        background_tasks.add_task(_run_async_processing)
        logger.info("Document processing queued (lite mode)", document_id=str(doc.id))
    else:
        try:
            from app.workers.tasks.document_tasks import process_document

            process_document.delay(
                document_id=str(doc.id),
                tenant_id=str(tenant_id),
                file_path=str(file_path),
                file_type=ext.lstrip("."),
            )
            logger.info("Document processing queued (Celery)", document_id=str(doc.id))
        except Exception as exc:
            logger.warning("Celery unavailable, using inline processing", error=str(exc))
            # Fallback to async processing if Celery is unavailable
            from app.services.document_service import process_document_async

            import asyncio

            def _run_fallback():
                loop = asyncio.new_event_loop()
                try:
                    loop.run_until_complete(process_document_async(
                        document_id=str(doc.id),
                        tenant_id=str(tenant_id),
                        file_path=str(file_path),
                        file_type=ext.lstrip("."),
                    ))
                finally:
                    loop.close()

            background_tasks.add_task(_run_fallback)

    logger.info(
        "Document uploaded",
        document_id=str(doc.id),
        filename=file.filename,
        size_bytes=len(content),
    )

    return {
        "document_id": str(doc.id),
        "filename": file.filename,
        "file_type": ext.lstrip("."),
        "file_size_bytes": len(content),
        "status": doc.status,
        "message": "Document uploaded and queued for processing",
    }


@router.get(
    "/",
    summary="List uploaded documents",
)
async def list_documents(
    user: dict = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> list[dict]:
    """List all documents uploaded by the current user's tenant."""
    tenant_id = uuid.UUID(user.get("tenant_id", ""))

    result = await db.execute(
        select(Document)
        .where(Document.tenant_id == tenant_id)
        .order_by(Document.created_at.desc())
        .limit(100)
    )
    docs = result.scalars().all()

    return [
        {
            "id": str(d.id),
            "original_filename": d.original_filename,
            "file_type": d.file_type,
            "file_size_bytes": d.file_size_bytes,
            "status": d.status,
            "chunk_count": d.chunk_count,
            "created_at": d.created_at.isoformat(),
        }
        for d in docs
    ]


@router.get(
    "/{document_id}",
    summary="Get document details",
)
async def get_document(
    document_id: uuid.UUID,
    user: dict = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> dict:
    """Get detailed information about an uploaded document."""
    tenant_id = uuid.UUID(user.get("tenant_id", ""))

    result = await db.execute(
        select(Document)
        .where(
            Document.id == document_id,
            Document.tenant_id == tenant_id,
        )
    )
    doc = result.scalar_one_or_none()

    if not doc:
        raise NotFoundError("Document", str(document_id))

    return {
        "id": str(doc.id),
        "original_filename": doc.original_filename,
        "file_type": doc.file_type,
        "file_size_bytes": doc.file_size_bytes,
        "status": doc.status,
        "error_message": doc.error_message,
        "page_count": doc.page_count,
        "chunk_count": doc.chunk_count,
        "character_count": doc.character_count,
        "content_hash": doc.content_hash,
        "created_at": doc.created_at.isoformat(),
        "updated_at": doc.updated_at.isoformat(),
    }


@router.delete(
    "/{document_id}",
    response_model=MessageResponse,
    summary="Delete a document",
)
async def delete_document(
    document_id: uuid.UUID,
    user: dict = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> MessageResponse:
    """Delete a document and its embeddings."""
    tenant_id = uuid.UUID(user.get("tenant_id", ""))

    result = await db.execute(
        select(Document)
        .where(
            Document.id == document_id,
            Document.tenant_id == tenant_id,
        )
    )
    doc = result.scalar_one_or_none()

    if not doc:
        raise NotFoundError("Document", str(document_id))

    # Delete the file
    from pathlib import Path
    file_path = Path(doc.file_path)
    if file_path.exists():
        file_path.unlink()

    # Delete ChromaDB chunks
    try:
        import chromadb

        settings = get_settings()
        client = chromadb.HttpClient(
            host=settings.chromadb_host,
            port=settings.chromadb_port,
        )
        collection_name = f"tenant_{tenant_id}_documents"
        try:
            collection = client.get_collection(name=collection_name)
            # Delete all chunks for this document
            collection.delete(where={"document_id": str(document_id)})
        except Exception:
            pass  # Collection may not exist
    except Exception as exc:
        logger.warning("Could not delete ChromaDB chunks", error=str(exc))

    await db.delete(doc)

    return MessageResponse(message="Document deleted successfully")
