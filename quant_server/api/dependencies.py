from typing import Any, Generator

from fastapi import Depends
from sqlalchemy.orm import Session

from quant_server.db.data_service import DataService
from quant_server.db.session import get_db_session

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