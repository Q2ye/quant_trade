"""
资金余额事件定义
用于账户资金变动相关的事件通知

业务场景：
1. 账户资金余额更新
2. 入金/出金操作完成
3. 资产总额变动
4. 资金流水记录
"""

from datetime import datetime
from decimal import Decimal
from typing import Dict, Any, List, Optional

from quant_server.core.events.base import BaseEvent, EventPriority
from .types import AccountEventType


class AccountBalanceUpdatedEvent(BaseEvent):
	"""
	账户资金余额更新事件

	触发时机：
	- 交易导致资金变动
	- 手续费扣除
	- 利息计算
	- 手动调整资金

	事件数据：
	- account_id: 账户ID
	- balance_type: 余额类型（可用资金/冻结资金/总资金）
	- old_balance: 变动前余额
	- new_balance: 变动后余额
	- change_amount: 变动金额
	- change_reason: 变动原因
	"""

	def __init__ (
			self,
			account_id: str,
			balance_type: str,
			old_balance: Decimal,
			new_balance: Decimal,
			change_amount: Decimal,
			change_reason: str,
			currency: str = "CNY",
			transaction_id: Optional[str] = None,
			**kwargs
	):
		super().__init__(
			module="events",
			event_type=AccountEventType.BALANCE_UPDATED.value,
			priority=EventPriority.NORMAL,
			source="account_service",
			**kwargs
		)

		# 计算变动方向和百分比
		change_direction = "increase" if change_amount > 0 else "decrease"
		change_percentage = 0
		if old_balance != 0:
			change_percentage = float((change_amount / old_balance) * 100)

		self.data = {
			"account_id": account_id,
			"balance_type": balance_type,
			"old_balance": str(old_balance),
			"new_balance": str(new_balance),
			"change_amount": str(change_amount),
			"change_direction": change_direction,
			"change_percentage": round(change_percentage, 4),
			"change_reason": change_reason,
			"currency": currency,
			"transaction_id": transaction_id,
			"update_time": datetime.now().isoformat(),
			"balance_snapshot": AccountBalanceUpdatedEvent._create_balance_snapshot(balance_type, new_balance)
		}

	@staticmethod
	def _create_balance_snapshot (balance_type: str, balance: Decimal) -> Dict[str, Any]:
		"""创建余额快照信息"""
		return {
			"type": balance_type,
			"amount": str(balance),
			"timestamp": datetime.now().isoformat(),
			"status": "confirmed"
		}


class AccountDepositCompletedEvent(BaseEvent):
	"""
	账户入金完成事件

	触发时机：
	- 用户充值操作完成
	- 资金划转入账
	- 系统奖励发放

	事件数据：
	- deposit_id: 入金记录ID
	- deposit_amount: 入金金额
	- deposit_method: 入金方式（网银/第三方支付/内部转账）
	- deposit_status: 入金状态（成功/失败/处理中）
	"""

	def __init__ (
			self,
			account_id: str,
			deposit_id: str,
			deposit_amount: Decimal,
			deposit_method: str,
			deposit_status: str = "completed",
			fee_amount: Decimal = Decimal("0"),
			actual_amount: Optional[Decimal] = None,
			reference_no: Optional[str] = None,
			**kwargs
	):
		super().__init__(
			module="events",
			event_type=AccountEventType.DEPOSIT_COMPLETED.value,
			priority=EventPriority.NORMAL,
			source="account_service",
			**kwargs
		)

		if actual_amount is None:
			actual_amount = deposit_amount - fee_amount

		self.data = {
			"account_id": account_id,
			"deposit_id": deposit_id,
			"deposit_amount": str(deposit_amount),
			"deposit_method": deposit_method,
			"deposit_status": deposit_status,
			"fee_amount": str(fee_amount),
			"actual_amount": str(actual_amount),
			"reference_no": reference_no,
			"completion_time": datetime.now().isoformat(),
			"verification_status": "pending",
			"deposit_details": AccountDepositCompletedEvent._get_deposit_details(deposit_method)
		}

	@staticmethod
	def _get_deposit_details (deposit_method: str) -> Dict[str, Any]:
		"""根据入金方式获取详细信息"""
		details = {
			"method": deposit_method,
			"processing_time": "即时" if deposit_method in ["内部转账", "第三方支付"] else "1-3个工作日",
			"fee_rate": "0%" if deposit_method == "内部转账" else "0.1%",
			"limit": AccountDepositCompletedEvent._get_deposit_limit(deposit_method)
		}
		return details

	@staticmethod
	def _get_deposit_limit (deposit_method: str) -> Dict[str, str]:
		"""获取入金限额"""
		limits = {
			"网银转账": {"min": "100", "max": "1000000"},
			"第三方支付": {"min": "10", "max": "500000"},
			"内部转账": {"min": "1", "max": "无限制"}
		}
		return limits.get(deposit_method, {"min": "100", "max": "1000000"})


class AccountWithdrawCompletedEvent(BaseEvent):
	"""
	账户出金完成事件

	触发时机：
	- 用户提现操作完成
	- 资金划转出账
	- 费用扣除

	事件数据：
	- withdraw_id: 出金记录ID
	- withdraw_amount: 出金金额
	- withdraw_method: 出金方式
	- withdraw_status: 出金状态
	"""

	def __init__ (
			self,
			account_id: str,
			withdraw_id: str,
			withdraw_amount: Decimal,
			withdraw_method: str,
			withdraw_status: str = "completed",
			fee_amount: Decimal = Decimal("0"),
			actual_amount: Optional[Decimal] = None,
			approval_time: Optional[datetime] = None,
			**kwargs
	):
		super().__init__(
			module="events",
			event_type=AccountEventType.WITHDRAW_COMPLETED.value,
			priority=EventPriority.NORMAL,
			source="account_service",
			**kwargs
		)

		if actual_amount is None:
			actual_amount = withdraw_amount - fee_amount

		if approval_time is None:
			approval_time = datetime.now()

		self.data = {
			"account_id": account_id,
			"withdraw_id": withdraw_id,
			"withdraw_amount": str(withdraw_amount),
			"withdraw_method": withdraw_method,
			"withdraw_status": withdraw_status,
			"fee_amount": str(fee_amount),
			"actual_amount": str(actual_amount),
			"approval_time": approval_time.isoformat(),
			"completion_time": datetime.now().isoformat(),
			"withdraw_details": AccountWithdrawCompletedEvent._get_withdraw_details(withdraw_method),
			"risk_level": AccountWithdrawCompletedEvent._assess_risk_level(withdraw_amount, withdraw_method)
		}

	@staticmethod
	def _get_withdraw_details (withdraw_method: str) -> Dict[str, Any]:
		"""根据出金方式获取详细信息"""
		details = {
			"method": withdraw_method,
			"processing_time": "1-3个工作日",
			"fee_rate": "0.1%",
			"limit": AccountWithdrawCompletedEvent._get_withdraw_limit(withdraw_method)
		}
		return details

	@staticmethod
	def _get_withdraw_limit (withdraw_method: str) -> Dict[str, str]:
		"""获取出金限额"""
		limits = {
			"银行卡": {"min": "100", "max": "500000", "daily_limit": "1000000"},
			"第三方支付": {"min": "10", "max": "200000", "daily_limit": "500000"},
			"内部转账": {"min": "1", "max": "无限制", "daily_limit": "无限制"}
		}
		return limits.get(withdraw_method, {"min": "100", "max": "500000", "daily_limit": "1000000"})

	@staticmethod
	def _assess_risk_level (amount: Decimal, method: str) -> str:
		"""评估出金风险等级"""
		amount_float = float(amount)

		if amount_float > 500000:
			return "high"
		elif amount_float > 100000:
			return "medium"
		elif method == "新收款方式":
			return "medium"
		else:
			return "low"


class AccountAssetUpdatedEvent(BaseEvent):
	"""
	账户资产更新事件

	触发时机：
	- 账户资产总额变动
	- 持仓市值更新
	- 资产组合重新估值

	事件数据：
	- total_assets: 总资产
	- total_liabilities: 总负债
	- net_asset_value: 净资产
	- asset_breakdown: 资产构成明细
	"""

	def __init__ (
			self,
			account_id: str,
			total_assets: Decimal,
			total_liabilities: Decimal,
			asset_breakdown: Dict[str, Decimal],
			update_reason: str = "daily_valuation",
			previous_assets: Optional[Decimal] = None,
			previous_liabilities: Optional[Decimal] = None,
			**kwargs
	):
		super().__init__(
			module="events",
			event_type=AccountEventType.ASSET_UPDATED.value,
			priority=EventPriority.NORMAL,
			source="account_service",
			**kwargs
		)

		# 计算净资产
		net_asset_value = total_assets - total_liabilities

		# 计算资产变动
		asset_change = Decimal("0")
		liability_change = Decimal("0")
		if previous_assets is not None:
			asset_change = total_assets - previous_assets
		if previous_liabilities is not None:
			liability_change = total_liabilities - previous_liabilities

		# 计算资产构成百分比
		asset_percentages = {}
		if total_assets > 0:
			for asset_type, amount in asset_breakdown.items():
				percentage = (amount / total_assets) * 100
				asset_percentages[asset_type] = float(percentage)

		self.data = {
			"account_id": account_id,
			"total_assets": str(total_assets),
			"total_liabilities": str(total_liabilities),
			"net_asset_value": str(net_asset_value),
			"asset_change": str(asset_change),
			"liability_change": str(liability_change),
			"asset_breakdown": {k: str(v) for k, v in asset_breakdown.items()},
			"asset_percentages": asset_percentages,
			"update_reason": update_reason,
			"valuation_time": datetime.now().isoformat(),
			"asset_health": AccountAssetUpdatedEvent._assess_asset_health(total_assets, total_liabilities, asset_breakdown),
			"risk_exposure": AccountAssetUpdatedEvent._calculate_risk_exposure(asset_breakdown)
		}

	@staticmethod
	def _assess_asset_health (assets: Decimal, liabilities: Decimal, breakdown: Dict[str, Decimal]) -> Dict[
		str, Any]:
		"""评估资产健康状况"""
		# 计算负债率
		debt_ratio = 0
		if assets > 0:
			debt_ratio = float((liabilities / assets) * 100)

		# 评估流动性
		liquid_assets = breakdown.get("cash", Decimal("0")) + breakdown.get("money_fund", Decimal("0"))
		liquidity_ratio = 0
		if liabilities > 0:
			liquidity_ratio = float((liquid_assets / liabilities) * 100)

		# 评估分散度
		asset_types_count = len(breakdown)
		diversification_score = min(asset_types_count / 5 * 100, 100)  # 满分为5类资产

		health_status = "良好"
		if debt_ratio > 70:
			health_status = "高风险"
		elif debt_ratio > 50:
			health_status = "中等风险"
		elif liquidity_ratio < 20:
			health_status = "流动性不足"

		return {
			"debt_ratio": round(debt_ratio, 2),
			"liquidity_ratio": round(liquidity_ratio, 2),
			"diversification_score": round(diversification_score, 2),
			"status": health_status,
			"recommendations": AccountAssetUpdatedEvent._generate_health_recommendations(debt_ratio, liquidity_ratio, diversification_score)
		}

	@staticmethod
	def _calculate_risk_exposure (breakdown: Dict[str, Decimal]) -> Dict[str, float]:
		"""计算风险敞口"""
		total = sum(breakdown.values())
		if total == 0:
			return {}

		# 定义各类资产的风险系数
		risk_coefficients = {
			"cash": 0.1,
			"money_fund": 0.2,
			"bond": 0.3,
			"stock": 0.8,
			"derivative": 0.9,
			"real_estate": 0.5,
			"commodity": 0.7
		}

		risk_exposure = {}
		for asset_type, amount in breakdown.items():
			coefficient = risk_coefficients.get(asset_type, 0.5)
			exposure = float(amount / total) * coefficient
			risk_exposure[asset_type] = round(exposure, 4)

		# 计算总风险敞口
		total_exposure = sum(risk_exposure.values())
		risk_exposure["total"] = round(total_exposure, 4)

		return risk_exposure

	@staticmethod
	def _generate_health_recommendations (debt_ratio: float, liquidity_ratio: float,
	                                      diversification_score: float) -> List[str]:
		"""生成资产健康建议"""
		recommendations = []

		if debt_ratio > 50:
			recommendations.append(f"当前负债率{debt_ratio:.1f}%偏高，建议降低杠杆")

		if liquidity_ratio < 30:
			recommendations.append(f"流动性比率{liquidity_ratio:.1f}%偏低，建议增加现金类资产")

		if diversification_score < 60:
			recommendations.append("资产分散度不足，建议增加资产类别")

		if not recommendations:
			recommendations.append("资产健康状况良好，建议保持当前配置")

		return recommendations


class AccountStatusChangedEvent(BaseEvent):
	"""
	账户状态变更事件

	触发时机：
	- 账户状态变更（正常/冻结/关闭）
	- 账户权限变更
	- 账户风险等级变更

	事件数据：
	- account_id: 账户ID
	- old_status: 变更前状态
	- new_status: 变更后状态
	- reason: 变更原因
	- timestamp: 变更时间
	"""

	def __init__ (
			self,
			account_id: str,
			old_status: str,
			new_status: str,
			reason: str,
			timestamp: datetime,
			operator: Optional[str] = None,
			ip_address: Optional[str] = None,
			**kwargs
	):
		super().__init__(
			module="events",
			event_type=AccountEventType.STATUS_CHANGED.value,
			priority=EventPriority.NORMAL,
			source="account_service",
			**kwargs
		)

		self.data = {
			"account_id": account_id,
			"old_status": old_status,
			"new_status": new_status,
			"reason": reason,
			"timestamp": timestamp.isoformat(),
			"operator": operator,
			"ip_address": ip_address,
			"status_change_details": AccountStatusChangedEvent._get_status_change_details(old_status, new_status, reason),
			"action_required": AccountStatusChangedEvent._determine_action_required(new_status)
		}

	@staticmethod
	def _get_status_change_details (old_status: str, new_status: str, reason: str) -> Dict[str, Any]:
		"""获取状态变更详情"""
		status_map = {
			"正常": "账户状态正常",
			"冻结": "账户已被冻结",
			"关闭": "账户已关闭",
			"审核中": "账户审核中"
		}

		return {
			"old_status_desc": status_map.get(old_status, old_status),
			"new_status_desc": status_map.get(new_status, new_status),
			"change_type": "升级" if AccountStatusChangedEvent._is_status_upgrade(old_status,
			                                                 new_status) else "降级" if AccountStatusChangedEvent._is_status_downgrade(
				old_status, new_status) else "变更",
			"reason_detail": AccountStatusChangedEvent._get_reason_detail(reason)
		}

	@staticmethod
	def _is_status_upgrade (old_status: str, new_status: str) -> bool:
		"""判断是否为状态升级"""
		status_priority = {"关闭": 0, "冻结": 1, "审核中": 2, "正常": 3}
		return status_priority.get(new_status, 0) > status_priority.get(old_status, 0)

	@staticmethod
	def _is_status_downgrade (old_status: str, new_status: str) -> bool:
		"""判断是否为状态降级"""
		status_priority = {"关闭": 0, "冻结": 1, "审核中": 2, "正常": 3}
		return status_priority.get(new_status, 0) < status_priority.get(old_status, 0)

	@staticmethod
	def _get_reason_detail (reason: str) -> str:
		"""获取原因详情"""
		reason_map = {
			"user_request": "用户主动请求",
			"risk_control": "风控触发",
			"admin_operation": "管理员操作",
			"system_maintenance": "系统维护",
			"compliance_issue": "合规问题"
		}
		return reason_map.get(reason, reason)

	@staticmethod
	def _determine_action_required (new_status: str) -> List[str]:
		"""确定需要的后续操作"""
		actions = []

		if new_status == "冻结":
			actions.append("联系客服了解冻结原因")
			actions.append("提交相关证明材料")
		elif new_status == "关闭":
			actions.append("账户已关闭，无法恢复")
			actions.append("如需继续交易，请重新开户")
		elif new_status == "审核中":
			actions.append("等待审核完成")
			actions.append("保持联系方式畅通")

		return actions