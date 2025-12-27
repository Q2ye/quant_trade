from abc import ABC, abstractmethod
import pandas as pd


class BaseDataSource(ABC):
    """数据源抽象基类"""

    def __init__(self):
        pass

    @abstractmethod
    def get_stock_history(self, symbol: str, start_date: str, end_date: str) -> pd.DataFrame:
        """获取股票历史数据"""
        pass

    @abstractmethod
    def get_index_constituents(self, index_code: str) -> list:
        """获取指数成分股"""
        pass

    @abstractmethod
    def get_ashare_list(self) -> list:
        """获取A股列表"""
        pass