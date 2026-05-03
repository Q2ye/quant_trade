"""
资金服务
处理账户资金存入、取出、冻结、解冻等操作
"""
import logging
from datetime import datetime
from decimal import Decimal
from typing import Optional, Dict, Any, List

from sqlalchemy.ext.asyncio import AsyncSession

from shared.cache.base import CacheBase
from shared.database.models.business_models import Account
from shared.database.repositories.account.asset.account_repo import AccountRepository
from shared.database.repositories.account.settlement.cash_flow_repo import CashFlowRepository
from shared.security.audit import AuditLogger
from utils.core_utils.data_utils.validation import validate_amount

logger = logging.getLogger(__name__)


class CashService:
	"""资金服务 - 处理资金相关业务逻辑"""

	def __init__ (self, db: AsyncSession, cache: Optional[CacheBase] = None):
		self.db = db
		self.cache = cache
		self.account_repo = AccountRepository(db)
		self.cash_flow_repo = CashFlowRepository(db)
		self.audit_logger = AuditLogger()

	async def _clear_cache (self, account_id: str, include_cash_flows: bool = False):
		"""
		清理账户相关缓存

		Args:
			account_id: 账户ID
			include_cash_flows: 是否清理资金流水缓存
		"""
		if self.cache:
			await self.cache.delete(f"events:{account_id}")
			if include_cash_flows:
				await self.cache.delete(f"events:cash_flows:{account_id}")

	async def _get_account (self, account_id: str, require_active: bool = True) -> Account:
		"""
		获取账户并检查状态

		Args:
			account_id: 账户ID
			require_active: 是否要求账户状态为活跃

		Returns:
			Account: 账户对象

		Raises:
			ValueError: 账户不存在或状态不符合要求
		"""
		account = await self.account_repo.get(account_id)
		if not account:
			raise ValueError(f"账户不存在: {account_id}")

		if require_active and account.status != "active":
			raise ValueError(f"账户状态为{account.status}，无法操作")

		return account

	async def deposit (
			self,
			account_id: str,
			amount: Decimal,
			description: str = "存款",
			reference_id: Optional[str] = None
	) -> Dict[str, Any]:
		"""
		资金存入

		Args:
			account_id: 账户ID
			amount: 存入金额
			description: 描述
			reference_id: 外部参考ID

		Returns:
			存款结果
		"""
		try:
			# 验证金额
			validate_amount(amount, min_value=Decimal("0.01"))

			# 获取账户
			account = await self._get_account(account_id)

			# 计算新余额
			new_total = Decimal(str(account.total_balance)) + amount
			new_available = Decimal(str(account.available_balance)) + amount

			# 更新账户余额
			update_data = {
				"total_balance": new_total,
				"available_balance": new_available
			}

			success = await self.account_repo.update(account_id, update_data)

			if success:
				# 记录资金流水
				cash_flow_data = {
					"user_id": account.user_id,
					"flow_type": "deposit",
					"amount": amount,
					"description": description,
					"reference_id": reference_id,
					"status": "completed"
				}

				await self.cash_flow_repo.create(cash_flow_data)

				# 记录审计日志
				await self.audit_logger.log_simple(
					action="cash_deposit",
					user_id=account.user_id,
					resource_type="events",
					resource_id=account_id,
					description=description,
					details={
						"amount": float(amount),
						"old_balance": float(account.available_balance),
						"new_balance": float(new_available),
						"reference_id": reference_id
					}
				)

				# 清理缓存
				await self._clear_cache(account_id, include_cash_flows=True)

				logger.info(f"存款成功: 账户ID={account_id}, 金额={amount}, 描述={description}")

				return {
					"success": True,
					"account_id": account_id,
					"amount": float(amount),
					"old_balance": float(account.available_balance),
					"new_balance": float(new_available),
					"description": description,
					"timestamp": datetime.now().isoformat()
				}
			else:
				raise ValueError("更新账户余额失败")

		except Exception as e:
			logger.error(f"存款失败: {str(e)}")
			raise

	async def withdraw (
			self,
			account_id: str,
			amount: Decimal,
			description: str = "取款",
			reference_id: Optional[str] = None
	) -> Dict[str, Any]:
		"""
		资金取出

		Args:
			account_id: 账户ID
			amount: 取出金额
			description: 描述
			reference_id: 外部参考ID

		Returns:
			取款结果
		"""
		try:
			# 验证金额
			validate_amount(amount, min_value=Decimal("0.01"))

			# 获取账户
			account = await self._get_account(account_id)

			# 检查资金是否足够
			if Decimal(str(account.available_balance)) < amount:
				raise ValueError(f"可用资金不足，当前可用: {account.available_balance}, 需要: {amount}")

			# 计算新余额
			new_total = Decimal(str(account.total_balance)) - amount
			new_available = Decimal(str(account.available_balance)) - amount

			# 更新账户余额
			update_data = {
				"total_balance": new_total,
				"available_balance": new_available
			}

			success = await self.account_repo.update(account_id, update_data)

			if success:
				# 记录资金流水
				cash_flow_data = {
					"user_id": account.user_id,
					"flow_type": "withdrawal",
					"amount": amount,
					"description": description,
					"reference_id": reference_id,
					"status": "completed"
				}

				await self.cash_flow_repo.create(cash_flow_data)

				# 记录审计日志
				await self.audit_logger.log_simple(
					action="cash_withdrawal",
					user_id=account.user_id,
					resource_type="events",
					resource_id=account_id,
					description=description,
					details={
						"amount": float(amount),
						"old_balance": float(account.available_balance),
						"new_balance": float(new_available),
						"reference_id": reference_id
					}
				)

				# 清理缓存
				await self._clear_cache(account_id, include_cash_flows=True)

				logger.info(f"取款成功: 账户ID={account_id}, 金额={amount}, 描述={description}")

				return {
					"success": True,
					"account_id": account_id,
					"amount": float(amount),
					"old_balance": float(account.available_balance),
					"new_balance": float(new_available),
					"description": description,
					"timestamp": datetime.now().isoformat()
				}
			else:
				raise ValueError("更新账户余额失败")

		except Exception as e:
			logger.error(f"取款失败: {str(e)}")
			raise

	async def freeze_funds (
			self,
			account_id: str,
			amount: Decimal,
			reason: str,
			reference_id: Optional[str] = None
	) -> Dict[str, Any]:
		"""
		冻结资金

		Args:
			account_id: 账户ID
			amount: 冻结金额
			reason: 冻结原因
			reference_id: 外部参考ID

		Returns:
			冻结结果
		"""
		try:
			# 验证金额
			validate_amount(amount, min_value=Decimal("0.01"))

			# 获取账户
			account = await self._get_account(account_id)

			# 检查可用资金是否足够
			if Decimal(str(account.available_balance)) < amount:
				raise ValueError(f"可用资金不足，当前可用: {account.available_balance}, 需要冻结: {amount}")

			# 计算新余额
			new_available = Decimal(str(account.available_balance)) - amount
			new_frozen = Decimal(str(account.frozen_balance)) + amount

			# 更新账户余额
			update_data = {
				"available_balance": new_available,
				"frozen_balance": new_frozen
			}

			success = await self.account_repo.update(account_id, update_data)

			if success:
				# 记录资金冻结流水
				cash_flow_data = {
					"user_id": account.user_id,
					"flow_type": "freeze",
					"amount": amount,
					"description": f"资金冻结 - {reason}",
					"reference_id": reference_id,
					"status": "completed"
				}

				await self.cash_flow_repo.create(cash_flow_data)

				# 记录审计日志
				await self.audit_logger.log_simple(
					action="cash_freeze",
					user_id=account.user_id,
					resource_type="events",
					resource_id=account_id,
					description=f"资金冻结 - {reason}",
					details={
						"amount": float(amount),
						"old_available": float(account.available_balance),
						"new_available": float(new_available),
						"old_frozen": float(account.frozen_balance),
						"new_frozen": float(new_frozen),
						"reason": reason,
						"reference_id": reference_id
					}
				)

				# 清理缓存
				await self._clear_cache(account_id)

				logger.info(f"资金冻结成功: 账户ID={account_id}, 金额={amount}, 原因={reason}")

				return {
					"success": True,
					"account_id": account_id,
					"amount": float(amount),
					"old_available": float(account.available_balance),
					"new_available": float(new_available),
					"old_frozen": float(account.frozen_balance),
					"new_frozen": float(new_frozen),
					"reason": reason,
					"timestamp": datetime.now().isoformat()
				}
			else:
				raise ValueError("更新账户余额失败")

		except Exception as e:
			logger.error(f"资金冻结失败: {str(e)}")
			raise

	async def unfreeze_funds (
			self,
			account_id: str,
			amount: Decimal,
			reason: str,
			reference_id: Optional[str] = None
	) -> Dict[str, Any]:
		"""
		解冻资金

		Args:
			account_id: 账户ID
			amount: 解冻金额
			reason: 解冻原因
			reference_id: 外部参考ID

		Returns:
			解冻结果
		"""
		try:
			# 验证金额
			validate_amount(amount, min_value=Decimal("0.01"))

			# 获取账户
			account = await self._get_account(account_id, require_active=False)

			# 检查冻结资金是否足够
			if Decimal(str(account.frozen_balance)) < amount:
				raise ValueError(f"冻结资金不足，当前冻结: {account.frozen_balance}, 需要解冻: {amount}")

			# 计算新余额
			new_available = Decimal(str(account.available_balance)) + amount
			new_frozen = Decimal(str(account.frozen_balance)) - amount

			# 更新账户余额
			update_data = {
				"available_balance": new_available,
				"frozen_balance": new_frozen
			}

			success = await self.account_repo.update(account_id, update_data)

			if success:
				# 记录资金解冻流水
				cash_flow_data = {
					"user_id": account.user_id,
					"flow_type": "unfreeze",
					"amount": amount,
					"description": f"资金解冻 - {reason}",
					"reference_id": reference_id,
					"status": "completed"
				}

				await self.cash_flow_repo.create(cash_flow_data)

				# 记录审计日志
				await self.audit_logger.log_simple(
					action="cash_unfreeze",
					user_id=account.user_id,
					resource_type="events",
					resource_id=account_id,
					description=f"资金解冻 - {reason}",
					details={
						"amount": float(amount),
						"old_available": float(account.available_balance),
						"new_available": float(new_available),
						"old_frozen": float(account.frozen_balance),
						"new_frozen": float(new_frozen),
						"reason": reason,
						"reference_id": reference_id
					}
				)

				# 清理缓存
				await self._clear_cache(account_id)

				logger.info(f"资金解冻成功: 账户ID={account_id}, 金额={amount}, 原因={reason}")

				return {
					"success": True,
					"account_id": account_id,
					"amount": float(amount),
					"old_available": float(account.available_balance),
					"new_available": float(new_available),
					"old_frozen": float(account.frozen_balance),
					"new_frozen": float(new_frozen),
					"reason": reason,
					"timestamp": datetime.now().isoformat()
				}
			else:
				raise ValueError("更新账户余额失败")

		except Exception as e:
			logger.error(f"资金解冻失败: {str(e)}")
			raise

	async def transfer_funds (
			self,
			from_account_id: str,
			to_account_id: str,
			amount: Decimal,
			description: str,
			reference_id: Optional[str] = None
	) -> Dict[str, Any]:
		"""
		资金转账

		Args:
			from_account_id: 转出账户ID
			to_account_id: 转入账户ID
			amount: 转账金额
			description: 描述
			reference_id: 外部参考ID

		Returns:
			转账结果
		"""
		try:
			# 验证金额
			validate_amount(amount, min_value=Decimal("0.01"))

			# 检查是否为同一账户
			if from_account_id == to_account_id:
				raise ValueError("不能向同一账户转账")

			# 获取转出账户
			from_account = await self._get_account(from_account_id)

			# 获取转入账户
			to_account = await self._get_account(to_account_id)

			# 检查转出账户资金是否足够
			if Decimal(str(from_account.available_balance)) < amount:
				raise ValueError(f"转出账户资金不足，当前可用: {from_account.available_balance}, 需要: {amount}")

			# 计算新余额
			from_new_available = Decimal(str(from_account.available_balance)) - amount
			from_new_total = Decimal(str(from_account.total_balance)) - amount

			to_new_available = Decimal(str(to_account.available_balance)) + amount
			to_new_total = Decimal(str(to_account.total_balance)) + amount

			# 执行转账（事务）
			async with self.db.begin():
				# 更新转出账户
				await self.account_repo.update(from_account_id, {
					"available_balance": from_new_available,
					"total_balance": from_new_total
				})

				# 更新转入账户
				await self.account_repo.update(to_account_id, {
					"available_balance": to_new_available,
					"total_balance": to_new_total
				})

				# 记录转出流水
				from_cash_flow_data = {
					"user_id": from_account.user_id,
					"flow_type": "transfer_out",
					"amount": amount,
					"description": f"转账给账户{to_account.account_number} - {description}",
					"reference_id": reference_id,
					"status": "completed"
				}

				await self.cash_flow_repo.create(from_cash_flow_data)

				# 记录转入流水
				to_cash_flow_data = {
					"user_id": to_account.user_id,
					"flow_type": "transfer_in",
					"amount": amount,
					"description": f"收到账户{from_account.account_number}转账 - {description}",
					"reference_id": reference_id,
					"status": "completed"
				}

				await self.cash_flow_repo.create(to_cash_flow_data)

			# 记录审计日志
			await self.audit_logger.log_simple(
				action="cash_transfer",
				user_id=from_account.user_id,
				resource_type="events",
				resource_id=from_account_id,
				description=description,
				details={
					"from_account": from_account.account_number,
					"to_account": to_account.account_number,
					"amount": float(amount),
					"reference_id": reference_id
				}
			)

			# 清理缓存
			await self._clear_cache(from_account_id, include_cash_flows=True)
			await self._clear_cache(to_account_id, include_cash_flows=True)

			logger.info(
				f"资金转账成功: 从{from_account.account_number}到{to_account.account_number}, "
				f"金额={amount}, 描述={description}"
			)

			return {
				"success": True,
				"from_account_id": from_account_id,
				"from_account_number": from_account.account_number,
				"to_account_id": to_account_id,
				"to_account_number": to_account.account_number,
				"amount": float(amount),
				"from_new_balance": float(from_new_available),
				"to_new_balance": float(to_new_available),
				"description": description,
				"timestamp": datetime.now().isoformat()
			}

		except Exception as e:
			await self.db.rollback()
			logger.error(f"资金转账失败: {str(e)}")
			raise

	async def get_cash_flows (
			self,
			account_id: str,
			flow_type: Optional[str] = None,
			start_date: Optional[datetime] = None,
			end_date: Optional[datetime] = None,
			skip: int = 0,
			limit: int = 100
	) -> List[Dict[str, Any]]:
		"""
		获取资金流水

		Args:
			account_id: 账户ID
			flow_type: 流水类型筛选
			start_date: 开始日期
			end_date: 结束日期
			skip: 跳过记录数
			limit: 返回记录数

		Returns:
			资金流水列表
		"""
		try:
			# 检查缓存
			cache_key = f"events:cash_flows:{account_id}:{flow_type}:{start_date}:{end_date}:{skip}:{limit}"
			if self.cache:
				cached_flows = await self.cache.get(cache_key)
				if cached_flows:
					return cached_flows

			# 构建查询
			query = self.cash_flow_repo.build_query()
			query = query.where(self.cash_flow_repo.model.user_id == account_id)

			if flow_type:
				query = query.where(self.cash_flow_repo.model.flow_type == flow_type)

			if start_date:
				query = query.where(self.cash_flow_repo.model.created_at >= start_date)

			if end_date:
				query = query.where(self.cash_flow_repo.model.created_at <= end_date)

			# 排序和分页
			query = query.order_by(self.cash_flow_repo.model.created_at.desc())
			query = query.offset(skip).limit(limit)

			# 查询资金流水
			cash_flows = await self.cash_flow_repo.execute_query(query)

			# 转换为字典格式
			result = []
			for flow in cash_flows:
				result.append({
					"id": flow.id,
					"flow_type": flow.flow_type,
					"amount": float(flow.amount),
					"description": flow.description,
					"reference_id": flow.reference_id,
					"status": flow.status,
					"created_at": flow.created_at.isoformat()
				})

			# 更新缓存
			if self.cache:
				await self.cache.set(cache_key, result, ttl=300)  # 缓存5分钟

			return result

		except Exception as e:
			logger.error(f"获取资金流水失败: {str(e)}")
			raise

	async def get_balance_summary (self, account_id: str) -> Dict[str, Any]:
		"""
		获取资金余额汇总

		Args:
			account_id: 账户ID

		Returns:
			资金余额汇总
		"""
		try:
			# 获取账户
			account = await self._get_account(account_id, require_active=False)

			# 获取今日资金流水
			today = datetime.now().replace(hour=0, minute=0, second=0, microsecond=0)
			today_cash_flows = await self.get_cash_flows(
				account_id=account_id,
				start_date=today
			)

			# 计算今日统计
			today_deposit = sum(
				flow["amount"] for flow in today_cash_flows
				if flow["flow_type"] == "deposit"
			)

			today_withdrawal = sum(
				flow["amount"] for flow in today_cash_flows
				if flow["flow_type"] == "withdrawal"
			)

			today_transfer_in = sum(
				flow["amount"] for flow in today_cash_flows
				if flow["flow_type"] == "transfer_in"
			)

			today_transfer_out = sum(
				flow["amount"] for flow in today_cash_flows
				if flow["flow_type"] == "transfer_out"
			)

			return {
				"account_id": account_id,
				"account_number": account.account_number,
				"total_balance": float(account.total_balance),
				"available_balance": float(account.available_balance),
				"frozen_balance": float(account.frozen_balance),
				"market_value": float(account.market_value),
				"today_statistics": {
					"deposit": today_deposit,
					"withdrawal": today_withdrawal,
					"transfer_in": today_transfer_in,
					"transfer_out": today_transfer_out,
					"net_change": today_deposit + today_transfer_in - today_withdrawal - today_transfer_out
				},
				"timestamp": datetime.now().isoformat()
			}

		except Exception as e:
			logger.error(f"获取资金余额汇总失败: {str(e)}")
			raise