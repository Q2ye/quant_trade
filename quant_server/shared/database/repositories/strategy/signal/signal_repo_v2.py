# -*- coding: utf-8 -*-
"""
SignalRepository v2.0 扩展方法（实盘人工确认）

通过 monkey-patch 或 mixin 方式为 SignalRepository 增加：
- get_pending_signals: 列出待确认信号
- expire_stale_signals: 过期信号标记
- update_signal_status: 便捷状态更新
- cancel_signals_if: 批量条件取消（实盘「当日目标池对账」用）
"""
import logging
from datetime import date, datetime
from typing import Iterable, List, Optional

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
    """更新信号确认状态（无条件流转）。

    Returns:
        True  — 确实更新了一行
        False — 目标信号不存在（调用方据此返回 404）

    修复 2026-09-12：此前恒返回 True，导致调用方的 404 分支永不生效。
    """
    from sqlalchemy import update as sql_update
    values = {"signal_status": status, **extra_fields}
    stmt = sql_update(Signal).where(Signal.id == signal_id).values(**values)
    result = await session.execute(stmt)
    await session.commit()
    return bool(result.rowcount)


async def update_signal_status_if(
    session,
    signal_id: str,
    status: str,
    allowed_from: Iterable[str],
    **extra_fields,
) -> bool:
    """条件状态流转：仅当当前状态 ∈ allowed_from 时才更新。

    用带旧状态条件的单条 UPDATE 实现，避免「先查后写」的竞态——
    重复点击或并发请求下，第二次会因状态已变而 rowcount=0 被拒。

    Args:
        allowed_from: 允许流转的旧状态集合

    Returns:
        True  — 已完成流转
        False — 信号不存在，或当前状态不在 allowed_from 中
    """
    from sqlalchemy import update as sql_update
    values = {"signal_status": status, **extra_fields}
    stmt = (
        sql_update(Signal)
        .where(Signal.id == signal_id, Signal.signal_status.in_(list(allowed_from)))
        .values(**values)
    )
    result = await session.execute(stmt)
    await session.commit()
    return bool(result.rowcount)


async def cancel_signals_if(
    session,
    signal_ids: Iterable[str],
    allowed_from: Iterable[str],
    reason: str = "",
) -> int:
    """批量条件取消：仅当当前状态 ∈ allowed_from 时才置为 cancelled。

    与 `update_signal_status_if` 同一竞态语义（旧状态条件写进 WHERE，不「先查后写」），
    区别只在**一次处理多条**：「当日目标池对账」会同时取消多个标的的过期买入意图，
    逐条 UPDATE 会退化成 N 次往返（违反批量写入约定）。

    ⚠️ 自动路径**不得**把 `confirmed` / `executed` 放进 allowed_from：
    人工确认与自动取消并发时，WHERE 的旧状态条件会让 rowcount=0，
    自动取消自然失败 —— **不会覆盖已成交事实**（人工路径 `_CANCELLABLE_FROM`
    含 confirmed 是人工判断，两者口径不同，勿混用）。

    ⚠️ 刻意**不写** `reviewed_at`：该列语义是「人工审核时间」，自动对账不是审核；
    与同类自动路径（`signal_engine._persist_signal` 的 supersede 分支）保持一致。
    状态变更时点由 `reason` + `strategy_decision.log` 的 `[pending对账]` 行留痕。

    Args:
        signal_ids: 目标信号 ID 集合（空集合直接返回 0，不发 SQL）
        allowed_from: 允许流转的旧状态集合
        reason: 取消原因（写入 signals.reason）

    Returns:
        实际流转的行数（0 = 无一条处于 allowed_from 中）
    """
    ids = [str(i) for i in signal_ids if i]
    if not ids:
        return 0
    from sqlalchemy import update as sql_update
    stmt = (
        sql_update(Signal)
        .where(Signal.id.in_(ids), Signal.signal_status.in_(list(allowed_from)))
        .values(signal_status="cancelled", reason=reason)
    )
    result = await session.execute(stmt)
    await session.commit()
    return int(result.rowcount or 0)
