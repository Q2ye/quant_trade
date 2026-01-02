# api/routers/system_router.py      # 系统模块路由
from datetime import datetime
from fastapi import APIRouter, Depends, Query, Body
from typing import Optional

from quant_server.api.dependencies import get_data_service
from quant_server.db.data_service import DataService

router = APIRouter(prefix="/events", tags=["events"])


@router.get("/status")
async def get_system_status(data_service: DataService = Depends(get_data_service)):
    """获取系统状态"""
    # 使用SystemService获取实际状态
    connections = data_service.system_service.get_connection_status()
    resources = data_service.system_service.get_system_resources()
    database_status = data_service.system_service.get_database_status()

    return {
        "status": "running",
        "connections": connections,
        "resources": resources,
        "database": database_status,
        "last_data_sync": "2023-08-23T08:00:00",
        "uptime": "5 days, 12 hours"
    }


@router.get("/logs")
async def get_system_logs(
        level: Optional[str] = Query(None),
        page: int = Query(1, ge=1),
        limit: int = Query(20, ge=1, le=100),
        data_service: DataService = Depends(get_data_service)
):
    """获取系统日志"""
    offset = (page - 1) * limit
    logs_data = data_service.system_service.get_system_logs(level=level, offset=offset, limit=limit)

    return {
        "events": logs_data["events"],
        "pagination": {
            "page": page,
            "limit": limit,
            "total": logs_data["pagination"]["total"],
            "pages": logs_data["pagination"]["pages"]
        }
    }


@router.post("/data/sync")
async def trigger_data_sync(
        sync_params: dict = Body(...),
):
    """触发数据同步"""
    # 这里需要实现数据同步逻辑
    # 暂时返回模拟数据
    return {
        "sync_id": f"sync_{datetime.now().timestamp()}",
        "status": "started",
        "params": sync_params
    }


@router.get("/data/status")
async def get_data_sync_status(data_service: DataService = Depends(get_data_service)):
    """获取数据同步状态"""
    return data_service.system_service.get_data_sync_status()


@router.get("/settings")
async def get_system_settings(data_service: DataService = Depends(get_data_service)):
    """获取系统设置"""
    return data_service.system_service.get_system_settings()


@router.put("/settings")
async def update_system_settings(
        settings: dict = Body(...),
        data_service: DataService = Depends(get_data_service)
):
    """更新系统设置"""
    success = data_service.system_service.update_system_settings(settings)
    return {"updated": success, "settings": settings}


@router.get("/connections")
async def get_connections(data_service: DataService = Depends(get_data_service)):
    """获取系统连接状态"""
    return data_service.system_service.get_connection_status()


@router.get("/resources")
async def get_resources(data_service: DataService = Depends(get_data_service)):
    """获取系统资源使用情况"""
    return data_service.system_service.get_system_resources()


@router.get("/database")
async def get_database(data_service: DataService = Depends(get_data_service)):
    """获取数据库状态"""
    return data_service.system_service.get_database_status()