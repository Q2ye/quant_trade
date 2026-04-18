"""
账户持仓事件定义
用于持仓管理相关的事件通知

业务场景：
1. 持仓开仓/平仓通知
2. 持仓数量调整
3. 持仓市值更新
4. 持仓状态变化
"""

from datetime import datetime
from decimal import Decimal
from typing import Dict, Any, Optional

from quant_server.core.events.base import BaseEvent, EventPriority
from .types import AccountEventType


class AccountPositionUpdatedEvent(BaseEvent):
	"""
	账户持仓更新事件

	触发时机：
	- 持仓数量变化
	- 持仓成本更新
	- 持仓市值重新计算
	- 持仓状态变化

	事件数据：
	- position_id: 持仓ID
	- symbol: 标的代码
	- position_type: 持仓类型（多/空）
	- quantity: 持仓数量
	- avg_cost: 平均成本
	- market_value: 市值
	"""

	def __init__ (
			self,
			account_id: str,
			position_id: str,
			symbol: str,
			position_type: str,
			quantity: Decimal,
			avg_cost: Decimal,
			market_value: Decimal,
			previous_quantity: Optional[Decimal] = None,
			previous_avg_cost: Optional[Decimal] = None,
			update_reason: str = "trade_execution",
			**kwargs
	):
		super().__init__(
			module="events",
			event_type=AccountEventType.POSITION_UPDATED.value,
			priority=EventPriority.NORMAL,
			source="position_service",
			**kwargs
		)

		# 计算变动
		quantity_change = Decimal("0")
		if previous_quantity is not None:
			quantity_change = quantity - previous_quantity

		cost_change = Decimal("0")
		if previous_avg_cost is not None:
			cost_change = avg_cost - previous_avg_cost

		# 计算盈亏
		unrealized_pnl = market_value - (avg_cost * quantity)
		unrealized_pnl_percentage = 0
		if avg_cost * quantity != 0:
			unrealized_pnl_percentage = float((unrealized_pnl / (avg_cost * quantity)) * 100)

		self.data = {
			"account_id": account_id,
			"position_id": position_id,
			"symbol": symbol,
			"position_type": position_type,
			"quantity": str(quantity),
			"avg_cost": str(avg_cost),
			"market_value": str(market_value),
			"quantity_change": str(quantity_change),
			"cost_change": str(cost_change),
			"unrealized_pnl": str(unrealized_pnl),
			"unrealized_pnl_percentage": round(unrealized_pnl_percentage, 4),
			"update_reason": update_reason,
			"update_time": datetime.now().isoformat(),
			"position_status": AccountPositionUpdatedEvent._determine_position_status(position_type, quantity, unrealized_pnl_percentage),
			"risk_metrics": AccountPositionUpdatedEvent._calculate_risk_metrics(quantity, avg_cost, market_value)
		}

	@staticmethod
	def _determine_position_status (position_type: str, quantity: Decimal, pnl_percentage: float) -> str:
		"""确定持仓状态"""
		if quantity == 0:
			return "closed"

		status = "normal"

		# 根据盈亏判断状态
		if pnl_percentage > 20:
			status = "profitable"
		elif pnl_percentage < -10:
			status = "loss"

		# 根据持仓类型添加前缀
		if position_type == "short":
			status = f"short_{status}"

		return status

	@staticmethod
	def _calculate_risk_metrics (quantity: Decimal, avg_cost: Decimal, market_value: Decimal) -> Dict[str, Any]:
		"""计算持仓风险指标"""
		cost_basis = avg_cost * quantity

		# 计算波动率风险
		volatility_risk = "low"
		value_change = abs(market_value - cost_basis)
		if value_change > cost_basis * Decimal("0.2"):
			volatility_risk = "high"
		elif value_change > cost_basis * Decimal("0.1"):
			volatility_risk = "medium"

		# 计算集中度风险
		# 这里需要总资产信息，暂时设为中等
		concentration_risk = "medium"

		# 计算流动性风险（假设）
		liquidity_risk = "low"

		return {
			"volatility_risk": volatility_risk,
			"concentration_risk": concentration_risk,
			"liquidity_risk": liquidity_risk,
			"overall_risk": AccountPositionUpdatedEvent._calculate_overall_risk(volatility_risk, concentration_risk, liquidity_risk)
		}

	@staticmethod
	def _calculate_overall_risk (volatility: str, concentration: str, liquidity: str) -> str:
		"""计算整体风险等级"""
		risk_scores = {
			"low": 1,
			"medium": 2,
			"high": 3
		}

		total_score = risk_scores.get(volatility, 1) + risk_scores.get(concentration, 1) + risk_scores.get(liquidity, 1)

		if total_score >= 7:
			return "high"
		elif total_score >= 5:
			return "medium"
		else:
			return "low"


class AccountPositionOpenedEvent(BaseEvent):
	"""
	账户开仓事件

	触发时机：
	- 新建持仓
	- 增加现有持仓

	事件数据：
	- open_price: 开仓价格
	- open_time: 开仓时间
	- open_reason: 开仓原因
	- initial_margin: 初始保证金
	"""

	def __init__ (
			self,
			account_id: str,
			position_id: str,
			symbol: str,
			position_type: str,
			quantity: Decimal,
			open_price: Decimal,
			open_reason: str,
			initial_margin: Optional[Decimal] = None,
			stop_loss: Optional[Decimal] = None,
			take_profit: Optional[Decimal] = None,
			**kwargs
	):
		super().__init__(
			module="events",
			event_type="events.position.opened",  # 自定义事件类型
			priority=EventPriority.NORMAL,
			source="trade_engine",
			**kwargs
		)

		if initial_margin is None:
			# 默认保证金为开仓价值的10%
			initial_margin = open_price * quantity * Decimal("0.1")

		self.data = {
			"account_id": account_id,
			"position_id": position_id,
			"symbol": symbol,
			"position_type": position_type,
			"quantity": str(quantity),
			"open_price": str(open_price),
			"open_value": str(open_price * quantity),
			"open_reason": open_reason,
			"initial_margin": str(initial_margin),
			"margin_ratio": str((initial_margin / (open_price * quantity)) * 100),
			"stop_loss": str(stop_loss) if stop_loss else None,
			"take_profit": str(take_profit) if take_profit else None,
			"open_time": datetime.now().isoformat(),
			"position_strategy": AccountPositionOpenedEvent._determine_strategy(open_reason),
			"risk_parameters": AccountPositionOpenedEvent._get_risk_parameters(position_type, quantity, open_price)
		}

	@staticmethod
	def _determine_strategy (open_reason: str) -> str:
		"""根据开仓原因确定策略类型"""
		if "signal" in open_reason:
			return "signal_driven"
		elif "manual" in open_reason:
			return "manual_trade"
		elif "hedge" in open_reason:
			return "hedging"
		elif "arbitrage" in open_reason:
			return "arbitrage"
		else:
			return "other"

	@staticmethod
	def _get_risk_parameters (position_type: str, quantity: Decimal, price: Decimal) -> Dict[str, Any]:
		"""获取风险参数"""
		position_value = quantity * price

		# 计算建议的止损止盈
		if position_type == "long":
			suggested_stop = price * Decimal("0.95")  # 5%止损
			suggested_take = price * Decimal("1.10")  # 10%止盈
		else:  # short
			suggested_stop = price * Decimal("1.05")  # 5%止损
			suggested_take = price * Decimal("0.90")  # 10%止盈

		return {
			"position_value": str(position_value),
			"suggested_stop_loss": str(suggested_stop),
			"suggested_take_profit": str(suggested_take),
			"max_position_size": str(position_value * Decimal("0.2")),  # 建议最大仓位20%
			"risk_reward_ratio": "1:2"  # 风险收益比
		}


class AccountPositionClosedEvent(BaseEvent):
	"""
	账户平仓事件

	触发时机：
	- 完全平仓
	- 部分平仓导致持仓关闭

	事件数据：
	- close_price: 平仓价格
	- close_time: 平仓时间
	- close_reason: 平仓原因
	- realized_pnl: 实现盈亏
	"""

	def __init__ (
			self,
			account_id: str,
			position_id: str,
			symbol: str,
			close_price: Decimal,
			close_quantity: Decimal,
			avg_cost: Decimal,
			close_reason: str,
			transaction_id: Optional[str] = None,
			fee_amount: Decimal = Decimal("0"),
			**kwargs
	):
		super().__init__(
			module="events",
			event_type="events.position.closed",  # 自定义事件类型
			priority=EventPriority.NORMAL,
			source="trade_engine",
			**kwargs
		)

		# 计算实现盈亏
		cost_basis = avg_cost * close_quantity
		close_value = close_price * close_quantity
		realized_pnl = close_value - cost_basis - fee_amount

		# 计算收益率
		pnl_percentage = 0.0
		if cost_basis != 0.0:
			pnl_percentage = float((realized_pnl / cost_basis) * 100)

		self.data = {
			"account_id": account_id,
			"position_id": position_id,
			"symbol": symbol,
			"close_price": str(close_price),
			"close_quantity": str(close_quantity),
			"close_value": str(close_value),
			"avg_cost": str(avg_cost),
			"close_reason": close_reason,
			"realized_pnl": str(realized_pnl),
			"realized_pnl_percentage": round(pnl_percentage, 4),
			"fee_amount": str(fee_amount),
			"transaction_id": transaction_id,
			"close_time": datetime.now().isoformat(),
			"trade_summary": AccountPositionClosedEvent._create_trade_summary(close_reason, realized_pnl, pnl_percentage),
			"performance_metrics": AccountPositionClosedEvent._calculate_performance_metrics(cost_basis, realized_pnl, close_reason)
		}

	@staticmethod
	def _create_trade_summary (reason: str, pnl: Decimal, pnl_percentage: float) -> Dict[str, Any]:
		"""创建交易摘要"""
		trade_result = "盈利" if pnl > 0 else "亏损"

		summary = {
			"result": trade_result,
			"reason": reason,
			"pnl_amount": str(pnl),
			"pnl_percentage": round(pnl_percentage, 2),
			"trade_quality": AccountPositionClosedEvent._assess_trade_quality(pnl_percentage, reason)
		}

		return summary

	@staticmethod
	def _assess_trade_quality (pnl_percentage: float, reason: str) -> str:
		"""评估交易质量"""
		if abs(pnl_percentage) > 20:
			return "exceptional" if pnl_percentage > 0 else "poor"
		elif abs(pnl_percentage) > 10:
			return "good" if pnl_percentage > 0 else "below_average"
		elif "stop_loss" in reason:
			return "disciplined"
		elif "take_profit" in reason:
			return "target_achieved"
		else:
			return "average"

	@staticmethod
	def _calculate_performance_metrics (cost_basis: Decimal, realized_pnl: Decimal, reason: str) -> Dict[
		str, Any]:
		"""计算绩效指标"""
		# 这里需要更多上下文信息，暂时提供基础指标
		metrics = {
			"return_on_capital": str((realized_pnl / cost_basis) * 100 if cost_basis != 0 else Decimal("0")),
			"risk_adjusted_return": "N/A",
			"win_loss_ratio": "1:0",
			"expectancy": "N/A",
			"consistency_score": AccountPositionClosedEvent._calculate_consistency_score(reason, realized_pnl)
		}

		return metrics

	@staticmethod
	def _calculate_consistency_score (reason: str, pnl: Decimal) -> float:
		"""计算一致性得分"""
		score = 50.0  # 基础分

		# 根据平仓原因调整
		if "stop_loss" in reason:
			score += 10  # 遵守止损纪律
		elif "take_profit" in reason:
			score += 15  # 达到止盈目标
		elif "signal" in reason:
			score += 5  # 信号驱动

		# 根据盈亏调整
		if pnl > 0:
			score += 20
		else:
			score -= 10

		return max(0.0, min(100.0, score))


class AccountPositionAdjustedEvent(BaseEvent):
	"""
	账户持仓调整事件

	触发时机：
	- 持仓数量调整
	- 成本基础调整
	- 持仓分类调整

	事件数据：
	- adjustment_type: 调整类型（数量/成本/分类）
	- adjustment_amount: 调整金额
	- adjustment_reason: 调整原因
	- adjustment_details: 调整详情
	"""

	def __init__ (
			self,
			account_id: str,
			position_id: str,
			adjustment_type: str,
			adjustment_amount: Decimal,
			adjustment_reason: str,
			previous_value: Decimal,
			new_value: Decimal,
			adjustment_details: Optional[Dict[str, Any]] = None,
			**kwargs
	):
		super().__init__(
			module="events",
			event_type="events.position.adjusted",  # 自定义事件类型
			priority=EventPriority.NORMAL,
			source="account_service",
			**kwargs
		)

		self.data = {
			"account_id": account_id,
			"position_id": position_id,
			"adjustment_type": adjustment_type,
			"adjustment_amount": str(adjustment_amount),
			"adjustment_reason": adjustment_reason,
			"previous_value": str(previous_value),
			"new_value": str(new_value),
			"adjustment_percentage": str(
				((new_value - previous_value) / previous_value * 100) if previous_value != 0 else "0"),
			"adjustment_details": adjustment_details or {},
			"adjustment_time": datetime.now().isoformat(),
			"approval_required": AccountPositionAdjustedEvent._requires_approval(adjustment_type, adjustment_amount),
			"audit_trail": self._create_audit_trail(adjustment_type, adjustment_reason)
		}

	@staticmethod
	def _requires_approval (adjustment_type: str, amount: Decimal) -> bool:
		"""判断是否需要审批"""
		amount_float = float(amount)

		if adjustment_type == "cost_basis" and amount_float > 10000:
			return True
		elif adjustment_type == "quantity" and amount_float > 1000:
			return True
		elif adjustment_type == "classification":
			return False  # 分类调整通常不需要审批
		else:
			return False

	def _create_audit_trail (self, adjustment_type: str, reason: str) -> Dict[str, Any]:
		"""创建审计跟踪记录"""
		return {
			"timestamp": datetime.now().isoformat(),
			"type": adjustment_type,
			"reason": reason,
			"operator": "events",  # 实际应用中应从上下文中获取
			"ip_address": "127.0.0.1",
			"session_id": self.event_id[:8],
			"verification_method": "auto_verification"
		}