# -*- coding: utf-8 -*-
"""应用 / 校验日频数据底座 DDL（`docs/sql/create_table.sql` 的标记段）。

只执行标记段内的语句：
  -- ===== BEGIN DAILY_DATA_BASE =====
  ...
  -- ===== END DAILY_DATA_BASE =====

这样既能保证 `create_table.sql` 仍是唯一 DDL 源，又不会重跑文件里
133 张既有表的建表语句（那些语句大多没有 IF NOT EXISTS）。

用法：
  cd quant_server
  .venv/Scripts/python.exe scripts/data/apply_daily_data_ddl.py --check
  .venv/Scripts/python.exe scripts/data/apply_daily_data_ddl.py --apply --role admin

角色：
  app   （默认）读 `.env` 的 PROD_DB_*（quant_prod），只够 --check；
  admin 读 DB_*（postgres），有 public 建表权；public 上的默认 ACL 会给
        quant_prod 自动授 SELECT/INSERT/UPDATE/DELETE。
"""

from __future__ import annotations

import argparse
import re
import sys
from pathlib import Path
from typing import Dict, List

import psycopg2

SCRIPT_DIR = Path(__file__).resolve().parent
SERVER_DIR = SCRIPT_DIR.parents[1]
REPO_ROOT = SERVER_DIR.parent
DDL_PATH = REPO_ROOT / "docs" / "sql" / "create_table.sql"
ENV_PATH = SERVER_DIR / ".env"

BEGIN_MARK = "-- ===== BEGIN DAILY_DATA_BASE ====="
END_MARK = "-- ===== END DAILY_DATA_BASE ====="


def load_env(path: Path) -> Dict[str, str]:
    env: Dict[str, str] = {}
    if not path.exists():
        return env
    for line in path.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        k, v = line.split("=", 1)
        env[k.strip()] = v.strip()
    return env


def section_text() -> str:
    text = DDL_PATH.read_text(encoding="utf-8")
    if BEGIN_MARK not in text or END_MARK not in text:
        raise SystemExit("create_table.sql 缺少 DAILY_DATA_BASE 标记段")
    return text.split(BEGIN_MARK, 1)[1].split(END_MARK, 1)[0]


def expected_tables(section: str) -> List[str]:
    return re.findall(r"CREATE TABLE IF NOT EXISTS\s+(\w+)", section)


def split_statements(section: str) -> List[str]:
    out: List[str] = []
    for raw in section.split(";"):
        body = "\n".join(
            ln for ln in raw.splitlines() if not ln.strip().startswith("--")
        ).strip()
        if body:
            out.append(raw.strip())
    return out


def connect(env: Dict[str, str], role: str):
    prefix = "DB_" if role == "admin" else "PROD_DB_"
    keys = {
        "host": f"{prefix}HOST",
        "port": f"{prefix}PORT",
        "user": f"{prefix}USER",
        "password": f"{prefix}PASSWORD",
        "dbname": f"{prefix}NAME",
    }
    missing = [k for k in keys.values() if not env.get(k)]
    if missing:
        raise SystemExit(f".env 缺少 {', '.join(missing)}（--role {role}）")
    return psycopg2.connect(
        host=env[keys["host"]],
        port=env[keys["port"]],
        user=env[keys["user"]],
        password=env[keys["password"]],
        dbname=env[keys["dbname"]],
        connect_timeout=10,
    )


def check(conn, expected: List[str]) -> int:
    with conn.cursor() as cur:
        cur.execute(
            "SELECT table_name FROM information_schema.tables "
            "WHERE table_schema = 'public' AND table_name = ANY(%s)",
            (expected,),
        )
        found = {r[0] for r in cur.fetchall()}
    missing = sorted(set(expected) - found)
    print(f"tables={len(expected)} found={len(found)} missing={len(missing)}")
    if missing:
        print("缺失：" + ", ".join(missing))
        return 1
    return 0


def apply(conn, statements: List[str]) -> int:
    failed = 0
    with conn.cursor() as cur:
        for i, stmt in enumerate(statements, 1):
            head = " ".join(stmt.split())[:90]
            try:
                cur.execute(stmt)
                conn.commit()
            except Exception as exc:  # noqa: BLE001 - 逐条报告，便于定位
                conn.rollback()
                failed += 1
                print(f"[{i:02d}/{len(statements)}] FAIL {head}")
                print(f"    {str(exc).strip()[:300]}")
            else:
                print(f"[{i:02d}/{len(statements)}] ok   {head}")
    return 1 if failed else 0


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--check", action="store_true", help="只校验表是否存在")
    ap.add_argument("--apply", action="store_true", help="执行标记段 DDL")
    ap.add_argument("--role", choices=["app", "admin"], default="app",
                    help="app=PROD_DB_*（只读校验）；admin=DB_*（建表）")
    args = ap.parse_args()
    if not args.check and not args.apply:
        ap.print_help()
        return 1

    env = load_env(ENV_PATH)
    section = section_text()
    expected = expected_tables(section)
    if len(expected) != 57:
        print(f"标记段表数异常：{len(expected)}（应为 57）", file=sys.stderr)
        return 2

    conn = connect(env, args.role)
    conn.autocommit = False
    try:
        rc = 0
        if args.apply:
            with conn.cursor() as cur:
                cur.execute("SELECT has_schema_privilege('public', 'CREATE')")
                can_create = cur.fetchone()[0]
            if not can_create:
                print("当前角色对 schema public 无 CREATE 权限；请加 --role admin",
                      file=sys.stderr)
                return 3
            statements = split_statements(section)
            print(f"[apply] role={args.role} statements={len(statements)}")
            rc = apply(conn, statements)
        if args.check:
            print(f"[check] role={args.role}")
            rc = check(conn, expected) or rc
        return rc
    finally:
        conn.close()


if __name__ == "__main__":
    sys.exit(main())
