# # -*- coding: utf-8 -*-
# """
# 监控模块API路由
# 基于混合架构设计，负责将HTTP请求路由到监控模块的业务处理层
# 位置：quant_server/api/routers/monitor_router.py
# 监控模块路由
# """
# from typing import Optional, Dict, Any
# from fastapi import APIRouter, Depends, HTTPException, status, Query
# from datetime import datetime, timedelta
# import logging
#
# # 导入架构依赖
# from quant_server.api.dependencies.database import get_db_session
# from quant_server.api.dependencies.auth import get_current_user
# from quant_server.api.dependencies.event_engine import get_event_engine
# from quant_server.api.dependencies.main_engine import get_main_engine
#
# # 导入响应格式化工具
# from quant_server.utils.api_utils.response_formatter import success_response, error_response
#
# # 导入监控模块的业务层处理函数（根据实际实现调整）
# from quant_server.modules.monitor.handlers import (
# 	get_system_metrics,
# 	get_risk_alerts,
# 	get_business_metrics,
# 	get_alert_history,
# 	create_alert_rule,
# 	update_alert_rule,
# 	delete_alert_rule,
# 	trigger_manual_alert,
# 	get_health_status,
# 	get_performance_stats
# )
#
# # 导入监控模块的Pydantic模型（根据实际实现调整）
# from quant_server.modules.monitor.schemas import (
# 	SystemMetricsRequest,
# 	SystemMetricsResponse,
# 	RiskAlertsRequest,
# 	RiskAlertsResponse,
# 	BusinessMetricsRequest,
# 	BusinessMetricsResponse,
# 	AlertHistoryRequest,
# 	AlertHistoryResponse,
# 	AlertRuleRequest,
# 	AlertRuleResponse,
# 	ManualAlertRequest,
# 	HealthStatusResponse,
# 	PerformanceStatsResponse
# )
#
# # 配置日志
# logger = logging.getLogger(__name__)
#
# # 创建路由器实例
# router = APIRouter(
# 	prefix="/monitor",
# 	tags=["监控中心"],
# 	responses={
# 		401: {"description": "认证失败"},
# 		403: {"description": "权限不足"},
# 		500: {"description": "服务器内部错误"}
# 	}
# )
#
#
# # ==================== 系统监控接口 ====================
#
# @router.get("/system/metrics", response_model=SystemMetricsResponse)
# async def get_system_metrics_api (
# 		request: SystemMetricsRequest = Depends(),
# 		current_user: Dict = Depends(get_current_user),
# 		db_session=Depends(get_db_session),
# 		event_engine=Depends(get_event_engine)
# ) -> SystemMetricsResponse:
# 	"""
# 	获取系统监控指标
#
# 	Args:
# 		request: 系统监控请求参数
# 		current_user: 当前登录用户
# 		db_session: 数据库会话
# 		event_engine: 事件引擎
#
# 	Returns:
# 		SystemMetricsResponse: 系统监控响应
# 	"""
# 	try:
# 		logger.info(f"用户 {current_user.get('username')} 请求系统监控指标，参数: {request.dict()}")
#
# 		# 调用业务层处理函数
# 		result = await get_system_metrics(
# 			session=db_session,
# 			request=request,
# 			event_engine=event_engine,
# 			user_id=current_user.get("id")
# 		)
#
# 		return result
#
# 	except Exception as e:
# 		logger.error(f"获取系统监控指标失败: {str(e)}", exc_info=True)
# 		raise HTTPException(
# 			status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
# 			detail=f"获取系统监控指标失败: {str(e)}"
# 		)
#
#
# @router.get("/health", response_model=HealthStatusResponse)
# async def get_health_status_api (
# 		current_user: Dict = Depends(get_current_user),
# 		db_session=Depends(get_db_session),
# 		main_engine=Depends(get_main_engine)
# ) -> HealthStatusResponse:
# 	"""
# 	获取系统健康状态
#
# 	Args:
# 		current_user: 当前登录用户
# 		db_session: 数据库会话
# 		main_engine: 主引擎
#
# 	Returns:
# 		HealthStatusResponse: 健康状态响应
# 	"""
# 	try:
# 		logger.info(f"用户 {current_user.get('username')} 请求系统健康状态")
#
# 		# 调用业务层处理函数
# 		result = await get_health_status(
# 			session=db_session,
# 			main_engine=main_engine,
# 			user_id=current_user.get("id")
# 		)
#
# 		return result
#
# 	except Exception as e:
# 		logger.error(f"获取健康状态失败: {str(e)}", exc_info=True)
# 		raise HTTPException(
# 			status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
# 			detail=f"获取健康状态失败: {str(e)}"
# 		)
#
#
# # ==================== 风险监控接口 ====================
#
# @router.get("/risk/alerts", response_model=RiskAlertsResponse)
# async def get_risk_alerts_api (
# 		request: RiskAlertsRequest = Depends(),
# 		current_user: Dict = Depends(get_current_user),
# 		db_session=Depends(get_db_session)
# ) -> RiskAlertsResponse:
# 	"""
# 	获取风险警报列表
#
# 	Args:
# 		request: 风险警报请求参数
# 		current_user: 当前登录用户
# 		db_session: 数据库会话
#
# 	Returns:
# 		RiskAlertsResponse: 风险警报响应
# 	"""
# 	try:
# 		logger.info(f"用户 {current_user.get('username')} 请求风险警报列表，参数: {request.dict()}")
#
# 		# 调用业务层处理函数
# 		result = await get_risk_alerts(
# 			session=db_session,
# 			request=request,
# 			user_id=current_user.get("id")
# 		)
#
# 		return result
#
# 	except Exception as e:
# 		logger.error(f"获取风险警报失败: {str(e)}", exc_info=True)
# 		raise HTTPException(
# 			status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
# 			detail=f"获取风险警报失败: {str(e)}"
# 		)
#
#
# # ==================== 业务监控接口 ====================
#
# @router.get("/business/metrics", response_model=BusinessMetricsResponse)
# async def get_business_metrics_api (
# 		request: BusinessMetricsRequest = Depends(),
# 		current_user: Dict = Depends(get_current_user),
# 		db_session=Depends(get_db_session)
# ) -> BusinessMetricsResponse:
# 	"""
# 	获取业务监控指标
#
# 	Args:
# 		request: 业务监控请求参数
# 		current_user: 当前登录用户
# 		db_session: 数据库会话
#
# 	Returns:
# 		BusinessMetricsResponse: 业务监控响应
# 	"""
# 	try:
# 		logger.info(f"用户 {current_user.get('username')} 请求业务监控指标，参数: {request.dict()}")
#
# 		# 调用业务层处理函数
# 		result = await get_business_metrics(
# 			session=db_session,
# 			request=request,
# 			user_id=current_user.get("id")
# 		)
#
# 		return result
#
# 	except Exception as e:
# 		logger.error(f"获取业务监控指标失败: {str(e)}", exc_info=True)
# 		raise HTTPException(
# 			status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
# 			detail=f"获取业务监控指标失败: {str(e)}"
# 		)
#
#
# @router.get("/performance/stats", response_model=PerformanceStatsResponse)
# async def get_performance_stats_api (
# 		current_user: Dict = Depends(get_current_user),
# 		db_session=Depends(get_db_session),
# 		event_engine=Depends(get_event_engine)
# ) -> PerformanceStatsResponse:
# 	"""
# 	获取性能统计信息
#
# 	Args:
# 		current_user: 当前登录用户
# 		db_session: 数据库会话
# 		event_engine: 事件引擎
#
# 	Returns:
# 		PerformanceStatsResponse: 性能统计响应
# 	"""
# 	try:
# 		logger.info(f"用户 {current_user.get('username')} 请求性能统计信息")
#
# 		# 调用业务层处理函数
# 		result = await get_performance_stats(
# 			session=db_session,
# 			event_engine=event_engine,
# 			user_id=current_user.get("id")
# 		)
#
# 		return result
#
# 	except Exception as e:
# 		logger.error(f"获取性能统计失败: {str(e)}", exc_info=True)
# 		raise HTTPException(
# 			status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
# 			detail=f"获取性能统计失败: {str(e)}"
# 		)
#
#
# # ==================== 警报管理接口 ====================
#
# @router.get("/alerts/history", response_model=AlertHistoryResponse)
# async def get_alert_history_api (
# 		request: AlertHistoryRequest = Depends(),
# 		current_user: Dict = Depends(get_current_user),
# 		db_session=Depends(get_db_session)
# ) -> AlertHistoryResponse:
# 	"""
# 	获取警报历史记录
#
# 	Args:
# 		request: 警报历史请求参数
# 		current_user: 当前登录用户
# 		db_session: 数据库会话
#
# 	Returns:
# 		AlertHistoryResponse: 警报历史响应
# 	"""
# 	try:
# 		logger.info(f"用户 {current_user.get('username')} 请求警报历史记录，参数: {request.dict()}")
#
# 		# 调用业务层处理函数
# 		result = await get_alert_history(
# 			session=db_session,
# 			request=request,
# 			user_id=current_user.get("id")
# 		)
#
# 		return result
#
# 	except Exception as e:
# 		logger.error(f"获取警报历史失败: {str(e)}", exc_info=True)
# 		raise HTTPException(
# 			status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
# 			detail=f"获取警报历史失败: {str(e)}"
# 		)
#
#
# @router.post("/alerts/rules", response_model=AlertRuleResponse)
# async def create_alert_rule_api (
# 		request: AlertRuleRequest,
# 		current_user: Dict = Depends(get_current_user),
# 		db_session=Depends(get_db_session)
# ) -> AlertRuleResponse:
# 	"""
# 	创建警报规则
#
# 	Args:
# 		request: 警报规则请求
# 		current_user: 当前登录用户
# 		db_session: 数据库会话
#
# 	Returns:
# 		AlertRuleResponse: 警报规则响应
# 	"""
# 	try:
# 		logger.info(f"用户 {current_user.get('username')} 创建警报规则，参数: {request.dict()}")
#
# 		# 检查用户权限
# 		if not current_user.get("can_manage_alerts", False):
# 			raise HTTPException(
# 				status_code=status.HTTP_403_FORBIDDEN,
# 				detail="用户没有管理警报权限"
# 			)
#
# 		# 调用业务层处理函数
# 		result = await create_alert_rule(
# 			session=db_session,
# 			request=request,
# 			user_id=current_user.get("id")
# 		)
#
# 		return result
#
# 	except HTTPException:
# 		raise
# 	except Exception as e:
# 		logger.error(f"创建警报规则失败: {str(e)}", exc_info=True)
# 		raise HTTPException(
# 			status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
# 			detail=f"创建警报规则失败: {str(e)}"
# 		)
#
#
# @router.put("/alerts/rules/{rule_id}", response_model=AlertRuleResponse)
# async def update_alert_rule_api (
# 		rule_id: str,
# 		request: AlertRuleRequest,
# 		current_user: Dict = Depends(get_current_user),
# 		db_session=Depends(get_db_session)
# ) -> AlertRuleResponse:
# 	"""
# 	更新警报规则
#
# 	Args:
# 		rule_id: 规则ID
# 		request: 警报规则请求
# 		current_user: 当前登录用户
# 		db_session: 数据库会话
#
# 	Returns:
# 		AlertRuleResponse: 警报规则响应
# 	"""
# 	try:
# 		logger.info(f"用户 {current_user.get('username')} 更新警报规则 {rule_id}，参数: {request.dict()}")
#
# 		# 检查用户权限
# 		if not current_user.get("can_manage_alerts", False):
# 			raise HTTPException(
# 				status_code=status.HTTP_403_FORBIDDEN,
# 				detail="用户没有管理警报权限"
# 			)
#
# 		# 调用业务层处理函数
# 		result = await update_alert_rule(
# 			session=db_session,
# 			rule_id=rule_id,
# 			request=request,
# 			user_id=current_user.get("id")
# 		)
#
# 		return result
#
# 	except ValueError as e:
# 		logger.warning(f"警报规则不存在: {rule_id}, 错误: {str(e)}")
# 		raise HTTPException(
# 			status_code=status.HTTP_404_NOT_FOUND,
# 			detail=f"警报规则 {rule_id} 不存在"
# 		)
# 	except HTTPException:
# 		raise
# 	except Exception as e:
# 		logger.error(f"更新警报规则失败: {str(e)}", exc_info=True)
# 		raise HTTPException(
# 			status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
# 			detail=f"更新警报规则失败: {str(e)}"
# 		)
#
#
# @router.delete("/alerts/rules/{rule_id}")
# async def delete_alert_rule_api (
# 		rule_id: str,
# 		current_user: Dict = Depends(get_current_user),
# 		db_session=Depends(get_db_session)
# ) -> Dict[str, Any]:
# 	"""
# 	删除警报规则
#
# 	Args:
# 		rule_id: 规则ID
# 		current_user: 当前登录用户
# 		db_session: 数据库会话
#
# 	Returns:
# 		Dict: 删除结果
# 	"""
# 	try:
# 		logger.info(f"用户 {current_user.get('username')} 删除警报规则 {rule_id}")
#
# 		# 检查用户权限
# 		if not current_user.get("can_manage_alerts", False):
# 			raise HTTPException(
# 				status_code=status.HTTP_403_FORBIDDEN,
# 				detail="用户没有管理警报权限"
# 			)
#
# 		# 调用业务层处理函数
# 		result = await delete_alert_rule(
# 			session=db_session,
# 			rule_id=rule_id,
# 			user_id=current_user.get("id")
# 		)
#
# 		return success_response(
# 			message="删除警报规则成功",
# 			data=result
# 		)
#
# 	except ValueError as e:
# 		logger.warning(f"警报规则不存在: {rule_id}, 错误: {str(e)}")
# 		raise HTTPException(
# 			status_code=status.HTTP_404_NOT_FOUND,
# 			detail=f"警报规则 {rule_id} 不存在"
# 		)
# 	except HTTPException:
# 		raise
# 	except Exception as e:
# 		logger.error(f"删除警报规则失败: {str(e)}", exc_info=True)
# 		raise HTTPException(
# 			status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
# 			detail=f"删除警报规则失败: {str(e)}"
# 		)
#
#
# @router.post("/alerts/manual")
# async def trigger_manual_alert_api (
# 		request: ManualAlertRequest,
# 		current_user: Dict = Depends(get_current_user),
# 		db_session=Depends(get_db_session),
# 		event_engine=Depends(get_event_engine)
# ) -> Dict[str, Any]:
# 	"""
# 	触发手动警报
#
# 	Args:
# 		request: 手动警报请求
# 		current_user: 当前登录用户
# 		db_session: 数据库会话
# 		event_engine: 事件引擎
#
# 	Returns:
# 		Dict: 触发结果
# 	"""
# 	try:
# 		logger.info(f"用户 {current_user.get('username')} 触发手动警报，参数: {request.dict()}")
#
# 		# 检查用户权限
# 		if not current_user.get("can_trigger_alerts", False):
# 			raise HTTPException(
# 				status_code=status.HTTP_403_FORBIDDEN,
# 				detail="用户没有触发警报权限"
# 			)
#
# 		# 调用业务层处理函数
# 		result = await trigger_manual_alert(
# 			session=db_session,
# 			request=request,
# 			event_engine=event_engine,
# 			user_id=current_user.get("id")
# 		)
#
# 		return success_response(
# 			message="手动警报触发成功",
# 			data=result
# 		)
#
# 	except HTTPException:
# 		raise
# 	except Exception as e:
# 		logger.error(f"触发手动警报失败: {str(e)}", exc_info=True)
# 		raise HTTPException(
# 			status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
# 			detail=f"触发手动警报失败: {str(e)}"
# 		)
#
#
# # ==================== 实时监控接口 ====================
#
# @router.get("/dashboard")
# async def get_monitor_dashboard (
# 		current_user: Dict = Depends(get_current_user),
# 		db_session=Depends(get_db_session),
# 		main_engine=Depends(get_main_engine),
# 		event_engine=Depends(get_event_engine)
# ) -> Dict[str, Any]:
# 	"""
# 	获取监控仪表板数据
#
# 	Args:
# 		current_user: 当前登录用户
# 		db_session: 数据库会话
# 		main_engine: 主引擎
# 		event_engine: 事件引擎
#
# 	Returns:
# 		Dict: 监控仪表板数据
# 	"""
# 	try:
# 		logger.info(f"用户 {current_user.get('username')} 请求监控仪表板数据")
#
# 		# 这里简化处理，实际应该调用专门的仪表板服务
# 		from sqlalchemy import text
#
# 		# 获取系统状态
# 		engine_status = main_engine.get_status() if main_engine else {"status": "unknown"}
#
# 		# 获取活跃警报数量
# 		active_alerts_result = await db_session.execute(
# 			text("SELECT COUNT(*) FROM alerts WHERE status = 'active' AND is_deleted = 0")
# 		)
# 		active_alerts = active_alerts_result.scalar() or 0
#
# 		# 获取今日警报数量
# 		today = datetime.now().date()
# 		today_alerts_result = await db_session.execute(
# 			text("""
#                 SELECT COUNT(*) FROM alerts
#                 WHERE DATE(created_at) = :today
#                   AND is_deleted = 0
#             """),
# 			{"today": today}
# 		)
# 		today_alerts = today_alerts_result.scalar() or 0
#
# 		return success_response(
# 			message="监控仪表板数据获取成功",
# 			data={
# 				"system_status": {
# 					"main_engine": engine_status.get("status", "unknown"),
# 					"event_engine": "running",  # 简化处理
# 					"database": "connected",
# 					"timestamp": datetime.now().isoformat()
# 				},
# 				"alerts_summary": {
# 					"active": active_alerts,
# 					"today": today_alerts,
# 					"critical": 0,  # 简化处理
# 					"warning": 0
# 				},
# 				"performance": {
# 					"cpu_usage": 0.15,  # 简化处理
# 					"memory_usage": 0.35,
# 					"disk_usage": 0.25,
# 					"response_time_ms": 125
# 				},
# 				"updated_at": datetime.now().isoformat()
# 			}
# 		)
#
# 	except Exception as e:
# 		logger.error(f"获取监控仪表板失败: {str(e)}", exc_info=True)
# 		return error_response(
# 			message="获取监控仪表板失败",
# 			data={"error": str(e)},
# 			status_code=500
# 		)