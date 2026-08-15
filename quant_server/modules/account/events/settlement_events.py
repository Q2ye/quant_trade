"""
结算对账事件定义
用于结算和对账过程中的事件通知

业务场景：
1. 日终结算开始和完成
2. 资金对账处理
3. 持仓核对
4. 结算报告生成
"""

from datetime import datetime, date
from typing import Dict, Any, List, Optional

from core.events.base import BaseEvent, EventPriority
from .types import AccountEventType


class AccountSettlementStartedEvent(BaseEvent):
	"""
	账户结算开始事件

	触发时机：
	- 交易日结束开始结算
	- 手动触发结算
	- 定时结算任务启动

	事件数据：
	- settlement_date: 结算日期
	- settlement_type: 结算类型（日结/周结/月结）
	- scope: 结算范围（全部/指定账户）
	"""

	event_type: str = AccountEventType.SETTLEMENT_STARTED.value

	def __init__ (
			self,
			settlement_date: date,
			settlement_type: str = "daily",
			scope: str = "all",
			account_ids: Optional[List[str]] = None,
			**kwargs
	):
		super().__init__(
			module="events",
			event_type=AccountEventType.SETTLEMENT_STARTED.value,
			priority=EventPriority.NORMAL,
			source="settlement_engine",
			**kwargs
		)

		if account_ids is None:
			account_ids = []

		self.data = {
			"settlement_date": settlement_date.isoformat(),
			"settlement_type": settlement_type,
			"scope": scope,
			"account_count": len(account_ids),
			"account_ids": account_ids,
			"start_time": datetime.now().isoformat(),
			"estimated_duration": AccountSettlementStartedEvent._estimate_duration(settlement_type, len(account_ids)),
			"settlement_steps": AccountSettlementStartedEvent._get_settlement_steps(settlement_type),
			"checkpoints": AccountSettlementStartedEvent._define_checkpoints(settlement_type)
		}

	@staticmethod
	def _estimate_duration (settlement_type: str, account_count: int) -> int:
		"""估计结算持续时间（分钟）"""
		base_times = {
			"daily": 5,
			"weekly": 15,
			"monthly": 30,
			"yearly": 60
		}

		base_time = base_times.get(settlement_type, 10)

		# 根据账户数量调整
		if account_count > 100:
			additional_time = account_count / 10  # 每10个账户增加1分钟
			return int(base_time + additional_time)

		return base_time

	@staticmethod
	def _get_settlement_steps (settlement_type: str) -> List[Dict[str, Any]]:
		"""获取结算步骤"""
		common_steps = [
			{"step": "数据准备", "description": "准备结算所需数据"},
			{"step": "交易核对", "description": "核对当日交易记录"},
			{"step": "持仓计算", "description": "计算持仓市值"},
			{"step": "资金结算", "description": "结算资金余额"}
		]

		additional_steps = {
			"daily": [
				{"step": "日终报告", "description": "生成日终结算报告"}
			],
			"weekly": [
				{"step": "周度汇总", "description": "汇总一周交易数据"},
				{"step": "周报生成", "description": "生成周度结算报告"}
			],
			"monthly": [
				{"step": "月度汇总", "description": "汇总一月交易数据"},
				{"step": "费用计算", "description": "计算月度费用"},
				{"step": "月报生成", "description": "生成月度结算报告"}
			]
		}

		steps = common_steps + additional_steps.get(settlement_type, [])
		return steps

	@staticmethod
	def _define_checkpoints (settlement_type: str) -> Dict[str, Dict[str, Any]]:
		"""定义结算检查点"""
		checkpoints = {
			"data_preparation": {
				"name": "数据准备完成",
				"weight": 0.2,
				"timeout": 300  # 5分钟
			},
			"trade_verification": {
				"name": "交易核对完成",
				"weight": 0.3,
				"timeout": 600  # 10分钟
			},
			"position_calculation": {
				"name": "持仓计算完成",
				"weight": 0.3,
				"timeout": 900  # 15分钟
			},
			"fund_settlement": {
				"name": "资金结算完成",
				"weight": 0.2,
				"timeout": 300  # 5分钟
			}
		}

		# 根据结算类型调整检查点
		if settlement_type == "monthly":
			checkpoints["fee_calculation"] = {
				"name": "费用计算完成",
				"weight": 0.1,
				"timeout": 600
			}
			# 调整其他权重
			for key in ["data_preparation", "trade_verification", "position_calculation", "fund_settlement"]:
				checkpoints[key]["weight"] *= 0.9

		return checkpoints


def _assess_settlement_quality (success_rate: float, issues: List[Dict[str, Any]], duration: float) -> Dict[
	str, Any]:
	"""评估结算质量"""
	quality_score = success_rate

	# 根据问题数量扣分
	if issues:
		issue_penalty = len(issues) * 5
		quality_score = max(0.0, quality_score - issue_penalty)

	# 根据持续时间调整
	expected_duration = 600  # 预期10分钟
	if duration > expected_duration * 2:
		quality_score = max(0.0, quality_score - 10)
	elif duration > expected_duration * 1.5:
		quality_score = max(0.0, quality_score - 5)

	# 确定质量等级
	if quality_score >= 95:
		quality_level = "excellent"
	elif quality_score >= 85:
		quality_level = "good"
	elif quality_score >= 70:
		quality_level = "fair"
	else:
		quality_level = "poor"

	return {
		"score": round(quality_score, 1),
		"level": quality_level,
		"assessment": AccountSettlementCompletedEvent.get_quality_assessment(quality_level)
	}


class AccountSettlementCompletedEvent(BaseEvent):
	"""
	账户结算完成事件

	触发时机：
	- 结算任务完成
	- 所有结算步骤执行完毕

	事件数据：
	- settlement_result: 结算结果摘要
	- statistics: 结算统计信息
	- issues: 结算过程中发现的问题
	- report_url: 结算报告地址
	"""

	def __init__ (
			self,
			settlement_date: date,
			settlement_type: str,
			total_accounts: int,
			successful_accounts: int,
			failed_accounts: int,
			settlement_statistics: Dict[str, Any],
			duration_seconds: float,
			report_path: Optional[str] = None,
			issues: Optional[List[Dict[str, Any]]] = None,
			**kwargs
	):
		super().__init__(
			module="events",
			event_type=AccountEventType.SETTLEMENT_COMPLETED.value,
			priority=EventPriority.NORMAL,
			source="settlement_engine",
			**kwargs
		)

		# 计算成功率
		success_rate = (successful_accounts / total_accounts * 100) if total_accounts > 0 else 0

		self.data = {
			"settlement_date": settlement_date.isoformat(),
			"settlement_type": settlement_type,
			"total_accounts": total_accounts,
			"successful_accounts": successful_accounts,
			"failed_accounts": failed_accounts,
			"success_rate": round(success_rate, 2),
			"settlement_statistics": settlement_statistics,
			"duration_seconds": round(duration_seconds, 2),
			"report_path": report_path,
			"issues": issues or [],
			"completion_time": datetime.now().isoformat(),
			"settlement_quality": _assess_settlement_quality(success_rate, issues, duration_seconds),
			"recommendations": AccountSettlementCompletedEvent._generate_recommendations(success_rate, issues)
		}

	@staticmethod
	def get_quality_assessment (quality_level: str) -> str:
		"""获取质量评估描述"""
		assessments = {
			"excellent": "结算过程完美，所有账户成功结算",
			"good": "结算过程良好，少数账户需要关注",
			"fair": "结算过程一般，有多个问题需要解决",
			"poor": "结算过程较差，需要立即关注和改进"
		}
		return assessments.get(quality_level, "未知质量等级")

	@staticmethod
	def _generate_recommendations (success_rate: float, issues: List[Dict[str, Any]]) -> List[str]:
		"""生成改进建议"""
		recommendations = []

		if success_rate < 100:
			recommendations.append(f"结算成功率{success_rate:.1f}%，需要检查失败账户")

		if issues:
			critical_issues = [issue for issue in issues if issue.get("severity") == "critical"]
			if critical_issues:
				recommendations.append(f"发现{len(critical_issues)}个严重问题，需要优先处理")

			warning_issues = [issue for issue in issues if issue.get("severity") == "warning"]
			if warning_issues:
				recommendations.append(f"发现{len(warning_issues)}个警告问题，建议及时处理")

		if not recommendations:
			recommendations.append("结算过程顺利，继续保持")

		return recommendations
