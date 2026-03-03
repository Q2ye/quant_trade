"""
quant_server/api/main.py
API网关主入口
"""

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.middleware.trustedhost import TrustedHostMiddleware

from .routers import (
	data_router,
	strategy_router,
	trade_router,
	backtest_router,
	account_router,
	analysis_router,
	monitor_router,
	system_router,
	health_router
)


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

	# 注册路由
	app.include_router(data_router.router, prefix="/api/data", tags=["数据"])
	# app.include_router(strategy_router.router, prefix="/api/strategy", tags=["策略"])
	# app.include_router(trade_router.router, prefix="/api/trade", tags=["交易"])
	# app.include_router(backtest_router.router, prefix="/api/backtest", tags=["回测"])
	# app.include_router(account_router.router, prefix="/api/account", tags=["账户"])
	# app.include_router(analysis_router.router, prefix="/api/analysis", tags=["分析"])
	# app.include_router(monitor_router.router, prefix="/api/monitor", tags=["监控"])
	# app.include_router(system_router.router, prefix="/api/system", tags=["系统"])
	app.include_router(health_router.router, prefix="/health", tags=["健康检查"])

	return app