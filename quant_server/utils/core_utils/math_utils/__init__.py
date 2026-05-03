"""
数学工具模块
提供统计计算、金融计算和优化工具等数学功能
"""
from .statistic_calculator import (
	mean, std, variance, skewness, kurtosis,
	correlation, covariance, percentile,
	rolling_mean, rolling_std, rolling_correlation,
	zscore, winsorize, normalize,
	t_statistic, p_value, confidence_interval,
	StatisticalCalculator
)

from .financial_calculator import (
	calculate_returns, log_returns, cumulative_returns,
	annualized_return, annualized_volatility,
	sharpe_ratio, sortino_ratio, calmar_ratio,
	maximum_drawdown, drawdown_duration,
	value_at_risk, conditional_value_at_risk,
	omega_ratio, information_ratio,
	tracking_error, beta, alpha,
	jensen_alpha, treynor_ratio,
	FinancialCalculator
)

from .optimization_tools import (
	portfolio_optimization, markowitz_optimization,
	black_litterman_optimization,
	risk_parity_optimization,
	mean_var_optimization,
	minimize_risk_given_return,
	maximize_return_given_risk,
	efficient_frontier,
	PortfolioOptimizer
)

__all__ = [
	# 统计计算
	'mean', 'std', 'variance', 'skewness', 'kurtosis',
	'correlation', 'covariance', 'percentile',
	'rolling_mean', 'rolling_std', 'rolling_correlation',
	'zscore', 'winsorize', 'normalize',
	't_statistic', 'p_value', 'confidence_interval',
	'StatisticalCalculator',

	# 金融计算
	'calculate_returns', 'log_returns', 'cumulative_returns',
	'annualized_return', 'annualized_volatility',
	'sharpe_ratio', 'sortino_ratio', 'calmar_ratio',
	'maximum_drawdown', 'drawdown_duration',
	'value_at_risk', 'conditional_value_at_risk',
	'omega_ratio', 'information_ratio',
	'tracking_error', 'beta', 'alpha',
	'jensen_alpha', 'treynor_ratio',
	'FinancialCalculator',

	# 优化工具
	'portfolio_optimization', 'markowitz_optimization',
	'black_litterman_optimization',
	'risk_parity_optimization',
	'mean_var_optimization',
	'minimize_risk_given_return',
	'maximize_return_given_risk',
	'efficient_frontier',
	'PortfolioOptimizer'
]

__version__ = "1.0.0"
__author__ = "量化交易系统团队"
__description__ = "量化交易系统核心数学工具库"




'''
# 完整使用示例
from core.utils.data_utils import (
    ValidationRuleFactory,
    TransformationFactory,
    SamplerFactory,
    assess_data_quality
)

# 1. 数据质量评估
stock_data = [...]  # 股票数据
quality_report = assess_data_quality(stock_data)
print(f"数据质量得分: {quality_report['quality_score']['overall_score']}")

# 2. 数据转换
pipeline = TransformationFactory.create_stock_transformation_pipeline()
transformed_data = pipeline.transform_batch(stock_data)

# 3. 数据采样
sampler = SamplerFactory.create_sampler('stratified', strata_column='industry')
sample_result = sampler.sample(transformed_data, sample_size=100)

# 4. 时间序列重采样
from core.utils.data_utils import DataResampler
resampler = DataResampler(date_column='trade_date')
ohlc_data = resampler.resample_ohlc(stock_data, freq='5T')

# 5. 滚动窗口采样
from core.utils.data_utils import RollingWindowSampler
window_sampler = RollingWindowSampler(window_size=20, forecast_horizon=5)
windows = window_sampler.create_windows(time_series_data)
'''