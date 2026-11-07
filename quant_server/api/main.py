"""
quant_server/api/main.py
API网关主入口
"""

import logging
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, Optional

from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.middleware.trustedhost import TrustedHostMiddleware
from fastapi.openapi.utils import get_openapi
from fastapi.responses import FileResponse

from .middleware.timing import timing_middleware
from .routers import (
    data_router, strategy_router, trade_router, basket_router, backtest_router,
    account_router, analysis_router, monitor_router, system_router, risk_router,
    health_router, market_router, composite_router,
)
from .routers.signal_router import router as signal_router
from .websocket import websocket_router
logger = logging.getLogger(__name__)


def _mount_frontend(app: FastAPI, frontend_dir: Optional[str] = None) -> None:
    """托管前端构建产物（单端口部署），并为 history 路由提供 SPA fallback。"""
    dist = Path(frontend_dir) if frontend_dir else (
        Path(__file__).resolve().parents[2] / "quant_web" / "dist"
    )
    root = dist.resolve()
    index_file = root / "index.html"
    if not index_file.is_file():
        logger.warning(
            "已启用前端托管，但未找到构建产物：%s（请先在 quant_web 下执行 pnpm build）",
            index_file,
        )
        return

    reserved = {"quantTrade", "api", "health", "docs", "redoc", "openapi.json"}

    @app.get("/{full_path:path}", include_in_schema=False)
    async def frontend_spa(full_path: str):
        # API/文档命名空间不吞成 index.html，保持 404 语义
        if full_path.split("/", 1)[0] in reserved:
            raise HTTPException(status_code=404, detail="Not Found")
        candidate = (root / full_path).resolve()
        if root in candidate.parents and candidate.is_file():
            return FileResponse(candidate)
        return FileResponse(index_file)


def create_app(
    title: str = "一念量化",
    version: str = "1.0.0",
    description: str = "基于混合架构的一念量化API",
    docs_url: str = "/docs",
    redoc_url: str = "/redoc",
    openapi_url: str = "/openapi.json",
    enabled_modules: list = None,
    cors_origins: list = None,
    serve_frontend: bool = False,
    frontend_dir: Optional[str] = None,
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
        serve_frontend: 是否托管 quant_web/dist（生产单端口部署）
        frontend_dir: 前端构建目录，None 时使用 <repo>/quant_web/dist

    Returns:
        FastAPI: 应用实例
    """
    # 如果未指定，默认全部启用
    if enabled_modules is None:
        enabled_modules = [
            "data", "strategy", "trade", "basket", "backtest", "account",
            "analysis", "monitor", "system", "risk", "market",
        ]
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
    def custom_openapi() -> Dict[str, Any]:
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

    # 请求计时中间件
    app.middleware("http")(timing_middleware)

    from api.handlers.exception_handlers import setup_exception_handlers
    setup_exception_handlers(app)

    # API层数据库依赖初始化
    async def startup_db():
        from api.dependencies.database import initialize_api_database
        if not await initialize_api_database():
            logger.error("API层数据库依赖初始化失败，部分功能可能不可用")
            return
        logger.info("API层数据库依赖初始化成功")

    from contextlib import asynccontextmanager

    @asynccontextmanager
    async def lifespan(_app: FastAPI):
        await startup_db()
        yield

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
        "risk": (risk_router, "/quantTrade/risk"),
        "market": (market_router, "/quantTrade/market"),
    }
    for module_name, (router, prefix) in _module_routers.items():
        if module_name in enabled_modules:
            app.include_router(router, prefix=prefix)
    # 始终注册的路由（不依赖模块初始化）
    app.include_router(health_router, prefix="/health")
    app.include_router(basket_router, prefix="/quantTrade/basket")
    app.include_router(composite_router, prefix="/quantTrade")
    # WebSocket 路由始终注册
    app.include_router(websocket_router, prefix="/api")
    # 信号确认路由（自带 /quantTrade/signals 前缀）
    app.include_router(signal_router)

    # 前端静态资源托管（生产单端口部署；必须最后注册，避免吞掉 API 路由）
    if serve_frontend:
        _mount_frontend(app, frontend_dir)

    return app
