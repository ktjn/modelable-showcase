#!/usr/bin/env -S uv run --script
# /// script
# requires-python = ">=3.11"
# dependencies = []
# ///
"""Build and package the browser clinic runtime with pinned tooling."""

from __future__ import annotations

import argparse
import shutil
import subprocess
import sys
import tomllib
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
MANIFEST = REPO_ROOT / "crates" / "showcase-wasm" / "Cargo.toml"
LOCK_FILE = MANIFEST.parent / "Cargo.lock"
VERSION_FILE = REPO_ROOT / ".wasm-bindgen-version"
TARGET = "wasm32-unknown-unknown"
TARGET_DIR = REPO_ROOT / ".modelable" / "showcase-wasm-target"
DEFAULT_OUTPUT = REPO_ROOT / "apps" / "web" / "public" / "wasm"


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--out-dir",
        type=Path,
        default=DEFAULT_OUTPUT,
        help="package output directory (default: apps/web/public/wasm)",
    )
    parser.add_argument(
        "--skip-install",
        action="store_true",
        help="require the pinned wasm-bindgen CLI instead of installing it",
    )
    return parser.parse_args()


def run_checked(command: list[str]) -> None:
    subprocess.run(command, cwd=REPO_ROOT, check=True)


def pinned_version() -> str:
    return VERSION_FILE.read_text(encoding="utf-8").strip()


def validate_crate_pin(expected: str) -> None:
    manifest = tomllib.loads(MANIFEST.read_text(encoding="utf-8"))
    dependency = manifest["dependencies"]["wasm-bindgen"]
    if dependency != f"={expected}":
        raise RuntimeError(
            f"{MANIFEST.relative_to(REPO_ROOT)} pins wasm-bindgen {dependency!r}; "
            f"expected '={expected}' from {VERSION_FILE.name}"
        )


def installed_cli_version() -> str | None:
    executable = shutil.which("wasm-bindgen")
    if executable is None:
        return None
    result = subprocess.run(
        [executable, "--version"],
        cwd=REPO_ROOT,
        capture_output=True,
        check=False,
        text=True,
    )
    if result.returncode != 0:
        return None
    parts = result.stdout.strip().split()
    return parts[-1] if parts else None


def ensure_cli(expected: str, skip_install: bool) -> None:
    actual = installed_cli_version()
    if actual == expected:
        return
    if skip_install:
        raise RuntimeError(
            f"wasm-bindgen-cli {expected} is required; found {actual or 'none'}. "
            "Run 'make bootstrap'."
        )
    run_checked(["uv", "run", "scripts/install-wasm-bindgen.py"])
    actual = installed_cli_version()
    if actual != expected:
        raise RuntimeError(f"wasm-bindgen-cli install produced {actual or 'no executable'}")


def ensure_target() -> None:
    installed = subprocess.run(
        ["rustup", "target", "list", "--installed"],
        cwd=REPO_ROOT,
        capture_output=True,
        check=True,
        text=True,
    ).stdout.splitlines()
    if TARGET not in installed:
        run_checked(["rustup", "target", "add", TARGET])


def run() -> int:
    args = parse_args()
    expected = pinned_version()
    validate_crate_pin(expected)
    ensure_cli(expected, args.skip_install)
    ensure_target()

    run_checked(
        [
            "cargo",
            "build",
            "--locked",
            "--release",
            "--target",
            TARGET,
            "--target-dir",
            str(TARGET_DIR),
            "--manifest-path",
            str(MANIFEST),
        ]
    )
    wasm = TARGET_DIR / TARGET / "release" / "showcase_wasm.wasm"
    run_checked(
        [
            "wasm-bindgen",
            str(wasm),
            "--target",
            "web",
            "--out-dir",
            str(args.out_dir.resolve()),
            "--out-name",
            "showcase_wasm",
        ]
    )
    print(f"packaged showcase WASM in {args.out_dir.resolve()}")
    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(run())
    except (KeyError, OSError, RuntimeError, subprocess.CalledProcessError) as error:
        print(f"build-showcase-wasm.py: {error}", file=sys.stderr)
        raise SystemExit(1) from error
