from typing import Any

import tushare as ts
import pandas as pd
from .base_source import BaseDataSource


class TushareSource(BaseDataSource):
    """Tushare数据源实现"""

    def __init__(self, config: dict):
        super().__init__(config)
        ts.set_token(self.config['token'])
        self.pro = ts.pro_api()

    def get_stock_history(self, symbol: str, start_date: str, end_date: str) -> Any | None:
        # 获取前复权数据
        df = ts.pro_bar(
            ts_code=symbol,
            adj='qfq',
            start_date=start_date,
            end_date=end_date
        )

        if df is None or df.empty:
            return None

        # 标准化数据格式
        df = df.sort_values('trade_date')
        df['trade_date'] = pd.to_datetime(df['trade_date'])
        df.set_index('trade_date', inplace=True)
        df.rename(columns={
            'open': 'open',
            'high': 'high',
            'low': 'low',
            'close': 'close',
            'vol': 'volume',
            'amount': 'turnover'
        }, inplace=True)

        return df[['open', 'high', 'low', 'close', 'volume', 'turnover']]

    def get_index_constituents(self, index_code: str) -> list:
        # 获取指数成分股
        df = self.pro.index_weight(
            index_code=index_code,
            start_date=pd.Timestamp.now().strftime('%Y%m%d')
        )
        return df['con_code'].tolist() if df is not None else []

    def get_ashare_list(self) -> list:
        # 获取A股列表（排除ST/*ST）
        df = self.pro.stock_basic(exchange='', list_status='L', fields='ts_code,name')
        # 过滤ST股票
        df = df[~df['name'].str.contains('ST')]
        return df['ts_code'].tolist()