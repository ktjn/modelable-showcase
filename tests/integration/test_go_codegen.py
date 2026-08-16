"""Go generated code build (IMPLEMENTATION_PLAN.md Task 7.4): prove generated
Go builds with a real `go build`, not a text grep.

The go target emits one file per model/projection under
generated/go/<domain>/<name>.go, packaged as the lowercase domain name, plus a
go.mod declaring the module name (modelable/generated) its cross-domain imports
reference. Go compiles whole packages. This file tests the current reality:

- The patient and scheduling packages build cleanly - their value types,
  semantic types, models, and projections all resolve within the same package -
  plus the self-contained billing/clinical value type files
  (`test_compilable_subset_builds`), mirroring what probes/go/generated_test.go
  compiles, which carries the construction/serialization proof via `go test`.

- The full generated set builds (`test_full_generated_set_builds`): cross-domain
  references are reference-scoped imports and semantic refs inline to their
  primitives. This reflects UPSTREAM_FINDINGS.md #31 being fixed by the #37
  cross-domain import fix (landed upstream, present in the pinned release).
"""

from __future__ import annotations

import os
import shutil
import subprocess
import tempfile
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parents[2]
GO_DIR = REPO_ROOT / "generated" / "go"

pytestmark = [
    pytest.mark.skipif(shutil.which("go") is None, reason="go toolchain is not on PATH"),
]

# The generated packages/files that build under the pinned 1.8.0 release:
# the whole patient and scheduling packages (all references resolve within the
# same package - #21/#22 fixed) plus the self-contained billing/clinical value
# type files. Kept in sync with probes/go/generated_test.go's reassembly set.
COMPILABLE_SUBSET = sorted(
    [str(p.relative_to(GO_DIR)) for p in GO_DIR.rglob("*.go")
     if p.parts[-2] in ("patient", "scheduling")]
    + ["billing/billing_invoice_line_v0.go", "clinical/clinical_diagnosis_v0.go"]
)


def _write_go_module(module_root: Path, files: list[tuple[Path, Path]]) -> None:
    """Lay out a throwaway Go module: go.mod plus the given (source, target)
    file pairs copied verbatim (never edited).

    The emitter now ships a go.mod declaring the module name its cross-domain
    imports reference (module modelable/generated); use that verbatim when
    present so cross-package imports resolve, falling back to `module probe`
    for the subset-only reassembly."""
    emitted_go_mod = GO_DIR / "go.mod"
    if emitted_go_mod.is_file():
        shutil.copy2(emitted_go_mod, module_root / "go.mod")
    else:
        (module_root / "go.mod").write_text("module probe\n\ngo 1.26\n", encoding="utf-8")
    for src, target in files:
        target.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(src, target)


def go_build(module_root: Path) -> subprocess.CompletedProcess[str]:
    env = dict(os.environ)
    env["GOTOOLCHAIN"] = "local"
    return subprocess.run(
        ["go", "build", "./..."],
        cwd=module_root,
        capture_output=True,
        text=True,
        env=env,
    )


def test_compilable_subset_builds():
    assert GO_DIR.is_dir(), "run 'make generate' first"
    missing = [rel for rel in COMPILABLE_SUBSET if not (GO_DIR / rel).exists()]
    assert not missing, f"generated/go missing expected files: {missing}"

    with tempfile.TemporaryDirectory() as tmp:
        module_root = Path(tmp)
        pairs = [
            (GO_DIR / rel, module_root / rel)
            for rel in COMPILABLE_SUBSET
        ]
        _write_go_module(module_root, pairs)
        result = go_build(module_root)
        assert result.returncode == 0, result.stdout + result.stderr


def test_full_generated_set_builds():
    assert GO_DIR.is_dir(), "run 'make generate' first"
    with tempfile.TemporaryDirectory() as tmp:
        module_root = Path(tmp)
        pairs = [
            (src, module_root / src.relative_to(GO_DIR))
            for src in sorted(GO_DIR.rglob("*.go"))
        ]
        assert pairs, "generated/go is empty"
        _write_go_module(module_root, pairs)
        result = go_build(module_root)
        # UPSTREAM_FINDINGS.md #31 (and the #37 cross-domain import fix): the
        # full generated/go/ set now builds in one module. The emitter emits a
        # go.mod (module modelable/generated); the throwaway module uses it.
        assert result.returncode == 0, result.stdout + result.stderr