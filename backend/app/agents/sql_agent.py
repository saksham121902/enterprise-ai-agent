"""SQL agent node for natural language to SQL translation and execution.

Converts user questions into SQL queries, validates them for safety,
and optionally executes them against the database. Dangerous operations
(INSERT, UPDATE, DELETE) trigger the human approval workflow.
"""

from __future__ import annotations

import time
from typing import Any

from langchain_core.messages import AIMessage

from app.agents.state import AgentState
from app.core.constants import SQL_ALLOWED_STATEMENTS, SQL_APPROVAL_REQUIRED_STATEMENTS
from app.core.logging import get_logger
from app.core.telemetry import AGENT_EXECUTIONS_TOTAL, AGENT_EXECUTION_DURATION
from app.llm.factory import get_llm_service
from app.prompts import prompt_manager

logger = get_logger(__name__, agent="sql")


async def sql_node(state: AgentState) -> dict[str, Any]:
    """SQL agent node — translates NL to SQL and executes safely.

    Steps:
    1. Fetch database schema metadata
    2. Generate SQL via LLM using the schema context
    3. Validate the SQL for safety
    4. Execute the query (or request approval for writes)
    5. Format and return results

    Args:
        state: The current agent pipeline state.

    Returns:
        State updates with SQL query, results, and response.
    """
    start = time.perf_counter()
    user_message = state.get("user_message", "")

    logger.info("SQL agent processing", message_preview=user_message[:100])

    # Step 1: Get schema information
    schema_tables = await _get_schema_info()

    # Step 2: Generate SQL
    system_prompt = prompt_manager.render(
        "sql_agent",
        schema_tables=schema_tables,
        user_message=user_message,
    )

    llm = get_llm_service()
    response = await llm.generate(
        prompt=user_message,
        system_prompt=system_prompt,
        temperature=0.1,
        max_tokens=2000,
    )

    # Step 3: Extract SQL from response
    sql_query = _extract_sql(response.content)

    # Step 4: Validate safety
    safety_result = _validate_sql_safety(sql_query)

    duration = time.perf_counter() - start

    AGENT_EXECUTIONS_TOTAL.labels(agent_type="sql", status="success").inc()
    AGENT_EXECUTION_DURATION.labels(
        agent_type="sql", model=response.model
    ).observe(duration)

    reasoning_step = {
        "agent": "sql",
        "action": "nl_to_sql",
        "sql_query": sql_query[:500] if sql_query else "none",
        "safety_status": safety_result["status"],
        "duration_ms": int(duration * 1000),
        "model": response.model,
        "tokens": response.total_tokens,
    }

    existing_reasoning = state.get("reasoning_steps", [])
    existing_reasoning.append(reasoning_step)

    updates: dict[str, Any] = {
        "current_agent": "sql",
        "next_agent": "end",
        "sql_query": sql_query,
        "reasoning_steps": existing_reasoning,
    }

    if safety_result["status"] == "blocked":
        updates["final_response"] = (
            f"⚠️ The generated SQL query was blocked for safety reasons: "
            f"{safety_result['reason']}\n\nGenerated query:\n```sql\n{sql_query}\n```"
        )
        updates["messages"] = [AIMessage(content=updates["final_response"])]

    elif safety_result["status"] == "requires_approval":
        updates["requires_approval"] = True
        updates["final_response"] = (
            f"🔒 This operation requires human approval before execution.\n\n"
            f"**Operation**: {safety_result['statement_type']}\n"
            f"**Query**:\n```sql\n{sql_query}\n```\n\n"
            f"A manager or admin must approve this operation."
        )
        updates["messages"] = [AIMessage(content=updates["final_response"])]

    else:
        # Safe SELECT query — execute it
        sql_result = await _execute_query(sql_query)
        updates["sql_result"] = sql_result
        updates["final_response"] = (
            f"{response.content}\n\n"
            f"**Query Results:**\n```\n{sql_result}\n```"
        )
        updates["messages"] = [AIMessage(content=updates["final_response"])]

    logger.info("SQL agent complete", duration_ms=int(duration * 1000))
    return updates


async def _get_schema_info() -> list[dict[str, Any]]:
    """Fetch database schema metadata for prompt context.

    Returns a simplified schema representation suitable for
    inclusion in the LLM prompt.
    """
    # Provides a static schema description for now.
    # In production, this queries information_schema dynamically.
    return [
        {
            "name": "users",
            "columns": [
                {"name": "id", "type": "UUID", "description": "Primary key"},
                {"name": "email", "type": "VARCHAR(255)", "description": "User email"},
                {"name": "username", "type": "VARCHAR(100)", "description": "Username"},
                {"name": "full_name", "type": "VARCHAR(255)", "description": "Full name"},
                {"name": "is_active", "type": "BOOLEAN", "description": "Active status"},
                {"name": "created_at", "type": "TIMESTAMP", "description": "Creation date"},
            ],
        },
        {
            "name": "chats",
            "columns": [
                {"name": "id", "type": "UUID", "description": "Primary key"},
                {"name": "title", "type": "VARCHAR(500)", "description": "Chat title"},
                {"name": "total_messages", "type": "INTEGER", "description": "Message count"},
                {"name": "total_tokens", "type": "INTEGER", "description": "Token usage"},
                {"name": "total_cost", "type": "NUMERIC", "description": "Cost in USD"},
                {"name": "user_id", "type": "UUID", "description": "Owner user ID"},
                {"name": "created_at", "type": "TIMESTAMP", "description": "Creation date"},
            ],
        },
        {
            "name": "documents",
            "columns": [
                {"name": "id", "type": "UUID", "description": "Primary key"},
                {"name": "filename", "type": "VARCHAR(500)", "description": "Stored filename"},
                {"name": "original_filename", "type": "VARCHAR(500)", "description": "Original name"},
                {"name": "file_type", "type": "VARCHAR(20)", "description": "File type"},
                {"name": "file_size_bytes", "type": "BIGINT", "description": "File size"},
                {"name": "status", "type": "VARCHAR(30)", "description": "Processing status"},
                {"name": "chunk_count", "type": "INTEGER", "description": "Number of chunks"},
                {"name": "created_at", "type": "TIMESTAMP", "description": "Upload date"},
            ],
        },
    ]


def _extract_sql(response: str) -> str:
    """Extract SQL query from the LLM response.

    Handles responses with SQL in code blocks or inline.
    """
    # Check for SQL code block
    if "```sql" in response:
        parts = response.split("```sql")
        if len(parts) > 1:
            return parts[1].split("```")[0].strip()

    if "```" in response:
        parts = response.split("```")
        if len(parts) > 1:
            candidate = parts[1].strip()
            if candidate.upper().startswith(("SELECT", "INSERT", "UPDATE", "DELETE", "WITH")):
                return candidate

    # Look for inline SQL
    for line in response.split("\n"):
        stripped = line.strip()
        if stripped.upper().startswith(("SELECT", "WITH")):
            return stripped

    return ""


def _validate_sql_safety(sql: str) -> dict[str, Any]:
    """Validate SQL query safety using the dedicated safety validator."""
    from app.agents.sql_validator import validate_sql_safety
    return validate_sql_safety(sql)


async def _execute_query(sql: str) -> str:
    """Execute a validated SQL query and return formatted results.

    Only executes SELECT statements. Includes a row limit for safety.
    """
    try:
        from sqlalchemy import text

        from app.core.constants import SQL_MAX_RESULT_ROWS, SQL_QUERY_TIMEOUT_SECONDS
        from app.database.session import get_engine

        engine = get_engine()
        async with engine.connect() as conn:
            result = await conn.execute(text(sql))
            rows = result.fetchmany(SQL_MAX_RESULT_ROWS)
            columns = list(result.keys())

            if not rows:
                return "No results found."

            # Format as table
            lines = [" | ".join(str(c) for c in columns)]
            lines.append("-" * len(lines[0]))
            for row in rows:
                lines.append(" | ".join(str(v) for v in row))

            if len(rows) == SQL_MAX_RESULT_ROWS:
                lines.append(f"\n(Results limited to {SQL_MAX_RESULT_ROWS} rows)")

            return "\n".join(lines)

    except Exception as exc:
        logger.error("SQL execution failed", error=str(exc), exc_info=True)
        return f"Query execution error: {exc}"
