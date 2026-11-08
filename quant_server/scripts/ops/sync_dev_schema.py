# -*- coding: utf-8 -*-
"""比对 public 与 dev 的应用表结构（REQ-20261108-db-env-isolation 任务 8）。

用法:
    python scripts/ops/sync_dev_schema.py --dry-run
    python scripts/ops/sync_dev_schema.py --apply

规则:
    - 缺表：只报告，提示先跑 init_dev_schema.py
    - 缺列：--apply 时 ALTER TABLE dev.x ADD COLUMN（可空，避免非空无默认失败）
    - 类型差异：只报告，不自动改（需人工确认）
    - dev 多出的列：忽略（开发实验列）
"""
import argparse
import os
from pathlib import Path

from psycopg2 import sql

try:
    from dotenv import load_dotenv

    _ENV_FILE = Path(__file__).resolve().parents[2] / ".env"
    if _ENV_FILE.exists():
        load_dotenv(_ENV_FILE, override=False)
except ImportError:
    pass

from init_dev_schema import MARKET_TABLES, _connect


def _env(name: str, default=None):
    return os.environ.get(name, default)


def _columns(cur, schema: str, tables: list[str]) -> dict:
    cur.execute(
        """
        SELECT c.relname, a.attname,
               format_type(a.atttypid, a.atttypmod) AS coltype,
               a.attnotnull,
               pg_get_expr(d.adbin, d.adrelid) AS default_expr
        FROM pg_attribute a
        JOIN pg_class c ON c.oid = a.attrelid
        JOIN pg_namespace n ON n.oid = c.relnamespace
        LEFT JOIN pg_attrdef d
          ON d.adrelid = a.attrelid AND d.adnum = a.attnum
        WHERE n.nspname = %s AND c.relkind = 'r'
          AND a.attnum > 0 AND NOT a.attisdropped
          AND c.relname = ANY(%s)
        ORDER BY c.relname, a.attnum
        """,
        (schema, tables),
    )
    result: dict = {}
    for table, column, coltype, notnull, default in cur.fetchall():
        result.setdefault(table, {})[column] = {
            "type": coltype,
            "notnull": bool(notnull),
            "default": default,
        }
    return result


def main() -> None:
    ap = argparse.ArgumentParser(description="比对 public 与 dev 的应用表结构")
    ap.add_argument("--dry-run", action="store_true", help="只报告，不修改")
    ap.add_argument("--apply", action="store_true", help="应用可加列")
    ap.add_argument("--database", default=_env("PROD_DB_NAME", "quant_signals"))
    args = ap.parse_args()

    if args.apply and args.dry_run:
        raise SystemExit("--dry-run 与 --apply 只能二选一")

    conn = _connect(args.database)
    conn.autocommit = False
    cur = conn.cursor()
    try:
        cur.execute(
            "SELECT tablename FROM pg_tables WHERE schemaname = 'public' ORDER BY tablename"
        )
        app_tables = [row[0] for row in cur.fetchall() if row[0] not in MARKET_TABLES]

        public_cols = _columns(cur, "public", app_tables)
        dev_cols = _columns(cur, "dev", app_tables)

        missing_tables = [t for t in app_tables if t not in dev_cols]
        missing_columns: list[tuple[str, str, dict]] = []
        type_diffs: list[str] = []

        for table in app_tables:
            if table not in dev_cols:
                continue
            for column, meta in public_cols[table].items():
                dev_meta = dev_cols[table].get(column)
                if dev_meta is None:
                    missing_columns.append((table, column, meta))
                elif dev_meta["type"] != meta["type"]:
                    type_diffs.append(
                        f"类型差异: dev.{table}.{column} "
                        f"{dev_meta['type']} != {meta['type']}"
                    )

        diffs = (
            [f"缺表: dev.{t}" for t in missing_tables]
            + [f"缺列: dev.{t}.{c} {m['type']}" for t, c, m in missing_columns]
            + type_diffs
        )
        if not diffs:
            print("0 diffs")
            return

        for diff in diffs:
            print(diff)

        if not args.apply:
            print(f"[dry-run] {len(diffs)} diffs；加 --apply 执行可加列（不改类型/不删列）")
            raise SystemExit(1)

        applied = 0
        for table, column, meta in missing_columns:
            cur.execute(
                sql.SQL("ALTER TABLE dev.{} ADD COLUMN {} {}").format(
                    sql.Identifier(table),
                    sql.Identifier(column),
                    sql.SQL(meta["type"]),
                )
            )
            if meta["notnull"]:
                print(f"  [WARN] dev.{table}.{column} 在 public 为 NOT NULL，dev 先加为可空")
            applied += 1
        conn.commit()
        print(f"已应用 {applied} 个缺列；类型差异需人工处理")
        if missing_tables or type_diffs:
            raise SystemExit(1)
    finally:
        cur.close()
        conn.close()


if __name__ == "__main__":
    main()
