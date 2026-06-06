# -*- coding: utf-8 -*-
"""宏观经济数据 Repository 包"""
from .cpi_repo import MacroCpiRepository
from .ppi_repo import MacroPpiRepository
from .gdp_repo import MacroGdpRepository

__all__ = ["MacroCpiRepository", "MacroPpiRepository", "MacroGdpRepository"]
