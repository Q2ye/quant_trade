# xtp_source.py
"""
XTP(迅投)数据源实现

提供实时行情、分钟级数据等
文档: https://www.xuntian.cn/
"""
import logging
from datetime import datetime
from typing import List, Dict
import pandas as pd
from .base_source import BaseDataSource

logger = logging.getLogger(__name__)

# XTP API 可能未安装，提供后备方案
try:
    from pytdx.hq import TdxHq_API
    from pytdx.params import TDXParams
    XTP_AVAILABLE = True
except ImportError:
    XTP_AVAILABLE = False
    logger.warning("pytdx 未安装，XTP数据源功能受限")


class XtpSource(BaseDataSource):
    """XTP(迅投)数据源实现

    支持数据类型:
    - 股票: 实时行情、分钟行情、A股列表
    - 有限: 历史日线(依赖通达信数据)

    特点: 实时性强，适合交易时段数据获取
    注意: 不支持财务数据和ETF深度数据
    """

    def __init__(self, config: dict = None):
        super().__init__()
        config = config or {}
        self.server = config.get('server', '115.231.218.73')
        self.port = config.get('port', 55310)
        self.api = None
        self._connect()

    def _connect(self) -> bool:
        """建立连接"""
        if not XTP_AVAILABLE:
            logger.warning("XTP API 不可用")
            return False

        try:
            self.api = TdxHq_API()
            self.api.connect(self.server, self.port)
            self._connected = True
            logger.info(f"XTP连接成功: {self.server}:{self.port}")
            return True
        except Exception as e:
            logger.error(f"XTP连接失败: {e}")
            self._connected = False
            return False

    def __del__(self):
        self.disconnect()

    def connect(self) -> bool:
        """建立连接"""
        return self._connect()

    def disconnect(self) -> None:
        """断开连接"""
        if self.api is not None:
            try:
                if hasattr(self.api, 'connected') and self.api.connected():
                    self.api.disconnect()
                elif hasattr(self.api, 'close'):
                    self.api.close()
            except Exception as e:
                logger.error(f"关闭XTP连接失败: {e}")
            finally:
                self._connected = False

    def _format_symbol_to_xtp(self, symbol: str) -> tuple:
        """转换股票代码格式: 600000.SH -> (0, '600000')

        Returns:
            (market, code): 0-上海, 1-深圳
        """
        if '.' not in symbol:
            return (0, symbol)

        code, exchange = symbol.split('.')
        market = 0 if exchange.upper() == 'SH' else 1
        return (market, code)

    def _format_symbol_from_xtp(self, market: int, code: str) -> str:
        """转换股票代码格式: (0, '600000') -> '600000.SH'"""
        exchange = 'SH' if market == 0 else 'SZ'
        return f"{code}.{exchange}"

    # ==================== 股票基础数据 ====================

    def get_ashare_list(self) -> list:
        """获取A股列表"""
        if not self._connected or not XTP_AVAILABLE:
            return []

        symbols = []

        try:
            # 上海A股
            for i in range(100):  # 最多获取100页
                try:
                    data = self.api.get_security_list(0, i * 100)
                    if not data:
                        break
                    for stock in data:
                        symbols.append(f"{stock['code']}.SH")
                except:
                    break

            # 深圳A股
            for i in range(100):
                try:
                    data = self.api.get_security_list(1, i * 100)
                    if not data:
                        break
                    for stock in data:
                        symbols.append(f"{stock['code']}.SZ")
                except:
                    break

        except Exception as e:
            logger.error(f"获取A股列表失败: {e}")

        return symbols

    def get_stock_basic(self, exchange: str = '', list_status: str = 'L') -> List[Dict]:
        """获取股票基本信息 (XTP不直接支持，返回空)"""
        logger.warning("XTP 不支持 get_stock_basic，请使用Tushare")
        return []

    def get_daily(self, symbol: str = '', trade_date: str = '',
                  start_date: str = '', end_date: str = '') -> pd.DataFrame:
        """获取日线行情 (XTP不支持历史日线查询)"""
        logger.warning("XTP 不支持历史日线查询，请使用Tushare或Baostock")
        return pd.DataFrame()

    def get_minute_bar(self, symbol: str, start_date: str, end_date: str,
                       freq: str = '5', adj: str = 'qfq') -> pd.DataFrame:
        """
        获取分钟行情

        Args:
            symbol: 股票代码 (如 600000.SH)
            start_date: 开始日期 (YYYYMMDD 或 YYYY-MM-DD)
            end_date: 结束日期
            freq: 频率 1/5/15/30/60 分钟
            adj: 复权类型 (XTP不支持，仅作占位)
        """
        if not self._connected or not XTP_AVAILABLE:
            return pd.DataFrame()

        market, code = self._format_symbol_to_xtp(symbol)

        # 转换日期格式
        start_date = start_date.replace('-', '')
        end_date = end_date.replace('-', '')

        # 转换频率: 1->0, 5->1, 15->2, 30->3, 60->4
        freq_map = {'1': 0, '5': 1, '15': 2, '30': 3, '60': 4}
        ktype = freq_map.get(freq, 1)  # 默认5分钟

        try:
            # 获取分钟K线数据
            data = self.api.get_k_data(code, start_date, end_date,
                                       market=market, ktype=ktype)

            if not data:
                return pd.DataFrame()

            df = pd.DataFrame(data)

            # 转换日期时间
            df['date'] = pd.to_datetime(df['date'])
            df = df.sort_values('date')
            df.rename(columns={
                'vol': 'volume',
                'amount': 'turnover'
            }, inplace=True)

            # 添加时间频率标识
            df['freq'] = freq

            return df

        except Exception as e:
            logger.error(f"获取分钟行情失败: {e}")
            return pd.DataFrame()

    def get_realtime_quotes(self, symbols: List[str]) -> pd.DataFrame:
        """
        获取实时行情（批量）

        Args:
            symbols: 股票代码列表

        Returns:
            实时行情DataFrame
        """
        if not self._connected or not XTP_AVAILABLE:
            return pd.DataFrame()

        # 转换代码格式
        xtp_symbols = []
        for symbol in symbols:
            market, code = self._format_symbol_to_xtp(symbol)
            xtp_symbols.append((market, code))

        try:
            quotes = self.api.get_security_quotes(xtp_symbols)

            if not quotes:
                return pd.DataFrame()

            data = []
            for quote in quotes:
                data.append({
                    'symbol': self._format_symbol_from_xtp(quote['market'], quote['code']),
                    'last_price': quote.get('price', 0),
                    'prev_close': quote.get('last_close', 0),
                    'open': quote.get('open', 0),
                    'high': quote.get('high', 0),
                    'low': quote.get('low', 0),
                    'volume': quote.get('vol', 0),
                    'amount': quote.get('amount', 0),
                    'bid1': quote.get('bid1', 0),
                    'ask1': quote.get('ask1', 0),
                    'bid_vol1': quote.get('bid_vol1', 0),
                    'ask_vol1': quote.get('ask_vol1', 0),
                    'trade_status': quote.get('trade_status', ''),
                    'update_time': datetime.now()
                })

            df = pd.DataFrame(data)
            df = df.set_index('symbol')
            return df

        except Exception as e:
            logger.error(f"获取实时行情失败: {e}")
            return pd.DataFrame()

    def get_realtime_quote(self, symbol: str) -> Dict:
        """
        获取单个股票实时行情

        Args:
            symbol: 股票代码

        Returns:
            行情字典
        """
        df = self.get_realtime_quotes([symbol])
        if not df.empty:
            return df.iloc[0].to_dict()
        return {}

    def get_stock_history(self, symbol: str, start_date: str, end_date: str) -> pd.DataFrame:
        """获取股票历史数据 (XTP不支持，建议使用Tushare)"""
        logger.warning("XTP 不支持历史数据查询，请使用Tushare或Baostock")
        return pd.DataFrame()

    def get_index_constituents(self, index_code: str) -> list:
        """获取指数成分股 (XTP不支持)"""
        logger.warning("XTP 不支持获取指数成分股")
        return []

    def get_tick_data(self, symbol: str, trade_date: str) -> pd.DataFrame:
        """获取Tick级行情数据 (XTP不支持)"""
        logger.warning("XTP 不支持Tick数据")
        return pd.DataFrame()

    def get_large_order(self, symbol: str, trade_date: str,
                        min_amount: float = 100000) -> pd.DataFrame:
        """获取大单成交数据 (XTP不支持)"""
        logger.warning("XTP 不支持大单数据")
        return pd.DataFrame()

    def get_adj_factor(self, symbol: str, start_date: str = '',
                       end_date: str = '') -> pd.DataFrame:
        """获取复权因子 (XTP不支持)"""
        logger.warning("XTP 不支持复权因子")
        return pd.DataFrame()

    def get_suspended(self, start_date: str = '', end_date: str = '') -> pd.DataFrame:
        """获取停牌信息 (XTP不支持)"""
        logger.warning("XTP 不支持停牌信息")
        return pd.DataFrame()

    def get_resumption(self, start_date: str = '', end_date: str = '') -> pd.DataFrame:
        """获取复牌信息 (XTP不支持)"""
        logger.warning("XTP 不支持复牌信息")
        return pd.DataFrame()

    def get_daily_basic(self, symbol: str = '', trade_date: str = '',
                        start_date: str = '', end_date: str = '') -> pd.DataFrame:
        """获取每日行情指标 (XTP不支持)"""
        logger.warning("XTP 不支持每日指标")
        return pd.DataFrame()

    def get_trade_cal(self, exchange: str = '',
                      start_date: str = '', end_date: str = '') -> pd.DataFrame:
        """获取交易日历 (XTP不支持)"""
        logger.warning("XTP 不支持交易日历")
        return pd.DataFrame()

    # ==================== ETF数据 (XTP有限支持) ====================

    def get_etf_basic(self, market: str = '') -> pd.DataFrame:
        """获取ETF基础信息 (XTP不支持)"""
        logger.warning("XTP 不支持ETF基础信息")
        return pd.DataFrame()

    def get_etf_index_weight(self, etf_code: str) -> pd.DataFrame:
        """获取ETF基准指数成分 (XTP不支持)"""
        return pd.DataFrame()

    def get_etf_realtime_minute(self, etf_code: str) -> pd.DataFrame:
        """获取ETF实时分钟行情"""
        return self.get_minute_bar(etf_code,
                                   datetime.now().strftime('%Y%m%d'),
                                   datetime.now().strftime('%Y%m%d'))

    def get_etf_historical_minute(self, etf_code: str, start_date: str,
                                   end_date: str, freq: str = '5') -> pd.DataFrame:
        """获取ETF历史分钟行情"""
        return self.get_minute_bar(etf_code, start_date, end_date, freq)

    def get_etf_realtime_daily(self, etf_code: str) -> pd.DataFrame:
        """获取ETF实时日线"""
        df = self.get_realtime_quotes([etf_code])
        return df

    def get_etf_daily(self, etf_code: str, start_date: str = '',
                      end_date: str = '') -> pd.DataFrame:
        """获取ETF日线行情 (XTP不支持)"""
        logger.warning("XTP 不支持ETF日线")
        return pd.DataFrame()

    def get_etf_adj_factor(self, etf_code: str, start_date: str = '',
                           end_date: str = '') -> pd.DataFrame:
        """获取ETF复权因子 (XTP不支持)"""
        return pd.DataFrame()

    def get_etf_share_scale(self, etf_code: str = '',
                            trade_date: str = '') -> pd.DataFrame:
        """获取ETF份额规模 (XTP不支持)"""
        return pd.DataFrame()

    # ==================== 财务数据 (XTP不支持) ====================

    def get_income_statement(self, symbol: str, period: str = '') -> pd.DataFrame:
        """获取利润表 (XTP不支持)"""
        logger.warning("XTP 不支持财务数据")
        return pd.DataFrame()

    def get_balance_sheet(self, symbol: str, period: str = '') -> pd.DataFrame:
        """获取资产负债表 (XTP不支持)"""
        return pd.DataFrame()

    def get_cashflow_statement(self, symbol: str, period: str = '') -> pd.DataFrame:
        """获取现金流量表 (XTP不支持)"""
        return pd.DataFrame()

    def get_forecast(self, symbol: str = '', period: str = '') -> pd.DataFrame:
        """获取业绩预告 (XTP不支持)"""
        return pd.DataFrame()

    def get_express(self, symbol: str = '', period: str = '') -> pd.DataFrame:
        """获取业绩快报 (XTP不支持)"""
        return pd.DataFrame()

    def get_dividend(self, symbol: str = '', limit: int = 100) -> pd.DataFrame:
        """获取分红送股数据 (XTP不支持)"""
        return pd.DataFrame()

    def get_fina_indicator(self, symbol: str = '', start_date: str = '',
                          end_date: str = '') -> pd.DataFrame:
        """获取财务指标数据 (XTP不支持)"""
        return pd.DataFrame()

    def get_fina_audit(self, symbol: str = '', start_date: str = '',
                       end_date: str = '') -> pd.DataFrame:
        """获取财务审计意见 (XTP不支持)"""
        return pd.DataFrame()

    def get_fina_mainbz(self, symbol: str = '', period: str = '') -> pd.DataFrame:
        """获取主营业务构成 (XTP不支持)"""
        return pd.DataFrame()