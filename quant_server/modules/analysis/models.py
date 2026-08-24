#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
分析模块业务模型

定义分析模块的业务模型（领域对象），这些模型用于业务逻辑处理，
不直接映射到数据库表。数据库表模型在 shared/database/models/ 中定义。

业务模型包含业务逻辑和计算方法，与Repository层配合使用。
"""

from dataclasses import dataclass, field
from datetime import datetime, date
from decimal import Decimal
from typing import Dict, List, Any, Optional


@dataclass
class PerformanceMetrics:
	"""绩效指标业务模型"""
	# 基本信息
	strategy_id: str
	account_id: str
	start_date: date
	end_date: date
	benchmark: Optional[str] = None

	# 收益指标
	total_return: Decimal = Decimal("0.0")
	annual_return: Decimal = Decimal("0.0")
	cagr: Decimal = Decimal("0.0")  # 年复合增长率

	# 风险调整收益
	sharpe_ratio: Decimal = Decimal("0.0")
	sortino_ratio: Decimal = Decimal("0.0")
	calmar_ratio: Decimal = Decimal("0.0")
	information_ratio: Decimal = Decimal("0.0")

	# 风险指标
	volatility: Decimal = Decimal("0.0")
	max_drawdown: Decimal = Decimal("0.0")
	var_95: Decimal = Decimal("0.0")
	var_99: Decimal = Decimal("0.0")
	expected_shortfall: Decimal = Decimal("0.0")

	# Alpha/Beta
	alpha: Decimal = Decimal("0.0")
	beta: Decimal = Decimal("0.0")
	tracking_error: Decimal = Decimal("0.0")
	r_squared: Decimal = Decimal("0.0")

	# 交易统计
	win_rate: Decimal = Decimal("0.0")
	profit_factor: Decimal = Decimal("0.0")
	average_win: Decimal = Decimal("0.0")
	average_loss: Decimal = Decimal("0.0")
	total_trades: int = 0
	winning_trades: int = 0
	losing_trades: int = 0

	# 时间周期
	analysis_period: str = "custom"
	trading_days: int = 0
	total_days: int = 0

	# 附加数据
	daily_returns: List[float] = field(default_factory=list)
	equity_curve: List[Dict[str, Any]] = field(default_factory=list)
	drawdown_curve: List[Dict[str, Any]] = field(default_factory=list)
	benchmark_curve: List[Dict[str, Any]] = field(default_factory=list)
	monthly_returns: Dict[str, Decimal] = field(default_factory=dict)
	annual_returns: Dict[int, Decimal] = field(default_factory=dict)

	def to_dict (self) -> Dict[str, Any]:
		"""转换为平铺字典（前端直接读取 flat keys）"""
		result = {
			"strategy_id": self.strategy_id,
			"account_id": self.account_id,
			"start_date": self.start_date.isoformat(),
			"end_date": self.end_date.isoformat(),
			"trading_days": self.trading_days,
			"total_days": self.total_days,
			"benchmark": self.benchmark,
			# 收益指标
			"total_return": float(self.total_return),
			"annual_return": float(self.annual_return),
			"cagr": float(self.cagr),
			# 风险调整收益
			"sharpe_ratio": float(self.sharpe_ratio),
			"sortino_ratio": float(self.sortino_ratio),
			"calmar_ratio": float(self.calmar_ratio),
			"information_ratio": float(self.information_ratio),
			# 风险指标
			"volatility": float(self.volatility),
			"max_drawdown": float(self.max_drawdown),
			"var_95": float(self.var_95),
			"var_99": float(self.var_99),
			"expected_shortfall": float(self.expected_shortfall),
			# Alpha/Beta
			"alpha": float(self.alpha),
			"beta": float(self.beta),
			"tracking_error": float(self.tracking_error),
			"r_squared": float(self.r_squared),
			# 交易统计
			"total_trades": self.total_trades,
			"winning_trades": self.winning_trades,
			"losing_trades": self.losing_trades,
			"win_rate": float(self.win_rate),
			"profit_factor": float(self.profit_factor),
			"average_win": float(self.average_win),
			"average_loss": float(self.average_loss),
			# 图表数据
			"equity_curve": self.equity_curve,
			"drawdown_curve": self.drawdown_curve,
			"monthly_returns": {k: float(v) for k, v in self.monthly_returns.items()} if self.monthly_returns else {},
			"daily_returns": self.daily_returns,
			"benchmark_curve": self.benchmark_curve,
			# 当前快照摘要（单点数据时填充）
			"total_asset": getattr(self, "total_asset_snapshot", {}).get("total_asset", 0) if hasattr(self, "total_asset_snapshot") else (
				float(self.equity_curve[-1]["equity"]) if self.equity_curve else 0
			),
			"daily_pnl": getattr(self, "total_asset_snapshot", {}).get("daily_pnl", 0) if hasattr(self, "total_asset_snapshot") else 0,
			"daily_return": getattr(self, "total_asset_snapshot", {}).get("daily_return", 0) if hasattr(self, "total_asset_snapshot") else 0,
			# 账户绩效附加：当前持仓列表（账户接口由 performance_service 填充，策略接口为空列表）
			"positions": getattr(self, "positions", []),
		}
		return result


@dataclass
class RiskMetrics:
	"""风险指标业务模型"""
	# 基础信息
	portfolio_id: str
	analysis_date: date
	confidence_level: Decimal = Decimal("0.95")

	# 波动率指标
	historical_volatility: Decimal = Decimal("0.0")
	realized_volatility: Decimal = Decimal("0.0")
	implied_volatility: Optional[Decimal] = None
	volatility_forecast: Optional[Decimal] = None

	# 在险价值（VaR）
	var_historical: Decimal = Decimal("0.0")
	var_parametric: Decimal = Decimal("0.0")
	var_monte_carlo: Decimal = Decimal("0.0")
	conditional_var: Decimal = Decimal("0.0")

	# 压力测试结果
	stress_test_results: Dict[str, Decimal] = field(default_factory=dict)

	# 流动性风险
	liquidity_metrics: Dict[str, Decimal] = field(default_factory=dict)

	# 集中度风险
	concentration_metrics: Dict[str, Decimal] = field(default_factory=dict)

	# 相关性风险
	correlation_matrix: Dict[str, Dict[str, Decimal]] = field(default_factory=dict)
	portfolio_beta: Decimal = Decimal("0.0")

	# 风险贡献度
	risk_contributions: Dict[str, Decimal] = field(default_factory=dict)

	# 风险限额监控
	limit_breaches: List[Dict[str, Any]] = field(default_factory=list)

	def to_dict (self) -> Dict[str, Any]:
		"""转换为字典"""
		return {
			"portfolio_id": self.portfolio_id,
			"analysis_date": self.analysis_date.isoformat(),
			"confidence_level": float(self.confidence_level),
			"volatility_metrics": {
				"historical_volatility": float(self.historical_volatility),
				"realized_volatility": float(self.realized_volatility),
				"implied_volatility": float(self.implied_volatility) if self.implied_volatility else None,
				"volatility_forecast": float(self.volatility_forecast) if self.volatility_forecast else None
			},
			"value_at_risk": {
				"historical": float(self.var_historical),
				"parametric": float(self.var_parametric),
				"monte_carlo": float(self.var_monte_carlo),
				"conditional": float(self.conditional_var)
			},
			"stress_test": self.stress_test_results,
			"liquidity_risk": self.liquidity_metrics,
			"concentration_risk": self.concentration_metrics,
			"correlation_risk": {
				"correlation_matrix": self.correlation_matrix,
				"portfolio_beta": float(self.portfolio_beta)
			},
			"risk_contributions": self.risk_contributions,
			"limit_monitoring": self.limit_breaches
		}


@dataclass
class StrategyComparison:
	"""策略对比业务模型"""
	# 对比信息
	comparison_id: str
	strategy_ids: List[str]
	comparison_date: date
	benchmark: Optional[str] = None

	# 绩效对比
	performance_comparison: Dict[str, PerformanceMetrics] = field(default_factory=dict)

	# 排名结果
	rankings: Dict[str, Dict[str, int]] = field(default_factory=dict)

	# 相关性分析
	correlations: Dict[str, Dict[str, Decimal]] = field(default_factory=dict)

	# 统计分析
	statistics: Dict[str, Dict[str, Any]] = field(default_factory=dict)

	# 风险调整后排名
	risk_adjusted_rankings: Dict[str, List[str]] = field(default_factory=dict)

	# 建议和洞察
	insights: List[str] = field(default_factory=list)
	recommendations: List[str] = field(default_factory=list)

	def to_dict (self) -> Dict[str, Any]:
		"""转换为字典"""
		return {
			"comparison_id": self.comparison_id,
			"strategy_ids": self.strategy_ids,
			"comparison_date": self.comparison_date.isoformat(),
			"benchmark": self.benchmark,
			"performance_comparison": {
				sid: metrics.to_dict() for sid, metrics in self.performance_comparison.items()
			},
			"rankings": self.rankings,
			"correlations": self.correlations,
			"statistics": self.statistics,
			"risk_adjusted_rankings": self.risk_adjusted_rankings,
			"insights": self.insights,
			"recommendations": self.recommendations
		}


@dataclass
class AttributionAnalysis:
	"""归因分析业务模型"""
	# 归因信息
	attribution_id: str
	portfolio_id: str
	analysis_period: str
	attribution_model: str
	benchmark: str

	# 总收益分解
	total_return: Decimal = Decimal("0.0")
	benchmark_return: Decimal = Decimal("0.0")
	active_return: Decimal = Decimal("0.0")

	# Brinson归因
	allocation_effect: Decimal = Decimal("0.0")
	selection_effect: Decimal = Decimal("0.0")
	interaction_effect: Decimal = Decimal("0.0")

	# 因子归因
	factor_attributions: Dict[str, Decimal] = field(default_factory=dict)
	factor_exposures: Dict[str, Decimal] = field(default_factory=dict)

	# 行业归因
	sector_attributions: Dict[str, Decimal] = field(default_factory=dict)
	sector_allocations: Dict[str, Decimal] = field(default_factory=dict)

	# 个股归因
	stock_attributions: Dict[str, Decimal] = field(default_factory=dict)
	stock_contributions: Dict[str, Decimal] = field(default_factory=dict)

	# 时间序列归因
	time_series_attribution: List[Dict[str, Any]] = field(default_factory=list)

	# 归因质量指标
	attribution_r_squared: Decimal = Decimal("0.0")
	tracking_error_explained: Decimal = Decimal("0.0")

	def to_dict (self) -> Dict[str, Any]:
		"""转换为字典"""
		return {
			"attribution_id": self.attribution_id,
			"portfolio_id": self.portfolio_id,
			"analysis_period": self.analysis_period,
			"attribution_model": self.attribution_model,
			"benchmark": self.benchmark,
			"return_decomposition": {
				"total_return": float(self.total_return),
				"benchmark_return": float(self.benchmark_return),
				"active_return": float(self.active_return)
			},
			"brinson_attribution": {
				"allocation_effect": float(self.allocation_effect),
				"selection_effect": float(self.selection_effect),
				"interaction_effect": float(self.interaction_effect)
			},
			"factor_attribution": {
				"attributions": self.factor_attributions,
				"exposures": self.factor_exposures
			},
			"sector_attribution": {
				"attributions": self.sector_attributions,
				"allocations": self.sector_allocations
			},
			"stock_attribution": {
				"attributions": self.stock_attributions,
				"contributions": self.stock_contributions
			},
			"quality_metrics": {
				"attribution_r_squared": float(self.attribution_r_squared),
				"tracking_error_explained": float(self.tracking_error_explained)
			}
		}


@dataclass
class TradeAnalysis:
	"""交易分析业务模型"""
	# 分析信息
	analysis_id: str
	strategy_id: str
	account_id: str
	analysis_period: str

	# 交易统计
	total_trades: int = 0
	winning_trades: int = 0
	losing_trades: int = 0
	breakeven_trades: int = 0

	# 交易成本
	total_commission: Decimal = Decimal("0.0")
	total_tax: Decimal = Decimal("0.0")
	total_slippage: Decimal = Decimal("0.0")
	total_impact_cost: Decimal = Decimal("0.0")
	total_trading_cost: Decimal = Decimal("0.0")

	# 执行质量
	average_execution_time: Decimal = Decimal("0.0")
	fill_rate: Decimal = Decimal("0.0")
	price_improvement: Decimal = Decimal("0.0")
	implementation_shortfall: Decimal = Decimal("0.0")

	# 交易行为
	average_trade_size: Decimal = Decimal("0.0")
	average_holding_period: Decimal = Decimal("0.0")
	turnover_rate: Decimal = Decimal("0.0")

	# 交易时间分析
	time_of_day_distribution: Dict[str, int] = field(default_factory=dict)
	day_of_week_distribution: Dict[str, int] = field(default_factory=dict)

	# 交易模式识别
	trading_patterns: List[Dict[str, Any]] = field(default_factory=list)

	# 成本分析
	cost_breakdown: Dict[str, Decimal] = field(default_factory=dict)
	cost_efficiency: Dict[str, Decimal] = field(default_factory=dict)

	def to_dict (self) -> Dict[str, Any]:
		"""转换为字典"""
		return {
			"analysis_id": self.analysis_id,
			"strategy_id": self.strategy_id,
			"account_id": self.account_id,
			"analysis_period": self.analysis_period,
			"trade_statistics": {
				"total_trades": self.total_trades,
				"winning_trades": self.winning_trades,
				"losing_trades": self.losing_trades,
				"breakeven_trades": self.breakeven_trades
			},
			"trading_costs": {
				"total_commission": float(self.total_commission),
				"total_tax": float(self.total_tax),
				"total_slippage": float(self.total_slippage),
				"total_impact_cost": float(self.total_impact_cost),
				"total_trading_cost": float(self.total_trading_cost)
			},
			"execution_quality": {
				"average_execution_time": float(self.average_execution_time),
				"fill_rate": float(self.fill_rate),
				"price_improvement": float(self.price_improvement),
				"implementation_shortfall": float(self.implementation_shortfall)
			},
			"trading_behavior": {
				"average_trade_size": float(self.average_trade_size),
				"average_holding_period": float(self.average_holding_period),
				"turnover_rate": float(self.turnover_rate)
			},
			"time_analysis": {
				"time_of_day": self.time_of_day_distribution,
				"day_of_week": self.day_of_week_distribution
			},
			"cost_analysis": {
				"breakdown": self.cost_breakdown,
				"efficiency": self.cost_efficiency
			},
			"trading_patterns": self.trading_patterns
		}


@dataclass
class AnalysisReport:
	"""分析报告业务模型"""
	# 报告基本信息
	report_id: str
	user_id: str
	report_type: str
	title: str
	description: Optional[str] = None

	# 分析参数
	parameters: Dict[str, Any] = field(default_factory=dict)

	# 分析结果
	performance_metrics: Optional[PerformanceMetrics] = None
	risk_metrics: Optional[RiskMetrics] = None
	attribution_analysis: Optional[AttributionAnalysis] = None
	comparison_analysis: Optional[StrategyComparison] = None
	trade_analysis: Optional[TradeAnalysis] = None

	# 图表数据
	charts: List[Dict[str, Any]] = field(default_factory=list)

	# 报告状态
	status: str = "pending"
	progress: float = 0.0
	error_message: Optional[str] = None

	# 时间信息
	created_at: datetime = field(default_factory=datetime.now)
	updated_at: datetime = field(default_factory=datetime.now)
	completed_at: Optional[datetime] = None

	# 导出信息
	export_formats: List[str] = field(default_factory=list)
	export_files: Dict[str, str] = field(default_factory=dict)

	def to_dict (self) -> Dict[str, Any]:
		"""转换为字典"""
		result = {
			"report_id": self.report_id,
			"user_id": self.user_id,
			"report_type": self.report_type,
			"title": self.title,
			"description": self.description,
			"parameters": self.parameters,
			"status": self.status,
			"progress": self.progress,
			"timestamps": {
				"created_at": self.created_at.isoformat(),
				"updated_at": self.updated_at.isoformat(),
				"completed_at": self.completed_at.isoformat() if self.completed_at else None
			},
			"export_info": {
				"formats": self.export_formats,
				"files": self.export_files
			},
			"charts": self.charts
		}

		# 根据报告类型添加相应数据
		if self.performance_metrics:
			result["performance_metrics"] = self.performance_metrics.to_dict()
		if self.risk_metrics:
			result["risk_metrics"] = self.risk_metrics.to_dict()
		if self.attribution_analysis:
			result["attribution_analysis"] = self.attribution_analysis.to_dict()
		if self.comparison_analysis:
			result["comparison_analysis"] = self.comparison_analysis.to_dict()
		if self.trade_analysis:
			result["trade_analysis"] = self.trade_analysis.to_dict()

		return result
