# trade_manager.py      # 交易管理器

import logging
from typing import Dict, Any, Optional

from core.engines.system import EventEngine

logger = logging.getLogger(__name__)


class TradeManager:
	"""交易管理器"""

	def __init__ (
			self,
			config: Dict[str, Any],
			event_engine: Optional[EventEngine] = None
	):
		self.config = config
		self.event_engine = event_engine
		self.trading_enabled = config.get("trading_enabled", True)
		self.simulated_trading = config.get("simulated_trading", True)

	def is_trading_enabled (self) -> bool:
		"""检查交易是否启用"""
		return self.trading_enabled

	def is_simulated_trading (self) -> bool:
		"""检查是否为模拟交易"""
		return self.simulated_trading

	def get_trading_config (self) -> Dict[str, Any]:
		"""获取交易配置"""
		return {
			"trading_enabled": self.trading_enabled,
			"simulated_trading": self.simulated_trading,
			**self.config
		}

	def update_trading_config (self, config: Dict[str, Any]) -> bool:
		"""更新交易配置"""
		try:
			if "trading_enabled" in config:
				self.trading_enabled = config["trading_enabled"]
			if "simulated_trading" in config:
				self.simulated_trading = config["simulated_trading"]
			# 更新其他配置项
			self.config.update(config)
			return True
		except Exception as e:
			logger.exception(f"更新交易配置失败: {str(e)}")
			return False
