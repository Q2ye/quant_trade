# -*- coding: utf-8 -*-
"""
模型训练任务Repository
提供模型训练任务（model_trainings 表）的数据访问接口。
"""

from datetime import datetime
from typing import Optional, Any

from sqlalchemy import select, desc
from sqlalchemy.ext.asyncio import AsyncSession

from shared.database.models.business_models import ModelTraining
from shared.database.repositories.base import BaseRepository


class ModelTrainingRepository(BaseRepository[ModelTraining]):
	"""模型训练任务Repository"""

	def __init__ (self, session: AsyncSession):
		super().__init__(session, ModelTraining)

	async def get_by_task_id (self, task_id: str) -> Optional[ModelTraining]:
		"""根据任务ID获取训练记录"""
		query = select(ModelTraining).where(ModelTraining.task_id == task_id)
		result = await self.session.execute(query)
		return result.scalars().first()

	async def list_recent (self, limit: int = 20) -> list:
		"""获取最近的训练记录（按创建时间倒序）"""
		query = select(ModelTraining).order_by(desc(ModelTraining.created_at)).limit(limit)
		result = await self.session.execute(query)
		return list(result.scalars().all())
