"""
账户管理器
负责协调账户相关的多个引擎和服务，处理复杂的账户业务逻辑
"""
import logging
from datetime import datetime, date
from decimal import Decimal
from typing import Optional, Dict, Any

from quant_server.modules.account.events import AccountBalanceUpdatedEvent, AccountStatusChangedEvent
from quant_server.shared.database.repositories.account.asset.account_repo import AccountRepository
from quant_server.shared.database.repositories.trading.order.order_repo import OrderRepository
from quant_server.shared.database.repositories.trading.position.position_repo import PositionRepository
from quant_server.shared.database.repositories.trading.order.trade_repo import TradeRepository
from sqlalchemy.ext.asyncio import AsyncSession

from quant_server.modules.account.calculators.asset_calculator import AssetCalculator
from quant_server.modules.account.calculators.pnl_calculator import PnLCalculator
from quant_server.modules.account.models import AccountDomain
from quant_server.modules.account.services.account_service import AccountService
from quant_server.modules.account.services.asset_service import AssetService
from quant_server.modules.account.services.cash_service import CashService
from quant_server.modules.account.services.fee_service import FeeService
from quant_server.modules.account.services.position_service import PositionService
from quant_server.shared.cache.base import CacheBase
from quant_server.shared.messaging.producer import MessageProducer

logger = logging.getLogger(__name__)


class AccountManager:
	"""账户管理器 - 协调账户相关的所有服务"""

	def __init__ (
			self,
			db: AsyncSession,
			cache: Optional[CacheBase] = None,
			message_producer: Optional[MessageProducer] = None
	):
		self.db = db
		self.cache = cache
		self.message_producer = message_producer

		# 初始化Repository
		self.account_repo = AccountRepository(db)
		self.position_repo = PositionRepository(db)
		self.trade_repo = TradeRepository(db)
		self.order_repo = OrderRepository(db)

		# 初始化服务
		self.account_service = AccountService(db)
		self.position_service = PositionService(db)
		self.asset_service = AssetService(db)
		self.cash_service = CashService(db)
		self.fee_service = FeeService(db)

		# 初始化计算器
		self.asset_calculator = AssetCalculator(self.db)
		self.pnl_calculator = PnLCalculator(self.db)

	async def create_user_account (
			self,
			user_id: str,
			account_name: str,
			account_type: str = "cash",
			initial_balance: Decimal = Decimal("1000000.00"),
			broker: Optional[str] = None,
			broker_account_id: Optional[str] = None
	) -> Dict[str, Any]:
		"""
		创建用户账户（完整流程）

		Args:
			user_id: 用户ID
			account_name: 账户名称
			account_type: 账户类型
			initial_balance: 初始资金
			broker: 券商名称
			broker_account_id: 券商账户ID

		Returns:
			创建结果
		"""
		try:
			# 1. 检查用户是否已有过多账户
			existing_accounts = await self.account_service.get_user_accounts(user_id)
			if len(existing_accounts) >= 5:  # 限制最多5个账户
				raise ValueError(f"用户已达到账户数量限制(5个)")

			# 2. 创建账户
			account = await self.account_service.create_account(
				user_id=user_id,
				account_name=account_name,
				account_type=account_type,
				initial_balance=initial_balance,
				broker=broker,
				broker_account_id=broker_account_id
			)

			# 3. 初始化账户资金
			if initial_balance > 0:
				await self.cash_service.deposit(account.id, initial_balance, "初始资金", "account_creation")

			# 4. 发布账户创建事件
			if self.message_producer:
				event = AccountBalanceUpdatedEvent(
					account_id=account.id,
					balance_type="total",
					old_balance=Decimal("0.00"),
					new_balance=initial_balance,
					change_amount=initial_balance,
					change_reason="account_creation"
				)
				await self.message_producer.publish("events.events", event)

			# 5. 更新缓存
			if self.cache:
				await self._update_account_cache(account)

			logger.info(f"账户创建成功: {account.account_number} (用户ID: {user_id})")

			return {
				"success": True,
				"account_id": account.id,
				"account_number": account.account_number,
				"message": "账户创建成功"
			}

		except Exception as e:
			logger.error(f"创建用户账户失败: {str(e)}")
			return {
				"success": False,
				"error": str(e)
			}

	async def close_account (self, account_id: str, reason: str) -> Dict[str, Any]:
		"""
		关闭账户（完整流程）

		Args:
			account_id: 账户ID
			reason: 关闭原因

		Returns:
			关闭结果
		"""
		try:
			# 1. 检查账户是否存在且活跃
			account = await self.account_service.get_account(account_id)
			if not account:
				raise ValueError("账户不存在")

			if account.status == "closed":
				raise ValueError("账户已关闭")

			# 2. 检查账户持仓
			positions = await self.position_service.get_account_positions(account_id)
			if any(p.volume > 0 for p in positions):
				raise ValueError("账户存在持仓，无法关闭")

			# 3. 检查未完成订单
			pending_orders = await self.order_repo.get_active_orders(account_id=account_id)
			if pending_orders:
				raise ValueError("存在未完成订单，无法关闭")

			# 4. 提取剩余资金
			if account.available_balance > 0:
				withdrawal_result = await self.cash_service.withdraw(
					account_id, account.available_balance, "账户关闭提现"
				)
				if not withdrawal_result:
					raise ValueError("资金提取失败")

			# 5. 关闭账户
			await self.account_service.update_account(
				account_id,
				status="closed",
				status_reason=reason
			)

			# 6. 发布账户状态变更事件
			if self.message_producer:
				event = AccountStatusChangedEvent(
					account_id=account_id,
					old_status=account.status,
					new_status="closed",
					reason=reason,
					timestamp=datetime.now()
				)
				await self.message_producer.publish("events.events", event)

			# 7. 清理缓存
			if self.cache:
				await self._clear_account_cache(account_id)

			logger.info(f"账户关闭成功: {account.account_number} (原因: {reason})")

			return {
				"success": True,
				"account_id": account_id,
				"message": "账户关闭成功"
			}

		except Exception as e:
			logger.error(f"关闭账户失败: {str(e)}")
			return {
				"success": False,
				"error": str(e)
			}

	async def get_account_overview (self, account_id: str) -> Dict[str, Any]:
		"""
		获取账户总览信息

		Args:
			account_id: 账户ID

		Returns:
			账户总览信息
		"""
		try:
			# 检查缓存
			cache_key = f"events:overview:{account_id}"
			if self.cache:
				cached_data = await self.cache.get(cache_key)
				if cached_data:
					return cached_data

			# 1. 获取账户信息
			account = await self.account_service.get_account(account_id)
			if not account:
				raise ValueError("账户不存在")

			# 2. 获取持仓列表
			positions = await self.position_service.get_account_positions(account_id)

			# 3. 获取资产计算
			asset_summary = await self.asset_service.get_account_assets(account_id)

			# 4. 获取今日交易统计
			today = date.today()
			daily_trades = await self.trade_repo.get_by_trade_date(today, user_id=None)

			# 5. 计算绩效指标
			performance = await self.pnl_calculator.calculate_account_performance(account_id)

			# 6. 构建总览数据
			overview = {
				"account_info": {
					"id": account.id,
					"account_number": account.account_number,
					"account_name": account.account_name,
					"status": account.status,
					"account_type": account.account_type
				},
				"balance_info": {
					"total_balance": float(account.total_balance),
					"available_balance": float(account.available_balance),
					"frozen_balance": float(account.frozen_balance),
					"market_value": float(account.market_value)
				},
				"position_summary": {
					"total_positions": len(positions),
					"positions_with_volume": len([p for p in positions if p.volume > 0]),
					"total_market_value": sum(float(p.market_value) for p in positions),
					"total_pnl": sum(float(p.pnl) for p in positions)
				},
				"asset_summary": asset_summary,
				"today_statistics": {
					"trade_count": len(daily_trades),
					"total_volume": sum(t.volume for t in daily_trades),
					"total_amount": sum(float(t.price * t.volume) for t in daily_trades),
					"total_fee": sum(float(t.commission + t.tax) for t in daily_trades)
				},
				"performance": performance,
				"timestamp": datetime.now().isoformat()
			}

			# 7. 更新缓存
			if self.cache:
				await self.cache.set(cache_key, overview, ttl=300)  # 缓存5分钟

			return overview

		except Exception as e:
			logger.error(f"获取账户总览失败: {str(e)}")
			raise

	async def process_daily_settlement (self, account_id: str, trade_date: date) -> Dict[str, Any]:
		"""
		处理账户日终结算

		Args:
			account_id: 账户ID
			trade_date: 交易日

		Returns:
			结算结果
		"""
		try:
			logger.info(f"开始日终结算: 账户ID={account_id}, 交易日={trade_date}")

			# 1. 检查账户状态
			account = await self.account_service.get_account(account_id)
			if not account:
				raise ValueError("账户不存在")

			if account.status != "active":
				raise ValueError(f"账户状态为{account.status}，无法结算")

			# 2. 结算当日交易
			await self._settle_daily_trades(account_id, trade_date)

			# 3. 更新持仓市值
			await self._update_position_market_value(account_id)

			# 4. 计算当日盈亏
			daily_pnl = await self.pnl_calculator.calculate_daily_pnl(account_id, trade_date)

			# 5. 记录结算信息
			await self.account_service.record_daily_settlement(
				account_id=account_id,
				trade_date=trade_date,
				total_asset=account.total_balance,
				cash=account.available_balance,
				market_value=account.market_value,
				daily_pnl=daily_pnl.total_pnl,
				daily_return=Decimal('0')  # 简化处理，实际需要计算
			)

			# 6. 清理临时数据
			await self._cleanup_temporary_data(account_id)

			# 7. 发布结算完成事件
			if self.message_producer:
				await self.message_producer.publish(
					"events.settlement",
					{
						"account_id": account_id,
						"trade_date": trade_date.isoformat(),
						"total_asset": float(account.total_balance),
						"daily_pnl": float(daily_pnl["total_pnl"]),
						"timestamp": datetime.now().isoformat()
					}
				)

			logger.info(f"日终结算完成: 账户ID={account_id}, 交易日={trade_date}")

			return {
				"success": True,
				"account_id": account_id,
				"trade_date": trade_date.isoformat(),
				"total_asset": float(account.total_balance),
				"daily_pnl": float(daily_pnl.total_pnl),
				"daily_return": 0.0,  # 简化处理，实际需要计算
				"message": "日终结算完成"
			}

		except Exception as e:
			logger.error(f"日终结算失败: {str(e)}")
			return {
				"success": False,
				"error": str(e)
			}

	async def transfer_between_accounts (
			self,
			from_account_id: str,
			to_account_id: str,
			amount: Decimal,
			reason: str
	) -> Dict[str, Any]:
		"""
		账户间资金划转

		Args:
			from_account_id: 转出账户ID
			to_account_id: 转入账户ID
			amount: 划转金额
			reason: 划转原因

		Returns:
			划转结果
		"""
		try:
			# 1. 验证两个账户
			from_account = await self.account_service.get_account(from_account_id)
			to_account = await self.account_service.get_account(to_account_id)

			if not from_account or not to_account:
				raise ValueError("账户不存在")

			if from_account.user_id != to_account.user_id:
				raise ValueError("只能在同一用户的不同账户间划转")

			# 2. 检查转出账户资金
			if from_account.available_balance < amount:
				raise ValueError(f"转出账户资金不足，可用: {from_account.available_balance}, 需要: {amount}")

			# 3. 执行划转（事务处理）
			async with self.db.begin():
				# 转出
				await self.cash_service.withdraw(
					from_account_id, amount, f"资金划转至账户{to_account.account_number}"
				)

				# 转入
				await self.cash_service.deposit(
					to_account_id, amount, f"收到来自账户{from_account.account_number}的划转"
				)

			logger.info(
				f"账户间资金划转成功: 从{from_account.account_number}到{to_account.account_number}, "
				f"金额={amount}, 原因={reason}"
			)

			return {
				"success": True,
				"from_account": from_account.account_number,
				"to_account": to_account.account_number,
				"amount": float(amount),
				"new_from_balance": float(from_account.available_balance - amount),
				"new_to_balance": float(to_account.available_balance + amount),
				"message": "资金划转成功"
			}

		except Exception as e:
			await self.db.rollback()
			logger.error(f"账户间资金划转失败: {str(e)}")
			return {
				"success": False,
				"error": str(e)
			}

	async def _settle_daily_trades (self, account_id: str, trade_date: date) -> Dict[str, Any]:
		"""结算当日交易"""
		# 获取当日所有成交
		start_of_day = datetime.combine(trade_date, datetime.min.time())
		end_of_day = datetime.combine(trade_date, datetime.max.time())
		daily_trades = await self.trade_repo.get_by_account_id(account_id, start_time=start_of_day, end_time=end_of_day)

		total_volume = 0
		total_amount = Decimal("0.00")
		total_fee = Decimal("0.00")

		for trade in daily_trades:
			total_volume += trade.volume
			total_amount += Decimal(str(trade.price)) * trade.volume
			total_fee += Decimal(str(trade.commission)) + Decimal(str(trade.tax))

			# 更新订单状态（如果有未完成订单）
			if trade.order_id:
				order = await self.order_repo.get_by_order_id(trade.order_id)
				if order and order.status in ["submitted", "partial_filled"]:
					await self.order_repo.batch_update_filled_info([{
						"order_id": order.order_id,
						"filled_volume": trade.volume,
						"filled_amount": trade.price * trade.volume,
						"avg_price": trade.price
					}])

		return {
			"trade_count": len(daily_trades),
			"total_volume": total_volume,
			"total_amount": float(total_amount),
			"total_fee": float(total_fee)
		}

	async def _update_position_market_value (self, account_id: str) -> None:
		"""更新持仓市值"""
		positions = await self.position_service.get_account_positions(account_id)

		for position in positions:
			if position.last_price and position.volume > 0:
				market_value = Decimal(str(position.last_price)) * position.volume
				await self.position_service.update_position_market_value(
					position.id, market_value
				)

	async def _cleanup_temporary_data (self, account_id: str) -> None:
		"""清理临时数据"""
		# 清理缓存
		if self.cache:
			await self.cache.delete(f"events:positions:{account_id}")
			await self.cache.delete(f"events:overview:{account_id}")

	async def _update_account_cache (self, account: AccountDomain) -> None:
		"""更新账户缓存"""
		if self.cache:
			cache_data = {
				"id": account.id,
				"account_number": account.account_number,
				"account_name": account.account_name,
				"status": account.status,
				"total_balance": float(account.total_balance),
				"available_balance": float(account.available_balance),
				"frozen_balance": float(account.frozen_balance),
				"updated_at": datetime.now().isoformat()
			}

			cache_key = f"events:{account.id}"
			await self.cache.set(cache_key, cache_data, ttl=3600)  # 缓存1小时

	async def _clear_account_cache (self, account_id: str) -> None:
		"""清理账户缓存"""
		if self.cache:
			await self.cache.delete(f"events:{account_id}")
			await self.cache.delete(f"events:overview:{account_id}")
			await self.cache.delete(f"events:positions:{account_id}")