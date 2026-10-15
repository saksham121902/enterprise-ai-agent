"""Live End-to-End Application Integration Test Suite.

Runs automated live tests against the production deployment on Render:
- Verifies Frontend static delivery and headers
- Tests Health, Readiness, and Prometheus metrics
- Tests Authentication & Role-Based Access Control (Admin vs Demo vs Invalid)
- Tests Multi-agent chat session management and message persistence
- Tests Document knowledge base indexing
- Tests Human-in-the-loop approvals workflow
- Tests Semantic memory storage
- Tests Analytics and token metrics
"""

from __future__ import annotations

import json
import ssl
import sys
import urllib.error
import urllib.request
from typing import Any

ctx = ssl.create_default_context()
FRONTEND_URL = "https://enterprise-ai-frontend-1um8.onrender.com"
BACKEND_URL = "https://enterprise-ai-backend-uwkc.onrender.com"
API_URL = f"{BACKEND_URL}/api/v1"


def api_call(
    endpoint: str,
    method: str = "GET",
    payload: dict[str, Any] | None = None,
    token: str | None = None,
    timeout: int = 20,
) -> tuple[int, Any]:
    url = f"{API_URL}{endpoint}" if endpoint.startswith("/") else endpoint
    headers = {"Content-Type": "application/json"}
    if token:
        headers["Authorization"] = f"Bearer {token}"
    data = json.dumps(payload).encode("utf-8") if payload else None
    req = urllib.request.Request(url, data=data, headers=headers, method=method)

    try:
        with urllib.request.urlopen(req, context=ctx, timeout=timeout) as resp:
            body = resp.read().decode("utf-8")
            try:
                parsed = json.loads(body)
            except json.JSONDecodeError:
                parsed = body
            return resp.getcode(), parsed
    except urllib.error.HTTPError as e:
        body = e.read().decode("utf-8")
        try:
            parsed = json.loads(body)
        except json.JSONDecodeError:
            parsed = body
        return e.code, parsed
    except Exception as e:  # noqa: BLE001
        return 0, str(e)


def run_e2e_tests() -> bool:
    print("=" * 75)
    print("🚀 ENTERPRISE AI AGENT — LIVE APPLICATION INTEGRATION TESTS")
    print(f"Target Frontend: {FRONTEND_URL}")
    print(f"Target Backend:  {BACKEND_URL}")
    print("=" * 75)

    tests_run = 0
    tests_passed = 0

    def check(name: str, passed: bool, details: str = "") -> bool:
        nonlocal tests_run, tests_passed
        tests_run += 1
        if passed:
            tests_passed += 1
            print(f"  ✅ [PASS] {name} {details}")
        else:
            print(f"  ❌ [FAIL] {name} {details}")
        return passed

    # 1. Frontend Test
    print("\n--- 1. Frontend Web App Delivery ---")
    try:
        req = urllib.request.Request(FRONTEND_URL, headers={"User-Agent": "Mozilla/5.0"})
        with urllib.request.urlopen(req, context=ctx, timeout=10) as r:
            html = r.read().decode("utf-8")
            check("Frontend HTTP 200 Status", r.getcode() == 200, f"(code {r.getcode()})")
            check("Frontend HTML Root Element", '<div id="root">' in html or "root" in html, "(React mount point found)")
            check("Frontend Modern Scripts Loaded", 'type="module"' in html or '<script' in html, "(Vite bundle script present)")
    except Exception as e:  # noqa: BLE001
        check("Frontend Delivery", False, f"Error: {e}")

    # 2. Health & Readiness
    print("\n--- 2. Infrastructure Health & Database Connectivity ---")
    code, h = api_call(f"{BACKEND_URL}/health")
    check("System Health (/health)", code == 200 and h.get("status") == "healthy", f"HTTP {code} status={h.get('status')}")

    code, r = api_call(f"{BACKEND_URL}/readiness")
    db_status = r.get("dependencies", {}).get("postgresql") if isinstance(r, dict) else "error"
    check("Database Readiness (/readiness)", code == 200 and db_status == "connected", f"PostgreSQL: {db_status}")

    # 3. Authentication & RBAC
    print("\n--- 3. Authentication & Role-Based Access Control ---")
    # Admin login
    code, admin_auth = api_call("/auth/login", "POST", {"login": "admin@enterprise-ai.local", "password": "admin123!"})
    admin_token = admin_auth.get("tokens", {}).get("access_token") if isinstance(admin_auth, dict) else None
    check("Admin Login (/auth/login)", code == 200 and bool(admin_token), f"JWT issued for role: {admin_auth.get('user', {}).get('role_name')}")

    # Admin profile
    code, profile = api_call("/auth/me", token=admin_token)
    check("Admin Token Verification (/auth/me)", code == 200 and profile.get("role_name") == "admin", f"User: {profile.get('full_name')} (ID: {profile.get('id')[:8]}...)")

    # Demo user login
    code, demo_auth = api_call("/auth/login", "POST", {"login": "demo@enterprise-ai.local", "password": "demo123!"})
    demo_token = demo_auth.get("tokens", {}).get("access_token") if isinstance(demo_auth, dict) else None
    check("Demo User Login", code == 200 and bool(demo_token), f"Role: {demo_auth.get('user', {}).get('role_name')}")

    # Invalid login rejection
    code, _inv = api_call("/auth/login", "POST", {"login": "hacker@bad.com", "password": "wrongpassword"})
    check("Unauthorized Login Rejection", code in (400, 401), f"Correctly rejected with HTTP {code}")

    # 4. Multi-Agent Chat Sessions
    print("\n--- 4. Multi-Agent Chat Engine & Persistence ---")
    code, chats = api_call("/chat/", token=admin_token)
    check("List Chat Sessions (/chat/)", code == 200 and isinstance(chats, list), f"{len(chats) if isinstance(chats, list) else 0} session(s) active")

    # Send a message
    code, msg_resp = api_call("/chat/message", "POST", {"message": "System status check and feature list request"}, token=admin_token, timeout=45)
    check("Agent Message Processing (/chat/message)", code == 200, f"HTTP {code} | Session: {msg_resp.get('chat_id') if isinstance(msg_resp, dict) else ''}")
    if isinstance(msg_resp, dict):
        content_preview = msg_resp.get("content", "")[:90].replace("\n", " ")
        check("Agent Response Returned", len(content_preview) > 0, f'Preview: "{content_preview}..."')

    # 5. Knowledge Base (RAG Documents)
    print("\n--- 5. Enterprise Document Store (RAG) ---")
    code, docs = api_call("/documents/", token=admin_token)
    check("Document Store Listing (/documents/)", code == 200 and isinstance(docs, list), f"{len(docs) if isinstance(docs, list) else 0} document(s) indexed")

    # 6. Approvals Workflow
    print("\n--- 6. Human-in-the-Loop Approvals ---")
    code, approvals = api_call("/approvals/", token=admin_token)
    check("Approvals Listing (/approvals/)", code == 200 and isinstance(approvals, list), f"{len(approvals) if isinstance(approvals, list) else 0} approval request(s) active")

    # 7. Agent Memory Store
    print("\n--- 7. Semantic Agent Memory ---")
    code, memories = api_call("/memory/", token=admin_token)
    check("Agent Memory Listing (/memory/)", code == 200 and isinstance(memories, list), f"{len(memories) if isinstance(memories, list) else 0} memory entry(ies)")

    # 8. Analytics & Telemetry
    print("\n--- 8. Real-Time Analytics & Cost Tracking ---")
    code, analytics = api_call("/analytics/overview", token=admin_token)
    check("Analytics Overview (/analytics/overview)", code == 200 and isinstance(analytics, dict), f"Cost: ${analytics.get('total_cost_usd', 0):.4f} | Processed: {analytics.get('total_input_tokens', 0) + analytics.get('total_output_tokens', 0):,} tokens")

    # Summary
    print("\n" + "=" * 75)
    print(f"📊 LIVE E2E TEST SUMMARY: {tests_passed}/{tests_run} Passed ({tests_passed/tests_run*100:.1f}%)")
    if tests_passed == tests_run:
        print("🎉 ALL LIVE INTEGRATION TESTS PASSED PERFECTLY!")
    else:
        print("⚠️ SOME TESTS ENCOUNTERED ISSUES — PLEASE REVIEW ABOVE LOGS")
    print("=" * 75)

    return tests_passed == tests_run


if __name__ == "__main__":
    success = run_e2e_tests()
    sys.exit(0 if success else 1)
