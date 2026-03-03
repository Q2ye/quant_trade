"""
账户管理领域Repository统一导出文件

该模块包含账户管理领域的所有Repository，按照子领域组织：
1. asset/ - 资产与绩效相关
2. settlement/ - 资金与对账相关

所有Repository提供标准的CRUD操作和领域特定的查询方法。
根据表类型选择继承BaseRepository或HyperRepositoryBase。

导出的Repository：

资产与绩效领域:
- AccountRepository - 账户信息表Repository
- AccountDailyPerformanceRepository - 账户每日绩效表Repository（超表）
- StrategyDailyPerformanceRepository - 策略每日绩效表Repository（超表）

资金与对账领域:
- AccountTransactionRepository - 账户流水表Repository
- AccountStatementRepository - 账户对账单表Repository
- CashFlowRepository - 资金流水表Repository
"""

# 资产与绩效领域
from .asset.account_repo import AccountRepository
from .asset.account_performance_repo import AccountDailyPerformanceRepository
from .asset.strategy_daily_performance_repo import StrategyDailyPerformanceRepository

# 资金与对账领域
from .settlement.transaction_repo import AccountTransactionRepository
from .settlement.statement_repo import AccountStatementRepository
from .settlement.cash_flow_repo import CashFlowRepository

__all__ = [
	# 资产与绩效
	"AccountRepository",
	"AccountDailyPerformanceRepository",
	"StrategyDailyPerformanceRepository",

	# 资金与对账
	"AccountTransactionRepository",
	"AccountStatementRepository",
	"CashFlowRepository",
]