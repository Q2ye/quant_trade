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
from typing import Dict, List, NamedTuple, Optional, Tuple

from sqlalchemy.ext.asyncio import AsyncSession

from modules.trade.utils.cost_calculator import calculate_fee
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
                 position: Position, account: Account,
                 strategy_name: Optional[str] = None):
        self.order = order
        self.trade = trade
        self.fees = fees
        self.position = position
        self.account = account
        self.strategy_name = strategy_name

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
            # 记账去向（2026-09-17 新增）：录单会落到哪个账户/策略维度。
            # 前端据此在成功提示里反显，避免"记了但不知道记到哪"。
            "account_id": str(self.account.id),
            "account_name": getattr(self.account, "account_name", None),
            "strategy_id": self.order.strategy_id,
            "strategy_name": self.strategy_name,
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


class DuplicateTradeRecordError(ValueError):
    """信号重复录单：同一 signal_id 已有成交订单/记录。

    继承 ValueError 以兼容既有 `except ValueError` 分支；
    调用方（handlers）单独捕获并映射为 HTTP 409。
    """


class AmbiguousHoldingError(ValueError):
    """记账去向歧义：同一标的在多个账户/策略维度下都有持仓，无法自动定位。

    此时**必须拒绝**而不是任选一条 —— 手工记账场景下选错账户会造成账实不符，
    且事后无从察觉。detail 中携带候选清单（账户名/策略名/持仓量），
    由用户从持仓列表指定，或在弹窗中手工填 strategy_id。
    调用方（handlers）单独捕获并映射为 HTTP 409。
    """


class AccountStrategyTarget(NamedTuple):
    """一笔手动成交的记账去向：账户 + 策略维度。"""
    account: Account
    strategy_id: Optional[str]
    strategy_name: Optional[str]


class TradeRecordService:
    """
    手动成交录入服务

    职责：编排多个 Repository 完成一笔已成交交易的原子写入。
    这是一个无状态服务，不持有事件引擎引用，被 TradeHandler 调用。
    """

    def __init__(self, session: AsyncSession):
        self._session = session
        self._order_repo = OrderRepository(session)
        self._trade_repo = TradeRepository(session)
        self._fee_repo = TradeFeeRepository(session)
        self._position_repo = PositionRepository(session)
        self._account_repo = AccountRepository(session)
        self._signal_repo = SignalRepository(session)

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

        # ---- 幂等保护（修复 2026-09-12）----
        # 同一信号可以承载多笔合法订单（如「买 1000 → 分两笔卖 500+500」），
        # 因此不能用「一信号一单」判定重复。改用累计数量护栏：
        # 该信号该方向已录数量 + 本次数量 超过信号计划数量 → 判定为重复/超额录入。
        # 前端仅靠 submitting 标志防抖，刷新页面即可绕过；无护栏时重复提交会让
        # _upsert_position 累加两次数量、_update_account_balance 扣两次现金。
        if signal_id:
            from sqlalchemy import text as _text
            _sig = (await self._session.execute(
                _text("SELECT quantity FROM signals WHERE id = :sid"),
                {"sid": signal_id},
            )).fetchone()
            _planned = int(_sig[0]) if (_sig and _sig[0]) else 0
            if _planned > 0:
                _recorded = (await self._session.execute(
                    _text("SELECT COALESCE(SUM(volume), 0) FROM orders "
                          "WHERE signal_id = :sid AND direction = :dir"),
                    {"sid": signal_id, "dir": direction},
                )).scalar() or 0
                if int(_recorded) + quantity > _planned:
                    raise DuplicateTradeRecordError(
                        f"信号 {signal_id} 的 {direction} 已录 {int(_recorded)} 股 / "
                        f"计划 {_planned} 股，本次 {quantity} 股将超额，已拒绝"
                        f"（疑似重复提交；若确为分笔成交请核对信号数量）"
                    )
            else:
                logger.warning(
                    "信号 %s 未记录计划数量，跳过录单幂等护栏", signal_id
                )

        # ---- 1. 解析记账去向（账户 + 策略维度）----
        # 2026-09-17 重写：仅「传了 strategy_id 才查策略绑定账户」不够 —— 手动录入
        # 通常不传 strategy_id，此时回落到 accounts[0]，而 accounts[0] 是
        # **created_at 最新**的账户（不是持仓所在账户）。实测事故：512400.SH 持仓在
        # 银河实盘账户(84d81a14)/熊市防守-01-实盘(cebe247d)，但 9-12 新建的
        # 「跨市场避险」成了 accounts[0] → 卖出报「没有 512400.SH 的持仓」。
        # 现改为按 ts_code 定位持仓（买卖一致），歧义时拒绝而非任选。
        target = await self._resolve_account_and_strategy(
            user_id=user_id, ts_code=ts_code, strategy_id=strategy_id,
        )
        account = target.account
        strategy_id = target.strategy_id

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
            # 修复 2026-08（C14）：卖出前查持仓成本，用于信号盈亏回填
            _sell_cost = None
            if direction == "sell" and signal_id:
                _pos_old = await self._position_repo.get_user_position_by_strategy(
                    user_id=user_id, account_id=account.id, ts_code=ts_code,
                    strategy_id=strategy_id,
                )
                _sell_cost = getattr(_pos_old, "cost_price", None) if _pos_old else None
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
                account, cash_change, price, quantity, direction, total_fee_amount
            )

            # ---- 8. 回写 Signal ----
            if signal_id:
                # 修复 2026-08（C14）：is_executed + 卖出录单回填盈亏（数据资产闭环）
                _sig_upd = {
                    "signal_status": "executed",
                    "order_id": order_id,
                    "is_executed": True,
                }
                if direction == "sell" and _sell_cost is not None:
                    _pnl = (price - Decimal(str(_sell_cost))) * Decimal(quantity)
                    _sig_upd["pnl_outcome"] = float(_pnl)
                await self._signal_repo.update(signal_id, _sig_upd)

        logger.info(
            f"手动成交录入成功: user={user_id}, {direction} {ts_code} "
            f"@{price} x{quantity}, order={order_id}, trade={trade_id}, "
            f"记账去向=账户[{getattr(account, 'account_name', None)}]{account.id} "
            f"策略[{target.strategy_name}]{strategy_id or '无(手工持仓)'}"
        )

        return TradeRecordResult(
            order=order, trade=trade, fees=fee_records,
            position=position, account=updated_account,
            strategy_name=target.strategy_name,
        )

    # ==================== 记账去向解析 ====================

    async def _resolve_account_and_strategy (
        self,
        user_id: str,
        ts_code: str,
        strategy_id: Optional[str] = None,
    ) -> AccountStrategyTarget:
        """
        解析一笔手动成交的记账去向（账户 + 策略维度）。

        优先级：
          A. 传了 strategy_id → 策略绑定账户优先，回退用户默认账户（既有语义，不变）
          B. 未传 strategy_id → **按 ts_code 定位持仓所在账户/策略**（2026-09-17 新增）
             B1 恰好 1 笔持仓 → 采用该持仓的 (account_id, strategy_id)
             B2 ≥2 笔持仓    → 抛 AmbiguousHoldingError（拒绝任选，防止账实不符）
             B3 0 笔持仓     → 回退用户默认账户 + strategy_id=None（保持既有语义）
             B4 B1 命中但持仓账户不可用（已软删/关闭）→ 回退默认账户并告警

        买入与卖出走同一套解析（买卖一致），避免同一只票在加仓与卖出时
        被拆到不同账户/策略维度。

        Raises:
            ValueError: 用户没有可用账户
            AmbiguousHoldingError: 多笔持仓无法自动定位
        """
        accounts = await self._account_repo.get_many_by_user_id(user_id)
        if not accounts:
            raise ValueError("用户没有可用账户，请先创建账户")
        account_by_id = {str(a.id): a for a in accounts}
        default_account = accounts[0]

        # ---- 路径 A：显式指定策略 ----
        if strategy_id:
            account = default_account
            try:
                from sqlalchemy import text as _text
                _row = (await self._session.execute(
                    _text("SELECT account_id FROM strategies WHERE id = :sid"),
                    {"sid": strategy_id})).fetchone()
                if _row and _row[0]:
                    _bound = account_by_id.get(str(_row[0]))
                    if _bound:
                        account = _bound
                    else:
                        logger.warning(
                            "策略 %s 绑定的账户 %s 不在可用账户列表（已删除/关闭），"
                            "回退默认账户 %s", strategy_id, _row[0], default_account.id,
                        )
            except Exception as _e:
                logger.warning(f"按策略绑定账户解析失败，回退用户默认账户: {_e}")
            return AccountStrategyTarget(
                account, strategy_id, await self._strategy_name(strategy_id),
            )

        # ---- 路径 B：按 ts_code 定位持仓 ----
        positions = await self._position_repo.get_user_positions_by_code(
            user_id=user_id, ts_code=ts_code, min_volume=1,
        )

        if len(positions) == 1:
            pos = positions[0]
            account = account_by_id.get(str(pos.account_id))
            if account is None:
                # B4：持仓所在账户已软删/关闭。不静默改写去向，回退默认账户并告警，
                # 让"卖出报没有持仓"这类显式失败替代"静默记到别的账户"。
                logger.warning(
                    "持仓 %s 所在账户 %s 不可用（已删除/关闭），回退默认账户 %s",
                    ts_code, pos.account_id, default_account.id,
                )
                account = default_account
            _st_name = await self._strategy_name(pos.strategy_id)
            logger.info(
                "录单定位: user=%s %s → 账户[%s]%s 策略[%s]%s（按持仓定位）",
                user_id, ts_code,
                getattr(account, "account_name", None), account.id,
                _st_name, pos.strategy_id or "无(手工持仓)",
            )
            return AccountStrategyTarget(account, pos.strategy_id, _st_name)

        if len(positions) >= 2:
            raise AmbiguousHoldingError(
                await self._describe_holding_candidates(ts_code, positions, account_by_id)
            )

        # B3：无持仓 → 保持既有语义
        logger.info(
            "录单定位: user=%s %s 无持仓记录，回落默认账户 %s",
            user_id, ts_code, default_account.id,
        )
        return AccountStrategyTarget(default_account, None, None)

    async def _describe_holding_candidates (
        self,
        ts_code: str,
        positions: List[Position],
        account_by_id: Dict[str, Account],
    ) -> str:
        """构造歧义时的候选清单文本（账户名/策略名/持仓量），供前端直接展示。"""
        _st_names = await self._strategy_names([p.strategy_id for p in positions])
        _parts = []
        for p in positions:
            _acc = account_by_id.get(str(p.account_id))
            _acc_name = (
                getattr(_acc, "account_name", None) or str(p.account_id)
            ) if _acc else f"账户{str(p.account_id)[:8]}…(不可用)"
            if p.strategy_id:
                _st = _st_names.get(str(p.strategy_id)) or str(p.strategy_id)
            else:
                _st = "手工持仓(无策略)"
            _parts.append(f"{_acc_name} / {_st}（{int(p.volume or 0)}股）")
        return (
            f"{ts_code} 存在 {len(positions)} 笔持仓，无法自动确定记账去向："
            + "；".join(_parts)
            + "。请从持仓列表点击「录入成交」指定，或在弹窗中手工填写「关联策略」ID。"
        )

    async def _strategy_names (
        self, strategy_ids: List[Optional[str]]
    ) -> Dict[str, str]:
        """批量取策略名（一次查询，避免 N+1）；失败时降级为不含名称。"""
        _ids = [str(s) for s in strategy_ids if s]
        if not _ids:
            return {}
        try:
            from sqlalchemy import text as _text
            _rows = (await self._session.execute(
                _text("SELECT id, name FROM strategies WHERE id = ANY(:ids)"),
                {"ids": _ids},
            )).fetchall()
            return {str(r[0]): r[1] for r in _rows}
        except Exception as _e:
            logger.warning(f"批量查询策略名失败，反显将回退为策略ID: {_e}")
            return {}

    async def _strategy_name (self, strategy_id: Optional[str]) -> Optional[str]:
        """取单个策略名（用于反显）。"""
        if not strategy_id:
            return None
        return (await self._strategy_names([str(strategy_id)])).get(str(strategy_id))

    # ==================== 辅助方法 ====================

    def _calculate_fees(
        self,
        direction: str,
        price: Decimal,
        quantity: int,
        ts_code: str,
        user_fees: Optional[Dict[str, Optional[Decimal]]] = None,
    ) -> List[Tuple[str, Decimal]]:
        """
        计算交易费用。

        以统一费率入口 `calculate_fee`（万一免五、印花税 0.05%、过户费万0.1 沪深双边）
        计算基准费用；用户手动填写的费用项覆盖对应项，未填写（None/缺省）的项
        保留自动计算值，避免"只填佣金漏算印花税/过户费"。
        """
        base = calculate_fee(
            direction=direction,
            price=float(price),
            quantity=quantity,
            ts_code=ts_code,
        )
        fee_map: Dict[str, Decimal] = {
            "commission": Decimal(str(base["commission"])),
            "stamp_duty": Decimal(str(base["stamp_duty"])),
            "transfer_fee": Decimal(str(base["transfer_fee"])),
        }

        if user_fees:
            for fee_type in ("commission", "stamp_duty", "transfer_fee"):
                user_val = user_fees.get(fee_type)
                if user_val is not None:
                    fee_map[fee_type] = Decimal(str(user_val))

        return [(fee_type, amount) for fee_type, amount in fee_map.items() if amount > 0]

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
        fee_amount: Decimal,
    ) -> Account:
        """更新账户余额和市值。

        总资产 = 现金 + 持仓市值。买卖是现金↔持仓的内部转换，不改变总资产，
        总资产只随费用减少（修复：原实现把总资产当现金扣，导致账户数据失真）。
        市值按成交价近似，日终结算会按收盘价重估校正。
        """
        old_available = Decimal(str(account.available_balance)) if account.available_balance else Decimal("0")
        old_market_value = Decimal(str(account.market_value)) if account.market_value else Decimal("0")
        old_balance = Decimal(str(account.total_balance)) if account.total_balance else Decimal("0")

        new_available = old_available + cash_change
        new_balance = old_balance - fee_amount

        # 市值（买入增加，卖出减少）
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
