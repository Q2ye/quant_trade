# -*- coding: utf-8 -*-
"""
数据模块API路由
基于混合架构设计，负责将HTTP请求路由到数据模块的业务处理层
位置：quant_server/api/routers/data_router.py
数据模块路由
"""
from typing import Optional, Dict, List
from fastapi import APIRouter, Depends, HTTPException, status, BackgroundTasks, Query, Body
from datetime import datetime, timedelta
from sqlalchemy import text, select
from sqlalchemy.ext.asyncio import AsyncSession

from starlette.responses import JSONResponse

from utils.api_utils.response_formatter import success_response, error_response
import logging
import uuid

# 导入架构依赖
from api.dependencies.database import get_db_session
from api.dependencies.auth import get_current_user
from api.dependencies.event_engine import get_event_engine
from shared.database.repositories.market.basic.index_repo import IndexRepository
from shared.database.repositories.market.basic.etf_repo import ETFRepository

# 导入数据模块的业务层处理函数
from modules.data.handlers import (
	get_sync_tasks,
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
	get_sync_types_meta,
	get_sync_status_all,  # Phase 5.1: 同步类型元数据
	initialize_data_module, delete_sync_task, delete_sync_tasks_batch
)

# 导入数据模块的Pydantic模型
from modules.data.models import DataTypeInfo
from modules.data.schemas import (
    SyncTaskListResponse,
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
	FactorMetadata,  # 新增：导入 FactorMetadata 模型
	SyncTypesMetaResponse,
	SyncStatusAllResponse,  # Phase 5.1: 同步类型元数据
)
from modules.data.schemas_market import (
	IndexListResponse,
	IndexDetailResponse,
	ETFListResponse,
	ETFDetailResponse,
	SectorListResponse,
	StockHistoryResponse,
	StockFinancialResponse,
)

from core import BusinessException

# 配置日志
logger = logging.getLogger(__name__)

# 创建路由器实例
router = APIRouter(
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
		# 用分页摘要替代完整数据日志，避免打印数千条股票信息
		pagination = result.pagination if hasattr(result, 'pagination') else {}
		logger.info(f"股票列表返回成功: success={result.success}, total={pagination.get('total', '?')}, page={pagination.get('page', '?')}")

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


# ==================== 市场行情数据接口 ====================

@router.get("/indexes", response_model=IndexListResponse)
async def get_indexes_api(
	keyword: Optional[str] = Query(default=None, description="搜索关键词"),
	limit: int = Query(default=100, ge=1, le=500, description="返回数量"),
	current_user: Dict = Depends(get_current_user),
	db_session: AsyncSession = Depends(get_db_session),
) -> IndexListResponse:
	"""获取指数列表"""
	try:
		repo = IndexRepository(db_session)
		if keyword:
			indices = await repo.search_indices(keyword, limit=limit)
		else:
			indices = await repo.index_basic_repo.get_all(limit=limit)

		items = [
			{
				"code": idx.ts_code,
				"name": idx.name,
				"market": getattr(idx, "market", None),
				"publisher": getattr(idx, "publisher", None),
				"category": getattr(idx, "category", None),
				"baseDate": idx.base_date.isoformat() if getattr(idx, "base_date", None) else None,
				"basePoint": float(idx.base_point) if getattr(idx, "base_point", None) else None,
			}
			for idx in indices
		]
		return IndexListResponse(indexes=items)
	except Exception as e:
		logger.error(f"获取指数列表失败: {e}", exc_info=True)
		raise HTTPException(status_code=500, detail=str(e))


@router.get("/indexes/{code}", response_model=IndexDetailResponse)
async def get_index_detail_api(
	code: str,
	current_user: Dict = Depends(get_current_user),
	db_session: AsyncSession = Depends(get_db_session),
) -> IndexDetailResponse:
	"""获取指数详情（含最新行情 + 估值 + 成分股数）"""
	try:
		repo = IndexRepository(db_session)
		basic = await repo.get_index_basic(code)
		if not basic:
			raise HTTPException(status_code=404, detail=f"指数 {code} 不存在")

		latest = await repo.get_latest_index_daily(code)
		# 估值数据（index_dailybasic）
		val = None
		try:
			val = await repo.get_latest_daily_basic(code)
		except Exception:
			pass
		# 成分股数
		comp_count = None
		try:
			comp_count = await repo.count_components(code)
		except Exception:
			pass

		detail: dict = {
			"ts_code": basic.ts_code,
			"name": basic.name,
			"fullname": getattr(basic, "fullname", None),
			"market": getattr(basic, "market", None),
			"publisher": getattr(basic, "publisher", None),
			"category": getattr(basic, "category", None),
			"base_date": basic.base_date.isoformat() if getattr(basic, "base_date", None) else None,
			"base_point": float(basic.base_point) if getattr(basic, "base_point", None) else None,
			"list_date": basic.list_date.isoformat() if getattr(basic, "list_date", None) else None,
		}
		if latest:
			detail.update({
				"close": float(latest.close) if latest.close else None,
				"open": float(latest.open) if getattr(latest, "open", None) else None,
				"high": float(latest.high) if getattr(latest, "high", None) else None,
				"low": float(latest.low) if getattr(latest, "low", None) else None,
				"pre_close": float(latest.pre_close) if getattr(latest, "pre_close", None) else None,
				"change": float(latest.change) if getattr(latest, "change", None) else None,
				"pct_chg": float(latest.pct_chg) if getattr(latest, "pct_chg", None) else None,
				"vol": int(latest.vol) if getattr(latest, "vol", None) else None,
				"amount": float(latest.amount) if getattr(latest, "amount", None) else None,
				"trade_date": latest.trade_date.isoformat() if latest.trade_date else None,
			})
		if val:
			detail.update({
				"pe": float(val.pe) if getattr(val, "pe", None) else None,
				"pb": float(val.pb) if getattr(val, "pb", None) else None,
				"total_mv": float(val.total_mv) if getattr(val, "total_mv", None) else None,
			})
		if comp_count is not None:
			detail["components_count"] = comp_count
		return IndexDetailResponse(index=detail)
	except HTTPException:
		raise
	except Exception as e:
		logger.error(f"获取指数详情失败: {e}", exc_info=True)
		raise HTTPException(status_code=500, detail=str(e))


@router.get("/etfs", response_model=ETFListResponse)
async def get_etfs_api(
	keyword: Optional[str] = Query(default=None, description="搜索关键词"),
	page: int = Query(default=1, ge=1, description="页码"),
	page_size: int = Query(default=50, ge=10, le=200, description="每页数量"),
	current_user: Dict = Depends(get_current_user),
	db_session: AsyncSession = Depends(get_db_session),
) -> ETFListResponse:
	"""获取ETF列表（分页）"""
	try:
		repo = ETFRepository(db_session)
		offset = (page - 1) * page_size
		if keyword:
			etfs = await repo.search_etfs(keyword, limit=page_size, skip=offset)
			total = await repo.count_etfs(active_only=True)
		else:
			etfs = await repo.get_all_etfs(active_only=True, limit=page_size, offset=offset)
			total = await repo.count_etfs(active_only=True)

		# 批量获取最新行情（一次 SQL 批量查询，避免 N+1）
		etf_codes = [etf.ts_code for etf in etfs]
		latest_prices: dict = {}
		if etf_codes:
			try:
				from sqlalchemy import text
				price_rows = await db_session.execute(
					text("""
						SELECT DISTINCT ON (ts_code) ts_code, close, pct_chg, amount
						FROM etf_daily WHERE ts_code = ANY(:codes)
						ORDER BY ts_code, trade_date DESC
					"""), {"codes": etf_codes}
				)
				for row in price_rows:
					latest_prices[row.ts_code] = {
						"close": float(row.close) if row.close else None,
						"pct_chg": float(row.pct_chg) if row.pct_chg else None,
						"amount": float(row.amount) if row.amount else None,
					}
			except Exception:
				pass  # ETF 日线表可能未同步，静默降级

		items = [
			{
				"ts_code": etf.ts_code,
				"name": getattr(etf, "cname", None),
				"shortName": getattr(etf, "csname", None),
				"exchange": getattr(etf, "exchange", None),
				"fundType": getattr(etf, "etf_type", None),
				"indexCode": getattr(etf, "index_code", None),
				"indexName": getattr(etf, "index_name", None),
				"manager": getattr(etf, "mgr_name", None),
				"listDate": etf.list_date.isoformat() if getattr(etf, "list_date", None) else None,
				"managementFee": float(etf.mgt_fee) if getattr(etf, "mgt_fee", None) else None,
				"latestPrice": latest_prices.get(etf.ts_code, {}).get("close"),
				"latestPctChg": latest_prices.get(etf.ts_code, {}).get("pct_chg"),
				"latestAmount": latest_prices.get(etf.ts_code, {}).get("amount"),
			}
			for etf in etfs
		]
		return ETFListResponse(etfs=items, total=total, page=page)
	except Exception as e:
		logger.error(f"获取ETF列表失败: {e}", exc_info=True)
		raise HTTPException(status_code=500, detail=str(e))


@router.get("/etfs/{code}", response_model=ETFDetailResponse)
async def get_etf_detail_api(
	code: str,
	current_user: Dict = Depends(get_current_user),
	db_session: AsyncSession = Depends(get_db_session),
) -> ETFDetailResponse:
	"""获取ETF详情（含最新行情）"""
	try:
		repo = ETFRepository(db_session)
		basic = await repo.get_etf_basic(code)
		if not basic:
			raise HTTPException(status_code=404, detail=f"ETF {code} 不存在")

		latest = await repo.get_latest_etf_daily(code)
		detail = {
			"ts_code": basic.ts_code,
			"name": getattr(basic, "cname", None),
			"shortName": getattr(basic, "csname", None),
			"exchange": getattr(basic, "exchange", None),
			"fundType": getattr(basic, "etf_type", None),
			"indexCode": getattr(basic, "index_code", None),
			"indexName": getattr(basic, "index_name", None),
			"manager": getattr(basic, "mgr_name", None),
			"listDate": basic.list_date.isoformat() if getattr(basic, "list_date", None) else None,
			"managementFee": float(basic.mgt_fee) if getattr(basic, "mgt_fee", None) else None,
		}
		if latest:
			detail.update({
				"latestPrice": float(latest.close) if latest.close else None,
				"latestChange": float(latest.change) if getattr(latest, "change", None) else None,
				"latestPctChg": float(latest.pct_chg) if getattr(latest, "pct_chg", None) else None,
				"latestVolume": int(latest.vol) if getattr(latest, "vol", None) else None,
				"latestAmount": float(latest.amount) if getattr(latest, "amount", None) else None,
			})
		return ETFDetailResponse(etf=detail)
	except HTTPException:
		raise
	except Exception as e:
		logger.error(f"获取ETF详情失败: {e}", exc_info=True)
		raise HTTPException(status_code=500, detail=str(e))


@router.get("/sectors", response_model=SectorListResponse)
async def get_sectors_api(
	current_user: Dict = Depends(get_current_user),
	db_session: AsyncSession = Depends(get_db_session),
) -> SectorListResponse:
	"""获取板块/行业列表（从 stock_basic 汇总）"""
	try:
		result = await db_session.execute(
			text("SELECT industry, COUNT(*) as stock_count FROM stock_basic WHERE industry IS NOT NULL AND industry != '' GROUP BY industry ORDER BY stock_count DESC")
		)
		rows = result.fetchall()
		sectors = [
			{"code": row[0], "name": row[0], "type": "industry", "stockCount": row[1]}
			for row in rows
		]
		return SectorListResponse(sectors=sectors)
	except Exception as e:
		logger.error(f"获取板块列表失败: {e}", exc_info=True)
		raise HTTPException(status_code=500, detail=str(e))


@router.get("/stocks/{code}/history", response_model=StockHistoryResponse)
async def get_stock_history_api(
	code: str,
	start_date: Optional[str] = Query(default=None, description="开始日期 yyyyMMdd"),
	end_date: Optional[str] = Query(default=None, description="结束日期 yyyyMMdd"),
	limit: int = Query(default=200, ge=1, le=5000, description="返回数量"),
	current_user: Dict = Depends(get_current_user),
	db_session: AsyncSession = Depends(get_db_session),
) -> StockHistoryResponse:
	"""获取股票K线历史数据"""
	try:
		from datetime import datetime as dt
		from shared.database.models.data_models import StockDaily

		query = select(StockDaily).where(StockDaily.ts_code == code)
		if start_date:
			query = query.where(StockDaily.trade_date >= dt.strptime(start_date, "%Y%m%d"))
		if end_date:
			query = query.where(StockDaily.trade_date <= dt.strptime(end_date, "%Y%m%d"))
		query = query.order_by(StockDaily.trade_date).limit(limit)

		r = await db_session.execute(query)
		dailies = r.scalars().all()

		items = [
			{
				"timestamp": d.trade_date.isoformat() if d.trade_date else "",
				"open": float(d.open) if d.open else 0,
				"high": float(d.high) if d.high else 0,
				"low": float(d.low) if d.low else 0,
				"close": float(d.close) if d.close else 0,
				"volume": float(d.vol) if getattr(d, "vol", None) else 0,
				"amount": float(d.amount) if d.amount else 0,
			}
			for d in dailies
		]
		return StockHistoryResponse(historical=items)
	except Exception as e:
		logger.error(f"获取股票K线数据失败: {e}", exc_info=True)
		raise HTTPException(status_code=500, detail=str(e))


@router.get("/stocks/{code}/financial", response_model=StockFinancialResponse)
async def get_stock_financial_api(
	code: str,
	report_date: Optional[str] = Query(default=None, description="报告期 yyyyMMdd"),
	limit: int = Query(default=20, ge=1, le=100, description="返回数量"),
	current_user: Dict = Depends(get_current_user),
	db_session: AsyncSession = Depends(get_db_session),
) -> StockFinancialResponse:
	"""获取股票财务数据"""
	try:
		from shared.database.models.data_models import FinancialIncome, FinancialBalance, FinancialCashflow
		from datetime import datetime as dt

		query = select(FinancialIncome).where(FinancialIncome.ts_code == code)
		if report_date:
			query = query.where(FinancialIncome.end_date == dt.strptime(report_date, "%Y%m%d"))
		query = query.order_by(FinancialIncome.end_date.desc()).limit(limit)

		r = await db_session.execute(query)
		statements = r.scalars().all()

		items = [
			{
				"symbol": s.ts_code,
				"report_date": s.end_date.isoformat() if s.end_date else "",
				"eps": float(s.basic_eps) if s.basic_eps else None,
				"bps": None,
				"roe": None,
				"profit_margin": None,
				"debt_to_asset": None,
				"revenue": float(s.revenue) if s.revenue else None,
				"net_profit": None,
				"total_assets": None,
			}
			for s in statements
		]
		return StockFinancialResponse(financial=items)
	except Exception as e:
		logger.error(f"获取财务数据失败: {e}", exc_info=True)
		raise HTTPException(status_code=500, detail=str(e))


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


@router.get("/sync/tasks", response_model=SyncTaskListResponse)
async def get_sync_tasks_api(
        status: Optional[str] = Query(None, description="状态筛选"),
        group: Optional[str] = Query(None, description="分组筛选: 1-7"),
        limit: int = Query(50, ge=1, le=1000, description="每页数量"),
        offset: int = Query(0, ge=0, description="偏移量"),
        current_user: Dict = Depends(get_current_user),
        db_session: AsyncSession = Depends(get_db_session),
) -> SyncTaskListResponse:
    """获取同步任务历史列表"""
    try:
        return await get_sync_tasks(
            session=db_session,
            user_id=current_user.get("id"),
            status=status,
            group=group,
            limit=limit,
            offset=offset,
        )
    except Exception as e:
        logger.error(f"获取同步任务列表失败: {str(e)}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"获取同步任务列表失败: {str(e)}"
        )


@router.post("/sync/cancel")
async def cancel_current_sync_api (
		current_user: Dict = Depends(get_current_user),
		db_session: AsyncSession = Depends(get_db_session),
		event_engine=Depends(get_event_engine)
) -> JSONResponse:
	"""取消当前正在运行的同步任务（无需指定 task_id）"""
	try:
		# 查询当前用户运行中的任务
		result = await db_session.execute(
			text("SELECT task_id FROM data_sync_tasks WHERE status = 'running' AND user_id = :uid ORDER BY start_time DESC LIMIT 1"),
			{"uid": current_user.get("id")}
		)
		row = result.fetchone()
		task_id = row[0] if row else None

		if not task_id:
			raise HTTPException(
				status_code=status.HTTP_404_NOT_FOUND,
				detail="当前没有正在运行的同步任务"
			)

		logger.info(f"用户 {current_user.get('username')} 取消当前同步任务，任务ID: {task_id}")

		cancel_result = await cancel_sync(
			session=db_session,
			task_id=task_id,
			event_engine=event_engine,
			user_id=current_user.get("id")
		)

		return success_response(
			message="取消同步任务成功",
			data=cancel_result
		)
	except HTTPException:
		raise
	except Exception as e:
		logger.error(f"取消同步任务失败: {str(e)}", exc_info=True)
		raise HTTPException(
			status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
			detail=f"取消同步任务失败: {str(e)}"
		)


@router.get("/sync/types", response_model=SyncTypesMetaResponse)
async def get_sync_types_api(
	db_session: AsyncSession = Depends(get_db_session),
) -> SyncTypesMetaResponse:
	"""获取同步类型的分组元数据和预设任务"""
	try:
		return await get_sync_types_meta(session=db_session)
	except Exception as e:
		logger.error(f"获取同步类型元数据失败: {str(e)}", exc_info=True)
		raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=str(e))


@router.get("/sync/status/all", response_model=SyncStatusAllResponse)
async def get_sync_status_all_api(
	db_session: AsyncSession = Depends(get_db_session),
) -> SyncStatusAllResponse:
	"""获取所有同步类型的状态概览"""
	try:
		return await get_sync_status_all(session=db_session)
	except Exception as e:
		logger.error(f"获取同步状态概览失败: {str(e)}", exc_info=True)
		raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=str(e))

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


# ============================================================================
# 支持的数据类型信息映射
# ============================================================================
_DATA_TYPE_INFO_MAP: Dict[str, DataTypeInfo] = {
	# ===== 核心：日线/周线交易必须 =====
	"stock_list":             DataTypeInfo(code="stock_list",             name="股票列表",     description="沪深A股股票基本信息列表",                     estimated_time=30,  requires_clean=True,  is_core=True),
	"st_list":                DataTypeInfo(code="st_list",                name="ST股票列表",   description="ST/*ST特别处理股票变更历史记录",             estimated_time=30,  requires_clean=False, is_core=False),
	"company":                DataTypeInfo(code="company",                name="公司基本信息", description="上市公司基本信息（注册地址/法人/主营等）",   estimated_time=60,  requires_clean=False, is_core=False),
	"daily_quotes":           DataTypeInfo(code="daily_quotes",           name="日线行情",     description="股票日K线行情数据（开高低收量额）",         estimated_time=120, requires_clean=True,  is_core=True),
	"weekly_quotes":          DataTypeInfo(code="weekly_quotes",          name="周线行情",     description="股票周K线行情数据",                         estimated_time=60,  requires_clean=True,  is_core=False),
	"monthly_quotes":         DataTypeInfo(code="monthly_quotes",         name="月线行情",     description="股票月K线行情数据",                         estimated_time=30,  requires_clean=True,  is_core=False),
	"adj_factor":             DataTypeInfo(code="adj_factor",             name="复权因子",     description="股票复权因子数据（前复权/后复权）",         estimated_time=60,  requires_clean=False, is_core=True),
	"daily_basic":            DataTypeInfo(code="daily_basic",            name="每日指标",     description="股票每日基本面指标（PE/PB/换手率等）",      estimated_time=90,  requires_clean=True,  is_core=True),
	"calendar":               DataTypeInfo(code="calendar",               name="交易日历",     description="沪深京交易所交易日历数据",                   estimated_time=10,  requires_clean=False, is_core=True),
	"financial_indicator":    DataTypeInfo(code="financial_indicator",    name="财务指标",     description="上市公司核心财务指标（ROE/ROA/毛利率等）",   estimated_time=120, requires_clean=True,  is_core=True),
	"financial_data":         DataTypeInfo(code="financial_data",         name="财务报表",     description="利润表+资产负债表+现金流量表（三表合并同步）", estimated_time=360, requires_clean=True,  is_core=True),
    "financial_income":       DataTypeInfo(code="financial_income",       name="利润表",     description="上市公司利润表数据",                           estimated_time=600, requires_clean=True,  is_core=True),
    "financial_balance":      DataTypeInfo(code="financial_balance",      name="资产负债表", description="上市公司资产负债表数据",                         estimated_time=600, requires_clean=True,  is_core=True),
    "financial_cashflow":     DataTypeInfo(code="financial_cashflow",     name="现金流量表", description="上市公司现金流量表数据",                         estimated_time=600, requires_clean=True,  is_core=True),
	"moneyflow":              DataTypeInfo(code="moneyflow",              name="资金流向",     description="个股及大盘资金流向数据（主力/散户/北向）",   estimated_time=90,  requires_clean=True,  is_core=True),
	"index_basic":            DataTypeInfo(code="index_basic",            name="指数基本信息", description="沪深市场全部指数基本信息（代码/名称/基期等）", estimated_time=30,  requires_clean=False, is_core=True),
	"index_daily":            DataTypeInfo(code="index_daily",            name="指数日线行情", description="指数日线行情数据（开高低收量额）",           estimated_time=60,  requires_clean=True,  is_core=True),
	# ===== 扩展：选股加分项 =====
	"dividend":               DataTypeInfo(code="dividend",               name="分红送股",     description="上市公司分红送股预案及实施数据",             estimated_time=60,  requires_clean=False, is_core=False),
	"forecast":               DataTypeInfo(code="forecast",               name="业绩预告",     description="上市公司业绩预告数据",                       estimated_time=60,  requires_clean=False, is_core=False),
	"express":                DataTypeInfo(code="express",                name="业绩快报",     description="上市公司业绩快报数据",                       estimated_time=60,  requires_clean=False, is_core=False),
	"suspend":                DataTypeInfo(code="suspend",                name="停复牌",       description="股票停牌/复牌信息",                         estimated_time=30,  requires_clean=False, is_core=False),
	"business_income":        DataTypeInfo(code="business_income",        name="主营业务收入", description="上市公司主营业务收入按行业/产品/地区构成",   estimated_time=90,  requires_clean=False, is_core=False),
	"audit_opinion":          DataTypeInfo(code="audit_opinion",          name="审计意见",     description="上市公司审计意见及审计机构信息",             estimated_time=30,  requires_clean=False, is_core=False),
	# ===== ETF =====
	"etf_basic":              DataTypeInfo(code="etf_basic",              name="ETF基本信息",  description="ETF基金基本信息（代码/名称/管理人/规模）",  estimated_time=30,  requires_clean=True,  is_core=False),
	"etf_daily":              DataTypeInfo(code="etf_daily",              name="ETF日线行情",  description="ETF日线行情数据（开高低收量额）",           estimated_time=120, requires_clean=True,  is_core=False),
	"fund_adj_factor":        DataTypeInfo(code="fund_adj_factor",        name="基金复权因子", description="基金复权因子数据",                           estimated_time=60,  requires_clean=False, is_core=False),
	"etf_index":              DataTypeInfo(code="etf_index",              name="ETF指数",      description="ETF跟踪指数成分及权重",                     estimated_time=60,  requires_clean=False, is_core=False),
	"etf_share":              DataTypeInfo(code="etf_share",              name="ETF份额",      description="ETF基金份额变动数据",                       estimated_time=60,  requires_clean=False, is_core=False),
	# ===== 公司治理 =====
	"managers":               DataTypeInfo(code="managers",               name="管理层信息",   description="上市公司董监高管理层人员信息",             estimated_time=120, requires_clean=False, is_core=False),
	"rewards":                DataTypeInfo(code="rewards",                name="管理层薪酬",   description="管理层薪酬及持股变动数据",                 estimated_time=120, requires_clean=False, is_core=False),
	# ===== 事件驱动数据 =====
	"stock_hsgt":            DataTypeInfo(code="stock_hsgt",            name="沪深港通股票列表", description="沪深港通标的股票名单（深股通/港股通深/沪股通/港股通沪）", estimated_time=20,  requires_clean=False, is_core=False),
	"st_stockrisk":          DataTypeInfo(code="st_stockrisk",          name="ST风险警示板", description="当前处于风险警示板的股票列表及ST变动原因",                 estimated_time=10,  requires_clean=False, is_core=False),
	"disclosure_date":       DataTypeInfo(code="disclosure_date",       name="财报披露日期", description="上市公司财报预计披露日期与实际披露日期，事件驱动策略核心",     estimated_time=15,  requires_clean=False, is_core=False),
	"share_float":           DataTypeInfo(code="share_float",           name="限售股解禁",   description="限售股解禁计划（解禁日期、股份数、股东）",                   estimated_time=15,  requires_clean=False, is_core=False),
	# ===== 高频/大体积：全量同步排除，仅手动同步 =====
	"minute_quotes":          DataTypeInfo(code="minute_quotes",          name="分钟行情",     description="⚠️股票分钟级行情（数据量极大，仅手动同步）",  estimated_time=300, requires_clean=False, is_core=False, is_available=False),
	"etf_minute":             DataTypeInfo(code="etf_minute",             name="ETF分钟行情",  description="⚠️ETF分钟级行情（数据量极大，仅手动同步）",   estimated_time=180, requires_clean=False, is_core=False, is_available=False),
	"tick_quotes":            DataTypeInfo(code="tick_quotes",            name="逐笔行情",     description="⚠️股票逐笔成交明细（数据量极大，仅手动同步）", estimated_time=600, requires_clean=False, is_core=False, is_available=False),
    # ===== 宏观数据 =====
    "cpi":                   DataTypeInfo(code="cpi",                   name="CPI",          description="居民消费价格指数月度数据",                     estimated_time=10,  requires_clean=False, is_core=False),
    "ppi":                   DataTypeInfo(code="ppi",                   name="PPI",          description="工业生产者出厂价格指数月度数据",               estimated_time=10,  requires_clean=False, is_core=False),
    "gdp":                   DataTypeInfo(code="gdp",                   name="GDP",          description="国内生产总值季度数据",                         estimated_time=10,  requires_clean=False, is_core=False),
    # ===== 指数扩展 =====
    "index_weight":          DataTypeInfo(code="index_weight",          name="指数成分权重", description="指数成分股及权重分布数据",                     estimated_time=30,  requires_clean=False, is_core=False),
    "index_weekly":          DataTypeInfo(code="index_weekly",          name="指数周线行情", description="指数周K线行情数据",                             estimated_time=20,  requires_clean=True,  is_core=False),
    # ===== 股东数据 =====
    "stk_holdernumber":      DataTypeInfo(code="stk_holdernumber",      name="股东人数",     description="上市公司股东户数变化趋势，散户化/机构化分析核心数据",     estimated_time=60,  requires_clean=False, is_core=False),
    "top10_holders":         DataTypeInfo(code="top10_holders",         name="前十大股东",   description="上市公司前十大股东持有数量及比例，筹码集中度分析",       estimated_time=90,  requires_clean=False, is_core=False),
    "top10_floatholders":    DataTypeInfo(code="top10_floatholders",    name="前十大流通股东", description="上市公司前十大流通股东持有数量及比例，机构持仓变动追踪", estimated_time=90,  requires_clean=False, is_core=False),
    "pledge_stat":           DataTypeInfo(code="pledge_stat",           name="股权质押统计", description="上市公司股权质押汇总数据（质押次数/质押比例），风险预警核心", estimated_time=60,  requires_clean=False, is_core=False),
    "stk_holdertrade":       DataTypeInfo(code="stk_holdertrade",       name="股东增减持",   description="大股东/高管增减持明细，产业资本行为信号",                 estimated_time=30,  requires_clean=False, is_core=False),
    # ===== Phase 3 新增 =====
    "index_sw_classify":     DataTypeInfo(code="index_sw_classify",     name="申万行业分类", description="申万行业分类（L1/L2/L3三级），个股行业归属分析基础",     estimated_time=20,  requires_clean=False, is_core=False),
    "index_sw_member":       DataTypeInfo(code="index_sw_member",       name="申万行业成分", description="申万行业成分股权重及进出记录，行业轮动策略核心",           estimated_time=20,  requires_clean=False, is_core=False),
    "index_dailybasic":      DataTypeInfo(code="index_dailybasic",      name="大盘指数每日指标", description="6大核心指数每日估值/市值/换手率指标，市场情绪分析",     estimated_time=30,  requires_clean=False, is_core=False),
    "forecast_pro":          DataTypeInfo(code="forecast_pro",          name="券商盈利预测", description="券商研究所盈利预测报告（需8000积分），基本面量化核心",     estimated_time=120, requires_clean=False, is_core=False),
    "moneyflow_hsgt":        DataTypeInfo(code="moneyflow_hsgt",        name="沪深港通资金流向", description="北向/南向资金当日净流入流出数据，外资动向追踪",         estimated_time=15,  requires_clean=False, is_core=False),
    "index_sw_daily":        DataTypeInfo(code="index_sw_daily",        name="申万行业日线行情", description="申万2021版31个一级行业日线行情（OHLCV+PE+PB+市值）", estimated_time=120, requires_clean=False, is_core=False),
    # ===== Phase 4 新增 =====
    "daily_limit":           DataTypeInfo(code="daily_limit",           name="涨跌停价格",     description="股票每日涨停价/跌停价/前收盘价",                             estimated_time=30,  requires_clean=False, is_core=False),
    "stk_factor":            DataTypeInfo(code="stk_factor",            name="技术因子(基础)", description="股票技术指标基础版（MACD/KDJ/RSI/BOLL/CCI等33个指标，不复权）", estimated_time=180, requires_clean=False, is_core=False),
    "stk_factor_pro":        DataTypeInfo(code="stk_factor_pro",        name="技术因子(专业)", description="股票技术指标专业版（200+指标，含三复权版本，需6000积分）",  estimated_time=300, requires_clean=False, is_core=False),
    "idx_factor_pro":        DataTypeInfo(code="idx_factor_pro",        name="指数技术因子(专业)", description="指数技术指标专业版（200+指标，仅不复权版本，需5000积分）",  estimated_time=120, requires_clean=False, is_core=False),
}


@router.get("/sync/supported-data-types")
async def get_supported_data_types_api() -> list:
	"""获取支持的数据类型列表及详细信息"""
	result = list(_DATA_TYPE_INFO_MAP.values())
	result.sort(key=lambda x: (not x.is_core, x.code))
	return [
		{
			"code": r.code,
			"name": r.name,
			"description": r.description,
			"estimated_time": r.estimated_time,
			"is_core": r.is_core,
		}
		for r in result
	]


@router.delete("/sync/tasks/batch")
async def delete_sync_tasks_batch_api (
		task_ids: List[str] = Body(..., description="要删除的任务ID列表"),
		current_user: Dict = Depends(get_current_user),
		db_session: AsyncSession = Depends(get_db_session)
) -> JSONResponse:
	"""
	批量删除同步任务记录

	逐一删除，含权限和状态校验，返回成功/失败明细。
	"""
	try:
		result = await delete_sync_tasks_batch(
			session=db_session,
			task_ids=task_ids,
			user_id=current_user.get("id")
		)
		return JSONResponse(content=result)
	except Exception as e:
		logger.error(f"批量删除同步任务失败: {str(e)}", exc_info=True)
		raise HTTPException(
			status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
			detail=f"批量删除同步任务失败: {str(e)}"
		)


@router.delete("/sync/tasks/{task_id}")
async def delete_sync_task_api (
		task_id: str,
		current_user: Dict = Depends(get_current_user),
		db_session: AsyncSession = Depends(get_db_session)
) -> JSONResponse:
	"""
	删除同步任务记录

	仅允许删除已完成/失败/取消状态的任务，运行中的任务需先取消。
	"""
	try:
		result = await delete_sync_task(
			session=db_session,
			task_id=task_id,
			user_id=current_user.get("id")
		)
		return JSONResponse(content=result)
	except Exception as e:
		logger.error(f"删除同步任务失败: {str(e)}", exc_info=True)
		raise HTTPException(
			status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
			detail=f"删除同步任务失败: {str(e)}"
		)

# ==================== 数据质量检查接口 ====================

@router.get("/quality", response_model=DataQualityResponse)
async def get_data_quality_api (
		request: DataQualityRequest = Depends(),
		current_user: Dict = Depends(get_current_user),
		db_session: AsyncSession = Depends(get_db_session),
		check: bool = False,
) -> DataQualityResponse:
	"""
	获取数据质量报告

	Args:
		request: 数据质量请求参数
		current_user: 当前登录用户
		db_session: 数据库会话
		check: True=执行新检查, False=返回最近一次结果（默认）

	Returns:
		DataQualityResponse: 数据质量响应
	"""
	try:
		logger.debug(f"用户 {current_user.get('username')} 请求数据质量报告，参数: {request.model_dump()}")

		# 调用业务层处理函数
		result = await get_data_quality(
			session=db_session,
			request=request,
			user_id=current_user.get("id"),
			run_check=check,
		)

		return result

	except Exception as e:
		logger.error(f"获取数据质量报告失败: {str(e)}", exc_info=True)
		raise HTTPException(
			status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
			detail=f"获取数据质量报告失败: {str(e)}"
		)


@router.delete("/quality")
async def delete_quality_records_api(
	data_type: Optional[str] = None,
	current_user: Dict = Depends(get_current_user),
	db_session: AsyncSession = Depends(get_db_session)
):
	"""删除数据质量检查记录"""
	try:
		from shared.database.repositories.analysis.factor.data_quality_check_repo import DataQualityCheckRepository
		repo = DataQualityCheckRepository(db_session)
		if data_type:
			records = await repo.get_by_data_type(data_type, limit=1000)
		else:
			records = await repo.get_latest_checks(limit=1000)
		count = 0
		for r in records:
			await db_session.delete(r)
			count += 1
		await db_session.commit()
		logger.info(f"用户 {current_user.get('username')} 删除了 {count} 条质量检查记录")
		return success_response(message=f"已删除 {count} 条记录", data={"deleted": count})
	except Exception as e:
		logger.error(f"删除质量记录失败: {str(e)}")
		raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=str(e))


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
		page = request.page or 1
		page_size = request.page_size or 20
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
		logger.debug(f"用户 {current_user.get('username')} 请求数据模块健康检查")

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
		if current_user.get("role") not in ("admin", "super_admin", "superadmin"):
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

	# 查询股票总数
		stock_count_result = await db_session.execute(
			text("SELECT COUNT(*) FROM stock_basic")
		)
		stock_count = stock_count_result.scalar() or 0
		
		# 查询活跃股票数量（近30个交易日有行情数据）
		active_stock_result = await db_session.execute(
			text("SELECT COUNT(DISTINCT ts_code) FROM stock_daily "
				"WHERE trade_date >= :cutoff ")
			, {"cutoff": (datetime.now() - timedelta(days=30)).strftime("%Y%m%d")}
		)
		active_stock_count = active_stock_result.scalar() or 0

		# 查询行情数据数量
		quote_count_result = await db_session.execute(
			text("SELECT COUNT(*) FROM stock_daily ")
		)
		quote_count = quote_count_result.scalar() or 0
		
		# 查询实际表占用空间（PostgreSQL），降级使用行估算
		try:
			size_result = await db_session.execute(
				text("SELECT pg_total_relation_size('stock_daily') / (1024.0 * 1024 * 1024) AS size_gb")
			)
			estimated_size_gb = round(float(size_result.scalar() or 0), 2)
		except BusinessException:
			# 降级：按每行约250 字节估算
			estimated_size_gb = round(quote_count * 250.0 / (1024**3), 2)

		# 查询最近同步时间
		latest_sync_result = await db_session.execute(
			text("""
                SELECT MAX(updated_at)
                FROM data_sync_tasks
                WHERE status = 'completed'
                
            """)
		)
		latest_sync = latest_sync_result.scalar()
		
		# 查询最近24小时完成的同步任务数
		sync_24h_result = await db_session.execute(
			text("SELECT COUNT(*) FROM data_sync_tasks "
				"WHERE status = 'completed' AND updated_at >= :since ")
			, {"since": datetime.now() - timedelta(hours=24)}
		)
		sync_last_24h = sync_24h_result.scalar() or 0

		# 查询数据覆盖范围
		date_range_result = await db_session.execute(
			text("""
                SELECT MIN(trade_date), MAX(trade_date)
                FROM stock_daily
                
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
					"active": active_stock_count
				},
				"quotes": {
					"daily": quote_count,
					"estimated_size_gb": estimated_size_gb
				},
				"sync": {
					"latest": latest_sync.isoformat() if latest_sync else None,
					"last_24h": sync_last_24h
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