# quant_server/api/data_sync.py
"""
数据同步API模块

提供统一的数据同步接口，支持批量数据类型同步和单个数据类型同步。
采用内存状态管理，每次同步完成后自动重置状态。

主要功能：
- 批量数据同步（支持前端复选框多选）
- 单个数据类型同步（向后兼容）
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
# 注意：在生产环境中，建议使用Redis或数据库存储状态以实现持久化和多实例支持
_sync_status: Dict[str, Any] = {
    "last_run": None,  # 最后运行时间
    "is_running": False,  # 是否正在运行
    "progress": 0,  # 进度百分比 (0-100)
    "current_task": None,  # 当前任务名称
    "results": {},  # 同步结果
    "error": None,  # 错误信息
    "total_tasks": 0,  # 总任务数
    "completed_tasks": 0,  # 已完成任务数
    "start_time": None,  # 任务开始时间
    "task_id": None  # 当前任务ID
}

# 数据类型的映射关系
# 将前端数据类型代码映射到后端服务方法
DATA_TYPE_MAPPING = {
    "stock_list": "stock_basic",  # 股票列表 -> 股票基础信息
    "company_info": "stock_company",  # 公司信息 -> 上市公司基本信息
    "management_info": "stk_managers",  # 管理层信息 -> 公司管理层信息
    "executive_rewards": "stk_rewards",  # 管理层薪酬 -> 管理层薪酬和持股信息
    "daily_quotes": "daily",  # 日线行情 -> A股日线行情数据
    "weekly_quotes": "weekly",  # 周线行情 -> 周线行情数据
    "monthly_quotes": "monthly",  # 月线行情 -> 月线行情数据
    "adj_factor": "adj_factor",  # 复权因子 -> 股票复权因子
    "daily_basic": "daily_basic",  # 每日指标 -> 每日基本面指标
    "money_flow": "moneyflow",  # 资金流向 -> 资金流向数据
    "trade_calendar": "trade_cal",  # 交易日历 -> 交易所交易日历
    "etf_basic": "fund_basic",  # ETF基本信息 -> ETF高级信息
    "etf_daily": "fund_daily",  # ETF行情 -> ETF行情数据
    "index_weight": "index_weight",  # 指数权重 -> 指数成分股权重
    "st_stock_list": "stock_st_list",  # ST股票列表 -> ST股票历史记录
    "daily_limit": "stock_daily_limit"  # 涨跌停价格 -> 每日涨跌停价格
}


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


class SyncResponse(BaseModel):
    """同步响应模型"""
    status: str
    message: str
    task_id: Optional[str] = None
    estimated_time: Optional[int] = None  # 预计完成时间(秒)
    total_tasks: Optional[int] = None
    current_progress: Optional[int] = None


class SyncStatusResponse(BaseModel):
    """同步状态响应模型"""
    is_running: bool
    last_run: Optional[datetime]
    progress: int
    current_task: Optional[str]
    results: Optional[Dict[str, Any]]
    error: Optional[str]
    estimated_remaining: Optional[int]  # 预计剩余时间(秒)
    total_tasks: int
    completed_tasks: int
    task_queue: Optional[List[str]] = None
    elapsed_time: Optional[int] = None  # 已运行时间(秒)
    start_time: Optional[datetime] = None


class DataTypeInfo(BaseModel):
    """数据类型信息模型"""
    code: str
    name: str
    description: str
    estimated_time: int


def get_sync_service() -> DataSyncService:
    """
    获取数据同步服务实例

    Returns:
        DataSyncService: 数据同步服务实例
    """
    return DataSyncService()


def reset_sync_status():
    """
    重置同步状态到初始值

    在每次同步任务开始前或完成后调用，确保状态被正确清理
    """
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
    """
    更新同步状态

    Args:
        is_running: 是否正在运行
        progress: 进度百分比
        current_task: 当前任务名称
        results: 同步结果
        error: 错误信息
        total_tasks: 总任务数
        completed_tasks: 已完成任务数
        task_id: 任务ID
    """
    global _sync_status

    # 设置开始时间（如果是第一次运行）
    if is_running and _sync_status["start_time"] is None:
        _sync_status["start_time"] = datetime.now()

    # 更新状态字段
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

    # 更新最后运行时间
    _sync_status["last_run"] = datetime.now()

    # 如果任务完成，重置运行状态但保留结果
    if progress == 100 or error is not None:
        _sync_status["is_running"] = False


def get_sync_status() -> Dict[str, Any]:
    """
    获取当前同步状态

    Returns:
        Dict: 包含所有同步状态信息的字典
    """
    # 计算已运行时间
    elapsed_time = None
    if _sync_status["start_time"]:
        elapsed_time = int((datetime.now() - _sync_status["start_time"]).total_seconds())

    status = _sync_status.copy()
    status["elapsed_time"] = elapsed_time

    return status


@router.get("/status", response_model=SyncStatusResponse)
async def get_sync_status_api():
    """
    获取数据同步状态API接口

    Returns:
        SyncStatusResponse: 包含详细同步状态信息的响应对象
    """
    status = get_sync_status()
    return SyncStatusResponse(**status)


@router.get("/supported-data-types", response_model=List[DataTypeInfo])
async def get_supported_data_types():
    """
    获取支持的数据类型列表及详细信息

    Returns:
        List[DataTypeInfo]: 包含所有支持的数据类型信息的列表
    """
    return [
        DataTypeInfo(
            code="stock_list",
            name="股票列表",
            description="股票基础信息",
            estimated_time=10
        ),
        DataTypeInfo(
            code="trade_calendar",
            name="交易日历",
            description="交易所交易日历",
            estimated_time=5
        ),
        DataTypeInfo(
            code="daily_quotes",
            name="日线行情",
            description="A股日线行情数据",
            estimated_time=300
        ),
        DataTypeInfo(
            code="weekly_quotes",
            name="周线行情",
            description="周线行情数据",
            estimated_time=60
        ),
        DataTypeInfo(
            code="monthly_quotes",
            name="月线行情",
            description="月线行情数据",
            estimated_time=30
        ),
        DataTypeInfo(
            code="money_flow",
            name="资金流向",
            description="资金流向数据",
            estimated_time=600
        ),
        DataTypeInfo(
            code="adj_factor",
            name="复权因子",
            description="股票复权因子",
            estimated_time=120
        ),
        DataTypeInfo(
            code="daily_basic",
            name="每日指标",
            description="每日基本面指标",
            estimated_time=180
        ),
        DataTypeInfo(
            code="st_stock_list",
            name="ST股票列表",
            description="ST股票历史记录",
            estimated_time=15
        ),
        DataTypeInfo(
            code="company_info",
            name="公司信息",
            description="上市公司基本信息",
            estimated_time=20
        ),
        DataTypeInfo(
            code="management_info",
            name="管理层信息",
            description="公司管理层信息",
            estimated_time=30
        ),
        DataTypeInfo(
            code="executive_rewards",
            name="管理层薪酬",
            description="管理层薪酬和持股信息",
            estimated_time=25
        ),
        DataTypeInfo(
            code="etf_basic",
            name="ETF基本信息",
            description="ETF高级信息",
            estimated_time=10
        ),
        DataTypeInfo(
            code="etf_daily",
            name="ETF行情",
            description="ETF行情数据",
            estimated_time=120
        ),
        DataTypeInfo(
            code="daily_limit",
            name="涨跌停价格",
            description="每日涨跌停价格",
            estimated_time=90
        )
    ]


@router.post("/batch-sync", response_model=SyncResponse)
async def batch_sync_data(
        request: BatchSyncRequest,
        background_tasks: BackgroundTasks,
        sync_service: DataSyncService = Depends(get_sync_service)
):
    """
    批量同步数据 - 根据前端复选框选择的数据类型进行同步

    Args:
        request: 批量同步请求对象
        background_tasks: FastAPI后台任务管理器
        sync_service: 数据同步服务实例

    Returns:
        SyncResponse: 同步任务启动响应

    Raises:
        HTTPException: 当已有任务运行或数据类型无效时抛出异常
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

    def sync_task():
        """后台同步任务执行函数"""
        try:
            results = {}
            total_tasks = len(valid_data_types)

            for i, data_type in enumerate(valid_data_types):
                # 更新当前任务进度
                progress = int((i / total_tasks) * 100)
                update_sync_status(
                    current_task=f"正在同步: {data_type}",
                    progress=progress,
                    completed_tasks=i
                )

                try:
                    # 根据数据类型调用不同的同步方法
                    if data_type == "stock_list":
                        results["stock_list"] = sync_service.sync_stock_basic(
                            exchange=request.exchange
                        )
                    elif data_type == "trade_calendar":
                        results["trade_calendar"] = sync_service.sync_trade_calendar(
                            exchanges=['SSE', 'SZSE'],
                            start_date=request.start_date or '19900101',
                            end_date=request.end_date or '20301231'
                        )
                    elif data_type == "daily_quotes":
                        results["daily_quotes"] = sync_service.sync_daily_data(
                            days=request.days,
                            stock_codes=request.stock_codes,
                            batch_size=request.batch_size
                        )
                    elif data_type == "weekly_quotes":
                        results["weekly_quotes"] = sync_service.sync_weekly_data(
                            days=request.days,
                            stock_codes=request.stock_codes,
                            batch_size=request.batch_size
                        )
                    elif data_type == "monthly_quotes":
                        results["monthly_quotes"] = sync_service.sync_monthly_data(
                            days=request.days,
                            stock_codes=request.stock_codes,
                            batch_size=request.batch_size
                        )
                    elif data_type == "money_flow":
                        results["money_flow"] = sync_service.sync_moneyflow_data(
                            days=request.days,
                            stock_codes=request.stock_codes,
                            batch_size=request.batch_size
                        )
                    elif data_type == "adj_factor":
                        results["adj_factor"] = sync_service.sync_adj_factor_data(
                            days=request.days,
                            stock_codes=request.stock_codes,
                            batch_size=request.batch_size
                        )
                    elif data_type == "daily_basic":
                        results["daily_basic"] = sync_service.sync_daily_basic_data(
                            days=request.days,
                            stock_codes=request.stock_codes,
                            batch_size=request.batch_size
                        )
                    elif data_type == "st_stock_list":
                        results["st_stock_list"] = sync_service.sync_st_stock_list(
                            days=request.days
                        )
                    elif data_type == "company_info":
                        results["company_info"] = sync_service.sync_company_info(
                            stock_codes=request.stock_codes
                        )
                    elif data_type == "management_info":
                        results["management_info"] = sync_service.sync_management_info(
                            days=request.days
                        )
                    elif data_type == "executive_rewards":
                        results["executive_rewards"] = sync_service.sync_executive_rewards(
                            days=request.days
                        )
                    elif data_type == "etf_basic":
                        results["etf_basic"] = sync_service.sync_etf_basic()
                    elif data_type == "etf_daily":
                        results["etf_daily"] = sync_service.sync_etf_daily_data(
                            days=request.days,
                            batch_size=request.batch_size
                        )
                    elif data_type == "daily_limit":
                        results["daily_limit"] = sync_service.sync_daily_limit_data(
                            days=request.days,
                            stock_codes=request.stock_codes,
                            batch_size=request.batch_size
                        )

                    logger.info(f"数据类型 {data_type} 同步完成")

                except Exception as e:
                    error_msg = f"数据类型 {data_type} 同步失败: {str(e)}"
                    logger.error(error_msg)
                    results[data_type] = {"error": error_msg}
                    # 继续执行其他数据类型的同步

            # 任务完成，更新最终状态
            update_sync_status(
                is_running=False,
                progress=100,
                completed_tasks=total_tasks,
                results=results
            )
            logger.info(f"批量数据同步完成，共处理 {total_tasks} 种数据类型")

        except Exception as e:
            # 任务失败，更新错误状态
            error_msg = f"批量数据同步失败: {str(e)}"
            logger.error(error_msg)
            update_sync_status(
                is_running=False,
                progress=100,
                error=error_msg
            )

    # 估算完成时间
    estimated_time = estimate_batch_time(valid_data_types, request)

    # 添加后台任务
    background_tasks.add_task(sync_task)

    return SyncResponse(
        status="started",
        message=f"开始同步 {len(valid_data_types)} 种数据类型",
        task_id=task_id,
        estimated_time=estimated_time,
        total_tasks=len(valid_data_types),
        current_progress=0
    )


def estimate_batch_time(data_types: List[str], request: BatchSyncRequest) -> int:
    """
    估算批量同步时间

    Args:
        data_types: 数据类型列表
        request: 同步请求对象

    Returns:
        int: 预估完成时间（秒）
    """
    # 基础时间估算（秒）
    time_estimates = {
        "stock_list": 10,
        "trade_calendar": 5,
        "daily_quotes": 300,
        "weekly_quotes": 60,
        "monthly_quotes": 30,
        "money_flow": 600,
        "adj_factor": 120,
        "daily_basic": 180,
        "st_stock_list": 15,
        "company_info": 20,
        "management_info": 30,
        "executive_rewards": 25,
        "etf_basic": 10,
        "etf_daily": 120,
        "daily_limit": 90
    }

    # 计算基础时间总和
    base_time = sum(time_estimates.get(dt, 30) for dt in data_types)

    # 根据股票数量调整时间估算
    stock_count = len(request.stock_codes) if request.stock_codes else 5000
    if stock_count > 1000:
        base_time = base_time * stock_count // 1000

    return max(60, base_time)  # 最少1分钟


# 保留现有的单个数据类型同步接口（向后兼容）
@router.post("/stock-basic", response_model=SyncResponse)
async def sync_stock_basic(
        request: SyncRequest,
        background_tasks: BackgroundTasks,
        sync_service: DataSyncService = Depends(get_sync_service)
):
    """
    同步股票基本信息（单个接口，向后兼容）

    内部转换为批量同步请求，只包含股票列表数据类型
    """
    batch_request = BatchSyncRequest(
        data_types=["stock_list"],
        days=request.days,
        start_date=request.start_date,
        end_date=request.end_date,
        stock_codes=request.stock_codes,
        exchange=request.exchange,
        batch_size=request.batch_size
    )
    return await batch_sync_data(batch_request, background_tasks, sync_service)


@router.post("/daily", response_model=SyncResponse)
async def sync_daily_data(
        request: SyncRequest,
        background_tasks: BackgroundTasks,
        sync_service: DataSyncService = Depends(get_sync_service)
):
    """
    同步日线数据（单个接口，向后兼容）

    内部转换为批量同步请求，只包含日线行情数据类型
    """
    batch_request = BatchSyncRequest(
        data_types=["daily_quotes"],
        days=request.days,
        start_date=request.start_date,
        end_date=request.end_date,
        stock_codes=request.stock_codes,
        exchange=request.exchange,
        batch_size=request.batch_size
    )
    return await batch_sync_data(batch_request, background_tasks, sync_service)


@router.post("/weekly", response_model=SyncResponse)
async def sync_weekly_data(
        request: SyncRequest,
        background_tasks: BackgroundTasks,
        sync_service: DataSyncService = Depends(get_sync_service)
):
    """
    同步周线数据（单个接口，向后兼容）

    内部转换为批量同步请求，只包含周线行情数据类型
    """
    batch_request = BatchSyncRequest(
        data_types=["weekly_quotes"],
        days=request.days,
        start_date=request.start_date,
        end_date=request.end_date,
        stock_codes=request.stock_codes,
        exchange=request.exchange,
        batch_size=request.batch_size
    )
    return await batch_sync_data(batch_request, background_tasks, sync_service)


@router.post("/monthly", response_model=SyncResponse)
async def sync_monthly_data(
        request: SyncRequest,
        background_tasks: BackgroundTasks,
        sync_service: DataSyncService = Depends(get_sync_service)
):
    """
    同步月线数据（单个接口，向后兼容）

    内部转换为批量同步请求，只包含月线行情数据类型
    """
    batch_request = BatchSyncRequest(
        data_types=["monthly_quotes"],
        days=request.days,
        start_date=request.start_date,
        end_date=request.end_date,
        stock_codes=request.stock_codes,
        exchange=request.exchange,
        batch_size=request.batch_size
    )
    return await batch_sync_data(batch_request, background_tasks, sync_service)


@router.post("/moneyflow", response_model=SyncResponse)
async def sync_moneyflow_data(
        request: SyncRequest,
        background_tasks: BackgroundTasks,
        sync_service: DataSyncService = Depends(get_sync_service)
):
    """
    同步资金流向数据（单个接口，向后兼容）

    内部转换为批量同步请求，只包含资金流向数据类型
    """
    batch_request = BatchSyncRequest(
        data_types=["money_flow"],
        days=request.days,
        start_date=request.start_date,
        end_date=request.end_date,
        stock_codes=request.stock_codes,
        exchange=request.exchange,
        batch_size=request.batch_size
    )
    return await batch_sync_data(batch_request, background_tasks, sync_service)


@router.post("/trade-calendar", response_model=SyncResponse)
async def sync_trade_calendar(
        exchanges: List[str] = Query(['SSE', 'SZSE']),
        start_date: str = '19900101',
        end_date: str = '20301231',
        background_tasks: BackgroundTasks = None,
        sync_service: DataSyncService = Depends(get_sync_service)
):
    """
    同步交易日历（单个接口，向后兼容）

    内部转换为批量同步请求，只包含交易日历数据类型
    """
    request = SyncRequest()
    batch_request = BatchSyncRequest(
        data_types=["trade_calendar"],
        days=30,
        start_date=start_date,
        end_date=end_date,
        stock_codes=None,
        exchange=None,
        batch_size=100
    )
    return await batch_sync_data(batch_request, background_tasks, sync_service)


@router.post("/all", response_model=SyncResponse)
async def sync_all_data(
        request: SyncRequest,
        background_tasks: BackgroundTasks,
        sync_service: DataSyncService = Depends(get_sync_service)
):
    """
    同步所有数据（全量同步）

    内部转换为批量同步请求，包含所有支持的数据类型
    """
    all_data_types = list(DATA_TYPE_MAPPING.keys())
    batch_request = BatchSyncRequest(
        data_types=all_data_types,
        days=request.days,
        start_date=request.start_date,
        end_date=request.end_date,
        stock_codes=request.stock_codes,
        exchange=request.exchange,
        batch_size=request.batch_size
    )
    return await batch_sync_data(batch_request, background_tasks, sync_service)


@router.post("/cancel")
async def cancel_sync():
    """
    取消当前同步任务

    Returns:
        Dict: 取消操作结果

    Raises:
        HTTPException: 当没有正在进行的任务时抛出异常
    """
    current_status = get_sync_status()
    if not current_status["is_running"]:
        raise HTTPException(status_code=400, detail="当前没有正在进行的同步任务")

    # 标记任务为已取消状态
    update_sync_status(
        is_running=False,
        error="任务已被用户取消"
    )

    return {"status": "cancelled", "message": "同步任务已取消"}