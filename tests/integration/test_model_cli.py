"""Integration tests proving the canonical model/ workspace against the real
Modelable CLI, via subprocess only. Never import modelable's Python
internals here - these tests exist to prove the downstream CLI contract,
not implementation details (IMPLEMENTATION_PLAN.md Sec 0, rule 2)."""

from __future__ import annotations

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
    # Compile into an isolated temp dir with its own registry/ledger paths so
    # this test never touches the repo's real .modelable/ or
    # registry-ids.lock (that file is durable allocation state, not a
    # disposable build artifact - see IMPLEMENTATION_PLAN.md Task 14.1).
    with tempfile.TemporaryDirectory() as tmp:
        tmp_path = Path(tmp)
        out_dir = tmp_path / "sql" / "postgres"
        result = run_modelable(
            "compile",
            str(MODEL_DIR),
            "--target",
            "sql-postgres",
            "--out",
            str(out_dir),
            "--registry",
            str(tmp_path / "registry.db"),
            "--registry-ids",
            str(tmp_path / "registry-ids.lock"),
        )
        assert result.returncode == 0, result.stdout + result.stderr

        db_sql_files = list(out_dir.glob("scheduling.AppointmentDb.*.sql"))
        assert len(db_sql_files) == 1, f"expected exactly one AppointmentDb SQL file, found {db_sql_files}"
        sql = db_sql_files[0].read_text()

        # Structural presence only - determinism/byte-for-byte SQL content is
        # a separate suite (SPEC.md Sec 18, IMPLEMENTATION_PLAN.md Task 5.3).
        assert "CREATE TABLE" in sql
        assert "CREATE INDEX IF NOT EXISTS by_patient_day" in sql
        assert "CREATE INDEX IF NOT EXISTS by_practitioner_day" in sql
        assert "CREATE INDEX IF NOT EXISTS by_status" in sql
