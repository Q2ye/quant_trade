"""
账户结算任务模块
负责账户的日终、周末、月末结算处理
"""

import logging
from datetime import datetime, date, timedelta
from decimal import Decimal
from typing import Dict, List, Optional, Any

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from core import BusinessException
from modules.account.calculators.asset_calculator import AssetCalculator
from modules.account.calculators.pnl_calculator import PnLCalculator
from modules.account.events.settlement_events import AccountSettlementCompletedEvent
from modules.account.services.account_service import AccountService
from modules.account.services.asset_service import AssetService
from shared.database.models.business_models import AccountDailyPerformance
from shared.database.repositories.account.asset.account_repo import AccountRepository
from shared.database.repositories.account.settlement.transaction_repo import AccountTransactionRepository
from shared.database.repositories.market.quote import StockDailyRepository
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

        # 结算辅助仓库
        self.stock_daily_repo = StockDailyRepository(account_repo.session)
        self.transaction_repo = AccountTransactionRepository(account_repo.session)

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
            # 1. 获取当日所有活跃账户（用 get_active_accounts，避免不存在的 get_all）
            accounts = await self.account_repo.get_active_accounts(limit=100000)

            results = {}
            for account in accounts:
                account_id = str(getattr(account, 'id', 'unknown'))
                logger.info(f"处理账户 {account_id} 的日终结算")

                try:
                    # 2. 计算当日盈亏（资产差分法，含市值重估）
                    daily_pnl = await self._calculate_daily_pnl(account_id, trading_day)

                    # 3. 回写账户资产 + 写单条日绩效快照
                    updated_assets = await self._update_account_assets(
                        account_id,
                        daily_pnl,
                        trading_day
                    )

                    # 4. 记录结算结果（对账单仅落库 account_statements，不再生成 PDF 文件）
                    settlement_record = await self.account_repo.create_settlement_record({
                        'account_id': account_id,
                        'trading_day': trading_day,
                        'settlement_type': 'daily',
                        'pnl': float(daily_pnl['total_pnl']),
                        'assets_snapshot': updated_assets,
                        'opening_balance': daily_pnl.get('yesterday_total_asset', 0),
                        'net_deposit': daily_pnl.get('net_deposit', 0),
                        'total_trades': daily_pnl.get('trade_count', 0),
                        'total_fees': daily_pnl.get('total_fees', 0),
                        'statement_path': '',
                        'status': 'completed'
                    })

                    results[account_id] = {
                        'status': 'success',
                        'daily_pnl': daily_pnl,
                        'updated_assets': updated_assets,
                        'updated_positions': 0,
                        'statement': {'file_path': '', 'statement_data': daily_pnl},
                        'settlement_id': settlement_record.id
                    }

                    logger.info(f"账户 {account_id} 日终结算完成: 当日盈亏={daily_pnl.get('total_pnl')}")

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

            # 获取所有活跃账户
            accounts = await self.account_repo.get_active_accounts(limit=100000)

            results = {}
            for account in accounts:
                account_id = str(getattr(account, 'id', 'unknown'))

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

            accounts = await self.account_repo.get_active_accounts(limit=100000)

            results = {}
            for account in accounts:
                account_id = str(getattr(account, 'id', 'unknown'))

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
        计算账户当日盈亏（资产差分法）。

            当日盈亏 = 今日总资产 - 昨日总资产 - 当日净出入金
            今日总资产 = 可用资金 + 冻结资金 + 持仓市值（按 trading_day 收盘价重估）
            昨日总资产 = 前一结算日快照（无历史快照时用初始资金兜底）

        修复点：
        - B1: 原实现把"累计浮盈"当"当日持仓变动"，混档已实现/未实现
        - B2: 原 total_asset 读取为 None → pnl_rate 恒 0
        - B4: 结算结果不回写账户表
        """
        account = await self.account_repo.get(account_id)
        if not account:
            raise ValueError(f"账户不存在: {account_id}")

        # 今日资产（市值按 trading_day 收盘价重估）
        market_value = await self._mark_to_market(account_id, trading_day)
        available = Decimal(str(account.available_balance or 0))
        frozen = Decimal(str(account.frozen_balance or 0))
        cash = available + frozen
        today_total = cash + market_value

        yesterday_total = await self._get_yesterday_total_asset(account_id, trading_day)
        net_deposit = await self._get_net_deposit(account_id, trading_day)

        daily_pnl = today_total - yesterday_total - net_deposit
        pnl_rate = (daily_pnl / yesterday_total) if yesterday_total and yesterday_total != Decimal("0") else Decimal("0")

        # 当日成交明细（对账单/统计用）
        trade_summary = await self._get_day_trade_summary(account_id, trading_day)

        return {
            "total_pnl": float(daily_pnl),
            "pnl_rate": float(pnl_rate),
            "detail": {
                "trade_pnl": float(trade_summary["realized_pnl"]),
                "position_pnl_change": float(daily_pnl - trade_summary["realized_pnl"]),
                "trade_volume": trade_summary["volume"],
                "trade_amount": float(trade_summary["amount"]),
                "commission": float(trade_summary["commission"]),
                "tax": float(trade_summary["tax"]),
            },
            "today_assets": {
                "total_asset": today_total,
                "cash_balance": cash,
                "available_cash": available,
                "frozen_cash": frozen,
                "market_value": market_value,
            },
            "yesterday_total_asset": float(yesterday_total),
            "net_deposit": float(net_deposit),
            "trade_count": trade_summary["count"],
            "total_fees": float(trade_summary["commission"] + trade_summary["tax"]),
        }

    async def _mark_to_market(self, account_id: str, trading_day: date) -> Decimal:
        """按 trading_day 收盘价重估持仓市值（当日行情缺失用持仓 last_price 兜底）"""
        positions = await self.position_repo.get_account_positions(account_id)
        if not positions:
            return Decimal("0")
        symbols = [p.ts_code for p in positions if p.volume and p.volume > 0]
        if not symbols:
            return Decimal("0")
        # 一次 IN 批量查询当日收盘价，避免 N+1
        rows = await self.stock_daily_repo.get_batch_by_date_range(symbols, trading_day, trading_day)
        close_map = {r.ts_code: Decimal(str(r.close)) for r in rows if getattr(r, "close", None) is not None}
        market_value = Decimal("0")
        for p in positions:
            if not p.volume or p.volume <= 0:
                continue
            close = close_map.get(p.ts_code)
            if close is None:
                close = Decimal(str(p.last_price)) if p.last_price else Decimal("0")
            market_value += Decimal(str(p.volume)) * close
        return market_value

    async def _get_yesterday_total_asset(self, account_id: str, trading_day: date) -> Decimal:
        """取前一结算日总资产；无历史快照时用初始资金兜底"""
        result = await self.account_repo.session.execute(
            select(AccountDailyPerformance)
            .where(
                AccountDailyPerformance.account_id == account_id,
                AccountDailyPerformance.trade_date < trading_day,
            )
            .order_by(AccountDailyPerformance.trade_date.desc())
            .limit(1)
        )
        rec = result.scalars().first()
        if rec and rec.total_asset is not None:
            return Decimal(str(rec.total_asset))
        account = await self.account_repo.get(account_id)
        return Decimal(str(account.initial_balance)) if account and account.initial_balance else Decimal("0")

    async def _get_net_deposit(self, account_id: str, trading_day: date) -> Decimal:
        """当日净出入金（存款 +，取款 -）

        注：transaction_repo.get_transactions_by_date_range 的 end_date 会转午夜零点，
        会漏掉当日 00:00 之后的流水，这里自建整天时间范围查询。
        """
        from shared.database.models.business_models import AccountTransaction

        start_dt = datetime.combine(trading_day, datetime.min.time())
        end_dt = datetime.combine(trading_day, datetime.max.time())
        result = await self.account_repo.session.execute(
            select(AccountTransaction).where(
                AccountTransaction.account_id == account_id,
                AccountTransaction.transaction_date >= start_dt,
                AccountTransaction.transaction_date <= end_dt,
            )
        )
        net = Decimal("0")
        for t in result.scalars().all():
            # deposit/withdrawal 为外部出入金，transfer 为账户间划转（转入+，转出-），
            # 均视为资金变动，需从当日盈亏中扣除，避免划转金额被误算成收益
            if t.transaction_type in ("deposit", "withdrawal", "transfer"):
                net += Decimal(str(t.amount))
        return net

    async def _get_day_trade_summary(self, account_id: str, trading_day: date) -> Dict:
        """当日成交汇总：已实现盈亏（卖出用当前持仓成本近似）、成交量额、费用"""
        from shared.database.models.business_models import Order

        trades = await self.trade_repo.get_trades_by_account_and_date(account_id, trading_day)
        if not trades:
            return {"realized_pnl": Decimal("0"), "volume": 0, "amount": Decimal("0"),
                    "commission": Decimal("0"), "tax": Decimal("0"), "count": 0}

        order_ids = list({t.order_id for t in trades if getattr(t, "order_id", None)})
        direction_map: Dict[str, str] = {}
        if order_ids:
            result = await self.account_repo.session.execute(
                select(Order.order_id, Order.direction).where(Order.order_id.in_(order_ids))
            )
            direction_map = {row[0]: row[1] for row in result.all()}

        realized = Decimal("0")
        volume = 0
        amount = Decimal("0")
        commission = Decimal("0")
        tax = Decimal("0")
        for t in trades:
            volume += int(t.volume)
            amount += Decimal(str(t.volume)) * Decimal(str(t.price))
            commission += Decimal(str(t.commission or 0))
            tax += Decimal(str(t.tax or 0))
            if direction_map.get(t.order_id) == "sell":
                cost = await self._get_position_cost(account_id, t.ts_code)
                if cost:
                    realized += Decimal(str(t.volume)) * (Decimal(str(t.price)) - cost)

        return {"realized_pnl": realized, "volume": volume, "amount": amount,
                "commission": commission, "tax": tax, "count": len(trades)}

    async def _get_position_cost(self, account_id: str, ts_code: str) -> Optional[Decimal]:
        """取某证券当前持仓成本价（无持仓返回 None）"""
        positions = await self.position_repo.get_account_positions(account_id)
        for pos in positions:
            if pos.ts_code == ts_code and pos.volume and pos.volume > 0:
                return Decimal(str(pos.cost_price))
        return None

    async def _update_account_assets(
            self,
            account_id: str,
            daily_pnl: Dict,
            trading_day: date
    ) -> Dict:
        """
        回写账户资产并写单条日绩效快照。

        - 回写 accounts 表：市值重估 + 总资产（现金+市值），与结算口径一致（修复 B4 不回写）
        - 单条 upsert account_daily_performance（修复 B3：原 create_asset_snapshot +
          record_daily_settlement 双写导致每日两条重复记录）
        """
        today = daily_pnl.get("today_assets", {})
        total_asset = Decimal(str(today.get("total_asset", 0)))
        cash_balance = Decimal(str(today.get("cash_balance", 0)))
        available_cash = Decimal(str(today.get("available_cash", 0)))
        frozen_cash = Decimal(str(today.get("frozen_cash", 0)))
        market_value = Decimal(str(today.get("market_value", 0)))
        pnl_amount = Decimal(str(daily_pnl.get("total_pnl", 0)))
        pnl_rate = Decimal(str(daily_pnl.get("pnl_rate", 0)))

        # 回写账户：市值重估 + 总资产（现金+市值）
        await self.account_repo.update(account_id, {
            "market_value": market_value,
            "total_balance": total_asset,
            "last_trade_date": trading_day,
        })

        # 单条 upsert 日绩效（幂等）
        await self._upsert_daily_performance(
            account_id=account_id,
            trading_day=trading_day,
            total_asset=total_asset,
            cash=cash_balance,
            market_value=market_value,
            daily_pnl=pnl_amount,
            daily_return=pnl_rate,
        )

        return {
            "total_asset": float(total_asset),
            "cash_balance": float(cash_balance),
            "available_cash": float(available_cash),
            "frozen_cash": float(frozen_cash),
            "market_value": float(market_value),
        }

    async def _upsert_daily_performance(
            self,
            account_id: str,
            trading_day: date,
            total_asset: Decimal,
            cash: Decimal,
            market_value: Decimal,
            daily_pnl: Decimal,
            daily_return: Decimal,
    ) -> None:
        """幂等写入 account_daily_performance（(account_id, trade_date) 存在则更新）"""
        account = await self.account_repo.get(account_id)
        user_id = account.user_id if account else ""

        result = await self.account_repo.session.execute(
            select(AccountDailyPerformance).where(
                AccountDailyPerformance.account_id == account_id,
                AccountDailyPerformance.trade_date == trading_day,
            )
        )
        rec = result.scalars().first()
        if rec:
            rec.total_asset = total_asset
            rec.cash = cash
            rec.market_value = market_value
            rec.daily_pnl = daily_pnl
            rec.daily_return = daily_return
        else:
            self.account_repo.session.add(AccountDailyPerformance(
                account_id=account_id,
                user_id=user_id,
                trade_date=trading_day,
                total_asset=total_asset,
                cash=cash,
                market_value=market_value,
                daily_pnl=daily_pnl,
                daily_return=daily_return,
            ))
        await self.account_repo.session.flush()

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
