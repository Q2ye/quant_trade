# quant_server/shared/database/models/__init__.py

# 从 base 导入 Base
from .base import Base

# 数据模型（市场数据相关）
from .data_models import (
	StockBasic, StockCompany, StkManager, StkReward,
	StockDaily, StockMinutes, StockWeekly, StockMonthly,
	StockAdjustedPrices, StockAdjFactor,
	StockDailyBasic, StockDailyLimit, StockMoneyflow,
	FinancialIncome, FinancialBalance, FinancialCashflow,
	TradeCalendar, StockSTList,
	EtfIndex, EtfBasic, EtfDaily, EtfMinute, FundAdjFactor,
	IndexBasic, IndexDaily, IndexWeight,
	FactorData,
)

# 业务模型（交易、策略相关）
from .business_models import (
	SysUser, SysRole, SysUserRole, SysPermission,
	Strategy, StrategyRun, StrategyDailyPerformance, Signal,
	Account, AccountDailyPerformance,
	Order, Trade, Position,
	RiskRule, RiskEvent,
	Basket, BasketItem,
	DataSyncTask,
	BacktestTask, BacktestEquityCurve, BacktestTrade, BacktestPosition,
)

# 系统模型（系统管理相关）
from .system_models import (
	SystemConfig, ScheduledTask, SystemLog,
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
	'FinancialIncome', 'FinancialBalance', 'FinancialCashflow',
	'TradeCalendar', 'StockSTList',
	'EtfIndex', 'EtfBasic', 'EtfDaily', 'EtfMinute', 'FundAdjFactor',
	'IndexBasic', 'IndexDaily', 'IndexWeight',
	'FactorData',

	# 业务模型
	'SysUser', 'SysRole', 'SysUserRole', 'SysPermission',
	'Strategy', 'StrategyRun', 'StrategyDailyPerformance', 'Signal',
	'Account', 'AccountDailyPerformance',
	'Order', 'Trade', 'Position',
	'RiskRule', 'RiskEvent',
	'Basket', 'BasketItem',
	'DataSyncTask',
	'BacktestTask', 'BacktestEquityCurve', 'BacktestTrade', 'BacktestPosition',

	# 系统模型
	'SystemConfig', 'ScheduledTask', 'SystemLog',
]

# 按模块分组导出，便于导入和批量操作
DATA_MODELS = [
	StockBasic, StockCompany, StkManager, StkReward,
	StockDaily, StockMinutes, StockWeekly, StockMonthly,
	StockAdjustedPrices, StockAdjFactor,
	StockDailyBasic, StockDailyLimit, StockMoneyflow,
	FinancialIncome, FinancialBalance, FinancialCashflow,
	TradeCalendar, StockSTList,
	EtfIndex, EtfBasic, EtfDaily, EtfMinute, FundAdjFactor,
	IndexBasic, IndexDaily, IndexWeight,
	FactorData,
]

BUSINESS_MODELS = [
	SysUser, SysRole, SysUserRole, SysPermission,
	Strategy, StrategyRun, StrategyDailyPerformance, Signal,
	Account, AccountDailyPerformance,
	Order, Trade, Position,
	RiskRule, RiskEvent,
	Basket, BasketItem,
	DataSyncTask,
	BacktestTask, BacktestEquityCurve, BacktestTrade, BacktestPosition,
]

SYSTEM_MODELS = [
	SystemConfig, ScheduledTask, SystemLog,
]

# 按功能域分组导出，便于领域驱动的开发
USER_MANAGEMENT_MODELS = [
	SysUser, SysRole, SysUserRole, SysPermission,
]

STRATEGY_MODELS = [
	Strategy, StrategyRun, StrategyDailyPerformance, Signal,
	BacktestTask, BacktestEquityCurve, BacktestTrade, BacktestPosition,
]

TRADING_MODELS = [
	Account, AccountDailyPerformance,
	Order, Trade, Position,
	Basket, BasketItem,
]

RISK_MANAGEMENT_MODELS = [
	RiskRule, RiskEvent,
]

MARKET_DATA_MODELS = [
	StockBasic, StockCompany, StkManager, StkReward,
	StockDaily, StockMinutes, StockWeekly, StockMonthly,
	StockAdjustedPrices, StockAdjFactor,
	StockDailyBasic, StockDailyLimit, StockMoneyflow,
	FinancialIncome, FinancialBalance, FinancialCashflow,
	TradeCalendar, StockSTList,
	EtfIndex, EtfBasic, EtfDaily, EtfMinute, FundAdjFactor,
	IndexBasic, IndexDaily, IndexWeight,
	FactorData,
]

SYSTEM_MANAGEMENT_MODELS = [
	SystemConfig, ScheduledTask, SystemLog, DataSyncTask,
]

# 按领域分组的映射
MODEL_GROUPS = {
	'user_management': USER_MANAGEMENT_MODELS,
	'strategy': STRATEGY_MODELS,
	'trading': TRADING_MODELS,
	'risk_management': RISK_MANAGEMENT_MODELS,
	'market_data': MARKET_DATA_MODELS,
	'system_management': SYSTEM_MANAGEMENT_MODELS,
}

# 按表名获取模型的映射
MODEL_BY_TABLE_NAME = {
	model.__tablename__: model
	for model in DATA_MODELS + BUSINESS_MODELS + SYSTEM_MODELS
}