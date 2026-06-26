# -*- coding: utf-8 -*-
"""
风控模块 API 路由

独立路由，统一管理所有风控相关 HTTP 端点。

端点前缀: /quantTrade/risk
"""

import logging
from typing import Any, Dict

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession

from api.dependencies.auth import get_current_user
from api.dependencies.database import get_db_session
from modules.risk.handlers import (
	get_rules,
	update_rule,
	check_signal,
	get_risk_metrics,
	get_risk_events,
	get_risk_alerts,
	acknowledge_alert,
	check_risk_module_health,
)
from modules.risk.schemas import (
	RiskRuleUpdateRequest,
	RiskRulesListResponse,
	SignalCheckRequest,
	SignalCheckResponse,
	RiskEventsListResponse,
	RiskEventsQueryRequest,
	RiskMetricsResponse,
	RiskAlertsListResponse,
	ThresholdUpdateRequest,
	ThresholdListResponse,
)
from utils.api_utils.response_formatter import success_response, error_response

logger = logging.getLogger(__name__)

router = APIRouter(tags=["风控管理"])


# ==================== 健康检查 ====================


@router.get("/health")
async def health_check(
		session: AsyncSession = Depends(get_db_session),
):
	"""风控模块健康检查"""
	result = await check_risk_module_health(session)
	return success_response(data=result)


# ==================== 规则管理 ====================


@router.get("/rules", response_model=RiskRulesListResponse)
async def list_rules(
		session: AsyncSession = Depends(get_db_session),
		current_user: Dict[str, Any] = Depends(get_current_user),
):
	"""获取所有风控规则及启用状态"""
	try:
		engine = await _get_risk_engine()
		result = await get_rules(session, risk_engine=engine)
		return success_response(data=result)
	except Exception as e:
		logger.error(f"获取规则列表失败: {e}")
		return error_response(message=str(e), code=500)


@router.put("/rules/{rule_name}")
async def toggle_rule(
		rule_name: str,
		request: RiskRuleUpdateRequest,
		session: AsyncSession = Depends(get_db_session),
		current_user: Dict[str, Any] = Depends(get_current_user),
):
	"""启用/禁用风控规则，或更新规则参数"""
	try:
		engine = await _get_risk_engine()
		result = await update_rule(
			session, rule_name,
			enabled=request.enabled,
			params=request.params,
			risk_engine=engine,
		)
		return success_response(data=result)
	except ValueError as e:
		return error_response(message=str(e), code=404)
	except Exception as e:
		logger.error(f"更新规则失败: {e}")
		return error_response(message=str(e), code=500)


# ==================== 信号检查 ====================


@router.post("/check", response_model=SignalCheckResponse)
async def check_trade_signal(
		request: SignalCheckRequest,
		session: AsyncSession = Depends(get_db_session),
		current_user: Dict[str, Any] = Depends(get_current_user),
):
	"""对交易信号执行风控检查"""
	try:
		engine = await _get_risk_engine()
		signal_data = request.model_dump(exclude_none=True)
		result = await check_signal(session, signal_data, risk_engine=engine)
		return success_response(data=result)
	except Exception as e:
		logger.error(f"信号检查失败: {e}")
		return error_response(message=str(e), code=500)


# ==================== 风险指标 ====================


@router.get("/metrics", response_model=RiskMetricsResponse)
async def get_metrics(
		session: AsyncSession = Depends(get_db_session),
		current_user: Dict[str, Any] = Depends(get_current_user),
):
	"""获取实时风险指标"""
	try:
		engine = await _get_risk_engine()
		result = await get_risk_metrics(session, risk_engine=engine)
		return success_response(data=result)
	except Exception as e:
		logger.error(f"获取风险指标失败: {e}")
		return error_response(message=str(e), code=500)


# ==================== 风险事件 ====================


@router.get("/events", response_model=RiskEventsListResponse)
async def list_events(
		request: RiskEventsQueryRequest = Depends(),
		session: AsyncSession = Depends(get_db_session),
		current_user: Dict[str, Any] = Depends(get_current_user),
):
	"""分页查询风控事件历史"""
	try:
		engine = await _get_risk_engine()
		result = await get_risk_events(session, request, risk_engine=engine)
		return success_response(data=result)
	except Exception as e:
		logger.error(f"获取风险事件失败: {e}")
		return error_response(message=str(e), code=500)


# ==================== 告警 ====================


@router.get("/alerts", response_model=RiskAlertsListResponse)
async def list_alerts(
		alert_level: str = None,
		session: AsyncSession = Depends(get_db_session),
		current_user: Dict[str, Any] = Depends(get_current_user),
):
	"""获取活跃的风险告警"""
	try:
		engine = await _get_risk_engine()

		# Create a simple request-like object
		class AlertRequest:
			pass

		req = AlertRequest()
		req.alert_level = alert_level
		result = await get_risk_alerts(session, req, risk_engine=engine)
		return success_response(data=result)
	except Exception as e:
		logger.error(f"获取告警失败: {e}")
		return error_response(message=str(e), code=500)


@router.post("/alerts/{alert_id}/acknowledge")
async def ack_alert(
		alert_id: str,
		session: AsyncSession = Depends(get_db_session),
		current_user: Dict[str, Any] = Depends(get_current_user),
):
	"""确认风险告警"""
	try:
		result = await acknowledge_alert(session, alert_id)
		return success_response(data=result)
	except Exception as e:
		logger.error(f"确认告警失败: {e}")
		return error_response(message=str(e), code=500)


# ==================== 阈值配置 ====================


@router.get("/thresholds", response_model=ThresholdListResponse)
async def list_thresholds(
		session: AsyncSession = Depends(get_db_session),
		current_user: Dict[str, Any] = Depends(get_current_user),
):
	"""获取所有阈值配置"""
	try:
		from modules.risk.handlers import RiskHandler
		engine = await _get_risk_engine()
		handler = RiskHandler(session, risk_engine=engine)
		result = await handler.get_thresholds()
		return success_response(data=result)
	except Exception as e:
		logger.error(f"获取阈值失败: {e}")
		return error_response(message=str(e), code=500)


@router.put("/thresholds/{metric_name}")
async def update_threshold(
		metric_name: str,
		request: ThresholdUpdateRequest,
		session: AsyncSession = Depends(get_db_session),
		current_user: Dict[str, Any] = Depends(get_current_user),
):
	"""更新阈值配置"""
	try:
		from modules.risk.handlers import RiskHandler
		engine = await _get_risk_engine()
		handler = RiskHandler(session, risk_engine=engine)
		result = await handler.update_threshold(
			metric_name=metric_name,
			warning_threshold=request.warning_threshold,
			critical_threshold=request.critical_threshold,
			description=request.description,
			is_active=request.is_active,
		)
		return success_response(data=result)
	except Exception as e:
		logger.error(f"更新阈值失败: {e}")
		return error_response(message=str(e), code=500)


# ==================== 辅助函数 ====================


async def _get_risk_engine():
	"""从 MainEngine 获取 RiskEngine 实例"""
	from api.dependencies.main_engine import get_main_engine
	main_engine = await get_main_engine()
	engine = getattr(main_engine, "_module_engines", {}).get("risk_engine")
	if not engine:
		logger.warning("RiskEngine 未在 MainEngine 中注册，风控模块可能未初始化")
		raise HTTPException(
			status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
			detail="风控引擎未就绪。请确认 risk 模块已正确初始化。",
		)
	return engine
