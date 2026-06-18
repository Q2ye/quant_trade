# -*- coding: utf-8 -*-
"""
优化引擎

负责:
- 策略参数优化
- 网格搜索
- 遗传算法
- 贝叶斯优化
"""
import asyncio
import logging
from typing import Dict, List, Any, Optional

import numpy as np
import pandas as pd

from core.engines.base.engine_base import EngineBase
from modules.backtest.engines.backtest_engine import BacktestEngine
from modules.backtest.optimizers.bayesian_optimization import BayesianOptimization
from modules.backtest.optimizers.genetic_algorithm import GeneticAlgorithm
from modules.backtest.optimizers.grid_search import GridSearch
from modules.strategy.constants import StrategyType
from modules.strategy.strategies.base.strategy_context import StrategyContext

logger = logging.getLogger(__name__)


class OptimizationEngine(EngineBase):
	"""
	优化引擎

	负责策略参数优化
	"""

	def __init__(self, config, event_engine=None, resource_pool=None, db=None):
		"""
		初始化优化引擎

		Args:
			config: 引擎配置
			event_engine: 事件引擎
			resource_pool: 资源池
			db: 数据库会话（用于 DataFeedEngine）
		"""
		super().__init__(config=config, event_engine=event_engine, resource_pool=resource_pool)

		self.db = db

		# 优化器
		self.optimizers = {
			"grid": GridSearch(),
			"genetic": GeneticAlgorithm(),
			"bayesian": BayesianOptimization()
		}

		# 回测引擎
		self.backtest_engine = BacktestEngine(config, event_engine, resource_pool)

		# 数据引擎（延迟初始化）
		self._data_feed = None

		# 优化结果
		self.results: Dict[str, Any] = {}

		# 活跃任务
		self.active_tasks: List[asyncio.Task] = []

	async def _on_initialize(self):
		"""
		引擎初始化逻辑
		"""
		logger.info(f"优化引擎 {self.config.name} 初始化")
		# 初始化优化器
		self.optimizers = {
			"grid": GridSearch(),
			"genetic": GeneticAlgorithm(),
			"bayesian": BayesianOptimization()
		}
		# 初始化回测引擎
		self.backtest_engine = BacktestEngine(self.config, self.event_engine, self.resource_pool)

	async def _on_start(self):
		"""
		引擎启动逻辑
		"""
		logger.info(f"优化引擎 {self.config.name} 启动")

	async def _on_stop (self):
		"""
		引擎停止逻辑
		"""
		logger.info(f"优化引擎 {self.config.name} 停止")
		# 取消所有活跃任务
		for task in self.active_tasks:
			if not task.done():
				task.cancel()
		self.active_tasks.clear()

	async def _on_pause (self):
		"""
		引擎暂停逻辑
		"""
		logger.info(f"优化引擎 {self.config.name} 暂停")

	async def _on_resume (self):
		"""
		引擎恢复逻辑
		"""
		logger.info(f"优化引擎 {self.config.name} 恢复")

	async def _on_force_stop (self):
		"""
		引擎强制停止逻辑
		"""
		logger.warning(f"优化引擎 {self.config.name} 强制停止")
		# 取消所有活跃任务
		for task in self.active_tasks:
			if not task.done():
				task.cancel()
		self.active_tasks.clear()

	async def _on_health_check (self) -> Dict[str, Any]:
		"""
		健康检查逻辑
		"""
		return {
			"optimization_tasks": len(self.active_tasks),
			"backtest_engine_status": self.backtest_engine.record.status.value if hasattr(self.backtest_engine,
			                                                                              'record') else "unknown"
		}

	def _validate_config (self):
		"""
		验证配置
		"""
		if not self.config:
			raise ValueError("优化引擎配置不能为空")
		if hasattr(self.config, 'config') and "max_workers" not in self.config.config:
			self.config.config["max_workers"] = 4
			logger.warning("未配置max_workers，使用默认值4")

	async def optimize (self, strategy_id: str, parameters: Dict[str, Any], method: str = "grid") -> Dict[str, Any]:
		"""
		执行参数优化（v1.2: 补全数据加载 + 参数注入）

		Args:
			strategy_id: 策略ID
			parameters: 参数范围，格式:
				{"param_name": {"min": 1, "max": 10, "step": 1}, ...}
				或 {"param_name": [1, 5, 10], ...}
			method: 优化方法 (grid / genetic / bayesian)

		Returns:
			优化结果 {"best_parameters": {...}, "best_score": ..., "method": ...}
		"""
		try:
			if method not in self.optimizers:
				raise ValueError(f"不支持的优化方法: {method}")

			logger.info(f"开始优化策略 {strategy_id}，方法: {method}")

			optimizer = self.optimizers[method]

			# 延迟初始化 DataFeedEngine
			if self._data_feed is None and self.db is not None:
				from modules.strategy.engines.data_feed_engine import DataFeedEngine
				self._data_feed = DataFeedEngine(self.db)

			# 提取策略元信息（从 parameters 中获取，外部传入）
			meta_keys = {'_ts_code', '_start_date', '_end_date', '_initial_capital',
			             '_commission_rate', '_slippage'}
			meta = {k: parameters.pop(k) for k in meta_keys if k in parameters}

			ts_code = meta.get('_ts_code', '000001.SZ')
			start_date = meta.get('_start_date', '2024-01-01')
			end_date = meta.get('_end_date', '2024-12-31')
			initial_capital = float(meta.get('_initial_capital', 1_000_000))
			commission_rate = float(meta.get('_commission_rate', 0.0003))
			slippage = float(meta.get('_slippage', 0.001))

			# 预加载历史数据（所有优化迭代共享）
			df = pd.DataFrame()
			if self._data_feed:
				df = await self._data_feed.load_historical_data(
					symbols=[ts_code],
					start_date=start_date,
					end_date=end_date,
				)
			if df.empty:
				logger.warning(f"历史数据为空: {ts_code} {start_date}~{end_date}")
				return {"best_parameters": {}, "best_score": -float('inf'),
				        "method": method, "strategy_id": strategy_id}

			# 定义目标函数
			async def objective(**params):
				"""目标函数：使用给定参数执行回测，返回优化指标"""
				try:
					strategy_obj = self.backtest_engine._strategy_instances.get(strategy_id)
					if strategy_obj is None:
						# 尝试通过注册表创建
						strategy_class = self.backtest_engine._strategy_registry.get(
							StrategyType.CUSTOM
						)
						if strategy_class is None:
							return -float('inf')
						strategy_obj = strategy_class(
							name="optimization",
							strategy_type=StrategyType.CUSTOM,
							parameters=params,
						)

					# 应用参数到策略对象
					if hasattr(strategy_obj, 'parameters'):
						strategy_obj.parameters.update(params)

					self.backtest_engine._strategy_instances[strategy_id] = strategy_obj

					# 通过 Broker + 模拟循环执行回测
					bkr = self.backtest_engine.broker
					if bkr is None:
						from modules.backtest.engines.backtest_broker import (
							BacktestBroker, BacktestBrokerConfig,
						)
						bkr_config = BacktestBrokerConfig(
							initial_capital=initial_capital,
							commission_rate=commission_rate,
							slippage=slippage,
						)
						bkr = BacktestBroker(config=bkr_config)

					bkr.reset(initial_capital)

					# 逐日迭代
					async for trade_date, bars in self._data_feed.iter_bars(df):
						bar_dict = {b.ts_code: b for b in bars}
						bkr.match_orders(trade_date, bar_dict)

						# 策略生成信号
						signals = []
						for bar in bars:
							try:
								sigs = strategy_obj.on_bar(bar)
								if sigs:
									if isinstance(sigs, list):
										signals.extend(sigs)
									else:
										signals.append(sigs)
							except Exception as exc:
								logger.debug(f"on_bar error: {exc}")

						# 信号转订单
						for sig in signals:
							ts = sig.ts_code if hasattr(sig, 'ts_code') else ts_code
							direction = (
								sig.direction.value
								if hasattr(sig, 'direction') and hasattr(sig.direction, 'value')
								else str(sig.direction)
							)
							price = sig.price if hasattr(sig, 'price') else 0.0
							qty = sig.quantity if hasattr(sig, 'quantity') else 0
							bkr.submit_order(ts, direction, price, qty)

						bkr.mark_to_market(bar_dict)

					# 计算绩效
					equity_df = bkr.get_equity_curve()
					if equity_df.empty:
						return -float('inf')

					final = equity_df['total_assets'].iloc[-1]
					total_return = (final - initial_capital) / initial_capital

					# 年化收益
					if len(equity_df) >= 2:
						days = max(
							(equity_df['trade_date'].iloc[-1] - equity_df['trade_date'].iloc[0]).days,
							1,
						)
						annual_return = (1 + total_return) ** (365 / days) - 1
					else:
						annual_return = total_return

					# 夏普比率
					daily_returns = equity_df['cumulative_return'].diff().dropna()
					if len(daily_returns) > 1:
						vol = float(daily_returns.std())
						sharpe = float(daily_returns.mean() / vol * np.sqrt(252)) if vol > 0 else 0.0
					else:
						sharpe = 0.0

					# 综合得分：夏普比率为主，兼顾年化收益
					score = sharpe + annual_return * 0.5
					return float(score)

				except Exception as exc:
					logger.debug(f"目标函数执行失败: {exc}")
					return -float('inf')

			# 执行优化
			best_params, best_score = await optimizer.optimize(
				objective=objective,
				parameters=parameters
			)

			result = {
				"best_parameters": best_params,
				"best_score": best_score,
				"method": method,
				"strategy_id": strategy_id
			}

			self.results[strategy_id] = result

			logger.info(
				f"策略 {strategy_id} 优化完成: "
				f"最佳参数={best_params}, 最佳得分={best_score:.4f}"
			)

			return result

		except Exception as e:
			logger.error(f"参数优化失败: {str(e)}", exc_info=True)
			raise

	def get_optimization_result (self, strategy_id: str) -> Optional[Dict[str, Any]]:
		"""
		获取优化结果

		Args:
			strategy_id: 策略ID

		Returns:
			优化结果
		"""
		return self.results.get(strategy_id)

	async def run_parallel_optimizations (self, optimization_tasks: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
		"""
		并行执行多个优化任务

		Args:
			optimization_tasks: 优化任务列表

		Returns:
			优化结果列表
		"""
		try:
			async def run_single_optimization (task):
					"""执行单个优化任务"""
					try:
						result = await self.optimize(
							strategy_id=task["strategy_id"],
							parameters=task["parameters"],
							method=task.get("method", "grid")
						)
						return result
					except Exception as exception:
						logger.error(f"优化任务失败: {str(exception)}")
						return {"error": str(exception)}

			# 创建并执行所有优化任务
			tasks = [run_single_optimization(task) for task in optimization_tasks]
			results = await asyncio.gather(*tasks)

			return results
		except Exception as e:
			logger.error(f"并行优化失败: {str(e)}")
			raise