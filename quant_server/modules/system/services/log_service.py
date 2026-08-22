# -*- coding: utf-8 -*-
"""
审计日志服务（原系统日志服务）

提供操作/安全审计日志（audit_logs 表）的查询、过滤、分页等纯业务逻辑。
2026-08：从读取无人写入的 system_logs 空表改为读取 audit_logs（由 AuditLogger 写入）。
"""

from datetime import datetime
from typing import Dict, Any, Optional

from sqlalchemy.ext.asyncio import AsyncSession

from shared.database.repositories.system.config.audit_repo import AuditRepository


class LogService:
	"""审计日志服务 — 无状态纯计算"""

	def __init__ (self, session: AsyncSession):
		self._repo = AuditRepository(session)

	async def query_logs (
			self,
			action_type: Optional[str] = None,
			status: Optional[str] = None,
			username: Optional[str] = None,
			start_date: Optional[str] = None,
			end_date: Optional[str] = None,
			page: int = 1,
			page_size: int = 20,
	) -> Dict[str, Any]:
		start_time = datetime.fromisoformat(start_date) if start_date else None
		end_time = datetime.fromisoformat(end_date) if end_date else None

		result = await self._repo.search_audit_logs(
			start_time=start_time,
			end_time=end_time,
			action_type=action_type,
			status=status,
			username=username,
			page=page,
			page_size=page_size,
		)

		return {
			"data": [self._orm_to_dict(log) for log in result["logs"]],
			"pagination": {
				"page": page,
				"page_size": page_size,
				"total": result["total"],
			},
		}

	@staticmethod
	def _orm_to_dict (log) -> Dict[str, Any]:
		return {
			"id": log.id,
			"action_type": log.action_type,
			"username": log.username,
			"user_id": log.user_id,
			"resource_type": log.resource_type,
			"resource_id": log.resource_id,
			"resource_name": log.resource_name,
			"old_values": log.old_values,
			"new_values": log.new_values,
			"changed_fields": log.changed_fields,
			"ip_address": log.ip_address,
			"user_agent": log.user_agent,
			"status": log.status,
			"error_message": log.error_message,
			"created_at": log.created_at.isoformat() if log.created_at else None,
		}
