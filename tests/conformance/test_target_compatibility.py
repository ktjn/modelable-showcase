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
- Named compatibility profiles (`--policy`/`--profile`, compat/
  release-gate-policy.yaml): a profile's `requirement` adds a semantic
  backward-compatibility check on top of a target's own wire-level
  classification, so a wire-safe protobuf reservation is not automatically
  profile-safe (a reserved-but-removed field is still a source-level
  removal) while a purely additive json-schema evolution passes both.
"""

from __future__ import annotations

import shutil
import subprocess
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parents[2]
COMPAT_DIR = REPO_ROOT / "compat"
RELEASE_GATE_POLICY = COMPAT_DIR / "release-gate-policy.yaml"

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


def validate_compat_with_profile(scenario: str, target: str) -> subprocess.CompletedProcess[str]:
    return run_modelable(
        "validate-compat",
        "--from",
        f"compat/{scenario}/old",
        "--to",
        f"compat/{scenario}/new",
        "--target",
        target,
        "--policy",
        str(RELEASE_GATE_POLICY),
        "--profile",
        "release-gate",
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


# --- Named compatibility profiles (--policy/--profile) -----------------------


def test_release_gate_profile_passes_a_purely_additive_json_schema_change():
    result = run_modelable(
        "validate-compat",
        "--from",
        "compat/baseline-v1",
        "--to",
        "compat/additive-v2",
        "--target",
        "json-schema",
        "--policy",
        str(RELEASE_GATE_POLICY),
        "--profile",
        "release-gate",
    )
    assert result.returncode == 0, result.stdout + result.stderr
    output = normalize(result.stdout)
    assert "status: compatible" in output, output
    assert "policy: threshold=review_required -> pass" in output, output


def test_release_gate_profile_rejects_protobuf_field_number_reuse():
    result = validate_compat_with_profile("protobuf-breaking", "protobuf")
    assert result.returncode == 1, result.stdout + result.stderr
    output = normalize(result.stdout)
    assert "status: breaking" in output, output
    assert "policy: threshold=review_required -> fail" in output, output
    assert "blocking:breaking" in output, output


def test_release_gate_profile_rejects_a_wire_safe_protobuf_field_removal():
    # compat/protobuf-safe reserves the dropped field's number+name, so the
    # *wire* classification alone (test_protobuf_safe_evolution_is_wire_
    # compatible above) is "wire_compatible". A named profile's requirement
    # adds the semantic/source comparison on top of that, and the field is
    # still genuinely removed at the source level - so the same fixture
    # that is wire-safe is NOT profile-safe. This is the concrete reason
    # profiles exist: "does not break the wire format" and "safe to
    # release under this policy" are different questions.
    result = validate_compat_with_profile("protobuf-safe", "protobuf")
    assert result.returncode == 1, result.stdout + result.stderr
    output = normalize(result.stdout)
    assert "status: breaking" in output, output
    assert "removed_field" in output, output
    assert "policy: threshold=review_required -> fail" in output, output
