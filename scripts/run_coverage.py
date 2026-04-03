#!/usr/bin/env python3
"""
Two-phase coverage measurement using separate processes to avoid module caching.

Phase 1: run test_aaa_isolated.py in its own process (seeds edge-case branches)
Phase 2: run full suite in its own process with --cov-append

Each phase starts fresh, so module imports don't shadow earlier patches.

Usage:
    python3 scripts/run_coverage.py
    python3 scripts/run_coverage.py --html
"""
import subprocess, sys, os

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
os.chdir(ROOT)

COVRC = "--cov-config=.coveragerc"


def phase(label, test_args, append=False, report=False, html=False):
    print(f"\n{'='*60}\n{label}\n{'='*60}")
    cmd = (
        ["python3", "-m", "pytest"]
        + test_args
        + [f"--cov=scripts", COVRC]
        + (["--cov-append"] if append else [])
        + (["--cov-report=term-missing"] if report else ["--cov-report="])
        + (["--cov-report=html"] if html else [])
        + ["-q"]
    )
    return subprocess.run(cmd).returncode


rc1 = phase("Phase 1 — isolated edge-case tests",
            ["scripts/test_aaa_isolated.py"],
            append=False, report=False)

html = "--html" in sys.argv
rc2 = phase("Phase 2 — full test suite",
            ["scripts/"],
            append=True, report=True, html=html)

sys.exit(rc1 or rc2)

