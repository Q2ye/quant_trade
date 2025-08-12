import pandas as pd
from typing import  Dict, Tuple


class TechnicalIndicators:
    """技术指标计算工具类（兼容vn.py社区版）"""

    @staticmethod
    def sma(series: pd.Series, window: int) -> pd.Series:
        """简单移动平均线"""
        return series.rolling(window=window).mean()

    @staticmethod
    def ema(series: pd.Series, window: int) -> pd.Series:
        """指数移动平均线"""
        return series.ewm(span=window, adjust=False).mean()

    @staticmethod
    def macd(series: pd.Series, fast: int = 12, slow: int = 26, signal: int = 9) -> Tuple[
        pd.Series, pd.Series, pd.Series]:
        """MACD指标"""
        fast_ema = series.ewm(span=fast, adjust=False).mean()
        slow_ema = series.ewm(span=slow, adjust=False).mean()
        macd_line = fast_ema - slow_ema
        signal_line = macd_line.ewm(span=signal, adjust=False).mean()
        histogram = macd_line - signal_line
        return macd_line, signal_line, histogram

    @staticmethod
    def rsi(series: pd.Series, window: int = 14) -> pd.Series:
        """相对强弱指数"""
        delta = series.diff()
        gain = delta.where(delta > 0, 0)
        loss = -delta.where(delta < 0, 0)

        avg_gain = gain.rolling(window=window).mean()
        avg_loss = loss.rolling(window=window).mean()

        rs = avg_gain / avg_loss
        rsi = 100 - (100 / (1 + rs))
        return rsi

    @staticmethod
    def bollinger_bands(series: pd.Series, window: int = 20, num_std: int = 2) -> Tuple[
        pd.Series, pd.Series, pd.Series]:
        """布林带"""
        sma = series.rolling(window=window).mean()
        std = series.rolling(window=window).std()
        upper = sma + (std * num_std)
        lower = sma - (std * num_std)
        return upper, sma, lower

    @staticmethod
    def stochastic_oscillator(high: pd.Series, low: pd.Series, close: pd.Series,
                              k_window: int = 14, d_window: int = 3) -> Tuple[pd.Series, pd.Series]:
        """随机震荡指标"""
        lowest_low = low.rolling(window=k_window).min()
        highest_high = high.rolling(window=k_window).max()

        k = 100 * (close - lowest_low) / (highest_high - lowest_low)
        d = k.rolling(window=d_window).mean()
        return k, d

    @staticmethod
    def atr(high: pd.Series, low: pd.Series, close: pd.Series, window: int = 14) -> pd.Series:
        """平均真实波幅"""
        tr = pd.DataFrame(index=high.index)
        tr['h-l'] = high - low
        tr['h-pc'] = (high - close.shift()).abs()
        tr['l-pc'] = (low - close.shift()).abs()
        tr['tr'] = tr.max(axis=1)

        atr = tr['tr'].rolling(window=window).mean()
        return atr

    @staticmethod
    def adx(high: pd.Series, low: pd.Series, close: pd.Series, window: int = 14) -> Tuple[
        pd.Series, pd.Series, pd.Series]:
        """平均方向指数"""
        # 计算方向运动
        plus_dm = high.diff()
        minus_dm = -low.diff()

        plus_dm[plus_dm < 0] = 0
        minus_dm[minus_dm < 0] = 0

        # 计算真实波幅
        tr = TechnicalIndicators.atr(high, low, close, window)

        # 计算方向指标
        plus_di = 100 * (plus_dm.ewm(alpha=1 / window).mean() / tr)
        minus_di = 100 * (minus_dm.ewm(alpha=1 / window).mean() / tr)

        # 计算ADX
        dx = 100 * abs(plus_di - minus_di) / (plus_di + minus_di)
        adx = dx.ewm(alpha=1 / window).mean()

        return adx, plus_di, minus_di

    @staticmethod
    def fibonacci_retracement(high: float, low: float) -> Dict[str, float]:
        """斐波那契回撤位"""
        levels = [0, 0.236, 0.382, 0.5, 0.618, 0.786, 1]
        diff = high - low
        return {f"level_{lvl}": high - lvl * diff for lvl in levels}

    @staticmethod
    def ichimoku_cloud(high: pd.Series, low: pd.Series,
                       conversion_period: int = 9,
                       base_period: int = 26,
                       lagging_period: int = 52,
                       displacement: int = 26) -> Tuple[pd.Series, pd.Series, pd.Series, pd.Series]:
        """一目均衡表"""
        conversion_line = (high.rolling(window=conversion_period).max() +
                           low.rolling(window=conversion_period).min()) / 2

        base_line = (high.rolling(window=base_period).max() +
                     low.rolling(window=base_period).min()) / 2

        leading_span_a = (conversion_line + base_line) / 2

        leading_span_b = (high.rolling(window=lagging_period).max() +
                          low.rolling(window=lagging_period).min()) / 2

        # 位移到未来
        leading_span_a = leading_span_a.shift(displacement)
        leading_span_b = leading_span_b.shift(displacement)

        return conversion_line, base_line, leading_span_a, leading_span_b

    @staticmethod
    def volume_profile(volume: pd.Series, price: pd.Series, bins: int = 20) -> Dict[float, float]:
        """成交量分布图"""
        volume_sum = volume.sum()
        if volume_sum == 0:
            return {}

        # 计算价格区间
        min_price = price.min()
        max_price = price.max()
        bin_size = (max_price - min_price) / bins

        # 计算每个价格区间的成交量
        profile = {}
        for i in range(bins):
            price_low = min_price + i * bin_size
            price_high = price_low + bin_size
            mask = (price >= price_low) & (price < price_high)
            bin_volume = volume[mask].sum()
            profile[price_low] = bin_volume / volume_sum * 100

        return profile