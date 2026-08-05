# -*- coding: utf-8 -*-
"""组合实盘 API"""
import logging
from typing import Dict

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession

from api.dependencies.auth import get_current_user
from api.dependencies.database import get_db_session
from modules.strategy.composite_schemas import (
	CompositeGroupCreate,
	CompositeGroupUpdate,
	CompositeTriggerRequest,
	CompositeRebalanceRequest,
	CapitalAdjustRequest,
	CompositeAddStrategyRequest,
)
from modules.strategy.services.composite_service import CompositeService
from utils.api_utils.response_formatter import success_response

logger = logging.getLogger(__name__)

router = APIRouter(
	tags=["组合实盘"],
	responses={401: {"description": "认证失败"}, 500: {"description": "服务器内部错误"}},
)

# 模块级 MainEngine 缓存，避免每个请求都创建新实例（资源泄漏）
_main_engine_cache = None


def _get_main_engine():
	"""获取 MainEngine 单例（惰性初始化，缓存复用）。"""
	global _main_engine_cache
	if _main_engine_cache is not None:
		return _main_engine_cache
	try:
		from core.engines.system.main_engine import MainEngine
		_main_engine_cache = MainEngine()
	except Exception as e:
		logger.warning("MainEngine 实例化失败: %s", e)
		_main_engine_cache = None
	return _main_engine_cache


def _get_service(db: AsyncSession) -> CompositeService:
	"""创建 CompositeService。strategy_manager 由 MainEngine 全局单例注入。"""
	mgr = None
	engine = _get_main_engine()
	if engine is not None:
		mgr = engine.get_module_engine("strategy_manager") if hasattr(engine, 'get_module_engine') else None
		if mgr is None:
			logger.warning("CompositeService: strategy_manager 未就绪，组合功能可能受限")
	return CompositeService(session=db, strategy_manager=mgr)


# =============================================================================
# 组合分组 CRUD
# =============================================================================

@router.post("/composite/groups", status_code=201)
async def create_composite_group(
		request: CompositeGroupCreate,
		current_user: Dict = Depends(get_current_user),
		db: AsyncSession = Depends(get_db_session),
):
	"""创建组合分组"""
	try:
		svc = _get_service(db)
		result = await svc.create_group(request.model_dump(), current_user.get("id", ""))
		return success_response(data=result, message="组合创建成功")
	except ValueError as e:
		raise HTTPException(status_code=400, detail=str(e))
	except Exception as e:
		logger.error(f"创建组合失败: {e}", exc_info=True)
		raise HTTPException(status_code=500, detail=str(e))


@router.get("/composite/groups")
async def list_composite_groups(
		current_user: Dict = Depends(get_current_user),
		db: AsyncSession = Depends(get_db_session),
):
	"""列出所有组合分组"""
	try:
		svc = _get_service(db)
		result = await svc.list_groups()
		return success_response(data=result)
	except Exception as e:
		raise HTTPException(status_code=500, detail=str(e))


@router.get("/composite/groups/{group_id}")
async def get_composite_group(
		group_id: str,
		current_user: Dict = Depends(get_current_user),
		db: AsyncSession = Depends(get_db_session),
):
	"""获取组合详情"""
	try:
		svc = _get_service(db)
		result = await svc.get_group(group_id)
		return success_response(data=result)
	except ValueError as e:
		raise HTTPException(status_code=404, detail=str(e))


@router.put("/composite/groups/{group_id}")
async def update_composite_group(
		group_id: str,
		request: CompositeGroupUpdate,
		current_user: Dict = Depends(get_current_user),
		db: AsyncSession = Depends(get_db_session),
):
	"""更新组合"""
	try:
		svc = _get_service(db)
		result = await svc.update_group(group_id, request.model_dump(exclude_none=True))
		return success_response(data=result)
	except ValueError as e:
		raise HTTPException(status_code=404, detail=str(e))


@router.delete("/composite/groups/{group_id}")
async def delete_composite_group(
		group_id: str,
		current_user: Dict = Depends(get_current_user),
		db: AsyncSession = Depends(get_db_session),
):
	"""删除组合"""
	try:
		svc = _get_service(db)
		await svc.delete_group(group_id)
		return success_response(message="组合已删除")
	except ValueError as e:
		raise HTTPException(status_code=404, detail=str(e))


# =============================================================================
# v6.13: 组合成员管理 + 净值
# =============================================================================

@router.post("/composite/groups/{group_id}/strategies")
async def add_strategy_to_group(
		group_id: str,
		request: CompositeAddStrategyRequest,
		current_user: Dict = Depends(get_current_user),
		db: AsyncSession = Depends(get_db_session),
):
	"""组合添加策略（含权重缩放 + 初始化资金）"""
	try:
		svc = _get_service(db)
		result = await svc.add_strategy(
			group_id, request.strategy_id, request.allocator_id,
			request.w0, request.w1, request.w2,
		)
		return success_response(data=result, message="策略已加入组合")
	except ValueError as e:
		raise HTTPException(status_code=400, detail=str(e))
	except Exception as e:
		logger.error(f"组合添加策略失败: {e}", exc_info=True)
		raise HTTPException(status_code=500, detail=str(e))


@router.delete("/composite/groups/{group_id}/strategies/{strategy_id}")
async def remove_strategy_from_group(
		group_id: str,
		strategy_id: str,
		current_user: Dict = Depends(get_current_user),
		db: AsyncSession = Depends(get_db_session),
):
	"""组合移除策略"""
	try:
		svc = _get_service(db)
		result = await svc.remove_strategy(group_id, strategy_id)
		return success_response(data=result, message="策略已移出组合")
	except ValueError as e:
		raise HTTPException(status_code=400, detail=str(e))
	except Exception as e:
		logger.error(f"组合移除策略失败: {e}", exc_info=True)
		raise HTTPException(status_code=500, detail=str(e))


@router.get("/composite/groups/{group_id}/nav")
async def get_composite_nav(
		group_id: str,
		current_user: Dict = Depends(get_current_user),
		db: AsyncSession = Depends(get_db_session),
):
	"""组合净值序列"""
	try:
		svc = _get_service(db)
		result = await svc.get_nav(group_id)
		return success_response(data=result)
	except ValueError as e:
		raise HTTPException(status_code=404, detail=str(e))


# =============================================================================
# 触发 & Rebalance
# =============================================================================

@router.post("/composite/trigger")
async def trigger_composite(
		request: CompositeTriggerRequest,
		current_user: Dict = Depends(get_current_user),
		db: AsyncSession = Depends(get_db_session),
):
	"""组合触发 — 一次触发组合中所有策略"""
	try:
		svc = _get_service(db)
		result = await svc.trigger(
			group_id=request.composite_group_id,
			trade_date_str=request.trade_date,
			end_date_str=request.end_date,
			symbols=request.symbols,
		)
		return success_response(data=result,
		                        message=f"触发 {len(result['strategies_triggered'])} 个策略, {result['total_signals']} 个信号")
	except ValueError as e:
		raise HTTPException(status_code=400, detail=str(e))
	except Exception as e:
		logger.error(f"组合触发失败: {e}", exc_info=True)
		raise HTTPException(status_code=500, detail=str(e))


@router.post("/composite/rebalance")
async def rebalance_composite(
		request: CompositeRebalanceRequest,
		current_user: Dict = Depends(get_current_user),
		db: AsyncSession = Depends(get_db_session),
):
	"""手动触发 rebalance"""
	try:
		svc = _get_service(db)
		result = await svc.rebalance(group_id=request.composite_group_id)
		return success_response(data=result, message="Rebalance 完成")
	except ValueError as e:
		raise HTTPException(status_code=400, detail=str(e))
	except Exception as e:
		logger.error(f"Rebalance 失败: {e}", exc_info=True)
		raise HTTPException(status_code=500, detail=str(e))


@router.post("/composite/strategies/{strategy_id}/capital")
async def adjust_capital(
		strategy_id: str,
		request: CapitalAdjustRequest,
		current_user: Dict = Depends(get_current_user),
		db: AsyncSession = Depends(get_db_session),
):
	"""手动调整策略 allocated_capital"""
	try:
		from modules.strategy.services.execution_service import ExecutionService
		svc = ExecutionService(db)
		result = await svc.update_allocated_capital(
			strategy_id=strategy_id,
			new_capital=request.new_capital,
			user_id=current_user.get("id", ""),
		)
		if not result.get("success"):
			raise HTTPException(status_code=400, detail=result.get("error", "调整失败"))
		return success_response(data=result)
	except HTTPException:
		raise
	except Exception as e:
		raise HTTPException(status_code=500, detail=str(e))
