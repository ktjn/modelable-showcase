"""Negative fixtures (IMPLEMENTATION_PLAN.md Task 3.2, SPEC.md Sec 13):
every file under tests/conformance/invalid/ MUST fail against the real
Modelable CLI, and MUST fail for its documented reason - a generic parse
failure is not an acceptable match for a fixture that's supposed to prove
a specific semantic/CEL/compatibility rule."""

from __future__ import annotations

import shutil
import subprocess
import tempfile
from pathlib import Path

import pytest
import yaml

REPO_ROOT = Path(__file__).resolve().parents[2]
INVALID_DIR = Path(__file__).resolve().parent / "invalid"
EXPECTED_PATH = INVALID_DIR / "expected.yaml"
FIXTURE_FILES = sorted(INVALID_DIR.glob("*.mdl"))

pytestmark = pytest.mark.skipif(
    shutil.which("modelable") is None,
    reason="modelable is not on PATH - run 'make bootstrap' (or source scripts/modelable-env.sh) first",
)


def run_modelable(*args: str) -> subprocess.CompletedProcess[str]:
    return subprocess.run(["modelable", *args], cwd=REPO_ROOT, capture_output=True, text=True)


def load_expected() -> dict[str, dict]:
    with EXPECTED_PATH.open() as f:
        return yaml.safe_load(f) or {}


EXPECTED = load_expected()


def test_expected_yaml_matches_fixture_files_exactly():
    fixture_names = {p.name for p in FIXTURE_FILES}
    expected_names = set(EXPECTED.keys())
    assert fixture_names == expected_names, (
        f"mismatch between tests/conformance/invalid/*.mdl and expected.yaml entries: "
        f"fixtures without an entry: {fixture_names - expected_names}; "
        f"entries without a fixture: {expected_names - fixture_names}"
    )


@pytest.mark.parametrize("fixture", FIXTURE_FILES, ids=lambda p: p.stem)
def test_invalid_fixture_fails_for_its_documented_reason(fixture: Path):
    expectation = EXPECTED.get(fixture.name)
    assert expectation is not None, f"no expected.yaml entry for {fixture.name}"

    command = expectation.get("command", "validate")
    if command == "validate":
        result = run_modelable("validate", str(fixture), "--strict")
    elif command == "compile-protobuf":
        with tempfile.TemporaryDirectory() as tmp:
            tmp_path = Path(tmp)
            result = run_modelable(
                "compile",
                str(fixture),
                "--target",
                "protobuf",
                "--out",
                str(tmp_path / "out"),
                "--registry",
                str(tmp_path / "registry.db"),
                "--registry-ids",
                str(tmp_path / "registry-ids.lock"),
            )
    else:
        raise AssertionError(f"unknown command '{command}' in expected.yaml for {fixture.name}")

    output = result.stdout + result.stderr
    # `rich` line-wraps CLI output to terminal width, which can insert a
    # newline in the middle of an otherwise-contiguous diagnostic message.
    # Normalize whitespace before substring matching so fixtures aren't
    # flaky based on incidental wrap points.
    normalized_output = " ".join(output.split())

    assert result.returncode == expectation["exit"], (
        f"{fixture.name}: expected exit {expectation['exit']}, got {result.returncode}\n{output}"
    )

    code = expectation.get("code")
    if code is not None:
        assert code in normalized_output, f"{fixture.name}: expected diagnostic code '{code}' in output\n{output}"

    expected_contains = " ".join(expectation["contains"].split())
    assert expected_contains in normalized_output, (
        f"{fixture.name}: expected substring {expectation['contains']!r} in output "
        f"(fixture must fail for its documented reason, not an unrelated parse error)\n{output}"
    )
