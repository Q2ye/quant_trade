# -*- coding: utf-8 -*-
"""
多因子策略
基于多因子模型进行股票选择和组合优化的Alpha策略
"""

import logging
from typing import Dict, List, Optional, Any
from datetime import datetime

import numpy as np

from core.engines.types.entities import BarData
from modules.strategy.constants import StrategyType, SignalDirection, SignalType
from modules.strategy.models import TradingSignal
from modules.strategy.strategies.base.base_strategy import BaseStrategy

logger = logging.getLogger(__name__)


class FactorStrategy(BaseStrategy):
	"""
	多因子策略类

	基于多因子模型进行股票选择和组合优化，支持：
	- 价值因子：PE、PB、股息率等
	- 成长因子：营收增长率、净利润增长率等
	- 质量因子：ROE、ROA、毛利率等
	- 动量因子：收益率、换手率等
	- 技术因子：波动率、Beta等
	"""

	def __init__ (
			self,
			name: str,
			strategy_type: StrategyType = StrategyType.ALPHA,
			parameters: Optional[Dict[str, Any]] = None
	):
		"""
		初始化多因子策略

		Args:
			name: 策略名称
			strategy_type: 策略类型
			parameters: 策略参数
		"""
		super().__init__(name, strategy_type, parameters)

		# 因子配置
		self.factors = self.parameters.get('factors', ['pe', 'pb', 'roe'])
		self.weights = self.parameters.get('weights', [0.4, 0.3, 0.3])
		self.stock_pool_size = self.parameters.get('stock_pool_size', 50)
		self.rebalance_frequency = self.parameters.get('rebalance_frequency', 20)

		# 数据缓存
		self.factor_data: Dict[str, Dict[str, float]] = {}
		self.stock_scores: Dict[str, float] = {}
		self.portfolio_weights: Dict[str, float] = {}

		# 状态变量
		self.bar_count = 0

		logger.info(f"多因子策略初始化: {name}")

	def on_init (self) -> None:
		"""策略初始化"""
		logger.info(f"多因子策略 {self.name} 初始化")

		# 验证因子配置
		if len(self.factors) != len(self.weights):
			raise ValueError("因子数量和权重数量必须一致")

		if abs(sum(self.weights) - 1.0) > 1e-6:
			raise ValueError("权重之和必须为1")

	def on_start (self) -> None:
		"""策略启动"""
		logger.info(f"多因子策略 {self.name} 启动")

	def on_stop (self) -> None:
		"""策略停止"""
		logger.info(f"多因子策略 {self.name} 停止")

	def on_bar (self, bar: BarData) -> List[TradingSignal]:
		"""
		处理K线数据，生成交易信号

		Args:
			bar: K线数据

		Returns:
			交易信号列表
		"""
		signals = []

		try:
			# 更新因子数据
			self._update_factor_data(bar)

			# 定期重平衡
			if self.bar_count % self.rebalance_frequency == 0:
				signals = self._rebalance_portfolio()

			self.bar_count += 1

		except Exception as e:
			logger.error(f"多因子策略处理K线数据失败: {e}")

		return signals

	def _update_factor_data (self, bar: BarData) -> None:
		"""
		更新因子数据

		Args:
			bar: K线数据
		"""
		# 这里应该从数据服务获取因子数据
		# 目前使用模拟数据
		if bar.ts_code not in self.factor_data:
			self.factor_data[bar.ts_code] = {}

		# 模拟因子数据
		self.factor_data[bar.ts_code]['close'] = bar.close

		# 价值因子（模拟）
		self.factor_data[bar.ts_code]['pe'] = np.random.normal(15, 5)
		self.factor_data[bar.ts_code]['pb'] = np.random.normal(2, 0.5)

		# 质量因子（模拟）
		self.factor_data[bar.ts_code]['roe'] = np.random.normal(0.1, 0.05)

		# 动量因子（模拟）
		self.factor_data[bar.ts_code]['momentum'] = np.random.normal(0.02, 0.01)

	def _calculate_stock_scores (self) -> Dict[str, float]:
		"""
		计算股票综合得分

		Returns:
			股票得分字典
		"""
		scores = {}

		for ts_code, factors in self.factor_data.items():
			total_score = 0.0

			for i, factor_name in enumerate(self.factors):
				if factor_name in factors:
					factor_value = factors[factor_name]

					# 因子标准化处理
					if factor_name in ['pe', 'pb']:  # 价值因子，越小越好
						normalized_value = -factor_value
					else:  # 其他因子，越大越好
						normalized_value = factor_value

					total_score += normalized_value * self.weights[i]

			scores[ts_code] = total_score

		return scores

	def _optimize_portfolio_weights (self, scores: Dict[str, float]) -> Dict[str, float]:
		"""
		优化组合权重

		Args:
			scores: 股票得分

		Returns:
			组合权重字典
		"""
		# 按得分排序
		sorted_stocks = sorted(scores.items(), key=lambda x: x[1], reverse=True)

		# 选择前N只股票
		selected_stocks = sorted_stocks[:self.stock_pool_size]

		# 等权重分配（可扩展为优化权重）
		weight = 1.0 / len(selected_stocks) if selected_stocks else 0

		weights = {ts_code: weight for ts_code, _ in selected_stocks}

		return weights

	def _rebalance_portfolio (self) -> List[TradingSignal]:
		"""
		组合重平衡

		Returns:
			重平衡信号列表
		"""
		import uuid
		signals = []

		try:
			# 计算股票得分
			self.stock_scores = self._calculate_stock_scores()

			# 优化组合权重
			new_weights = self._optimize_portfolio_weights(self.stock_scores)

			# 生成调仓信号
			for ts_code, target_weight in new_weights.items():
				# 获取当前持仓权重（简化处理）
				current_weight = self.portfolio_weights.get(ts_code, 0)

				# 如果权重变化超过阈值，生成信号
				if abs(target_weight - current_weight) > 0.01:
					# 生成买入或卖出信号
					if target_weight > current_weight:
						direction = SignalDirection.LONG
					else:
						direction = SignalDirection.SHORT

					# 创建交易信号
					signal = TradingSignal(
						id=str(uuid.uuid4()),
						strategy_id=self.name,
						strategy_name=self.name,
						ts_code=ts_code,
						signal_type=SignalType.REBALANCE,
						direction=direction,
						price=self.factor_data[ts_code].get('close', 0),
						confidence=0.8,
						timestamp=datetime.now()
					)

					signals.append(signal)

			# 更新组合权重
			self.portfolio_weights = new_weights

			logger.info(f"多因子策略 {self.name} 完成重平衡，选中 {len(new_weights)} 只股票")

		except Exception as e:
			logger.error(f"多因子策略重平衡失败: {e}")

		return signals

	def get_factor_exposure (self) -> Dict[str, float]:
		"""
		获取组合因子暴露

		Returns:
			因子暴露字典
		"""
		exposure = {}

		for factor_name in self.factors:
			factor_exposure = 0.0

			for ts_code, weight in self.portfolio_weights.items():
				if ts_code in self.factor_data and factor_name in self.factor_data[ts_code]:
					factor_value = self.factor_data[ts_code][factor_name]
					factor_exposure += factor_value * weight

			exposure[factor_name] = factor_exposure

		return exposure

	def get_portfolio_info (self) -> Dict[str, Any]:
		"""
		获取组合信息

		Returns:
			组合信息字典
		"""
		return {
			'strategy_name': self.name,
			'stock_count': len(self.portfolio_weights),
			'factor_exposure': self.get_factor_exposure(),
			'stock_scores': self.stock_scores,
			'portfolio_weights': self.portfolio_weights
		}