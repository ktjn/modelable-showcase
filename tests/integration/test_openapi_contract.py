"""OpenAPI contract generation and consumption (IMPLEMENTATION_PLAN.md Task
9.6). `generated/openapi/openapi.json` is produced by `make generate` (the
`openapi` target is discovered dynamically by `scripts/generate-all.py` -
see Task 9.0's `test_openapi_checkpoint.py` - so no code change was needed to
start generating it). This module is the "showcase consumption" half of
Task 9.6:

- non-empty `paths`, generated from the real `api {}` declarations added to
  `model/patient.mdl`/`scheduling.mdl`/`clinical.mdl`/`billing.mdl` for the
  `POST` create operations built in Tasks 9.2-9.4 (`createPatient`,
  `createAppointment`, `createEncounter`, `createInvoice`);
- independent validation with `openapi-spec-validator` (a parser separate
  from whatever validation Modelable's own test suite performs, per
  `UPSTREAM_POLICY.md` Sec 4.4/5.3) - this is what caught
  UPSTREAM_FINDINGS.md #38, so the "currently fails" case is pinned rather
  than silently skipped, the same pattern
  `tests/integration/test_postgres_generated_schema.py` uses for #27.

`GET /api/patients/:id/summary` (Task 9.4) and `GET /api/analytics/clinic`
(Task 9.5) are intentionally out of scope here: both return hand-composed
aggregation shapes with no generated Modelable projection to declare an
`api {}` operation against, and SPEC.md/UPSTREAM_POLICY.md forbid a second
handwritten schema for what Modelable would otherwise generate.

The Rust-side half of Task 9.6 (HTTP contract tests asserting the running
Axum API's actual request/response shapes conform to this document) is
`apps/api/tests/openapi_contract.rs`.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

import pytest

REPO_ROOT = Path(__file__).resolve().parents[2]
OPENAPI_PATH = REPO_ROOT / "generated" / "openapi" / "openapi.json"

pytestmark = pytest.mark.skipif(
    not OPENAPI_PATH.exists(), reason="run 'make generate' first (generated/openapi/openapi.json missing)"
)


@pytest.fixture(scope="module")
def doc() -> dict[str, Any]:
    return json.loads(OPENAPI_PATH.read_text(encoding="utf-8"))


CREATE_OPERATIONS = {
    "/api/patients": ("createPatient", "patient.PatientRequest.v2", "patient.PatientReply.v2"),
    "/api/appointments": ("createAppointment", "scheduling.AppointmentRequest.v1", "scheduling.AppointmentReply.v1"),
    "/api/encounters": ("createEncounter", "clinical.EncounterRequest.v1", "clinical.EncounterReply.v1"),
    "/api/invoices": ("createInvoice", "billing.InvoiceRequest.v2", "billing.InvoiceReply.v2"),
}


def test_document_is_openapi_31_with_nonempty_paths(doc: dict[str, Any]) -> None:
    assert doc["openapi"] == "3.1.0"
    assert doc["paths"], "Task 9.6: paths is empty - no api{} operations are emitted"


def test_declared_create_operations_match_the_api_blocks(doc: dict[str, Any]) -> None:
    for path, (operation_id, request_schema, reply_schema) in CREATE_OPERATIONS.items():
        operation = doc["paths"][path]["post"]
        assert operation["operationId"] == operation_id, path
        assert operation["requestBody"]["content"]["application/json"]["schema"]["$ref"] == (
            f"#/components/schemas/{request_schema}"
        ), path
        assert operation["responses"]["201"]["content"]["application/json"]["schema"]["$ref"] == (
            f"#/components/schemas/{reply_schema}"
        ), path


def _collect_component_refs(node: Any, refs: set[str]) -> set[str]:
    if isinstance(node, dict):
        ref = node.get("$ref")
        if isinstance(ref, str) and ref.startswith("#/components/schemas/"):
            refs.add(ref.removeprefix("#/components/schemas/"))
        for value in node.values():
            _collect_component_refs(value, refs)
    elif isinstance(node, list):
        for item in node:
            _collect_component_refs(item, refs)
    return refs


def test_patient_create_schemas_have_no_dangling_refs(doc: dict[str, Any]) -> None:
    # Patient has no ref<> fields, so its schemas are unaffected by #38 and
    # should resolve cleanly - the counter-case to the pin below.
    schemas = doc["components"]["schemas"]
    for name in ("patient.PatientRequest.v2", "patient.PatientReply.v2"):
        refs = _collect_component_refs(schemas[name], set())
        missing = {ref for ref in refs if ref not in schemas}
        assert not missing, f"{name} has unexpectedly dangling refs: {missing}"


def test_appointment_encounter_invoice_reply_schemas_have_the_known_dangling_ref(doc: dict[str, Any]) -> None:
    # UPSTREAM_FINDINGS.md #38 pin: a ref<Domain.Entity@N> field's $ref
    # target (the bare entity) is never emitted as a component schema. This
    # must be updated (not silently deleted) once #38 is fixed upstream.
    schemas = doc["components"]["schemas"]
    expected_dangling = {
        "scheduling.AppointmentReply.v1": {"patient.Patient.v2"},
        "clinical.EncounterReply.v1": {"scheduling.Appointment.v1"},
        "billing.InvoiceReply.v2": {"clinical.Encounter.v1"},
    }
    for name, expected in expected_dangling.items():
        refs = _collect_component_refs(schemas[name], set())
        missing = {ref for ref in refs if ref not in schemas}
        assert missing == expected, (
            f"{name}: dangling refs changed from the #38 pin ({expected}) to {missing} - "
            "update UPSTREAM_FINDINGS.md #38 and this pin together"
        )


def test_full_document_currently_fails_independent_validation(doc: dict[str, Any]) -> None:
    # UPSTREAM_FINDINGS.md #38: an independent OpenAPI 3.1 parser/validator
    # (openapi-spec-validator, separate from Modelable's own test suite -
    # UPSTREAM_POLICY.md Sec 4.4/5.3) cannot resolve the full document today
    # because of the dangling ref<> component refs above. This is the flip
    # signal: once #38 is fixed upstream, this test should be replaced with
    # a plain `validate(doc)` call that is expected to succeed.
    from openapi_spec_validator import validate
    from referencing.exceptions import PointerToNowhere

    with pytest.raises(PointerToNowhere):
        validate(doc)


def test_patient_request_and_reply_schemas_individually_validate() -> None:
    # The unaffected counterpart to the flip test above: build a standalone
    # document containing only the patient schemas (which have no ref<>
    # fields, so no dangling refs) and confirm openapi-spec-validator
    # resolves and validates it cleanly - proving the failure above is
    # specifically the #38 ref<> gap, not a general document malformation.
    from openapi_spec_validator import validate

    full = json.loads(OPENAPI_PATH.read_text(encoding="utf-8"))
    schemas = full["components"]["schemas"]
    needed = {"patient.PatientRequest.v2", "patient.PatientReply.v2"}
    needed |= _collect_component_refs({name: schemas[name] for name in needed}, set())
    standalone = {
        "openapi": full["openapi"],
        "info": full["info"],
        "components": {"schemas": {name: schemas[name] for name in needed}},
        "paths": {"/api/patients": full["paths"]["/api/patients"]},
    }
    validate(standalone)
