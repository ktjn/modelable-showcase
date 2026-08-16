"""Go generated code build (IMPLEMENTATION_PLAN.md Task 7.4): prove generated
Go builds with a real `go build`, not a text grep.

The go target emits one file per model/projection under
generated/go/<domain>/<name>.go, packaged as the lowercase domain name. Go
compiles whole packages. This file tests both halves of the current 1.8.0
reality:

- The patient and scheduling packages build cleanly - their value types,
  semantic types, models, and projections all resolve within the same package
  (the #21/#22 fix from #365) - plus the self-contained billing/clinical value
  type files. These are reassembled verbatim into a throwaway module
  (`test_compilable_subset_builds`), mirroring what probes/go/generated_test.go
  compiles, which carries the construction/serialization proof via `go test`.

- The full generated set still does NOT build: references to types declared in
  another package are emitted bare with no import
  (`test_full_generated_set_currently_fails_cross_package_resolution`). That
  is the residual half of #21/#22, logged as a new finding - UPSTREAM_FINDINGS.md
  #31. This failure assertion is the flip signal: it must be updated (and
  probes/go grown to build the full set) once Modelable is re-pinned past a
  release that fixes #31.
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


def test_full_generated_set_currently_fails_cross_package_resolution():
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
            "generated/go/ now builds in full - UPSTREAM_FINDINGS.md #31 "
            "appears fixed. Update this test and grow probes/go to the full set "
            "instead of leaving it green by accident.\n"
            + result.stdout
            + result.stderr
        )

        output = result.stdout + result.stderr
        # #31: references to types declared in another package are emitted bare
        # with no import - the cross-domain names in this graph.
        assert "undefined: PatientPatientId" in output, output
        assert "undefined: SchedulingPractitionerId" in output, output
        assert "undefined: SchedulingTimeRangeV0" in output, output

        # The probe's own subset files must not be implicated in any error.
        for rel in COMPILABLE_SUBSET:
            assert Path(rel).name not in output, f"subset file {rel} unexpectedly reported an error:\n{output}"