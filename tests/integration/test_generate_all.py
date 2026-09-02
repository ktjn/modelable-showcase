"""Unified generation script (IMPLEMENTATION_PLAN.md Task 5.1, SPEC.md
Sec 9): scripts/generate-all.py must compile every target the pinned CLI
reports as `implemented` and record a complete, valid manifest. This is
a real integration invocation - it shells out to the actual `modelable`
CLI and compiles the actual model/ directory to every implemented
target, the same as `make generate` does."""

from __future__ import annotations

import importlib.util
import json
import shutil
import subprocess
import sys
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parents[2]
GENERATED_DIR = REPO_ROOT / "generated"
MANIFEST_PATH = GENERATED_DIR / "manifest.json"
SCRIPT_PATH = REPO_ROOT / "scripts" / "generate-all.py"

pytestmark = pytest.mark.skipif(
    shutil.which("modelable") is None,
    reason="modelable is not on PATH - run 'make bootstrap' (or source scripts/modelable-env.sh) first",
)

EXPECTED_TARGETS = {
    "json-schema",
    "markdown",
    "typescript",
    "csharp",
    "java",
    "python",
    "rust",
    "go",
    "sql-postgres",
    "sql-clickhouse",
    "dbt-yaml",
    "fhir-profile",
    "openmetadata",
    "openlineage",
    "odcs",
    "protobuf",
    "grpc",
}


@pytest.fixture(scope="module")
def generate_result() -> subprocess.CompletedProcess[str]:
    if GENERATED_DIR.exists():
        shutil.rmtree(GENERATED_DIR)
    result = subprocess.run(
        [sys.executable, str(SCRIPT_PATH)], cwd=REPO_ROOT, capture_output=True, text=True
    )
    return result


def test_generate_all_succeeds(generate_result: subprocess.CompletedProcess[str]):
    assert generate_result.returncode == 0, generate_result.stdout + generate_result.stderr


def test_manifest_is_valid_json(generate_result: subprocess.CompletedProcess[str]):
    assert MANIFEST_PATH.exists(), "generated/manifest.json was not written"
    json.loads(MANIFEST_PATH.read_text())  # raises if malformed


def test_manifest_reports_every_currently_implemented_target(generate_result: subprocess.CompletedProcess[str]):
    manifest = json.loads(MANIFEST_PATH.read_text())
    assert manifest["failed_targets"] == [], manifest["failed_targets"]
    assert set(manifest["targets"]) >= EXPECTED_TARGETS, (
        f"missing targets: {EXPECTED_TARGETS - set(manifest['targets'])}"
    )
    assert manifest["modelable_version"], manifest


def test_generation_validates_stable_plan_v1_protocol(generate_result: subprocess.CompletedProcess[str]):
    output = generate_result.stdout + generate_result.stderr
    assert "validated 25 modelable.plan/v1 documents" in output


def test_every_generated_plan_is_an_independently_valid_v1_document(
    generate_result: subprocess.CompletedProcess[str],
):
    assert generate_result.returncode == 0, generate_result.stdout + generate_result.stderr
    plan_paths = sorted((REPO_ROOT / ".modelable" / "plans").glob("*.plan.json"))
    assert len(plan_paths) == 25
    for plan_path in plan_paths:
        document = json.loads(plan_path.read_text(encoding="utf-8"))
        assert isinstance(document, dict), plan_path
        assert document["$schema"] == "modelable.plan/v1", plan_path
        assert document["fields"], plan_path


def test_validate_plan_protocol_rejects_non_object_json_without_crashing(tmp_path, monkeypatch):
    script_spec = importlib.util.spec_from_file_location("generate_all", SCRIPT_PATH)
    assert script_spec and script_spec.loader
    generate_all = importlib.util.module_from_spec(script_spec)
    script_spec.loader.exec_module(generate_all)

    monkeypatch.setattr(generate_all, "PLAN_DIR", tmp_path)
    monkeypatch.setattr(
        generate_all,
        "run_modelable",
        lambda *args: subprocess.CompletedProcess(args, 0, "", ""),
    )

    for contents in ("[]", "{"):
        plan_path = tmp_path / "malformed.plan.json"
        plan_path.write_text(contents, encoding="utf-8")
        assert generate_all.validate_plan_protocol() is False


def test_manifest_file_hashes_are_real_sha256_of_generated_files(generate_result: subprocess.CompletedProcess[str]):
    manifest = json.loads(MANIFEST_PATH.read_text())
    assert manifest["files"], "manifest reports zero generated files"

    import hashlib
    import random

    sample = random.sample(sorted(manifest["files"]), k=min(10, len(manifest["files"])))
    for rel_path in sample:
        file_path = GENERATED_DIR / rel_path
        assert file_path.is_file(), f"manifest references missing file {rel_path}"
        actual = hashlib.sha256(file_path.read_bytes()).hexdigest()
        assert actual == manifest["files"][rel_path], f"hash mismatch for {rel_path}"


def test_generated_directory_is_disposable_and_manifest_not_committed():
    gitignore = (REPO_ROOT / ".gitignore").read_text()
    assert "generated/" in gitignore.splitlines(), ".gitignore must exclude generated/ wholesale"
    result = subprocess.run(
        ["git", "check-ignore", "-q", str(MANIFEST_PATH)], cwd=REPO_ROOT
    )
    assert result.returncode == 0, "generated/manifest.json must be git-ignored"
