# -*- coding: utf-8 -*-
"""
账户数据仓库 - 优化重构版本
位置：quant_server/shared/database/repositories/account_repo.py

设计原则：
1. 单一职责：只处理Account模型的CRUD操作和特定查询
2. 纯数据访问：不包含任何业务逻辑（如余额计算、状态判断等）
3. 方法明确：方法名清晰表达操作意图
4. 返回原始数据：返回ORM对象或原始查询结果，不做业务转换
5. 无业务异常：不抛出业务异常，只抛出数据访问异常

注意：所有业务逻辑应放在对应模块的Service层
"""

from typing import List, Optional, Dict, Any
from datetime import datetime, date, timedelta
from decimal import Decimal
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, and_, or_, desc, func, update, between
from sqlalchemy.orm import selectinload, joinedload

from quant_server.shared.database.repositories.base import BaseRepository
from quant_server.shared.database.models.business_models import Account


class AccountRepository(BaseRepository[Account]):
	"""
	账户数据仓库 - 专注于Account模型的纯数据访问

	按照Repository模式设计原则：
	1. 只负责单个模型（Account）的数据访问
	2. 提供基础的CRUD操作（通过继承BaseRepository获得）
	3. 添加特定于Account模型的查询方法
	4. 不包含任何业务逻辑，仅做数据访问

	业务逻辑应该放在：
	- modules/account/services/account_service.py
	- modules/account/services/asset_service.py
	- modules/trade/services/risk_service.py 等
	"""

	def __init__ (self, session: AsyncSession):
		"""
		初始化账户仓库

		Args:
			session: 异步数据库会话
		"""
		super().__init__(session, Account)  # ✅ 专注于单一模型

	# ==================== Account特定查询方法 ====================

	async def get_by_user_id (self, user_id: int) -> Optional[Account]:
		"""
		根据用户ID获取第一个关联的账户

		Args:
			user_id: 用户ID

		Returns:
			Account对象或None
		"""
		return await self.get_one(Account.user_id == user_id)

	async def get_many_by_user_id (
			self,
			user_id: int,
			skip: int = 0,
			limit: int = 100
	) -> List[Account]:
		"""
		获取用户的所有账户列表

		Args:
			user_id: 用户ID
			skip: 跳过的记录数
			limit: 返回的最大记录数

		Returns:
			账户列表，按创建时间倒序排列
		"""
		return await self.get_many(
			Account.user_id == user_id,
			skip=skip,
			limit=limit,
			order_by=desc(Account.created_at)
		)

	async def get_by_account_number (self, account_number: str) -> Optional[Account]:
		"""
		根据账户号码获取账户

		Args:
			account_number: 账户号码（唯一）

		Returns:
			Account对象或None
		"""
		return await self.get_one(Account.account_number == account_number)

	async def get_by_broker_account_id (self, broker_account_id: str) -> Optional[Account]:
		"""
		根据券商账户ID获取账户

		Args:
			broker_account_id: 券商分配的账户ID

		Returns:
			Account对象或None
		"""
		return await self.get_one(Account.broker_account_id == broker_account_id)

	async def get_active_accounts (
			self,
			user_id: Optional[int] = None,
			skip: int = 0,
			limit: int = 100
	) -> List[Account]:
		"""
		获取活跃账户列表（状态为启用）

		Args:
			user_id: 可选，筛选指定用户的账户
			skip: 跳过的记录数
			limit: 返回的最大记录数

		Returns:
			活跃账户列表，按账户号排序
		"""
		filters = [
			Account.status == "active",
			Account.is_deleted == 0
		]

		if user_id is not None:
			filters.append(Account.user_id == user_id)

		return await self.get_many(
			*filters,
			skip=skip,
			limit=limit,
			order_by=Account.account_number
		)

	async def get_accounts_by_type (
			self,
			account_type: str,
			user_id: Optional[int] = None,
			status: Optional[str] = None
	) -> List[Account]:
		"""
		根据账户类型获取账户列表

		Args:
			account_type: 账户类型（cash, margin, simulation等）
			user_id: 可选，筛选指定用户的账户
			status: 可选，筛选指定状态的账户

		Returns:
			指定类型的账户列表
		"""
		filters = [Account.account_type == account_type]

		if user_id is not None:
			filters.append(Account.user_id == user_id)

		if status is not None:
			filters.append(Account.status == status)

		return await self.get_many(*filters)

	async def get_total_balance_stats (self, user_id: int) -> Dict[str, Any]:
		"""
		获取用户所有账户的总余额统计（纯数据聚合）

		Args:
			user_id: 用户ID

		Returns:
			余额统计字典，包含汇总值和原始Decimal类型
		"""
		query = select(
			func.count(Account.id).label("account_count"),
			func.sum(Account.total_balance).label("total_balance_sum"),
			func.sum(Account.available_balance).label("available_balance_sum"),
			func.sum(Account.frozen_balance).label("frozen_balance_sum"),
			func.sum(Account.market_value).label("market_value_sum"),
			func.avg(Account.total_balance).label("average_balance")
		).where(
			and_(
				Account.user_id == user_id,
				Account.status == "active",
				Account.is_deleted == 0
			)
		)

		result = await self.session.execute(query)
		row = result.fetchone()

		# 返回原始数据，不做业务转换
		return {
			"account_count": row.account_count or 0,
			"total_balance_sum": row.total_balance_sum or Decimal("0"),
			"available_balance_sum": row.available_balance_sum or Decimal("0"),
			"frozen_balance_sum": row.frozen_balance_sum or Decimal("0"),
			"market_value_sum": row.market_value_sum or Decimal("0"),
			"average_balance": row.average_balance or Decimal("0")
		}

	async def get_accounts_by_status (self, status: str) -> List[Account]:
		"""
		根据状态获取账户列表

		Args:
			status: 账户状态（active, frozen, closed等）

		Returns:
			指定状态的账户列表
		"""
		return await self.get_many(
			Account.status == status,
			Account.is_deleted == 0
		)

	async def update_balance_fields (
			self,
			account_id: int,
			**balance_updates: Decimal
	) -> bool:
		"""
		原子更新账户余额字段

		Args:
			account_id: 账户ID
			balance_updates: 余额字段更新值

		Returns:
			是否成功更新（影响行数>0）
		"""
		# 过滤出有效的余额字段
		valid_fields = {
			"total_balance", "available_balance",
			"frozen_balance", "market_value"
		}

		update_data = {
			"updated_at": datetime.now()
		}

		for field, delta in balance_updates.items():
			if field in valid_fields and delta != 0:
				current_column = getattr(Account, field)
				update_data[field] = current_column + delta

		if len(update_data) <= 1:  # 只有updated_at
			return False

		query = update(Account).where(
			and_(
				Account.id == account_id,
				Account.is_deleted == 0
			)
		).values(**update_data)

		result = await self.session.execute(query)
		await self.session.flush()

		return result.rowcount > 0

	async def update_account_status (self, account_id: int, status: str, reason: Optional[str] = None) -> bool:
		"""
		更新账户状态

		Args:
			account_id: 账户ID
			status: 新的状态（active, frozen, closed等）
			reason: 状态变更原因

		Returns:
			是否成功更新
		"""
		update_data = {
			"status": status,
			"updated_at": datetime.now()
		}

		if reason:
			update_data["status_reason"] = reason

		return await self.update(account_id, update_data) is not None

	async def update_last_trade_date (self, account_id: int, trade_date: date) -> bool:
		"""
		更新账户最后交易日

		Args:
			account_id: 账户ID
			trade_date: 最后交易日

		Returns:
			是否成功更新
		"""
		update_data = {
			"last_trade_date": trade_date,
			"updated_at": datetime.now()
		}

		return await self.update(account_id, update_data) is not None

	async def get_accounts_by_broker (
			self,
			broker_name: str,
			status: Optional[str] = None
	) -> List[Account]:
		"""
		获取指定券商的所有账户

		Args:
			broker_name: 券商名称
			status: 可选，筛选指定状态的账户

		Returns:
			指定券商的账户列表
		"""
		filters = [Account.broker == broker_name]

		if status is not None:
			filters.append(Account.status == status)

		return await self.get_many(*filters)

	async def search_accounts (
			self,
			keyword: str,
			status: Optional[str] = None,
			account_type: Optional[str] = None,
			broker: Optional[str] = None,
			skip: int = 0,
			limit: int = 50
	) -> List[Account]:
		"""
		搜索账户（按账户号、账户名或券商账户ID模糊搜索）

		Args:
			keyword: 搜索关键词
			status: 可选的账户状态筛选
			account_type: 可选的账户类型筛选
			broker: 可选的券商筛选
			skip: 跳过的记录数
			limit: 返回的最大记录数

		Returns:
			搜索结果列表
		"""
		filters = [
			or_(
				Account.account_number.ilike(f"%{keyword}%"),
				Account.broker_account_id.ilike(f"%{keyword}%"),
				Account.account_name.ilike(f"%{keyword}%")
			),
			Account.is_deleted == 0
		]

		if status:
			filters.append(Account.status == status)
		if account_type:
			filters.append(Account.account_type == account_type)
		if broker:
			filters.append(Account.broker == broker)

		return await self.get_many(
			*filters,
			skip=skip,
			limit=limit,
			order_by=desc(Account.updated_at)
		)

	async def get_account_ids_by_user (self, user_id: int) -> List[int]:
		"""
		获取用户的所有账户ID列表

		Args:
			user_id: 用户ID

		Returns:
			账户ID列表
		"""
		query = select(Account.id).where(
			and_(
				Account.user_id == user_id,
				Account.is_deleted == 0
			)
		).order_by(Account.created_at)

		result = await self.session.execute(query)
		return [row[0] for row in result.fetchall()]

	async def batch_update_status (
			self,
			account_ids: List[int],
			status: str,
			reason: Optional[str] = None
	) -> int:
		"""
		批量更新账户状态

		Args:
			account_ids: 账户ID列表
			status: 新的状态
			reason: 状态变更原因（可选）

		Returns:
			实际更新的记录数
		"""
		if not account_ids:
			return 0

		update_data = {
			"status": status,
			"updated_at": datetime.now()
		}

		if reason:
			update_data["status_reason"] = reason

		query = update(Account).where(
			and_(
				Account.id.in_(account_ids),
				Account.is_deleted == 0
			)
		).values(**update_data)

		result = await self.session.execute(query)
		await self.session.flush()

		return result.rowcount

	async def get_account_statistics (self) -> Dict[str, Any]:
		"""
		获取账户统计信息（数据层面）

		Returns:
			账户统计字典
		"""
		# 按状态统计
		status_query = select(
			Account.status,
			func.count(Account.id).label("count"),
			func.sum(Account.total_balance).label("total_balance_sum"),
			func.avg(Account.total_balance).label("avg_balance")
		).where(
			Account.is_deleted == 0
		).group_by(Account.status)

		status_result = await self.session.execute(status_query)
		status_stats = {
			row.status: {
				"count": row.count,
				"total_balance": row.total_balance_sum or Decimal("0"),
				"average_balance": row.avg_balance or Decimal("0")
			}
			for row in status_result
		}

		# 按账户类型统计
		type_query = select(
			Account.account_type,
			func.count(Account.id).label("count"),
			func.sum(Account.total_balance).label("total_balance_sum")
		).where(Account.is_deleted == 0).group_by(Account.account_type)

		type_result = await self.session.execute(type_query)
		type_stats = {
			row.account_type: {
				"count": row.count,
				"total_balance": row.total_balance_sum or Decimal("0")
			}
			for row in type_result
		}

		# 按券商统计
		broker_query = select(
			Account.broker,
			func.count(Account.id).label("count"),
			func.sum(Account.total_balance).label("total_balance_sum")
		).where(
			and_(
				Account.is_deleted == 0,
				Account.broker.isnot(None)
			)
		).group_by(Account.broker)

		broker_result = await self.session.execute(broker_query)
		broker_stats = {
			row.broker: {
				"count": row.count,
				"total_balance": row.total_balance_sum or Decimal("0")
			}
			for row in broker_result
		}

		# 总体统计
		overall_query = select(
			func.count(Account.id).label("total_count"),
			func.sum(Account.total_balance).label("total_balance_all"),
			func.avg(Account.total_balance).label("avg_balance"),
			func.max(Account.total_balance).label("max_balance"),
			func.min(Account.total_balance).label("min_balance"),
			func.sum(Account.market_value).label("total_market_value")
		).where(Account.is_deleted == 0)

		overall_result = await self.session.execute(overall_query)
		overall_row = overall_result.fetchone()

		return {
			"overall": {
				"total_accounts": overall_row.total_count or 0,
				"total_balance": overall_row.total_balance_all or Decimal("0"),
				"average_balance": overall_row.avg_balance or Decimal("0"),
				"max_balance": overall_row.max_balance or Decimal("0"),
				"min_balance": overall_row.min_balance or Decimal("0"),
				"total_market_value": overall_row.total_market_value or Decimal("0")
			},
			"by_status": status_stats,
			"by_type": type_stats,
			"by_broker": broker_stats
		}

	async def get_low_balance_accounts (
			self,
			threshold: Decimal = Decimal("10000"),
			status: str = "active",
			limit: int = 100
	) -> List[Account]:
		"""
		获取余额低于阈值的账户

		Args:
			threshold: 余额阈值
			status: 账户状态筛选
			limit: 返回结果数量限制

		Returns:
			低余额账户列表
		"""
		return await self.get_many(
			and_(
				Account.available_balance < threshold,
				Account.status == status,
				Account.is_deleted == 0
			),
			limit=limit,
			order_by=Account.available_balance
		)

	async def get_inactive_accounts (
			self,
			days_threshold: int = 30,
			status: str = "active"
	) -> List[Account]:
		"""
		获取长时间未交易的账户

		Args:
			days_threshold: 天数阈值
			status: 账户状态筛选

		Returns:
			不活跃账户列表
		"""
		threshold_date = datetime.now().date() - timedelta(days=days_threshold)

		return await self.get_many(
			and_(
				or_(
					Account.last_trade_date.is_(None),
					Account.last_trade_date < threshold_date
				),
				Account.status == status,
				Account.is_deleted == 0
			),
			order_by=Account.last_trade_date
		)

	async def get_accounts_with_balance_range (
			self,
			min_balance: Optional[Decimal] = None,
			max_balance: Optional[Decimal] = None,
			status: Optional[str] = None,
			limit: int = 100
	) -> List[Account]:
		"""
		获取余额在指定范围内的账户

		Args:
			min_balance: 最小余额（包含）
			max_balance: 最大余额（包含）
			status: 账户状态筛选
			limit: 返回结果数量限制

		Returns:
			符合条件的账户列表
		"""
		filters = [Account.is_deleted == 0]

		if min_balance is not None and max_balance is not None:
			filters.append(
				between(Account.total_balance, min_balance, max_balance)
			)
		elif min_balance is not None:
			filters.append(Account.total_balance >= min_balance)
		elif max_balance is not None:
			filters.append(Account.total_balance <= max_balance)

		if status is not None:
			filters.append(Account.status == status)

		return await self.get_many(
			*filters,
			limit=limit,
			order_by=desc(Account.total_balance)
		)

	async def count_accounts_by_criteria (
			self,
			user_id: Optional[int] = None,
			status: Optional[str] = None,
			account_type: Optional[str] = None,
			broker: Optional[str] = None
	) -> int:
		"""
		根据条件统计账户数量

		Args:
			user_id: 用户ID筛选
			status: 状态筛选
			account_type: 类型筛选
			broker: 券商筛选

		Returns:
			符合条件的账户数量
		"""
		filters = [Account.is_deleted == 0]

		if user_id is not None:
			filters.append(Account.user_id == user_id)
		if status is not None:
			filters.append(Account.status == status)
		if account_type is not None:
			filters.append(Account.account_type == account_type)
		if broker is not None:
			filters.append(Account.broker == broker)

		return await self.count(*filters)

	async def exists_by_account_number (self, account_number: str) -> bool:
		"""
		检查账户号码是否存在

		Args:
			account_number: 账户号码

		Returns:
			是否存在
		"""
		count = await self.count(
			Account.account_number == account_number,
			Account.is_deleted == 0
		)
		return count > 0

	async def get_with_positions (self, account_id: int) -> Optional[Account]:
		"""
		获取账户信息及其持仓（预加载）

		Args:
			account_id: 账户ID

		Returns:
			Account对象（包含positions关联）或None
		"""
		query = select(Account).options(
			selectinload(Account.positions)
		).where(
			and_(
				Account.id == account_id,
				Account.is_deleted == 0
			)
		)

		result = await self.session.execute(query)
		return result.scalar_one_or_none()

	async def get_with_orders (self, account_id: int, limit: int = 50) -> Optional[Account]:
		"""
		获取账户信息及其最近订单（预加载）

		Args:
			account_id: 账户ID
			limit: 返回的订单数量限制

		Returns:
			Account对象（包含orders关联）或None
		"""
		# 注意：这里使用了joinedload和limit的特定写法
		query = select(Account).options(
			joinedload(Account.orders).limit(limit)
		).where(
			and_(
				Account.id == account_id,
				Account.is_deleted == 0
			)
		)

		result = await self.session.execute(query)
		return result.unique().scalar_one_or_none()


# 工厂函数
def create_account_repository (session: AsyncSession) -> AccountRepository:
	"""
	创建账户仓库实例的工厂函数

	Args:
		session: 数据库会话

	Returns:
		AccountRepository实例
	"""
	return AccountRepository(session)