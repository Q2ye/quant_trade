# main.py
from contextlib import asynccontextmanager
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from fastapi.openapi.docs import get_swagger_ui_html
import uvicorn
import os
import logging
import signal
import sys

from quant_server.data_services import init_services

# 确保正确导入 api_router
try:
    from quant_server.api import api_router
except ImportError:
    # 如果导入失败，尝试相对导入
    from .api import api_router

from quant_server.db.session import init_db, close_db

# 配置日志
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)


# 生命周期管理器
@asynccontextmanager
async def app_lifespan(app: FastAPI):
    # 启动事件
    logger.info("正在启动量化交易平台服务...")

    if not init_db():
        logger.error("数据库初始化失败")
        raise RuntimeError("数据库初始化失败")

    if not init_services():
        logger.error("服务初始化失败")
        raise RuntimeError("服务初始化失败")

    logger.info("服务启动完成")

    yield  # 应用程序运行期间

    # 关闭事件
    logger.info("正在关闭量化交易平台服务...")
    close_db()
    logger.info("服务已关闭")


# 创建 FastAPI 应用实例
fastapi_app = FastAPI(
    title="A股量化交易平台",
    description="基于FastAPI的A股量化交易平台后端API",
    version="1.0.0",
    lifespan=app_lifespan,
    docs_url=None,  # 禁用默认的/docs路由
    redoc_url=None,  # 禁用默认的/redoc路由
)

# 挂载本地静态文件目录
fastapi_app.mount("/static", StaticFiles(directory="static"), name="static")


# 自定义Swagger UI路由
@fastapi_app.get("/docs", include_in_schema=False)
async def custom_swagger_ui_html():
    return get_swagger_ui_html(
        openapi_url="/openapi.json",
        title="A股量化交易平台 - API文档",
        swagger_js_url="/static/swagger/swagger-ui-bundle.js",
        swagger_css_url="/static/swagger/swagger-ui.css",
    )


# 添加CORS中间件
fastapi_app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# 包含API路由
fastapi_app.include_router(api_router)


@fastapi_app.get("/")
async def root():
    return {"message": "A股量化交易平台API服务运行中"}


# 优雅关闭处理
def handle_shutdown(signal, frame):
    logger.info("接收到关闭信号，正在优雅关闭服务...")
    sys.exit(0)


if __name__ == "__main__":
    # 注册信号处理
    signal.signal(signal.SIGINT, handle_shutdown)
    signal.signal(signal.SIGTERM, handle_shutdown)

    # 从环境变量获取端口，默认8000
    port = int(os.getenv("APP_PORT", 8080))
    host = str(os.getenv("APP_HOST", "0.0.0.0"))

    try:
        logger.info(f"启动服务器在 http://{host}:{port}")
        uvicorn.run(
            fastapi_app,
            host=host,
            port=port,
            # 添加更多配置以提高稳定性
            log_config=None,
            access_log=True,
            timeout_keep_alive=60
        )
    except Exception as e:
        logger.error(f"服务器启动失败: {e}")
        sys.exit(1)