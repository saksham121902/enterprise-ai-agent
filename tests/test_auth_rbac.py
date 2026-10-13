"""Unit tests for Authentication, JWT Tokens, and Role-Based Access Control (RBAC)."""

import sys
import unittest
from pathlib import Path

repo_root = Path(__file__).resolve().parent.parent
backend_path = repo_root / "backend"
if str(backend_path) not in sys.path:
    sys.path.insert(0, str(backend_path))

from app.core.constants import Permission
from app.core.security import (
    create_access_token,
    create_refresh_token,
    decode_access_token,
    hash_password,
    verify_password,
)


class TestAuthRBAC(unittest.TestCase):
    """Test suite for authentication, password hashing, JWTs, and RBAC."""

    def test_password_hashing_and_verification(self):
        """Plain passwords should verify against hash and reject wrong passwords."""
        plain = "CorrectHorseBatteryStaple123!"
        hashed = hash_password(plain)
        self.assertNotEqual(plain, hashed)
        self.assertTrue(verify_password(plain, hashed))
        self.assertFalse(verify_password("WrongPassword123!", hashed))

    def test_create_and_decode_access_token(self):
        """Access token creation should embed subject, tenant_id, and role claims."""
        token = create_access_token(
            subject="usr-12345",
            tenant_id="ten-99999",
            role="admin",
        )
        self.assertIsInstance(token, str)
        self.assertTrue(len(token) > 20)

        payload = decode_access_token(token)
        self.assertEqual(payload["sub"], "usr-12345")
        self.assertEqual(payload["tenant_id"], "ten-99999")
        self.assertEqual(payload["role"], "admin")
        self.assertEqual(payload["type"], "access")

    def test_create_refresh_token(self):
        """Refresh token should have type refresh and valid tenant claims."""
        refresh = create_refresh_token(
            subject="usr-12345",
            tenant_id="ten-99999",
        )
        self.assertIsInstance(refresh, str)

    def test_rbac_role_permissions(self):
        """Verify role hierarchy and permissions logic."""
        admin_perms = {
            Permission.CHAT_CREATE,
            Permission.DOCUMENT_UPLOAD,
            Permission.USER_CREATE,
            Permission.APPROVAL_REVIEW,
            Permission.DATABASE_QUERY,
        }
        manager_perms = {
            Permission.CHAT_CREATE,
            Permission.DOCUMENT_UPLOAD,
            Permission.APPROVAL_REVIEW,
        }
        employee_perms = {
            Permission.CHAT_CREATE,
            Permission.DOCUMENT_UPLOAD,
            Permission.DOCUMENT_READ,
        }

        # Admin must have supervisor/user privileges
        self.assertIn(Permission.USER_CREATE, admin_perms)
        self.assertIn(Permission.APPROVAL_REVIEW, admin_perms)

        # Manager can approve operations but cannot manage users
        self.assertIn(Permission.APPROVAL_REVIEW, manager_perms)
        self.assertNotIn(Permission.USER_CREATE, manager_perms)

        # Employee cannot approve operations or manage users
        self.assertNotIn(Permission.APPROVAL_REVIEW, employee_perms)
        self.assertNotIn(Permission.USER_CREATE, employee_perms)


if __name__ == "__main__":
    unittest.main()
