# -*- coding: utf-8 -*-
"""
数据模块API路由
基于混合架构设计，负责将HTTP请求路由到数据模块的业务处理层
位置：quant_server/api/routers/data_router.py
数据模块路由
"""
from typing import Optional, Dict
from fastapi import APIRouter, Depends, HTTPException, status, BackgroundTasks, Query
from datetime import datetime, timedelta
from sqlalchemy.ext.asyncio import AsyncSession

from starlette.responses import JSONResponse

from quant_server.utils.api_utils.response_formatter import success_response, error_response
import logging

# 导入架构依赖
from quant_server.api.dependencies.database import get_db_session
from quant_server.api.dependencies.auth import get_current_user
from quant_server.api.dependencies.event_engine import get_event_engine

# 导入数据模块的业务层处理函数
from quant_server.modules.data.handlers import (
	# 基础数据查询
	get_stock_list,
	get_stock_detail,
	get_historical_quotes,

	# 数据同步
	get_sync_status,
	batch_sync_data,
	quick_sync_data,
	cancel_sync,

	# 数据质量
	get_data_quality,

	# 因子数据
	get_factor_data,
	research_factor,
	get_factor_metadata,
	get_research_status,

	# 模块管理
	check_data_module_health,
	initialize_data_module
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
	QuickSyncResponse,
	DataQualityRequest,
	DataQualityResponse,
	FactorRequest,
	FactorResponse,
	ResearchRequest,
	ResearchResponse,
	FactorMetadataRequest,
	FactorMetadataResponse,
	FactorMetadata  # 新增：导入 FactorMetadata 模型
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
		db_session: AsyncSession = Depends(get_db_session)
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
		logger.info(f"用户 {current_user.get('username')} 请求股票列表，参数: {request.model_dump()}")

		# 调用业务层处理函数
		result = await get_stock_list(
			session=db_session,
			request=request,
			user_id=current_user.get("id")
		)

		return result

	except HTTPException:
		raise
	except ValueError as e:
		logger.warning(f"参数错误: {str(e)}")
		raise HTTPException(
			status_code=status.HTTP_400_BAD_REQUEST,
			detail=str(e)
		)
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
		db_session: AsyncSession = Depends(get_db_session)
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

	except HTTPException:
		raise
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
		db_session: AsyncSession = Depends(get_db_session)
) -> HistoricalQuotesResponse:
	"""
	获取历史行情数据

	Args:
		request: 历史行情请求参数
		current_user: 当前登录用户
		db_session: 数据库会话

	Returns:
		HistoricalQuotesResponse: 历史行情响应
	"""
	try:
		logger.info(f"用户 {current_user.get('username')} 请求历史行情，参数: {request.model_dump()}")

		# 调用业务层处理函数
		result = await get_historical_quotes(
			session=db_session,
			request=request,
			user_id=current_user.get("id")
		)

		return result

	except HTTPException:
		raise
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
		db_session: AsyncSession = Depends(get_db_session),
		event_engine=Depends(get_event_engine)
) -> BatchSyncResponse:
	"""
	批量同步数据

	Args:
		request: 批量同步请求
		background_tasks: FastAPI后台任务
		current_user: 当前登录用户
		db_session: 数据库会话
		event_engine: 事件引擎

	Returns:
		BatchSyncResponse: 批量同步响应
	"""
	try:
		logger.info(f"用户 {current_user.get('username')} 发起批量数据同步，参数: {request.model_dump()}")

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


@router.post("/sync/quick", response_model=QuickSyncResponse)
async def quick_sync_data_api (
		request: QuickSyncRequest,
		background_tasks: BackgroundTasks,
		current_user: Dict = Depends(get_current_user),
		db_session: AsyncSession = Depends(get_db_session),
		event_engine=Depends(get_event_engine)
) -> QuickSyncResponse:
	"""
	快速同步核心数据

	Args:
		request: 快速同步请求
		background_tasks: 后台任务
		current_user: 当前登录用户
		db_session: 数据库会话
		event_engine: 事件引擎

	Returns:
		QuickSyncResponse: 同步响应
	"""
	try:
		logger.info(f"用户 {current_user.get('username')} 发起快速数据同步，参数: {request.model_dump()}")

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
		db_session: AsyncSession = Depends(get_db_session)
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
		db_session: AsyncSession = Depends(get_db_session),
		event_engine=Depends(get_event_engine)
) -> JSONResponse:
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

		return success_response(
			message="取消同步任务成功",
			data=result
		)

	except HTTPException:
		raise
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
		db_session: AsyncSession = Depends(get_db_session)
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
		logger.info(f"用户 {current_user.get('username')} 请求数据质量报告，参数: {request.model_dump()}")

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
		db_session: AsyncSession = Depends(get_db_session)
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
		logger.info(f"用户 {current_user.get('username')} 请求因子数据，参数: {request.model_dump()}")

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


@router.get("/factors/metadata", response_model=FactorMetadataResponse)
async def get_factor_metadata_api (
		request: FactorMetadataRequest = Depends(),
		current_user: Dict = Depends(get_current_user),
		db_session: AsyncSession = Depends(get_db_session)
) -> FactorMetadataResponse:
	"""
	获取因子元数据

	Args:
		request: 因子元数据请求参数
		current_user: 当前登录用户
		db_session: 数据库会话

	Returns:
		FactorMetadataResponse: 因子元数据响应
	"""
	try:
		logger.info(f"用户 {current_user.get('username')} 请求因子元数据，参数: {request.model_dump()}")

		# 检查用户权限
		if not current_user.get("can_access_factor", False):
			raise HTTPException(
				status_code=status.HTTP_403_FORBIDDEN,
				detail="用户没有因子数据访问权限"
			)

		# 调用业务层处理函数获取字典列表
		metadata_dicts = await get_factor_metadata(
			session=db_session,
			factor_code=request.factor_name,
			category=request.factor_category,
			user_id=current_user.get("id")
		)

		# 将字典列表转换为 FactorMetadata 模型列表
		metadata_list = []
		for item in metadata_dicts:
			# 修复问题1：item是字典，直接访问字典键
			category_value = item.get('category')
			# 如果category有value属性（比如是枚举），则获取value，否则直接使用
			if hasattr(category_value, 'value'):
				item['category'] = category_value.value
			else:
				item['category'] = category_value

			# 创建 FactorMetadata 模型实例
			metadata_item = FactorMetadata(**item)
			metadata_list.append(metadata_item)

		# 计算分页信息
		total_count = len(metadata_list)
		page = request.page
		page_size = request.page_size
		start_idx = (page - 1) * page_size
		end_idx = start_idx + page_size

		# 应用分页
		paginated_metadata = metadata_list[start_idx:end_idx]

		# 按类别统计
		by_category = {}
		for item in metadata_list:
			# 修复问题2：item现在是FactorMetadata对象
			category = item.category
			by_category[category] = by_category.get(category, 0) + 1

		return FactorMetadataResponse(
			success=True,
			metadata_list=paginated_metadata,  # 修复问题2：现在这是FactorMetadata对象列表
			pagination={
				"page": page,
				"page_size": page_size,
				"total": total_count,
				"total_pages": (total_count + page_size - 1) // page_size
			},
			summary={
				"total_factors": total_count,
				"by_category": by_category
			},
			message="获取因子元数据成功"
		)

	except HTTPException:
		raise
	except Exception as e:
		logger.error(f"获取因子元数据失败: {str(e)}", exc_info=True)
		raise HTTPException(
			status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
			detail=f"获取因子元数据失败: {str(e)}"
		)


@router.post("/factors/research", response_model=ResearchResponse)
async def research_factor_api (
		request: ResearchRequest,
		background_tasks: BackgroundTasks,
		current_user: Dict = Depends(get_current_user),
		db_session: AsyncSession = Depends(get_db_session),
		event_engine=Depends(get_event_engine)
) -> ResearchResponse:
	"""
	因子研究接口

	Args:
		request: 因子研究请求
		background_tasks: 后台任务
		current_user: 当前登录用户
		db_session: 数据库会话
		event_engine: 事件引擎

	Returns:
		ResearchResponse: 因子研究响应
	"""
	try:
		logger.info(f"用户 {current_user.get('username')} 发起因子研究，参数: {request.model_dump()}")

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
			user_id=current_user.get("id"),
			background_tasks=background_tasks
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


@router.get("/factors/research/status")
async def get_research_status_api (
		research_id: Optional[str] = Query(None, description="研究ID"),
		current_user: Dict = Depends(get_current_user),
		db_session: AsyncSession = Depends(get_db_session)
) -> JSONResponse:
	"""
	获取因子研究状态

	Args:
		research_id: 研究ID
		current_user: 当前登录用户
		db_session: 数据库会话

	Returns:
		JSONResponse: 研究状态
	"""
	try:
		logger.info(f"用户 {current_user.get('username')} 查询因子研究状态，研究ID: {research_id}")

		# 检查用户权限
		if not current_user.get("can_research_factor", False):
			raise HTTPException(
				status_code=status.HTTP_403_FORBIDDEN,
				detail="用户没有因子研究权限"
			)

		# 调用业务层处理函数
		status_data = await get_research_status(
			session=db_session,
			research_id=research_id,
			user_id=current_user.get("id")
		)

		return success_response(
			data=status_data,
			message="获取研究状态成功"
		)

	except HTTPException:
		raise
	except Exception as e:
		logger.error(f"获取研究状态失败: {str(e)}", exc_info=True)
		raise HTTPException(
			status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
			detail=f"获取研究状态失败: {str(e)}"
		)


# ==================== 模块管理接口 ====================

@router.get("/health")
async def data_module_health_check (
		current_user: Dict = Depends(get_current_user),
		db_session: AsyncSession = Depends(get_db_session)
) -> JSONResponse:
	"""
	数据模块健康检查

	Args:
		current_user: 当前登录用户
		db_session: 数据库会话

	Returns:
		JSONResponse: 健康状态
	"""
	try:
		logger.info(f"用户 {current_user.get('username')} 请求数据模块健康检查")

		# 调用业务层处理函数
		health_status = await check_data_module_health(
			session=db_session,
		)

		return success_response(
			data=health_status,
			message="数据模块健康检查完成"
		)

	except Exception as e:
		logger.error(f"数据模块健康检查失败: {str(e)}", exc_info=True)
		return error_response(
			message="数据模块健康检查失败",
			data={
				"status": "unhealthy",
				"error": str(e),
				"timestamp": datetime.now().isoformat()
			},
			status_code=500
		)


@router.post("/initialize")
async def initialize_data_module_api (
		current_user: Dict = Depends(get_current_user),
		db_session: AsyncSession = Depends(get_db_session),
) -> JSONResponse:
	"""
	初始化数据模块

	Args:
		current_user: 当前登录用户
		db_session: 数据库会话

	Returns:
		JSONResponse: 初始化结果
	"""
	try:
		logger.info(f"用户 {current_user.get('username')} 初始化数据模块")

		# 检查用户权限（通常需要管理员权限）
		if not current_user.get("is_admin", False):
			raise HTTPException(
				status_code=status.HTTP_403_FORBIDDEN,
				detail="只有管理员可以初始化数据模块"
			)

		# 调用业务层处理函数
		init_result = await initialize_data_module(
			session=db_session,
		)

		return success_response(
			data=init_result,
			message="数据模块初始化完成"
		)

	except HTTPException:
		raise
	except Exception as e:
		logger.error(f"数据模块初始化失败: {str(e)}", exc_info=True)
		raise HTTPException(
			status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
			detail=f"数据模块初始化失败: {str(e)}"
		)


# ==================== 数据统计接口 ====================

@router.get("/statistics")
async def get_data_statistics (
		current_user: Dict = Depends(get_current_user),
		db_session: AsyncSession = Depends(get_db_session)
) -> JSONResponse:
	"""
	获取数据统计信息

	Args:
		current_user: 当前登录用户
		db_session: 数据库会话

	Returns:
		JSONResponse: 数据统计信息
	"""
	try:
		logger.info(f"用户 {current_user.get('username')} 请求数据统计信息")

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
		date_range = date_range_result.fetchone()

		# 安全处理日期范围
		if date_range and date_range[0] and date_range[1]:
			min_date, max_date = date_range
			days = (max_date - min_date).days
		else:
			min_date, max_date, days = None, None, 0

		return success_response(
			message="数据统计获取成功",
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
					"days": days
				},
				"updated_at": datetime.now().isoformat()
			}
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
) -> JSONResponse:
	"""
	订阅数据事件（实际通过WebSocket实现，此处返回订阅信息）

	Args:
		event_type: 事件类型
		current_user: 当前登录用户

	Returns:
		JSONResponse: 订阅信息
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

		return success_response(
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