# shared/database/repositories/account/cash_flow_repo.py
from datetime import date, datetime, timedelta
from decimal import Decimal
from typing import List, Dict, Any, Optional

from sqlalchemy import select, func, and_, desc, case
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.sql import literal

from shared.database.models.business_models import CashFlow
from shared.database.repositories.base import BaseRepository


class CashFlowRepository(BaseRepository[CashFlow]):
	"""资金流水数据仓库"""

	def __init__ (self, session: AsyncSession):
		super().__init__(session, CashFlow)

	async def get_user_cash_flows (self, user_id: str, skip: int = 0,
	                               limit: int = 100) -> List[CashFlow]:
		"""获取用户的资金流水"""
		query = (
			select(self.model)
			.where(self.model.user_id == user_id)
			.order_by(desc(self.model.flow_date))
			.offset(skip)
			.limit(limit)
		)

		result = await self.session.execute(query)
		return result.scalars().all()

	async def get_cash_flows_by_type (self, user_id: str, flow_type: str,
	                                  start_date: Optional[date] = None,
	                                  end_date: Optional[date] = None) -> List[CashFlow]:
		"""按类型获取资金流水"""
		query = select(self.model).where(
			and_(
				self.model.user_id == user_id,
				self.model.flow_type == flow_type
			)
		)

		if start_date:
			query = query.where(self.model.flow_date >= start_date)
		if end_date:
			query = query.where(self.model.flow_date <= end_date)

		query = query.order_by(desc(self.model.flow_date))
		result = await self.session.execute(query)
		return result.scalars().all()

	async def get_cash_flow_summary (self, user_id: str, start_date: Optional[date] = None,
	                                 end_date: Optional[date] = None) -> Dict[str, Any]:
		"""获取资金流水汇总统计"""
		query = select(self.model).where(self.model.user_id == user_id)

		if start_date:
			query = query.where(self.model.flow_date >= start_date)
		if end_date:
			query = query.where(self.model.flow_date <= end_date)

		result = await self.session.execute(query)
		cash_flows = result.scalars().all()

		if not cash_flows:
			return {
				"total_flows": 0,
				"total_inflows": 0,
				"total_outflows": 0,
				"net_flow": 0,
				"by_type": {},
				"by_status": {},
				"recent_flows": []
			}

		# 计算流入流出
		total_inflows = Decimal('0')
		total_outflows = Decimal('0')
		by_type = {}
		by_status = {}

		for flow in cash_flows:
			amount = flow.amount
			flow_type = flow.flow_type
			status = flow.status

			# 流入流出判断
			if flow_type in ['deposit', 'dividend']:
				total_inflows += amount
			elif flow_type in ['withdrawal', 'fee']:
				total_outflows += amount
			elif flow_type == 'transfer':
				# 转账需要根据金额正负判断
				if amount > 0:
					total_inflows += amount
				else:
					total_outflows += abs(amount)

			# 按类型统计
			if flow_type not in by_type:
				by_type[flow_type] = {"count": 0, "amount": Decimal('0')}
			by_type[flow_type]["count"] += 1
			by_type[flow_type]["amount"] += amount

			# 按状态统计
			if status not in by_status:
				by_status[status] = 0
			by_status[status] += 1

		net_flow = total_inflows - total_outflows

		# 获取最近流水
		recent_query = (
			select(self.model)
			.where(self.model.user_id == user_id)
			.order_by(desc(self.model.flow_date))
			.limit(10)
		)

		recent_result = await self.session.execute(recent_query)
		recent_flows = [
			{
				"id": flow.id,
				"flow_type": flow.flow_type,
				"flow_date": flow.flow_date,
				"amount": float(flow.amount),
				"currency": flow.currency,
				"status": flow.status,
				"description": flow.description
			}
			for flow in recent_result.scalars().all()
		]

		return {
			"total_flows": len(cash_flows),
			"total_inflows": float(total_inflows),
			"total_outflows": float(total_outflows),
			"net_flow": float(net_flow),
			"by_type": {
				flow_type: {
					"count": stats["count"],
					"amount": float(stats["amount"])
				}
				for flow_type, stats in by_type.items()
			},
			"by_status": by_status,
			"recent_flows": recent_flows
		}

	async def create_cash_flow (self, user_id: str, flow_type: str, amount: Decimal,
	                            currency: str = "CNY", description: str = "",
	                            reference_id: Optional[str] = None,
	                            reference_type: Optional[str] = None) -> CashFlow:
		"""创建资金流水记录"""
		cash_flow_data = {
			"user_id": user_id,
			"flow_type": flow_type,
			"flow_date": datetime.now(),
			"amount": amount,
			"currency": currency,
			"status": "pending",  # 默认为待处理
			"description": description,
			"reference_id": reference_id,
			"reference_type": reference_type,
			"created_at": datetime.now()
		}

		instance = self.model(**cash_flow_data)
		self.session.add(instance)
		await self.session.flush()

		return instance

	async def update_cash_flow_status (self, cash_flow_id: str, status: str,
	                                   notes: Optional[str] = None) -> bool:
		"""更新资金流水状态"""
		from sqlalchemy import update as sql_update

		update_data = {
			"status": status,
			"updated_at": datetime.now()
		}

		if notes:
			update_data["status_notes"] = notes

		stmt = (
			sql_update(self.model)
			.where(self.model.id == cash_flow_id)
			.values(**update_data)
		)

		result = await self.session.execute(stmt)
		return result.rowcount > 0

	async def get_monthly_cash_flow (self, user_id: str, months: int = 12) -> List[Dict[str, Any]]:
		"""获取月度现金流分析"""
		cutoff_date = datetime.now() - timedelta(days=months * 30)

		monthly_query = (
			select(
				func.date_trunc('month', self.model.flow_date).label('month'),
				func.count().label('total_flows'),
				func.sum(
					case(
					(self.model.flow_type.in_(['deposit', 'dividend']), self.model.amount),
					(self.model.flow_type == 'transfer',
						case((self.model.amount > 0, self.model.amount), else_=literal(0))),
					else_=literal(0)
				)
				).label('total_inflows'),
				func.sum(
					case(
					(self.model.flow_type.in_(['withdrawal', 'fee']), self.model.amount),
					(self.model.flow_type == 'transfer',
						case((self.model.amount < 0, -self.model.amount), else_=literal(0))),
					else_=literal(0)
				)
				).label('total_outflows')
			)
			.where(
				and_(
					self.model.user_id == user_id,
					self.model.flow_date >= cutoff_date,
					self.model.status == 'completed'
				)
			)
			.group_by(func.date_trunc('month', self.model.flow_date))
			.order_by(desc('month'))
		)

		result = await self.session.execute(monthly_query)

		monthly_analysis = []
		for row in result.all():
			monthly_analysis.append({
				"month": row.month.strftime('%Y-%m'),
				"total_flows": row.total_flows,
				"total_inflows": float(row.total_inflows or 0),
				"total_outflows": float(row.total_outflows or 0),
				"net_flow": float((row.total_inflows or 0) - (row.total_outflows or 0))
			})

		return monthly_analysis

	async def get_pending_cash_flows (self, user_id: Optional[str] = None,
	                                  flow_type: Optional[str] = None) -> List[CashFlow]:
		"""获取待处理的资金流水"""
		query = select(self.model).where(self.model.status == 'pending')

		if user_id:
			query = query.where(self.model.user_id == user_id)

		if flow_type:
			query = query.where(self.model.flow_type == flow_type)

		query = query.order_by(self.model.flow_date)
		result = await self.session.execute(query)
		return result.scalars().all()