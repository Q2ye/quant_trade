#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
绩效分析服务

负责计算和管理策略/账户的绩效指标，包括收益、风险、夏普比率等。
使用共享Repository进行数据访问，处理业务逻辑。
"""

from decimal import Decimal
from typing import Dict, List, Optional, Tuple, Any
from datetime import datetime, date, timedelta
import asyncio
import numpy as np
import pandas as pd
from sqlalchemy.ext.asyncio import AsyncSession

from modules.analysis.models import PerformanceMetrics
from shared.database.repositories.base import BaseRepository
from shared.database.repositories.strategy_repo import StrategyRepository
from shared.database.repositories.account_repo import AccountRepository
from shared.database.repositories.backtest_repo import BacktestRepository
from shared.database.repositories.trade_repo import TradeRepository
from shared.database.repositories.quote_repo import QuoteRepository
from core.utils.math_utils.statistic_calculator import StatisticCalculator
from core.utils.math_utils.financial_calculator import FinancialCalculator


class PerformanceService:
	"""绩效分析服务"""

	def __init__ (
			self,
			session: AsyncSession,
			strategy_repo: StrategyRepository = None,
			account_repo: AccountRepository = None,
			backtest_repo: BacktestRepository = None,
			trade_repo: TradeRepository = None,
			quote_repo: QuoteRepository = None
	):
		"""
		初始化绩效服务

		Args:
			session: 数据库会话
			strategy_repo: 策略Repository
			account_repo: 账户Repository
			backtest_repo: 回测Repository
			trade_repo: 交易Repository
			quote_repo: 行情Repository
		"""
		self.session = session
		self.strategy_repo = strategy_repo or StrategyRepository(session)
		self.account_repo = account_repo or AccountRepository(session)
		self.backtest_repo = backtest_repo or BacktestRepository(session)
		self.trade_repo = trade_repo or TradeRepository(session)
		self.quote_repo = quote_repo or QuoteRepository(session)
		self.stat_calc = StatisticCalculator()
		self.fin_calc = FinancialCalculator()

	async def calculate_strategy_performance (
			self,
			strategy_id: str,
			start_date: date,
			end_date: date,
			benchmark: Optional[str] = None
	) -> PerformanceMetrics:
		"""
		计算策略绩效指标

		Args:
			strategy_id: 策略ID
			start_date: 开始日期
			end_date: 结束日期
			benchmark: 基准代码（可选）

		Returns:
			PerformanceMetrics: 绩效指标对象
		"""
		try:
			# 获取策略信息
			strategy = await self.strategy_repo.get(strategy_id)
			if not strategy:
				raise ValueError(f"策略不存在: {strategy_id}")

			# 获取策略的净值曲线
			equity_curve = await self._get_strategy_equity_curve(
				strategy_id, start_date, end_date
			)

			if len(equity_curve) < 2:
				raise ValueError("净值曲线数据不足")

			# 转换为DataFrame
			df_equity = pd.DataFrame(equity_curve)
			df_equity['trade_date'] = pd.to_datetime(df_equity['trade_date'])
			df_equity.set_index('trade_date', inplace=True)

			# 计算收益率序列
			returns = df_equity['equity'].pct_change().dropna()

			# 获取基准收益率（如果提供了基准）
			benchmark_returns = None
			if benchmark:
				benchmark_returns = await self._get_benchmark_returns(
					benchmark, start_date, end_date
				)

			# 计算绩效指标
			total_return = self.fin_calc.calculate_total_return(
				df_equity['equity'].iloc[0],
				df_equity['equity'].iloc[-1]
			)

			annual_return = self.fin_calc.calculate_annual_return(
				returns, trading_days=len(returns)
			)

			cagr = self.fin_calc.calculate_cagr(
				df_equity['equity'].iloc[0],
				df_equity['equity'].iloc[-1],
				(end_date - start_date).days / 365.25
			)

			sharpe_ratio = calculate_sharpe_ratio(
				returns, risk_free_rate=0.03
			)

			volatility = self.fin_calc.calculate_volatility(returns)

			max_drawdown = self.fin_calc.calculate_max_drawdown(
				df_equity['equity'].values
			)

			# 获取交易统计
			trade_stats = await self._get_trade_statistics(
				strategy_id, start_date, end_date
			)

			# 计算Alpha/Beta（如果有基准）
			alpha = beta = tracking_error = r_squared = Decimal("0.0")
			if benchmark_returns is not None and len(benchmark_returns) > 0:
				alpha, beta = self.fin_calc.calculate_alpha_beta(
					returns.values, benchmark_returns.values
				)
				tracking_error = self.fin_calc.calculate_tracking_error(
					returns.values, benchmark_returns.values
				)
				r_squared = self.fin_calc.calculate_r_squared(
					returns.values, benchmark_returns.values
				)

			# 构建绩效指标对象
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
				volatility=Decimal(str(volatility)),
				max_drawdown=Decimal(str(max_drawdown)),
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

			# 添加净值曲线数据
			metrics.equity_curve = [
				{
					'date': row['trade_date'].strftime('%Y-%m-%d'),
					'equity': float(row['equity']),
					'cash': float(row.get('cash', 0)),
					'market_value': float(row.get('market_value', 0))
				}
				for _, row in df_equity.iterrows()
			]

			# 计算月度收益
			if len(df_equity) > 0:
				monthly_returns = self._calculate_monthly_returns(df_equity)
				metrics.monthly_returns = {
					month: Decimal(str(ret))
					for month, ret in monthly_returns.items()
				}

			return metrics

		except Exception as e:
			raise ValueError(f"计算策略绩效失败: {str(e)}")

	async def calculate_account_performance (
			self,
			account_id: int,
			start_date: date,
			end_date: date
	) -> PerformanceMetrics:
		"""
		计算账户绩效指标

		Args:
			account_id: 账户ID
			start_date: 开始日期
			end_date: 结束日期

		Returns:
			PerformanceMetrics: 绩效指标对象
		"""
		try:
			# 获取账户信息
			account = await self.account_repo.get(account_id)
			if not account:
				raise ValueError(f"账户不存在: {account_id}")

			# 获取账户的每日资产快照
			snapshots = await self.account_repo.get_daily_snapshots(
				account_id, start_date, end_date
			)

			if len(snapshots) < 2:
				raise ValueError("账户快照数据不足")

			# 构建资产曲线
			equity_curve = []
			for snapshot in snapshots:
				equity_curve.append({
					'trade_date': snapshot.trade_date,
					'equity': snapshot.total_asset,
					'cash': snapshot.cash,
					'market_value': snapshot.market_value
				})

			# 转换为DataFrame
			df_equity = pd.DataFrame(equity_curve)
			df_equity['trade_date'] = pd.to_datetime(df_equity['trade_date'])
			df_equity.set_index('trade_date', inplace=True)

			# 计算收益率序列
			returns = df_equity['equity'].pct_change().dropna()

			# 计算绩效指标（与策略类似，但使用账户数据）
			total_return = self.fin_calc.calculate_total_return(
				df_equity['equity'].iloc[0],
				df_equity['equity'].iloc[-1]
			)

			annual_return = self.fin_calc.calculate_annual_return(
				returns, trading_days=len(returns)
			)

			# 构建基础绩效指标对象
			metrics = PerformanceMetrics(
				strategy_id=None,
				account_id=str(account_id),
				start_date=start_date,
				end_date=end_date,
				total_return=Decimal(str(total_return)),
				annual_return=Decimal(str(annual_return))
			)

			# 填充更多指标...
			# （这里可以调用其他计算方法）

			return metrics

		except Exception as e:
			raise ValueError(f"计算账户绩效失败: {str(e)}")

	async def compare_multiple_strategies (
			self,
			strategy_ids: List[str],
			start_date: date,
			end_date: date,
			benchmark: Optional[str] = None
	) -> Dict[str, PerformanceMetrics]:
		"""
		比较多个策略的绩效

		Args:
			strategy_ids: 策略ID列表
			start_date: 开始日期
			end_date: 结束日期
			benchmark: 基准代码

		Returns:
			各策略的绩效指标字典
		"""
		results = {}

		# 并行计算每个策略的绩效
		tasks = []
		for strategy_id in strategy_ids:
			task = self.calculate_strategy_performance(
				strategy_id, start_date, end_date, benchmark
			)
			tasks.append(task)

		# 等待所有任务完成
		all_results = await asyncio.gather(*tasks, return_exceptions=True)

		for i, result in enumerate(all_results):
			if isinstance(result, Exception):
				print(f"计算策略 {strategy_ids[i]} 绩效失败: {str(result)}")
			else:
				results[strategy_ids[i]] = result

		return results

	async def _get_strategy_equity_curve (
			self,
			strategy_id: str,
			start_date: date,
			end_date: date
	) -> List[Dict[str, Any]]:
		"""
		获取策略的净值曲线

		Args:
			strategy_id: 策略ID
			start_date: 开始日期
			end_date: 结束日期

		Returns:
			净值曲线数据列表
		"""
		# 优先从回测结果获取
		backtest_tasks = await self.backtest_repo.get_by_strategy(
			strategy_id, start_date, end_date
		)

		if backtest_tasks:
			# 使用最新的回测结果
			latest_task = max(backtest_tasks, key=lambda x: x.created_at)
			equity_curve = await self.backtest_repo.get_equity_curve(
				latest_task.id
			)

			if equity_curve:
				return [
					{
						'trade_date': curve.trade_date,
						'equity': curve.equity,
						'cash': curve.cash,
						'market_value': curve.market_value
					}
					for curve in equity_curve
				]

		# 如果没有回测结果，从实盘交易重建
		trades = await self.trade_repo.get_by_strategy(
			strategy_id, start_date, end_date
		)

		if not trades:
			return []

		# 重建净值曲线（简化实现）
		# 实际应用中可能需要更复杂的逻辑
		return await self._reconstruct_equity_curve(trades, start_date, end_date)

	async def _get_benchmark_returns (
			self,
			benchmark_code: str,
			start_date: date,
			end_date: date
	) -> pd.Series:
		"""
		获取基准收益率序列

		Args:
			benchmark_code: 基准代码（如 '000300.SH'）
			start_date: 开始日期
			end_date: 结束日期

		Returns:
			基准收益率序列
		"""
		try:
			# 获取基准行情数据
			benchmark_data = await self.quote_repo.get_daily_quotes(
				benchmark_code, start_date, end_date
			)

			if not benchmark_data:
				raise ValueError(f"基准数据不存在: {benchmark_code}")

			# 转换为DataFrame
			df_benchmark = pd.DataFrame([
				{
					'trade_date': data.trade_date,
					'close': data.close
				}
				for data in benchmark_data
			])

			df_benchmark['trade_date'] = pd.to_datetime(df_benchmark['trade_date'])
			df_benchmark.set_index('trade_date', inplace=True)

			# 计算收益率
			returns = df_benchmark['close'].pct_change().dropna()

			return returns

		except Exception as e:
			print(f"获取基准收益率失败: {str(e)}")
			return pd.Series()

	async def _get_trade_statistics (
			self,
			strategy_id: str,
			start_date: date,
			end_date: date
	) -> Dict[str, Any]:
		"""
		获取交易统计信息

		Args:
			strategy_id: 策略ID
			start_date: 开始日期
			end_date: 结束日期

		Returns:
			交易统计字典
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

		# 计算盈利交易和亏损交易
		winning_trades = []
		losing_trades = []

		for trade in trades:
			# 假设trade对象有pnl属性
			if hasattr(trade, 'pnl') and trade.pnl > 0:
				winning_trades.append(trade)
			else:
				losing_trades.append(trade)

		# 计算总盈利和总亏损
		total_profit = sum(t.pnl for t in winning_trades) if winning_trades else 0
		total_loss = abs(sum(t.pnl for t in losing_trades)) if losing_trades else 0

		# 计算各项指标
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

	def _calculate_monthly_returns (
			self,
			df_equity: pd.DataFrame
	) -> Dict[str, float]:
		"""
		计算月度收益率

		Args:
			df_equity: 资产DataFrame

		Returns:
			月度收益率字典 {YYYY-MM: return}
		"""
		if len(df_equity) == 0:
			return {}

		# 重采样到月度
		monthly_df = df_equity['equity'].resample('M').last()

		# 计算月度收益率
		monthly_returns = monthly_df.pct_change().dropna()

		return {
			date.strftime('%Y-%m'): ret
			for date, ret in monthly_returns.items()
		}

	async def _reconstruct_equity_curve (
			self,
			trades: List,
			start_date: date,
			end_date: date
	) -> List[Dict[str, Any]]:
		"""
		从交易记录重建净值曲线（简化实现）

		Args:
			trades: 交易记录列表
			start_date: 开始日期
			end_date: 结束日期

		Returns:
			重建的净值曲线
		"""
		# 简化实现：返回空列表
		# 实际应用中需要实现完整的净值重建逻辑
		return []

	async def get_performance_summary (
			self,
			entity_type: str,
			entity_id: str,
			period: str = '1y'
	) -> Dict[str, Any]:
		"""
		获取绩效摘要

		Args:
			entity_type: 实体类型 ('events' 或 'events')
			entity_id: 实体ID
			period: 时间段 ('1m', '3m', '6m', '1y', '3y', '5y', 'all')

		Returns:
			绩效摘要
		"""
		# 根据period计算开始日期
		end_date = date.today()

		if period == '1m':
			start_date = end_date - timedelta(days=30)
		elif period == '3m':
			start_date = end_date - timedelta(days=90)
		elif period == '6m':
			start_date = end_date - timedelta(days=180)
		elif period == '1y':
			start_date = end_date - timedelta(days=365)
		elif period == '3y':
			start_date = end_date - timedelta(days=1095)
		elif period == '5y':
			start_date = end_date - timedelta(days=1825)
		else:  # 'all' 或其他
			# 获取最早的数据日期
			start_date = await self._get_earliest_date(entity_type, entity_id)

		# 根据实体类型计算绩效
		if entity_type == 'events':
			metrics = await self.calculate_strategy_performance(
				entity_id, start_date, end_date
			)
		elif entity_type == 'events':
			metrics = await self.calculate_account_performance(
				int(entity_id), start_date, end_date
			)
		else:
			raise ValueError(f"不支持的实体类型: {entity_type}")

		return metrics.to_dict()

	async def _get_earliest_date (
			self,
			entity_type: str,
			entity_id: str
	) -> date:
		"""
		获取实体的最早数据日期

		Args:
			entity_type: 实体类型
			entity_id: 实体ID

		Returns:
			最早日期
		"""
		# 简化实现：返回一年前
		return date.today() - timedelta(days=365)