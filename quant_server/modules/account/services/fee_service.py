"""
费用服务
处理交易费用计算、记录和统计
"""
import logging
from typing import Optional, Dict, Any, List, Tuple
from decimal import Decimal
from datetime import datetime, date
from sqlalchemy.ext.asyncio import AsyncSession

from shared.database.repositories.trade_repo import TradeRepository
from shared.database.repositories.fee_repo import FeeRepository
from shared.database.repositories.account_repo import AccountRepository
from shared.database.models.business_models import Trade, FeeRecord
from modules.account.models import AccountDomain
from shared.cache.base import CacheBase
from shared.utils.validation import validate_amount

logger = logging.getLogger(__name__)


class FeeService:
	"""费用服务 - 处理费用相关业务逻辑"""

	def __init__ (self, db: AsyncSession, cache: Optional[CacheBase] = None):
		self.db = db
		self.cache = cache
		self.trade_repo = TradeRepository(db)
		self.fee_repo = FeeRepository(db)
		self.account_repo = AccountRepository(db)

	async def calculate_trading_fees (
			self,
			account_id: int,
			ts_code: str,
			price: Decimal,
			volume: int,
			direction: str,
			market: str = "SH"
	) -> Dict[str, Any]:
		"""
		计算交易费用

		Args:
			account_id: 账户ID
			ts_code: 证券代码
			price: 价格
			volume: 数量
			direction: 方向（buy/sell）
			market: 市场（SH/SZ）

		Returns:
			费用计算结果
		"""
		try:
			# 验证输入
			validate_amount(price, min_value=Decimal("0.01"))
			if volume <= 0:
				raise ValueError("交易数量必须大于0")

			if direction not in ["buy", "sell"]:
				raise ValueError("交易方向必须是buy或sell")

			# 计算交易金额
			trade_amount = price * volume

			# 计算佣金（这里使用简化规则）
			# 实际实现中需要根据券商费率计算
			commission_rate = Decimal("0.00025")  # 0.025%
			commission = trade_amount * commission_rate

			# 最低佣金5元
			min_commission = Decimal("5.00")
			if commission < min_commission:
				commission = min_commission

			# 计算印花税（仅卖出时收取）
			stamp_tax = Decimal("0.00")
			if direction == "sell":
				stamp_tax_rate = Decimal("0.001")  # 0.1%
				stamp_tax = trade_amount * stamp_tax_rate

			# 计算过户费（仅沪市，双向收取）
			transfer_fee = Decimal("0.00")
			if market == "SH":
				transfer_fee_rate = Decimal("0.00002")  # 0.002%
				transfer_fee = trade_amount * transfer_fee_rate

			# 计算监管费（简化处理）
			regulation_fee = trade_amount * Decimal("0.00002")  # 0.002%

			# 计算总费用
			total_fee = commission + stamp_tax + transfer_fee + regulation_fee

			return {
				"account_id": account_id,
				"ts_code": ts_code,
				"direction": direction,
				"price": float(price),
				"volume": volume,
				"trade_amount": float(trade_amount),
				"fees": {
					"commission": float(commission),
					"stamp_tax": float(stamp_tax),
					"transfer_fee": float(transfer_fee),
					"regulation_fee": float(regulation_fee),
					"total_fee": float(total_fee)
				},
				"fee_rates": {
					"commission_rate": float(commission_rate),
					"stamp_tax_rate": float(stamp_tax_rate) if direction == "sell" else 0,
					"transfer_fee_rate": float(transfer_fee_rate) if market == "SH" else 0,
					"regulation_fee_rate": float(Decimal("0.00002"))
				},
				"market": market,
				"calculated_at": datetime.now().isoformat()
			}

		except Exception as e:
			logger.error(f"计算交易费用失败: {str(e)}")
			raise

	async def record_trade_fees (
			self,
			trade_id: str,
			account_id: int,
			ts_code: str,
			commission: Decimal,
			stamp_tax: Decimal,
			transfer_fee: Decimal,
			regulation_fee: Decimal,
			total_fee: Decimal,
			fee_details: Optional[Dict[str, Any]] = None
	) -> bool:
		"""
		记录交易费用

		Args:
			trade_id: 交易ID
			account_id: 账户ID
			ts_code: 证券代码
			commission: 佣金
			stamp_tax: 印花税
			transfer_fee: 过户费
			regulation_fee: 监管费
			total_fee: 总费用
			fee_details: 费用详情

		Returns:
			记录是否成功
		"""
		try:
			# 验证费用
			for fee_name, fee_amount in [
				("commission", commission),
				("stamp_tax", stamp_tax),
				("transfer_fee", transfer_fee),
				("regulation_fee", regulation_fee),
				("total_fee", total_fee)
			]:
				if fee_amount < 0:
					raise ValueError(f"{fee_name}不能为负数")

			# 检查交易是否存在
			trade = await self.trade_repo.get_by_id(trade_id)
			if not trade:
				raise ValueError(f"交易不存在: {trade_id}")

			# 创建费用记录
			fee_data = {
				"trade_id": trade_id,
				"account_id": account_id,
				"ts_code": ts_code,
				"commission": commission,
				"stamp_tax": stamp_tax,
				"transfer_fee": transfer_fee,
				"regulation_fee": regulation_fee,
				"total_fee": total_fee,
				"fee_details": fee_details or {},
				"status": "recorded"
			}

			success = await self.fee_repo.create(fee_data)

			if success:
				logger.info(f"记录交易费用成功: 交易ID={trade_id}, 总费用={total_fee}")

				# 清理缓存
				if self.cache:
					await self.cache.delete(f"account:fees:{account_id}")
					await self.cache.delete(f"trade:fees:{trade_id}")

				return True
			else:
				raise ValueError("创建费用记录失败")

		except Exception as e:
			logger.error(f"记录交易费用失败: {str(e)}")
			raise

	async def get_trade_fees (self, trade_id: str) -> Optional[Dict[str, Any]]:
		"""
		获取交易费用

		Args:
			trade_id: 交易ID

		Returns:
			交易费用详情，如果不存在则返回None
		"""
		try:
			# 检查缓存
			cache_key = f"trade:fees:{trade_id}"
			if self.cache:
				cached_fees = await self.cache.get(cache_key)
				if cached_fees:
					return cached_fees

			# 查询费用记录
			fee_record = await self.fee_repo.get_by_trade_id(trade_id)
			if not fee_record:
				return None

			# 获取交易信息
			trade = await self.trade_repo.get_by_id(trade_id)

			fee_details = {
				"trade_id": trade_id,
				"account_id": fee_record.account_id,
				"ts_code": fee_record.ts_code,
				"trade_time": trade.trade_time.isoformat() if trade else None,
				"price": float(trade.price) if trade else None,
				"volume": trade.volume if trade else None,
				"fees": {
					"commission": float(fee_record.commission),
					"stamp_tax": float(fee_record.stamp_tax),
					"transfer_fee": float(fee_record.transfer_fee),
					"regulation_fee": float(fee_record.regulation_fee),
					"total_fee": float(fee_record.total_fee)
				},
				"fee_details": fee_record.fee_details or {},
				"status": fee_record.status,
				"recorded_at": fee_record.created_at.isoformat()
			}

			# 更新缓存
			if self.cache:
				await self.cache.set(cache_key, fee_details, expire=3600)  # 缓存1小时

			return fee_details

		except Exception as e:
			logger.error(f"获取交易费用失败: {str(e)}")
			raise

	async def get_account_fees (
			self,
			account_id: int,
			start_date: Optional[date] = None,
			end_date: Optional[date] = None,
			fee_type: Optional[str] = None,
			skip: int = 0,
			limit: int = 100
	) -> Dict[str, Any]:
		"""
		获取账户费用统计

		Args:
			account_id: 账户ID
			start_date: 开始日期
			end_date: 结束日期
			fee_type: 费用类型筛选
			skip: 跳过记录数
			limit: 返回记录数

		Returns:
			账户费用统计
		"""
		try:
			# 检查缓存
			cache_key = f"account:fees:{account_id}:{start_date}:{end_date}:{fee_type}:{skip}:{limit}"
			if self.cache:
				cached_stats = await self.cache.get(cache_key)
				if cached_stats:
					return cached_stats

			# 构建查询条件
			conditions = [FeeRecord.account_id == account_id]

			if start_date:
				start_datetime = datetime.combine(start_date, datetime.min.time())
				conditions.append(FeeRecord.created_at >= start_datetime)

			if end_date:
				end_datetime = datetime.combine(end_date, datetime.max.time())
				conditions.append(FeeRecord.created_at <= end_datetime)

			# 查询费用记录
			fee_records = await self.fee_repo.get_by_conditions(
				conditions=conditions,
				order_by=[FeeRecord.created_at.desc()],
				skip=skip,
				limit=limit
			)

			# 计算费用统计
			total_commission = Decimal("0.00")
			total_stamp_tax = Decimal("0.00")
			total_transfer_fee = Decimal("0.00")
			total_regulation_fee = Decimal("0.00")
			total_fees = Decimal("0.00")

			fee_details = []

			for record in fee_records:
				total_commission += Decimal(str(record.commission))
				total_stamp_tax += Decimal(str(record.stamp_tax))
				total_transfer_fee += Decimal(str(record.transfer_fee))
				total_regulation_fee += Decimal(str(record.regulation_fee))
				total_fees += Decimal(str(record.total_fee))

				# 获取交易信息
				trade = await self.trade_repo.get_by_id(record.trade_id)

				fee_details.append({
					"trade_id": record.trade_id,
					"ts_code": record.ts_code,
					"trade_time": trade.trade_time.isoformat() if trade else None,
					"price": float(trade.price) if trade else None,
					"volume": trade.volume if trade else None,
					"direction": "buy" if trade and trade.volume > 0 else "sell",
					"fees": {
						"commission": float(record.commission),
						"stamp_tax": float(record.stamp_tax),
						"transfer_fee": float(record.transfer_fee),
						"regulation_fee": float(record.regulation_fee),
						"total_fee": float(record.total_fee)
					},
					"recorded_at": record.created_at.isoformat()
				})

			# 按费用类型筛选
			if fee_type:
				if fee_type == "commission":
					fee_details = [f for f in fee_details if f["fees"]["commission"] > 0]
				elif fee_type == "stamp_tax":
					fee_details = [f for f in fee_details if f["fees"]["stamp_tax"] > 0]
				elif fee_type == "transfer_fee":
					fee_details = [f for f in fee_details if f["fees"]["transfer_fee"] > 0]
				elif fee_type == "regulation_fee":
					fee_details = [f for f in fee_details if f["fees"]["regulation_fee"] > 0]

			# 按日期分组统计
			daily_stats = await self._calculate_daily_fee_stats(
				account_id, start_date, end_date
			)

			# 按证券代码分组统计
			security_stats = await self._calculate_security_fee_stats(
				account_id, start_date, end_date
			)

			result = {
				"account_id": account_id,
				"period": {
					"start_date": start_date.isoformat() if start_date else None,
					"end_date": end_date.isoformat() if end_date else None
				},
				"summary": {
					"total_commission": float(total_commission),
					"total_stamp_tax": float(total_stamp_tax),
					"total_transfer_fee": float(total_transfer_fee),
					"total_regulation_fee": float(total_regulation_fee),
					"total_fees": float(total_fees),
					"record_count": len(fee_records)
				},
				"daily_stats": daily_stats,
				"security_stats": security_stats,
				"fee_details": fee_details,
				"timestamp": datetime.now().isoformat()
			}

			# 更新缓存
			if self.cache:
				await self.cache.set(cache_key, result, expire=300)  # 缓存5分钟

			return result

		except Exception as e:
			logger.error(f"获取账户费用统计失败: {str(e)}")
			raise

	async def _calculate_daily_fee_stats (
			self,
			account_id: int,
			start_date: Optional[date],
			end_date: Optional[date]
	) -> List[Dict[str, Any]]:
		"""计算每日费用统计"""
		try:
			# 这里简化处理，实际实现需要按日期分组查询
			# 获取日期范围内的所有费用记录
			conditions = [FeeRecord.account_id == account_id]

			if start_date:
				start_datetime = datetime.combine(start_date, datetime.min.time())
				conditions.append(FeeRecord.created_at >= start_datetime)

			if end_date:
				end_datetime = datetime.combine(end_date, datetime.max.time())
				conditions.append(FeeRecord.created_at <= end_datetime)

			fee_records = await self.fee_repo.get_by_conditions(conditions)

			# 按日期分组
			daily_stats_map = {}

			for record in fee_records:
				record_date = record.created_at.date()
				date_key = record_date.isoformat()

				if date_key not in daily_stats_map:
					daily_stats_map[date_key] = {
						"date": record_date.isoformat(),
						"commission": Decimal("0.00"),
						"stamp_tax": Decimal("0.00"),
						"transfer_fee": Decimal("0.00"),
						"regulation_fee": Decimal("0.00"),
						"total_fee": Decimal("0.00"),
						"trade_count": 0
					}

				stats = daily_stats_map[date_key]
				stats["commission"] += Decimal(str(record.commission))
				stats["stamp_tax"] += Decimal(str(record.stamp_tax))
				stats["transfer_fee"] += Decimal(str(record.transfer_fee))
				stats["regulation_fee"] += Decimal(str(record.regulation_fee))
				stats["total_fee"] += Decimal(str(record.total_fee))
				stats["trade_count"] += 1

			# 转换为列表并排序
			daily_stats = list(daily_stats_map.values())
			daily_stats.sort(key=lambda x: x["date"])

			return daily_stats

		except Exception as e:
			logger.error(f"计算每日费用统计失败: {str(e)}")
			return []

	async def _calculate_security_fee_stats (
			self,
			account_id: int,
			start_date: Optional[date],
			end_date: Optional[date]
	) -> List[Dict[str, Any]]:
		"""按证券代码计算费用统计"""
		try:
			# 构建查询条件
			conditions = [FeeRecord.account_id == account_id]

			if start_date:
				start_datetime = datetime.combine(start_date, datetime.min.time())
				conditions.append(FeeRecord.created_at >= start_datetime)

			if end_date:
				end_datetime = datetime.combine(end_date, datetime.max.time())
				conditions.append(FeeRecord.created_at <= end_datetime)

			fee_records = await self.fee_repo.get_by_conditions(conditions)

			# 按证券代码分组
			security_stats_map = {}

			for record in fee_records:
				ts_code = record.ts_code

				if ts_code not in security_stats_map:
					security_stats_map[ts_code] = {
						"ts_code": ts_code,
						"commission": Decimal("0.00"),
						"stamp_tax": Decimal("0.00"),
						"transfer_fee": Decimal("0.00"),
						"regulation_fee": Decimal("0.00"),
						"total_fee": Decimal("0.00"),
						"trade_count": 0,
						"buy_count": 0,
						"sell_count": 0
					}

				stats = security_stats_map[ts_code]
				stats["commission"] += Decimal(str(record.commission))
				stats["stamp_tax"] += Decimal(str(record.stamp_tax))
				stats["transfer_fee"] += Decimal(str(record.transfer_fee))
				stats["regulation_fee"] += Decimal(str(record.regulation_fee))
				stats["total_fee"] += Decimal(str(record.total_fee))
				stats["trade_count"] += 1

				# 判断买卖方向（通过印花税判断）
				if Decimal(str(record.stamp_tax)) > 0:
					stats["sell_count"] += 1
				else:
					stats["buy_count"] += 1

			# 转换为列表并排序
			security_stats = list(security_stats_map.values())
			security_stats.sort(key=lambda x: x["total_fee"], reverse=True)

			# 转换Decimal为float
			for stats in security_stats:
				stats["commission"] = float(stats["commission"])
				stats["stamp_tax"] = float(stats["stamp_tax"])
				stats["transfer_fee"] = float(stats["transfer_fee"])
				stats["regulation_fee"] = float(stats["regulation_fee"])
				stats["total_fee"] = float(stats["total_fee"])

			return security_stats

		except Exception as e:
			logger.error(f"按证券计算费用统计失败: {str(e)}")
			return []

	async def get_fee_summary (self, account_id: int, period: str = "month") -> Dict[str, Any]:
		"""
		获取费用汇总

		Args:
			account_id: 账户ID
			period: 周期（day, week, month, quarter, year）

		Returns:
			费用汇总
		"""
		try:
			# 确定日期范围
			end_date = date.today()

			if period == "day":
				start_date = end_date
			elif period == "week":
				start_date = end_date - datetime.timedelta(days=7)
			elif period == "month":
				start_date = end_date - datetime.timedelta(days=30)
			elif period == "quarter":
				start_date = end_date - datetime.timedelta(days=90)
			elif period == "year":
				start_date = end_date - datetime.timedelta(days=365)
			else:
				start_date = end_date - datetime.timedelta(days=30)

			# 获取费用统计
			fee_stats = await self.get_account_fees(
				account_id=account_id,
				start_date=start_date,
				end_date=end_date
			)

			# 计算费用占比
			summary = fee_stats["summary"]
			total_fees = summary["total_fees"]

			if total_fees > 0:
				commission_percentage = (summary["total_commission"] / total_fees) * 100
				stamp_tax_percentage = (summary["total_stamp_tax"] / total_fees) * 100
				transfer_fee_percentage = (summary["total_transfer_fee"] / total_fees) * 100
				regulation_fee_percentage = (summary["total_regulation_fee"] / total_fees) * 100
			else:
				commission_percentage = 0
				stamp_tax_percentage = 0
				transfer_fee_percentage = 0
				regulation_fee_percentage = 0

			return {
				"account_id": account_id,
				"period": period,
				"start_date": start_date.isoformat(),
				"end_date": end_date.isoformat(),
				"fee_summary": {
					"total_fees": total_fees,
					"average_daily_fee": total_fees / max(1, (end_date - start_date).days),
					"fee_breakdown": {
						"commission": {
							"amount": summary["total_commission"],
							"percentage": commission_percentage
						},
						"stamp_tax": {
							"amount": summary["total_stamp_tax"],
							"percentage": stamp_tax_percentage
						},
						"transfer_fee": {
							"amount": summary["total_transfer_fee"],
							"percentage": transfer_fee_percentage
						},
						"regulation_fee": {
							"amount": summary["total_regulation_fee"],
							"percentage": regulation_fee_percentage
						}
					}
				},
				"trade_statistics": {
					"total_trades": summary["record_count"],
					"trades_per_day": summary["record_count"] / max(1, (end_date - start_date).days),
					"average_fee_per_trade": total_fees / summary["record_count"] if summary["record_count"] > 0 else 0
				},
				"timestamp": datetime.now().isoformat()
			}

		except Exception as e:
			logger.error(f"获取费用汇总失败: {str(e)}")
			raise

	async def adjust_fee_record (
			self,
			fee_record_id: int,
			adjustment_amount: Decimal,
			reason: str,
			adjusted_by: str
	) -> bool:
		"""
		调整费用记录

		Args:
			fee_record_id: 费用记录ID
			adjustment_amount: 调整金额
			reason: 调整原因
			adjusted_by: 调整人

		Returns:
			调整是否成功
		"""
		try:
			# 获取费用记录
			fee_record = await self.fee_repo.get_by_id(fee_record_id)
			if not fee_record:
				raise ValueError(f"费用记录不存在: {fee_record_id}")

			# 计算新的总费用
			new_total_fee = Decimal(str(fee_record.total_fee)) + adjustment_amount

			if new_total_fee < 0:
				raise ValueError("调整后费用不能为负数")

			# 更新费用记录
			update_data = {
				"total_fee": new_total_fee,
				"adjustment_history": {
					"adjustment_amount": float(adjustment_amount),
					"reason": reason,
					"adjusted_by": adjusted_by,
					"adjusted_at": datetime.now().isoformat()
				}
			}

			success = await self.fee_repo.update(fee_record_id, update_data)

			if success:
				logger.info(f"调整费用记录成功: 记录ID={fee_record_id}, 调整金额={adjustment_amount}, 原因={reason}")

				# 清理缓存
				if self.cache:
					await self.cache.delete(f"trade:fees:{fee_record.trade_id}")
					await self.cache.delete(f"account:fees:{fee_record.account_id}")

				return True
			else:
				raise ValueError("更新费用记录失败")

		except Exception as e:
			logger.error(f"调整费用记录失败: {str(e)}")
			raise