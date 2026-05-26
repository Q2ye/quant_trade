"""
quant_server/api/main.py
API网关主入口
"""

import logging
from typing import Dict, Any

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.middleware.trustedhost import TrustedHostMiddleware
from fastapi.openapi.utils import get_openapi

from .routers import (
    data_router, strategy_router, trade_router, backtest_router,
    account_router, analysis_router, monitor_router, system_router, health_router,
)
from .websocket import websocket_router
logger = logging.getLogger(__name__)


def create_app (
		title: str = "一念量化",
		version: str = "1.0.0",
		description: str = "基于混合架构的一念量化API",
		docs_url: str = "/docs",
		redoc_url: str = "/redoc",
		openapi_url: str = "/openapi.json",
		enabled_modules: list = None,
	cors_origins: list = None,
) -> FastAPI:
	"""创建FastAPI应用

	Args:
		title: API标题
		version: API版本
		description: API描述
		docs_url: Swagger文档URL
		redoc_url: ReDoc文档URL
		openapi_url: OpenAPI规范URL
		enabled_modules: 启用的模块列表，None表示全部启用
		cors_origins: CORS允许源列表，None使用默认值

	Returns:
		FastAPI: 应用实例
	"""
	# 如果未指定，默认全部启用
	if enabled_modules is None:
		enabled_modules = ["data", "strategy", "trade", "backtest", "account", "analysis", "monitor", "system"]
	if cors_origins is None:
		cors_origins = ["http://localhost:3000", "http://localhost:5173"]
	# 创建FastAPI应用
	app = FastAPI(
		title=title,
		version=version,
		description=description,
		docs_url=docs_url,
		redoc_url=redoc_url,
		openapi_url=openapi_url
	)

	# 自定义OpenAPI配置
	def custom_openapi () -> Dict[str, Any]:
		if app.openapi_schema:
			return app.openapi_schema

		openapi_schema = get_openapi(
			title=title,
			version=version,
			description=description,
			routes=app.routes,
		)

		# 安全方案配置
		openapi_schema.setdefault("components", {}).update({
			"securitySchemes": {
				"BearerAuth": {
					"type": "http",
					"scheme": "bearer",
					"bearerFormat": "JWT"
				}
			}
		})

		# 为所有路径添加安全要求
		for path_item in openapi_schema["paths"].values():
			for operation in path_item.values():
				operation.setdefault("security", [{"BearerAuth": []}])

		# 隐藏分页和排序参数（page, page_size, sort_by, sort_order）
		params_to_hide = ["page", "page_size", "sort_by", "sort_order"]
		for path, path_item in openapi_schema["paths"].items():
			for method, operation in path_item.items():
				if "parameters" in operation:
					# 过滤掉分页和排序参数
					operation["parameters"] = [
						param for param in operation["parameters"]
						if param.get("name") not in params_to_hide
					]

		# 清理可能为空的参数列表
		for path, path_item in openapi_schema["paths"].items():
			for method, operation in path_item.items():
				if "parameters" in operation and not operation["parameters"]:
					del operation["parameters"]

		app.openapi_schema = openapi_schema
		return app.openapi_schema

	app.openapi = custom_openapi

	# 添加中间件
	app.add_middleware(
		CORSMiddleware,
		allow_origins=cors_origins,
		allow_credentials=True,
		allow_methods=["*"],
		allow_headers=["*"],
	)

	app.add_middleware(
		TrustedHostMiddleware,
		allowed_hosts=["*"]  # 生产环境应该限制
	)

	# 添加异常处理器
	from api.handlers.exception_handlers import setup_exception_handlers
	setup_exception_handlers(app)

	# API层数据库依赖初始化
	async def startup_db():
		from api.dependencies.database import initialize_api_database

		# 初始化API层数据库依赖（包含共享层数据库的初始化）
		if not await initialize_api_database():
			logger.error("API层数据库依赖初始化失败，部分功能可能不可用")
		else:
			logger.info("API层数据库依赖初始化成功")

	# 使用 lifespan 事件处理器
	from contextlib import asynccontextmanager

	@asynccontextmanager
	async def lifespan(_app: FastAPI):
		# 启动时
		await startup_db()
		yield
		# 关闭时
		pass

	app.lifespan = lifespan

	# 注册路由（仅注册已启用的模块路由）
	_module_routers = {
		"data": (data_router, "/quantTrade/data"),
		"strategy": (strategy_router, "/quantTrade/strategy"),
		"trade": (trade_router, "/quantTrade/trade"),
		"backtest": (backtest_router, "/quantTrade/backtest"),
		"account": (account_router, "/quantTrade/account"),
		"analysis": (analysis_router, "/quantTrade/analysis"),
		"monitor": (monitor_router, "/quantTrade/monitor"),
		"system": (system_router, "/quantTrade/system"),
	}
	for module_name, (router, prefix) in _module_routers.items():
		if module_name in enabled_modules:
			app.include_router(router, prefix=prefix)
	# health 路由始终注册
	app.include_router(health_router, prefix="/health")
	# WebSocket 路由始终注册
	app.include_router(websocket_router, prefix="/api")

	return app