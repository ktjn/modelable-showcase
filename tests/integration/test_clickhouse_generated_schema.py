"""ClickHouse schema application (IMPLEMENTATION_PLAN.md Task 8.2): prove the
generated sql-clickhouse DDL applies to a real ClickHouse and round-trips
report data, using clickhouse-connect - an actual DB client library - never
shell greps.

Prerequisite: the dev ClickHouse from the repository docker-compose.yml
(clickhouse/clickhouse-server:24.8-alpine, pinned version) must be running:

    docker compose up -d clickhouse

It listens on 127.0.0.1:8123 (HTTP) with synthetic credentials showcase/showcase
and database showcase. Connection settings come from SHOWCASE_CH_* environment
variables with those defaults (shared with scripts/apply-clickhouse-ddl.py,
whose connection_params() this module imports). Tests skip when the server is
unreachable.

Under the pinned 1.7.0 release the FULL generated graph does not apply: the
clickhouse emitter renders optional array fields as `Nullable(Array(T))`
(UPSTREAM_FINDINGS.md #25), an illegal ClickHouse type, so application aborts
at the first such table. The six `reporting.*` tables contain no array columns
and apply cleanly, so they carry the real proof (deterministic sorted
application, representative reporting tables, synthetic-row insert/query-back).
The full-set failure is asserted explicitly in
test_full_generated_set_currently_fails_nullable_array so it flips when the
emitter is fixed.

The clickhouse target emits no secondary indexes at all (that capability is
deferred upstream - `tests/conformance/test_deferred_capabilities.py`), so the
showcase's reporting tables carry no index requirement; that is asserted
explicitly in test_generated_clickhouse_ddl_has_no_secondary_indexes.
"""

from __future__ import annotations

import importlib.util
import shutil
import subprocess
import sys
import time
from datetime import date, datetime, timezone
from decimal import Decimal
from pathlib import Path

import clickhouse_connect
import pytest

REPO_ROOT = Path(__file__).resolve().parents[2]
DDL_DIR = REPO_ROOT / "generated" / "sql-clickhouse"
APPLY_SCRIPT = REPO_ROOT / "scripts" / "apply-clickhouse-ddl.py"
REPORTING_GLOB = "reporting.*.sql"

_apply_spec = importlib.util.spec_from_file_location("apply_clickhouse_ddl", APPLY_SCRIPT)
assert _apply_spec is not None and _apply_spec.loader is not None
_apply_module = importlib.util.module_from_spec(_apply_spec)
sys.modules["apply_clickhouse_ddl"] = _apply_module
_apply_spec.loader.exec_module(_apply_module)

connection_params = _apply_module.connection_params
apply_ddl = _apply_module.apply_ddl


def _can_connect() -> bool:
    # Retry briefly so a cold-starting server does not cause a false skip;
    # bounded so an unreachable host fails fast.
    for _ in range(6):
        params = connection_params()
        params["connect_timeout"] = 2
        try:
            client = clickhouse_connect.get_client(**params)
            try:
                if client.ping():
                    return True
            finally:
                client.close()
        except Exception:
            pass
        time.sleep(2)
    return False


pytestmark = pytest.mark.skipif(
    not _can_connect(),
    reason="ClickHouse not reachable on SHOWCASE_CH_* - run 'docker compose up -d clickhouse' first",
)


def _snake_case(camel: str) -> str:
    out: list[str] = []
    for i, ch in enumerate(camel):
        if ch.isupper() and i > 0:
            out.append("_")
        out.append(ch.lower())
    return "".join(out)


def _utc_naive(value):
    if isinstance(value, datetime) and value.tzinfo is not None:
        return value.astimezone(timezone.utc).replace(tzinfo=None)
    return value


@pytest.fixture(scope="module")
def client():
    c = clickhouse_connect.get_client(**connection_params())
    yield c
    c.close()


@pytest.fixture(scope="module")
def reporting_ddl_dir(tmp_path_factory):
    d = tmp_path_factory.mktemp("reporting-ddl")
    for f in sorted(DDL_DIR.glob(REPORTING_GLOB)):
        shutil.copy2(f, d / f.name)
    return d


@pytest.fixture(scope="module", autouse=True)
def applied_ddl(client, reporting_ddl_dir):
    apply_ddl(reporting_ddl_dir, client)


# --- DDL application ---------------------------------------------------------


def test_apply_script_cli_is_deterministic_sorted_and_idempotent(reporting_ddl_dir):
    uv = shutil.which("uv")
    assert uv is not None, "uv is not on PATH"
    expected = [f.name for f in sorted(DDL_DIR.glob(REPORTING_GLOB))]
    assert expected, "run 'make generate' first (generated/sql-clickhouse missing)"

    first = subprocess.run(
        [uv, "run", str(APPLY_SCRIPT), str(reporting_ddl_dir)],
        cwd=REPO_ROOT,
        capture_output=True,
        text=True,
    )
    assert first.returncode == 0, first.stdout + first.stderr
    applied = [
        line.split("applied ", 1)[1]
        for line in first.stdout.splitlines()
        if line.startswith("applied ") and line.split("applied ", 1)[1] in expected
    ]
    assert applied == expected, "DDL files are not applied in sorted filename order"
    assert f"applied {len(expected)} file(s) from {reporting_ddl_dir}" in first.stdout, first.stdout

    second = subprocess.run(
        [uv, "run", str(APPLY_SCRIPT), str(reporting_ddl_dir)],
        cwd=REPO_ROOT,
        capture_output=True,
        text=True,
    )
    assert second.returncode == 0, "re-applying the DDL must be idempotent: " + second.stdout + second.stderr


def test_full_generated_set_currently_fails_nullable_array():
    # UPSTREAM_FINDINGS.md #25: optional array fields are emitted as
    # Nullable(Array(T)), which ClickHouse rejects (arrays cannot be Nullable).
    # Application aborts at the first such table, so the full generated graph
    # cannot be applied.
    assert DDL_DIR.is_dir(), "run 'make generate' first (generated/sql-clickhouse missing)"
    uv = shutil.which("uv")
    assert uv is not None, "uv is not on PATH"

    result = subprocess.run(
        [uv, "run", str(APPLY_SCRIPT), str(DDL_DIR)],
        cwd=REPO_ROOT,
        capture_output=True,
        text=True,
    )
    assert result.returncode != 0, (
        "the full generated/sql-clickhouse set now applies - UPSTREAM_FINDINGS.md "
        "#25 appears fixed. Update this test (and the finding) instead of leaving "
        "it green by accident.\n" + result.stdout + result.stderr
    )
    output = result.stdout + result.stderr
    assert "failed to apply" in output, output
    assert "Array(String) cannot be inside Nullable" in output, output
    assert "ILLEGAL_TYPE_OF_ARGUMENT" in output, output


def test_representative_reporting_tables_exist(client):
    expected = {
        "daily_schedule",
        "monthly_clinic_stats",
        "outstanding_invoices",
        "patient_clinical_summary",
        "patient_summary",
        "practitioner_revenue",
    }
    rows = client.query(
        "SELECT name FROM system.tables WHERE database = currentDatabase()"
    ).result_rows
    present = {row[0] for row in rows}
    assert expected.issubset(present), f"missing reporting tables: {sorted(expected - present)}"


def test_representative_reporting_columns_and_types(client):
    expected = {
        "outstanding_invoices": {
            "invoice_id": "String",
            "patient_id": "String",
            "encounter_id": "Nullable(String)",
            "subtotal": "Decimal(10, 2)",
            "tax": "Decimal(10, 2)",
            "total": "Decimal(10, 2)",
            "currency": "Nullable(String)",
            "billing_period": "Nullable(String)",
            "status": "LowCardinality(String)",
            "issued_at": "Nullable(DateTime64(9))",
            "due_date": "Nullable(Date)",
            "is_outstanding": "String",
        },
        "daily_schedule": {
            "appointment_id": "String",
            "patient_name": "String",
            "practitioner_id": "String",
            "scheduled_date": "Date",
            "slot": "String",
            "status_label": "String",
            "display_reason": "String",
        },
    }
    for table, expected_types in expected.items():
        rows = client.query(f"DESCRIBE TABLE {table}").result_rows
        actual = {row[0]: row[1] for row in rows}
        assert actual == expected_types, f"{table}: got {actual}, expected {expected_types}"


def test_insert_and_query_back_synthetic_report_rows(client):
    # The tables have no keys, so re-runs would accumulate duplicates; the dev
    # database is disposable, so wipe both tables before each run to stay
    # deterministic.
    client.command("TRUNCATE TABLE daily_schedule")
    client.command("TRUNCATE TABLE outstanding_invoices")

    client.insert(
        "daily_schedule",
        [["appt-1", "Jane Doe", "prac-1", date(2026, 8, 17), "09:00", "scheduled", "routine check"]],
        column_names=[
            "appointment_id",
            "patient_name",
            "practitioner_id",
            "scheduled_date",
            "slot",
            "status_label",
            "display_reason",
        ],
    )
    client.insert(
        "outstanding_invoices",
        [[
            "inv-1",
            "pat-1",
            None,
            Decimal("150.00"),
            Decimal("12.00"),
            Decimal("162.00"),
            "USD",
            "2026-08",
            "issued",
            datetime(2026, 8, 16, 10, 30, tzinfo=timezone.utc),
            date(2026, 9, 15),
            "false",
        ]],
        column_names=[
            "invoice_id",
            "patient_id",
            "encounter_id",
            "subtotal",
            "tax",
            "total",
            "currency",
            "billing_period",
            "status",
            "issued_at",
            "due_date",
            "is_outstanding",
        ],
    )

    schedule_rows = client.query(
        "SELECT appointment_id, patient_name, practitioner_id, scheduled_date, slot, "
        "status_label, display_reason FROM daily_schedule WHERE appointment_id = {id:String}",
        parameters={"id": "appt-1"},
    ).result_rows
    assert schedule_rows == [
        ("appt-1", "Jane Doe", "prac-1", date(2026, 8, 17), "09:00", "scheduled", "routine check")
    ], schedule_rows

    invoice_rows = client.query(
        "SELECT invoice_id, patient_id, encounter_id, subtotal, tax, total, currency, "
        "billing_period, status, issued_at, due_date, is_outstanding "
        "FROM outstanding_invoices WHERE invoice_id = {id:String}",
        parameters={"id": "inv-1"},
    ).result_rows
    assert len(invoice_rows) == 1, invoice_rows
    actual = tuple(_utc_naive(value) for value in invoice_rows[0])
    expected = tuple(
        _utc_naive(value)
        for value in (
            "inv-1",
            "pat-1",
            None,
            Decimal("150.00"),
            Decimal("12.00"),
            Decimal("162.00"),
            "USD",
            "2026-08",
            "issued",
            datetime(2026, 8, 16, 10, 30, tzinfo=timezone.utc),
            date(2026, 9, 15),
            "false",
        )
    )
    assert actual == expected, f"read-back mismatch:\n got {actual}\n exp {expected}"


def test_generated_clickhouse_ddl_has_no_secondary_indexes():
    # The clickhouse target emits no secondary-index DDL of any kind - the
    # capability is deferred upstream (test_deferred_capabilities.py::test_clickhouse_secondary_indexes_are_absent).
    # This showcases that no index requirement is imposed on the applied schema.
    for sql_file in sorted(DDL_DIR.glob("*.sql")):
        assert "CREATE INDEX" not in sql_file.read_text(encoding="utf-8"), sql_file.name