# -*- coding: utf-8 -*-
"""
数据模块API路由
基于混合架构设计，负责将HTTP请求路由到数据模块的业务处理层
位置：quant_server/api/routers/data_router.py
数据模块路由
"""
from typing import Optional, Dict, Any
from fastapi import APIRouter, Depends, HTTPException, status, BackgroundTasks, Query
from datetime import datetime
import logging

# 导入架构依赖
from quant_server.api.dependencies.database import get_db_session
from quant_server.api.dependencies.auth import get_current_user
from quant_server.api.dependencies.event_engine import get_event_engine
from quant_server.api.dependencies.main_engine import get_main_engine
from quant_server.api.utils import format_response
from quant_server.api.utils import paginate

# 导入数据模块的业务层处理函数
from quant_server.modules.data.handlers import (
	get_stock_list,
	get_stock_detail,
	get_historical_quotes,
	get_sync_status,
	batch_sync_data,
	quick_sync_data,
	cancel_sync,
	get_data_quality,
	get_factor_data,
	research_factor
)

# 导入数据模块的Pydantic模型
from quant_server.modules.data.schemas import (
	StockListRequest,
	StockListResponse,
	StockDetailRequest,
	StockDetailResponse,
	HistoricalQuotesRequest,
	HistoricalQuotesResponse,
	BatchSyncRequest,
	BatchSyncResponse,
	SyncStatusResponse,
	QuickSyncRequest,
	DataQualityRequest,
	DataQualityResponse,
	FactorRequest,
	FactorResponse,
	ResearchRequest,
	ResearchResponse
)

# 配置日志
logger = logging.getLogger(__name__)

# 创建路由器实例
router = APIRouter(
	prefix="/events",
	tags=["数据中心"],
	responses={
		401: {"description": "认证失败"},
		403: {"description": "权限不足"},
		500: {"description": "服务器内部错误"}
	}
)


# ==================== 基础数据查询接口 ====================

@router.get("/stocks", response_model=StockListResponse)
async def get_stocks_api (
		request: StockListRequest = Depends(),
		current_user: Dict = Depends(get_current_user),
		db_session=Depends(get_db_session)
) -> StockListResponse:
	"""
	获取股票列表

	Args:
		request: 股票列表请求参数
		current_user: 当前登录用户
		db_session: 数据库会话

	Returns:
		StockListResponse: 股票列表响应

	Raises:
		HTTPException: 业务异常
	"""
	try:
		logger.info(f"用户 {current_user.get('username')} 请求股票列表，参数: {request.dict()}")

		# 调用业务层处理函数
		result = await get_stock_list(
			session=db_session,
			request=request,
			user_id=current_user.get("id")
		)

		return result

	except Exception as e:
		logger.error(f"获取股票列表失败: {str(e)}", exc_info=True)
		raise HTTPException(
			status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
			detail=f"获取股票列表失败: {str(e)}"
		)


@router.get("/stocks/{ts_code}", response_model=StockDetailResponse)
async def get_stock_detail_api (
		ts_code: str,
		request: StockDetailRequest = Depends(),
		current_user: Dict = Depends(get_current_user),
		db_session=Depends(get_db_session)
) -> StockDetailResponse:
	"""
	获取股票详细信息

	Args:
		ts_code: 股票代码
		request: 股票详情请求参数
		current_user: 当前登录用户
		db_session: 数据库会话

	Returns:
		StockDetailResponse: 股票详情响应
	"""
	try:
		logger.info(f"用户 {current_user.get('username')} 请求股票详情，股票代码: {ts_code}")

		# 调用业务层处理函数
		result = await get_stock_detail(
			session=db_session,
			ts_code=ts_code,
			request=request,
			user_id=current_user.get("id")
		)

		return result

	except ValueError as e:
		logger.warning(f"股票不存在: {ts_code}, 错误: {str(e)}")
		raise HTTPException(
			status_code=status.HTTP_404_NOT_FOUND,
			detail=f"股票 {ts_code} 不存在"
		)
	except Exception as e:
		logger.error(f"获取股票详情失败: {str(e)}", exc_info=True)
		raise HTTPException(
			status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
			detail=f"获取股票详情失败: {str(e)}"
		)


@router.get("/quotes/historical", response_model=HistoricalQuotesResponse)
async def get_historical_quotes_api (
		request: HistoricalQuotesRequest = Depends(),
		current_user: Dict = Depends(get_current_user),
		db_session=Depends(get_db_session),
		event_engine=Depends(get_event_engine)
) -> HistoricalQuotesResponse:
	"""
	获取历史行情数据

	Args:
		request: 历史行情请求参数
		current_user: 当前登录用户
		db_session: 数据库会话
		event_engine: 事件引擎

	Returns:
		HistoricalQuotesResponse: 历史行情响应
	"""
	try:
		logger.info(f"用户 {current_user.get('username')} 请求历史行情，参数: {request.dict()}")

		# 调用业务层处理函数
		result = await get_historical_quotes(
			session=db_session,
			request=request,
			event_engine=event_engine,
			user_id=current_user.get("id")
		)

		return result

	except ValueError as e:
		logger.warning(f"参数错误: {str(e)}")
		raise HTTPException(
			status_code=status.HTTP_400_BAD_REQUEST,
			detail=str(e)
		)
	except Exception as e:
		logger.error(f"获取历史行情失败: {str(e)}", exc_info=True)
		raise HTTPException(
			status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
			detail=f"获取历史行情失败: {str(e)}"
		)


# ==================== 数据同步接口 ====================

@router.post("/sync/batch", response_model=BatchSyncResponse)
async def batch_sync_data_api (
		request: BatchSyncRequest,
		background_tasks: BackgroundTasks,
		current_user: Dict = Depends(get_current_user),
		db_session=Depends(get_db_session),
		event_engine=Depends(get_event_engine),
		main_engine=Depends(get_main_engine)
) -> BatchSyncResponse:
	"""
	批量同步数据

	Args:
		request: 批量同步请求
		background_tasks: FastAPI后台任务
		current_user: 当前登录用户
		db_session: 数据库会话
		event_engine: 事件引擎
		main_engine: 主引擎

	Returns:
		BatchSyncResponse: 批量同步响应
	"""
	try:
		logger.info(f"用户 {current_user.get('username')} 发起批量数据同步，参数: {request.dict()}")

		# 检查用户权限
		if not current_user.get("can_sync_data", False):
			raise HTTPException(
				status_code=status.HTTP_403_FORBIDDEN,
				detail="用户没有数据同步权限"
			)

		# 调用业务层处理函数
		result = await batch_sync_data(
			session=db_session,
			request=request,
			event_engine=event_engine,
			main_engine=main_engine,
			user_id=current_user.get("id"),
			background_tasks=background_tasks
		)

		return result

	except HTTPException:
		raise
	except Exception as e:
		logger.error(f"批量数据同步失败: {str(e)}", exc_info=True)
		raise HTTPException(
			status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
			detail=f"批量数据同步失败: {str(e)}"
		)


@router.post("/sync/quick", response_model=BatchSyncResponse)
async def quick_sync_data_api (
		request: QuickSyncRequest,
		background_tasks: BackgroundTasks,
		current_user: Dict = Depends(get_current_user),
		db_session=Depends(get_db_session),
		event_engine=Depends(get_event_engine)
) -> BatchSyncResponse:
	"""
	快速同步核心数据

	Args:
		request: 快速同步请求
		background_tasks: 后台任务
		current_user: 当前登录用户
		db_session: 数据库会话
		event_engine: 事件引擎

	Returns:
		BatchSyncResponse: 同步响应
	"""
	try:
		logger.info(f"用户 {current_user.get('username')} 发起快速数据同步，参数: {request.dict()}")

		# 检查用户权限
		if not current_user.get("can_sync_data", False):
			raise HTTPException(
				status_code=status.HTTP_403_FORBIDDEN,
				detail="用户没有数据同步权限"
			)

		# 调用业务层处理函数
		result = await quick_sync_data(
			session=db_session,
			request=request,
			event_engine=event_engine,
			user_id=current_user.get("id"),
			background_tasks=background_tasks
		)

		return result

	except HTTPException:
		raise
	except Exception as e:
		logger.error(f"快速数据同步失败: {str(e)}", exc_info=True)
		raise HTTPException(
			status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
			detail=f"快速数据同步失败: {str(e)}"
		)


@router.get("/sync/status", response_model=SyncStatusResponse)
async def get_sync_status_api (
		task_id: Optional[str] = Query(None, description="任务ID"),
		current_user: Dict = Depends(get_current_user),
		db_session=Depends(get_db_session)
) -> SyncStatusResponse:
	"""
	获取数据同步状态

	Args:
		task_id: 任务ID
		current_user: 当前登录用户
		db_session: 数据库会话

	Returns:
		SyncStatusResponse: 同步状态响应
	"""
	try:
		logger.info(f"用户 {current_user.get('username')} 查询数据同步状态，任务ID: {task_id}")

		# 调用业务层处理函数
		result = await get_sync_status(
			session=db_session,
			task_id=task_id,
			user_id=current_user.get("id")
		)

		return result

	except Exception as e:
		logger.error(f"获取同步状态失败: {str(e)}", exc_info=True)
		raise HTTPException(
			status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
			detail=f"获取同步状态失败: {str(e)}"
		)


@router.post("/sync/{task_id}/cancel")
async def cancel_sync_api (
		task_id: str,
		current_user: Dict = Depends(get_current_user),
		db_session=Depends(get_db_session),
		event_engine=Depends(get_event_engine)
) -> Dict[str, Any]:
	"""
	取消数据同步任务

	Args:
		task_id: 任务ID
		current_user: 当前登录用户
		db_session: 数据库会话
		event_engine: 事件引擎

	Returns:
		Dict: 取消结果
	"""
	try:
		logger.info(f"用户 {current_user.get('username')} 取消数据同步任务，任务ID: {task_id}")

		# 调用业务层处理函数
		result = await cancel_sync(
			session=db_session,
			task_id=task_id,
			event_engine=event_engine,
			user_id=current_user.get("id")
		)

		return format_response(
			success=True,
			data=result,
			message="取消同步任务成功"
		)

	except ValueError as e:
		logger.warning(f"取消同步任务失败: {str(e)}")
		raise HTTPException(
			status_code=status.HTTP_400_BAD_REQUEST,
			detail=str(e)
		)
	except Exception as e:
		logger.error(f"取消同步任务失败: {str(e)}", exc_info=True)
		raise HTTPException(
			status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
			detail=f"取消同步任务失败: {str(e)}"
		)


# ==================== 数据质量检查接口 ====================

@router.get("/quality", response_model=DataQualityResponse)
async def get_data_quality_api (
		request: DataQualityRequest = Depends(),
		current_user: Dict = Depends(get_current_user),
		db_session=Depends(get_db_session)
) -> DataQualityResponse:
	"""
	获取数据质量报告

	Args:
		request: 数据质量请求参数
		current_user: 当前登录用户
		db_session: 数据库会话

	Returns:
		DataQualityResponse: 数据质量响应
	"""
	try:
		logger.info(f"用户 {current_user.get('username')} 请求数据质量报告，参数: {request.dict()}")

		# 调用业务层处理函数
		result = await get_data_quality(
			session=db_session,
			request=request,
			user_id=current_user.get("id")
		)

		return result

	except Exception as e:
		logger.error(f"获取数据质量报告失败: {str(e)}", exc_info=True)
		raise HTTPException(
			status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
			detail=f"获取数据质量报告失败: {str(e)}"
		)


# ==================== 因子数据接口 ====================

@router.get("/factors", response_model=FactorResponse)
async def get_factor_data_api (
		request: FactorRequest = Depends(),
		current_user: Dict = Depends(get_current_user),
		db_session=Depends(get_db_session)
) -> FactorResponse:
	"""
	获取因子数据

	Args:
		request: 因子数据请求参数
		current_user: 当前登录用户
		db_session: 数据库会话

	Returns:
		FactorResponse: 因子数据响应
	"""
	try:
		logger.info(f"用户 {current_user.get('username')} 请求因子数据，参数: {request.dict()}")

		# 检查用户权限
		if not current_user.get("can_access_factor", False):
			raise HTTPException(
				status_code=status.HTTP_403_FORBIDDEN,
				detail="用户没有因子数据访问权限"
			)

		# 调用业务层处理函数
		result = await get_factor_data(
			session=db_session,
			request=request,
			user_id=current_user.get("id")
		)

		return result

	except HTTPException:
		raise
	except Exception as e:
		logger.error(f"获取因子数据失败: {str(e)}", exc_info=True)
		raise HTTPException(
			status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
			detail=f"获取因子数据失败: {str(e)}"
		)


@router.post("/factors/research", response_model=ResearchResponse)
async def research_factor_api (
		request: ResearchRequest,
		current_user: Dict = Depends(get_current_user),
		db_session=Depends(get_db_session),
		event_engine=Depends(get_event_engine)
) -> ResearchResponse:
	"""
	因子研究接口

	Args:
		request: 因子研究请求
		current_user: 当前登录用户
		db_session: 数据库会话
		event_engine: 事件引擎

	Returns:
		ResearchResponse: 因子研究响应
	"""
	try:
		logger.info(f"用户 {current_user.get('username')} 发起因子研究，参数: {request.dict()}")

		# 检查用户权限
		if not current_user.get("can_research_factor", False):
			raise HTTPException(
				status_code=status.HTTP_403_FORBIDDEN,
				detail="用户没有因子研究权限"
			)

		# 调用业务层处理函数
		result = await research_factor(
			session=db_session,
			request=request,
			event_engine=event_engine,
			user_id=current_user.get("id")
		)

		return result

	except HTTPException:
		raise
	except Exception as e:
		logger.error(f"因子研究失败: {str(e)}", exc_info=True)
		raise HTTPException(
			status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
			detail=f"因子研究失败: {str(e)}"
		)


# ==================== 健康检查接口 ====================

@router.get("/health")
async def data_module_health_check (
		current_user: Dict = Depends(get_current_user),
		db_session=Depends(get_db_session)
) -> Dict[str, Any]:
	"""
	数据模块健康检查

	Args:
		current_user: 当前登录用户
		db_session: 数据库会话

	Returns:
		Dict: 健康状态
	"""
	try:
		# 检查数据库连接
		from sqlalchemy import text
		await db_session.execute(text("SELECT 1"))

		# 检查数据表是否存在
		from sqlalchemy import inspect
		inspector = inspect(db_session.bind)
		tables = inspector.get_table_names()

		required_tables = ["stocks", "daily_quotes", "sync_tasks"]
		missing_tables = [t for t in required_tables if t not in tables]

		status = "healthy" if not missing_tables else "degraded"

		return format_response(
			success=True,
			data={
				"status": status,
				"database": "connected",
				"tables": {
					"total": len(tables),
					"missing": missing_tables
				},
				"timestamp": datetime.now().isoformat()
			},
			message="数据模块健康检查完成"
		)

	except Exception as e:
		logger.error(f"数据模块健康检查失败: {str(e)}")
		return format_response(
			success=False,
			data={
				"status": "unhealthy",
				"error": str(e),
				"timestamp": datetime.now().isoformat()
			},
			message="数据模块健康检查失败"
		)


# ==================== 数据统计接口 ====================

@router.get("/statistics")
async def get_data_statistics (
		current_user: Dict = Depends(get_current_user),
		db_session=Depends(get_db_session)
) -> Dict[str, Any]:
	"""
	获取数据统计信息

	Args:
		current_user: 当前登录用户
		db_session: 数据库会话

	Returns:
		Dict: 数据统计信息
	"""
	try:
		from sqlalchemy import text

		# 查询股票数量
		stock_count_result = await db_session.execute(
			text("SELECT COUNT(*) FROM stocks WHERE is_deleted = 0")
		)
		stock_count = stock_count_result.scalar() or 0

		# 查询行情数据数量
		quote_count_result = await db_session.execute(
			text("SELECT COUNT(*) FROM daily_quotes WHERE is_deleted = 0")
		)
		quote_count = quote_count_result.scalar() or 0

		# 查询最近同步时间
		latest_sync_result = await db_session.execute(
			text("""
                 SELECT MAX(updated_at)
                 FROM sync_tasks
                 WHERE status = 'completed'
                   AND is_deleted = 0
			     """)
		)
		latest_sync = latest_sync_result.scalar()

		# 查询数据覆盖范围
		date_range_result = await db_session.execute(
			text("""
                 SELECT MIN(trade_date), MAX(trade_date)
                 FROM daily_quotes
                 WHERE is_deleted = 0
			     """)
		)
		min_date, max_date = date_range_result.fetchone() or (None, None)

		return format_response(
			success=True,
			data={
				"stocks": {
					"total": stock_count,
					"active": stock_count  # 简化处理，实际应查询活跃股票
				},
				"quotes": {
					"daily": quote_count,
					"estimated_size_gb": round(quote_count * 0.0001, 2)  # 估算大小
				},
				"sync": {
					"latest": latest_sync.isoformat() if latest_sync else None,
					"last_24h": 0  # 简化处理，实际应统计
				},
				"coverage": {
					"start_date": min_date.isoformat() if min_date else None,
					"end_date": max_date.isoformat() if max_date else None,
					"days": (max_date - min_date).days if min_date and max_date else 0
				},
				"updated_at": datetime.now().isoformat()
			},
			message="数据统计获取成功"
		)

	except Exception as e:
		logger.error(f"获取数据统计失败: {str(e)}", exc_info=True)
		raise HTTPException(
			status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
			detail=f"获取数据统计失败: {str(e)}"
		)


# ==================== WebSocket事件订阅 ====================

@router.get("/events/subscribe")
async def subscribe_data_events (
		event_type: str = Query(..., description="事件类型: sync_progress, quality_alert, factor_update"),
		current_user: Dict = Depends(get_current_user)
) -> Dict[str, Any]:
	"""
	订阅数据事件（实际通过WebSocket实现，此处返回订阅信息）

	Args:
		event_type: 事件类型
		current_user: 当前登录用户

	Returns:
		Dict: 订阅信息
	"""
	try:
		valid_event_types = ["sync_progress", "quality_alert", "factor_update"]

		if event_type not in valid_event_types:
			raise HTTPException(
				status_code=status.HTTP_400_BAD_REQUEST,
				detail=f"无效的事件类型，可选值: {', '.join(valid_event_types)}"
			)

		# 生成订阅ID
		import uuid
		subscription_id = str(uuid.uuid4())

		return format_response(
			success=True,
			data={
				"subscription_id": subscription_id,
				"event_type": event_type,
				"ws_endpoint": f"/ws/events/{subscription_id}",
				"expires_at": (datetime.now() + timedelta(hours=24)).isoformat(),
				"user_id": current_user.get("id")
			},
			message="事件订阅创建成功，请连接WebSocket端点接收事件"
		)

	except HTTPException:
		raise
	except Exception as e:
		logger.error(f"创建事件订阅失败: {str(e)}")
		raise HTTPException(
			status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
			detail=f"创建事件订阅失败: {str(e)}"
		)