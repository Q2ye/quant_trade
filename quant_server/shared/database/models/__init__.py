# quant_server/shared/database/models/__init__.py

# 从 base 导入 Base
from .base import Base

# 数据模型（市场数据相关）
from .data_models import (
	StockBasic, StockCompany, StkManager, StkReward,
	StockDaily, StockMinutes, StockWeekly, StockMonthly,
	StockAdjustedPrices, StockAdjFactor,
	StockDailyBasic, StockDailyLimit, StockMoneyflow,
	TradeCalendar, StockSTList,
	EtfIndex, EtfBasic, EtfDaily, EtfMinute, FundAdjFactor,
)

# 业务模型（交易、策略相关）
from .business_models import (
	SysUser, SysPermission,
	Strategy, StrategyRun,
	Order, Trade, Position,
	RiskRule, RiskEvent,
	Account, AccountDailyPerformance, StrategyDailyPerformance, Signal,
	Basket, BasketItem,
	DataSyncTask,
	BacktestTask, BacktestEquityCurve, BacktestTrade, BacktestPosition,
)

# 系统模型（系统管理相关）
from .system_models import (
	SystemConfig, ScheduledTask, SystemLog,
	FinancialStatement, IndexBasic, IndexDaily, FactorData,
)

# 所有模型的列表，方便批量操作
__all__ = [
	# 基础
	'Base',

	# 数据模型
	'StockBasic', 'StockCompany', 'StkManager', 'StkReward',
	'StockDaily', 'StockMinutes', 'StockWeekly', 'StockMonthly',
	'StockAdjustedPrices', 'StockAdjFactor',
	'StockDailyBasic', 'StockDailyLimit', 'StockMoneyflow',
	'TradeCalendar', 'StockSTList',
	'EtfIndex', 'EtfBasic', 'EtfDaily', 'EtfMinute', 'FundAdjFactor',

	# 业务模型
	'SysUser', 'SysPermission',
	'Strategy', 'StrategyRun',
	'Order', 'Trade', 'Position',
	'RiskRule', 'RiskEvent',
	'Account', 'AccountDailyPerformance', 'StrategyDailyPerformance', 'Signal',
	'Basket', 'BasketItem',
	'DataSyncTask',
	'BacktestTask', 'BacktestEquityCurve', 'BacktestTrade', 'BacktestPosition',

	# 系统模型
	'SystemConfig', 'ScheduledTask', 'SystemLog',
	'FinancialStatement', 'IndexBasic', 'IndexDaily', 'FactorData',
]

# 按模块分组导出，便于导入
DATA_MODELS = [
	StockBasic, StockCompany, StkManager, StkReward,
	StockDaily, StockMinutes, StockWeekly, StockMonthly,
	StockAdjustedPrices, StockAdjFactor,
	StockDailyBasic, StockDailyLimit, StockMoneyflow,
	TradeCalendar, StockSTList,
	EtfIndex, EtfBasic, EtfDaily, EtfMinute, FundAdjFactor,
]

BUSINESS_MODELS = [
	SysUser, SysPermission,
	Strategy, StrategyRun,
	Order, Trade, Position,
	RiskRule, RiskEvent,
	Account, AccountDailyPerformance, StrategyDailyPerformance, Signal,
	Basket, BasketItem,
	DataSyncTask,
	BacktestTask, BacktestEquityCurve, BacktestTrade, BacktestPosition,
]

SYSTEM_MODELS = [
	SystemConfig, ScheduledTask, SystemLog,
	FinancialStatement, IndexBasic, IndexDaily, FactorData,
]