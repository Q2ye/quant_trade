# -*- coding: utf-8 -*-
"""
数据模块业务处理层
基于混合架构设计，实现数据模块的核心业务逻辑
位置：quant_server/modules/data/handlers.py
数据API处理函数
设计原则：
1. 使用共享Repository进行数据访问
2. 依赖事件引擎进行模块间通信
3. 业务逻辑与API层分离
4. 统一的异常处理
"""
from typing import List, Dict, Any, Optional, Tuple
from datetime import datetime, date, timedelta
import logging
import asyncio
from sqlalchemy.ext.asyncio import AsyncSession
from fastapi import BackgroundTasks

# 导入共享层组件
from quant_server.shared.database.repositories.stock_repo import StockRepository
from quant_server.shared.database.repositories.quote_repo import DailyQuoteRepository
from quant_server.shared.database.repositories.sync_task_repo import SyncTaskRepository
from quant_server.shared.database.repositories.factor_repo import FactorRepository
from quant_server.shared.config.settings import Settings
from quant_server.shared.cache.redis_cache import RedisCache

# 导入核心基础设施
from quant_server.core.engines.system.event_engine import EventEngine
from quant_server.core.engines.system.main_engine import MainEngine
from quant_server.core.events.data_events import (
	DataSyncedEvent,
	SyncProgressEvent,
	DataQualityEvent,
	FactorResearchEvent
)

# 导入数据模块内部组件
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
from quant_server.modules.data.services.sync_service import DataSyncService
from quant_server.modules.data.services.quality_service import DataQualityService
from quant_server.modules.data.services.research_service import FactorResearchService
from quant_server.modules.data.services.market_service import MarketDataService
from quant_server.modules.data.engines.sync_engine import SyncEngine

# 配置日志
logger = logging.getLogger(__name__)


# ==================== 基础数据查询处理函数 ====================

async def get_stock_list (
		session: AsyncSession,
		request: StockListRequest,
		user_id: int
) -> StockListResponse:
	"""
	获取股票列表业务处理

	Args:
		session: 数据库会话
		request: 股票列表请求
		user_id: 用户ID

	Returns:
		StockListResponse: 股票列表响应
	"""
	try:
		logger.info(f"处理获取股票列表请求，用户ID: {user_id}, 参数: {request.dict()}")

		# 使用共享Repository
		stock_repo = StockRepository(session)

		# 构建查询条件
		filters = []
		if request.exchange:
			filters.append(StockRepository.model.exchange == request.exchange)
		if request.industry:
			filters.append(StockRepository.model.industry == request.industry)
		if request.name_keyword:
			filters.append(StockRepository.model.name.contains(request.name_keyword))
		if request.ts_code:
			filters.append(StockRepository.model.ts_code == request.ts_code)

		# 获取股票数据
		stocks = await stock_repo.get_many(
			*filters,
			skip=(request.page - 1) * request.page_size,
			limit=request.page_size
		)

		# 获取总数
		total = await stock_repo.count(*filters)

		# 转换为响应模型
		stock_items = []
		for stock in stocks:
			stock_items.append({
				"ts_code": stock.ts_code,
				"name": stock.name,
				"exchange": stock.exchange,
				"industry": stock.industry,
				"market": stock.market,
				"list_date": stock.list_date.isoformat() if stock.list_date else None,
				"is_hs": stock.is_hs
			})

		return StockListResponse(
			stocks=stock_items,
			total=total,
			page=request.page,
			page_size=request.page_size,
			total_pages=(total + request.page_size - 1) // request.page_size
		)

	except Exception as e:
		logger.error(f"获取股票列表业务处理失败: {str(e)}", exc_info=True)
		raise


async def get_stock_detail (
		session: AsyncSession,
		ts_code: str,
		request: StockDetailRequest,
		user_id: int
) -> StockDetailResponse:
	"""
	获取股票详情业务处理

	Args:
		session: 数据库会话
		ts_code: 股票代码
		request: 股票详情请求
		user_id: 用户ID

	Returns:
		StockDetailResponse: 股票详情响应
	"""
	try:
		logger.info(f"处理获取股票详情请求，用户ID: {user_id}, 股票代码: {ts_code}")

		# 使用共享Repository
		stock_repo = StockRepository(session)

		# 获取股票信息
		stock = await stock_repo.get_by_ts_code(ts_code)
		if not stock:
			raise ValueError(f"股票 {ts_code} 不存在")

		# 获取最新行情（如果需要）
		latest_quote = None
		if request.include_latest_quote:
			quote_repo = QuoteRepository(session)
			latest_quote = await quote_repo.get_latest_by_ts_code(ts_code)

		# 构建响应
		response_data = {
			"ts_code": stock.ts_code,
			"name": stock.name,
			"exchange": stock.exchange,
			"industry": stock.industry,
			"market": stock.market,
			"list_date": stock.list_date.isoformat() if stock.list_date else None,
			"delist_date": stock.delist_date.isoformat() if stock.delist_date else None,
			"is_hs": stock.is_hs,
			"area": stock.area,
			"fullname": stock.fullname,
			"enname": stock.enname,
			"cnspell": stock.cnspell,
			"market_cap": float(stock.market_cap) if stock.market_cap else None,
			"circ_mv": float(stock.circ_mv) if stock.circ_mv else None,
			"updated_at": stock.updated_at.isoformat()
		}

		if latest_quote:
			response_data["latest_quote"] = {
				"trade_date": latest_quote.trade_date.isoformat(),
				"open": float(latest_quote.open) if latest_quote.open else None,
				"high": float(latest_quote.high) if latest_quote.high else None,
				"low": float(latest_quote.low) if latest_quote.low else None,
				"close": float(latest_quote.close) if latest_quote.close else None,
				"pre_close": float(latest_quote.pre_close) if latest_quote.pre_close else None,
				"change": float(latest_quote.change) if latest_quote.change else None,
				"pct_chg": float(latest_quote.pct_chg) if latest_quote.pct_chg else None,
				"vol": float(latest_quote.vol) if latest_quote.vol else None,
				"amount": float(latest_quote.amount) if latest_quote.amount else None
			}

		return StockDetailResponse(**response_data)

	except ValueError:
		raise
	except Exception as e:
		logger.error(f"获取股票详情业务处理失败: {str(e)}", exc_info=True)
		raise


async def get_historical_quotes (
		session: AsyncSession,
		request: HistoricalQuotesRequest,
		event_engine: EventEngine,
		user_id: int
) -> HistoricalQuotesResponse:
	"""
	获取历史行情数据业务处理

	Args:
		session: 数据库会话
		request: 历史行情请求
		event_engine: 事件引擎
		user_id: 用户ID

	Returns:
		HistoricalQuotesResponse: 历史行情响应
	"""
	try:
		logger.info(f"处理获取历史行情请求，用户ID: {user_id}, 参数: {request.dict()}")

		# 验证参数
		if request.start_date and request.end_date:
			if request.start_date > request.end_date:
				raise ValueError("开始日期不能晚于结束日期")

		# 使用市场数据服务
		market_service = MarketDataService(session, event_engine)

		# 获取历史行情数据
		quotes_data = await market_service.get_historical_quotes(
			ts_code=request.ts_code,
			start_date=request.start_date,
			end_date=request.end_date,
			freq=request.freq,
			adj=request.adj,
			fields=request.fields
		)

		# 发布数据访问事件
		await event_engine.put(
			DataSyncedEvent(
				data_type="historical_quotes",
				record_count=len(quotes_data),
				ts_code=request.ts_code,
				user_id=user_id
			)
		)

		return HistoricalQuotesResponse(
			ts_code=request.ts_code,
			quotes=quotes_data,
			count=len(quotes_data),
			start_date=request.start_date,
			end_date=request.end_date,
			freq=request.freq
		)

	except ValueError:
		raise
	except Exception as e:
		logger.error(f"获取历史行情业务处理失败: {str(e)}", exc_info=True)
		raise


# ==================== 数据同步处理函数 ====================

async def sync_market_data (
		session: AsyncSession,
		data_type: str,
		start_date: Optional[date],
		end_date: Optional[date],
		ts_codes: Optional[List[str]],
		event_engine: EventEngine,
		user_id: int
) -> Dict[str, Any]:
	"""
	同步市场数据业务处理

	Args:
		session: 数据库会话
		data_type: 数据类型
		start_date: 开始日期
		end_date: 结束日期
		ts_codes: 股票代码列表
		event_engine: 事件引擎
		user_id: 用户ID

	Returns:
		Dict: 同步结果
	"""
	try:
		logger.info(f"处理同步市场数据请求，用户ID: {user_id}, 数据类型: {data_type}")

		# 使用数据同步服务
		sync_service = DataSyncService(session, event_engine)

		# 执行同步
		result = await sync_service.sync_market_data(
			data_type=data_type,
			start_date=start_date,
			end_date=end_date,
			ts_codes=ts_codes,
			user_id=user_id
		)

		return result

	except Exception as e:
		logger.error(f"同步市场数据业务处理失败: {str(e)}", exc_info=True)
		raise


async def batch_sync_data (
		session: AsyncSession,
		request: BatchSyncRequest,
		event_engine: EventEngine,
		main_engine: MainEngine,
		user_id: int,
		background_tasks: BackgroundTasks
) -> BatchSyncResponse:
	"""
	批量同步数据业务处理

	Args:
		session: 数据库会话
		request: 批量同步请求
		event_engine: 事件引擎
		main_engine: 主引擎
		user_id: 用户ID
		background_tasks: 后台任务

	Returns:
		BatchSyncResponse: 批量同步响应
	"""
	try:
		logger.info(f"处理批量同步数据请求，用户ID: {user_id}, 参数: {request.dict()}")

		# 使用同步任务Repository
		sync_task_repo = SyncTaskRepository(session)

		# 创建同步任务记录
		task_data = {
			"task_id": f"batch_sync_{datetime.now().strftime('%Y%m%d_%H%M%S')}",
			"user_id": user_id,
			"data_types": request.data_types,
			"status": "pending",
			"total_items": len(request.data_types),
			"completed_items": 0,
			"start_date": request.start_date,
			"end_date": request.end_date,
			"ts_codes": request.ts_codes,
			"priority": request.priority.value if request.priority else "normal"
		}

		task = await sync_task_repo.create(task_data)

		# 根据同步模式决定执行方式
		if request.sync_mode == "sync":
			# 同步执行
			sync_engine = SyncEngine(session, event_engine)
			results = await sync_engine.execute_batch_sync(request, task.task_id)

			# 更新任务状态
			await sync_task_repo.update(task.id, {
				"status": "completed",
				"completed_items": len(request.data_types),
				"results": results,
				"completed_at": datetime.now()
			})

			return BatchSyncResponse(
				task_id=task.task_id,
				status="completed",
				message="批量同步完成",
				total_tasks=len(request.data_types),
				completed_tasks=len(request.data_types),
				results=results
			)

		else:
			# 异步执行（后台任务）
			from modules.data.tasks.sync_tasks import execute_async_batch_sync

			# 添加到后台任务
			background_tasks.add_task(
				execute_async_batch_sync,
				session=session,
				task_id=task.task_id,
				request=request,
				event_engine=event_engine,
				user_id=user_id
			)

			# 更新任务状态
			await sync_task_repo.update(task.id, {
				"status": "running",
				"started_at": datetime.now()
			})

			return BatchSyncResponse(
				task_id=task.task_id,
				status="started",
				message="批量同步已开始，将在后台执行",
				total_tasks=len(request.data_types),
				completed_tasks=0,
				estimated_time=estimate_sync_time(request)
			)

	except Exception as e:
		logger.error(f"批量同步数据业务处理失败: {str(e)}", exc_info=True)
		raise


async def quick_sync_data (
		session: AsyncSession,
		request: QuickSyncRequest,
		event_engine: EventEngine,
		user_id: int,
		background_tasks: BackgroundTasks
) -> BatchSyncResponse:
	"""
	快速同步数据业务处理

	Args:
		session: 数据库会话
		request: 快速同步请求
		event_engine: 事件引擎
		user_id: 用户ID
		background_tasks: 后台任务

	Returns:
		BatchSyncResponse: 快速同步响应
	"""
	try:
		logger.info(f"处理快速同步数据请求，用户ID: {user_id}, 参数: {request.dict()}")

		# 定义快速同步的数据类型
		quick_data_types = ["stock_basic", "trade_calendar", "daily", "daily_basic"]

		# 创建批量同步请求
		batch_request = BatchSyncRequest(
			data_types=quick_data_types,
			days=request.days or 7,
			sync_mode="async",
			priority="high"
		)

		# 调用批量同步处理函数
		return await batch_sync_data(
			session=session,
			request=batch_request,
			event_engine=event_engine,
			main_engine=None,  # 快速同步不需要主引擎
			user_id=user_id,
			background_tasks=background_tasks
		)

	except Exception as e:
		logger.error(f"快速同步数据业务处理失败: {str(e)}", exc_info=True)
		raise


async def get_sync_status (
		session: AsyncSession,
		task_id: Optional[str],
		user_id: int
) -> SyncStatusResponse:
	"""
	获取同步状态业务处理

	Args:
		session: 数据库会话
		task_id: 任务ID
		user_id: 用户ID

	Returns:
		SyncStatusResponse: 同步状态响应
	"""
	try:
		logger.info(f"处理获取同步状态请求，用户ID: {user_id}, 任务ID: {task_id}")

		# 使用同步任务Repository
		sync_task_repo = SyncTaskRepository(session)

		if task_id:
			# 获取指定任务状态
			task = await sync_task_repo.get_by_task_id(task_id)
			if not task:
				raise ValueError(f"任务 {task_id} 不存在")

			# 检查用户权限
			if task.user_id != user_id:
				raise ValueError("无权查看此任务状态")

			return SyncStatusResponse(
				task_id=task.task_id,
				status=task.status,
				progress=task.completed_items / task.total_items * 100 if task.total_items > 0 else 0,
				total_items=task.total_items,
				completed_items=task.completed_items,
				started_at=task.started_at.isoformat() if task.started_at else None,
				completed_at=task.completed_at.isoformat() if task.completed_at else None,
				error_message=task.error_message,
				results=task.results
			)
		else:
			# 获取用户最近的任务状态
			tasks = await sync_task_repo.get_recent_tasks(user_id, limit=10)

			recent_tasks = []
			for task in tasks:
				recent_tasks.append({
					"task_id": task.task_id,
					"status": task.status,
					"progress": task.completed_items / task.total_items * 100 if task.total_items > 0 else 0,
					"data_types": task.data_types,
					"started_at": task.started_at.isoformat() if task.started_at else None,
					"completed_at": task.completed_at.isoformat() if task.completed_at else None
				})

			# 获取系统整体同步状态
			total_tasks = await sync_task_repo.count_by_user(user_id)
			completed_tasks = await sync_task_repo.count_by_status(user_id, "completed")
			running_tasks = await sync_task_repo.count_by_status(user_id, "running")

			return SyncStatusResponse(
				task_id=None,
				status="summary",
				progress=completed_tasks / total_tasks * 100 if total_tasks > 0 else 100,
				total_items=total_tasks,
				completed_items=completed_tasks,
				running_tasks=running_tasks,
				recent_tasks=recent_tasks
			)

	except ValueError:
		raise
	except Exception as e:
		logger.error(f"获取同步状态业务处理失败: {str(e)}", exc_info=True)
		raise


async def cancel_sync (
		session: AsyncSession,
		task_id: str,
		event_engine: EventEngine,
		user_id: int
) -> Dict[str, Any]:
	"""
	取消同步任务业务处理

	Args:
		session: 数据库会话
		task_id: 任务ID
		event_engine: 事件引擎
		user_id: 用户ID

	Returns:
		Dict: 取消结果
	"""
	try:
		logger.info(f"处理取消同步任务请求，用户ID: {user_id}, 任务ID: {task_id}")

		# 使用同步任务Repository
		sync_task_repo = SyncTaskRepository(session)

		# 获取任务
		task = await sync_task_repo.get_by_task_id(task_id)
		if not task:
			raise ValueError(f"任务 {task_id} 不存在")

		# 检查用户权限
		if task.user_id != user_id:
			raise ValueError("无权取消此任务")

		# 检查任务状态
		if task.status not in ["pending", "running"]:
			raise ValueError(f"任务状态为 {task.status}，无法取消")

		# 更新任务状态
		await sync_task_repo.update(task.id, {
			"status": "cancelled",
			"cancelled_at": datetime.now(),
			"error_message": "任务被用户取消"
		})

		# 发布任务取消事件
		await event_engine.put(
			SyncProgressEvent(
				task_id=task_id,
				progress=0,
				status="cancelled",
				message="同步任务已取消",
				user_id=user_id
			)
		)

		return {
			"task_id": task_id,
			"status": "cancelled",
			"cancelled_at": datetime.now().isoformat(),
			"message": "同步任务已成功取消"
		}

	except ValueError:
		raise
	except Exception as e:
		logger.error(f"取消同步任务业务处理失败: {str(e)}", exc_info=True)
		raise


# ==================== 数据质量检查处理函数 ====================

async def get_data_quality (
		session: AsyncSession,
		request: DataQualityRequest,
		user_id: int
) -> DataQualityResponse:
	"""
	获取数据质量报告业务处理

	Args:
		session: 数据库会话
		request: 数据质量请求
		user_id: 用户ID

	Returns:
		DataQualityResponse: 数据质量响应
	"""
	try:
		logger.info(f"处理获取数据质量报告请求，用户ID: {user_id}, 参数: {request.dict()}")

		# 使用数据质量服务
		quality_service = DataQualityService(session)

		# 获取数据质量报告
		quality_report = await quality_service.get_quality_report(
			data_type=request.data_type,
			start_date=request.start_date,
			end_date=request.end_date,
			ts_code=request.ts_code
		)

		return DataQualityResponse(
			data_type=request.data_type,
			report_date=datetime.now().date().isoformat(),
			metrics=quality_report["metrics"],
			issues=quality_report["issues"],
			suggestions=quality_report["suggestions"],
			overall_score=quality_report["overall_score"]
		)

	except Exception as e:
		logger.error(f"获取数据质量报告业务处理失败: {str(e)}", exc_info=True)
		raise


# ==================== 因子数据处理函数 ====================

async def get_factor_data (
		session: AsyncSession,
		request: FactorRequest,
		user_id: int
) -> FactorResponse:
	"""
	获取因子数据业务处理

	Args:
		session: 数据库会话
		request: 因子数据请求
		user_id: 用户ID

	Returns:
		FactorResponse: 因子数据响应
	"""
	try:
		logger.info(f"处理获取因子数据请求，用户ID: {user_id}, 参数: {request.dict()}")

		# 使用因子Repository
		factor_repo = FactorRepository(session)

		# 构建查询条件
		filters = []
		if request.factor_name:
			filters.append(FactorRepository.model.factor_name == request.factor_name)
		if request.ts_code:
			filters.append(FactorRepository.model.ts_code == request.ts_code)
		if request.start_date:
			filters.append(FactorRepository.model.trade_date >= request.start_date)
		if request.end_date:
			filters.append(FactorRepository.model.trade_date <= request.end_date)

		# 获取因子数据
		factors = await factor_repo.get_many(
			*filters,
			skip=(request.page - 1) * request.page_size,
			limit=request.page_size,
			order_by=FactorRepository.model.trade_date.desc()
		)

		# 获取总数
		total = await factor_repo.count(*filters)

		# 转换为响应格式
		factor_items = []
		for factor in factors:
			factor_items.append({
				"ts_code": factor.ts_code,
				"trade_date": factor.trade_date.isoformat(),
				"factor_name": factor.factor_name,
				"factor_value": float(factor.factor_value) if factor.factor_value else None,
				"percentile": float(factor.percentile) if factor.percentile else None,
				"updated_at": factor.updated_at.isoformat()
			})

		# 获取可用的因子列表
		available_factors = await factor_repo.get_available_factors()

		return FactorResponse(
			factors=factor_items,
			total=total,
			page=request.page,
			page_size=request.page_size,
			total_pages=(total + request.page_size - 1) // request.page_size,
			available_factors=available_factors
		)

	except Exception as e:
		logger.error(f"获取因子数据业务处理失败: {str(e)}", exc_info=True)
		raise


async def research_factor (
		session: AsyncSession,
		request: ResearchRequest,
		event_engine: EventEngine,
		user_id: int
) -> ResearchResponse:
	"""
	因子研究业务处理

	Args:
		session: 数据库会话
		request: 因子研究请求
		event_engine: 事件引擎
		user_id: 用户ID

	Returns:
		ResearchResponse: 因子研究响应
	"""
	try:
		logger.info(f"处理因子研究请求，用户ID: {user_id}, 参数: {request.dict()}")

		# 使用因子研究服务
		research_service = FactorResearchService(session, event_engine)

		# 执行因子研究
		research_result = await research_service.research_factor(
			factor_definition=request.factor_definition,
			universe=request.universe,
			start_date=request.start_date,
			end_date=request.end_date,
			parameters=request.parameters,
			user_id=user_id
		)

		# 发布因子研究事件
		await event_engine.put(
			FactorResearchEvent(
				factor_name=request.factor_definition.get("name"),
				status="completed",
				user_id=user_id
			)
		)

		return ResearchResponse(
			research_id=research_result["research_id"],
			factor_name=research_result["factor_name"],
			status=research_result["status"],
			metrics=research_result["metrics"],
			charts=research_result["charts"],
			created_at=research_result["created_at"],
			message=research_result["message"]
		)

	except Exception as e:
		logger.error(f"因子研究业务处理失败: {str(e)}", exc_info=True)
		raise


# ==================== 辅助函数 ====================

def estimate_sync_time (request: BatchSyncRequest) -> int:
	"""
	估算同步时间

	Args:
		request: 批量同步请求

	Returns:
		int: 估算时间（秒）
	"""
	# 基础时间估算
	base_time_per_type = {
		"stock_basic": 30,
		"trade_calendar": 5,
		"daily": 120,
		"weekly": 60,
		"monthly": 45,
		"adj_factor": 25,
		"daily_basic": 50,
		"moneyflow": 75
	}

	# 计算基础时间
	total_seconds = 0
	for data_type in request.data_types:
		total_seconds += base_time_per_type.get(data_type, 30)

	# 根据股票数量调整
	stock_count = len(request.ts_codes) if request.ts_codes else 5000
	if stock_count > 1000:
		total_seconds = total_seconds * stock_count // 1000

	# 根据天数调整
	if request.days and request.days > 30:
		total_seconds = total_seconds * request.days // 30

	return max(60, total_seconds)  # 最少60秒


async def update_sync_progress (
		session: AsyncSession,
		task_id: str,
		progress: float,
		current_task: str,
		event_engine: EventEngine,
		user_id: int
) -> None:
	"""
	更新同步进度

	Args:
		session: 数据库会话
		task_id: 任务ID
		progress: 进度（0-100）
		current_task: 当前任务描述
		event_engine: 事件引擎
		user_id: 用户ID
	"""
	try:
		# 使用同步任务Repository
		sync_task_repo = SyncTaskRepository(session)

		# 获取任务
		task = await sync_task_repo.get_by_task_id(task_id)
		if not task:
			logger.warning(f"更新进度失败：任务 {task_id} 不存在")
			return

		# 计算完成的项目数
		completed_items = int(task.total_items * progress / 100)

		# 更新任务进度
		await sync_task_repo.update(task.id, {
			"completed_items": completed_items,
			"progress": progress,
			"current_task": current_task,
			"updated_at": datetime.now()
		})

		# 发布进度事件
		await event_engine.put(
			SyncProgressEvent(
				task_id=task_id,
				progress=progress,
				status="running",
				message=current_task,
				user_id=user_id
			)
		)

	except Exception as e:
		logger.error(f"更新同步进度失败: {str(e)}", exc_info=True)


async def validate_sync_request (request: BatchSyncRequest) -> Tuple[bool, Optional[str]]:
	"""
	验证同步请求参数

	Args:
		request: 批量同步请求

	Returns:
		Tuple[bool, Optional[str]]: (是否有效, 错误信息)
	"""
	try:
		# 验证数据类型
		valid_data_types = [
			"stock_basic", "trade_calendar", "daily", "weekly", "monthly",
			"adj_factor", "daily_basic", "moneyflow", "etf", "daily_limit"
		]

		for data_type in request.data_types:
			if data_type not in valid_data_types:
				return False, f"无效的数据类型: {data_type}"

		# 验证日期范围
		if request.start_date and request.end_date:
			if request.start_date > request.end_date:
				return False, "开始日期不能晚于结束日期"

			# 检查日期范围是否过大
			days_diff = (request.end_date - request.start_date).days
			if days_diff > 365 * 5:  # 限制5年
				return False, "日期范围不能超过5年"

		# 验证股票代码格式
		if request.ts_codes:
			for ts_code in request.ts_codes:
				if not (len(ts_code) == 9 or len(ts_code) == 6):
					return False, f"股票代码格式错误: {ts_code}"

		return True, None

	except Exception as e:
		return False, f"验证请求参数失败: {str(e)}"


async def cleanup_old_sync_tasks (session: AsyncSession, days: int = 30) -> int:
	"""
	清理旧的同步任务记录

	Args:
		session: 数据库会话
		days: 保留天数

	Returns:
		int: 清理的任务数
	"""
	try:
		sync_task_repo = SyncTaskRepository(session)

		# 计算截止日期
		cutoff_date = datetime.now() - timedelta(days=days)

		# 标记旧任务为已删除
		deleted_count = await sync_task_repo.mark_old_tasks_deleted(cutoff_date)

		logger.info(f"清理了 {deleted_count} 条超过 {days} 天的同步任务记录")

		return deleted_count

	except Exception as e:
		logger.error(f"清理旧同步任务失败: {str(e)}", exc_info=True)
		return 0


# ==================== 数据模块初始化函数 ====================

async def initialize_data_module (
		session: AsyncSession,
		event_engine: EventEngine,
		settings: Settings
) -> Dict[str, Any]:
	"""
	初始化数据模块

	Args:
		session: 数据库会话
		event_engine: 事件引擎
		settings: 系统设置

	Returns:
		Dict: 初始化结果
	"""
	try:
		logger.info("开始初始化数据模块...")

		# 检查必要的数据表
		from sqlalchemy import inspect
		inspector = inspect(session.bind)
		tables = inspector.get_table_names()

		required_tables = ["stocks", "daily_quotes", "sync_tasks", "factors"]
		missing_tables = [t for t in required_tables if t not in tables]

		if missing_tables:
			logger.warning(f"数据模块缺少表: {missing_tables}")
			return {
				"status": "degraded",
				"missing_tables": missing_tables,
				"message": "数据模块初始化完成，但缺少必要的表"
			}

		# 初始化缓存
		cache = RedisCache(
			host=settings.redis_host,
			port=settings.redis_port,
			db=settings.redis_db,
			password=settings.redis_password
		)

		# 测试缓存连接
		cache_connected = await cache.test_connection()

		# 清理旧的任务记录
		cleaned_tasks = await cleanup_old_sync_tasks(session)

		logger.info("数据模块初始化完成")

		return {
			"status": "healthy",
			"tables": {
				"total": len(tables),
				"required": required_tables,
				"missing": missing_tables
			},
			"cache": {
				"connected": cache_connected,
				"host": settings.redis_host
			},
			"cleanup": {
				"old_tasks_removed": cleaned_tasks
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


# ==================== 数据模块健康检查函数 ====================

async def check_data_module_health (
		session: AsyncSession,
		cache: RedisCache
) -> Dict[str, Any]:
	"""
	检查数据模块健康状态

	Args:
		session: 数据库会话
		cache: 缓存实例

	Returns:
		Dict: 健康状态
	"""
	try:
		health_checks = {}

		# 1. 检查数据库连接
		from sqlalchemy import text
		try:
			await session.execute(text("SELECT 1"))
			health_checks["database"] = {
				"status": "healthy",
				"latency_ms": 0  # 简化处理
			}
		except Exception as e:
			health_checks["database"] = {
				"status": "unhealthy",
				"error": str(e)
			}

		# 2. 检查缓存连接
		try:
			cache_connected = await cache.test_connection()
			health_checks["cache"] = {
				"status": "healthy" if cache_connected else "unhealthy",
				"connected": cache_connected
			}
		except Exception as e:
			health_checks["cache"] = {
				"status": "unhealthy",
				"error": str(e)
			}

		# 3. 检查数据完整性
		try:
			stock_repo = StockRepository(session)
			stock_count = await stock_repo.count()

			quote_repo = QuoteRepository(session)
			quote_count = await quote_repo.count()

			health_checks["data_integrity"] = {
				"status": "healthy",
				"stocks": stock_count,
				"quotes": quote_count,
				"coverage": f"{quote_count / (stock_count * 250) * 100:.1f}%" if stock_count > 0 else "0%"
			}
		except Exception as e:
			health_checks["data_integrity"] = {
				"status": "unhealthy",
				"error": str(e)
			}

		# 汇总健康状态
		all_healthy = all(
			check["status"] == "healthy"
			for check in health_checks.values()
			if isinstance(check, dict)
		)

		return {
			"overall_status": "healthy" if all_healthy else "degraded",
			"checks": health_checks,
			"timestamp": datetime.now().isoformat()
		}

	except Exception as e:
		logger.error(f"数据模块健康检查失败: {str(e)}", exc_info=True)
		return {
			"overall_status": "unhealthy",
			"error": str(e),
			"timestamp": datetime.now().isoformat()
		}