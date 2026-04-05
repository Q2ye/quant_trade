# quant_server/api/dependencies/__init__.py
"""
API依赖注入模块

统一导出所有依赖注入功能，为FastAPI应用提供完整的依赖注入支持。
基于设计文档的混合架构设计，确保依赖方向正确、职责明确。

Author: 量化交易系统团队
Version: 1.0.0
"""
from typing import Dict

# 从各子模块导入依赖函数和类型
from .auth import (
	# 认证依赖
	get_current_user,
	require_permission,
	require_superuser,
	optional_auth,
	# 类型注解
	CurrentUser,
	PermissionRequired,
	SuperuserRequired,
	OptionalAuth,
)


from .database import (
	# 数据库依赖
	get_db_session,
	get_readonly_session,
	get_transaction_session,
	get_database_health,
	# 类型注解
	DBSessionDep,
	ReadonlySessionDep,
	TransactionSessionDep,
	# 会话工厂
	create_session,
	# 事务装饰器
	with_transaction,
	# 初始化和关闭
	initialize_database,
	close_database,
	# 兼容性导出
	SharedDBSessionDep,
)

from .event_engine import (
	# 事件引擎依赖
	get_event_engine,
	publish_event,
	publish_system_event,
	subscribe,
	unsubscribe,
	wait_for_event,
	get_event_stats,
	# 类型注解
	EventEngineDep,
	# 事件优先级枚举
	EventPriority,
	# 上下文管理器
	event_context,
	# 初始化和关闭
	initialize_event_engine,
	close_event_engine,
)

from .main_engine import (
	# 主引擎依赖
	get_main_engine,
	get_engine,
	start_engine,
	stop_engine,
	restart_engine,
	get_engine_status,
	get_all_engines_status,
	get_system_status,
	change_system_mode,
	execute_system_command,
	# 类型注解
	MainEngineDep,
	# 系统模式枚举
	SystemMode,
	# 上下文管理器
	engine_context,
	# 引擎依赖快捷方式
	require_engine,
	get_data_engine,
	get_strategy_engine,
	get_trade_engine,
	get_backtest_engine,
	# 常用引擎依赖类型注解
	DataEngineDep,
	StrategyEngineDep,
	TradeEngineDep,
	BacktestEngineDep,
	# 初始化和关闭
	initialize_main_engine,
	close_main_engine,
)
from ...shared.config.config_manager import get_config


# 依赖管理器（协调所有依赖的初始化和关闭）
class DependencyManager:
	"""依赖管理器"""

	@staticmethod
	async def initialize_all () -> Dict[str, bool]:
		"""
		初始化所有依赖

		Returns:
			Dict[str, bool]: 各依赖初始化结果
		"""
		results = {}

		# 初始化数据库依赖
		try:
			results["database"] = await initialize_database()
		except Exception as e:
			import logging
			logging.error(f"数据库依赖初始化失败: {e}")
			results["database"] = False

		# 初始化事件引擎依赖
		try:
			results["event_engine"] = await initialize_event_engine()
		except Exception as e:
			import logging
			logging.error(f"事件引擎依赖初始化失败: {e}")
			results["event_engine"] = False

		# 初始化主引擎依赖
		try:
			results["main_engine"] = await initialize_main_engine()
		except Exception as e:
			import logging
			logging.error(f"主引擎依赖初始化失败: {e}")
			results["main_engine"] = False

		# 检查整体初始化状态
		all_success = all(results.values())
		import logging
		if all_success:
			logging.info("所有依赖初始化成功")
		else:
			failed_deps = [name for name, success in results.items() if not success]
			logging.error(f"部分依赖初始化失败: {failed_deps}")

		return results

	@staticmethod
	async def close_all ():
		"""关闭所有依赖"""
		import logging

		try:
			await close_main_engine()
			logging.info("主引擎依赖已关闭")
		except Exception as e:
			logging.error(f"关闭主引擎依赖失败: {e}")

		try:
			await close_event_engine()
			logging.info("事件引擎依赖已关闭")
		except Exception as e:
			logging.error(f"关闭事件引擎依赖失败: {e}")

		try:
			await close_database()
			logging.info("数据库依赖已关闭")
		except Exception as e:
			logging.error(f"关闭数据库依赖失败: {e}")

		logging.info("所有依赖已关闭")


# 导出依赖管理器
__all__ = [
	# 认证依赖
	"get_current_user",
	"require_permission",
	"require_superuser",
	"optional_auth",
	"CurrentUser",
	"PermissionRequired",
	"SuperuserRequired",
	"OptionalAuth",

	# 配置依赖
	"get_config",

	# 数据库依赖
	"get_db_session",
	"get_readonly_session",
	"get_transaction_session",
	"get_database_health",
	"DBSessionDep",
	"ReadonlySessionDep",
	"TransactionSessionDep",
	"create_session",
	"with_transaction",
	"initialize_database",
	"close_database",
	"SharedDBSessionDep",

	# 事件引擎依赖
	"get_event_engine",
	"publish_event",
	"publish_system_event",
	"subscribe",
	"unsubscribe",
	"wait_for_event",
	"get_event_stats",
	"EventEngineDep",
	"EventPriority",
	"event_context",
	"initialize_event_engine",
	"close_event_engine",

	# 主引擎依赖
	"get_main_engine",
	"get_engine",
	"start_engine",
	"stop_engine",
	"restart_engine",
	"get_engine_status",
	"get_all_engines_status",
	"get_system_status",
	"change_system_mode",
	"execute_system_command",
	"MainEngineDep",
	"SystemMode",
	"engine_context",
	"require_engine",
	"get_data_engine",
	"get_strategy_engine",
	"get_trade_engine",
	"get_backtest_engine",
	"DataEngineDep",
	"StrategyEngineDep",
	"TradeEngineDep",
	"BacktestEngineDep",
	"initialize_main_engine",
	"close_main_engine",

	# 依赖管理器
	"DependencyManager",
]

# 模块元数据
__version__ = "1.0.0"
__author__ = "量化交易系统团队"
__description__ = "FastAPI依赖注入模块，提供认证、配置、数据库、事件引擎、主引擎等依赖"
__license__ = "MIT"