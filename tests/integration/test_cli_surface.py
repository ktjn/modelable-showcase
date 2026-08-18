"""Deterministic import/interchange and non-AI CLI surface
(IMPLEMENTATION_PLAN.md Task 5.4): the real Modelable CLI has a
deterministic command surface beyond validate/resolve/lineage/diff/compile
that no other task in this plan exercises - schema import/interchange,
external-source drift tracking, and graph export. None of it is reported
by `modelable capabilities --format json` (that manifest only covers
target/sql_dialect/model_kind/annotation/deferred_feature), so
capability-coverage.yaml's gate cannot catch drift here on its own; this
suite is what does.

Everything here is the deterministic local path. `generate --from` also
has a freeform natural-language/AI path and `update`/`chat` mutation turns
call a configured LLM provider - none of that is exercised here, per
SPEC.md Sec 2's exclusion of AI-assisted commands from the required
deterministic gate.

Requires `make generate` to have already populated generated/ (the
generate --from tests import this repo's own generated json-schema/odcs
artifacts rather than fetching third-party schemas, so this suite has no
external network dependency).
"""

from __future__ import annotations

import json
import shutil
import subprocess
import tempfile
from pathlib import Path

import pytest
import yaml

REPO_ROOT = Path(__file__).resolve().parents[2]
MODEL_DIR = REPO_ROOT / "model"
GENERATED_DIR = REPO_ROOT / "generated"
IMPORT_DIR = Path(__file__).resolve().parents[1] / "conformance" / "import"
WIDGET_MDL = IMPORT_DIR / "dbt-roundtrip-widget.mdl"

pytestmark = pytest.mark.skipif(
    shutil.which("modelable") is None,
    reason="modelable is not on PATH - run 'make bootstrap' (or source scripts/modelable-env.sh) first",
)


def run_modelable(*args: str, cwd: Path = REPO_ROOT) -> subprocess.CompletedProcess[str]:
    return subprocess.run(["modelable", *args], cwd=cwd, capture_output=True, text=True)


# --- 1. `generate --from` deterministic import ------------------------------
#
# Both importers are currently broken on any contract that references a
# semantic or named type - UPSTREAM_FINDINGS.md #32 (json-schema) and #33
# (odcs). Each test below pins that failure explicitly (the flip signal) and
# separately proves the importer still round-trips primitive-only contracts.

PRIMITIVE_JSON_SCHEMA = """\
{
  "$schema": "https://json-schema.org/draft/2020-12/schema",
  "$id": "patient.Probe.v1",
  "type": "object",
  "title": "Probe",
  "x-modelable": {
    "domain": "patient",
    "name": "Probe",
    "kind": "entity",
    "version": 1,
    "owner": "clinic-frontdesk-team"
  },
  "properties": {
    "id": { "type": "string", "format": "uuid", "x-modelable-field": { "classification": "internal" } },
    "legalName": { "type": "string", "x-modelable-field": { "pii": true } },
    "notes": { "type": "string", "x-modelable-field": { "owner": "clinical-documentation-team" } }
  },
  "required": ["id", "legalName"]
}
"""

PRIMITIVE_ODCS = """\
apiVersion: v3.1.0
kind: DataContract
id: modelable://patient/Probe/v1
name: patient.Probe.v1
version: '1'
domain: patient
status: active
schema:
- name: Probe
  logicalType: object
  physicalName: Probe
  properties:
  - name: id
    logicalType: string
    required: true
    customProperties:
    - property: modelableType
      value: uuid
    primaryKey: true
  - name: legalName
    logicalType: string
    required: true
    customProperties:
    - property: modelableType
      value: string
    - property: modelablePii
      value: true
  customProperties:
  - property: modelableKind
    value: entity
authoritativeDefinitions:
- url: modelable:patient.Probe@1
  type: modelable
customProperties:
- property: modelableRef
  value: patient.Probe@1
- property: modelableKind
  value: entity
"""


def _write_fixture(tmp_path: Path, name: str, content: str) -> Path:
    path = tmp_path / name
    path.write_text(content, encoding="utf-8")
    return path


def test_generate_from_json_schema_round_trips_ref_typed_fields():
    # UPSTREAM_FINDINGS.md #32: the json-schema importer previously mapped `$ref`
    # fields to the literal JSON Pointer (`#/$defs/<Type>`), which the parser
    # rejected. Fixed upstream (landed in the pinned release): `$ref` fields now
    # import as semantic types and the round-trip validates cleanly.
    source = GENERATED_DIR / "json-schema" / "patient.Patient.v2.json"
    assert source.exists(), "run 'make generate' first"
    with tempfile.TemporaryDirectory() as tmp:
        out = Path(tmp) / "imported.mdl"
        result = run_modelable(
            "generate", "--from", str(source), "--format", "json-schema", "--domain", "patient", "--output", str(out)
        )
        assert result.returncode == 0, result.stdout + result.stderr
        validate = run_modelable("validate", str(out))
        assert validate.returncode == 0, validate.stdout + validate.stderr
        text = out.read_text()
        assert "semantic PatientId: string" in text
        assert "semantic ContactDetails: string" in text
        assert "patientId: PatientId" in text


def test_generate_from_json_schema_round_trips_primitive_only_schemas():
    with tempfile.TemporaryDirectory() as tmp:
        fixture = _write_fixture(Path(tmp), "probe.json", PRIMITIVE_JSON_SCHEMA)
        out = Path(tmp) / "imported.mdl"
        result = run_modelable(
            "generate", "--from", str(fixture), "--format", "json-schema", "--domain", "patient", "--output", str(out)
        )
        assert result.returncode == 0, result.stdout + result.stderr
        text = out.read_text()

        validate = run_modelable("validate", str(out))
        assert validate.returncode == 0, validate.stdout + validate.stderr

        # Primitive-only fields (no $ref) round-trip with their governance
        # metadata intact (per-field, not just the object-level annotations).
        assert "@key id: uuid" in text
        assert "@pii legalName: string" in text
        assert '@owner("clinical-documentation-team") notes?: string' in text

        provenance = json.loads((out.parent / f"{out.name}.provenance.json").read_text())
        assert provenance["inputs"]["format"] == "json-schema"
        assert provenance["validation_status"] == "passed"


def test_generate_from_odcs_round_trips_semantic_or_value_typed_fields():
    # UPSTREAM_FINDINGS.md #33: the odcs importer previously dropped the domain
    # qualifier from modelableType/modelableNamedType references and imported
    # them without their `semantic`/`value` declarations, so the imported model
    # failed validation. Fixed upstream (landed in the pinned release): the
    # referenced semantic/value types are now declared and the round-trip
    # validates cleanly.
    source = GENERATED_DIR / "odcs" / "patient.Patient.v2.odcs.yaml"
    assert source.exists(), "run 'make generate' first"
    with tempfile.TemporaryDirectory() as tmp:
        out = Path(tmp) / "imported.mdl"
        result = run_modelable(
            "generate", "--from", str(source), "--format", "odcs", "--domain", "patient", "--output", str(out)
        )
        assert result.returncode == 0, result.stdout + result.stderr

        validate = run_modelable("validate", str(out))
        assert validate.returncode == 0, validate.stdout + validate.stderr
        text = out.read_text()
        assert "semantic PatientId: string" in text
        assert "semantic ContactDetails: string" in text
        assert "patientId: PatientId" in text


def test_generate_from_odcs_round_trips_primitive_only_contracts():
    with tempfile.TemporaryDirectory() as tmp:
        fixture = _write_fixture(Path(tmp), "probe.odcs.yaml", PRIMITIVE_ODCS)
        out = Path(tmp) / "imported.mdl"
        result = run_modelable(
            "generate", "--from", str(fixture), "--format", "odcs", "--domain", "patient", "--output", str(out)
        )
        assert result.returncode == 0, result.stdout + result.stderr
        text = out.read_text()

        validate = run_modelable("validate", str(out))
        assert validate.returncode == 0, validate.stdout + validate.stderr

        assert "@key id: uuid" in text
        assert "@pii legalName: string" in text


# --- 2. `attach` -------------------------------------------------------------


def _attach_workspace() -> Path:
    tmp = Path(tempfile.mkdtemp())
    shutil.copy(WIDGET_MDL, tmp / WIDGET_MDL.name)
    return tmp


def test_attach_reports_no_drift_when_source_matches():
    workspace = _attach_workspace()
    with tempfile.TemporaryDirectory() as compiled_tmp:
        compiled_dir = Path(compiled_tmp)
        compile_result = run_modelable(
            "compile",
            str(WIDGET_MDL),
            "--target",
            "dbt-yaml",
            "--out",
            str(compiled_dir),
            "--registry",
            str(compiled_dir / "registry.db"),
            "--registry-ids",
            str(compiled_dir / "registry-ids.lock"),
        )
        assert compile_result.returncode == 0, compile_result.stdout + compile_result.stderr
        source_yaml = compiled_dir / "importroundtrip.Widget.v1.yml"
        assert source_yaml.exists()

        result = run_modelable(
            "attach",
            "importroundtrip.Widget@1",
            "--source",
            str(source_yaml),
            "--source-format",
            "dbt",
            "--path",
            str(workspace),
            "--preview",
        )
        assert result.returncode == 0, result.stdout + result.stderr
        assert "already matches" in result.stdout
        assert "no new version created" in result.stdout
        # --preview must not have written anything.
        assert not (workspace / f"{WIDGET_MDL.name}.attachments.json").exists()


def test_attach_reports_additive_drift_from_a_mutated_dbt_source():
    workspace = _attach_workspace()
    mutated_source = IMPORT_DIR / "dbt-roundtrip-widget-additive.yml"
    result = run_modelable(
        "attach",
        "importroundtrip.Widget@1",
        "--source",
        str(mutated_source),
        "--source-format",
        "dbt",
        "--path",
        str(workspace),
    )
    assert result.returncode == 0, result.stdout + result.stderr
    assert "new version 2 (additive)" in result.stdout

    updated = (workspace / WIDGET_MDL.name).read_text()
    assert "Widget @ 2 (additive)" in updated
    assert "notes" in updated

    sidecar = json.loads((workspace / f"{WIDGET_MDL.name}.attachments.json").read_text())
    record = sidecar[-1]
    assert record["change_kind"] == "additive"
    assert record["from_version"] == 1
    assert record["to_version"] == 2
    assert [c["kind"] for c in record["changes"]] == ["added_field"]
    assert record["changes"][0]["field_name"] == "notes"


def test_attach_reports_breaking_drift_from_a_mutated_dbt_source():
    workspace = _attach_workspace()
    mutated_source = IMPORT_DIR / "dbt-roundtrip-widget-breaking.yml"
    result = run_modelable(
        "attach",
        "importroundtrip.Widget@1",
        "--source",
        str(mutated_source),
        "--source-format",
        "dbt",
        "--path",
        str(workspace),
    )
    assert result.returncode == 0, result.stdout + result.stderr
    assert "new version 2 (breaking)" in result.stdout

    updated = (workspace / WIDGET_MDL.name).read_text()
    assert "Widget @ 2 (breaking)" in updated
    assert "quantity" not in updated.split("Widget @ 2")[1]

    sidecar = json.loads((workspace / f"{WIDGET_MDL.name}.attachments.json").read_text())
    record = sidecar[-1]
    assert record["change_kind"] == "breaking"
    assert [c["kind"] for c in record["changes"]] == ["removed_field"]
    assert record["changes"][0]["field_name"] == "quantity"


# --- 3. `spec add` / `spec status` / `spec diff` -----------------------------


def _spec_workspace(source: Path) -> Path:
    tmp = Path(tempfile.mkdtemp())
    shutil.copy(WIDGET_MDL, tmp / WIDGET_MDL.name)
    add_result = run_modelable(
        "spec",
        "add",
        "widget-dbt",
        "--kind",
        "dbt",
        "--source",
        str(source),
        "--source-name",
        "Widget",
        "--ref",
        "importroundtrip.Widget@1",
        "--path",
        str(tmp),
    )
    assert add_result.returncode == 0, add_result.stdout + add_result.stderr
    specs_yaml = yaml.safe_load((tmp / ".modelable" / "specs.yml").read_text())
    assert specs_yaml["specs"][0]["id"] == "widget-dbt"
    return tmp


def test_spec_status_reports_clean_when_source_matches():
    with tempfile.TemporaryDirectory() as compiled_tmp:
        compiled_dir = Path(compiled_tmp)
        compile_result = run_modelable(
            "compile",
            str(WIDGET_MDL),
            "--target",
            "dbt-yaml",
            "--out",
            str(compiled_dir),
            "--registry",
            str(compiled_dir / "registry.db"),
            "--registry-ids",
            str(compiled_dir / "registry-ids.lock"),
        )
        assert compile_result.returncode == 0, compile_result.stdout + compile_result.stderr
        source_yaml = compiled_dir / "importroundtrip.Widget.v1.yml"

        workspace = _spec_workspace(source_yaml)
        status = run_modelable("spec", "status", "--path", str(workspace), "--json")
        assert status.returncode == 0, status.stdout + status.stderr
        report = json.loads(status.stdout)["specs"][0]
        assert report["status"] == "clean"
        assert report["change_count"] == 0


def test_spec_status_and_diff_report_drifted_when_source_mutated():
    mutated_source = IMPORT_DIR / "dbt-roundtrip-widget-additive.yml"
    workspace = _spec_workspace(mutated_source)

    status = run_modelable("spec", "status", "--path", str(workspace), "--json")
    assert status.returncode == 0, status.stdout + status.stderr
    report = json.loads(status.stdout)["specs"][0]
    assert report["status"] == "drifted"
    assert report["change_kind"] == "additive"
    assert report["change_count"] == 1

    diff = run_modelable("spec", "diff", "widget-dbt", "--path", str(workspace), "--json")
    assert diff.returncode == 0, diff.stdout + diff.stderr
    diff_report = json.loads(diff.stdout)
    assert diff_report["status"] == "drifted"
    assert diff_report["changes"][0]["kind"] == "added_field"
    assert diff_report["changes"][0]["field_name"] == "notes"


# --- 4. `graph export` -------------------------------------------------------


def test_graph_export_contains_expected_domain_and_model_identities():
    with tempfile.TemporaryDirectory() as tmp:
        out = Path(tmp) / "graph.json"
        result = run_modelable("graph", "export", str(MODEL_DIR), "--out", str(out))
        assert result.returncode == 0, result.stdout + result.stderr

        graph = json.loads(out.read_text())
        assert graph["kind"] == "workspace_graph"
        node_ids = {n["id"] for n in graph["nodes"]}
        assert "domain:patient" in node_ids
        assert "model:patient.Patient" in node_ids
        assert "projection:reporting.PatientSummary" in node_ids

        owns_edges = [e for e in graph["edges"] if e["kind"] == "owns"]
        assert {"source": "domain:patient", "target": "model:patient.Patient"} in [
            {"source": e["source"], "target": e["target"]} for e in owns_edges
        ]


def test_graph_export_focus_narrows_to_neighborhood():
    with tempfile.TemporaryDirectory() as tmp:
        full_out = Path(tmp) / "full.json"
        focus_out = Path(tmp) / "focus.json"
        run_modelable("graph", "export", str(MODEL_DIR), "--out", str(full_out))
        focus_result = run_modelable(
            "graph", "export", str(MODEL_DIR), "--focus", "patient.Patient@2", "--out", str(focus_out)
        )
        assert focus_result.returncode == 0, focus_result.stdout + focus_result.stderr

        full_graph = json.loads(full_out.read_text())
        focus_graph = json.loads(focus_out.read_text())
        assert len(focus_graph["nodes"]) < len(full_graph["nodes"])

        focus_node_ids = {n["id"] for n in focus_graph["nodes"]}
        assert "model_version:patient.Patient@2" in focus_node_ids
        assert "field:patient.Patient@2.patientId" in focus_node_ids
        # Unrelated domains must not appear in a narrowly-focused export.
        assert "domain:audit" not in focus_node_ids


# --- 5. `codegen formats` / `codegen types` ----------------------------------


def _implemented_targets() -> set[str]:
    result = run_modelable("capabilities", "--format", "json")
    assert result.returncode == 0, result.stdout + result.stderr
    capabilities = json.loads(result.stdout)
    return {c["name"] for c in capabilities if c.get("category") == "target" and c.get("status") == "implemented"}


def test_codegen_formats_matches_capabilities_implemented_targets():
    result = run_modelable("codegen", "formats")
    assert result.returncode == 0, result.stdout + result.stderr
    listed = {
        line.strip().lstrip("-").split(":", 1)[0].strip()
        for line in result.stdout.splitlines()
        if line.strip().startswith("-")
    }
    assert listed == _implemented_targets()


def test_codegen_types_returns_nonempty_type_mapping_for_rust():
    result = run_modelable("codegen", "types", "--format", "rust")
    assert result.returncode == 0, result.stdout + result.stderr
    assert "Type shape catalog:" in result.stdout
    catalog_lines = [
        line for line in result.stdout.splitlines() if line.strip().startswith("-") and ":" in line
    ]
    assert len(catalog_lines) >= 3, result.stdout


# --- 6. `transform --explain` -------------------------------------------------


def test_transform_explain_produces_a_nonempty_explanation():
    result = run_modelable("transform", "patient.Patient@2", "--path", "model", "--to", "typescript", "--explain")
    assert result.returncode == 0, result.stdout + result.stderr
    assert result.stdout.startswith("Explanation:")
    explanation_line = result.stdout.splitlines()[0]
    assert len(explanation_line) > len("Explanation:")
    assert "export interface" in result.stdout
