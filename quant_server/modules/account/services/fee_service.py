"""
费用服务
处理交易费用计算、记录和统计
"""
import logging
from datetime import datetime, date, timedelta
from decimal import Decimal
from typing import Optional, Dict, Any, List

from sqlalchemy.ext.asyncio import AsyncSession

from quant_server.shared.cache.base import CacheBase
from quant_server.shared.database.models.business_models import TradeFee
from quant_server.shared.database.repositories.account.asset.account_repo import AccountRepository
from quant_server.shared.database.repositories.trading.order.trade_repo import TradeRepository
from quant_server.shared.database.repositories.trading.support.trade_fee_repo import TradeFeeRepository
from quant_server.shared.utils.validation import validate_amount

logger = logging.getLogger(__name__)


def _calculate_fee_amounts(fee_records: List[TradeFee]) -> Dict[str, Decimal]:
	"""计算费用金额"""
	fees = {
		"commission": Decimal("0.00"),
		"stamp_tax": Decimal("0.00"),
		"transfer_fee": Decimal("0.00"),
		"regulation_fee": Decimal("0.00"),
		"total_fee": Decimal("0.00")
	}

	for fee_record in fee_records:
		if fee_record.fee_type == "commission":
			fees["commission"] += Decimal(str(fee_record.fee_amount))
		elif fee_record.fee_type == "tax":
			fees["stamp_tax"] += Decimal(str(fee_record.fee_amount))
		elif fee_record.fee_type == "transfer":
			fees["transfer_fee"] += Decimal(str(fee_record.fee_amount))
		elif fee_record.fee_type == "regulation":
			fees["regulation_fee"] += Decimal(str(fee_record.fee_amount))
		fees["total_fee"] += Decimal(str(fee_record.fee_amount))

	return fees


class FeeService:
	"""费用服务 - 处理费用相关业务逻辑"""

	def __init__ (self, db: AsyncSession, cache: Optional[CacheBase] = None):
		self.db = db
		self.cache = cache
		self.trade_repo = TradeRepository(db)
		self.fee_repo = TradeFeeRepository(db)
		self.account_repo = AccountRepository(db)

	@staticmethod
	async def calculate_trading_fees (
			account_id: str,
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
			stamp_tax_rate = Decimal("0.00")
			if direction == "sell":
				stamp_tax_rate = Decimal("0.001")  # 0.1%
				stamp_tax = trade_amount * stamp_tax_rate

			# 计算过户费（仅沪市，双向收取）
			transfer_fee = Decimal("0.00")
			transfer_fee_rate = Decimal("0.00")
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
			commission: Decimal,
			stamp_tax: Decimal,
			transfer_fee: Decimal,
			regulation_fee: Decimal
	) -> bool:
		"""
		记录交易费用

		Args:
			trade_id: 交易ID
			commission: 佣金
			stamp_tax: 印花税
			transfer_fee: 过户费
			regulation_fee: 监管费

		Returns:
			记录是否成功
		"""
		try:
			# 验证费用
			for fee_name, fee_amount in [
				("commission", commission),
				("stamp_tax", stamp_tax),
				("transfer_fee", transfer_fee),
				("regulation_fee", regulation_fee)
			]:
				if fee_amount < 0:
					raise ValueError(f"{fee_name}不能为负数")

			# 检查交易是否存在
			trade = await self.trade_repo.get_by_trade_id(trade_id)
			if not trade:
				raise ValueError(f"交易不存在: {trade_id}")

			# 批量创建费用记录
			fees_data = []

			if commission > 0:
				fees_data.append({
					"trade_id": trade_id,
					"fee_type": "commission",
					"fee_amount": commission,
					"description": "佣金"
				})

			if stamp_tax > 0:
				fees_data.append({
					"trade_id": trade_id,
					"fee_type": "tax",
					"fee_amount": stamp_tax,
					"description": "印花税"
				})

			if transfer_fee > 0:
				fees_data.append({
					"trade_id": trade_id,
					"fee_type": "transfer",
					"fee_amount": transfer_fee,
					"description": "过户费"
				})

			if regulation_fee > 0:
				fees_data.append({
					"trade_id": trade_id,
					"fee_type": "regulation",
					"fee_amount": regulation_fee,
					"description": "监管费"
				})

			if fees_data:
				await self.fee_repo.batch_create_fees(fees_data)
				logger.info(f"记录交易费用成功: 交易ID={trade_id}")
			else:
				logger.info(f"无费用需要记录: 交易ID={trade_id}")

			return True

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
			fee_records = await self.fee_repo.get_fees_by_trade_id(trade_id)
			if not fee_records:
				return None

			# 获取交易信息
			trade = await self.trade_repo.get_by_trade_id(trade_id)

			# 计算各项费用
			fees = {
				"commission": 0.0,
				"stamp_tax": 0.0,
				"transfer_fee": 0.0,
				"regulation_fee": 0.0,
				"total_fee": 0.0
			}

			for fee_record in fee_records:
				if fee_record.fee_type == "commission":
					fees["commission"] = float(fee_record.fee_amount)
				elif fee_record.fee_type == "tax":
					fees["stamp_tax"] = float(fee_record.fee_amount)
				elif fee_record.fee_type == "transfer":
					fees["transfer_fee"] = float(fee_record.fee_amount)
				elif fee_record.fee_type == "regulation":
					fees["regulation_fee"] = float(fee_record.fee_amount)
				fees["total_fee"] += float(fee_record.fee_amount)

			fee_details = {
				"trade_id": trade_id,
				"trade_time": trade.trade_time.isoformat() if trade else None,
				"price": float(trade.price) if trade else None,
				"volume": trade.volume if trade else None,
				"fees": fees,
				"recorded_at": fee_records[0].created_at.isoformat() if fee_records else None
			}

			# 更新缓存
			if self.cache:
				await self.cache.set(cache_key, fee_details, ttl=3600)  # 缓存1小时

			return fee_details

		except Exception as e:
			logger.error(f"获取交易费用失败: {str(e)}")
			raise

	async def get_account_fees (
			self,
			account_id: str,
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

			# 获取账户的所有交易
			trades = await self.trade_repo.get_by_account_id(account_id, start_time=start_date, end_time=end_date)

			# 计算费用统计
			total_commission = Decimal("0.00")
			total_stamp_tax = Decimal("0.00")
			total_transfer_fee = Decimal("0.00")
			total_regulation_fee = Decimal("0.00")
			total_fees = Decimal("0.00")

			fee_details = []

			for trade in trades:
				# 获取交易的费用记录
				fee_records = await self.fee_repo.get_fees_by_trade_id(trade.trade_id)

				# 计算该交易的费用
				trade_fees = {
					"commission": 0.0,
					"stamp_tax": 0.0,
					"transfer_fee": 0.0,
					"regulation_fee": 0.0,
					"total_fee": 0.0
				}

				for fee_record in fee_records:
					if fee_record.fee_type == "commission":
						trade_fees["commission"] = float(fee_record.fee_amount)
						total_commission += Decimal(str(fee_record.fee_amount))
					elif fee_record.fee_type == "tax":
						trade_fees["stamp_tax"] = float(fee_record.fee_amount)
						total_stamp_tax += Decimal(str(fee_record.fee_amount))
					elif fee_record.fee_type == "transfer":
						trade_fees["transfer_fee"] = float(fee_record.fee_amount)
						total_transfer_fee += Decimal(str(fee_record.fee_amount))
					elif fee_record.fee_type == "regulation":
						trade_fees["regulation_fee"] = float(fee_record.fee_amount)
						total_regulation_fee += Decimal(str(fee_record.fee_amount))
					trade_fees["total_fee"] += float(fee_record.fee_amount)
					total_fees += Decimal(str(fee_record.fee_amount))

				# 添加到费用详情
				if trade_fees["total_fee"] > 0:
					fee_details.append({
						"trade_id": trade.trade_id,
						"ts_code": trade.ts_code,
						"trade_time": trade.trade_time.isoformat(),
						"price": float(trade.price),
						"volume": trade.volume,
						"direction": "buy" if trade.volume > 0 else "sell",
						"fees": trade_fees,
						"recorded_at": fee_records[0].created_at.isoformat() if fee_records else None
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
					"record_count": len(fee_details)
				},
				"daily_stats": daily_stats,
				"security_stats": security_stats,
				"fee_details": fee_details,
				"timestamp": datetime.now().isoformat()
			}

			# 更新缓存
			if self.cache:
				await self.cache.set(cache_key, result, ttl=300)  # 缓存5分钟

			return result

		except Exception as e:
			logger.error(f"获取账户费用统计失败: {str(e)}")
			raise

	async def _calculate_daily_fee_stats (
			self,
			account_id: str,
			start_date: Optional[date],
			end_date: Optional[date]
	) -> List[Dict[str, Any]]:
		"""计算每日费用统计"""
		try:
			# 获取账户的所有交易
			trades = await self.trade_repo.get_by_account_id(account_id, start_time=start_date, end_time=end_date)

			# 按日期分组
			daily_stats_map = {}

			for trade in trades:
				# 获取交易的费用记录
				fee_records = await self.fee_repo.get_fees_by_trade_id(trade.trade_id)
				if not fee_records:
					continue

				record_date = trade.trade_time.date()
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
				stats["trade_count"] += 1

				# 计算费用金额
				fee_amounts = _calculate_fee_amounts(fee_records)
				stats["commission"] += fee_amounts["commission"]
				stats["stamp_tax"] += fee_amounts["stamp_tax"]
				stats["transfer_fee"] += fee_amounts["transfer_fee"]
				stats["regulation_fee"] += fee_amounts["regulation_fee"]
				stats["total_fee"] += fee_amounts["total_fee"]

			# 转换为列表并排序
			daily_stats = list(daily_stats_map.values())
			daily_stats.sort(key=lambda x: x["date"])

			return daily_stats

		except Exception as e:
			logger.error(f"计算每日费用统计失败: {str(e)}")
			return []

	async def _calculate_security_fee_stats (
			self,
			account_id: str,
			start_date: Optional[date],
			end_date: Optional[date]
	) -> List[Dict[str, Any]]:
		"""按证券代码计算费用统计"""
		try:
			# 获取账户的所有交易
			trades = await self.trade_repo.get_by_account_id(account_id, start_time=start_date, end_time=end_date)

			# 按证券代码分组
			security_stats_map = {}

			for trade in trades:
				ts_code = trade.ts_code

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
				stats["trade_count"] += 1

				# 判断买卖方向
				if trade.volume > 0:
					stats["buy_count"] += 1
				else:
					stats["sell_count"] += 1

				# 获取交易的费用记录
				fee_records = await self.fee_repo.get_fees_by_trade_id(trade.trade_id)
				# 计算费用金额
				fee_amounts = _calculate_fee_amounts(fee_records)
				stats["commission"] += fee_amounts["commission"]
				stats["stamp_tax"] += fee_amounts["stamp_tax"]
				stats["transfer_fee"] += fee_amounts["transfer_fee"]
				stats["regulation_fee"] += fee_amounts["regulation_fee"]
				stats["total_fee"] += fee_amounts["total_fee"]

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

	async def get_fee_summary (self, account_id: str, period: str = "month") -> Dict[str, Any]:
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
				start_date = end_date - timedelta(days=7)
			elif period == "month":
				start_date = end_date - timedelta(days=30)
			elif period == "quarter":
				start_date = end_date - timedelta(days=90)
			elif period == "year":
				start_date = end_date - timedelta(days=365)
			else:
				start_date = end_date - timedelta(days=30)

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
			fee_record_id: str,
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
			fee_record = await self.fee_repo.get(fee_record_id)
			if not fee_record:
				raise ValueError(f"费用记录不存在: {fee_record_id}")

			# 计算新的费用金额
			new_fee_amount = Decimal(str(fee_record.fee_amount)) + adjustment_amount

			if new_fee_amount < 0:
				raise ValueError("调整后费用不能为负数")

			# 更新费用记录
			update_data = {
				"fee_amount": new_fee_amount,
				"description": f"{fee_record.description} - 调整: {reason} (调整人: {adjusted_by})"
			}

			success = await self.fee_repo.update(fee_record_id, update_data)

			if success:
				logger.info(f"调整费用记录成功: 记录ID={fee_record_id}, 调整金额={adjustment_amount}, 原因={reason}")

				# 清理缓存
				if self.cache:
					await self.cache.delete(f"trade:fees:{fee_record.trade_id}")

				return True
			else:
				raise ValueError("更新费用记录失败")

		except Exception as e:
			logger.error(f"调整费用记录失败: {str(e)}")
			raise