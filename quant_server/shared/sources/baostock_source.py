# baostock_source.py
"""
Baostock数据源实现

提供A股历史行情、指数成分股等数据
文档: https://www.baostock.com/
"""
import logging
from typing import List, Dict
import baostock as bs
import pandas as pd
from pandas import DataFrame

from .base_source import BaseDataSource

logger = logging.getLogger(__name__)


class BaostockSource(BaseDataSource):
    """Baostock数据源实现

    支持数据类型:
    - 股票: 基础列表、日线/分钟线、复权因子、指数成分股
    - 有限支持: 停复牌信息

    注意: Baostock 不支持 ETF 数据和财务数据
    """

    def __init__(self, config: dict = None):
        super().__init__()
        config = config or {}
        self._lg = None
        self._connect()

    def _connect(self) -> bool:
        """建立连接"""
        try:
            self._lg = bs.login()
            if self._lg.error_code == '0':
                self._connected = True
                logger.info(f"Baostock连接成功: {self._lg.error_msg}")
                return True
            else:
                logger.error(f"Baostock连接失败: {self._lg.error_msg}")
                return False
        except Exception as e:
            logger.error(f"Baostock连接异常: {e}")
            return False

    def __del__(self):
        self.disconnect()

    def connect(self) -> bool:
        """建立连接"""
        return self._connect()

    def disconnect(self) -> None:
        """断开连接"""
        if self._lg is not None:
            try:
                bs.logout()
                self._connected = False
                logger.info("Baostock连接已关闭")
            except Exception as e:
                logger.error(f"关闭Baostock连接失败: {e}")

    def _format_symbol(self, symbol: str) -> str:
        """转换股票代码格式: 000001.SZ -> sz.000001"""
        symbol = symbol.upper()
        if '.' in symbol:
            code, exchange = symbol.split('.')
            if exchange == 'SH':
                return f"sh.{code}"
            elif exchange == 'SZ':
                return f"sz.{code}"
        return symbol

    # ==================== 股票基础数据 ====================

    def get_ashare_list(self) -> list:
        """获取A股列表"""
        if not self._connected:
            self._connect()

        rs = bs.query_stock_basic()
        if rs.error_code != '0':
            logger.error(f"获取A股列表失败: {rs.error_msg}")
            return []

        data_list = []
        while rs.next():
            data_list.append(rs.get_row_data())

        if not data_list:
            return []

        df = pd.DataFrame(data_list, columns=rs.fields)
        # 过滤ST股票
        df = df[~df['code_name'].str.contains('ST', na=False)]
        return df['code'].tolist()

    async def get_stock_basic(self, exchange: str = '', list_status: str = 'L') -> List[Dict]:
        """获取股票基本信息"""
        import asyncio

        async def _fetch():
            if not self._connected:
                self._connect()

            rs = bs.query_stock_basic()
            if rs.error_code != '0':
                return []

            data_list = []
            while rs.next():
                data_list.append(rs.get_row_data())

            if not data_list:
                return []

            df = pd.DataFrame(data_list, columns=rs.fields)
            from utils.core_utils.data_utils.sanitizer import df_to_safe_records; return df_to_safe_records(df)

        return await asyncio.to_thread(_fetch)

    def get_daily(self, symbol: str = '', trade_date: str = '',
                  start_date: str = '', end_date: str = '') -> pd.DataFrame:
        """获取日线行情

        Args:
            symbol: 股票代码 (如 600000.SH)
            trade_date: 交易日期
            start_date: 开始日期
            end_date: 结束日期
        """
        if not self._connected:
            self._connect()

        # 转换日期格式
        start_date = start_date.replace('-', '') if start_date else ''
        end_date = end_date.replace('-', '') if end_date else ''
        trade_date = trade_date.replace('-', '') if trade_date else ''

        bs_symbol = self._format_symbol(symbol) if symbol else ''

        try:
            rs = bs.query_history_k_data_plus(
                bs_symbol,
                "date,open,high,low,close,volume,amount,turn,pctChg",
                start_date=start_date,
                end_date=end_date,
                frequency="d",
                adjustflag="2"  # 前复权
            )

            if rs.error_code != '0':
                logger.error(f"获取日线行情失败: {rs.error_msg}")
                return pd.DataFrame()

            data_list = []
            while rs.next():
                data_list.append(rs.get_row_data())

            if not data_list:
                return pd.DataFrame()

            df = pd.DataFrame(data_list, columns=rs.fields)

            # 转换数据类型
            for col in ['open', 'high', 'low', 'close', 'volume', 'amount', 'turn', 'pctChg']:
                if col in df.columns:
                    df[col] = pd.to_numeric(df[col], errors='coerce')

            df['date'] = pd.to_datetime(df['date'])
            df = df.sort_values('date')
            df.rename(columns={
                'volume': 'vol',
                'amount': 'turnover',
                'pctChg': 'pct_chg',
                'turn': 'turnover_rate'
            }, inplace=True)

            return df

        except Exception as e:
            logger.error(f"获取日线行情异常: {e}")
            return pd.DataFrame()

    def get_minute_bar(self, symbol: str, start_date: str, end_date: str,
                       freq: str = '5', adj: str = 'qfq') -> pd.DataFrame:
        """
        获取分钟行情

        Args:
            symbol: 股票代码
            start_date: 开始日期时间 (YYYY-MM-DD HH:MM:SS)
            end_date: 结束日期时间
            freq: 频率 5/15/30/60 分钟
            adj: 复权类型 (仅支持: 1-后复权 2-前复权 3-不复权)
        """
        if not self._connected:
            self._connect()

        # 转换频率
        freq_map = {'5': '5', '15': '15', '30': '30', '60': '60'}
        bs_freq = freq_map.get(freq, '5')

        # 转换复权类型
        adj_map = {'qfq': '2', 'hfq': '1', 'none': '3'}
        adj_flag = adj_map.get(adj, '2')

        bs_symbol = self._format_symbol(symbol)

        # 提取日期部分
        if ' ' in start_date:
            start_date = start_date.split(' ')[0].replace('-', '')
        if ' ' in end_date:
            end_date = end_date.split(' ')[0].replace('-', '')

        try:
            rs = bs.query_history_k_data_plus(
                bs_symbol,
                "date,time,open,high,low,close,volume,amount",
                start_date=start_date,
                end_date=end_date,
                frequency=bs_freq,
                adjustflag=adj_flag
            )

            if rs.error_code != '0':
                logger.error(f"获取分钟行情失败: {rs.error_msg}")
                return pd.DataFrame()

            data_list = []
            while rs.next():
                data_list.append(rs.get_row_data())

            if not data_list:
                return pd.DataFrame()

            df = pd.DataFrame(data_list, columns=rs.fields)

            # 转换数据类型
            for col in ['open', 'high', 'low', 'close', 'volume', 'amount']:
                if col in df.columns:
                    df[col] = pd.to_numeric(df[col], errors='coerce')

            # 组合日期时间
            df['trade_time'] = pd.to_datetime(df['date'] + ' ' + df['time'])
            df = df.sort_values('trade_time')
            df.rename(columns={
                'volume': 'volume',
                'amount': 'turnover'
            }, inplace=True)

            return df

        except Exception as e:
            logger.error(f"获取分钟行情异常: {e}")
            return pd.DataFrame()

    def get_adj_factor(self, symbol: str, start_date: str = '',
                       end_date: str = '') -> pd.DataFrame:
        """获取复权因子"""
        if not self._connected:
            self._connect()

        bs_symbol = self._format_symbol(symbol)
        start_date = start_date.replace('-', '') if start_date else ''
        end_date = end_date.replace('-', '') if end_date else ''

        try:
            rs = bs.query_adj_factor(
                code=bs_symbol,
                start_date=start_date,
                end_date=end_date
            )

            if rs.error_code != '0':
                logger.error(f"获取复权因子失败: {rs.error_msg}")
                return pd.DataFrame()

            data_list = []
            while rs.next():
                data_list.append(rs.get_row_data())

            if not data_list:
                return pd.DataFrame()

            df = pd.DataFrame(data_list, columns=rs.fields)
            df['date'] = pd.to_datetime(df['date'])
            df['adj_factor'] = pd.to_numeric(df['adj_factor'], errors='coerce')

            return df

        except Exception as e:
            logger.error(f"获取复权因子异常: {e}")
            return pd.DataFrame()

    def get_stock_history(self, symbol: str, start_date: str, end_date: str) -> pd.DataFrame:
        """获取股票历史数据（日线前复权）"""
        # 转换日期格式
        start_date = start_date.replace('-', '')
        end_date = end_date.replace('-', '')

        bs_symbol = self._format_symbol(symbol)

        rs = bs.query_history_k_data_plus(
            bs_symbol,
            "date,open,high,low,close,volume,amount",
            start_date=start_date,
            end_date=end_date,
            frequency="d",
            adjustflag="2"  # 前复权
        )

        if rs.error_code != '0':
            logger.error(f"获取历史数据失败: {rs.error_msg}")
            return pd.DataFrame()

        data_list = []
        while rs.next():
            data_list.append(rs.get_row_data())

        if not data_list:
            return pd.DataFrame()

        df = pd.DataFrame(data_list, columns=rs.fields)

        # 数据类型转换
        for col in ['open', 'high', 'low', 'close', 'volume', 'amount']:
            df[col] = pd.to_numeric(df[col], errors='coerce')

        # 标准化格式
        df['date'] = pd.to_datetime(df['date'])
        df = df.sort_values('date')
        df.set_index('date', inplace=True)
        df.rename(columns={
            'amount': 'turnover'
        }, inplace=True)

        return df[['open', 'high', 'low', 'close', 'volume', 'turnover']]

    def get_index_constituents(self, index_code: str) -> list:
        """获取指数成分股

        Args:
            index_code: 指数代码 (如 000300.SH 沪深300)
        """
        if not self._connected:
            self._connect()

        # 转换指数代码
        index_map = {
            '000300.SH': 'hs300',
            '000905.SH': 'zz500',
            '000016.SH': 'sz50',
            '000001.SH': 'sh'
        }
        bs_index = index_map.get(index_code, index_code.lower())

        try:
            if bs_index == 'hs300':
                rs = bs.query_hs300_stocks()
            elif bs_index == 'zz500':
                rs = bs.query_zz500_stocks()
            elif bs_index == 'sz50':
                rs = bs.query_sz50_stocks()
            else:
                # 通用指数查询
                rs = bs.query_stock_basic()

            if rs.error_code != '0':
                logger.error(f"获取指数成分股失败: {rs.error_msg}")
                return []

            data_list = []
            while rs.next():
                data_list.append(rs.get_row_data())

            if not data_list:
                return []

            df = pd.DataFrame(data_list, columns=rs.fields)

            # 确定代码列名
            if 'code' in df.columns:
                return df['code'].tolist()
            elif 'con_code' in df.columns:
                return df['con_code'].tolist()
            else:
                # 尝试常见列名
                for col in df.columns:
                    if 'code' in col.lower():
                        return df[col].tolist()
                return []

        except Exception as e:
            logger.error(f"获取指数成分股异常: {e}")
            return []

    def get_suspended(self, start_date: str = '', end_date: str = '') -> pd.DataFrame:
        """获取停牌信息"""
        if not self._connected:
            self._connect()

        start_date = start_date.replace('-', '') if start_date else ''
        end_date = end_date.replace('-', '') if end_date else ''

        try:
            rs = bs.query_stock_suspended(start_date=start_date, end_date=end_date)

            if rs.error_code != '0':
                logger.error(f"获取停牌信息失败: {rs.error_msg}")
                return pd.DataFrame()

            data_list = []
            while rs.next():
                data_list.append(rs.get_row_data())

            if not data_list:
                return pd.DataFrame()

            df = pd.DataFrame(data_list, columns=rs.fields)
            df['suspend_date'] = pd.to_datetime(df['suspend_date'])
            if 'resume_date' in df.columns:
                df['resume_date'] = pd.to_datetime(df['resume_date'])

            return df

        except Exception as e:
            logger.error(f"获取停牌信息异常: {e}")
            return pd.DataFrame()

    def get_resumption(self, start_date: str = '', end_date: str = '') -> pd.DataFrame:
        """获取复牌信息"""
        if not self._connected:
            self._connect()

        start_date = start_date.replace('-', '') if start_date else ''
        end_date = end_date.replace('-', '') if end_date else ''

        try:
            rs = bs.query_stock_resumed(start_date=start_date, end_date=end_date)

            if rs.error_code != '0':
                logger.error(f"获取复牌信息失败: {rs.error_msg}")
                return pd.DataFrame()

            data_list = []
            while rs.next():
                data_list.append(rs.get_row_data())

            if not data_list:
                return pd.DataFrame()

            df = pd.DataFrame(data_list, columns=rs.fields)
            df['resume_date'] = pd.to_datetime(df['resume_date'])

            return df

        except Exception as e:
            logger.error(f"获取复牌信息异常: {e}")
            return pd.DataFrame()

    def get_daily_basic(self, symbol: str = '', trade_date: str = '',
                        start_date: str = '', end_date: str = '') -> pd.DataFrame:
        """获取每日行情指标

        注意: Baostock 不直接支持此接口，可使用日线数据计算
        """
        # 使用日线数据代替
        return self.get_daily(symbol, trade_date, start_date, end_date)

    async def get_trade_cal(self, exchange: str = '',
                      start_date: str = '', end_date: str = '') -> pd.DataFrame:
        """获取交易日历"""
        if not self._connected:
            self._connect()

        start_date = start_date.replace('-', '') if start_date else ''
        end_date = end_date.replace('-', '') if end_date else ''

        # 转换交易所代码
        exchange_map = {'SSE': 'sh', 'SZSE': 'sz', 'CFFEX': 'cf'}
        bs_exchange = exchange_map.get(exchange, '')

        try:
            rs = bs.query_trade_cal(
                start_date=start_date,
                end_date=end_date,
                exchange=bs_exchange
            )

            if rs.error_code != '0':
                logger.error(f"获取交易日历失败: {rs.error_msg}")
                return pd.DataFrame()

            data_list = []
            while rs.next():
                data_list.append(rs.get_row_data())

            if not data_list:
                return pd.DataFrame()

            df = pd.DataFrame(data_list, columns=rs.fields)
            df['cal_date'] = pd.to_datetime(df['cal_date'])
            df['is_trading_day'] = df['is_trading_day'].astype(int)

            return df

        except Exception as e:
            logger.error(f"获取交易日历异常: {e}")
            return pd.DataFrame()

    # ==================== ETF数据 (Baostock不支持) ====================

    def get_etf_basic(self, market: str = '') -> pd.DataFrame:
        """获取ETF基础信息 (Baostock不支持)"""
        logger.warning("Baostock 不支持 ETF 数据")
        return pd.DataFrame()

    def get_etf_index_weight(self, etf_code: str) -> pd.DataFrame:
        """获取ETF基准指数成分 (Baostock不支持)"""
        logger.warning("Baostock 不支持 ETF 数据")
        return pd.DataFrame()

    def get_etf_realtime_minute(self, etf_code: str) -> pd.DataFrame:
        """获取ETF实时分钟行情 (Baostock不支持)"""
        logger.warning("Baostock 不支持 ETF 数据")
        return pd.DataFrame()

    def get_etf_historical_minute(self, etf_code: str, start_date: str,
                                   end_date: str, freq: str = '5') -> pd.DataFrame:
        """获取ETF历史分钟行情 (Baostock不支持)"""
        logger.warning("Baostock 不支持 ETF 数据")
        return pd.DataFrame()

    def get_etf_realtime_daily(self, etf_code: str) -> pd.DataFrame:
        """获取ETF实时日线 (Baostock不支持)"""
        logger.warning("Baostock 不支持 ETF 数据")
        return pd.DataFrame()

    def get_etf_daily(self, etf_code: str, start_date: str = '',
                      end_date: str = '') -> pd.DataFrame:
        """获取ETF日线行情 (Baostock不支持)"""
        logger.warning("Baostock 不支持 ETF 数据")
        return pd.DataFrame()

    def get_etf_adj_factor(self, etf_code: str, start_date: str = '',
                           end_date: str = '') -> pd.DataFrame:
        """获取ETF复权因子 (Baostock不支持)"""
        logger.warning("Baostock 不支持 ETF 数据")
        return pd.DataFrame()

    def get_etf_share_scale(self, etf_code: str = '',
                            trade_date: str = '') -> pd.DataFrame:
        """获取ETF份额规模 (Baostock不支持)"""
        logger.warning("Baostock 不支持 ETF 数据")
        return pd.DataFrame()

    # ==================== 财务数据 (Baostock不支持) ====================

    def get_income_statement(self, symbol: str, period: str = '') -> pd.DataFrame:
        """获取利润表 (Baostock不支持)"""
        logger.warning("Baostock 不支持财务数据，请使用Tushare")
        return pd.DataFrame()

    def get_balance_sheet(self, symbol: str, period: str = '') -> pd.DataFrame:
        """获取资产负债表 (Baostock不支持)"""
        logger.warning("Baostock 不支持财务数据，请使用Tushare")
        return pd.DataFrame()

    def get_cashflow_statement(self, symbol: str, period: str = '') -> pd.DataFrame:
        """获取现金流量表 (Baostock不支持)"""
        logger.warning("Baostock 不支持财务数据，请使用Tushare")
        return pd.DataFrame()

    def get_forecast(self, symbol: str = '', period: str = '') -> pd.DataFrame:
        """获取业绩预告 (Baostock不支持)"""
        logger.warning("Baostock 不支持财务数据，请使用Tushare")
        return pd.DataFrame()

    def get_express(self, symbol: str = '', period: str = '') -> pd.DataFrame:
        """获取业绩快报 (Baostock不支持)"""
        logger.warning("Baostock 不支持财务数据，请使用Tushare")
        return pd.DataFrame()

    def get_dividend(self, symbol: str = '', limit: int = 100) -> pd.DataFrame:
        """获取分红送股数据 (Baostock不支持)"""
        logger.warning("Baostock 不支持财务数据，请使用Tushare")
        return pd.DataFrame()

    def get_fina_indicator(self, symbol: str = '', start_date: str = '',
                          end_date: str = '') -> pd.DataFrame:
        """获取财务指标数据 (Baostock不支持)"""
        logger.warning("Baostock 不支持财务数据，请使用Tushare")
        return pd.DataFrame()

    def get_fina_audit(self, symbol: str = '', start_date: str = '',
                       end_date: str = '') -> pd.DataFrame:
        """获取财务审计意见 (Baostock不支持)"""
        logger.warning("Baostock 不支持财务数据，请使用Tushare")
        return pd.DataFrame()

    def get_fina_mainbz(self, symbol: str = '', period: str = '') -> pd.DataFrame:
        """获取主营业务构成 (Baostock不支持)"""
        logger.warning("Baostock 不支持财务数据，请使用Tushare")
        return pd.DataFrame()