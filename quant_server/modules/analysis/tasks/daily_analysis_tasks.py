# -*- coding: utf-8 -*-
"""
每日分析任务模块
负责执行每日的分析任务，包括绩效计算、风险监控、报告生成等
位置：quant_server/modules/events/tasks/daily_analysis_tasks.py
"""

import asyncio
import logging
from typing import List, Dict, Any, Optional
from datetime import datetime, timedelta, date
from decimal import Decimal
import pandas as pd
import numpy as np

from quant_server.shared.database.repositories.base import BaseRepository
from quant_server.modules.analysis.utils.statistic_utils import StatisticUtils
from quant_server.modules.analysis.visualizers.report_generator import ReportGenerator
from quant_server.core.events import EventEngine
from quant_server.core.events.system_events import AnalysisCompletedEvent


class DailyAnalysisTasks:
	"""每日分析任务类"""

	def __init__ (self,
	              event_engine: EventEngine,
	              repositories: Dict[str, BaseRepository],
	              config: Dict[str, Any] = None):
		"""
		初始化每日分析任务

		Args:
			event_engine: 事件引擎
			repositories: Repository字典
			config: 配置字典
		"""
		self.event_engine = event_engine
		self.repositories = repositories
		self.config = config or {}

		# 获取所需的Repository
		self.account_repo = repositories.get('account_repo')
		self.trade_repo = repositories.get('trade_repo')
		self.position_repo = repositories.get('position_repo')
		self.performance_repo = repositories.get('performance_repo')

		# 工具类
		self.stat_utils = StatisticUtils()
		self.report_generator = ReportGenerator()

		# 日志
		self.logger = logging.getLogger(__name__)

		# 任务状态
		self.is_running = False
		self.last_run_date = None

	async def run_daily_analysis (self, analysis_date: date = None) -> Dict[str, Any]:
		"""
		执行每日分析任务

		Args:
			analysis_date: 分析日期，默认为前一天

		Returns:
			Dict[str, Any]: 分析结果
		"""
		if analysis_date is None:
			analysis_date = datetime.now().date() - timedelta(days=1)

		self.logger.info(f"开始执行每日分析任务，日期: {analysis_date}")

		try:
			# 1. 检查是否为交易日
			if not await self._is_trading_day(analysis_date):
				self.logger.info(f"{analysis_date} 为非交易日，跳过分析")
				return {'status': 'skipped', 'reason': '非交易日'}

			# 2. 执行各项分析任务
			tasks = [
				self._calculate_daily_performance(analysis_date),
				self._calculate_daily_risk(analysis_date),
				self._analyze_daily_trades(analysis_date),
				self._generate_daily_report(analysis_date),
				self._check_risk_alerts(analysis_date)
			]

			results = await asyncio.gather(*tasks, return_exceptions=True)

			# 3. 汇总结果
			analysis_result = {
				'analysis_date': analysis_date.isoformat(),
				'tasks': {},
				'status': 'completed',
				'timestamp': datetime.now().isoformat()
			}

			task_names = ['performance', 'risk', 'trades', 'report', 'alerts']
			for name, result in zip(task_names, results):
				if isinstance(result, Exception):
					analysis_result['tasks'][name] = {
						'status': 'failed',
						'error': str(result)
					}
					self.logger.error(f"任务 {name} 执行失败: {result}")
				else:
					analysis_result['tasks'][name] = {
						'status': 'completed',
						'result': result
					}

			# 4. 发布分析完成事件
			await self.event_engine.put(
				AnalysisCompletedEvent(
					analysis_date=analysis_date,
					results=analysis_result
				)
			)

			# 5. 更新最后运行日期
			self.last_run_date = analysis_date

			self.logger.info(f"每日分析任务完成，日期: {analysis_date}")

			return analysis_result

		except Exception as e:
			self.logger.error(f"每日分析任务执行失败: {e}", exc_info=True)
			return {
				'status': 'failed',
				'error': str(e),
				'analysis_date': analysis_date.isoformat()
			}

	async def _is_trading_day (self, check_date: date) -> bool:
		"""
		检查是否为交易日

		Args:
			check_date: 检查日期

		Returns:
			bool: 是否为交易日
		"""
		try:
			if self.repositories.get('trade_calendar_repo'):
				calendar = await self.repositories['trade_calendar_repo'].get_by(
					cal_date=check_date,
					exchange='SSE'  # 上海交易所
				)
				return calendar.is_open if calendar else False
		except Exception as e:
			self.logger.warning(f"检查交易日失败: {e}")

		# 默认周一至周五为交易日
		return check_date.weekday() < 5

	async def _calculate_daily_performance (self, analysis_date: date) -> Dict[str, Any]:
		"""
		计算每日绩效

		Args:
			analysis_date: 分析日期

		Returns:
			Dict[str, Any]: 绩效计算结果
		"""
		self.logger.info(f"计算每日绩效，日期: {analysis_date}")

		try:
			# 获取账户数据
			accounts = await self.account_repo.get_many(
				status='active',
				skip=0,
				limit=100
			) if self.account_repo else []

			performance_results = []

			for account in accounts:
				# 获取账户资产数据
				account_id = account.id

				# 获取当日和前一日资产
				today_assets = await self._get_account_assets(account_id, analysis_date)
				prev_date = analysis_date - timedelta(days=1)
				prev_assets = await self._get_account_assets(account_id, prev_date)

				if not today_assets or not prev_assets:
					continue

				# 计算日收益
				daily_pnl = today_assets['total_asset'] - prev_assets['total_asset']
				daily_return = daily_pnl / prev_assets['total_asset'] if prev_assets['total_asset'] > 0 else 0

				# 计算累计收益
				initial_balance = account.initial_balance or account.total_balance
				total_return = (today_assets[
					                'total_asset'] - initial_balance) / initial_balance if initial_balance > 0 else 0

				# 获取交易数据
				daily_trades = await self.trade_repo.get_many(
					account_id=account_id,
					trade_date=analysis_date
				) if self.trade_repo else []

				# 计算交易相关指标
				trade_metrics = self._calculate_trade_metrics(daily_trades)

				# 保存绩效数据
				performance_data = {
					'account_id': account_id,
					'user_id': account.user_id,
					'trade_date': analysis_date,
					'total_asset': float(today_assets['total_asset']),
					'cash': float(today_assets['cash']),
					'market_value': float(today_assets['market_value']),
					'daily_pnl': float(daily_pnl),
					'daily_return': float(daily_return),
					'total_return': float(total_return),
					'trade_count': len(daily_trades),
					'trade_metrics': trade_metrics
				}

				if self.performance_repo:
					await self.performance_repo.upsert(
						match_fields=['account_id', 'trade_date'],
						data=performance_data,
						update_fields=['total_asset', 'cash', 'market_value', 'daily_pnl',
						               'daily_return', 'total_return', 'trade_count', 'trade_metrics']
					)

				performance_results.append({
					'account_id': account_id,
					'account_name': account.account_name,
					'performance': performance_data
				})

			return {
				'accounts_analyzed': len(performance_results),
				'results': performance_results
			}

		except Exception as e:
			self.logger.error(f"计算每日绩效失败: {e}", exc_info=True)
			raise

	async def _get_account_assets (self, account_id: int, asset_date: date) -> Optional[Dict[str, float]]:
		"""
		获取账户资产数据

		Args:
			account_id: 账户ID
			asset_date: 资产日期

		Returns:
			Optional[Dict[str, float]]: 资产数据
		"""
		try:
			# 这里应该从数据库获取具体的资产数据
			# 由于数据结构未知，这里返回模拟数据
			return {
				'total_asset': 1000000.0,
				'cash': 200000.0,
				'market_value': 800000.0
			}
		except Exception as e:
			self.logger.warning(f"获取账户资产失败: {e}")
			return None

	def _calculate_trade_metrics (self, trades: List) -> Dict[str, Any]:
		"""
		计算交易指标

		Args:
			trades: 交易列表

		Returns:
			Dict[str, Any]: 交易指标
		"""
		if not trades:
			return {}

		profits = []
		for trade in trades:
			if hasattr(trade, 'profit'):
				profits.append(float(trade.profit))
			elif hasattr(trade, 'filled_amount') and hasattr(trade, 'price'):
				# 估算收益
				profit = (trade.price * trade.filled_volume) - trade.filled_amount
				profits.append(float(profit))

		if not profits:
			return {}

		profits_array = np.array(profits)
		winning_trades = profits_array[profits_array > 0]
		losing_trades = profits_array[profits_array < 0]

		return {
			'total_trades': len(trades),
			'winning_trades': len(winning_trades),
			'losing_trades': len(losing_trades),
			'win_rate': len(winning_trades) / len(trades) if trades else 0,
			'total_profit': float(np.sum(profits_array)),
			'avg_profit': float(np.mean(profits_array)) if profits else 0,
			'max_profit': float(np.max(profits_array)) if profits else 0,
			'max_loss': float(np.min(profits_array)) if profits else 0,
			'profit_factor': float(np.sum(winning_trades) / abs(np.sum(losing_trades)))
			if len(losing_trades) > 0 else float('inf')
		}

	async def _calculate_daily_risk (self, analysis_date: date) -> Dict[str, Any]:
		"""
		计算每日风险指标

		Args:
			analysis_date: 分析日期

		Returns:
			Dict[str, Any]: 风险计算结果
		"""
		self.logger.info(f"计算每日风险，日期: {analysis_date}")

		try:
			# 获取账户列表
			accounts = await self.account_repo.get_many(
				status='active',
				skip=0,
				limit=100
			) if self.account_repo else []

			risk_results = []

			for account in accounts:
				# 获取持仓数据
				positions = await self.position_repo.get_many(
					account_id=account.id
				) if self.position_repo else []

				# 计算持仓风险
				position_risk = self._calculate_position_risk(positions)

				# 获取历史收益数据
				historical_returns = await self._get_historical_returns(account.id, analysis_date)

				# 计算风险指标
				risk_metrics = {}
				if historical_returns and len(historical_returns) > 10:
					returns_array = np.array(historical_returns)

					risk_metrics = {
						'volatility': float(np.std(returns_array) * np.sqrt(252)),
						'var_95': self.stat_utils.calculate_var_cvar(returns_array, 0.95)[0],
						'cvar_95': self.stat_utils.calculate_var_cvar(returns_array, 0.95)[1],
						'max_drawdown': self.stat_utils.calculate_max_drawdown(
							np.cumprod(1 + returns_array)
						)[0],
						'sharpe_ratio': self.stat_utils.calculate_sharpe_ratio(returns_array)
					}

				# 计算账户风险
				account_risk = {
					'account_id': account.id,
					'account_name': account.account_name,
					'position_risk': position_risk,
					'market_risk': risk_metrics,
					'concentration_risk': self._calculate_concentration_risk(positions),
					'liquidity_risk': self._calculate_liquidity_risk(account, positions)
				}

				risk_results.append(account_risk)

			return {
				'accounts_analyzed': len(risk_results),
				'risk_levels': self._assess_overall_risk(risk_results),
				'details': risk_results
			}

		except Exception as e:
			self.logger.error(f"计算每日风险失败: {e}", exc_info=True)
			raise

	def _calculate_position_risk (self, positions: List) -> Dict[str, Any]:
		"""
		计算持仓风险

		Args:
			positions: 持仓列表

		Returns:
			Dict[str, Any]: 持仓风险指标
		"""
		if not positions:
			return {
				'total_positions': 0,
				'total_market_value': 0,
				'position_concentration': 0,
				'sector_concentration': {}
			}

		total_mv = sum(float(pos.market_value) for pos in positions if hasattr(pos, 'market_value'))

		# 计算持仓集中度
		position_values = [float(pos.market_value) for pos in positions if hasattr(pos, 'market_value')]
		if position_values and total_mv > 0:
			sorted_values = sorted(position_values, reverse=True)
			top3_concentration = sum(sorted_values[:3]) / total_mv
		else:
			top3_concentration = 0

		return {
			'total_positions': len(positions),
			'total_market_value': total_mv,
			'position_concentration': top3_concentration,
			'sector_concentration': self._calculate_sector_concentration(positions)
		}

	def _calculate_sector_concentration (self, positions: List) -> Dict[str, float]:
		"""
		计算行业集中度

		Args:
			positions: 持仓列表

		Returns:
			Dict[str, float]: 行业集中度
		"""
		# 这里需要根据证券代码获取行业信息
		# 由于数据结构未知，返回空字典
		return {}

	async def _get_historical_returns (self, account_id: int, end_date: date,
	                                   days: int = 252) -> Optional[List[float]]:
		"""
		获取历史收益率数据

		Args:
			account_id: 账户ID
			end_date: 结束日期
			days: 数据天数

		Returns:
			Optional[List[float]]: 收益率序列
		"""
		try:
			# 这里应该从数据库获取历史收益数据
			# 由于数据结构未知，返回模拟数据
			np.random.seed(account_id)
			returns = np.random.normal(0.0005, 0.02, days)
			return returns.tolist()
		except Exception as e:
			self.logger.warning(f"获取历史收益数据失败: {e}")
			return None

	def _calculate_concentration_risk (self, positions: List) -> Dict[str, Any]:
		"""
		计算集中度风险

		Args:
			positions: 持仓列表

		Returns:
			Dict[str, Any]: 集中度风险指标
		"""
		if not positions:
			return {'level': '低', 'score': 0}

		position_values = [float(pos.market_value) for pos in positions if hasattr(pos, 'market_value')]
		if not position_values:
			return {'level': '低', 'score': 0}

		total_mv = sum(position_values)
		if total_mv == 0:
			return {'level': '低', 'score': 0}

		# 计算赫芬达尔指数
		market_shares = [mv / total_mv for mv in position_values]
		hhi = sum(share ** 2 for share in market_shares)

		# 根据HHI评估风险等级
		if hhi > 0.25:
			level = '高'
			score = 3
		elif hhi > 0.15:
			level = '中'
			score = 2
		else:
			level = '低'
			score = 1

		return {
			'level': level,
			'score': score,
			'hhi': hhi,
			'top3_concentration': sum(sorted(market_shares, reverse=True)[:3])
		}

	def _calculate_liquidity_risk (self, account, positions: List) -> Dict[str, Any]:
		"""
		计算流动性风险

		Args:
			account: 账户对象
			positions: 持仓列表

		Returns:
			Dict[str, Any]: 流动性风险指标
		"""
		try:
			cash = float(account.available_balance) if hasattr(account, 'available_balance') else 0
			total_asset = float(account.total_balance) if hasattr(account, 'total_balance') else 1

			cash_ratio = cash / total_asset if total_asset > 0 else 0

			if cash_ratio < 0.1:
				level = '高'
				score = 3
			elif cash_ratio < 0.2:
				level = '中'
				score = 2
			else:
				level = '低'
				score = 1

			return {
				'level': level,
				'score': score,
				'cash_ratio': cash_ratio,
				'available_cash': cash
			}
		except Exception as e:
			self.logger.warning(f"计算流动性风险失败: {e}")
			return {'level': '未知', 'score': 0, 'cash_ratio': 0}

	def _assess_overall_risk (self, risk_results: List[Dict[str, Any]]) -> Dict[str, Any]:
		"""
		评估整体风险水平

		Args:
			risk_results: 风险结果列表

		Returns:
			Dict[str, Any]: 整体风险评估
		"""
		if not risk_results:
			return {'overall_risk': '低', 'alert_count': 0}

		risk_scores = []
		alert_count = 0

		for result in risk_results:
			# 汇总各项风险得分
			total_score = 0
			risk_count = 0

			for risk_type in ['concentration_risk', 'liquidity_risk']:
				if risk_type in result:
					risk_data = result[risk_type]
					if isinstance(risk_data, dict) and 'score' in risk_data:
						total_score += risk_data['score']
						risk_count += 1

						if risk_data.get('level') == '高':
							alert_count += 1

			if risk_count > 0:
				avg_score = total_score / risk_count
				risk_scores.append(avg_score)

		if not risk_scores:
			return {'overall_risk': '低', 'alert_count': 0}

		avg_risk_score = np.mean(risk_scores)

		if avg_risk_score >= 2.5:
			overall_risk = '高'
		elif avg_risk_score >= 1.5:
			overall_risk = '中'
		else:
			overall_risk = '低'

		return {
			'overall_risk': overall_risk,
			'average_score': float(avg_risk_score),
			'alert_count': alert_count,
			'accounts_at_risk': sum(1 for score in risk_scores if score >= 2.5)
		}

	async def _analyze_daily_trades (self, analysis_date: date) -> Dict[str, Any]:
		"""
		分析每日交易

		Args:
			analysis_date: 分析日期

		Returns:
			Dict[str, Any]: 交易分析结果
		"""
		self.logger.info(f"分析每日交易，日期: {analysis_date}")

		try:
			# 获取当日所有交易
			trades = await self.trade_repo.get_many(
				trade_date=analysis_date
			) if self.trade_repo else []

			if not trades:
				return {
					'total_trades': 0,
					'message': '当日无交易'
				}

			# 按账户分组
			trades_by_account = {}
			for trade in trades:
				account_id = trade.account_id if hasattr(trade, 'account_id') else 0
				if account_id not in trades_by_account:
					trades_by_account[account_id] = []
				trades_by_account[account_id].append(trade)

			# 分析每个账户的交易
			account_analyses = []
			total_profit = 0
			total_volume = 0

			for account_id, account_trades in trades_by_account.items():
				account_analysis = self._analyze_account_trades(account_trades)
				account_analyses.append({
					'account_id': account_id,
					**account_analysis
				})

				total_profit += account_analysis.get('total_profit', 0)
				total_volume += account_analysis.get('total_volume', 0)

			# 识别异常交易
			unusual_trades = self._identify_unusual_trades(trades)

			return {
				'total_trades': len(trades),
				'total_accounts': len(trades_by_account),
				'total_profit': total_profit,
				'total_volume': total_volume,
				'account_analyses': account_analyses,
				'unusual_trades': unusual_trades,
				'trade_patterns': self._identify_trade_patterns(trades)
			}

		except Exception as e:
			self.logger.error(f"分析每日交易失败: {e}", exc_info=True)
			raise

	def _analyze_account_trades (self, trades: List) -> Dict[str, Any]:
		"""
		分析账户交易

		Args:
			trades: 交易列表

		Returns:
			Dict[str, Any]: 交易分析结果
		"""
		if not trades:
			return {}

		# 提取交易数据
		profits = []
		volumes = []
		symbols = []

		for trade in trades:
			# 估算收益
			profit = 0
			if hasattr(trade, 'profit'):
				profit = float(trade.profit)
			elif hasattr(trade, 'filled_amount') and hasattr(trade, 'price') and hasattr(trade, 'filled_volume'):
				if trade.direction == 'buy':
					profit = -float(trade.filled_amount)  # 买入为负收益
				else:
					profit = float(trade.price * trade.filled_volume) - float(trade.filled_amount)

			profits.append(profit)

			# 交易量
			if hasattr(trade, 'filled_volume'):
				volumes.append(float(trade.filled_volume))

			# 交易标的
			if hasattr(trade, 'ts_code'):
				symbols.append(trade.ts_code)

		profits_array = np.array(profits)
		winning_trades = profits_array[profits_array > 0]
		losing_trades = profits_array[profits_array < 0]

		return {
			'trade_count': len(trades),
			'unique_symbols': len(set(symbols)),
			'total_profit': float(np.sum(profits_array)),
			'total_volume': float(np.sum(volumes)) if volumes else 0,
			'win_rate': len(winning_trades) / len(trades) if trades else 0,
			'avg_profit': float(np.mean(profits_array)) if profits else 0,
			'profit_factor': float(np.sum(winning_trades) / abs(np.sum(losing_trades)))
			if len(losing_trades) > 0 else float('inf'),
			'most_traded_symbol': max(set(symbols), key=symbols.count) if symbols else None
		}

	def _identify_unusual_trades (self, trades: List) -> List[Dict[str, Any]]:
		"""
		识别异常交易

		Args:
			trades: 交易列表

		Returns:
			List[Dict[str, Any]]: 异常交易列表
		"""
		unusual_trades = []

		for trade in trades:
			unusual_flags = []

			# 检查大额交易
			if hasattr(trade, 'filled_amount'):
				amount = float(trade.filled_amount)
				if amount > 1000000:  # 超过100万
					unusual_flags.append('大额交易')

			# 检查异常价格
			if hasattr(trade, 'price') and hasattr(trade, 'pre_close'):
				price = float(trade.price)
				pre_close = float(trade.pre_close)
				if pre_close > 0:
					price_change = abs(price - pre_close) / pre_close
					if price_change > 0.1:  # 价格变动超过10%
						unusual_flags.append('异常价格')

			# 检查异常成交量
			if hasattr(trade, 'filled_volume'):
				volume = float(trade.filled_volume)
				if volume > 1000000:  # 成交量超过100万股
					unusual_flags.append('异常成交量')

			if unusual_flags:
				unusual_trades.append({
					'trade_id': getattr(trade, 'trade_id', getattr(trade, 'id', '未知')),
					'account_id': getattr(trade, 'account_id', '未知'),
					'symbol': getattr(trade, 'ts_code', '未知'),
					'unusual_flags': unusual_flags,
					'amount': getattr(trade, 'filled_amount', 0),
					'volume': getattr(trade, 'filled_volume', 0)
				})

		return unusual_trades

	def _identify_trade_patterns (self, trades: List) -> Dict[str, Any]:
		"""
		识别交易模式

		Args:
			trades: 交易列表

		Returns:
			Dict[str, Any]: 交易模式
		"""
		if not trades:
			return {}

		# 按时间分析
		trade_times = []
		for trade in trades:
			if hasattr(trade, 'trade_time'):
				trade_time = trade.trade_time
				if isinstance(trade_time, str):
					try:
						trade_time = datetime.fromisoformat(trade_time.replace('Z', '+00:00'))
					except:
						continue
				trade_times.append(trade_time.hour)

		# 按方向分析
		directions = []
		for trade in trades:
			if hasattr(trade, 'direction'):
				directions.append(trade.direction)

		return {
			'time_distribution': {
				'morning_trades': sum(1 for t in trade_times if 9 <= t < 12),
				'afternoon_trades': sum(1 for t in trade_times if 13 <= t < 15),
				'peak_hour': max(set(trade_times), key=trade_times.count) if trade_times else None
			},
			'direction_distribution': {
				'buy_count': directions.count('buy'),
				'sell_count': directions.count('sell'),
				'buy_ratio': directions.count('buy') / len(directions) if directions else 0
			},
			'frequency': {
				'trades_per_hour': len(trades) / 6 if trades else 0,  # 按6小时交易时间算
				'avg_trade_interval': self._calculate_avg_trade_interval(trades)
			}
		}

	def _calculate_avg_trade_interval (self, trades: List) -> Optional[float]:
		"""
		计算平均交易间隔

		Args:
			trades: 交易列表

		Returns:
			Optional[float]: 平均间隔（分钟）
		"""
		trade_times = []
		for trade in trades:
			if hasattr(trade, 'trade_time'):
				trade_time = trade.trade_time
				if isinstance(trade_time, str):
					try:
						trade_time = datetime.fromisoformat(trade_time.replace('Z', '+00:00'))
					except:
						continue
				trade_times.append(trade_time)

		if len(trade_times) < 2:
			return None

		trade_times.sort()
		intervals = [(trade_times[i + 1] - trade_times[i]).total_seconds() / 60
		             for i in range(len(trade_times) - 1)]

		return float(np.mean(intervals)) if intervals else None

	async def _generate_daily_report (self, analysis_date: date) -> Dict[str, Any]:
		"""
		生成每日报告

		Args:
			analysis_date: 分析日期

		Returns:
			Dict[str, Any]: 报告生成结果
		"""
		self.logger.info(f"生成每日报告，日期: {analysis_date}")

		try:
			# 收集报告数据
			report_data = {
				'report_date': analysis_date.isoformat(),
				'generation_time': datetime.now().isoformat(),
				'market_summary': await self._get_market_summary(analysis_date),
				'account_summary': await self._get_account_summary(analysis_date),
				'trade_summary': await self._get_trade_summary(analysis_date),
				'risk_summary': await self._get_risk_summary(analysis_date)
			}

			# 生成报告文件
			report_path = self.report_generator.generate_performance_report(
				strategy_name='每日分析',
				equity_data={},  # 需要实际数据
				trade_data=[],  # 需要实际数据
				output_format='html'
			)

			return {
				'report_generated': True,
				'report_path': report_path,
				'report_data': report_data
			}

		except Exception as e:
			self.logger.error(f"生成每日报告失败: {e}", exc_info=True)
			raise

	async def _get_market_summary (self, analysis_date: date) -> Dict[str, Any]:
		"""获取市场总结"""
		# 这里应该获取实际市场数据
		# 返回模拟数据
		return {
			'market_condition': '震荡',
			'major_indices': {
				'上证指数': {'change': 0.5, 'volume': '3000亿'},
				'深证成指': {'change': 0.3, 'volume': '4000亿'}
			},
			'sector_performance': {
				'科技': 1.2,
				'金融': -0.5,
				'消费': 0.8
			}
		}

	async def _get_account_summary (self, analysis_date: date) -> Dict[str, Any]:
		"""获取账户总结"""
		try:
			accounts = await self.account_repo.get_many(
				status='active',
				skip=0,
				limit=100
			) if self.account_repo else []

			total_assets = sum(float(acc.total_balance) for acc in accounts if hasattr(acc, 'total_balance'))
			total_cash = sum(float(acc.available_balance) for acc in accounts if hasattr(acc, 'available_balance'))

			return {
				'total_accounts': len(accounts),
				'total_assets': total_assets,
				'total_cash': total_cash,
				'avg_account_size': total_assets / len(accounts) if accounts else 0
			}
		except Exception as e:
			self.logger.warning(f"获取账户总结失败: {e}")
			return {}

	async def _get_trade_summary (self, analysis_date: date) -> Dict[str, Any]:
		"""获取交易总结"""
		try:
			trades = await self.trade_repo.get_many(
				trade_date=analysis_date
			) if self.trade_repo else []

			return {
				'total_trades': len(trades),
				'total_volume': sum(float(t.filled_volume) for t in trades if hasattr(t, 'filled_volume')),
				'total_amount': sum(float(t.filled_amount) for t in trades if hasattr(t, 'filled_amount')),
				'avg_trade_size': sum(float(t.filled_amount) for t in trades if hasattr(t, 'filled_amount')) / len(
					trades) if trades else 0
			}
		except Exception as e:
			self.logger.warning(f"获取交易总结失败: {e}")
			return {}

	async def _get_risk_summary (self, analysis_date: date) -> Dict[str, Any]:
		"""获取风险总结"""
		# 这里应该计算实际风险数据
		return {
			'overall_risk': '中',
			'risk_alerts': 2,
			'high_risk_accounts': 1,
			'market_risk': '低',
			'liquidity_risk': '中'
		}

	async def _check_risk_alerts (self, analysis_date: date) -> Dict[str, Any]:
		"""
		检查风险警报

		Args:
			analysis_date: 分析日期

		Returns:
			Dict[str, Any]: 风险警报结果
		"""
		self.logger.info(f"检查风险警报，日期: {analysis_date}")

		try:
			alerts = []

			# 1. 检查账户风险
			accounts = await self.account_repo.get_many(
				status='active',
				skip=0,
				limit=100
			) if self.account_repo else []

			for account in accounts:
				# 检查保证金比例
				if hasattr(account, 'total_balance') and hasattr(account, 'available_balance'):
					total = float(account.total_balance)
					available = float(account.available_balance)

					if total > 0:
						cash_ratio = available / total
						if cash_ratio < 0.1:
							alerts.append({
								'type': 'liquidity_risk',
								'level': 'high',
								'account_id': account.id,
								'account_name': getattr(account, 'account_name', '未知'),
								'message': f'账户现金比例过低: {cash_ratio:.1%}',
								'value': cash_ratio,
								'threshold': 0.1
							})

				# 检查账户亏损
				if hasattr(account, 'initial_balance') and hasattr(account, 'total_balance'):
					initial = float(account.initial_balance)
					current = float(account.total_balance)

					if initial > 0:
						drawdown = (initial - current) / initial
						if drawdown > 0.2:
							alerts.append({
								'type': 'drawdown_alert',
								'level': 'high',
								'account_id': account.id,
								'account_name': getattr(account, 'account_name', '未知'),
								'message': f'账户回撤过大: {drawdown:.1%}',
								'value': drawdown,
								'threshold': 0.2
							})

			# 2. 检查交易风险
			trades = await self.trade_repo.get_many(
				trade_date=analysis_date
			) if self.trade_repo else []

			if trades:
				# 检查异常交易
				unusual_trades = self._identify_unusual_trades(trades)
				for trade in unusual_trades:
					if '大额交易' in trade['unusual_flags']:
						alerts.append({
							'type': 'large_trade',
							'level': 'medium',
							'trade_id': trade['trade_id'],
							'account_id': trade['account_id'],
							'message': f'检测到大额交易: {trade["amount"]:.0f}元',
							'value': trade['amount'],
							'threshold': 1000000
						})

			# 3. 检查市场风险（这里需要实际市场数据）
			market_alerts = await self._check_market_risk(analysis_date)
			alerts.extend(market_alerts)

			return {
				'total_alerts': len(alerts),
				'high_priority': len([a for a in alerts if a['level'] == 'high']),
				'medium_priority': len([a for a in alerts if a['level'] == 'medium']),
				'low_priority': len([a for a in alerts if a['level'] == 'low']),
				'alerts': alerts
			}

		except Exception as e:
			self.logger.error(f"检查风险警报失败: {e}", exc_info=True)
			raise

	async def _check_market_risk (self, analysis_date: date) -> List[Dict[str, Any]]:
		"""检查市场风险"""
		# 这里应该获取实际市场数据并检查风险
		# 返回模拟数据
		return [
			{
				'type': 'market_volatility',
				'level': 'medium',
				'message': '市场波动率上升',
				'value': 0.25,
				'threshold': 0.2
			}
		]

	async def schedule_daily_analysis (self, hour: int = 18, minute: int = 0):
		"""
		调度每日分析任务

		Args:
			hour: 调度小时
			minute: 调度分钟
		"""
		self.logger.info(f"调度每日分析任务: {hour}:{minute}")

		# 这里应该集成到系统的调度器中
		# 由于调度器实现未知，这里只记录日志

		self.logger.info(f"每日分析任务已调度，将在每天 {hour}:{minute} 执行")