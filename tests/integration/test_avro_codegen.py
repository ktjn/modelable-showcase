"""Avro generated code is valid Avro (IMPLEMENTATION_PLAN.md Task 1.3 follow-up,
re-pin to Modelable 1.9.5): `avro` was a canary-only target under the pinned
1.9.4 release (UPSTREAM_FINDINGS.md #44 - `compile --target avro` crashed on
any field with a default value) and had no manifest entry or test coverage
here as a result. 1.9.5 includes the upstream fix (ktjn/modelable#417); this
is that target's first real coverage in this repo.

Per this repo's own standing rule (prefer a real downstream tool over a text
assertion), every emitted `.avsc` schema is parsed with `fastavro` - a real
Avro schema parser, not a JSON/dict-shape assertion - the same bar every
other target's probe here is held to (protoc for protobuf/grpc, a real
psycopg/clickhouse-connect connection for the SQL targets, etc.).
"""

from __future__ import annotations

import json
from pathlib import Path

import fastavro

REPO_ROOT = Path(__file__).resolve().parents[2]
AVRO_DIR = REPO_ROOT / "generated" / "avro"


def _avsc_files() -> list[Path]:
    assert AVRO_DIR.is_dir(), "run 'make generate' first"
    files = sorted(AVRO_DIR.rglob("*.avsc"))
    assert files, "generated/avro is empty"
    return files


def test_every_generated_avro_schema_parses_with_a_real_avro_parser():
    for path in _avsc_files():
        schema = json.loads(path.read_text(encoding="utf-8"))
        # Raises fastavro.schema.SchemaParseException on anything that isn't
        # genuinely valid Avro - this is the real acceptance bar, not just
        # "modelable didn't crash while emitting the file".
        fastavro.parse_schema(schema)


def test_decimal_fields_use_the_avro_decimal_logical_type():
    # UPSTREAM_FINDINGS.md #44's crash reproduction was specifically a
    # defaulted decimal field (billing.mdl's `tax: decimal(10, 2) = 0`).
    # Confirm the fixed emitter now renders it as a real Avro decimal
    # logical type, not just "doesn't crash".
    schema = json.loads((AVRO_DIR / "billing" / "InvoiceLine.v0.avsc").read_text(encoding="utf-8"))
    fastavro.parse_schema(schema)
    fields = {f["name"]: f for f in schema["fields"]}
    assert fields["unitPrice"]["type"] == {
        "type": "bytes",
        "logicalType": "decimal",
        "precision": 10,
        "scale": 2,
    }


def test_multi_field_named_type_references_are_lossy():
    # UPSTREAM_FINDINGS.md #47 flip test: `_type_schema`'s NamedType branch
    # only ever attempts semantic-type resolution, so any reference to a
    # multi-field value type degrades to a lossy fallback - same-domain
    # references included, not just cross-domain (PatientDb.v2's `contact`
    # references PatientContactDetailsV0 within the same `patient` domain;
    # PatientEvent.v2's `address` is likewise same-domain). Pinned here so
    # this flips loudly (delete this test, strengthen the assertion above)
    # the day upstream resolves it for avro too.
    event_schema = json.loads((AVRO_DIR / "patient" / "PatientEvent.v2.avsc").read_text(encoding="utf-8"))
    fastavro.parse_schema(event_schema)
    event_fields = {f["name"]: f for f in event_schema["fields"]}
    assert event_fields["address"]["type"] == ["null", "string"]

    patient_schema = json.loads((AVRO_DIR / "patient" / "Patient.v2.avsc").read_text(encoding="utf-8"))
    fastavro.parse_schema(patient_schema)
    patient_fields = {f["name"]: f for f in patient_schema["fields"]}
    assert patient_fields["contact"]["type"] == "string"
