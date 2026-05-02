"""分析模块事件处理器"""

import logging
from datetime import date
from typing import Dict, Any

from quant_server.core.events.base import BaseEvent
from quant_server.modules.analysis.events import (
	PerformanceAnalysisStartedEvent,
	PerformanceAnalysisCompletedEvent,
	RiskAnalysisStartedEvent,
	RiskAnalysisCompletedEvent,
	AttributionAnalysisCompletedEvent,
	ComparisonAnalysisCompletedEvent,
	TradeAnalysisStartedEvent,
	TradeAnalysisCompletedEvent
)

logger = logging.getLogger(__name__)


class AnalysisEventHandler:
	"""分析模块事件处理器"""

	def __init__ (self, event_engine):
		"""
		初始化事件处理器

		Args:
			event_engine: 事件引擎实例
		"""
		self.event_engine = event_engine
		self._subscribe_events()

	def _subscribe_events (self):
		"""订阅相关事件"""
		# 订阅策略执行事件
		# 注意：这里需要根据实际的事件类型进行调整
		try:
			self.event_engine.register('strategy.executed', self.handle_strategy_executed)
		except ImportError:
			logger.warning("策略模块事件未找到，跳过订阅")

		# 订阅交易完成事件
		try:
			self.event_engine.register('trade.order.completed', self.handle_trade_completed)
		except ImportError:
			logger.warning("交易模块事件未找到，跳过订阅")

		# 订阅回测完成事件
		try:
			from quant_server.modules.backtest.events import BacktestCompletedEvent
			self.event_engine.register('backtest.task.completed', self.handle_backtest_completed)
		except ImportError:
			logger.warning("回测模块事件未找到，跳过订阅")

	def handle_strategy_executed (self, event: BaseEvent):
		"""处理策略执行事件"""
		try:
			strategy_id = event.data.get('strategy_id')
			if not strategy_id:
				return

			# 触发绩效分析
			self.trigger_performance_analysis(strategy_id)

			# 触发风险分析
			self.trigger_risk_analysis(strategy_id)

		except Exception as e:
			logger.error(f"处理策略执行事件失败: {str(e)}")

	def handle_trade_completed (self, event: BaseEvent):
		"""处理交易完成事件"""
		try:
			strategy_id = event.data.get('strategy_id')
			if not strategy_id:
				return

			# 触发交易分析
			self.trigger_trade_analysis(strategy_id)

		except Exception as e:
			logger.error(f"处理交易完成事件失败: {str(e)}")

	def handle_backtest_completed (self, event: BaseEvent):
		"""处理回测完成事件"""
		try:
			strategy_id = event.data.get('strategy_id')
			if not strategy_id:
				return

			# 触发回测结果分析
			self.trigger_backtest_analysis(strategy_id)

		except Exception as e:
			logger.error(f"处理回测完成事件失败: {str(e)}")

	async def trigger_performance_analysis (self, strategy_id: str):
		"""触发绩效分析"""
		try:
			# 计算日期范围（最近30天）
			end_date = date.today()
			start_date = end_date.replace(day=1) if end_date.day > 1 else end_date.replace(
				month=end_date.month - 1 if end_date.month > 1 else 12, day=1)

			# 发布绩效分析开始事件
			start_event = PerformanceAnalysisStartedEvent(
				strategy_id=strategy_id,
				start_date=start_date,
				end_date=end_date,
				analysis_type="daily"
			)
			await self.event_engine.put(start_event)

		except Exception as e:
			logger.error(f"触发绩效分析失败: {str(e)}")

	async def trigger_risk_analysis (self, strategy_id: str):
		"""触发风险分析"""
		try:
			# 计算日期范围（最近90天）
			end_date = date.today()
			start_date = end_date.replace(month=end_date.month - 3 if end_date.month > 3 else end_date.month + 9, day=1)

			# 发布风险分析开始事件
			start_event = RiskAnalysisStartedEvent(
				strategy_id=strategy_id,
				start_date=start_date,
				end_date=end_date,
				risk_type="VaR"
			)
			await self.event_engine.put(start_event)

		except Exception as e:
			logger.error(f"触发风险分析失败: {str(e)}")

	async def trigger_trade_analysis (self, strategy_id: str):
		"""触发交易分析"""
		try:
			# 计算日期范围（最近7天）
			end_date = date.today()
			start_date = end_date.replace(day=end_date.day - 7 if end_date.day > 7 else 1)

			# 发布交易分析开始事件
			start_event = TradeAnalysisStartedEvent(
				strategy_id=strategy_id,
				start_date=start_date,
				end_date=end_date,
				analysis_type="trade_summary"
			)
			await self.event_engine.put(start_event)

		except Exception as e:
			logger.error(f"触发交易分析失败: {str(e)}")

	async def trigger_backtest_analysis (self, strategy_id: str):
		"""触发回测结果分析"""
		try:
			# 发布绩效分析和风险分析事件
			await self.trigger_performance_analysis(strategy_id)
			await self.trigger_risk_analysis(strategy_id)

		except Exception as e:
			logger.error(f"触发回测分析失败: {str(e)}")

	async def publish_performance_completed (self, strategy_id: str, start_date: date, end_date: date,
	                                         result: Dict[str, Any]):
		"""发布绩效分析完成事件"""
		try:
			completed_event = PerformanceAnalysisCompletedEvent(
				strategy_id=strategy_id,
				start_date=start_date,
				end_date=end_date,
				analysis_type="daily",
				result=result
			)
			await self.event_engine.put(completed_event)

		except Exception as e:
			logger.error(f"发布绩效分析完成事件失败: {str(e)}")

	async def publish_risk_completed (self, strategy_id: str, start_date: date, end_date: date, result: Dict[str, Any]):
		"""发布风险分析完成事件"""
		try:
			completed_event = RiskAnalysisCompletedEvent(
				strategy_id=strategy_id,
				start_date=start_date,
				end_date=end_date,
				risk_type="VaR",
				result=result
			)
			await self.event_engine.put(completed_event)

		except Exception as e:
			logger.error(f"发布风险分析完成事件失败: {str(e)}")

	async def publish_attribution_completed (self, portfolio_id: str, start_date: date, end_date: date,
	                                         attribution_model: str, result: Dict[str, Any]):
		"""发布归因分析完成事件"""
		try:
			completed_event = AttributionAnalysisCompletedEvent(
				portfolio_id=portfolio_id,
				start_date=start_date,
				end_date=end_date,
				attribution_model=attribution_model,
				result=result
			)
			await self.event_engine.put(completed_event)

		except Exception as e:
			logger.error(f"发布归因分析完成事件失败: {str(e)}")

	async def publish_comparison_completed (self, items: list, start_date: date, end_date: date, comparison_type: str,
	                                        result: Dict[str, Any]):
		"""发布对比分析完成事件"""
		try:
			completed_event = ComparisonAnalysisCompletedEvent(
				items=items,
				start_date=start_date,
				end_date=end_date,
				comparison_type=comparison_type,
				result=result
			)
			await self.event_engine.put(completed_event)

		except Exception as e:
			logger.error(f"发布对比分析完成事件失败: {str(e)}")

	async def publish_trade_analysis_completed (self, strategy_id: str, start_date: date, end_date: date,
	                                            result: Dict[str, Any]):
		"""发布交易分析完成事件"""
		try:
			completed_event = TradeAnalysisCompletedEvent(
				strategy_id=strategy_id,
				start_date=start_date,
				end_date=end_date,
				analysis_type="trade_summary",
				result=result
			)
			await self.event_engine.put(completed_event)

		except Exception as e:
			logger.error(f"发布交易分析完成事件失败: {str(e)}")