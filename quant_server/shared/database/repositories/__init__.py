# 数据仓库（Repository模式）
# -*- coding: utf-8 -*-
"""
# 数据仓库模块导出
# 位置：quant_server/shared/database/repositories/__init__.py
Repository层 - 纯数据访问层
所有业务逻辑应该在Service层实现
"""

from .base import BaseRepository

from .stock_repo import StockRepository
from .quote_repo import QuoteRepository
from .financial_repo import FinancialRepository
from .company_repo import CompanyRepository
from .etf_repo import ETFRepository
from .fund_repo import FundRepository
from .index_repo import IndexRepository

from .sync_task_repo import SyncTaskRepository
from .trade_calendar_repo import TradeCalendarRepository
from .basket_repo import BasketRepository
from .st_list_repo import STListRepository
from .daily_basic_repo import DailyBasicRepository
from .daily_limit_repo import DailyLimitRepository
from .moneyflow_repo import MoneyflowRepository
from .reward_repo import RewardRepository
from .adjusted_price_repo import AdjustedPriceRepository

from .strategy_repo import StrategyRepository
from .parameter_repo import ParameterRepository
from .signal_repo import SignalRepository
from .backtest_repo import BacktestRepository
from .performance_repo import PerformanceRepository

from .trade_repo import TradeRepository
from .position_repo import PositionRepository
from .account_repo import AccountRepository
from .asset_repo import AssetRepository

from .user_repo import UserRepository
from .role_repo import RoleRepository
from .permission_repo import PermissionRepository
from .config_repo import ConfigRepository
from .log_repo import LogRepository

from .cache_repo import CacheRepository

__all__ = [
	'BaseRepository',

	'StockRepository',
	'QuoteRepository',
	'FinancialRepository',
	'CompanyRepository',
	'ETFRepository',
	'FundRepository',
	'IndexRepository',

	'SyncTaskRepository',
	'TradeCalendarRepository',
	'BasketRepository',
	'STListRepository',
	'DailyBasicRepository',
	'DailyLimitRepository',
	'MoneyflowRepository',
	'RewardRepository',
	'AdjustedPriceRepository',

	'StrategyRepository',
	'ParameterRepository',
	'SignalRepository',
	'BacktestRepository',
	'PerformanceRepository',

	'TradeRepository',
	'PositionRepository',
	'AccountRepository',
	'AssetRepository',

	'UserRepository',
	'RoleRepository',
	'PermissionRepository',
	'ConfigRepository',
	'LogRepository',

	'CacheRepository',
]