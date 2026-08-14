# -*- coding: utf-8 -*-
"""
买卖配对追溯服务（FIFO）

将同一账户 + 同一股票的买入/卖出成交按时间顺序做 FIFO 配对，
回答「这笔卖出吃掉了哪些买入、已实现盈亏多少」以及「当前持仓由哪些买入构成」。

计算型服务：不落库，实时基于 trades/orders 计算，无状态（不持有事件引擎）。
"""
import logging
from datetime import date, datetime
from decimal import Decimal
from typing import Dict, List, Optional, Tuple, Any

from sqlalchemy import and_, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import joinedload, selectinload

from shared.database.models.business_models import Order, Trade

logger = logging.getLogger(__name__)


class TradeRoundTripService:
    """买卖 FIFO 配对服务"""

    def __init__(self, session: AsyncSession):
        self.session = session

    async def get_round_trips(
        self,
        account_id: str,
        ts_code: Optional[str] = None,
    ) -> Dict[str, Any]:
        """计算账户的买卖配对明细。

        Args:
            account_id: 账户 ID
            ts_code: 可选，只看某只股票

        Returns:
            {
                "summary": {total_realized_pnl, closed_count, open_count},
                "stocks": [{ts_code, closed: [...], open: {...}}]
            }
        """
        trades = await self._load_trades(account_id, ts_code)

        # 按 ts_code 分组（保持成交时间升序）
        by_stock: Dict[str, List[Trade]] = {}
        for t in trades:
            by_stock.setdefault(t.ts_code, []).append(t)

        stocks: List[Dict[str, Any]] = []
        total_realized = Decimal("0")
        closed_count = 0
        open_count = 0

        for code in sorted(by_stock):
            stock_trades = sorted(by_stock[code], key=lambda t: self._time_key(t))
            closed, open_pos, realized = self._fifo_match(code, stock_trades)
            total_realized += realized
            closed_count += len(closed)
            if open_pos["remaining_volume"] > 0:
                open_count += 1
            stocks.append({
                "ts_code": code,
                "closed": closed,
                "open": open_pos,
                "realized_pnl": float(realized),
            })

        return {
            "summary": {
                "total_realized_pnl": float(total_realized),
                "closed_count": closed_count,
                "open_count": open_count,
            },
            "stocks": stocks,
        }

    # ==================== 内部 ====================

    async def _load_trades(self, account_id: str, ts_code: Optional[str]) -> List[Trade]:
        """预加载账户成交 + 订单方向 + 费用明细，避免 N+1 查询。"""
        filters = [Order.account_id == account_id]
        if ts_code:
            filters.append(Trade.ts_code == ts_code)
        query = (
            select(Trade)
            .join(Order, Trade.order_id == Order.order_id)
            .options(joinedload(Trade.order), selectinload(Trade.fees))
            .where(and_(*filters))
            .order_by(Trade.trade_time.asc(), Trade.created_at.asc())
        )
        result = await self.session.execute(query)
        return list(result.scalars().all())

    @staticmethod
    def _time_key(trade: Trade):
        return trade.trade_time or trade.created_at or datetime.min

    @staticmethod
    def _trade_fees(trade: Trade) -> Decimal:
        """单笔成交的总费用 = 佣金 + 印花税 + 过户费等（TradeFee 明细汇总）。

        优先用 Trade 表汇总字段 commission/tax，再叠加 TradeFee 里的过户费/其他，
        避免漏记过户费（Trade.commission/tax 仅含佣金与印花税）。
        """
        total = Decimal(str(trade.commission or 0)) + Decimal(str(trade.tax or 0))
        for fee in (trade.fees or []):
            if fee.fee_type not in ("commission", "tax", "stamp_duty"):
                total += Decimal(str(fee.fee_amount or 0))
        return total

    def _fifo_match(self, ts_code: str, trades: List[Trade]):
        """对单只股票的成交做 FIFO 配对。

        买入入队，卖出从队头消费。返回 (closed, open_pos, realized)。
        """
        buy_queue: List[Dict[str, Any]] = []  # 元素含 volume 会被就地修改
        closed: List[Dict[str, Any]] = []
        total_realized = Decimal("0")

        for trade in trades:
            direction = trade.order.direction if trade.order else "buy"
            price = Decimal(str(trade.price)) if trade.price else Decimal("0")
            volume = int(trade.volume or 0)
            fees = self._trade_fees(trade)

            if direction == "buy":
                buy_queue.append({
                    "trade_id": trade.trade_id,
                    "order_id": trade.order_id,
                    "time": self._time_key(trade),
                    "price": price,
                    "volume": volume,
                    "fees_per_share": (fees / Decimal(volume)) if volume > 0 else Decimal("0"),
                })
                continue

            # 卖出：从队头消费
            sell_fee_per_share = (fees / Decimal(volume)) if volume > 0 else Decimal("0")
            remaining = volume
            matched: List[Dict[str, Any]] = []
            sell_realized = Decimal("0")

            while remaining > 0 and buy_queue:
                buy = buy_queue[0]
                match_vol = min(remaining, buy["volume"])
                buy_fee_allocated = buy["fees_per_share"] * Decimal(match_vol)
                pnl = (price - buy["price"]) * Decimal(match_vol) - sell_fee_per_share * Decimal(match_vol) - buy_fee_allocated
                holding_days = (self._time_key(trade).date() - buy["time"].date()).days

                matched.append({
                    "buy_trade_id": buy["trade_id"],
                    "buy_order_id": buy["order_id"],
                    "buy_time": buy["time"].isoformat() if hasattr(buy["time"], "isoformat") else str(buy["time"]),
                    "buy_price": float(buy["price"]),
                    "matched_volume": match_vol,
                    "buy_fees_allocated": float(buy_fee_allocated),
                    "holding_days": holding_days,
                    "realized_pnl": float(pnl),
                })
                sell_realized += pnl
                remaining -= match_vol
                buy["volume"] -= match_vol
                if buy["volume"] <= 0:
                    buy_queue.pop(0)

            closed.append({
                "sell_trade_id": trade.trade_id,
                "sell_order_id": trade.order_id,
                "sell_time": self._time_key(trade).isoformat() if hasattr(self._time_key(trade), "isoformat") else str(self._time_key(trade)),
                "sell_price": float(price),
                "sell_volume": volume,
                "sell_fees": float(fees),
                "matched_buys": matched,
                "total_realized_pnl": float(sell_realized),
            })
            total_realized += sell_realized

        # 未平仓持仓
        open_buys = [{
            "buy_trade_id": b["trade_id"],
            "buy_order_id": b["order_id"],
            "buy_time": b["time"].isoformat() if hasattr(b["time"], "isoformat") else str(b["time"]),
            "buy_price": float(b["price"]),
            "remaining_volume": b["volume"],
        } for b in buy_queue if b["volume"] > 0]

        remaining_volume = sum(b["volume"] for b in buy_queue if b["volume"] > 0)
        # 加权平均成本
        total_cost = sum(b["price"] * Decimal(b["volume"]) for b in buy_queue if b["volume"] > 0)
        cost_price = (total_cost / Decimal(remaining_volume)) if remaining_volume > 0 else Decimal("0")

        open_pos = {
            "remaining_volume": remaining_volume,
            "cost_price": float(cost_price),
            "buys": open_buys,
        }

        return closed, open_pos, total_realized
