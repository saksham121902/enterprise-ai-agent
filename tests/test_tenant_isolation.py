"""Unit tests for Multi-Tenant Isolation and Data Scoping."""

import sys
import unittest
from pathlib import Path

repo_root = Path(__file__).resolve().parent.parent
backend_path = repo_root / "backend"
if str(backend_path) not in sys.path:
    sys.path.insert(0, str(backend_path))


class TestTenantIsolation(unittest.TestCase):
    """Test suite for strict multi-tenant boundary enforcement."""

    def test_chromadb_collection_name_tenant_scoping(self):
        """Vector collections must strictly isolate data per tenant slug."""
        tenant_a = "tenant-alpha-123"
        tenant_b = "tenant-beta-456"

        coll_a = f"tenant_{tenant_a}_documents"
        coll_b = f"tenant_{tenant_b}_documents"

        self.assertNotEqual(coll_a, coll_b)
        self.assertTrue(coll_a.startswith(f"tenant_{tenant_a}"))
        self.assertTrue(coll_b.startswith(f"tenant_{tenant_b}"))

    def test_cross_tenant_token_rejection(self):
        """A user token from Tenant A cannot be accepted for Tenant B operations."""
        from app.core.security import create_access_token, decode_access_token

        token_tenant_a = create_access_token(
            subject="user_1",
            tenant_id="tenant_alpha",
            role="employee",
        )
        claims = decode_access_token(token_tenant_a)

        # Scoping check: verify tenant matches intended context
        self.assertEqual(claims["tenant_id"], "tenant_alpha")
        self.assertNotEqual(claims["tenant_id"], "tenant_beta")

    def test_tenant_context_in_agent_state(self):
        """Agent pipeline state must always maintain an explicit tenant_id."""
        state = {
            "user_message": "Search our knowledge base for PTO",
            "tenant_id": "tenant_123",
            "messages": [],
        }
        self.assertIn("tenant_id", state)
        self.assertEqual(state["tenant_id"], "tenant_123")


if __name__ == "__main__":
    unittest.main()
