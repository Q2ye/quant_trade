# -*- coding: utf-8 -*-
"""回填 market_state_daily.limit_up_count / avg_turnover（方案 B，一次性）

用法（CWD=quant_server）:
    python -m scripts.data.backfill_emotion_metrics

前置:
    1. 已执行 DDL（docs/02-功能设计/市场模块/Market概览页重设计-开发路径说明.md §10.15）:
       ALTER TABLE market_state_daily ADD COLUMN IF NOT EXISTS limit_up_count INT;
       ALTER TABLE market_state_daily ADD COLUMN IF NOT EXISTS avg_turnover NUMERIC(8,4);
    2. market_state_daily 行已由 classifier 生成（无行则先跑 classifier）。
"""
import asyncio
import logging
import sys
from pathlib import Path

import asyncpg

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from _db_env import db_kwargs

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
logger = logging.getLogger(__name__)


def _get_db_config() -> dict:
    return db_kwargs()


async def main() -> None:
    from modules.data.services.market_state_classifier import (
        update_emotion_metrics,
        CLASSIFIED_BY,
    )
    conn = await asyncpg.connect(**_get_db_config())
    try:
        min_date = await conn.fetchval(
            "SELECT MIN(trade_date) FROM market_state_daily WHERE classified_by = $1",
            CLASSIFIED_BY,
        )
        if not min_date:
            logger.warning("market_state_daily 无数据，请先运行 classifier 生成行")
            return
        # 无需前序窗口：涨停家数/换手率均为当日口径，直接从最早行起算
        updated = await update_emotion_metrics(conn, since=min_date)
        total_l = await conn.fetchval(
            "SELECT COUNT(*) FROM market_state_daily WHERE limit_up_count IS NOT NULL")
        total_t = await conn.fetchval(
            "SELECT COUNT(*) FROM market_state_daily WHERE avg_turnover IS NOT NULL")
        logger.info(
            "回填完成：写入 %d 行；limit_up_count 已填充 %d 天；avg_turnover 已填充 %d 天",
            updated, total_l or 0, total_t or 0,
        )
    finally:
        await conn.close()


if __name__ == "__main__":
    asyncio.run(main())
