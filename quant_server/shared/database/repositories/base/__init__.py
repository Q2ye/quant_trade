# quant_server/shared/database/repositories/base/__init__.py
"""
Repository基类模块 - 统一数据访问接口

提供数据库操作的基类和工具类，支持CRUD操作和复杂查询
所有具体的Repository都应继承自BaseRepository或HyperRepositoryBase
"""

from .repository_base import BaseRepository, RepositoryError
from .hyper_repository_base import HyperRepositoryBase
from ..types import PaginationParams, PaginationResult

__all__ = [
    'BaseRepository',
    'RepositoryError',
    'HyperRepositoryBase',
    'PaginationParams',
    'PaginationResult'
]
