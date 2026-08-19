#!/usr/bin/env -S uv run --script
# /// script
# requires-python = ">=3.11"
# dependencies = ["pyyaml>=6.0"]
# ///
"""Print a compact capability coverage table (IMPLEMENTATION_PLAN.md Task
18.2): one row per upstream Modelable capability, joining `modelable
capabilities --format json` against tests/conformance/capability-coverage.yaml
- the same two data sources scripts/check-capability-coverage.py already
validates, reused here rather than re-implemented.

Run via `uv run scripts/coverage-report.py` (or `make coverage-report`).

Usage:
    uv run scripts/coverage-report.py [--out PATH]

--out PATH additionally writes the same table to PATH (e.g.
generated/capability-coverage.md for a CI artifact - not committed unless
explicitly desired, matching this task's own note).
"""

from __future__ import annotations

import argparse
import importlib.util
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent

_spec = importlib.util.spec_from_file_location(
    "check_capability_coverage", REPO_ROOT / "scripts" / "check-capability-coverage.py"
)
assert _spec is not None and _spec.loader is not None
_check = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(_check)


def build_table() -> tuple[list[tuple[str, str, str, str]], int]:
    upstream = _check.run_modelable_capabilities()
    entries = _check.load_manifest()

    rows: list[tuple[str, str, str, str]] = []
    for cap in upstream:
        key = _check.flatten_key(cap)
        entry = entries.get(key)
        coverage = entry.get("coverage", "uncovered") if isinstance(entry, dict) else "uncovered"
        rows.append((cap["category"], cap["name"], cap["status"], coverage))

    rows.sort(key=lambda r: (r[0], r[1]))
    return rows, len(upstream)


def render_table(rows: list[tuple[str, str, str, str]]) -> str:
    headers = ("CATEGORY", "CAPABILITY", "STATUS", "COVERAGE")
    widths = [
        max(len(headers[i]), *(len(row[i]) for row in rows)) if rows else len(headers[i]) for i in range(4)
    ]
    lines = ["  ".join(headers[i].ljust(widths[i]) for i in range(4))]
    for row in rows:
        lines.append("  ".join(row[i].ljust(widths[i]) for i in range(4)))
    return "\n".join(lines)


def render_markdown(rows: list[tuple[str, str, str, str]]) -> str:
    headers = ("CATEGORY", "CAPABILITY", "STATUS", "COVERAGE")
    lines = [
        "| " + " | ".join(headers) + " |",
        "|" + "|".join("---" for _ in headers) + "|",
    ]
    for row in rows:
        lines.append("| " + " | ".join(row) + " |")
    return "\n".join(lines)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--out", type=Path, help="also write the table as a Markdown file to this path")
    args = parser.parse_args(argv)

    rows, total = build_table()
    print(render_table(rows))
    print(f"\n{len(rows)}/{total} upstream capabilities listed.")

    if args.out:
        args.out.parent.mkdir(parents=True, exist_ok=True)
        args.out.write_text(
            "# Capability coverage report\n\n"
            f"{len(rows)}/{total} upstream capabilities listed.\n\n" + render_markdown(rows) + "\n",
            encoding="utf-8",
        )
        try:
            display_path = args.out.resolve().relative_to(REPO_ROOT)
        except ValueError:
            display_path = args.out
        print(f"\nWrote {display_path}", file=sys.stderr)

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
