# main.py
from contextlib import asynccontextmanager
from fastapi import FastAPI, Request, Depends
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from fastapi.openapi.docs import get_swagger_ui_html

from quant_server.core.strategy_engine.main_engine import MainEngine
from quant_server.api import api_router
from quant_server.db.session import init_db, close_db

import uvicorn
import os
import logging
import signal
import sys
import asyncio
from datetime import datetime

# 配置日志
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)


class QuantServer:
    """量化交易平台主服务器类"""

    def __init__(self):
        self.app = None
        self.main_engine = None
        self._setup_signal_handlers()

    def _setup_signal_handlers(self):
        """设置信号处理"""
        signal.signal(signal.SIGINT, self._handle_shutdown)
        signal.signal(signal.SIGTERM, self._handle_shutdown)

    def _handle_shutdown(self, signum, frame):
        """处理关闭信号"""
        logger.info("接收到关闭信号，正在优雅关闭服务...")
        if self.main_engine:
            asyncio.create_task(self.main_engine.shutdown())
        sys.exit(0)

    @asynccontextmanager
    async def app_lifespan(self, app: FastAPI):
        """应用生命周期管理"""
        # 启动事件
        logger.info("正在启动量化交易平台服务...")

        # 初始化数据库
        if not init_db():
            logger.error("数据库初始化失败")
            raise RuntimeError("数据库初始化失败")

        # 初始化主引擎
        try:
            self.main_engine = MainEngine()
            await self.main_engine.initialize()
            app.state.main_engine = self.main_engine
            logger.info("主引擎初始化成功")
        except Exception as e:
            logger.error(f"主引擎初始化失败: {str(e)}")
            raise RuntimeError(f"主引擎初始化失败: {str(e)}")

        logger.info("服务启动完成")

        yield  # 应用程序运行期间

        # 关闭事件
        logger.info("正在关闭量化交易平台服务...")

        # 关闭主引擎
        if self.main_engine:
            await self.main_engine.shutdown()

        # 关闭数据库
        close_db()
        logger.info("服务已关闭")

    def create_app(self) -> FastAPI:
        """创建FastAPI应用实例"""
        # 创建FastAPI应用
        app = FastAPI(
            title="A股量化交易平台",
            description="基于FastAPI的A股量化交易平台后端API",
            version="1.0.0",
            lifespan=self.app_lifespan,
            docs_url=None,  # 禁用默认的/docs路由
            redoc_url=None,  # 禁用默认的/redoc路由
        )

        # 挂载本地静态文件目录
        app.mount("/static", StaticFiles(directory="static"), name="static")

        # 添加CORS中间件
        app.add_middleware(
            CORSMiddleware,
            allow_origins=["*"],
            allow_credentials=True,
            allow_methods=["*"],
            allow_headers=["*"],
        )

        # 包含API路由
        app.include_router(api_router)

        # 主引擎依赖项
        async def get_main_engine(request: Request) -> MainEngine:
            return request.app.state.main_engine

        # 根路由
        @app.get("/")
        async def root():
            return {"message": "A股量化交易平台API服务运行中", "timestamp": datetime.now().isoformat()}

        # 健康检查端点
        @app.get("/health")
        async def health_check(main_engine: MainEngine = Depends(get_main_engine)):
            return {
                "status": "healthy",
                "timestamp": datetime.now().isoformat(),
                "engines": list(main_engine.engines.keys()),
                "strategies": list(main_engine.strategies.keys())
            }

        # 自定义Swagger UI路由
        @app.get("/docs", include_in_schema=False)
        async def custom_swagger_ui_html():
            return get_swagger_ui_html(
                openapi_url="/openapi.json",
                title="A股量化交易平台 - API文档",
                swagger_js_url="/static/swagger/swagger-ui-bundle.js",
                swagger_css_url="/static/swagger/swagger-ui.css",
            )

        self.app = app
        return app

    def run(self, host: str = "0.0.0.0", port: int = 8080):
        """运行服务器"""
        app_instance = self.create_app()

        try:
            logger.info(f"启动服务器在 https://{host}:{port}")
            uvicorn.run(
                app_instance,
                host=host,
                port=port,
                log_config=None,
                access_log=True,
                timeout_keep_alive=60
            )
        except Exception as e:
            logger.error(f"服务器启动失败: {e}")
            sys.exit(1)


def main():
    """主函数"""
    # 从环境变量获取配置
    host = str(os.getenv("APP_HOST", "0.0.0.0"))
    port = int(os.getenv("APP_PORT", 8080))

    # 创建并运行服务器
    server = QuantServer()
    server.run(host=host, port=port)


if __name__ == "__main__":
    main()