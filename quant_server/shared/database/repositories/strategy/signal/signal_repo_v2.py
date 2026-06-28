# -*- coding: utf-8 -*-
"""
SignalRepository v2.0 扩展方法（实盘人工确认）

通过 monkey-patch 或 mixin 方式为 SignalRepository 增加：
- get_pending_signals: 列出待确认信号
- expire_stale_signals: 过期信号标记
- update_signal_status: 便捷状态更新
"""
import logging
from datetime import date, datetime
from typing import List, Optional

from sqlalchemy import update, desc

from shared.database.models.business_models import Signal
from shared.database.repositories.base import RepositoryError

logger = logging.getLogger(__name__)


async def get_pending_signals(
    session,
    strategy_id: Optional[str] = None,
    limit: int = 50,
) -> list:
    """获取待人工确认的信号"""
    from sqlalchemy import select
    stmt = select(Signal).where(
        Signal.signal_status == "pending_manual"
    )
    if strategy_id:
        stmt = stmt.where(Signal.strategy_id == strategy_id)
    stmt = stmt.order_by(desc(Signal.signal_time)).limit(limit)

    result = await session.execute(stmt)
    return result.scalars().all()


async def expire_stale_signals(session, before_date: date) -> int:
    """将超期未确认的信号标记为 expired"""
    stmt = (
        update(Signal)
        .where(
            Signal.signal_status == "pending_manual",
            Signal.signal_time < before_date,
        )
        .values(signal_status="expired")
    )
    result = await session.execute(stmt)
    await session.commit()
    return result.rowcount or 0


async def update_signal_status(
    session, signal_id: str, status: str, **extra_fields
) -> bool:
    """更新信号确认状态"""
    from sqlalchemy import update as sql_update
    values = {"signal_status": status, **extra_fields}
    stmt = sql_update(Signal).where(Signal.id == signal_id).values(**values)
    await session.execute(stmt)
    await session.commit()
    return True
