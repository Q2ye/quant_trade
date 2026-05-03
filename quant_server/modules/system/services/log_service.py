# -*- coding: utf-8 -*-
"""
系统日志服务

提供日志查询、过滤、分页等纯业务逻辑。
"""

from datetime import datetime
from typing import Dict, Any, Optional

from sqlalchemy.ext.asyncio import AsyncSession

from shared.database.repositories.system.config.operation_log_repo import OperationLogRepository


class LogService:
	"""系统日志服务 — 无状态纯计算"""

	def __init__ (self, session: AsyncSession):
		self._repo = OperationLogRepository(session)

	async def query_logs (
			self,
			log_level: Optional[str] = None,
			module: Optional[str] = None,
			user_id: Optional[str] = None,
			start_date: Optional[str] = None,
			end_date: Optional[str] = None,
			page: int = 1,
			page_size: int = 20,
	) -> Dict[str, Any]:
		start_time = datetime.fromisoformat(start_date) if start_date else None
		end_time = datetime.fromisoformat(end_date) if end_date else None

		offset = (page - 1) * page_size
		logs = await self._repo.get_logs(
			start_time=start_time,
			end_time=end_time,
			log_level=log_level,
			module=module,
			user_id=user_id,
			limit=page_size,
			offset=offset,
		)

		return {
			"data": [self._orm_to_dict(log) for log in logs],
			"pagination": {
				"page": page,
				"page_size": page_size,
				"total": len(logs),
			},
		}

	async def get_statistics (self, start_date: str, end_date: str) -> Dict[str, Any]:
		start_time = datetime.fromisoformat(start_date) if start_date else datetime.now().replace(day=1)
		end_time = datetime.fromisoformat(end_date) if end_date else datetime.now()
		return await self._repo.get_log_statistics(start_time, end_time)

	@staticmethod
	def _orm_to_dict (log) -> Dict[str, Any]:
		return {
			"id": log.id,
			"log_level": log.log_level,
			"module": log.module,
			"user_id": log.user_id,
			"action": log.action,
			"details": log.details,
			"ip_address": log.ip_address,
			"user_agent": log.user_agent,
			"execution_time": log.execution_time,
			"created_at": log.created_at.isoformat() if log.created_at else None,
		}
