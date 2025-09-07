import logging

from quant_server.core.strategies.base_strategy import BaseStrategy

logger = logging.getLogger(__name__)


class BreakoutStrategy(BaseStrategy):
    """突破策略"""

    def __init__(self, config, main_engine=None):
        super().__init__(config, main_engine)

        # 策略参数
        params = config['params']
        self.breakout_window = params.get("breakout_window", 20)
        self.breakout_multiplier = params.get("breakout_multiplier", 1.02)

        logger.info(f"突破策略初始化: {self.name}")

    def _generate_signals_for_live(self) -> list:
        """实盘生成信号"""
        signals = []
        for symbol in self.symbols:
            try:
                df = self.get_historical_data(symbol, days=self.breakout_window + 1)
                if len(df) < self.breakout_window + 1:
                    continue

                resistance = df['high'].rolling(self.breakout_window).max().iloc[-2]
                breakout_level = resistance * self.breakout_multiplier
                current_price = df['close'].iloc[-1]

                if current_price > breakout_level:
                    signals.append(self._create_signal(
                        symbol, "BUY",
                        f"突破阻力位: {current_price:.2f} > {breakout_level:.2f}",
                        score=0.85,
                        price=current_price
                    ))
            except Exception as e:
                logger.warning(f"分析{symbol}失败: {str(e)}")

        return signals
