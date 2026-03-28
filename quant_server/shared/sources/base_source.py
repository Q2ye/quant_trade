from abc import ABC, abstractmethod
from typing import Any, List, Dict, Optional
from datetime import datetime
import pandas as pd


class BaseDataSource(ABC):
    """
    数据源抽象基类

    定义统一的数据访问接口，支持多种数据类型：
    - 股票基础数据（列表、日线、分钟线、Tick、大单、复权因子、停复牌）
    - ETF数据（基础信息、行情、份额规模）
    - 财务数据（报表、指标）
    """

    def __init__(self):
        self._connected = False

    # ==================== 股票基础数据 ====================

    @abstractmethod
    def get_stock_history(self, symbol: str, start_date: str, end_date: str) -> pd.DataFrame:
        """获取股票历史数据（日线）"""
        pass

    @abstractmethod
    def get_index_constituents(self, index_code: str) -> list:
        """获取指数成分股"""
        pass

    @abstractmethod
    def get_ashare_list(self) -> list:
        """获取A股列表"""
        pass

    async def get_stock_basic(self, exchange: str = '', list_status: str = 'L') -> List[Dict]:
        """获取股票基础信息"""
        raise NotImplementedError("子类需实现 get_stock_basic")

    def get_daily(self, symbol: str = '', trade_date: str = '',
                  start_date: str = '', end_date: str = '') -> pd.DataFrame:
        """获取日线行情"""
        raise NotImplementedError("子类需实现 get_daily")

    def get_minute_bar(self, symbol: str, start_date: str, end_date: str,
                       freq: str = '5', adj: str = 'qfq') -> pd.DataFrame:
        """
        获取分钟行情

        Args:
            symbol: 股票代码
            start_date: 开始日期时间
            end_date: 结束日期时间
            freq: 频率 (1/5/15/30/60 分钟)
            adj: 复权类型 (qfq/hfq/none)
        """
        raise NotImplementedError("子类需实现 get_minute_bar")

    def get_tick_data(self, symbol: str, trade_date: str) -> pd.DataFrame:
        """获取Tick级行情数据"""
        raise NotImplementedError("子类需实现 get_tick_data")

    def get_large_order(self, symbol: str, trade_date: str,
                        min_amount: float = 100000) -> pd.DataFrame:
        """
        获取大单成交数据

        Args:
            symbol: 股票代码
            trade_date: 交易日期
            min_amount: 最小成交金额（元）
        """
        raise NotImplementedError("子类需实现 get_large_order")

    def get_adj_factor(self, symbol: str, start_date: str = '',
                       end_date: str = '') -> pd.DataFrame:
        """获取复权因子"""
        raise NotImplementedError("子类需实现 get_adj_factor")

    def get_suspended(self, start_date: str = '', end_date: str = '') -> pd.DataFrame:
        """获取停牌信息"""
        raise NotImplementedError("子类需实现 get_suspended")

    def get_resumption(self, start_date: str = '', end_date: str = '') -> pd.DataFrame:
        """获取复牌信息"""
        raise NotImplementedError("子类需实现 get_resumption")

    def get_daily_basic(self, symbol: str = '', trade_date: str = '',
                       start_date: str = '', end_date: str = '') -> pd.DataFrame:
        """获取每日行情指标（PE、PB、成交量等）"""
        raise NotImplementedError("子类需实现 get_daily_basic")

    # ==================== ETF数据 ====================

    def get_etf_basic(self, market: str = '') -> pd.DataFrame:
        """获取ETF基础信息"""
        raise NotImplementedError("子类需实现 get_etf_basic")

    def get_etf_index_weight(self, etf_code: str) -> pd.DataFrame:
        """获取ETF基准指数成分"""
        raise NotImplementedError("子类需实现 get_etf_index_weight")

    def get_etf_realtime_minute(self, etf_code: str) -> pd.DataFrame:
        """获取ETF实时分钟行情"""
        raise NotImplementedError("子类需实现 get_etf_realtime_minute")

    def get_etf_historical_minute(self, etf_code: str, start_date: str,
                                   end_date: str, freq: str = '5') -> pd.DataFrame:
        """获取ETF历史分钟行情"""
        raise NotImplementedError("子类需实现 get_etf_historical_minute")

    def get_etf_realtime_daily(self, etf_code: str) -> pd.DataFrame:
        """获取ETF实时日线"""
        raise NotImplementedError("子类需实现 get_etf_realtime_daily")

    def get_etf_daily(self, etf_code: str, start_date: str = '',
                      end_date: str = '') -> pd.DataFrame:
        """获取ETF日线行情"""
        raise NotImplementedError("子类需实现 get_etf_daily")

    def get_etf_adj_factor(self, etf_code: str, start_date: str = '',
                           end_date: str = '') -> pd.DataFrame:
        """获取ETF复权因子"""
        raise NotImplementedError("子类需实现 get_etf_adj_factor")

    def get_etf_share_scale(self, etf_code: str = '',
                            trade_date: str = '') -> pd.DataFrame:
        """获取ETF份额规模"""
        raise NotImplementedError("子类需实现 get_etf_share_scale")

    # ==================== 财务数据 ====================

    def get_income_statement(self, symbol: str, period: str = '') -> pd.DataFrame:
        """获取利润表"""
        raise NotImplementedError("子类需实现 get_income_statement")

    def get_balance_sheet(self, symbol: str, period: str = '') -> pd.DataFrame:
        """获取资产负债表"""
        raise NotImplementedError("子类需实现 get_balance_sheet")

    def get_cashflow_statement(self, symbol: str, period: str = '') -> pd.DataFrame:
        """获取现金流量表"""
        raise NotImplementedError("子类需实现 get_cashflow_statement")

    def get_forecast(self, symbol: str = '', period: str = '') -> pd.DataFrame:
        """获取业绩预告"""
        raise NotImplementedError("子类需实现 get_forecast")

    def get_express(self, symbol: str = '', period: str = '') -> pd.DataFrame:
        """获取业绩快报"""
        raise NotImplementedError("子类需实现 get_express")

    def get_dividend(self, symbol: str = '', limit: int = 100) -> pd.DataFrame:
        """获取分红送股数据"""
        raise NotImplementedError("子类需实现 get_dividend")

    def get_fina_indicator(self, symbol: str = '', start_date: str = '',
                          end_date: str = '') -> pd.DataFrame:
        """获取财务指标数据"""
        raise NotImplementedError("子类需实现 get_fina_indicator")

    def get_fina_audit(self, symbol: str = '', start_date: str = '',
                       end_date: str = '') -> pd.DataFrame:
        """获取财务审计意见"""
        raise NotImplementedError("子类需实现 get_fina_audit")

    def get_fina_mainbz(self, symbol: str = '', period: str = '') -> pd.DataFrame:
        """获取主营业务构成"""
        raise NotImplementedError("子类需实现 get_fina_mainbz")

    # ==================== 通用接口 ====================

    def connect(self) -> bool:
        """建立连接"""
        self._connected = True
        return True

    def disconnect(self) -> None:
        """断开连接"""
        self._connected = False

    def is_connected(self) -> bool:
        """检查连接状态"""
        return self._connected

    async def get_trade_cal(self, exchange: str = '',
                      start_date: str = '', end_date: str = '') -> pd.DataFrame:
        """获取交易日历"""
        raise NotImplementedError("子类需实现 get_trade_cal")