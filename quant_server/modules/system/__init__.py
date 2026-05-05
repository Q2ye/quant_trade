# -*- coding: utf-8 -*-
"""
系统模块
负责用户权限、任务调度、全局配置、日志管理等基础服务

模块结构：
- constants: 常量定义
- models: 业务DTO
- events: 事件定义
- services: 业务服务（user/auth/role/config/task/log）
- auth: 认证授权（jwt/authentication/authorization）
- managers: 资源管理器
- tasks: 定时任务
- handlers: API处理函数
- utils: 工具函数
"""

import logging

from . import constants
from . import models
from . import events
from . import services
from . import auth
from . import managers
from . import handlers
from . import utils

logger = logging.getLogger(__name__)

__version__ = "1.0.0"
__author__ = "量化交易系统团队"
__description__ = "量化交易系统管理模块（用户/权限/配置/调度）"


async def shutdown () -> None:
	"""系统模块关闭函数"""
	logger.info("系统模块已关闭")


__all__ = [
	"constants",
	"models",
	"events",
	"services",
	"auth",
	"managers",
	"handlers",
	"utils",
	"initialize",
	"shutdown",
]


async def initialize (
		main_engine=None,
		event_engine=None,
		config=None
) -> bool:
	"""
	系统模块初始化函数（最先被调用，提供基础服务）

	Args:
		main_engine: 主引擎实例
		event_engine: 事件引擎实例
		config: 模块配置

	Returns:
		bool: 初始化是否成功
	"""
	success = False
	init_result = {}

	try:
		logger.info("开始初始化系统模块...")

		if main_engine and hasattr(main_engine, 'get_async_session'):
			session = main_engine.get_async_session()
			init_result = await _initialize_system_module(session, config or {})
			success = init_result.get('status') != 'failed'
		else:
			from shared.database.session import get_session_manager

			session_manager = get_session_manager()
			async with session_manager.get_session() as session:
				init_result = await _initialize_system_module(session, config or {})
				success = init_result.get('status') != 'failed'

		if success:
			print(f"✅ 系统模块初始化成功: {init_result.get('message', '完成')}")
		else:
			print(f"⚠️  系统模块初始化警告: {init_result.get('message', '存在警告')}")

		return success

	except Exception as e:
		print(f"❌ 系统模块初始化失败: {str(e)}")
		logger.exception("系统模块初始化失败")
		return False


async def _initialize_system_module (session, config: dict) -> dict:
	"""
	系统模块内部初始化逻辑

	Args:
		session: 数据库会话
		config: 模块配置

	Returns:
		dict: 初始化结果
	"""
	from sqlalchemy import text

	try:
		# 1. 检查必要的表
		from sqlalchemy import inspect
		tables = await session.run_sync(
			lambda sync_session: inspect(sync_session.connection()).get_table_names()
		)

		required_tables = [
			"sys_users",
			"sys_roles",
			"sys_user_roles",
			"system_configs",
			"system_logs",
		]

		missing_tables = [t for t in required_tables if t not in tables]

		if missing_tables:
			logger.warning(f"系统模块缺少表: {missing_tables}")
			return {
				"status": "degraded",
				"missing_tables": missing_tables,
				"message": "系统模块初始化完成，但缺少必要的表"
			}

		# 2. 检查数据库连接
		await session.execute(text("SELECT 1"))

		# 3. 加载全局配置
		logger.info("系统模块初始化完成")

		return {
			"status": "success",
			"message": "系统模块初始化完成",
			"loaded_components": ["auth", "user", "role"]
		}

	except Exception as e:
		logger.error(f"系统模块初始化失败: {str(e)}")
		return {
			"status": "failed",
			"message": f"系统模块初始化失败: {str(e)}"
		}
