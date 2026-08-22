# -*- coding: utf-8 -*-
"""
恐慌指数历史回算（阶段 4b，一次性初始化）

建表（幂等）+ 计算 2019-01-01 ~ 昨天的恐慌指数。

执行: cd quant_server && .venv/Scripts/python.exe scripts/backfill_panic_index.py [start]
默认 start: 2019-01-01（stock_daily 全量可用起点，M2 反例统计同区间）
"""
import asyncio
import sys
from datetime import date, timedelta
from pathlib import Path

DEFAULT_START = "2019-01-01"


def _load_env() -> dict:
    env = {}
    p = Path(__file__).resolve().parents[1] / ".env"
    if p.exists():
        for line in p.read_text(encoding="utf-8", errors="ignore").splitlines():
            line = line.strip()
            if line and not line.startswith("#") and "=" in line:
                k, _, v = line.partition("=")
                env[k.strip()] = v.strip()
    return env


async def main() -> None:
    from sqlalchemy.ext.asyncio import create_async_engine, async_sessionmaker
    from sqlalchemy import text

    start = date.fromisoformat(sys.argv[1] if len(sys.argv) > 1 else DEFAULT_START)
    end = date.today() - timedelta(days=1)

    env = _load_env()
    user = env.get("DB_USER", "postgres")
    password = env.get("DB_PASSWORD", "")
    host = env.get("DB_HOST", "localhost")
    port = env.get("DB_PORT", "5432")
    dbname = env.get("DB_DEV_NAME", "quant_signals_dev")
    url = f"postgresql+asyncpg://{user}:{password}@{host}:{port}/{dbname}"
    engine = create_async_engine(url)
    Session = async_sessionmaker(engine, expire_on_commit=False)

    async with Session() as session:
        # 建表（幂等，分语句执行——asyncpg 不支持多语句 text）
        await session.execute(text("""
            CREATE TABLE IF NOT EXISTS panic_index (
                trade_date      DATE NOT NULL,
                panic_idx       NUMERIC(8,4) NOT NULL,
                median_pct_chg  NUMERIC(8,4),
                down_ratio      NUMERIC(8,4),
                created_at      TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP,
                PRIMARY KEY (trade_date)
            )
        """))
        await session.execute(text(
            "CREATE INDEX IF NOT EXISTS idx_panic_index_date ON panic_index(trade_date)"
        ))
        await session.commit()
        print(f"panic_index 表就绪")

        from modules.data.services.panic_index_service import PanicIndexService
        n = await PanicIndexService.recalculate(session, start, end)
        print(f"回算完成: {start} ~ {end}, {n} 个交易日")

        latest = await PanicIndexService.get_latest(session)
        print(f"最新恐慌指数: {latest}")

    await engine.dispose()


if __name__ == "__main__":
    asyncio.run(main())
