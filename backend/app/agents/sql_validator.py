"""SQL safety validation engine with Abstract Syntax Tree (AST) parsing.

Enforces comprehensive database guardrails:
1. AST parsing via sqlglot (with standard-library fallback)
2. Single-statement enforcement (prevents query chaining / compound injection)
3. Strict statement type inspection (SELECT only for direct execution)
4. Table allow-listing: queries can only access registered application tables
5. Read-only direct execution: INSERT/UPDATE/DELETE require human approval
6. Strict blocking of DDL/destructive commands (DROP, TRUNCATE, ALTER, GRANT, etc.)
7. Enforces or auto-appends row limits (LIMIT 1000 max)
"""

from __future__ import annotations

import re
from typing import Any

from app.core.constants import (
    SQL_ALLOWED_STATEMENTS,
    SQL_APPROVAL_REQUIRED_STATEMENTS,
    SQL_BLOCKED_STATEMENTS,
    SQL_MAX_RESULT_ROWS,
)

# Table allow-list: only these tables can be queried by the operations agent
ALLOWED_TABLES: frozenset[str] = frozenset({
    "users",
    "chats",
    "messages",
    "documents",
    "tenants",
    "approvals",
    "memories",
    "cost_tracking",
    "roles",
    "workflows",
    "workflow_steps",
    "audit_logs",
})

# Columns containing sensitive credentials that must not be exposed via text-to-sql
BLOCKED_COLUMNS: frozenset[str] = frozenset({
    "password_hash",
    "hashed_password",
    "secret_key",
    "jwt_secret",
    "private_key",
    "access_token",
    "refresh_token",
})

# Destructive operations that are strictly prohibited
DESTRUCTIVE_KEYWORDS: frozenset[str] = frozenset({
    "DROP",
    "TRUNCATE",
    "ALTER",
    "GRANT",
    "REVOKE",
    "CREATE",
    "EXEC",
    "EXECUTE",
    "COPY",
    "VACUUM",
})


def _extract_tables_ast(sql: str) -> set[str]:
    """Extract referenced table names using sqlglot AST or fallback regex."""
    try:
        import sqlglot
        from sqlglot import exp

        parsed = sqlglot.parse_one(sql)
        tables = {
            t.name.lower()
            for t in parsed.find_all(exp.Table)
            if t.name
        }
        return tables
    except Exception:
        # Fallback regex parser for table extraction
        clean_sql = re.sub(r"--.*$", "", sql, flags=re.MULTILINE)
        clean_sql = re.sub(r"/\*.*?\*/", "", clean_sql, flags=re.DOTALL)
        matches = re.findall(
            r"\b(?:FROM|JOIN|UPDATE|INTO|TABLE)\s+([a-zA-Z_][a-zA-Z0-9_]*)",
            clean_sql,
            flags=re.IGNORECASE,
        )
        return {m.lower() for m in matches}


def validate_sql_safety(sql: str) -> dict[str, Any]:
    """Validate candidate SQL query safety using AST and semantic inspection.

    Args:
        sql: The candidate SQL query string.

    Returns:
        Dict with:
        - status: 'allowed', 'requires_approval', or 'blocked'
        - statement_type: SQL operation keyword
        - target_tables: List of extracted tables
        - sanitized_sql: Query with safety LIMIT enforced
        - reason: Explanation if blocked or requiring approval
    """
    if not sql or not sql.strip():
        return {
            "status": "blocked",
            "statement_type": "NONE",
            "target_tables": [],
            "sanitized_sql": "",
            "reason": "No SQL query was provided",
        }

    raw_sql = sql.strip().rstrip(";")
    # Strip comments for structure analysis
    clean_sql = re.sub(r"--.*$", "", raw_sql, flags=re.MULTILINE)
    clean_sql = re.sub(r"/\*.*?\*/", "", clean_sql, flags=re.DOTALL).strip()
    sql_upper = clean_sql.upper()

    # 1. Multi-statement chaining check (e.g., "SELECT 1; DROP TABLE users")
    statements = [s.strip() for s in clean_sql.split(";") if s.strip()]
    if len(statements) > 1:
        return {
            "status": "blocked",
            "statement_type": "MULTI_STATEMENT",
            "target_tables": [],
            "sanitized_sql": "",
            "reason": "Multiple SQL statements in a single query are forbidden (statement chaining)",
        }

    # 2. Check for destructive keywords anywhere in query
    for destructive in DESTRUCTIVE_KEYWORDS:
        if re.search(rf"\b{destructive}\b", sql.upper()):
            return {
                "status": "blocked",
                "statement_type": destructive,
                "target_tables": [],
                "sanitized_sql": "",
                "reason": f"Destructive operation '{destructive}' is prohibited by safety policy",
            }

    # 3. Check for restricted sensitive credential columns
    for col in BLOCKED_COLUMNS:
        if re.search(rf"\b{col}\b", clean_sql, flags=re.IGNORECASE):
            return {
                "status": "blocked",
                "statement_type": "CREDENTIAL_HARVESTING",
                "target_tables": [],
                "sanitized_sql": "",
                "reason": f"Access to sensitive credential column '{col}' is strictly forbidden",
            }

    # 3. Determine primary statement type
    first_word = sql_upper.split()[0] if sql_upper.split() else ""

    # Check against blocked list
    if first_word in SQL_BLOCKED_STATEMENTS:
        return {
            "status": "blocked",
            "statement_type": first_word,
            "target_tables": [],
            "sanitized_sql": "",
            "reason": f"Statement type '{first_word}' is blocked by security policy",
        }

    # 4. Extract tables and verify against ALLOWED_TABLES
    extracted_tables = _extract_tables_ast(raw_sql)
    cte_aliases = {
        c.lower()
        for c in re.findall(
            r"\b(?:WITH|,)\s+([a-zA-Z_][a-zA-Z0-9_]*)\s+AS\s*\(",
            raw_sql,
            flags=re.IGNORECASE,
        )
    }
    if extracted_tables:
        physical_tables = extracted_tables - cte_aliases
        disallowed = physical_tables - ALLOWED_TABLES
        if disallowed:
            return {
                "status": "blocked",
                "statement_type": first_word,
                "target_tables": sorted(extracted_tables),
                "sanitized_sql": "",
                "reason": f"Access to table(s) {sorted(disallowed)} is not permitted. Only application tables may be queried.",
            }

    # 5. DML Write queries require Human Approval
    if first_word in SQL_APPROVAL_REQUIRED_STATEMENTS:
        return {
            "status": "requires_approval",
            "statement_type": first_word,
            "target_tables": sorted(extracted_tables),
            "sanitized_sql": raw_sql,
            "reason": f"{first_word} operations modify database state and require human approval before execution",
        }

    # 6. Read-only queries (SELECT, WITH)
    if first_word in SQL_ALLOWED_STATEMENTS:
        # Enforce row limit
        sanitized_sql = raw_sql
        if "LIMIT" not in sql_upper:
            sanitized_sql = f"{raw_sql} LIMIT {SQL_MAX_RESULT_ROWS}"
        else:
            # Check existing limit value
            limit_match = re.search(r"\bLIMIT\s+(\d+)", sql_upper)
            if limit_match and int(limit_match.group(1)) > SQL_MAX_RESULT_ROWS:
                sanitized_sql = re.sub(
                    r"\bLIMIT\s+\d+",
                    f"LIMIT {SQL_MAX_RESULT_ROWS}",
                    raw_sql,
                    flags=re.IGNORECASE,
                )

        return {
            "status": "allowed",
            "statement_type": first_word,
            "target_tables": sorted(extracted_tables),
            "sanitized_sql": sanitized_sql,
            "reason": "Operation permitted",
        }

    # Default fallback: unknown statement types are blocked
    return {
        "status": "blocked",
        "statement_type": first_word,
        "target_tables": sorted(extracted_tables),
        "sanitized_sql": "",
        "reason": f"Statement type '{first_word}' is not recognized or permitted",
    }
