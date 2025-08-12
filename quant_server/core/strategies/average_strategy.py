import logging

from quant_server.core.strategies.base_strategy import BaseStrategy
from quant_server.utils.technical_indicators import TechnicalIndicators

logger = logging.getLogger('average_strategy')


class DualMovingAverageStrategy(BaseStrategy):
    """双均线策略"""

    def __init__(self, config, main_engine=None):
        super().__init__(config, main_engine)

        # 策略参数
        params = config['params']
        self.fast_window = params.get("fast_window", 5)
        self.slow_window = params.get("slow_window", 20)
        self.tech = TechnicalIndicators()

        logger.info(f"双均线策略初始化: {self.name}")

    def _generate_signals_for_live(self) -> list:
        """实盘生成信号"""
        signals = []
        for symbol in self.symbols:
            try:
                df = self.get_historical_data(symbol, days=self.slow_window + 1)
                if len(df) < self.slow_window + 1:
                    continue

                closes = df['close']
                fast_ma = self.tech.sma(closes, self.fast_window).iloc[-1]
                slow_ma = self.tech.sma(closes, self.slow_window).iloc[-1]

                prev_fast_ma = self.tech.sma(closes.iloc[:-1], self.fast_window).iloc[-1]
                prev_slow_ma = self.tech.sma(closes.iloc[:-1], self.slow_window).iloc[-1]

                if fast_ma > slow_ma and prev_fast_ma <= prev_slow_ma:
                    signals.append(self._create_signal(
                        symbol, "BUY",
                        f"金叉信号: 快线{fast_ma:.2f} > 慢线{slow_ma:.2f}",
                        score=0.8,
                        price=closes.iloc[-1]
                    ))
                elif fast_ma < slow_ma and prev_fast_ma >= prev_slow_ma:
                    signals.append(self._create_signal(
                        symbol, "SELL",
                        f"死叉信号: 快线{fast_ma:.2f} < 慢线{slow_ma:.2f}",
                        score=0.8,
                        price=closes.iloc[-1]
                    ))
            except Exception as e:
                logger.warning(f"分析{symbol}失败: {str(e)}")

        return signals




