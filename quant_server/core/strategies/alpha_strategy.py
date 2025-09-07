import numpy as np
import pandas as pd
import logging
from typing import Dict, Any, Optional

from quant_server.core.strategies.base_strategy import BaseStrategy
from quant_server.utils.technical_indicators import TechnicalIndicators

logger = logging.getLogger(__name__)


class ValueAlphaStrategy(BaseStrategy):
    """价值因子Alpha策略"""

    def __init__(self, config, main_engine=None):
        super().__init__(config, main_engine)

        # 策略参数
        params = config['params']
        self.factors = params.get("factors", ["pe", "pb", "dividend_yield"])
        self.weights = params.get("weights", [0.4, 0.3, 0.3])
        self.factor_data = {}

        logger.info(f"价值Alpha策略初始化: {self.name}")

    def _generate_signals_for_live(self) -> list:
        """实盘生成信号"""
        self.get_current_factor_data()
        return self.generate_signals()

    def _generate_signals_for_backtest(self, daily_data: dict, current_date: str) -> list:
        """回测生成信号"""
        self.get_factor_data_for_date(current_date)
        return self.generate_signals()

    def get_current_factor_data(self):
        """获取当前因子数据"""
        self.factor_data = {}
        for symbol in self.symbols:
            try:
                # 使用数据服务获取基本面数据
                fundamental = self.data_service.get_fundamental_data(symbol)
                if fundamental:
                    self.factor_data[symbol] = {
                        "pe": fundamental.get('pe_ratio', 0),
                        "pb": fundamental.get('pb_ratio', 0),
                        "dividend_yield": fundamental.get('dividend_yield', 0),
                        "close": fundamental.get('close', 0)
                    }
            except Exception as e:
                logger.warning(f"获取{symbol}基本面数据失败: {str(e)}")

    def get_factor_data_for_date(self, date):
        """获取特定日期的因子数据"""
        self.factor_data = {}
        for symbol in self.symbols:
            try:
                # 使用数据服务获取历史基本面数据
                fundamental = self.data_service.get_fundamental_data(symbol, date)
                if fundamental:
                    self.factor_data[symbol] = {
                        "pe": fundamental.get('pe_ratio', 0),
                        "pb": fundamental.get('pb_ratio', 0),
                        "dividend_yield": fundamental.get('dividend_yield', 0),
                        "close": fundamental.get('close', 0)
                    }
            except Exception as e:
                logger.warning(f"获取{symbol}历史基本面数据失败: {str(e)}")

    def calculate_scores(self):
        """计算因子分数"""
        if not self.factor_data:
            return {}

        df = pd.DataFrame.from_dict(self.factor_data, orient='index')
        df = df.replace([np.inf, -np.inf], np.nan).fillna(df.mean())

        for factor in self.factors:
            if factor in df.columns:
                # 价值因子: 越低越好 (取负值)
                if factor in ["pe", "pb"]:
                    df[factor] = -df[factor]

                # 标准化
                mean = df[factor].mean()
                std = df[factor].std()
                if std > 0:
                    df[factor] = (df[factor] - mean) / std

        # 计算综合分数
        df["score"] = 0
        for i, factor in enumerate(self.factors):
            if factor in df.columns:
                df["score"] += df[factor] * self.weights[i]

        return df["score"].to_dict()

    def generate_signals(
        self,
        daily_data: Optional[Dict[str, Dict[str, Any]]] = None,
        current_date: Optional[str] = None
    ) -> list:
        """生成交易信号（添加参数以匹配基类签名）"""
        scores = self.calculate_scores()
        if not scores:
            return []

        # 按分数排序
        sorted_symbols = sorted(scores.items(), key=lambda x: x[1], reverse=True)

        # 买入前20%的股票
        buy_count = max(1, int(len(sorted_symbols) * 0.2))
        buy_symbols = [item[0] for item in sorted_symbols[:buy_count]]

        signals = []
        for symbol in buy_symbols:
            price = self.factor_data[symbol]["close"]
            score = scores[symbol]

            signals.append(self._create_signal(
                symbol, "BUY",
                f"价值因子得分: {score:.2f}",
                score=score,
                price=price
            ))

        logger.info(f"生成{len(signals)}个买入信号")
        return signals


class TechnicalAlphaStrategy(BaseStrategy):
    """技术因子Alpha策略"""

    def __init__(self, config, main_engine=None):
        super().__init__(config, main_engine)

        # 策略参数
        params = config['params']
        self.rsi_period = params.get("rsi_period", 14)
        self.macd_fast = params.get("macd_fast", 12)
        self.macd_slow = params.get("macd_slow", 26)
        self.macd_signal = params.get("macd_signal", 9)
        self.volume_multiplier = params.get("volume_multiplier", 1.5)

        # 技术指标计算器
        self.tech = TechnicalIndicators()

        logger.info(f"技术Alpha策略初始化: {self.name}")

    def _generate_signals_for_live(self) -> list:
        """实盘生成信号"""
        signals = []
        for symbol in self.symbols:
            try:
                # 使用数据服务获取历史数据
                df = self.get_historical_data(symbol, days=30)
                if len(df) < 30:
                    continue

                signal = self.analyze_symbol(df, symbol)
                if signal:
                    signals.append(signal)
            except Exception as e:
                logger.warning(f"分析{symbol}失败: {str(e)}")

        return signals

    def _generate_signals_for_backtest(self, daily_data: dict, current_date: str) -> list:
        """回测生成信号"""
        signals = []
        for symbol in self.symbols:
            try:
                # 使用数据服务获取历史数据
                df = self.get_historical_data(symbol, days=30)
                if len(df) < 30:
                    continue

                signal = self.analyze_symbol(df, symbol)
                if signal:
                    signals.append(signal)
            except Exception as e:
                logger.warning(f"分析{symbol}失败: {str(e)}")

        return signals

    def analyze_symbol(self, df, symbol):
        """分析单个股票生成信号"""
        # 计算技术指标
        closes = df['close'].values
        volumes = df['volume'].values

        rsi = self.tech.rsi(df['close'], self.rsi_period).iloc[-1]

        macd, signal, _ = self.tech.macd(
            df['close'], self.macd_fast, self.macd_slow, self.macd_signal
        )
        macd_val = macd.iloc[-1]
        signal_val = signal.iloc[-1]

        last_close = closes[-1]
        last_volume = volumes[-1]
        prev_volume = volumes[-2] if len(volumes) >= 2 else last_volume

        # 技术信号判断
        buy_signal = False
        reasons = []

        if rsi < 30:
            buy_signal = True
            reasons.append("RSI超卖")
        if macd_val > signal_val and macd.iloc[-2] <= signal.iloc[-2]:
            buy_signal = True
            reasons.append("MACD金叉")
        if last_volume > prev_volume * self.volume_multiplier:
            buy_signal = True
            reasons.append("成交量放大")

        if buy_signal:
            # 计算信号强度
            score = 0.5 * (1 - rsi / 100)
            score += 0.3 * (macd_val - signal_val) / last_close * 100
            score += 0.2 * min(last_volume / np.mean(volumes[-10:]) / 3, 1.0)
            score = min(max(score, 0), 1.0)

            return self._create_signal(
                symbol, "BUY",
                ", ".join(reasons),
                score=score,
                price=last_close
            )

        return None