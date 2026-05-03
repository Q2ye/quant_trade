# shared/database/repositories/account/statement_repo.py
from datetime import date, datetime
from decimal import Decimal
from typing import List, Dict, Any, Optional

from sqlalchemy import select, func, and_, desc
from sqlalchemy.ext.asyncio import AsyncSession

from shared.database.models.business_models import AccountStatement
from shared.database.repositories.base import BaseRepository


class AccountStatementRepository(BaseRepository[AccountStatement]):
	"""账户对账单数据仓库"""

	def __init__ (self, session: AsyncSession):
		super().__init__(session, AccountStatement)

	async def get_account_statements (self, account_id: str, skip: int = 0,
	                                  limit: int = 50) -> List[AccountStatement]:
		"""获取账户的对账单列表"""
		query = (
			select(self.model)
			.where(self.model.account_id == account_id)
			.order_by(desc(self.model.statement_date))
			.offset(skip)
			.limit(limit)
		)

		result = await self.session.execute(query)
		return result.scalars().all()

	async def get_statement_by_date (self, account_id: str, statement_date: date,
	                                 statement_period: str = 'daily') -> Optional[AccountStatement]:
		"""获取指定日期的对账单"""
		query = (
			select(self.model)
			.where(
				and_(
					self.model.account_id == account_id,
					self.model.statement_date == statement_date,
					self.model.statement_period == statement_period
				)
			)
		)

		result = await self.session.execute(query)
		return result.scalar_one_or_none()

	async def get_statements_by_period (self, account_id: str, statement_period: str,
	                                    start_date: Optional[date] = None,
	                                    end_date: Optional[date] = None) -> List[AccountStatement]:
		"""按对账周期获取对账单"""
		query = select(self.model).where(
			and_(
				self.model.account_id == account_id,
				self.model.statement_period == statement_period
			)
		)

		if start_date:
			query = query.where(self.model.statement_date >= start_date)
		if end_date:
			query = query.where(self.model.statement_date <= end_date)

		query = query.order_by(self.model.statement_date)
		result = await self.session.execute(query)
		return result.scalars().all()

	async def generate_daily_statement (self, account_id: str, statement_date: date) -> AccountStatement:
		"""生成日度对账单"""
		# 获取账户信息
		from shared.database.models.business_models import Account

		account_query = select(Account).where(Account.id == account_id)
		account_result = await self.session.execute(account_query)
		account = account_result.scalar_one_or_none()

		if not account:
			raise ValueError(f"Account {account_id} not found")

		# 获取当天的交易流水
		from shared.database.repositories.account.settlement.transaction_repo import \
			AccountTransactionRepository
		transaction_repo = AccountTransactionRepository(self.session)

		start_datetime = datetime.combine(statement_date, datetime.min.time())
		end_datetime = datetime.combine(statement_date, datetime.max.time())

		transactions = await transaction_repo.get_transactions_by_date_range(
			account_id, start_datetime, end_datetime
		)

		# 计算统计信息
		statement_data = []
		total_deposits = Decimal('0')
		total_withdrawals = Decimal('0')
		total_trades = Decimal('0')
		total_fees = Decimal('0')

		for txn in transactions:
			txn_dict = {
				"transaction_id": txn.id,
				"transaction_type": txn.transaction_type,
				"transaction_date": txn.transaction_date,
				"amount": float(txn.amount),
				"balance_before": float(txn.balance_before),
				"balance_after": float(txn.balance_after),
				"description": txn.description
			}
			statement_data.append(txn_dict)

			# 分类统计
			amount = txn.amount
			if txn.transaction_type == 'deposit':
				total_deposits += amount
			elif txn.transaction_type == 'withdrawal':
				total_withdrawals += amount
			elif txn.transaction_type in ['trade', 'buy', 'sell']:
				total_trades += amount
			elif txn.transaction_type == 'fee':
				total_fees += amount

		# 创建对账单
		statement = self.model(
			account_id=account_id,
			statement_date=statement_date,
			statement_period='daily',
			opening_balance=account.available_balance - sum(txn.amount for txn in transactions),
			closing_balance=account.available_balance,
			total_deposits=total_deposits,
			total_withdrawals=total_withdrawals,
			total_trades=total_trades,
			total_fees=total_fees,
			statement_data=statement_data,
			generated_at=datetime.now(),
			created_at=datetime.now()
		)

		self.session.add(statement)
		await self.session.flush()
		return statement

	async def get_statement_summary (self, account_id: str) -> Dict[str, Any]:
		"""获取对账单汇总信息"""
		# 获取最新的对账单
		latest_query = (
			select(self.model)
			.where(self.model.account_id == account_id)
			.order_by(desc(self.model.statement_date))
			.limit(1)
		)

		latest_result = await self.session.execute(latest_query)
		latest_statement = latest_result.scalar_one_or_none()

		# 统计各类对账单数量
		count_query = (
			select(
				self.model.statement_period,
				func.count().label('count')
			)
			.where(self.model.account_id == account_id)
			.group_by(self.model.statement_period)
		)

		count_result = await self.session.execute(count_query)
		period_counts = {row.statement_period: row.count for row in count_result.all()}

		# 月度统计
		monthly_query = (
			select(
				func.date_trunc('month', self.model.statement_date).label('month'),
				func.count().label('count'),
				func.sum(self.model.total_deposits).label('total_deposits'),
				func.sum(self.model.total_withdrawals).label('total_withdrawals'),
				func.sum(self.model.total_trades).label('total_trades')
			)
			.where(
				and_(
					self.model.account_id == account_id,
					self.model.statement_period == 'daily'
				)
			)
			.group_by(func.date_trunc('month', self.model.statement_date))
			.order_by(desc('month'))
			.limit(6)
		)

		monthly_result = await self.session.execute(monthly_query)
		monthly_stats = []

		for row in monthly_result.all():
			monthly_stats.append({
				"month": row.month.strftime('%Y-%m'),
				"count": row.count,
				"total_deposits": float(row.total_deposits or 0),
				"total_withdrawals": float(row.total_withdrawals or 0),
				"total_trades": float(row.total_trades or 0),
				"net_flow": float((row.total_deposits or 0) - (row.total_withdrawals or 0))
			})

		return {
			"latest_statement": {
				"date": latest_statement.statement_date if latest_statement else None,
				"period": latest_statement.statement_period if latest_statement else None,
				"closing_balance": float(latest_statement.closing_balance) if latest_statement else 0
			},
			"period_counts": period_counts,
			"monthly_stats": monthly_stats,
			"total_statements": sum(period_counts.values())
		}

	async def verify_statement (self, statement_id: str, verified_by: int,
	                            verification_notes: Optional[str] = None) -> bool:
		"""核验对账单"""
		from sqlalchemy import update as sql_update

		update_data = {
			"verification_status": "verified",
			"verified_by": verified_by,
			"verified_at": datetime.now(),
			"verification_notes": verification_notes,
			"updated_at": datetime.now()
		}

		stmt = (
			sql_update(self.model)
			.where(self.model.id == statement_id)
			.values(**update_data)
		)

		result = await self.session.execute(stmt)
		return result.rowcount > 0
