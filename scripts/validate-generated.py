#!/usr/bin/env -S uv run --script
# /// script
# requires-python = ">=3.11"
# dependencies = []
# ///
"""Thin Makefile/CI wrapper around tests/integration/test_generated_artifacts.py
(IMPLEMENTATION_PLAN.md Task 5.2, SPEC.md Sec 9.3). The real assertions live
in the pytest file, per the task's own instruction to "prefer pytest for
assertions and a script wrapper for Makefile/CI" - this script exists so a
Makefile target or CI step has a single non-pytest-aware command to run.

Requires `make generate` (or `uv run scripts/generate-all.py`) to have
already populated generated/ - this script does not regenerate it, matching
the task's own acceptance section ordering (`make generate` then
`pytest -q tests/integration/test_generated_artifacts.py` as two steps).
"""

from __future__ import annotations

import subprocess
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent


def main() -> int:
    result = subprocess.run(
        ["uv", "run", "pytest", "-q", "tests/integration/test_generated_artifacts.py"],
        cwd=REPO_ROOT,
    )
    return result.returncode


if __name__ == "__main__":
    raise SystemExit(main())
