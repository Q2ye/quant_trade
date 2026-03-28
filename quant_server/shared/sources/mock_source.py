# quant_server/shared/sources/mock_source.py
"""
模拟数据源

用于开发/测试环境，生成模拟的市场数据，无需外部数据源
继承 BaseDataSource 接口，提供与真实数据源一致的访问方法
"""

import random
import logging
from datetime import date, datetime, timedelta
from typing import Any, List, Dict, Optional
import pandas as pd

from .base_source import BaseDataSource

logger = logging.getLogger(__name__)

# 常用A股股票代码和名称
DEFAULT_STOCKS = {
    "000001.SZ": {"name": "平安银行", "industry": "银行", "area": "深圳", "market": "主板"},
    "600000.SH": {"name": "浦发银行", "industry": "银行", "area": "上海", "market": "主板"},
    "600519.SH": {"name": "贵州茅台", "industry": "白酒", "area": "贵州", "market": "主板"},
    "000002.SZ": {"name": "万科A", "industry": "房地产", "area": "深圳", "market": "主板"},
    "000333.SZ": {"name": "美的集团", "industry": "家电", "area": "广东", "market": "主板"},
    "601318.SH": {"name": "中国平安", "industry": "保险", "area": "深圳", "market": "主板"},
    "601398.SH": {"name": "工商银行", "industry": "银行", "area": "北京", "market": "主板"},
    "600036.SH": {"name": "招商银行", "industry": "银行", "area": "深圳", "market": "主板"},
    "000651.SZ": {"name": "格力电器", "industry": "家电", "area": "广东", "market": "主板"},
    "300750.SZ": {"name": "宁德时代", "industry": "新能源", "area": "福建", "market": "创业板"},
    "600276.SH": {"name": "恒瑞医药", "industry": "医药", "area": "江苏", "market": "主板"},
    "000858.SZ": {"name": "五粮液", "industry": "白酒", "area": "四川", "market": "主板"},
    "601888.SH": {"name": "中国中免", "industry": "旅游", "area": "北京", "market": "主板"},
    "002594.SZ": {"name": "比亚迪", "industry": "汽车", "area": "广东", "market": "主板"},
    "600900.SH": {"name": "长江电力", "industry": "电力", "area": "湖北", "market": "主板"},
}


class MockSource(BaseDataSource):
    """
    模拟数据源

    生成符合真实数据结构的数据，用于开发/测试环境
    """

    def __init__(self, config: Optional[Dict] = None):
        """
        初始化模拟数据源

        Args:
            config: 配置字典，支持以下参数：
                - stock_codes: 股票代码列表
                - date_range_days: 日期范围（天）
                - price_variance: 价格波动幅度
        """
        super().__init__()
        self._connected = True

        config = config or {}

        # 获取配置的股票代码
        stock_codes = config.get("stock_codes", "")
        if isinstance(stock_codes, str) and stock_codes:
            self.stock_codes = [s.strip() for s in stock_codes.split(",") if s.strip()]
        else:
            self.stock_codes = list(DEFAULT_STOCKS.keys())

        self.date_range_days = config.get("date_range_days", 90)
        self.price_variance = config.get("price_variance", 0.1)

        # 存储每个股票的初始价格
        self._stock_prices: Dict[str, float] = {}
        self._init_stock_prices()

        logger.info(f"MockSource 初始化完成，股票数量: {len(self.stock_codes)}")

    def _init_stock_prices(self):
        """初始化股票价格"""
        for stock_code in self.stock_codes:
            if stock_code not in self._stock_prices:
                self._stock_prices[stock_code] = random.uniform(5, 500)

    def _get_trading_dates(self, days: int) -> List[date]:
        """生成交易日期列表（排除周末）"""
        dates = []
        current = date.today()
        while len(dates) < days:
            if current.weekday() < 5:  # 排除周六(5)和周日(6)
                dates.append(current)
            current -= timedelta(days=1)
        return list(reversed(dates))

    def get_stock_history(self, symbol: str, start_date: str, end_date: str) -> pd.DataFrame:
        """获取股票历史数据（日线）"""
        return self.get_daily(symbol=symbol, start_date=start_date, end_date=end_date)

    def get_index_constituents(self, index_code: str) -> list:
        """获取指数成分股"""
        # 返回默认的股票列表作为模拟
        return list(DEFAULT_STOCKS.keys())

    async def get_ashare_list(self) -> list:
        """获取A股列表"""
        result = await self.get_stock_basic()
        return [item["ts_code"] for item in result]

    async def get_stock_basic(self, exchange: str = '', list_status: str = 'L') -> List[Dict]:
        """获取股票基础信息"""
        stocks = []
        for code in self.stock_codes:
            info = DEFAULT_STOCKS.get(code, {"name": code, "industry": "未知", "area": "未知", "market": "主板"})
            stocks.append({
                "ts_code": code,
                "symbol": code.split(".")[0],
                "name": info["name"],
                "area": info.get("area", "未知"),
                "industry": info["industry"],
                "list_date": "2015-01-01",
                "market": info.get("market", "主板"),
                "exchange": "SZSE" if code.endswith(".SZ") else "SSE",
                "delist_date": None,
                "is_hs": "1" if code.startswith("600") or code.startswith("000") else "0",
                "list_status": list_status,
            })
        return stocks

    def get_daily(self, symbol: str = '', trade_date: str = '',
                  start_date: str = '', end_date: str = '') -> pd.DataFrame:
        """获取日线行情"""
        # 解析日期
        if trade_date:
            start = end = datetime.strptime(trade_date, "%Y%m%d").date()
        else:
            if start_date:
                start = datetime.strptime(start_date, "%Y%m%d").date()
            else:
                start = date.today() - timedelta(days=self.date_range_days)
            if end_date:
                end = datetime.strptime(end_date, "%Y%m%d").date()
            else:
                end = date.today()

        trading_dates = self._get_trading_dates((end - start).days + 1)

        # 确定要获取的股票代码
        codes = [symbol] if symbol else self.stock_codes

        all_data = []
        for stock_code in codes:
            info = DEFAULT_STOCKS.get(stock_code, {"name": stock_code, "industry": "未知"})

            if stock_code not in self._stock_prices:
                self._stock_prices[stock_code] = random.uniform(5, 500)
            prev_close = self._stock_prices[stock_code]

            for trade_date_obj in trading_dates:
                # 随机波动
                change_pct = random.uniform(-self.price_variance, self.price_variance)
                close = prev_close * (1 + change_pct)
                open_price = prev_close * (1 + random.uniform(-0.02, 0.02))
                high = max(open_price, close) * (1 + random.uniform(0, 0.05))
                low = min(open_price, close) * (1 - random.uniform(0, 0.05))
                volume = int(random.uniform(500000, 5000000))
                amount = volume * close

                all_data.append({
                    "ts_code": stock_code,
                    "trade_date": trade_date_obj.strftime("%Y%m%d"),
                    "open": round(open_price, 2),
                    "high": round(high, 2),
                    "low": round(low, 2),
                    "close": round(close, 2),
                    "pre_close": round(prev_close, 2),
                    "change": round(close - prev_close, 2),
                    "pct_chg": round(change_pct * 100, 2),
                    "vol": volume,
                    "amount": round(amount, 2),
                })
                prev_close = close

            self._stock_prices[stock_code] = prev_close

        df = pd.DataFrame(all_data)
        if not df.empty:
            df['trade_date'] = pd.to_datetime(df['trade_date'])
        return df

    def get_minute_bar(self, symbol: str, start_date: str, end_date: str,
                       freq: str = '5', adj: str = 'qfq') -> pd.DataFrame:
        """获取分钟行情"""
        # 简化的分钟数据生成
        return pd.DataFrame()

    def get_tick_data(self, symbol: str, trade_date: str) -> pd.DataFrame:
        """获取Tick级行情数据"""
        return pd.DataFrame()

    def get_large_order(self, symbol: str, trade_date: str,
                        min_amount: float = 100000) -> pd.DataFrame:
        """获取大单成交数据"""
        return pd.DataFrame()

    def get_adj_factor(self, symbol: str, start_date: str = '',
                       end_date: str = '') -> pd.DataFrame:
        """获取复权因子"""
        factors = []
        for stock_code in ([symbol] if symbol else self.stock_codes):
            factors.append({
                "ts_code": stock_code,
                "trade_date": date.today().strftime("%Y%m%d"),
                "adj_factor": 1.0
            })
        return pd.DataFrame(factors)

    def get_suspended(self, start_date: str = '', end_date: str = '') -> pd.DataFrame:
        """获取停牌信息"""
        return pd.DataFrame()

    def get_daily_basic(self, trade_date: str = '', start_date: str = '',
                        end_date: str = '') -> pd.DataFrame:
        """获取每日指标"""
        daily_data = self.get_daily(trade_date=trade_date, start_date=start_date, end_date=end_date)
        if daily_data.empty:
            return pd.DataFrame()

        basic_data = []
        for _, row in daily_data.iterrows():
            basic_data.append({
                "ts_code": row["ts_code"],
                "trade_date": row["trade_date"],
                "turnover_rate": round(random.uniform(0.5, 5.0), 2),
                "turnover_rate_f": round(random.uniform(0.3, 3.0), 2),
                "volume_ratio": round(random.uniform(0.5, 2.0), 2),
                "pe": round(random.uniform(10, 50), 2),
                "pb": round(random.uniform(1, 10), 2),
                "ps": round(random.uniform(1, 20), 2),
                "dv_ratio": round(random.uniform(0, 5), 2),
                "total_share": round(random.uniform(1e8, 1e10), 2),
                "float_share": round(random.uniform(1e7, 1e9), 2),
                "free_share": round(random.uniform(1e7, 1e9), 2),
                "total_mv": round(random.uniform(1e8, 1e11), 2),
                "circ_mv": round(random.uniform(1e7, 1e10), 2),
            })
        return pd.DataFrame(basic_data)

    def get_moneyflow(self, symbol: str = '', trade_date: str = '',
                      start_date: str = '', end_date: str = '') -> pd.DataFrame:
        """获取资金流向"""
        daily_data = self.get_daily(trade_date=trade_date, start_date=start_date, end_date=end_date)
        if daily_data.empty:
            return pd.DataFrame()

        moneyflow_data = []
        for _, row in daily_data.iterrows():
            moneyflow_data.append({
                "ts_code": row["ts_code"],
                "trade_date": row["trade_date"],
                "net_amount_main": round(random.uniform(-1e8, 1e8), 2),
                "net_amount_huge": round(random.uniform(-5e7, 5e7), 2),
                "net_amount_large": round(random.uniform(-3e7, 3e7), 2),
                "net_amount_medium": round(random.uniform(-1e7, 1e7), 2),
                "net_amount_small": round(random.uniform(-5e6, 5e6), 2),
            })
        return pd.DataFrame(moneyflow_data)

    def get_etf_basic(self, exchange: str = '') -> List[Dict]:
        """获取ETF基础信息"""
        etfs = [
            {"ts_code": "510300.SH", "name": "沪深300ETF", "exchange": "SSE"},
            {"ts_code": "510500.SH", "name": "中证500ETF", "exchange": "SSE"},
            {"ts_code": "159919.SZ", "name": "创业板ETF", "exchange": "SZSE"},
        ]
        return etfs

    def get_etf_daily(self, symbol: str = '', trade_date: str = '',
                      start_date: str = '', end_date: str = '') -> pd.DataFrame:
        """获取ETF行情"""
        return self.get_daily(symbol=symbol, trade_date=trade_date,
                             start_date=start_date, end_date=end_date)

    def get_financial_statement(self, symbol: str, report_type: str = 'annual') -> pd.DataFrame:
        """获取财务报表"""
        return pd.DataFrame()

    async def get_trade_cal(self, exchange: str = '',
                      start_date: str = '', end_date: str = '') -> pd.DataFrame:
        """获取交易日历"""
        # 如果没有提供日期范围，默认获取当前年份的交易日历
        if not start_date:
            start_date = date.today().strftime("%Y0101")
        if not end_date:
            end_date = date.today().strftime("%Y1231")

        start = datetime.strptime(start_date, "%Y%m%d").date()
        end = datetime.strptime(end_date, "%Y%m%d").date()
        trading_dates = self._get_trading_dates((end - start).days + 1)

        calendar_data = []
        for td in trading_dates:
            calendar_data.append({
                "exchange": exchange or "SSE",
                "cal_date": td.strftime("%Y%m%d"),
                "is_open": 1,
                "pretrade_date": (td - timedelta(days=1)).strftime("%Y%m%d") if td.weekday() > 0 else (td - timedelta(days=3)).strftime("%Y%m%d"),
            })
        return pd.DataFrame(calendar_data)

    def connect(self) -> bool:
        """连接数据源"""
        self._connected = True
        return True

    def disconnect(self) -> None:
        """断开连接"""
        self._connected = False

    @property
    def is_connected(self) -> bool:
        """检查是否已连接"""
        return self._connected
