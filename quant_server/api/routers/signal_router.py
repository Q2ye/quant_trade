# -*- coding: utf-8 -*-
"""
信号确认 API（v2.0 实盘手动交易）

POST /quantTrade/signals/{signal_id}/confirm  — 确认成交
POST /quantTrade/signals/{signal_id}/cancel    — 取消信号
GET  /quantTrade/signals/pending               — 列出待确认信号
"""
import logging
from datetime import datetime
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Query
from api.dependencies.event_engine import get_event_engine
from pydantic import BaseModel, Field

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/quantTrade/signals", tags=["signals"])


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
async def confirm_signal(signal_id: str, body: ConfirmSignalRequest, event_engine=Depends(get_event_engine)):
    """
    人工确认成交。

    用户在收到微信通知后，通过同花顺手动下单，成交后回系统标记。
    系统自动更新策略持仓。
    """
    from shared.database.session.session_manager import get_session_manager
    from shared.database.repositories.strategy.signal.signal_repo_v2 import update_signal_status
    from sqlalchemy import text

    sm = get_session_manager()
    async with sm.get_session() as session:
        # 先获取信号元数据
        r = await session.execute(
            text('SELECT strategy_id, ts_code FROM signals WHERE id = :sid'),
            {'sid': signal_id},
        )
        row = r.fetchone()
        if not row:
            raise HTTPException(404, f"信号 {signal_id} 不存在")
        strategy_id, ts_code = row[0], row[1]

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
                fill_price=body.fill_price,
                fill_quantity=body.fill_quantity,
                fill_time=body.fill_time,
            )
            await event_engine.put(event)
        except ImportError:
            pass  # EventEngine 未初始化时不阻塞

    return {"success": True, "signal_id": signal_id, "status": "confirmed"}


@router.post("/{signal_id}/cancel")
async def cancel_signal(signal_id: str, body: CancelSignalRequest):
    """
    人工取消信号。

    用户在收到微信通知后，判断不执行该信号（如开盘价超出范围），回系统标记取消。
    """
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
                "created_at": s.created_at.isoformat() if s.created_at else None,
            }
            for s in signals
        ],
    }
