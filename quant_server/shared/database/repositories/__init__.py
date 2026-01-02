# 数据仓库（Repository模式）
# -*- coding: utf-8 -*-
"""
# 数据仓库模块导出
# 位置：quant_server/shared/database/repositories/__init__.py
Repository层 - 纯数据访问层
所有业务逻辑应该在Service层实现
"""

from .base import BaseRepository

from quant_server.shared.database.repositories.market.stock_repo import StockRepository
from quant_server.shared.database.repositories.market.quote_repo import QuoteRepository
from quant_server.shared.database.repositories.market.financial_repo import FinancialRepository
from quant_server.shared.database.repositories.market.company_repo import CompanyRepository
from quant_server.shared.database.repositories.market.etf_repo import ETFRepository
from quant_server.shared.database.repositories.market.fund_repo import FundRepository
from quant_server.shared.database.repositories.market.index_repo import IndexRepository

from quant_server.shared.database.repositories.market.sync_task_repo import SyncTaskRepository
from quant_server.shared.database.repositories.reference.trade_calendar_repo import TradeCalendarRepository
from quant_server.shared.database.repositories.reference.basket_repo import BasketRepository
from quant_server.shared.database.repositories.reference.st_list_repo import STListRepository
from quant_server.shared.database.repositories.reference.daily_basic_repo import DailyBasicRepository
from quant_server.shared.database.repositories.reference.daily_limit_repo import DailyLimitRepository
from quant_server.shared.database.repositories.reference.moneyflow_repo import MoneyflowRepository
from quant_server.shared.database.repositories.reference.reward_repo import RewardRepository
from quant_server.shared.database.repositories.reference.adjusted_price_repo import AdjustedPriceRepository

from quant_server.shared.database.repositories.strategy.strategy_repo import StrategyRepository
from quant_server.shared.database.repositories.strategy.parameter_repo import ParameterRepository
from quant_server.shared.database.repositories.strategy.signal_repo import SignalRepository
from quant_server.shared.database.repositories.strategy.backtest_repo import BacktestRepository
from quant_server.shared.database.repositories.strategy.performance_repo import PerformanceRepository

from quant_server.shared.database.repositories.trading.trade_repo import TradeRepository
from quant_server.shared.database.repositories.trading.position_repo import PositionRepository
from quant_server.shared.database.repositories.trading.account_repo import AccountRepository
from quant_server.shared.database.repositories.trading.asset_repo import AssetRepository

from quant_server.shared.database.repositories.system.user_repo import UserRepository
from quant_server.shared.database.repositories.system.role_repo import RoleRepository
from quant_server.shared.database.repositories.system.permission_repo import PermissionRepository
from quant_server.shared.database.repositories.system.config_repo import ConfigRepository
from quant_server.shared.database.repositories.system.log_repo import LogRepository

from quant_server.shared.database.repositories.cache.cache_repo import CacheRepository

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