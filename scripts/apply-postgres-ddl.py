#!/usr/bin/env -S uv run --script
# /// script
# requires-python = ">=3.11"
# dependencies = ["psycopg[binary]>=3.2"]
# ///
"""Apply the generated sql-postgres DDL to a PostgreSQL database
(IMPLEMENTATION_PLAN.md Task 8.1).

The generated output is one standalone `.sql` file per model/projection, each
`CREATE TABLE IF NOT EXISTS` plus `CREATE INDEX IF NOT EXISTS`, with no
cross-file dependencies (no foreign keys, no views), so the deterministic
order is simply sorted filename order. The script never rewrites SQL
semantics: each statement is executed verbatim, and the whole thing is
idempotent because every emitted statement already says `IF NOT EXISTS`.

Connection settings come from SHOWCASE_PG_* environment variables, defaulting
to the dev PostgreSQL defined in the repository docker-compose.yml:

  SHOWCASE_PG_HOST   (default 127.0.0.1)
  SHOWCASE_PG_PORT   (default 5433)
  SHOWCASE_PG_USER   (default showcase)
  SHOWCASE_PG_PASSWORD (default showcase)
  SHOWCASE_PG_DBNAME (default showcase)

Usage:

  uv run scripts/apply-postgres-ddl.py [GENERATED_SQL_POSTGRES_DIR]
"""

from __future__ import annotations

import argparse
import os
import sys
from pathlib import Path

import psycopg

SCRIPT_DIR = Path(__file__).resolve().parent
DEFAULT_DDL_DIR = SCRIPT_DIR.parent / "generated" / "sql-postgres"


def connection_params() -> dict:
    return {
        "host": os.environ.get("SHOWCASE_PG_HOST", "127.0.0.1"),
        "port": int(os.environ.get("SHOWCASE_PG_PORT", "5433")),
        "user": os.environ.get("SHOWCASE_PG_USER", "showcase"),
        "password": os.environ.get("SHOWCASE_PG_PASSWORD", "showcase"),
        "dbname": os.environ.get("SHOWCASE_PG_DBNAME", "showcase"),
        "connect_timeout": int(os.environ.get("SHOWCASE_PG_CONNECT_TIMEOUT", "10")),
    }


def apply_ddl(ddl_dir: Path, conn) -> list[str]:
    """Apply every *.sql file under ddl_dir in sorted filename order and return
    the list of applied filenames. Statements are split on ';' only - the
    generated files contain plain CREATE TABLE/CREATE INDEX statements with no
    embedded semicolons, so each statement is passed to PostgreSQL verbatim."""
    sql_files = sorted(ddl_dir.glob("*.sql"))
    applied: list[str] = []
    with conn.cursor() as cur:
        for sql_file in sql_files:
            statements = [s.strip() for s in sql_file.read_text(encoding="utf-8").split(";") if s.strip()]
            for statement in statements:
                cur.execute(statement)
            applied.append(sql_file.name)
    conn.commit()
    return applied


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=(__doc__ or "").splitlines()[0])
    parser.add_argument(
        "ddl_dir",
        nargs="?",
        default=str(DEFAULT_DDL_DIR),
        help=f"generated sql-postgres directory (default: {DEFAULT_DDL_DIR})",
    )
    args = parser.parse_args(argv)

    ddl_dir = Path(args.ddl_dir)
    if not ddl_dir.is_dir():
        print(f"error: DDL directory not found: {ddl_dir}", file=sys.stderr)
        return 1
    if not list(ddl_dir.glob("*.sql")):
        print(f"error: no *.sql files in {ddl_dir} - run 'make generate' first", file=sys.stderr)
        return 1

    with psycopg.connect(**connection_params()) as conn:
        applied = apply_ddl(ddl_dir, conn)

    for name in applied:
        print(f"applied {name}")
    print(f"applied {len(applied)} file(s) from {ddl_dir}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())