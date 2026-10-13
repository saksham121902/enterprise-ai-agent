"""Unit tests for SQL Agent safety validator and AST query inspection."""

import sys
import unittest
from pathlib import Path

# Add backend to path
repo_root = Path(__file__).resolve().parent.parent
backend_path = repo_root / "backend"
if str(backend_path) not in sys.path:
    sys.path.insert(0, str(backend_path))

from app.agents.sql_validator import (
    validate_sql_safety,
)


class TestSQLValidator(unittest.TestCase):
    """Test suite for database security and SQL safety guardrails."""

    def test_safe_select_query_allowed(self):
        """Analytical SELECT queries on allowed tables should pass."""
        sql = "SELECT id, email, username FROM users WHERE is_active = true"
        result = validate_sql_safety(sql)
        self.assertEqual(result["status"], "allowed")
        self.assertEqual(result["statement_type"], "SELECT")
        self.assertIn("LIMIT 1000", result["sanitized_sql"])

    def test_cte_with_query_allowed(self):
        """WITH common table expressions should pass."""
        sql = "WITH active_chats AS (SELECT id FROM chats) SELECT COUNT(*) FROM active_chats"
        result = validate_sql_safety(sql)
        self.assertEqual(result["status"], "allowed")
        self.assertEqual(result["statement_type"], "WITH")

    def test_automatic_row_limit_enforced(self):
        """Queries without LIMIT should have default LIMIT 1000 appended."""
        sql = "SELECT * FROM documents"
        result = validate_sql_safety(sql)
        self.assertEqual(result["status"], "allowed")
        self.assertTrue(result["sanitized_sql"].endswith("LIMIT 1000"))

    def test_excessive_limit_capped(self):
        """LIMIT clauses exceeding 1000 should be capped to 1000."""
        sql = "SELECT * FROM chats LIMIT 50000"
        result = validate_sql_safety(sql)
        self.assertEqual(result["status"], "allowed")
        self.assertIn("LIMIT 1000", result["sanitized_sql"])

    def test_disallowed_table_blocked(self):
        """Queries accessing tables not in the allow-list must be blocked."""
        sql = "SELECT * FROM secret_financial_records"
        result = validate_sql_safety(sql)
        self.assertEqual(result["status"], "blocked")
        self.assertIn("not permitted", result["reason"])

    def test_system_catalogs_blocked(self):
        """Queries probing postgres metadata catalogs must be blocked."""
        sql = "SELECT * FROM pg_catalog.pg_tables"
        result = validate_sql_safety(sql)
        self.assertEqual(result["status"], "blocked")

    def test_write_operations_require_approval(self):
        """UPDATE, DELETE, INSERT queries must trigger human approval workflow."""
        writes = [
            "UPDATE users SET is_active = false WHERE id = 'abc'",
            "DELETE FROM chats WHERE is_archived = true",
            "INSERT INTO tenants (id, name, slug) VALUES ('1', 'Org', 'org')",
        ]
        for query in writes:
            result = validate_sql_safety(query)
            self.assertEqual(
                result["status"],
                "requires_approval",
                f"Failed for query: {query}",
            )

    def test_destructive_ddl_blocked(self):
        """DROP, TRUNCATE, ALTER, GRANT must be strictly blocked."""
        destructives = [
            "DROP TABLE users",
            "TRUNCATE TABLE chats",
            "ALTER TABLE documents DROP COLUMN file_path",
            "GRANT ALL PRIVILEGES ON ALL TABLES TO public",
            "REVOKE ALL ON users FROM admin",
        ]
        for query in destructives:
            result = validate_sql_safety(query)
            self.assertEqual(
                result["status"],
                "blocked",
                f"Destructive query was not blocked: {query}",
            )

    def test_multi_statement_chaining_blocked(self):
        """Statement chaining (injection evasion) must be detected and blocked."""
        chained = "SELECT 1 FROM users; DROP TABLE chats;"
        result = validate_sql_safety(chained)
        self.assertEqual(result["status"], "blocked")
        self.assertIn("Multiple SQL statements", result["reason"])

    def test_empty_sql_handled_safely(self):
        """Empty or whitespace-only SQL queries should be safely rejected."""
        result = validate_sql_safety("   ")
        self.assertEqual(result["status"], "blocked")


if __name__ == "__main__":
    unittest.main()
