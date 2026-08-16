"""C# generated code build (IMPLEMENTATION_PLAN.md Task 7.2): prove generated
C# compiles with a real `dotnet build`, not a text grep.

The csharp target emits a flat set of `.cs` files (one per model/projection),
all namespaced under `Modelable.<Domain>`. Unlike the Rust target's
multi-package layout, there is no package split to isolate what compiles, so
this file tests both halves of the current 1.8.0 reality:

- The same-domain subset compiles as-is: every `patient.*` and `scheduling.*`
  artifact (their value types, semantic types, models, and projections resolve
  within their own namespace - the #15/#16 fix from #365). This subset is what
  `probes/csharp/ModelableShowcase.Probe.csproj` links, which carries the
  instantiate/serialize proof.

- The full generated set still does NOT compile: references to types declared
  in another domain are emitted bare with no `using` import
  (`test_full_generated_set_currently_fails_cross_domain_resolution`). That is
  the residual half of #15/#16, logged as a new finding - UPSTREAM_FINDINGS.md
  #28. This failure assertion is the flip signal: it must be updated (and
  `probes/csharp`'s linked subset grown to the full set) once Modelable is
  re-pinned past a release that fixes #28.
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

# The generated artifacts that compile as-is under the pinned 1.8.0 release:
# everything in the patient and scheduling namespaces (all references resolve
# within the same domain - #15/#16 fixed), plus the plain billing/clinical
# value types that have no cross-domain or named-type references. Kept in sync
# with probes/csharp/ModelableShowcase.Probe.csproj's <Compile Include> list.
COMPILABLE_SUBSET = sorted(
    [name for name in (p.name for p in Path.iterdir(CSHARP_DIR) if p.suffix == ".cs")
     if name.startswith(("patient.", "scheduling."))]
    + ["billing.InvoiceLine.v0.cs", "clinical.Diagnosis.v0.cs"]
)


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


def test_full_generated_set_currently_fails_cross_domain_resolution():
    assert CSHARP_DIR.is_dir(), "run 'make generate' first"
    files = sorted(path.name for path in CSHARP_DIR.glob("*.cs"))

    with tempfile.TemporaryDirectory() as tmp:
        project_dir = Path(tmp)
        _write_probe_csproj(project_dir, files)
        result = dotnet_build(project_dir)

        assert result.returncode != 0, (
            "generated/csharp/ now builds in full - UPSTREAM_FINDINGS.md #28 "
            "appears fixed. Update this test and grow "
            "probes/csharp/ModelableShowcase.Probe.csproj's linked subset to the "
            "full set instead of leaving it green by accident.\n"
            + result.stdout
            + result.stderr
        )

        output = result.stdout + result.stderr
        assert "CS0246" in output, output
        # #28: references to types declared in another domain are emitted bare
        # with no `using` import - the four cross-domain names in this graph.
        assert "The type or namespace name 'PatientPatientId' could not be found" in output, output
        assert "The type or namespace name 'SchedulingPractitionerId' could not be found" in output, output
        assert "The type or namespace name 'PatientContactDetailsV0' could not be found" in output, output
        assert "The type or namespace name 'SchedulingTimeRangeV0' could not be found" in output, output

        # The probe's own same-domain subset must not be implicated in any error.
        for name in COMPILABLE_SUBSET:
            assert name not in output, f"subset file {name} unexpectedly reported an error:\n{output}"