# quant_server/api/dependencies.py
from fastapi import Depends, HTTPException
from sqlalchemy.orm import Session

from quant_server.db.session import get_db
from quant_server.services.data_service import DataService

def get_data_service(db: Session = Depends(get_db)) -> DataService:
    """获取数据服务依赖项"""
    return DataService(db)