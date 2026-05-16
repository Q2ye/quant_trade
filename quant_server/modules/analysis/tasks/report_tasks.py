# -*- coding: utf-8 -*-
"""
报告生成任务模块
负责异步生成各种分析报告，包括绩效报告、风险报告、比较报告等
位置：quant_server/modules/analysis/tasks/report_tasks.py
"""

import logging
import uuid
from datetime import datetime, timedelta, date
from typing import List, Dict, Any, Optional

from core.engines.system.event_engine import EventEngine
from core.events.system_events import ReportGeneratedEvent
from modules.analysis.visualizers.report_generator import ReportGenerator
from shared.database.repositories.base.repository_base import BaseRepository


class ReportTasks:
	"""报告生成任务类"""

	def __init__(self,
	              event_engine: EventEngine,
	              repositories: Dict[str, BaseRepository],
	              config: Dict[str, Any] = None):
		"""
		初始化报告生成任务

		Args:
			event_engine: 事件引擎
			repositories: Repository字典
			config: 配置字典
		"""
		self.event_engine = event_engine
		self.repositories = repositories
		self.config = config or {}

		# 获取所需的Repository
		self.strategy_repo = repositories.get('strategy_repo')
		self.backtest_repo = repositories.get('backtest_repo')
		self.trade_repo = repositories.get('trade_repo')
		self.performance_repo = repositories.get('performance_repo')

		# 报告生成器
		self.report_generator = ReportGenerator(
			output_dir=self.config.get('report_output_dir', './reports')
		)

		# 日志
		self.logger = logging.getLogger(__name__)

		# 任务状态
		self.active_tasks = {}

	async def generate_performance_report (self,
	                                       report_type: str,
	                                       strategy_id: Optional[str] = None,
	                                       start_date: Optional[date] = None,
	                                       end_date: Optional[date] = None,
	                                       parameters: Dict[str, Any] = None) -> Dict[str, Any]:
		"""
		生成绩效报告

		Args:
			report_type: 报告类型 ('daily', 'weekly', 'monthly', 'custom')
			strategy_id: 策略ID
			start_date: 开始日期
			end_date: 结束日期
			parameters: 额外参数

		Returns:
			Dict[str, Any]: 报告生成结果
		"""
		task_id = str(uuid.uuid4())
		self.active_tasks[task_id] = {
			'status': 'running',
			'start_time': datetime.now(),
			'type': 'performance_report',
			'report_type': report_type
		}

		self.logger.info(f"开始生成绩效报告，任务ID: {task_id}, 类型: {report_type}")

		try:
			# 1. 确定报告期间
			report_period = self._determine_report_period(report_type, start_date, end_date)

			# 2. 收集报告数据
			report_data = await self._collect_performance_data(
				strategy_id,
				report_period['start_date'],
				report_period['end_date']
			)

			# 3. 生成报告
			report_result = await self._generate_performance_report_content(
				report_data, report_type, parameters
			)

			# 4. 保存报告记录
			if self.performance_repo:
				await self._save_report_record(
					task_id, 'performance', report_type, report_result
				)

			# 5. 发布事件
			await self.event_engine.put(
				ReportGeneratedEvent(
					task_id=task_id,
					report_type='performance',
					report_path=report_result.get('report_path'),
					metadata={
						'strategy_id': strategy_id,
						'period': report_period,
						'parameters': parameters
					}
				)
			)

			return self._complete_task(task_id, report_result, '绩效报告')

		except Exception as e:
			self.logger.error(f"生成绩效报告失败: {e}", exc_info=True)

			# 更新任务状态
			self.active_tasks[task_id]['status'] = 'failed'
			self.active_tasks[task_id]['end_time'] = datetime.now()
			self.active_tasks[task_id]['error'] = str(e)

			return {
				'task_id': task_id,
				'status': 'failed',
				'error': str(e),
				'generation_time': datetime.now().isoformat()
			}

	async def generate_risk_report (self,
	                                report_type: str,
	                                account_id: Optional[str] = None,
	                                start_date: Optional[date] = None,
	                                end_date: Optional[date] = None,
	                                parameters: Dict[str, Any] = None) -> Dict[str, Any]:
		"""
		生成风险报告

		Args:
			report_type: 报告类型
			account_id: 账户ID
			start_date: 开始日期
			end_date: 结束日期
			parameters: 额外参数

		Returns:
			Dict[str, Any]: 报告生成结果
		"""
		task_id = str(uuid.uuid4())
		self.active_tasks[task_id] = {
			'status': 'running',
			'start_time': datetime.now(),
			'type': 'risk_report',
			'report_type': report_type
		}

		self.logger.info(f"开始生成风险报告，任务ID: {task_id}, 账户ID: {account_id}")

		try:
			# 1. 确定报告期间
			report_period = self._determine_report_period(report_type, start_date, end_date)

			# 2. 收集风险数据
			risk_data = await self._collect_risk_data(
				account_id,
				report_period['start_date'],
				report_period['end_date']
			)

			# 3. 生成报告
			report_result = await self._generate_risk_report_content(
				risk_data, report_type, parameters
			)

			# 4. 保存报告记录
			if self.performance_repo:
				await self._save_report_record(
					task_id, 'risk', report_type, report_result
				)

			# 5. 发布事件
			await self.event_engine.put(
				ReportGeneratedEvent(
					task_id=task_id,
					report_type='risk',
					report_path=report_result.get('report_path'),
					metadata={
						'account_id': account_id,
						'period': report_period,
						'parameters': parameters
					}
				)
			)

			return self._complete_task(task_id, report_result, '风险报告')

		except Exception as e:
			self.logger.error(f"生成风险报告失败: {e}", exc_info=True)

			# 更新任务状态
			self.active_tasks[task_id]['status'] = 'failed'
			self.active_tasks[task_id]['end_time'] = datetime.now()
			self.active_tasks[task_id]['error'] = str(e)

			return {
				'task_id': task_id,
				'status': 'failed',
				'error': str(e),
				'generation_time': datetime.now().isoformat()
			}

	async def generate_comparison_report (self,
	                                      strategy_ids: List[str],
	                                      report_type: str = 'comparison',
	                                      parameters: Dict[str, Any] = None) -> Dict[str, Any]:
		"""
		生成策略比较报告

		Args:
			strategy_ids: 策略ID列表
			report_type: 报告类型
			parameters: 额外参数

		Returns:
			Dict[str, Any]: 报告生成结果
		"""
		task_id = str(uuid.uuid4())
		self.active_tasks[task_id] = {
			'status': 'running',
			'start_time': datetime.now(),
			'type': 'comparison_report',
			'report_type': report_type
		}

		self.logger.info(f"开始生成比较报告，任务ID: {task_id}, 策略数量: {len(strategy_ids)}")

		try:
			# 1. 收集策略数据
			strategies_data = {}
			for strategy_id in strategy_ids:
				strategy_data = await self._collect_strategy_data(strategy_id)
				if strategy_data:
					strategies_data[strategy_id] = strategy_data

			if not strategies_data:
				raise ValueError("没有有效的策略数据")

			# 2. 生成报告
			report_result = await self._generate_comparison_report_content(
				strategies_data, parameters
			)

			# 3. 保存报告记录
			if self.performance_repo:
				await self._save_report_record(
					task_id, 'comparison', report_type, report_result
				)

			# 4. 发布事件
			await self.event_engine.put(
				ReportGeneratedEvent(
					task_id=task_id,
					report_type='comparison',
					report_path=report_result.get('report_path'),
					metadata={
						'strategy_ids': strategy_ids,
						'parameters': parameters
					}
				)
			)

			return self._complete_task(task_id, report_result, '比较报告')

		except Exception as e:
			self.logger.error(f"生成比较报告失败: {e}", exc_info=True)

			# 更新任务状态
			self.active_tasks[task_id]['status'] = 'failed'
			self.active_tasks[task_id]['end_time'] = datetime.now()
			self.active_tasks[task_id]['error'] = str(e)

			return {
				'task_id': task_id,
				'status': 'failed',
				'error': str(e),
				'generation_time': datetime.now().isoformat()
			}

	async def generate_custom_report (self,
	                                  report_template: str,
	                                  data_sources: Dict[str, Any],
	                                  parameters: Dict[str, Any] = None) -> Dict[str, Any]:
		"""
		生成自定义报告

		Args:
			report_template: 报告模板
			data_sources: 数据源配置
			parameters: 额外参数

		Returns:
			Dict[str, Any]: 报告生成结果
		"""
		task_id = str(uuid.uuid4())
		self.active_tasks[task_id] = {
			'status': 'running',
			'start_time': datetime.now(),
			'type': 'custom_report',
			'template': report_template
		}

		self.logger.info(f"开始生成自定义报告，任务ID: {task_id}, 模板: {report_template}")

		try:
			# 1. 收集数据
			collected_data = await self._collect_custom_data(data_sources)

			# 2. 生成报告（这里需要根据模板生成）
			report_result = await self._generate_custom_report_content(
				report_template, collected_data, parameters
			)

			# 3. 保存报告记录
			if self.performance_repo:
				await self._save_report_record(
					task_id, 'custom', report_template, report_result
				)

			# 4. 发布事件
			await self.event_engine.put(
				ReportGeneratedEvent(
					task_id=task_id,
					report_type='custom',
					report_path=report_result.get('report_path'),
					metadata={
						'template': report_template,
						'data_sources': data_sources,
						'parameters': parameters
					}
				)
			)

			return self._complete_task(task_id, report_result, '自定义报告')

		except Exception as e:
			self.logger.error(f"生成自定义报告失败: {e}", exc_info=True)

			# 更新任务状态
			self.active_tasks[task_id]['status'] = 'failed'
			self.active_tasks[task_id]['end_time'] = datetime.now()
			self.active_tasks[task_id]['error'] = str(e)

			return {
				'task_id': task_id,
				'status': 'failed',
				'error': str(e),
				'generation_time': datetime.now().isoformat()
			}

	@staticmethod
	def _determine_report_period(
			report_type: str,
			start_date: Optional[date],
			end_date: Optional[date]) -> Dict[str, date]:
		"""
		确定报告期间

		Args:
			report_type: 报告类型
			start_date: 开始日期
			end_date: 结束日期

		Returns:
			Dict[str, date]: 开始日期和结束日期
		"""
		today = datetime.now().date()

		if start_date and end_date:
			# 使用自定义日期
			return {'start_date': start_date, 'end_date': end_date}

		# 根据报告类型确定默认期间
		if report_type == 'daily':
			return {
				'start_date': today - timedelta(days=1),
				'end_date': today - timedelta(days=1)
			}
		elif report_type == 'weekly':
			return {
				'start_date': today - timedelta(days=7),
				'end_date': today - timedelta(days=1)
			}
		elif report_type == 'monthly':
			return {
				'start_date': today - timedelta(days=30),
				'end_date': today - timedelta(days=1)
			}
		elif report_type == 'quarterly':
			return {
				'start_date': today - timedelta(days=90),
				'end_date': today - timedelta(days=1)
			}
		elif report_type == 'yearly':
			return {
				'start_date': today - timedelta(days=365),
				'end_date': today - timedelta(days=1)
			}
		else:
			# 默认为最近一个月
			return {
				'start_date': today - timedelta(days=30),
				'end_date': today - timedelta(days=1)
			}

	async def _collect_performance_data (self,
	                                     strategy_id: Optional[str],
	                                     start_date: date,
	                                     end_date: date) -> Dict[str, Any]:
		"""
		收集绩效数据

		Args:
			strategy_id: 策略ID
			start_date: 开始日期
			end_date: 结束日期

		Returns:
			Dict[str, Any]: 绩效数据
		"""
		self.logger.info(f"收集绩效数据，策略: {strategy_id}, 期间: {start_date} 至 {end_date}")

		try:
			data = {
				'strategy_id': strategy_id,
				'period': {
					'start_date': start_date.isoformat(),
					'end_date': end_date.isoformat()
				},
				'equity_data': {},
				'trade_data': [],
				'metrics': {}
			}

			# 获取策略信息
			if strategy_id and self.strategy_repo:
				strategy = await self.strategy_repo.get(strategy_id)
				if strategy:
					data['strategy_info'] = {
						'name': strategy.name,
						'description': strategy.description,
						'status': strategy.status,
						'parameters': {}
					}

			# 获取净值数据（这里需要根据实际数据结构调整）
			# events['equity_data'] = await self._get_equity_data(strategy_id, start_date, end_date)

			# 获取交易数据
			if self.trade_repo:
				trades = await self.trade_repo.get_many(
					strategy_id=strategy_id,
					skip=0,
					limit=1000
				)
				trades = [t for t in trades if hasattr(t, "trade_date")
				          and start_date <= getattr(t, "trade_date") <= end_date]
				data['trade_data'] = [
					{
						'trade_id': getattr(t, 'trade_id', getattr(t, 'id', '')),
						'trade_time': getattr(t, 'trade_time', ''),
						'symbol': getattr(t, 'ts_code', ''),
						'direction': getattr(t, 'direction', ''),
						'price': float(getattr(t, 'price', 0)),
						'volume': int(getattr(t, 'filled_volume', 0)),
						'amount': float(getattr(t, 'filled_amount', 0)),
						'profit': float(getattr(t, 'profit', 0))
					}
					for t in trades
				]

			# 获取绩效指标
			if self.performance_repo and strategy_id:
				performance_records = await self.performance_repo.get_many(
					strategy_id=strategy_id,
					skip=0,
					limit=1000
				)
				performance_records = [p for p in performance_records if hasattr(p, "trade_date")
				                       and start_date <= getattr(p, "trade_date") <= end_date]

				if performance_records:
					# 计算汇总指标
					returns = [float(getattr(p, 'daily_return', 0)) for p in performance_records]
					if returns:
						data['metrics']['avg_daily_return'] = str(sum(returns) / len(returns))
						data['metrics']['total_return'] = str((1 + sum(returns)) ** len(returns) - 1)

					# 获取最新记录
					latest = max(performance_records, key=lambda x: getattr(x, 'trade_date', datetime.min))
					data['metrics'].update({
						'latest_equity': str(float(getattr(latest, 'equity', 0))),
						'latest_cash': str(float(getattr(latest, 'cash', 0))),
						'latest_market_value': str(float(getattr(latest, 'market_value', 0)))
					})

			return data

		except Exception as e:
			self.logger.error(f"收集绩效数据失败: {e}", exc_info=True)
			return {}

	async def _collect_risk_data (self,
	                              account_id: Optional[str],
	                              start_date: date,
	                              end_date: date) -> Dict[str, Any]:
		"""
		收集风险数据

		Args:
			account_id: 账户ID
			start_date: 开始日期
			end_date: 结束日期

		Returns:
			Dict[str, Any]: 风险数据
		"""
		self.logger.info(f"收集风险数据，账户: {account_id}, 期间: {start_date} 至 {end_date}")

		try:
			data = {
				'account_id': account_id,
				'period': {
					'start_date': start_date.isoformat(),
					'end_date': end_date.isoformat()
				},
				'returns_data': [],
				'positions_data': [],
				'risk_metrics': {}
			}

			# 获取收益数据（这里需要根据实际数据结构调整）
			# events['returns_data'] = await self._get_returns_data(account_id, start_date, end_date)

			# 获取持仓数据
			# events['positions_data'] = await self._get_positions_data(account_id)

			# 计算风险指标
			# events['risk_metrics'] = await self._calculate_risk_metrics(events['returns_data'])

			return data

		except Exception as e:
			self.logger.error(f"收集风险数据失败: {e}", exc_info=True)
			return {}

	async def _collect_strategy_data (self, strategy_id: str) -> Dict[str, Any]:
		"""
		收集策略数据

		Args:
			strategy_id: 策略ID

		Returns:
			Dict[str, Any]: 策略数据
		"""
		try:
			data = {
				'strategy_id': strategy_id,
				'basic_info': {},
				'performance_metrics': {},
				'recent_trades': []
			}

			# 获取策略基本信息
			if self.strategy_repo:
				strategy = await self.strategy_repo.get(strategy_id)
				if strategy:
					data['basic_info'] = {
						'name': strategy.name,
						'description': strategy.description,
						'status': strategy.status,
						'created_at': strategy.created_at.isoformat() if strategy.created_at else '',
						'parameters': {}
					}

			# 获取回测结果
			if self.backtest_repo:
				backtests = await self.backtest_repo.get_many(
					strategy_id=strategy_id,
					skip=0,
					limit=5
				)
				backtests = sorted(
					backtests,
					key=lambda x: getattr(x, "completed_at", datetime.min),
					reverse=True,
				)

				if backtests:
					latest_backtest = backtests[0]
					data['performance_metrics'] = latest_backtest.result or {}

			# 获取最近交易
			if self.trade_repo:
				recent_trades = await self.trade_repo.get_many(
					strategy_id=strategy_id,
					skip=0,
					limit=50
				)
				recent_trades = sorted(
					recent_trades,
					key=lambda x: getattr(x, "trade_time", datetime.min),
					reverse=True,
				)

				data['recent_trades'] = [
					{
						'trade_time': t.trade_time.isoformat() if hasattr(t, 'trade_time') else '',
						'symbol': getattr(t, 'ts_code', ''),
						'direction': getattr(t, 'direction', ''),
						'price': float(getattr(t, 'price', 0)),
						'profit': float(getattr(t, 'profit', 0))
					}
					for t in recent_trades
				]

			return data

		except Exception as e:
			self.logger.error(f"收集策略数据失败: {e}", exc_info=True)
			return {}

	async def _collect_custom_data (self, data_sources: Dict[str, Any]) -> Dict[str, Any]:
		"""
		收集自定义数据

		Args:
			data_sources: 数据源配置

		Returns:
			Dict[str, Any]: 收集的数据
		"""
		collected_data = {}

		for source_name, source_config in data_sources.items():
			try:
				if source_config.get('type') == 'database':
					# 从数据库获取数据
					repo_name = source_config.get('repository')
					query_params = source_config.get('parameters', {})

					if repo_name in self.repositories:
						repo = self.repositories[repo_name]
						data = await repo.get_many(**query_params)
						collected_data[source_name] = data

				elif source_config.get('type') == 'external':
					# 外部数据源
					# 这里需要根据具体的外部数据源实现
					pass

				elif source_config.get('type') == 'calculated':
					# 计算数据
					# 这里需要根据具体计算逻辑实现
					pass

			except Exception as e:
				self.logger.warning(f"收集数据源 {source_name} 失败: {e}")
				collected_data[source_name] = {'error': str(e)}

		return collected_data

	async def _generate_performance_report_content (self,
	                                                data: Dict[str, Any],
	                                                report_type: str,
	                                                parameters: Dict[str, Any]) -> Dict[str, Any]:
		"""
		生成绩效报告内容

		Args:
			data: 绩效数据
			report_type: 报告类型
			parameters: 额外参数

		Returns:
			Dict[str, Any]: 报告内容
		"""
		try:
			# 使用报告生成器生成绩效报告
			strategy_name = data.get('strategy_info', {}).get('name', '未知策略')

			# 准备报告数据
			report_data = {
				'strategy_name': strategy_name,
				'equity_data': data.get('equity_data', {}),
				'trade_data': data.get('trade_data', []),
				'metrics': data.get('metrics', {}),
				'period': data.get('period', {})
			}

			# 生成报告
			report_path = self.report_generator.generate_performance_report(
				strategy_name=strategy_name,
				equity_data=report_data['equity_data'],
				trade_data=report_data['trade_data'],
				output_format=parameters.get('format', 'html') if parameters else 'html',
				include_charts=parameters.get('include_charts', True) if parameters else True
			)

			return {
				'report_path': report_path,
				'report_data': report_data,
				'report_type': report_type,
				'generation_time': datetime.now().isoformat()
			}

		except Exception as e:
			self.logger.error(f"生成绩效报告内容失败: {e}", exc_info=True)
			raise

	async def _generate_risk_report_content (self,
	                                         data: Dict[str, Any],
	                                         report_type: str,
	                                         parameters: Dict[str, Any]) -> Dict[str, Any]:
		"""
		生成风险报告内容

		Args:
			data: 风险数据
			report_type: 报告类型
			parameters: 额外参数

		Returns:
			Dict[str, Any]: 报告内容
		"""
		try:
			# 准备报告数据
			report_data = {
				'account_id': data.get('account_id'),
				'returns_data': data.get('returns_data', []),
				'positions_data': data.get('positions_data', []),
				'risk_metrics': data.get('risk_metrics', {}),
				'period': data.get('period', {})
			}

			# 生成报告
			report_path = self.report_generator.generate_risk_report(
				strategy_name=f"账户 {data.get('account_id', '未知')}",
				returns=report_data['returns_data'],
				positions=report_data['positions_data'],
				risk_metrics=report_data['risk_metrics'],
				output_format=parameters.get('format', 'html') if parameters else 'html'
			)

			return {
				'report_path': report_path,
				'report_data': report_data,
				'report_type': report_type,
				'generation_time': datetime.now().isoformat()
			}

		except Exception as e:
			self.logger.error(f"生成风险报告内容失败: {e}", exc_info=True)
			raise

	async def _generate_comparison_report_content (self,
	                                               strategies_data: Dict[str, Dict[str, Any]],
	                                               parameters: Dict[str, Any]) -> Dict[str, Any]:
		"""
		生成比较报告内容

		Args:
			strategies_data: 策略数据字典
			parameters: 额外参数

		Returns:
			Dict[str, Any]: 报告内容
		"""
		try:
			# 准备比较数据
			comparison_data = {}
			comparison_metrics = ['total_return', 'sharpe_ratio', 'max_drawdown', 'win_rate']

			for strategy_id, data in strategies_data.items():
				strategy_name = data.get('basic_info', {}).get('name', strategy_id)
				comparison_data[strategy_name] = {
					'metrics': data.get('performance_metrics', {}),
					'basic_info': data.get('basic_info', {}),
					'recent_trades': data.get('recent_trades', [])
				}

			# 生成报告
			report_path = self.report_generator.generate_comparison_report(
				strategies=comparison_data,
				comparison_metrics=comparison_metrics,
				output_format=parameters.get('format', 'html') if parameters else 'html'
			)

			return {
				'report_path': report_path,
				'report_data': {
					'strategies': comparison_data,
					'comparison_metrics': comparison_metrics
				},
				'report_type': 'comparison',
				'generation_time': datetime.now().isoformat()
			}

		except Exception as e:
			self.logger.error(f"生成比较报告内容失败: {e}", exc_info=True)
			raise

	async def _generate_custom_report_content (self,
	                                           template: str,
	                                           data: Dict[str, Any],
	                                           parameters: Dict[str, Any]) -> Dict[str, Any]:
		"""
		生成自定义报告内容

		Args:
			template: 报告模板
			data: 数据
			parameters: 额外参数

		Returns:
			Dict[str, Any]: 报告内容
		"""
		try:
			# 这里需要根据模板生成自定义报告
			# 由于模板系统复杂，这里只生成基本报告

			report_data = {
				'template': template,
				'events': data,
				'parameters': parameters,
				'generation_time': datetime.now().isoformat()
			}

			# 生成报告文件路径
			timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
			report_filename = f"custom_report_{template}_{timestamp}.html"
			report_path = self.report_generator.output_dir / report_filename

			# 创建简单的HTML报告
			html_content = f"""
            <!DOCTYPE html>
            <html>
            <head>
                <title>自定义报告 - {template}</title>
                <style>
                    body {{ font-family: Arial, sans-serif; margin: 40px; }}
                    h1 {{ color: #333; }}
                    .section {{ margin-bottom: 30px; }}
                    .events-item {{ margin: 5px 0; }}
                </style>
            </head>
            <body>
                <h1>自定义报告: {template}</h1>
                <div class="section">
                    <h2>报告信息</h2>
                    <div class="events-item">生成时间: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}</div>
                    <div class="events-item">模板: {template}</div>
                </div>
                <div class="section">
                    <h2>数据概览</h2>
                    <div class="events-item">数据源数量: {len(data)}</div>
                </div>
            </body>
            </html>
            """

			report_path.write_text(html_content, encoding='utf-8')

			return {
				'report_path': str(report_path),
				'report_data': report_data,
				'report_type': 'custom',
				'generation_time': datetime.now().isoformat()
			}

		except Exception as e:
			self.logger.error(f"生成自定义报告内容失败: {e}", exc_info=True)
			raise

	async def _save_report_record (self,
	                               task_id: str,
	                               report_type: str,
	                               report_subtype: str,
	                               report_result: Dict[str, Any]) -> bool:
		"""
		保存报告记录

		Args:
			task_id: 任务ID
			report_type: 报告类型
			report_subtype: 报告子类型
			report_result: 报告结果

		Returns:
			bool: 是否成功
		"""
		try:
			if not self.performance_repo:
				return False

			report_record = {
				'task_id': task_id,
				'report_type': report_type,
				'report_subtype': report_subtype,
				'report_path': report_result.get('report_path'),
				'generated_at': datetime.now(),
				'metadata': {
					'report_data': report_result.get('report_data', {}),
					'generation_time': report_result.get('generation_time')
				}
			}

			await self.performance_repo.create(report_record)
			return True

		except Exception as e:
			self.logger.warning(f"保存报告记录失败: {e}")
			return False

	async def get_task_status (self, task_id: str) -> Dict[str, Any]:
		"""
		获取任务状态

		Args:
			task_id: 任务ID

		Returns:
			Dict[str, Any]: 任务状态
		"""
		if task_id not in self.active_tasks:
			return {'status': 'not_found', 'task_id': task_id}

		task_info = self.active_tasks[task_id].copy()

		# 计算运行时间
		if task_info['status'] == 'running':
			duration = (datetime.now() - task_info['start_time']).total_seconds()
			task_info['duration_seconds'] = duration

		return task_info

	async def cancel_task (self, task_id: str) -> Dict[str, Any]:
		"""
		取消任务

		Args:
			task_id: 任务ID

		Returns:
			Dict[str, Any]: 取消结果
		"""
		if task_id not in self.active_tasks:
			return {'status': 'not_found', 'task_id': task_id}

		task_info = self.active_tasks[task_id]

		if task_info['status'] == 'completed' or task_info['status'] == 'failed':
			return {'status': 'cannot_cancel', 'task_id': task_id, 'current_status': task_info['status']}

		# 标记为取消
		task_info['status'] = 'cancelled'
		task_info['end_time'] = datetime.now()

		return {'status': 'cancelled', 'task_id': task_id}

	def _complete_task (self, task_id: str, report_result: Dict[str, Any], report_type: str) -> Dict[str, Any]:
		"""
		完成任务并返回结果

		Args:
			task_id: 任务ID
			report_result: 报告结果
			report_type: 报告类型

		Returns:
			任务完成结果
		"""
		# 更新任务状态
		self.active_tasks[task_id]['status'] = 'completed'
		self.active_tasks[task_id]['end_time'] = datetime.now()
		self.active_tasks[task_id]['result'] = report_result

		self.logger.info(f"{report_type}生成完成，任务ID: {task_id}")

		return {
			'task_id': task_id,
			'status': 'completed',
			'report_path': report_result.get('report_path'),
			'report_data': report_result.get('report_data'),
			'generation_time': datetime.now().isoformat()
		}

	async def cleanup_old_tasks (self, max_age_hours: int = 24):
		"""
		清理旧任务

		Args:
			max_age_hours: 最大保留时间（小时）
		"""
		cutoff_time = datetime.now() - timedelta(hours=max_age_hours)

		tasks_to_remove = []
		for task_id, task_info in self.active_tasks.items():
			if 'end_time' in task_info and task_info['end_time'] < cutoff_time:
				tasks_to_remove.append(task_id)

		for task_id in tasks_to_remove:
			del self.active_tasks[task_id]

		self.logger.info(f"清理了 {len(tasks_to_remove)} 个旧任务")