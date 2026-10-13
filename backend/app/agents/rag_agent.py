"""RAG (Retrieval-Augmented Generation) agent node.

Searches the vector store (ChromaDB) for relevant document chunks,
then generates an answer grounded in the retrieved context.
"""

from __future__ import annotations

import time
from typing import Any

from langchain_core.messages import AIMessage

from app.agents.state import AgentState
from app.core.logging import get_logger
from app.core.telemetry import AGENT_EXECUTIONS_TOTAL, AGENT_EXECUTION_DURATION
from app.llm.factory import get_llm_service
from app.prompts import prompt_manager

logger = get_logger(__name__, agent="rag")


async def rag_node(state: AgentState) -> dict[str, Any]:
    """RAG agent node — retrieves context and generates grounded answers.

    Steps:
    1. Query ChromaDB for relevant document chunks
    2. Render the RAG prompt with retrieved context
    3. Generate an answer using the LLM
    4. Return the answer with source citations

    Args:
        state: The current agent pipeline state.

    Returns:
        State updates with retrieved chunks and final response.
    """
    start = time.perf_counter()
    user_message = state.get("user_message", "")
    tenant_id = state.get("tenant_id", "")

    logger.info("RAG agent processing", message_preview=user_message[:100])

    # Step 1: Retrieve relevant chunks from ChromaDB
    chunks = await _retrieve_chunks(user_message, tenant_id)

    # Step 2: Sanitize retrieved chunks against prompt injection
    from app.core.guardrails import defuse_prompt_injection

    sanitized_chunks = []
    for c in chunks:
        clean_content, was_defused = defuse_prompt_injection(c.get("content", ""))
        chunk_copy = dict(c)
        chunk_copy["content"] = clean_content
        if was_defused:
            logger.warning("Prompt injection defused in retrieved chunk", source=c.get("source"))
        sanitized_chunks.append(chunk_copy)

    # Step 3: Render the RAG prompt with sanitized context
    system_prompt = prompt_manager.render(
        "rag_agent",
        retrieved_chunks=sanitized_chunks,
        user_message=user_message,
    )

    # Step 3: Generate answer
    llm = get_llm_service()
    response = await llm.generate(
        prompt=user_message,
        system_prompt=system_prompt,
        temperature=0.3,
        max_tokens=2000,
    )

    duration = time.perf_counter() - start

    AGENT_EXECUTIONS_TOTAL.labels(agent_type="rag", status="success").inc()
    AGENT_EXECUTION_DURATION.labels(
        agent_type="rag", model=response.model
    ).observe(duration)

    # Build reasoning step
    reasoning_step = {
        "agent": "rag",
        "action": "document_retrieval_and_answer",
        "chunks_retrieved": len(chunks),
        "sources": list({c.get("source", "unknown") for c in chunks}),
        "duration_ms": int(duration * 1000),
        "model": response.model,
        "tokens": response.total_tokens,
    }

    existing_reasoning = state.get("reasoning_steps", [])
    existing_reasoning.append(reasoning_step)

    logger.info(
        "RAG agent complete",
        chunks_retrieved=len(chunks),
        duration_ms=int(duration * 1000),
    )

    return {
        "current_agent": "rag",
        "next_agent": "end",
        "retrieved_chunks": chunks,
        "final_response": response.content,
        "reasoning_steps": existing_reasoning,
        "messages": [AIMessage(content=response.content)],
    }


async def _retrieve_chunks(
    query: str, tenant_id: str, n_results: int = 10
) -> list[dict[str, Any]]:
    """Retrieve relevant document chunks from ChromaDB.

    Args:
        query: The search query.
        tenant_id: Tenant ID for filtering.
        n_results: Maximum number of chunks to retrieve.

    Returns:
        List of chunk dicts with content, source, page, and score.
    """
    try:
        import chromadb

        from app.core.config import get_settings

        settings = get_settings()
        client = chromadb.HttpClient(
            host=settings.chromadb_host,
            port=settings.chromadb_port,
        )

        # Collection name follows tenant scoping convention
        collection_name = f"tenant_{tenant_id}_documents"

        try:
            collection = client.get_collection(name=collection_name)
        except Exception:
            logger.info("No ChromaDB collection found for tenant", tenant_id=tenant_id)
            return []

        results = collection.query(
            query_texts=[query],
            n_results=n_results,
            include=["documents", "metadatas", "distances"],
        )

        chunks: list[dict[str, Any]] = []
        if results and results.get("documents"):
            for i, doc in enumerate(results["documents"][0]):
                metadata = results["metadatas"][0][i] if results.get("metadatas") else {}
                distance = results["distances"][0][i] if results.get("distances") else 0.0
                # Convert distance to similarity score (cosine distance → similarity)
                score = max(0, 1 - distance)
                chunks.append({
                    "content": doc,
                    "source": metadata.get("source", "Unknown"),
                    "page": metadata.get("page_number"),
                    "score": score,
                    "chunk_id": metadata.get("chunk_id", ""),
                })

        return chunks

    except Exception as exc:
        logger.error("ChromaDB retrieval failed", error=str(exc), exc_info=True)
        return []
