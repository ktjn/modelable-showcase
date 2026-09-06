"""Integration tests proving the canonical model/ workspace against the real
Modelable CLI, via subprocess only. Never import modelable's Python
internals here - these tests exist to prove the downstream CLI contract,
not implementation details (IMPLEMENTATION_PLAN.md Sec 0, rule 2)."""

from __future__ import annotations

import json
import shutil
import subprocess
import tempfile
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parents[2]
MODEL_DIR = REPO_ROOT / "model"

pytestmark = pytest.mark.skipif(
    shutil.which("modelable") is None,
    reason="modelable is not on PATH - run 'make bootstrap' (or source scripts/modelable-env.sh) first",
)


def run_modelable(*args: str) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        ["modelable", *args],
        cwd=REPO_ROOT,
        capture_output=True,
        text=True,
    )


def compile_to_tmp(tmp_path: Path, target: str) -> tuple[subprocess.CompletedProcess[str], Path]:
    """Compile into an isolated temp dir with its own --registry/--registry-ids/
    --enum-numbers paths, so tests never touch the repo's real .modelable/,
    registry-ids.lock, or enum-numbers.lock (durable allocation state, not a
    disposable build artifact - see IMPLEMENTATION_PLAN.md Task 14.1)."""
    out_dir = tmp_path / target
    result = run_modelable(
        "compile",
        str(MODEL_DIR),
        "--target",
        target,
        "--out",
        str(out_dir),
        "--registry",
        str(tmp_path / "registry.db"),
        "--registry-ids",
        str(tmp_path / "registry-ids.lock"),
        "--enum-numbers",
        str(tmp_path / "enum-numbers.lock"),
    )
    return result, out_dir


def test_strict_validation_succeeds():
    result = run_modelable("validate", str(MODEL_DIR), "--strict")
    assert result.returncode == 0, result.stdout + result.stderr


def test_resolve_patient_v1_succeeds():
    result = run_modelable("resolve", "patient.Patient@1", "--path", str(MODEL_DIR))
    assert result.returncode == 0, result.stdout + result.stderr
    assert "entity Patient @ 1" in result.stdout
    assert "@key" in result.stdout


def test_resolve_patient_live_version_succeeds():
    result = run_modelable("resolve", "patient.Patient@2", "--path", str(MODEL_DIR))
    assert result.returncode == 0, result.stdout + result.stderr
    assert "entity Patient @ 2" in result.stdout
    assert "clinicalNotes" in result.stdout


def test_lineage_on_canonical_model_succeeds():
    result = run_modelable("lineage", "patient.Patient@2", "--path", str(MODEL_DIR))
    assert result.returncode == 0, result.stdout + result.stderr
    assert "patientId" in result.stdout
    assert "key" in result.stdout


def test_auto_projection_inspection_succeeds():
    result = run_modelable("inspect", "patient.Patient@2", "--auto", "--path", str(MODEL_DIR))
    assert result.returncode == 0, result.stdout + result.stderr
    for expected in ("PatientDb", "PatientRequest", "PatientReply", "PatientEvent"):
        assert expected in result.stdout, f"expected {expected} in auto-projection output"

    # @server fields (createdAt/updatedAt) must not leak into the write model
    # (SPEC.md Sec 7.5: "@server exclusion from request projections").
    request_section = result.stdout.split("PatientRequest")[1].split("PatientReply")[0]
    assert "createdAt" not in request_section
    assert "updatedAt" not in request_section


def test_resolve_appointment_succeeds():
    result = run_modelable("resolve", "scheduling.Appointment@1", "--path", str(MODEL_DIR))
    assert result.returncode == 0, result.stdout + result.stderr
    assert "entity Appointment @ 1" in result.stdout
    assert "ref<patient.Patient @ 2>" in result.stdout


def test_appointment_auto_projection_names():
    result = run_modelable("inspect", "scheduling.Appointment@1", "--auto", "--path", str(MODEL_DIR))
    assert result.returncode == 0, result.stdout + result.stderr
    for expected in ("AppointmentDb", "AppointmentRequest", "AppointmentReply", "AppointmentEvent"):
        assert expected in result.stdout, f"expected {expected} in auto-projection output"

    request_section = result.stdout.split("AppointmentRequest")[1].split("AppointmentReply")[0]
    assert "createdAt" not in request_section
    assert "updatedAt" not in request_section


def test_sql_postgres_secondary_indexes_present():
    with tempfile.TemporaryDirectory() as tmp:
        result, out_dir = compile_to_tmp(Path(tmp), "sql-postgres")
        assert result.returncode == 0, result.stdout + result.stderr

        db_sql_files = list(out_dir.glob("scheduling.AppointmentDb.*.sql"))
        assert len(db_sql_files) == 1, f"expected exactly one AppointmentDb SQL file, found {db_sql_files}"
        sql = db_sql_files[0].read_text()

        # Structural presence only - determinism/byte-for-byte SQL content is
        # a separate suite (SPEC.md Sec 18, IMPLEMENTATION_PLAN.md Task 5.3).
        assert "CREATE TABLE" in sql
        # Index names now carry the <table>_ prefix (UPSTREAM_FINDINGS.md #24,
        # fixed in 1.8.0) so they are collision-proof across projections that
        # share a field set (by_patient_day, by_practitioner_day, by_status
        # would otherwise collide across AppointmentDb/Event/Reply/Request).
        assert "CREATE INDEX IF NOT EXISTS appointment_db_by_patient_day" in sql
        assert "CREATE INDEX IF NOT EXISTS appointment_db_by_practitioner_day" in sql
        assert "CREATE INDEX IF NOT EXISTS appointment_db_by_status" in sql


def test_clinical_json_schema_compiles():
    with tempfile.TemporaryDirectory() as tmp:
        result, out_dir = compile_to_tmp(Path(tmp), "json-schema")
        assert result.returncode == 0, result.stdout + result.stderr

        schema_files = list(out_dir.glob("clinical.*.json"))
        assert schema_files, "expected at least one clinical.*.json schema file"
        for path in schema_files:
            schema = json.loads(path.read_text())
            assert schema.get("$schema", "").startswith("https://json-schema.org/draft/2020-12"), path


def test_fhir_profiles_use_intended_resource_bases():
    with tempfile.TemporaryDirectory() as tmp:
        result, out_dir = compile_to_tmp(Path(tmp), "fhir-profile")
        assert result.returncode == 0, result.stdout + result.stderr

        expected = {
            "clinical.PatientFhirView.v1.fhir.json": "Patient",
            "clinical.EncounterFhirView.v1.fhir.json": "Encounter",
            "clinical.ObservationFhirView.v1.fhir.json": "Observation",
        }
        for filename, base_resource in expected.items():
            path = out_dir / filename
            assert path.exists(), f"expected {filename} to be generated"
            profile = json.loads(path.read_text())
            # Parses as real FHIR JSON, and does not silently fall back to
            # the generic 'Basic' resource (SPEC.md Sec 6.3).
            assert profile["resourceType"] == "StructureDefinition"
            assert profile["type"] == base_resource
            assert profile["baseDefinition"] == f"http://hl7.org/fhir/StructureDefinition/{base_resource}"

        # A source model outside the hardened set (scheduling.Appointment)
        # is expected to fall back to Basic rather than fail the compile.
        appointment_profile = json.loads((out_dir / "scheduling.AppointmentDb.v1.fhir.json").read_text())
        assert appointment_profile["type"] == "Basic"


# `modelable lineage` has no --format flag (checked `modelable lineage --help`),
# so these assert stable substrings of the plain-text output per
# IMPLEMENTATION_PLAN.md Task 2.4 ("prefer structured output if the CLI
# supports it; otherwise assert minimal stable substrings").


def test_patient_summary_name_traces_to_patient_model():
    result = run_modelable("lineage", "reporting.PatientSummary@1", "--path", str(MODEL_DIR))
    assert result.returncode == 0, result.stdout + result.stderr
    assert "legalName: direct" in result.stdout
    assert "<- patient.Patient@2#legalName" in result.stdout


def test_patient_clinical_summary_traces_to_observation_source():
    result = run_modelable("lineage", "reporting.PatientClinicalSummary@1", "--path", str(MODEL_DIR))
    assert result.returncode == 0, result.stdout + result.stderr
    assert "<- clinical.Observation@1#observationId" in result.stdout
    assert "<- clinical.Observation@1#temperatureCelsius" in result.stdout


def test_practitioner_revenue_traces_to_invoice_and_payment_source():
    result = run_modelable("lineage", "reporting.PractitionerRevenue@1", "--path", str(MODEL_DIR))
    assert result.returncode == 0, result.stdout + result.stderr
    assert "<- billing.Invoice@2#total" in result.stdout
    assert "<- billing.PaymentReceived@1#amount" in result.stdout
