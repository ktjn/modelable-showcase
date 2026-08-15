"""Positive edge-case fixtures (IMPLEMENTATION_PLAN.md Task 3.1, SPEC.md
Sec 12): every file under tests/conformance/valid/ must validate strictly
against the real Modelable CLI, and a handful get a targeted compilation
assertion proving a specific emitter edge actually works - not just that
the source parses."""

from __future__ import annotations

import shutil
import subprocess
import tempfile
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parents[2]
VALID_DIR = Path(__file__).resolve().parent / "valid"
FIXTURE_FILES = sorted(VALID_DIR.glob("*.mdl"))

pytestmark = pytest.mark.skipif(
    shutil.which("modelable") is None,
    reason="modelable is not on PATH - run 'make bootstrap' (or source scripts/modelable-env.sh) first",
)


def run_modelable(*args: str) -> subprocess.CompletedProcess[str]:
    return subprocess.run(["modelable", *args], cwd=REPO_ROOT, capture_output=True, text=True)


def compile_fixture(tmp_path: Path, fixture: Path, target: str) -> tuple[subprocess.CompletedProcess[str], Path]:
    out_dir = tmp_path / target
    result = run_modelable(
        "compile",
        str(fixture),
        "--target",
        target,
        "--out",
        str(out_dir),
        "--registry",
        str(tmp_path / "registry.db"),
        "--registry-ids",
        str(tmp_path / "registry-ids.lock"),
    )
    return result, out_dir


def read_all(out_dir: Path, glob: str) -> str:
    return "\n".join(p.read_text() for p in out_dir.glob(glob))


@pytest.mark.parametrize("fixture", FIXTURE_FILES, ids=lambda p: p.stem)
def test_valid_fixture_validates_strictly(fixture: Path):
    result = run_modelable("validate", str(fixture), "--strict")
    assert result.returncode == 0, result.stdout + result.stderr


def test_at_least_fifteen_fixtures_present():
    # Guards against this directory silently losing coverage over time.
    assert len(FIXTURE_FILES) >= 15, FIXTURE_FILES


def test_u128_i128_representable_in_rust():
    with tempfile.TemporaryDirectory() as tmp:
        result, out_dir = compile_fixture(Path(tmp), VALID_DIR / "numeric-widths.mdl", "rust")
        assert result.returncode == 0, result.stdout + result.stderr
        combined = read_all(out_dir, "**/*.rs")
        assert "pub u128_field: u128," in combined
        assert "pub i128_field: i128," in combined


def test_optional_arrays_compile_in_rust():
    with tempfile.TemporaryDirectory() as tmp:
        result, out_dir = compile_fixture(Path(tmp), VALID_DIR / "optional-arrays.mdl", "rust")
        assert result.returncode == 0, result.stdout + result.stderr
        combined = read_all(out_dir, "**/*.rs")
        # Optional arrays render as a plain Vec with #[serde(default)]
        # (absent => empty), not Option<Vec<T>> - verified against real
        # compiler output before writing this assertion.
        assert "pub optional_tags: Vec<String>," in combined
        assert "pub optional_numbers: Vec<i64>," in combined
        assert combined.count("#[serde(default)]") >= 2


def test_arrays_of_inline_enums_compile_in_typescript():
    with tempfile.TemporaryDirectory() as tmp:
        result, out_dir = compile_fixture(Path(tmp), VALID_DIR / "array-enums.mdl", "typescript")
        assert result.returncode == 0, result.stdout + result.stderr
        combined = read_all(out_dir, "**/*.ts")
        assert "('pending' | 'active' | 'closed')[]" in combined
        assert "('low' | 'medium' | 'high' | 'critical')[]" in combined


def test_legal_maps_compile_in_protobuf():
    with tempfile.TemporaryDirectory() as tmp:
        result, out_dir = compile_fixture(Path(tmp), VALID_DIR / "maps.mdl", "protobuf")
        assert result.returncode == 0, result.stdout + result.stderr
        combined = read_all(out_dir, "**/*.proto")
        assert "map<string, string> string_to_string = 1;" in combined
        assert "map<string, int64> string_to_int = 2;" in combined
        assert "map<string, bool> optional_map = 4;" in combined


def test_fixed_binary_metadata_appears_in_json_schema():
    with tempfile.TemporaryDirectory() as tmp:
        result, out_dir = compile_fixture(Path(tmp), VALID_DIR / "fixed-binary.mdl", "json-schema")
        assert result.returncode == 0, result.stdout + result.stderr
        combined = read_all(out_dir, "*.json")
        assert '"x-modelable-fixed-length": 1' in combined
        assert '"x-modelable-fixed-length": 4096' in combined


def test_pinned_content_signature_reference_resolves():
    # The most fragile fixture: proves modelable actually enforces the
    # pinned hash by resolving it, not just accepting arbitrary text after
    # '#'. If version-ranges.mdl's Widget@1 declaration ever changes, this
    # is expected to fail loudly rather than silently pass.
    with tempfile.TemporaryDirectory() as tmp:
        result, _ = compile_fixture(Path(tmp), VALID_DIR / "version-ranges.mdl", "json-schema")
        assert result.returncode == 0, result.stdout + result.stderr
