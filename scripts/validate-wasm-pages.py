#!/usr/bin/env -S uv run --script
# /// script
# requires-python = ">=3.11"
# dependencies = []
# ///
"""Validate the self-contained GitHub Pages WASM build."""

from __future__ import annotations

import sys
from html.parser import HTMLParser
from pathlib import Path, PurePosixPath
from urllib.parse import urlparse

REPO_ROOT = Path(__file__).resolve().parent.parent
DIST = REPO_ROOT / "apps" / "web" / "dist"
PAGES_BASE = "/modelable-showcase/"


class AssetParser(HTMLParser):
    def __init__(self) -> None:
        super().__init__()
        self.references: list[str] = []

    def handle_starttag(
        self,
        tag: str,
        attrs: list[tuple[str, str | None]],
    ) -> None:
        attribute = "href" if tag == "link" else "src" if tag == "script" else None
        if attribute is None:
            return
        values = dict(attrs)
        if values.get(attribute):
            self.references.append(values[attribute] or "")


def require_file(relative: str) -> Path:
    path = DIST / relative
    if not path.is_file():
        raise RuntimeError(f"missing Pages artifact: {path.relative_to(REPO_ROOT)}")
    return path


def validate_index() -> None:
    index = require_file("index.html")
    parser = AssetParser()
    parser.feed(index.read_text(encoding="utf-8"))
    if not parser.references:
        raise RuntimeError("Pages index.html contains no asset references")

    for reference in parser.references:
        parsed = urlparse(reference)
        if parsed.scheme or parsed.netloc:
            raise RuntimeError(f"Pages index references external asset {reference!r}")
        if not parsed.path.startswith(PAGES_BASE):
            raise RuntimeError(
                f"Pages asset {reference!r} is outside expected base {PAGES_BASE!r}"
            )
        relative = PurePosixPath(parsed.path.removeprefix(PAGES_BASE))
        require_file(relative.as_posix())


def validate_runtime_assets() -> None:
    require_file("wasm/showcase_wasm.js")
    wasm = require_file("wasm/showcase_wasm_bg.wasm")
    if wasm.read_bytes()[:4] != b"\x00asm":
        raise RuntimeError("packaged showcase_wasm_bg.wasm has an invalid magic header")

    workers = list((DIST / "assets").glob("runtime.worker-*.js"))
    if len(workers) != 1:
        relative = (DIST / "assets").relative_to(REPO_ROOT)
        raise RuntimeError(f"expected one worker bundle under {relative}, found {len(workers)}")


def run() -> int:
    validate_index()
    validate_runtime_assets()
    print(f"validated self-contained Pages build in {DIST}")
    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(run())
    except RuntimeError as error:
        print(f"validate-wasm-pages.py: {error}", file=sys.stderr)
        raise SystemExit(1) from error
