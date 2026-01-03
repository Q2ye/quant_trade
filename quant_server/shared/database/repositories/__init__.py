"""
数据库仓库模块统一导出入口

本模块按照领域驱动设计原则，将所有数据访问逻辑封装在Repository中。
Repository提供统一的数据访问接口，屏蔽底层数据库细节，确保业务逻辑与数据访问解耦。

领域划分：
1. market/      - 市场数据领域：股票、行情、财务、公司、ETF、基金、指数等
2. trading/     - 交易领域：订单、成交、持仓、账户、资产、费用等
3. strategy/    - 策略领域：策略、参数、信号、回测、绩效、组合等
4. risk/        - 风控领域：风控规则、风险事件、黑名单、限制规则等
5. reference/   - 参考数据领域：交易日历、股票篮子、ST列表、基础指标等
6. system/      - 系统管理领域：用户、角色、权限、配置、日志、审计、通知等
7. cache/       - 缓存数据领域：缓存管理、分布式锁等

设计原则：
1. 一表一仓库：每个数据库表对应一个Repository类
2. 领域驱动：按照业务领域组织Repository
3. 统一接口：所有Repository继承自RepositoryBase基类
4. 依赖倒置：通过Repository接口访问数据，不直接依赖具体实现
"""

from .base import BaseRepository
from .types import (
	RepositoryResult,
	PaginationParams,
	PaginationResult,
	FilterOperator,
	FilterCondition,
	SortCondition,
	QueryParams,
	DateRange,
	DateTimeRange,
	DatabaseConfig,
	BulkOperationResult,
	UpsertResult,
	CacheStrategy,
	CacheConfig
)
from .utils import (
	get_db_session,
	execute_with_session,
	build_select_query,
	build_count_query,
	build_exists_query,
	build_pagination_query,
	execute_query,
	fetch_one,
	fetch_all,
	fetch_paginated,
	fetch_dict,
	fetch_scalar,
	batch_insert,
	batch_update,
	batch_upsert,
	batch_delete,
	model_to_dict,
	dict_to_model,
	rows_to_dict_list,
	result_to_repository_result,
	ensure_date,
	ensure_datetime,
	QueryCache,
	RepositoryError,
	NotFoundError,
	AlreadyExistsError,
	ValidationError,
	handle_repository_operation
)

# 导出基础类和工具类
__all__ = [
	# 基类
	'BaseRepository',

	# 类型定义
	'RepositoryResult',
	'PaginationParams',
	'PaginationResult',
	'FilterOperator',
	'FilterCondition',
	'SortCondition',
	'QueryParams',
	'DateRange',
	'DateTimeRange',
	'DatabaseConfig',
	'BulkOperationResult',
	'UpsertResult',
	'CacheStrategy',
	'CacheConfig',

	# 工具函数
	'get_db_session',
	'execute_with_session',
	'build_select_query',
	'build_count_query',
	'build_exists_query',
	'build_pagination_query',
	'execute_query',
	'fetch_one',
	'fetch_all',
	'fetch_paginated',
	'fetch_dict',
	'fetch_scalar',
	'batch_insert',
	'batch_update',
	'batch_upsert',
	'batch_delete',
	'model_to_dict',
	'dict_to_model',
	'rows_to_dict_list',
	'result_to_repository_result',
	'ensure_date',
	'ensure_datetime',
	'QueryCache',

	# 异常类
	'RepositoryError',
	'NotFoundError',
	'AlreadyExistsError',
	'ValidationError',
	'handle_repository_operation'
]

# ============================================
# 市场数据领域 (market/)
# ============================================
try:
	from .market import (
		# 股票数据
		StockRepository,
		# 行情数据
		QuoteRepository,
		# 财务数据
		FinancialRepository,
		# 公司信息
		CompanyRepository,
		# ETF数据
		EtfRepository,
		# 基金数据
		FundRepository,
		# 指数数据
		IndexRepository,
		# 数据同步任务
		SyncTaskRepository
	)

	# 导出市场数据领域的所有Repository
	MARKET_REPOSITORIES = {
		'stock_repo': StockRepository,
		'quote_repo': QuoteRepository,
		'financial_repo': FinancialRepository,
		'company_repo': CompanyRepository,
		'etf_repo': EtfRepository,
		'fund_repo': FundRepository,
		'index_repo': IndexRepository,
		'sync_task_repo': SyncTaskRepository
	}

	# 添加到全局导出
	__all__.extend([
		'StockRepository',
		'QuoteRepository',
		'FinancialRepository',
		'CompanyRepository',
		'EtfRepository',
		'FundRepository',
		'IndexRepository',
		'SyncTaskRepository'
	])

except ImportError as e:
	print(f"Warning: Failed to import market repositories: {e}")
	MARKET_REPOSITORIES = {}

# ============================================
# 交易领域 (trading/)
# ============================================
try:
	from .trading import (
		# 交易订单
		TradeRepository,
		# 持仓数据
		PositionRepository,
		# 账户数据
		AccountRepository,
		# 资产数据
		AssetRepository,
		# 费用数据
		FeeRepository
	)

	# 导出交易领域的所有Repository
	TRADING_REPOSITORIES = {
		'trade_repo': TradeRepository,
		'position_repo': PositionRepository,
		'account_repo': AccountRepository,
		'asset_repo': AssetRepository,
		'fee_repo': FeeRepository
	}

	# 添加到全局导出
	__all__.extend([
		'TradeRepository',
		'PositionRepository',
		'AccountRepository',
		'AssetRepository',
		'FeeRepository'
	])

except ImportError as e:
	print(f"Warning: Failed to import trading repositories: {e}")
	TRADING_REPOSITORIES = {}

# ============================================
# 策略领域 (strategy/)
# ============================================
try:
	from .strategy import (
		# 策略数据
		StrategyRepository,
		# 策略参数
		ParameterRepository,
		# 交易信号
		SignalRepository,
		# 回测结果
		BacktestRepository,
		# 绩效数据
		PerformanceRepository,
		# 组合数据
		PortfolioRepository
	)

	# 导出策略领域的所有Repository
	STRATEGY_REPOSITORIES = {
		'strategy_repo': StrategyRepository,
		'parameter_repo': ParameterRepository,
		'signal_repo': SignalRepository,
		'backtest_repo': BacktestRepository,
		'performance_repo': PerformanceRepository,
		'portfolio_repo': PortfolioRepository
	}

	# 添加到全局导出
	__all__.extend([
		'StrategyRepository',
		'ParameterRepository',
		'SignalRepository',
		'BacktestRepository',
		'PerformanceRepository',
		'PortfolioRepository'
	])

except ImportError as e:
	print(f"Warning: Failed to import strategy repositories: {e}")
	STRATEGY_REPOSITORIES = {}

# ============================================
# 风控领域 (risk/)
# ============================================
try:
	from .risk import (
		# 风控规则
		RiskRuleRepository,
		# 风险事件
		RiskEventRepository,
		# 黑名单
		BlacklistRepository,
		# 限制规则
		LimitRepository
	)

	# 导出风控领域的所有Repository
	RISK_REPOSITORIES = {
		'risk_rule_repo': RiskRuleRepository,
		'risk_event_repo': RiskEventRepository,
		'blacklist_repo': BlacklistRepository,
		'limit_repo': LimitRepository
	}

	# 添加到全局导出
	__all__.extend([
		'RiskRuleRepository',
		'RiskEventRepository',
		'BlacklistRepository',
		'LimitRepository'
	])

except ImportError as e:
	print(f"Warning: Failed to import risk repositories: {e}")
	RISK_REPOSITORIES = {}

# ============================================
# 参考数据领域 (reference/)
# ============================================
try:
	from .reference import (
		# 交易日历
		TradeCalendarRepository,
		# 股票篮子
		BasketRepository,
		# ST股票列表
		STListRepository,
		# 每日基本面
		DailyBasicRepository,
		# 涨跌停数据
		DailyLimitRepository,
		# 资金流数据
		MoneyflowRepository,
		# 分红送股
		RewardRepository,
		# 复权价格
		AdjustedPriceRepository
	)

	# 导出参考数据领域的所有Repository
	REFERENCE_REPOSITORIES = {
		'trade_calendar_repo': TradeCalendarRepository,
		'basket_repo': BasketRepository,
		'st_list_repo': STListRepository,
		'daily_basic_repo': DailyBasicRepository,
		'daily_limit_repo': DailyLimitRepository,
		'moneyflow_repo': MoneyflowRepository,
		'reward_repo': RewardRepository,
		'adjusted_price_repo': AdjustedPriceRepository
	}

	# 添加到全局导出
	__all__.extend([
		'TradeCalendarRepository',
		'BasketRepository',
		'STListRepository',
		'DailyBasicRepository',
		'DailyLimitRepository',
		'MoneyflowRepository',
		'RewardRepository',
		'AdjustedPriceRepository'
	])

except ImportError as e:
	print(f"Warning: Failed to import reference repositories: {e}")
	REFERENCE_REPOSITORIES = {}

# ============================================
# 系统管理领域 (system/)
# ============================================
try:
	from .system import (
		# 用户数据
		UserRepository,
		# 角色数据
		RoleRepository,
		# 权限数据
		PermissionRepository,
		# 系统配置
		ConfigRepository,
		# 日志数据
		LogRepository,
		# 审计日志
		AuditRepository,
		# 通知记录
		NotificationRepository
	)

	# 导出系统管理领域的所有Repository
	SYSTEM_REPOSITORIES = {
		'user_repo': UserRepository,
		'role_repo': RoleRepository,
		'permission_repo': PermissionRepository,
		'config_repo': ConfigRepository,
		'log_repo': LogRepository,
		'audit_repo': AuditRepository,
		'notification_repo': NotificationRepository
	}

	# 添加到全局导出
	__all__.extend([
		'UserRepository',
		'RoleRepository',
		'PermissionRepository',
		'ConfigRepository',
		'LogRepository',
		'AuditRepository',
		'NotificationRepository'
	])

except ImportError as e:
	print(f"Warning: Failed to import system repositories: {e}")
	SYSTEM_REPOSITORIES = {}

# ============================================
# 缓存数据领域 (cache/)
# ============================================
try:
	from .cache import (
		# 缓存数据
		CacheRepository,
		# 分布式锁
		DistributedLockRepository
	)

	# 导出缓存数据领域的所有Repository
	CACHE_REPOSITORIES = {
		'cache_repo': CacheRepository,
		'distributed_lock_repo': DistributedLockRepository
	}

	# 添加到全局导出
	__all__.extend([
		'CacheRepository',
		'DistributedLockRepository'
	])

except ImportError as e:
	print(f"Warning: Failed to import cache repositories: {e}")
	CACHE_REPOSITORIES = {}


# ============================================
# Repository工厂函数
# ============================================

class RepositoryFactory:
	"""
	Repository工厂类

	提供统一的方式创建和管理Repository实例，支持依赖注入和生命周期管理
	"""

	def __init__ (self):
		"""初始化Repository工厂"""
		self._repositories = {}
		self._merge_all_repositories()

	def _merge_all_repositories (self):
		"""合并所有领域的Repository"""
		self._repositories.update(MARKET_REPOSITORIES)
		self._repositories.update(TRADING_REPOSITORIES)
		self._repositories.update(STRATEGY_REPOSITORIES)
		self._repositories.update(RISK_REPOSITORIES)
		self._repositories.update(REFERENCE_REPOSITORIES)
		self._repositories.update(SYSTEM_REPOSITORIES)
		self._repositories.update(CACHE_REPOSITORIES)

	def create_repository (self, repo_name: str, session) -> BaseRepository:
		"""
		创建指定名称的Repository实例

		Args:
			repo_name: Repository名称
			session: SQLAlchemy数据库会话

		Returns:
			BaseRepository: Repository实例

		Raises:
			ValueError: 当Repository名称不存在时
		"""
		repo_class = self._repositories.get(repo_name)
		if not repo_class:
			raise ValueError(f"Repository '{repo_name}' not found")

		return repo_class(session)

	def get_available_repositories (self) -> dict:
		"""
		获取所有可用的Repository类

		Returns:
			dict: Repository名称到类的映射
		"""
		return self._repositories.copy()

	def get_repository_by_domain (self, domain: str) -> dict:
		"""
		获取指定领域的Repository

		Args:
			domain: 领域名称（market/trading/strategy/risk/reference/system/cache）

		Returns:
			dict: 领域内所有Repository名称到类的映射
		"""
		domain_mapping = {
			'market': MARKET_REPOSITORIES,
			'trading': TRADING_REPOSITORIES,
			'strategy': STRATEGY_REPOSITORIES,
			'risk': RISK_REPOSITORIES,
			'reference': REFERENCE_REPOSITORIES,
			'system': SYSTEM_REPOSITORIES,
			'cache': CACHE_REPOSITORIES
		}

		return domain_mapping.get(domain, {})


# 创建全局Repository工厂实例
repository_factory = RepositoryFactory()

# 添加到导出列表
__all__.append('repository_factory')
__all__.append('RepositoryFactory')

# ============================================
# 简化的导出方式（按领域分组导出）
# ============================================

# 按领域分组导出类
MarketRepositories = type('MarketRepositories', (), MARKET_REPOSITORIES)
TradingRepositories = type('TradingRepositories', (), TRADING_REPOSITORIES)
StrategyRepositories = type('StrategyRepositories', (), STRATEGY_REPOSITORIES)
RiskRepositories = type('RiskRepositories', (), RISK_REPOSITORIES)
ReferenceRepositories = type('ReferenceRepositories', (), REFERENCE_REPOSITORIES)
SystemRepositories = type('SystemRepositories', (), SYSTEM_REPOSITORIES)
CacheRepositories = type('CacheRepositories', (), CACHE_REPOSITORIES)

# 添加到导出列表
__all__.extend([
	'MarketRepositories',
	'TradingRepositories',
	'StrategyRepositories',
	'RiskRepositories',
	'ReferenceRepositories',
	'SystemRepositories',
	'CacheRepositories'
])


# ============================================
# 模块初始化验证
# ============================================

def _validate_repositories ():
	"""
	验证所有Repository是否正确实现

	检查每个Repository是否都继承自RepositoryBase基类
	"""
	for repo_name, repo_class in repository_factory._repositories.items():
		if not issubclass(repo_class, BaseRepository):
			print(f"Warning: Repository '{repo_name}' does not inherit from BaseRepository")

	print(f"Repository模块初始化完成，共加载 {len(repository_factory._repositories)} 个Repository")


# 模块导入时自动验证
_validate_repositories()

# ============================================
# 模块说明文档
# ============================================
__doc__ = """
数据库仓库模块

使用示例：
---------
1. 直接导入具体的Repository:
   >>> from quant_server.shared.database.repositories import StockRepository
   >>> repo = StockRepository(session)
   >>> stocks = await repo.get_all()

2. 使用Repository工厂:
   >>> from quant_server.shared.database.repositories import repository_factory
   >>> repo = repository_factory.create_repository('stock_repo', session)

3. 按领域批量导入:
   >>> from quant_server.shared.database.repositories import MarketRepositories
   >>> StockRepository = MarketRepositories.stock_repo

4. 使用事务装饰器:
   >>> from quant_server.shared.database.repositories.utils import handle_repository_operation
   >>> result = await handle_repository_operation(repo.update, id=1, data={'name': 'new_name'})

领域划分：
---------
- market:      市场数据相关，如股票、行情、财务数据等
- trading:     交易相关，如订单、持仓、账户等
- strategy:    策略相关，如策略管理、回测、信号等
- risk:        风控相关，如风控规则、风险事件等
- reference:   参考数据相关，如交易日历、股票篮子等
- system:      系统管理相关，如用户、权限、配置等
- cache:       缓存相关，如分布式锁、缓存管理等

设计模式：
---------
1. Repository模式: 封装数据访问逻辑，提供统一的CRUD接口
2. 工厂模式: RepositoryFactory提供统一的创建方式
3. 装饰器模式: 事务管理、缓存等通过装饰器实现
4. 策略模式: 支持多种查询策略和过滤条件
"""