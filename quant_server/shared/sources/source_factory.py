# quant_server/shared/sources/source_factory.py
"""
数据源工厂模块

根据配置创建对应的数据源实例，支持动态扩展和实例缓存。
从全局配置（settings）中读取数据源相关参数，并提供统一的 get_source 接口。
"""

import os
import logging
from typing import Dict, Optional, Type, Union

from quant_server.shared.config.settings import get_settings, Settings
from .base_source import BaseDataSource
from .tushare_source import TushareSource
from .baostock_source import BaostockSource
from .xtp_source import XtpSource

logger = logging.getLogger(__name__)


class UnsupportedDataSourceError(Exception):
    """不支持的 data source 类型异常"""
    pass


class DataSourceFactory:
    """
    数据源工厂类

    负责创建和管理数据源实例，根据配置中的参数初始化对应的数据源。
    支持的数据源类型：tushare, baostock, xtp
    """

    # 数据源类型与类的映射
    _source_map: Dict[str, Type[BaseDataSource]] = {
        'tushare': TushareSource,
        'baostock': BaostockSource,
        'xtp': XtpSource,
        # 可扩展其他数据源，如 'sina': SinaSource, 'eastmoney': EastMoneySource 等
    }

    def __init__(self, settings: Optional[Settings] = None):
        """
        初始化工厂

        Args:
            settings: 全局配置实例，如果为 None 则自动获取
        """
        self.settings = settings or get_settings()
        self._instances: Dict[str, BaseDataSource] = {}

    @classmethod
    def register_source(cls, name: str, source_class: Type[BaseDataSource]) -> None:
        """
        注册新的数据源类型

        Args:
            name: 数据源类型名称
            source_class: 数据源类（必须继承 BaseDataSource）
        """
        if not issubclass(source_class, BaseDataSource):
            raise TypeError(f"{source_class.__name__} must inherit from BaseDataSource")
        cls._source_map[name] = source_class
        logger.info(f"Registered data source: {name} -> {source_class.__name__}")

    def get_source(self, source_type: Union[str, object]) -> BaseDataSource:
        """
        获取数据源实例（如果已存在则返回缓存实例，否则创建并缓存）

        Args:
            source_type: 数据源类型，可以是字符串（如 'tushare'）或枚举值（如 DataSource.TUSHARE）

        Returns:
            数据源实例

        Raises:
            UnsupportedDataSourceError: 当 source_type 不支持时抛出
        """
        # 处理枚举类型（假设枚举有 value 属性）
        if hasattr(source_type, 'value'):
            source_type = source_type.value

        source_key = source_type.lower()

        # 返回缓存的实例
        if source_key in self._instances:
            logger.debug(f"Return cached data source instance for {source_key}")
            return self._instances[source_key]

        source_class = self._source_map.get(source_key)
        if not source_class:
            raise UnsupportedDataSourceError(
                f"Unsupported data source type: '{source_type}'. "
                f"Supported types: {list(self._source_map.keys())}"
            )

        # 根据不同类型准备配置并创建实例
        instance = self._create_instance(source_key, source_class)
        self._instances[source_key] = instance
        logger.info(f"Created new data source instance of type: {source_key}")
        return instance

    def _create_instance(self, source_key: str, source_class: Type[BaseDataSource]) -> BaseDataSource:
        """
        根据数据源类型创建实例，并从配置中提取所需参数

        Args:
            source_key: 数据源类型键（小写）
            source_class: 数据源类

        Returns:
            数据源实例
        """
        # Tushare 特殊处理：需要设置 token（可通过环境变量或构造函数）
        if source_key == 'tushare':
            token = self.settings.DATA_SOURCE.TUSHARE_TOKEN if hasattr(self.settings, 'DATA_SOURCE') else None
            config = {'token': token} if token else {}
            return source_class(config)

        # Baostock 需要 config 字典
        elif source_key == 'baostock':
            config = {}
            return source_class(config)

        # Xtp 需要 config 字典，包含 server 和 port
        elif source_key == 'xtp':
            # 从配置中提取 XTP 服务器信息
            config = {
                'server': getattr(self.settings.TRADE, 'BROKER_HOST', None) or '115.231.218.73',
                'port': getattr(self.settings.TRADE, 'BROKER_PORT', None) or 55310
            }
            logger.debug(f"Xtp config: server={config['server']}, port={config['port']}")
            return source_class(config)

        # 其他数据源可在此扩展
        else:
            # 默认传递空配置，或尝试从 settings 中提取对应前缀的配置
            try:
                return source_class()
            except TypeError:
                # 如果必须传 config，则传递空字典
                return source_class({})

    def close_all(self):
        """
        关闭所有已创建的数据源实例，释放资源（如网络连接）
        """
        for source_key, instance in self._instances.items():
            try:
                # 尝试调用 close 或 disconnect 方法（不同数据源可能不同）
                if hasattr(instance, 'close') and callable(instance.close):
                    instance.close()
                elif hasattr(instance, 'disconnect') and callable(instance.disconnect):
                    instance.disconnect()
                elif hasattr(instance, '__del__'):
                    # 触发析构函数（不推荐显式调用，但作为后备）
                    instance.__del__()
                logger.debug(f"Closed data source: {source_key}")
            except Exception as e:
                logger.error(f"Error closing data source {source_key}: {e}")

        self._instances.clear()

    def __del__(self):
        """析构时自动关闭所有数据源"""
        self.close_all()