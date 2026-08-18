"""Marquez/OpenLineage sync integration profile (IMPLEMENTATION_PLAN.md Task
15.3): prove `modelable sync --lineage marquez` sends real dataset/job/run
lineage through the CLI to a real Marquez backend, then verifies receipt by
querying Marquez's own API, via subprocess + a plain HTTP client only. Never
import modelable's Python internals here - these tests exist to prove the
downstream CLI contract, not implementation details (IMPLEMENTATION_PLAN.md
Sec 0, rule 2).

Only implemented because the pinned Modelable CLI reports real support:
`modelable sync --lineage marquez --url ... [--dry-run]` is a real command on
the pinned release (verified against .modelable-version's pinned release),
and a live sync was manually confirmed end-to-end against a real Marquez
0.50.0 before writing this test - datasets land with real field lists, jobs
land with real input/output dataset edges and a COMPLETED run.

Prerequisite: the optional `marquez` Compose profile must be running:

    docker compose --profile marquez up -d marquez

Marquez hard-requires its own dedicated PostgreSQL (see docker-compose.yml's
`marquez-db` service comment) - this is a heavier two-container profile than
Task 15.2's Apicurio profile, kept separate from `make integration`/the core
PR gate per the task's own "keep it separate if startup cost is high" note.
Marquez listens on 127.0.0.1:5010 (API) / 127.0.0.1:5011 (admin/healthcheck).
The base URL comes from SHOWCASE_MARQUEZ_URL with that default. Tests skip
when Marquez is unreachable, exactly like the postgres/clickhouse/apicurio
integration tests skip when their service is down."""

from __future__ import annotations

import json
import os
import shutil
import subprocess
import time
import urllib.error
import urllib.parse
import urllib.request
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parents[2]
MODEL_DIR = REPO_ROOT / "model"
MARQUEZ_URL = os.environ.get("SHOWCASE_MARQUEZ_URL", "http://127.0.0.1:5010")
MARQUEZ_ADMIN_URL = os.environ.get("SHOWCASE_MARQUEZ_ADMIN_URL", "http://127.0.0.1:5011")


def _marquez_reachable() -> bool:
    for _ in range(6):
        try:
            with urllib.request.urlopen(f"{MARQUEZ_ADMIN_URL}/healthcheck", timeout=2) as response:
                if response.status == 200:
                    return True
        except (urllib.error.URLError, TimeoutError, OSError):
            pass
        time.sleep(2)
    return False


pytestmark = [
    pytest.mark.skipif(
        shutil.which("modelable") is None,
        reason="modelable is not on PATH - run 'make bootstrap' (or source scripts/modelable-env.sh) first",
    ),
    pytest.mark.skipif(
        not _marquez_reachable(),
        reason=(
            "Marquez not reachable on SHOWCASE_MARQUEZ_URL - run "
            "'docker compose --profile marquez up -d marquez' first"
        ),
    ),
]


def run_modelable(*args: str) -> subprocess.CompletedProcess[str]:
    return subprocess.run(["modelable", *args], cwd=REPO_ROOT, capture_output=True, text=True)


def _get_json(path: str) -> dict:
    with urllib.request.urlopen(f"{MARQUEZ_URL}{path}", timeout=5) as response:
        return json.loads(response.read().decode("utf-8"))


def test_sync_dry_run_lists_events_without_publishing():
    result = run_modelable("sync", str(MODEL_DIR), "--lineage", "marquez", "--url", MARQUEZ_URL, "--dry-run")
    assert result.returncode == 0, result.stdout + result.stderr
    assert "patient.Patient.v2" in result.stdout, result.stdout


def test_sync_publishes_dataset_with_real_fields():
    result = run_modelable("sync", str(MODEL_DIR), "--lineage", "marquez", "--url", MARQUEZ_URL)
    assert result.returncode == 0, result.stdout + result.stderr
    assert "OK synced" in result.stdout, result.stdout

    namespace = urllib.parse.quote("modelable://patient", safe="")
    doc = _get_json(f"/api/v1/namespaces/{namespace}/datasets")
    datasets = {entry["name"]: entry for entry in doc["datasets"]}
    assert "patient.Patient.v2" in datasets, datasets.keys()

    fields = {field["name"] for field in datasets["patient.Patient.v2"]["fields"]}
    assert {"patientId", "legalName", "dateOfBirth", "contact"} <= fields, fields


def test_sync_publishes_a_projection_job_with_lineage_edges_and_a_completed_run():
    result = run_modelable("sync", str(MODEL_DIR), "--lineage", "marquez", "--url", MARQUEZ_URL)
    assert result.returncode == 0, result.stdout + result.stderr

    namespace = urllib.parse.quote("modelable://reporting", safe="")
    doc = _get_json(f"/api/v1/namespaces/{namespace}/jobs")
    jobs = {entry["name"]: entry for entry in doc["jobs"]}
    job = jobs["compile/reporting.PatientSummary.v1"]

    input_names = {(edge["namespace"], edge["name"]) for edge in job["inputs"]}
    assert ("modelable://patient", "patient.Patient.v2") in input_names, input_names

    output_names = {(edge["namespace"], edge["name"]) for edge in job["outputs"]}
    assert ("modelable://reporting", "reporting.PatientSummary.v1") in output_names, output_names

    assert job["latestRun"]["state"] == "COMPLETED", job["latestRun"]
