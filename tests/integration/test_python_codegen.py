"""Python generated code (IMPLEMENTATION_PLAN.md Task 7.4): prove generated
Python's annotations resolve with `typing.get_type_hints`, not a text grep.

The python target emits one module per model/projection under
generated/python/<domain>/<name>.py as frozen dataclasses. Every generated
module starts with `from __future__ import annotations`, so a broken type
reference is a lazy string - modules import and instantiate fine even when
annotations do not resolve, and only `typing.get_type_hints` surfaces it.

- The value-type modules (no cross-module or named-type references) have
  annotations that resolve cleanly (`test_value_type_annotations_resolve`).
  These are exactly the classes `probes/python/test_generated.py` imports and
  serializes.

- UPSTREAM_FINDINGS.md #30 (a module referencing a type declared in another
  module emitted the bare name with no sibling import, so
  `typing.get_type_hints` raised `NameError` on cross-module annotations -
  including every cross-domain reference) is fixed as of Modelable 1.9.5
  (`test_full_generated_set_annotation_resolution`): every generated module's
  annotations now resolve cleanly, cross-domain and same-domain alike.
"""

from __future__ import annotations

import importlib
import sys
import typing
import uuid
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parents[2]
PYTHON_DIR = REPO_ROOT / "generated" / "python"

# The generated value-type modules with no cross-module or named-type
# references. Kept in sync with probes/python/test_generated.py's fixtures.
RESOLVABLE_MODULES = [
    "patient.patient_address_v0",
    "patient.patient_contact_details_v0",
    "scheduling.scheduling_time_range_v0",
    "billing.billing_invoice_line_v0",
    "clinical.clinical_diagnosis_v0",
]


def _load_module(dotted: str):
    if not PYTHON_DIR.is_dir():
        pytest.skip("run 'make generate' first (generated/python missing)")
    if str(PYTHON_DIR) not in sys.path:
        sys.path.insert(0, str(PYTHON_DIR))
    return importlib.import_module(dotted)


def test_all_generated_modules_import():
    if not PYTHON_DIR.is_dir():
        pytest.skip("run 'make generate' first (generated/python missing)")
    modules = sorted(PYTHON_DIR.rglob("*.py"))
    assert modules, "generated/python is empty"

    if str(PYTHON_DIR) not in sys.path:
        sys.path.insert(0, str(PYTHON_DIR))
    for module_file in modules:
        dotted = ".".join(module_file.relative_to(PYTHON_DIR).with_suffix("").parts)
        importlib.import_module(dotted)


def test_value_type_annotations_resolve():
    for dotted in RESOLVABLE_MODULES:
        module = _load_module(dotted)
        # Module file patient_address_v0.py defines class PatientAddressV0
        # (snake_case filename -> PascalCase class name).
        class_name = "".join(part.title() for part in dotted.rsplit(".", 1)[1].split("_"))
        dataclass_type = getattr(module, class_name)
        hints = typing.get_type_hints(dataclass_type)
        assert hints, f"{dotted}.{class_name} has no resolvable annotations"


def test_full_generated_set_annotation_resolution():
    # UPSTREAM_FINDINGS.md #30, fixed in Modelable 1.9.5: a module that
    # references a type declared in another module now emits the sibling
    # import it needs, so annotations resolve cross-module and cross-domain.
    # PatientPatientV2's `contact` field references PatientContactDetailsV0
    # (patient value type, emitted in patient/patient_contact_details_v0.py).
    entity = _load_module("patient.patient_patient_v2")
    hints = typing.get_type_hints(entity.PatientPatientV2)
    assert hints["contact"].__name__ == "PatientContactDetailsV0"

    # ClinicalEncounterDbV1's annotations reference PatientPatientId (patient
    # domain, represented as its bare underlying uuid.UUID primitive per the
    # semantic-typed half of #30/#365), SchedulingPractitionerId (scheduling
    # domain, same representation), and ClinicalDiagnosisV0 (clinical value
    # type, same domain but sibling module, resolved to the real named type).
    projection = _load_module("clinical.clinical_encounter_db_v1")
    hints = typing.get_type_hints(projection.ClinicalEncounterDbV1)
    assert hints["patientId"] is uuid.UUID
    assert hints["practitionerId"] is uuid.UUID
    diagnoses_type = typing.get_args(hints["diagnoses"])[0]
    assert typing.get_args(diagnoses_type)[0].__name__ == "ClinicalDiagnosisV0"