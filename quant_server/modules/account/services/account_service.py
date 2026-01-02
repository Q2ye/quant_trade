"""
账户服务
处理账户相关的核心业务逻辑
"""
import logging
from typing import Optional, List, Dict, Any
from decimal import Decimal
from datetime import datetime, date
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import and_, or_

from shared.database.repositories.account_repo import AccountRepository
from shared.database.repositories.user_repo import UserRepository
from shared.database.repositories.position_repo import PositionRepository
from shared.database.models.business_models import Account, AccountDailyPerformance
from modules.account.models import AccountDomain
from shared.cache.base import CacheBase
from shared.security.audit import AuditLogger
from shared.utils.validation import validate_account_data

logger = logging.getLogger(__name__)


class AccountService:
	"""账户服务 - 处理账户核心业务逻辑"""

	def __init__ (self, db: AsyncSession, cache: Optional[CacheBase] = None):
		self.db = db
		self.cache = cache
		self.account_repo = AccountRepository(db)
		self.user_repo = UserRepository(db)
		self.position_repo = PositionRepository(db)
		self.audit_logger = AuditLogger(db)

	async def get_account (self, account_id: int) -> Optional[AccountDomain]:
		"""
		获取账户详情

		Args:
			account_id: 账户ID

		Returns:
			账户领域对象，如果不存在则返回None
		"""
		try:
			# 检查缓存
			cache_key = f"events:{account_id}"
			if self.cache:
				cached_account = await self.cache.get(cache_key)
				if cached_account:
					return AccountDomain(**cached_account)

			# 从数据库获取
			account = await self.account_repo.get_by_id(account_id)
			if not account:
				return None

			# 转换为领域对象
			account_domain = AccountDomain(
				id=account.id,
				account_number=account.account_number,
				account_name=account.account_name,
				user_id=account.user_id,
				account_type=account.account_type,
				broker=account.broker,
				broker_account_id=account.broker_account_id,
				status=account.status,
				status_reason=account.status_reason,
				total_balance=Decimal(str(account.total_balance)),
				available_balance=Decimal(str(account.available_balance)),
				frozen_balance=Decimal(str(account.frozen_balance)),
				market_value=Decimal(str(account.market_value)),
				initial_balance=Decimal(str(account.initial_balance)),
				credit_line=Decimal(str(account.credit_line)) if account.credit_line else None,
				last_trade_date=account.last_trade_date,
				created_at=account.created_at,
				updated_at=account.updated_at
			)

			# 更新缓存
			if self.cache:
				await self.cache.set(cache_key, account_domain.dict(), expire=3600)

			return account_domain

		except Exception as e:
			logger.error(f"获取账户详情失败: {str(e)}")
			raise

	async def get_account_by_number (self, account_number: str) -> Optional[AccountDomain]:
		"""
		根据账户号获取账户

		Args:
			account_number: 账户号

		Returns:
			账户领域对象，如果不存在则返回None
		"""
		try:
			account = await self.account_repo.get_by_account_number(account_number)
			if not account:
				return None

			return await self.get_account(account.id)

		except Exception as e:
			logger.error(f"根据账户号获取账户失败: {str(e)}")
			raise

	async def get_user_accounts (
			self,
			user_id: int,
			include_closed: bool = False
	) -> List[AccountDomain]:
		"""
		获取用户的所有账户

		Args:
			user_id: 用户ID
			include_closed: 是否包含已关闭账户

		Returns:
			账户列表
		"""
		try:
			# 构建查询条件
			conditions = [Account.user_id == user_id]
			if not include_closed:
				conditions.append(Account.status != "closed")

			# 查询账户
			accounts = await self.account_repo.get_by_conditions(conditions)

			# 转换为领域对象
			account_domains = []
			for account in accounts:
				account_domain = AccountDomain(
					id=account.id,
					account_number=account.account_number,
					account_name=account.account_name,
					user_id=account.user_id,
					account_type=account.account_type,
					broker=account.broker,
					broker_account_id=account.broker_account_id,
					status=account.status,
					status_reason=account.status_reason,
					total_balance=Decimal(str(account.total_balance)),
					available_balance=Decimal(str(account.available_balance)),
					frozen_balance=Decimal(str(account.frozen_balance)),
					market_value=Decimal(str(account.market_value)),
					initial_balance=Decimal(str(account.initial_balance)),
					credit_line=Decimal(str(account.credit_line)) if account.credit_line else None,
					last_trade_date=account.last_trade_date,
					created_at=account.created_at,
					updated_at=account.updated_at
				)
				account_domains.append(account_domain)

			return account_domains

		except Exception as e:
			logger.error(f"获取用户账户失败: {str(e)}")
			raise

	async def create_account (
			self,
			user_id: int,
			account_name: str,
			account_type: str = "cash",
			initial_balance: Decimal = Decimal("1000000.00"),
			broker: Optional[str] = None,
			broker_account_id: Optional[str] = None
	) -> AccountDomain:
		"""
		创建新账户

		Args:
			user_id: 用户ID
			account_name: 账户名称
			account_type: 账户类型
			initial_balance: 初始资金
			broker: 券商名称
			broker_account_id: 券商账户ID

		Returns:
			创建的账户领域对象
		"""
		try:
			# 1. 验证用户存在
			user = await self.user_repo.get_by_id(user_id)
			if not user:
				raise ValueError(f"用户不存在: {user_id}")

			# 2. 验证输入数据
			validate_account_data({
				"account_name": account_name,
				"account_type": account_type,
				"initial_balance": float(initial_balance),
				"broker": broker,
				"broker_account_id": broker_account_id
			})

			# 3. 生成账户号
			account_number = await self._generate_account_number(user_id)

			# 4. 创建账户记录
			account_data = {
				"account_number": account_number,
				"account_name": account_name,
				"user_id": user_id,
				"account_type": account_type,
				"broker": broker,
				"broker_account_id": broker_account_id,
				"total_balance": initial_balance,
				"available_balance": initial_balance,
				"frozen_balance": Decimal("0.00"),
				"market_value": Decimal("0.00"),
				"initial_balance": initial_balance,
				"status": "active"
			}

			account = await self.account_repo.create(account_data)

			# 5. 记录审计日志
			await self.audit_logger.log(
				action="account_create",
				user_id=user_id,
				resource_type="events",
				resource_id=account.id,
				details={
					"account_number": account_number,
					"account_name": account_name,
					"account_type": account_type,
					"initial_balance": float(initial_balance)
				}
			)

			logger.info(f"账户创建成功: {account_number} (用户ID: {user_id})")

			# 6. 转换为领域对象返回
			return AccountDomain(
				id=account.id,
				account_number=account.account_number,
				account_name=account.account_name,
				user_id=account.user_id,
				account_type=account.account_type,
				broker=account.broker,
				broker_account_id=account.broker_account_id,
				status=account.status,
				status_reason=account.status_reason,
				total_balance=Decimal(str(account.total_balance)),
				available_balance=Decimal(str(account.available_balance)),
				frozen_balance=Decimal(str(account.frozen_balance)),
				market_value=Decimal(str(account.market_value)),
				initial_balance=Decimal(str(account.initial_balance)),
				credit_line=Decimal(str(account.credit_line)) if account.credit_line else None,
				last_trade_date=account.last_trade_date,
				created_at=account.created_at,
				updated_at=account.updated_at
			)

		except Exception as e:
			logger.error(f"创建账户失败: {str(e)}")
			raise

	async def update_account (
			self,
			account_id: int,
			**update_data
	) -> Optional[AccountDomain]:
		"""
		更新账户信息

		Args:
			account_id: 账户ID
			**update_data: 更新字段

		Returns:
			更新后的账户领域对象，如果账户不存在则返回None
		"""
		try:
			# 1. 检查账户是否存在
			account = await self.account_repo.get_by_id(account_id)
			if not account:
				return None

			# 2. 记录旧数据（用于审计）
			old_data = {
				"account_name": account.account_name,
				"status": account.status,
				"status_reason": account.status_reason,
				"broker": account.broker,
				"broker_account_id": account.broker_account_id
			}

			# 3. 执行更新
			updated_account = await self.account_repo.update(account_id, update_data)

			# 4. 记录审计日志
			if updated_account:
				changed_fields = {}
				for key, new_value in update_data.items():
					if key in old_data and old_data[key] != new_value:
						changed_fields[key] = {
							"old": old_data[key],
							"new": new_value
						}

				if changed_fields:
					await self.audit_logger.log(
						action="account_update",
						user_id=account.user_id,
						resource_type="events",
						resource_id=account_id,
						details={
							"changed_fields": changed_fields,
							"update_reason": update_data.get("update_reason")
						}
					)

			# 5. 清理缓存
			if self.cache:
				await self.cache.delete(f"events:{account_id}")

			# 6. 转换为领域对象返回
			if updated_account:
				return await self.get_account(account_id)

			return None

		except Exception as e:
			logger.error(f"更新账户失败: {str(e)}")
			raise

	async def delete_account (self, account_id: int) -> bool:
		"""
		软删除账户

		Args:
			account_id: 账户ID

		Returns:
			删除是否成功
		"""
		try:
			# 1. 检查账户是否存在
			account = await self.account_repo.get_by_id(account_id)
			if not account:
				return False

			# 2. 检查账户是否可以删除
			# 检查是否有持仓
			positions = await self.position_repo.get_by_account_id(account_id)
			if any(p.volume > 0 for p in positions):
				raise ValueError("账户存在持仓，无法删除")

			# 检查是否有未完成订单（这里简化处理）
			# 实际实现中需要检查订单表

			# 3. 执行软删除
			update_data = {
				"status": "closed",
				"status_reason": "用户删除",
				"is_deleted": 1
			}

			success = await self.account_repo.update(account_id, update_data)

			# 4. 记录审计日志
			if success:
				await self.audit_logger.log(
					action="account_delete",
					user_id=account.user_id,
					resource_type="events",
					resource_id=account_id,
					details={
						"account_number": account.account_number,
						"reason": "用户删除"
					}
				)

				# 清理缓存
				if self.cache:
					await self.cache.delete(f"events:{account_id}")

			return success

		except Exception as e:
			logger.error(f"删除账户失败: {str(e)}")
			raise

	async def get_accounts (
			self,
			user_id: Optional[int] = None,
			account_type: Optional[str] = None,
			status: Optional[str] = None,
			skip: int = 0,
			limit: int = 100
	) -> List[AccountDomain]:
		"""
		获取账户列表（支持筛选）

		Args:
			user_id: 用户ID筛选
			account_type: 账户类型筛选
			status: 状态筛选
			skip: 跳过记录数
			limit: 返回记录数

		Returns:
			账户列表
		"""
		try:
			# 构建查询条件
			conditions = []

			if user_id:
				conditions.append(Account.user_id == user_id)

			if account_type:
				conditions.append(Account.account_type == account_type)

			if status:
				conditions.append(Account.status == status)

			# 查询账户
			accounts = await self.account_repo.get_by_conditions(
				conditions=conditions,
				skip=skip,
				limit=limit
			)

			# 转换为领域对象
			account_domains = []
			for account in accounts:
				account_domain = AccountDomain(
					id=account.id,
					account_number=account.account_number,
					account_name=account.account_name,
					user_id=account.user_id,
					account_type=account.account_type,
					broker=account.broker,
					broker_account_id=account.broker_account_id,
					status=account.status,
					status_reason=account.status_reason,
					total_balance=Decimal(str(account.total_balance)),
					available_balance=Decimal(str(account.available_balance)),
					frozen_balance=Decimal(str(account.frozen_balance)),
					market_value=Decimal(str(account.market_value)),
					initial_balance=Decimal(str(account.initial_balance)),
					credit_line=Decimal(str(account.credit_line)) if account.credit_line else None,
					last_trade_date=account.last_trade_date,
					created_at=account.created_at,
					updated_at=account.updated_at
				)
				account_domains.append(account_domain)

			return account_domains

		except Exception as e:
			logger.error(f"获取账户列表失败: {str(e)}")
			raise

	async def adjust_total_balance (
			self,
			account_id: int,
			amount: Decimal,
			reason: str
	) -> bool:
		"""
		调整账户总资产

		Args:
			account_id: 账户ID
			amount: 调整金额（正数为增加，负数为减少）
			reason: 调整原因

		Returns:
			调整是否成功
		"""
		try:
			# 获取账户
			account = await self.account_repo.get_by_id(account_id)
			if not account:
				raise ValueError(f"账户不存在: {account_id}")

			# 计算新的总资产
			new_total = Decimal(str(account.total_balance)) + amount

			# 更新总资产
			update_data = {
				"total_balance": new_total
			}

			# 如果是减少，需要检查可用资金
			if amount < 0 and Decimal(str(account.available_balance)) < abs(amount):
				# 自动从可用资金中扣除，不足部分从冻结资金扣除
				available_reduction = min(Decimal(str(account.available_balance)), abs(amount))
				frozen_reduction = abs(amount) - available_reduction

				new_available = Decimal(str(account.available_balance)) - available_reduction
				new_frozen = Decimal(str(account.frozen_balance)) - frozen_reduction

				if new_frozen < 0:
					raise ValueError("调整金额超过可用资金和冻结资金总和")

				update_data["available_balance"] = new_available
				update_data["frozen_balance"] = new_frozen

			success = await self.account_repo.update(account_id, update_data)

			# 记录审计日志
			if success:
				await self.audit_logger.log(
					action="account_balance_adjust",
					user_id=account.user_id,
					resource_type="events",
					resource_id=account_id,
					details={
						"adjustment_type": "total_balance",
						"amount": float(amount),
						"old_balance": float(account.total_balance),
						"new_balance": float(new_total),
						"reason": reason
					}
				)

				# 清理缓存
				if self.cache:
					await self.cache.delete(f"events:{account_id}")

			return success

		except Exception as e:
			logger.error(f"调整账户总资产失败: {str(e)}")
			raise

	async def adjust_available_balance (
			self,
			account_id: int,
			amount: Decimal,
			reason: str
	) -> bool:
		"""
		调整账户可用资金

		Args:
			account_id: 账户ID
			amount: 调整金额（正数为增加，负数为减少）
			reason: 调整原因

		Returns:
			调整是否成功
		"""
		try:
			# 获取账户
			account = await self.account_repo.get_by_id(account_id)
			if not account:
				raise ValueError(f"账户不存在: {account_id}")

			# 计算新的可用资金
			new_available = Decimal(str(account.available_balance)) + amount

			if new_available < 0:
				raise ValueError("调整后可用资金不能为负")

			# 更新可用资金和总资产
			update_data = {
				"available_balance": new_available,
				"total_balance": Decimal(str(account.total_balance)) + amount
			}

			success = await self.account_repo.update(account_id, update_data)

			# 记录审计日志
			if success:
				await self.audit_logger.log(
					action="account_balance_adjust",
					user_id=account.user_id,
					resource_type="events",
					resource_id=account_id,
					details={
						"adjustment_type": "available_balance",
						"amount": float(amount),
						"old_balance": float(account.available_balance),
						"new_balance": float(new_available),
						"reason": reason
					}
				)

				# 清理缓存
				if self.cache:
					await self.cache.delete(f"events:{account_id}")

			return success

		except Exception as e:
			logger.error(f"调整账户可用资金失败: {str(e)}")
			raise

	async def adjust_frozen_balance (
			self,
			account_id: int,
			amount: Decimal,
			reason: str
	) -> bool:
		"""
		调整账户冻结资金

		Args:
			account_id: 账户ID
			amount: 调整金额（正数为增加，负数为减少）
			reason: 调整原因

		Returns:
			调整是否成功
		"""
		try:
			# 获取账户
			account = await self.account_repo.get_by_id(account_id)
			if not account:
				raise ValueError(f"账户不存在: {account_id}")

			# 计算新的冻结资金
			new_frozen = Decimal(str(account.frozen_balance)) + amount

			if new_frozen < 0:
				raise ValueError("调整后冻结资金不能为负")

			# 更新冻结资金和总资产
			update_data = {
				"frozen_balance": new_frozen,
				"total_balance": Decimal(str(account.total_balance)) + amount
			}

			success = await self.account_repo.update(account_id, update_data)

			# 记录审计日志
			if success:
				await self.audit_logger.log(
					action="account_balance_adjust",
					user_id=account.user_id,
					resource_type="events",
					resource_id=account_id,
					details={
						"adjustment_type": "frozen_balance",
						"amount": float(amount),
						"old_balance": float(account.frozen_balance),
						"new_balance": float(new_frozen),
						"reason": reason
					}
				)

				# 清理缓存
				if self.cache:
					await self.cache.delete(f"events:{account_id}")

			return success

		except Exception as e:
			logger.error(f"调整账户冻结资金失败: {str(e)}")
			raise

	async def record_daily_settlement (
			self,
			account_id: int,
			trade_date: date,
			total_asset: Decimal,
			cash: Decimal,
			market_value: Decimal,
			daily_pnl: Decimal,
			daily_return: Decimal
	) -> bool:
		"""
		记录账户每日结算信息

		Args:
			account_id: 账户ID
			trade_date: 交易日
			total_asset: 总资产
			cash: 现金
			market_value: 持仓市值
			daily_pnl: 当日盈亏
			daily_return: 当日收益率

		Returns:
			记录是否成功
		"""
		try:
			# 获取账户
			account = await self.account_repo.get_by_id(account_id)
			if not account:
				raise ValueError(f"账户不存在: {account_id}")

			# 创建每日绩效记录
			performance_data = {
				"user_id": account.user_id,
				"trade_date": trade_date,
				"total_asset": total_asset,
				"cash": cash,
				"market_value": market_value,
				"daily_pnl": daily_pnl,
				"daily_return": daily_return
			}

			# 这里需要调用AccountDailyPerformance的Repository
			# 实际实现中需要具体的Repository方法
			# 这里简化处理
			from sqlalchemy.ext.asyncio import AsyncSession
			from sqlalchemy import insert

			stmt = insert(AccountDailyPerformance).values(**performance_data)
			await self.db.execute(stmt)

			# 更新账户最后交易日
			await self.account_repo.update(account_id, {"last_trade_date": trade_date})

			logger.info(f"记录每日结算: 账户ID={account_id}, 交易日={trade_date}, 总资产={total_asset}")

			return True

		except Exception as e:
			logger.error(f"记录每日结算失败: {str(e)}")
			raise

	async def _generate_account_number (self, user_id: int) -> str:
		"""
		生成账户号

		Args:
			user_id: 用户ID

		Returns:
			生成的账户号
		"""
		try:
			# 获取用户已有账户数
			user_accounts = await self.get_user_accounts(user_id, include_closed=True)
			account_count = len(user_accounts) + 1

			# 生成账户号格式: ACC + 用户ID(6位) + 序号(3位)
			account_number = f"ACC{str(user_id).zfill(6)}{str(account_count).zfill(3)}"

			# 检查是否已存在（理论上不会，但为了安全）
			existing = await self.account_repo.get_by_account_number(account_number)
			if existing:
				# 如果已存在，增加序号重新生成
				account_count += 1
				account_number = f"ACC{str(user_id).zfill(6)}{str(account_count).zfill(3)}"

			return account_number

		except Exception as e:
			logger.error(f"生成账户号失败: {str(e)}")
			raise