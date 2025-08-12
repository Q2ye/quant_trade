from .base_strategy import BaseStrategy
import pandas as pd
import logging

logger = logging.getLogger('value_strategy')


class ValueStrategy(BaseStrategy):
    """价值投资策略 - 基于低估值指标选股"""

    def __init__(self, config, main_engine=None):
        super().__init__(config, main_engine)
        # 策略参数
        self.pe_max = config['params'].get('pe_max', 25)
        self.pb_max = config['params'].get('pb_max', 3)
        self.dividend_min = config['params'].get('dividend_min', 2.0)
        self.market_cap_min = config['params'].get('market_cap_min', 50)  # 单位：亿

    def preload_data(self, symbols=None, days=60):
        """预加载所需数据"""
        super().preload_data(symbols)
        # 加载基本面数据
        self.fundamental_data = self.data_service.get_fundamental_data()
        # 加载市场数据
        self.market_data = self.data_service.get_market_data()
        logger.info(f"价值策略 {self.name} 数据预加载完成")

    def _generate_signals_for_live(self):
        """实盘生成信号"""
        # 合并基本面数据
        merged_data = pd.merge(
            self.fundamental_data,
            self.market_data[['symbol', 'close']],
            on='symbol'
        )

        # 计算市值
        merged_data['market_cap'] = merged_data['total_shares'] * merged_data['close'] / 1e8

        # 筛选条件
        signals = []
        for _, row in merged_data.iterrows():
            symbol = row['symbol']

            # 排除ST/*ST股票
            if 'ST' in row['name']:
                continue

            # 估值筛选
            if (row['pe'] < self.pe_max and
                    row['pb'] < self.pb_max and
                    row['dividend_yield'] > self.dividend_min and
                    row['market_cap'] > self.market_cap_min):
                # 计算综合得分
                pe_score = (self.pe_max - row['pe']) / self.pe_max
                pb_score = (self.pb_max - row['pb']) / self.pb_max
                div_score = row['dividend_yield'] / 10  # 假设股息率上限为10%
                cap_score = row['market_cap'] / 1000  # 假设市值上限为1000亿

                total_score = 0.4 * pe_score + 0.3 * pb_score + 0.2 * div_score + 0.1 * cap_score

                # 生成买入信号，使用当前收盘价
                signals.append(self._create_signal(
                    symbol, "BUY",
                    f"PE:{row['pe']:.1f}, PB:{row['pb']:.1f}, DIV:{row['dividend_yield']:.2f}%",
                    score=total_score, price=row['close']
                ))

        return signals

    def _generate_signals_for_backtest(self, daily_data, current_date):
        """回测生成信号"""
        # 回测模式下使用传入的daily_data
        signals = []
        for symbol, data in daily_data.items():
            # 获取基本面数据
            fundamental = self.data_service.get_fundamental(symbol, current_date)

            if fundamental:
                # 计算市值
                market_cap = fundamental['total_shares'] * data['close'] / 1e8

                # 估值筛选
                if (fundamental['pe'] < self.pe_max and
                        fundamental['pb'] < self.pb_max and
                        fundamental['dividend_yield'] > self.dividend_min and
                        market_cap > self.market_cap_min):
                    # 生成买入信号，使用当日收盘价
                    signals.append(self._create_signal(
                        symbol, "BUY",
                        f"PE:{fundamental['pe']:.1f}, PB:{fundamental['pb']:.1f}",
                        score=0.9, price=data['close']
                    ))

        return signals