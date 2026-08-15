# -*- coding: utf-8 -*-
"""
quant_server/modules/account/calculators/pnl_calculator.py
盈亏计算器 - 计算账户盈亏相关指标

职责：
1. 计算持仓盈亏（已实现/未实现）
2. 计算交易盈亏（逐笔匹配，FIFO）
3. 计算日度盈亏摘要
4. 盈亏分析（胜率、夏普比率、索提诺比率等）
5. 计算账户整体绩效指标
"""

import logging
from datetime import date, datetime
from decimal import Decimal
from enum import Enum
from typing import List, Optional, Dict, Any

import numpy as np
from sqlalchemy import select, and_
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import joinedload

from core import BusinessException
from modules.account.models import (
    PositionPnL,
    DailyPnLSummary,
    PnLAnalysis,
)
from shared.database.models.business_models import Trade, Order
from shared.database.repositories.account.asset.account_performance_repo import (
    AccountDailyPerformanceRepository,
)
from shared.database.repositories.account.asset.account_repo import AccountRepository
from shared.database.repositories.trading.order.order_repo import OrderRepository
from shared.database.repositories.trading.order.trade_repo import TradeRepository
from shared.database.repositories.trading.position.position_repo import PositionRepository

logger = logging.getLogger(__name__)


class PnLType(Enum):
    """盈亏类型枚举"""
    REALIZED = "realized"
    UNREALIZED = "unrealized"
    TOTAL = "total"


class PnLCalculator:
    """盈亏计算器"""

    def __init__(self, session: AsyncSession):
        self.session = session
        self.position_repo = PositionRepository(session)
        self.trade_repo = TradeRepository(session)
        self.order_repo = OrderRepository(session)
        self.account_repo = AccountRepository(session)
        self.performance_repo = AccountDailyPerformanceRepository(session)

    # ==================== 持仓盈亏 ====================

    async def calculate_position_pnl(self, account_id: str) -> List[PositionPnL]:
        """计算账户每只持仓的盈亏明细"""
        positions = await self.position_repo.get_account_positions(account_id)
        pnl_list: List[PositionPnL] = []

        for position in positions:
            if position.volume <= 0:
                continue

            cost_basis = Decimal(str(position.cost_price)) * int(position.volume)

            if position.last_price:
                market_value = Decimal(str(position.volume)) * Decimal(str(position.last_price))
                unrealized_pnl = market_value - cost_basis
                unrealized_pnl_rate = (
                    unrealized_pnl / cost_basis if cost_basis != 0 else Decimal("0")
                )
            else:
                market_value = Decimal("0")
                unrealized_pnl = Decimal("0")
                unrealized_pnl_rate = Decimal("0")

            realized_pnl = await self._calculate_realized_pnl(account_id, position.ts_code)

            pnl_list.append(
                PositionPnL(
                    ts_code=position.ts_code,
                    position_id=position.id,
                    volume=int(position.volume),
                    cost_price=Decimal(str(position.cost_price)),
                    last_price=Decimal(str(position.last_price)) if position.last_price else None,
                    market_value=market_value,
                    cost_basis=cost_basis,
                    unrealized_pnl=Decimal(str(position.pnl)) if position.pnl else unrealized_pnl,
                    unrealized_pnl_rate=(
                        Decimal(str(position.pnl_rate)) if position.pnl_rate else unrealized_pnl_rate
                    ),
                    realized_pnl=realized_pnl,
                    total_pnl=(
                        (Decimal(str(position.pnl)) + realized_pnl)
                        if position.pnl
                        else (unrealized_pnl + realized_pnl)
                    ),
                    last_update=position.last_update,
                )
            )

        return pnl_list

    async def _calculate_realized_pnl(self, account_id: str, ts_code: str) -> Decimal:
        """FIFO 匹配计算某证券的已实现盈亏"""
        trades = await self._get_trades_with_order_for_account(account_id, ts_code=ts_code)

        buy_queue: List[Dict[str, Any]] = []
        sell_queue: List[Dict[str, Any]] = []
        for t in trades:
            entry = {"price": Decimal(str(t.price)), "volume": t.volume, "time": t.trade_time}
            if t.order.direction == "buy":
                buy_queue.append(entry)
            else:
                sell_queue.append(entry)

        buy_queue.sort(key=lambda x: x["time"])
        sell_queue.sort(key=lambda x: x["time"])

        realized_pnl = Decimal("0")
        for sell in sell_queue:
            remaining = sell["volume"]
            sell_price = sell["price"]
            while remaining > 0 and buy_queue:
                buy = buy_queue[0]
                match_vol = min(remaining, buy["volume"])
                realized_pnl += Decimal(str(match_vol)) * (sell_price - buy["price"])
                remaining -= match_vol
                buy["volume"] -= match_vol
                if buy["volume"] == 0:
                    buy_queue.pop(0)
        return realized_pnl

    # ==================== 日度盈亏 ====================

    async def calculate_daily_pnl(self, account_id: str, trade_date: date) -> DailyPnLSummary:
        """计算账户日度盈亏摘要"""
        try:
            daily_trades = await self.trade_repo.get_trades_by_account_and_date(
                account_id, trade_date
            )

            # 预加载订单方向，避免异步 lazy load
            direction_map: Dict[str, str] = {}
            order_ids = list({t.order_id for t in daily_trades if getattr(t, "order_id", None)})
            if order_ids:
                from sqlalchemy import select
                from shared.database.models.business_models import Order
                result = await self.session.execute(
                    select(Order.order_id, Order.direction).where(Order.order_id.in_(order_ids))
                )
                direction_map = {row[0]: row[1] for row in result.all()}

            trade_pnl = Decimal("0")
            trade_volume = 0
            trade_amount = Decimal("0")
            commission = Decimal("0")
            tax = Decimal("0")

            for trade in daily_trades:
                trade_volume += trade.volume
                trade_amount += Decimal(str(trade.volume)) * Decimal(str(trade.price))
                commission += Decimal(str(trade.commission))
                tax += Decimal(str(trade.tax))

                direction = direction_map.get(trade.order_id, "buy")
                if direction == "sell":
                    cost_price = await self._get_cost_price(account_id, trade.ts_code, trade_date)
                    if cost_price:
                        trade_pnl += Decimal(str(trade.volume)) * (
                                Decimal(str(trade.price)) - cost_price
                        )

            positions = await self.position_repo.get_account_positions(account_id)
            position_pnl_change = Decimal("0")
            # 修复 2026-08（C4）：MTM 增量口径——今日市值 - 昨日市值（不含历史浮盈）。
            # 旧实现用 (最新价 - 成本价) 实为累计浮盈，污染日收益序列。
            _codes = [p.ts_code for p in positions if p.volume and p.volume > 0]
            if _codes:
                from sqlalchemy import text as _text
                _rows = (await self.session.execute(_text(
                    "SELECT sd.ts_code, sd.close AS today_close, "
                    "(SELECT y.close FROM stock_daily y "
                    "  WHERE y.ts_code = sd.ts_code AND y.trade_date < sd.trade_date "
                    "  ORDER BY y.trade_date DESC LIMIT 1) AS prev_close "
                    "FROM stock_daily sd "
                    "WHERE sd.ts_code = ANY(:codes) AND sd.trade_date = :td"
                ), {"codes": _codes, "td": trade_date})).fetchall()
                _price_map = {r.ts_code: (r.today_close, r.prev_close) for r in _rows}
                for pos in positions:
                    if pos.volume and pos.volume > 0 and pos.ts_code in _price_map:
                        _today_c, _prev_c = _price_map[pos.ts_code]
                        if _prev_c is not None:
                            position_pnl_change += Decimal(str(pos.volume)) * (
                                Decimal(str(_today_c)) - Decimal(str(_prev_c))
                            )

            return DailyPnLSummary(
                trade_date=trade_date,
                trade_pnl=trade_pnl,
                position_pnl_change=position_pnl_change,
                total_pnl=trade_pnl + position_pnl_change,
                trade_volume=trade_volume,
                trade_amount=trade_amount,
                commission=commission,
                tax=tax,
            )
        except BusinessException:
            logger.exception("计算日度盈亏失败")
            return DailyPnLSummary(
                trade_date=trade_date,
                trade_pnl=Decimal("0"),
                position_pnl_change=Decimal("0"),
                total_pnl=Decimal("0"),
                trade_volume=0,
                trade_amount=Decimal("0"),
                commission=Decimal("0"),
                tax=Decimal("0"),
            )

    async def _get_cost_price(
            self, account_id: str, ts_code: str, _as_of_date: Optional[date] = None
    ) -> Optional[Decimal]:
        """获取某证券的当前持仓成本价"""
        positions = await self.position_repo.get_account_positions(account_id)
        for pos in positions:
            if pos.ts_code == ts_code and pos.volume > 0:
                return Decimal(str(pos.cost_price))
        return None

    # ==================== 盈亏分析 ====================

    async def calculate_pnl_analysis(
            self, account_id: str, start_date: date, end_date: date
    ) -> PnLAnalysis:
        """计算账户在指定区间的盈亏分析"""
        trades = await self._get_trades_with_order_for_account(
            account_id, start_date=start_date, end_date=end_date
        )

        pnl_values: List[float] = []
        total_pnl = Decimal("0")
        winning_trades = 0
        total_sell_trades = 0

        for trade in trades:
            pnl = await self._calculate_trade_pnl(trade)
            total_pnl += pnl
            pnl_values.append(float(pnl))
            if trade.order.direction == "sell":
                total_sell_trades += 1
                if pnl > 0:
                    winning_trades += 1

        win_rate = Decimal(str(winning_trades / total_sell_trades)) if total_sell_trades > 0 else Decimal("0")

        positive = [p for p in pnl_values if p > 0]
        negative = [p for p in pnl_values if p < 0]
        avg_win = float(np.mean(positive)) if positive else 0.0
        avg_loss = float(np.mean(negative)) if negative else 0.0
        profit_ratio = abs(avg_win / avg_loss) if avg_loss != 0 else 0.0

        return PnLAnalysis(
            start_date=start_date,
            end_date=end_date,
            total_trades=len(trades),
            win_rate=win_rate,
            total_pnl=total_pnl,
            avg_pnl_per_trade=(
                Decimal(str(total_pnl / len(trades))) if trades else Decimal("0")
            ),
            profit_ratio=Decimal(str(profit_ratio)),
            max_winning_trade=Decimal(str(max(pnl_values))) if pnl_values else Decimal("0"),
            max_losing_trade=Decimal(str(min(pnl_values))) if pnl_values else Decimal("0"),
            sharpe_ratio=self._calculate_sharpe_ratio(pnl_values),
            sortino_ratio=self._calculate_sortino_ratio(pnl_values),
        )

    async def _calculate_trade_pnl(self, trade: Trade) -> Decimal:
        """计算单笔成交的盈亏（卖出时计算，买入为0）"""
        if trade.order.direction == "buy":
            return Decimal("0")
        cost_price = await self._get_cost_price(
            trade.order.account_id, trade.ts_code, trade.trade_time.date()
        )
        if cost_price:
            pnl = Decimal(str(trade.volume)) * (Decimal(str(trade.price)) - cost_price)
            pnl -= Decimal(str(trade.commission))
            pnl -= Decimal(str(trade.tax))
            return pnl
        return Decimal("0")

    # ==================== 绩效指标 ====================

    async def calculate_account_performance(self, account_id: str) -> Dict[str, Any]:
        """计算账户综合绩效指标"""
        try:
            account = await self.account_repo.get(account_id)
            if not account:
                raise ValueError(f"账户不存在: {account_id}")

            # 总收益率
            total_return = 0.0
            if account.initial_balance and float(account.initial_balance) > 0:
                total_return = float(
                    (Decimal(str(account.total_balance)) - Decimal(str(account.initial_balance)))
                    / Decimal(str(account.initial_balance))
                )

            # 从 AccountDailyPerformance 获取历史绩效数据
            records = await self.performance_repo.get_user_performance(account.user_id)
            daily_returns: List[float] = [float(r.daily_return) for r in records if r.daily_return]

            sharpe = self._calculate_sharpe_ratio(daily_returns)
            max_dd = self._calculate_max_drawdown(daily_returns)

            # 胜率（卖出交易中盈利的比例）
            trades = await self._get_trades_with_order_for_account(account_id)
            sell_count = 0
            win_count = 0
            for t in trades:
                if t.order.direction == "sell":
                    sell_count += 1
                    pnl = await self._calculate_trade_pnl(t)
                    if pnl > 0:
                        win_count += 1
            win_rate = win_count / sell_count if sell_count > 0 else 0.0

            # 年化收益率（修复 2026-08（C4）：252 交易日基准，替代 365 自然日）
            annualized_return = total_return
            if records and len(records) > 1:
                _n = len(records)  # 绩效记录数 = 交易日数
                if _n > 1 and total_return > -1:
                    annualized_return = float((1 + total_return) ** (252 / _n) - 1)

            return {
                "total_return": round(total_return, 6),
                "annualized_return": round(annualized_return, 6),
                "sharpe_ratio": float(sharpe),
                "max_drawdown": round(max_dd, 6),
                "win_rate": round(win_rate, 6),
                "total_trades": len(trades),
                "total_sell_trades": sell_count,
                "winning_trades": win_count,
            }
        except BusinessException:
            logger.exception("计算账户绩效失败")
            return {
                "total_return": 0.0,
                "annualized_return": 0.0,
                "sharpe_ratio": 0.0,
                "max_drawdown": 0.0,
                "win_rate": 0.0,
                "total_trades": 0,
                "total_sell_trades": 0,
                "winning_trades": 0,
            }

    # ==================== 风险指标 ====================

    @staticmethod
    def _calculate_sharpe_ratio(
            returns: List[float], risk_free_rate: float = 0.02
    ) -> Decimal:
        """年化夏普比率"""
        if not returns or len(returns) < 2:
            return Decimal("0")
        arr = np.array(returns, dtype=np.float64)
        excess = arr - risk_free_rate / 252
        std = float(np.std(excess, ddof=1))  # 修复 2026-08（C4）：ddof=1 样本标准差
        if std == 0:
            return Decimal("0")
        sharpe = float(np.mean(excess)) / std * np.sqrt(252)
        return Decimal(str(round(sharpe, 6)))

    @staticmethod
    def _calculate_sortino_ratio(
            returns: List[float], risk_free_rate: float = 0.02
    ) -> Decimal:
        """年化索提诺比率（仅考虑下行波动）"""
        if not returns or len(returns) < 2:
            return Decimal("0")
        arr = np.array(returns, dtype=np.float64)
        excess = arr - risk_free_rate / 252
        downside = excess[excess < 0]
        if len(downside) == 0:
            return Decimal("0")
        std = float(np.std(downside))
        if std == 0:
            return Decimal("0")
        sortino = float(np.mean(excess)) / std * np.sqrt(252)
        return Decimal(str(round(sortino, 6)))

    @staticmethod
    def _calculate_max_drawdown(returns: List[float]) -> float:
        """从日收益率序列计算最大回撤"""
        if not returns or len(returns) < 2:
            return 0.0
        cum = np.cumprod(np.array(returns, dtype=np.float64) + 1)
        peak = np.maximum.accumulate(cum)
        drawdown = (cum - peak) / peak
        return float(np.min(drawdown))

    # ==================== 内部辅助 ====================

    async def _get_trades_with_order_for_account(
            self,
            account_id: str,
            ts_code: Optional[str] = None,
            start_date: Optional[date] = None,
            end_date: Optional[date] = None,
    ) -> List[Trade]:
        """查询账户的成交记录并 eager-load Order 关系"""
        filters: List[Any] = [Order.account_id == account_id]
        if ts_code:
            filters.append(Trade.ts_code == ts_code)
        if start_date:
            filters.append(Trade.trade_time >= datetime.combine(start_date, datetime.min.time()))
        if end_date:
            filters.append(
                Trade.trade_time <= datetime.combine(end_date, datetime.max.time())
            )

        query = (
            select(Trade)
            .join(Order, Trade.order_id == Order.order_id)
            .options(joinedload(Trade.order))
            .where(and_(*filters))
            .order_by(Trade.trade_time.asc())
        )
        result = await self.session.execute(query)
        return list(result.scalars().all())
