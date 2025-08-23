# main.py
from contextlib import asynccontextmanager
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
import uvicorn
import os
import logging

from quant_server.api import api_router
from quant_server.db.session import init_db, close_db
from quant_server.config_loader import load_config, get_db_config

# 配置日志
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

# 生命周期管理器
@asynccontextmanager
async def app_lifespan(_app: FastAPI):  # 重命名参数以避免隐藏外部作用域
    # 启动事件
    logger.info("正在启动量化交易平台服务...")

    # 加载配置文件
    config = load_config('quant_server/config/main.yaml')
    db_config = get_db_config(config)

    if not init_db(db_config):
        logger.error("数据库初始化失败")
        raise RuntimeError("数据库初始化失败")

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
    lifespan=app_lifespan
)

# 添加CORS中间件 - 使用正确的类型
fastapi_app.add_middleware(
    CORSMiddleware,  # 这是正确的用法，FastAPI 期望接收类而不是实例
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

@fastapi_app.get("/health")
async def health_check():
    return {"status": "healthy"}

if __name__ == "__main__":
    # 从环境变量获取端口，默认8000
    port = int(os.getenv("PORT", 8000))
    uvicorn.run(fastapi_app, host="0.0.0.0", port=port)