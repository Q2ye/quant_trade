"""
持仓服务
处理持仓管理、查询、更新和计算
"""
import logging
from datetime import datetime, date
from decimal import Decimal
from typing import Optional, List, Dict, Any

from sqlalchemy.ext.asyncio import AsyncSession

from quant_server.modules.account.models import PositionDomain
from quant_server.shared.cache.base import CacheBase
from quant_server.shared.database.models.business_models import Trade, Order
from quant_server.shared.database.repositories.account.asset.account_repo import AccountRepository
from quant_server.shared.database.repositories.market.quote import StockDailyRepository
from quant_server.shared.database.repositories.trading.order.trade_repo import TradeRepository
from quant_server.shared.database.repositories.trading.position.position_repo import PositionRepository
from quant_server.shared.security.audit import AuditLogger

logger = logging.getLogger(__name__)


class PositionService:
	"""持仓服务 - 处理持仓相关业务逻辑"""

	def __init__ (self, db: AsyncSession, cache: Optional[CacheBase] = None):
		self.db = db
		self.cache = cache
		self.position_repo = PositionRepository(db)
		self.account_repo = AccountRepository(db)
		self.trade_repo = TradeRepository(db)
		self.stock_daily_repo = StockDailyRepository(db)
		self.audit_logger = AuditLogger(db)

	async def get_account_positions (
			self,
			account_id: str,
			ts_code: Optional[str] = None,
			with_volume_only: bool = False
	) -> List[PositionDomain]:
		"""
		获取账户持仓列表

		Args:
			account_id: 账户ID
			ts_code: 证券代码筛选
			with_volume_only: 是否只返回有持仓的记录

		Returns:
			持仓列表
		"""
		try:
			# 检查缓存
			cache_key = f"account:positions:{account_id}:{ts_code}:{with_volume_only}"
			if self.cache:
				cached_positions = await self.cache.get(cache_key)
				if cached_positions:
					return [PositionDomain(**p) for p in cached_positions]

			# 构建查询条件
			kwargs = {"account_id": account_id}
			if ts_code:
				kwargs["ts_code"] = ts_code

			# 查询持仓
			positions = await self.position_repo.get_many(**kwargs)
			# Post-filter for comparison operators (TODO: add comparison filter support to BaseRepository)
			if with_volume_only:
				positions = [p for p in positions if hasattr(p, "volume") and p.volume > 0]
			# Sort by last_update descending
			positions = sorted(
				positions,
				key=lambda x: getattr(x, "last_update", datetime.min),
				reverse=True,
			)

			# 转换为领域对象
			position_domains = []
			for position in positions:
				position_domain = PositionDomain(
					id=position.id,
					account_id=position.account_id,
					ts_code=position.ts_code,
					volume=position.volume,
					available_volume=position.available_volume,
					frozen_volume=position.frozen_volume,
					cost_price=Decimal(str(position.cost_price)) if position.cost_price else Decimal("0.00"),
					market_value=Decimal(str(position.market_value)) if position.market_value else Decimal("0.00"),
					last_price=Decimal(str(position.last_price)) if position.last_price else None,
					pnl=Decimal(str(position.pnl)) if position.pnl else Decimal("0.00"),
					pnl_rate=Decimal(str(position.pnl_rate)) if position.pnl_rate else Decimal("0.00"),
					last_update=position.last_update
				)
				position_domains.append(position_domain)

			# 更新缓存
			if self.cache:
				await self.cache.set(
					cache_key,
					[p.model_dump() for p in position_domains],
					ttl=60  # 缓存1分钟，因为持仓可能频繁变动
				)

			return position_domains

		except Exception as e:
			logger.error(f"获取账户持仓列表失败: {str(e)}")
			raise

	async def get_position_by_id (self, position_id: str) -> Optional[PositionDomain]:
		"""
		根据ID获取持仓

		Args:
			position_id: 持仓ID

		Returns:
			持仓领域对象，如果不存在则返回None
		"""
		try:
			position = await self.position_repo.get(position_id)
			if not position:
				return None

			return PositionDomain(
				id=position.id,
				account_id=position.account_id,
				ts_code=position.ts_code,
				volume=position.volume,
				available_volume=position.available_volume,
				frozen_volume=position.frozen_volume,
				cost_price=Decimal(str(position.cost_price)) if position.cost_price else Decimal("0.00"),
				market_value=Decimal(str(position.market_value)) if position.market_value else Decimal("0.00"),
				last_price=Decimal(str(position.last_price)) if position.last_price else None,
				pnl=Decimal(str(position.pnl)) if position.pnl else Decimal("0.00"),
				pnl_rate=Decimal(str(position.pnl_rate)) if position.pnl_rate else Decimal("0.00"),
				last_update=position.last_update
			)

		except Exception as e:
			logger.error(f"根据ID获取持仓失败: {str(e)}")
			raise

	async def get_position_by_security (
			self,
			account_id: str,
			ts_code: str
	) -> Optional[PositionDomain]:
		"""
		根据证券代码获取持仓

		Args:
			account_id: 账户ID
			ts_code: 证券代码

		Returns:
			持仓领域对象，如果不存在则返回None
		"""
		try:
			position = await self.position_repo.get_by(
				account_id=account_id,
				ts_code=ts_code
			)
			if not position:
				return None

			return PositionDomain(
				id=position.id,
				account_id=position.account_id,
				ts_code=position.ts_code,
				volume=position.volume,
				available_volume=position.available_volume,
				frozen_volume=position.frozen_volume,
				cost_price=Decimal(str(position.cost_price)) if position.cost_price else Decimal("0.00"),
				market_value=Decimal(str(position.market_value)) if position.market_value else Decimal("0.00"),
				last_price=Decimal(str(position.last_price)) if position.last_price else None,
				pnl=Decimal(str(position.pnl)) if position.pnl else Decimal("0.00"),
				pnl_rate=Decimal(str(position.pnl_rate)) if position.pnl_rate else Decimal("0.00"),
				last_update=position.last_update
			)

		except Exception as e:
			logger.error(f"根据证券代码获取持仓失败: {str(e)}")
			raise

	async def update_position (
			self,
			account_id: str,
			ts_code: str,
			volume_change: int,
			price: Decimal,
			direction: str,
			trade_id: Optional[str] = None
	) -> Dict[str, Any]:
		"""
		更新持仓（买入或卖出）

		Args:
			account_id: 账户ID
			ts_code: 证券代码
			volume_change: 数量变化（正数为买入，负数为卖出）
			price: 价格
			direction: 方向（buy/sell）
			trade_id: 交易ID（用于审计）

		Returns:
			更新结果
		"""
		try:
			# 验证输入
			if volume_change == 0:
				raise ValueError("数量变化不能为0")

			if price <= 0:
				raise ValueError("价格必须大于0")

			if direction not in ["buy", "sell"]:
				raise ValueError("方向必须是buy或sell")

			# 获取账户
			account = await self.account_repo.get(account_id)
			if not account:
				raise ValueError(f"账户不存在: {account_id}")

			if account.status != "active":
				raise ValueError(f"账户状态为{account.status}，无法交易")

			# 获取现有持仓
			position = await self.position_repo.get_by(
				account_id=account_id,
				ts_code=ts_code
			)

			if direction == "sell":
				# 卖出检查
				if not position or position.volume < volume_change:
					raise ValueError(
						f"持仓不足，当前持仓: {position.volume if position else 0}, 需要卖出: {volume_change}")

				if position.available_volume < volume_change:
					raise ValueError(f"可用持仓不足，当前可用: {position.available_volume}, 需要卖出: {volume_change}")

			# 计算新持仓信息
			if position:
				old_volume = position.volume
				old_cost_price = Decimal(str(position.cost_price)) if position.cost_price else Decimal("0.00")

				if direction == "buy":
					# 买入：计算新的平均成本
					if old_volume + volume_change > 0:
						new_cost_price = (
								                 (old_cost_price * old_volume) + (price * volume_change)
						                 ) / (old_volume + volume_change)
					else:
						new_cost_price = Decimal("0.00")

					new_volume = old_volume + volume_change
					new_available_volume = position.available_volume + volume_change

				else:  # sell
					# 卖出：成本价不变（先进先出或移动平均法）
					new_cost_price = old_cost_price
					new_volume = old_volume - volume_change
					new_available_volume = position.available_volume - volume_change

					if new_volume == 0:
						new_cost_price = Decimal("0.00")

				# 更新持仓
				update_data = {
					"volume": new_volume,
					"available_volume": new_available_volume,
					"cost_price": new_cost_price,
					"last_update": datetime.now()
				}

				# 如果持仓为0，重置成本价和盈亏
				if new_volume == 0:
					update_data.update({
						"cost_price": Decimal("0.00"),
						"market_value": Decimal("0.00"),
						"pnl": Decimal("0.00"),
						"pnl_rate": Decimal("0.00")
					})

				success = await self.position_repo.update(position.id, update_data)
				position_id = position.id

			else:
				# 新建持仓（只能是买入）
				if direction != "buy":
					raise ValueError("没有持仓记录，不能卖出")

				position_data = {
					"account_id": account_id,
					"ts_code": ts_code,
					"volume": volume_change,
					"available_volume": volume_change,
					"frozen_volume": 0,
					"cost_price": price,
					"market_value": Decimal("0.00"),
					"last_price": price,
					"pnl": Decimal("0.00"),
					"pnl_rate": Decimal("0.00"),
					"last_update": datetime.now()
				}

				new_position = await self.position_repo.create(position_data)
				success = new_position is not None
				position_id = new_position.id if new_position else None

			if success:
				# 记录审计日志
				if self.audit_logger:
					await self.audit_logger.log_simple(
						action="position_update",
						user_id=account.user_id,
						resource_type="position",
						resource_id=str(position_id),
						details={
							"account_id": account_id,
							"ts_code": ts_code,
							"direction": direction,
							"volume_change": volume_change,
							"price": float(price),
							"trade_id": trade_id,
							"old_volume": position.volume if position else 0,
							"new_volume": position.volume + volume_change if position else volume_change,
							"old_cost_price": float(position.cost_price) if position and position.cost_price else 0,
							"new_cost_price": float(position.cost_price) if position and position.cost_price else float(
								price)
						}
					)

				# 清理缓存
				if self.cache:
					await self.cache.delete(f"account:positions:{account_id}")
					await self.cache.delete(f"account:positions:{account_id}:{ts_code}")

				logger.info(
					f"持仓更新成功: 账户ID={account_id}, 证券={ts_code}, "
					f"方向={direction}, 数量={volume_change}, 价格={price}"
				)

				return {
					"success": True,
					"account_id": account_id,
					"ts_code": ts_code,
					"position_id": position_id,
					"direction": direction,
					"volume_change": volume_change,
					"price": float(price),
					"new_volume": position.volume + volume_change if position else volume_change,
					"new_cost_price": float(position.cost_price) if position and position.cost_price else float(price),
					"timestamp": datetime.now().isoformat()
				}
			else:
				raise ValueError("更新持仓失败")

		except Exception as e:
			logger.error(f"更新持仓失败: {str(e)}")
			raise

	async def freeze_position (
			self,
			account_id: str,
			ts_code: str,
			volume: int,
			reason: str,
			reference_id: Optional[str] = None
	) -> Dict[str, Any]:
		"""
		冻结持仓

		Args:
			account_id: 账户ID
			ts_code: 证券代码
			volume: 冻结数量
			reason: 冻结原因
			reference_id: 外部参考ID

		Returns:
			冻结结果
		"""
		try:
			# 验证输入
			if volume <= 0:
				raise ValueError("冻结数量必须大于0")

			# 获取持仓
			position = await self.position_repo.get_by(
				account_id=account_id,
				ts_code=ts_code
			)
			if not position:
				raise ValueError(f"持仓不存在: 账户={account_id}, 证券={ts_code}")

			if position.available_volume < volume:
				raise ValueError(f"可用持仓不足，当前可用: {position.available_volume}, 需要冻结: {volume}")

			# 计算新值
			new_available_volume = position.available_volume - volume
			new_frozen_volume = position.frozen_volume + volume

			# 更新持仓
			update_data = {
				"available_volume": new_available_volume,
				"frozen_volume": new_frozen_volume,
				"last_update": datetime.now()
			}

			success = await self.position_repo.update(position.id, update_data)

			if success:
				# 记录审计日志
				account = await self.account_repo.get(account_id)
				if account and self.audit_logger:
					await self.audit_logger.log_simple(
						action="position_freeze",
						user_id=account.user_id,
						resource_type="position",
						resource_id=str(position.id),
						details={
							"account_id": account_id,
							"ts_code": ts_code,
							"volume": volume,
							"reason": reason,
							"reference_id": reference_id,
							"old_available": position.available_volume,
							"new_available": new_available_volume,
							"old_frozen": position.frozen_volume,
							"new_frozen": new_frozen_volume
						}
					)

				# 清理缓存
				if self.cache:
					await self.cache.delete(f"account:positions:{account_id}")
					await self.cache.delete(f"account:positions:{account_id}:{ts_code}")

				logger.info(f"持仓冻结成功: 账户ID={account_id}, 证券={ts_code}, 数量={volume}, 原因={reason}")

				return {
					"success": True,
					"account_id": account_id,
					"ts_code": ts_code,
					"volume": volume,
					"old_available": position.available_volume,
					"new_available": new_available_volume,
					"old_frozen": position.frozen_volume,
					"new_frozen": new_frozen_volume,
					"reason": reason,
					"timestamp": datetime.now().isoformat()
				}
			else:
				raise ValueError("冻结持仓失败")

		except Exception as e:
			logger.error(f"冻结持仓失败: {str(e)}")
			raise

	async def unfreeze_position (
			self,
			account_id: str,
			ts_code: str,
			volume: int,
			reason: str,
			reference_id: Optional[str] = None
	) -> Dict[str, Any]:
		"""
		解冻持仓

		Args:
			account_id: 账户ID
			ts_code: 证券代码
			volume: 解冻数量
			reason: 解冻原因
			reference_id: 外部参考ID

		Returns:
			解冻结果
		"""
		try:
			# 验证输入
			if volume <= 0:
				raise ValueError("解冻数量必须大于0")

			# 获取持仓
			position = await self.position_repo.get_by(
				account_id=account_id,
				ts_code=ts_code
			)
			if not position:
				raise ValueError(f"持仓不存在: 账户={account_id}, 证券={ts_code}")

			if position.frozen_volume < volume:
				raise ValueError(f"冻结持仓不足，当前冻结: {position.frozen_volume}, 需要解冻: {volume}")

			# 计算新值
			new_available_volume = position.available_volume + volume
			new_frozen_volume = position.frozen_volume - volume

			# 更新持仓
			update_data = {
				"available_volume": new_available_volume,
				"frozen_volume": new_frozen_volume,
				"last_update": datetime.now()
			}

			success = await self.position_repo.update(position.id, update_data)

			if success:
				# 记录审计日志
				account = await self.account_repo.get(account_id)
				if account and self.audit_logger:
					await self.audit_logger.log_simple(
						action="position_unfreeze",
						user_id=account.user_id,
						resource_type="position",
						resource_id=str(position.id),
						details={
							"account_id": account_id,
							"ts_code": ts_code,
							"volume": volume,
							"reason": reason,
							"reference_id": reference_id,
							"old_available": position.available_volume,
							"new_available": new_available_volume,
							"old_frozen": position.frozen_volume,
							"new_frozen": new_frozen_volume
						}
					)

				# 清理缓存
				if self.cache:
					await self.cache.delete(f"account:positions:{account_id}")
					await self.cache.delete(f"account:positions:{account_id}:{ts_code}")

				logger.info(f"持仓解冻成功: 账户ID={account_id}, 证券={ts_code}, 数量={volume}, 原因={reason}")

				return {
					"success": True,
					"account_id": account_id,
					"ts_code": ts_code,
					"volume": volume,
					"old_available": position.available_volume,
					"new_available": new_available_volume,
					"old_frozen": position.frozen_volume,
					"new_frozen": new_frozen_volume,
					"reason": reason,
					"timestamp": datetime.now().isoformat()
				}
			else:
				raise ValueError("解冻持仓失败")

		except Exception as e:
			logger.error(f"解冻持仓失败: {str(e)}")
			raise

	async def update_position_market_value (
			self,
			position_id: str,
			market_value: Decimal,
			last_price: Optional[Decimal] = None
	) -> bool:
		"""
		更新持仓市值

		Args:
			position_id: 持仓ID
			market_value: 市值
			last_price: 最新价格

		Returns:
			更新是否成功
		"""
		try:
			# 获取持仓
			position = await self.position_repo.get(position_id)
			if not position:
				raise ValueError(f"持仓不存在: {position_id}")

			# 计算盈亏
			cost_value = Decimal(str(position.cost_price)) * position.volume if position.cost_price else Decimal("0.00")

			if cost_value > 0:
				pnl = market_value - cost_value
				pnl_rate = (pnl / cost_value) * 100
			else:
				pnl = Decimal("0.00")
				pnl_rate = Decimal("0.00")

			# 更新持仓
			update_data = {
				"market_value": market_value,
				"pnl": pnl,
				"pnl_rate": pnl_rate,
				"last_update": datetime.now()
			}

			if last_price:
				update_data["last_price"] = last_price

			success = await self.position_repo.update(position_id, update_data)

			if success:
				# 清理缓存
				if self.cache:
					await self.cache.delete(f"account:positions:{position.account_id}")
					await self.cache.delete(f"account:positions:{position.account_id}:{position.ts_code}")

				logger.info(f"更新持仓市值成功: 持仓ID={position_id}, 市值={market_value}, 盈亏={pnl}")

				return True
			else:
				raise ValueError("更新持仓市值失败")

		except Exception as e:
			logger.error(f"更新持仓市值失败: {str(e)}")
			raise

	async def calculate_position_performance (
			self,
			account_id: str,
			ts_code: Optional[str] = None
	) -> Dict[str, Any]:
		"""
		计算持仓绩效

		Args:
			account_id: 账户ID
			ts_code: 证券代码（可选，不指定则计算所有持仓）

		Returns:
			持仓绩效
		"""
		try:
			# 获取持仓
			positions = await self.get_account_positions(account_id, ts_code)

			if not positions:
				return {
					"account_id": account_id,
					"ts_code": ts_code,
					"message": "没有持仓数据",
					"timestamp": datetime.now().isoformat()
				}

			# 计算汇总指标
			total_market_value = Decimal("0.00")
			total_cost_value = Decimal("0.00")
			total_pnl = Decimal("0.00")
			weighted_pnl_rate = Decimal("0.00")
			position_count = 0
			positions_with_volume = 0

			position_details = []

			for position in positions:
				position_count += 1

				if position.volume > 0:
					positions_with_volume += 1

					cost_value = position.cost_price * position.volume
					market_value = position.market_value

					total_market_value += market_value
					total_cost_value += cost_value
					total_pnl += position.pnl

					# 加权盈亏率
					if market_value > 0:
						weight = market_value / (total_market_value if total_market_value > 0 else market_value)
						weighted_pnl_rate += position.pnl_rate * weight

					position_details.append({
						"ts_code": position.ts_code,
						"volume": position.volume,
						"cost_price": float(position.cost_price),
						"market_value": float(market_value),
						"last_price": float(position.last_price) if position.last_price else None,
						"pnl": float(position.pnl),
						"pnl_rate": float(position.pnl_rate),
						"weight": float(market_value / total_market_value) if total_market_value > 0 else 0
					})

			# 计算整体指标
			if total_cost_value > 0:
				overall_pnl_rate = (total_pnl / total_cost_value) * 100
			else:
				overall_pnl_rate = Decimal("0.00")

			return {
				"account_id": account_id,
				"ts_code": ts_code,
				"summary": {
					"total_positions": position_count,
					"positions_with_volume": positions_with_volume,
					"total_market_value": float(total_market_value),
					"total_cost_value": float(total_cost_value),
					"total_pnl": float(total_pnl),
					"overall_pnl_rate": float(overall_pnl_rate),
					"weighted_pnl_rate": float(weighted_pnl_rate)
				},
				"position_details": position_details,
				"calculation_date": datetime.now().isoformat(),
				"timestamp": datetime.now().isoformat()
			}

		except Exception as e:
			logger.error(f"计算持仓绩效失败: {str(e)}")
			raise

	async def get_position_history (
			self,
			account_id: str,
			ts_code: str,
			start_date: Optional[date] = None,
			end_date: Optional[date] = None,
			skip: int = 0,
			limit: int = 100
	) -> List[Dict[str, Any]]:
		"""
		获取持仓历史

		Args:
			account_id: 账户ID
			ts_code: 证券代码
			start_date: 开始日期
			end_date: 结束日期
			skip: 跳过记录数
			limit: 返回记录数

		Returns:
			持仓历史记录
		"""
		try:
			# 构建查询条件
			conditions = [
				Trade.ts_code == ts_code
			]

			if start_date:
				start_datetime = datetime.combine(start_date, datetime.min.time())
				conditions.append(Trade.trade_time >= start_datetime)

			if end_date:
				end_datetime = datetime.combine(end_date, datetime.max.time())
				conditions.append(Trade.trade_time <= end_datetime)

			# 查询交易记录
			if account_id:
				# 通过Order关联查询账户ID
				from sqlalchemy import select, join
				query = select(Trade).join(Order).where(
					Trade.ts_code == ts_code,
					Order.account_id == account_id
				)
				if start_date:
					start_datetime = datetime.combine(start_date, datetime.min.time())
					query = query.where(Trade.trade_time >= start_datetime)
				if end_date:
					end_datetime = datetime.combine(end_date, datetime.max.time())
					query = query.where(Trade.trade_time <= end_datetime)
				trades = await self.trade_repo.execute_query(query)
			else:
				trades = await self.trade_repo.get_many(
					skip=skip,
					limit=limit,
					**{c.left.name: c.right.value for c in conditions}
				)

			# 计算持仓历史
			position_history = []
			current_volume = 0
			current_cost = Decimal("0.00")

			for trade in trades:
				trade_volume = trade.volume
				trade_price = Decimal(str(trade.price))
				trade_amount = trade_price * trade_volume

				# 判断买卖方向（这里简化，实际需要根据订单信息）
				# 假设所有交易都是买入，实际实现中需要根据具体业务逻辑调整
				direction = "buy"

				if direction == "buy":
					if current_volume + trade_volume > 0:
						current_cost = (
								               (current_cost * current_volume) + trade_amount
						               ) / (current_volume + trade_volume)

					current_volume += trade_volume
				else:  # sell
					current_volume -= trade_volume

					if current_volume == 0:
						current_cost = Decimal("0.00")

				position_history.append({
					"trade_id": trade.trade_id,
					"trade_time": trade.trade_time.isoformat(),
					"direction": direction,
					"price": float(trade_price),
					"volume": trade_volume,
					"amount": float(trade_amount),
					"cumulative_volume": current_volume,
					"average_cost": float(current_cost),
					"commission": float(trade.commission),
					"tax": float(trade.tax)
				})

			return position_history

		except Exception as e:
			logger.error(f"获取持仓历史失败: {str(e)}")
			raise
