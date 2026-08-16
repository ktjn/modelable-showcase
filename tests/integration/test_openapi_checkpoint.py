"""Upstream OpenAPI Phase A/B checkpoint (IMPLEMENTATION_PLAN.md Task 9.0).

Task 9.0 requires verifying, before any HTTP API contract work, whether the
Modelable ref in use generates OpenAPI. UPSTREAM_POLICY.md Section 10 mandates
this check; Section 2 forbids hand-written OpenAPI and Section 4.3 requires
non-empty `paths` (Phase B) generated from explicit Modelable contract
declarations.

State on each ref:

- pinned `1.7.0` (`.modelable-version`): no `openapi` target at all -
  `modelable capabilities` omits it and `modelable compile --target` rejects
  it. All tests here skip, recording "missing on the pinned ref".
- pinned `1.8.0` (current `.modelable-version`): `openapi` is an implemented
  target (#353 Phase A component schemas, #357 Phase B paths and operations).
  The probe below exercises an `api {}` block and asserts non-empty `paths`
  with operationId/method/typed path parameters/requestBody/responses, so
  Phase B is confirmed "available" as opposed to merely present in code.
- upstream `ktjn/modelable@main` (canary, install via `MODELABLE_REF=<sha>
  bash scripts/install-modelable.sh`): `openapi` remains implemented; the
  same probe applies.

This is the permanent record Task 9.0 step 4 asks for: later agents re-run
this module against the installed ref instead of re-verifying from scratch.
"""

from __future__ import annotations

import json
import shutil
import subprocess
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parents[2]
PROBE_MODEL = """\
domain openapiprobe {
  owner: "probe"

  entity Patient @ 1 (additive) {
    @key id: uuid
    name: string
  }

  auto projections Patient @ 1 {
    request
    reply
  }

  api Patient @ 1 {
    operation "getPatient" {
      method: GET
      path: "/patients/{id}"
      responses {
        200: PatientReply @ 1
        404: PatientReply @ 1
      }
    }
    operation "createPatient" {
      method: POST
      path: "/patients"
      request: PatientRequest @ 1
      responses {
        201: PatientReply @ 1
      }
    }
  }
}
"""

MODELABLE = shutil.which("modelable")
OPENAPI_IMPLEMENTED: bool | None = None

if MODELABLE is not None:
    result = subprocess.run(
        ["modelable", "capabilities", "--format", "json"],
        cwd=REPO_ROOT,
        capture_output=True,
        text=True,
    )
    if result.returncode == 0:
        OPENAPI_IMPLEMENTED = any(
            entry.get("name") == "openapi" and entry.get("status") == "implemented"
            for entry in json.loads(result.stdout)
        )


def _run_modelable(*args: str, cwd: Path) -> subprocess.CompletedProcess[str]:
    assert MODELABLE is not None
    return subprocess.run(["modelable", *args], cwd=cwd, capture_output=True, text=True)


@pytest.fixture(scope="module")
def openapi_doc(tmp_path_factory):
    probe_dir = tmp_path_factory.mktemp("openapi-probe")
    (probe_dir / "probe.mdl").write_text(PROBE_MODEL, encoding="utf-8")
    out_dir = probe_dir / "out"
    result = _run_modelable("compile", ".", "--target", "openapi", "--out", str(out_dir), cwd=probe_dir)
    assert result.returncode == 0, f"probe compile failed:\n{result.stdout}\n{result.stderr}"
    return json.loads((out_dir / "openapi.json").read_text(encoding="utf-8"))


requires_openapi = pytest.mark.skipif(
    not OPENAPI_IMPLEMENTED,
    reason=(
        "installed Modelable reports no implemented 'openapi' target (older "
        "pins than 1.8.0). Task 9.0 checkpoint: verify with the upstream "
        "canary ref via MODELABLE_REF=<sha> bash scripts/install-modelable.sh"
    ),
)


@requires_openapi
def test_openapi_target_reports_implemented():
    assert MODELABLE is not None
    result = _run_modelable("capabilities", "--format", "json", cwd=REPO_ROOT)
    assert result.returncode == 0, result.stderr
    entries = {e["name"]: e["status"] for e in json.loads(result.stdout)}
    assert entries.get("openapi") == "implemented", entries


@requires_openapi
def test_openapi_document_is_3_1_with_schemas_and_paths(openapi_doc):
    assert openapi_doc["openapi"] == "3.1.0"
    assert openapi_doc["info"]["title"] == "Modelable API"
    assert len(openapi_doc["components"]["schemas"]) > 0, "Phase A: no component schemas"
    assert openapi_doc["paths"], "Phase B: paths is empty - api{} operations are not emitted"


@requires_openapi
def test_openapi_get_operation_has_typed_path_parameter_and_responses(openapi_doc):
    get_operation = openapi_doc["paths"]["/patients/{id}"]["get"]
    assert get_operation["operationId"] == "getPatient"
    assert set(get_operation["responses"]) == {"200", "404"}
    for status in ("200", "404"):
        schema = get_operation["responses"][status]["content"]["application/json"]["schema"]
        assert schema["$ref"] == "#/components/schemas/openapiprobe.PatientReply.v1"
    (parameter,) = get_operation["parameters"]
    assert parameter == {
        "name": "id",
        "in": "path",
        "required": True,
        "schema": {
            "type": "string",
            "format": "uuid",
            "x-modelable-field": {"key": True},
        },
    }
    assert get_operation["x-modelable"] == {
        "domain": "openapiprobe",
        "api": "Patient",
        "apiVersion": 1,
        "name": "getPatient",
    }


@requires_openapi
def test_openapi_post_operation_has_request_body_and_201(openapi_doc):
    post_operation = openapi_doc["paths"]["/patients"]["post"]
    assert post_operation["operationId"] == "createPatient"
    assert post_operation["requestBody"] == {
        "required": True,
        "content": {
            "application/json": {
                "schema": {"$ref": "#/components/schemas/openapiprobe.PatientRequest.v1"}
            }
        },
    }
    assert post_operation["responses"]["201"]["content"]["application/json"]["schema"] == {
        "$ref": "#/components/schemas/openapiprobe.PatientReply.v1"
    }


@requires_openapi
def test_openapi_probe_schemas_include_request_reply_projection(tmp_path_factory):
    assert MODELABLE is not None
    probe_dir = tmp_path_factory.mktemp("openapi-schemas")
    (probe_dir / "probe.mdl").write_text(PROBE_MODEL, encoding="utf-8")
    out_dir = probe_dir / "out"
    result = _run_modelable("compile", ".", "--target", "openapi", "--out", str(out_dir), cwd=probe_dir)
    assert result.returncode == 0, result.stdout + result.stderr
    doc = json.loads((out_dir / "openapi.json").read_text(encoding="utf-8"))
    schemas = doc["components"]["schemas"]
    reply = schemas["openapiprobe.PatientReply.v1"]
    assert reply["type"] == "object"
    assert reply["x-modelable"]["kind"] == "reply"
    assert reply["x-modelable"]["sourceEntity"] == "openapiprobe.Patient@1"
    assert set(reply["properties"]) == {"id", "name"}
    assert "openapiprobe.PatientRequest.v1" in schemas


@requires_openapi
def test_openapi_probe_emission_is_deterministic(tmp_path_factory):
    assert MODELABLE is not None
    first_dir = tmp_path_factory.mktemp("openapi-det-a")
    second_dir = tmp_path_factory.mktemp("openapi-det-b")
    for probe_dir in (first_dir, second_dir):
        (probe_dir / "probe.mdl").write_text(PROBE_MODEL, encoding="utf-8")
        out_dir = probe_dir / "out"
        result = _run_modelable("compile", ".", "--target", "openapi", "--out", str(out_dir), cwd=probe_dir)
        assert result.returncode == 0, result.stdout + result.stderr
    first = (first_dir / "out" / "openapi.json").read_bytes()
    second = (second_dir / "out" / "openapi.json").read_bytes()
    assert first == second, "openapi output is not deterministic"


@requires_openapi
def test_openapi_probe_schemas_validate_with_jsonschema_2020_12(openapi_doc):
    jsonschema = pytest.importorskip("jsonschema")
    schemas = openapi_doc["components"]["schemas"]
    validator = jsonschema.Draft202012Validator(
        {"$schema": "https://json-schema.org/draft/2020-12/schema", "$defs": schemas}
    )
    assert validator.is_valid({"$ref": "#/$defs/openapiprobe.PatientReply.v1"}), (
        "component schemas failed Draft 2020-12 metaschema validation"
    )