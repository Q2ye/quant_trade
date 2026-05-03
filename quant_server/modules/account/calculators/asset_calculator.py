# quant_server/modules/account/calculators/asset_calculator.py
"""
资产计算器 - 计算账户资产相关指标

职责：
1. 计算账户总资产
2. 计算持仓市值
3. 计算现金余额
4. 计算资产变化率
"""

from datetime import date, datetime
from decimal import Decimal
from typing import Dict, List, Optional

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from core import BusinessException
from modules.account.models import (
    AssetBreakdown,
    AssetHistory,
)
from shared.database.models.business_models import AccountTransaction
from shared.database.repositories.account.asset.account_repo import AccountRepository
from shared.database.repositories.trading.position.position_repo import PositionRepository
from shared.database.repositories.trading.position.position_snapshot_repo import PositionSnapshotRepository


class AssetCalculator:
    """资产计算器"""

    def __init__(self, session: AsyncSession):
        """
        初始化资产计算器

        Args:
            session: 数据库会话
        """
        self.session = session
        self.account_repo = AccountRepository(session)
        self.position_repo = PositionRepository(session)
        self.snapshot_repo = PositionSnapshotRepository(session)

    async def calculate_total_asset(self, account_id: str, as_of_date: Optional[date] = None) -> Decimal:
        """
        计算账户总资产

        Args:
            account_id: 账户ID
            as_of_date: 截止日期，None表示当前

        Returns:
            Decimal: 总资产金额
        """
        account = await self.account_repo.get(account_id)
        if not account:
            raise ValueError(f"账户不存在: {account_id}")

        if as_of_date:
            # 历史计算：持仓市值来自持仓快照表
            historical_market_value = await self._get_historical_market_value(account_id, as_of_date)

            # 历史现金：从 account_transactions 找到距指定日期最近的流水余额
            historical_cash = await self._get_historical_cash(account_id, as_of_date)

            total_asset = historical_cash + historical_market_value
        else:
            # 当前计算：使用账户实时数据
            total_asset = account.total_balance

        return Decimal(str(total_asset))

    async def _get_historical_market_value(self, account_id: str, as_of_date: date) -> Decimal:
        """从持仓快照表获取历史日期的持仓总市值"""
        snapshots = await self.snapshot_repo.get_account_snapshot_by_date(account_id, as_of_date)
        if not snapshots:
            # 快照可能尚未生成，降级为 0（或从 positions 表估算）
            return Decimal("0")
        return Decimal(sum(Decimal(str(s.market_value or 0)) for s in snapshots))

    async def _get_historical_cash(self, account_id: str, as_of_date: date) -> Decimal:
        """从 account_transactions 表获取历史日期的现金余额"""
        # 查询距 as_of_date 之前最近的一条流水记录
        cutoff = datetime.combine(as_of_date, datetime.max.time())
        query = (
            select(AccountTransaction)
            .where(
                AccountTransaction.account_id == account_id,
                AccountTransaction.transaction_date <= cutoff,
            )
            .order_by(AccountTransaction.transaction_date.desc())
            .limit(1)
        )
        result = await self.session.execute(query)
        last_txn = result.scalar_one_or_none()

        if last_txn:
            return Decimal(str(last_txn.balance_after))

        # 如果没有历史流水，使用账户初始资金
        account = await self.account_repo.get(account_id)
        return Decimal(str(account.initial_balance)) if account else Decimal("0")

    async def calculate_market_value(self, account_id: str) -> Decimal:
        """
        计算持仓市值

        Args:
            account_id: 账户ID

        Returns:
            Decimal: 持仓市值
        """
        positions = await self.position_repo.get_account_positions(account_id)

        total_market_value = Decimal("0")
        for position in positions:
            if position.volume > 0 and position.last_price:
                position_value = Decimal(str(position.volume)) * Decimal(str(position.last_price))
                total_market_value += position_value

        return total_market_value

    async def calculate_cash_breakdown(self, account_id: str) -> Dict[str, Decimal]:
        """
        计算现金构成

        Args:
            account_id: 账户ID

        Returns:
            Dict: 现金构成详情
        """
        account = await self.account_repo.get(account_id)
        if not account:
            raise ValueError(f"账户不存在: {account_id}")

        return {
            "total_balance": Decimal(str(account.total_balance)),
            "available_balance": Decimal(str(account.available_balance)),
            "frozen_balance": Decimal(str(account.frozen_balance)),
            "margin_balance": Decimal(
                str(account.total_balance - account.available_balance - account.frozen_balance)
            ),
        }

    async def calculate_asset_allocation(self, account_id: str) -> List[AssetBreakdown]:
        """
        计算资产配置详情

        Args:
            account_id: 账户ID

        Returns:
            List[AssetBreakdown]: 资产配置列表
        """
        account = await self.account_repo.get(account_id)
        positions = await self.position_repo.get_account_positions(account_id)

        # 计算持仓市值
        position_values = []
        for position in positions:
            if position.volume > 0 and position.last_price:
                market_value = Decimal(str(position.volume)) * Decimal(str(position.last_price))
                position_values.append(
                    {
                        "ts_code": position.ts_code,
                        "market_value": market_value,
                        "weight": (
                            market_value / Decimal(str(account.total_balance))
                            if account.total_balance > 0
                            else Decimal("0")
                        ),
                    }
                )

        # 计算现金占比
        cash_value = Decimal(str(account.available_balance))
        cash_weight = (
            cash_value / Decimal(str(account.total_balance))
            if account.total_balance > 0
            else Decimal("0")
        )

        # 构建资产配置
        allocation = [
            AssetBreakdown(
                asset_type="cash",
                asset_name="现金",
                market_value=cash_value,
                weight=cash_weight,
                cost_basis=cash_value,
                pnl=Decimal("0"),
            )
        ]

        # 持仓部分
        for pos_value in position_values:
            position = next(p for p in positions if p.ts_code == pos_value["ts_code"])

            allocation.append(
                AssetBreakdown(
                    asset_type="stock",
                    asset_name=position.ts_code,
                    market_value=pos_value["market_value"],
                    weight=pos_value["weight"],
                    cost_basis=Decimal(str(position.cost_price)) * Decimal(str(position.volume)),
                    pnl=Decimal(str(position.pnl)),
                )
            )

        return allocation

    # ---- 静态工具方法 ----

    @staticmethod
    async def _resolve_user_id(session: AsyncSession, account_id: str) -> str:
        """将 account_id 解析为 user_id（account_daily_performance 表以 user_id 为维度）"""
        from shared.database.repositories.account.asset.account_repo import AccountRepository

        repo = AccountRepository(session)
        account = await repo.get(account_id)
        return account.user_id if account else account_id

    @staticmethod
    async def calculate_asset_history(
        _account_id: str,
        _start_date: date,
        _end_date: date,
    ) -> List[AssetHistory]:
        """
        计算资产历史

        从 AccountDailyPerformance 表查询每日绩效快照，重建资产曲线。
        account_daily_performance 表以 user_id 为维度，需先解析。

        Args:
            _account_id: 账户ID
            _start_date: 开始日期
            _end_date: 结束日期

        Returns:
            List[AssetHistory]: 资产历史记录
        """
        from shared.database.session import get_session_manager
        from sqlalchemy import text

        session_manager = get_session_manager()
        async with session_manager.get_session() as session:
            # 解析 account_id → user_id
            user_id = await AssetCalculator._resolve_user_id(session, _account_id)

            # 从每日绩效表获取快照
            try:
                result = await session.execute(
                    text(
                        # account_daily_performance 的列名是 cash / user_id（无 cumulative_pnl）
                        "SELECT trade_date, total_asset, cash, market_value, "
                        "daily_pnl, daily_return "
                        "FROM account_daily_performance "
                        "WHERE user_id = :uid AND trade_date BETWEEN :sd AND :ed "
                        "ORDER BY trade_date"
                    ),
                    {"uid": user_id, "sd": _start_date, "ed": _end_date},
                )
                rows = result.fetchall()
                if rows:
                    return [
                        AssetHistory(
                            trade_date=row.trade_date,
                            total_asset=Decimal(str(row.total_asset)),
                            cash=Decimal(str(row.cash)),
                            market_value=Decimal(str(row.market_value)),
                            daily_pnl=Decimal(str(row.daily_pnl or 0)),
                            daily_return=Decimal(str(row.daily_return or 0)),
                        )
                        for row in rows
                    ]
            except BusinessException:
                pass

            # 降级方案：从 trades 表重建
            try:
                result = await session.execute(
                    text(
                        "SELECT t.trade_time::date AS trade_date, "
                        "SUM(t.volume * t.price) AS trade_amount, "
                        "SUM(t.commission + COALESCE(t.tax, 0)) AS total_fee "
                        "FROM trades t "
                        "JOIN orders o ON t.order_id = o.order_id "
                        "WHERE o.account_id = :aid AND t.trade_time BETWEEN :sd AND :ed "
                        "GROUP BY t.trade_time::date ORDER BY trade_date"
                    ),
                    {"aid": _account_id, "sd": _start_date, "ed": _end_date},
                )
                rows = result.fetchall()
                if rows:
                    history = []
                    cumulative = Decimal("0")
                    for row in rows:
                        daily_pnl = Decimal(str(row.trade_amount or 0)) - Decimal(str(row.total_fee or 0))
                        cumulative += daily_pnl
                        history.append(
                            AssetHistory(
                                trade_date=row.trade_date,
                                total_asset=cumulative,
                                cash=cumulative,
                                market_value=Decimal("0"),
                                daily_pnl=daily_pnl,
                                cumulative_pnl=cumulative,
                                daily_return=Decimal("0"),
                            )
                        )
                    return history
            except BusinessException:
                pass

        return []

    @staticmethod
    async def calculate_asset_growth_rate(
        _account_id: str,
        _start_date: date,
        _end_date: date,
    ) -> Dict[str, Decimal]:
        """
        计算资产增长率

        基于资产历史快照计算总收益率、年化收益率和CAGR（复合年增长率）。

        Args:
            _account_id: 账户ID
            _start_date: 开始日期
            _end_date: 结束日期

        Returns:
            Dict: 增长率指标 {total_return, annualized_return, cagr}
        """
        from shared.database.session import get_session_manager
        from sqlalchemy import text

        session_manager = get_session_manager()
        async with session_manager.get_session() as session:
            # 解析 account_id → user_id
            user_id = await AssetCalculator._resolve_user_id(session, _account_id)

            try:
                # 获取区间 首尾两天的资产总额
                result = await session.execute(
                    text(
                        "SELECT total_asset FROM account_daily_performance "
                        "WHERE user_id = :uid AND trade_date IN (:sd, :ed) "
                        "ORDER BY trade_date LIMIT 2"
                    ),
                    {"uid": user_id, "sd": _start_date, "ed": _end_date},
                )
                rows = result.fetchall()
                if len(rows) < 2:
                    return {
                        "total_return": Decimal("0"),
                        "annualized_return": Decimal("0"),
                        "cagr": Decimal("0"),
                    }
                start_asset = Decimal(str(rows[0][0]))
                end_asset = Decimal(str(rows[1][0]))
            except BusinessException:
                return {
                    "total_return": Decimal("0"),
                    "annualized_return": Decimal("0"),
                    "cagr": Decimal("0"),
                }

        if start_asset <= 0:
            return {
                "total_return": Decimal("0"),
                "annualized_return": Decimal("0"),
                "cagr": Decimal("0"),
            }

        total_return = (end_asset - start_asset) / start_asset

        days_diff = (_end_date - _start_date).days
        if days_diff <= 0:
            return {
                "total_return": total_return,
                "annualized_return": Decimal("0"),
                "cagr": Decimal("0"),
            }

        years = Decimal(str(days_diff)) / Decimal("365")
        try:
            cagr = (Decimal("1") + total_return) ** (Decimal("1") / years) - Decimal("1")
        except (ValueError, ZeroDivisionError):
            cagr = Decimal("0")

        return {
            "total_return": total_return,
            "annualized_return": cagr,
            "cagr": cagr,
        }

    @staticmethod
    def _annualize_return(total_return: Decimal, start_date: date, end_date: date) -> Decimal:
        """
        年化收益率计算

        Args:
            total_return: 总收益率
            start_date: 开始日期
            end_date: 结束日期

        Returns:
            Decimal: 年化收益率
        """
        days_diff = (end_date - start_date).days
        years = Decimal(str(days_diff)) / Decimal("365")

        if years <= 0:
            return Decimal("0")

        try:
            annualized = (Decimal("1") + total_return) ** (Decimal("1") / years) - Decimal("1")
        except (ValueError, ZeroDivisionError):
            annualized = Decimal("0")

        return annualized
