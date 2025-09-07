import logging

from quant_server.core.strategies.base_strategy import BaseStrategy
from quant_server.utils.technical_indicators import TechnicalIndicators

logger = logging.getLogger(__name__)


class RSIMeanReversionStrategy(BaseStrategy):
    """RSI均值回归策略"""

    def __init__(self, config, main_engine=None):
        super().__init__(config, main_engine)

        # 策略参数
        params = config['params']
        self.rsi_period = params.get("rsi_period", 14)
        self.oversold = params.get("oversold", 30)
        self.overbought = params.get("overbought", 70)
        self.tech = TechnicalIndicators()

        logger.info(f"RSI均值回归策略初始化: {self.name}")

    def _generate_signals_for_live(self) -> list:
        """实盘生成信号"""
        signals = []
        for symbol in self.symbols:
            try:
                df = self.get_historical_data(symbol, days=self.rsi_period + 1)
                if len(df) < self.rsi_period + 1:
                    continue

                rsi = self.tech.rsi(df['close'], self.rsi_period).iloc[-1]
                current_price = df['close'].iloc[-1]

                if rsi < self.oversold:
                    signals.append(self._create_signal(
                        symbol, "BUY",
                        f"RSI超卖: {rsi:.2f} < {self.oversold}",
                        score=0.75,
                        price=current_price
                    ))
                elif rsi > self.overbought:
                    signals.append(self._create_signal(
                        symbol, "SELL",
                        f"RSI超买: {rsi:.2f} > {self.overbought}",
                        score=0.75,
                        price=current_price
                    ))
            except Exception as e:
                logger.warning(f"分析{symbol}失败: {str(e)}")

        return signals