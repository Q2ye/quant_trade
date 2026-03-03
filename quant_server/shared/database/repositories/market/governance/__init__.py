# -*- coding: utf-8 -*-
"""
公司治理领域Repository统一导出
位置：shared/database/repositories/market/governance/__init__.py

包含公司治理相关数据仓库：
1. ManagerRepository - 上市公司管理层数据仓库
2. RewardRepository - 股票分红送股数据仓库
"""

from .manager_repo import ManagerRepository
from .reward_repo import RewardRepository

__all__ = [
    "ManagerRepository",
    "RewardRepository",
]