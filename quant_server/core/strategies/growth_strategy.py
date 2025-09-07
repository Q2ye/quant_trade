from .base_strategy import BaseStrategy
import pandas as pd
import logging

logger = logging.getLogger(__name__)


class GrowthStrategy(BaseStrategy):
    """成长投资策略 - 基于高增长指标选股"""

    def __init__(self, config, main_engine=None):
        super().__init__(config, main_engine)
        # 策略参数
        self.revenue_growth_min = config['params'].get('revenue_growth_min', 0.15)  # 15%
        self.profit_growth_min = config['params'].get('profit_growth_min', 0.20)  # 20%
        self.roe_min = config['params'].get('roe_min', 0.15)  # 15%
        self.debt_ratio_max = config['params'].get('debt_ratio_max', 0.60)  # 60%

    def preload_data(self, symbols=None, days=60):  # 添加 days 参数
        """预加载所需数据"""
        super().preload_data(symbols, days)  # 传递 days 参数
        # 使用 data_service 替代 data_fetcher
        self.fundamental_data = self.data_service.get_fundamental_data()
        self.financial_data = self.data_service.get_financial_data()
        logger.info(f"成长策略 {self.name} 数据预加载完成")

    def _generate_signals_for_live(self):
        """实盘生成信号"""
        # 合并数据
        merged_data = pd.merge(
            self.fundamental_data,
            self.financial_data,
            on='symbol'
        )

        # 筛选条件
        signals = []
        for _, row in merged_data.iterrows():
            symbol = row['symbol']

            # 排除ST/*ST股票
            if 'ST' in row['name']:
                continue

            # 成长性筛选
            if (row['revenue_growth'] > self.revenue_growth_min and
                    row['profit_growth'] > self.profit_growth_min and
                    row['roe'] > self.roe_min and
                    row['debt_ratio'] < self.debt_ratio_max):
                # 计算综合得分
                rev_score = min(row['revenue_growth'] / 0.5, 1.0)  # 假设50%增长为上限
                profit_score = min(row['profit_growth'] / 0.5, 1.0)
                roe_score = min(row['roe'] / 0.3, 1.0)  # 假设30% ROE为上限
                debt_score = 1 - (row['debt_ratio'] / 1.0)  # 假设100%负债为最差

                total_score = 0.3 * rev_score + 0.3 * profit_score + 0.3 * roe_score + 0.1 * debt_score

                # 生成买入信号，使用当前收盘价作为信号价格
                signals.append(self._create_signal(
                    symbol, "BUY",
                    f"营收增:{row['revenue_growth'] * 100:.1f}%, 利润增:{row['profit_growth'] * 100:.1f}%",
                    score=total_score, price=row['close']
                ))

        return signals

    def _generate_signals_for_backtest(self, daily_data, current_date):
        """回测生成信号"""
        signals = []
        for symbol, data in daily_data.items():
            # 获取财务数据
            financial = self.data_service.get_financial(symbol, current_date)

            if financial:
                # 成长性筛选
                if (financial['revenue_growth'] > self.revenue_growth_min and
                        financial['profit_growth'] > self.profit_growth_min and
                        financial['roe'] > self.roe_min and
                        financial['debt_ratio'] < self.debt_ratio_max):
                    # 生成买入信号，使用当日收盘价
                    signals.append(self._create_signal(
                        symbol, "BUY",
                        f"利润增:{financial['profit_growth'] * 100:.1f}%",
                        score=0.9, price=data['close']
                    ))

        return signals