"""
技术指标模块
提供趋势指标、动量指标、波动率指标和成交量指标等各类技术分析工具
"""

from .trend_indicators import (
	# 移动平均类
	simple_moving_average, exponential_moving_average,
	weighted_moving_average, hull_moving_average,
	moving_average_convergence_divergence,
	parabolic_sar, ichimoku_cloud, vortex_indicator,

	# 趋势判断
	moving_average_crossover, trend_direction,

	# 数据类
	MovingAverage, EMACalculator, MACDResult, IchimokuCloud,

	# 枚举
	MovingAverageType
)

from .momentum_indicators import (
	# 动量指标
	relative_strength_index, stochastic_oscillator,
	williams_percent_r, commodity_channel_index,
	rate_of_change, momentum_oscillator,
	awesome_oscillator, ultimate_oscillator,

	# 超买超卖判断
	is_overbought, is_oversold,

	# 数据类
	RSICalculator, StochasticResult, MomentumResult
)

from .volatility_indicators import (
	# 波动率指标
	bollinger_bands, average_true_range,
	keltner_channels, donchian_channels,
	standard_deviation_bands,

	# 波动率状态
	volatility_regime, bollinger_squeeze,

	# 数据类
	BollingerBands, ATRResult, KeltnerChannels
)

from .volume_indicators import (
	# 成交量指标
	on_balance_volume, volume_weighted_average_price,
	accumulation_distribution_line, chaikin_money_flow,
	money_flow_index, ease_of_movement,
	volume_price_trend, negative_volume_index,

	# 量价关系
	volume_confirmation, volume_divergence,

	# 数据类
	VolumeProfile, VolumeAnalysis
)

__all__ = [
	# 趋势指标
	'simple_moving_average', 'exponential_moving_average',
	'weighted_moving_average', 'hull_moving_average',
	'moving_average_convergence_divergence',
	'parabolic_sar', 'ichimoku_cloud', 'vortex_indicator',
	'moving_average_crossover', 'trend_direction',
	'MovingAverage', 'EMACalculator', 'MACDResult', 'IchimokuCloud',
	'MovingAverageType',

	# 动量指标
	'relative_strength_index', 'stochastic_oscillator',
	'williams_percent_r', 'commodity_channel_index',
	'rate_of_change', 'momentum_oscillator',
	'awesome_oscillator', 'ultimate_oscillator',
	'is_overbought', 'is_oversold',
	'RSICalculator', 'StochasticResult', 'MomentumResult',

	# 波动率指标
	'bollinger_bands', 'average_true_range',
	'keltner_channels', 'donchian_channels',
	'standard_deviation_bands',
	'volatility_regime', 'bollinger_squeeze',
	'BollingerBands', 'ATRResult', 'KeltnerChannels',

	# 成交量指标
	'on_balance_volume', 'volume_weighted_average_price',
	'accumulation_distribution_line', 'chaikin_money_flow',
	'money_flow_index', 'ease_of_movement',
	'volume_price_trend', 'negative_volume_index',
	'volume_confirmation', 'volume_divergence',
	'VolumeProfile', 'VolumeAnalysis'
]

__version__ = "1.0.0"
__author__ = "量化交易系统团队"
__description__ = "量化交易系统技术指标库"

# 使用场景说明
"""
技术指标使用场景概述：

1. 趋势指标 (Trend Indicators):
   - 识别市场趋势方向和强度
   - 确定支撑和阻力位
   - 判断趋势反转信号
   - 适合趋势跟踪策略

2. 动量指标 (Momentum Indicators):
   - 测量价格变化的速度和幅度
   - 识别超买超卖区域
   - 发现价格与动量的背离
   - 适合震荡市和反转策略

3. 波动率指标 (Volatility Indicators):
   - 衡量价格波动的程度
   - 识别市场波动率的变化
   - 判断波动率扩张和收缩
   - 适合波动率交易和期权策略

4. 成交量指标 (Volume Indicators):
   - 分析成交量与价格的关系
   - 确认价格趋势的强度
   - 识别资金流入流出
   - 适合量价分析和机构行为分析

技术指标选择建议：
- 趋势市场：移动平均线、MACD、布林带
- 震荡市场：RSI、随机指标、威廉指标
- 高波动市场：ATR、布林带、凯尔特纳通道
- 量价分析：OBV、MFI、成交量加权价格
"""

'''
todo 使用示例
# 导入技术指标
from core.utils.technical_indicators import (
    # 趋势指标
    simple_moving_average, exponential_moving_average,
    moving_average_convergence_divergence,
    # 动量指标
    relative_strength_index, stochastic_oscillator,
    # 波动率指标
    bollinger_bands, average_true_range,
    # 成交量指标
    on_balance_volume, money_flow_index
)

# 示例数据
prices = [100, 102, 101, 105, 107, 106, 110, 108, 112, 115]
high = [101, 103, 102, 106, 108, 107, 112, 110, 114, 117]
low = [99, 101, 100, 104, 106, 105, 108, 106, 110, 113]
close = [100, 102, 101, 105, 107, 106, 110, 108, 112, 115]
volume = [10000, 12000, 8000, 15000, 13000, 9000, 18000, 11000, 16000, 20000]

# 1. 计算移动平均线
sma_20 = simple_moving_average(prices, period=20)  # 使用默认周期
ema_12 = exponential_moving_average(prices, period=12)

print("简单移动平均线（20周期）:", sma_20[-5:])
print("指数移动平均线（12周期）:", ema_12[-5:])

# 2. 计算MACD
macd_result = moving_average_convergence_divergence(prices)
print("MACD线:", macd_result.macd_line[-5:])
print("信号线:", macd_result.signal_line[-5:])
print("柱状图:", macd_result.histogram[-5:])

# 3. 计算RSI
rsi = relative_strength_index(prices, period=14)
print("RSI（14周期）:", rsi[-5:])

# 4. 计算随机指标
stoch_result = stochastic_oscillator(high, low, close, k_period=14, d_period=3)
print("%K线:", stoch_result.k_line[-5:])
print("%D线:", stoch_result.d_line[-5:])

# 5. 计算布林带
bb_result = bollinger_bands(prices, period=20, num_std=2.0)
print("布林带上轨:", bb_result.upper_band[-5:])
print("布林带中轨:", bb_result.middle_band[-5:])
print("布林带下轨:", bb_result.lower_band[-5:])
print("布林带%B:", bb_result.percent_b[-5:])

# 6. 计算ATR
atr_result = average_true_range(high, low, close, period=14)
print("ATR值:", atr_result.atr_values[-5:])
print("ATR百分比:", atr_result.percent_atr[-5:])

# 7. 计算OBV
obv = on_balance_volume(close, volume)
print("OBV:", obv[-5:])

# 8. 计算MFI
mfi = money_flow_index(high, low, close, volume, period=14)
print("MFI:", mfi[-5:])

# 9. 综合技术分析示例
def technical_analysis_signal(prices, high, low, close, volume):
    """综合技术分析信号"""
    signals = []
    
    # 计算多个指标
    sma_20 = simple_moving_average(prices, 20)
    sma_50 = simple_moving_average(prices, 50)
    rsi = relative_strength_index(prices, 14)
    bb = bollinger_bands(prices, 20, 2.0)
    
    for i in range(len(prices)):
        if i < 50:  # 确保有足够数据
            signals.append(0)
            continue
        
        signal = 0
        
        # 移动平均线金叉/死叉
        if sma_20[i] > sma_50[i] and sma_20[i-1] <= sma_50[i-1]:
            signal += 1  # 金叉买入信号
        elif sma_20[i] < sma_50[i] and sma_20[i-1] >= sma_50[i-1]:
            signal -= 1  # 死叉卖出信号
        
        # RSI超买超卖
        if rsi[i] < 30:
            signal += 1  # 超卖买入信号
        elif rsi[i] > 70:
            signal -= 1  # 超买卖出信号
        
        # 布林带突破
        if prices[i] > bb.upper_band[i]:
            signal -= 1  # 突破上轨卖出信号
        elif prices[i] < bb.lower_band[i]:
            signal += 1  # 突破下轨买入信号
        
        signals.append(signal)
    
    return signals

# 生成综合信号
signals = technical_analysis_signal(prices, high, low, close, volume)
print("综合技术信号:", signals)
'''