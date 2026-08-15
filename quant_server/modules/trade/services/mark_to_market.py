# -*- coding: utf-8 -*-
"""
持仓盯市服务
监听数据同步完成事件 → 查询持仓股票的当日收盘价 → 更新浮动盈亏
"""
import logging
from datetime import date
from typing import Dict, List, Optional

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from modules.data.events.sync_events import DataSyncCompletedEvent
from shared.database.models.business_models import Position
from shared.database.models.data_models import StockAdjustedPrices, StockDaily

logger = logging.getLogger(__name__)

# 日线行情相关的 sync_type（监听这些类型的同步完成事件）
WATCHED_SYNC_TYPES = {"daily", "batch"}


async def _get_today_close_prices(
    session: AsyncSession, ts_codes: List[str], trade_date: date,
) -> Dict[str, float]:
    """批量查询指定股票在指定交易日的收盘价（优先复权数据）"""
    if not ts_codes:
        return {}

    prices: Dict[str, float] = {}

    # 修复 2026-08（C12）：盯市改用未复权收盘价，与持仓成本（原始成交价）口径一致。
    # 旧实现优先用前复权价（qfq），除权日市值与成本不可比导致 pnl 失真。
    q_daily = select(
        StockDaily.ts_code,
        StockDaily.close,
    ).where(
        StockDaily.trade_date == trade_date,
        StockDaily.ts_code.in_(ts_codes),
    )
    result = await session.execute(q_daily)
    for row in result.fetchall():
        if row[1] is not None:
            prices[row[0]] = float(row[1])

    return prices


async def mark_positions_to_market(
    session: AsyncSession,
    trade_date: Optional[date] = None,
) -> Dict:
    """
    对所有持仓执行盯市：查询当日收盘价并更新浮动盈亏。

    Args:
        session: 数据库异步会话（由调用方管理生命周期）
        trade_date: 交易日，默认今天

    Returns:
        Dict: {"updated": int, "skipped": int, "errors": int}
    """
    if trade_date is None:
        trade_date = date.today()

    # 1. 查出所有有持仓的非零仓位
    q = select(Position).where(Position.volume > 0)
    result = await session.execute(q)
    positions = result.scalars().all()

    if not positions:
        logger.debug("盯市跳过: 无持仓记录")
        return {"updated": 0, "skipped": 0, "errors": 0}

    # 2. 去重取股票代码列表
    ts_codes = list({p.ts_code for p in positions})
    logger.info("盯市: %d 个持仓 / %d 只股票, 交易日=%s", len(positions), len(ts_codes), trade_date)

    # 3. 批量查今日收盘价
    prices = await _get_today_close_prices(session, ts_codes, trade_date)

    if not prices:
        logger.warning("盯市: 未查到任何股票在 %s 的收盘价，跳过更新", trade_date)
        return {"updated": 0, "skipped": len(positions), "errors": 0}

    # 4. 逐条更新
    updated = 0
    skipped = 0
    errors = 0

    for pos in positions:
        last_price = prices.get(pos.ts_code)
        if last_price is None or last_price <= 0:
            skipped += 1
            continue

        try:
            cost = float(pos.cost_price) if pos.cost_price else 0.0
            volume = pos.volume if pos.volume else 0
            market_value = last_price * volume
            pnl = (last_price - cost) * volume
            pnl_rate = ((last_price - cost) / cost * 100) if cost > 0 else 0.0

            pos.last_price = last_price
            pos.market_value = market_value
            pos.pnl = pnl
            pos.pnl_rate = pnl_rate
            # last_update is handled by the Position model default

            updated += 1
        except Exception:
            logger.exception("盯市更新失败: pos_id=%s ts_code=%s", pos.id, pos.ts_code)
            errors += 1

    if updated > 0:
        await session.flush()
        logger.info(
            "盯市完成: updated=%d skipped=%d errors=%d (有价格=%d 只)",
            updated, skipped, errors, len(prices),
        )

    return {"updated": updated, "skipped": skipped, "errors": errors}


async def on_data_sync_completed(
    event: DataSyncCompletedEvent,
    session_factory,
) -> None:
    """
    数据同步完成事件处理器 — 触发盯市。

    此函数注册到 EventEngine 上，收到 DataSyncCompletedEvent 时自动调用。

    Args:
        event: 数据同步完成事件
        session_factory: 异步 session 工厂
    """
    sync_type = getattr(event, "sync_type", "") or ""
    # 只对日线/批量同步做盯市，跳过因子/财务/ETF 等
    if sync_type not in WATCHED_SYNC_TYPES:
        return

    if not session_factory:
        logger.warning("盯市跳过: session_factory 未注入")
        return

    logger.info("盯市触发: sync_type=%s", sync_type)

    try:
        async with session_factory() as session:
            result = await mark_positions_to_market(session)
            await session.commit()
            logger.info(
                "盯市完成: updated=%(updated)d skipped=%(skipped)d errors=%(errors)d",
                result,
            )
    except Exception:
        logger.exception("盯市执行失败")


def bind_mark_to_market(event_engine, session_factory) -> bool:
    """
    将盯市处理器绑定到事件引擎。

    在交易模块初始化时调用一次即可。

    Args:
        event_engine: 事件引擎实例
        session_factory: 异步 session 工厂（用于创建 DB 会话）

    Returns:
        bool: 绑定成功返回 True
    """
    if event_engine is None:
        logger.warning("盯市绑定失败: event_engine 为 None")
        return False
    if session_factory is None:
        logger.warning("盯市绑定失败: session_factory 为 None")
        return False

    async def _handler(event):
        await on_data_sync_completed(event, session_factory)

    event_engine.register_handler(DataSyncCompletedEvent, _handler)
    logger.info("盯市处理器已绑定 → DataSyncCompletedEvent")
    return True
