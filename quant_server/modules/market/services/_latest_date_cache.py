# -*- coding: utf-8 -*-
"""最新交易日期查询 — 进程内 TTL 缓存

背景：stock_daily / stock_daily_basic / etf_daily 为 TimescaleDB 压缩超表，
``SELECT MAX(trade_date)`` 会全量扫描所有压缩 chunk（实测 ~3.4s）。
数据同步频率远低于查询频率，因此：
1. 缓存最近一次 MAX 结果（60s TTL）；
2. TTL 到期后先做「是否存在比缓存值更新的数据」快速检查
   （``WHERE trade_date > :prev LIMIT 1``，TimescaleDB 按时间分块排除旧 chunk，
   实测 ~1-70ms），无新数据则仅续期；
3. 只有首次调用或确认有新数据（即每次数据同步完成后）才执行全量 MAX。

语义始终等于真实 MAX(trade_date)，仅引入最多 TTL 秒的短暂延迟。
"""
import logging
import time
from typing import Dict, Optional, Tuple

from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

logger = logging.getLogger(__name__)

_TTL = 60.0  # 秒
_cache: Dict[str, Tuple[float, object]] = {}


async def get_latest_trade_date(session: AsyncSession, table: str) -> Optional[object]:
    """返回 table 的最新 trade_date（进程内缓存；同步完成后自动感知新数据）。

    Args:
        session: 数据库会话
        table: 表名（仅限内部常量，如 stock_daily / stock_daily_basic / etf_daily）
    """
    now = time.monotonic()
    hit = _cache.get(table)

    if hit is not None and hit[1] is not None and (now - hit[0]) < _TTL:
        return hit[1]

    if hit is not None and hit[1] is not None:
        # 快速检查：是否存在比缓存值更新的数据（只访问比 prev 新的 chunk）
        try:
            newer = await session.execute(
                text(f"SELECT 1 FROM {table} WHERE trade_date > :prev LIMIT 1"),
                {"prev": hit[1]},
            )
            if newer.scalar() is None:
                _cache[table] = (now, hit[1])  # 无新数据，仅续期
                return hit[1]
        except Exception:
            logger.warning("latest_date 快速检查失败，回退全量 MAX: %s", table, exc_info=True)

    # 首次调用 / 缓存值为空 / 确认有新数据 → 全量 MAX（每次同步后仅一次）
    try:
        row = await session.execute(text(f"SELECT MAX(trade_date) FROM {table}"))
        value = row.scalar()
        _cache[table] = (now, value)
        return value
    except Exception:
        logger.error("查询 %s 最新交易日期失败", table, exc_info=True)
        raise
