# -*- coding: utf-8 -*-
"""
策略运行记录Repository
提供策略运行历史的数据访问接口
"""

from typing import List, Optional, Dict, Any
from datetime import datetime
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, and_, desc

from quant_server.shared.database.repositories.base import BaseRepository
from quant_server.shared.database.models.business_models import StrategyRun


class StrategyRunRepository(BaseRepository[StrategyRun]):
    """策略运行记录Repository"""

    def __init__(self, session: AsyncSession):
        super().__init__(session, StrategyRun)

    async def create(self, data: Dict[str, Any]) -> StrategyRun:
        """创建运行记录"""
        return await self.base_repo.create(data)

    async def get(self, id: int) -> Optional[StrategyRun]:
        """根据ID获取运行记录"""
        return await self.base_repo.get(id)

    async def update(self, id: int, data: Dict[str, Any]) -> Optional[StrategyRun]:
        """更新运行记录"""
        return await self.base_repo.update(id, data)

    async def delete(self, id: int, soft: bool = True) -> bool:
        """删除运行记录"""
        return await self.base_repo.delete(id, soft)

    async def get_by_strategy_id(self, strategy_id: str) -> List[StrategyRun]:
        """根据策略ID获取运行记录"""
        query = select(StrategyRun).where(
            StrategyRun.strategy_id == strategy_id
        ).order_by(desc(StrategyRun.started_at))

        result = await self.session.execute(query)
        return result.scalars().all()

    async def get_by_status(self, status: str) -> List[StrategyRun]:
        """根据状态获取运行记录"""
        query = select(StrategyRun).where(
            StrategyRun.status == status
        ).order_by(desc(StrategyRun.started_at))

        result = await self.session.execute(query)
        return result.scalars().all()

    async def get_active_runs(self) -> List[StrategyRun]:
        """获取正在运行的记录"""
        return await self.get_by_status("running")

    async def get_by_strategy_status(self, strategy_id: str, status: str) -> Optional[StrategyRun]:
        """根据策略ID和状态获取运行记录"""
        query = select(StrategyRun).where(
            and_(
                StrategyRun.strategy_id == strategy_id,
                StrategyRun.status == status
            )
        ).order_by(desc(StrategyRun.started_at)).limit(1)

        result = await self.session.execute(query)
        return result.scalar_one_or_none()

    async def update_status(self, run_id: int, status: str) -> bool:
        """更新运行状态"""
        data = {"status": status}
        if status == "stopped":
            data["stopped_at"] = datetime.now()

        result = await self.update(run_id, data)
        return result is not None

    async def stop_run(self, run_id: int) -> bool:
        """停止运行记录"""
        return await self.update_status(run_id, "stopped")

    async def get_recent_runs(self, strategy_id: str, limit: int = 10) -> List[StrategyRun]:
        """获取最近的运行记录"""
        query = select(StrategyRun).where(
            StrategyRun.strategy_id == strategy_id
        ).order_by(desc(StrategyRun.started_at)).limit(limit)

        result = await self.session.execute(query)
        return result.scalars().all()
