"""Test Suite Runner — executes all unit tests and outputs pass/fail metrics.

Usage::

    python -m tests.run_tests
    # or
    pytest tests/
"""

from __future__ import annotations

import sys
import time
import unittest
from pathlib import Path

repo_root = Path(__file__).resolve().parent.parent
backend_path = repo_root / "backend"
if str(backend_path) not in sys.path:
    sys.path.insert(0, str(backend_path))


def run_tests() -> bool:
    """Discover and execute all unit tests."""
    print("=" * 72)
    print("🧪 RUNNING UNIT & SECURITY GUARDRAIL TEST SUITE")
    print("=" * 72)

    loader = unittest.TestLoader()
    suite = loader.discover(str(repo_root / "tests"), pattern="test_*.py")

    start_time = time.perf_counter()
    runner = unittest.TextTestRunner(verbosity=2)
    result = runner.run(suite)
    duration = time.perf_counter() - start_time

    print("\n" + "=" * 72)
    print(f"📊 Test Results Summary:")
    print(f"   Total Tests Run: {result.testsRun}")
    print(f"   Passed:          {result.testsRun - len(result.failures) - len(result.errors)}")
    print(f"   Failures:        {len(result.failures)}")
    print(f"   Errors:          {len(result.errors)}")
    print(f"   Duration:        {duration:.3f}s")
    print(f"   Status:          {'✅ ALL PASSED' if result.wasSuccessful() else '❌ FAILED'}")
    print("=" * 72)

    return result.wasSuccessful()


if __name__ == "__main__":
    success = run_tests()
    sys.exit(0 if success else 1)
