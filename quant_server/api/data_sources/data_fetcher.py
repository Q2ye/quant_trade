import logging
from datetime import datetime

import pandas as pd
from typing import List, Dict, Optional, Any

from pandas import Series

from quantCore.database.data_sources.data_source_manager import DataSourceManager

logger = logging.getLogger('data_fetcher')


class DataFetcher:
    """统一数据获取接口（适配器模式）"""

    def __init__(self, config_path: str = "config/data_sources.yaml"):
        self.manager = DataSourceManager(config_path)
        logger.info("数据获取工具初始化完成")

    def get_daily_data(self, symbol: str, start: str, end: str,
                       adj: str = 'qfq') -> pd.DataFrame:
        """获取日线数据（自动处理复权）"""
        try:
            # 从数据源管理器获取原始数据
            df = self.manager.get_stock_history(symbol, start, end)

            # 应用复权逻辑
            if adj == 'qfq':
                return self._apply_qfq_adjustment(df, symbol)
            elif adj == 'hfq':
                return self._apply_hfq_adjustment(df, symbol)
            return df
        except Exception as e:
            logger.error(f"获取日线数据失败 [{symbol}]: {str(e)}", exc_info=True)
            # 返回空DataFrame避免崩溃
            return pd.DataFrame(columns=['open', 'high', 'low', 'close', 'volume', 'turnover'])

    def _apply_qfq_adjustment(self, df: pd.DataFrame, symbol: str) -> pd.DataFrame:
        """应用前复权计算"""
        try:
            # 获取复权因子
            factor_df = self.manager.get_adjust_factor(symbol)

            if factor_df.empty:
                logger.warning(f"未找到 {symbol} 的复权因子，返回原始数据")
                return df

            # 合并因子数据
            merged = df.join(factor_df, how='left')

            # 前向填充缺失的因子值
            merged['factor'].ffill(inplace=True)

            # 计算复权价格
            last_factor = merged['factor'].iloc[-1] if not merged.empty else 1.0
            for col in ['open', 'high', 'low', 'close']:
                merged[col] = merged[col] * merged['factor'] / last_factor

            return merged[['open', 'high', 'low', 'close', 'volume', 'turnover']]
        except Exception as e:
            logger.error(f"前复权计算失败 [{symbol}]: {str(e)}", exc_info=True)
            return df

    def _apply_hfq_adjustment(self, df: pd.DataFrame, symbol: str) -> pd.DataFrame:
        """应用后复权计算"""
        try:
            # 获取复权因子
            factor_df = self.manager.get_adjust_factor(symbol)

            if factor_df.empty:
                logger.warning(f"未找到 {symbol} 的复权因子，返回原始数据")
                return df

            # 合并因子数据
            merged = df.join(factor_df, how='left')

            # 前向填充缺失的因子值
            merged['factor'].ffill(inplace=True)

            # 计算复权价格
            first_factor = merged['factor'].iloc[0] if not merged.empty else 1.0
            for col in ['open', 'high', 'low', 'close']:
                merged[col] = merged[col] * merged['factor'] / first_factor

            return merged[['open', 'high', 'low', 'close', 'volume', 'turnover']]
        except Exception as e:
            logger.error(f"后复权计算失败 [{symbol}]: {str(e)}", exc_info=True)
            return df

    def get_ashare_list(self) -> List[Dict[str, str]]:
        """获取A股列表"""
        try:
            return self.manager.get_ashare_list()
        except Exception as e:
            logger.error(f"获取A股列表失败: {str(e)}", exc_info=True)
            return []

    def get_index_constituents(self, index_code: str = '000300.SH') -> List[str]:
        """获取指数成分股"""
        try:
            return self.manager.get_index_constituents(index_code)
        except Exception as e:
            logger.error(f"获取指数成分股失败 [{index_code}]: {str(e)}", exc_info=True)
            return []

    def get_minute_data(self, symbol: str, date: str, freq: str = '5min') -> pd.DataFrame:
        """获取分钟线数据"""
        try:
            return self.manager.get_minute_data(symbol, date, freq)
        except Exception as e:
            logger.error(f"获取分钟线数据失败 [{symbol}-{date}-{freq}]: {str(e)}", exc_info=True)
            return pd.DataFrame()

    def get_latest_bar(self, symbol: str, interval: str = '1min') -> Optional[Dict[str, Any]]:
        """
        获取最新的K线数据

        参数:
            symbol: 股票代码
            interval: K线间隔，如 '1min', '5min', '15min'

        返回:
            包含最新K线数据的字典，格式:
            {
                'symbol': 股票代码,
                'datetime': 时间戳,
                'open': 开盘价,
                'high': 最高价,
                'low': 最低价,
                'close': 收盘价,
                'volume': 成交量,
                'turnover': 成交额（可选）
            }
        """
        try:
            # 获取当前时间
            now = datetime.now()
            date_str = now.strftime('%Y-%m-%d')

            # 获取当天的分钟线数据
            df = self.manager.get_minute_data(symbol, date_str, interval)

            if df.empty:
                return None

            # 获取最新的一行数据
            latest_row = df.iloc[-1]

            return {
                'symbol': symbol,
                'datetime': latest_row.name,  # 假设index是时间戳
                'open': latest_row['open'],
                'high': latest_row['high'],
                'low': latest_row['low'],
                'close': latest_row['close'],
                'volume': latest_row['volume'],
                'turnover': latest_row.get('turnover', 0)
            }
        except Exception as e:
            logger.error(f"获取最新K线数据失败 [{symbol}-{interval}]: {str(e)}", exc_info=True)
            return None

    def get_financial_data(self, symbol: str, period: str = 'latest') -> Dict[str, Any]:
        """获取财务数据"""
        try:
            return self.manager.get_financial_data(symbol, period)
        except Exception as e:
            logger.error(f"获取财务数据失败 [{symbol}-{period}]: {str(e)}", exc_info=True)
            return {}

    def get_financial_indicator(self, symbol: str, indicator: str,
                                start: str, end: str) -> Series:
        """获取财务指标时间序列"""
        try:
            return self.manager.get_financial_indicator(symbol, indicator, start, end)
        except Exception as e:
            logger.error(f"获取财务指标失败 [{symbol}-{indicator}]: {str(e)}", exc_info=True)
            return pd.Series()

    def switch_data_source(self, source_name: str):
        """切换首选数据源"""
        try:
            self.manager.set_primary_source(source_name)
            logger.info(f"已切换到数据源: {source_name}")
        except Exception as e:
            logger.error(f"切换数据源失败: {str(e)}", exc_info=True)

    def set_fetch_strategy(self, strategy: str):
        """设置数据获取策略"""
        try:
            self.manager.set_fetch_strategy(strategy)
            logger.info(f"数据获取策略已设置为: {strategy}")
        except Exception as e:
            logger.error(f"设置获取策略失败: {str(e)}", exc_info=True)

    def get_adjust_factor(self, symbol: str) -> pd.DataFrame:
        """获取复权因子"""
        try:
            return self.manager.get_adjust_factor(symbol)
        except Exception as e:
            logger.error(f"获取复权因子失败 [{symbol}]: {str(e)}", exc_info=True)
            return pd.DataFrame()