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

The current 1.8.0 reality, pinned here exactly:

- The full generated set does NOT apply in one pass: v1.8.0 adds `FOREIGN KEY`
  emission, but every FK references the referenced *model* name, not the bound
  *table* name - `REFERENCES patient`, `REFERENCES appointment`,
  `REFERENCES encounter` - and no such relations exist, so the first FK
  statement aborts the whole apply with `relation "encounter" does not exist`
  (UPSTREAM_FINDINGS.md #27). `test_full_generated_set_currently_fails_to_apply`
  is the flip signal for that; `test_fk_clauses_reference_model_names` pins
  the exact emitted clauses.
- The FK-free subset (every file with no FOREIGN KEY) applies cleanly and
  deterministically in sorted filename order, and round-trips data. That is
  what `apply_ddl` exercises below.
- Secondary index names are now table-prefixed (`appointment_db_by_status`,
  `patient_db_by_name`, ...) so they no longer collide across tables
  (UPSTREAM_FINDINGS.md #24, fixed in 1.8.0); `test_generated_secondary_indexes_are_table_prefixed`
  pins that fixed reality.
"""

from __future__ import annotations

import importlib.util
import json
import shutil
import subprocess
import sys
import tempfile
from datetime import date, datetime, timedelta, timezone
from decimal import Decimal
from pathlib import Path
from typing import Iterator

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

# The subset of the generated set that applies under UPSTREAM_FINDINGS.md #27:
# every file that emits no FOREIGN KEY. Files with FKs reference the model name
# (`REFERENCES patient`) not the bound table (`patient_db`), so they cannot be
# applied until #27 is fixed upstream.
FK_FREE_FILES = sorted(
    f.name
    for f in DDL_DIR.glob("*.sql")
    if "FOREIGN KEY" not in f.read_text(encoding="utf-8")
)
assert FK_FREE_FILES, "run 'make generate' first (generated/sql-postgres missing or all files carry FKs)"


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
    for name in FK_FREE_FILES:
        projection = Path(name).stem.split(".")[-2]
        names.append(_snake_case(projection))
    return names


def _copy_files_into(dest: Path, names: list[str]) -> None:
    dest.mkdir(parents=True, exist_ok=True)
    for name in names:
        shutil.copy2(DDL_DIR / name, dest / name)


@pytest.fixture(scope="module")
def conn() -> Iterator[psycopg.Connection]:
    with psycopg.connect(**connection_params()) as connection:
        yield connection


@pytest.fixture(scope="module", autouse=True)
def applied_ddl(conn, tmp_path_factory):
    # Apply only the FK-free subset (see module docstring / finding #27). The
    # full generated set is exercised by the dedicated flip test below, which
    # must NOT leave FK-bearing tables behind.
    with tempfile.TemporaryDirectory() as tmp:
        subset_dir = Path(tmp)
        _copy_files_into(subset_dir, FK_FREE_FILES)
        apply_ddl(subset_dir, conn)


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

    # Run the CLI against a copy of the FK-free subset (finding #27): the full
    # tree cannot apply, so the CLI's sorted/idempotent mechanics are proven on
    # what CAN apply.
    with tempfile.TemporaryDirectory() as tmp:
        subset_dir = Path(tmp)
        _copy_files_into(subset_dir, FK_FREE_FILES)
        first = subprocess.run(
            [uv, "run", str(APPLY_SCRIPT), str(subset_dir)], cwd=REPO_ROOT, capture_output=True, text=True
        )
        assert first.returncode == 0, first.stdout + first.stderr
        applied = [
            line.split("applied ", 1)[1]
            for line in first.stdout.splitlines()
            if line.startswith("applied ") and line.split("applied ", 1)[1] in expected
        ]
        assert applied == FK_FREE_FILES, "DDL files are not applied in sorted filename order"
        assert f"applied {len(FK_FREE_FILES)} file(s) from {subset_dir}" in first.stdout, first.stdout

        second = subprocess.run(
            [uv, "run", str(APPLY_SCRIPT), str(subset_dir)], cwd=REPO_ROOT, capture_output=True, text=True
        )
        assert second.returncode == 0, "re-applying the DDL must be idempotent: " + second.stdout + second.stderr


def test_full_generated_set_currently_fails_to_apply():
    # UPSTREAM_FINDINGS.md #27: the v1.8.0 FK emission references the referenced
    # model name, not the bound table name, so the full generated set cannot be
    # applied. This is the flip signal - it must be deleted (and the FK-free
    # subset merged back into the whole-tree apply) once Modelable is re-pinned
    # past a release that fixes #27.
    uv = shutil.which("uv")
    assert uv is not None, "uv is not on PATH"
    full_expected = sorted(f.name for f in DDL_DIR.glob("*.sql"))
    assert any("FOREIGN KEY" in (DDL_DIR / name).read_text(encoding="utf-8") for name in full_expected)

    result = subprocess.run([uv, "run", str(APPLY_SCRIPT), str(DDL_DIR)], cwd=REPO_ROOT, capture_output=True, text=True)
    assert result.returncode != 0, (
        "full generated/sql-postgres now applies in one pass - "
        "UPSTREAM_FINDINGS.md #27 appears fixed. Update this test (and the "
        "FK-free-subset split) instead of leaving it green by accident.\n"
        + result.stdout
        + result.stderr
    )
    output = result.stdout + result.stderr
    assert 'relation "encounter" does not exist' in output, output


def test_fk_clauses_reference_model_names_not_bound_tables():
    # The exact #27 clauses (see UPSTREAM_FINDINGS.md #27): each FK references
    # the referenced model's name, while the actual created table is the bound
    # `<name>_db` table. Pinned so the specific emitted text is documented, not
    # just "apply fails".
    clauses = {
        "billing.InvoiceDb.v2.sql": "REFERENCES encounter (encounter_id)",
        "scheduling.AppointmentDb.v1.sql": "REFERENCES patient (patient_id)",
        "clinical.EncounterDb.v1.sql": "REFERENCES appointment (appointment_id)",
    }
    for filename, clause in clauses.items():
        sql = (DDL_DIR / filename).read_text(encoding="utf-8")
        assert "FOREIGN KEY" in sql and clause in sql, f"{filename} lacks {clause}:\n{sql}"


def test_all_generated_tables_exist(conn: psycopg.Connection):
    expected = set(_expected_table_names())
    rows = conn.execute(
        "SELECT table_name FROM information_schema.tables WHERE table_schema = 'public'"
    ).fetchall()
    present = {row[0] for row in rows}
    assert present.issuperset(expected), f"missing tables: {sorted(expected - present)}"


def test_patient_db_columns_and_sql_types(conn: psycopg.Connection):
    expected = {
        "patient_db": [
            ("patient_id", "text", False),
            ("legal_name", "text", False),
            ("preferred_name", "text", True),
            ("date_of_birth", "date", False),
            ("contact", "jsonb", False),
            ("address", "jsonb", True),
            ("preferred_language", "text", False),
            ("alternate_phone_numbers", "text[]", True),
            ("notes", "text", True),
            ("clinical_notes", "text", True),
            ("created_at", "timestamp with time zone", False),
            ("updated_at", "timestamp with time zone", True),
        ],
    }
    for table, expected_columns in expected.items():
        actual = _columns(conn, table)
        got = [(name, sql_type, nullable) for name, (sql_type, nullable) in actual.items()]
        assert got == expected_columns, f"{table}: got {got}, expected {expected_columns}"


def test_generated_secondary_indexes_are_table_prefixed(conn: psycopg.Connection):
    # UPSTREAM_FINDINGS.md #24, fixed in 1.8.0: index names now carry the
    # <table>_ prefix so same-named indexes no longer collide across tables
    # (by_name/by_status/by_patient_day are shared by every projection in a
    # domain family). Every applied FK-free table keeps its intended indexes.
    rows = conn.execute(
        "SELECT tablename, indexname FROM pg_indexes WHERE schemaname = 'public'"
    ).fetchall()
    indexes_by_table: dict[str, set[str]] = {}
    for tablename, indexname in rows:
        indexes_by_table.setdefault(tablename, set()).add(indexname)

    # invoice_db and appointment_db carry FKs (finding #27) so they are NOT in
    # the applied FK-free subset - only the FK-free tables below are created.
    expected_indexes = {
        "patient_db": {"patient_db_by_name"},
        "patient_fhir_view": {"patient_fhir_view_by_name"},
        "patient_event": {"patient_event_by_name"},
        "patient_reply": {"patient_reply_by_name"},
        "patient_request": {"patient_request_by_name"},
        "patient_summary": {"patient_summary_by_name"},
        "daily_schedule": {"daily_schedule_by_practitioner_day"},
    }
    for table, expected in expected_indexes.items():
        assert table in indexes_by_table, f"{table} missing entirely (indexes: {indexes_by_table})"
        missing = expected - indexes_by_table[table]
        assert not missing, f"{table} missing indexes {missing}: {indexes_by_table[table]}"


def test_insert_and_read_back_synthetic_rows(conn: psycopg.Connection):
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
                '{"street": "123 Main St", "city": "Springfield"}',
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
        # JSONB columns come back as dicts; compare them against the parsed
        # JSON string literals used at insert time.
        normalized = []
        for value in read_back:
            if isinstance(value, str) and value.lstrip().startswith("{"):
                normalized.append(json.loads(value))
            else:
                normalized.append(value)
        expected = []
        for value in values:
            if isinstance(value, str) and value.lstrip().startswith("{"):
                expected.append(json.loads(value))
            else:
                expected.append(value)
        assert normalized == expected, f"{table}: read-back mismatch:\n got {read_back}\n exp {values}"