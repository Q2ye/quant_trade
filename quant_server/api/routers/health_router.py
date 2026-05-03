# -*- coding: utf-8 -*-
"""
健康检查API路由
提供系统健康状态检查和探针端点
位置：quant_server/api/routers/health_router.py
"""
from typing import Dict
from fastapi import APIRouter, Depends
from datetime import datetime
import logging

from starlette.responses import JSONResponse

# 导入架构依赖
from api.dependencies.database import get_db_session
from api.dependencies.main_engine import get_main_engine
from api.dependencies.event_engine import get_event_engine

# 导入响应格式化工具
from utils.api_utils.response_formatter import success_response, error_response

# 配置日志
logger = logging.getLogger(__name__)

# 创建路由器实例
router = APIRouter(
	prefix="",
	tags=["健康检查"],
	responses={
		200: {"description": "健康检查成功"},
		503: {"description": "服务不可用"}
	}
)


@router.get("/")
async def health_root () -> JSONResponse:
	"""
	健康检查根端点

	Returns:
		Dict: 健康状态
	"""
	return success_response(
		message="量化交易系统运行正常",
		data={
			"service": "quant_server",
			"status": "healthy",
			"timestamp": datetime.now().isoformat(),
			"version": "1.0.0"
		}
	)


@router.get("/live")
async def liveness_probe () -> JSONResponse:
	"""
	存活探针（Kubernetes Liveness Probe）

	Returns:
		Dict: 存活状态
	"""
	try:
		# 简单检查应用是否运行
		return success_response(
			message="应用存活",
			data={
				"status": "alive",
				"timestamp": datetime.now().isoformat()
			}
		)
	except Exception as e:
		logger.error(f"存活探针检查失败: {str(e)}")
		return error_response(
			message="应用不存活",
			data={"error": str(e)},
			status_code=503
		)


@router.get("/ready")
async def readiness_probe (
		db_session=Depends(get_db_session),
		main_engine=Depends(get_main_engine),
		event_engine=Depends(get_event_engine)
) -> JSONResponse:
	"""
	就绪探针（Kubernetes Readiness Probe）
	检查所有依赖服务的可用性

	Args:
		db_session: 数据库会话
		main_engine: 主引擎
		event_engine: 事件引擎

	Returns:
		Dict: 就绪状态
	"""
	checks = {}
	all_healthy = True

	try:
		# 检查数据库连接
		from sqlalchemy import text
		await db_session.execute(text("SELECT 1"))
		checks["database"] = {"status": "healthy", "message": "数据库连接正常"}
	except Exception as e:
		checks["database"] = {"status": "unhealthy", "message": f"数据库连接失败: {str(e)}"}
		all_healthy = False
		logger.error(f"数据库健康检查失败: {str(e)}")

	try:
		# 检查主引擎
		if main_engine:
			engine_status = main_engine.get_status()
			checks["main_engine"] = {
				"status": "healthy" if engine_status.get("status") == "running" else "unhealthy",
				"message": f"主引擎状态: {engine_status.get('status', 'unknown')}",
				"details": engine_status
			}
		else:
			checks["main_engine"] = {"status": "unhealthy", "message": "主引擎未初始化"}
			all_healthy = False
	except Exception as e:
		checks["main_engine"] = {"status": "unhealthy", "message": f"主引擎检查失败: {str(e)}"}
		all_healthy = False
		logger.error(f"主引擎健康检查失败: {str(e)}")

	try:
		# 检查事件引擎
		if event_engine:
			checks["event_engine"] = {"status": "healthy", "message": "事件引擎运行正常"}
		else:
			checks["event_engine"] = {"status": "unhealthy", "message": "事件引擎未初始化"}
			all_healthy = False
	except Exception as e:
		checks["event_engine"] = {"status": "unhealthy", "message": f"事件引擎检查失败: {str(e)}"}
		all_healthy = False
		logger.error(f"事件引擎健康检查失败: {str(e)}")

	# 返回检查结果
	if all_healthy:
		return success_response(
			message="系统就绪",
			data={
				"status": "ready",
				"checks": checks,
				"timestamp": datetime.now().isoformat()
			}
		)
	else:
		return error_response(
			message="系统未就绪",
			data={
				"status": "not_ready",
				"checks": checks,
				"timestamp": datetime.now().isoformat()
			},
			status_code=503
		)


@router.get("/detailed")
async def detailed_health_check (
		db_session=Depends(get_db_session),
		main_engine=Depends(get_main_engine),
		event_engine=Depends(get_event_engine)
) -> JSONResponse:
	"""
	详细健康检查
	提供系统各个组件的详细健康状态

	Args:
		db_session: 数据库会话
		main_engine: 主引擎
		event_engine: 事件引擎

	Returns:
		Dict: 详细健康状态
	"""
	components = {}

	try:
		# 数据库详细检查
		from sqlalchemy import text, inspect

		# 检查连接
		await db_session.execute(text("SELECT 1"))

		# 检查关键数据表
		tables = await db_session.bind.run_sync(
			lambda sync_conn: inspect(sync_conn).get_table_names()
		)

		required_tables = ["stocks", "daily_quotes", "users", "strategies", "orders"]
		missing_tables = [t for t in required_tables if t not in tables]

		# 获取表记录数统计
		table_stats = {}
		for table in ["stocks", "daily_quotes"]:
			if table in tables:
				count_result = await db_session.execute(
					text(f"SELECT COUNT(*) FROM {table} WHERE is_deleted = 0")
				)
				table_stats[table] = count_result.scalar() or 0

		components["database"] = {
			"status": "healthy" if not missing_tables else "degraded",
			"connection": "connected",
			"tables": {
				"total": len(tables),
				"missing": missing_tables,
				"stats": table_stats
			}
		}
	except Exception as e:
		components["database"] = {
			"status": "unhealthy",
			"error": str(e)
		}

	try:
		# 主引擎详细检查
		if main_engine:
			engine_status = main_engine.get_status()
			components["main_engine"] = {
				"status": "healthy" if engine_status.get("status") == "running" else "unhealthy",
				"details": engine_status
			}
		else:
			components["main_engine"] = {
				"status": "unhealthy",
				"error": "主引擎未初始化"
			}
	except Exception as e:
		components["main_engine"] = {
			"status": "unhealthy",
			"error": str(e)
		}

	try:
		# 事件引擎详细检查
		if event_engine:
			event_stats = {
				"total_events_processed": getattr(event_engine, "total_events_processed", 0),
				"active_handlers": len(getattr(event_engine, "_handlers", {})),
				"queue_size": getattr(event_engine, "queue_size", 0)
			}
			components["event_engine"] = {
				"status": "healthy",
				"details": event_stats
			}
		else:
			components["event_engine"] = {
				"status": "unhealthy",
				"error": "事件引擎未初始化"
			}
	except Exception as e:
		components["event_engine"] = {
			"status": "unhealthy",
			"error": str(e)
		}

	# 计算总体状态
	status_counts = {"healthy": 0, "degraded": 0, "unhealthy": 0}
	for component in components.values():
		status = component.get("status", "unknown")
		if status in status_counts:
			status_counts[status] += 1

	overall_status = "healthy"
	if status_counts["unhealthy"] > 0:
		overall_status = "unhealthy"
	elif status_counts["degraded"] > 0:
		overall_status = "degraded"

	return success_response(
		message="详细健康检查完成",
		data={
			"overall_status": overall_status,
			"components": components,
			"summary": {
				"total_components": len(components),
				"healthy": status_counts["healthy"],
				"degraded": status_counts["degraded"],
				"unhealthy": status_counts["unhealthy"]
			},
			"timestamp": datetime.now().isoformat()
		}
	)


@router.get("/version")
async def version_info () -> JSONResponse:
	"""
	获取版本信息

	Returns:
		Dict: 版本信息
	"""
	try:
		import importlib.metadata

		# 尝试获取包版本
		try:
			version = importlib.metadata.version("quant_server")
		except:
			version = "1.0.0"

		return success_response(
			message="版本信息获取成功",
			data={
				"name": "quant_server",
				"version": version,
				"api_version": "v1",
				"architecture": "hybrid",
				"python_version": "3.8+",
				"timestamp": datetime.now().isoformat()
			}
		)
	except Exception as e:
		logger.error(f"获取版本信息失败: {str(e)}")
		return error_response(
			message="获取版本信息失败",
			data={"error": str(e)},
			status_code=500
		)