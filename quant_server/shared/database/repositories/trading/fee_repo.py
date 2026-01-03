# quant_server/shared/database/repositories/trading/fee_repo.py
"""
费用Repository
"""
from sqlalchemy.orm import Session
from sqlalchemy import desc, func
from typing import List, Optional, Dict, Any, Union
from datetime import datetime, timedelta

from quant_server.shared.database.models.business_models import Order, Trade
from quant_server.shared.database.repositories.base import RepositoryBase


class FeeRepository(RepositoryBase):
	"""
	费用仓库
	用于管理交易费用，包括佣金、印花税、过户费等
	"""

	def __init__ (self, session: Session):
		super().__init__(session)

	def calculate_commission (
			self,
			trade_value: float,
			commission_rate: float = 0.0003,
			min_commission: float = 5.0
	) -> float:
		"""
		计算佣金

		Args:
			trade_value: 交易金额
			commission_rate: 佣金费率（默认万分之三）
			min_commission: 最低佣金（默认5元）

		Returns:
			float: 佣金金额
		"""
		commission = trade_value * commission_rate
		return max(commission, min_commission)

	def calculate_tax (
			self,
			trade_value: float,
			direction: str,
			tax_rate: float = 0.001
	) -> float:
		"""
		计算印花税

		Args:
			trade_value: 交易金额
			direction: 交易方向（buy/sell）
			tax_rate: 印花税率（默认千分之一）

		Returns:
			float: 印花税金额
		"""
		# 印花税只在卖出时收取
		if direction == "sell":
			return trade_value * tax_rate
		return 0.0

	def calculate_transfer_fee (
			self,
			trade_value: float,
			fee_rate: float = 0.00002
	) -> float:
		"""
		计算过户费

		Args:
			trade_value: 交易金额
			fee_rate: 过户费率（默认十万分之二）

		Returns:
			float: 过户费金额
		"""
		return trade_value * fee_rate

	def calculate_total_fees (
			self,
			trade_value: float,
			direction: str,
			commission_rate: float = 0.0003,
			min_commission: float = 5.0,
			tax_rate: float = 0.001,
			transfer_fee_rate: float = 0.00002
	) -> Dict[str, float]:
		"""
		计算总费用

		Args:
			trade_value: 交易金额
			direction: 交易方向
			commission_rate: 佣金费率
			min_commission: 最低佣金
			tax_rate: 印花税率
			transfer_fee_rate: 过户费率

		Returns:
			Dict: 各项费用明细
		"""
		commission = self.calculate_commission(trade_value, commission_rate, min_commission)
		tax = self.calculate_tax(trade_value, direction, tax_rate)
		transfer_fee = self.calculate_transfer_fee(trade_value, transfer_fee_rate)

		return {
			"commission": commission,
			"tax": tax,
			"transfer_fee": transfer_fee,
			"total": commission + tax + transfer_fee
		}

	def get_trade_fees (self, trade_id: str) -> Optional[Dict[str, Any]]:
		"""
		获取交易费用详情

		Args:
			trade_id: 交易ID

		Returns:
			Optional[Dict]: 交易费用详情
		"""
		trade = self.session.query(Trade).filter(
			Trade.trade_id == trade_id
		).first()

		if not trade:
			return None

		return {
			"trade_id": trade_id,
			"commission": float(trade.commission),
			"tax": float(trade.tax),
			"total_fee": float(trade.commission + trade.tax),
			"trade_value": float(trade.price * trade.volume),
			"trade_time": trade.trade_time
		}

	def get_order_fees (self, order_id: str) -> Dict[str, Any]:
		"""
		获取订单费用汇总

		Args:
			order_id: 订单ID

		Returns:
			Dict: 订单费用汇总
		"""
		trades = self.session.query(Trade).filter(
			Trade.order_id == order_id
		).all()

		total_commission = sum(float(t.commission) for t in trades)
		total_tax = sum(float(t.tax) for t in trades)
		total_volume = sum(t.volume for t in trades)
		total_amount = sum(float(t.price * t.volume) for t in trades)

		return {
			"order_id": order_id,
			"trade_count": len(trades),
			"total_commission": total_commission,
			"total_tax": total_tax,
			"total_fees": total_commission + total_tax,
			"total_volume": total_volume,
			"total_amount": total_amount,
			"avg_fee_rate": (total_commission + total_tax) / total_amount if total_amount > 0 else 0,
			"trades": [{"trade_id": t.trade_id, "commission": float(t.commission), "tax": float(t.tax)} for t in trades]
		}

	def get_user_fees_summary (
			self,
			user_id: int,
			start_date: Optional[datetime] = None,
			end_date: Optional[datetime] = None
	) -> Dict[str, Any]:
		"""
		获取用户费用汇总

		Args:
			user_id: 用户ID
			start_date: 开始日期
			end_date: 结束日期

		Returns:
			Dict: 用户费用汇总
		"""
		# 查询用户的所有成交
		query = self.session.query(Trade).join(
			Order, Trade.order_id == Order.order_id
		).filter(
			Order.user_id == user_id
		)

		if start_date:
			query = query.filter(Trade.trade_time >= start_date)
		if end_date:
			query = query.filter(Trade.trade_time <= end_date)

		trades = query.all()

		# 计算统计
		buy_trades = [t for t in trades if Order.direction == "buy"]
		sell_trades = [t for t in trades if Order.direction == "sell"]

		total_buy_amount = sum(float(t.price * t.volume) for t in buy_trades)
		total_sell_amount = sum(float(t.price * t.volume) for t in sell_trades)
		total_commission = sum(float(t.commission) for t in trades)
		total_tax = sum(float(t.tax) for t in trades)

		return {
			"user_id": user_id,
			"period": {
				"start": start_date,
				"end": end_date
			},
			"trade_statistics": {
				"total_trades": len(trades),
				"buy_trades": len(buy_trades),
				"sell_trades": len(sell_trades),
				"total_buy_amount": total_buy_amount,
				"total_sell_amount": total_sell_amount,
				"total_trade_amount": total_buy_amount + total_sell_amount
			},
			"fee_statistics": {
				"total_commission": total_commission,
				"total_tax": total_tax,
				"total_fees": total_commission + total_tax,
				"avg_commission_rate": total_commission / (total_buy_amount + total_sell_amount) if (
							                                                                                    total_buy_amount + total_sell_amount) > 0 else 0,
				"avg_tax_rate": total_tax / total_sell_amount if total_sell_amount > 0 else 0
			},
			"daily_breakdown": self._get_daily_fee_breakdown(trades, start_date, end_date)
		}

	def _get_daily_fee_breakdown (
			self,
			trades: List[Trade],
			start_date: Optional[datetime] = None,
			end_date: Optional[datetime] = None
	) -> List[Dict[str, Any]]:
		"""
		获取每日费用明细

		Args:
			trades: 交易列表
			start_date: 开始日期
			end_date: 结束日期

		Returns:
			List[Dict]: 每日费用明细
		"""
		if not trades:
			return []

		# 按交易日分组
		daily_fees = {}
		for trade in trades:
			trade_date = trade.trade_time.date()
			if trade_date not in daily_fees:
				daily_fees[trade_date] = {
					"commission": 0.0,
					"tax": 0.0,
					"buy_amount": 0.0,
					"sell_amount": 0.0,
					"trade_count": 0
				}

			daily_fees[trade_date]["commission"] += float(trade.commission)
			daily_fees[trade_date]["tax"] += float(trade.tax)
			daily_fees[trade_date]["trade_count"] += 1

			# 需要获取交易方向
			order = self.session.query(Order).filter(
				Order.order_id == trade.order_id
			).first()

			if order and order.direction == "buy":
				daily_fees[trade_date]["buy_amount"] += float(trade.price * trade.volume)
			elif order and order.direction == "sell":
				daily_fees[trade_date]["sell_amount"] += float(trade.price * trade.volume)

		# 转换为列表并排序
		result = []
		for date, fees in daily_fees.items():
			result.append({
				"date": date,
				**fees,
				"total_fees": fees["commission"] + fees["tax"],
				"total_amount": fees["buy_amount"] + fees["sell_amount"]
			})

		result.sort(key=lambda x: x["date"])
		return result

	def get_fee_config (self, user_id: int, account_id: int) -> Dict[str, Any]:
		"""
		获取用户的费用配置

		Args:
			user_id: 用户ID
			account_id: 账户ID

		Returns:
			Dict: 费用配置
		"""
		# 这里可以根据用户等级、账户类型等返回不同的费率
		return {
			"commission_rate": 0.0003,  # 佣金费率：万分之三
			"min_commission": 5.0,  # 最低佣金：5元
			"tax_rate": 0.001,  # 印花税率：千分之一（卖出）
			"transfer_fee_rate": 0.00002,  # 过户费率：十万分之二
			"stamp_duty_exempt": False,  # 是否免征印花税
			"special_rate": False  # 是否有特殊费率
		}

	def update_fee_config (
			self,
			user_id: int,
			account_id: int,
			config: Dict[str, Any]
	) -> bool:
		"""
		更新费用配置

		Args:
			user_id: 用户ID
			account_id: 账户ID
			config: 新的配置

		Returns:
			bool: 是否成功更新
		"""
		# 这里需要根据实际的表结构实现
		# 暂时返回成功
		return True

	def export_fee_report (
			self,
			user_id: int,
			start_date: datetime,
			end_date: datetime,
			format: str = "csv"
	) -> Dict[str, Any]:
		"""
		导出费用报告

		Args:
			user_id: 用户ID
			start_date: 开始日期
			end_date: 结束日期
			format: 导出格式

		Returns:
			Dict: 导出结果
		"""
		summary = self.get_user_fees_summary(user_id, start_date, end_date)

		return {
			"user_id": user_id,
			"period": {
				"start": start_date,
				"end": end_date
			},
			"format": format,
			"summary": summary,
			"generated_at": datetime.now()
		}