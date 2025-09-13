# quant_server/api/data_sync.py
from datetime import datetime
from typing import Dict, Any, List, Optional
from fastapi import APIRouter, HTTPException, BackgroundTasks, Depends, Query
from pydantic import BaseModel, Field
import logging

from quant_server.db.services.data_sync_service import DataSyncService

router = APIRouter(prefix="/data-sync", tags=["数据同步"])

logger = logging.getLogger(__name__)


#todo 全局存储同步状态（实际项目中建议使用Redis或数据库）
sync_status: Dict[str, Any] = {
    "last_run": None,
    "is_running": False,
    "progress": 0,
    "current_task": None,
    "results": {},
    "error": None
}


class SyncRequest(BaseModel):
    days: int = Field(30, ge=1, le=365, description="同步天数")
    start_date: Optional[str] = Field(None, description="开始日期(YYYYMMDD)")
    end_date: Optional[str] = Field(None, description="结束日期(YYYYMMDD)")
    stock_codes: Optional[List[str]] = Field(None, description="指定股票代码列表")
    exchange: Optional[str] = Field(None, description="交易所代码")
    batch_size: int = Field(100, ge=1, le=500, description="批量处理大小")


class SyncResponse(BaseModel):
    status: str
    message: str
    task_id: Optional[str] = None
    estimated_time: Optional[int] = None  # 预计完成时间(秒)


class SyncStatusResponse(BaseModel):
    is_running: bool
    last_run: Optional[datetime]
    progress: int
    current_task: Optional[str]
    results: Optional[Dict[str, Any]]
    error: Optional[str]
    estimated_remaining: Optional[int]  # 预计剩余时间(秒)


class DataTypeRequest(BaseModel):
    data_types: List[str] = Field(..., description="数据类型列表")


def get_sync_service():
    """获取数据同步服务实例"""
    return DataSyncService()


def update_sync_status(
    is_running: Optional[bool] = None,
    progress: Optional[int] = None,
    current_task: Optional[str] = None,
    results: Optional[Dict[str, Any]] = None,
    error: Optional[str] = None
):
    """更新同步状态"""
    if is_running is not None:
        sync_status["is_running"] = is_running
    if progress is not None:
        sync_status["progress"] = progress
    if current_task is not None:
        sync_status["current_task"] = current_task
    if results is not None:
        sync_status["results"] = results
    if error is not None:
        sync_status["error"] = error

    sync_status["last_run"] = datetime.now()

@router.get("/status", response_model=SyncStatusResponse)
async def get_sync_status():
    """获取数据同步状态"""
    return sync_status


@router.get("/supported-data-types")
async def get_supported_data_types():
    """获取支持的数据类型列表"""
    return {
        "data_types": [
            "stock_basic", "stock_company", "stk_managers", "stk_rewards",
            "daily", "weekly", "monthly", "adj_factor", "daily_basic",
            "moneyflow", "trade_cal", "fund_basic", "fund_daily",
            "index_weight"
        ]
    }


@router.post("/stock-basic", response_model=SyncResponse)
async def sync_stock_basic(
        request: SyncRequest,
        background_tasks: BackgroundTasks,
        sync_service: DataSyncService = Depends(get_sync_service)
):
    """同步股票基本信息"""
    if sync_status["is_running"]:
        raise HTTPException(status_code=409, detail="已有同步任务正在进行中")

    update_sync_status(
        is_running=True,
        current_task="stock_basic",
        progress=0
    )

    def sync_task():
        try:
            result = sync_service.sync_stock_basic(
                exchange=request.exchange
            )
            update_sync_status(
                is_running=False,
                progress=100,
                results={"stock_basic": result}
            )
            logger.info(f"股票基本信息同步完成，共处理{result.get('count', 0)}条记录")
        except Exception as e:
            error_msg = f"股票基本信息同步失败: {str(e)}"
            logger.error(error_msg)
            update_sync_status(
                is_running=False,
                progress=100,
                error=error_msg
            )

    background_tasks.add_task(sync_task)

    return SyncResponse(
        status="started",
        message="股票基本信息同步任务已开始",
        task_id=f"stock_basic_{datetime.now().strftime('%Y%m%d_%H%M%S')}",
        estimated_time=10  # 预计10秒完成
    )


@router.post("/daily", response_model=SyncResponse)
async def sync_daily_data(
        request: SyncRequest,
        background_tasks: BackgroundTasks,
        sync_service: DataSyncService = Depends(get_sync_service)
):
    """同步日线数据"""
    if sync_status["is_running"]:
        raise HTTPException(status_code=409, detail="已有同步任务正在进行中")

    update_sync_status(
        is_running=True,
        current_task="daily",
        progress=0
    )

    def sync_task():
        try:
            result = sync_service.sync_daily_data(
                days=request.days,
                stock_codes=request.stock_codes,
                batch_size=request.batch_size
            )
            update_sync_status(
                is_running=False,
                progress=100,
                results={"daily": result}
            )
            logger.info(f"日线数据同步完成，共处理{result.get('count', 0)}条记录")
        except Exception as e:
            error_msg = f"日线数据同步失败: {str(e)}"
            logger.error(error_msg)
            update_sync_status(
                is_running=False,
                progress=100,
                error=error_msg
            )

    # 估算完成时间 (每只股票约0.1秒，加上缓冲)
    stock_count = len(request.stock_codes) if request.stock_codes else 5000  # 默认估计5000只股票
    estimated_time = max(30, int(stock_count * 0.1 / request.batch_size * 5))  # 考虑并行处理

    background_tasks.add_task(sync_task)

    return SyncResponse(
        status="started",
        message="日线数据同步任务已开始",
        task_id=f"daily_{datetime.now().strftime('%Y%m%d_%H%M%S')}",
        estimated_time=estimated_time
    )


@router.post("/weekly", response_model=SyncResponse)
async def sync_weekly_data(
        request: SyncRequest,
        background_tasks: BackgroundTasks,
        sync_service: DataSyncService = Depends(get_sync_service)
):
    """同步周线数据"""
    if sync_status["is_running"]:
        raise HTTPException(status_code=409, detail="已有同步任务正在进行中")

    update_sync_status(
        is_running=True,
        current_task="weekly",
        progress=0
    )

    def sync_task():
        try:
            result = sync_service.sync_weekly_data(
                days=request.days,
                stock_codes=request.stock_codes,
                batch_size=request.batch_size
            )
            update_sync_status(
                is_running=False,
                progress=100,
                results={"weekly": result}
            )
            logger.info(f"周线数据同步完成，共处理{result.get('count', 0)}条记录")
        except Exception as e:
            error_msg = f"周线数据同步失败: {str(e)}"
            logger.error(error_msg)
            update_sync_status(
                is_running=False,
                progress=100,
                error=error_msg
            )

    background_tasks.add_task(sync_task)

    return SyncResponse(
        status="started",
        message="周线数据同步任务已开始",
        task_id=f"weekly_{datetime.now().strftime('%Y%m%d_%H%M%S')}",
        estimated_time=300  # 预计5分钟完成
    )


@router.post("/monthly", response_model=SyncResponse)
async def sync_monthly_data(
        request: SyncRequest,
        background_tasks: BackgroundTasks,
        sync_service: DataSyncService = Depends(get_sync_service)
):
    """同步月线数据"""
    if sync_status["is_running"]:
        raise HTTPException(status_code=409, detail="已有同步任务正在进行中")

    update_sync_status(
        is_running=True,
        current_task="monthly",
        progress=0
    )

    def sync_task():
        try:
            result = sync_service.sync_monthly_data(
                days=request.days,
                stock_codes=request.stock_codes,
                batch_size=request.batch_size
            )
            update_sync_status(
                is_running=False,
                progress=100,
                results={"monthly": result}
            )
            logger.info(f"月线数据同步完成，共处理{result.get('count', 0)}条记录")
        except Exception as e:
            error_msg = f"月线数据同步失败: {str(e)}"
            logger.error(error_msg)
            update_sync_status(
                is_running=False,
                progress=100,
                error=error_msg
            )

    background_tasks.add_task(sync_task)

    return SyncResponse(
        status="started",
        message="月线数据同步任务已开始",
        task_id=f"monthly_{datetime.now().strftime('%Y%m%d_%H%M%S')}",
        estimated_time=300  # 预计5分钟完成
    )


@router.post("/moneyflow", response_model=SyncResponse)
async def sync_moneyflow_data(
        request: SyncRequest,
        background_tasks: BackgroundTasks,
        sync_service: DataSyncService = Depends(get_sync_service)
):
    """同步资金流向数据"""
    if sync_status["is_running"]:
        raise HTTPException(status_code=409, detail="已有同步任务正在进行中")

    update_sync_status(
        is_running=True,
        current_task="moneyflow",
        progress=0
    )

    def sync_task():
        try:
            result = sync_service.sync_moneyflow_data(
                days=request.days,
                stock_codes=request.stock_codes,
                batch_size=request.batch_size
            )
            update_sync_status(
                is_running=False,
                progress=100,
                results={"moneyflow": result}
            )
            logger.info(f"资金流向数据同步完成，共处理{result.get('count', 0)}条记录")
        except Exception as e:
            error_msg = f"资金流向数据同步失败: {str(e)}"
            logger.error(error_msg)
            update_sync_status(
                is_running=False,
                progress=100,
                error=error_msg
            )

    background_tasks.add_task(sync_task)

    return SyncResponse(
        status="started",
        message="资金流向数据同步任务已开始",
        task_id=f"moneyflow_{datetime.now().strftime('%Y%m%d_%H%M%S')}",
        estimated_time=600  # 预计10分钟完成
    )


@router.post("/trade-calendar", response_model=SyncResponse)
async def sync_trade_calendar(
        exchanges: List[str] = Query(['SSE', 'SZSE']),
        start_date: str = '19900101',
        end_date: str = '20301231',
        background_tasks: BackgroundTasks = None,
        sync_service: DataSyncService = Depends(get_sync_service)
):
    """同步交易日历"""
    if sync_status["is_running"]:
        raise HTTPException(status_code=409, detail="已有同步任务正在进行中")

    update_sync_status(
        is_running=True,
        current_task="trade_calendar",
        progress=0
    )

    def sync_task():
        try:
            result = sync_service.sync_trade_calendar(
                exchanges=exchanges,
                start_date=start_date,
                end_date=end_date
            )
            update_sync_status(
                is_running=False,
                progress=100,
                results={"trade_calendar": result}
            )
            logger.info(f"交易日历同步完成，共处理{result.get('count', 0)}条记录")
        except Exception as e:
            error_msg = f"交易日历同步失败: {str(e)}"
            logger.error(error_msg)
            update_sync_status(
                is_running=False,
                progress=100,
                error=error_msg
            )

    if background_tasks:
        background_tasks.add_task(sync_task)
    else:
        # 如果没有BackgroundTasks，直接运行
        sync_task()

    return SyncResponse(
        status="started",
        message="交易日历同步任务已开始",
        task_id=f"trade_calendar_{datetime.now().strftime('%Y%m%d_%H%M%S')}",
        estimated_time=30  # 预计30秒完成
    )

@router.post("/all", response_model=SyncResponse)
async def sync_all_data(
        request: SyncRequest,
        background_tasks: BackgroundTasks,
        sync_service: DataSyncService = Depends(get_sync_service)
):
    """同步所有数据"""
    if sync_status["is_running"]:
        raise HTTPException(status_code=409, detail="已有同步任务正在进行中")

    update_sync_status(
        is_running=True,
        current_task="all",
        progress=0
    )

    def sync_task():
        try:
            result = sync_service.sync_all_data(
                days=request.days,
                batch_size=request.batch_size
            )
            update_sync_status(
                is_running=False,
                progress=100,
                results=result
            )
            logger.info("所有数据同步完成")
        except Exception as e:
            error_msg = f"所有数据同步失败: {str(e)}"
            logger.error(error_msg)
            update_sync_status(
                is_running=False,
                progress=100,
                error=error_msg
            )

    # 估算完成时间 (根据数据类型和数量)
    estimated_time = 1800  # 预计30分钟完成全量同步

    background_tasks.add_task(sync_task)

    return SyncResponse(
        status="started",
        message="所有数据同步任务已开始",
        task_id=f"all_{datetime.now().strftime('%Y%m%d_%H%M%S')}",
        estimated_time=estimated_time
    )


@router.post("/cancel")
async def cancel_sync():
    """取消当前同步任务"""
    if not sync_status["is_running"]:
        raise HTTPException(status_code=400, detail="当前没有正在进行的同步任务")

    # 这里需要实现取消逻辑，可能需要终止线程池中的任务
    # 由于Python线程终止比较复杂，这里只是标记状态
    update_sync_status(
        is_running=False,
        error="任务已被用户取消"
    )

    return {"status": "cancelled", "message": "同步任务已取消"}