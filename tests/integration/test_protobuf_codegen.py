"""Protobuf and gRPC generated code compile (IMPLEMENTATION_PLAN.md Task 7.5):
prove generated .proto graphs compile with a real `protoc`, inspect
schema/service manifests, and verify `--descriptor-set` descriptor artifacts.

protoc is pinned by scripts/install-protoc.sh (see .protoc-version) and placed
on PATH by scripts/modelable-env.sh; the bundled include/ directory provides
the `google/protobuf/timestamp.proto` well-known import. Tests that shell out
to `protoc` skip when it (or its include tree) is not available, mirroring the
javac/go skips elsewhere in this directory.

Two realities are asserted for the graphs:

- The full protobuf graph compiles cleanly in one invocation
  (`test_full_protobuf_graph_compiles`).

- The full gRPC graph does NOT compile in one invocation: every model/projection
  gets its own standalone `.grpc.proto` file, all in the same
  `modelable.<domain>.<version>.scalable` package, so the envelope/service
  definitions collide (UPSTREAM_FINDINGS.md #23). That failure is asserted
  explicitly (`test_full_grpc_graph_currently_fails_duplicate_service_symbols`)
  so it flips when the emitter is fixed - while the schema `.proto` files and
  each individual service file DO compile (`test_grpc_schema_protos_compile`,
  `test_each_grpc_service_proto_compiles_standalone`), which is the documented
  per-service mode that `--descriptor-set` also uses.
"""

from __future__ import annotations

import json
import os
import shutil
import subprocess
import tempfile
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parents[2]
PROTOBUF_DIR = REPO_ROOT / "generated" / "protobuf"
GRPC_DIR = REPO_ROOT / "generated" / "grpc"
MODEL_DIR = REPO_ROOT / "model"
COMPAT_FIXTURE = REPO_ROOT / "compat" / "protobuf-safe" / "new"

PROTOC = shutil.which("protoc")
MODELABLE = shutil.which("modelable")

requires_protoc = pytest.mark.skipif(PROTOC is None, reason="protoc is not on PATH")
requires_modelable = pytest.mark.skipif(MODELABLE is None, reason="modelable is not on PATH")


def _protoc_include_dir() -> Path | None:
    """Locate the google/protobuf well-known-types include tree that ships with
    the pinned protoc. Candidates: the project-local install from
    scripts/install-protoc.sh, then a system install's ../include."""
    if PROTOC is None:
        return None
    version = (REPO_ROOT / ".protoc-version").read_text().strip()
    candidates = [
        REPO_ROOT / "tools" / f"protoc-{version}" / "include",
        Path(PROTOC).resolve().parent / "include",
    ]
    for candidate in candidates:
        if (candidate / "google" / "protobuf" / "timestamp.proto").is_file():
            return candidate
    return None


PROTOC_INCLUDE = _protoc_include_dir()
requires_protoc_include = pytest.mark.skipif(
    PROTOC_INCLUDE is None,
    reason="cannot locate protoc's google/protobuf include tree "
    "(run scripts/install-protoc.sh and add tools/protoc-*/bin to PATH)",
)


def _protoc(files: list[Path], include_root: Path, descriptor_out: Path) -> subprocess.CompletedProcess[str]:
    assert PROTOC is not None
    assert PROTOC_INCLUDE is not None
    return subprocess.run(
        [
            PROTOC,
            "-I",
            str(include_root),
            "-I",
            str(PROTOC_INCLUDE),
            "--descriptor_set_out",
            str(descriptor_out),
            *(str(f) for f in files),
        ],
        capture_output=True,
        text=True,
    )


def _modelable(*args: str, cwd: Path) -> subprocess.CompletedProcess[str]:
    assert MODELABLE is not None
    return subprocess.run(["modelable", *args], cwd=cwd, capture_output=True, text=True)


def load_json(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8"))


# --- protoc graph compilation ------------------------------------------------


@requires_protoc
@requires_protoc_include
def test_protoc_reports_pinned_version():
    assert PROTOC is not None
    version = (REPO_ROOT / ".protoc-version").read_text().strip()
    result = subprocess.run([PROTOC, "--version"], capture_output=True, text=True)
    assert result.returncode == 0, result.stderr
    assert f"libprotoc {version}" in result.stdout, result.stdout


@requires_protoc
@requires_protoc_include
def test_full_protobuf_graph_compiles():
    assert PROTOBUF_DIR.is_dir(), "run 'make generate' first"
    files = sorted(PROTOBUF_DIR.rglob("*.proto"))
    assert files, "generated/protobuf is empty"

    with tempfile.TemporaryDirectory() as tmp:
        result = _protoc(files, PROTOBUF_DIR, Path(tmp) / "graph.desc")
        assert result.returncode == 0, result.stdout + result.stderr
        assert (Path(tmp) / "graph.desc").stat().st_size > 0


@requires_protoc
@requires_protoc_include
def test_grpc_schema_protos_compile():
    assert GRPC_DIR.is_dir(), "run 'make generate' first"
    files = sorted(p for p in GRPC_DIR.rglob("*.proto") if ".grpc.proto" not in p.name)
    assert files, "generated/grpc contains no schema .proto files"

    with tempfile.TemporaryDirectory() as tmp:
        result = _protoc(files, GRPC_DIR, Path(tmp) / "schema.desc")
        assert result.returncode == 0, result.stdout + result.stderr


@requires_protoc
@requires_protoc_include
def test_each_grpc_service_proto_compiles_standalone():
    assert GRPC_DIR.is_dir(), "run 'make generate' first"
    service_files = sorted(p for p in GRPC_DIR.rglob("*.proto") if ".grpc.proto" in p.name)
    assert service_files, "generated/grpc contains no service .proto files"

    with tempfile.TemporaryDirectory() as tmp:
        for service_file in service_files:
            result = _protoc([service_file], GRPC_DIR, Path(tmp) / "service.desc")
            assert result.returncode == 0, f"{service_file}:\n" + result.stdout + result.stderr


@requires_protoc
@requires_protoc_include
def test_full_grpc_graph_currently_fails_duplicate_service_symbols():
    assert GRPC_DIR.is_dir(), "run 'make generate' first"
    files = sorted(GRPC_DIR.rglob("*.proto"))
    assert files, "generated/grpc is empty"

    with tempfile.TemporaryDirectory() as tmp:
        result = _protoc(files, GRPC_DIR, Path(tmp) / "all.desc")

        assert result.returncode != 0, (
            "generated/grpc/ now compiles as one graph - UPSTREAM_FINDINGS.md #23 "
            "appears fixed. Update this test (and the workaround note in #23) "
            "instead of leaving it green by accident.\n"
            + result.stdout
            + result.stderr
        )

        output = result.stdout + result.stderr
        # #23: every .grpc.proto file redeclares the same package-scoped envelope
        # and service definitions, so the union is a mass of duplicate symbols.
        assert "is already defined" in output, output
        assert "modelable.billing.v2.scalable.SchemaIdentity" in output, output
        # Only service .proto files are implicated; the schema .proto files are not.
        for line in output.splitlines():
            if ".proto:" in line and ".grpc.proto" not in line:
                pytest.fail(f"schema proto unexpectedly implicated in #23 failure:\n{output}")


# --- --descriptor-set generation (requires protoc + modelable) --------------


@requires_protoc
@requires_modelable
def test_descriptor_set_generation_for_protobuf_and_grpc():
    with tempfile.TemporaryDirectory() as tmp:
        cwd = Path(tmp)
        pb_out = cwd / "pb"
        gr_out = cwd / "gr"

        pb_result = _modelable("compile", str(MODEL_DIR), "--target", "protobuf", "--descriptor-set", "--out", str(pb_out), cwd=cwd)
        assert pb_result.returncode == 0, pb_result.stdout + pb_result.stderr
        gr_result = _modelable("compile", str(MODEL_DIR), "--target", "grpc", "--descriptor-set", "--out", str(gr_out), cwd=cwd)
        assert gr_result.returncode == 0, gr_result.stdout + gr_result.stderr

        pb_descriptors = sorted(pb_out.rglob("*.descriptor.pb"))
        gr_descriptors = sorted(gr_out.rglob("*.grpc.descriptor.pb"))
        assert pb_descriptors, "protobuf --descriptor-set produced no descriptor files"
        assert gr_descriptors, "grpc --descriptor-set produced no descriptor files"
        for descriptor in [*pb_descriptors, *gr_descriptors]:
            assert descriptor.stat().st_size > 0, f"descriptor {descriptor} is empty"

        # Each schema/service manifest records its own descriptor artifact.
        pb_manifest = load_json(pb_out / "patient" / "Patient.v2" / "schema-manifest.json")
        assert pb_manifest["schemas"][0]["descriptor"]["path"] == "Patient.v2.descriptor.pb"
        assert (pb_out / "patient" / "Patient.v2" / "Patient.v2.descriptor.pb").exists()

        gr_manifest = load_json(gr_out / "patient" / "Patient.v2" / "service-manifest.json")
        assert gr_manifest["descriptor"]["path"] == "Patient.v2.grpc.descriptor.pb"
        assert (gr_out / "patient" / "Patient.v2" / "Patient.v2.grpc.descriptor.pb").exists()


# --- schema/service manifest inspection (reads generated/ directly) ---------


def test_schema_manifest_schema_identity():
    manifest = load_json(PROTOBUF_DIR / "patient" / "Patient.v2" / "schema-manifest.json")
    schema = manifest["schemas"][0]
    assert manifest["target"] == "protobuf"
    assert schema["ref"] == "patient.Patient@2"
    assert schema["kind"] == "entity"
    assert schema["schema_id"] == "modelable://patient/Patient/v2/protobuf"
    assert len(schema["modelable_signature"]) == 64
    assert len(schema["schema_fingerprint"]) == 64


def test_schema_manifest_semantic_type_metadata():
    manifest = load_json(PROTOBUF_DIR / "patient" / "Patient.v2" / "schema-manifest.json")
    schema = manifest["schemas"][0]
    semantic = next(s for s in schema["semantic_types"] if s["ref"] == "patient.PatientId")
    assert semantic["proto_type"] == ".modelable.patient.semantic.PatientId"
    assert semantic["underlying_type"] == "string"
    assert isinstance(semantic["registry_id"], int)

    key_field = next(f for f in schema["fields"] if f["name"] == "patientId")
    assert key_field["proto_name"] == "patient_id"
    assert key_field["key"] is True
    assert key_field["semantic_type"] == "patient.PatientId"


def test_schema_manifest_index_metadata():
    manifest = load_json(PROTOBUF_DIR / "patient" / "Patient.v2" / "schema-manifest.json")
    indexes = manifest["schemas"][0]["indexes"]
    assert indexes["primary"]["key_fields"] == ["patientId"]
    assert indexes["primary"]["unique"] is True
    by_name = next(s for s in indexes["secondary"] if s["index_name"] == "byName")
    assert by_name["key_fields"] == ["legalName"]
    assert by_name["sort_fields"] == [{"field": "dateOfBirth", "direction": "asc"}]
    assert by_name["unique"] is False


def test_service_manifest_read_indexes_and_entity_types():
    manifest = load_json(GRPC_DIR / "patient" / "Patient.v2" / "service-manifest.json")
    assert manifest["target"] == "grpc"
    assert manifest["ref"] == "patient.Patient@2"
    assert set(manifest["services"]) >= {"CommandService", "EntityReadService"}
    assert "patient.Patient@2" in manifest["entity_types"]
    primary = next(i for i in manifest["read_indexes"] if i["index_name"] == "primary")
    assert primary["key_fields"] == ["patientId"]
    assert primary["unique"] is True
    by_name = next(i for i in manifest["read_indexes"] if i["index_name"] == "byName")
    assert by_name["sort_fields"] == ["dateOfBirth"]


@requires_modelable
def test_schema_manifest_reservations_in_evolved_fixture():
    # compat/protobuf-safe/new drops legacyNotes and reserves its number/name;
    # compile it and confirm the reservation survives into the schema manifest
    # and the rendered .proto (UPSTREAM_FINDINGS.md #11 workaround).
    assert COMPAT_FIXTURE.is_dir(), "compat/protobuf-safe/new is missing"

    with tempfile.TemporaryDirectory() as tmp:
        cwd = Path(tmp)
        out = cwd / "out"
        result = _modelable(
            "compile",
            str(COMPAT_FIXTURE),
            "--target",
            "protobuf",
            "--out",
            str(out),
            "--registry-ids",
            str(cwd / "registry-ids.lock"),
            cwd=cwd,
        )
        assert result.returncode == 0, result.stdout + result.stderr

        manifest = load_json(out / "compat" / "Patient.v1" / "schema-manifest.json")
        reservations = manifest["schemas"][0]["reservations"]
        assert reservations["numbers"] == [3]
        assert reservations["names"] == ["legacy_notes"]

        proto = (out / "compat" / "Patient.v1" / "Patient.v1.proto").read_text(encoding="utf-8")
        assert "reserved 3;" in proto
        assert 'reserved "legacy_notes";' in proto