#!/usr/bin/env -S uv run --script
# /// script
# requires-python = ">=3.11"
# dependencies = ["clickhouse-connect>=0.8"]
# ///
"""Apply the generated sql-clickhouse DDL to a ClickHouse server
(IMPLEMENTATION_PLAN.md Task 8.2).

The generated output is one standalone `.sql` file per model/projection, each a
single `CREATE TABLE IF NOT EXISTS ... ENGINE = MergeTree() ORDER BY tuple()`
with no secondary indexes (that capability is deferred upstream - see
`tests/conformance/test_deferred_capabilities.py`), no cross-file dependencies
and no rewritten semantics, so the deterministic order is simply sorted
filename order. Applying is idempotent because every statement says
`IF NOT EXISTS`. Statement chunks are split on ';' and comment-only chunks are
dropped; each real statement is passed to ClickHouse verbatim.

Connection settings come from SHOWCASE_CH_* environment variables, defaulting
to the dev ClickHouse defined in the repository docker-compose.yml:

  SHOWCASE_CH_HOST     (default 127.0.0.1)
  SHOWCASE_CH_PORT     (default 8123)
  SHOWCASE_CH_USER     (default showcase)
  SHOWCASE_CH_PASSWORD (default showcase)
  SHOWCASE_CH_DBNAME   (default showcase)

Usage:

  uv run scripts/apply-clickhouse-ddl.py [GENERATED_SQL_CLICKHOUSE_DIR]
"""

from __future__ import annotations

import argparse
import os
import sys
from pathlib import Path

import clickhouse_connect

SCRIPT_DIR = Path(__file__).resolve().parent
DEFAULT_DDL_DIR = SCRIPT_DIR.parent / "generated" / "sql-clickhouse"


def connection_params() -> dict:
    return {
        "host": os.environ.get("SHOWCASE_CH_HOST", "127.0.0.1"),
        "port": int(os.environ.get("SHOWCASE_CH_PORT", "8123")),
        "username": os.environ.get("SHOWCASE_CH_USER", "showcase"),
        "password": os.environ.get("SHOWCASE_CH_PASSWORD", "showcase"),
        "database": os.environ.get("SHOWCASE_CH_DBNAME", "showcase"),
        "connect_timeout": int(os.environ.get("SHOWCASE_CH_CONNECT_TIMEOUT", "10")),
    }


def _statement_chunks(sql_text: str) -> list[str]:
    """Split a generated file into executable statements. The generated files
    contain plain CREATE TABLE statements and line comments only, so splitting
    on ';' and dropping comment-only chunks never changes a statement."""
    statements: list[str] = []
    for chunk in sql_text.split(";"):
        lines = [line.strip() for line in chunk.splitlines() if not line.strip().startswith("--")]
        statement = "\n".join(lines).strip()
        if statement:
            statements.append(statement)
    return statements


def apply_ddl(ddl_dir: Path, client) -> list[str]:
    """Apply every *.sql file under ddl_dir in sorted filename order and return
    the list of applied filenames."""
    sql_files = sorted(ddl_dir.glob("*.sql"))
    applied: list[str] = []
    for sql_file in sql_files:
        for statement in _statement_chunks(sql_file.read_text(encoding="utf-8")):
            client.command(statement)
        applied.append(sql_file.name)
    return applied


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=(__doc__ or "").splitlines()[0])
    parser.add_argument(
        "ddl_dir",
        nargs="?",
        default=str(DEFAULT_DDL_DIR),
        help=f"generated sql-clickhouse directory (default: {DEFAULT_DDL_DIR})",
    )
    args = parser.parse_args(argv)

    ddl_dir = Path(args.ddl_dir)
    if not ddl_dir.is_dir():
        print(f"error: DDL directory not found: {ddl_dir}", file=sys.stderr)
        return 1
    if not list(ddl_dir.glob("*.sql")):
        print(f"error: no *.sql files in {ddl_dir} - run 'make generate' first", file=sys.stderr)
        return 1

    client = clickhouse_connect.get_client(**connection_params())
    try:
        applied = apply_ddl(ddl_dir, client)
    except Exception as exc:
        print(f"error: failed to apply {ddl_dir}: {exc}", file=sys.stderr)
        return 1
    finally:
        client.close()

    for name in applied:
        print(f"applied {name}")
    print(f"applied {len(applied)} file(s) from {ddl_dir}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())