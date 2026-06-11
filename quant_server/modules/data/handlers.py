# -*- coding: utf-8 -*-
"""
数据模块业务处理层 (Handlers)
基于混合架构设计的量化交易系统 - 数据模块
位置：quant_server/modules/data/handlers.py

设计原则：
1. 分层架构：作为API层与业务逻辑层的桥梁
2. 依赖注入：通过参数接收所需依赖（session、event_engine等）
3. 单一职责：每个函数只处理一个特定的API请求
4. 错误处理：统一异常处理，返回友好的错误信息
5. 事件驱动：通过事件引擎进行模块间通信

文件结构：
- 因子数据相关处理函数
- 因子研究相关处理函数
- 基础数据查询处理函数
- 数据同步处理函数
- 数据质量处理函数
- 辅助私有方法
- 模块健康检查与初始化

修复说明：
1. 修复了请求/响应模型属性不匹配的问题
2. 修复了Repository方法调用问题
3. 修复了事件引擎调用问题
4. 修复了参数传递错误
5. 统一了缩进和代码风格
6. 修复了类型注解和异步调用问题
7. 修复了Settings属性访问问题
8. 修复了Redis缓存连接问题
9. 修复了模型属性访问问题
"""
import logging
import uuid
from datetime import datetime, timedelta
from typing import List, Dict, Any, Optional

from fastapi import BackgroundTasks
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

# ==================== 核心基础设施导入 ====================
# 事件引擎
from core.engines.system.event_engine import EventEngine
# 异常处理
from core.exceptions.business_exceptions import (
	ValidationException,
	ResourceNotFoundException,
	PermissionDeniedException,
	BusinessException
)
# ==================== 数据模块内部组件导入 ====================
# 事件定义
from modules.data.events import (
	DataSyncStartedEvent,
	DataSyncProgressEvent,
	DataSyncCompletedEvent,
	DataSyncFailedEvent,
	DataResearchStartedEvent,
	DataResearchProgressEvent,
	DataResearchCompletedEvent
)
# Schema定义（API请求/响应模型）
from modules.data.schemas import (
	# 基础数据查询
	StockListRequest,
	StockListResponse,
	StockDetailRequest,
	StockDetailResponse,
	HistoricalQuotesRequest,
	HistoricalQuotesResponse,

	# 数据同步
	BatchSyncRequest,
	BatchSyncResponse,
	SyncStatusResponse,
	QuickSyncRequest,
	QuickSyncResponse,

	# 数据质量
	DataQualityRequest,
	DataQualityResponse,

	# 因子数据
	FactorRequest,
	FactorResponse,
	ResearchRequest,
	ResearchResponse,
	FactorMetadata, FactorCategory,
)
from modules.data.services.quality_service import DataQualityService
# 服务层组件
from modules.data.services.research_service import FactorResearchService
from modules.data.services.sync_service import DataSyncService
from shared.cache.redis_cache import RedisCache
# 配置与缓存
from shared.config.config_manager import ConfigSettings as Settings, get_config
# ==================== 数据模型导入 ====================
from shared.database.models.data_models import StockBasic
# 分析领域Repository - 因子数据
from shared.database.repositories.analysis.factor.factor_data_repo import FactorDataRepository
from shared.database.repositories.analysis.factor.factor_definition_repo import FactorDefinitionRepository
# ==================== 共享层组件导入 ====================
# 市场数据Repository - 基础信息
from shared.database.repositories.market.basic.stock_repo import StockBasicRepository
# 市场数据Repository - 行情数据
from shared.database.repositories.market.quote.stock_daily_repo import StockDailyRepository
# 运营领域Repository - 任务管理
from shared.database.repositories.operation.task.data_sync_task_repo import DataSyncTaskRepository
from shared.database.repositories.operation.task.factor_research_repo import FactorResearchRepository
from shared.database.session.session_manager import get_session_manager

# ==================== 日志配置 ====================
logger = logging.getLogger(__name__)


# ==================== 因子数据相关处理函数 ====================
async def get_factor_data (
		session: AsyncSession,
		request: FactorRequest,
		user_id: str,
		settings: Settings = get_config().settings
) -> FactorResponse:
	"""
	获取因子数据 - 支持缓存、分页、过滤的高级查询

	Args:
		session: 数据库会话
		request: 因子数据请求参数
		user_id: 当前用户ID
		settings: 系统配置

	Returns:
		FactorResponse: 因子数据响应

	Raises:
		ValidationException: 参数验证失败
		ResourceNotFoundException: 资源未找到
		BusinessException: 业务逻辑异常
	"""
	try:
		logger.info(
			f"用户 {user_id} 请求因子数据: "
			f"股票={request.ts_code}, "
			f"日期范围={request.start_date} 至 {request.end_date}, "
			f"页码={request.page}, 页大小={request.page_size}"
		)

		# 1. 参数验证
		await _validate_factor_request(request)

		# 2. 尝试从缓存获取（优化性能）
		cache_key = (
			f"factor:{request.ts_code}:"
			f"{request.start_date}:{request.end_date}:"
			f"{request.page}:{request.page_size}"
		)

		cached_result = await _get_factor_data_from_cache(cache_key, settings)
		if cached_result:
			logger.info(f"缓存命中: {cache_key}")
			return FactorResponse(**cached_result)

		# 3. 数据库查询 - 使用共享Repository
		factor_data_repo = FactorDataRepository(session)
		factor_def_repo = FactorDefinitionRepository(session)

		# 构建查询条件
		kwargs = {}
		if request.ts_code:
			kwargs["ts_code"] = request.ts_code

		# 执行分页查询
		factors = await factor_data_repo.get_many(
			skip=(request.page - 1) * request.page_size,
			limit=request.page_size,
			**kwargs,
		)
		# Post-filter by date range (TODO: add comparison filter support to BaseRepository)
		if request.start_date:
			factors = [f for f in factors if hasattr(f, "trade_date") and f.trade_date >= request.start_date]
		if request.end_date:
			factors = [f for f in factors if hasattr(f, "trade_date") and f.trade_date <= request.end_date]
		# Sort by trade_date desc, ts_code
		factors = sorted(
			factors,
			key=lambda x: (getattr(x, "trade_date", datetime.min), getattr(x, "ts_code", "")),
			reverse=True,
		)

		# 获取总记录数（用于分页）
		total_count = await factor_data_repo.count()

		# 数据转换：ORM对象 -> 字典
		factor_items = []
		for factor in factors:
			if factor:
				factor_items.append({
					"ts_code": factor.ts_code,
					"trade_date": factor.trade_date.isoformat() if factor.trade_date else None,
					"factor_name": factor.factor_name,
					"factor_value": float(factor.factor_value) if factor.factor_value is not None else None,
					"z_score": None,  # 这些字段需要从业务逻辑计算
					"percentile": None,
					"rank": None,
					"universe_rank": None,
					"updated_at": factor.updated_at.isoformat() if factor.updated_at else None
				})

		# 获取可用的公开因子列表
		available_factors = await factor_def_repo.get_public_factors()
		available_factor_objects = []
		for factor in available_factors:
			# 创建 FactorMetadata 对象
			factor_metadata = FactorMetadata(
				factor_name=factor.factor_name,
				display_name=factor.factor_name,  # 如果没有 display_name，使用 factor_name
				description=factor.description or "",
				category=FactorCategory(factor.category) if factor.category else FactorCategory.VALUE,
				formula=factor.formula,
				data_source="internal",  # 根据实际情况设置
				update_frequency="daily",  # 根据实际情况设置
				last_update=datetime.now()
			)
			available_factor_objects.append(factor_metadata)

		# 获取因子元数据
		factor_metadata = None
		if factor_items:
			# 取第一个因子的元数据
			factor_name = factor_items[0].get('factor_name')
			if factor_name:
				metadata_list = await get_factor_metadata(
					session=session,
					factor_code=factor_name,
					user_id=user_id
				)
				if metadata_list:
					# 直接创建FactorMetadata对象
					factor_metadata = FactorMetadata(**metadata_list[0])

		# 构建响应
		response = FactorResponse(
			success=True,
			ts_code=request.ts_code,
			factor_values=factor_items,
			metadata=factor_metadata,
			statistics={
				"total": total_count,
				"page": request.page,
				"page_size": request.page_size
			},
			pagination={
				"page": request.page,
				"page_size": request.page_size,
				"total": total_count,
				"total_pages": ((total_count or 0) + (request.page_size or 10) - 1) // (request.page_size or 10)
			},
			available_factors=available_factor_objects,
			message="获取因子数据成功"
		)

		# 10. 缓存结果（5分钟TTL）
		await _cache_factor_data(cache_key, response.model_dump(), settings, ttl=300)

		logger.info(f"成功返回因子数据，共 {total_count} 条记录，当前页 {len(factor_items)} 条")
		return response

	except (ValidationException, ResourceNotFoundException) as e:
		logger.warning(f"因子数据查询失败: {str(e)}")
		raise
	except Exception as e:
		logger.error(f"因子数据查询异常: {str(e)}", exc_info=True)
		raise BusinessException(f"获取因子数据失败: {str(e)}")


async def research_factor (
		session: AsyncSession,
		request: ResearchRequest,
		event_engine: EventEngine,
		user_id: str,
		background_tasks: BackgroundTasks,
		settings: Settings = get_config().settings
) -> ResearchResponse:
	"""
	执行因子研究任务 - 修复版本

	Args:
		session: 数据库会话
		request: 因子研究请求参数
		event_engine: 事件引擎
		user_id: 当前用户ID
		background_tasks: 后台任务管理器
		settings: 系统配置

	Returns:
		ResearchResponse: 因子研究响应

	Raises:
		ValidationException: 参数验证失败
		BusinessException: 业务逻辑异常
	"""
	try:
		logger.info(
			f"用户 {user_id} 发起因子研究: "
			f"因子列表={request.factor_names}, "
			f"股票池数量={len(request.universe)}"
		)

		# 1. 参数验证
		await _validate_research_request(request)

		# 2. 创建研究任务ID
		research_id: str = f"research_{uuid.uuid4().hex[:8]}"

		# 3. 创建任务记录（使用运营领域的Repository）
		research_repo = FactorResearchRepository(session)

		# 使用ResearchRequest中的正确属性
		research_name = f"因子研究_{request.factor_names[0]}" if request.factor_names else "未命名研究"
		factor_name = request.factor_names[0] if request.factor_names else "unknown"

		# 创建研究任务记录 - 使用正确的参数名
		research_task_data = {
			"research_id": research_id,
			"research_name": research_name,
			"factor_name": factor_name,
			"user_id": user_id,
			"status": "pending",
			"progress": 0.0,
			"calculated_count": 0,
			"total_stocks": len(request.universe) if request.universe else 0,
			"start_date": request.start_date,
			"end_date": request.end_date,
			"parameters": {
				"factor_names": request.factor_names,
				"universe": request.universe,
				"frequency": request.frequency,
				"group_count": request.group_count,
				"analysis_type": request.analysis_type
			},
			"analysis_type": request.analysis_type or "ic_analysis",
			"created_at": datetime.now()
		}

		research_task = await research_repo.create(research_task_data)

		# 4. 发布研究开始事件
		event = DataResearchStartedEvent(
			research_id=research_id,
			research_type=request.analysis_type or "ic_analysis",
			target_factors=request.factor_names,
			user_id=user_id,
			timestamp=datetime.now(),
			source="data_module"
		)
		# EventEngine的put方法应该接受Event子类
		await event_engine.put(event)  # type: ignore

		# 5. 默认使用异步执行
		logger.info(f"异步执行因子研究: {research_id}")

		# 更新任务状态为运行中
		update_data = {
			"status": "running",
			"started_at": datetime.now()
		}
		await research_repo.update(research_task.id, update_data)

		# 将研究任务加入后台任务队列
		background_tasks.add_task(
			_execute_async_factor_research,
			session=session,
			research_id=research_id,
			request=request,
			event_engine=event_engine,
			user_id=user_id
		)

		# 返回异步任务响应
		return ResearchResponse(
			success=True,
			research_id=research_id,
			analysis_type=request.analysis_type or "ic_analysis",  # 必须字段
			parameters={
				"factor_names": request.factor_names,
				"universe": request.universe,
				"start_date": request.start_date.isoformat(),
				"end_date": request.end_date.isoformat(),
				"frequency": request.frequency,
				"group_count": request.group_count,
				"analysis_type": request.analysis_type
			},
			# 以下字段在异步任务开始时还没有结果，设为 None
			ic_analysis=None,
			quantile_analysis=None,
			correlation_analysis=None,
			summary={},  # 空的摘要
			generated_at=datetime.now(),
			# 异步任务特定字段
			status="started",
			created_at=datetime.now(),
			estimated_time=_estimate_research_time(request),
			factor_name=factor_name,
			message="因子研究已开始，将在后台执行"
		)

	except ValidationException as ve:
		logger.warning(f"因子研究参数验证失败: {str(ve)}")
		raise
	except Exception as e:
		logger.error(f"因子研究任务创建失败: {str(e)}", exc_info=True)

		# 记录失败状态
		if "research_id" in locals():
			research_repo = FactorResearchRepository(session)
			research_task_result = await research_repo.get_by_research_id(locals()["research_id"])
			if research_task_result.success and research_task_result.data:
				update_data = {
					"status": "failed",
					"error_message": str(e)
				}
				await research_repo.update(research_task_result.data.id, update_data)

		raise BusinessException(f"创建因子研究任务失败: {str(e)}")


async def get_factor_metadata (
		session: AsyncSession,
		factor_code: Optional[str] = None,
		category: Optional[str] = None,
		is_public: Optional[bool] = True,
		user_id: str = None
) -> List[Dict[str, Any]]:
	"""
	获取因子元数据信息 - 支持按代码、类别、公开性过滤

	Args:
		session: 数据库会话
		factor_code: 因子代码（可选，精确匹配）
		category: 因子类别（可选，过滤条件）
		is_public: 是否只返回公开因子（默认True）
		user_id: 当前用户ID（用于日志记录）

	Returns:
		List[Dict]: 因子元数据列表，包含因子定义信息

	Raises:
		ResourceNotFoundException: 指定的因子代码不存在
		BusinessException: 查询过程发生异常
	"""
	try:
		logger.info(
			f"用户 {user_id} 请求因子元数据: "
			f"因子代码={factor_code}, 类别={category}, 公开={is_public}"
		)

		factor_def_repo = FactorDefinitionRepository(session)

		if factor_code:
			# 精确查询：根据因子代码获取单个因子定义
			factor_def = await factor_def_repo.get_by_code(factor_code)
			if not factor_def:
				raise ResourceNotFoundException(f"因子 '{factor_code}' 不存在")

			factors = [factor_def]
		else:
			# 模糊查询：根据条件搜索因子定义
			factors = await factor_def_repo.search_factors(
				keyword=factor_code,  # 使用factor_code作为关键词搜索
				category=category,
				is_public=is_public,
				is_active=True,
				limit=100
			)

		# 数据转换：ORM对象 -> 字典
		metadata_list = []
		for factor in factors:
			metadata = {
				"factor_code": factor.factor_code,
				"factor_name": factor.factor_name,
				"factor_type": factor.factor_type,
				"category": factor.category,
				"description": factor.description,
				"formula": factor.formula,
				"parameters": factor.parameters,
				"data_requirements": factor.data_requirements,
				"output_type": factor.output_type,
				"calculation_frequency": factor.calculation_frequency,
				"is_public": factor.is_public,
				"is_active": factor.is_active,
				"created_by": factor.created_by,
				"created_at": factor.created_at.isoformat() if factor.created_at else None,
				"updated_at": factor.updated_at.isoformat() if factor.updated_at else None
			}
			metadata_list.append(metadata)

		logger.info(f"成功返回因子元数据，共 {len(metadata_list)} 条记录")
		return metadata_list

	except ResourceNotFoundException as rnf:
		logger.warning(f"因子资源未找到: {str(rnf)}")
		raise
	except Exception as e:
		logger.error(f"获取因子元数据失败: {str(e)}", exc_info=True)
		raise BusinessException(f"查询因子元数据失败: {str(e)}")


async def get_research_status (
		session: AsyncSession,
		research_id: Optional[str] = None,
		user_id: str = None
) -> Dict[str, Any]:
	"""
	获取因子研究任务状态 - 支持指定任务或用户最近任务查询

	Args:
		session: 数据库会话
		research_id: 研究任务ID（可选，如未指定则返回用户最近任务）
		user_id: 当前用户ID（用于权限验证和查询）

	Returns:
		Dict: 研究任务状态信息，包含进度、结果等

	Raises:
		ResourceNotFoundException: 指定的研究任务不存在
		PermissionDeniedException: 用户无权查看该研究任务
		BusinessException: 查询过程发生异常
	"""
	try:
		logger.info(
			f"用户 {user_id} 请求研究状态: "
			f"研究ID={research_id if research_id else '用户最近任务'}"
		)

		research_repo = FactorResearchRepository(session)

		if research_id:
			# 查询指定研究任务
			result = await research_repo.get_by_research_id(research_id)
			if not result.success or not result.data:
				raise ResourceNotFoundException(f"研究任务 '{research_id}' 不存在")

			research_task = result.data

			# 权限验证：用户只能查看自己的研究任务
			if research_task.user_id != user_id:
				raise PermissionDeniedException("无权查看其他用户的研究任务")

			# 构建详细状态信息
			status_info = {
				"research_id": research_task.research_id,
				"research_name": research_task.research_name,
				"factor_name": research_task.factor_name,
				"status": research_task.status,
				"progress": research_task.progress * 100 if research_task.progress else 0,  # 转换为百分比
				"calculated_count": research_task.calculated_count or 0,
				"total_stocks": research_task.total_stocks or 0,
				"start_date": research_task.start_date.isoformat() if research_task.start_date else None,
				"end_date": research_task.end_date.isoformat() if research_task.end_date else None,
				"started_at": research_task.started_at.isoformat() if research_task.started_at else None,
				"completed_at": research_task.completed_at.isoformat() if research_task.completed_at else None,
				"error_message": research_task.error_message,
				"result": research_task.result,
				"summary": research_task.summary,
				"report": research_task.report,
				"created_at": research_task.created_at.isoformat() if research_task.created_at else None
			}

			return status_info

		else:
			# 查询用户最近的研究任务（最多10个）
			result = await research_repo.get_user_research_tasks(
				user_id=user_id,
			)

			# 构建任务概览列表
			recent_tasks = []
			if result.success and result.data:
				research_tasks = result.data.items if hasattr(result.data, "items") else result.data
				for task in research_tasks:
					recent_tasks.append({
						"research_id": task.research_id,
						"research_name": task.research_name,
						"factor_name": task.factor_name,
						"status": task.status,
						"progress": task.progress * 100 if task.progress else 0,
						"started_at": task.started_at.isoformat() if task.started_at else None,
						"completed_at": task.completed_at.isoformat() if task.completed_at else None,
						"created_at": task.created_at.isoformat() if task.created_at else None
					})

			return {
				"recent_tasks": recent_tasks,
				"total_count": len(recent_tasks)
			}

	except (ResourceNotFoundException, PermissionDeniedException) as e:
		logger.warning(f"研究状态查询失败: {str(e)}")
		raise
	except Exception as e:
		logger.error(f"获取研究状态失败: {str(e)}", exc_info=True)
		raise BusinessException(f"查询研究状态失败: {str(e)}")


# ==================== 基础数据查询处理函数 ====================

async def get_stock_list (
		session: AsyncSession,
		request: StockListRequest,
		user_id: str
) -> StockListResponse:
	"""
	获取股票列表 - 支持搜索、过滤、分页

	Args:
		session: 数据库会话
		request: 股票列表查询参数
		user_id: 当前用户ID

	Returns:
		StockListResponse: 股票列表响应，包含分页信息

	Raises:
		BusinessException: 查询过程发生异常
	"""
	try:
		logger.info(
			f"用户 {user_id} 请求股票列表: "
			f"搜索词={request.search}, 市场={request.market}, "
			f"行业={request.industry}, 页码={request.page}, 页大小={request.page_size}"
		)

		# 使用市场数据Repository
		stock_repo = StockBasicRepository(session)

		# 构建查询过滤器 - 使用正确的模型引用
		filters = []
		if request.search:
			filters.append(
				(StockBasic.ts_code.like(f"%{request.search}%")) |
				(StockBasic.name.like(f"%{request.search}%"))
			)
		if request.market:
			filters.append(StockBasic.market == request.market)
		if request.industry:
			filters.append(StockBasic.industry == request.industry)
		if request.list_status:
			filters.append(StockBasic.list_status == request.list_status)
		# 注意：StockListRequest中没有is_active字段

		# 使用配置化的分页参数（获取实际有效的分页值）
		effective_page = request.get_effective_page()
		effective_page_size = request.get_effective_page_size()

		# 执行分页查询
		stocks = await stock_repo.get_many(
			skip=(effective_page - 1) * effective_page_size,
			limit=effective_page_size,
		)
		# Sort by ts_code (TODO: add order_by support to BaseRepository)
		stocks = sorted(stocks, key=lambda x: getattr(x, "ts_code", ""))

		# 获取总记录数
		total_count = await stock_repo.count()

		# 数据转换：ORM对象 -> 字典
		stock_items = []
		for stock in stocks:
			stock_items.append({
				"ts_code": stock.ts_code,
				"symbol": stock.symbol,
				"name": stock.name,
				"area": stock.area,
				"industry": stock.industry,
				"market": stock.market,
				"list_date": stock.list_date.isoformat() if stock.list_date else None,
				"is_hs": stock.is_hs,
				"is_active": stock.is_active if hasattr(stock, "is_active") else True,
				"updated_at": stock.updated_at.isoformat() if stock.updated_at else None
			})

		# 构建响应
		response = StockListResponse(
			success=True,
			data=stock_items,
			pagination={
				"page": request.page,
				"page_size": request.page_size,
				"total": total_count,
				"total_pages": (
						               total_count + request.get_effective_page_size() - 1) // request.get_effective_page_size()
			},
			message="获取股票列表成功"
		)

		logger.info(f"成功返回股票列表，共 {total_count} 条记录，当前页 {len(stock_items)} 条")
		return response

	except Exception as e:
		logger.error(f"获取股票列表失败: {str(e)}", exc_info=True)
		raise BusinessException(f"查询股票列表失败: {str(e)}")


async def get_stock_detail (
		session: AsyncSession,
		ts_code: str,
		request: StockDetailRequest,
		user_id: str
) -> StockDetailResponse:
	"""
	获取股票详细信息 - 包含基础信息和最新行情

	Args:
		session: 数据库会话
		ts_code: 股票TS代码
		request: 股票详情查询参数
		user_id: 当前用户ID

	Returns:
		StockDetailResponse: 股票详情响应

	Raises:
		ResourceNotFoundException: 股票不存在
		BusinessException: 查询过程发生异常
	"""
	try:
		logger.info(f"用户 {user_id} 请求股票详情: {ts_code}")

		# 1. 获取股票基础信息
		stock_repo = StockBasicRepository(session)
		stock = await stock_repo.get_by_ts_code(ts_code)

		if not stock:
			raise ResourceNotFoundException(f"股票 '{ts_code}' 不存在")

		# 2. 获取最新行情（如果请求中包含）
		latest_quote = None
		if request.include_quote:  # 使用正确的属性名
			quote_repo = StockDailyRepository(session)
			quotes = await quote_repo.get_many(
				ts_code=ts_code,
				limit=1
			)
			if quotes:
				# 按日期倒序排列取最新
				latest_quote = max(quotes, key=lambda x: x.trade_date if x.trade_date else None)

		# 3. 构建基础信息
		basic_info = {
			"ts_code": stock.ts_code,
			"symbol": stock.symbol,
			"name": stock.name,
			"area": stock.area,
			"industry": stock.industry,
			"market": stock.market,
			"list_date": stock.list_date.isoformat() if stock.list_date else None,
			"is_hs": stock.is_hs
		}

		# 4. 构建响应数据
		from modules.data.schemas import StockBasicInfo, QuoteData

		# 转换为StockBasicInfo对象
		basic_info_obj = StockBasicInfo(
			ts_code=basic_info["ts_code"],
			symbol=basic_info["symbol"],
			name=basic_info["name"],
			area=basic_info["area"],
			industry=basic_info["industry"],
			market=basic_info["market"],
			list_date=basic_info["list_date"],
			is_hs=basic_info["is_hs"]
		)

		quotes = None
		if latest_quote and request.include_quote:
			quote_data = QuoteData(
				trade_date=latest_quote.trade_date,
				open=float(latest_quote.open) if latest_quote.open else None,
				high=float(latest_quote.high) if latest_quote.high else None,
				low=float(latest_quote.low) if latest_quote.low else None,
				close=float(latest_quote.close) if latest_quote.close else None,
				pre_close=float(latest_quote.pre_close) if latest_quote.pre_close else None,
				change=float(latest_quote.change) if latest_quote.change else None,
				pct_chg=float(latest_quote.pct_chg) if latest_quote.pct_chg else None,
				vol=float(latest_quote.vol) if latest_quote.vol else None,
				amount=float(latest_quote.amount) if latest_quote.amount else None
			)
			quotes = [quote_data]

		# 5. 创建并返回响应对象
		logger.info(f"成功返回股票 '{ts_code}' 的详细信息")
		return StockDetailResponse(
			success=True,
			basic_info=basic_info_obj,
			quotes=quotes,
			message=f"成功获取股票 '{ts_code}' 的详细信息"
		)

	except ResourceNotFoundException as rnf:
		logger.warning(f"股票资源未找到: {str(rnf)}")
		raise
	except Exception as e:
		logger.error(f"获取股票详情失败: {str(e)}", exc_info=True)
		raise BusinessException(f"查询股票详情失败: {str(e)}")


async def get_historical_quotes (
		session: AsyncSession,
		request: HistoricalQuotesRequest,
		user_id: str
) -> HistoricalQuotesResponse:
	"""
	获取历史行情数据 - 支持分页、日期范围、复权类型过滤

	Args:
		session: 数据库会话
		request: 历史行情查询参数
		user_id: 当前用户ID

	Returns:
		HistoricalQuotesResponse: 历史行情响应

	Raises:
		ValidationException: 请求参数验证失败
		BusinessException: 查询过程发生异常
	"""
	try:
		logger.info(
			f"用户 {user_id} 请求历史行情: "
			f"股票={request.ts_code}, 日期范围={request.start_date} 至 {request.end_date}, "
			f"频率={request.frequency}, 复权类型={request.adjust}"
		)

		# 1. 参数验证
		if request.start_date and request.end_date:
			if request.start_date > request.end_date:
				raise ValidationException("开始日期不能晚于结束日期")

		# 2. 使用行情数据Repository
		quote_repo = StockDailyRepository(session)

		# 3. 构建查询条件
		kwargs = {}
		if request.ts_code:
			kwargs["ts_code"] = request.ts_code

		# 4. 执行查询（历史行情通常不分页，返回全部数据）
		quotes = await quote_repo.get_many(**kwargs)
		# Post-filter by date range (TODO: add comparison filter support to BaseRepository)
		if request.start_date:
			quotes = [q for q in quotes if hasattr(q, "trade_date") and q.trade_date >= request.start_date]
		if request.end_date:
			quotes = [q for q in quotes if hasattr(q, "trade_date") and q.trade_date <= request.end_date]
		# Sort by trade_date descending
		quotes = sorted(
			quotes,
			key=lambda x: getattr(x, "trade_date", datetime.min),
			reverse=True,
		)

		# 5. 数据转换：ORM对象 -> 字典
		quote_items = []
		for quote in quotes:
			quote_items.append({
				"ts_code": quote.ts_code,
				"trade_date": quote.trade_date.isoformat() if quote.trade_date else None,
				"open": float(quote.open) if quote.open else None,
				"high": float(quote.high) if quote.high else None,
				"low": float(quote.low) if quote.low else None,
				"close": float(quote.close) if quote.close else None,
				"pre_close": float(quote.pre_close) if quote.pre_close else None,
				"change": float(quote.change) if quote.change else None,
				"pct_chg": float(quote.pct_chg) if quote.pct_chg else None,
				"vol": float(quote.vol) if quote.vol else None,
				"amount": float(quote.amount) if quote.amount else None,
				"adj_factor": float(quote.adj_factor) if hasattr(quote, "adj_factor") else None,
				"updated_at": quote.updated_at.isoformat() if quote.updated_at else None
			})

		# 6. 按股票代码分组
		quotes_by_stock = {}
		if request.ts_code:
			# 如果只查询一个股票，直接分组
			quotes_by_stock[request.ts_code] = quote_items
		else:
			# 按股票代码分组
			for quote in quote_items:
				ts_code = quote.get("ts_code")
				if ts_code not in quotes_by_stock:
					quotes_by_stock[ts_code] = []
				quotes_by_stock[ts_code].append(quote)

		# 7. 构建响应
		response = HistoricalQuotesResponse(
			success=True,
			data=quotes_by_stock,
			metadata={
				"total_records": len(quote_items),
				"date_range": {
					"start": request.start_date.isoformat() if request.start_date else None,
					"end": request.end_date.isoformat() if request.end_date else None
				},
				"frequency": request.frequency,
				"adjust": request.adjust if hasattr(request, "adjust") else None
			},
			message="获取历史行情成功"
		)

		logger.info(f"成功返回历史行情，共 {len(quote_items)} 条记录")
		return response

	except ValidationException as ve:
		logger.warning(f"历史行情参数验证失败: {str(ve)}")
		raise
	except Exception as e:
		logger.error(f"获取历史行情失败: {str(e)}", exc_info=True)
		raise BusinessException(f"查询历史行情失败: {str(e)}")


# ==================== 数据同步处理函数 ====================

async def batch_sync_data (
		session: AsyncSession,
		request: BatchSyncRequest,
		event_engine: EventEngine,
		user_id: str,
		background_tasks: BackgroundTasks
) -> BatchSyncResponse:
	"""
	批量同步数据 - 支持多种数据类型和同步模式

	Args:
		session: 数据库会话
		request: 批量同步请求参数
		event_engine: 事件引擎，用于发布同步事件
		user_id: 当前用户ID
		background_tasks: FastAPI后台任务管理器

	Returns:
		BatchSyncResponse: 同步任务响应

	Raises:
		BusinessException: 同步任务创建失败
	"""
	try:
		logger.info(
			f"用户 {user_id} 发起批量同步: "
			f"任务数量={len(request.tasks)}, "
			f"优先级={request.priority}"
		)

		# 1. 创建同步任务ID
		task_id = f'batch_sync_{datetime.now().strftime("%Y%m%d_%H%M%S")}'

		# 2. 提取数据类型（从任务中提取）
		data_types = []
		for task in request.tasks:
			if task.data_type not in data_types:
				data_types.append(task.data_type)

		# 3. 创建任务记录
		sync_task_repo = DataSyncTaskRepository(session)

		# 创建同步任务记录（注意：id字段为自增主键，由数据库自动生成）
		sync_task_data = {
			"task_id": task_id,
			"task_type": "batch",
			"data_types": data_types,
			"user_id": user_id,
			"status": "pending",
			"parameters": {
				"tasks": [task.model_dump() for task in request.tasks],
				"priority": request.priority,
				"notify_on_complete": request.notify_on_complete,
				"callback_url": request.callback_url
			},
			"created_at": datetime.now()
		}

		# 创建同步任务
		sync_task = await sync_task_repo.create(sync_task_data)

		# 立即提交，确保后台任务和轮询请求能从 DB 查到该记录
		await session.commit()

		# 4. 发布同步开始事件
		start_event = DataSyncStartedEvent(
			sync_type="batch",
			source="data_module",
			params={
				"task_id": task_id,
				"data_types": data_types,
				"user_id": user_id,
				"timestamp": datetime.now().isoformat()
			}
		)
		await event_engine.put(start_event)  # type: ignore

		# 5. 根据执行模式选择执行路径（BatchSyncRequest中没有execution_mode字段，使用默认异步执行）
		logger.info(f"已将同步任务加入后台队列: {task_id}")

		# 状态将由后台任务更新为 running，此处保持 pending

		# 将同步任务加入后台任务队列（传递DB主键id避免再次查询）
		background_tasks.add_task(
			_execute_async_data_sync,
			task_id=task_id,
			db_id=sync_task.id,
			request=request,
			event_engine=event_engine,
			user_id=user_id
		)

		# 返回异步任务响应
		return BatchSyncResponse(
			success=True,
			task_id=task_id,
			task_count=len(request.tasks),
			estimated_duration=_estimate_sync_time(request),
			start_time=datetime.now(),
			progress_endpoint=f"/api/events/sync/status?task_id={task_id}",
			message="数据同步已开始，将在后台执行"
		)

	except Exception as e:
		logger.error(f"创建数据同步任务失败: {str(e)}", exc_info=True)
		raise BusinessException(f"创建数据同步任务失败: {str(e)}")


async def quick_sync_data (
		session: AsyncSession,
		request: QuickSyncRequest,
		event_engine: EventEngine,
		user_id: str,
		background_tasks: BackgroundTasks
) -> QuickSyncResponse:
	"""
	快速同步数据 - 同步最近几天数据，简化参数

	Args:
		session: 数据库会话
		request: 快速同步请求参数
		event_engine: 事件引擎
		user_id: 当前用户ID
		background_tasks: 后台任务管理器

	Returns:
		QuickSyncResponse: 同步任务响应

	Raises:
		BusinessException: 快速同步任务创建失败
	"""
	try:
		logger.info(
			f"用户 {user_id} 发起快速同步: "
			f"日期范围={request.date_range}"
		)

		# 1. 根据日期范围计算开始和结束日期
		end_date = datetime.now().date()
		if request.date_range == "7d":
			start_date = end_date - timedelta(days=7)
		elif request.date_range == "30d":
			start_date = end_date - timedelta(days=30)
		elif request.date_range == "90d":
			start_date = end_date - timedelta(days=90)
		elif request.date_range == "1y":
			start_date = end_date - timedelta(days=365)
		elif request.date_range == "all":
			start_date = None  # 同步所有数据
		else:
			start_date = end_date - timedelta(days=7)  # 默认7天

		# 2. 确定要同步的数据类型
		sync_tasks = []

		# 股票列表
		if request.include_stock_list:
			sync_tasks.append({
				"data_type": "stock_list",
				"force_update": True
			})

		# 日行情数据
		if start_date:
			sync_tasks.append({
				"data_type": "daily_quotes",
				"start_date": start_date,
				"end_date": end_date,
				"force_update": False
			})

		# 交易日历
		if request.include_calendar:
			sync_tasks.append({
				"data_type": "calendar",
				"start_date": start_date,
				"end_date": end_date,
				"force_update": False
			})

		# 3. 构建批量同步请求
		from modules.data.schemas import SyncTaskItem, SyncPriority
		task_items = [SyncTaskItem(**task) for task in sync_tasks]

		batch_request = BatchSyncRequest(
			tasks=task_items,
			priority=SyncPriority.HIGH,  # 快速同步使用高优先级
			notify_on_complete=True
		)

		# 4. 调用批量同步函数
		batch_result = await batch_sync_data(
			session=session,
			request=batch_request,
			event_engine=event_engine,
			user_id=user_id,
			background_tasks=background_tasks
		)

		# 5. 转换为快速同步响应格式
		return QuickSyncResponse(
			success=True,
			task_id=batch_result.task_id,
			sync_type="quick_sync",
			date_range=request.date_range,
			included_data_types=[task.data_type for task in task_items],
			estimated_stocks=5000,  # 估计值，实际应从数据库获取
			estimated_records=35000,  # 估计值
			start_time=datetime.now(),
			progress_endpoint=batch_result.progress_endpoint,
			quick_status_endpoint=f"/api/events/sync/quick-status?task_id={batch_result.task_id}",
			message="快速同步任务已开始",
			warnings=["请注意，快速同步可能会对系统性能产生短暂影响"]
		)

	except Exception as e:
		logger.error(f"创建快速同步任务失败: {str(e)}", exc_info=True)
		raise BusinessException(f"创建快速同步任务失败: {str(e)}")


# 同步类型元数据缓存（60 秒 TTL，页面频繁刷新不重复构建）
_sync_meta_cache: Optional["SyncTypesMetaResponse"] = None
_sync_meta_cache_time: float = 0.0

async def get_sync_types_meta(
	session: AsyncSession,
) -> "SyncTypesMetaResponse":
	"""
	获取同步类型的分组元数据和预设任务列表。
	供前端渲染分组视图、列表视图和预设任务。
	"""
	import time as _t
	global _sync_meta_cache, _sync_meta_cache_time
	if _sync_meta_cache is not None and (_t.time() - _sync_meta_cache_time) < 60:
		return _sync_meta_cache

	from modules.data.schemas import SyncTypesMetaResponse, SyncGroupMeta, SyncTypeMeta, SyncPresetMeta
	from modules.data.constants import DataType

	# 新分组定义（按日常使用场景）
	groups_config = [
		{"id": "1", "label": "每日行情", "icon": "date", "color": "#3B82F6",
		 "description": "每天盘前/盘后必跑的核心行情数据", "frequency": "每天",
		 "deps": ["7"]},
		{"id": "2", "label": "财务数据", "icon": "money", "color": "#F59E0B",
		 "description": "财报季集中更新", "frequency": "每季度",
		 "deps": ["7"]},
		{"id": "3", "label": "公司治理", "icon": "building", "color": "#EF4444",
		 "description": "股东变动、管理层、质押等", "frequency": "每月/季度",
		 "deps": ["7"]},
		{"id": "4", "label": "因子数据", "icon": "chart", "color": "#8B5CF6",
		 "description": "技术因子，策略研究用", "frequency": "按需",
		 "deps": ["7"]},
		{"id": "5", "label": "事件驱动", "icon": "lightning", "color": "#EC4899",
		 "description": "解禁/披露/增减持/资金流向", "frequency": "按需",
		 "deps": ["7"]},
		{"id": "6", "label": "宏观数据", "icon": "globe", "color": "#10B981",
		 "description": "CPI/PPI/GDP 宏观经济指标", "frequency": "每月/季度",
		 "deps": []},
		{"id": "7", "label": "基础数据", "icon": "database", "color": "#6B7280",
		 "description": "首次初始化，后续按需更新", "frequency": "首次+按需",
		 "deps": []},
	]

	# 类型到分组的映射（DataType值 → 组ID, 序号, 表名, 耗时秒, 数据量, 是否核心）
	type_group_map = {
		# 1: 每日行情
		DataType.DAILY_QUOTES: ("1", "1.1", "stock_daily", 1500, "~1.25M条", True),
		DataType.DAILY_BASIC: ("1", "1.2", "stock_daily_basic", 300, "~5K条", True),
		DataType.ADJ_FACTOR: ("1", "1.3", "stock_adj_factor", 180, "~5K条", True),
		DataType.MONEYFLOW: ("1", "1.4", "stock_moneyflow", 300, "~5K条", False),
		DataType.DAILY_LIMIT: ("1", "1.5", "stock_daily_limit", 60, "~5K条", False),
		DataType.SUSPEND: ("1", "1.6", "stock_suspend_info", 15, "~200条", False),
		DataType.WEEKLY_QUOTES: ("1", "1.7", "stock_weekly", 120, "~5K条", False),
		DataType.MONTHLY_QUOTES: ("1", "1.8", "stock_monthly", 60, "~5K条", False),
		DataType.ETF_DAILY: ("1", "1.9", "etf_daily", 45, "~1K条", True),
		DataType.ETF_SHARE: ("1", "1.10", "etf_share", 15, "~1K条", False),
		DataType.FUND_ADJ_FACTOR: ("1", "1.11", "fund_adj_factor", 30, "~1K条", False),
		DataType.INDEX_DAILY: ("1", "1.12", "index_daily", 12, "~500条", True),
		DataType.INDEX_WEEKLY: ("1", "1.13", "index_weekly", 15, "~500条", False),
		DataType.INDEX_WEIGHT: ("1", "1.14", "index_weight", 5, "~3K条", False),
		DataType.ST_STOCKRISK: ("1", "1.15", "stock_st_risk", 10, "~200条", False),
		# 2: 财务数据
		DataType.FINANCIAL_DATA: ("2", "2.0", "financial_statements", 1800, "三表合并", True),
		DataType.FINANCIAL_INCOME: ("2", "2.1", "financial_statements", 600, "利润表", True),
		DataType.FINANCIAL_BALANCE: ("2", "2.2", "financial_statements", 600, "资产负债表", True),
		DataType.FINANCIAL_CASHFLOW: ("2", "2.3", "financial_statements", 600, "现金流量表", True),
		DataType.FORECAST: ("2", "2.4", "stock_forecasts", 120, "~5K条", False),
		DataType.EXPRESS: ("2", "2.5", "stock_expresses", 120, "~5K条", False),
		DataType.DIVIDEND: ("2", "2.6", "stock_dividends", 60, "~5K条", False),
		DataType.FINANCIAL_INDICATOR: ("2", "2.7", "stock_fina_indicators", 300, "~5K条", True),
		DataType.AUDIT_OPINION: ("2", "2.8", "stock_audit_opinions", 60, "~5K条", False),
		DataType.BUSINESS_INCOME: ("2", "2.9", "stock_business_incomes", 120, "~5K条", False),
		# 3: 公司治理
		DataType.MANAGERS: ("3", "3.1", "stk_managers", 120, "~75K条", True),
		DataType.REWARDS: ("3", "3.2", "stk_rewards", 120, "~75K条", True),
		DataType.TOP10_HOLDERS: ("3", "3.3", "stock_top10_holders", 90, "~50K条", True),
		DataType.TOP10_FLOAT_HOLDERS: ("3", "3.4", "stock_top10_float_holders", 90, "~50K条", True),
		DataType.STK_HOLDERNUMBER: ("3", "3.5", "stock_stk_holdernumber", 60, "~100K条", True),
		DataType.PLEDGE_STAT: ("3", "3.6", "stock_pledge_stat", 60, "~5K条", False),
		DataType.STK_HOLDERTRADE: ("3", "3.7", "stock_stk_holdertrade", 30, "~3K条", False),
		DataType.SHARE_FLOAT: ("3", "3.8", "stock_share_float", 15, "~500条", False),
		DataType.FORECAST_PRO: ("3", "3.9", "stock_forecast_pro", 120, "~25K条", False),
		DataType.INDEX_SW_CLASSIFY: ("3", "3.10", "index_sw_classify", 15, "~400条", False),
		DataType.INDEX_SW_MEMBER: ("3", "3.11", "index_sw_member", 20, "~5K条", False),
		# 4: 因子数据
		DataType.STK_FACTOR: ("4", "4.1", "stock_factor_daily", 600, "~5K条/天", False),
		DataType.STK_FACTOR_PRO: ("4", "4.2", "stock_factor_pro_daily", 600, "~5K条/天", False),
		DataType.IDX_FACTOR_PRO: ("4", "4.3", "index_factor_pro_daily", 120, "~125K条", False),
		# 5: 事件驱动
		DataType.ST_LIST: ("5", "5.2", "stock_st_list", 30, "~3K条", False),
		DataType.DISCLOSURE_DATE: ("5", "5.3", "financial_disclosure_dates", 15, "~5K条", False),
		DataType.MONEYFLOW_HSGT: ("1", "1.18", "stock_moneyflow_hsgt", 15, "~300条", True),
		# 6: 宏观数据
		DataType.CPI: ("6", "6.1", "macro_cpi", 10, "~200条", True),
		DataType.PPI: ("6", "6.2", "macro_ppi", 10, "~200条", True),
		DataType.GDP: ("6", "6.3", "macro_gdp", 10, "~200条", True),
		# 7: 基础数据
		DataType.STOCK_LIST: ("7", "7.1", "stock_basic", 30, "~5K条", True),
		DataType.CALENDAR: ("7", "7.2", "trade_calendar", 15, "~8K条", True),
		DataType.COMPANY: ("7", "7.3", "stock_company", 60, "~5K条", True),
		DataType.INDEX_BASIC: ("7", "7.4", "index_basic", 20, "~500条", True),
		DataType.ETF_BASIC: ("7", "7.5", "etf_basic", 20, "~1K条", True),
		DataType.ETF_INDEX: ("7", "7.6", "etf_index", 10, "~1K条", True),
		DataType.STOCK_HSGT: ("7", "7.7", "stock_hsgt", 20, "~2K条", False),
		DataType.INDEX_SW_CLASSIFY: ("7", "7.8", "index_sw_classify", 15, "~400条", False),
		DataType.INDEX_SW_MEMBER: ("7", "7.9", "index_sw_member", 20, "~5K条", False),
		DataType.INDEX_DAILYBASIC: ("1", "1.16", "index_dailybasic", 30, "~1.5K条", True),
		# 兼容
		DataType.INDEX_SW_DAILY: ("1", "1.17", "index_sw_daily", 120, "~7.7K条", False),
		DataType.TICK_QUOTES: ("1", "1.99", "", 0, "未实现", False),
		DataType.MINUTE_QUOTES: ("4", "4.4", "stock_minute", 600, "7天×100只", False),
		DataType.ETF_MINUTE: ("4", "4.5", "etf_minute", 300, "7天×50只", False),
	}

	# 未实现的类型
	not_implemented = {DataType.TICK_QUOTES}

	# 查询每个 type 的上次同步时间
	last_sync_map = {}
	try:
		from sqlalchemy import text
		result = await session.execute(text(
			"SELECT task_type, MAX(end_time) as last_sync FROM data_sync_tasks "
			"WHERE status = 'completed' GROUP BY task_type"
		))
		for row in result:
			last_sync_map[row[0]] = row[1]
	except Exception:
		pass

	# 构建分组
	groups = []
	for gc in groups_config:
		types = []
		for dt_val, (gid, gidx, table, est_sec, volume, is_core) in type_group_map.items():
			if gid == gc["id"]:
				dt_str = dt_val.value if hasattr(dt_val, 'value') else str(dt_val)
				types.append(SyncTypeMeta(
					data_type=dt_str,
					label=DataType.get_display_name(dt_val),
					group_index=gidx,
					implemented=dt_val not in not_implemented,
					table_name=table,
					estimated_time_seconds=est_sec,
					data_volume=volume,
					last_sync_at=last_sync_map.get(dt_str),
					coverage=1.0 if dt_val not in not_implemented else 0.0,
					is_core=is_core,
				))
		groups.append(SyncGroupMeta(
			id=gc["id"], label=gc["label"], color=gc["color"],
			description=gc["description"], recommended_frequency=gc["frequency"],
			depends_on=gc["deps"], types=types,
		))

	# 预设任务
	presets = [
		SyncPresetMeta(id="daily", name="每日行情（增量）", description="盘前/盘后运行，更新所有行情数据",
		               recommended=True, estimated_time_seconds=2100,
		               steps=[{"group_id": "1"}]),
		SyncPresetMeta(id="init", name="首次全量", description="新数据库初始化，按依赖顺序：基础→行情→财务→治理",
		               recommended=False, estimated_time_seconds=14400,
		               steps=[{"group_id": "7"}, {"group_id": "1"}, {"group_id": "2"}, {"group_id": "3"}]),
		SyncPresetMeta(id="earnings", name="财报季更新", description="季度财报发布后，更新财务+治理数据",
		               recommended=False, estimated_time_seconds=2700,
		               steps=[{"group_id": "2"}, {"group_id": "3"}]),
	]

	return SyncTypesMetaResponse(groups=groups, presets=presets)


async def get_sync_status_all(
	session: AsyncSession,
) -> "SyncStatusAllResponse":
	"""获取所有同步类型的状态概览（供前端渲染覆盖度）"""
	from modules.data.schemas import SyncStatusAllResponse, SyncTypeStatus
	from modules.data.constants import DataType

	# 复用 get_sync_types_meta 获取元数据
	meta = await get_sync_types_meta(session)
	types_status = []
	from datetime import datetime
	for group in meta.groups:
		for t in group.types:
			if t.last_sync_at:
				hours_ago = (datetime.now() - t.last_sync_at).total_seconds() / 3600
				if hours_ago < 24:
					status = "up_to_date"
				elif hours_ago < 72:
					status = "needs_update"
				else:
					status = "outdated"
			else:
				status = "never_synced"
			types_status.append(SyncTypeStatus(
				data_type=t.data_type, label=t.label, group=group.id,
				last_sync_at=t.last_sync_at, coverage=t.coverage, status=status,
			))
	return SyncStatusAllResponse(types=types_status)



async def get_sync_status (
		session: AsyncSession,
		task_id: Optional[str],
		user_id: str
) -> SyncStatusResponse:
	"""
	获取数据同步任务状态

	Args:
		session: 数据库会话
		task_id: 同步任务ID（可选，如未指定则返回用户最近任务）
		user_id: 当前用户ID

	Returns:
		SyncStatusResponse: 同步任务状态响应

	Raises:
		ResourceNotFoundException: 任务不存在
		PermissionDeniedException: 用户无权查看该任务
		BusinessException: 查询状态失败
	"""
	try:
		sync_task_repo = DataSyncTaskRepository(session)

		if task_id:
			# 查询指定任务（使用get_by_task_id方法，将字符串task_id转换为整数id）
			task_result = await sync_task_repo.get_by_task_id(task_id)
			if not task_result.success or not task_result.data:
				raise ResourceNotFoundException(f"同步任务 '{task_id}' 不存在")

			task = task_result.data

			# 权限验证
			if task.user_id != user_id:
				raise PermissionDeniedException("无权查看其他用户的同步任务")

			# 计算进度
			progress = 0
			if hasattr(task, "total_records") and hasattr(task, "processed_records"):
				if task.total_records and task.processed_records:
					progress = task.processed_records / task.total_records * 100

			# 构建进度信息
			from modules.data.schemas import SyncProgress, SyncResult

			# 计算预计剩余时间
			estimated_time_remaining = None
			if task.status == "running" and hasattr(task, "start_time") and task.start_time and progress > 0:
				elapsed = (datetime.now() - task.start_time).total_seconds()
				estimated_total = elapsed / (progress / 100)
				estimated_time_remaining = int(max(0.0, estimated_total - elapsed))

			# 构建同步结果
			sync_results = []
			if hasattr(task, "data_types") and task.data_types:
				for data_type in task.data_types:
					sync_results.append(SyncResult(
						data_type=data_type,
						success=task.status == "completed",
						records_added=task.records_succeeded or 0,
						records_updated=0,
						records_failed=task.records_failed or 0,
						start_time=task.start_time or datetime.now(),
						end_time=task.end_time or (datetime.now() if task.status == "completed" else datetime.now()),
					))

			progress_info = SyncProgress(
				task_id=task.task_id,
				total_tasks=len(task.data_types) if task.data_types else 1,
				completed_tasks=1 if task.status == "completed" else 0,
				current_task=f"同步{task.task_type}",
				progress_percentage=progress,
				estimated_time_remaining=estimated_time_remaining
			)

			# 构建响应
			return SyncStatusResponse(
				success=True,
				task_id=task.task_id,
				status=task.status,
				progress=progress_info,
				results=sync_results,
				created_by=str(task.user_id),
				created_at=task.created_at,
				updated_at=task.updated_at,
				message="获取同步状态成功"
			)

		else:
			# 查询用户最近任务
			tasks = await sync_task_repo.get_by_user_id(
				user_id=user_id,
				limit=10
			)

			from modules.data.schemas import SyncProgress, SyncResult

			# 如果有运行中的任务，委托给 task_id 路径获取真实进度
			running_tasks = [t for t in tasks if t.status == "running"] if tasks else []
			if running_tasks:
				# 复用已有的 task_id 查询逻辑，获取 DB 中的实时进度
				task_id = running_tasks[0].task_id
				task_result = await sync_task_repo.get_by_task_id(task_id)
				if task_result.success and task_result.data:
					task = task_result.data
					progress = 0
					current_task = f"同步{task.task_type}"
					# 优先读取 Redis 实时进度（_update_progress 写入）
					try:
						from modules.data.constants import CacheKey
						redis = RedisCache()
						progress_raw = await redis.get(CacheKey.SYNC_PROGRESS.format(task_id=task_id))
						if progress_raw:
							import json as _json
							pd = _json.loads(progress_raw)
							progress = pd.get("progress", 0)
							current_task = pd.get("current_task", current_task)
					except Exception:
						pass
					return SyncStatusResponse(
						success=True,
						task_id=task.task_id,
						status=task.status,
						progress=SyncProgress(
							task_id=task.task_id,
							total_tasks=len(task.data_types) if task.data_types else 1,
							completed_tasks=0,
							current_task=current_task,
							progress_percentage=progress,
							estimated_time_remaining=None,
						),
						results=[SyncResult(data_type=dt, success=False, records_added=0, records_updated=0, records_failed=0, start_time=task.start_time or task.created_at, end_time=datetime.now()) for dt in (task.data_types if task.data_types else [task.task_type])],
						created_by=str(task.user_id),
						created_at=task.created_at,
						updated_at=task.updated_at,
						message=f"正在同步 {len(task.data_types) if task.data_types else 1} 种数据类型"
					)

			# 无运行中任务时，汇总最近任务状态
			recent_tasks = []
			if tasks:
				for task in tasks:
					recent_tasks.append({
						"task_id": task.task_id,
						"task_type": task.task_type,
						"data_types": task.data_types if hasattr(task, "data_types") else [],
						"status": task.status,
						"created_at": task.created_at.isoformat() if task.created_at else None,
						"completed_at": task.completed_at.isoformat() if hasattr(task,
						                                                        "completed_at") and task.completed_at else None
					})

			seen_types: set = set()
			sync_results = []
			if tasks:
				for task in tasks:
					data_types = task.data_types if hasattr(task, "data_types") and task.data_types else [task.task_type]
					for data_type in data_types:
						if data_type in seen_types:
							continue
						seen_types.add(data_type)
						sync_results.append(SyncResult(
							data_type=data_type,
							success=task.status == "completed",
							records_added=task.records_succeeded or 0,
							records_updated=0,
							records_failed=task.records_failed or 0,
							start_time=task.start_time if hasattr(task, "start_time") and task.start_time else task.created_at,
							end_time=task.end_time if hasattr(task, "end_time") and task.end_time else task.updated_at if hasattr(task, "updated_at") and task.updated_at else task.created_at,
						))

			if not tasks:
				aggregate_status = "idle"
			else:
				failed_count = sum(1 for t in tasks if t.status == "failed")
				completed_count = sum(1 for t in tasks if t.status == "completed")
				if completed_count == 0 and failed_count > 0:
					aggregate_status = "failed"
				elif failed_count == 0 and completed_count > 0:
					aggregate_status = "completed"
				else:
					aggregate_status = "partial"

			earliest_time = min((t.created_at for t in tasks if t.created_at), default=datetime.now())
			latest_time = max((t.updated_at if hasattr(t, "updated_at") and t.updated_at else t.created_at for t in tasks if t.created_at), default=datetime.now())

			return SyncStatusResponse(
				success=True,
				task_id="recent_tasks",
				status=aggregate_status,
				progress=SyncProgress(
					task_id="recent_tasks",
					total_tasks=len(recent_tasks),
					completed_tasks=completed_count,
					current_task="查看历史任务",
					progress_percentage=100,
					estimated_time_remaining=0
				),
				results=sync_results,
				created_by=str(user_id),
				created_at=earliest_time,
				updated_at=latest_time,
				message=f"获取到{len(recent_tasks)}个历史任务"
			)

	except (ResourceNotFoundException, PermissionDeniedException) as e:
		logger.warning(f"同步状态查询失败: {str(e)}")
		raise
	except Exception as e:
		logger.error(f"获取同步状态失败: {str(e)}", exc_info=True)
		raise BusinessException(f"查询同步状态失败: {str(e)}")


async def get_sync_tasks(
        session: AsyncSession,
        user_id: str,
        status: Optional[str] = None,
        group: Optional[str] = None,
        limit: int = 20,
        offset: int = 0,
) -> "SyncTaskListResponse":
    """
    获取同步任务历史列表
    """
    from modules.data.schemas import SyncTaskRecord, SyncTaskListResponse
    from modules.data.constants import DataType

    # 构建类型标签查找表
    type_label_map = {dt.value: DataType.get_display_name(dt) for dt in DataType}

    try:
        sync_task_repo = DataSyncTaskRepository(session)
        tasks = await sync_task_repo.get_by_user_id(
            user_id=user_id, limit=limit, offset=offset,
            status=status, parent_only=True,
        )
        total = await sync_task_repo.count_by_user(user_id, status)

        def _to_record(task):
            return SyncTaskRecord(
                id=task.id,
                task_id=task.task_id,
                task_type=task.task_type,
                task_label=type_label_map.get(task.task_type, task.task_type),
                data_types=task.data_types if hasattr(task, "data_types") else None,
                status=task.status,
                start_time=task.start_time,
                end_time=task.end_time,
                records_processed=task.records_processed or 0,
                records_succeeded=task.records_succeeded or 0,
                records_failed=task.records_failed or 0,
                total_records=task.total_records or 0,
                parent_task_id=getattr(task, "parent_task_id", None),
                parameters=task.parameters if hasattr(task, "parameters") else None,
                error_message=task.error_message,
                created_at=task.created_at,
                updated_at=task.updated_at,
                completed_at=task.completed_at,
            )

        records = []
        for task in tasks:
            r = _to_record(task)
            if task.task_type == "batch":
                children = await sync_task_repo.get_children(task.task_id)
                if children:
                    r.children = [_to_record(c) for c in children]
            records.append(r)

        return SyncTaskListResponse(
            success=True,
            tasks=records,
            total=total,
        )

    except Exception as e:
        logger.error(f"获取同步任务列表失败: {str(e)}", exc_info=True)
        raise BusinessException(f"获取同步任务列表失败: {str(e)}")


async def cancel_sync (
		session: AsyncSession,
		task_id: str,
		event_engine: EventEngine,
		user_id: str
) -> Dict[str, Any]:
	"""
	取消数据同步任务

	Args:
		session: 数据库会话
		task_id: 同步任务ID
		event_engine: 事件引擎，用于发布取消事件
		user_id: 当前用户ID

	Returns:
		Dict: 取消操作结果

	Raises:
		ResourceNotFoundException: 任务不存在
		PermissionDeniedException: 用户无权取消该任务
		ValidationException: 任务已处于最终状态，无法取消
		BusinessException: 取消操作失败
	"""
	try:
		logger.info(f"用户 {user_id} 请求取消同步任务: {task_id}")

		sync_task_repo = DataSyncTaskRepository(session)

		# 1. 获取任务信息
		task_result = await sync_task_repo.get_by_task_id(task_id)
		if not task_result.success or not task_result.data:
			raise ResourceNotFoundException(f"同步任务 '{task_id}' 不存在")

		task = task_result.data

		# 2. 权限验证
		if task.user_id != user_id:
			raise PermissionDeniedException("无权取消其他用户的同步任务")

		# 3. 状态验证
		if task.status in ["completed", "cancelled", "failed"]:
			raise ValidationException(f"任务已处于最终状态 '{task.status}'，无法取消")

		# 4. 校验全部通过后，发送取消信号（不再在 DB 操作之前，避免校验失败时 token 已被设置）
		from modules.data import signal_cancel
		cancelled = signal_cancel(task_id)
		if cancelled:
			logger.info(f"取消信号已发送: task_id={task_id}")
		else:
			logger.warning(f"取消信号发送失败（token 未命中）: task_id={task_id}, "
			               f"可能后台任务尚未创建取消令牌或已被清理")

		# 4. 更新任务状态
		# 更新任务 + 所有子任务为 cancelled
		from sqlalchemy import text as _sql
		await session.execute(
			_sql("UPDATE data_sync_tasks SET status='cancelled', error_message='用户手动取消', updated_at=:now WHERE (task_id=:tid OR parent_task_id=:tid) AND status='running'"),
			{"tid": task_id, "now": datetime.now()}
		)
		await session.commit()

		# 5. 发布取消事件
		cancel_event = DataSyncProgressEvent(
			sync_type="cancel",
			task_id=task_id,
			data_types=task.data_types if hasattr(task, "data_types") else [],
			progress=0,
			current_item="任务已取消",
			current_task="任务已取消",
			total_tasks=1,
			completed_tasks=0,
			user_id=str(user_id),
			timestamp=datetime.now(),
			source="data_module"
		)
		await event_engine.put(cancel_event)  # type: ignore

		logger.info(f"成功取消同步任务: {task_id}")
		return {
			"task_id": task_id,
			"status": "cancelled",
			"cancelled_at": datetime.now().isoformat(),
			"message": "同步任务已成功取消"
		}

	except (ResourceNotFoundException, PermissionDeniedException, ValidationException) as e:
		logger.warning(f"取消同步任务失败: {str(e)}")
		raise
	except Exception as e:
		logger.error(f"取消同步任务异常: {str(e)}", exc_info=True)
		raise BusinessException(f"取消同步任务失败: {str(e)}")



async def delete_sync_task(
		session: AsyncSession,
		task_id: str,
		user_id: str
) -> Dict[str, Any]:
	"""删除同步任务记录（仅允许删除已完成/失败/取消的任务）"""
	try:
		sync_task_repo = DataSyncTaskRepository(session)
		task_result = await sync_task_repo.get_by_task_id(task_id)
		if not task_result.success or not task_result.data:
			raise ResourceNotFoundException(f"同步任务 '{task_id}' 不存在")

		task = task_result.data
		if task.user_id != user_id:
			raise PermissionDeniedException("无权删除其他用户的同步任务")
		if task.status == "running":
			raise ValidationException("运行中的任务无法删除，请先取消")

		await sync_task_repo.delete(task.id, soft=False)
		logger.info(f"成功删除同步任务: {task_id}")
		return {"task_id": task_id, "deleted": True, "message": "同步任务已删除"}

	except (ResourceNotFoundException, PermissionDeniedException, ValidationException) as e:
		logger.warning(f"删除同步任务失败: {str(e)}")
		raise
	except Exception as e:
		logger.error(f"删除同步任务异常: {str(e)}", exc_info=True)
		raise BusinessException(f"删除同步任务失败: {str(e)}")


async def delete_sync_tasks_batch(
		session: AsyncSession,
		task_ids: list,
		user_id: str
) -> Dict[str, Any]:
	"""批量删除同步任务记录"""
	results = {"deleted": [], "failed": [], "total": len(task_ids)}
	sync_task_repo = DataSyncTaskRepository(session)
	for task_id in task_ids:
		try:
			task_result = await sync_task_repo.get_by_task_id(task_id)
			if not task_result.success or not task_result.data:
				results["failed"].append({"task_id": task_id, "reason": "不存在"})
				continue
			task = task_result.data
			if task.user_id != user_id:
				results["failed"].append({"task_id": task_id, "reason": "无权操作"})
				continue
			if task.status == "running":
				results["failed"].append({"task_id": task_id, "reason": "运行中，请先取消"})
				continue
			await sync_task_repo.delete(task.id, soft=False)
			results["deleted"].append(task_id)
		except Exception as e:
			results["failed"].append({"task_id": task_id, "reason": str(e)})
	logger.info(f"批量删除同步任务: {len(results['deleted'])}/{len(task_ids)} 成功")
	return results


# ==================== 数据质量处理函数 ====================

async def get_data_quality (
		session: AsyncSession,
		request: DataQualityRequest,
		user_id: str,
		run_check: bool = False,
) -> DataQualityResponse:
	"""
	获取数据质量报告

	Args:
		session: 数据库会话
		request: 请求参数
		user_id: 用户ID
		run_check: True=执行新检查, False=返回最近一次结果

	Returns:
		DataQualityResponse: 数据质量报告响应
	"""
	try:
		logger.debug(
			f"用户 {user_id} 请求数据质量报告: "
			f"数据类型={request.data_type}, "
			f"日期范围={request.start_date} 至 {request.end_date}"
		)

		# run_check=True: 执行新检查; False: 仅返回最近一次结果
		quality_service = DataQualityService(session)
		if run_check:
			quality_report = await quality_service.check_data_quality(
				data_type=request.data_type,
				start_date=request.start_date,
				end_date=request.end_date,
				user_id=user_id,
			)
			result = quality_report.get("result", {})
			quality_score = result.get("overall_score", 0)
		else:
			quality_report = await quality_service.get_quality_report(
				data_type=request.data_type or "all",
				limit=1
			)
			latest_result = quality_report.get("reports", [])
			if latest_result:
				result = latest_result[0]
				quality_score = result.get("quality_score", 0)
			elif not run_check:
				# 无缓存结果时自动触发首次检查
				logger.info("无缓存质量数据，自动触发首次检查")
				quality_report = await quality_service.check_data_quality(
					data_type=request.data_type,
					start_date=request.start_date,
					end_date=request.end_date,
					user_id=user_id,
				)
				result = quality_report.get("result", {})
				quality_score = result.get("overall_score", 0)
			else:
				result = {}
				quality_score = 0

		# 确定质量等级
		from modules.data.schemas import DataQualityLevel
		if quality_score >= 99:
			quality_level = DataQualityLevel.EXCELLENT
		elif quality_score >= 95:
			quality_level = DataQualityLevel.GOOD
		elif quality_score >= 90:
			quality_level = DataQualityLevel.FAIR
		else:
			quality_level = DataQualityLevel.POOR

		# 构建 QualityMetric 列表
		from modules.data.schemas import QualityMetric
		metrics: list = []
		if result.get("total_records", 0) > 0:
			total = result.get("total_records", 1)
			valid = result.get("valid_records", 0)
			invalid = result.get("invalid_records", 0)
			missing = result.get("missing_records", 0)
			duplicate = result.get("duplicate_records", 0)
			metrics = [
				QualityMetric(
					metric_name="数据完整率",
					metric_value=round(valid / total * 100, 2),
					threshold=95.0,
					status="pass" if valid / total >= 0.95 else ("warning" if valid / total >= 0.90 else "fail")
				),
				QualityMetric(
					metric_name="无效记录率",
					metric_value=round(invalid / total * 100, 2),
					threshold=5.0,
					status="pass" if invalid / total <= 0.05 else ("warning" if invalid / total <= 0.10 else "fail")
				),
				QualityMetric(
					metric_name="缺失记录数",
					metric_value=float(missing),
					threshold=0,
					status="pass" if missing == 0 else ("warning" if missing <= 10 else "fail")
				),
				QualityMetric(
					metric_name="重复记录数",
					metric_value=float(duplicate),
					threshold=0,
					status="pass" if duplicate == 0 else ("warning" if duplicate <= 5 else "fail")
				),
			]

		# 构建 DataIssue 列表
		from modules.data.schemas import DataIssue
		raw_issues = result.get("issues", [])
		issues: list = [
			DataIssue(
				issue_type=item.get("issue_type", "unknown"),
				severity=item.get("severity", "low"),
				count=item.get("count", 0),
				description=item.get("description", ""),
				affected_records=item.get("affected_records"),
			)
			for item in raw_issues
		] if raw_issues else []

		# 构建响应
		response = DataQualityResponse(
			success=True,
			data_type=request.data_type,
			date_range={"start": request.start_date, "end": request.end_date} if request.start_date is not None and request.end_date is not None else None,
			quality_score=quality_score,
			quality_level=quality_level,
			metrics=metrics,
			issues=issues,
			recommendations=result.get("recommendations", []),
			generated_at=datetime.now(),
			message="数据质量检查完成"
		)

		logger.debug(
			f"成功生成数据质量报告: {request.data_type}, "
			f"综合得分={response.quality_score}"
		)
		return response

	except Exception as e:
		logger.error(f"生成数据质量报告失败: {str(e)}", exc_info=True)
		raise BusinessException(f"生成数据质量报告失败: {str(e)}")


# ==================== 私有辅助方法 ====================

async def _validate_factor_request (request: FactorRequest) -> None:
	"""
	验证因子数据请求参数

	Args:
		request: 因子数据请求参数

	Raises:
		ValidationException: 参数验证失败
	"""
	if request.page < 1:
		raise ValidationException("页码必须大于0")

	if request.page_size < 1 or request.page_size > 1000:
		raise ValidationException("每页大小必须在1-1000之间")

	if request.start_date and request.end_date:
		if request.start_date > request.end_date:
			raise ValidationException("开始日期不能晚于结束日期")

		# 检查日期范围是否过大（限制3年）
		days_diff = (request.end_date - request.start_date).days
		if days_diff > 365 * 3:
			raise ValidationException("日期范围不能超过3年")


async def _validate_research_request (request: ResearchRequest) -> None:
	"""
	验证因子研究请求参数

	Args:
		request: 因子研究请求参数

	Raises:
		ValidationException: 参数验证失败
	"""
	if not request.factor_names or len(request.factor_names) == 0:
		raise ValidationException("因子名称列表不能为空")

	if not request.universe or len(request.universe) == 0:
		raise ValidationException("股票池不能为空")

	if request.start_date and request.end_date:
		if request.start_date > request.end_date:
			raise ValidationException("开始日期不能晚于结束日期")

		# 检查日期范围合理性
		days_diff = (request.end_date - request.start_date).days
		if days_diff > 365 * 5:
			raise ValidationException("研究日期范围不能超过5年")
		if days_diff < 30:
			raise ValidationException("研究日期范围至少需要30天")


async def _get_factor_data_from_cache (cache_key: str, settings: Settings) -> Optional[Dict]:
	"""
	从Redis缓存获取因子数据

	Args:
		cache_key: 缓存键
		settings: 系统配置

	Returns:
		Optional[Dict]: 缓存数据，如未命中则返回None
	"""
	try:
		# 检查Redis配置
		if not hasattr(settings, "REDIS") or not settings.REDIS.ENABLED:
			return None

		# 创建Redis缓存实例
		cache = RedisCache(
			host=settings.REDIS.HOST,
			port=settings.REDIS.PORT,
			db=settings.REDIS.DB,
			password=settings.REDIS.PASSWORD
		)

		# 测试连接并获取数据
		cache_connected = await cache.ping()
		if cache_connected:
			cached_data = await cache.get(cache_key)
			return cached_data if cached_data else None
		else:
			logger.warning("Redis缓存连接失败")

	except Exception as e:
		logger.warning(f"获取缓存数据失败: {str(e)}")

	return None


async def _cache_factor_data (
		cache_key: str,
		data: Dict,
		settings: Settings,
		ttl: int = 300
) -> None:
	"""
	将因子数据存储到Redis缓存

	Args:
		cache_key: 缓存键
		data: 要缓存的数据
		settings: 系统配置
		ttl: 缓存生存时间（秒），默认300秒
	"""
	try:
		# 检查Redis配置
		if not hasattr(settings, "REDIS") or not settings.REDIS.ENABLED:
			return

		# 创建Redis缓存实例
		cache = RedisCache(
			host=settings.REDIS.HOST,
			port=settings.REDIS.PORT,
			db=settings.REDIS.DB,
			password=settings.REDIS.PASSWORD
		)

		# 测试连接并存储数据
		cache_connected = await cache.ping()
		if cache_connected:
			await cache.set(cache_key, data, ttl)
			logger.debug(f"因子数据已缓存: {cache_key}, TTL={ttl}秒")
		else:
			logger.warning("Redis缓存连接失败，无法缓存数据")

	except Exception as e:
		logger.warning(f"缓存因子数据失败: {str(e)}")


async def _execute_sync_factor_research (
		session: AsyncSession,
		research_id: str,
		request: ResearchRequest,
		event_engine: EventEngine,
		user_id: str
) -> ResearchResponse:
	"""
	同步执行因子研究（内部辅助方法）

	Args:
		session: 数据库会话
		research_id: 研究任务ID
		request: 研究请求参数
		event_engine: 事件引擎
		user_id: 当前用户ID

	Returns:
		ResearchResponse: 研究结果响应
	"""
	try:
		# 1. 使用因子研究服务
		research_service = FactorResearchService(session, event_engine)

		# 2. 执行因子研究
		factor_definition = {
			"name": request.factor_names[0] if request.factor_names else "unknown",
			"formula": "",
			"category": "",
			"description": ""
		}
		parameters = {
			"frequency": request.frequency,
			"group_count": request.group_count,
			"analysis_type": request.analysis_type
		}
		research_result = await research_service.research_factor(
			factor_definition=factor_definition,
			universe=request.universe,
			start_date=request.start_date,
			end_date=request.end_date,
			parameters=parameters,
			user_id=user_id
		)

		# 3. 保存研究结果和更新状态
		research_repo = FactorResearchRepository(session)
		await _process_research_completion(
			research_repo=research_repo,
			research_id=research_id,
			request=request,
			research_result=research_result,
			event_engine=event_engine,
			user_id=user_id
		)

		# 6. 构建响应
		return ResearchResponse(
			success=True,
			research_id=research_id,
			analysis_type=request.analysis_type or "ic_analysis",
			parameters={
				"factor_names": request.factor_names,
				"universe": request.universe,
				"start_date": request.start_date.isoformat(),
				"end_date": request.end_date.isoformat(),
				"frequency": request.frequency,
				"group_count": request.group_count
			},
			ic_analysis=research_result.get("ic_analysis"),
			quantile_analysis=research_result.get("quantile_analysis"),
			correlation_analysis=research_result.get("correlation_analysis"),
			summary=research_result.get("summary", {}),
			generated_at=datetime.now(),
			message="因子研究同步执行完成"
		)

	except Exception as e:
		logger.error(f"同步因子研究失败: {str(e)}", exc_info=True)

		# 记录失败状态
		research_repo = FactorResearchRepository(session)
		await research_repo.update_research_status(
			research_id=research_id,
			status="failed",
			error_message=str(e)
		)

		raise BusinessException(f"同步执行因子研究失败: {str(e)}")


async def _process_research_completion (
		research_repo: FactorResearchRepository,
		research_id: str,
		request: ResearchRequest,
		research_result: Dict[str, Any],
		event_engine: EventEngine,
		user_id: str
) -> None:
	"""
	处理研究完成的通用逻辑

	Args:
		research_repo: 因子研究仓库
		research_id: 研究任务ID
		request: 研究请求参数
		research_result: 研究结果
		event_engine: 事件引擎
		user_id: 当前用户ID
	"""
	# 1. 保存研究结果
	await research_repo.save_research_result(
		research_id=research_id,
		result=research_result.get("result", {}),
		summary=research_result.get("summary", {}),
		report=research_result.get("report", {})
	)

	# 2. 更新任务状态
	await research_repo.update_research_status(
		research_id=research_id,
		status="completed"
	)

	# 3. 发布研究完成事件
	completed_event = DataResearchCompletedEvent(
		research_id=research_id,
		research_type=request.analysis_type or "ic_analysis",
		duration_seconds=research_result.get("duration_seconds", 0),
		results=research_result.get("result", {}),
		key_findings=research_result.get("key_findings", []),
		report_data=research_result.get("report", {}),
		user_id=user_id,
		timestamp=datetime.now(),
		source="data_module"
	)
	await event_engine.put(completed_event)  # type: ignore


async def _execute_async_factor_research (
		session: AsyncSession,
		research_id: str,
		request: ResearchRequest,
		event_engine: EventEngine,
		user_id: str
) -> None:
	"""
	异步执行因子研究（后台任务）

	Args:
		session: 数据库会话
		research_id: 研究任务ID
		request: 研究请求参数
		event_engine: 事件引擎
		user_id: 当前用户ID
	"""
	try:
		logger.info(f"开始异步因子研究: {research_id}")

		# 1. 初始化组件
		research_service = FactorResearchService(session, event_engine)
		research_repo = FactorResearchRepository(session)

		# 2. 更新初始进度
		await research_repo.update_research_progress(
			research_id=research_id,
			progress=0.1,
			calculated_count=0,
			total_stocks=len(request.universe) if request.universe else 0
		)

		# 3. 发布进度事件
		progress_event = DataResearchProgressEvent(
			research_id=research_id,
			progress=0.1,
			current_step="初始化研究任务",
			user_id=user_id,
			timestamp=datetime.now(),
			source="data_module"
		)
		await event_engine.put(progress_event)  # type: ignore

		# 4. 执行因子研究
		factor_definition = {
			"name": request.factor_names[0] if request.factor_names else "unknown",
			"formula": "",
			"category": "",
			"description": ""
		}
		parameters = {
			"frequency": request.frequency,
			"group_count": request.group_count,
			"analysis_type": request.analysis_type
		}
		research_result = await research_service.research_factor(
			factor_definition=factor_definition,
			universe=request.universe,
			start_date=request.start_date,
			end_date=request.end_date,
			parameters=parameters,
			user_id=user_id
		)

		# 5. 处理研究完成
		await _process_research_completion(
			research_repo=research_repo,
			research_id=research_id,
			request=request,
			research_result=research_result,
			event_engine=event_engine,
			user_id=user_id
		)

		logger.info(f"异步因子研究完成: {research_id}")

	except Exception as e:
		logger.error(f"异步因子研究失败: {str(e)}", exc_info=True)

		# 更新任务状态为失败
		research_repo = FactorResearchRepository(session)
		await research_repo.update_research_status(
			research_id=research_id,
			status="failed",
			error_message=str(e)
		)

		# 发布失败事件
		fail_event = DataResearchProgressEvent(
			research_id=research_id,
			progress=0,
			current_step="研究失败",
			error_message=str(e),
			user_id=user_id,
			timestamp=datetime.now(),
			source="data_module"
		)
		await event_engine.put(fail_event)  # type: ignore


async def _execute_sync_data_sync (
		session: AsyncSession,
		task_id: str,
		request: BatchSyncRequest,
		event_engine: EventEngine,
		user_id: str
) -> BatchSyncResponse:
	"""
	同步执行数据同步（内部辅助方法）

	Args:
		session: 数据库会话
		task_id: 同步任务ID
		request: 同步请求参数
		event_engine: 事件引擎
		user_id: 当前用户ID

	Returns:
		BatchSyncResponse: 同步结果响应
	"""
	try:
		# 1. 使用数据同步服务
		sync_service = DataSyncService(session, event_engine)

		# 2. 提取任务信息
		data_types = []
		for task in request.tasks:
			if task.data_type not in data_types:
				data_types.append(task.data_type)

		# 3. 执行数据同步
		sync_result = await sync_service.batch_sync_data(
			tasks=request.tasks,
			priority=request.priority,
			user_id=user_id,
			task_id=task_id
		)

		# 4. 更新任务状态
		sync_task_repo = DataSyncTaskRepository(session)
		# 先获取任务以得到整数id
		task_result = await sync_task_repo.get_by_task_id(task_id)
		if task_result.success and task_result.data:
			update_data = {
				"status": "completed",
				"records_processed": sync_result.get("records_processed", 0),
				"records_succeeded": sync_result.get("records_succeeded", 0),
				"records_failed": sync_result.get("records_failed", 0),
				"end_time": datetime.now()
			}
			await sync_task_repo.update(task_result.data.id, update_data)

		# 5. 发布同步完成事件
		completed_event = DataSyncCompletedEvent(
			sync_type="batch",
			record_count=sync_result.get("records_processed", 0),
			duration_seconds=sync_result.get("duration_seconds", 0),
			task_id=task_id,
			user_id=str(user_id),
			timestamp=datetime.now(),
			source="data_module"
		)
		await event_engine.put(completed_event)  # type: ignore

		# 6. 构建响应
		return BatchSyncResponse(
			success=True,
			task_id=task_id,
			task_count=len(request.tasks),
			estimated_duration=sync_result.get("duration_seconds", 0),
			start_time=datetime.now(),
			progress_endpoint=f"/api/events/sync/status?task_id={task_id}",
			message="数据同步完成"
		)

	except Exception as e:
		logger.error(f"同步数据同步失败: {str(e)}", exc_info=True)

		# 记录失败状态
		sync_task_repo = DataSyncTaskRepository(session)
		task_result = await sync_task_repo.get_by_task_id(task_id)
		if task_result.success and task_result.data:
			update_data = {
				"status": "failed",
				"error_message": str(e),
				"end_time": datetime.now()
			}
			await sync_task_repo.update(task_result.data.id, update_data)

		raise BusinessException(f"同步执行数据同步失败: {str(e)}")


async def _execute_async_data_sync (
		task_id: str,
		db_id: Any,
		request: BatchSyncRequest,
		event_engine: EventEngine,
		user_id: str
) -> None:
	"""
	异步执行数据同步（后台任务）

	Args:
		session: 数据库会话
		task_id: 同步任务ID
		request: 同步请求参数
		event_engine: 事件引擎
		user_id: 当前用户ID
	"""
	try:
		logger.warning("=" * 60)
		logger.warning("=" * 60)
		logger.warning("[后台任务] 开始异步数据同步: %s", task_id)
		for t in request.tasks:
			extra = []
			if t.start_date: extra.append(f"日期={t.start_date}")
			if t.end_date: extra.append(f"~{t.end_date}")
			detail = ", ".join(extra) if extra else "全量"
			logger.warning("[后台任务]   类型=%s | %s", t.data_type, detail)
		logger.warning("=" * 60)

		# 立即创建取消令牌（在获取 DB 会话之前，确保取消 API 随时可用）
		from modules.data import create_cancel_token, cleanup_cancel_token, get_sync_engine
		cancel_token = create_cancel_token(task_id)

		# 创建独立的数据库会话（不依赖主请求的session）
		logger.info(f"[后台任务] 获取独立数据库会话: {task_id}")
		session_manager = get_session_manager()
		async with session_manager.get_session() as session:
			sync_service = DataSyncService(session, event_engine, cancel_token=cancel_token, task_id=task_id)
			logger.info(f"[后台任务] 数据库会话已创建, 准备更新状态: {task_id}")
			sync_task_repo = DataSyncTaskRepository(session)

			# 注入 sync_service 到模块级引擎（统一任务状态管理）
			engine = get_sync_engine()
			if engine:
				engine.sync_service = sync_service

			# 写 running 前先检查是否已被取消（防止覆盖 handler 的 cancelled）
			if cancel_token and cancel_token.is_set():
				logger.info(f"[后台任务] 任务已被取消，跳过执行: {task_id}")
				await sync_task_repo.update(db_id, {"status": "cancelled", "error_message": "用户手动取消"})
				await session.commit()
				return {"task_id": task_id, "status": "cancelled", "message": "任务已被取消"}

			await sync_task_repo.update(db_id, {"status": "running", "processed_records": 0})
			await session.commit()
			logger.info(f"[后台任务] 状态已更新为 running: {task_id}")

			# 向引擎注册任务（统一进度追踪和并发控制）
			if engine and task_id not in engine.tasks:
				from modules.data.engines.sync_engine import SyncTaskConfig, SyncTaskProgress, SyncTaskStatus
				from modules.data.events.types import DataSyncType
				engine.tasks[task_id] = {
					"task_id": task_id,
					"config": SyncTaskConfig(
						sync_type=DataSyncType.FULL,
						data_sources=["tushare"],
					),
					"status": SyncTaskStatus.RUNNING,
					"progress": SyncTaskProgress(),
					"result": None,
					"created_at": datetime.now(),
					"updated_at": datetime.now(),
					"error_count": 0,
					"retry_count": 0,
					"start_time": datetime.now(),
				}
				engine.active_tasks.add(task_id)
				engine.stats["total_tasks"] += 1

			# 3. 发布进度事件
			sync_type = request.tasks[0].data_type if request.tasks else "batch"
			progress_event = DataSyncProgressEvent(
				sync_type=sync_type,
				progress=0.1,
				current_item="初始化同步任务",
				total_items=len(request.tasks),
				processed_items=1,
				task_id=task_id,
				user_id=str(user_id),
				timestamp=datetime.now(),
				source="data_module"
			)
			await event_engine.put(progress_event)  # type: ignore
			logger.info(f"[后台任务] 已发布进度事件: {task_id}")

			# 4. 执行数据同步（含取消检查）
			data_type_list = [t.data_type for t in request.tasks]
			logger.warning(f"[后台任务] 开始执行 {len(request.tasks)} 个数据类型的同步: {data_type_list}")
			for i, dt in enumerate(data_type_list):
				logger.info(f"[后台任务] 同步进度: {i+1}/{len(request.tasks)} - 开始同步 {dt}")
			# 取消检查：DB 状态优先（cancel API 已更新），令牌为补充
			should_cancel = cancel_token.is_set()
			if not should_cancel:
				current = await sync_task_repo.get(db_id)
				should_cancel = current and getattr(current, 'status', None) == 'cancelled'
			if should_cancel:
				logger.warning(f"[后台任务] 检测到取消信号(DB={'Y' if not cancel_token.is_set() and should_cancel else 'N'}, token={'Y' if cancel_token.is_set() else 'N'}), 跳过同步: {task_id}")
				cleanup_cancel_token(task_id)
				if not cancel_token.is_set():
					await sync_task_repo.update(db_id, {"status": "cancelled", "end_time": datetime.now()})
				if engine:
					engine.active_tasks.discard(task_id)
					engine.stats["cancelled_tasks"] += 1
				return
			sync_result = await sync_service.batch_sync_data(
				tasks=request.tasks,
				priority=request.priority,
				user_id=user_id,
				task_id=task_id
			)
			logger.info(f"[后台任务] 同步执行返回: {task_id}, 结果={sync_result.get('success', False)}")

			# 5. 检查取消（用 token 不用 DB，避免 session 缓存问题）
			if cancel_token.is_set():
				logger.info(f"[后台任务] 任务已取消: {task_id}")
				await sync_task_repo.update(db_id, {
					"status": "cancelled",
					"records_processed": sync_result.get("records_processed", 0),
					"records_succeeded": sync_result.get("records_succeeded", 0),
					"records_failed": sync_result.get("records_failed", 0),
					"end_time": datetime.now()
				})
				if engine and task_id in engine.tasks:
					engine.tasks[task_id]["status"] = SyncTaskStatus.CANCELLED
					engine.tasks[task_id]["updated_at"] = datetime.now()
					engine.active_tasks.discard(task_id)
					engine.stats["cancelled_tasks"] += 1
				return

			# 6. 根据实际同步结果更新任务状态
			is_success = sync_result.get("success", False)
			final_status = "completed" if is_success else "failed"
			error_msg = None if is_success else sync_result.get("message", "数据同步失败")
			update_data = {
				"status": final_status,
				"error_message": error_msg,
				"records_processed": sync_result.get("records_processed", 0),
				"records_succeeded": sync_result.get("records_succeeded", 0),
				"records_failed": sync_result.get("records_failed", 0),
				"end_time": datetime.now()
			}
			await sync_task_repo.update(db_id, update_data)
			logger.info(f"[后台任务] 状态已更新为 {final_status}: {task_id}")

			# 更新引擎任务状态
			if engine and task_id in engine.tasks:
				engine.tasks[task_id]["status"] = SyncTaskStatus.COMPLETED if is_success else SyncTaskStatus.FAILED
				engine.tasks[task_id]["updated_at"] = datetime.now()
				engine.active_tasks.discard(task_id)
				if is_success:
					engine.stats["completed_tasks"] += 1
				else:
					engine.stats["failed_tasks"] += 1
				engine.stats["total_records"] += sync_result.get("records_processed", 0)
				engine.stats["last_sync_time"] = datetime.now().timestamp()

			# 7. 发布同步完成或失败事件
			if is_success:
				completed_event = DataSyncCompletedEvent(
					sync_type=sync_type,
					record_count=sync_result.get("records_processed", 0),
					duration_seconds=sync_result.get("duration_seconds", 0),
					success=True,
					summary={
						"records_succeeded": sync_result.get("records_succeeded", 0),
						"records_failed": sync_result.get("records_failed", 0),
						"data_types": [task.data_type for task in request.tasks]
					},
					task_id=task_id,
					user_id=str(user_id),
					timestamp=datetime.now()
				)
				await event_engine.put(completed_event)  # type: ignore
			else:
				failed_event = DataSyncFailedEvent(
					sync_type=sync_type,
					error_message=error_msg or "未知错误",
					task_id=task_id,
					user_id=str(user_id),
					timestamp=datetime.now()
				)
				await event_engine.put(failed_event)  # type: ignore
			logger.info(f"[后台任务] 已发布完成事件: {task_id}")

			# 8. 自动触发数据质量检查（使用独立session，避免受同步事务影响）
			try:
				from modules.data.services.quality_service import DataQualityService
				session_manager = get_session_manager()
				async with session_manager.get_session() as quality_session:
					quality_service = DataQualityService(quality_session)
					for dt in data_type_list:
						try:
							await quality_service.check_data_quality(
								data_type=dt.value if hasattr(dt, 'value') else str(dt),
								user_id=str(user_id)
							)
							logger.info(f"[后台任务] 质量检查完成: {dt}")
						except Exception as qe:
							logger.warning(f"[后台任务] 质量检查跳过 {dt}: {qe}")
			except Exception as qe:
				logger.warning(f"[后台任务] 质量检查初始化失败: {qe}")

			logger.warning(f"[后台任务] 异步数据同步完成: {task_id}, 处理={sync_result.get('records_processed', 0)}, 成功={sync_result.get('records_succeeded', 0)}, 失败={sync_result.get('records_failed', 0)}")
			cleanup_cancel_token(task_id)

	except Exception as e:
		cleanup_cancel_token(task_id)
		logger.warning("=" * 60)
		logger.error(f"[后台任务] 异步数据同步失败: {task_id}, 错误: {str(e)}", exc_info=True)
		logger.warning("=" * 60)

		# 创建独立session处理失败状态更新（原session可能已关闭）
		try:
			session_manager = get_session_manager()
			async with session_manager.get_session() as err_session:
				sync_task_repo = DataSyncTaskRepository(err_session)
				task_result = await sync_task_repo.get_by_task_id(task_id)
				if task_result.success and task_result.data:
					task = task_result.data
					update_data = {
						"status": "failed",
						"error_message": str(e),
						"end_time": datetime.now()
					}
					await sync_task_repo.update(task.id, update_data)
		except Exception as err_handler_error:
			logger.error(f"更新失败状态时出错: {str(err_handler_error)}", exc_info=True)

		# 发布失败事件
		sync_type = request.tasks[0].data_type if request.tasks else "batch"
		fail_event = DataSyncProgressEvent(
			sync_type=sync_type,
			progress=0,
			current_item="同步失败",
			total_items=len(request.tasks),
			processed_items=0,
			task_id=task_id,
			user_id=str(user_id),
			error_message=str(e),
			timestamp=datetime.now(),
			source="data_module"
		)
		await event_engine.put(fail_event)  # type: ignore


def _estimate_research_time (request: ResearchRequest) -> int:
	"""
	估算因子研究所需时间

	Args:
		request: 因子研究请求参数

	Returns:
		int: 估算时间（秒）
	"""
	# 基础时间（每个因子）
	base_time_per_factor = 60

	# 股票数量调整
	stock_count = len(request.universe) if request.universe else 100
	time_per_stock = 2

	# 日期范围调整
	days_count = 250  # 默认一年交易日
	if request.start_date and request.end_date:
		days_diff = (request.end_date - request.start_date).days
		days_count = max(30, min(days_diff, 250))  # 限制在30-250天之间

	# 计算总时间
	total_seconds = (
			base_time_per_factor +
			(stock_count * time_per_stock) +
			(days_count * 0.1)
	)

	# 最少30秒，最多600秒（10分钟）
	return max(30, min(int(total_seconds), 600))


def _estimate_sync_time (request: BatchSyncRequest) -> int:
	"""
	估算数据同步所需时间

	Args:
		request: 批量同步请求参数

	Returns:
		int: 估算时间（秒）
	"""
	# 基础时间（每种数据类型）
	base_time_per_type = 30

	# 数据类型数量调整
	data_types = set()
	for task in request.tasks:
		data_types.add(task.data_type)
	data_type_count = len(data_types) if data_types else 1
	time_per_type = 60

	# 日期范围调整
	days_count = 30  # 默认30天
	# 从任务中获取日期范围
	for task in request.tasks:
		if task.start_date and task.end_date:
			days_diff = (task.end_date - task.start_date).days
			days_count = max(days_count, min(days_diff, 90))  # 限制在1-90天之间

	# 计算总时间
	total_seconds = (
			base_time_per_type +
			(data_type_count * time_per_type) +
			(days_count * 2)
	)

	# 最少10秒，最多300秒（5分钟）
	return max(10, min(int(total_seconds), 300))


# ==================== 模块健康检查与初始化 ====================

async def check_data_module_health (
		session: AsyncSession,
		settings: Settings = get_config().settings
) -> Dict[str, Any]:
	"""
	检查数据模块健康状态 - 包含数据库、缓存、数据完整性等多项检查

	Args:
		session: 数据库会话
		settings: 系统配置

	Returns:
		Dict: 健康状态报告
	"""
	try:
		health_checks = {}

		# 1. 数据库连接检查
		try:
			await session.execute(text("SELECT 1"))
			health_checks["database"] = {
				"status": "healthy",
				"latency_ms": 0
			}
		except Exception as e:
			health_checks["database"] = {
				"status": "unhealthy",
				"error": str(e)
			}

		# 2. 缓存连接检查
		try:
			if hasattr(settings, "REDIS") and settings.REDIS.ENABLED:
				cache = RedisCache(
					host=settings.REDIS.HOST,
					port=settings.REDIS.PORT,
					db=settings.REDIS.DB,
					password=settings.REDIS.PASSWORD
				)
				cache_connected = await cache.ping()
				health_checks["cache"] = {
					"status": "healthy" if cache_connected else "unhealthy",
					"connected": cache_connected
				}
			else:
				health_checks["cache"] = {
					"status": "disabled",
					"message": "Redis未配置"
				}
		except Exception as e:
			health_checks["cache"] = {
				"status": "unhealthy",
				"error": str(e)
			}

		# 3. 数据完整性检查
		try:
			stock_repo = StockBasicRepository(session)
			stock_count_result = await stock_repo.count()
			# 修复：处理不同类型的返回值
			stock_count = stock_count_result if isinstance(stock_count_result, int) else 0

			quote_repo = StockDailyRepository(session)
			quote_count_result = await quote_repo.count()
			quote_count = quote_count_result if isinstance(quote_count_result, int) else 0

			# 因子数据检查
			factor_repo = FactorDataRepository(session)
			factor_count_result = await factor_repo.count()
			factor_count = factor_count_result if isinstance(factor_count_result, int) else 0

			factor_def_repo = FactorDefinitionRepository(session)
			factor_def_count_result = await factor_def_repo.count()
			factor_def_count = factor_def_count_result if isinstance(factor_def_count_result, int) else 0

			# 计算数据覆盖率
			coverage = 0
			if stock_count > 0:
				coverage = quote_count / (stock_count * 250) * 100

			health_checks["data_integrity"] = {
				"status": "healthy" if coverage > 80 else "degraded",
				"stocks": stock_count,
				"quotes": quote_count,
				"factor_data": factor_count,
				"factor_definitions": factor_def_count,
				"coverage": f"{coverage:.1f}%"
			}
		except Exception as e:
			health_checks["data_integrity"] = {
				"status": "unhealthy",
				"error": str(e)
			}

		# 4. 因子研究任务检查
		try:
			research_repo = FactorResearchRepository(session)

			# 待处理任务
			pending_tasks_result = await research_repo.get_many(
				status="pending",
				limit=10
			)
			pending_tasks = pending_tasks_result if isinstance(pending_tasks_result, list) else []

			# 失败任务
			failed_tasks_result = await research_repo.get_many(
				status="failed",
				limit=10
			)
			failed_tasks = failed_tasks_result if isinstance(failed_tasks_result, list) else []

			health_checks["research_tasks"] = {
				"status": "healthy" if len(failed_tasks) == 0 else "warning",
				"pending_tasks": len(pending_tasks),
				"failed_tasks": len(failed_tasks),
				"recent_failures": [
					{
						"research_id": task.research_id,
						"error_message": task.error_message[:100] if task.error_message else None
					}
					for task in failed_tasks[:5]
				]
			}
		except Exception as e:
			health_checks["research_tasks"] = {
				"status": "unhealthy",
				"error": str(e)
			}

		# 5. 同步任务检查
		try:
			sync_task_repo = DataSyncTaskRepository(session)

			# 运行中的任务
			running_tasks_result = await sync_task_repo.get_many(
				status="running",
				limit=5
			)
			running_tasks = running_tasks_result if isinstance(running_tasks_result, list) else []

			# 最近失败的任务
			recent_failed_tasks_result = await sync_task_repo.get_many(
				status="failed",
				limit=5,
				order_by="updated_at_desc"
			)
			recent_failed_tasks = recent_failed_tasks_result if isinstance(recent_failed_tasks_result, list) else []

			health_checks["sync_tasks"] = {
				"status": "healthy" if len(recent_failed_tasks) == 0 else "warning",
				"running_tasks": len(running_tasks),
				"recent_failed_tasks": len(recent_failed_tasks)
			}
		except Exception as e:
			health_checks["sync_tasks"] = {
				"status": "unhealthy",
				"error": str(e)
			}

		# 汇总健康状态
		all_healthy = all(
			check.get("status") in ["healthy", "disabled"]
			for check in health_checks.values()
			if isinstance(check, dict) and "status" in check
		)

		return {
			"overall_status": "healthy" if all_healthy else "degraded",
			"module": "data",
			"checks": health_checks,
			"timestamp": datetime.now().isoformat()
		}

	except Exception as e:
		logger.error(f"数据模块健康检查失败: {str(e)}", exc_info=True)
		return {
			"overall_status": "unhealthy",
			"module": "data",
			"error": str(e),
			"timestamp": datetime.now().isoformat()
		}


async def initialize_data_module (
		session: AsyncSession,
		settings: Settings = None
) -> Dict[str, Any]:
	"""
	初始化数据模块 - 检查表结构、初始化缓存、清理旧任务

	Args:
		session: 数据库会话
		settings: 系统配置

	Returns:
		Dict: 初始化结果报告
	"""
	try:
		if settings is None:
			from api.dependencies.config import get_settings
			settings = get_settings()
		logger.info("开始初始化数据模块...")

		# 1. 检查必要的数据表
		from sqlalchemy import inspect
		# 使用 run_sync 在异步会话上执行同步操作
		tables = await session.run_sync(
			lambda sync_session: inspect(sync_session.connection()).get_table_names()
		)

		required_tables = [
			"stock_basic", "stock_daily", "data_sync_tasks",
			"factor_data", "factor_definitions"
		]

		missing_tables = [t for t in required_tables if t not in tables]

		if missing_tables:
			logger.warning(f"数据模块缺少表: {missing_tables}")
			return {
				"status": "degraded",
				"missing_tables": missing_tables,
				"message": "数据模块初始化完成，但缺少必要的表"
			}

		# 2. 初始化缓存
		cache_initialized = False
		try:
			if hasattr(settings, "REDIS") and settings.REDIS.ENABLED:
				cache = RedisCache(
					host=settings.REDIS.HOST,
					port=settings.REDIS.PORT,
					db=settings.REDIS.DB,
					password=settings.REDIS.PASSWORD
				)
				cache_connected = await cache.ping()
				cache_initialized = cache_connected
				if cache_initialized:
					logger.info("Redis缓存连接成功")
				else:
					logger.warning("Redis缓存连接失败")
			else:
				logger.info("Redis未配置，跳过缓存初始化")
		except Exception as e:
			logger.warning(f"缓存初始化失败: {str(e)}")

		# 3. 清理旧的研究任务（超过30天）
		cleaned_tasks = 0
		try:
			research_repo = FactorResearchRepository(session)
			cutoff_date = datetime.now() - timedelta(days=30)

			# 查询旧任务
			old_tasks_result = await research_repo.get_many(
				created_at__lte=cutoff_date,
				status__in=["pending", "running"],
				limit=100
			)
			old_tasks = old_tasks_result if isinstance(old_tasks_result, list) else []

			# 标记为已取消
			for task in old_tasks:
				update_data = {
					"status": "cancelled",
					"error_message": "任务超时自动取消"
				}
				await research_repo.update(task.id, update_data)
				cleaned_tasks += 1

			if cleaned_tasks > 0:
				logger.info(f"清理了 {cleaned_tasks} 个旧研究任务")
		except Exception as e:
			logger.warning(f"清理旧研究任务失败: {str(e)}")

		# 4. 清理旧同步任务（超过7天）
		cleaned_sync_tasks = 0
		try:
			sync_task_repo = DataSyncTaskRepository(session)
			sync_cutoff_date = datetime.now() - timedelta(days=7)

			# 查询旧完成/失败任务
			old_sync_tasks_result = await sync_task_repo.get_many(
				skip=0,
				limit=100,
				created_at__lte=sync_cutoff_date,
				status__in=["completed", "failed", "cancelled"]
			)
			old_sync_tasks = old_sync_tasks_result if isinstance(old_sync_tasks_result, list) else []

			# 可以在这里执行删除或归档操作
			cleaned_sync_tasks = len(old_sync_tasks)
			if cleaned_sync_tasks > 0:
				logger.info(f"发现 {cleaned_sync_tasks} 个旧的同步任务可清理")
		except Exception as e:
			logger.warning(f"清理旧同步任务失败: {str(e)}")

		# 4.1 清理重启前遗留的运行中任务
		cleaned_running_tasks = 0
		try:
			stale_running = await sync_task_repo.get_running_tasks()
			for task in stale_running:
				await sync_task_repo.update(task.id, {
					"status": "failed",
					"error_message": "服务器重启，任务中断",
					"end_time": datetime.now()
				})
				cleaned_running_tasks += 1
			if cleaned_running_tasks:
				logger.warning(f"已将 {cleaned_running_tasks} 个遗留运行中任务标记为失败")
		except Exception as e:
			logger.warning(f"清理遗留运行中任务失败: {str(e)}")

		# 4.2 清理僵尸 pending 任务（超过 1 小时未进入 running）
		try:
			stale_pending = await sync_task_repo.get_many(status="pending", limit=1000)
			if stale_pending:
				cutoff = datetime.now() - timedelta(hours=1)
				zombie = 0
				for task in stale_pending:
					if task.created_at and task.created_at < cutoff:
						await sync_task_repo.update(task.id, {"status": "failed",
							"error_message": "任务超时未启动（僵尸pending）", "end_time": datetime.now()})
						zombie += 1
				if zombie:
					logger.warning(f"已将 {zombie} 个僵尸pending任务标记为失败")
		except Exception as e:
			logger.warning(f"清理僵尸pending任务失败: {str(e)}")

		# 5. 检查因子数据完整性
		try:
			factor_def_repo = FactorDefinitionRepository(session)
			factor_repo = FactorDataRepository(session)

			factor_def_count_result = await factor_def_repo.count()
			factor_data_count_result = await factor_repo.count()

			factor_def_count = factor_def_count_result if isinstance(factor_def_count_result, int) else 0
			factor_data_count = factor_data_count_result if isinstance(factor_data_count_result, int) else 0

			# 计算平均每个因子的数据量
			avg_per_factor = 0
			if factor_def_count > 0:
				avg_per_factor = factor_data_count / factor_def_count

			factor_integrity = {
				"factor_definitions": factor_def_count,
				"factor_data": factor_data_count,
				"average_per_factor": round(avg_per_factor, 2)
			}

			logger.info(f"因子数据完整性检查: {factor_def_count} 个因子定义, {factor_data_count} 条因子数据")
		except Exception as e:
			logger.warning(f"检查因子数据完整性失败: {str(e)}")
			factor_integrity = {"error": str(e)}

		# 6. 初始化默认因子定义（如果需要）
		initialized_factors = 0
		try:
			factor_def_repo = FactorDefinitionRepository(session)
			default_factors = [
				{
					"factor_code": "PE",
					"factor_name": "市盈率",
					"factor_type": "fundamental",
					"category": "valuation",
					"description": "股价除以每股收益",
					"is_public": True,
					"is_active": True
				},
				{
					"factor_code": "PB",
					"factor_name": "市净率",
					"factor_type": "fundamental",
					"category": "valuation",
					"description": "股价除以每股净资产",
					"is_public": True,
					"is_active": True
				},
				{
					"factor_code": "ROE",
					"factor_name": "净资产收益率",
					"factor_type": "fundamental",
					"category": "profitability",
					"description": "净利润除以净资产",
					"is_public": True,
					"is_active": True
				}
			]

			for factor_data in default_factors:
				existing = await factor_def_repo.get_by_code(factor_data["factor_code"])
				if not existing:
					await factor_def_repo.create(factor_data)
					initialized_factors += 1

			if initialized_factors > 0:
				logger.info(f"初始化了 {initialized_factors} 个默认因子定义")
		except Exception as e:
			logger.warning(f"初始化默认因子定义失败: {str(e)}")

		logger.info("数据模块初始化完成")

		return {
			"status": "healthy",
			"tables": {
				"total": len(tables),
				"required": required_tables,
				"missing": missing_tables
			},
			"cache": {
				"initialized": cache_initialized,
				"host": settings.REDIS.HOST if hasattr(settings, "REDIS") and settings.REDIS.ENABLED else None
			},
			"cleanup": {
				"old_research_tasks_cleaned": cleaned_tasks,
				"old_sync_tasks_found": cleaned_sync_tasks
			},
			"factor_integrity": factor_integrity,
			"factor_initialization": {
				"default_factors_initialized": initialized_factors
			},
			"timestamp": datetime.now().isoformat()
		}

	except Exception as e:
		logger.error(f"数据模块初始化失败: {str(e)}", exc_info=True)
		return {
			"status": "failed",
			"error": str(e),
			"timestamp": datetime.now().isoformat()
		}
