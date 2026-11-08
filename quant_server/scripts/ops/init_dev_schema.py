# -*- coding: utf-8 -*-
"""初始化 dev schema（REQ-20261108-db-env-isolation 任务 7）。

做法:
    1. 取 public 中的「应用表」= 全部表 - MARKET_TABLES
    2. 按 FK 依赖拓扑排序，逐表 CREATE TABLE dev.x (LIKE public.x INCLUDING ALL)
    3. 重建触发器（LIKE 不复制 trigger）
    4. 重建 TimescaleDB 超表
    5. 种子 dev 用户 / 账户 / 少量参考数据

用法:
    python scripts/ops/init_dev_schema.py --dry-run
    python scripts/ops/init_dev_schema.py --apply
    python scripts/ops/init_dev_schema.py --apply --recreate

DDL 连接: DB_DDL_*，缺失时回退 DB_*；数据库默认 PROD_DB_NAME 或 quant_signals。
"""
import argparse
import base64
import os
import re
import secrets
from pathlib import Path

import psycopg2
from psycopg2 import sql

try:
    from dotenv import load_dotenv

    _ENV_FILE = Path(__file__).resolve().parents[2] / ".env"
    if _ENV_FILE.exists():
        load_dotenv(_ENV_FILE, override=False)
except ImportError:
    pass

# 市场数据域：留在 public，dev 只读。其余 public 表都克隆到 dev。
MARKET_TABLES = {
    "stock_basic", "stock_company", "stock_daily", "stock_weekly", "stock_monthly",
    "stock_adj_factor", "stock_adjusted_prices", "stock_daily_basic",
    "stock_daily_limit", "stock_suspend_info", "stock_limit_list",
    "stock_moneyflow", "stock_moneyflow_hsgt", "stock_st_list", "stock_st_risk",
    "stock_hsgt", "stock_minutes", "stock_top10_holders",
    "stock_top10_float_holders", "stock_stk_holdernumber", "stock_stk_holdertrade",
    "stock_pledge_stat", "stock_share_float", "stock_dividends",
    "stock_forecasts", "stock_expresses", "stock_audit_opinions",
    "stock_business_incomes", "stock_fina_indicators", "stock_forecast_pro",
    "stock_factor_daily", "stock_factor_pro_daily",
    "etf_basic", "etf_daily", "etf_index", "etf_minute", "etf_shares",
    "fund_adj_factor",
    "index_basic", "index_daily", "index_weekly", "index_weight",
    "index_dailybasic", "index_sw_classify", "index_sw_member",
    "index_sw_daily", "index_factor_pro_daily",
    "macro_cpi", "macro_ppi", "macro_gdp",
    "margin", "factor_data", "market_state_daily", "panic_index",
    "trade_calendar", "stk_managers", "stk_rewards",
    "financial_income", "financial_balance", "financial_cashflow",
    "financial_disclosure_dates",
}

DEV_USER_ID = "dev00000-0000-0000-0000-000000000001"
DEV_ACCOUNT_ID = "dev00000-0000-0000-0000-000000000002"
DEV_USERNAME = "dev"
DEV_ACCOUNT_NUMBER = "DEV000001"

SEED_TABLES = ("trade_fees", "risk_rules", "system_configs")


def _env(name: str, default=None):
    return os.environ.get(name, default)


def _ddl_user() -> str:
    user = _env("DB_DDL_USER") or _env("DB_USER")
    if not user:
        raise SystemExit("缺少 DB_DDL_USER / DB_USER（DDL 需要建 schema 权限）")
    return user


def _connect(database: str):
    return psycopg2.connect(
        host=_env("DB_DDL_HOST") or _env("DB_HOST", "localhost"),
        port=int(_env("DB_DDL_PORT") or _env("DB_PORT", "5432")),
        user=_ddl_user(),
        password=_env("DB_DDL_PASSWORD") or _env("DB_PASSWORD", ""),
        database=database,
    )


def _public_tables(cur) -> list[str]:
    cur.execute(
        "SELECT tablename FROM pg_tables WHERE schemaname = 'public' ORDER BY tablename"
    )
    return [row[0] for row in cur.fetchall()]


def _app_tables(cur) -> list[str]:
    return [t for t in _public_tables(cur) if t not in MARKET_TABLES]


def _create_tables(cur, tables: list[str]) -> None:
    """按 public 建 dev 表；FK 由 _create_app_fks 显式补建。

    `LIKE ... INCLUDING ALL` 不复制外键，故建表后再补：
    应用域 FK 指向 dev，市场表 FK 指向 public。
    """
    cur.execute("CREATE SCHEMA IF NOT EXISTS dev")
    cur.execute("SET search_path = public")
    for table in tables:
        cur.execute(
            sql.SQL("CREATE TABLE IF NOT EXISTS dev.{} (LIKE public.{} INCLUDING ALL)").format(
                sql.Identifier(table), sql.Identifier(table)
            )
        )


def _create_app_fks(cur, tables: list[str]) -> int:
    """把 public 应用表的 FK 复制到 dev。

    `LIKE ... INCLUDING ALL` **不复制外键**，故必须显式补：
    - 父表在应用域 → REFERENCES dev.parent
    - 父表是市场表 → REFERENCES public.parent（只读引用）
    """
    table_set = set(tables)
    cur.execute(
        """
        SELECT c.conname,
               ch.relname AS child,
               pa.relname AS parent,
               pg_get_constraintdef(c.oid) AS definition
        FROM pg_constraint c
        JOIN pg_class ch ON ch.oid = c.conrelid
        JOIN pg_namespace cn ON cn.oid = ch.relnamespace
        JOIN pg_class pa ON pa.oid = c.confrelid
        JOIN pg_namespace pn ON pn.oid = pa.relnamespace
        WHERE c.contype = 'f' AND cn.nspname = 'public' AND ch.relname = ANY(%s)
        """,
        (tables,),
    )
    rows = cur.fetchall()
    created = 0
    for conname, child, parent, definition in rows:
        cur.execute(
            """
            SELECT 1 FROM pg_constraint c
            JOIN pg_class ch ON ch.oid = c.conrelid
            JOIN pg_namespace cn ON cn.oid = ch.relnamespace
            WHERE c.contype = 'f' AND c.conname = %s
              AND cn.nspname = 'dev' AND ch.relname = %s
            """,
            (conname, child),
        )
        if cur.fetchone():
            continue
        target_schema = "dev" if parent in table_set else "public"
        new_definition = re.sub(
            rf"REFERENCES\s+(?:public\.)?{re.escape(parent)}\b",
            f"REFERENCES {target_schema}.{parent}",
            definition,
            count=1,
        )
        expected_reference = f"REFERENCES {target_schema}.{parent}"
        if expected_reference not in new_definition:
            raise RuntimeError(
                f"FK 重写失败: {conname} ({child} -> {parent})，原文: {definition}"
            )
        cur.execute(
            sql.SQL("ALTER TABLE dev.{} ADD CONSTRAINT {} ").format(
                sql.Identifier(child), sql.Identifier(conname)
            ) + sql.SQL(new_definition)
        )
        created += 1
    return created


def _create_triggers(cur, tables: list[str]) -> int:
    cur.execute(
        """
        SELECT t.tgname, c.relname, pg_get_triggerdef(t.oid) AS definition
        FROM pg_trigger t
        JOIN pg_class c ON c.oid = t.tgrelid
        JOIN pg_namespace n ON n.oid = c.relnamespace
        WHERE NOT t.tgisinternal AND n.nspname = 'public'
          AND c.relname = ANY(%s)
        """,
        (tables,),
    )
    rows = cur.fetchall()
    created = 0
    for trigger_name, table_name, definition in rows:
        cur.execute(
            sql.SQL("DROP TRIGGER IF EXISTS {} ON dev.{}").format(
                sql.Identifier(trigger_name), sql.Identifier(table_name)
            )
        )
        dev_definition = definition.replace(
            f" ON public.{table_name} ", f" ON dev.{table_name} "
        )
        if f" ON dev.{table_name} " not in dev_definition:
            raise RuntimeError(
                f"触发器重写失败: {trigger_name} ({table_name})，原文: {definition}"
            )
        cur.execute(dev_definition)
        created += 1
    return created


def _create_hypertables(cur, tables: list[str]) -> int:
    cur.execute(
        """
        SELECT h.hypertable_name, d.column_name
        FROM timescaledb_information.hypertables h
        JOIN timescaledb_information.dimensions d
          ON d.hypertable_name = h.hypertable_name
         AND d.dimension_number = 1
        WHERE h.hypertable_schema = 'public'
          AND h.hypertable_name = ANY(%s)
        """,
        (tables,),
    )
    rows = cur.fetchall()
    created = 0
    for table_name, time_column in rows:
        cur.execute(
            sql.SQL("SELECT create_hypertable('dev.{}', {}, if_not_exists => TRUE)").format(
                sql.Identifier(table_name), sql.Literal(time_column)
            )
        )
        created += 1
    return created


def _seed(cur) -> None:
    cur.execute("SELECT 1 FROM dev.sys_users WHERE id = %s", (DEV_USER_ID,))
    if cur.fetchone() is None:
        seed_password = os.environ.get("DEV_SEED_PASSWORD") or secrets.token_urlsafe(12)
        password = base64.b64encode(seed_password.encode("utf-8")).decode("ascii")
        cur.execute(
            """
            INSERT INTO dev.sys_users (id, username, password, role, is_active)
            VALUES (%s, %s, %s, 'admin', TRUE)
            """,
            (DEV_USER_ID, DEV_USERNAME, password),
        )
        if not os.environ.get("DEV_SEED_PASSWORD"):
            print(f"[INFO] dev 种子用户口令（仅本次生成）: {seed_password}")
    cur.execute(
        """
        INSERT INTO dev.accounts
            (id, account_number, account_name, user_id, account_type, status,
             total_balance, available_balance, initial_balance)
        VALUES (%s, %s, %s, %s, 'simulation', 'active', 100000, 100000, 100000)
        ON CONFLICT (id) DO NOTHING
        """,
        (DEV_ACCOUNT_ID, DEV_ACCOUNT_NUMBER, "开发测试账户", DEV_USER_ID),
    )
    for table in SEED_TABLES:
        savepoint = f"seed_{table}"
        cur.execute(f"SAVEPOINT {savepoint}")
        try:
            cur.execute(
                sql.SQL("INSERT INTO dev.{} SELECT * FROM public.{} ON CONFLICT DO NOTHING").format(
                    sql.Identifier(table), sql.Identifier(table)
                )
            )
            cur.execute(f"RELEASE SAVEPOINT {savepoint}")
            print(f"  种子: {table} <- public")
        except Exception as exc:
            cur.execute(f"ROLLBACK TO SAVEPOINT {savepoint}")
            print(f"  [WARN] 种子 {table} 跳过: {str(exc)[:120]}")


def main() -> None:
    ap = argparse.ArgumentParser(description="初始化 dev schema")
    ap.add_argument("--dry-run", action="store_true", help="只列出将克隆的表，不建表")
    ap.add_argument("--apply", action="store_true", help="执行")
    ap.add_argument("--recreate", action="store_true", help="先 DROP SCHEMA dev CASCADE")
    ap.add_argument("--database", default=_env("PROD_DB_NAME", "quant_signals"))
    args = ap.parse_args()

    if args.apply and args.dry_run:
        raise SystemExit("--dry-run 与 --apply 只能二选一")

    conn = _connect(args.database)
    conn.autocommit = False
    cur = conn.cursor()
    try:
        tables = _app_tables(cur)
        if not tables:
            raise SystemExit("未找到应用表：请确认连接到 quant_signals")

        print(f"应用表 {len(tables)} 张（public 总数 - {len(MARKET_TABLES)} 张市场表）")
        for table in tables:
            print(f"  {table}")

        if not args.apply:
            print("\n[dry-run] 未执行；加 --apply 执行。")
            return

        if args.recreate:
            cur.execute("DROP SCHEMA IF EXISTS dev CASCADE")
            print("已 DROP SCHEMA dev CASCADE")

        _create_tables(cur, tables)
        fks = _create_app_fks(cur, tables)
        triggers = _create_triggers(cur, tables)
        hypertables = _create_hypertables(cur, tables)
        _seed(cur)
        conn.commit()

        cur.execute("SELECT count(*) FROM pg_tables WHERE schemaname = 'dev'")
        dev_count = cur.fetchone()[0]
        print(f"[OK] dev schema 完成: {dev_count} 张表, {fks} 个 FK, "
              f"{triggers} 个触发器, {hypertables} 个超表")
    except Exception:
        conn.rollback()
        raise
    finally:
        cur.close()
        conn.close()


if __name__ == "__main__":
    main()
