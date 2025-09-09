from typing import Any, Generator

from fastapi import Depends
from sqlalchemy.orm import Session

from quant_server.core.strategy_engine.main_engine import MainEngine
from quant_server.db.data_service import DataService
from quant_server.db.session import get_db_session

# 全局主引擎实例
_main_engine = None

# 创建一个符合 FastAPI 依赖注入模式的数据库会话获取函数
def get_db() -> Generator[Session, Any, None]:
    """获取数据库会话的依赖函数"""
    db = get_db_session()
    try:
        yield db
    finally:
        db.close()

def get_data_service(db: Session = Depends(get_db)) -> DataService:
    """获取数据服务依赖项"""
    return DataService(db)

async def get_main_engine() -> MainEngine:
    """获取主引擎实例"""
    global _main_engine

    if _main_engine is None:
        _main_engine = MainEngine()
        await _main_engine.initialize()

    return _main_engine

async def get_strategy_manager_engine(main_engine: MainEngine = Depends(get_main_engine)):
    """获取策略管理引擎实例"""
    return main_engine.get_engine("strategy_manager")

async def shutdown_main_engine():
    """关闭主引擎"""
    global _main_engine

    if _main_engine is not None:
        await _main_engine.shutdown()
        _main_engine = None