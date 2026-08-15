"""Protobuf and gRPC target compatibility (IMPLEMENTATION_PLAN.md Task
4.2, SPEC.md Sec 11): `modelable validate-compat` compares generated
target manifests between two standalone workspace directories, entirely
separate from the model-level `modelable diff` classification exercised
in test_model_compatibility.py.

Every case SPEC.md Sec 11 requires of this task is covered:
- Protobuf reserved name/number safe evolution (compat/protobuf-safe):
  a field is dropped and its number+name reserved, reported
  `wire_compatible`.
- Protobuf field-number/name reuse rejection where supported
  (compat/protobuf-breaking): a field is dropped without reservation and
  a new, unrelated field lands on the same wire number, reported
  `breaking`.
- Protobuf target compatibility command: exercised directly by both
  cases above.
- gRPC target compatibility command: exercised by
  compat/grpc-read-index-change.
- gRPC read-index change producing the upstream-defined
  non-wire-compatible/rebuild classification
  (compat/grpc-read-index-change): a secondary index's key field
  changes; the wire schema is untouched (protobuf: wire_compatible) but
  the read model is not (grpc: requires_read_rebuild).
"""

from __future__ import annotations

import shutil
import subprocess
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parents[2]
COMPAT_DIR = REPO_ROOT / "compat"

pytestmark = pytest.mark.skipif(
    shutil.which("modelable") is None,
    reason="modelable is not on PATH - run 'make bootstrap' (or source scripts/modelable-env.sh) first",
)


def run_modelable(*args: str) -> subprocess.CompletedProcess[str]:
    return subprocess.run(["modelable", *args], cwd=REPO_ROOT, capture_output=True, text=True)


def normalize(text: str) -> str:
    return " ".join(text.split())


def validate_compat(scenario: str, target: str) -> subprocess.CompletedProcess[str]:
    return run_modelable(
        "validate-compat",
        "--from",
        f"compat/{scenario}/old",
        "--to",
        f"compat/{scenario}/new",
        "--target",
        target,
    )


@pytest.mark.parametrize(
    "directory",
    [
        "protobuf-safe/old",
        "protobuf-safe/new",
        "protobuf-breaking/old",
        "protobuf-breaking/new",
        "grpc-read-index-change/old",
        "grpc-read-index-change/new",
    ],
)
def test_compat_fixture_directory_validates_strictly(directory: str):
    result = run_modelable("validate", str(COMPAT_DIR / directory), "--strict")
    assert result.returncode == 0, result.stdout + result.stderr


# --- Protobuf: reservation-safe evolution -----------------------------------


def test_protobuf_safe_evolution_is_wire_compatible():
    result = validate_compat("protobuf-safe", "protobuf")
    assert result.returncode == 0, result.stdout + result.stderr
    output = result.stdout
    assert "target: protobuf" in output, output
    assert "status: wire_compatible" in output, output


# --- Protobuf: field-number/name reuse rejection -----------------------------


def test_protobuf_field_number_reuse_is_rejected():
    result = validate_compat("protobuf-breaking", "protobuf")
    assert result.returncode == 1, result.stdout + result.stderr
    output = normalize(result.stdout)
    assert "target: protobuf" in output, output
    assert "status: breaking" in output, output
    assert "field_number_reused" in output, output
    assert "legacy_notes" in output and "insurance_id" in output, output


# --- gRPC: read-index change classification ----------------------------------


def test_grpc_read_index_change_requires_read_rebuild():
    result = validate_compat("grpc-read-index-change", "grpc")
    assert result.returncode == 1, result.stdout + result.stderr
    output = normalize(result.stdout)
    assert "target: grpc" in output, output
    assert "status: requires_read_rebuild" in output, output
    assert "read_index_changed" in output, output


def test_grpc_read_index_change_leaves_protobuf_wire_schema_untouched():
    # Same two directories, different --target: proves the read-index
    # rebuild classification is a gRPC-specific read-model concern, not a
    # wire-format break - the underlying Protobuf schema never changed.
    result = validate_compat("grpc-read-index-change", "protobuf")
    assert result.returncode == 0, result.stdout + result.stderr
    output = result.stdout
    assert "target: protobuf" in output, output
    assert "status: wire_compatible" in output, output


def test_grpc_success_status_is_read_compatible_not_wire_compatible():
    # The grpc target's success classification is its own distinct label
    # ("read_compatible"), not a reuse of protobuf's "wire_compatible" -
    # confirmed against a scenario with no index change at all so this
    # assertion doesn't depend on the read-index-change fixture above.
    result = validate_compat("protobuf-safe", "grpc")
    assert result.returncode == 0, result.stdout + result.stderr
    assert "status: read_compatible" in result.stdout, result.stdout
