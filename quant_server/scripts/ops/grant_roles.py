# -*- coding: utf-8 -*-
"""创建/更新应用数据库角色与权限（REQ-20261108-db-env-isolation 任务 6）。

用法:
    python scripts/ops/grant_roles.py --dry-run
    python scripts/ops/grant_roles.py --apply --database quant_signals

角色:
    quant_prod  public 读写（含日终同步、账户、策略、交易）
    quant_dev   public 只读 + dev 读写
    quant_ro    可选，public 只读（--with-ro）

密码来源:
    PROD_DB_PASSWORD / DB_DEV_PASSWORD / DB_RO_PASSWORD，缺失时回退 DB_PASSWORD。
DDL 连接:
    DB_DDL_*，缺失时回退 DB_*（需要建角色权限）。
"""
import argparse
import os
from pathlib import Path

import psycopg2
from psycopg2 import sql

# 与 shared.config 一致：把 quant_server/.env 注入进程环境（override=False）
try:
    from dotenv import load_dotenv

    _ENV_FILE = Path(__file__).resolve().parents[2] / ".env"
    if _ENV_FILE.exists():
        load_dotenv(_ENV_FILE, override=False)
except ImportError:
    pass

PROD_ROLE = "quant_prod"
DEV_ROLE = "quant_dev"
RO_ROLE = "quant_ro"


def _env(name: str, default=None):
    return os.environ.get(name, default)


def _password(role: str) -> str:
    if role == PROD_ROLE:
        return _env("PROD_DB_PASSWORD") or _env("DB_PASSWORD", "")
    if role == DEV_ROLE:
        return _env("DB_DEV_PASSWORD") or _env("DB_PASSWORD", "")
    return _env("DB_RO_PASSWORD") or _env("DB_PASSWORD", "")


def _ddl_user() -> str:
    user = _env("DB_DDL_USER") or _env("DB_USER")
    if not user:
        raise SystemExit("缺少 DB_DDL_USER / DB_USER（DDL 需要建角色权限）")
    return user


def _ddl_connect(database: str):
    return psycopg2.connect(
        host=_env("DB_DDL_HOST") or _env("DB_HOST", "localhost"),
        port=int(_env("DB_DDL_PORT") or _env("DB_PORT", "5432")),
        user=_ddl_user(),
        password=_env("DB_DDL_PASSWORD") or _env("DB_PASSWORD", ""),
        database=database,
    )


def _build_plan(database: str, ddl_user: str, with_ro: bool) -> list[str]:
    plan = [
        "REVOKE CREATE ON SCHEMA public FROM PUBLIC;",
        f"CREATE ROLE {PROD_ROLE} LOGIN PASSWORD '<from PROD_DB_PASSWORD>';",
        f"ALTER ROLE {PROD_ROLE} SET search_path = public;",
        f"ALTER ROLE {PROD_ROLE} NOSUPERUSER NOCREATEDB NOCREATEROLE;",
        f"CREATE ROLE {DEV_ROLE} LOGIN PASSWORD '<from DB_DEV_PASSWORD>';",
        f"ALTER ROLE {DEV_ROLE} SET search_path = dev, public;",
        f"ALTER ROLE {DEV_ROLE} NOSUPERUSER NOCREATEDB NOCREATEROLE;",
        f"GRANT CONNECT ON DATABASE {database} TO {PROD_ROLE}, {DEV_ROLE};",
        f"GRANT USAGE ON SCHEMA public TO {PROD_ROLE}, {DEV_ROLE};",
        f"GRANT SELECT, INSERT, UPDATE, DELETE ON ALL TABLES IN SCHEMA public TO {PROD_ROLE};",
        f"GRANT USAGE, SELECT ON ALL SEQUENCES IN SCHEMA public TO {PROD_ROLE};",
        f"GRANT SELECT ON ALL TABLES IN SCHEMA public TO {DEV_ROLE};",
        f"REVOKE CREATE ON SCHEMA public FROM {DEV_ROLE};",
        f"REVOKE INSERT, UPDATE, DELETE, TRUNCATE ON ALL TABLES IN SCHEMA public FROM {DEV_ROLE};",
        f"REVOKE ALL ON ALL SEQUENCES IN SCHEMA public FROM {DEV_ROLE};",
        f"ALTER DEFAULT PRIVILEGES FOR ROLE {ddl_user} IN SCHEMA public "
        f"GRANT SELECT, INSERT, UPDATE, DELETE ON TABLES TO {PROD_ROLE};",
        f"ALTER DEFAULT PRIVILEGES FOR ROLE {ddl_user} IN SCHEMA public "
        f"GRANT SELECT ON TABLES TO {DEV_ROLE};",
        f"-- dev schema 存在时追加: GRANT USAGE / DML ON SCHEMA dev TO {DEV_ROLE}",
    ]
    if with_ro:
        plan += [
            f"CREATE ROLE {RO_ROLE} LOGIN PASSWORD '<from DB_RO_PASSWORD>';",
            f"ALTER ROLE {RO_ROLE} SET search_path = public;",
            f"ALTER ROLE {RO_ROLE} NOSUPERUSER NOCREATEDB NOCREATEROLE;",
            f"ALTER ROLE {RO_ROLE} SET default_transaction_read_only = on;",
            f"GRANT CONNECT ON DATABASE {database} TO {RO_ROLE};",
            f"GRANT USAGE ON SCHEMA public TO {RO_ROLE};",
            f"GRANT SELECT ON ALL TABLES IN SCHEMA public TO {RO_ROLE};",
        ]
    return plan


def _apply(conn, database: str, with_ro: bool) -> None:
    conn.autocommit = True
    cur = conn.cursor()
    cur.execute("SELECT current_user")
    ddl_user = cur.fetchone()[0]

    roles = [(PROD_ROLE, "public"), (DEV_ROLE, "dev, public")]
    if with_ro:
        roles.append((RO_ROLE, "public"))

    for role, search_path in roles:
        password = _password(role)
        cur.execute("SELECT 1 FROM pg_roles WHERE rolname = %s", (role,))
        exists = cur.fetchone() is not None
        if exists:
            if password:
                cur.execute(
                    sql.SQL("ALTER ROLE {} PASSWORD {}").format(
                        sql.Identifier(role), sql.Literal(password)
                    )
                )
        else:
            cur.execute(
                sql.SQL("CREATE ROLE {} LOGIN PASSWORD {}").format(
                    sql.Identifier(role), sql.Literal(password)
                )
            )
        cur.execute(
            sql.SQL("ALTER ROLE {} SET search_path = {}").format(
                sql.Identifier(role), sql.SQL(search_path)
            )
        )
        cur.execute(
            sql.SQL("ALTER ROLE {} NOSUPERUSER NOCREATEDB NOCREATEROLE").format(
                sql.Identifier(role)
            )
        )
        if role == RO_ROLE:
            cur.execute(
                sql.SQL("ALTER ROLE {} SET default_transaction_read_only = on").format(
                    sql.Identifier(role)
                )
            )

    cur.execute(sql.SQL("REVOKE CREATE ON SCHEMA public FROM PUBLIC"))
    cur.execute(
        sql.SQL("REVOKE CREATE ON SCHEMA public FROM {}").format(
            sql.Identifier(DEV_ROLE)
        )
    )
    cur.execute(
        sql.SQL("GRANT CONNECT ON DATABASE {} TO {}, {}").format(
            sql.Identifier(database), sql.Identifier(PROD_ROLE), sql.Identifier(DEV_ROLE)
        )
    )
    cur.execute(
        sql.SQL("GRANT USAGE ON SCHEMA public TO {}, {}").format(
            sql.Identifier(PROD_ROLE), sql.Identifier(DEV_ROLE)
        )
    )
    cur.execute(
        sql.SQL("GRANT SELECT, INSERT, UPDATE, DELETE ON ALL TABLES IN SCHEMA public TO {}").format(
            sql.Identifier(PROD_ROLE)
        )
    )
    cur.execute(
        sql.SQL("GRANT USAGE, SELECT ON ALL SEQUENCES IN SCHEMA public TO {}").format(
            sql.Identifier(PROD_ROLE)
        )
    )
    cur.execute(
        sql.SQL("GRANT SELECT ON ALL TABLES IN SCHEMA public TO {}").format(
            sql.Identifier(DEV_ROLE)
        )
    )
    cur.execute(
        sql.SQL("ALTER DEFAULT PRIVILEGES FOR ROLE {} IN SCHEMA public "
                "GRANT SELECT, INSERT, UPDATE, DELETE ON TABLES TO {}").format(
            sql.Identifier(ddl_user), sql.Identifier(PROD_ROLE)
        )
    )
    cur.execute(
        sql.SQL("ALTER DEFAULT PRIVILEGES FOR ROLE {} IN SCHEMA public "
                "GRANT SELECT ON TABLES TO {}").format(
            sql.Identifier(ddl_user), sql.Identifier(DEV_ROLE)
        )
    )
    # 收敛：即使 dev 历史上被授予过 public 写权限，也显式回收
    cur.execute(
        sql.SQL("REVOKE INSERT, UPDATE, DELETE, TRUNCATE ON ALL TABLES IN SCHEMA public FROM {}").format(
            sql.Identifier(DEV_ROLE)
        )
    )
    cur.execute(
        sql.SQL("REVOKE ALL ON ALL SEQUENCES IN SCHEMA public FROM {}").format(
            sql.Identifier(DEV_ROLE)
        )
    )

    cur.execute("SELECT 1 FROM pg_namespace WHERE nspname = 'dev'")
    if cur.fetchone():
        cur.execute(
            sql.SQL("GRANT USAGE ON SCHEMA dev TO {}").format(sql.Identifier(DEV_ROLE))
        )
        cur.execute(
            sql.SQL("GRANT SELECT, INSERT, UPDATE, DELETE ON ALL TABLES IN SCHEMA dev TO {}").format(
                sql.Identifier(DEV_ROLE)
            )
        )
        cur.execute(
            sql.SQL("GRANT USAGE, SELECT ON ALL SEQUENCES IN SCHEMA dev TO {}").format(
                sql.Identifier(DEV_ROLE)
            )
        )
        cur.execute(
            sql.SQL("ALTER DEFAULT PRIVILEGES FOR ROLE {} IN SCHEMA dev "
                    "GRANT SELECT, INSERT, UPDATE, DELETE ON TABLES TO {}").format(
                sql.Identifier(ddl_user), sql.Identifier(DEV_ROLE)
            )
        )
    else:
        print("提示: dev schema 尚不存在，跳过 dev 授权（任务 7 创建后重跑本脚本）")

    if with_ro:
        cur.execute(
            sql.SQL("GRANT CONNECT ON DATABASE {} TO {}").format(
                sql.Identifier(database), sql.Identifier(RO_ROLE)
            )
        )
        cur.execute(
            sql.SQL("GRANT USAGE ON SCHEMA public TO {}").format(sql.Identifier(RO_ROLE))
        )
        cur.execute(
            sql.SQL("GRANT SELECT ON ALL TABLES IN SCHEMA public TO {}").format(
                sql.Identifier(RO_ROLE)
            )
        )
        cur.execute(
            sql.SQL("ALTER DEFAULT PRIVILEGES FOR ROLE {} IN SCHEMA public "
                    "GRANT SELECT ON TABLES TO {}").format(
                sql.Identifier(ddl_user), sql.Identifier(RO_ROLE)
            )
        )

    cur.close()


def main() -> None:
    ap = argparse.ArgumentParser(description="创建/更新应用数据库角色与权限")
    ap.add_argument("--dry-run", action="store_true", help="只打印 SQL，不连接")
    ap.add_argument("--apply", action="store_true", help="执行")
    ap.add_argument("--database", default=_env("PROD_DB_NAME", "quant_signals"),
                    help="目标数据库（默认 PROD_DB_NAME 或 quant_signals）")
    ap.add_argument("--with-ro", action="store_true", help="同时创建 quant_ro")
    args = ap.parse_args()

    if args.apply and args.dry_run:
        raise SystemExit("--dry-run 与 --apply 只能二选一")

    if not args.apply:
        ddl_user = _ddl_user()
        print("\n".join(_build_plan(args.database, ddl_user, args.with_ro)))
        print("\n[dry-run] 未执行；加 --apply 执行。")
        return

    conn = _ddl_connect(args.database)
    try:
        _apply(conn, args.database, args.with_ro)
        print("[OK] 角色与权限已应用")
    finally:
        conn.close()


if __name__ == "__main__":
    main()
