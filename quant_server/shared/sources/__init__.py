# quant_server/shared/sources/__init__.py
"""
数据源模块

提供统一的数据访问接口，支持多种数据源（Tushare, Baostock, XTP等）
"""

from .base_source import BaseDataSource
from .tushare_source import TushareSource
from .baostock_source import BaostockSource
from .xtp_source import XtpSource
from .source_factory import DataSourceFactory

__all__ = [
    'BaseDataSource',
    'TushareSource',
    'BaostockSource',
    'XtpSource',
    'DataSourceFactory',
]