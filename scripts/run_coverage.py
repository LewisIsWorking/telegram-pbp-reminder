#!/usr/bin/env python3
"""
Run tests in two phases for accurate coverage:
1. test_aaa_isolated.py first (seeds edge-case branches)
2. Full suite with --cov-append

Usage:
    python3 scripts/run_coverage.py
    python3 scripts/run_coverage.py --html  # generate HTML report
"""
import subprocess, sys, os

os.chdir(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

COV_ARGS = [
    "--cov=scripts",
    "--cov-config=.coveragerc",
]
REPORT_ARGS = ["--cov-report=term-missing"]

def run(args, extra_cov=None):
    cmd = ["python3", "-m", "pytest"] + args + COV_ARGS
    if extra_cov:
        cmd += extra_cov
    result = subprocess.run(cmd, capture_output=False)
    return result.returncode

# Phase 1: isolated edge-case tests (seed coverage)
print("=" * 60)
print("Phase 1: Isolated edge-case tests")
print("=" * 60)
rc1 = run(["scripts/test_aaa_isolated.py", "-q"], ["--cov-append"])

# Phase 2: full suite with append
print("\n" + "=" * 60)
print("Phase 2: Full test suite")
print("=" * 60)
html = ["--cov-report=html"] if "--html" in sys.argv else []
rc2 = run(["scripts/", "-q"], ["--cov-append"] + REPORT_ARGS + html)

sys.exit(rc1 or rc2)
