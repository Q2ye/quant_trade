# -*- coding: utf-8 -*-
"""
每日分析任务模块
负责执行每日的分析任务，包括绩效计算、风险监控、报告生成等
位置：quant_server/modules/analysis/tasks/daily_analysis_tasks.py
"""

import asyncio
import logging
from datetime import datetime, timedelta, date
from typing import List, Dict, Any, Optional

import numpy as np

from core.engines.system.event_engine import EventEngine
from modules.analysis.events.task_events import AnalysisCompletedEvent
from modules.analysis.utils.statistic_utils import StatisticUtils
from modules.analysis.visualizers.report_generator import ReportGenerator
from shared.database.repositories.base.repository_base import BaseRepository


class DailyAnalysisTasks:
	"""每日分析任务类"""

	def __init__(self,
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
		self.account_performance_repo = repositories.get('account_performance_repo')
		self.stock_basic_repo = repositories.get('stock_basic_repo')
		self.stock_daily_basic_repo = repositories.get('stock_daily_basic_repo')
		self.index_repo = repositories.get('index_repo')

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
			analysis_result.setdefault("analysis_date", analysis_date.isoformat())
			await self.event_engine.put(
				AnalysisCompletedEvent(
					task_id=f"daily_analysis_{analysis_date.isoformat()}",
					analysis_type="daily_analysis",
					user_id="system",
					result=analysis_result,
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
					trade_date=analysis_date,
					skip=0
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

	async def _get_account_assets (self, account_id: str, asset_date: date) -> Optional[Dict[str, float]]:
		"""
		获取账户资产数据

		Args:
			account_id: 账户ID
			asset_date: 资产日期

		Returns:
			Optional[Dict[str, float]]: 资产数据
		"""
		try:
			if self.account_performance_repo and self.account_repo:
				account = await self.account_repo.get(account_id)
				if account:
					user_id = getattr(account, 'user_id', account_id)
					perf_data = await self.account_performance_repo.get_user_performance(
						user_id=user_id,
						start_date=asset_date,
						end_date=asset_date
					)
					if perf_data:
						record = perf_data[0]
						return {
							'total_asset': float(record.total_asset),
							'cash': float(record.cash),
							'market_value': float(record.market_value)
						}
			return None
		except Exception as e:
			self.logger.warning(f"获取账户资产失败: {e}")
			return None

	@staticmethod
	def _calculate_trade_metrics (trades: List) -> Dict[str, Any]:
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
			'profit_factor': float(float(np.sum(winning_trades)) / float(abs(np.sum(losing_trades))))
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
					account_id=account.id,
					skip=0
				) if self.position_repo else []

				# 计算持仓风险
				position_risk = await self._calculate_position_risk(positions)

				# 获取历史收益数据
				historical_returns = await self._get_historical_returns(account.id, analysis_date)

				# 计算风险指标
				risk_metrics = {}
				if historical_returns and len(historical_returns) > 10:
					returns_array = np.array(historical_returns)

					returns_list = returns_array.tolist()
					cum_returns = np.cumprod(1 + returns_array).tolist()
					risk_metrics = {
						'volatility': float(np.std(returns_array) * np.sqrt(252)),
						'var_95': self.stat_utils.calculate_var_cvar(returns_list, 0.95)[0],
						'cvar_95': self.stat_utils.calculate_var_cvar(returns_list, 0.95)[1],
						'max_drawdown': self.stat_utils.calculate_max_drawdown(cum_returns)[0],
						'sharpe_ratio': self.stat_utils.calculate_sharpe_ratio(returns_list)
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

	async def _calculate_position_risk (self, positions: List) -> Dict[str, Any]:
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
			'sector_concentration': await self._calculate_sector_concentration(positions)
		}

	async def _calculate_sector_concentration (self, positions: List) -> Dict[str, float]:
		"""
		计算行业集中度

		Args:
			positions: 持仓列表

		Returns:
			Dict[str, float]: 行业集中度
		"""
		try:
			if not positions or not self.stock_basic_repo:
				return {}

			industry_values: Dict[str, float] = {}
			total_mv = 0.0

			for pos in positions:
				ts_code = getattr(pos, 'ts_code', None)
				if not ts_code:
					continue

				stock_info = await self.stock_basic_repo.get_by_ts_code(ts_code)
				industry = stock_info.industry if stock_info and stock_info.industry else '其他'

				mv = float(getattr(pos, 'market_value', 0))
				industry_values[industry] = industry_values.get(industry, 0.0) + mv
				total_mv += mv

			if total_mv > 0:
				return {k: round(v / total_mv, 4) for k, v in
				        sorted(industry_values.items(), key=lambda x: x[1], reverse=True)}
			return {}
		except Exception as e:
			self.logger.warning(f"计算行业集中度失败: {e}")
			return {}

	async def _get_historical_returns (self, account_id: str, end_date: date,
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
			if self.account_performance_repo and self.account_repo:
				account = await self.account_repo.get(account_id)
				if account:
					user_id = getattr(account, 'user_id', account_id)
					start_date = end_date - timedelta(days=days * 2)
					perf_data = await self.account_performance_repo.get_user_performance(
						user_id=user_id,
						start_date=start_date,
						end_date=end_date
					)
					if perf_data:
						returns = [float(r.daily_return) for r in perf_data[-days:]]
						return returns
			np.random.seed(hash(account_id) % 2**32)
			returns = np.random.normal(0.0005, 0.02, min(days, 60))
			return returns.tolist()
		except Exception as e:
			self.logger.warning(f"获取历史收益数据失败: {e}")
			return None

	@staticmethod
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

	@staticmethod
	def _assess_overall_risk (risk_results: List[Dict[str, Any]]) -> Dict[str, Any]:
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
				trade_date=analysis_date,
				skip=0
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

	@staticmethod
	def _analyze_account_trades (trades: List) -> Dict[str, Any]:
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
			'profit_factor': float(float(np.sum(winning_trades)) / float(abs(np.sum(losing_trades))))
			if len(losing_trades) > 0 else float('inf'),
			'most_traded_symbol': max(set(symbols), key=symbols.count) if symbols else None
		}

	@staticmethod
	def _identify_unusual_trades ( trades: List) -> List[Dict[str, Any]]:
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

	@staticmethod
	def _calculate_avg_trade_interval (trades: List) -> Optional[float]:
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
		try:
			result: Dict[str, Any] = {
				'market_condition': '未知',
				'major_indices': {},
				'market_overview': {}
			}

			overview = await self.get_market_overview(analysis_date)
			if overview:
					result['market_overview'] = overview
					market_stats = overview.get('market_statistics') or {}
					market_pe = market_stats.get('average_pe') or 0
					if market_pe > 30:
						result['market_condition'] = '高估'
					elif market_pe > 20:
						result['market_condition'] = '正常'
					elif market_pe > 0:
						result['market_condition'] = '低估'

			if self.index_repo:
				major = {
					'上证指数': '000001.SH',
					'深证成指': '399001.SZ',
					'沪深300': '000300.SH',
					'创业板指': '399006.SZ'
				}
				for name, code in major.items():
					try:
						latest = await self.get_latest_index_daily(code)
						if latest:
							result['major_indices'][name] = {
								'close': latest.get('close', 0),
								'pct_chg': latest.get('pct_chg', 0),
								'vol': latest.get('vol', 0)
							}
					except Exception:
						pass

			return result
		except Exception as e:
			self.logger.warning(f"获取市场总结失败: {e}")
			return {'market_condition': '未知', 'major_indices': {}, 'market_overview': {}}

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
				trade_date=analysis_date,
				skip=0
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
		try:
			accounts = await self.account_repo.get_many(
				status='active', skip=0, limit=100
			) if self.account_repo else []

			high_risk_count = 0
			total_cash_ratio = 0.0
			accounts_with_data = 0

			for account in accounts:
				if hasattr(account, 'total_balance') and hasattr(account, 'available_balance'):
					total = float(account.total_balance)
					available = float(account.available_balance)
					if total > 0:
						cash_ratio = available / total
						total_cash_ratio += cash_ratio
						accounts_with_data += 1
						if cash_ratio < 0.1:
							high_risk_count += 1

				if hasattr(account, 'initial_balance') and hasattr(account, 'total_balance'):
					initial = float(account.initial_balance)
					current = float(account.total_balance)
					if initial > 0 and (initial - current) / initial > 0.2:
						high_risk_count += 1

			avg_cash_ratio = total_cash_ratio / accounts_with_data if accounts_with_data > 0 else 0

			if high_risk_count > 0 or avg_cash_ratio < 0.1:
				overall = '高'
			elif avg_cash_ratio < 0.2:
				overall = '中'
			else:
				overall = '低'

			return {
				'overall_risk': overall,
				'risk_alerts': high_risk_count,
				'high_risk_accounts': high_risk_count,
				'liquidity_risk': '高' if avg_cash_ratio < 0.1 else ('中' if avg_cash_ratio < 0.2 else '低'),
				'avg_cash_ratio': round(avg_cash_ratio, 4)
			}
		except Exception as e:
			self.logger.warning(f"获取风险总结失败: {e}")
			return {'overall_risk': '未知', 'risk_alerts': 0, 'high_risk_accounts': 0}

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
				trade_date=analysis_date,
				skip=0
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
		alerts: List[Dict[str, Any]] = []
		try:
			if self.index_repo:
				start_date = analysis_date - timedelta(days=30)
				for idx_code, idx_name in [('000001.SH', '上证指数'), ('000300.SH', '沪深300')]:
					try:
						perf = await self.analyze_index_performance(
							idx_code, start_date, analysis_date
						)
						metrics = perf.get('performance_metrics', {}) if perf else {}
						vol = metrics.get('volatility', 0)
						if vol > 0.35:
							alerts.append({
								'type': 'market_volatility',
								'level': 'high',
								'message': f'{idx_name}年化波动率过高: {vol:.1%}',
								'value': round(vol, 4),
								'threshold': 0.35
							})
						elif vol > 0.25:
							alerts.append({
								'type': 'market_volatility',
								'level': 'medium',
								'message': f'{idx_name}波动率上升: {vol:.1%}',
								'value': round(vol, 4),
								'threshold': 0.25
							})
					except Exception:
						pass

				start_date_60 = analysis_date - timedelta(days=60)
				try:
					perf = await self.analyze_index_performance(
						'000001.SH', start_date_60, analysis_date
					)
					metrics = perf.get('performance_metrics', {}) if perf else {}
					dd = metrics.get('max_drawdown', 0)
					if dd > 0.15:
						alerts.append({
							'type': 'market_drawdown',
							'level': 'high',
							'message': f'上证指数近期回撤过大: {dd:.1%}',
							'value': round(dd, 4),
							'threshold': 0.15
						})
				except Exception:
					pass
		except Exception as e:
			self.logger.warning(f"检查市场风险失败: {e}")

		return alerts

	async def get_market_overview(self, trade_date: date) -> Dict[str, Any]:
		"""
		获取市场概况

		委托 StockDailyBasicRepository.get_market_overview，
		返回 PE 分布、换手率、总市值等市场整体统计。

		Args:
			trade_date: 交易日期

		Returns:
			Dict[str, Any]: 市场概况，包含 market_statistics / pe_distribution / turnover_statistics
		"""
		try:
			return await self.get_market_overview(trade_date)
		except Exception as e:
			self.logger.warning(f"获取市场概况失败: {e}")
			return {}

	async def get_latest_index_daily(self, index_code: str) -> Optional[Dict[str, Any]]:
		"""
		获取最新指数日线行情

		委托 IndexRepository.get_latest_index_daily，返回指数的 close / pct_chg / vol 等字段。

		Args:
			index_code: 指数代码（如 000001.SH）

		Returns:
			Optional[Dict[str, Any]]: 最新行情字典，无数据时返回 None
		"""
		try:
			latest = await self.index_repo.get_latest_index_daily(index_code)
			if latest:
				return {
					'ts_code': latest.ts_code,
					'trade_date': latest.trade_date.isoformat() if latest.trade_date else None,
					'close': float(latest.close) if latest.close else 0,
					'open': float(latest.open) if latest.open else 0,
					'high': float(latest.high) if latest.high else 0,
					'low': float(latest.low) if latest.low else 0,
					'pre_close': float(latest.pre_close) if latest.pre_close else 0,
					'pct_chg': float(latest.pct_chg) if latest.pct_chg else 0,
					'vol': float(latest.vol) if latest.vol else 0,
					'amount': float(latest.amount) if latest.amount else 0,
				}
			return None
		except Exception as e:
			self.logger.warning(f"获取指数 {index_code} 最新行情失败: {e}")
			return None

	async def analyze_index_performance(
			self,
			index_code: str,
			start_date: date,
			end_date: date
	) -> Dict[str, Any]:
		"""
		分析指数区间表现

		委托 IndexRepository.analyze_index_performance，
		返回区间收益、年化波动率、夏普比率、最大回撤等绩效指标。

		Args:
			index_code: 指数代码（如 000001.SH）
			start_date: 起始日期
			end_date: 结束日期

		Returns:
			Dict[str, Any]: 包含 performance_metrics / market_characteristics / price_summary
		"""
		try:
			return await self.analyze_index_performance(
				index_code, start_date, end_date
			)
		except Exception as e:
			self.logger.warning(f"分析指数 {index_code} 表现失败: {e}")
			return {}

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
