# -*- coding: utf-8 -*-
"""脚本统一数据库连接解析（REQ-20261108-script-dsn-unification）。

用法（脚本内）:
    import sys
    from pathlib import Path
    sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
    from _db_env import db_kwargs, db_url

    conn = await asyncpg.connect(**db_kwargs())
    engine = create_async_engine(db_url())

env:
    None  → 按 ENVIRONMENT 解析（production → PROD_DB_*；development → DB_DEV_*）
    "dev" → DB_DEV_*
    "prod" → PROD_DB_*
"""
import os
from pathlib import Path

_ENV_LOADED = False


def _load_env() -> None:
    """把 quant_server/.env 注入进程环境（override=False，已有的环境变量优先）。"""
    global _ENV_LOADED
    if _ENV_LOADED:
        return
    try:
        from dotenv import load_dotenv

        load_dotenv(Path(__file__).resolve().parents[1] / ".env", override=False)
    except ImportError:
        pass
    _ENV_LOADED = True


def _target_env(env: str | None) -> str:
    if env is None:
        return (os.getenv("ENVIRONMENT") or "development").lower()
    value = env.lower()
    if value in ("dev", "development"):
        return "development"
    if value in ("prod", "production"):
        return "production"
    raise SystemExit(f"非法 env={env!r}，只允许 dev/prod")


def db_kwargs(env: str | None = None) -> dict:
    """返回 psycopg2 / asyncpg 连接参数。"""
    _load_env()
    from shared.config.config_manager import DatabaseSettings, resolve_database_env

    target = _target_env(env)
    base = DatabaseSettings().model_dump()
    values, missing = resolve_database_env(target, base)
    if target != "development" and missing:
        raise SystemExit(f"生产 DB 配置缺失: {missing}")
    if values["USER"] == "postgres":
        raise SystemExit(
            "拒绝用 postgres 超管运行脚本；请配置 PROD_DB_USER=quant_prod / DB_DEV_USER=quant_dev"
        )
    return {
        "host": values["HOST"],
        "port": values["PORT"],
        "user": values["USER"],
        "password": values["PASSWORD"],
        "database": values["NAME"],
    }


def db_url(env: str | None = None) -> str:
    """返回 SQLAlchemy asyncpg 连接 URL。"""
    cfg = db_kwargs(env)
    return (
        f"postgresql+asyncpg://{cfg['user']}:{cfg['password']}"
        f"@{cfg['host']}:{cfg['port']}/{cfg['database']}"
    )
