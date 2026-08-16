"""C# generated code build (IMPLEMENTATION_PLAN.md Task 7.2): prove generated
C# compiles with a real `dotnet build`, not a text grep.

The csharp target emits a flat set of `.cs` files (one per model/projection),
all namespaced under `Modelable.<Domain>`. Unlike the Rust target's
multi-package layout, there is no package split to isolate what compiles, so
this file tests both halves of the current reality:

- The five value-type artifacts that compile as-is under the pinned 1.7.0
  release build cleanly (`test_compilable_subset_builds`). These are exactly
  the files `probes/csharp/ModelableShowcase.Probe.csproj` links, which
  carries the instantiate/serialize proof.

- Everything else the csharp target emits does NOT compile: value types are
  referenced by their short source name while defined under the stable
  prefixed name, and semantic types are referenced but never emitted at all
  (`test_full_generated_set_currently_fails_named_type_resolution`). Both are
  real, logged upstream findings - UPSTREAM_FINDINGS.md #15 and #16 - broken
  on the pinned release AND on upstream `main` (verified there: the emitter is
  byte-identical). This failure assertion is the flip signal: it must be
  updated (and `probes/csharp`'s linked subset grown to the full set) once
  Modelable is re-pinned past a release that fixes either finding.
"""

from __future__ import annotations

import os
import shutil
import subprocess
import tempfile
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parents[2]
CSHARP_DIR = REPO_ROOT / "generated" / "csharp"

pytestmark = [
    pytest.mark.skipif(shutil.which("dotnet") is None, reason="dotnet is not on PATH"),
]

# The five generated value-type artifacts that compile as-is under the pinned
# 1.7.0 release. Kept in sync with probes/csharp/ModelableShowcase.Probe.csproj's
# <Compile Include> list.
COMPILABLE_SUBSET = [
    "patient.Address.v0.cs",
    "patient.ContactDetails.v0.cs",
    "scheduling.TimeRange.v0.cs",
    "billing.InvoiceLine.v0.cs",
    "clinical.Diagnosis.v0.cs",
]


def _write_probe_csproj(project_dir: Path, files: list[str]) -> None:
    rel_generated = os.path.relpath(CSHARP_DIR, project_dir).replace("\\", "/")
    compile_items = "\n".join(
        f'    <Compile Include="{rel_generated}/{name}" Link="{name}" />' for name in files
    )
    (project_dir / "probe.csproj").write_text(
        f"""<Project Sdk="Microsoft.NET.Sdk">
  <PropertyGroup>
    <TargetFramework>net10.0</TargetFramework>
    <Nullable>enable</Nullable>
    <IsPackable>false</IsPackable>
  </PropertyGroup>
  <ItemGroup>
{compile_items}
  </ItemGroup>
</Project>
""",
        encoding="utf-8",
    )


def dotnet_build(project_dir: Path) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        ["dotnet", "build", "--nologo", "-m:1"],
        cwd=project_dir,
        capture_output=True,
        text=True,
    )


def test_compilable_subset_builds():
    assert CSHARP_DIR.is_dir(), "run 'make generate' first"
    missing = [name for name in COMPILABLE_SUBSET if not (CSHARP_DIR / name).exists()]
    assert not missing, f"generated/csharp missing expected files: {missing}"

    with tempfile.TemporaryDirectory() as tmp:
        project_dir = Path(tmp)
        _write_probe_csproj(project_dir, COMPILABLE_SUBSET)
        result = dotnet_build(project_dir)
        assert result.returncode == 0, result.stdout + result.stderr


def test_full_generated_set_currently_fails_named_type_resolution():
    assert CSHARP_DIR.is_dir(), "run 'make generate' first"
    files = sorted(path.name for path in CSHARP_DIR.glob("*.cs"))

    with tempfile.TemporaryDirectory() as tmp:
        project_dir = Path(tmp)
        _write_probe_csproj(project_dir, files)
        result = dotnet_build(project_dir)

        assert result.returncode != 0, (
            "generated/csharp/ now builds in full - UPSTREAM_FINDINGS.md #15/#16 "
            "appear fixed. Update this test and grow "
            "probes/csharp/ModelableShowcase.Probe.csproj's linked subset to the "
            "full set instead of leaving it green by accident.\n"
            + result.stdout
            + result.stderr
        )

        output = result.stdout + result.stderr
        assert "CS0246" in output, output
        # #16: a semantic-typed @key field references a type that is never emitted.
        assert "The type or namespace name 'PatientId' could not be found" in output, output
        # #15: a value-type reference uses the short source name, not the emitted
        # stable name (Address is emitted as PatientAddressV0; Diagnosis as
        # ClinicalDiagnosisV0).
        assert "The type or namespace name 'Address' could not be found" in output, output
        assert "The type or namespace name 'Diagnosis' could not be found" in output, output

        # The probe's own subset must not be implicated in any error.
        for name in COMPILABLE_SUBSET:
            assert name not in output, f"subset file {name} unexpectedly reported an error:\n{output}"