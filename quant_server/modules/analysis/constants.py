#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
分析模块常量定义

定义分析模块中使用的各种常量，包括：
- 分析类型
- 指标类型
- 报告状态
- 错误代码
"""

from enum import Enum
from typing import Dict, Any


class AnalysisType(str, Enum):
	"""分析类型枚举"""
	PERFORMANCE = "performance"  # 绩效分析
	RISK = "risk"  # 风险分析
	ATTRIBUTION = "attribution"  # 归因分析
	COMPARISON = "comparison"  # 对比分析


class ReportStatus(str, Enum):
	"""报告状态枚举"""
	PENDING = "pending"  # 待处理
	PROCESSING = "processing"  # 处理中
	COMPLETED = "completed"  # 已完成
	FAILED = "failed"  # 失败
	CANCELLED = "cancelled"  # 已取消


class RiskModel(str, Enum):
	"""风险模型枚举"""
	COVARIANCE = "covariance"  # 协方差模型
	HISTORICAL = "historical"  # 历史模拟
	MONTE_CARLO = "monte_carlo"  # 蒙特卡洛模拟
	PARAMETRIC = "parametric"  # 参数模型


class AttributionModel(str, Enum):
	"""归因模型枚举"""
	BRINSON = "brinson"  # Brinson归因
	FACTOR = "factor"  # 因子归因


class CorrelationMethod(str, Enum):
	"""相关性计算方法枚举"""
	PEARSON = "pearson"  # 皮尔逊相关性
	SPEARMAN = "spearman"  # 斯皮尔曼相关性
	KENDALL = "kendall"  # 肯德尔相关性


class ExportFormat(str, Enum):
	"""导出格式枚举"""
	PDF = "pdf"  # PDF格式
	EXCEL = "excel"  # Excel格式
	CSV = "csv"  # CSV格式
	HTML = "html"  # HTML格式
	JSON = "json"  # JSON格式


# 绩效指标定义
PERFORMANCE_METRICS: Dict[str, Dict[str, Any]] = {
	"return_metrics": {
		"total_return": {"name": "累计收益率", "description": "策略从开始到结束的总收益率"},
		"annual_return": {"name": "年化收益率", "description": "将总收益率年化后的值"},
		"daily_return": {"name": "日收益率", "description": "每日的收益率"},
		"monthly_return": {"name": "月收益率", "description": "每月的收益率"},
		"alpha": {"name": "阿尔法", "description": "超额收益，相对于基准的超额回报"},
		"beta": {"name": "贝塔", "description": "系统性风险，策略相对于市场的波动性"},
	},
	"risk_metrics": {
		"volatility": {"name": "波动率", "description": "收益率的年化标准差"},
		"sharpe_ratio": {"name": "夏普比率", "description": "每单位风险获得的超额收益"},
		"sortino_ratio": {"name": "索提诺比率", "description": "只考虑下行风险的调整后夏普比率"},
		"calmar_ratio": {"name": "卡玛比率", "description": "年化收益与最大回撤的比率"},
		"information_ratio": {"name": "信息比率", "description": "相对于基准的超额收益与跟踪误差的比率"},
	},
	"drawdown_metrics": {
		"max_drawdown": {"name": "最大回撤", "description": "策略净值从峰值到谷底的最大跌幅"},
		"drawdown_duration": {"name": "回撤持续时间", "description": "从峰值到恢复的时间"},
		"recovery_time": {"name": "恢复时间", "description": "从回撤底部回到峰值的时间"},
	},
	"win_loss_metrics": {
		"win_rate": {"name": "胜率", "description": "盈利交易占总交易的比例"},
		"profit_factor": {"name": "盈利因子", "description": "总盈利与总亏损的比率"},
		"average_win": {"name": "平均盈利", "description": "盈利交易的平均收益"},
		"average_loss": {"name": "平均亏损", "description": "亏损交易的平均损失"},
	}
}

# 风险指标定义
RISK_METRICS: Dict[str, Dict[str, Any]] = {
	"volatility_metrics": {
		"historical_volatility": {"name": "历史波动率", "description": "基于历史收益率的波动率"},
		"implied_volatility": {"name": "隐含波动率", "description": "从期权价格推导的波动率"},
		"realized_volatility": {"name": "已实现波动率", "description": "基于实际收益的波动率"},
	},
	"value_at_risk": {
		"var_95": {"name": "95% VaR", "description": "95%置信水平下的在险价值"},
		"var_99": {"name": "99% VaR", "description": "99%置信水平下的在险价值"},
		"conditional_var": {"name": "条件VaR", "description": "超过VaR的平均损失"},
	},
	"stress_test": {
		"historical_stress": {"name": "历史压力测试", "description": "基于历史极端事件的压力测试"},
		"hypothetical_stress": {"name": "假设压力测试", "description": "基于假设情景的压力测试"},
		"reverse_stress": {"name": "反向压力测试", "description": "确定导致重大损失的情景"},
	},
	"liquidity_risk": {
		"bid_ask_spread": {"name": "买卖价差", "description": "衡量市场流动性的指标"},
		"market_impact": {"name": "市场冲击", "description": "大额交易对价格的影响"},
		"liquidity_coverage": {"name": "流动性覆盖率", "description": "覆盖短期流动性需求的比率"},
	}
}

# 归因指标定义
ATTRIBUTION_METRICS: Dict[str, Dict[str, Any]] = {
	"brinson_attribution": {
		"allocation_effect": {"name": "资产配置效应", "description": "资产配置带来的超额收益"},
		"selection_effect": {"name": "证券选择效应", "description": "证券选择带来的超额收益"},
		"interaction_effect": {"name": "交互效应", "description": "配置和选择的交互作用"},
	},
	"factor_attribution": {
		"market_factor": {"name": "市场因子", "description": "市场风险带来的收益"},
		"size_factor": {"name": "规模因子", "description": "市值效应带来的收益"},
		"value_factor": {"name": "价值因子", "description": "价值效应带来的收益"},
		"momentum_factor": {"name": "动量因子", "description": "动量效应带来的收益"},
		"quality_factor": {"name": "质量因子", "description": "质量效应带来的收益"},
	},
	"sector_attribution": {
		"sector_allocation": {"name": "行业配置", "description": "行业配置带来的收益"},
		"stock_selection": {"name": "个股选择", "description": "行业内个股选择带来的收益"},
	},
	"currency_attribution": {
		"currency_effect": {"name": "货币效应", "description": "汇率变动带来的收益"},
		"hedging_effect": {"name": "对冲效应", "description": "货币对冲带来的收益"},
	}
}

# 交易分析指标定义
TRADE_ANALYSIS_METRICS: Dict[str, Dict[str, Any]] = {
	"cost_metrics": {
		"commission_cost": {"name": "佣金成本", "description": "支付给券商的佣金"},
		"tax_cost": {"name": "税费成本", "description": "支付的交易税费"},
		"slippage_cost": {"name": "滑点成本", "description": "由于市场冲击造成的成本"},
		"implementation_shortfall": {"name": "执行缺口", "description": "实际执行价格与决策价格的差异"},
	},
	"execution_quality": {
		"fill_rate": {"name": "成交率", "description": "订单成交的比例"},
		"execution_speed": {"name": "执行速度", "description": "从下单到成交的时间"},
		"price_improvement": {"name": "价格改善", "description": "成交价格优于报价的比例"},
		"market_impact": {"name": "市场冲击", "description": "交易对市场价格的影响"},
	},
	"timing_metrics": {
		"market_timing": {"name": "市场择时", "description": "把握市场时机的贡献"},
		"stock_timing": {"name": "个股择时", "description": "把握个股买卖时机的贡献"},
		"turnover_rate": {"name": "换手率", "description": "交易活跃度的指标"},
	}
}


class AnalysisModuleConstants:
	"""分析模块常量类"""

	# 默认参数
	DEFAULT_LOOKBACK_PERIOD = 252  # 默认回看周期（交易日）
	DEFAULT_CONFIDENCE_LEVEL = 0.95  # 默认置信水平
	DEFAULT_BENCHMARK = "000300.SH"  # 默认基准（沪深300）

	# 时间周期
	TIME_PERIODS = {
		"1d": "1天",
		"1w": "1周",
		"1m": "1月",
		"3m": "3月",
		"6m": "6月",
		"1y": "1年",
		"3y": "3年",
		"5y": "5年",
		"10y": "10年",
		"ytd": "年初至今",
		"all": "全部"
	}

	# 分析频率
	FREQUENCIES = {
		"daily": "日度",
		"weekly": "周度",
		"monthly": "月度",
		"quarterly": "季度",
		"yearly": "年度"
	}

	# 风险等级
	RISK_LEVELS = {
		"conservative": {"name": "保守型", "max_drawdown": 0.05, "volatility": 0.10},
		"moderate": {"name": "稳健型", "max_drawdown": 0.10, "volatility": 0.15},
		"balanced": {"name": "平衡型", "max_drawdown": 0.15, "volatility": 0.20},
		"aggressive": {"name": "进取型", "max_drawdown": 0.20, "volatility": 0.25},
		"speculative": {"name": "投机型", "max_drawdown": 0.30, "volatility": 0.30}
	}

	# 错误代码
	ERROR_CODES = {
		# 数据错误 (1000-1999)
		"DATA_NOT_FOUND": 1001,
		"INSUFFICIENT_DATA": 1002,
		"DATA_VALIDATION_ERROR": 1003,

		# 计算错误 (2000-2999)
		"CALCULATION_ERROR": 2001,
		"CONVERGENCE_ERROR": 2002,
		"OPTIMIZATION_ERROR": 2003,

		# 配置错误 (3000-3999)
		"INVALID_CONFIG": 3001,
		"MISSING_PARAMETER": 3002,
		"UNSUPPORTED_MODEL": 3003,

		# 系统错误 (4000-4999)
		"TIMEOUT_ERROR": 4001,
		"MEMORY_ERROR": 4002,
		"CONCURRENCY_ERROR": 4003,

		# 权限错误 (5000-5999)
		"UNAUTHORIZED_ACCESS": 5001,
		"LIMIT_EXCEEDED": 5002,
		"QUOTA_EXCEEDED": 5003
	}
