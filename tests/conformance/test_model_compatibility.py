"""Model compatibility evolution (IMPLEMENTATION_PLAN.md Task 4.1,
SPEC.md Sec 11): the additive/breaking fixtures under compat/ must be
independently classified by the real `modelable diff` command, not just
by whichever (additive)/(breaking) keyword their author typed - `diff`
is what actually tells a consumer whether an evolution was safe.

Every case SPEC.md Sec 11 requires of this task is covered:
- additive field addition accepted (compat/additive-v2, Patient@1 -> @2)
- required field addition rejected/breaking as appropriate (rejected: an
  inline probe below, mirroring the already-committed
  tests/conformance/invalid/additive-marked-breaking-change.mdl's
  field-removal variant of the same rejection mechanism; breaking: part
  of compat/breaking-v3, Patient@1 -> @3)
- field removal (compat/breaking-v3)
- type change (compat/breaking-v3)
- nullability change, both directions (loosened: compat/additive-v2;
  tightened: compat/breaking-v3)
- enum evolution (compat/breaking-v3)
- source version change (both compat/additive-v2 and compat/breaking-v3,
  at the projection level)
- projection lineage change visibility (compat/additive-v2's
  PatientSummary@2 picking up preferredName)
- classification/access change visibility (compat/breaking-v3's
  PatientSummary@3 - see UPSTREAM_FINDINGS.md #10 for why this has to be
  on the projection, not the entity)
"""

from __future__ import annotations

import shutil
import subprocess
import tempfile
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parents[2]
COMPAT_DIR = REPO_ROOT / "compat"

pytestmark = pytest.mark.skipif(
    shutil.which("modelable") is None,
    reason="modelable is not on PATH - run 'make bootstrap' (or source scripts/modelable-env.sh) first",
)


def run_modelable(*args: str, cwd: Path = REPO_ROOT) -> subprocess.CompletedProcess[str]:
    return subprocess.run(["modelable", *args], cwd=cwd, capture_output=True, text=True)


def normalize(text: str) -> str:
    return " ".join(text.split())


@pytest.mark.parametrize("directory", ["baseline-v1", "additive-v2", "breaking-v3"])
def test_compat_fixture_directory_validates_strictly(directory: str):
    result = run_modelable("validate", str(COMPAT_DIR / directory), "--strict")
    assert result.returncode == 0, result.stdout + result.stderr


# --- compat/additive-v2: everything here must classify as compatible -------


def test_additive_field_addition_and_nullability_loosening_are_compatible():
    result = run_modelable("diff", "compat.Patient@1", "compat.Patient@2", "--path", "compat/additive-v2")
    assert result.returncode == 0, result.stdout + result.stderr
    output = result.stdout
    assert "status: compatible" in output, output
    assert "presence_changed dateOfBirth: required -> optional" in output, output
    assert "added_field preferredName" in output, output


def test_additive_projection_shows_source_version_change_and_lineage_growth():
    result = run_modelable(
        "diff", "compat.PatientSummary@1", "compat.PatientSummary@2", "--path", "compat/additive-v2"
    )
    assert result.returncode == 0, result.stdout + result.stderr
    output = normalize(result.stdout)
    assert "status: compatible" in output, output
    assert "field_added preferredName" in output, output
    assert "source_version_changed p" in output and "Patient@1 to 2" in output, output
    assert "(compatible)" in output, output

    lineage_v1 = run_modelable("lineage", "compat.PatientSummary@1", "--path", "compat/additive-v2")
    lineage_v2 = run_modelable("lineage", "compat.PatientSummary@2", "--path", "compat/additive-v2")
    assert lineage_v1.returncode == 0 and lineage_v2.returncode == 0
    assert "preferredName" not in lineage_v1.stdout
    assert "preferredName" in lineage_v2.stdout
    assert "<- compat.Patient@2#preferredName" in lineage_v2.stdout, lineage_v2.stdout


# --- compat/breaking-v3: everything here must classify as breaking ---------


def test_breaking_entity_reports_every_documented_change_category():
    result = run_modelable("diff", "compat.Patient@1", "compat.Patient@3", "--path", "compat/breaking-v3")
    # `diff` exits 1 on a breaking classification.
    assert result.returncode == 1, result.stdout + result.stderr
    output = result.stdout
    assert "status: breaking" in output, output
    assert "removed_field legalName" in output, output
    assert "type_changed dateOfBirth" in output, output
    assert "presence_changed contactPhone: optional -> required" in output, output
    assert "enum_changed status" in output, output
    assert "added_field insuranceId" in output, output
    # A bonus signal from the same command: it also flags which
    # dependent projections break as a result.
    assert "BROKEN" in output and "PatientSummary@1" in output, output


def test_breaking_projection_reports_governance_changes():
    # See UPSTREAM_FINDINGS.md #10: governance (access/classification)
    # comparison only runs for projection diffs, not entity diffs - this
    # is why the assertion targets PatientSummary, not Patient.
    result = run_modelable(
        "diff", "compat.PatientSummary@1", "compat.PatientSummary@3", "--path", "compat/breaking-v3"
    )
    assert result.returncode == 1, result.stdout + result.stderr
    output = normalize(result.stdout)
    assert "status: breaking" in output, output
    assert "field_removed legalName" in output, output
    assert "field_added insuranceId" in output, output
    assert "access_grant_removed ssn" in output and "permission 'write'" in output, output
    assert "classification_changed ssn" in output and "None -> restricted" in output, output
    assert "source_version_changed p" in output and "Patient@1 to 3" in output, output


# --- required-field-addition: rejected when mismarked, accepted when honest -


def test_required_field_addition_rejected_when_marked_additive():
    # The mirror image of tests/conformance/invalid/additive-marked-breaking-change.mdl
    # (which proves a *removed* required field is rejected under (additive));
    # this proves the same COMPAT rejection fires for an *added* required
    # field too - not committed as its own compat/ fixture directory since
    # Task 4.1 only mandates baseline-v1/additive-v2/breaking-v3, and a
    # workspace that fails validate isn't something worth persisting as a
    # standalone "conformance fixture" the way tests/conformance/invalid/
    # already is for exactly this kind of case.
    with tempfile.TemporaryDirectory() as tmp:
        tmp_path = Path(tmp)
        (tmp_path / "probe.mdl").write_text(
            "domain compat {\n"
            '  owner: "conformance-fixtures"\n'
            "  entity Patient @ 1 (additive) {\n"
            "    @key\n"
            "    patientId: uuid\n"
            "    legalName: string\n"
            "  }\n"
            "  entity Patient @ 2 (additive) {\n"
            "    @key\n"
            "    patientId: uuid\n"
            "    legalName: string\n"
            "    insuranceId: uuid\n"
            "  }\n"
            "}\n"
        )
        result = run_modelable("validate", ".", cwd=tmp_path)
        output = normalize(result.stdout + result.stderr)
        assert result.returncode == 1, output
        assert "ERROR COMPAT" in output, output
        assert "added required field insuranceId" in output, output


def test_required_field_addition_accepted_when_marked_breaking():
    # The honest-declaration counterpart of the above: the identical
    # change, correctly marked (breaking), is exactly what
    # compat/breaking-v3/patient.mdl's Patient@3.insuranceId already is -
    # re-asserted here narrowly so this specific case has its own
    # unambiguous test rather than relying only on the broader
    # test_breaking_entity_reports_every_documented_change_category.
    result = run_modelable("diff", "compat.Patient@1", "compat.Patient@3", "--path", "compat/breaking-v3")
    assert result.returncode == 1
    assert "added_field insuranceId" in result.stdout

    validate_result = run_modelable("validate", "compat/breaking-v3", "--strict")
    assert validate_result.returncode == 0, validate_result.stdout + validate_result.stderr
