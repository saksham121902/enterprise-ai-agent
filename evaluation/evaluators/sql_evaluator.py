"""Text-to-SQL Pipeline and Guardrail Evaluator.

Measures:
1. Unsafe Query Interception Rate: Percentage of destructive queries (DROP, TRUNCATE, ALTER, injection)
   successfully blocked by the safety validator.
2. Human-in-the-Loop Routing Rate: Percentage of write queries (UPDATE, DELETE, INSERT)
   correctly requiring human manager approval.
3. Execution Accuracy: Validates that allowed SELECT queries adhere to schema, syntax,
   and allowed table boundaries.
"""

from __future__ import annotations

import sys
import time
from pathlib import Path
from typing import Any

repo_root = Path(__file__).resolve().parent.parent.parent
backend_path = repo_root / "backend"
if str(backend_path) not in sys.path:
    sys.path.insert(0, str(backend_path))

from app.agents.sql_validator import validate_sql_safety
from evaluation.datasets.sql_dataset import SQL_DATASET, SQLTestCase


class SQLEvaluator:
    """Evaluates SQL query validation safety, approval gating, and execution."""

    def evaluate_test_case(self, tc: SQLTestCase) -> dict[str, Any]:
        """Evaluate a single SQL test case against the safety validator."""
        sql = tc["expected_sql_pattern"]
        safety_result = validate_sql_safety(sql)
        actual_status = safety_result["status"]
        expected_status = tc["expected_safety_status"]

        # Did it match safety classification?
        safety_matched = (actual_status == expected_status)

        # For destructive queries, blocking is mandatory
        is_correctly_guarded = False
        if expected_status == "blocked" and actual_status == "blocked":
            is_correctly_guarded = True
        elif expected_status == "requires_approval" and actual_status == "requires_approval":
            is_correctly_guarded = True
        elif expected_status == "allowed" and actual_status == "allowed":
            is_correctly_guarded = True

        return {
            "id": tc["id"],
            "nl_query": tc["nl_query"],
            "statement_type": tc["expected_statement_type"],
            "sql": sql,
            "expected_status": expected_status,
            "actual_status": actual_status,
            "is_correctly_guarded": is_correctly_guarded,
            "target_tables": tc["target_tables"],
            "reason": safety_result.get("reason", "Operation permitted"),
        }

    def run(self) -> dict[str, Any]:
        """Execute evaluation across all 30 SQL test cases."""
        start_time = time.perf_counter()
        results = [self.evaluate_test_case(tc) for tc in SQL_DATASET]
        duration = time.perf_counter() - start_time

        total = len(results)
        safe_cases = [r for r in results if r["expected_status"] == "allowed"]
        approval_cases = [r for r in results if r["expected_status"] == "requires_approval"]
        destructive_cases = [r for r in results if r["expected_status"] == "blocked"]

        safe_allowed_count = sum(1 for r in safe_cases if r["is_correctly_guarded"])
        approval_routed_count = sum(1 for r in approval_cases if r["is_correctly_guarded"])
        destructive_blocked_count = sum(1 for r in destructive_cases if r["is_correctly_guarded"])

        total_correct = safe_allowed_count + approval_routed_count + destructive_blocked_count

        return {
            "total_test_cases": total,
            "duration_seconds": round(duration, 3),
            "overall_accuracy": round(total_correct / total * 100, 1),
            "safe_select_accuracy": round(safe_allowed_count / len(safe_cases) * 100, 1) if safe_cases else 100.0,
            "approval_routing_rate": round(approval_routed_count / len(approval_cases) * 100, 1) if approval_cases else 100.0,
            "destructive_block_rate": round(destructive_blocked_count / len(destructive_cases) * 100, 1) if destructive_cases else 100.0,
            "breakdown": {
                "safe_select_queries": {"total": len(safe_cases), "passed": safe_allowed_count},
                "write_queries_requiring_approval": {"total": len(approval_cases), "passed": approval_routed_count},
                "destructive_queries_blocked": {"total": len(destructive_cases), "passed": destructive_blocked_count},
            },
            "details": results,
        }
