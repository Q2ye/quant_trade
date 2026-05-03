# shared/database/repositories/account/transaction_repo.py
from datetime import date, datetime, timedelta
from decimal import Decimal
from typing import List, Dict, Any, Optional

from sqlalchemy import select, func, and_, or_, desc
from sqlalchemy.ext.asyncio import AsyncSession

from shared.database.models.business_models import AccountTransaction
from shared.database.repositories.base import BaseRepository


class AccountTransactionRepository(BaseRepository[AccountTransaction]):
	"""账户流水数据仓库"""

	def __init__ (self, session: AsyncSession):
		super().__init__(session, AccountTransaction)

	async def get_account_transactions (self, account_id: str, skip: int = 0,
	                                    limit: int = 100) -> List[AccountTransaction]:
		"""获取账户的交易流水"""
		query = (
			select(self.model)
			.where(self.model.account_id == account_id)
			.order_by(desc(self.model.transaction_date))
			.offset(skip)
			.limit(limit)
		)

		result = await self.session.execute(query)
		return result.scalars().all()

	async def get_transactions_by_date_range (self, account_id: str, start_date: date,
	                                          end_date: date) -> List[AccountTransaction]:
		"""获取指定日期范围内的交易流水"""
		query = (
			select(self.model)
			.where(
				and_(
					self.model.account_id == account_id,
					self.model.transaction_date >= start_date,
					self.model.transaction_date <= end_date
				)
			)
			.order_by(self.model.transaction_date)
		)

		result = await self.session.execute(query)
		return result.scalars().all()

	async def get_transactions_by_type (self, account_id: str, transaction_type: str,
	                                    skip: int = 0, limit: int = 100) -> List[AccountTransaction]:
		"""按交易类型获取流水"""
		query = (
			select(self.model)
			.where(
				and_(
					self.model.account_id == account_id,
					self.model.transaction_type == transaction_type
				)
			)
			.order_by(desc(self.model.transaction_date))
			.offset(skip)
			.limit(limit)
		)

		result = await self.session.execute(query)
		return result.scalars().all()

	async def get_transaction_summary (self, account_id: str, start_date: Optional[date] = None,
	                                   end_date: Optional[date] = None) -> Dict[str, Any]:
		"""获取交易流水汇总统计"""
		query = select(self.model).where(self.model.account_id == account_id)

		if start_date:
			query = query.where(self.model.transaction_date >= start_date)
		if end_date:
			query = query.where(self.model.transaction_date <= end_date)

		result = await self.session.execute(query)
		transactions = result.scalars().all()

		if not transactions:
			return {
				"total_transactions": 0,
				"total_amount": 0,
				"transaction_counts": {},
				"amount_by_type": {},
				"daily_summary": []
			}

		# 按类型统计
		type_stats = {}
		amount_by_type = {}

		for txn in transactions:
			txn_type = txn.transaction_type
			amount = float(txn.amount)

			if txn_type not in type_stats:
				type_stats[txn_type] = 0
				amount_by_type[txn_type] = 0

			type_stats[txn_type] += 1
			amount_by_type[txn_type] += amount

		# 按日汇总
		daily_query = (
			select(
				func.date(self.model.transaction_date).label('date'),
				func.count().label('count'),
				func.sum(self.model.amount).label('total_amount')
			)
			.where(self.model.account_id == account_id)
		)

		if start_date:
			daily_query = daily_query.where(self.model.transaction_date >= start_date)
		if end_date:
			daily_query = daily_query.where(self.model.transaction_date <= end_date)

		daily_query = daily_query.group_by(func.date(self.model.transaction_date)).order_by(desc('date'))
		daily_result = await self.session.execute(daily_query)

		daily_summary = []
		for row in daily_result.all():
			daily_summary.append({
				"date": row.date,
				"count": row.count,
				"total_amount": float(row.total_amount or 0)
			})

		# 总额计算
		total_amount = sum(amount_by_type.values())

		return {
			"total_transactions": len(transactions),
			"total_amount": total_amount,
			"transaction_counts": type_stats,
			"amount_by_type": amount_by_type,
			"daily_summary": daily_summary[:30]  # 最近30天
		}

	async def create_transaction (self, account_id: str, transaction_type: str, amount: Decimal,
	                              description: str = "", reference_id: Optional[str] = None,
	                              reference_type: Optional[str] = None) -> AccountTransaction:
		"""创建账户流水记录"""
		# 获取账户当前余额（需要从账户表中查询）
		from shared.database.models.business_models import Account

		account_query = select(Account).where(Account.id == account_id)
		account_result = await self.session.execute(account_query)
		account = account_result.scalar_one_or_none()

		if not account:
			raise ValueError(f"Account {account_id} not found")

		# 计算交易前余额和交易后余额
		balance_before = account.available_balance
		balance_after = balance_before + amount  # 注意：amount可能为负

		transaction_data = {
			"account_id": account_id,
			"transaction_type": transaction_type,
			"transaction_date": datetime.now(),
			"amount": amount,
			"balance_before": balance_before,
			"balance_after": balance_after,
			"description": description,
			"reference_id": reference_id,
			"reference_type": reference_type,
			"created_at": datetime.now()
		}

		instance = self.model(**transaction_data)
		self.session.add(instance)

		# 更新账户余额
		from sqlalchemy import update as sql_update
		update_stmt = (
			sql_update(Account)
			.where(Account.id == account_id)
			.values(
				available_balance=balance_after,
				updated_at=datetime.now()
			)
		)
		await self.session.execute(update_stmt)

		await self.session.flush()
		return instance

	async def search_transactions (self, account_id: str, keyword: Optional[str] = None,
	                               min_amount: Optional[Decimal] = None,
	                               max_amount: Optional[Decimal] = None,
	                               skip: int = 0, limit: int = 50) -> List[AccountTransaction]:
		"""搜索交易流水"""
		query = select(self.model).where(self.model.account_id == account_id)

		if keyword:
			keyword_pattern = f"%{keyword}%"
			query = query.where(
				or_(
					self.model.description.ilike(keyword_pattern),
					self.model.reference_id.ilike(keyword_pattern)
				)
			)

		if min_amount is not None:
			query = query.where(self.model.amount >= min_amount)

		if max_amount is not None:
			query = query.where(self.model.amount <= max_amount)

		query = query.order_by(desc(self.model.transaction_date)).offset(skip).limit(limit)
		result = await self.session.execute(query)
		return result.scalars().all()

	async def get_recent_transactions (self, account_id: str, days: int = 7) -> List[Dict[str, Any]]:
		"""获取最近交易记录"""
		cutoff_date = datetime.now() - timedelta(days=days)

		query = (
			select(self.model)
			.where(
				and_(
					self.model.account_id == account_id,
					self.model.transaction_date >= cutoff_date
				)
			)
			.order_by(desc(self.model.transaction_date))
			.limit(50)
		)

		result = await self.session.execute(query)
		transactions = result.scalars().all()

		return [
			{
				"id": txn.id,
				"transaction_type": txn.transaction_type,
				"transaction_date": txn.transaction_date,
				"amount": float(txn.amount),
				"balance_before": float(txn.balance_before),
				"balance_after": float(txn.balance_after),
				"description": txn.description,
				"reference": f"{txn.reference_type}: {txn.reference_id}" if txn.reference_type else None
			}
			for txn in transactions
		]
