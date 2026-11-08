# -*- coding: utf-8 -*-
"""环境隔离验收脚本（REQ-20261108-db-env-isolation 任务 9）。

依次跑 AC-1 ~ AC-4，全部 PASS 时 exit 0：
    AC-1 quant_dev 的 current_user / search_path
    AC-2 quant_dev 不能写 public.accounts
    AC-3 quant_dev 能写 dev.strategies，且 public.strategies 不受影响
    AC-4 quant_prod 能写 public.accounts 与 public.stock_daily
"""
import argparse
import os
from pathlib import Path

import psycopg2

try:
    from dotenv import load_dotenv

    _ENV_FILE = Path(__file__).resolve().parents[2] / ".env"
    if _ENV_FILE.exists():
        load_dotenv(_ENV_FILE, override=False)
except ImportError:
    pass

DEV_USER_ID = "dev00000-0000-0000-0000-000000000001"
TEST_STRATEGY_ID = "ac-test-strategy"


def _env(name: str, default=None):
    return os.environ.get(name, default)


def _connect(user: str, password: str, database: str):
    return psycopg2.connect(
        host=_env("DB_DDL_HOST") or _env("DB_HOST", "localhost"),
        port=int(_env("DB_DDL_PORT") or _env("DB_PORT", "5432")),
        user=user,
        password=password,
        database=database,
    )


def _password(role: str) -> str:
    if role == "quant_prod":
        return _env("PROD_DB_PASSWORD") or _env("DB_PASSWORD", "")
    return _env("DB_DEV_PASSWORD") or _env("DB_PASSWORD", "")


def ac1(conn) -> tuple[bool, str]:
    with conn.cursor() as cur:
        cur.execute("SELECT current_user, current_setting('search_path')")
        user, path = cur.fetchone()
    ok = user == "quant_dev" and (path or "").replace(" ", "").startswith("dev")
    return ok, f"current_user={user} search_path={path}"


def ac1b(conn) -> tuple[bool, str]:
    """正向校验：quant_dev 仍能读 public 行情表（防止误删读权限）。"""
    try:
        with conn.cursor() as cur:
            cur.execute("SELECT 1 FROM public.stock_daily LIMIT 1")
            row = cur.fetchone()
        return True, f"public.stock_daily readable={row[0] if row else 0}"
    except psycopg2.Error as exc:
        return False, f"{exc.pgcode}: {str(exc).strip().splitlines()[0]}"


def ac2(conn) -> tuple[bool, str]:
    try:
        with conn.cursor() as cur:
            cur.execute("UPDATE public.accounts SET updated_at = updated_at")
        conn.rollback()
        return False, "UPDATE public.accounts 未被拒绝（隔离失效）"
    except psycopg2.Error as exc:
        conn.rollback()
        message = str(exc).strip().splitlines()[0]
        # 42501 = insufficient_privilege；不依赖本地化错误文案
        return exc.pgcode == "42501", f"{exc.pgcode}: {message}"


def ac3(dev_conn, prod_conn) -> tuple[bool, str]:
    with dev_conn.cursor() as cur:
        cur.execute(
            """
            INSERT INTO dev.strategies
                (id, name, user_id, class_name, module_path, status)
            VALUES (%s, 'AC test', %s, 'AcTest', 'ac/test.py', 'draft')
            ON CONFLICT (id) DO NOTHING
            """,
            (TEST_STRATEGY_ID, DEV_USER_ID),
        )
        dev_conn.commit()
        cur.execute(
            "SELECT count(*) FROM dev.strategies WHERE id = %s", (TEST_STRATEGY_ID,)
        )
        dev_count = cur.fetchone()[0]

    with prod_conn.cursor() as cur:
        cur.execute(
            "SELECT count(*) FROM public.strategies WHERE id = %s", (TEST_STRATEGY_ID,)
        )
        prod_count = cur.fetchone()[0]

    with dev_conn.cursor() as cur:
        cur.execute("DELETE FROM dev.strategies WHERE id = %s", (TEST_STRATEGY_ID,))
        dev_conn.commit()

    return dev_count == 1 and prod_count == 0, f"dev={dev_count} prod={prod_count}"


def ac4(conn) -> tuple[bool, str]:
    with conn.cursor() as cur:
        cur.execute(
            "SELECT current_user, "
            "has_table_privilege(current_user, 'public.accounts', 'UPDATE'), "
            "has_table_privilege(current_user, 'public.stock_daily', 'INSERT')"
        )
        user, can_account, can_market = cur.fetchone()
    ok = user == "quant_prod" and bool(can_account) and bool(can_market)
    return ok, f"{user}|{can_account}|{can_market}"


def main() -> None:
    ap = argparse.ArgumentParser(description="环境隔离验收（AC-1 ~ AC-4）")
    ap.add_argument("--database", default=_env("PROD_DB_NAME", "quant_signals"))
    args = ap.parse_args()

    dev_conn = _connect("quant_dev", _password("quant_dev"), args.database)
    prod_conn = _connect("quant_prod", _password("quant_prod"), args.database)
    results = []
    try:
        checks = [
            ("AC-1", lambda: ac1(dev_conn)),
            ("AC-1b", lambda: ac1b(dev_conn)),
            ("AC-2", lambda: ac2(dev_conn)),
            ("AC-3", lambda: ac3(dev_conn, prod_conn)),
            ("AC-4", lambda: ac4(prod_conn)),
        ]
        for name, fn in checks:
            try:
                ok, detail = fn()
            except Exception as exc:  # noqa: BLE001 - 验收脚本需报告所有失败
                ok, detail = False, f"异常: {exc}"
            print(f"{name} {'PASS' if ok else 'FAIL'}: {detail}")
            results.append(ok)
    finally:
        dev_conn.close()
        prod_conn.close()

    raise SystemExit(0 if all(results) else 1)


if __name__ == "__main__":
    main()
