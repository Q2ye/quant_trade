"""
优化工具模块
提供投资组合优化和参数优化功能
"""

import warnings
from dataclasses import dataclass
from enum import Enum
from typing import Union, List, Optional, Dict, Any

import numpy as np
import pandas as pd
from scipy.optimize import minimize, Bounds, LinearConstraint, NonlinearConstraint
from scipy.stats import norm


class OptimizationMethod(Enum):
	"""优化方法枚举"""
	SLSP = "slsqp"  # 序列最小二 乘法
	COBYLA = "cobyla"  # 约束优化
	TRUST_CONSTR = "trust-constr"  # 信赖域约束优化


class ObjectiveType(Enum):
	"""目标函数类型枚举"""
	MINIMIZE_VARIANCE = "minimize_variance"
	MAXIMIZE_RETURN = "maximize_return"
	MAXIMIZE_SHARPE = "maximize_sharpe"
	MINIMIZE_CVAR = "minimize_cvar"
	RISK_PARITY = "risk_parity"


@dataclass
class OptimizationResult:
	"""优化结果"""
	success: bool
	message: str
	weights: np.ndarray
	expected_return: float
	volatility: float
	sharpe_ratio: float
	objective_value: float
	iterations: int
	function_calls: int


@dataclass
class EfficientFrontier:
	"""有效前沿"""
	returns: np.ndarray
	volatilities: np.ndarray
	sharpe_ratios: np.ndarray
	weights_matrix: np.ndarray


class PortfolioOptimizer:
	"""
	投资组合优化器类
	提供多种投资组合优化方法
	"""

	def __init__(self, risk_free_rate: float = 0.03,
	             method: OptimizationMethod = OptimizationMethod.SLSP):
		"""
		初始化投资组合优化器

		Args:
			risk_free_rate: 无风险利率
			method: 优化方法
		"""
		self.risk_free_rate = risk_free_rate
		self.method = method.value

	def portfolio_optimization(self,
	                           returns: Union[List[float], np.ndarray, pd.DataFrame],
	                           objective: ObjectiveType = ObjectiveType.MAXIMIZE_SHARPE,
	                           constraints: Optional[Dict[str, Any]] = None) -> OptimizationResult:
		"""
		通用投资组合优化

		Args:
			returns: 收益率序列或矩阵
			objective: 优化目标
			constraints: 约束条件

		Returns:
			OptimizationResult: 优化结果
		"""
		if isinstance(returns, (list, pd.DataFrame)):
			returns = np.array(returns)

		# 确保returns是二维数组
		if returns.ndim == 1:
			returns = returns.reshape(-1, 1)

		n_assets = returns.shape[1]

		# 计算预期收益和协方差矩阵
		expected_returns = np.mean(returns, axis=0)
		covariance_matrix = np.cov(returns, rowvar=False, ddof=1)

		# 默认约束
		if constraints is None:
			constraints = {
				'sum_to_one': True,
				'no_short': True,
				'max_weight': 1.0,
				'min_weight': 0.0,
				'target_return': None,
				'max_risk': None
			}

		# 初始权重
		x0 = np.ones(n_assets) / n_assets

		# 设置边界
		bounds = self._create_bounds(n_assets, constraints)

		# 设置约束
		constraints_list = self._create_constraints(
			n_assets, expected_returns, covariance_matrix, constraints)

		# 选择目标函数
		if objective == ObjectiveType.MINIMIZE_VARIANCE:
			objective_func = self._portfolio_variance
		elif objective == ObjectiveType.MAXIMIZE_RETURN:
			objective_func = self._negative_portfolio_return
		elif objective == ObjectiveType.MAXIMIZE_SHARPE:
			objective_func = self._negative_sharpe_ratio
		elif objective == ObjectiveType.MINIMIZE_CVAR:
			objective_func = self._portfolio_cvar
		elif objective == ObjectiveType.RISK_PARITY:
			objective_func = self._risk_parity_objective
		else:
			raise ValueError(f"不支持的优化目标: {objective}")

		# 优化参数
		args = (expected_returns, covariance_matrix, constraints)

		# 执行优化
		try:
			result = minimize(
				fun=objective_func,
				x0=x0,
				args=args,
				method=self.method,
				bounds=bounds,
				constraints=constraints_list,
				options={'maxiter': 1000, 'ftol': 1e-8}
			)

			# 检查优化结果
			if not result.success:
				warnings.warn(f"优化未成功: {result.message}")

			# 提取最优权重
			optimal_weights = result.x

			# 确保权重和为1
			if constraints.get('sum_to_one', True):
				optimal_weights = optimal_weights / np.sum(optimal_weights)

			# 计算优化指标
			portfolio_return = self._calculate_portfolio_return(
				optimal_weights, expected_returns)
			portfolio_vol = self._calculate_portfolio_volatility(
				optimal_weights, covariance_matrix)

			if portfolio_vol > 0:
				sharpe_ratio = (portfolio_return - self.risk_free_rate) / portfolio_vol
			else:
				sharpe_ratio = 0.0

			return OptimizationResult(
				success=result.success,
				message=result.message,
				weights=optimal_weights,
				expected_return=portfolio_return,
				volatility=portfolio_vol,
				sharpe_ratio=sharpe_ratio,
				objective_value=result.fun,
				iterations=result.nit,
				function_calls=result.nfev
			)

		except Exception as e:
			return OptimizationResult(
				success=False,
				message=str(e),
				weights=np.ones(n_assets) / n_assets,
				expected_return=0.0,
				volatility=0.0,
				sharpe_ratio=0.0,
				objective_value=0.0,
				iterations=0,
				function_calls=0
			)

	def markowitz_optimization(self,
	                           returns: Union[List[float], np.ndarray, pd.DataFrame],
	                           target_return: Optional[float] = None) -> OptimizationResult:
		"""
		马科维茨均值-方差优化

		Args:
			returns: 收益率序列或矩阵
			target_return: 目标收益率

		Returns:
			OptimizationResult: 优化结果
		"""
		constraints = {
			'sum_to_one': True,
			'no_short': True,
			'target_return': target_return
		}

		return self.portfolio_optimization(
			returns, ObjectiveType.MINIMIZE_VARIANCE, constraints)

	def black_litterman_optimization(self,
	                                 returns: Union[List[float], np.ndarray, pd.DataFrame],
	                                 prior_weights: np.ndarray,
	                                 views: Dict[str, Any]) -> OptimizationResult:
		"""
		Black-Litterman模型优化

		Args:
			returns: 收益率序列或矩阵
			prior_weights: 先验权重
			views: 观点字典

		Returns:
			OptimizationResult: 优化结果
		"""
		if isinstance(returns, (list, pd.DataFrame)):
			returns = np.array(returns)

		# 确保returns是二维数组
		if returns.ndim == 1:
			returns = returns.reshape(-1, 1)

		n_assets = returns.shape[1]

		# 计算市场隐含收益率
		market_weights = prior_weights
		covariance_matrix = np.cov(returns, rowvar=False, ddof=1)

		# 风险厌恶系数（通常设为2-4）
		risk_aversion = 3.0

		# 市场隐含均衡收益率 Π = λ Σ w_mkt (reverse optimization)
		implied_returns = risk_aversion * covariance_matrix @ market_weights

		# Black-Litterman 贝叶斯整合投资者观点
		if views and 'P' in views and 'Q' in views:
			P = np.atleast_2d(np.array(views['P'], dtype=float))
			Q = np.atleast_1d(np.array(views['Q'], dtype=float))
			tau = float(views.get('tau', 1.0 / max(returns.shape[0], 1)))
			# 观点误差协方差 Ω: 默认 Ω = diag(P(τΣ)Pᵀ)
			if 'Omega' in views:
				Omega = np.atleast_2d(np.array(views['Omega'], dtype=float))
			else:
				Omega = np.diag(np.diag(P @ (tau * covariance_matrix) @ P.T))
			# 后验收益率 E[R] = [(τΣ)⁻¹ + PᵀΩ⁻¹P]⁻¹ · [(τΣ)⁻¹Π + PᵀΩ⁻¹Q]
			tau_Sigma_inv = np.linalg.inv(tau * covariance_matrix)
			Omega_inv = np.linalg.inv(Omega)
			M = tau_Sigma_inv + P.T @ Omega_inv @ P
			b = tau_Sigma_inv @ implied_returns + P.T @ Omega_inv @ Q
			posterior_returns = np.linalg.solve(M, b)
			# 后验协方差 Σ_post = Σ + M⁻¹
			posterior_cov = covariance_matrix + np.linalg.inv(M)
		else:
			posterior_returns = implied_returns
			posterior_cov = covariance_matrix

		# 用后验估计进行均值-方差优化
		return self._optimize_given_estimates(
			posterior_returns, posterior_cov, n_assets=n_assets
		)

	def risk_parity_optimization(self,
	                             returns: Union[List[float], np.ndarray, pd.DataFrame]) -> OptimizationResult:
		"""
		风险平价优化

		Args:
			returns: 收益率序列或矩阵

		Returns:
			OptimizationResult: 优化结果
		"""
		constraints = {
			'sum_to_one': True,
			'no_short': True
		}

		return self.portfolio_optimization(
			returns, ObjectiveType.RISK_PARITY, constraints)

	def mean_var_optimization(self,
	                          returns: Union[List[float], np.ndarray, pd.DataFrame],
	                          target_return: Optional[float] = None,
	                          target_risk: Optional[float] = None) -> OptimizationResult:
		"""
		均值-方差优化

		Args:
			returns: 收益率序列或矩阵
			target_return: 目标收益率
			target_risk: 目标风险

		Returns:
			OptimizationResult: 优化结果
		"""
		constraints = {
			'sum_to_one': True,
			'no_short': True,
			'target_return': target_return,
			'max_risk': target_risk
		}

		if target_return is not None:
			return self.portfolio_optimization(
				returns, ObjectiveType.MINIMIZE_VARIANCE, constraints)
		elif target_risk is not None:
			return self.portfolio_optimization(
				returns, ObjectiveType.MAXIMIZE_RETURN, constraints)
		else:
			return self.portfolio_optimization(
				returns, ObjectiveType.MAXIMIZE_SHARPE, constraints)

	def minimize_risk_given_return(self,
	                               returns: Union[List[float], np.ndarray, pd.DataFrame],
	                               target_return: float) -> OptimizationResult:
		"""
		给定收益率下的最小风险优化

		Args:
			returns: 收益率序列或矩阵
			target_return: 目标收益率

		Returns:
			OptimizationResult: 优化结果
		"""
		constraints = {
			'sum_to_one': True,
			'no_short': True,
			'target_return': target_return
		}

		return self.portfolio_optimization(
			returns, ObjectiveType.MINIMIZE_VARIANCE, constraints)

	def maximize_return_given_risk(self,
	                               returns: Union[List[float], np.ndarray, pd.DataFrame],
	                               max_risk: float) -> OptimizationResult:
		"""
		给定风险下的最大收益优化

		Args:
			returns: 收益率序列或矩阵
			max_risk: 最大风险

		Returns:
			OptimizationResult: 优化结果
		"""
		constraints = {
			'sum_to_one': True,
			'no_short': True,
			'max_risk': max_risk
		}

		return self.portfolio_optimization(
			returns, ObjectiveType.MAXIMIZE_RETURN, constraints)

	def efficient_frontier(self,
	                       returns: Union[List[float], np.ndarray, pd.DataFrame],
	                       n_points: int = 20) -> EfficientFrontier:
		"""
		计算有效前沿

		Args:
			returns: 收益率序列或矩阵
			n_points: 前沿点数

		Returns:
			EfficientFrontier: 有效前沿
		"""
		if isinstance(returns, (list, pd.DataFrame)):
			returns = np.array(returns)

		# 确保returns是二维数组
		if returns.ndim == 1:
			returns = returns.reshape(-1, 1)

		n_assets = returns.shape[1]

		# 计算预期收益和协方差矩阵
		expected_returns = np.mean(returns, axis=0)
		covariance_matrix = np.cov(returns, rowvar=False, ddof=1)

		# 计算最小方差组合
		min_var_result = self.minimize_risk_given_return(returns, None)

		# 计算最大收益组合
		constraints = {'sum_to_one': True, 'no_short': True}
		max_return_result = self.portfolio_optimization(
			returns, ObjectiveType.MAXIMIZE_RETURN, constraints)

		# 生成目标收益率范围
		min_return = min_var_result.expected_return
		max_return = max_return_result.expected_return

		target_returns = np.linspace(min_return, max_return, n_points)

		# 计算有效前沿上的点
		frontier_returns = []
		frontier_volatilities = []
		frontier_sharpe_ratios = []
		frontier_weights = []

		for target_return in target_returns:
			result = self.minimize_risk_given_return(returns, target_return)

			if result.success:
				frontier_returns.append(result.expected_return)
				frontier_volatilities.append(result.volatility)
				frontier_sharpe_ratios.append(result.sharpe_ratio)
				frontier_weights.append(result.weights)

		return EfficientFrontier(
			returns=np.array(frontier_returns),
			volatilities=np.array(frontier_volatilities),
			sharpe_ratios=np.array(frontier_sharpe_ratios),
			weights_matrix=np.array(frontier_weights)
		)

	def _create_bounds(self, n_assets: int, constraints: Dict[str, Any]) -> Bounds:
		"""创建边界条件"""
		min_weight = constraints.get('min_weight', 0.0)
		max_weight = constraints.get('max_weight', 1.0)

		if constraints.get('no_short', True):
			lb = min_weight
		else:
			lb = -max_weight

		ub = max_weight

		return Bounds(lb=np.full(n_assets, lb), ub=np.full(n_assets, ub))

	def _create_constraints(self, n_assets: int,
	                        expected_returns: np.ndarray,
	                        covariance_matrix: np.ndarray,
	                        constraints: Dict[str, Any]) -> List:
		"""创建约束条件列表"""
		constraints_list = []

		# 权重和为1约束
		if constraints.get('sum_to_one', True):
			constraints_list.append(
				LinearConstraint(np.ones(n_assets), 1, 1)
			)

		# 目标收益率约束
		target_return = constraints.get('target_return')
		if target_return is not None:
			constraints_list.append(
				LinearConstraint(expected_returns, target_return, target_return)
			)

		# 最大风险约束
		max_risk = constraints.get('max_risk')
		if max_risk is not None:
			def risk_constraint(weights):
				return self._calculate_portfolio_volatility(weights, covariance_matrix)

			constraints_list.append(
				NonlinearConstraint(risk_constraint, -np.inf, max_risk)
			)

		return constraints_list

	def _portfolio_variance(self, weights: np.ndarray,
	                        expected_returns: np.ndarray,
	                        covariance_matrix: np.ndarray,
	                        constraints: Dict[str, Any]) -> float:
		"""投资组合方差目标函数"""
		return self._calculate_portfolio_volatility(weights, covariance_matrix) ** 2

	def _negative_portfolio_return(self, weights: np.ndarray,
	                               expected_returns: np.ndarray,
	                               covariance_matrix: np.ndarray,
	                               constraints: Dict[str, Any]) -> float:
		"""投资组合收益目标函数（负值，用于最小化）"""
		return -self._calculate_portfolio_return(weights, expected_returns)

	def _negative_sharpe_ratio(self, weights: np.ndarray,
	                           expected_returns: np.ndarray,
	                           covariance_matrix: np.ndarray,
	                           constraints: Dict[str, Any]) -> float:
		"""夏普比率目标函数（负值，用于最小化）"""
		portfolio_return = self._calculate_portfolio_return(weights, expected_returns)
		portfolio_vol = self._calculate_portfolio_volatility(weights, covariance_matrix)

		if portfolio_vol > 0:
			sharpe = (portfolio_return - self.risk_free_rate) / portfolio_vol
			return -sharpe
		else:
			return 1e6  # 惩罚零波动率

	def _portfolio_cvar(self, weights: np.ndarray,
	                    expected_returns: np.ndarray,
	                    covariance_matrix: np.ndarray,
	                    constraints: Dict[str, Any]) -> float:
		"""投资组合CVaR目标函数 — 正态假设下的解析解"""
		# 从约束中获取置信水平，默认95%
		alpha = float(constraints.get('cvar_alpha', 0.05))
		if not 0 < alpha < 0.5:
			alpha = 0.05
		portfolio_return = self._calculate_portfolio_return(weights, expected_returns)
		portfolio_vol = self._calculate_portfolio_volatility(weights, covariance_matrix)

		if portfolio_vol > 0:
			z_alpha = norm.ppf(alpha)
			# CVaR_α = μ − σ · φ(z_α) / α  (正态分布下的条件期望)
			cvar = portfolio_return - portfolio_vol * norm.pdf(z_alpha) / alpha
		else:
			cvar = portfolio_return

		return -cvar  # 最小化风险，取负值

	def _risk_parity_objective(self, weights: np.ndarray,
	                           expected_returns: np.ndarray,
	                           covariance_matrix: np.ndarray,
	                           constraints: Dict[str, Any]) -> float:
		"""风险平价目标函数"""
		n_assets = len(weights)

		# 计算总风险
		total_risk = self._calculate_portfolio_volatility(weights, covariance_matrix)

		# 计算各资产的风险贡献
		risk_contributions = []
		for i in range(n_assets):
			# 边际风险贡献
			mrc = (covariance_matrix @ weights)[i] / total_risk
			# 风险贡献
			rc = weights[i] * mrc
			risk_contributions.append(rc)

		# 计算风险贡献与平均贡献的差异
		avg_contribution = total_risk / n_assets
		differences = np.array(risk_contributions) - avg_contribution

		# 目标是最小化差异的平方和
		objective = np.sum(differences ** 2)

		return objective

	def _optimize_given_estimates(self,
	                                expected_returns: np.ndarray,
	                                covariance_matrix: np.ndarray,
	                                n_assets: int,
	                                constraints: Optional[Dict[str, Any]] = None) -> OptimizationResult:
		"""用给定的预期收益和协方差进行均值-方差优化"""
		if constraints is None:
			constraints = {
				'sum_to_one': True,
				'no_short': True,
				'max_weight': 1.0,
				'min_weight': 0.0,
			}
		x0 = np.ones(n_assets) / n_assets
		bounds = self._create_bounds(n_assets, constraints)
		cons_list = self._create_constraints(
			n_assets, expected_returns, covariance_matrix, constraints)
		args = (expected_returns, covariance_matrix, constraints)

		try:
			result = minimize(
				fun=self._negative_sharpe_ratio,
				x0=x0,
				args=args,
				method=self.method,
				bounds=bounds,
				constraints=cons_list,
				options={'maxiter': 1000, 'ftol': 1e-8}
			)
			if not result.success:
				warnings.warn(f"BL优化未成功: {result.message}")

			optimal_weights = result.x
			if constraints.get("sum_to_one", True):
				optimal_weights = optimal_weights / np.sum(optimal_weights)

			portfolio_return = self._calculate_portfolio_return(
				optimal_weights, expected_returns)
			portfolio_vol = self._calculate_portfolio_volatility(
				optimal_weights, covariance_matrix)
			sharpe = ((portfolio_return - self.risk_free_rate) / portfolio_vol
			          if portfolio_vol > 0 else 0.0)

			return OptimizationResult(
				success=result.success,
				message=result.message,
				weights=optimal_weights,
				expected_return=portfolio_return,
				volatility=portfolio_vol,
				sharpe_ratio=sharpe,
				objective_value=result.fun,
				iterations=result.nit,
				function_calls=result.nfev
			)
		except Exception as e:
			return OptimizationResult(
				success=False, message=str(e),
				weights=np.ones(n_assets) / n_assets,
				expected_return=0.0, volatility=0.0,
				sharpe_ratio=0.0, objective_value=0.0,
				iterations=0, function_calls=0
			)

	@staticmethod
	def _calculate_portfolio_return( weights: np.ndarray,
	                                expected_returns: np.ndarray) -> float:
		"""计算投资组合预期收益"""
		return np.dot(weights, expected_returns)

	@staticmethod
	def _calculate_portfolio_volatility( weights: np.ndarray,
	                                    covariance_matrix: np.ndarray) -> float:
		"""计算投资组合波动率"""
		return np.sqrt(np.dot(weights.T, np.dot(covariance_matrix, weights)))


# 便捷函数
def portfolio_optimization(returns: Union[List[float], np.ndarray, pd.DataFrame],
                           objective: ObjectiveType = ObjectiveType.MAXIMIZE_SHARPE,
                           constraints: Optional[Dict[str, Any]] = None) -> OptimizationResult:
	"""通用投资组合优化"""
	return PortfolioOptimizer().portfolio_optimization(returns, objective, constraints)


def markowitz_optimization(returns: Union[List[float], np.ndarray, pd.DataFrame],
                           target_return: Optional[float] = None) -> OptimizationResult:
	"""马科维茨均值-方差优化"""
	return PortfolioOptimizer().markowitz_optimization(returns, target_return)


def black_litterman_optimization(returns: Union[List[float], np.ndarray, pd.DataFrame],
                                 prior_weights: np.ndarray,
                                 views: Dict[str, Any]) -> OptimizationResult:
	"""Black-Litterman模型优化"""
	return PortfolioOptimizer().black_litterman_optimization(returns, prior_weights, views)


def risk_parity_optimization(returns: Union[List[float], np.ndarray, pd.DataFrame]) -> OptimizationResult:
	"""风险平价优化"""
	return PortfolioOptimizer().risk_parity_optimization(returns)


def mean_var_optimization(returns: Union[List[float], np.ndarray, pd.DataFrame],
                          target_return: Optional[float] = None,
                          target_risk: Optional[float] = None) -> OptimizationResult:
	"""均值-方差优化"""
	return PortfolioOptimizer().mean_var_optimization(returns, target_return, target_risk)


def minimize_risk_given_return(returns: Union[List[float], np.ndarray, pd.DataFrame],
                               target_return: float) -> OptimizationResult:
	"""给定收益率下的最小风险优化"""
	return PortfolioOptimizer().minimize_risk_given_return(returns, target_return)


def maximize_return_given_risk(returns: Union[List[float], np.ndarray, pd.DataFrame],
                               max_risk: float) -> OptimizationResult:
	"""给定风险下的最大收益优化"""
	return PortfolioOptimizer().maximize_return_given_risk(returns, max_risk)


def efficient_frontier(returns: Union[List[float], np.ndarray, pd.DataFrame],
                       n_points: int = 20) -> EfficientFrontier:
	"""计算有效前沿"""
	return PortfolioOptimizer().efficient_frontier(returns, n_points)
