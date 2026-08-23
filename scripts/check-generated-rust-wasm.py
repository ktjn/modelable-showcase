#!/usr/bin/env -S uv run --script
# /// script
# requires-python = ">=3.11"
# dependencies = []
# ///
"""Compile every generated Rust package consumed by Modelable Clinic for WASM."""

from __future__ import annotations

import shutil
import subprocess
import sys
import tempfile
import tomllib
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
MODEL_DIR = REPO_ROOT / "model"
API_MANIFEST = REPO_ROOT / "apps" / "api" / "Cargo.toml"
GENERATED_RUST_DIR = REPO_ROOT / "generated" / "rust"
TARGET = "wasm32-unknown-unknown"


def consumed_package_paths() -> list[Path]:
    """Return API path dependencies that point into generated/rust."""
    manifest = tomllib.loads(API_MANIFEST.read_text(encoding="utf-8"))
    generated_root = GENERATED_RUST_DIR.resolve()
    packages: list[Path] = []

    for dependency in manifest.get("dependencies", {}).values():
        if not isinstance(dependency, dict) or not isinstance(dependency.get("path"), str):
            continue
        dependency_path = (API_MANIFEST.parent / dependency["path"]).resolve()
        try:
            packages.append(dependency_path.relative_to(generated_root))
        except ValueError:
            continue

    packages = sorted(set(packages), key=lambda path: path.as_posix())
    if not packages:
        raise RuntimeError(f"{API_MANIFEST.relative_to(REPO_ROOT)} consumes no generated Rust packages")
    return packages


def run() -> int:
    missing_tools = [tool for tool in ("modelable", "cargo") if shutil.which(tool) is None]
    if missing_tools:
        print(
            "check-generated-rust-wasm.py: missing required tool(s): "
            + ", ".join(missing_tools)
            + ". Run 'make bootstrap' first.",
            file=sys.stderr,
        )
        return 1

    package_paths = consumed_package_paths()
    target_dir = REPO_ROOT / ".modelable" / "wasm-target"

    with tempfile.TemporaryDirectory(prefix="modelable-showcase-wasm-") as temporary:
        probe_root = Path(temporary)
        output_dir = probe_root / "rust"
        registry_ids = probe_root / "registry-ids.lock"
        shutil.copy2(MODEL_DIR / "registry-ids.lock", registry_ids)

        compile_result = subprocess.run(
            [
                "modelable",
                "compile",
                str(MODEL_DIR),
                "--target",
                "rust",
                "--out",
                str(output_dir),
                "--registry",
                str(probe_root / "registry.db"),
                "--registry-ids",
                str(registry_ids),
            ],
            cwd=REPO_ROOT,
            capture_output=True,
            check=False,
            text=True,
        )
        if compile_result.returncode != 0:
            sys.stdout.write(compile_result.stdout)
            sys.stderr.write(compile_result.stderr)
            print("check-generated-rust-wasm.py: Rust generation failed", file=sys.stderr)
            return compile_result.returncode

        failures: list[str] = []
        for package_path in package_paths:
            package_manifest = output_dir / package_path / "Cargo.toml"
            if not package_manifest.is_file():
                failures.append(f"{package_path.as_posix()} (generated Cargo.toml missing)")
                continue

            package_name = tomllib.loads(package_manifest.read_text(encoding="utf-8"))["package"]["name"]
            print(f"==> cargo check {package_name} --target {TARGET}", flush=True)
            result = subprocess.run(
                [
                    "cargo",
                    "check",
                    "--target",
                    TARGET,
                    "--manifest-path",
                    str(package_manifest),
                    "--target-dir",
                    str(target_dir),
                ],
                cwd=REPO_ROOT,
                check=False,
            )
            if result.returncode != 0:
                failures.append(package_name)

        if failures:
            print(
                "check-generated-rust-wasm.py: WASM compatibility failed for: " + ", ".join(failures),
                file=sys.stderr,
            )
            print(
                "Record generator-caused failures in UPSTREAM_FINDINGS.md; never rewrite generated output.",
                file=sys.stderr,
            )
            return 1

    print(
        f"Generated Rust WASM compatibility passed for {len(package_paths)} package(s): "
        + ", ".join(path.as_posix() for path in package_paths)
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(run())
