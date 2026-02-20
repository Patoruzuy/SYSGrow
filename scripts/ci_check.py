#!/usr/bin/env python
"""
SYSGrow CI — lint + test pipeline.

Usage (from repo root):
    python scripts/ci_check.py          # full pipeline
    python scripts/ci_check.py --lint   # lint only
    python scripts/ci_check.py --test   # test only

Exit code 0 = all green, non-zero = something failed.
"""

from __future__ import annotations

import argparse
import subprocess
import sys
from pathlib import Path

REPO = Path(__file__).resolve().parent.parent


def _run(cmd: list[str], label: str) -> bool:
    """Run *cmd* inside the repo root; return True on success."""
    sep = "=" * 60
    print(f"\n{sep}\n  {label}\n{sep}\n")
    result = subprocess.run(cmd, cwd=str(REPO))
    ok = result.returncode == 0
    status = "PASS" if ok else "FAIL"
    print(f"\n  {label}: {status}  (exit {result.returncode})\n")
    return ok


def lint() -> bool:
    """Run ruff check on the entire codebase."""
    return _run(
        [sys.executable, "-m", "ruff", "check", "."],
        "Ruff lint",
    )


def test() -> bool:
    """Run pytest with coverage on the test suite."""
    return _run(
        [
            sys.executable,
            "-m",
            "pytest",
            "tests/",
            "--tb=short",
            "-q",
            "--cov=app",
            "--cov=infrastructure",
            "--cov-report=term-missing:skip-covered",
            "--cov-fail-under=5",
        ],
        "Pytest + coverage",
    )


def main() -> int:
    ap = argparse.ArgumentParser(description="SYSGrow CI pipeline")
    ap.add_argument("--lint", action="store_true", help="Run lint only")
    ap.add_argument("--test", action="store_true", help="Run tests only")
    args = ap.parse_args()

    # Default: run everything
    run_lint = args.lint or (not args.lint and not args.test)
    run_test = args.test or (not args.lint and not args.test)

    results: list[bool] = []

    if run_lint:
        results.append(lint())
    if run_test:
        results.append(test())

    all_ok = all(results)
    banner = "ALL CHECKS PASSED" if all_ok else "SOME CHECKS FAILED"
    print(f"\n{'=' * 60}\n  {banner}\n{'=' * 60}")
    return 0 if all_ok else 1


if __name__ == "__main__":
    raise SystemExit(main())
