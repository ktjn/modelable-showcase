#!/usr/bin/env -S uv run --script
# /// script
# requires-python = ">=3.11"
# dependencies = []
# ///
"""Install the repository-pinned wasm-bindgen CLI when needed."""

from __future__ import annotations

import shutil
import subprocess
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
VERSION_FILE = REPO_ROOT / ".wasm-bindgen-version"


def pinned_version() -> str:
    version = VERSION_FILE.read_text(encoding="utf-8").strip()
    if not version:
        raise RuntimeError(f"{VERSION_FILE.name} is empty")
    return version


def installed_version() -> str | None:
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


def run() -> int:
    expected = pinned_version()
    actual = installed_version()
    if actual == expected:
        print(f"wasm-bindgen-cli {actual} is already installed")
        return 0

    if shutil.which("cargo") is None:
        print("install-wasm-bindgen.py: cargo is required", file=sys.stderr)
        return 1

    if actual is not None:
        print(f"replacing wasm-bindgen-cli {actual} with pinned {expected}")
    else:
        print(f"installing wasm-bindgen-cli {expected}")
    return subprocess.run(
        [
            "cargo",
            "install",
            "wasm-bindgen-cli",
            "--version",
            f"={expected}",
            "--locked",
        ],
        cwd=REPO_ROOT,
        check=False,
    ).returncode


if __name__ == "__main__":
    try:
        raise SystemExit(run())
    except (OSError, RuntimeError) as error:
        print(f"install-wasm-bindgen.py: {error}", file=sys.stderr)
        raise SystemExit(1) from error
