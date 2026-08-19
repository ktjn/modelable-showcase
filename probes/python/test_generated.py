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
  `typing.get_type_hints` raises NameError whenever it references a value
  type - value types are emitted under their stable <Domain><Name>V<version>
  name in a sibling file, but nothing that references one ever imports it
  (finding #19/#30). Re-verified against the current pin (1.9.4): the
  semantic-type half of #19/#20 is no longer reproducible this way - a
  semantic-typed field (e.g. `clinical.Encounter.patientId`) is now emitted
  as its bare underlying primitive (`patientId: UUID`) rather than an
  unimported semantic-type name, so it resolves fine either way. The value-
  type half is unchanged: `clinical.Encounter.diagnoses` (same domain) and
  `patient.Patient.contact` (same domain) both still reference an unimported
  stable name (`ClinicalDiagnosisV0`, `PatientContactDetailsV0`) and still
  raise NameError - contradicts UPSTREAM_FINDINGS.md #19's "Fixed... for
  same-module references" claim, which was verified only against a value
  type's own file self-resolving (this file's test_value_type_annotations_resolve,
  still true), never against a sibling file that actually references one.
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
from clinical import clinical_encounter_v1
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


def test_value_typed_annotations_currently_do_not_resolve():
    # PatientPatientV2.contact references patient.ContactDetails, emitted
    # under the stable name PatientContactDetailsV0 in a sibling file
    # (patient_contact_details_v0.py) that patient_patient_v2.py never
    # imports. Resolving the annotation must raise NameError under the
    # pinned release (UPSTREAM_FINDINGS.md #19/#30); this is the flip
    # signal - PatientContactDetailsV0 is the first unresolvable name
    # `typing.get_type_hints` hits (fields are resolved in declaration
    # order, and `contact` comes before the optional `address`).
    with pytest.raises(NameError) as excinfo:
        typing.get_type_hints(patient_patient_v2.PatientPatientV2)
    assert excinfo.value.name == "PatientContactDetailsV0", excinfo.value


def test_semantic_typed_annotations_now_emit_as_bare_primitives():
    # As of the pinned 1.9.4 release, a cross-domain semantic-typed field is
    # emitted as its bare underlying primitive rather than an unimported
    # semantic-type name (clinical.Encounter.patientId/practitionerId are
    # semantic-typed refs to patient.PatientId/scheduling.PractitionerId in
    # model/clinical.mdl, but generated/python/clinical/clinical_encounter_v1.py
    # declares them `patientId: UUID`/`practitionerId: UUID`) - this sidesteps
    # the original NameError from UPSTREAM_FINDINGS.md #20's reproduction,
    # though it is a representation change rather than an import fix.
    #
    # Checked as a raw `__annotations__` string, not via `typing.get_type_hints`:
    # the class also has an unrelated broken value-type field (`diagnoses`,
    # see test_same_domain_value_typed_annotation_also_does_not_resolve
    # below), and `get_type_hints` evaluates every field together, so it
    # raises on that field before this one could be checked in isolation.
    annotations = clinical_encounter_v1.ClinicalEncounterV1.__annotations__
    assert annotations["patientId"] == "UUID"
    assert annotations["practitionerId"] == "UUID"


def test_same_domain_value_typed_annotation_also_does_not_resolve():
    # clinical.Encounter.diagnoses references clinical.Diagnosis, emitted
    # under the stable name ClinicalDiagnosisV0 in a sibling file within the
    # *same* domain (clinical_diagnosis_v0.py) that
    # clinical_encounter_v1.py never imports - proves the missing-import gap
    # is not specific to patient.Patient/cross-file coincidence.
    with pytest.raises(NameError) as excinfo:
        typing.get_type_hints(clinical_encounter_v1.ClinicalEncounterV1)
    assert excinfo.value.name == "ClinicalDiagnosisV0", excinfo.value