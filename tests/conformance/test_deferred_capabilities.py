"""Deferred capability fixtures and output-semantics checks
(IMPLEMENTATION_PLAN.md Task 3.3, SPEC.md Sec 14): lock in explicit,
CLI-verified behavior for upstream-deferred capabilities so this showcase
never accidentally depends on a capability upstream doesn't actually
implement yet.

Two shapes of deferred capability are covered here, per Task 3.3's own
instruction not to pretend they all behave identically:

- Parseable-but-deferred syntax (the seven tests/conformance/deferred/*.mdl
  fixtures, except composite-keys.mdl): the CLI parses the construct,
  emits an explicit "WARNING DEFERRED" diagnostic, and treats the file as
  valid (exit 0, including under --strict) - the declared configuration
  has no effect on compilation.
- Grammar-level non-support (composite-keys.mdl): the CLI rejects the
  construct outright with a hard SEM error, matching
  tests/conformance/invalid/composite-key.mdl's negative case.

The remaining four deferred capabilities are output semantics rather than
source syntax, and are covered by direct CLI probes instead of fixtures:
ClickHouse secondary index emission, nominal semantic-type identity in
targets other than Rust, model lifecycle status, and projection
event-operation compatibility comparison.

Per SPEC.md Sec 14, the deferred federated-registry CLI entry points
(`registry init`, `registry peer add`, `registry graph`, `registry sync`,
`dependents`, `lineage verify`) are covered here too, with the same
discipline as the .mdl fixtures, even though none of them currently exist
as CLI subcommands at all in modelable==1.7.0 (verified below - `registry`
and `dependents` are unrecognized top-level commands, and `lineage verify`
is the real `lineage` command receiving the literal string "verify" as its
REF argument, which fails cleanly because "verify" is not a valid
`domain.Model@version` reference)."""

from __future__ import annotations

import shutil
import subprocess
import tempfile
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parents[2]
DEFERRED_DIR = Path(__file__).resolve().parent / "deferred"
FIXTURE_FILES = sorted(DEFERRED_DIR.glob("*.mdl"))
MODEL_DIR = REPO_ROOT / "model"

pytestmark = pytest.mark.skipif(
    shutil.which("modelable") is None,
    reason="modelable is not on PATH - run 'make bootstrap' (or source scripts/modelable-env.sh) first",
)


def run_modelable(*args: str, cwd: Path = REPO_ROOT) -> subprocess.CompletedProcess[str]:
    return subprocess.run(["modelable", *args], cwd=cwd, capture_output=True, text=True)


def normalize(text: str) -> str:
    # `rich` line-wraps CLI output to terminal width; normalize whitespace
    # before substring matching (see tests/conformance/test_invalid_fixtures.py).
    return " ".join(text.split())


# Each entry is either:
#   {"exit": 1, "contains": [...]}                      - hard failure
#   {"exit": 0, "warnings": [...]}                       - deferred warning(s), file still valid
FIXTURE_EXPECTATIONS: dict[str, dict] = {
    "composite-keys.mdl": {
        "exit": 1,
        "contains": ["ERROR SEM", "entity must have exactly one @key field"],
    },
    "workspace-registry.mdl": {
        "exit": 0,
        "warnings": [
            "WARNING DEFERRED",
            "`registry {}` is parsed but not enforced by the compiler",
            "declared registry configuration has no effect",
        ],
    },
    "workspace-peers.mdl": {
        "exit": 0,
        "warnings": [
            "WARNING DEFERRED",
            "`peers: [...]` is parsed but not validated by the compiler",
            "declared peer entries have no effect on compilation",
        ],
    },
    "consumer.mdl": {
        "exit": 0,
        "warnings": [
            "WARNING DEFERRED",
            "`consumer {}` declarations are parsed but not tracked by the compiler",
            "declared consumer registration has no effect",
        ],
    },
    "subscription.mdl": {
        "exit": 0,
        "warnings": [
            "WARNING DEFERRED",
            "`subscription {}` is parsed but the compiler implements no runtime subscription behavior",
            "`subscription NAME {}` is parsed but the compiler implements no runtime subscription behavior",
        ],
    },
    "materialisation.mdl": {
        "exit": 0,
        "warnings": [
            "WARNING DEFERRED",
            "`materialisation {}` is parsed but the compiler implements no runtime materialization",
        ],
    },
    "binding-opaque-content.mdl": {
        "exit": 0,
        "warnings": [
            "WARNING DEFERRED",
            "unrecognized content inside `binding {}` is parsed but ignored",
            "only `adapter`, `model`, and `table` are currently honored",
        ],
    },
}


def test_expected_fixtures_present():
    fixture_names = {p.name for p in FIXTURE_FILES}
    assert fixture_names == set(FIXTURE_EXPECTATIONS), (
        f"mismatch between tests/conformance/deferred/*.mdl and this test's expectations: "
        f"fixtures without an expectation: {fixture_names - set(FIXTURE_EXPECTATIONS)}; "
        f"expectations without a fixture: {set(FIXTURE_EXPECTATIONS) - fixture_names}"
    )


def test_at_least_seven_deferred_fixtures_present():
    assert len(FIXTURE_FILES) >= 7, FIXTURE_FILES


@pytest.mark.parametrize("fixture", FIXTURE_FILES, ids=lambda p: p.stem)
def test_deferred_fixture_behaves_as_documented(fixture: Path):
    expectation = FIXTURE_EXPECTATIONS[fixture.name]
    # --strict is used deliberately: it proves a WARNING DEFERRED diagnostic
    # does not get promoted to a failure the way a real SEM/COMPAT/CEL
    # error would - deferred capabilities are non-blocking by design.
    result = run_modelable("validate", str(fixture), "--strict")
    output = normalize(result.stdout + result.stderr)

    assert result.returncode == expectation["exit"], (
        f"{fixture.name}: expected exit {expectation['exit']}, got {result.returncode}\n{result.stdout + result.stderr}"
    )

    if "contains" in expectation:
        for substring in expectation["contains"]:
            assert substring in output, f"{fixture.name}: expected {substring!r} in output\n{output}"
    if "warnings" in expectation:
        for substring in expectation["warnings"]:
            assert substring in output, f"{fixture.name}: expected {substring!r} in output\n{output}"
        assert "is valid" in output, f"{fixture.name}: expected the file to still validate as OK\n{output}"


# --- Output-semantics deferred capabilities (SPEC.md Sec 14) ---------------


def test_clickhouse_secondary_indexes_are_absent():
    # deferred_feature: clickhouse-secondary-indexes. model/patient.mdl
    # declares a real `secondary byName {...}` index on Patient@2. Postgres
    # emits it as a CREATE INDEX statement; ClickHouse silently drops it -
    # the generated table has no secondary-index DDL of any kind, only the
    # mandatory ORDER BY clause.
    with tempfile.TemporaryDirectory() as tmp:
        tmp_path = Path(tmp)
        pg_out = tmp_path / "postgres"
        ch_out = tmp_path / "clickhouse"
        common_args = ["--registry", str(tmp_path / "registry.db"), "--registry-ids", str(tmp_path / "registry-ids.lock")]

        pg_result = run_modelable(
            "compile", str(MODEL_DIR), "--target", "sql-postgres", "--out", str(pg_out), *common_args
        )
        assert pg_result.returncode == 0, pg_result.stdout + pg_result.stderr
        pg_sql = (pg_out / "patient.PatientDb.v2.sql").read_text()
        assert "CREATE INDEX" in pg_sql and "by_name" in pg_sql, pg_sql

        ch_result = run_modelable(
            "compile", str(MODEL_DIR), "--target", "sql-clickhouse", "--out", str(ch_out), *common_args
        )
        assert ch_result.returncode == 0, ch_result.stdout + ch_result.stderr
        ch_sql = (ch_out / "patient.PatientDb.v2.sql").read_text()
        assert "CREATE INDEX" not in ch_sql, ch_sql
        assert "by_name" not in ch_sql, ch_sql
        assert "ORDER BY tuple()" in ch_sql, ch_sql


def test_nominal_semantic_identity_lost_beyond_rust():
    # deferred_feature: nominal-semantic-types-beyond-rust. Rust preserves
    # PatientId as its own newtype wrapping uuid::Uuid (nominal identity
    # kept). JSON Schema has no way to express that distinction and emits
    # an EMIT002 warning ("cannot be represented without loss") instead,
    # falling back to the underlying structural type.
    with tempfile.TemporaryDirectory() as tmp:
        tmp_path = Path(tmp)
        rust_out = tmp_path / "rust"
        json_schema_out = tmp_path / "json-schema"
        common_args = ["--registry", str(tmp_path / "registry.db"), "--registry-ids", str(tmp_path / "registry-ids.lock")]

        rust_result = run_modelable(
            "compile", str(MODEL_DIR), "--target", "rust", "--out", str(rust_out), *common_args
        )
        assert rust_result.returncode == 0, rust_result.stdout + rust_result.stderr
        rust_output = normalize(rust_result.stdout + rust_result.stderr)
        # Rust does emit EMIT002 elsewhere (for CEL-computed projection
        # fields whose inferred type can't be represented cleanly) - that's
        # unrelated to nominal semantic-type identity. What must be absent
        # here specifically is an EMIT002 warning naming PatientId itself.
        assert "Type 'PatientId'" not in rust_output, rust_output
        assert "Type 'patient.PatientId'" not in rust_output, rust_output
        patient_id_files = list(rust_out.glob("**/patient_id.rs"))
        assert len(patient_id_files) == 1, list(rust_out.glob("**/*.rs"))
        assert "pub struct PatientId(pub uuid::Uuid);" in patient_id_files[0].read_text()

        json_result = run_modelable(
            "compile", str(MODEL_DIR), "--target", "json-schema", "--out", str(json_schema_out), *common_args
        )
        assert json_result.returncode == 0, json_result.stdout + json_result.stderr
        json_output = normalize(json_result.stdout + json_result.stderr)
        assert "EMIT002" in json_output
        assert "PatientId" in json_output and "cannot be represented without loss" in json_output, json_output


def test_model_lifecycle_status_not_representable():
    # deferred_feature: model-lifecycle-status. The only place a
    # draft/published/deprecated/retired-style keyword could plausibly go
    # is the version-header modifier slot next to (additive)/(breaking).
    # That slot's grammar only accepts those two tokens - there is no
    # third lifecycle-status token, confirmed directly against the parser
    # rather than by reading docs.
    with tempfile.TemporaryDirectory() as tmp:
        tmp_path = Path(tmp)
        probe = tmp_path / "probe.mdl"
        probe.write_text(
            "domain probe {\n"
            '  owner: "test"\n'
            "  entity Thing @ 1 (draft) {\n"
            "    @key\n"
            "    thingId: uuid\n"
            "  }\n"
            "}\n"
        )
        result = run_modelable("validate", str(probe))
        output = normalize(result.stdout + result.stderr)
        assert result.returncode == 1, output
        assert "ERROR PARSE" in output, output
        assert "BREAKING" in output and "ADDITIVE" in output, output


def test_projection_event_operation_coverage_not_comparable():
    # deferred_feature: projection-event-operation-coverage-compatibility.
    # scheduling.mdl declares `auto projections Appointment @ 1 { ...
    # event on [created, updated] }`, restricting AppointmentEvent to only
    # fire on those two operations. That operation subset is discarded
    # during auto-projection expansion and is not present anywhere on the
    # resulting AppointmentEvent@1 projection - field-level lineage shows
    # every field's direct source but no trace of the [created, updated]
    # restriction, confirming there is nothing upstream could diff between
    # two projection versions to compare operation coverage even if it
    # tried.
    #
    # A more direct test would declare two auto-projected versions of the
    # same model with different `on [...]` subsets and diff the resulting
    # events. That approach hits a separate, real upstream bug instead
    # (see UPSTREAM_FINDINGS.md #9): when two `auto projections` blocks for
    # different versions of the same model exist in one domain, only the
    # first one declared in file order survives - the second is silently
    # dropped, so `probe.ThingEvent@2` never gets created and `diff` fails
    # with an unrelated "unresolved model reference" error rather than
    # anything about operation coverage. Using the real, already-shipped,
    # single-version scheduling.Appointment model sidesteps that bug while
    # still proving the underlying claim.
    result = run_modelable("lineage", "scheduling.AppointmentEvent@1", "--path", "model")
    assert result.returncode == 0, result.stdout + result.stderr
    output = result.stdout

    for field in [
        "appointmentId",
        "patientId",
        "practitionerId",
        "scheduledDate",
        "slot",
        "bufferDuration",
        "status",
        "reason",
        "notes",
        "createdAt",
        "updatedAt",
    ]:
        assert field in output, f"expected field '{field}' in lineage output\n{output}"

    # The operation-subset restriction itself must not appear anywhere.
    # "created"/"updated" only show up here as substrings of the unrelated
    # createdAt/updatedAt field names, never as the `on [created, updated]`
    # operation list.
    assert "operations" not in output.lower()
    assert "on [" not in output


# --- Deferred federated-registry CLI entry points (SPEC.md Sec 14) ---------


def test_registry_subcommand_does_not_exist():
    for args in (["registry", "init"], ["registry", "peer", "add"], ["registry", "graph"], ["registry", "sync"]):
        result = run_modelable(*args)
        output = normalize(result.stdout + result.stderr)
        assert result.returncode == 2, f"modelable {' '.join(args)}: expected exit 2, got {result.returncode}\n{output}"
        assert "No such command 'registry'" in output, output


def test_dependents_subcommand_does_not_exist():
    result = run_modelable("dependents")
    output = normalize(result.stdout + result.stderr)
    assert result.returncode == 2, output
    assert "No such command 'dependents'" in output, output


def test_lineage_verify_is_not_a_real_subcommand():
    # `lineage` is a real command whose only positional argument is REF (a
    # `domain.Model@version` reference), not a command group with a
    # `verify` subcommand - "verify" is parsed as a (invalid) REF, not
    # dispatched to any registry-verification behavior.
    with tempfile.TemporaryDirectory() as tmp:
        tmp_path = Path(tmp)
        (tmp_path / "probe.mdl").write_text(
            "domain probe {\n"
            '  owner: "test"\n'
            "  entity Thing @ 1 (additive) {\n"
            "    @key\n"
            "    thingId: uuid\n"
            "  }\n"
            "}\n"
        )
        result = run_modelable("lineage", "verify", "--path", ".", cwd=tmp_path)
        output = normalize(result.stdout + result.stderr)
        assert result.returncode == 1, output
        assert "REF must be in the form domain.Model@version" in output, output
