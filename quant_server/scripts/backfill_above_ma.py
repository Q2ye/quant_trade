# -*- coding: utf-8 -*-
"""回填 market_state_daily.above_ma20_pct / above_ma60_pct（方案 A，一次性）

用法（CWD=quant_server）:
    python -m scripts.backfill_above_ma

前置:
    1. 已执行 DDL（docs/02-功能设计/市场模块/Market概览页重设计-开发路径说明.md §10.14）:
       ALTER TABLE market_state_daily ADD COLUMN IF NOT EXISTS above_ma20_pct NUMERIC(6,3);
       ALTER TABLE market_state_daily ADD COLUMN IF NOT EXISTS above_ma60_pct NUMERIC(6,3);
    2. market_state_daily 行已由 classifier 生成（无行则先跑 classifier）。
"""
import asyncio
import logging
from datetime import timedelta

import asyncpg

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
logger = logging.getLogger(__name__)


def _get_db_config() -> dict:
    try:
        from shared.config.config_manager import config
        db = config.settings.DATABASE
        return {
            "host": db.HOST, "port": int(db.PORT),
            "user": db.USER, "password": db.PASSWORD,
            "database": db.NAME,
        }
    except Exception:
        return {
            "host": "localhost", "port": 5432, "user": "postgres",
            "password": "123456", "database": "quant_signals_dev",
        }


async def main() -> None:
    from modules.data.services.market_state_classifier import (
        update_above_ma_ratios,
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
        # 窗口扫描需提前 100 天（MA60 前序完整）
        updated = await update_above_ma_ratios(conn, since=min_date - timedelta(days=100))
        total = await conn.fetchval(
            "SELECT COUNT(*) FROM market_state_daily WHERE above_ma20_pct IS NOT NULL")
        logger.info("回填完成：更新 %d 天；above_ma20_pct 已填充共 %d 天", updated, total or 0)
    finally:
        await conn.close()


if __name__ == "__main__":
    asyncio.run(main())
