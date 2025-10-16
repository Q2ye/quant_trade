# quant_server/api/data_sync.py
"""
数据同步API模块

提供统一的数据同步接口，支持批量数据类型同步。
采用智能执行策略：少量数据同步执行，大量数据异步执行。

主要功能：
- 批量数据同步（支持前端复选框多选）
- 智能同步策略（同步/异步自动选择）
- 实时同步状态查询
- 同步任务取消
- 支持的数据类型查询
"""

from datetime import datetime
from typing import Dict, Any, List, Optional
from fastapi import APIRouter, HTTPException, BackgroundTasks, Depends, Query
from pydantic import BaseModel, Field
import logging
import asyncio

from quant_server.db.services.data_sync_service import DataSyncService

# 初始化路由器和日志
router = APIRouter(prefix="/data-sync", tags=["数据同步"])
logger = logging.getLogger(__name__)

# 内存存储同步状态（每次同步完成后自动重置）
_sync_status: Dict[str, Any] = {
    "last_run": None,
    "is_running": False,
    "progress": 0,
    "current_task": None,
    "results": {},
    "error": None,
    "total_tasks": 0,
    "completed_tasks": 0,
    "start_time": None,
    "task_id": None
}

# 数据类型的映射关系
DATA_TYPE_MAPPING = {
    "stock_basic": "stock_basic",
    "trade_calendar": "trade_cal",
    "daily": "daily",
    "weekly": "weekly",
    "monthly": "monthly",
    "adj_factor": "adj_factor",
    "daily_basic": "daily_basic",
    "moneyflow": "moneyflow",
    "etf": "fund_basic",
    "daily_limit": "stock_daily_limit",
    "st_list": "stock_st_list",
    "company": "stock_company",
    "managers": "stk_managers",
}

# 快速同步的数据类型（核心数据类型）
QUICK_SYNC_TYPES = ["stock_basic", "trade_calendar", "daily", "daily_basic"]


# 同步模式
class SyncMode:
    SYNC = "sync"  # 同步执行
    ASYNC = "async"  # 异步执行


class SyncRequest(BaseModel):
    """同步请求基础模型"""
    days: int = Field(30, ge=1, le=365, description="同步天数")
    start_date: Optional[str] = Field(None, description="开始日期(YYYYMMDD)")
    end_date: Optional[str] = Field(None, description="结束日期(YYYYMMDD)")
    stock_codes: Optional[List[str]] = Field(None, description="指定股票代码列表")
    exchange: Optional[str] = Field(None, description="交易所代码")
    batch_size: int = Field(100, ge=1, le=500, description="批量处理大小")


class BatchSyncRequest(SyncRequest):
    """批量同步请求模型"""
    data_types: List[str] = Field(..., description="需要同步的数据类型列表")
    sync_mode: Optional[str] = Field(SyncMode.SYNC, description="同步模式: sync|async")


class SyncResponse(BaseModel):
    """同步响应模型"""
    status: str
    message: str
    task_id: Optional[str] = None
    estimated_time: Optional[int] = None
    total_tasks: Optional[int] = None
    current_progress: Optional[int] = None
    sync_mode: Optional[str] = None


class SyncStatusResponse(BaseModel):
    """同步状态响应模型"""
    is_running: bool
    last_run: Optional[datetime] = None
    progress: int
    current_task: Optional[str] = None
    results: Optional[Dict[str, Any]] = None
    error: Optional[str] = None
    estimated_remaining: Optional[int] = None
    total_tasks: int
    completed_tasks: int
    task_queue: Optional[List[str]] = None
    elapsed_time: Optional[int] = None
    start_time: Optional[datetime] = None


class DataTypeInfo(BaseModel):
    """数据类型信息模型"""
    code: str
    name: str
    description: str
    estimated_time: int


def get_sync_service() -> DataSyncService:
    """获取数据同步服务实例"""
    return DataSyncService()


def reset_sync_status():
    """重置同步状态到初始值"""
    global _sync_status
    _sync_status = {
        "last_run": None,
        "is_running": False,
        "progress": 0,
        "current_task": None,
        "results": {},
        "error": None,
        "total_tasks": 0,
        "completed_tasks": 0,
        "start_time": None,
        "task_id": None
    }


def update_sync_status(
        is_running: Optional[bool] = None,
        progress: Optional[int] = None,
        current_task: Optional[str] = None,
        results: Optional[Dict[str, Any]] = None,
        error: Optional[str] = None,
        total_tasks: Optional[int] = None,
        completed_tasks: Optional[int] = None,
        task_id: Optional[str] = None
):
    """更新同步状态"""
    global _sync_status

    if is_running and _sync_status["start_time"] is None:
        _sync_status["start_time"] = datetime.now()

    if is_running is not None:
        _sync_status["is_running"] = is_running
    if progress is not None:
        _sync_status["progress"] = progress
    if current_task is not None:
        _sync_status["current_task"] = current_task
    if results is not None:
        _sync_status["results"] = results
    if error is not None:
        _sync_status["error"] = error
    if total_tasks is not None:
        _sync_status["total_tasks"] = total_tasks
    if completed_tasks is not None:
        _sync_status["completed_tasks"] = completed_tasks
    if task_id is not None:
        _sync_status["task_id"] = task_id

    _sync_status["last_run"] = datetime.now()

    if progress == 100 or error is not None:
        _sync_status["is_running"] = False


def get_sync_status() -> Dict[str, Any]:
    """获取当前同步状态"""
    elapsed_time = None
    if _sync_status["start_time"]:
        elapsed_time = int((datetime.now() - _sync_status["start_time"]).total_seconds())

    estimated_remaining = None
    if _sync_status["is_running"] and _sync_status["progress"] > 0:
        estimated_remaining = int((elapsed_time / _sync_status["progress"]) * (100 - _sync_status["progress"]))

    status = _sync_status.copy()
    status["elapsed_time"] = elapsed_time
    status["estimated_remaining"] = estimated_remaining

    return status


def should_use_async_mode(data_types: List[str], days: int, stock_codes: Optional[List[str]]) -> bool:
    """
    判断是否应该使用异步模式

    策略：
    - 数据类型数量 >= 3 个 → 异步
    - 包含日线、周线、月线等大数据量类型 → 异步
    - 同步天数 > 30 天 → 异步
    - 指定了大量股票代码 → 异步
    - 其他情况 → 同步
    """
    # 大数据量数据类型
    heavy_data_types = {"daily", "weekly", "monthly", "moneyflow", "financial"}

    # 如果数据类型数量多
    if len(data_types) >= 3:
        return True

    # 如果包含大数据量类型
    if any(dt in heavy_data_types for dt in data_types):
        return True

    # 如果同步时间长
    if days > 30:
        return True

    # 如果指定了大量股票代码
    if stock_codes and len(stock_codes) > 10:
        return True

    return False


def execute_sync_task(sync_service: DataSyncService, data_types: List[str], request: BatchSyncRequest) -> Dict[
    str, Any]:
    """执行同步任务（同步版本）"""
    results = {}
    total_tasks = len(data_types)

    for i, current_data_type in enumerate(data_types):
        progress = int((i / total_tasks) * 100)
        update_sync_status(
            current_task=f"正在同步: {current_data_type}",
            progress=progress,
            completed_tasks=i
        )

        try:
            # 根据数据类型调用不同的同步方法
            if current_data_type == "stock_basic":
                results["stock_basic"] = sync_service.sync_stock_basic(
                    exchange=request.exchange
                )
            elif current_data_type == "trade_calendar":
                results["trade_calendar"] = sync_service.sync_trade_calendar(
                    exchanges=['SSE', 'SZSE'],
                    start_date=request.start_date or '19900101',
                    end_date=request.end_date or '20301231'
                )
            elif current_data_type == "daily":
                results["daily"] = sync_service.sync_daily_data(
                    days=request.days,
                    stock_codes=request.stock_codes,
                    batch_size=request.batch_size
                )
            elif current_data_type == "weekly":
                results["weekly"] = sync_service.sync_weekly_data(
                    days=request.days,
                    stock_codes=request.stock_codes,
                    batch_size=request.batch_size
                )
            elif current_data_type == "monthly":
                results["monthly"] = sync_service.sync_monthly_data(
                    days=request.days,
                    stock_codes=request.stock_codes,
                    batch_size=request.batch_size
                )
            elif current_data_type == "moneyflow":
                results["moneyflow"] = sync_service.sync_moneyflow_data(
                    days=request.days,
                    stock_codes=request.stock_codes,
                    batch_size=request.batch_size
                )
            elif current_data_type == "adj_factor":
                results["adj_factor"] = sync_service.sync_adj_factor_data(
                    days=request.days,
                    stock_codes=request.stock_codes,
                    batch_size=request.batch_size
                )
            elif current_data_type == "daily_basic":
                results["daily_basic"] = sync_service.sync_daily_basic_data(
                    days=request.days,
                    stock_codes=request.stock_codes,
                    batch_size=request.batch_size
                )
            elif current_data_type == "st_list":
                results["st_list"] = sync_service.sync_st_stock_list(
                    days=request.days
                )
            elif current_data_type == "company":
                results["company"] = sync_service.sync_company_info(
                    stock_codes=request.stock_codes
                )
            elif current_data_type == "managers":
                results["managers"] = sync_service.sync_management_info(
                    days=request.days
                )
            elif current_data_type == "etf":
                results["etf"] = sync_service.sync_etf_basic()
            elif current_data_type == "daily_limit":
                results["daily_limit"] = sync_service.sync_daily_limit_data(
                    days=request.days,
                    stock_codes=request.stock_codes,
                    batch_size=request.batch_size
                )

            logger.info(f"数据类型 {current_data_type} 同步完成")

        except Exception as e:
            error_msg = f"数据类型 {current_data_type} 同步失败: {str(e)}"
            logger.error(error_msg)
            results[current_data_type] = {"error": error_msg}

    return results


async def execute_async_sync_task(sync_service: DataSyncService, data_types: List[str], request: BatchSyncRequest):
    """执行同步任务（异步版本）"""
    try:
        results = {}
        total_tasks = len(data_types)

        for i, current_data_type in enumerate(data_types):
            progress = int((i / total_tasks) * 100)
            update_sync_status(
                current_task=f"正在同步: {current_data_type}",
                progress=progress,
                completed_tasks=i
            )

            try:
                # 在线程池中执行同步方法
                loop = asyncio.get_event_loop()

                if current_data_type == "stock_basic":
                    results["stock_basic"] = await loop.run_in_executor(
                        None, sync_service.sync_stock_basic, request.exchange
                    )
                elif current_data_type == "trade_calendar":
                    results["trade_calendar"] = await loop.run_in_executor(
                        None, sync_service.sync_trade_calendar,
                        ['SSE', 'SZSE'],
                        request.start_date or '19900101',
                        request.end_date or '20301231'
                    )
                elif current_data_type == "daily":
                    results["daily"] = await loop.run_in_executor(
                        None, sync_service.sync_daily_data,
                        request.days, request.stock_codes, request.batch_size
                    )
                elif current_data_type == "weekly":
                    results["weekly"] = await loop.run_in_executor(
                        None, sync_service.sync_weekly_data,
                        request.days, request.stock_codes, request.batch_size
                    )
                elif current_data_type == "monthly":
                    results["monthly"] = await loop.run_in_executor(
                        None, sync_service.sync_monthly_data,
                        request.days, request.stock_codes, request.batch_size
                    )
                elif current_data_type == "moneyflow":
                    results["moneyflow"] = await loop.run_in_executor(
                        None, sync_service.sync_moneyflow_data,
                        request.days, request.stock_codes, request.batch_size
                    )
                elif current_data_type == "adj_factor":
                    results["adj_factor"] = await loop.run_in_executor(
                        None, sync_service.sync_adj_factor_data,
                        request.days, request.stock_codes, request.batch_size
                    )
                elif current_data_type == "daily_basic":
                    results["daily_basic"] = await loop.run_in_executor(
                        None, sync_service.sync_daily_basic_data,
                        request.days, request.stock_codes, request.batch_size
                    )
                elif current_data_type == "st_list":
                    results["st_list"] = await loop.run_in_executor(
                        None, sync_service.sync_st_stock_list, request.days
                    )
                elif current_data_type == "company":
                    results["company"] = await loop.run_in_executor(
                        None, sync_service.sync_company_info, request.stock_codes
                    )
                elif current_data_type == "managers":
                    results["managers"] = await loop.run_in_executor(
                        None, sync_service.sync_management_info, request.days
                    )
                elif current_data_type == "etf":
                    results["etf"] = await loop.run_in_executor(
                        None, sync_service.sync_etf_basic
                    )
                elif current_data_type == "daily_limit":
                    results["daily_limit"] = await loop.run_in_executor(
                        None, sync_service.sync_daily_limit_data,
                        request.days, request.stock_codes, request.batch_size
                    )

                logger.info(f"数据类型 {current_data_type} 同步完成")

            except Exception as e:
                error_msg = f"数据类型 {current_data_type} 同步失败: {str(e)}"
                logger.error(error_msg)
                results[current_data_type] = {"error": error_msg}

        # 任务完成
        update_sync_status(
            is_running=False,
            progress=100,
            completed_tasks=total_tasks,
            results=results
        )
        logger.info(f"批量数据同步完成，共处理 {total_tasks} 种数据类型")

    except Exception as e:
        error_msg = f"批量数据同步失败: {str(e)}"
        logger.error(error_msg)
        update_sync_status(
            is_running=False,
            progress=100,
            error=error_msg
        )


@router.get("/status", response_model=SyncStatusResponse)
async def get_sync_status_api():
    """获取数据同步状态接口"""
    try:
        status = get_sync_status()

        if status.get("elapsed_time") is None:
            status["elapsed_time"] = 0

        if status.get("total_tasks") is None:
            status["total_tasks"] = 0

        if status.get("completed_tasks") is None:
            status["completed_tasks"] = 0

        if status.get("progress") is None:
            status["progress"] = 0

        if status.get("estimated_remaining") is None:
            status["estimated_remaining"] = 0

        if status.get("results") is None:
            status["results"] = {}

        if status.get("task_queue") is None:
            status["task_queue"] = []

        return SyncStatusResponse(**status)
    except Exception as e:
        logger.error(f"获取同步状态失败: {str(e)}")
        return SyncStatusResponse(
            is_running=False,
            progress=0,
            total_tasks=0,
            completed_tasks=0,
            estimated_remaining=0,
            elapsed_time=0,
            error="状态查询失败"
        )


@router.get("/supported-data-types", response_model=List[DataTypeInfo])
async def get_supported_data_types():
    """获取支持的数据类型列表及详细信息"""
    return [
        DataTypeInfo(code="stock_basic", name="股票列表", description="股票基础信息", estimated_time=30),
        DataTypeInfo(code="trade_calendar", name="交易日历", description="交易所交易日历", estimated_time=5),
        DataTypeInfo(code="daily", name="日线行情", description="A股日线行情数据", estimated_time=120),
        DataTypeInfo(code="weekly", name="周线行情", description="周线行情数据", estimated_time=60),
        DataTypeInfo(code="monthly", name="月线行情", description="月线行情数据", estimated_time=45),
        DataTypeInfo(code="moneyflow", name="资金流向", description="资金流向数据", estimated_time=75),
        DataTypeInfo(code="etf", name="ETF数据", description="ETF基础信息和行情", estimated_time=40),
        DataTypeInfo(code="adj_factor", name="复权因子", description="股票复权因子", estimated_time=25),
        DataTypeInfo(code="daily_basic", name="每日指标", description="每日基本面指标", estimated_time=50),
        DataTypeInfo(code="daily_limit", name="涨跌停价格", description="每日涨跌停价格", estimated_time=20),
        DataTypeInfo(code="st_list", name="ST股票列表", description="ST股票历史记录", estimated_time=15),
        DataTypeInfo(code="company", name="公司信息", description="上市公司基本信息", estimated_time=35),
        DataTypeInfo(code="managers", name="管理层信息", description="公司管理层信息", estimated_time=25)
    ]


@router.post("/batch-sync", response_model=SyncResponse)
async def batch_sync_data(
        request: BatchSyncRequest,
        background_tasks: BackgroundTasks,
        sync_service: DataSyncService = Depends(get_sync_service)
):
    """
    批量同步数据 - 智能选择同步/异步模式

    策略：
    - 少量数据类型（1-2个）：同步执行，立即返回结果
    - 大量数据类型（3个以上）：异步执行，后台任务处理
    - 强制指定模式：按指定模式执行
    """
    # 检查是否有任务正在运行
    current_status = get_sync_status()
    if current_status["is_running"]:
        raise HTTPException(status_code=409, detail="已有同步任务正在进行中")

    # 验证数据类型
    valid_data_types = []
    for data_type in request.data_types:
        if data_type in DATA_TYPE_MAPPING:
            valid_data_types.append(data_type)
        else:
            logger.warning(f"未知的数据类型: {data_type}")

    if not valid_data_types:
        raise HTTPException(status_code=400, detail="未选择有效的数据类型")

    # 生成任务ID
    task_id = f"batch_{datetime.now().strftime('%Y%m%d_%H%M%S')}"

    # 确定同步模式
    sync_mode = request.sync_mode or SyncMode.SYNC
    if sync_mode not in [SyncMode.SYNC, SyncMode.ASYNC]:
        sync_mode = SyncMode.SYNC

    # 智能模式选择：如果没有指定模式，根据数据量自动选择
    if request.sync_mode is None:
        sync_mode = SyncMode.ASYNC if should_use_async_mode(valid_data_types, request.days,
                                                            request.stock_codes) else SyncMode.SYNC

    # 重置并更新同步状态
    reset_sync_status()
    update_sync_status(
        is_running=True,
        current_task="初始化批量同步",
        progress=0,
        total_tasks=len(valid_data_types),
        completed_tasks=0,
        task_id=task_id
    )

    # 估算完成时间
    estimated_time = estimate_batch_time(valid_data_types, request)

    # 同步执行模式
    if sync_mode == SyncMode.SYNC:
        try:
            logger.info(f"使用同步模式执行数据同步，数据类型: {valid_data_types}")

            # 同步执行
            results = execute_sync_task(sync_service, valid_data_types, request)

            # 任务完成
            update_sync_status(
                is_running=False,
                progress=100,
                completed_tasks=len(valid_data_types),
                results=results
            )

            logger.info(f"同步数据同步完成，共处理 {len(valid_data_types)} 种数据类型")

            return SyncResponse(
                status="completed",
                message=f"同步完成，共处理 {len(valid_data_types)} 种数据类型",
                task_id=task_id,
                estimated_time=estimated_time,
                total_tasks=len(valid_data_types),
                current_progress=100,
                sync_mode=sync_mode
            )

        except Exception as e:
            error_msg = f"同步数据同步失败: {str(e)}"
            logger.error(error_msg)
            update_sync_status(
                is_running=False,
                progress=100,
                error=error_msg
            )
            raise HTTPException(status_code=500, detail=error_msg)

    # 异步执行模式
    else:
        logger.info(f"使用异步模式执行数据同步，数据类型: {valid_data_types}")

        # 添加后台任务
        background_tasks.add_task(execute_async_sync_task, sync_service, valid_data_types, request)

        return SyncResponse(
            status="started",
            message=f"开始异步同步 {len(valid_data_types)} 种数据类型",
            task_id=task_id,
            estimated_time=estimated_time,
            total_tasks=len(valid_data_types),
            current_progress=0,
            sync_mode=sync_mode
        )


@router.post("/quick-sync", response_model=SyncResponse)
async def quick_sync_data(
        background_tasks: BackgroundTasks,
        sync_service: DataSyncService = Depends(get_sync_service)
):
    """
    快速同步 - 异步执行核心数据类型
    """
    # 检查是否有任务正在运行
    current_status = get_sync_status()
    if current_status["is_running"]:
        raise HTTPException(status_code=409, detail="已有同步任务正在进行中")

    # 使用快速同步的数据类型
    data_types = QUICK_SYNC_TYPES

    # 生成任务ID
    task_id = f"quick_{datetime.now().strftime('%Y%m%d_%H%M%S')}"

    # 重置并更新同步状态
    reset_sync_status()
    update_sync_status(
        is_running=True,
        current_task="初始化快速同步",
        progress=0,
        total_tasks=len(data_types),
        completed_tasks=0,
        task_id=task_id
    )

    # 创建快速同步请求
    quick_request = BatchSyncRequest(
        data_types=data_types,
        days=30,  # 快速同步使用30天
        batch_size=100
    )

    # 估算完成时间
    estimated_time = estimate_batch_time(data_types, quick_request)

    # 异步执行快速同步
    background_tasks.add_task(execute_async_sync_task, sync_service, data_types, quick_request)

    return SyncResponse(
        status="started",
        message=f"开始快速同步 {len(data_types)} 种核心数据类型",
        task_id=task_id,
        estimated_time=estimated_time,
        total_tasks=len(data_types),
        current_progress=0,
        sync_mode=SyncMode.ASYNC
    )


@router.post("/full-sync", response_model=SyncResponse)
async def full_sync_data(
        request: SyncRequest,
        background_tasks: BackgroundTasks,
        sync_service: DataSyncService = Depends(get_sync_service)
):
    """
    全量同步 - 异步执行所有数据类型
    """
    # 检查是否有任务正在运行
    current_status = get_sync_status()
    if current_status["is_running"]:
        raise HTTPException(status_code=409, detail="已有同步任务正在进行中")

    # 使用所有支持的数据类型
    data_types = list(DATA_TYPE_MAPPING.keys())

    # 生成任务ID
    task_id = f"full_{datetime.now().strftime('%Y%m%d_%H%M%S')}"

    # 重置并更新同步状态
    reset_sync_status()
    update_sync_status(
        is_running=True,
        current_task="初始化全量同步",
        progress=0,
        total_tasks=len(data_types),
        completed_tasks=0,
        task_id=task_id
    )

    # 创建全量同步请求
    full_request = BatchSyncRequest(
        data_types=data_types,
        days=request.days,
        start_date=request.start_date,
        end_date=request.end_date,
        stock_codes=request.stock_codes,
        exchange=request.exchange,
        batch_size=request.batch_size
    )

    # 估算完成时间
    estimated_time = estimate_batch_time(data_types, full_request)

    # 异步执行全量同步
    background_tasks.add_task(execute_async_sync_task, sync_service, data_types, full_request)

    return SyncResponse(
        status="started",
        message=f"开始全量同步 {len(data_types)} 种数据类型",
        task_id=task_id,
        estimated_time=estimated_time,
        total_tasks=len(data_types),
        current_progress=0,
        sync_mode=SyncMode.ASYNC
    )


def estimate_batch_time(data_types: List[str], request: BatchSyncRequest) -> int:
    """估算批量同步时间"""
    time_estimates = {
        "stock_basic": 30,
        "trade_calendar": 5,
        "daily": 120,
        "weekly": 60,
        "monthly": 45,
        "moneyflow": 75,
        "etf": 40,
        "adj_factor": 25,
        "daily_basic": 50,
        "daily_limit": 20,
        "st_list": 15,
        "company": 35,
        "managers": 25
    }

    base_time = sum(time_estimates.get(dt, 30) for dt in data_types)

    stock_count = len(request.stock_codes) if request.stock_codes else 5000
    if stock_count > 1000:
        base_time = base_time * stock_count // 1000

    return max(60, base_time)


@router.post("/cancel")
async def cancel_sync():
    """取消当前同步任务"""
    current_status = get_sync_status()
    if not current_status["is_running"]:
        raise HTTPException(status_code=400, detail="当前没有正在进行的同步任务")

    update_sync_status(
        is_running=False,
        error="任务已被用户取消"
    )

    return {"status": "cancelled", "message": "同步任务已取消"}