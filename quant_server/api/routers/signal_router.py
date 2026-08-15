# -*- coding: utf-8 -*-
"""
信号确认 API（v2.0 实盘手动交易）

POST /quantTrade/signals/{signal_id}/confirm  — 确认成交
POST /quantTrade/signals/{signal_id}/cancel    — 取消信号
GET  /quantTrade/signals/pending               — 列出待确认信号
"""
import logging
from datetime import datetime
from typing import Optional, Dict

from fastapi import APIRouter, Depends, HTTPException, Query
from api.dependencies.event_engine import get_event_engine
from api.dependencies.auth import get_current_user
from pydantic import BaseModel, Field

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/quantTrade/signals", tags=["signals"])


# 修复 2026-08（B1）：信号确认/取消为资金级操作，加认证与交易权限
def _has_trade_permission(user: Dict) -> bool:
    role = user.get("role", user.get("user_role", ""))
    if role in ("superadmin", "admin"):
        return True
    return user.get("can_trade", False)


class ConfirmSignalRequest(BaseModel):
    fill_price: float = Field(..., gt=0, description="实际成交价")
    fill_quantity: int = Field(..., gt=0, description="实际成交数量（股）")
    fill_time: Optional[str] = Field(None, description="成交时间 ISO")


class CancelSignalRequest(BaseModel):
    reason: str = Field("手动取消", description="取消原因")


# ═══════════════════════════════════════════════════════════
# API 端点
# ═══════════════════════════════════════════════════════════


@router.post("/{signal_id}/confirm")
async def confirm_signal(
    signal_id: str,
    body: ConfirmSignalRequest,
    current_user: Dict = Depends(get_current_user),
    event_engine=Depends(get_event_engine),
):
    """
    人工确认成交。

    用户在收到微信通知后，通过同花顺手动下单，成交后回系统标记。
    系统自动更新策略持仓。
    """
    if not _has_trade_permission(current_user):
        raise HTTPException(403, "用户没有交易权限")
    from shared.database.session.session_manager import get_session_manager
    from shared.database.repositories.strategy.signal.signal_repo_v2 import update_signal_status
    from sqlalchemy import text

    sm = get_session_manager()
    async with sm.get_session() as session:
        # 先获取信号元数据
        r = await session.execute(
            text('SELECT strategy_id, ts_code, direction FROM signals WHERE id = :sid'),
            {'sid': signal_id},
        )
        row = r.fetchone()
        if not row:
            raise HTTPException(404, f"信号 {signal_id} 不存在")
        strategy_id, ts_code, direction = row[0], row[1], row[2]

        # 更新信号状态
        await update_signal_status(
            session, signal_id, "confirmed",
            price=body.fill_price,
            quantity=body.fill_quantity,
            reviewed_at=datetime.now(),
        )
        await session.commit()

        # 发布 SignalConfirmedEvent → StrategyManager 同步持仓
        try:
            from modules.strategy.events.signal_events import SignalConfirmedEvent
            event = SignalConfirmedEvent(
                strategy_id=strategy_id,
                signal_id=signal_id,
                ts_code=ts_code,
                direction=direction or "",
                fill_price=body.fill_price,
                fill_quantity=body.fill_quantity,
                fill_time=body.fill_time,
            )
            await event_engine.put(event)
        except ImportError:
            pass  # EventEngine 未初始化时不阻塞

    return {"success": True, "signal_id": signal_id, "status": "confirmed"}


@router.post("/{signal_id}/cancel")
async def cancel_signal(
    signal_id: str,
    body: CancelSignalRequest,
    current_user: Dict = Depends(get_current_user),
):
    """
    人工取消信号。

    用户在收到微信通知后，判断不执行该信号（如开盘价超出范围），回系统标记取消。
    """
    if not _has_trade_permission(current_user):
        raise HTTPException(403, "用户没有交易权限")
    from shared.database.session.session_manager import get_session_manager
    from shared.database.repositories.strategy.signal.signal_repo_v2 import update_signal_status

    sm = get_session_manager()
    async with sm.get_session() as session:
        ok = await update_signal_status(
            session, signal_id, "cancelled",
            reason=body.reason,
            reviewed_at=datetime.now(),
        )
        if not ok:
            raise HTTPException(404, f"信号 {signal_id} 不存在")
        await session.commit()

    return {"success": True, "signal_id": signal_id, "status": "cancelled"}


@router.get("/pending")
async def list_pending_signals(
    strategy_id: Optional[str] = Query(None),
    limit: int = Query(50, le=200),
    current_user: Dict = Depends(get_current_user),  # 修复 2026-08（B1）
):
    """
    列出所有待人工确认的信号（signal_status = pending_manual）。
    """
    from shared.database.session.session_manager import get_session_manager
    from shared.database.repositories.strategy.signal.signal_repo_v2 import get_pending_signals

    sm = get_session_manager()
    async with sm.get_session() as session:
        signals = await get_pending_signals(session, strategy_id=strategy_id, limit=limit)

    return {
        "success": True,
        "data": [
            {
                "id": s.id,
                "strategy_id": s.strategy_id,
                "ts_code": s.ts_code,
                "signal_type": s.signal_type,
                "direction": getattr(s, "direction", ""),
                "price": float(s.price) if s.price else 0,
                "price_limit_low": float(s.price_limit_low) if getattr(s, "price_limit_low", None) else None,
                "price_limit_high": float(s.price_limit_high) if getattr(s, "price_limit_high", None) else None,
                "quantity": s.quantity if getattr(s, "quantity", None) else 0,
                "confidence": float(getattr(s, "confidence", 1.0)),
                "reason": getattr(s, "reason", ""),
                "signal_time": s.signal_time.isoformat() if getattr(s, "signal_time", None) else None,
                "created_at": s.created_at.isoformat() if s.created_at else None,
            }
            for s in signals
        ],
    }


# ═══════════════════════════════════════════════════════════
# v3.4: 信号链路追溯 — 聚合 候选→信号→订单→成交
# ═══════════════════════════════════════════════════════════


@router.get("/{signal_id}/trace")
async def get_signal_trace(
    signal_id: str,
    current_user: Dict = Depends(get_current_user),  # 修复 2026-08（B1）
):
    """
    信号链路追溯：聚合 候选(parent) → 信号 → 订单 → 成交 完整链路。

    从任意信号 ID 出发，双向展开：
      - 顺向：该信号的下游（parent_id=该信号 的子信号）
      - 逆向：该信号的上游（parent_id 指向的父信号）
      - 订单：signals.order_id → orders
      - 成交：orders → trades

    Returns:
        {signal, parent, children, order, trades} — 各环节可为 null
    """
    from shared.database.session.session_manager import get_session_manager
    from sqlalchemy import text

    sm = get_session_manager()
    async with sm.get_session() as session:
        # 1. 当前信号
        cur = (await session.execute(
            text("""SELECT id, strategy_id, ts_code, signal_type, direction, signal_status,
                           price, quantity, reason, order_id, parent_id, signal_time, created_at
                    FROM signals WHERE id = :sid"""),
            {"sid": signal_id})).fetchone()
        if not cur:
            raise HTTPException(status_code=404, detail=f"信号 {signal_id} 不存在")

        def _sig_row(r):
            return {
                "id": r[0], "strategy_id": r[1], "ts_code": r[2],
                "signal_type": r[3], "direction": r[4], "signal_status": r[5],
                "price": float(r[6]) if r[6] else None,
                "quantity": r[7] if r[7] else 0,
                "reason": r[8] or "",
                "order_id": r[9], "parent_id": r[10],
                "signal_time": r[11].isoformat() if r[11] else None,
                "created_at": r[12].isoformat() if r[12] else None,
            }

        signal = _sig_row(cur)

        # 2. 逆向：父信号（候选）
        parent = None
        if cur[10]:  # parent_id
            p = (await session.execute(
                text("""SELECT id, strategy_id, ts_code, signal_type, direction, signal_status,
                               price, quantity, reason, order_id, parent_id, signal_time, created_at
                        FROM signals WHERE id = :pid"""),
                {"pid": cur[10]})).fetchone()
            if p:
                parent = _sig_row(p)

        # 3. 顺向：子信号（parent_id = 当前信号）
        children = []
        ch = (await session.execute(
            text("""SELECT id, strategy_id, ts_code, signal_type, direction, signal_status,
                           price, quantity, reason, order_id, parent_id, signal_time, created_at
                    FROM signals WHERE parent_id = :sid ORDER BY signal_time LIMIT 100"""),
            {"sid": signal_id})).fetchall()
        for c in ch:
            children.append(_sig_row(c))

        # 4. 订单（当前信号 order_id）
        order = None
        if cur[9]:
            o = (await session.execute(
                text("""SELECT order_id, ts_code, direction, price, volume,
                               filled_volume, filled_amount, avg_price, status,
                               submitted_at, filled_at
                        FROM orders WHERE order_id = :oid"""),
                {"oid": cur[9]})).fetchone()
            if o:
                order = {
                    "order_id": o[0], "ts_code": o[1], "direction": o[2],
                    "price": float(o[3]) if o[3] else None,
                    "volume": o[4] if o[4] else 0,
                    "filled_volume": o[5] if o[5] else 0,
                    "filled_amount": float(o[6]) if o[6] else 0,
                    "avg_price": float(o[7]) if o[7] else None,
                    "status": o[8],
                    "submitted_at": o[9].isoformat() if o[9] else None,
                    "filled_at": o[10].isoformat() if o[10] else None,
                }

        # 5. 成交（订单 → trades）
        trades = []
        if cur[9]:
            tr = (await session.execute(
                text("""SELECT trade_id, order_id, ts_code, price, volume, trade_time
                        FROM trades WHERE order_id = :oid ORDER BY trade_time LIMIT 100"""),
                {"oid": cur[9]})).fetchall()
            for t in tr:
                trades.append({
                    "trade_id": t[0], "order_id": t[1], "ts_code": t[2],
                    "price": float(t[3]) if t[3] else None,
                    "volume": t[4] if t[4] else 0,
                    "trade_time": t[5].isoformat() if t[5] else None,
                })

        return {
            "success": True,
            "data": {
                "signal": signal,
                "parent": parent,
                "children": children,
                "order": order,
                "trades": trades,
            },
        }
