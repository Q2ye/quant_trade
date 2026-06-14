# -*- coding: utf-8 -*-
"""
BacktestBroker — 虚拟券商

模拟回测环境下的订单执行和账户管理。
参照: Backtrader BackBroker + VN.PY BacktestingEngine

模拟链路:
TradingSignal → Order → (次日开盘价成交) → Trade → Position → EquityCurve

A 股规则:
- T+1 制度：当日买入次日可卖
- 涨跌停限制：主板 ±10%，科创板 ±20%，ST ±5%
- 费用：佣金 ≥ 5 元/笔，印花税 0.1%(仅卖出)，过户费 0.002%
- 最小交易单位：100 股（1 手）

v1.0: 初始实现
"""
import logging
from copy import deepcopy
from dataclasses import dataclass, field
from datetime import date, datetime
from decimal import Decimal
from typing import Dict, List, Optional, Any

import pandas as pd

from core.engines.base.engine_base import EngineBase, EngineConfigEntity
from core.engines.types.entities import BarData
from core.engines.types.enums import EngineType

logger = logging.getLogger(__name__)


# ============================================================
# 内部数据类
# ============================================================

@dataclass
class BrokerOrder:
    """内部订单对象"""
    order_id: str
    ts_code: str
    direction: str  # LONG / SHORT
    price: float
    quantity: int
    order_type: str  # market / limit
    status: str  # pending / filled / cancelled
    create_date: date
    fill_date: Optional[date] = None
    fill_price: Optional[float] = None
    commission: float = 0.0
    stamp_tax: float = 0.0
    transfer_fee: float = 0.0


@dataclass
class BrokerPosition:
    """内部持仓对象"""
    ts_code: str
    quantity: int
    available_quantity: int  # T+1: 当日买入部分为 0
    avg_cost: float
    current_price: float = 0.0
    market_value: float = 0.0
    pnl: float = 0.0
    pnl_rate: float = 0.0


@dataclass
class AccountSnapshot:
    """每日账户快照"""
    trade_date: date
    total_assets: float
    available_cash: float
    frozen_cash: float
    market_value: float
    positions_value: float
    daily_pnl: float
    cumulative_return: float
    max_drawdown: float = 0.0


# ============================================================
# BacktestBroker 配置
# ============================================================

@dataclass
class BacktestBrokerConfig:
    """回测券商配置"""
    initial_capital: float = 1_000_000
    commission_rate: float = 0.0003   # 佣金 万分之三
    min_commission: float = 5.0        # 最低佣金 5 元
    stamp_tax: float = 0.001           # 印花税 千分之一（仅卖出）
    transfer_fee_rate: float = 0.00002 # 过户费 十万分之二
    slippage: float = 0.001            # 滑点 0.1%
    t_plus_1: bool = True              # T+1 制度
    price_limit: bool = True           # 涨跌停限制
    limit_up_down: float = 0.10        # 默认涨跌停幅度（主板）
    lot_size: int = 100                # 1 手 = 100 股


# ============================================================
# BacktestBroker
# ============================================================

class BacktestBroker(EngineBase):
    """
    虚拟券商 — 模拟回测环境下的订单执行和账户管理

    参照:
    - Backtrader BackBroker: 订单队列 → 成交 → 持仓 → 账户更新
    - VN.PY BacktestingEngine: 逐日结算 + 滑点 + 佣金
    """

    def __init__(
        self,
        config: BacktestBrokerConfig = None,
        event_engine=None,
    ):
        """
        Args:
            config: 券商配置
            event_engine: 事件引擎（可选）
        """
        super().__init__(
            EngineConfigEntity(
                name="BacktestBroker",
                engine_type="backtest_broker",
            ),
            event_engine=event_engine,
        )

        self.config = config or BacktestBrokerConfig()

        # 账户状态
        self.initial_capital: float = self.config.initial_capital
        self.cash: float = self.config.initial_capital
        self.frozen_cash: float = 0.0

        # 持仓: {ts_code: BrokerPosition}
        self.positions: Dict[str, BrokerPosition] = {}

        # 订单: {order_id: BrokerOrder}
        self.orders: Dict[str, BrokerOrder] = {}
        self.pending_orders: List[BrokerOrder] = []  # T+1 挂单队列

        # 历史记录
        self.trade_history: List[Dict[str, Any]] = []
        self.snapshots: List[AccountSnapshot] = []
        self._equity_curve: pd.DataFrame = None

        # 上一交易日收盘价缓存（用于涨跌停判断）
        self._prev_close: Dict[str, float] = {}

        # 科创板/ST 识别
        self._star_market_stocks: set = set()   # 688xxx
        self._st_stocks: set = set()            # ST / *ST

        self._trade_date: Optional[date] = None

    # ---- 订单处理 ----

    def submit_order(
        self,
        ts_code: str,
        direction: str,
        price: float,
        quantity: int,
        order_type: str = "market",
    ) -> BrokerOrder:
        """
        接收策略信号，创建订单（T+1 挂单）

        Args:
            ts_code: 股票代码
            direction: LONG / SHORT / CLOSE_LONG / CLOSE_SHORT
            price: 委托价格
            quantity: 委托数量（股）
            order_type: market / limit

        Returns:
            BrokerOrder
        """
        # 标准化方向
        if direction in ("CLOSE_LONG", "CLOSE_SHORT"):
            direction = "SHORT" if "SHORT" in direction else "LONG"

        # 手数取整
        quantity = (quantity // self.config.lot_size) * self.config.lot_size
        if quantity <= 0:
            logger.warning(f"订单数量为 0，跳过: {ts_code}")
            return None

        # 检查资金（买入时）
        if direction == "LONG":
            estimated_cost = price * quantity * (1 + self.config.commission_rate)
            if estimated_cost > self.cash:
                max_qty = int(
                    self.cash / (price * (1 + self.config.commission_rate))
                    // self.config.lot_size
                    * self.config.lot_size
                )
                if max_qty <= 0:
                    logger.warning(
                        f"资金不足: 需要 {estimated_cost:.2f}, "
                        f"可用 {self.cash:.2f}, 跳过 {ts_code}"
                    )
                    return None
                quantity = max_qty
                logger.info(f"资金不足，调整数量: {ts_code} → {quantity} 股")

        # 冻结资金
        estimated_cost = price * quantity
        if direction == "LONG":
            self.frozen_cash += estimated_cost
            self.cash -= estimated_cost

        order_id = f"order_{len(self.orders) + 1:06d}"
        order = BrokerOrder(
            order_id=order_id,
            ts_code=ts_code,
            direction=direction,
            price=price,
            quantity=quantity,
            order_type=order_type,
            status="pending",
            create_date=self._trade_date or date.today(),
        )

        self.orders[order_id] = order
        self.pending_orders.append(order)

        logger.debug(
            f"订单创建: {order_id} {direction} {ts_code} "
            f"{quantity}股 @ {price:.2f}"
        )
        return order

    def match_orders(
        self,
        trade_date: date,
        bars: Dict[str, BarData],
    ) -> List[Dict[str, Any]]:
        """
        撮合昨日挂单 — 用当日 Bar 的 open price 成交

        规则:
        1. 市价单以次日 open 成交
        2. 限价单检查是否触及价格
        3. 涨停买不进、跌停卖不出
        4. T+1 制度（当日买入次日可卖）

        Args:
            trade_date: 当前交易日
            bars: 当日所有股票 BarData，key 为 ts_code

        Returns:
            成交记录列表
        """
        self._trade_date = trade_date
        trades = []

        # 更新昨日收盘价缓存
        for ts_code, bar in bars.items():
            self._prev_close[ts_code] = bar.close

        # 撮合昨日挂单
        remaining_orders = []
        for order in self.pending_orders:
            bar = bars.get(order.ts_code)
            if bar is None:
                # 停牌或数据缺失，保留到下一交易日
                remaining_orders.append(order)
                continue

            # 涨跌停检查
            if self.config.price_limit:
                if not self._can_trade(order.ts_code, order.direction, bar.open):
                    logger.debug(
                        f"涨跌停限制，无法成交: {order.ts_code} "
                        f"{order.direction} @ {bar.open:.2f}"
                    )
                    remaining_orders.append(order)
                    continue

            # 成交价 = 开盘价（考虑滑点）
            fill_price = bar.open
            if self.config.slippage > 0:
                if order.direction == "LONG":
                    fill_price *= (1 + self.config.slippage)  # 买入滑点向上
                else:
                    fill_price *= (1 - self.config.slippage)  # 卖出滑点向下

            # 限价单检查
            if order.order_type == "limit":
                if order.direction == "LONG" and fill_price > order.price:
                    remaining_orders.append(order)
                    continue
                if order.direction == "SHORT" and fill_price < order.price:
                    remaining_orders.append(order)
                    continue

            # 成交
            fill_amount = fill_price * order.quantity

            # 计算费用
            commission = max(
                fill_amount * self.config.commission_rate,
                self.config.min_commission,
            )
            stamp_tax = (
                fill_amount * self.config.stamp_tax
                if order.direction == "SHORT"
                else 0.0
            )
            transfer_fee = fill_amount * self.config.transfer_fee_rate

            # 更新订单
            order.status = "filled"
            order.fill_date = trade_date
            order.fill_price = fill_price
            order.commission = commission
            order.stamp_tax = stamp_tax
            order.transfer_fee = transfer_fee

            # 更新资金
            total_cost = fill_amount + commission + stamp_tax + transfer_fee
            if order.direction == "LONG":
                # 解冻预扣资金，按实际成交价扣款
                estimated = order.price * order.quantity
                self.frozen_cash -= estimated
                self.cash += estimated
                self.cash -= total_cost
            else:
                # 卖出，释放冻结
                estimated = order.price * order.quantity
                if self.frozen_cash >= estimated:
                    self.frozen_cash -= estimated
                self.cash += (fill_amount - commission - stamp_tax - transfer_fee)

            # 更新持仓
            self._update_position(order, fill_price, trade_date)

            # 记录成交
            trade_record = {
                "trade_id": f"trade_{len(self.trade_history) + 1:06d}",
                "order_id": order.order_id,
                "ts_code": order.ts_code,
                "direction": order.direction,
                "price": fill_price,
                "quantity": order.quantity,
                "amount": fill_amount,
                "commission": commission,
                "stamp_tax": stamp_tax,
                "transfer_fee": transfer_fee,
                "trade_date": trade_date,
            }
            trades.append(trade_record)
            self.trade_history.append(trade_record)

            logger.debug(
                f"成交: {order.ts_code} {order.direction} "
                f"{order.quantity}股 @ {fill_price:.2f} "
                f"费用={commission + stamp_tax + transfer_fee:.2f}"
            )

        self.pending_orders = remaining_orders
        return trades

    def mark_to_market(self, bars: Dict[str, BarData]):
        """
        逐日盯市 — 用当日收盘价更新持仓市值和浮动盈亏

        Args:
            bars: 当日所有股票 BarData
        """
        total_market_value = 0.0
        total_pnl = 0.0

        for ts_code, bar in bars.items():
            if ts_code in self.positions:
                pos = self.positions[ts_code]
                pos.current_price = bar.close
                pos.market_value = pos.quantity * bar.close
                pos.pnl = (bar.close - pos.avg_cost) * pos.quantity
                pos.pnl_rate = (
                    (bar.close - pos.avg_cost) / pos.avg_cost
                    if pos.avg_cost > 0
                    else 0.0
                )
                total_market_value += pos.market_value
                total_pnl += pos.pnl

        # 冻结资金也产生持仓市值（提交买入订单但尚未成交的）
        total_assets = self.cash + self.frozen_cash + total_market_value

        # 记录快照
        if self._trade_date and self.initial_capital > 0:
            cumulative_return = (
                (total_assets - self.initial_capital) / self.initial_capital
            )
        else:
            cumulative_return = 0.0

        # 计算最大回撤
        if self.snapshots:
            prev_peak = max(s.total_assets for s in self.snapshots)
        else:
            prev_peak = self.initial_capital
        current_drawdown = (
            (prev_peak - total_assets) / prev_peak if prev_peak > 0 else 0.0
        )
        max_drawdown = current_drawdown
        if self.snapshots:
            max_drawdown = max(
                max(s.max_drawdown for s in self.snapshots),
                current_drawdown,
            )

        snapshot = AccountSnapshot(
            trade_date=self._trade_date,
            total_assets=total_assets,
            available_cash=self.cash,
            frozen_cash=self.frozen_cash,
            market_value=total_market_value,
            positions_value=total_market_value,
            daily_pnl=total_pnl,
            cumulative_return=cumulative_return,
            max_drawdown=max_drawdown,
        )
        self.snapshots.append(snapshot)

    # ---- 查询接口 ----

    def get_equity_curve(self) -> pd.DataFrame:
        """
        返回完整净值曲线 DataFrame

        Returns:
            DataFrame 列: trade_date, total_assets, cumulative_return, max_drawdown
        """
        if not self.snapshots:
            return pd.DataFrame(
                columns=["trade_date", "total_assets", "cumulative_return", "max_drawdown"]
            )

        df = pd.DataFrame([
            {
                "trade_date": s.trade_date,
                "total_assets": s.total_assets,
                "available_cash": s.available_cash,
                "market_value": s.market_value,
                "daily_pnl": s.daily_pnl,
                "cumulative_return": s.cumulative_return,
                "max_drawdown": s.max_drawdown,
            }
            for s in self.snapshots
        ])
        return df

    def get_trade_list(self) -> List[Dict[str, Any]]:
        """返回所有成交记录"""
        return deepcopy(self.trade_history)

    def get_position_list(self) -> List[Dict[str, Any]]:
        """返回当前持仓列表"""
        return [
            {
                "ts_code": pos.ts_code,
                "quantity": pos.quantity,
                "available_quantity": pos.available_quantity,
                "avg_cost": pos.avg_cost,
                "current_price": pos.current_price,
                "market_value": pos.market_value,
                "pnl": pos.pnl,
                "pnl_rate": pos.pnl_rate,
            }
            for pos in self.positions.values()
        ]

    def get_account_snapshot(self) -> Dict[str, Any]:
        """返回当前账户状态"""
        total_mv = sum(p.market_value for p in self.positions.values())
        total_assets = self.cash + self.frozen_cash + total_mv
        return {
            "initial_capital": self.initial_capital,
            "cash": self.cash,
            "frozen_cash": self.frozen_cash,
            "market_value": total_mv,
            "total_assets": total_assets,
            "total_return": (
                (total_assets - self.initial_capital) / self.initial_capital
                if self.initial_capital > 0
                else 0.0
            ),
            "trade_date": self._trade_date,
            "position_count": len(self.positions),
            "pending_order_count": len(self.pending_orders),
            "total_trades": len(self.trade_history),
        }

    # ---- 生命周期管理 ----

    def reset(self, initial_capital: float = None):
        """
        重置账户到初始状态（用于新的回测运行）

        Args:
            initial_capital: 新的初始资金，None 则使用配置值
        """
        if initial_capital is not None:
            self.initial_capital = initial_capital
            self.config.initial_capital = initial_capital

        self.cash = self.initial_capital
        self.frozen_cash = 0.0
        self.positions.clear()
        self.orders.clear()
        self.pending_orders.clear()
        self.trade_history.clear()
        self.snapshots.clear()
        self._equity_curve = None
        self._prev_close.clear()
        self._trade_date = None
        logger.info(f"券商已重置: 初始资金={self.initial_capital:,.0f}")

    # ---- 私有方法 ----

    def _update_position(
        self,
        order: BrokerOrder,
        fill_price: float,
        trade_date: date,
    ):
        """根据成交订单更新持仓"""
        ts_code = order.ts_code

        if order.direction == "LONG":
            if ts_code in self.positions:
                pos = self.positions[ts_code]
                total_cost = pos.avg_cost * pos.quantity + fill_price * order.quantity
                pos.quantity += order.quantity
                pos.avg_cost = total_cost / pos.quantity if pos.quantity > 0 else 0.0
                # T+1: 当日买入部分不可卖
                if self.config.t_plus_1:
                    pos.available_quantity = pos.quantity - order.quantity
                else:
                    pos.available_quantity = pos.quantity
            else:
                self.positions[ts_code] = BrokerPosition(
                    ts_code=ts_code,
                    quantity=order.quantity,
                    available_quantity=(
                        0 if self.config.t_plus_1 else order.quantity
                    ),
                    avg_cost=fill_price,
                )

        elif order.direction == "SHORT":
            if ts_code in self.positions:
                pos = self.positions[ts_code]
                pos.quantity -= order.quantity
                if pos.quantity <= 0:
                    del self.positions[ts_code]
                else:
                    pos.available_quantity = min(
                        pos.available_quantity, pos.quantity
                    )

    def _can_trade(
        self,
        ts_code: str,
        direction: str,
        price: float,
    ) -> bool:
        """
        检查是否可以在涨跌停限制下成交

        Args:
            ts_code: 股票代码
            direction: LONG / SHORT
            price: 当日开盘价

        Returns:
            True 如果可以成交
        """
        prev_close = self._prev_close.get(ts_code)
        if prev_close is None or prev_close <= 0:
            return True  # 无前收价，不限制

        # 确定涨跌停幅度
        if ts_code in self._star_market_stocks or ts_code.startswith("688"):
            limit_pct = 0.20
        elif ts_code in self._st_stocks or "ST" in ts_code:
            limit_pct = 0.05
        else:
            limit_pct = self.config.limit_up_down

        limit_up = prev_close * (1 + limit_pct)
        limit_down = prev_close * (1 - limit_pct)

        if direction == "LONG" and price >= limit_up:
            return False  # 涨停买不进
        if direction in ("SHORT", "CLOSE_LONG", "CLOSE_SHORT") and price <= limit_down:
            return False  # 跌停卖不出

        return True

    # ---- EngineBase 生命周期 ----

    async def _on_initialize(self) -> None:
        logger.info(
            f"BacktestBroker 初始化完成: "
            f"初始资金={self.initial_capital:,.0f}, "
            f"佣金={self.config.commission_rate:.4%}, "
            f"印花税={self.config.stamp_tax:.3%}"
        )

    async def _on_start(self) -> None:
        logger.info("BacktestBroker 已启动")

    async def _on_stop(self) -> None:
        logger.info(
            f"BacktestBroker 已停止: "
            f"总成交 {len(self.trade_history)} 笔, "
            f"最终资产 {self.cash + sum(p.market_value for p in self.positions.values()):,.2f}"
        )
