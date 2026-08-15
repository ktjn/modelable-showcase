#!/usr/bin/env -S uv run --script
# /// script
# requires-python = ">=3.11"
# dependencies = []
# ///
"""Determinism gate (IMPLEMENTATION_PLAN.md Task 5.3, SPEC.md Sec 18): for
every target `modelable capabilities --format json` reports as
`implemented`, compile model/ into two independent clean directories and
require the output to be byte-identical - same relative file set, same
SHA-256 per file.

`.modelable/registry.db` is never compared (it lives outside the per-target
--out directories this script hashes, and Task 5.3 explicitly excludes it
unless its determinism becomes an upstream public contract, which it isn't
today).

As of this script's introduction, all 17 implemented targets were verified
byte-identical across two independent compiles with no normalization
needed - x-modelable-por/openlineage timestamps already render as a fixed
epoch sentinel (1970-01-01T00:00:00Z) rather than wall-clock time, and
nothing else in the generated output varies run to run. If a future
Modelable version introduces legitimate nondeterminism in some target,
IMPLEMENTATION_PLAN.md Task 5.3 requires verifying upstream
documentation/tests first, then adding the narrowest possible
normalization here, documented next to the code that does it - do not add
speculative normalization for a problem that hasn't been observed.

Run via `uv run scripts/check-determinism.py` (or `make determinism`).
"""

from __future__ import annotations

import hashlib
import json
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
MODEL_DIR = REPO_ROOT / "model"


def run_modelable(*args: str) -> subprocess.CompletedProcess[str]:
    return subprocess.run(["modelable", *args], cwd=REPO_ROOT, capture_output=True, text=True)


def discover_implemented_targets() -> list[str]:
    result = run_modelable("capabilities", "--format", "json")
    if result.returncode != 0:
        print(
            "check-determinism.py: 'modelable capabilities --format json' failed:\n" + result.stdout + result.stderr,
            file=sys.stderr,
        )
        raise SystemExit(1)
    capabilities = json.loads(result.stdout)
    return sorted(
        cap["name"] for cap in capabilities if cap.get("category") == "target" and cap.get("status") == "implemented"
    )


def hash_tree(root: Path) -> dict[str, str]:
    return {
        path.relative_to(root).as_posix(): hashlib.sha256(path.read_bytes()).hexdigest()
        for path in sorted(root.rglob("*"))
        if path.is_file()
    }


def main() -> int:
    if not shutil.which("modelable"):
        print(
            "check-determinism.py: 'modelable' is not on PATH. Run 'make bootstrap' "
            "(or 'source scripts/modelable-env.sh') first.",
            file=sys.stderr,
        )
        return 1

    targets = discover_implemented_targets()
    if not targets:
        print("check-determinism.py: 'modelable capabilities' reported zero implemented targets.", file=sys.stderr)
        return 1

    failures: dict[str, list[str]] = {}

    with tempfile.TemporaryDirectory(prefix="modelable-determinism-") as tmp:
        tmp_path = Path(tmp)
        for target in targets:
            dir_a = tmp_path / "a" / target
            dir_b = tmp_path / "b" / target
            dir_a.mkdir(parents=True)
            dir_b.mkdir(parents=True)

            result_a = run_modelable("compile", str(MODEL_DIR), "--target", target, "--out", str(dir_a))
            result_b = run_modelable("compile", str(MODEL_DIR), "--target", target, "--out", str(dir_b))

            if result_a.returncode != 0 or result_b.returncode != 0:
                failures[target] = [f"compile failed (exit {result_a.returncode}/{result_b.returncode})"]
                print(f"FAIL {target}: compile itself failed on at least one of the two runs", file=sys.stderr)
                continue

            files_a = hash_tree(dir_a)
            files_b = hash_tree(dir_b)

            mismatches: list[str] = []
            only_in_a = sorted(set(files_a) - set(files_b))
            only_in_b = sorted(set(files_b) - set(files_a))
            if only_in_a:
                mismatches.append(f"present only in run A: {only_in_a}")
            if only_in_b:
                mismatches.append(f"present only in run B: {only_in_b}")

            for rel in sorted(set(files_a) & set(files_b)):
                if files_a[rel] != files_b[rel]:
                    mismatches.append(f"{rel}: A={files_a[rel]} B={files_b[rel]}")

            if mismatches:
                failures[target] = mismatches
                print(f"FAIL {target}:", file=sys.stderr)
                for m in mismatches:
                    print(f"  - {m}", file=sys.stderr)
            else:
                print(f"OK   {target}: {len(files_a)} files byte-identical", file=sys.stderr)

    if failures:
        print(
            f"\ncheck-determinism.py: FAILED - {len(failures)} target(s) not deterministic: "
            f"{', '.join(sorted(failures))}",
            file=sys.stderr,
        )
        return 1

    print(f"\ncheck-determinism.py: all {len(targets)} implemented targets are byte-identical across two independent generations.", file=sys.stderr)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
