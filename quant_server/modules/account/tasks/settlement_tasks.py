"""
账户结算任务模块
负责账户的日终、周末、月末结算处理
"""

import logging
from datetime import datetime, date, timedelta
from decimal import Decimal
from typing import Dict, List, Optional, Any

from sqlalchemy.ext.asyncio import AsyncSession

from core import BusinessException
from modules.account.calculators.asset_calculator import AssetCalculator
from modules.account.calculators.pnl_calculator import PnLCalculator
from modules.account.events.settlement_events import AccountSettlementCompletedEvent
from modules.account.services.account_service import AccountService
from modules.account.services.asset_service import AssetService
from shared.database.repositories.account.asset.account_repo import AccountRepository
from shared.database.repositories.trading.order.trade_repo import TradeRepository
from shared.database.repositories.trading.position.position_repo import PositionRepository

logger = logging.getLogger(__name__)


class SettlementTasks:
    """
    结算任务管理器
    负责调度和执行各类结算任务
    """

    def __init__(
            self,
            account_repo: AccountRepository,
            trade_repo: TradeRepository,
            position_repo: PositionRepository,
            event_engine: Any = None
    ):
        """
        初始化结算任务管理器

        Args:
            account_repo: 账户仓库
            trade_repo: 交易仓库
            position_repo: 持仓仓库
            event_engine: 事件引擎
        """
        self.account_repo = account_repo
        self.trade_repo = trade_repo
        self.position_repo = position_repo
        self.event_engine = event_engine

        # 初始化服务
        self.account_service = AccountService(db=account_repo.session)
        self.asset_service = AssetService(
            db=account_repo.session
        )

        # 初始化计算器
        self.pnl_calculator = PnLCalculator(session=account_repo.session)
        self.asset_calculator = AssetCalculator(session=account_repo.session)

    async def daily_settlement_task(self, trading_day: Optional[date] = None) -> Dict:
        """
        日终结算任务
        每日收盘后执行，计算当日盈亏、更新资产、生成对账单

        Args:
            trading_day: 交易日，默认使用当日

        Returns:
            Dict: 结算结果
        """
        if not trading_day:
            trading_day = datetime.now().date()

        logger.info(f"开始执行日终结算任务，交易日: {trading_day}")

        try:
            # 1. 获取当日所有账户
            accounts = await self.account_repo.get_all(status="active")

            results = {}
            for account in accounts:
                account_id = getattr(account, 'account_id', str(getattr(account, 'id', 'unknown')))
                logger.info(f"处理账户 {account_id} 的日终结算")

                try:
                    # 2. 计算当日盈亏
                    daily_pnl = await self._calculate_daily_pnl(account_id, trading_day)

                    # 3. 更新账户资产
                    updated_assets = await self._update_account_assets(
                        account_id,
                        daily_pnl,
                        trading_day
                    )

                    # 4. 更新持仓成本
                    updated_positions = await self._update_position_cost(account_id)

                    # 5. 生成日终对账单
                    statement = await self._generate_daily_statement(
                        account_id,
                        trading_day,
                        daily_pnl,
                        updated_assets
                    )

                    # 6. 记录结算结果
                    settlement_record = await self.account_repo.create_settlement_record({
                        'account_id': account_id,
                        'trading_day': trading_day,
                        'settlement_type': 'daily',
                        'pnl': float(daily_pnl['total_pnl']),
                        'assets_snapshot': updated_assets,
                        'statement_path': statement['file_path'],
                        'status': 'completed'
                    })

                    results[account_id] = {
                        'status': 'success',
                        'daily_pnl': daily_pnl,
                        'updated_assets': updated_assets,
                        'updated_positions': len(updated_positions),
                        'statement': statement,
                        'settlement_id': settlement_record.id
                    }

                    logger.info(f"账户 {account_id} 日终结算完成")

                except Exception as e:
                    logger.error(f"账户 {account_id} 日终结算失败: {str(e)}", exc_info=True)
                    results[account_id] = {
                        'status': 'failed',
                        'error': str(e)
                    }

            # 7. 发布结算完成事件
            if self.event_engine:
                total_accounts = len(results)
                successful_accounts = sum(1 for r in results.values() if r['status'] == 'success')
                failed_accounts = total_accounts - successful_accounts

                await self.event_engine.put(AccountSettlementCompletedEvent(
                    settlement_date=trading_day,
                    settlement_type='daily',
                    total_accounts=total_accounts,
                    successful_accounts=successful_accounts,
                    failed_accounts=failed_accounts,
                    settlement_statistics={},
                    duration_seconds=0
                ))

            logger.info(f"日终结算任务完成，共处理 {len(accounts)} 个账户")
            return {
                'task': 'daily_settlement',
                'trading_day': trading_day,
                'total_accounts': len(accounts),
                'results': results
            }

        except Exception as e:
            logger.error(f"日终结算任务执行失败: {str(e)}", exc_info=True)
            raise

    async def weekly_settlement_task(self, week_end_date: Optional[date] = None) -> Dict:
        """
        周末结算任务
        每周五收盘后执行，生成周度报告

        Args:
            week_end_date: 周结束日期，默认使用本周五

        Returns:
            Dict: 周结算结果
        """
        if not week_end_date:
            # 默认使用上周五
            today = datetime.now().date()
            week_end_date = today - timedelta(days=today.weekday() - 4)

        logger.info(f"开始执行周末结算任务，周结束日: {week_end_date}")

        try:
            # 获取本周所有交易日
            week_start_date = week_end_date - timedelta(days=4)

            # 获取所有账户
            accounts = await self.account_repo.get_all(status="active")

            results = {}
            for account in accounts:
                account_id = getattr(account, 'account_id', str(getattr(account, 'id', 'unknown')))

                try:
                    # 计算周度盈亏
                    weekly_pnl = await self._calculate_period_pnl(
                        account_id,
                        week_start_date,
                        week_end_date
                    )

                    # 生成周度报告
                    weekly_report = await self._generate_weekly_report(
                        account_id,
                        week_start_date,
                        week_end_date,
                        weekly_pnl
                    )

                    # 记录周结算
                    settlement_record = await self.account_repo.create_settlement_record({
                        'account_id': account_id,
                        'trading_day': week_end_date,
                        'settlement_type': 'weekly',
                        'pnl': float(weekly_pnl['total_pnl']),
                        'statement_path': weekly_report['file_path'],
                        'status': 'completed'
                    })

                    results[account_id] = {
                        'status': 'success',
                        'weekly_pnl': weekly_pnl,
                        'report': weekly_report,
                        'settlement_id': settlement_record.id
                    }

                except Exception as e:
                    logger.error(f"账户 {account_id} 周末结算失败: {str(e)}")
                    results[account_id] = {
                        'status': 'failed',
                        'error': str(e)
                    }

            logger.info(f"周末结算任务完成")
            return {
                'task': 'weekly_settlement',
                'week_end_date': week_end_date,
                'results': results
            }

        except Exception as e:
            logger.error(f"周末结算任务执行失败: {str(e)}")
            raise

    async def monthly_settlement_task(self, month_end_date: Optional[date] = None) -> Dict:
        """
        月末结算任务
        每月最后一个交易日执行，生成月度报告

        Args:
            month_end_date: 月结束日期

        Returns:
            Dict: 月结算结果
        """
        if not month_end_date:
            today = datetime.now().date()
            month_end_date = date(today.year, today.month, 1) - timedelta(days=1)

        logger.info(f"开始执行月末结算任务，月结束日: {month_end_date}")

        try:
            # 计算月初日期
            month_start_date = date(month_end_date.year, month_end_date.month, 1)

            accounts = await self.account_repo.get_all(status="active")

            results = {}
            for account in accounts:
                account_id = getattr(account, 'account_id', str(getattr(account, 'id', 'unknown')))

                try:
                    # 计算月度盈亏
                    monthly_pnl = await self._calculate_period_pnl(
                        account_id,
                        month_start_date,
                        month_end_date
                    )

                    # 生成月度报告
                    monthly_report = await self._generate_monthly_report(
                        account_id,
                        month_start_date,
                        month_end_date,
                        monthly_pnl
                    )

                    # 记录月结算
                    settlement_record = await self.account_repo.create_settlement_record({
                        'account_id': account_id,
                        'trading_day': month_end_date,
                        'settlement_type': 'monthly',
                        'pnl': float(monthly_pnl['total_pnl']),
                        'statement_path': monthly_report['file_path'],
                        'status': 'completed'
                    })

                    results[account_id] = {
                        'status': 'success',
                        'monthly_pnl': monthly_pnl,
                        'report': monthly_report,
                        'settlement_id': settlement_record.id
                    }

                except Exception as e:
                    logger.error(f"账户 {account_id} 月末结算失败: {str(e)}")
                    results[account_id] = {
                        'status': 'failed',
                        'error': str(e)
                    }

            logger.info(f"月末结算任务完成")
            return {
                'task': 'monthly_settlement',
                'month_end_date': month_end_date,
                'results': results
            }

        except Exception as e:
            logger.error(f"月末结算任务执行失败: {str(e)}")
            raise

    async def _calculate_daily_pnl(self, account_id: str, trading_day: date) -> Dict:
        """
        计算账户当日盈亏

        Args:
            account_id: 账户ID
            trading_day: 交易日

        Returns:
            Dict: 盈亏计算结果
        """
        daily_summary = await self.pnl_calculator.calculate_daily_pnl(account_id, trading_day)

        total_asset = Decimal("0")
        try:
            assets = await self.asset_service.get_account_assets(account_id)
            total_asset = assets.get("total_asset", Decimal("0")) if isinstance(assets, dict) else Decimal("0")
        except BusinessException:
            pass

        pnl_rate = float(daily_summary.total_pnl / total_asset) if total_asset and float(total_asset) != 0 else 0.0

        return {
            "total_pnl": float(daily_summary.total_pnl),
            "pnl_rate": pnl_rate,
            "detail": {
                "trade_pnl": float(daily_summary.trade_pnl),
                "position_pnl_change": float(daily_summary.position_pnl_change),
                "trade_volume": daily_summary.trade_volume,
                "trade_amount": float(daily_summary.trade_amount),
                "commission": float(daily_summary.commission),
                "tax": float(daily_summary.tax),
            },
        }

    async def _update_account_assets(
            self,
            account_id: str,
            daily_pnl: Dict,
            trading_day: date
    ) -> Dict:
        """
        更新账户资产

        Args:
            account_id: 账户ID
            daily_pnl: 当日盈亏
            trading_day: 交易日

        Returns:
            Dict: 更新后的资产快照
        """
        current_assets = await self.asset_service.get_account_assets(account_id)
        if not isinstance(current_assets, dict):
            current_assets = {}

        cash_balance = float(current_assets.get("available_cash", 0) or 0)
        frozen_cash = float(current_assets.get("frozen_cash", 0) or 0)
        market_value = float(current_assets.get("market_value", 0) or 0)
        total_asset = cash_balance + frozen_cash + market_value

        pnl_amount = float(daily_pnl.get("total_pnl", 0))
        cash_balance += pnl_amount
        total_asset += pnl_amount

        updated_assets = {
            "total_asset": total_asset,
            "cash_balance": cash_balance,
            "market_value": market_value,
            "available_cash": cash_balance,
            "frozen_cash": frozen_cash,
        }

        asset_snapshot = {
            "account_id": account_id,
            "trading_day": trading_day,
            "total_asset": total_asset,
            "cash_balance": cash_balance,
            "market_value": market_value,
            "available_cash": cash_balance,
            "frozen_cash": frozen_cash,
            "pnl": pnl_amount,
            "pnl_rate": float(daily_pnl.get("pnl_rate", 0)),
        }

        await self.account_repo.create_asset_snapshot(asset_snapshot)

        return updated_assets

    async def _update_position_cost(self, account_id: str) -> List:
        """
        更新持仓成本（均价法）

        买入时：新均价 = (旧数量×旧成本 + 买入量×买入价) / 新总量
        卖出时：只减数量，均价不变

        Args:
            account_id: 账户ID

        Returns:
            List: 更新的持仓列表
        """
        from sqlalchemy import select
        from shared.database.models.business_models import Order

        today = datetime.now().date()
        trades = await self.trade_repo.get_trades_by_account_and_date(account_id, today)

        if not trades:
            return []

        positions = await self.position_repo.get_account_positions(account_id)
        pos_map: Dict[str, Dict[str, float]] = {}
        for p in positions:
            pos_map[p.ts_code] = {
                "volume": float(p.volume or 0),
                "cost_price": float(p.cost_price or 0),
            }

        order_ids = list({t.order_id for t in trades if hasattr(t, "order_id")})
        orders: Dict[str, Any] = {}
        if order_ids:
            order_query = select(Order).where(Order.order_id.in_(order_ids))
            result = await self.account_repo.session.execute(order_query)
            orders = {o.order_id: o for o in result.scalars().all()}

        position_updates = []
        for trade in trades:
            ts_code = getattr(trade, "ts_code", "unknown")
            order = orders.get(getattr(trade, "order_id", None))
            direction = getattr(order, "direction", None) if order else None

            current = pos_map.get(ts_code, {"volume": 0.0, "cost_price": 0.0})

            if direction == "buy":
                new_volume = current["volume"] + float(trade.volume)
                new_cost = (
                        (current["volume"] * current["cost_price"] + float(trade.volume) * float(trade.price))
                        / new_volume
                ) if new_volume > 0 else float(trade.price)
                current["volume"] = new_volume
                current["cost_price"] = new_cost
            elif direction == "sell":
                current["volume"] = max(0.0, current["volume"] - float(trade.volume))

            pos_map[ts_code] = current

        for ts_code, info in pos_map.items():
            position_updates.append({
                "security_id": ts_code,
                "cost_price": info["cost_price"],
                "volume": info["volume"],
                "update_time": datetime.now(),
            })

        return position_updates

    async def _generate_daily_statement(
            self,
            account_id: str,
            trading_day: date,
            daily_pnl: Dict,
            assets: Dict
    ) -> Dict:
        """
        生成日终对账单

        Args:
            account_id: 账户ID
            trading_day: 交易日
            daily_pnl: 当日盈亏
            assets: 资产信息

        Returns:
            Dict: 对账单信息
        """
        from modules.account.utils.statement_generator import StatementGenerator

        generator = StatementGenerator()

        # 获取当日交易明细
        trades = await self.trade_repo.get_trades_by_account_and_date(
            account_id,
            trading_day
        )

        # 获取持仓明细
        positions = await self.position_repo.get_current_positions(account_id)

        # 转换 trades 为字典列表
        trade_dicts = []
        for trade in trades:
            trade_dicts.append({
                'trade_id': getattr(trade, 'trade_id', 'unknown'),
                'security_id': getattr(trade, 'security_id', getattr(trade, 'ts_code', 'unknown')),
                'price': trade.price,
                'volume': trade.volume,
                'trade_time': trade.trade_time
            })

        # 转换 positions 为字典列表
        position_dicts = []
        for position in positions:
            position_dicts.append({
                'security_id': getattr(position, 'ts_code', 'unknown'),
                'quantity': position.volume,
                'cost_price': position.cost_price,
                'current_price': float(position.last_price) if getattr(position, 'last_price', None) else 0.0,
            })

        # 生成对账单
        statement = generator.generate_daily_statement(
            account_id=account_id,
            trading_day=trading_day,
            trades=trade_dicts,
            positions=position_dicts,
            daily_pnl=daily_pnl,
            assets=assets
        )

        return statement

    async def _calculate_period_pnl(
            self,
            account_id: str,
            start_date: date,
            end_date: date
    ) -> Dict:
        """
        计算期间盈亏

        Args:
            account_id: 账户ID
            start_date: 开始日期
            end_date: 结束日期

        Returns:
            Dict: 期间盈亏
        """
        analysis = await self.pnl_calculator.calculate_pnl_analysis(
            account_id, start_date, end_date
        )

        pnl_rate = Decimal("0")
        from core import BusinessException
        try:
            assets = await self.asset_service.get_account_assets(account_id)
            total_asset = assets.get("total_asset", Decimal("0")) if isinstance(assets, dict) else Decimal("0")
            if total_asset and float(total_asset) != 0:
                pnl_rate = analysis.total_pnl / Decimal(str(total_asset))
        except BusinessException:
            pass

        return {
            "total_pnl": float(analysis.total_pnl),
            "pnl_rate": float(pnl_rate),
            "detail": {
                "total_trades": analysis.total_trades,
                "win_rate": float(analysis.win_rate),
                "avg_pnl_per_trade": float(analysis.avg_pnl_per_trade),
                "profit_ratio": float(analysis.profit_ratio),
                "max_winning_trade": float(analysis.max_winning_trade),
                "max_losing_trade": float(analysis.max_losing_trade),
                "sharpe_ratio": float(analysis.sharpe_ratio),
                "sortino_ratio": float(analysis.sortino_ratio),
            },
        }

    @staticmethod
    async def _generate_weekly_report(
            account_id: str,
            start_date: date,
            end_date: date,
            weekly_pnl: Dict
    ) -> Dict:
        """
        生成周度报告

        Args:
            account_id: 账户ID
            start_date: 周开始日期
            end_date: 周结束日期
            weekly_pnl: 周盈亏

        Returns:
            Dict: 周度报告信息
        """
        from modules.account.utils.statement_generator import StatementGenerator

        generator = StatementGenerator()

        # 生成周度报告
        report = generator.generate_weekly_report(
            account_id=account_id,
            start_date=start_date,
            end_date=end_date,
            weekly_pnl=weekly_pnl
        )

        return report

    @staticmethod
    async def _generate_monthly_report(
            account_id: str,
            start_date: date,
            end_date: date,
            monthly_pnl: Dict
    ) -> Dict:
        """
        生成月度报告

        Args:
            account_id: 账户ID
            start_date: 月开始日期
            end_date: 月结束日期
            monthly_pnl: 月盈亏

        Returns:
            Dict: 月度报告信息
        """
        from modules.account.utils.statement_generator import StatementGenerator

        generator = StatementGenerator()

        # 生成月度报告
        report = generator.generate_monthly_report(
            account_id=account_id,
            start_date=start_date,
            end_date=end_date,
            monthly_pnl=monthly_pnl
        )

        return report


def create_settlement_tasks(
        session: "AsyncSession",
        event_engine: Any = None,
) -> SettlementTasks:
    """工厂函数：基于已有 session 创建 SettlementTasks 实例

    供 FastAPI 依赖注入（Depends(get_db_session)）使用，避免嵌套事件循环问题。

    Args:
        session: SQLAlchemy 异步会话（由 FastAPI DI 管理生命周期）
        event_engine: 可选事件引擎，用于发布结算完成事件

    Returns:
        SettlementTasks: 新构建的结算任务管理器

    Example:
        @router.post("/settlement/daily")
        async def run_daily_settlement(
            db: AsyncSession = Depends(get_db_session),
            event_engine: EventEngine = Depends(get_event_engine),
        ):
            tasks = create_settlement_tasks(db, event_engine)
            return await tasks.daily_settlement_task()
    """
    from shared.database.repositories.account.asset.account_repo import AccountRepository
    from shared.database.repositories.trading.order.trade_repo import TradeRepository
    from shared.database.repositories.trading.position.position_repo import PositionRepository

    return SettlementTasks(
        account_repo=AccountRepository(session),
        trade_repo=TradeRepository(session),
        position_repo=PositionRepository(session),
        event_engine=event_engine,
    )


# 兼容别名：旧代码中可能引用的 get_settlement_tasks
get_settlement_tasks = create_settlement_tasks


def _create_session_for_celery():
    """Celery 任务中创建数据库会话（同步上下文内使用 asyncio.run）"""
    from shared.database.session.connection_pool import get_connection_pool

    pool = get_connection_pool()
    try:
        factory = pool.get_session_factory()
    except RuntimeError:
        import asyncio
        asyncio.run(pool.initialize())
        factory = pool.get_session_factory()
    return factory()


def _run_async_in_celery(coro):
    """在 Celery 同步任务中安全执行异步协程"""
    import asyncio
    try:
        loop = asyncio.get_running_loop()
    except RuntimeError:
        return asyncio.run(coro)
    # 如果已在事件循环中（罕见），使用 nest_asyncio 或直接报错
    raise RuntimeError("Celery task should not run inside an existing event loop")


# 定义Celery任务（如果使用Celery）
try:
    from celery import shared_task


    @shared_task
    def daily_settlement_task(trading_day: Optional[str] = None):
        """Celery日终结算任务"""
        if trading_day:
            from datetime import datetime
            trading_date = datetime.strptime(trading_day, "%Y-%m-%d").date()
        else:
            trading_date = None

        session = _create_session_for_celery()
        try:
            tasks = create_settlement_tasks(session)
            return _run_async_in_celery(tasks.daily_settlement_task(trading_date))
        finally:
            _run_async_in_celery(session.close())


    @shared_task
    def weekly_settlement_task(week_end_date: Optional[str] = None):
        """Celery周末结算任务"""
        if week_end_date:
            from datetime import datetime
            week_end = datetime.strptime(week_end_date, "%Y-%m-%d").date()
        else:
            week_end = None

        session = _create_session_for_celery()
        try:
            tasks = create_settlement_tasks(session)
            return _run_async_in_celery(tasks.weekly_settlement_task(week_end))
        finally:
            _run_async_in_celery(session.close())


    @shared_task
    def monthly_settlement_task(month_end_date: Optional[str] = None):
        """Celery月末结算任务"""
        if month_end_date:
            from datetime import datetime
            month_end = datetime.strptime(month_end_date, "%Y-%m-%d").date()
        else:
            month_end = None

        session = _create_session_for_celery()
        try:
            tasks = create_settlement_tasks(session)
            return _run_async_in_celery(tasks.monthly_settlement_task(month_end))
        finally:
            _run_async_in_celery(session.close())

except ImportError:
    pass  # Celery 未安装，不注册 shared_task
