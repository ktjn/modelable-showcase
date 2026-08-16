"""PostgreSQL schema application (IMPLEMENTATION_PLAN.md Task 8.1): prove the
generated sql-postgres DDL applies to a real PostgreSQL and round-trips data,
using psycopg - an actual DB client library - never shell greps.

Prerequisite: the dev PostgreSQL from the repository docker-compose.yml
(postgres:17-alpine, pinned major version) must be running:

    docker compose up -d postgres

It listens on 127.0.0.1:5433 with synthetic credentials showcase/showcase and
database showcase. Connection settings come from SHOWCASE_PG_* environment
variables with those defaults (shared with scripts/apply-postgres-ddl.py, whose
connection_params() this module imports). Tests skip when the database is
unreachable.

DDL application is scripts/apply-postgres-ddl.py's canonical logic (imported
here): every emitted *.sql file under generated/sql-postgres is applied
verbatim in sorted filename order - the deterministic order for this target,
whose files are independent CREATE TABLE/CREATE INDEX statements with no
cross-file dependencies and no rewritten semantics. The script's CLI is
exercised separately in test_apply_script_cli_is_deterministic_sorted_and_idempotent.
"""

from __future__ import annotations

import importlib.util
import shutil
import subprocess
import sys
from datetime import date, datetime, timedelta, timezone
from decimal import Decimal
from pathlib import Path

import psycopg
import pytest

REPO_ROOT = Path(__file__).resolve().parents[2]
DDL_DIR = REPO_ROOT / "generated" / "sql-postgres"
APPLY_SCRIPT = REPO_ROOT / "scripts" / "apply-postgres-ddl.py"

_apply_spec = importlib.util.spec_from_file_location("apply_postgres_ddl", APPLY_SCRIPT)
assert _apply_spec is not None and _apply_spec.loader is not None
_apply_module = importlib.util.module_from_spec(_apply_spec)
sys.modules["apply_postgres_ddl"] = _apply_module
_apply_spec.loader.exec_module(_apply_module)

connection_params = _apply_module.connection_params
apply_ddl = _apply_module.apply_ddl


def _can_connect() -> bool:
    params = connection_params()
    params["connect_timeout"] = 2
    try:
        with psycopg.connect(**params) as conn:
            conn.execute("SELECT 1")
        return True
    except Exception:
        return False


pytestmark = pytest.mark.skipif(
    not _can_connect(),
    reason="PostgreSQL not reachable on SHOWCASE_PG_* - run 'docker compose up -d postgres' first",
)


def _snake_case(camel: str) -> str:
    out: list[str] = []
    for i, ch in enumerate(camel):
        if ch.isupper() and i > 0:
            out.append("_")
        out.append(ch.lower())
    return "".join(out)


def _expected_table_names() -> list[str]:
    names = []
    for sql_file in sorted(DDL_DIR.glob("*.sql")):
        projection = sql_file.stem.split(".")[-2]
        names.append(_snake_case(projection))
    return names


@pytest.fixture(scope="module")
def conn():
    with psycopg.connect(**connection_params()) as connection:
        yield connection


@pytest.fixture(scope="module", autouse=True)
def applied_ddl(conn):
    apply_ddl(DDL_DIR, conn)


def _columns(conn, table: str) -> dict[str, tuple[str, bool]]:
    rows = conn.execute(
        """
        SELECT a.attname, pg_catalog.format_type(a.atttypid, a.atttypmod), a.attnotnull
        FROM pg_catalog.pg_attribute a
        WHERE a.attrelid = %s::regclass AND a.attnum > 0 AND NOT a.attisdropped
        ORDER BY a.attnum
        """,
        (table,),
    ).fetchall()
    return {name: (sql_type, not not_null) for name, sql_type, not_null in rows}


# --- DDL application ---------------------------------------------------------


def test_apply_script_cli_is_deterministic_sorted_and_idempotent():
    uv = shutil.which("uv")
    assert uv is not None, "uv is not on PATH"
    expected = [f.name for f in sorted(DDL_DIR.glob("*.sql"))]
    assert expected, "run 'make generate' first (generated/sql-postgres missing)"

    first = subprocess.run([uv, "run", str(APPLY_SCRIPT)], cwd=REPO_ROOT, capture_output=True, text=True)
    assert first.returncode == 0, first.stdout + first.stderr
    applied = [
        line.split("applied ", 1)[1]
        for line in first.stdout.splitlines()
        if line.startswith("applied ") and line.split("applied ", 1)[1] in expected
    ]
    assert applied == expected, "DDL files are not applied in sorted filename order"
    assert f"applied {len(expected)} file(s) from {DDL_DIR}" in first.stdout, first.stdout

    second = subprocess.run([uv, "run", str(APPLY_SCRIPT)], cwd=REPO_ROOT, capture_output=True, text=True)
    assert second.returncode == 0, "re-applying the DDL must be idempotent: " + second.stdout + second.stderr


def test_all_generated_tables_exist(conn):
    expected = set(_expected_table_names())
    rows = conn.execute(
        "SELECT table_name FROM information_schema.tables WHERE table_schema = 'public'"
    ).fetchall()
    present = {row[0] for row in rows}
    assert present.issuperset(expected), f"missing tables: {sorted(expected - present)}"


def test_patient_appointment_invoice_columns_and_sql_types(conn):
    expected = {
        "patient_db": [
            ("patient_id", "text", False),
            ("legal_name", "text", False),
            ("preferred_name", "text", True),
            ("date_of_birth", "date", False),
            ("contact", "text", False),
            ("address", "text", True),
            ("preferred_language", "text", False),
            ("alternate_phone_numbers", "text[]", True),
            ("notes", "text", True),
            ("clinical_notes", "text", True),
            ("created_at", "timestamp with time zone", False),
            ("updated_at", "timestamp with time zone", True),
        ],
        "appointment_db": [
            ("appointment_id", "text", False),
            ("patient_id", "text", False),
            ("practitioner_id", "text", False),
            ("scheduled_date", "date", False),
            ("slot", "text", False),
            ("buffer_duration", "interval", True),
            ("status", "text", False),
            ("reason", "text", True),
            ("notes", "text", True),
            ("created_at", "timestamp with time zone", False),
            ("updated_at", "timestamp with time zone", True),
        ],
        "invoice_db": [
            ("invoice_id", "text", False),
            ("patient_id", "text", False),
            ("encounter_id", "text", True),
            ("lines", "text[]", False),
            ("subtotal", "numeric(10,2)", False),
            ("tax", "numeric(10,2)", False),
            ("total", "numeric(10,2)", False),
            ("currency", "text", True),
            ("billing_period", "text", True),
            ("status", "text", False),
            ("issued_at", "timestamp with time zone", True),
            ("due_date", "date", True),
            ("created_at", "timestamp with time zone", False),
            ("updated_at", "timestamp with time zone", True),
        ],
    }
    for table, expected_columns in expected.items():
        actual = _columns(conn, table)
        got = [(name, sql_type, nullable) for name, (sql_type, nullable) in actual.items()]
        assert got == expected_columns, f"{table}: got {got}, expected {expected_columns}"


def test_generated_secondary_indexes_currently_conflict_across_tables(conn):
    # The sql-postgres emitter (UPSTREAM_FINDINGS.md #24) renders each secondary
    # index with only its declared name (`by_name`, `by_status`, ...), no
    # table/domain prefix. PostgreSQL scopes index names per schema, not per
    # table, so applying the full generated graph into one schema makes every
    # same-named index collide: `CREATE INDEX IF NOT EXISTS` silently skips the
    # later files, and only the first-applied table keeps the index. This test
    # pins the exact applied reality so it flips when #24 is fixed upstream.
    rows = conn.execute(
        "SELECT tablename, indexname FROM pg_indexes WHERE schemaname = 'public'"
    ).fetchall()
    indexes_by_table: dict[str, set[str]] = {}
    for tablename, indexname in rows:
        indexes_by_table.setdefault(tablename, set()).add(indexname)

    # billing.InvoiceDb is first in sorted application order, so both of its
    # intended indexes survive.
    assert {"by_patient", "by_status"} <= indexes_by_table["invoice_db"], indexes_by_table

    # clinical.PatientFhirView sorts before patient.PatientDb, so `by_name`
    # is stolen by the view and patient_db ends up with NO index at all.
    assert "by_name" not in indexes_by_table.get("patient_db", set()), (
        "patient_db now has by_name - UPSTREAM_FINDINGS.md #24 appears fixed. "
        "Update this test (and the finding) instead of leaving it green by accident."
    )
    assert "by_name" in indexes_by_table["patient_fhir_view"], indexes_by_table

    # appointment_db keeps by_patient_day (first in its family) but loses
    # by_practitioner_day to reporting.DailySchedule and by_status to
    # billing.InvoiceDb.
    assert "by_patient_day" in indexes_by_table["appointment_db"], indexes_by_table
    assert "by_practitioner_day" not in indexes_by_table["appointment_db"], indexes_by_table
    assert "by_practitioner_day" in indexes_by_table["daily_schedule"], indexes_by_table
    assert "by_status" not in indexes_by_table["appointment_db"], (
        "appointment_db now has by_status - UPSTREAM_FINDINGS.md #24 appears fixed. "
        "Update this test (and the finding) instead of leaving it green by accident."
    )
    assert "by_status" in indexes_by_table["invoice_db"], indexes_by_table


def test_insert_and_read_back_synthetic_rows(conn):
    now = datetime.now(timezone.utc)
    rows = [
        (
            "patient_db",
            (
                "pat-1",
                "Jane Doe",
                "Jane",
                date(1990, 1, 1),
                '{"email": "jane@example.com"}',
                "123 Main St",
                "en",
                ["555-0101", "555-0102"],
                "initial visit",
                "none",
                now,
                None,
            ),
            [
                "patient_id",
                "legal_name",
                "preferred_name",
                "date_of_birth",
                "contact",
                "address",
                "preferred_language",
                "alternate_phone_numbers",
                "notes",
                "clinical_notes",
                "created_at",
                "updated_at",
            ],
        ),
        (
            "appointment_db",
            (
                "appt-1",
                "pat-1",
                "prac-1",
                date(2026, 8, 17),
                "09:00",
                timedelta(minutes=15),
                "scheduled",
                "routine check",
                "n/a",
                now,
                None,
            ),
            [
                "appointment_id",
                "patient_id",
                "practitioner_id",
                "scheduled_date",
                "slot",
                "buffer_duration",
                "status",
                "reason",
                "notes",
                "created_at",
                "updated_at",
            ],
        ),
        (
            "invoice_db",
            (
                "inv-1",
                "pat-1",
                "enc-1",
                ['{"code": "E0001", "qty": 1, "price": 150.00}'],
                Decimal("150.00"),
                Decimal("12.00"),
                Decimal("162.00"),
                "USD",
                "2026-08",
                "issued",
                now,
                date(2026, 9, 15),
                now,
                None,
            ),
            [
                "invoice_id",
                "patient_id",
                "encounter_id",
                "lines",
                "subtotal",
                "tax",
                "total",
                "currency",
                "billing_period",
                "status",
                "issued_at",
                "due_date",
                "created_at",
                "updated_at",
            ],
        ),
        (
            "encounter_db",
            (
                "enc-1",
                "pat-1",
                "prac-1",
                "appt-1",
                "completed",
                now,
                now,
                timedelta(minutes=30),
                "R10",
                ["J00"],
                now,
                None,
            ),
            [
                "encounter_id",
                "patient_id",
                "practitioner_id",
                "appointment_id",
                "status",
                "started_at",
                "ended_at",
                "expected_duration",
                "reason_code",
                "diagnoses",
                "created_at",
                "updated_at",
            ],
        ),
    ]

    for table, values, columns in rows:
        id_col, id_value = columns[0], values[0]
        conn.execute(f"DELETE FROM {table} WHERE {id_col} = %s", (id_value,))

    for table, values, columns in rows:
        placeholders = ", ".join(["%s"] * len(columns))
        conn.execute(
            f"INSERT INTO {table} ({', '.join(columns)}) VALUES ({placeholders})",
            values,
        )

    for table, values, columns in rows:
        id_col, id_value = columns[0], values[0]
        read_back = conn.execute(
            f"SELECT {', '.join(columns)} FROM {table} WHERE {id_col} = %s",
            (id_value,),
        ).fetchone()
        assert read_back is not None, f"{table}: synthetic row {id_value} was not read back"
        assert tuple(read_back) == values, f"{table}: read-back mismatch:\n got {read_back}\n exp {values}"