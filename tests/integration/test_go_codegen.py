"""Go generated code build (IMPLEMENTATION_PLAN.md Task 7.4): prove generated
Go builds with a real `go build`, not a text grep.

The go target emits one file per model/projection under
generated/go/<domain>/<name>.go, packaged as the lowercase domain name. Go
compiles whole packages, and every domain package contains structs that
reference undefined names under the pinned 1.7.0 release, so nothing in
generated/go/ builds in its original layout. This file tests both halves of
the current reality:

- The five value-type source files, reassembled verbatim into a throwaway
  module whose packages contain only their own declarations, build cleanly
  (`test_value_type_files_compile_in_isolation`). This mirrors what
  `probes/go/generated_test.go` compiles, which carries the
  construction/serialization proof via `go test`.

- Everything else the go target emits does NOT build: value types are
  referenced by their short source name while defined under the stable
  <Domain><Name>V<version> name, and semantic types are referenced but never
  emitted at all (`test_full_generated_set_currently_fails_named_type_resolution`).
  Both are real, logged upstream findings - UPSTREAM_FINDINGS.md #21 and #22 -
  broken on the pinned release AND on upstream `main` (verified there: the
  emitter is byte-identical). This failure assertion is the flip signal: it
  must be updated (and probes/go grown to build the full set) once Modelable
  is re-pinned past a release that fixes either finding.
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

# The five generated value-type files that are self-contained under the pinned
# 1.7.0 release. Kept in sync with probes/go/generated_test.go's reassembly set.
COMPILABLE_SUBSET = [
    ("patient", "patient_address_v0.go"),
    ("patient", "patient_contact_details_v0.go"),
    ("scheduling", "scheduling_time_range_v0.go"),
    ("billing", "billing_invoice_line_v0.go"),
    ("clinical", "clinical_diagnosis_v0.go"),
]


def _write_go_module(module_root: Path, files: list[tuple[Path, Path]]) -> None:
    """Lay out a throwaway Go module: go.mod plus the given (source, target)
    file pairs copied verbatim (never edited)."""
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


def test_value_type_files_compile_in_isolation():
    assert GO_DIR.is_dir(), "run 'make generate' first"
    missing = [f"{dom}/{name}" for dom, name in COMPILABLE_SUBSET if not (GO_DIR / dom / name).exists()]
    assert not missing, f"generated/go missing expected files: {missing}"

    with tempfile.TemporaryDirectory() as tmp:
        module_root = Path(tmp)
        pairs = [
            (GO_DIR / dom / name, module_root / dom / name)
            for dom, name in COMPILABLE_SUBSET
        ]
        _write_go_module(module_root, pairs)
        result = go_build(module_root)
        assert result.returncode == 0, result.stdout + result.stderr


def test_full_generated_set_currently_fails_named_type_resolution():
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

        assert result.returncode != 0, (
            "generated/go/ now builds in full - UPSTREAM_FINDINGS.md #21/#22 "
            "appear fixed. Update this test and grow probes/go to the full set "
            "instead of leaving it green by accident.\n"
            + result.stdout
            + result.stderr
        )

        output = result.stdout + result.stderr
        # #22: semantic-typed @key fields reference types that are never emitted,
        # including the cross-domain pascalized spelling.
        assert "undefined: PatientId" in output, output
        assert "undefined: PatientPatientId" in output, output
        # #21: value-type references use the short source name, not the emitted
        # stable name (Address is emitted as PatientAddressV0; TimeRange as
        # SchedulingTimeRangeV0).
        assert "undefined: Address" in output, output
        assert "undefined: TimeRange" in output, output

        # The probe's own subset files must not be implicated in any error.
        for dom, name in COMPILABLE_SUBSET:
            assert name not in output, f"subset file {dom}/{name} unexpectedly reported an error:\n{output}"