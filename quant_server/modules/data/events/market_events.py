"""
市场数据处理事件定义
用于市场数据更新和处理过程中的事件通知

业务场景：
1. 实时行情数据更新
2. 日频/周频数据更新
3. 市场状态变化通知
4. 数据预处理完成通知
"""

from datetime import datetime
from typing import Dict, Any, List, Optional
from dataclasses import field

from quant_server.core.events.base import BaseEvent, EventPriority
from quant_server.core.events.types import DataEventType


class MarketDataUpdatedEvent(BaseEvent):
	"""
	市场数据更新事件

	触发时机：
	- 实时行情数据到达
	- 日终数据更新完成
	- 批量数据导入完成

	事件数据：
	- data_type: 数据类型（tick/k线/日线等）
	- symbols: 更新的标的列表
	- update_type: 更新类型（增量/全量）
	- data_summary: 数据摘要信息
	"""

	def __init__ (
			self,
			data_type: str,
			symbols: List[str],
			update_time: Optional[datetime] = None,
			update_type: str = "incremental",
			data_summary: Optional[Dict[str, Any]] = None,
			source: str = "market_data_service",
			**kwargs
	):
		super().__init__(
			module="events",
			event_type=DataEventType.MARKET_DATA_UPDATED.value,
			priority=EventPriority.NORMAL,
			source=source,
			**kwargs
		)

		if update_time is None:
			update_time = datetime.now()

		self.data = {
			"data_type": data_type,
			"symbols": symbols,
			"symbol_count": len(symbols),
			"update_time": update_time.isoformat(),
			"update_type": update_type,
			"data_summary": data_summary or self._default_summary(data_type, symbols),
			"data_quality": "unknown",
			"processing_status": "raw",  # raw, processed, validated
			"available_indicators": self._get_available_indicators(data_type)
		}

	def _default_summary (self, data_type: str, symbols: List[str]) -> Dict[str, Any]:
		"""生成默认的数据摘要"""
		summary = {
			"record_count": len(symbols),
			"first_symbol": symbols[0] if symbols else "",
			"last_symbol": symbols[-1] if symbols else "",
		}

		# 根据数据类型添加特定字段
		if data_type == "tick":
			summary.update({
				"frequency": "tick",
				"fields": ["price", "volume", "bid", "ask"]
			})
		elif data_type == "1min":
			summary.update({
				"frequency": "1min",
				"fields": ["open", "high", "low", "close", "volume"]
			})
		elif data_type == "daily":
			summary.update({
				"frequency": "daily",
				"fields": ["open", "high", "low", "close", "volume", "amount"]
			})

		return summary

	def _get_available_indicators (self, data_type: str) -> List[str]:
		"""根据数据类型返回可计算的指标"""
		base_indicators = ["ma", "ema", "macd", "rsi", "boll"]

		if data_type == "tick":
			return ["tick_volume", "bid_ask_spread", "vwap"]
		elif data_type in ["1min", "5min", "15min", "30min", "60min"]:
			return base_indicators + ["atr", "kdj", "obv"]
		elif data_type == "daily":
			return base_indicators + ["atr", "kdj", "obv", "adx", "cci"]

		return base_indicators

	def add_data_quality_info (self, quality_metrics: Dict[str, Any]) -> None:
		"""添加数据质量信息"""
		self.data["data_quality"] = quality_metrics.get("overall_quality", "unknown")
		self.data["quality_metrics"] = quality_metrics
		self.data["processing_status"] = "validated"

	def add_processing_result (self, indicators: List[str], processed_count: int) -> None:
		"""添加处理结果信息"""
		self.data["processed_indicators"] = indicators
		self.data["processed_count"] = processed_count
		self.data["processing_status"] = "processed"