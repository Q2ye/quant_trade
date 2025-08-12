from .base_strategy import BaseStrategy
import logging

from ...utils.technical_indicators import TechnicalIndicators

logger = logging.getLogger('technical_strategy')


class TechnicalStrategy(BaseStrategy):
    """技术分析策略 - 基于技术指标选股"""

    def __init__(self, config, main_engine=None):
        super().__init__(config, main_engine)
        # 策略参数
        self.rsi_period = config['params'].get('rsi_period', 14)
        self.macd_fast = config['params'].get('macd_fast', 12)
        self.macd_slow = config['params'].get('macd_slow', 26)
        self.macd_signal = config['params'].get('macd_signal', 9)
        self.volume_multiplier = config['params'].get('volume_multiplier', 1.5)

        # 技术指标计算器
        self.tech = TechnicalIndicators()

    def preload_data(self, symbols=None, days=60):
        """预加载所需数据"""
        super().preload_data(symbols, days)
        logger.info(f"技术策略 {self.name} 数据预加载完成")

    def _generate_signals_for_live(self) -> list:
        """实盘生成信号"""
        signals = []

        for symbol in self.symbols:
            # 获取历史数据
            df = self.get_historical_data(symbol, days=60)
            if len(df) < max(self.rsi_period, self.macd_slow):
                continue

            # 计算技术指标 - 使用正确的方法名
            df['rsi'] = self.tech.rsi(df['close'], self.rsi_period)
            macd_line, signal_line, _ = self.tech.macd(
                df['close'], self.macd_fast, self.macd_slow, self.macd_signal
            )
            df['macd'] = macd_line
            df['macd_signal'] = signal_line

            # 获取最新数据点
            last_row = df.iloc[-1]
            prev_row = df.iloc[-2]

            # 技术信号判断
            buy_signal = False
            reason = ""

            # RSI超卖
            if last_row['rsi'] < 30:
                buy_signal = True
                reason += "RSI超卖 "

            # MACD金叉
            if last_row['macd'] > last_row['macd_signal'] and prev_row['macd'] <= prev_row['macd_signal']:
                buy_signal = True
                reason += "MACD金叉 "

            # 成交量放大
            if last_row['volume'] > prev_row['volume'] * self.volume_multiplier:
                buy_signal = True
                reason += "成交量放大 "

            if buy_signal:
                # 计算信号强度
                score = 0.4 * (1 - last_row['rsi'] / 100)  # RSI越低得分越高
                score += 0.4 * (last_row['macd'] - last_row['macd_signal']) / last_row['close'] * 100
                score += 0.2 * min(last_row['volume'] / (df['volume'].mean() * 3), 1.0)
                score = min(max(score, 0), 1.0)  # 限制在0-1之间

                # 使用最新收盘价作为信号价格
                signals.append(self._create_signal(
                    symbol, "BUY", reason.strip(),
                    score=score, price=last_row['close']
                ))

        return signals

    def _generate_signals_for_backtest(self, daily_data: dict, current_date: str) -> list:
        """回测生成信号"""
        signals = []
        for symbol, data in daily_data.items():
            # 使用基类方法获取历史数据
            hist_data = self.get_historical_data(symbol, days=30)

            if len(hist_data) < max(self.rsi_period, self.macd_slow):
                continue

            # 计算技术指标 - 使用正确的方法名
            hist_data['rsi'] = self.tech.rsi(hist_data['close'], self.rsi_period)
            macd_line, signal_line, _ = self.tech.macd(
                hist_data['close'], self.macd_fast, self.macd_slow, self.macd_signal
            )
            hist_data['macd'] = macd_line
            hist_data['macd_signal'] = signal_line

            # 获取最新数据点
            last_row = hist_data.iloc[-1]
            prev_row = hist_data.iloc[-2]

            # MACD金叉
            if last_row['macd'] > last_row['macd_signal'] and prev_row['macd'] <= prev_row['macd_signal']:
                # 使用当日收盘价作为信号价格
                signals.append(self._create_signal(
                    symbol, "BUY", "MACD金叉",
                    score=0.8, price=data['close']
                ))

        return signals