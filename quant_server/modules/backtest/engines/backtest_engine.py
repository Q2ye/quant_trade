# -*- coding: utf-8 -*-
"""
回测引擎

负责:
- 加载策略
- 执行回测
- 计算绩效指标
- 生成报告
"""
import logging
from datetime import datetime
from typing import Dict, List, Any, Type

import pandas as pd


from quant_server.core.engines.base.engine_base import EngineBase
from quant_server.core.engines.types.entities import BarData
from quant_server.modules.strategy.constants import StrategyType, StrategyLifecycleStatus
from quant_server.modules.strategy.models import (
	StrategyInstance,
	StrategyConfig
)
from quant_server.modules.strategy.strategies.base.base_strategy import BaseStrategy
from quant_server.modules.strategy.strategies.base.strategy_context import StrategyContext

logger = logging.getLogger(__name__)


class BacktestEngine(EngineBase):
	"""
	回测引擎

	负责策略回测的执行和结果分析

	属性:
		strategies: 回测策略实例
		results: 回测结果
	"""

	def __init__ (self, config, event_engine=None, resource_pool=None):
		"""初始化回测引擎"""
		super().__init__(config=config, event_engine=event_engine, resource_pool=resource_pool)

		# 策略实例 {strategy_id: StrategyInstance}
		self.strategies: Dict[int, StrategyInstance] = {}

		# 策略类注册表 {strategy_type: StrategyClass}
		self._strategy_registry: Dict[StrategyType, Type[BaseStrategy]] = {}

		# 回测结果 {strategy_id: Dict[str, Any]}
		self.results: Dict[int, Dict[str, Any]] = {}

		# 历史数据缓存
		self._data_cache: Dict[str, pd.DataFrame] = {}

		# 策略实例缓存 {strategy_id: BaseStrategy}
		self._strategy_instances: Dict[int, BaseStrategy] = {}

	async def _on_initialize (self):
		"""
		引擎初始化逻辑
		"""
		logger.info(f"回测引擎 {self.config.name} 初始化")
		# 初始化策略注册表
		self._strategy_registry = {}
		# 初始化策略实例缓存
		self._strategy_instances = {}

	async def _on_start (self):
		"""
		引擎启动逻辑
		"""
		logger.info(f"回测引擎 {self.config.name} 启动")

	async def _on_stop (self):
		"""
		引擎停止逻辑
		"""
		logger.info(f"回测引擎 {self.config.name} 停止")
		# 清理缓存
		self._data_cache.clear()
		self._strategy_instances.clear()

	async def _on_pause (self):
		"""
		引擎暂停逻辑
		"""
		logger.info(f"回测引擎 {self.config.name} 暂停")

	async def _on_resume (self):
		"""
		引擎恢复逻辑
		"""
		logger.info(f"回测引擎 {self.config.name} 恢复")

	async def _on_force_stop (self):
		"""
		引擎强制停止逻辑
		"""
		logger.warning(f"回测引擎 {self.config.name} 强制停止")
		# 清理缓存
		self._data_cache.clear()
		self._strategy_instances.clear()

	async def _on_health_check (self) -> Dict[str, Any]:
		"""
		健康检查逻辑
		"""
		return {
			"strategies_loaded": len(self.strategies),
			"results_cached": len(self.results),
			"data_cache_size": len(self._data_cache)
		}

	def _validate_config (self):
		"""
		验证配置
		"""
		if not self.config:
			raise ValueError("回测引擎配置不能为空")

	def register_strategy (
			self,
			strategy_type: StrategyType,
			strategy_class: Type[BaseStrategy]
	) -> None:
		"""
		注册策略类

		Args:
			strategy_type: 策略类型
			strategy_class: 策略类
		"""
		self._strategy_registry[strategy_type] = strategy_class
		logger.info(f"注册策略类: {strategy_type.value} -> {strategy_class.__name__}")

	def load_strategy (
			self,
			strategy_id: str,
			name: str,
			strategy_type: StrategyType,
			code: str,
			parameters: Dict[str, Any],
			config: StrategyConfig,
	) -> StrategyInstance:
		"""
		加载策略

		Args:
			strategy_id: 策略ID
			name: 策略名称
			strategy_type: 策略类型
			code: 策略代码
			parameters: 策略参数
			config: 策略配置

		Returns:
			策略实例
		"""
		# 创建策略实例对象
		instance = StrategyInstance(
			id=strategy_id,
			name=name,
			strategy_type=strategy_type,
			status=StrategyLifecycleStatus.COMPILED,
			user_id=config.user_id if hasattr(config, 'user_id') else 0,
			code=code,
			parameters=parameters,
			capital=config.initial_capital,
		)

		# 保存策略实例
		self.strategies[strategy_id] = instance

		logger.info(f"策略加载成功: {strategy_id}, {name}")

		return instance

	def initialize_strategy (
			self,
			strategy_id: str,
			context: StrategyContext,
	) -> BaseStrategy:
		"""
		初始化策略

		Args:
			strategy_id: 策略ID
			context: 策略上下文

		Returns:
			策略实例
		"""
		if strategy_id not in self.strategies:
			raise ValueError(f"策略 {strategy_id} 未加载")

		strategy_instance = self.strategies[strategy_id]

		# 检查策略实例缓存
		if strategy_id in self._strategy_instances:
			strategy = self._strategy_instances[strategy_id]
			# 更新上下文
			strategy.context = context
			logger.info(f"使用缓存的策略实例: {strategy_id}")
			return strategy

		# 获取策略类并初始化
		strategy_type = strategy_instance.strategy_type
		strategy_class = self._strategy_registry.get(strategy_type)
		if not strategy_class:
			raise ValueError(f"未注册的策略类型: {strategy_type}")

		# 创建策略对象
		strategy = strategy_class(
			name=strategy_instance.name,
			strategy_type=strategy_type,
			parameters=strategy_instance.parameters,
		)

		# 注入上下文
		strategy.context = context
		strategy.initialize()

		# 缓存策略实例
		self._strategy_instances[strategy_id] = strategy

		# 更新实例状态
		strategy_instance.status = StrategyLifecycleStatus.COMPILED

		logger.info(f"策略初始化成功: {strategy_id}")
		return strategy

	def run_backtest (
			self,
			strategy_id: str,
			data: Dict[str, pd.DataFrame],
			context: StrategyContext
	) -> Dict[str, Any]:
		"""
		执行回测

		Args:
			strategy_id: 策略ID
			data: 回测数据 {symbol: DataFrame}
			context: 策略上下文

		Returns:
			回测结果
		"""
		if strategy_id not in self.strategies:
			raise ValueError(f"策略 {strategy_id} 未加载")

		# 验证数据格式
		if not isinstance(data, dict):
			raise ValueError("数据格式必须是字典")
		for symbol, df in data.items():
			if not isinstance(df, pd.DataFrame):
				raise ValueError(f"符号 {symbol} 的数据必须是 DataFrame")
			# 验证 DataFrame 包含必要的列
			required_columns = ['open', 'high', 'low', 'close', 'volume']
			if not all(col in df.columns for col in required_columns):
				raise ValueError(f"数据缺少必要的列: {required_columns}")

		# 初始化策略并获取策略实例
		strategy = self.initialize_strategy(strategy_id, context)

		# 执行回测
		signals = []
		for symbol, df in data.items():
			for _, row in df.iterrows():
				# 提取标量值
				# 确保从pandas Series中提取标量值并转换为float
				open_val = float(row['open'].iloc[0]) if hasattr(row['open'], 'iloc') else row['open']
				high_val = float(row['high'].iloc[0]) if hasattr(row['high'], 'iloc') else row['high']
				low_val = float(row['low'].iloc[0]) if hasattr(row['low'], 'iloc') else row['low']
				close_val = float(row['close'].iloc[0]) if hasattr(row['close'], 'iloc') else row['close']
				volume_val = float(row['volume'].iloc[0]) if hasattr(row['volume'], 'iloc') else row['volume']
				amount_val = volume_val * close_val
				
				bar_data = BarData(
					ts_code=symbol,
					period="daily",
					open=open_val,
					high=high_val,
					low=low_val,
					close=close_val,
					volume=volume_val,
					amount=amount_val,
					trade_date=row.name
				)
				signals.extend(strategy.on_bar(bar_data))

		# 保存结果
		result = {
			'signals': signals,
			'initial_capital': context.initial_capital,
			'final_capital': context.available_capital,
			'start_time': datetime.now(),
			'end_time': datetime.now()
		}

		self.results[strategy_id] = result

		logger.info(f"回测执行完成: {strategy_id}")

		return result

	def calculate_metrics (self, strategy_id: Any) -> Dict[str, float]:
		"""
		计算绩效指标

		Args:
			strategy_id: 策略ID

		Returns:
			绩效指标
		"""
		if strategy_id not in self.results:
			raise ValueError(f"策略 {strategy_id} 没有回测结果")

		result = self.results[strategy_id]
		signals = result['signals']

		# 计算基础指标
		initial = result['initial_capital']
		final = result['final_capital']
		total_return = (final - initial) / initial
		duration_days = (result['end_time'] - result['start_time']).days

		# 计算交易相关指标
		win_signals = [s for s in signals if s.profit_pct > 0]
		loss_signals = [s for s in signals if s.profit_pct <= 0]

		win_rate = len(win_signals) / len(signals) if signals else 0
		avg_win = sum(s.profit_pct for s in win_signals) / len(win_signals) if win_signals else 0
		avg_loss = sum(s.profit_pct for s in loss_signals) / len(loss_signals) if loss_signals else 0
		profit_factor = (sum(s.profit_pct for s in win_signals) /
		                 abs(sum(s.profit_pct for s in loss_signals))) if loss_signals else float('inf')

		# 年化收益率
		annualized_return = (1 + total_return) ** (365 / duration_days) - 1 if duration_days > 0 else 0

		# 计算最大回撤
		max_drawdown = self._calculate_max_drawdown(signals, initial)

		# 计算夏普比率（假设无风险利率为0）
		sharpe_ratio = self._calculate_sharpe_ratio(signals, annualized_return)

		metrics = {
			'total_return': total_return,
			'annualized_return': annualized_return,
			'num_signals': len(signals),
			'win_rate': win_rate,
			'avg_win_pct': avg_win,
			'avg_loss_pct': avg_loss,
			'profit_factor': profit_factor,
			'duration_days': duration_days,
			'max_drawdown': max_drawdown,
			'sharpe_ratio': sharpe_ratio
		}

		return metrics

	@staticmethod
	def _calculate_max_drawdown (signals, initial_capital):
		"""
		计算最大回撤
		
		Args:
			signals: 交易信号列表
			initial_capital: 初始资金
			
		Returns:
			最大回撤
		"""
		if not signals:
			return 0.0

		# 计算累计权益
		equity = initial_capital
		equity_curve = [equity]

		for signal in signals:
			# 假设每个信号的利润已经计算
			if hasattr(signal, 'profit'):
				equity += signal.profit
				equity_curve.append(equity)

		# 计算最大回撤
		max_equity = equity_curve[0]
		max_drawdown = 0.0

		for eq in equity_curve[1:]:
			if eq > max_equity:
				max_equity = eq
			else:
				drawdown = (max_equity - eq) / max_equity
				if drawdown > max_drawdown:
					max_drawdown = drawdown

		return max_drawdown

	@staticmethod
	def _calculate_sharpe_ratio (signals, annualized_return):
		"""
		计算夏普比率
		
		Args:
			signals: 交易信号列表
			annualized_return: 年化收益率
			
		Returns:
			夏普比率
		"""
		if not signals:
			return 0.0

		# 计算日收益率
		daily_returns = []
		for signal in signals:
			if hasattr(signal, 'profit_pct'):
				daily_returns.append(signal.profit_pct)

		if not daily_returns:
			return 0.0

		# 计算标准差
		import numpy as np
		std_dev = np.std(daily_returns)

		if std_dev == 0:
			return 0.0

		# 计算夏普比率（假设无风险利率为0）
		sharpe_ratio = annualized_return / std_dev * np.sqrt(252)  # 252个交易日

		return float(sharpe_ratio)

	async def run_parallel_backtests (
			self,
			strategy_ids: List[int],
			data: Dict[str, pd.DataFrame],
			contexts: Dict[int, StrategyContext]
	) -> Dict[int, Dict[str, Any]]:
		"""
		并行执行多个策略的回测

		Args:
			strategy_ids: 策略ID列表
			data: 回测数据 {symbol: DataFrame}
			contexts: 策略上下文字典 {strategy_id: StrategyContext}

		Returns:
			回测结果字典 {strategy_id: result}
		"""
		import asyncio

		async def run_single_backtest (strategy_id):
			"""执行单个策略的回测"""
			try:
				context = contexts[strategy_id]
				result = await asyncio.to_thread(
					self.run_backtest,
					strategy_id,
					data,
					context
				)
				return strategy_id, result
			except Exception as e:
				logger.error(f"策略 {strategy_id} 回测失败: {str(e)}")
				return strategy_id, {"error": str(e)}

		# 创建并执行所有回测任务
		tasks = [run_single_backtest(sid) for sid in strategy_ids]
		results = await asyncio.gather(*tasks)

		# 整理结果
		return {sid: result for sid, result in results}