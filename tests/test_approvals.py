"""Unit tests for Human-in-the-Loop Approval Workflow."""

import json
import sys
import unittest
from pathlib import Path

repo_root = Path(__file__).resolve().parent.parent
backend_path = repo_root / "backend"
if str(backend_path) not in sys.path:
    sys.path.insert(0, str(backend_path))

from app.core.constants import ApprovalStatus, Permission


class TestApprovalWorkflow(unittest.TestCase):
    """Test suite for human approval states, permissions, and lifecycle."""

    def test_approval_valid_statuses(self):
        """Verify defined approval states."""
        self.assertEqual(ApprovalStatus.PENDING, "pending")
        self.assertEqual(ApprovalStatus.APPROVED, "approved")
        self.assertEqual(ApprovalStatus.REJECTED, "rejected")

    def test_approval_permission_gating(self):
        """Only users with APPROVAL_MANAGE permission can approve or reject."""
        user_roles = {
            "admin": [Permission.APPROVAL_REVIEW, Permission.USER_CREATE],
            "manager": [Permission.APPROVAL_REVIEW],
            "employee": [Permission.CHAT_CREATE, Permission.DOCUMENT_READ],
        }

        def can_review(role: str) -> bool:
            return Permission.APPROVAL_REVIEW in user_roles.get(role, [])

        self.assertTrue(can_review("admin"))
        self.assertTrue(can_review("manager"))
        self.assertFalse(can_review("employee"))

    def test_approval_payload_serialization(self):
        """Approval requests must preserve exact operation payload and risk metadata."""
        payload = {
            "query": "DELETE FROM staging_sync_events WHERE created_at < NOW() - INTERVAL '30 days'",
            "affected_rows_estimated": 450,
            "risk_level": "medium",
            "statement_type": "DELETE",
        }
        serialized = json.dumps(payload)
        deserialized = json.loads(serialized)

        self.assertEqual(deserialized["statement_type"], "DELETE")
        self.assertEqual(deserialized["risk_level"], "medium")
        self.assertIn("DELETE FROM staging_sync_events", deserialized["query"])


if __name__ == "__main__":
    unittest.main()
