#!/usr/bin/env -S uv run --script
# /// script
# requires-python = ">=3.11"
# dependencies = ["psycopg[binary]>=3.2", "clickhouse-connect>=0.8"]
# ///
"""Bootstrap a fresh PostgreSQL + ClickHouse database with the FULL generated
schema, for apps/api's own test suite (Task 9.x) and CI (Task 16.1's
`product` job) - both need every table apps/api reads/writes, including the
FK-bearing `appointment_db`/`encounter_db`/`invoice_db` that
`scripts/setup-e2e-database.py` deliberately excludes (that script's FK-free
subset is a separate, narrower scoping decision for the Task 12.1 Playwright
harness specifically - see its own module docstring - and is out of scope
for this script to revisit).

UPSTREAM_FINDINGS.md #27 (the FK-bound-table-name bug that motivated
`setup-e2e-database.py`'s FK-free subset) is fixed as of the pinned 1.9.4
release, so the full generated `sql-postgres` set applies cleanly in one
pass - this script does not special-case it.

Applies the full `generated/sql-postgres` and `generated/sql-clickhouse`
sets in dependency order, plus the same two Postgres tables and one
ClickHouse table that are genuinely hand-written because their source models
have no generated table at all (`observation_db`/`payment_db`/
`payment_event` - PaymentReceived/Observation are bare `event` declarations
with no `auto projections` block; see apps/api/src/billing.rs and
apps/api/src/clinical.rs's module docs).

Usage:

  uv run scripts/setup-full-database.py
"""

from __future__ import annotations

import importlib.util
import sys
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
# Kept byte-identical to scripts/setup-e2e-database.py's copies.
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


def apply_postgres(conn: psycopg.Connection) -> None:
    applied = pg_ddl.apply_ddl(PG_DDL_DIR, conn)
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

    print("setup-full-database.py: done")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
