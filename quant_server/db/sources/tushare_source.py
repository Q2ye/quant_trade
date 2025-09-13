# tushare_source.py
import os
from typing import Any, List, Dict
import tushare as ts
import pandas as pd
from .base_source import BaseDataSource


class TushareSource(BaseDataSource):
    """Tushare数据源实现"""

    def __init__(self):
        super().__init__()
        ts.set_token(os.getenv('TUSHARE_TOKEN'))
        self.pro = ts.pro_api()

    def get_stock_basic(self, exchange: str = '', list_status: str = 'L') -> List[Dict]:
        """获取股票基本信息"""
        fields = 'ts_code,symbol,name,area,industry,market,list_date,fullname,enname,cnspell,exchange,curr_type,list_status,delist_date,is_hs'
        df = self.pro.stock_basic(exchange=exchange, list_status=list_status, fields=fields)
        return df.to_dict('records') if df is not None else []

    def get_stock_company(self, exchange: str = '') -> List[Dict]:
        """获取上市公司基本信息"""
        df = self.pro.stock_company(exchange=exchange)
        return df.to_dict('records') if df is not None else []

    def get_stk_managers(self, ts_code: str = '', ann_date: str = '') -> List[Dict]:
        """获取上市公司管理层信息"""
        df = self.pro.stk_managers(ts_code=ts_code, ann_date=ann_date)
        return df.to_dict('records') if df is not None else []

    def get_stk_rewards(self, ts_code: str = '', end_date: str = '') -> List[Dict]:
        """获取管理层薪酬和持股信息"""
        df = self.pro.stk_rewards(ts_code=ts_code, end_date=end_date)
        return df.to_dict('records') if df is not None else []

    def get_daily(self, ts_code: str = '', trade_date: str = '', start_date: str = '', end_date: str = '') -> List[
        Dict]:
        """获取日线行情"""
        df = self.pro.daily(ts_code=ts_code, trade_date=trade_date, start_date=start_date, end_date=end_date)
        return df.to_dict('records') if df is not None else []

    def get_weekly(self, ts_code: str = '', trade_date: str = '', start_date: str = '', end_date: str = '') -> List[
        Dict]:
        """获取周线行情"""
        df = self.pro.weekly(ts_code=ts_code, trade_date=trade_date, start_date=start_date, end_date=end_date)
        return df.to_dict('records') if df is not None else []

    def get_monthly(self, ts_code: str = '', trade_date: str = '', start_date: str = '', end_date: str = '') -> List[
        Dict]:
        """获取月线行情"""
        df = self.pro.monthly(ts_code=ts_code, trade_date=trade_date, start_date=start_date, end_date=end_date)
        return df.to_dict('records') if df is not None else []

    def get_adj_factor(self, ts_code: str = '', trade_date: str = '', start_date: str = '', end_date: str = '') -> List[
        Dict]:
        """获取复权因子"""
        df = self.pro.adj_factor(ts_code=ts_code, trade_date=trade_date, start_date=start_date, end_date=end_date)
        return df.to_dict('records') if df is not None else []

    def get_daily_basic(self, ts_code: str = '', trade_date: str = '', start_date: str = '', end_date: str = '') -> \
    List[Dict]:
        """获取每日指标"""
        df = self.pro.daily_basic(ts_code=ts_code, trade_date=trade_date, start_date=start_date, end_date=end_date)
        return df.to_dict('records') if df is not None else []

    def get_moneyflow(self, ts_code: str = '', trade_date: str = '', start_date: str = '', end_date: str = '') -> List[
        Dict]:
        """获取资金流向"""
        df = self.pro.moneyflow(ts_code=ts_code, trade_date=trade_date, start_date=start_date, end_date=end_date)
        return df.to_dict('records') if df is not None else []

    def get_trade_cal(self, exchange: str = '', start_date: str = '', end_date: str = '') -> List[Dict]:
        """获取交易日历"""
        df = self.pro.trade_cal(exchange=exchange, start_date=start_date, end_date=end_date)
        return df.to_dict('records') if df is not None else []

    def get_fund_basic(self, market: str = '') -> List[Dict]:
        """获取基金基本信息"""
        df = self.pro.fund_basic(market=market)
        return df.to_dict('records') if df is not None else []

    def get_fund_daily(self, ts_code: str = '', trade_date: str = '', start_date: str = '', end_date: str = '') -> List[
        Dict]:
        """获取基金日线行情"""
        df = self.pro.fund_daily(ts_code=ts_code, trade_date=trade_date, start_date=start_date, end_date=end_date)
        return df.to_dict('records') if df is not None else []

    def get_index_weight(self, index_code: str = '', trade_date: str = '') -> List[Dict]:
        """获取指数成分股"""
        df = self.pro.index_weight(index_code=index_code, trade_date=trade_date)
        return df.to_dict('records') if df is not None else []

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

    def sync_all_data(self):
        """同步所有数据到数据库"""
        # 这里可以实现全量数据同步逻辑
        # 依次调用各个数据获取方法，并使用对应的Service保存到数据库
        pass