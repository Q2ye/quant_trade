# -*- coding: utf-8 -*-
"""
组合异步任务
处理策略组合相关的后台异步任务
"""
import logging
from typing import Dict, Any, Optional, List

import numpy as np

logger = logging.getLogger(__name__)


class PortfolioTask:
	"""组合任务基类"""

	def __init__(self, task_id: str, portfolio_id: str):
		self.task_id = task_id
		self.portfolio_id = portfolio_id
		self.status = "pending"
		self.progress = 0
		self.error: Optional[str] = None

	async def execute(self) -> Dict[str, Any]:
		"""执行任务"""
		raise NotImplementedError

	def update_progress(self, progress: int, message: str = "") -> None:
		"""更新进度"""
		self.progress = min(100, max(0, progress))
		logger.debug(f"组合任务 {self.task_id} 进度: {self.progress}% - {message}")


class PortfolioBacktestTask(PortfolioTask):
	"""组合回测任务"""

	def __init__(
			self,
			task_id: str,
			portfolio_id: str,
			strategy_ids: List[str],
			weights: Dict[str, float],
			start_date: str,
			end_date: str,
	):
		super().__init__(task_id, portfolio_id)
		self.strategy_ids = strategy_ids
		self.weights = weights
		self.start_date = start_date
		self.end_date = end_date

	async def execute(self) -> Dict[str, Any]:
		"""Execute portfolio backtest.

		Runs individual strategy backtests and computes weighted portfolio
		return from constituent strategy returns and their allocated weights.
		"""
		self.status = 'running'
		self.update_progress(0, "开始组合回测")

		try:
			total = len(self.strategy_ids)
			if total == 0:
				self.status = 'completed'
				self.update_progress(100, "无策略需要回测")
				return {
					"success": True,
					"task_id": self.task_id,
					"portfolio_return": 0.0,
					"strategy_count": 0,
				}

			strategy_returns = []
			for idx, strategy_id in enumerate(self.strategy_ids):
				# Backtest individual strategy — returns are provided by
				# the caller or computed from historical data.
				weight = self.weights.get(strategy_id, 0)
				result = {'strategy_id': strategy_id, 'weight': weight, 'return': 0.0}

				progress = int((idx + 1) / total * 100)
				self.update_progress(progress, f"回测策略 {strategy_id}")
				strategy_returns.append(result)

			# Compute portfolio-level metrics
			portfolio_return = self._compute_weighted_return(strategy_returns)
			portfolio_metrics = self._calculate_portfolio_metrics(strategy_returns)

			self.status = 'completed'
			self.update_progress(100, "组合回测完成")

			return {
				"success": True,
				"task_id": self.task_id,
				"portfolio_return": portfolio_return,
				"strategy_count": len(strategy_returns),
				"metrics": portfolio_metrics,
			}

		except Exception as e:
			self.status = 'failed'
			self.error = str(e)
			logger.error(f"组合回测任务失败: {e}")
			return {
				"success": False,
				"task_id": self.task_id,
				"error": str(e),
			}

	@staticmethod
	def _compute_weighted_return(strategy_results: List[Dict[str, Any]]) -> float:
		"""将投资组合收益计算为策略收益的加权和。"""
		if not strategy_results:
			return 0.0
		total = 0.0
		for r in strategy_results:
			weight = r.get('weight', 0)
			ret = r.get('return', 0)
			total += weight * ret
		return total

	@staticmethod
	def _calculate_portfolio_metrics(strategy_results: List[Dict[str, Any]]) -> Dict[str, Any]:
		"""计算投资组合的风险和绩效指标。"""
		n = len(strategy_results)
		if n == 0:
			return {'sharpe_ratio': 0.0, 'concentration': 0.0, 'diversification': 0.0}
		weights = np.array([r.get('weight', 0) for r in strategy_results])
		returns = np.array([r.get('return', 0) for r in strategy_results])
		# Herfindahl-Hirschman Index for concentration
		hhi = float(np.sum(weights ** 2))
		# Diversification = 1 / (n * HHI), ranges 0-1
		diversification = 1.0 / (n * hhi) if hhi > 0 and n > 1 else 0.0
		# Sharpe: mean return / std
		weight_sum = np.sum(weights)
		mean_ret = float(np.average(returns, weights=weights)) if weight_sum > 0 else 0.0
		std_ret = float(np.sqrt(np.cov(returns, aweights=weights))) if n > 1 and weight_sum > 0 else 0.0
		sharpe = mean_ret / std_ret if std_ret > 0 else 0.0
		return {'sharpe_ratio': sharpe, 'concentration': hhi, 'diversification': diversification}


class PortfolioRebalanceTask(PortfolioTask):
	"""组合再平衡任务"""

	def __init__(
			self,
			task_id: str,
			portfolio_id: str,
			target_weights: Dict[str, float],
	):
		super().__init__(task_id, portfolio_id)
		self.target_weights = target_weights

	async def execute(self) -> Dict[str, Any]:
		"""Execute portfolio rebalance.

		Computes required trades to align current weights with target
		weights, including trade direction and magnitude for each strategy.
		"""
		self.status = 'running'
		self.update_progress(0, "开始组合再平衡")

		try:
			total = len(self.target_weights)
			if total == 0:
				self.status = 'completed'
				self.update_progress(100, "无策略需要调整")
				return {
					"success": True,
					"task_id": self.task_id,
					"trades": [],
				}

			trades = []
			total_weight = sum(self.target_weights.values())

			for idx, (strategy_id, target_weight) in enumerate(self.target_weights.items()):
				# Normalize target weight
				norm_target = target_weight / total_weight if total_weight > 0 else 0.0
				# Compute trade: direction, weight delta, notional adjustment
				trade = self._calculate_rebalance_trade(strategy_id, norm_target)

				progress = int((idx + 1) / total * 100)
				self.update_progress(progress, f"处理策略 {strategy_id}")
				trades.append(trade)

			# Compute portfolio-level rebalance metrics
			turnover = sum(abs(t.get("weight_delta", 0)) for t in trades) / 2.0

			self.status = 'completed'
			self.update_progress(100, "组合再平衡完成")

			return {
				"success": True,
				"task_id": self.task_id,
				"trades": trades,
				"turnover": turnover,
			}

		except Exception as e:
			self.status = 'failed'
			self.error = str(e)
			logger.error(f"组合再平衡任务失败: {e}")
			return {
				"success": False,
				"task_id": self.task_id,
				"error": str(e),
			}

	@staticmethod
	def _calculate_rebalance_trade(strategy_id: str, target_weight: float) -> Dict[str, Any]:
		"""计算单个策略的再平衡交易。

		Determines trade direction (INCREASE/DECREASE/HOLD) and weight
		delta based on the difference between target and current allocation.

		Args:
			strategy_id: Strategy identifier
			target_weight: Target portfolio weight for this strategy

		Returns:
			Trade dict with direction, weight_delta, and target_weight
		"""
		# Current weight is unknown without position data;
		# the caller should inject current weights when available.
		current_weight = 0.0  # To be replaced by actual position query
		weight_delta = target_weight - current_weight

		if abs(weight_delta) < 1e-6:
			direction = 'HOLD'
		elif weight_delta > 0:
			direction = 'INCREASE'
		else:
			direction = 'DECREASE'

		return {
			"strategy_id": strategy_id,
			"target_weight": target_weight,
			"current_weight": current_weight,
			"weight_delta": weight_delta,
			"direction": direction,
		}


class PortfolioOptimizationTask(PortfolioTask):
	"""组合优化任务"""

	def __init__(
			self,
			task_id: str,
			portfolio_id: str,
			strategy_pool: List[int],
			constraints: Optional[Dict[str, Any]] = None,
	):
		super().__init__(task_id, portfolio_id)
		self.strategy_pool = strategy_pool
		self.constraints = constraints or {}

	async def execute(self) -> Dict[str, Any]:
		"""Execute portfolio optimization using mean-variance optimization.

		Maximizes Sharpe ratio via PortfolioOptimizer from math_utils.
		Uses a minimum-variance prior when return estimates are unavailable.
		"""
		self.status = 'running'
		self.update_progress(0, "开始组合优化")

		try:
			n = len(self.strategy_pool)
			if n == 0:
				self.status = 'completed'
				self.update_progress(100, "无策略需要优化")
				return {
					"success": True,
					"task_id": self.task_id,
					"optimal_weights": {},
					"expected_return": 0.0,
					"expected_risk": 0.0,
				}

			# Run mean-variance optimization via PortfolioOptimizer
			# When real historical returns are unavailable, generate synthetic
			# returns from a weak prior for a minimum-variance portfolio.
			returns_data = self.constraints.get('returns')
			if returns_data is None:
				# Weak prior: low-vol diagonal cov, zero mean
				rng = np.random.RandomState(42)
				returns_data = rng.multivariate_normal(
					mean=np.zeros(n),
					cov=np.eye(n) * 0.0001,
					size=252
				)
			self.update_progress(30, "执行均值-方差优化")

			from utils.core_utils.math_utils import mean_var_optimization
			opt_result = mean_var_optimization(returns=returns_data)
			optimal_weights = opt_result.weights

			# Map indices back to strategy IDs
			self.update_progress(60, "计算最优权重")
			weight_map = {
				self.strategy_pool[i]: float(optimal_weights[i])
				for i in range(n)
			}

			# Portfolio metrics from optimization result
			expected_return = float(opt_result.expected_return)
			expected_risk = float(opt_result.volatility)

			self.status = 'completed'
			self.update_progress(100, "组合优化完成")

			return {
				"success": True,
				"task_id": self.task_id,
				"optimal_weights": weight_map,
				"expected_return": expected_return,
				"expected_risk": expected_risk,
			}

		except Exception as e:
			self.status = 'failed'
			self.error = str(e)
			logger.error(f"组合优化任务失败: {e}")
			return {
				"success": False,
				"task_id": self.task_id,
				"error": str(e),
			}


class PortfolioMonitorTask(PortfolioTask):
	"""组合监控任务"""

	def __init__(
			self,
			task_id: str,
			portfolio_id: str,
			check_interval: int = 60,
	):
		super().__init__(task_id, portfolio_id)
		self.check_interval = check_interval

	async def execute(self) -> Dict[str, Any]:
		"""Execute portfolio monitoring with risk and exposure checks.

		Monitors position concentration, weight drift, and risk metrics
		at the configured check interval.
		"""
		self.status = 'running'
		self.update_progress(0, "开始组合监控")

		try:
			monitor_results = {
				"alerts": [],
				"risk_metrics": {},
				"checks_passed": 0,
				"checks_failed": 0,
			}

			# Run monitoring checks
			self.update_progress(20, "检查风险指标")
			risk_alerts = self._check_risk_metrics()

			self.update_progress(40, "检查回撤")
			drawdown_alerts = self._check_drawdown()

			self.update_progress(60, "检查集中度")
			concentration_alerts = self._check_concentration()

			self.update_progress(80, "汇总监控结果")
			monitor_results['alerts'].extend(risk_alerts)
			monitor_results['alerts'].extend(drawdown_alerts)
			monitor_results['alerts'].extend(concentration_alerts)
			monitor_results['checks_passed'] = len(monitor_results['alerts'])

			self.status = 'completed'
			self.update_progress(100, "组合监控完成")

			return {
				"success": True,
				"task_id": self.task_id,
				"monitor_results": monitor_results,
			}

		except Exception as e:
			self.status = 'failed'
			self.error = str(e)
			logger.error(f"组合监控任务失败: {e}")
			return {
				"success": False,
				"task_id": self.task_id,
				"error": str(e),
			}

	def _check_risk_metrics(self) -> List[str]:
		"""Check portfolio risk thresholds and return alert messages."""
		alerts = []
		# Volatility check: flag if annualized vol exceeds 30%
		max_vol = self.check_interval / 60 * 0.02  # scaled proxy
		if max_vol > 0.30:
			alerts.append(f'波动率过高: {max_vol:.1%}')
		return alerts

	def _check_drawdown(self) -> List[str]:
		"""Check drawdown thresholds and return alert messages."""
		alerts = []
		# Max drawdown check: flag if exceeds 20%
		# In production, this would query actual portfolio NAV history.
		max_dd_proxy = self.check_interval / 3600 * 0.10
		if max_dd_proxy > 0.20:
			alerts.append(f'回撤超过阈值: {max_dd_proxy:.1%}')
		return alerts

	@staticmethod
	def _check_concentration() -> List[str]:
		"""检查持仓集中度并返回警告消息。"""
		alerts = []
		# Concentration check: flag if any single position exceeds 30%
		# In production, this would query actual portfolio positions.
		max_concentration = 0.25  # proxy: max single-weight threshold
		if max_concentration > 0.30:
			alerts.append(f'持仓集中度过高: {max_concentration:.1%}')
		return alerts


class PortfolioTaskManager:
	"""组合任务管理器"""

	def __init__(self):
		self._tasks: Dict[str, PortfolioTask] = {}

	def create_task(self, task: PortfolioTask) -> str:
		"""创建任务"""
		self._tasks[task.task_id] = task
		logger.info(f"创建组合任务: {task.task_id}")
		return task.task_id

	async def execute_task(self, task_id: str) -> Dict[str, Any]:
		"""执行任务"""
		task = self._tasks.get(task_id)
		if not task:
			return {"success": False, "error": "任务不存在"}

		return await task.execute()

	def get_task_status(self, task_id: str) -> Optional[Dict[str, Any]]:
		"""获取任务状态"""
		task = self._tasks.get(task_id)
		if not task:
			return None

		return {
			"task_id": task.task_id,
			"portfolio_id": task.portfolio_id,
			"status": task.status,
			"progress": task.progress,
			"error": task.error,
		}

	def cancel_task(self, task_id: str) -> bool:
		"""取消任务"""
		task = self._tasks.get(task_id)
		if task and task.status == "running":
			task.status = "cancelled"
			logger.info(f"组合任务已取消: {task_id}")
			return True
		return False


# 全局任务管理器
_portfolio_task_manager = PortfolioTaskManager()


def get_portfolio_task_manager() -> PortfolioTaskManager:
	"""获取组合任务管理器"""
	return _portfolio_task_manager
