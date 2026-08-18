#!/usr/bin/env -S uv run --script
# /// script
# requires-python = ">=3.11"
# dependencies = ["psycopg[binary]>=3.2", "clickhouse-connect>=0.8"]
# ///
"""Bootstrap a fresh PostgreSQL + ClickHouse database for the Playwright E2E
harness (IMPLEMENTATION_PLAN.md Task 12.1).

UPSTREAM_FINDINGS.md #27: the generated `sql-postgres` DDL for `invoice_db`,
`appointment_db`, and `encounter_db` carries an inline `FOREIGN KEY (...)
REFERENCES <model-name> (...)` clause that references a relation that never
exists (the bound table is `<name>_db`, not `<name>`), so those three
`CREATE TABLE` statements fail outright and the tables are never created.
There is no sanctioned workaround for this (UPSTREAM_POLICY.md Sec 7 bans a
script that rewrites generated SQL to make it usable - "if generated output
needs systematic rewriting to become usable, the emitter is incomplete, fix
the emitter"), so this script does not attempt one. It applies exactly the
same FK-free subset `tests/integration/test_postgres_generated_schema.py`
already pins as the current 1.9.3 reality, plus the two Postgres tables and
one ClickHouse table that are genuinely hand-written because their source
models have no generated table at all (`observation_db`/`payment_db`/
`payment_event` - PaymentReceived/Observation are bare `event` declarations
with no `auto projections` block; see apps/api/src/billing.rs and
apps/api/src/clinical.rs's module docs for the same pattern applied to the
running API's own dev database).

Consequence for the E2E suite: `invoice_db`/`appointment_db`/`encounter_db`
do not exist after this script runs, so any request that touches them
(POST /api/appointments, POST /api/encounters, POST /api/invoices, and
GET /api/patients/:id/summary, which joins across all of them) fails with a
PostgreSQL "relation does not exist" error. tests/e2e/clinic.spec.ts scopes
its assertions to what this schema actually supports (patient create/list/
search/detail) and documents the rest as blocked by #27 rather than silently
skipping or faking coverage.

Usage:

  uv run scripts/setup-e2e-database.py
"""

from __future__ import annotations

import importlib.util
import sys
import tempfile
from pathlib import Path

import clickhouse_connect
import psycopg

REPO_ROOT = Path(__file__).resolve().parent.parent
PG_DDL_DIR = REPO_ROOT / "generated" / "sql-postgres"
CH_DDL_DIR = REPO_ROOT / "generated" / "sql-clickhouse"


def _load_module(name: str, path: Path):
    spec = importlib.util.spec_from_file_location(name, path)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    sys.modules[name] = module
    spec.loader.exec_module(module)
    return module


pg_ddl = _load_module("apply_postgres_ddl", REPO_ROOT / "scripts" / "apply-postgres-ddl.py")
ch_ddl = _load_module("apply_clickhouse_ddl", REPO_ROOT / "scripts" / "apply-clickhouse-ddl.py")


# Hand-written tables for event-only models with no generated projection at
# all (not a rewrite of anything Modelable generates - see module docstring).
OBSERVATION_DB_SQL = """
CREATE TABLE IF NOT EXISTS observation_db (
    observation_id TEXT NOT NULL PRIMARY KEY,
    encounter_id TEXT NOT NULL,
    code TEXT NOT NULL,
    is_abnormal BOOLEAN NOT NULL,
    recorded_at TIMESTAMPTZ NOT NULL,
    temperature_celsius DOUBLE PRECISION,
    weight_kg TEXT,
    blood_pressure_systolic INTEGER,
    blood_pressure_diastolic INTEGER,
    pulse_bpm INTEGER,
    device_id TEXT,
    metadata JSONB
)
"""

PAYMENT_DB_SQL = """
CREATE TABLE IF NOT EXISTS payment_db (
    payment_id TEXT NOT NULL PRIMARY KEY,
    invoice_id TEXT NOT NULL,
    amount NUMERIC(10, 2) NOT NULL,
    method TEXT NOT NULL,
    received_at TIMESTAMPTZ NOT NULL
)
"""

PAYMENT_EVENT_SQL = """
CREATE TABLE IF NOT EXISTS payment_event (
    payment_id String,
    invoice_id String,
    amount Decimal(10, 2),
    method LowCardinality(String),
    received_at DateTime64(9)
) ENGINE = MergeTree()
ORDER BY tuple()
"""


def fk_free_postgres_files() -> list[Path]:
    return sorted(f for f in PG_DDL_DIR.glob("*.sql") if "FOREIGN KEY" not in f.read_text(encoding="utf-8"))


def apply_postgres(conn: psycopg.Connection) -> None:
    fk_free = fk_free_postgres_files()
    with tempfile.TemporaryDirectory() as tmp:
        subset_dir = Path(tmp)
        for sql_file in fk_free:
            (subset_dir / sql_file.name).write_text(sql_file.read_text(encoding="utf-8"), encoding="utf-8")
        applied = pg_ddl.apply_ddl(subset_dir, conn)
    for name in applied:
        print(f"postgres: applied {name}")

    with conn.cursor() as cur:
        cur.execute(OBSERVATION_DB_SQL)
        cur.execute(PAYMENT_DB_SQL)
    conn.commit()
    print("postgres: applied hand-written observation_db")
    print("postgres: applied hand-written payment_db")


def apply_clickhouse(client) -> None:
    applied = ch_ddl.apply_ddl(CH_DDL_DIR, client)
    for name in applied:
        print(f"clickhouse: applied {name}")

    for statement in PAYMENT_EVENT_SQL.split(";"):
        statement = statement.strip()
        if statement:
            client.command(statement)
    print("clickhouse: applied hand-written payment_event")


def main() -> int:
    if not list(PG_DDL_DIR.glob("*.sql")) or not list(CH_DDL_DIR.glob("*.sql")):
        print("error: generated/sql-postgres or generated/sql-clickhouse missing - run 'make generate' first", file=sys.stderr)
        return 1

    with psycopg.connect(**pg_ddl.connection_params()) as conn:
        apply_postgres(conn)

    ch_client = clickhouse_connect.get_client(**ch_ddl.connection_params())
    try:
        apply_clickhouse(ch_client)
    finally:
        ch_client.close()

    print("setup-e2e-database.py: done")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
