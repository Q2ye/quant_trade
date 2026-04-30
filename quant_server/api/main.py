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

from .routers import data_router, strategy_router, health_router, backtest_router, trade_router, monitor_router
logger = logging.getLogger(__name__)


def create_app (
		title: str = "量化交易平台",
		version: str = "1.0.0",
		description: str = "基于混合架构的量化交易平台API",
		docs_url: str = "/docs",
		redoc_url: str = "/redoc",
		openapi_url: str = "/openapi.json"
) -> FastAPI:
	"""创建FastAPI应用

	Args:
		title: API标题
		version: API版本
		description: API描述
		docs_url: Swagger文档URL
		redoc_url: ReDoc文档URL
		openapi_url: OpenAPI规范URL

	Returns:
		FastAPI: 应用实例
	"""
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

		# 简化安全方案配置
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
		allow_origins=["*"],  # 生产环境应该限制
		allow_credentials=True,
		allow_methods=["*"],
		allow_headers=["*"],
	)

	app.add_middleware(
		TrustedHostMiddleware,
		allowed_hosts=["*"]  # 生产环境应该限制
	)

	# 添加异常处理器
	from quant_server.api.handlers.exception_handlers import setup_exception_handlers
	setup_exception_handlers(app)

	# API层数据库依赖初始化
	async def startup_db():
		from quant_server.api.dependencies.database import initialize_api_database

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

	# 注册路由
	app.include_router(data_router, prefix="/api/data")
	app.include_router(strategy_router, prefix="/api/strategy")
	app.include_router(trade_router, prefix="/api/trade")
	app.include_router(backtest_router, prefix="/api/backtest")
	# app.include_router(account_router, prefix="/api/account")
	# app.include_router(analysis_router, prefix="/api/analysis")
	app.include_router(monitor_router, prefix="/api/monitor")
	# app.include_router(system_router, prefix="/api/system")
	app.include_router(health_router, prefix="/health")

	return app