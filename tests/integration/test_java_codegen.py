"""Java generated code build (IMPLEMENTATION_PLAN.md Task 7.3): prove generated
Java compiles with a real `javac`, not a text grep.

The java target emits one record per model/projection under
generated/java/<domain>/<Type>.java, packaged as the lowercase domain name.
Like the csharp target (findings #15/#16), there is no package split to
isolate what compiles, so this file tests both halves of the current reality:

- The five value-type artifacts that compile as-is under the pinned 1.7.0
  release compile cleanly (`test_compilable_subset_compiles`). These are
  exactly the files `probes/java/pom.xml` compiles, which carries the
  construction/equality proof via `mvn test`.

- Everything else the java target emits does NOT compile: value types are
  referenced by their short source name while defined under the stable
  <Name>V<version> name, and semantic types are referenced but never emitted
  at all (`test_full_generated_set_currently_fails_named_type_resolution`).
  Both are real, logged upstream findings - UPSTREAM_FINDINGS.md #17 and #18 -
  broken on the pinned release AND on upstream `main` (verified there: the
  emitter is byte-identical). This failure assertion is the flip signal: it
  must be updated (and `probes/java/pom.xml`'s include list grown to the full
  set) once Modelable is re-pinned past a release that fixes either finding.
"""

from __future__ import annotations

import shutil
import subprocess
import tempfile
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parents[2]
JAVA_DIR = REPO_ROOT / "generated" / "java"

pytestmark = [
    pytest.mark.skipif(shutil.which("javac") is None, reason="javac is not on PATH"),
]

# The five generated value-type artifacts that compile as-is under the pinned
# 1.7.0 release. Kept in sync with probes/java/pom.xml's <include> list.
COMPILABLE_SUBSET = [
    "patient/AddressV0.java",
    "patient/ContactDetailsV0.java",
    "scheduling/TimeRangeV0.java",
    "billing/InvoiceLineV0.java",
    "clinical/DiagnosisV0.java",
]


def javac(*files: str, out_dir: Path) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        ["javac", "--release", "21", "-d", str(out_dir), *files],
        capture_output=True,
        text=True,
    )


def test_compilable_subset_compiles():
    assert JAVA_DIR.is_dir(), "run 'make generate' first"
    missing = [name for name in COMPILABLE_SUBSET if not (JAVA_DIR / name).exists()]
    assert not missing, f"generated/java missing expected files: {missing}"

    with tempfile.TemporaryDirectory() as tmp:
        result = javac(
            *(str(JAVA_DIR / name) for name in COMPILABLE_SUBSET),
            out_dir=Path(tmp),
        )
        assert result.returncode == 0, result.stdout + result.stderr


def test_full_generated_set_currently_fails_named_type_resolution():
    assert JAVA_DIR.is_dir(), "run 'make generate' first"
    files = [str(path) for path in sorted(JAVA_DIR.rglob("*.java"))]

    with tempfile.TemporaryDirectory() as tmp:
        result = javac(*files, out_dir=Path(tmp))

        assert result.returncode != 0, (
            "generated/java/ now compiles in full - UPSTREAM_FINDINGS.md #17/#18 "
            "appear fixed. Update this test and grow probes/java/pom.xml's "
            "<include> list to the full set instead of leaving it green by "
            "accident.\n"
            + result.stdout
            + result.stderr
        )

        output = result.stdout + result.stderr
        # #18: semantic-typed @key fields reference types that are never emitted,
        # including the cross-domain pascalized spelling.
        assert "cannot find symbol" in output, output
        assert "symbol:   class PatientId" in output, output
        assert "symbol:   class PatientPatientId" in output, output
        # #17: value-type references use the short source name, not the emitted
        # stable name (Address is emitted as AddressV0; Diagnosis as DiagnosisV0).
        assert "symbol:   class Address" in output, output
        assert "symbol:   class Diagnosis" in output, output

        # The probe's own subset must not be implicated in any error.
        for name in COMPILABLE_SUBSET:
            assert name not in output, f"subset file {name} unexpectedly reported an error:\n{output}"