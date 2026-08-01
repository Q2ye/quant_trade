# -*- coding: utf-8 -*-
"""
交易记录服务 — 手动成交录入核心业务逻辑

负责将一个已成交的交易（用户在券商端手动完成）原子写入系统：
  Order(已成交) → Trade → TradeFee → Position(更新) → Account(更新) → Signal(回写)

所有操作在一个数据库事务内完成，确保数据一致性。
"""
import logging
import uuid
from datetime import datetime, timezone
from decimal import Decimal
from typing import Dict, List, Optional, Tuple

from sqlalchemy.ext.asyncio import AsyncSession

from modules.trade.utils.cost_calculator import CostCalculator
from shared.database.models.business_models import (
    Account, Order, Position, Signal, Trade, TradeFee,
)
from shared.database.repositories.account.asset.account_repo import AccountRepository
from shared.database.repositories.strategy.signal.signal_repo import SignalRepository
from shared.database.repositories.trading.order.order_repo import OrderRepository
from shared.database.repositories.trading.order.trade_repo import TradeRepository
from shared.database.repositories.trading.position.position_repo import PositionRepository
from shared.database.repositories.trading.support.trade_fee_repo import TradeFeeRepository

logger = logging.getLogger(__name__)


class TradeRecordResult:
    """成交录入结果"""

    def __init__(self, order: Order, trade: Trade, fees: List[TradeFee],
                 position: Position, account: Account):
        self.order = order
        self.trade = trade
        self.fees = fees
        self.position = position
        self.account = account

    def to_dict(self) -> Dict:
        return {
            "order_id": self.order.order_id,
            "trade_id": self.trade.trade_id,
            "ts_code": self.order.ts_code,
            "direction": self.order.direction,
            "price": float(self.trade.price),
            "volume": self.trade.volume,
            "total_fees": sum(float(f.fee_amount) for f in self.fees),
            "fees": [
                {"fee_type": f.fee_type, "fee_amount": float(f.fee_amount)}
                for f in self.fees
            ],
            "position": {
                "ts_code": self.position.ts_code,
                "volume": self.position.volume,
                "cost_price": float(self.position.cost_price),
                "pnl": float(self.position.pnl) if self.position.pnl else 0.0,
            },
            "account": {
                "total_balance": float(self.account.total_balance),
                "available_balance": float(self.account.available_balance),
                "market_value": float(self.account.market_value),
            },
        }


class TradeRecordService:
    """
    手动成交录入服务

    职责：编排多个 Repository 完成一笔已成交交易的原子写入。
    这是一个无状态服务，不持有事件引擎引用，被 TradeHandler 调用。
    """

    # A股费率常量
    COMMISSION_RATE = Decimal("0.0003")  # 佣金 0.03%
    MIN_COMMISSION = Decimal("5.00")     # 最低佣金 5 元
    STAMP_DUTY_RATE = Decimal("0.001")   # 印花税 0.1%（仅卖出）
    TRANSFER_FEE_RATE = Decimal("0.00002")  # 过户费 0.002%

    def __init__(self, session: AsyncSession):
        self._session = session
        self._order_repo = OrderRepository(session)
        self._trade_repo = TradeRepository(session)
        self._fee_repo = TradeFeeRepository(session)
        self._position_repo = PositionRepository(session)
        self._account_repo = AccountRepository(session)
        self._signal_repo = SignalRepository(session)
        self._cost_calc = CostCalculator()

    # ==================== 核心方法：单笔成交录入 ====================

    async def record_filled_trade(
        self,
        user_id: str,
        ts_code: str,
        direction: str,
        price: Decimal,
        quantity: int,
        trade_date: datetime,
        signal_id: Optional[str] = None,
        strategy_id: Optional[str] = None,
        user_fees: Optional[Dict[str, Decimal]] = None,
    ) -> TradeRecordResult:
        """
        录入一笔已成交的交易。

        在一个事务内完成：
        1. 获取/校验账户
        2. 创建 Order (status=filled)
        3. 创建 Trade
        4. 创建 TradeFee（多条）
        5. 更新 Position（成本、数量）
        6. 更新 Account（资金、市值）
        7. 回写 Signal（如果有 signal_id）

        Args:
            user_id: 用户ID
            ts_code: 股票代码
            direction: buy / sell
            price: 实际成交价
            quantity: 成交数量
            trade_date: 成交日期
            signal_id: 关联信号ID（可选）
            strategy_id: 关联策略ID（可选）
            user_fees: 用户手动填的费用 {'commission': 4.71, 'stamp_duty': 0, 'transfer_fee': 0.31}

        Returns:
            TradeRecordResult

        Raises:
            ValueError: 参数校验失败
        """
        # ---- 参数校验 ----
        if direction not in ("buy", "sell"):
            raise ValueError(f"无效的交易方向: {direction}，必须为 buy 或 sell")
        if quantity <= 0:
            raise ValueError("成交数量必须大于 0")
        if price <= 0:
            raise ValueError("成交价格必须大于 0")

        # ---- 1. 获取账户 ----
        accounts = await self._account_repo.get_many_by_user_id(user_id)
        if not accounts:
            raise ValueError("用户没有可用账户，请先创建账户")
        account = accounts[0]

        # ---- 2. 计算费用 ----
        fees = self._calculate_fees(direction, price, quantity, ts_code, user_fees)

        # 所有写入在一个事务内完成，确保数据一致性
        # 使用 begin_nested 兼容外部已有事务（如 FastAPI 依赖注入的 session 已通过查询隐式开启事务）
        async with self._session.begin_nested():
            # ---- 3. 创建 Order (已成交) ----
            order_id = uuid.uuid4().hex[:32]
            now = datetime.now(timezone.utc)
            order_data = {
                "order_id": order_id,
                "user_id": user_id,
                "account_id": account.id,
                "strategy_id": strategy_id,
                "signal_id": signal_id,
                "ts_code": ts_code,
                "order_type": "limit",
                "direction": direction,
                "price": price,
                "volume": quantity,
                "filled_volume": quantity,
                "filled_amount": price * quantity,
                "avg_price": price,
                "status": "filled",
                "submitted_at": trade_date,
                "filled_at": trade_date,
            }
            order = await self._order_repo.create(order_data)

            # ---- 4. 创建 Trade ----
            trade_id = uuid.uuid4().hex[:32]
            total_commission = sum(
                f[1] for f in fees if f[0] == "commission"
            )
            total_stamp = sum(
                f[1] for f in fees if f[0] in ("stamp_duty", "tax")
            )
            trade_data = {
                "trade_id": trade_id,
                "order_id": order_id,
                "ts_code": ts_code,
                "price": price,
                "volume": quantity,
                "trade_time": trade_date,
                "commission": total_commission,
                "tax": total_stamp,
            }
            trade = await self._trade_repo.create(trade_data)

            # ---- 5. 创建 TradeFee（多条明细） ----
            fee_records = []
            for fee_type, fee_amount in fees:
                fee_record = await self._fee_repo.create({
                    "trade_id": trade_id,
                    "fee_type": fee_type,
                    "fee_amount": fee_amount,
                    "calculated_at": now,
                })
                fee_records.append(fee_record)

            # ---- 6. 更新 Position ----
            position = await self._upsert_position(
                user_id, account.id, ts_code, direction, price, quantity,
                strategy_id=strategy_id,
            )

            # ---- 7. 更新 Account 余额 ----
            total_fee_amount = sum(f[1] for f in fees)
            trade_amount = price * quantity
            if direction == "buy":
                cash_change = -(trade_amount + total_fee_amount)
            else:
                cash_change = trade_amount - total_fee_amount

            updated_account = await self._update_account_balance(
                account, cash_change, price, quantity, direction
            )

            # ---- 8. 回写 Signal ----
            if signal_id:
                await self._signal_repo.update(signal_id, {
                    "signal_status": "executed",
                    "order_id": order_id,
                })

        logger.info(
            f"手动成交录入成功: user={user_id}, {direction} {ts_code} "
            f"@{price} x{quantity}, order={order_id}, trade={trade_id}"
        )

        return TradeRecordResult(
            order=order, trade=trade, fees=fee_records,
            position=position, account=updated_account,
        )

    # ==================== 辅助方法 ====================

    def _calculate_fees(
        self,
        direction: str,
        price: Decimal,
        quantity: int,
        ts_code: str,
        user_fees: Optional[Dict[str, Decimal]] = None,
    ) -> List[Tuple[str, Decimal]]:
        """
        计算交易费用。

        优先使用用户手动填的费用；若未填，则按 A 股标准费率自动计算。
        """
        # 如果用户提供了完整费用，直接使用
        if user_fees and any(v > 0 for v in user_fees.values()):
            fees = []
            for fee_type in ("commission", "stamp_duty", "transfer_fee"):
                amount = user_fees.get(fee_type, Decimal("0"))
                if amount > 0:
                    fees.append((fee_type, amount))
            return fees

        # 自动计算
        trade_amount = price * quantity
        fees = []

        # 佣金：0.03%，最低 5 元
        commission = max(trade_amount * self.COMMISSION_RATE, self.MIN_COMMISSION)
        fees.append(("commission", commission))

        # 印花税：仅卖出 0.1%
        if direction == "sell":
            stamp = trade_amount * self.STAMP_DUTY_RATE
            fees.append(("stamp_duty", stamp))

        # 过户费：0.002%，仅沪市
        if ts_code.startswith("6"):
            transfer = max(trade_amount * self.TRANSFER_FEE_RATE, Decimal("1.00"))
            fees.append(("transfer_fee", transfer))

        return fees

    async def _upsert_position(
        self,
        user_id: str,
        account_id: str,
        ts_code: str,
        direction: str,
        price: Decimal,
        quantity: int,
        strategy_id: Optional[str] = None,
    ) -> Position:
        """创建或更新持仓（加权平均成本）。

        持仓按 (account_id, ts_code, strategy_id) 维度隔离，故查找/新建/返回
        均须带 strategy_id，避免误更新其他策略的同票持仓。
        """
        position = await self._position_repo.get_user_position_by_strategy(
            user_id=user_id, account_id=account_id, ts_code=ts_code,
            strategy_id=strategy_id,
        )

        now = datetime.now(timezone.utc)

        if position is None:
            if direction == "sell":
                raise ValueError(
                    f"没有 {ts_code} 的持仓，无法卖出。请先买入或录入买入成交记录"
                )
            # 新建持仓
            position_data = {
                "user_id": user_id,
                "account_id": account_id,
                "strategy_id": strategy_id,
                "ts_code": ts_code,
                "volume": quantity,
                "available_volume": quantity,
                "frozen_volume": 0,
                "cost_price": price,
                "market_value": price * quantity,
                "last_price": price,
                "pnl": 0,
                "pnl_rate": 0,
                "last_update": now,
            }
            return await self._position_repo.create(position_data)

        # 更新持仓
        old_volume = position.volume or 0
        old_cost = Decimal(str(position.cost_price)) if position.cost_price else Decimal("0")

        if direction == "buy":
            new_volume = old_volume + quantity
            # 加权平均成本
            if new_volume > 0:
                new_cost = (old_cost * old_volume + price * quantity) / new_volume
            else:
                new_cost = price
        else:
            new_volume = old_volume - quantity
            new_cost = old_cost  # 卖出不变成本

        if new_volume < 0:
            raise ValueError(
                f"卖出数量超过持仓: {ts_code} 持仓 {old_volume}，尝试卖出 {quantity}"
            )

        # PnL 用最新成交价作为市价估值（手动记账场景下成交价即已知最新价）
        new_market_value = price * new_volume
        new_pnl = (price - new_cost) * new_volume if new_volume > 0 else Decimal("0")
        new_pnl_rate = (new_pnl / (new_cost * new_volume)) if new_volume > 0 and new_cost > 0 else Decimal("0")

        await self._position_repo.update(str(position.id), {
            "volume": new_volume,
            "available_volume": new_volume,
            "frozen_volume": 0,
            "cost_price": new_cost,
            "market_value": new_market_value,
            "last_price": price,
            "pnl": new_pnl,
            "pnl_rate": new_pnl_rate,
            "last_update": now,
        })

        # 重新查询返回最新数据
        return await self._position_repo.get_user_position_by_strategy(
            user_id=user_id, account_id=account_id, ts_code=ts_code,
            strategy_id=strategy_id,
        )

    async def _update_account_balance(
        self,
        account: Account,
        cash_change: Decimal,
        price: Decimal,
        quantity: int,
        direction: str,
    ) -> Account:
        """更新账户余额和市值"""
        old_balance = Decimal(str(account.total_balance)) if account.total_balance else Decimal("0")
        old_available = Decimal(str(account.available_balance)) if account.available_balance else Decimal("0")
        old_market_value = Decimal(str(account.market_value)) if account.market_value else Decimal("0")

        new_balance = old_balance + cash_change
        new_available = old_available + cash_change

        # 更新市值（买入增加，卖出减少）
        position_value_change = price * quantity
        if direction == "buy":
            new_market_value = old_market_value + position_value_change
        else:
            new_market_value = max(old_market_value - position_value_change, Decimal("0"))

        update_data = {
            "total_balance": new_balance,
            "available_balance": new_available,
            "market_value": new_market_value,
            "last_trade_date": datetime.now(timezone.utc).date(),
        }

        await self._account_repo.update(str(account.id), update_data)

        # 更新 account 对象属性后返回，避免多账户场景下查回错误账户
        account.total_balance = new_balance
        account.available_balance = new_available
        account.market_value = new_market_value
        return account
