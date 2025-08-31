import logging

import baostock as bs
import pandas as pd
from pandas import DataFrame

from .base_source import BaseDataSource

logger = logging.getLogger('baostock_source')


class BaostockSource(BaseDataSource):
    """Baostock数据源实现"""

    def __init__(self, config: dict):
        super().__init__(config)
        # self.lg = bs.login()

    def __del__(self):
        bs.logout()

    def get_stock_history(self, symbol: str, start_date: str, end_date: str) -> DataFrame | None:
        # 获取复权数据
        rs = bs.query_history_k_data_plus(
            symbol,
            "date,open,high,low,close,volume,amount",
            start_date=start_date,
            end_date=end_date,
            frequency="d",
            adjustflag="2"  # 前复权
        )

        if rs.error_code != '0':
            return None

        # 转换为DataFrame
        df = pd.DataFrame(rs.data, columns=rs.fields)
        if df.empty:
            return None

        # 标准化数据格式
        df['date'] = pd.to_datetime(df['date'])
        df.set_index('date', inplace=True)
        df = df.astype({
            'open': float,
            'high': float,
            'low': float,
            'close': float,
            'volume': float,
            'amount': float
        })
        df.rename(columns={'amount': 'turnover'}, inplace=True)

        return df

    def get_index_constituents(self, index_code: str) -> list:
        """获取指数成分股"""
        # 根据不同的指数代码使用不同的查询方法
        if index_code == '000300.SH':  # 沪深300
            rs = bs.query_hs300_stocks()
        elif index_code == '000905.SH':  # 中证500
            rs = bs.query_zz500_stocks()
        elif index_code == '000016.SH':  # 上证50
            rs = bs.query_sz50_stocks()
        else:
            # 通用指数查询
            rs = bs.query_stock_basic()

        if rs.error_code != '0':
            logger.error(f"获取指数成分股失败: {rs.error_msg}")
            return []

        # 解析结果
        df = pd.DataFrame(rs.data, columns=rs.fields)

        # 确定成分股代码列名（不同接口返回的列名不同）
        if 'code' in df.columns:
            return df['code'].tolist()
        elif 'con_code' in df.columns:
            return df['con_code'].tolist()
        else:
            logger.warning(f"无法识别指数成分股列名: {df.columns}")
            return []


    def get_ashare_list(self) -> list:
        # 获取A股列表
        rs = bs.query_stock_basic()
        if rs.error_code != '0':
            return []

        df = pd.DataFrame(rs.data, columns=rs.fields)
        # 过滤ST股票
        df = df[~df['code_name'].str.contains('ST')]
        return df['code'].tolist()
