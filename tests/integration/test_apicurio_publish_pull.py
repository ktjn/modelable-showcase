"""Apicurio publish/pull integration profile (IMPLEMENTATION_PLAN.md Task
15.2): prove `modelable publish apicurio`/`modelable pull apicurio` round-trip
a real generated JSON Schema artifact through a real Apicurio Registry, via
subprocess only. Never import modelable's Python internals here - these
tests exist to prove the downstream CLI contract, not implementation details
(IMPLEMENTATION_PLAN.md Sec 0, rule 2).

Only implemented because the pinned Modelable CLI reports real support:
`modelable --help` advertises "Apicurio JSON Schema artifact publish/pull"
and `modelable publish apicurio`/`modelable pull apicurio` are real
subcommands (verified against .modelable-version's pinned release).

Prerequisite: the optional `apicurio` Compose profile must be running:

    docker compose --profile apicurio up -d apicurio

It listens on 127.0.0.1:8090 (Apicurio Registry v3, in-memory - disposable,
no persistence). The base URL comes from SHOWCASE_APICURIO_URL with that
default. Tests skip when the registry is unreachable, exactly like the
postgres/clickhouse integration tests skip when their service is down - not
part of ordinary `docker compose up`/`make integration`, only
`make integration-apicurio`.

No internet access is required to run these tests themselves - only the one-
time `docker pull apicurio/apicurio-registry:3.0.6` image acquisition needs
it, same as any other pinned Compose service image."""

from __future__ import annotations

import json
import os
import shutil
import subprocess
import time
import urllib.error
import urllib.request
import uuid
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parents[2]
MODEL_DIR = REPO_ROOT / "model"
APICURIO_URL = os.environ.get("SHOWCASE_APICURIO_URL", "http://127.0.0.1:8090/apis/registry/v3")


def _apicurio_reachable() -> bool:
    for _ in range(6):
        try:
            with urllib.request.urlopen(f"{APICURIO_URL}/system/info", timeout=2) as response:
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
        not _apicurio_reachable(),
        reason=(
            "Apicurio Registry not reachable on SHOWCASE_APICURIO_URL - run "
            "'docker compose --profile apicurio up -d apicurio' first"
        ),
    ),
]


def run_modelable(*args: str, cwd: Path = REPO_ROOT) -> subprocess.CompletedProcess[str]:
    return subprocess.run(["modelable", *args], cwd=cwd, capture_output=True, text=True)


@pytest.fixture
def json_schema_dir(tmp_path: Path) -> Path:
    out_dir = tmp_path / "json-schema"
    result = run_modelable(
        "compile",
        str(MODEL_DIR),
        "--target",
        "json-schema",
        "--out",
        str(out_dir),
        "--registry",
        str(tmp_path / "registry.db"),
        "--registry-ids",
        str(tmp_path / "registry-ids.lock"),
    )
    assert result.returncode == 0, result.stdout + result.stderr
    return out_dir


def test_publish_and_pull_round_trips_a_real_artifact(json_schema_dir: Path, tmp_path: Path):
    # A fresh group per test run, so re-running this test never collides
    # with (or depends on) a previous run's published artifacts in the
    # disposable dev registry.
    group = f"showcase-test-{uuid.uuid4().hex[:12]}"

    publish = run_modelable(
        "publish",
        "apicurio",
        str(MODEL_DIR),
        "--url",
        APICURIO_URL,
        "--group",
        group,
    )
    assert publish.returncode == 0, publish.stdout + publish.stderr
    assert "OK published" in publish.stdout, publish.stdout

    pull_out = tmp_path / "pulled"
    pull = run_modelable(
        "pull",
        "apicurio",
        "patient.Patient@2",
        "--url",
        APICURIO_URL,
        "--group",
        group,
        "--out",
        str(pull_out),
    )
    assert pull.returncode == 0, pull.stdout + pull.stderr

    pulled_files = list(pull_out.rglob("*.json"))
    assert len(pulled_files) == 1, pulled_files
    pulled = json.loads(pulled_files[0].read_text(encoding="utf-8"))

    local = json.loads((json_schema_dir / "patient.Patient.v2.json").read_text(encoding="utf-8"))
    assert pulled == local, "pulled artifact must be content-identical to the locally compiled one"
    assert pulled["x-modelable"]["domain"] == "patient"
    assert pulled["x-modelable"]["name"] == "Patient"
    assert pulled["x-modelable"]["version"] == 2


def test_publish_dry_run_lists_artifacts_without_publishing():
    group = f"showcase-test-{uuid.uuid4().hex[:12]}"

    dry_run = run_modelable(
        "publish",
        "apicurio",
        str(MODEL_DIR),
        "--url",
        APICURIO_URL,
        "--group",
        group,
        "--dry-run",
    )
    assert dry_run.returncode == 0, dry_run.stdout + dry_run.stderr
    assert "patient.Patient.v2" in dry_run.stdout, dry_run.stdout

    # Nothing was actually published under this group - a real pull must fail.
    pull = run_modelable(
        "pull",
        "apicurio",
        "patient.Patient@2",
        "--url",
        APICURIO_URL,
        "--group",
        group,
    )
    assert pull.returncode != 0, "dry-run must not have published any artifact"
