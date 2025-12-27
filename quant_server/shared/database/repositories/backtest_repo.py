# -*- coding: utf-8 -*-
"""
# 回测数据仓库
# 位置：quant_server/shared/database/repositories/backtest_repo.py
# 职责：管理回测任务、结果、曲线等数据访问
"""

from typing import List, Optional, Dict, Any, Tuple
from datetime import datetime, date
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, and_, or_, desc, func, text
from sqlalchemy.orm import selectinload, joinedload

from quant_server.shared.database.repositories.base import BaseRepository
from quant_server.shared.database.models.business_models import (
	BacktestTask,
	BacktestEquityCurve,
	BacktestTrade,
	BacktestPosition
)


class BacktestRepository:
	"""回测数据仓库 - 负责回测相关数据访问"""

	def __init__ (self, session: AsyncSession):
		self.session = session
		self.task_repo = BaseRepository[BacktestTask](session, BacktestTask)
		self.equity_repo = BaseRepository[BacktestEquityCurve](session, BacktestEquityCurve)
		self.trade_repo = BaseRepository[BacktestTrade](session, BacktestTrade)
		self.position_repo = BaseRepository[BacktestPosition](session, BacktestPosition)

	# ==================== 回测任务操作 ====================

	async def get_task_by_id (self, task_id: str) -> Optional[BacktestTask]:
		"""
		根据任务ID获取回测任务

		Args:
			task_id: 任务ID

		Returns:
			回测任务或None
		"""
		return await self.task_repo.get_by(id=task_id)

	async def get_tasks_by_user (
			self,
			user_id: int,
			limit: int = 100,
			skip: int = 0
	) -> List[BacktestTask]:
		"""
		获取用户的所有回测任务

		Args:
			user_id: 用户ID
			limit: 返回数量限制
			skip: 跳过数量

		Returns:
			回测任务列表
		"""
		return await self.task_repo.get_many(
			user_id=user_id,
			skip=skip,
			limit=limit
		)

	async def get_tasks_by_strategy (
			self,
			strategy_id: str,
			limit: int = 100,
			skip: int = 0
	) -> List[BacktestTask]:
		"""
		获取策略的所有回测任务

		Args:
			strategy_id: 策略ID
			limit: 返回数量限制
			skip: 跳过数量

		Returns:
			回测任务列表
		"""
		return await self.task_repo.get_many(
			strategy_id=strategy_id,
			skip=skip,
			limit=limit
		)

	async def create_task (self, task_data: Dict[str, Any]) -> BacktestTask:
		"""
		创建回测任务

		Args:
			task_data: 任务数据

		Returns:
			创建的回测任务
		"""
		return await self.task_repo.create(task_data)

	async def update_task_status (
			self,
			task_id: str,
			status: str,
			progress: float = None,
			error_message: str = None,
			result: Dict[str, Any] = None
	) -> Optional[BacktestTask]:
		"""
		更新回测任务状态

		Args:
			task_id: 任务ID
			status: 新状态
			progress: 进度（可选）
			error_message: 错误信息（可选）
			result: 结果数据（可选）

		Returns:
			更新后的回测任务
		"""
		update_data = {"status": status}

		if progress is not None:
			update_data["progress"] = progress

		if error_message is not None:
			update_data["error_message"] = error_message

		if result is not None:
			update_data["result"] = result

		if status == "running" and "started_at" not in update_data:
			update_data["started_at"] = datetime.utcnow()
		elif status in ["completed", "failed"]:
			update_data["completed_at"] = datetime.utcnow()

		return await self.task_repo.update(task_id, update_data)

	async def delete_task (self, task_id: str) -> bool:
		"""
		删除回测任务

		Args:
			task_id: 任务ID

		Returns:
			是否成功
		"""
		return await self.task_repo.delete(task_id)

	# ==================== 净值曲线操作 ====================

	async def get_equity_curve (self, task_id: str) -> List[BacktestEquityCurve]:
		"""
		获取回测净值曲线

		Args:
			task_id: 任务ID

		Returns:
			净值曲线数据列表
		"""
		query = select(BacktestEquityCurve).where(
			BacktestEquityCurve.task_id == task_id
		).order_by(BacktestEquityCurve.trade_date)

		result = await self.session.execute(query)
		return result.scalars().all()

	async def get_equity_by_date (
			self,
			task_id: str,
			trade_date: date
	) -> Optional[BacktestEquityCurve]:
		"""
		获取指定日期的净值数据

		Args:
			task_id: 任务ID
			trade_date: 交易日期

		Returns:
			净值数据或None
		"""
		return await self.equity_repo.get_by(
			task_id=task_id,
			trade_date=trade_date
		)

	async def create_equity_point (self, equity_data: Dict[str, Any]) -> BacktestEquityCurve:
		"""
		创建净值曲线点

		Args:
			equity_data: 净值数据

		Returns:
			创建的净值记录
		"""
		return await self.equity_repo.create(equity_data)

	async def batch_create_equity_curve (self, curve_data: List[Dict[str, Any]]) -> List[BacktestEquityCurve]:
		"""
		批量创建净值曲线

		Args:
			curve_data: 净值数据列表

		Returns:
			创建的净值记录列表
		"""
		return await self.equity_repo.batch_create(curve_data)

	# ==================== 回测交易操作 ====================

	async def get_backtest_trades (self, task_id: str) -> List[BacktestTrade]:
		"""
		获取回测交易记录

		Args:
			task_id: 任务ID

		Returns:
			回测交易记录列表
		"""
		query = select(BacktestTrade).where(
			BacktestTrade.task_id == task_id
		).order_by(BacktestTrade.trade_time)

		result = await self.session.execute(query)
		return result.scalars().all()

	async def get_backtest_trades_by_stock (
			self,
			task_id: str,
			ts_code: str
	) -> List[BacktestTrade]:
		"""
		获取回测中某只股票的交易记录

		Args:
			task_id: 任务ID
			ts_code: 股票代码

		Returns:
			交易记录列表
		"""
		query = select(BacktestTrade).where(
			and_(
				BacktestTrade.task_id == task_id,
				BacktestTrade.ts_code == ts_code
			)
		).order_by(BacktestTrade.trade_time)

		result = await self.session.execute(query)
		return result.scalars().all()

	async def create_backtest_trade (self, trade_data: Dict[str, Any]) -> BacktestTrade:
		"""
		创建回测交易记录

		Args:
			trade_data: 交易数据

		Returns:
			创建的交易记录
		"""
		return await self.trade_repo.create(trade_data)

	async def batch_create_backtest_trades (self, trades_data: List[Dict[str, Any]]) -> List[BacktestTrade]:
		"""
		批量创建回测交易记录

		Args:
			trades_data: 交易数据列表

		Returns:
			创建的交易记录列表
		"""
		return await self.trade_repo.batch_create(trades_data)

	# ==================== 回测持仓操作 ====================

	async def get_backtest_positions (self, task_id: str, trade_date: date = None) -> List[BacktestPosition]:
		"""
		获取回测持仓数据

		Args:
			task_id: 任务ID
			trade_date: 交易日期（可选，不指定则返回所有）

		Returns:
			持仓数据列表
		"""
		query = select(BacktestPosition).where(
			BacktestPosition.task_id == task_id
		)

		if trade_date:
			query = query.where(BacktestPosition.trade_date == trade_date)

		query = query.order_by(BacktestPosition.trade_date, BacktestPosition.ts_code)

		result = await self.session.execute(query)
		return result.scalars().all()

	async def get_backtest_position_by_stock (
			self,
			task_id: str,
			ts_code: str,
			trade_date: date = None
	) -> Optional[BacktestPosition]:
		"""
		获取回测中某只股票的持仓

		Args:
			task_id: 任务ID
			ts_code: 股票代码
			trade_date: 交易日期（可选）

		Returns:
			持仓数据或None
		"""
		filters = {
			"task_id": task_id,
			"ts_code": ts_code
		}

		if trade_date:
			filters["trade_date"] = trade_date

		query = select(BacktestPosition).where(
			and_(*[getattr(BacktestPosition, k) == v for k, v in filters.items()])
		).order_by(desc(BacktestPosition.trade_date)).limit(1)

		result = await self.session.execute(query)
		return result.scalar_one_or_none()

	async def create_backtest_position (self, position_data: Dict[str, Any]) -> BacktestPosition:
		"""
		创建回测持仓记录

		Args:
			position_data: 持仓数据

		Returns:
			创建的持仓记录
		"""
		return await self.position_repo.create(position_data)

	async def batch_create_backtest_positions (self, positions_data: List[Dict[str, Any]]) -> List[BacktestPosition]:
		"""
		批量创建回测持仓记录

		Args:
			positions_data: 持仓数据列表

		Returns:
			创建的持仓记录列表
		"""
		return await self.position_repo.batch_create(positions_data)

	# ==================== 批量操作 ====================

	async def batch_upsert_equity_curve (self, curve_data: List[Dict[str, Any]]) -> List[BacktestEquityCurve]:
		"""
		批量插入或更新净值曲线

		Args:
			curve_data: 净值数据列表

		Returns:
			更新后的净值记录列表
		"""
		return await self.equity_repo.batch_upsert(
			match_fields=["task_id", "trade_date"],
			data_list=curve_data
		)

	async def batch_upsert_backtest_positions (self, positions_data: List[Dict[str, Any]]) -> List[BacktestPosition]:
		"""
		批量插入或更新回测持仓

		Args:
			positions_data: 持仓数据列表

		Returns:
			更新后的持仓记录列表
		"""
		return await self.position_repo.batch_upsert(
			match_fields=["task_id", "trade_date", "ts_code"],
			data_list=positions_data
		)