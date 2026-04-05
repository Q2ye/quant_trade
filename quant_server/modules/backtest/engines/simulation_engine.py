# -*- coding: utf-8 -*-
"""
模拟执行引擎

负责:
- 模拟市场环境
- 执行交易
- 计算交易成本
- 处理滑点
"""
import logging
from datetime import datetime
from typing import Dict, List, Any

import pandas as pd

from quant_server.core.engines.base.engine_base import EngineBase
from quant_server.modules.backtest.simulators.cost_simulator import CostSimulator
from quant_server.modules.backtest.simulators.market_simulator import MarketSimulator
from quant_server.modules.backtest.simulators.slippage_simulator import SlippageSimulator

logger = logging.getLogger(__name__)


class SimulationEngine(EngineBase):
	"""
	模拟执行引擎

	负责模拟市场环境和交易执行
	"""

	def __init__ (self, config, event_engine=None, resource_pool=None):
		"""
		初始化模拟执行引擎
		"""
		super().__init__(config=config, event_engine=event_engine, resource_pool=resource_pool)

		# 模拟器
		self.market_simulator = MarketSimulator()
		self.cost_simulator = CostSimulator()
		self.slippage_simulator = SlippageSimulator()

		# 交易记录
		self.trades: List[Dict[str, Any]] = []

		# 持仓信息
		self.positions: Dict[str, Dict[str, Any]] = {}

		# 账户信息
		self.account = {
			"initial_capital": 0.0,
			"available_capital": 0.0,
			"total_equity": 0.0
		}

	async def _on_initialize (self):
		"""
		引擎初始化逻辑
		"""
		logger.info(f"模拟执行引擎 {self.config.name} 初始化")
		# 重置状态
		self.trades = []
		self.positions = {}
		self.account = {
			"initial_capital": 0.0,
			"available_capital": 0.0,
			"total_equity": 0.0
		}

	async def _on_start (self):
		"""
		引擎启动逻辑
		"""
		logger.info(f"模拟执行引擎 {self.config.name} 启动")

	async def _on_stop (self):
		"""
		引擎停止逻辑
		"""
		logger.info(f"模拟执行引擎 {self.config.name} 停止")
		# 清理状态
		self.trades = []
		self.positions = {}

	async def _on_pause (self):
		"""
		引擎暂停逻辑
		"""
		logger.info(f"模拟执行引擎 {self.config.name} 暂停")

	async def _on_resume (self):
		"""
		引擎恢复逻辑
		"""
		logger.info(f"模拟执行引擎 {self.config.name} 恢复")

	async def _on_force_stop (self):
		"""
		引擎强制停止逻辑
		"""
		logger.warning(f"模拟执行引擎 {self.config.name} 强制停止")
		# 清理状态
		self.trades = []
		self.positions = {}

	async def _on_health_check (self) -> Dict[str, Any]:
		"""
		健康检查逻辑
		"""
		return {
			"trades_executed": len(self.trades),
			"positions_held": len(self.positions),
			"total_equity": self.account.get("total_equity", 0.0)
		}

	def _validate_config (self):
		"""
		验证配置
		"""
		if not self.config:
			raise ValueError("模拟执行引擎配置不能为空")

	async def initialize (self) -> bool:
		"""
		初始化引擎

		Returns:
			bool: 初始化是否成功
		"""
		try:
			logger.info(f"模拟执行引擎 {self.config.name} 初始化")
			# 重置状态
			self.trades = []
			self.positions = {}
			self.account = {
				"initial_capital": 0.0,
				"available_capital": 0.0,
				"total_equity": 0.0
			}
			logger.info("模拟执行引擎初始化完成")
			return True
		except Exception as e:
			logger.error(f"模拟执行引擎初始化失败: {str(e)}")
			return False

	def execute_trade (self, signal: Dict[str, Any], market_data: pd.DataFrame) -> Dict[str, Any]:
		"""
		执行交易

		Args:
			signal: 交易信号
			market_data: 市场数据

		Returns:
			交易执行结果
		"""
		try:
			# 验证交易信号格式
			required_fields = ["symbol", "side", "volume", "datetime"]
			for field in required_fields:
				if field not in signal:
					logger.warning(f"交易信号缺少字段: {field}")
					return {"success": False, "error": f"交易信号缺少字段: {field}"}

			symbol = signal["symbol"]
			side = signal["side"]
			volume = signal["volume"]
			timestamp = signal["datetime"]

			# 验证交易信号数据
			if not isinstance(symbol, str):
				return {"success": False, "error": "交易信号: symbol 必须是字符串"}
			if side not in ["BUY", "SELL"]:
				return {"success": False, "error": "交易信号: side 必须是 BUY 或 SELL"}
			if not isinstance(volume, (int, float)) or volume <= 0:
				return {"success": False, "error": "交易信号: volume 必须是正数"}
			if not isinstance(timestamp, (datetime, str)):
				return {"success": False, "error": "交易信号: datetime 必须是 datetime 或字符串"}

			# 验证市场数据格式
			if not isinstance(market_data, pd.DataFrame):
				return {"success": False, "error": "市场数据必须是 DataFrame"}
			if not all(col in market_data.columns for col in ["open", "high", "low", "close", "volume"]):
				return {"success": False, "error": "市场数据缺少必要的列"}

			# 获取当前价格
			current_price = self.market_simulator.get_price(market_data, symbol, timestamp)
			if current_price is None:
				logger.warning(f"无法获取价格: {symbol}, {timestamp}")
				return {"success": False, "error": "无法获取价格"}

			# 计算滑点
			slippage = self.slippage_simulator.calculate_slippage(side, volume, current_price)
			execution_price = current_price * (1 + slippage)

			# 计算交易成本
			cost = self.cost_simulator.calculate_cost(side, volume, execution_price)

			# 计算交易金额
			trade_amount = execution_price * volume
			total_cost = trade_amount + cost["total"]

			# 初始化profit变量
			profit = 0.0

			# 检查资金是否足够
			if side == "BUY" and total_cost > self.account["available_capital"]:
				logger.warning(f"资金不足: 可用资金 {self.account['available_capital']}, 交易金额 {total_cost}")
				return {"success": False, "error": "资金不足"}

			# 执行交易
			if side == "BUY":
				# 买入
				self.account["available_capital"] -= total_cost

				if symbol in self.positions:
					# 已有持仓，更新
					position = self.positions[symbol]
					total_volume = position["volume"] + volume
					total_cost = position["volume"] * position["cost_price"] + trade_amount
					position["volume"] = total_volume
					position["cost_price"] = total_cost / total_volume
				else:
					# 新持仓
					self.positions[symbol] = {
						"symbol": symbol,
						"volume": volume,
						"cost_price": execution_price,
						"current_price": execution_price,
						"last_updated": timestamp
					}
			elif side == "SELL":
				# 卖出
				if symbol not in self.positions or self.positions[symbol]["volume"] < volume:
					logger.warning(f"持仓不足: 持仓 {self.positions.get(symbol, {}).get('volume', 0)}, 卖出 {volume}")
					return {"success": False, "error": "持仓不足"}

				position = self.positions[symbol]
				profit = (execution_price - position["cost_price"]) * volume
				self.account["available_capital"] += trade_amount - cost["total"]

				# 更新持仓
				position["volume"] -= volume
				if position["volume"] == 0:
					del self.positions[symbol]
				else:
					position["last_updated"] = timestamp

			# 记录交易
			trade = {
				"symbol": symbol,
				"side": side,
				"price": execution_price,
				"volume": volume,
				"cost": cost,
				"amount": trade_amount,
				"datetime": timestamp,
				"profit": profit
			}
			self.trades.append(trade)

			# 更新账户权益
			self.update_equity(market_data, timestamp)

			logger.info(f"交易执行成功: {side} {volume} {symbol} @ {execution_price}")

			return {
				"success": True,
				"trade": trade
			}
		except Exception as e:
			logger.error(f"交易执行失败: {str(e)}")
			return {"success": False, "error": str(e)}


	def update_equity (self, market_data: pd.DataFrame, timestamp: datetime) -> None:


		"""
		更新账户权益

		Args:
			market_data: 市场数据
			timestamp: 时间
		"""
		try:
			# 计算持仓市值
			positions_value = 0.0
			for symbol, position in self.positions.items():
				current_price = self.market_simulator.get_price(market_data, symbol, timestamp)
				if current_price is not None:
					position["current_price"] = current_price
					position["last_updated"] = timestamp
					positions_value += current_price * position["volume"]

			# 更新总权益
			self.account["total_equity"] = self.account["available_capital"] + positions_value

		except Exception as e:
			logger.error(f"更新账户权益失败: {str(e)}")


	def get_positions (self) -> Dict[str, Dict[str, Any]]:
		"""
		获取当前持仓

		Returns:
			持仓信息
		"""
		return self.positions


	def get_trades (self) -> List[Dict[str, Any]]:
		"""
		获取交易记录

		Returns:
			交易记录
		"""
		return self.trades


	def get_account (self) -> Dict[str, float]:
		"""
		获取账户信息

		Returns:
			账户信息
		"""
		return self.account


	def calculate_metrics (self) -> Dict[str, float]:
		"""
		计算绩效指标

		Returns:
			绩效指标
		"""
		try:
			initial = self.account["initial_capital"]
			final = self.account["total_equity"]
			total_return = (final - initial) / initial

			# 计算交易相关指标
			win_trades = [t for t in self.trades if t.get("profit", 0) > 0]
			loss_trades = [t for t in self.trades if t.get("profit", 0) <= 0]

			win_rate = len(win_trades) / len(self.trades) if self.trades else 0.0
			avg_win = sum(t["profit"] for t in win_trades) / len(win_trades) if win_trades else 0.0
			avg_loss = sum(t["profit"] for t in loss_trades) / len(loss_trades) if loss_trades else 0.0
			profit_factor = (sum(t["profit"] for t in win_trades) /
			                 abs(sum(t["profit"] for t in loss_trades))) if loss_trades else float('inf')

			metrics = {
				"total_return": total_return,
				"num_trades": len(self.trades),
				"win_rate": win_rate,
				"avg_win": avg_win,
				"avg_loss": avg_loss,
				"profit_factor": profit_factor
			}

			return metrics
		except Exception as e:
			logger.error(f"计算绩效指标失败: {str(e)}")
			return {}