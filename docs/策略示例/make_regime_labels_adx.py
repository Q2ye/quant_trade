# features.py > make_regime_labels_adx
"""特征工程 - 纯函数，训练/推理共用，杜绝数据泄露。

核心原则:
1. 每行特征只用该行及之前的数据(rolling/pct_change 天然满足)
2. 最后一行特征 = 最后一根已完成K线的特征(已知信息)，不含未来
3. 纯函数: 输入 DataFrame -> 输出 DataFrame(同索引，特征列)
4. 推理时传 ctx.bars.iloc[:-1](去掉当前未完成K线)
"""
from __future__ import annotations

import numpy as np
import pandas as pd

from .indicators import rsi_series, adx_series, atr_series  # 公开指标(单一来源)

# 全局特征列名(训练时保存到模型，推理时对齐校验)
FEATURE_NAMES = [
	"ret_5", "ret_10", "ret_20",           # 多周期收益率
	"atr_pct",                             # 波动率(归一化ATR)
	"rsi_14",                              # 动量
	"bb_pos",                              # 布林带位置
	"ma_gap",                              # 均线距离(趋势强度)
	"vol_ratio",                           # 量比
	"hour_sin", "hour_cos",                # 日内时间(周期编码)
	"adx_14",                              # ADX 趋势强度(经典 regime 指标)
	"bb_width",                            # 布林带宽度(宽=趋势扩张，窄=震荡收敛)
	"atr_ratio",                           # 短期/长期 ATR 比(regime 转换领先信号)
	"vol_trend",                           # 量能趋势(5周期均量/20周期均量)
]


def extract_features(bars: pd.DataFrame) -> pd.DataFrame:
	"""从K线DataFrame提取特征矩阵。输入需含 open/high/low/close/volume/time 列。

	保证: 每行特征只使用该行及之前的数据，不泄露未来。
	返回: 与输入同索引的 DataFrame，列为 FEATURE_NAMES。
	"""
	df = bars.copy()
	close = df["close"]
	high = df["high"]
	low = df["low"]
	volume = df["volume"] if "volume" in df.columns else pd.Series(0, index=df.index)

	feats = pd.DataFrame(index=df.index)

	# 1-3. 多周期收益率 pct_change 天然只用历史)
	feats["ret_5"] = close.pct_change(5)
	feats["ret_10"] = close.pct_change(10)
	feats["ret_20"] = close.pct_change(20)

	# 4. ATRX(Wilder, 归一化)
	feats["atr_pct"] = _wilder_atr_pct(high, low, close, period=14)

	# 5. RSI 14
	feats["rsi_14"] = rsi_series(close, 14)

	# 6. 布林带位置: (close - lower) / (upper - lower), 0=下轨, 1=上轨
	ma20 = close.rolling(20).mean()
	std20 = close.rolling(20).std()
	band_width = 4 * std20  # upper - lower = 2*(ma+2σ) - 2*(ma-2σ) = 4σ
	feats["bb_pos"] = (close - (ma20 - 2 * std20)) / band_width.replace(0, np.nan)

	# 7. 均线距离 (MA5 - MA20) / close
	ma5 = close.rolling(5).mean()
	feats["ma_gap"] = (ma5 - ma20) / close

	# 8. 量比: 当前量 / 20周期均量
	vol_ma = volume.rolling(20).mean()
	feats["vol_ratio"] = volume / vol_ma.replace(0, np.nan)

	# 9-10. 日内时间(周期编码，捕捉时段效应)
	times = pd.to_datetime(df["time"]) if "time" in df.columns else df.index.to_series()
	hour = times.dt.hour + times.dt.minute / 60.0
	feats["hour_sin"] = np.sin(2 * np.pi * hour / 24)
	feats["hour_cos"] = np.cos(2 * np.pi * hour / 24)

	# 11. ADX 趋势强度(经典 regime 指标: >25 趋势, <20 震荡)
	feats["adx_14"] = adx_series(df, 14)

	# 12. 布林带宽度(归一化): 4σ / close(宽=波动扩张/趋势, 窄=收敛/震荡)
	feats["bb_width"] = band_width / close

	# 13. 多周期波动率对比: ATR(5) / ATR(20)(短期波动放大=regime转换信号)
	atr_short = atr_series(df, 5)
	atr_long = atr_series(df, 20)
	feats["atr_ratio"] = atr_short / atr_long.replace(0, np.nan)

	# 14. 量能趋势: 5周期均量 / 20周期均量(放量=资金进场, 趋势启动信号)
	vol_ma5 = volume.rolling(5).mean()
	feats["vol_trend"] = vol_ma5 / vol_ma.replace(0, np.nan)

	return feats[FEATURE_NAMES]


def make_labels(bars: pd.DataFrame, horizon: int = 10, k_atr: float = 1.0) -> pd.Series:
	"""生成训练标签: 未来 horizon 根内，收益率超 2k*ATR。

	返回: 1(做多信号) / -1(做空信号) / 0(观望)。最后 horizon 行为 NaN(无未来数据)。
	"""
	close = bars["close"].values
	high = bars["high"].values
	low = bars["low"].values
	n = len(bars)
	atr = _wilder_atr(bars["high"], bars["low"], close, 14).values
	labels = np.zeros(n)

	for i in range(n - horizon):
		future_high = high[i + 1: i + 1 + horizon].max()
		future_low = low[i + 1: i + 1 + horizon].min()
		threshold = k_atr * atr[i]
		if threshold <= 0:
			labels[i] = 0
		elif (future_high - close[i]) > threshold and (future_low - close[i]) > -threshold:
			labels[i] = 1  # 未来涨超ATR且未跌破-ATR
		elif (future_low - close[i]) < -threshold and (future_high - close[i]) < threshold:
			labels[i] = -1  # 未来跌超ATR且未涨破ATR
		else:
			labels[i] = 0  # 观望

	result = pd.Series(labels, index=bars.index, name="label")
	result.iloc[-horizon:] = np.nan
	return result


# ==================== 辅助函数 ====================
def _wilder_atr_pct(high, low, close, period=14):
	"""ATR / close(归一化波动率)。"""
	atr = _wilder_atr(high, low, close, period)
	return atr / close


def _wilder_atr(high, low, close, period=14):
	"""Wilder ATR(SMA seed + EMA 递推)。"""
	prev_close = close.shift(1)
	tr = pd.concat(((high - low), (high - prev_close).abs(), (low - prev_close).abs()), axis=1).max(axis=1)
	# Wilder: 首个 ATR = SMA(TR, period), 之后 ATR = (prev_atr * (period-1) + TR) / period
	atr = tr.ewm(alpha=1 / period, adjust=False).mean()
	return atr


def make_regime_labels(bars: pd.DataFrame, horizon: int = 20, efficiency_thr: float = 0.4) -> pd.Series:
	"""震荡/趋势二分类标签(供 regime ML 训练，区别于涨跌的 make_labels)。

	用【路径效率】判: 未来 horizon 根内，效率 = |净位移| / 路径总长 ∈ [0,1].
	高效率(价格沿一个方向走，净位移=路径长)=>趋势(label=1);
	低效率(来回折返，净位移远小于路径)=>震荡(label=0).
	efficiency_thr 控分界(默认 0.4, 更明确的趋势; 0.3 太松导致70%标签为震荡).
	返回 0/1 Series(name="regime"): 未来 horizon 行 NaN(无未来数据)。
	"""
	close = bars["close"].values
	n = len(bars)
	labels = np.zeros(n)
	for i in range(n - horizon):
		seg = close[i + 1: i + 1 + horizon + 1]  # 未来 horizon 根的 close 路径
		net = abs(seg[-1] - seg[0])
		path = np.abs(np.diff(seg)).sum()
		eff = net / path if path > 0 else 0.0
		labels[i] = 1 if eff > efficiency_thr else 0
	result = pd.Series(labels, index=bars.index, name="regime")
	result.iloc[-horizon:] = np.nan
	return result


def make_regime_labels_adx(bars: pd.DataFrame, horizon: int = 10,
                           trend_thr: float = 25.0, range_thr: float = 20.0) -> pd.Series:
	"""ADX 标签法: 用**未来** ADX 的方向性变化打标(考虑 ADX 滞后性)。

	ADX 是滞后指标—趋势已经走了一段它才确认，趋势结束了它还在高位。
	所以不能简单用"未来某根 ADX > 25 = 趋势"，而要看 ADX 的**方向性变化**:

	标签逻辑(看未来 horizon 根的 ADX 走势):
		ADX 从低位上穿 range_thr(20) 且末值在上升 → 趋势启动(1)
		ADX 从高位下穿 trend_thr(25) 且末值在下降 → 趋势结束/震荡(0)
		其他(持续高位/持续低位/模糊) → NaN(不训练)

	这样模型学的是"ADX 即将发生 regime 转换的时点"，而不是"ADX 已经确认后的马后炮"。
	"""
	from .indicators import adx_series
	adx = adx_series(bars, 14)
	future_adx = adx.shift(-horizon)
	future_adx_prev = adx.shift(-1)           # 未来第1根(看是否穿越)
	labels = pd.Series(np.nan, index=bars.index, name="regime")

	# 趋势启动: 当前 ADX <= 20(震荡) -> 未来 horizon 根内 ADX 上穿 20 且末值上升
	trend_start = (adx <= range_thr) & (future_adx >= trend_thr) & (future_adx > future_adx_prev)
	labels[trend_start] = 1.0

	# 趋势结束: 当前 ADX >= 25(趋势) -> 未来 horizon 根内 ADX 下穿 25 且末值下降
	trend_end = (adx >= trend_thr) & (future_adx <= range_thr) & (future_adx < future_adx_prev)
	labels[trend_end] = 0.0

	# 持续趋势(当前>25 且 未来>25): 也标为趋势(让模型学会识别"稳定趋势中")
	stable_trend = (adx >= trend_thr) & (future_adx >= trend_thr)
	labels[stable_trend] = 1.0

	# 持续震荡(当前<20 且 未来<20): 也标为震荡
	stable_range = (adx <= range_thr) & (future_adx <= range_thr)
	labels[stable_range] = 0.0

	return labels