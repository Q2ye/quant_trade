# main.py
import types
from contextlib import asynccontextmanager

from fastapi import FastAPI, Request, Depends, WebSocket, WebSocketDisconnect
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from fastapi.openapi.docs import get_swagger_ui_html

from quant_server.api import router
from quant_server.core.strategy_engine.main_engine import MainEngine
from quant_server.db.session import init_db, close_db

import uvicorn
import os
import logging
import signal
import sys
import asyncio
from datetime import datetime
import json

# 配置日志
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)


class ConnectionManager:
    """WebSocket 连接管理器"""

    def __init__(self):
        self.active_connections: list[WebSocket] = []

    async def connect(self, websocket: WebSocket):
        await websocket.accept()
        self.active_connections.append(websocket)
        logger.info(f"WebSocket 连接已建立，当前连接数: {len(self.active_connections)}")

    def disconnect(self, websocket: WebSocket):
        if websocket in self.active_connections:
            self.active_connections.remove(websocket)
        logger.info(f"WebSocket 连接已断开，当前连接数: {len(self.active_connections)}")

    async def send_personal_message(self, message: str, websocket: WebSocket):
        await websocket.send_text(message)

    async def broadcast(self, message: str):
        disconnected = []
        for connection in self.active_connections:
            try:
                await connection.send_text(message)
            except Exception as e:
                logger.warning(f"发送消息到 WebSocket 失败: {e}")
                disconnected.append(connection)

        # 清理断开的连接
        for connection in disconnected:
            self.disconnect(connection)


class QuantServer:
    """量化交易平台主服务器类"""

    def __init__(self):
        self.app = None
        self.main_engine = None
        self.connection_manager = ConnectionManager()
        self._setup_signal_handlers()

    def _setup_signal_handlers(self):
        """设置信号处理"""
        signal.signal(signal.SIGINT, self._handle_shutdown)
        signal.signal(signal.SIGTERM, self._handle_shutdown)

    def _handle_shutdown(self, signum: int, frame: types.FrameType = None):
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

        # 启动模拟信号生成任务（仅用于测试）
        asyncio.create_task(self._simulate_signals())

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

    async def _simulate_signals(self):
        """模拟交易信号生成（用于测试）"""
        import random
        symbols = ["000001.SZ", "600000.SH", "000858.SZ", "600519.SH", "000333.SZ"]
        signal_types = ["buy", "sell", "hold"]

        while True:
            try:
                # 每5-15秒生成一个随机信号
                await asyncio.sleep(random.randint(5, 15))

                if not self.connection_manager.active_connections:
                    continue

                signal_data = {
                    "signal_type": random.choice(signal_types),
                    "ts_code": random.choice(symbols),
                    "symbol": random.choice(symbols),
                    "strategy_id": f"strategy_{random.randint(1, 5)}",
                    "signal_time": datetime.now().isoformat(),
                    "current_price": round(random.uniform(10, 100), 2),
                    "strength": round(random.uniform(0.1, 0.99), 2),
                    "reason": random.choice([
                        "技术指标突破",
                        "基本面改善",
                        "市场情绪变化",
                        "资金流入",
                        "风险控制触发"
                    ])
                }

                await self.connection_manager.broadcast(json.dumps(signal_data))
                logger.debug(f"广播交易信号: {signal_data}")

            except Exception as e:
                logger.error(f"模拟信号生成错误: {e}")
                await asyncio.sleep(5)

    def create_app(self) -> FastAPI:
        """创建FastAPI应用实例"""
        # 创建FastAPI应用
        app = FastAPI(
            title="A股量化交易平台",
            description="基于FastAPI的量化交易平台后端API",
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
            allow_origins=["*"],  # 在生产环境中应该限制为具体域名
            allow_credentials=True,
            allow_methods=["*"],
            allow_headers=["*"],
        )

        # 包含API路由
        app.include_router(router)

        # WebSocket 路由
        @app.websocket("/api/ws/signals")
        async def websocket_endpoint(websocket: WebSocket):
            await self.connection_manager.connect(websocket)
            try:
                while True:
                    # 保持连接，可以接收客户端消息（如果需要）
                    data = await websocket.receive_text()
                    # 可以处理客户端发送的消息
                    logger.debug(f"收到客户端消息: {data}")
            except WebSocketDisconnect:
                self.connection_manager.disconnect(websocket)
            except Exception as e:
                logger.error(f"WebSocket 错误: {e}")
                self.connection_manager.disconnect(websocket)

        # 主引擎依赖项
        async def get_main_engine(request: Request) -> MainEngine:
            return request.app.state.main_engine

        # 根路由
        @app.get("/")
        async def root():
            return {"message": "量化交易平台API服务运行中", "timestamp": datetime.now().isoformat()}

        # 健康检查端点
        @app.get("/health")
        async def health_check(main_engine: MainEngine = Depends(get_main_engine)):
            return {
                "status": "healthy",
                "timestamp": datetime.now().isoformat(),
                "websocket_connections": len(self.connection_manager.active_connections),
                "engines": list(main_engine.engines.keys()) if main_engine else [],
                "strategies": list(
                    main_engine.get_engine("strategy_manager").strategies.keys()) if main_engine and hasattr(
                    main_engine, 'get_engine') else []
            }

        # WebSocket 连接信息端点
        @app.get("/api/ws/info")
        async def websocket_info():
            return {
                "active_connections": len(self.connection_manager.active_connections),
                "websocket_url": "ws://localhost:8000/api/ws/signals"
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

    def run(self, host: str = "0.0.0.0", port: int = 8000):  # 默认端口改为8000
        """运行服务器"""
        app_instance = self.create_app()

        try:
            logger.info(f"启动服务器在 http://{host}:{port}")
            logger.info(f"WebSocket 服务在 ws://{host}:{port}/api/ws/signals")
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
    port = int(os.getenv("APP_PORT", 8000))  # 默认端口改为8000

    # 创建并运行服务器
    server = QuantServer()
    server.run(host=host, port=port)


if __name__ == "__main__":
    main()