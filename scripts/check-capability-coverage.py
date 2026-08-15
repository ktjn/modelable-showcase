#!/usr/bin/env -S uv run --script
# /// script
# requires-python = ">=3.11"
# dependencies = ["pyyaml>=6.0"]
# ///
"""Fail visibly when tests/conformance/capability-coverage.yaml drifts from
what the pinned/canary `modelable capabilities --format json` actually
reports. See IMPLEMENTATION_PLAN.md Task 1.3 and SPEC.md Sec 8.

Run via `uv run scripts/check-capability-coverage.py` (or plain
`python3 scripts/check-capability-coverage.py` once PyYAML is available on
that interpreter) - the inline script metadata above lets `uv run` provision
PyYAML on the fly without a project-wide dependency file.

Two enforcement levels:

- Always enforced: manifest *authoring* mistakes - an entry with no matching
  upstream capability (unless explicitly marked historical), an invalid
  `coverage` value, `excluded` without a `reason`, or a `test` path that does
  not exist. These indicate the manifest itself is wrong, independent of how
  much of the showcase has been built yet.
- Enforced only under --strict (Task 17.1 turns this on for good): upstream
  capabilities with no manifest entry at all, and coverage classifications
  that disagree with upstream's implemented/deferred status. Early in the
  showcase's implementation almost every capability is legitimately
  uncovered - that is a gap to report, not yet a failure.
"""

from __future__ import annotations

import argparse
import json
import subprocess
import sys
from pathlib import Path

import yaml

REPO_ROOT = Path(__file__).resolve().parent.parent
MANIFEST_PATH = REPO_ROOT / "tests/conformance/capability-coverage.yaml"
ALLOWED_COVERAGE = {"product", "probe", "fixture", "deferred", "excluded"}


def run_modelable_capabilities() -> list[dict]:
    try:
        proc = subprocess.run(
            ["modelable", "capabilities", "--format", "json"],
            capture_output=True,
            text=True,
            check=True,
        )
    except FileNotFoundError:
        print(
            "check-capability-coverage.py: 'modelable' is not on PATH. "
            "Run 'make bootstrap' (or 'source scripts/modelable-env.sh') first.",
            file=sys.stderr,
        )
        raise SystemExit(1)
    except subprocess.CalledProcessError as exc:
        print(f"check-capability-coverage.py: 'modelable capabilities --format json' failed:\n{exc.stderr}", file=sys.stderr)
        raise SystemExit(1)
    return json.loads(proc.stdout)


def flatten_key(cap: dict) -> str:
    return f"{cap['category']}:{cap['name']}"


def load_manifest() -> dict[str, dict]:
    if not MANIFEST_PATH.exists():
        return {}
    with MANIFEST_PATH.open() as f:
        data = yaml.safe_load(f) or {}
    return data.get("capabilities") or {}


def resolve_test_path(test_ref: str) -> Path:
    # "tests/integration/test_x.py::test_y" -> tests/integration/test_x.py
    return REPO_ROOT / test_ref.split("::", 1)[0]


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument(
        "--strict",
        action="store_true",
        help="also fail on upstream capabilities with no manifest entry and on "
        "coverage/status mismatches (enabled permanently starting Task 17.1)",
    )
    args = parser.parse_args(argv)

    upstream = run_modelable_capabilities()
    upstream_by_key = {flatten_key(c): c for c in upstream}
    entries = load_manifest()

    hard_errors: list[str] = []
    strict_gaps: list[str] = []

    for key, entry in entries.items():
        if not isinstance(entry, dict):
            hard_errors.append(f"{key}: manifest entry must be a mapping, got {type(entry).__name__}")
            continue

        coverage = entry.get("coverage")
        if coverage not in ALLOWED_COVERAGE:
            hard_errors.append(f"{key}: invalid coverage '{coverage}' (allowed: {sorted(ALLOWED_COVERAGE)})")
            continue

        if coverage == "excluded" and not str(entry.get("reason", "")).strip():
            hard_errors.append(f"{key}: coverage 'excluded' requires a non-empty 'reason'")

        test_ref = entry.get("test")
        if coverage != "excluded" and not str(test_ref or "").strip():
            hard_errors.append(f"{key}: coverage '{coverage}' requires a non-empty 'test' reference")
        elif test_ref and ("/" in test_ref):
            test_path = resolve_test_path(test_ref)
            if not test_path.exists():
                hard_errors.append(f"{key}: referenced test path does not exist: {test_path.relative_to(REPO_ROOT)}")

        if key not in upstream_by_key:
            if not entry.get("historical"):
                hard_errors.append(
                    f"{key}: no matching upstream capability - remove this entry, or set "
                    f"'historical: true' with a 'reason' if the capability was removed upstream"
                )
            elif not str(entry.get("reason", "")).strip():
                hard_errors.append(f"{key}: historical entry requires a non-empty 'reason'")

    # upstream capabilities with no manifest entry at all
    for key, cap in upstream_by_key.items():
        if key not in entries:
            strict_gaps.append(f"{key}: upstream reports '{cap['status']}' but has no manifest entry")

    # coverage classification vs upstream status
    for key, entry in entries.items():
        if not isinstance(entry, dict) or key not in upstream_by_key:
            continue
        upstream_status = upstream_by_key[key]["status"]
        coverage = entry.get("coverage")
        if upstream_status == "implemented" and coverage == "deferred":
            strict_gaps.append(f"{key}: upstream is 'implemented' but local coverage is 'deferred'")
        if upstream_status == "deferred" and coverage == "product" and not str(entry.get("override_reason", "")).strip():
            strict_gaps.append(
                f"{key}: upstream is 'deferred' but local coverage is 'product' "
                f"without an 'override_reason' explaining why"
            )

    by_category: dict[str, dict[str, int]] = {}
    for key in upstream_by_key:
        category = key.split(":", 1)[0]
        coverage = entries.get(key, {}).get("coverage", "uncovered") if isinstance(entries.get(key), dict) else "uncovered"
        by_category.setdefault(category, {}).setdefault(coverage, 0)
        by_category[category][coverage] += 1

    print("Capability coverage summary (by upstream category):")
    for category in sorted(by_category):
        parts = ", ".join(f"{cov}={n}" for cov, n in sorted(by_category[category].items()))
        print(f"  {category}: {parts}")
    covered = sum(1 for k in upstream_by_key if k in entries)
    print(f"Upstream capabilities: {len(upstream_by_key)}, with a manifest entry: {covered}")

    if strict_gaps:
        label = "Gaps (--strict would fail on these)" if not args.strict else "Gaps"
        print(f"\n{label}:")
        for g in sorted(strict_gaps):
            print(f"  - {g}")

    if hard_errors:
        print("\nManifest errors:", file=sys.stderr)
        for e in sorted(hard_errors):
            print(f"  - {e}", file=sys.stderr)

    if hard_errors or (args.strict and strict_gaps):
        return 1

    print("\nNo manifest errors." + (" (non-strict: gaps above do not fail the build)" if strict_gaps else ""))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
