"""Python probe for Modelable-generated dataclasses (IMPLEMENTATION_PLAN.md
Task 7.4): prove generated Python imports, instantiates, and serializes.

The python target emits one module per model/projection under
generated/python/<domain>/<name>.py as frozen dataclasses. Unlike every other
code target, the python modules import and instantiate fine under the pinned
1.7.0 release - every generated module starts with `from __future__ import
annotations`, so broken type references are lazy string annotations rather
than hard errors. Two halves of the current reality are asserted:

- What works (positive proof): every generated module imports, and the five
  value-type dataclasses plus a representative entity construct and serialize
  (`dataclasses.asdict`, then a real `json.dumps`).

- What is broken (flip signal): resolving a field's annotation with
  `typing.get_type_hints` raises NameError whenever it references a value type
  or a semantic type - value types are referenced by their short source name
  while defined under the stable <Domain><Name>V<version> name (finding #19),
  and semantic types are referenced but never emitted at all (finding #20).
  Both are real, logged upstream findings - UPSTREAM_FINDINGS.md #19/#20 -
  broken on the pinned release AND on upstream `main` (verified there: the
  emitter is byte-identical). These assertions must be updated (and the entity
  annotations expected to resolve) once Modelable is re-pinned past a release
  that fixes either finding.
"""

from __future__ import annotations

import importlib
import json
import typing
from dataclasses import asdict
from datetime import date, datetime, time
from decimal import Decimal
from pathlib import Path

import pytest

from billing import billing_invoice_line_v0
from clinical import clinical_diagnosis_v0
from patient import patient_address_v0
from patient import patient_contact_details_v0
from patient import patient_patient_v2
from scheduling import scheduling_time_range_v0

REPO_ROOT = Path(__file__).resolve().parents[2]
PYTHON_DIR = REPO_ROOT / "generated" / "python"

# The five generated value-type classes with no named-type or semantic-typed
# fields. Kept in sync with probes/go's reassembly set and
# tests/integration/test_python_codegen.py's expectations.
VALUE_TYPE_FIXTURES = [
    (
        patient_address_v0.PatientAddressV0(
            street="1 Main",
            city="Springfield",
            postalCode="12345",
            country="US",
        ),
        {"street": "1 Main", "city": "Springfield", "postalCode": "12345", "country": "US"},
    ),
    (
        patient_contact_details_v0.PatientContactDetailsV0(email="ada@example.com"),
        {"email": "ada@example.com", "phone": None},
    ),
    (
        scheduling_time_range_v0.SchedulingTimeRangeV0(start=time(9, 0), end=time(17, 0)),
        {"start": time(9, 0), "end": time(17, 0)},
    ),
    (
        billing_invoice_line_v0.BillingInvoiceLineV0(
            description="clinic visit",
            quantity=2,
            unitPrice=Decimal("10.50"),
            lineTotal=Decimal("21.00"),
        ),
        {
            "description": "clinic visit",
            "quantity": 2,
            "unitPrice": Decimal("10.50"),
            "lineTotal": Decimal("21.00"),
        },
    ),
    (
        clinical_diagnosis_v0.ClinicalDiagnosisV0(
            codes=["R10"],
            diagnosedDate=date(2026, 1, 1),
            severityRank=2,
        ),
        {"codes": ["R10"], "diagnosedDate": date(2026, 1, 1), "description": None, "severityRank": 2},
    ),
]


def test_all_generated_modules_import():
    assert PYTHON_DIR.is_dir(), "run 'make generate' first"
    modules = sorted(PYTHON_DIR.rglob("*.py"))
    assert modules, "generated/python is empty"

    for module_file in modules:
        dotted = ".".join(module_file.relative_to(PYTHON_DIR).with_suffix("").parts)
        importlib.import_module(dotted)


def test_value_types_instantiate_and_serialize():
    for dataclass_value, expected in VALUE_TYPE_FIXTURES:
        payload = asdict(dataclass_value)
        assert payload == expected, (dataclass_value, payload, expected)
        # A real JSON round-trip (default=str renders date/time/Decimal).
        text = json.dumps(payload, default=str)
        assert json.loads(text) == json.loads(json.dumps(expected, default=str))


def test_entity_instantiates_and_serializes():
    # PatientPatientV2 annotates patientId: PatientId, contact: ContactDetails,
    # address: Optional[Address] - all unresolved under the pinned release - but
    # those are lazy strings, so construction and asdict serialization work.
    contact = patient_contact_details_v0.PatientContactDetailsV0(email="ada@example.com")
    entity = patient_patient_v2.PatientPatientV2(
        patientId="patient-1",
        legalName="Ada Lovelace",
        dateOfBirth=date(1815, 12, 10),
        contact=contact,
        preferredLanguage="en",
        createdAt=datetime(2026, 1, 1, 9, 0, 0),
    )

    payload = asdict(entity)
    assert payload["patientId"] == "patient-1"
    assert payload["legalName"] == "Ada Lovelace"
    assert payload["contact"]["email"] == "ada@example.com"
    json.dumps(payload, default=str)


def test_value_type_annotations_resolve():
    hints = typing.get_type_hints(patient_address_v0.PatientAddressV0)
    assert hints == {"street": str, "city": str, "postalCode": str, "country": str}


def test_value_and_semantic_typed_annotations_currently_do_not_resolve():
    # PatientPatientV2's annotations reference PatientId (#20: semantic types are
    # referenced but never emitted), ContactDetails and Address (#19: value types
    # are referenced by short source name but defined as PatientContactDetailsV0 /
    # PatientAddressV0). Resolving them must raise NameError under the pinned
    # release; this is the flip signal for both findings.
    with pytest.raises(NameError) as excinfo:
        typing.get_type_hints(patient_patient_v2.PatientPatientV2)
    assert excinfo.value.name in {"PatientId", "ContactDetails", "Address"}, excinfo.value