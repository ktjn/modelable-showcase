"""Java generated code build (IMPLEMENTATION_PLAN.md Task 7.3): prove generated
Java compiles with a real `javac`, not a text grep.

The java target emits one record per model/projection under
generated/java/<domain>/<Type>.java, packaged as the lowercase domain name.
Like the csharp target, there is no package split to isolate what compiles, so
this file tests both halves of the current 1.8.0 reality:

- The same-domain subset compiles cleanly: every `patient.*` and `scheduling.*`
  artifact plus the plain billing/clinical value types (`test_compilable_subset_compiles`).
  These are exactly the files `probes/java/pom.xml` compiles, which carries the
  construction/equality proof via `mvn test`.

- The full generated set still does NOT compile: references to types declared
  in another package are emitted bare with no import
  (`test_full_generated_set_currently_fails_cross_package_resolution`). That is
  the residual half of #17/#18, logged as a new finding - UPSTREAM_FINDINGS.md
  #29. This failure assertion is the flip signal: it must be updated (and
  `probes/java/pom.xml`'s include list grown to the full set) once Modelable is
  re-pinned past a release that fixes #29.
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

# The generated artifacts that compile as-is under the pinned 1.8.0 release:
# every patient/scheduling class (all references resolve within the same package
# - #17/#18 fixed) plus the plain billing/clinical value types. Kept in sync
# with probes/java/pom.xml's <include> list.
COMPILABLE_SUBSET = sorted(
    [str(p.relative_to(JAVA_DIR)).replace("\\", "/")
     for p in JAVA_DIR.rglob("*.java")
     if p.parts[-2] in ("patient", "scheduling")]
    + ["billing/InvoiceLineV0.java", "clinical/DiagnosisV0.java"]
)


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


def test_full_generated_set_currently_fails_cross_package_resolution():
    assert JAVA_DIR.is_dir(), "run 'make generate' first"
    files = [str(path) for path in sorted(JAVA_DIR.rglob("*.java"))]

    with tempfile.TemporaryDirectory() as tmp:
        result = javac(*files, out_dir=Path(tmp))

        assert result.returncode != 0, (
            "generated/java/ now compiles in full - UPSTREAM_FINDINGS.md #29 "
            "appears fixed. Update this test and grow probes/java/pom.xml's "
            "<include> list to the full set instead of leaving it green by "
            "accident.\n"
            + result.stdout
            + result.stderr
        )

        output = result.stdout + result.stderr
        assert "cannot find symbol" in output, output
        # #29: references to types declared in another package are emitted bare
        # with no import - the cross-domain names in this graph.
        assert "symbol:   class PatientPatientId" in output, output
        assert "symbol:   class SchedulingPractitionerId" in output, output
        assert "symbol:   class ContactDetailsV0" in output, output
        assert "symbol:   class TimeRangeV0" in output, output

        # The probe's own subset must not be implicated in any error.
        for name in COMPILABLE_SUBSET:
            assert name not in output, f"subset file {name} unexpectedly reported an error:\n{output}"