"""Python generated code (IMPLEMENTATION_PLAN.md Task 7.4): prove generated
Python's annotations resolve with `typing.get_type_hints`, not a text grep.

The python target emits one module per model/projection under
generated/python/<domain>/<name>.py as frozen dataclasses. Every generated
module starts with `from __future__ import annotations`, so under the pinned
1.7.0 release the modules import and instantiate fine - the broken type
references are lazy strings. This file tests both halves of the current
reality:

- The five value-type modules (no named-type or semantic-typed fields) have
  annotations that resolve cleanly (`test_value_type_annotations_resolve`).
  These are exactly the classes `probes/python/test_generated.py` imports and
  serializes.

- Everything else does not resolve: value types are referenced by their short
  source name while defined under the stable <Domain><Name>V<version> name,
  and semantic types are referenced but never emitted at all
  (`test_full_generated_set_currently_fails_annotation_resolution`). Both are
  real, logged upstream findings - UPSTREAM_FINDINGS.md #19 and #20 - broken
  on the pinned release AND on upstream `main` (verified there: the emitter is
  byte-identical). This failure assertion is the flip signal: it must be
  updated (and the entity annotations expected to resolve) once Modelable is
  re-pinned past a release that fixes either finding.
"""

from __future__ import annotations

import importlib
import sys
import typing
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parents[2]
PYTHON_DIR = REPO_ROOT / "generated" / "python"

# The five generated value-type modules with no named-type or semantic-typed
# fields. Kept in sync with probes/python/test_generated.py's fixtures.
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


def test_full_generated_set_currently_fails_annotation_resolution():
    # PatientPatientV2's annotations reference PatientId (#20: semantic types
    # are referenced but never emitted), ContactDetails and Address (#19: value
    # types are referenced by short source name but defined as
    # PatientContactDetailsV0 / PatientAddressV0).
    entity = _load_module("patient.patient_patient_v2")
    with pytest.raises(NameError) as excinfo:
        typing.get_type_hints(entity.PatientPatientV2)
    assert excinfo.value.name in {"PatientId", "ContactDetails", "Address"}, excinfo.value

    # ClinicalEncounterDbV1's annotations reference EncounterId,
    # PatientPatientId, SchedulingPractitionerId (#20) and Diagnosis (#19) -
    # including the cross-domain pascalized semantic spellings.
    projection = _load_module("clinical.clinical_encounter_db_v1")
    with pytest.raises(NameError) as excinfo:
        typing.get_type_hints(projection.ClinicalEncounterDbV1)
    assert excinfo.value.name in {
        "EncounterId",
        "PatientPatientId",
        "SchedulingPractitionerId",
        "Diagnosis",
    }, excinfo.value