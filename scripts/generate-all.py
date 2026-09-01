#!/usr/bin/env -S uv run --script
# /// script
# requires-python = ">=3.11"
# dependencies = []
# ///
"""Compile every Modelable target the pinned/canary CLI reports as
`implemented` from model/ into generated/<target>/, and record what was
produced in generated/manifest.json. See IMPLEMENTATION_PLAN.md Task 5.1
and SPEC.md Sec 9.

Targets are discovered from `modelable capabilities --format json`, not
hard-coded, so a canary build (MODELABLE_REF set - see
scripts/install-modelable.sh) that adds or removes a target is picked up
automatically.

generated/ is disposable build output (see .gitignore) and
generated/manifest.json is never committed - it exists for downstream
tooling (Task 5.2's artifact validation, Task 5.3's determinism gate) to
consume within a single run, not as tracked history.

Run via `uv run scripts/generate-all.py` (or `make generate`).
"""

from __future__ import annotations

import hashlib
import json
import os
import shutil
import subprocess
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
MODEL_DIR = REPO_ROOT / "model"
GENERATED_DIR = REPO_ROOT / "generated"
MANIFEST_PATH = GENERATED_DIR / "manifest.json"
PLAN_DIR = REPO_ROOT / ".modelable" / "plans"
PLAN_SCHEMA = "modelable.plan/v1"


def run_modelable(*args: str) -> subprocess.CompletedProcess[str]:
    return subprocess.run(["modelable", *args], cwd=REPO_ROOT, capture_output=True, text=True)


def discover_implemented_targets() -> list[str]:
    result = run_modelable("capabilities", "--format", "json")
    if result.returncode != 0:
        print(
            "generate-all.py: 'modelable capabilities --format json' failed:\n" + result.stdout + result.stderr,
            file=sys.stderr,
        )
        raise SystemExit(1)
    capabilities = json.loads(result.stdout)
    return sorted(
        cap["name"] for cap in capabilities if cap.get("category") == "target" and cap.get("status") == "implemented"
    )


def modelable_version() -> str:
    result = run_modelable("--version")
    # "modelable, version 1.7.0" -> "1.7.0"
    return result.stdout.strip().rsplit(" ", 1)[-1]


def hash_generated_files(target_dir: Path) -> dict[str, str]:
    hashes: dict[str, str] = {}
    for path in sorted(target_dir.rglob("*")):
        if path.is_file():
            digest = hashlib.sha256(path.read_bytes()).hexdigest()
            rel = path.relative_to(GENERATED_DIR).as_posix()
            hashes[rel] = digest
    return hashes


def validate_plan_protocol() -> bool:
    plan_paths = sorted(PLAN_DIR.glob("*.plan.json"))
    if not plan_paths:
        print(f"generate-all.py: no plans found under {PLAN_DIR}", file=sys.stderr)
        return False

    failures: list[str] = []
    for plan_path in plan_paths:
        try:
            document = json.loads(plan_path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError) as exc:
            failures.append(f"{plan_path.name}: could not read JSON ({exc})")
            continue

        if document.get("$schema") != PLAN_SCHEMA:
            failures.append(f"{plan_path.name}: expected {PLAN_SCHEMA}, got {document.get('$schema')!r}")
            continue

        result = run_modelable("plan", "validate", str(plan_path))
        if result.returncode != 0:
            failures.append(f"{plan_path.name}: modelable plan validate failed\n{result.stdout}{result.stderr}")

    if failures:
        print("generate-all.py: plan protocol validation failed:", file=sys.stderr)
        for failure in failures:
            print(f"  - {failure}", file=sys.stderr)
        return False

    print(f"generate-all.py: validated {len(plan_paths)} {PLAN_SCHEMA} documents", file=sys.stderr)
    return True


def main() -> int:
    if not shutil.which("modelable"):
        print(
            "generate-all.py: 'modelable' is not on PATH. Run 'make bootstrap' "
            "(or 'source scripts/modelable-env.sh') first.",
            file=sys.stderr,
        )
        return 1

    targets = discover_implemented_targets()
    if not targets:
        print("generate-all.py: 'modelable capabilities' reported zero implemented targets.", file=sys.stderr)
        return 1

    GENERATED_DIR.mkdir(parents=True, exist_ok=True)

    succeeded: list[str] = []
    failed: list[str] = []
    files: dict[str, str] = {}

    for target in targets:
        target_dir = GENERATED_DIR / target
        if target_dir.exists():
            shutil.rmtree(target_dir)
        target_dir.mkdir(parents=True)

        print(f"==> modelable compile model --target {target} --out generated/{target}", file=sys.stderr)
        result = run_modelable("compile", str(MODEL_DIR), "--target", target, "--out", str(target_dir))
        sys.stdout.write(result.stdout)
        sys.stderr.write(result.stderr)

        if result.returncode != 0:
            print(f"generate-all.py: target '{target}' FAILED (exit {result.returncode})", file=sys.stderr)
            failed.append(target)
            continue

        succeeded.append(target)
        files.update(hash_generated_files(target_dir))

    manifest = {
        "modelable_version": modelable_version(),
        "upstream_ref": os.environ.get("MODELABLE_REF") or None,
        "targets": succeeded,
        "failed_targets": failed,
        "files": files,
    }
    MANIFEST_PATH.write_text(json.dumps(manifest, indent=2, sort_keys=True) + "\n")

    if failed:
        print(
            f"\ngenerate-all.py: FAILED - {len(failed)} implemented target(s) did not compile: "
            f"{', '.join(failed)}",
            file=sys.stderr,
        )
        return 1

    if not validate_plan_protocol():
        return 1

    print(
        f"\ngenerate-all.py: wrote {MANIFEST_PATH.relative_to(REPO_ROOT)} - "
        f"{len(succeeded)} targets, {len(files)} files",
        file=sys.stderr,
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
