#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
绩效分析服务

负责计算和管理策略/账户的绩效指标，是分析模块最核心的服务。

指标体系：
----------
**收益类**
- total_return：区间总收益率 = (end_value - start_value) / start_value
- annual_return：年化收益率（通过 FinancialCalculator 计算）
- cagr：年复合增长率 = (end_value / start_value)^(1/years) - 1

**风险调整收益**
- sharpe_ratio：夏普比率 = (年化收益 - 无风险利率) / 年化波动率
- sortino_ratio：索提诺比率 — 仅用下行波动率（负收益部分）计算
- calmar_ratio：卡玛比率 = 年化收益 / |最大回撤|
- information_ratio：信息比率 = 超额收益 / 跟踪误差（需基准）

**风险指标**
- volatility：年化波动率 = std(daily_returns) × sqrt(252)
- max_drawdown：最大回撤 = max((peak - valley) / peak)
- var_95 / var_99：95%/99% 置信度在险价值
- expected_shortfall (CVaR)：超过 VaR 的尾部损失的期望值
- tracking_error：跟踪误差（需基准）

**Alpha/Beta（需基准）**
- alpha：Jensen's Alpha — 策略超越 CAPM 预期的超额收益
- beta：策略对基准的敏感度 — Cov(R_s, R_b) / Var(R_b)
- r_squared：拟合优度 — 策略收益能被基准解释的比例

**交易统计**
- win_rate：胜率 = 盈利交易数 / 总交易数
- profit_factor：盈亏比 = 总盈利 / |总亏损|

计算流程：
---------
1. 从交易记录重建净值曲线（或从账户快照获取）
2. 计算日收益率序列：returns = equity.pct_change()
3. 调用 FinancialCalculator 计算各项指标
4. 计算回撤曲线、月度收益
5. 如需基准对比，获取基准收益率并计算 Alpha/Beta
"""

import asyncio
import logging
from datetime import date, datetime, timedelta
from decimal import Decimal
from typing import Dict, List, Optional, Any

import numpy as np
import pandas as pd
from sqlalchemy.ext.asyncio import AsyncSession

from modules.analysis.models import PerformanceMetrics
from shared.database.repositories import AccountRepository
from shared.database.repositories import StrategyRepository
from shared.database.repositories import TradeRepository
from shared.database.repositories.market.quote import StockDailyRepository
from utils.core_utils.math_utils.financial_calculator import FinancialCalculator

logger = logging.getLogger(__name__)


class PerformanceService:
    """绩效分析服务

    计算策略或账户在指定区间的全面绩效指标。
    通过 Repository 层获取数据，委托 FinancialCalculator 执行金融数学计算。

    使用方式：
        service = PerformanceService(session)
        metrics = await service.calculate_strategy_performance(
            strategy_id="xxx", start_date=..., end_date=..., benchmark="000300.SH"
        )
        # metrics.to_dict() 返回完整的绩效字典
    """

    def __init__(
            self,
            session: AsyncSession,
            strategy_repo: StrategyRepository = None,
            account_repo: AccountRepository = None,
            trade_repo: TradeRepository = None,
            quote_repo: StockDailyRepository = None
    ):
        """
        初始化绩效服务

        Args:
            session: 异步数据库会话
            strategy_repo: 策略 Repository（可选，默认根据 session 创建）
            account_repo: 账户 Repository（可选）
            trade_repo: 交易 Repository（可选，用于重建净值曲线）
            quote_repo: 日线行情 Repository（可选，用于获取基准收益率）
        """
        self.session = session
        self.strategy_repo = strategy_repo or StrategyRepository(session)
        self.account_repo = account_repo or AccountRepository(session)
        self.trade_repo = trade_repo or TradeRepository(session)
        self.quote_repo = quote_repo or StockDailyRepository(session)
        self.fin_calc = FinancialCalculator()

    # =========================================================================
    # 公有方法 — 绩效计算入口
    # =========================================================================

    async def calculate_strategy_performance(
            self,
            strategy_id: str,
            start_date: date,
            end_date: date,
            benchmark: Optional[str] = None
    ) -> PerformanceMetrics:
        """计算策略在指定区间的完整绩效指标

        这是绩效分析的主入口，汇总所有收益、风险、Alpha/Beta 和交易统计指标。

        数据获取流程：
        1. 验证策略存在
        2. 通过 trade_repo 获取策略的交易记录
        3. 从交易记录重建每日净值曲线
        4. 计算日收益率序列
        5. 如提供基准代码，获取基准收益率用于 Alpha/Beta/信息比率计算

        指标计算委托 FinancialCalculator 完成，确保公式一致性。

        Args:
            strategy_id: 策略 ID
            start_date: 分析区间起始日期
            end_date: 分析区间结束日期
            benchmark: 基准指数代码（如 "000300.SH"），为 None 则跳过 Alpha/Beta 计算

        Returns:
            PerformanceMetrics: 包含所有绩效指标的领域对象

        Raises:
            ValueError: 策略不存在、净值数据不足或计算失败时抛出
        """
        try:
            # 1. 验证策略存在
            strategy = await self.strategy_repo.get(strategy_id)
            if not strategy:
                raise ValueError(f"策略不存在: {strategy_id}")

            # 2. 获取净值曲线（从交易记录重建）
            equity_curve = await self._get_strategy_equity_curve(
                strategy_id, start_date, end_date
            )

            if len(equity_curve) < 2:
                raise ValueError("净值曲线数据不足（至少需要 2 个数据点）")

            # 3. 转换为 DataFrame 并计算日收益率
            df_equity = pd.DataFrame(equity_curve)
            df_equity['trade_date'] = pd.to_datetime(df_equity['trade_date'])
            df_equity.set_index('trade_date', inplace=True)

            returns = df_equity['equity'].pct_change().dropna()

            # 4. 获取基准收益率（可选）
            benchmark_returns = None
            if benchmark:
                benchmark_returns = await self._get_benchmark_returns(
                    benchmark, start_date, end_date
                )

            # 5. 计算核心绩效指标 — 委托 FinancialCalculator
            start_value = float(df_equity['equity'].iloc[0])
            end_value = float(df_equity['equity'].iloc[-1])
            years = (end_date - start_date).days / 365.25

            total_return = (end_value - start_value) / start_value if start_value != 0 else 0.0
            annual_return = self.fin_calc.annualized_return(returns.values)
            cagr = ((end_value / start_value) ** (1.0 / years) - 1.0) if start_value > 0 and years > 0 else 0.0
            sharpe_ratio = self.fin_calc.sharpe_ratio(returns.values, risk_free_rate=0.03)
            sortino_ratio = self.fin_calc.sortino_ratio(returns.values, risk_free_rate=0.03)
            volatility = self.fin_calc.annualized_volatility(returns.values)
            max_drawdown = self.fin_calc.maximum_drawdown(df_equity['equity'].values)
            calmar_ratio = self.fin_calc.calmar_ratio(df_equity['equity'].values)
            var_95 = self.fin_calc.value_at_risk(returns.values, confidence=0.95)
            var_99 = self.fin_calc.value_at_risk(returns.values, confidence=0.99)
            expected_shortfall = self.fin_calc.conditional_value_at_risk(returns.values, confidence=0.95)

            # 6. 获取交易统计
            trade_stats = await self._get_trade_statistics(
                strategy_id, start_date, end_date
            )

            # 7. Alpha/Beta/信息比率（需基准收益率）
            alpha = beta = tracking_error = information_ratio = r_squared = Decimal("0.0")
            if benchmark_returns is not None and len(benchmark_returns) > 0:
                alpha = self.fin_calc.alpha(
                    returns.values, benchmark_returns.values
                )
                beta = self.fin_calc.beta(
                    returns.values, benchmark_returns.values
                )
                tracking_error = self.fin_calc.tracking_error(
                    returns.values, benchmark_returns.values
                )
                information_ratio = self.fin_calc.information_ratio(
                    returns.values, benchmark_returns.values
                )
                # 计算 R²：策略收益与基准收益的相关系数的平方
                aligned_bench = benchmark_returns.reindex(returns.index).dropna()
                aligned_ret = returns.reindex(aligned_bench.index).dropna()
                if len(aligned_ret) > 2:
                    corr = np.corrcoef(aligned_ret.values, aligned_bench.values)[0, 1]
                    r_squared = corr ** 2

            # 8. 构建绩效指标对象
            metrics = PerformanceMetrics(
                strategy_id=strategy_id,
                account_id=strategy.user_id,
                start_date=start_date,
                end_date=end_date,
                benchmark=benchmark,
                total_return=Decimal(str(total_return)),
                annual_return=Decimal(str(annual_return)),
                cagr=Decimal(str(cagr)),
                sharpe_ratio=Decimal(str(sharpe_ratio)),
                sortino_ratio=Decimal(str(sortino_ratio)),
                calmar_ratio=Decimal(str(calmar_ratio)),
                information_ratio=Decimal(str(information_ratio)),
                volatility=Decimal(str(volatility)),
                max_drawdown=Decimal(str(max_drawdown)),
                var_95=Decimal(str(var_95)),
                var_99=Decimal(str(var_99)),
                expected_shortfall=Decimal(str(expected_shortfall)),
                alpha=Decimal(str(alpha)),
                beta=Decimal(str(beta)),
                tracking_error=Decimal(str(tracking_error)),
                r_squared=Decimal(str(r_squared)),
                win_rate=Decimal(str(trade_stats.get('win_rate', 0))),
                profit_factor=Decimal(str(trade_stats.get('profit_factor', 0))),
                average_win=Decimal(str(trade_stats.get('average_win', 0))),
                average_loss=Decimal(str(trade_stats.get('average_loss', 0))),
                total_trades=trade_stats.get('total_trades', 0),
                winning_trades=trade_stats.get('winning_trades', 0),
                losing_trades=trade_stats.get('losing_trades', 0),
                trading_days=len(returns),
                total_days=(end_date - start_date).days + 1
            )

            # 9. 附加序列数据（不存入 PerformanceMetrics dataclass 的标准字段，动态挂载）
            metrics.daily_returns = returns.dropna().tolist()

            # 净值曲线
            metrics.equity_curve = [
                {
                    'date': str(idx)[:10],
                    'equity': float(row['equity']), # type: ignore
                    'cash': float(row.get('cash', 0)),
                    'market_value': float(row.get('market_value', 0))
                }
                for idx, row in df_equity.iterrows()
            ]

            # 月度收益率
            if len(df_equity) > 0:
                monthly_returns = self._calculate_monthly_returns(df_equity)
                metrics.monthly_returns = {
                    month: Decimal(str(ret))
                    for month, ret in monthly_returns.items()
                }

            # 回撤曲线（每个交易日的累计回撤）
            equity_arr = df_equity['equity'].values
            peak = np.maximum.accumulate(equity_arr)
            drawdown_series = (peak - equity_arr) / peak
            metrics.drawdown_curve = [
                {
                    'date': str(df_equity.index[i])[:10],
                    'drawdown': float(drawdown_series[i])
                }
                for i in range(len(df_equity))
            ]

            return metrics

        except Exception as e:
            raise ValueError(f"计算策略绩效失败: {str(e)}")

    async def calculate_account_performance(
            self,
            account_id: str,
            start_date: date,
            end_date: date
    ) -> PerformanceMetrics:
        """计算账户在指定区间的绩效指标

        与 calculate_strategy_performance 逻辑平行，但数据来源不同：
        - 策略绩效：从交易记录重建净值曲线
        - 账户绩效：从每日资产快照获取净值

        注意：账户级绩效不含交易统计（win_rate 等），不含 Alpha/Beta。

        Args:
            account_id: 账户 ID
            start_date: 起始日期
            end_date: 结束日期

        Returns:
            PerformanceMetrics: 账户绩效指标（Alpha/Beta 和交易统计字段为空/默认值）

        Raises:
            ValueError: 账户不存在或快照数据不足时抛出
        """
        try:
            # 1. 验证账户存在（"default" 无对应账户时返回空数据）
            account = await self.account_repo.get(account_id)
            if not account:
                if account_id == "default":
                    return {
                        "total_return": 0, "annual_return": 0,
                        "sharpe_ratio": 0, "max_drawdown": 0,
                        "total_asset": 0, "equity_curve": [],
                    }
                raise ValueError(f"账户不存在: {account_id}")

            # 2. 获取每日资产快照
            snapshots = await self.account_repo.get_daily_snapshots(
                account_id, start_date, end_date
            )

            if len(snapshots) < 2:
                raise ValueError("账户快照数据不足（至少需要 2 个数据点）")

            # 3. 构建资产曲线
            equity_curve = []
            for snapshot in snapshots:
                equity_curve.append({
                    'trade_date': snapshot.trade_date,
                    'equity': snapshot.total_asset,
                    'cash': snapshot.cash,
                    'market_value': snapshot.market_value
                })

            df_equity = pd.DataFrame(equity_curve)
            df_equity['trade_date'] = pd.to_datetime(df_equity['trade_date'])
            df_equity.set_index('trade_date', inplace=True)

            returns = df_equity['equity'].pct_change().dropna()

            # 4. 计算绩效指标
            start_value = float(df_equity['equity'].iloc[0])
            end_value = float(df_equity['equity'].iloc[-1])
            years = (end_date - start_date).days / 365.25
            total_return = (end_value - start_value) / start_value if start_value != 0 else 0.0
            annual_return = self.fin_calc.annualized_return(returns.values)
            cagr = ((end_value / start_value) ** (1.0 / years) - 1.0) if start_value > 0 and years > 0 else 0.0
            sharpe = self.fin_calc.sharpe_ratio(returns.values)
            sortino = self.fin_calc.sortino_ratio(returns.values)
            vol = self.fin_calc.annualized_volatility(returns.values)
            max_dd = self.fin_calc.maximum_drawdown(df_equity['equity'].values)
            calmar = self.fin_calc.calmar_ratio(df_equity['equity'].values)
            var_95 = self.fin_calc.value_at_risk(returns.values, confidence=0.95)
            cvar_95 = self.fin_calc.conditional_value_at_risk(returns.values, confidence=0.95)

            metrics = PerformanceMetrics(
                strategy_id='',  # 账户绩效无策略ID
                account_id=account_id,
                start_date=start_date,
                end_date=end_date,
                total_return=Decimal(str(total_return)),
                annual_return=Decimal(str(annual_return)),
                cagr=Decimal(str(cagr)),
                sharpe_ratio=Decimal(str(sharpe)),
                sortino_ratio=Decimal(str(sortino)),
                calmar_ratio=Decimal(str(calmar)),
                volatility=Decimal(str(vol)),
                max_drawdown=Decimal(str(max_dd)),
                var_95=Decimal(str(var_95)),
                expected_shortfall=Decimal(str(cvar_95)),
                trading_days=len(returns),
                total_days=(end_date - start_date).days + 1
            )
            metrics.daily_returns = returns.dropna().tolist()

            return metrics

        except Exception as e:
            raise ValueError(f"计算账户绩效失败: {str(e)}")

    async def compare_multiple_strategies(
            self,
            strategy_ids: List[str],
            start_date: date,
            end_date: date,
            benchmark: Optional[str] = None
    ) -> Dict[str, PerformanceMetrics]:
        """并行计算多个策略的绩效指标

        使用 asyncio.gather 并发计算，提升批量对比效率。
        单个策略失败不影响其他策略（异常被捕获并跳过）。

        Args:
            strategy_ids: 策略 ID 列表
            start_date: 起始日期
            end_date: 结束日期
            benchmark: 基准代码（可选，应用于所有策略）

        Returns:
            Dict[str, PerformanceMetrics]: {strategy_id: metrics}，失败的策略不包含在结果中
        """
        results = {}

        # 并发计算
        tasks = []
        for strategy_id in strategy_ids:
            task = self.calculate_strategy_performance(
                strategy_id, start_date, end_date, benchmark
            )
            tasks.append(task)

        all_results = await asyncio.gather(*tasks, return_exceptions=True)

        for i, result in enumerate(all_results):
            if isinstance(result, Exception):
                logger.warning(f"计算策略 {strategy_ids[i]} 绩效失败: {str(result)}")
            else:
                results[strategy_ids[i]] = result

        return results

    async def get_performance_summary(
            self,
            entity_type: str,
            entity_id: str,
            period: str = '1y'
    ) -> Dict[str, Any]:
        """获取指定时间段的绩效摘要

        根据 period 自动计算起始日期，调用对应的绩效计算方法。

        支持的时间段：
        - '1m'：近 1 个月（30 天）
        - '3m'：近 3 个月（90 天）
        - '6m'：近半年（180 天）
        - '1y'：近 1 年（365 天）
        - '3y'：近 3 年（1095 天）
        - '5y'：近 5 年（1825 天）
        - 'all'：从最早数据至今

        Args:
            entity_type: 实体类型 — 'strategy' 或 'account'
            entity_id: 实体 ID
            period: 时间段代码（默认 '1y'）

        Returns:
            Dict: metrics.to_dict() 的结果

        Raises:
            ValueError: 不支持的实体类型时抛出
        """
        end_date = date.today()

        # period → start_date 映射
        period_days = {
            '1m': 30, '3m': 90, '6m': 180,
            '1y': 365, '3y': 1095, '5y': 1825
        }

        if period in period_days:
            start_date = end_date - timedelta(days=period_days[period])
        else:
            # 'all' 或其他：从最早数据日期开始
            start_date = await self._get_earliest_date(entity_type, entity_id)

        if entity_type == 'strategy':
            metrics = await self.calculate_strategy_performance(
                entity_id, start_date, end_date
            )
        elif entity_type == 'account':
            metrics = await self.calculate_account_performance(
                entity_id, start_date, end_date
            )
        else:
            raise ValueError(f"不支持的实体类型: {entity_type}，请使用 'strategy' 或 'account'")

        return metrics.to_dict()

    # =========================================================================
    # 私有方法 — 数据获取与重建
    # =========================================================================

    async def _get_strategy_equity_curve(
            self,
            strategy_id: str,
            start_date: date,
            end_date: date
    ) -> List[Dict[str, Any]]:
        """获取策略的净值曲线

        从 trade_repo 获取策略在区间内的所有交易记录，
        按时间顺序重建每日净值。

        Args:
            strategy_id: 策略 ID
            start_date: 起始日期
            end_date: 结束日期

        Returns:
            List[Dict]: 每日净值记录 [{trade_date, equity, cash, market_value}, ...]
        """
        if start_date is None:
            start_date = date.today() - timedelta(days=365)
        if end_date is None:
            end_date = date.today()
        start_dt = datetime.combine(start_date, datetime.min.time())
        end_dt = datetime.combine(end_date, datetime.max.time())
        trades = await self.trade_repo.get_by_strategy_id(
            strategy_id, start_dt, end_dt, limit=100000
        )

        if not trades:
            # v1.3: 无交易记录时，回退到 backtest_equity_curves 表读取净值
            return await self._get_equity_from_backtest_curves(
                strategy_id, start_date, end_date
            )

        # 尝试从关联账户获取实际初始资金
        initial_capital = 1000000.0
        try:
            from sqlalchemy import select as _select
            from shared.database.models.business_models import Order
            result = await self.session.execute(
                _select(Order.account_id).where(
                    Order.strategy_id == strategy_id
                ).limit(1)
            )
            row = result.first()
            if row:
                account = await self.account_repo.get(row.account_id)
                if account and account.initial_balance:
                    initial_capital = float(account.initial_balance)
        except Exception:
            pass

        return await self._reconstruct_equity_curve(
            trades, start_date, end_date, initial_capital
        )

    async def _get_equity_from_backtest_curves(
            self,
            strategy_id: str,
            start_date: date,
            end_date: date,
    ) -> list:
        """
        v1.3: 无交易记录时，从 backtest_equity_curves 表读取净值曲线。

        查询该策略最近一次完成的回测任务，读取其净值曲线数据。
        """
        try:
            from shared.database.repositories.strategy.backtest.task_repo import \
                BacktestTaskRepository
            from shared.database.repositories.strategy.backtest.backtest_equity_curve_repo import \
                BacktestEquityCurveRepository

            task_repo = BacktestTaskRepository(self.session)
            equity_repo = BacktestEquityCurveRepository(self.session)

            # 查找最近一次完成的回测
            tasks, _ = await task_repo.get_list(
                filters={"strategy_id": strategy_id, "status": "completed"},
                page=1, page_size=1,
            )
            if not tasks:
                return []

            task_id = tasks[0].id
            curves = await equity_repo.get_equity_curve(
                task_id, start_date, end_date
            )
            if not curves:
                return []

            return [
                {
                    "trade_date": c.trade_date.date() if hasattr(c.trade_date, "date") else c.trade_date,
                    "equity": float(c.equity),
                    "cash": float(c.cash) if c.cash else 0.0,
                    "market_value": float(c.market_value) if c.market_value else 0.0,
                }
                for c in curves
            ]
        except Exception:
            return []

    async def _reconstruct_equity_curve(
            self,
            trades,
            start_date: date,
            end_date: date,
            initial_capital: float = 1000000.0
    ) -> list:
        """从交易记录重建每日净值曲线（平均成本法）

        按时间顺序处理每笔成交：BUY 增加成本基础，SELL 按平均成本比例减少。
        无实时行情时，未平仓持仓按成本计价。equity = cash + cost_basis。

        Args:
            trades: Trade ORM 对象列表
            start_date: 起始日期
            end_date: 结束日期
            initial_capital: 初始资金

        Returns:
            list: [{trade_date, equity, cash, market_value}, ...] 按日期排序
        """
        if not trades:
            return [{
                'trade_date': start_date,
                'equity': round(initial_capital, 2),
                'cash': round(initial_capital, 2),
                'market_value': 0.0,
            }]

        # 按交易时间排序
        sorted_trades = sorted(trades, key=lambda t: t.trade_time)

        # 批量查询 direction（Trade 表无 direction，需从 Order 表获取）
        from shared.database.models.business_models import Order
        from sqlalchemy import select as _select
        order_ids = list({t.order_id for t in sorted_trades})
        direction_map = {}
        if order_ids:
            result = await self.session.execute(
                _select(Order).where(Order.order_id.in_(order_ids))
            )
            for order in result.scalars().all():
                direction_map[order.order_id] = order.direction

        # 按日期分组交易
        from collections import defaultdict
        day_trades = defaultdict(list)
        for t in sorted_trades:
            td = t.trade_time.date()
            day_trades[td].append(t)

        # 平均成本法持仓跟踪: {ts_code: {'volume': int, 'cost': float}}
        positions = {}
        cash = initial_capital
        curve = []
        all_dates = sorted(day_trades.keys())

        # 起始日净值点（首个交易日 > start_date 时补一条初始点）
        if all_dates[0] > start_date:
            curve.append({
                'trade_date': start_date,
                'equity': round(initial_capital, 2),
                'cash': round(initial_capital, 2),
                'market_value': 0.0,
            })

        for trade_date in all_dates:
            for t in day_trades[trade_date]:
                direction = direction_map.get(t.order_id, 'buy')
                price = float(t.price)
                volume = int(t.volume)
                commission = float(t.commission or 0)
                tax = float(t.tax or 0)

                if direction == 'buy':
                    trade_cost = price * volume + commission + tax
                    cash -= trade_cost
                    pos = positions.setdefault(t.ts_code, {'volume': 0, 'cost': 0.0})
                    pos['volume'] += volume
                    pos['cost'] += trade_cost
                else:
                    trade_proceeds = price * volume - commission - tax
                    cash += trade_proceeds
                    pos = positions.get(t.ts_code)
                    if pos and pos['volume'] > 0:
                        sell_ratio = min(volume / pos['volume'], 1.0)
                        pos['cost'] -= pos['cost'] * sell_ratio
                        pos['volume'] -= volume
                        if pos['volume'] <= 0:
                            del positions[t.ts_code]

            market_value = sum(p['cost'] for p in positions.values())
            equity = cash + market_value

            curve.append({
                'trade_date': trade_date,
                'equity': round(equity, 2),
                'cash': round(cash, 2),
                'market_value': round(market_value, 2),
            })

        # 结束日净值点（前向填充）
        if curve and curve[-1]['trade_date'] < end_date:
            last = curve[-1]
            curve.append({
                'trade_date': end_date,
                'equity': last['equity'],
                'cash': last['cash'],
                'market_value': last['market_value'],
            })

        return curve

    async def _get_benchmark_returns(
            self,
            benchmark_code: str,
            start_date: date,
            end_date: date
    ) -> pd.Series:
        """获取基准指数的日收益率序列

        从 quote_repo 获取基准指数的日线行情数据，
        计算收盘价的日收益率（pct_change）。

        Args:
            benchmark_code: 基准指数代码（如 "000300.SH"）
            start_date: 起始日期
            end_date: 结束日期

        Returns:
            pd.Series: 日收益率序列，index=日期。数据不足时返回空 Series
        """
        try:
            benchmark_data = await self.quote_repo.get_daily_quotes(
                benchmark_code, start_date, end_date
            )

            if not benchmark_data:
                logger.warning(f"基准数据不存在: {benchmark_code}")
                return pd.Series()

            # 转换为 DataFrame 并计算日收益率
            df_benchmark = pd.DataFrame([
                {
                    'trade_date': data.trade_date,
                    'close': data.close
                }
                for data in benchmark_data
            ])

            df_benchmark['trade_date'] = pd.to_datetime(df_benchmark['trade_date'])
            df_benchmark.set_index('trade_date', inplace=True)

            returns = df_benchmark['close'].pct_change().dropna()

            return returns

        except Exception as e:
            logger.warning(f"获取基准收益率失败 ({benchmark_code}): {str(e)}")
            return pd.Series()

    async def _get_trade_statistics(
            self,
            strategy_id: str,
            start_date: date,
            end_date: date
    ) -> Dict[str, Any]:
        """获取策略的交易统计信息

        基于交易记录的 pnl 字段将交易分为盈利/亏损两类，
        计算胜率、盈亏比、平均盈利和平均亏损。

        Args:
            strategy_id: 策略 ID
            start_date: 起始日期
            end_date: 结束日期

        Returns:
            Dict: {total_trades, winning_trades, losing_trades,
                   win_rate, profit_factor, average_win, average_loss}
        """
        trades = await self.trade_repo.get_by_strategy(
            strategy_id, start_date, end_date
        )

        if not trades:
            return {
                'total_trades': 0,
                'winning_trades': 0,
                'losing_trades': 0,
                'win_rate': 0.0,
                'profit_factor': 0.0,
                'average_win': 0.0,
                'average_loss': 0.0
            }

        # 按 pnl 正负分类
        winning_trades = []
        losing_trades = []

        for trade in trades:
            if hasattr(trade, 'pnl') and trade.pnl > 0:
                winning_trades.append(trade)
            else:
                losing_trades.append(trade)

        # 计算统计指标
        total_profit = sum(t.pnl for t in winning_trades) if winning_trades else 0
        total_loss = abs(sum(t.pnl for t in losing_trades)) if losing_trades else 0

        win_rate = len(winning_trades) / len(trades) if trades else 0
        profit_factor = total_profit / total_loss if total_loss > 0 else 0
        average_win = total_profit / len(winning_trades) if winning_trades else 0
        average_loss = total_loss / len(losing_trades) if losing_trades else 0

        return {
            'total_trades': len(trades),
            'winning_trades': len(winning_trades),
            'losing_trades': len(losing_trades),
            'win_rate': win_rate,
            'profit_factor': profit_factor,
            'average_win': average_win,
            'average_loss': average_loss
        }

    async def _get_earliest_date(
            self,
            entity_type: str,
            entity_id: str
    ) -> date:
        """获取实体最早数据日期

        用于 'all' 时间段，查找该策略或账户的第一笔交易/快照日期。
        无数据时默认返回 1 年前。

        Args:
            entity_type: 'strategy' 或 'account'
            entity_id: 实体 ID

        Returns:
            date: 最早数据日期
        """
        try:
            if entity_type == 'strategy':
                trades = await self.trade_repo.get_by_strategy(entity_id, None, None)
                if trades:
                    dlist = [getattr(t, 'trade_time', None) for t in trades]
                    dlist = [d.date() if hasattr(d, 'date') else d for d in dlist if d]
                    if dlist:
                        return min(dlist)
            elif entity_type == 'account':
                snaps = await self.account_repo.get_daily_snapshots(
                    entity_id, None, date.today()
                )
                if snaps:
                    dlist = [s.trade_date for s in snaps if getattr(s, 'trade_date', None)]
                    if dlist:
                        return min(dlist)
            return date.today() - timedelta(days=365)
        except (ValueError, TypeError):
            return date.today() - timedelta(days=365)

    # =========================================================================
    # 静态方法 — 辅助计算
    # =========================================================================

    @staticmethod
    def _calculate_monthly_returns(df_equity: pd.DataFrame) -> Dict[str, float]:
        """计算月度收益率

        通过月末净值计算月度收益率：monthly_return = month_end / prev_month_end - 1

        Args:
            df_equity: 含 'equity' 列的 DataFrame，index 为日期

        Returns:
            Dict[str, float]: {YYYY-MM: return}
        """
        if len(df_equity) == 0:
            return {}

        # 取每月最后交易日的净值
        monthly_df = df_equity['equity'].resample('M').last()
        monthly_returns = monthly_df.pct_change().dropna()

        return {
            str(dt)[:7]: ret
            for dt, ret in monthly_returns.items()
        }