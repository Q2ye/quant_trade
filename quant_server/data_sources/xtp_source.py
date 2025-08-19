import pandas as pd
from .base_source import BaseDataSource
from pytdx.hq import TdxHq_API


class XtpSource(BaseDataSource):
    """迅投(XTP)数据源实现"""

    def __init__(self, config: dict):
        super().__init__(config)
        self.server = config.get('server', '115.231.218.73')
        self.port = config.get('port', 55310)
        self.api = TdxHq_API()
        # 添加连接异常处理
        try:
            self.api.connect(self.server, self.port)
        except Exception as e:
            print(f"连接XTP服务器失败: {e}")

    def __del__(self):
        # 使用connected()方法检查连接状态
        if hasattr(self.api, 'connected') and self.api.connected():
            self.api.disconnect()

    def get_stock_history(self, symbol: str, start_date: str, end_date: str) -> pd.DataFrame:
        """获取股票历史数据"""
        # 转换股票代码格式：600000.SH -> SH600000
        exchange = symbol.split('.')[-1]
        stock_code = f"{exchange}{symbol[:6]}"

        # 确保日期格式正确
        start_date = start_date.replace('-', '')
        end_date = end_date.replace('-', '')

        try:
            # 使用ktype参数替代frequency，使用整数9表示日线
            data = self.api.get_k_data(stock_code,start_date,end_date)
        except Exception as e:
            print(f"获取股票历史数据失败: {e}")
            return pd.DataFrame()  # 返回空DataFrame

        if not data:
            return pd.DataFrame()  # 返回空DataFrame

        # 转换为DataFrame
        df = pd.DataFrame(data)
        df['date'] = pd.to_datetime(df['date'])
        df.set_index('date', inplace=True)
        df.rename(columns={
            'open': 'open',
            'high': 'high',
            'low': 'low',
            'close': 'close',
            'vol': 'volume',
            'amount': 'turnover'  # 直接使用API提供的amount字段
        }, inplace=True)

        # 不需要手动计算成交额
        return df[['open', 'high', 'low', 'close', 'volume', 'turnover']]

    def get_index_constituents(self, index_code: str) -> list:
        """获取指数成分股（迅投API不支持，需使用其他数据源）"""
        return []  # 需结合其他数据源实现

    def get_ashare_list(self) -> list:
        """获取A股列表"""
        # 获取上海A股
        try:
            sh_stocks = self.api.get_security_list(0, 0)
        except:
            sh_stocks = []

        # 获取深圳A股
        try:
            sz_stocks = self.api.get_security_list(1, 0)
        except:
            sz_stocks = []

        all_stocks = sh_stocks + sz_stocks

        # 格式化股票代码
        symbols = []
        for stock in all_stocks:
            exchange = 'SH' if stock['market'] == 0 else 'SZ'
            symbol = f"{stock['code']}.{exchange}"
            symbols.append(symbol)

        return symbols

    def get_realtime_quotes(self, symbols: list) -> pd.DataFrame:
        """获取实时行情"""
        # 转换股票代码格式
        xtp_symbols = []
        for symbol in symbols:
            exchange = symbol.split('.')[-1]
            code = symbol[:6]
            market = 0 if exchange == 'SH' else 1
            xtp_symbols.append((market, code))

        try:
            # 批量获取行情
            quotes = self.api.get_security_quotes(xtp_symbols)
        except Exception as e:
            print(f"获取实时行情失败: {e}")
            return pd.DataFrame()

        # 转换为DataFrame
        data = []
        for quote in quotes:
            data.append({
                'symbol': f"{quote['code']}.{'SH' if quote['market'] == 0 else 'SZ'}",
                'current_price': quote['price'],
                'prev_close': quote['last_close'],
                'open': quote['open'],
                'high': quote['high'],
                'low': quote['low'],
                'volume': quote['vol'],
                'amount': quote['amount']
            })

        return pd.DataFrame(data).set_index('symbol')