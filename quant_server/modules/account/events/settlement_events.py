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


class AccountReconciliationStartedEvent(BaseEvent):
	"""
	账户对账开始事件

	触发时机：
	- 启动资金或持仓对账
	- 定时对账任务开始

	事件数据：
	- reconciliation_type: 对账类型（资金/持仓/交易）
	- reconciliation_scope: 对账范围
	- data_sources: 数据源信息
	"""

	def __init__ (
			self,
			reconciliation_id: str,
			reconciliation_type: str,
			reconciliation_scope: str = "all",
			data_sources: Optional[List[Dict[str, str]]] = None,
			**kwargs
	):
		super().__init__(
			module="events",
			event_type="events.reconciliation.started",  # 自定义事件类型
			priority=EventPriority.NORMAL,
			source="reconciliation_service",
			**kwargs
		)

		if data_sources is None:
			data_sources = [
				{"name": "交易系统", "type": "internal"},
				{"name": "券商系统", "type": "external"}
			]

		self.data = {
			"reconciliation_id": reconciliation_id,
			"reconciliation_type": reconciliation_type,
			"reconciliation_scope": reconciliation_scope,
			"data_sources": data_sources,
			"start_time": datetime.now().isoformat(),
			"expected_records": self._estimate_record_count(reconciliation_type, reconciliation_scope),
			"matching_rules": AccountReconciliationStartedEvent._get_matching_rules(reconciliation_type),
			"tolerance_settings": AccountReconciliationStartedEvent._get_tolerance_settings(reconciliation_type)
		}

	def _estimate_record_count (self, recon_type: str, scope: str) -> Dict[str, int]:
		"""估计对账记录数量"""
		base_counts = {
			"fund": 100,
			"position": 500,
			"events": 1000
		}

		base_count = base_counts.get(recon_type, 100)

		# 根据范围调整
		multiplier = 1
		if scope == "all":
			multiplier = 10
		elif scope == "daily":
			multiplier = 1
		elif scope == "monthly":
			multiplier = 30

		return {
			"estimated_total": base_count * multiplier,
			"estimated_per_source": base_count * multiplier // len(self.data["data_sources"])
		}

	@staticmethod
	def _get_matching_rules (recon_type: str) -> List[Dict[str, Any]]:
		"""获取对账匹配规则"""
		common_rules = [
			{"field": "account_id", "rule": "exact_match", "required": True},
			{"field": "date", "rule": "exact_match", "required": True}
		]

		type_specific_rules = {
			"fund": [
				{"field": "balance", "rule": "numeric_within_tolerance", "tolerance": 0.01},
				{"field": "currency", "rule": "exact_match", "required": True}
			],
			"position": [
				{"field": "symbol", "rule": "exact_match", "required": True},
				{"field": "quantity", "rule": "numeric_within_tolerance", "tolerance": 0.001},
				{"field": "cost", "rule": "numeric_within_tolerance", "tolerance": 0.01}
			],
			"events": [
				{"field": "trade_id", "rule": "exact_match", "required": True},
				{"field": "execution_price", "rule": "numeric_within_tolerance", "tolerance": 0.0001},
				{"field": "quantity", "rule": "exact_match", "required": True}
			]
		}

		rules = common_rules + type_specific_rules.get(recon_type, [])
		return rules

	@staticmethod
	def _get_tolerance_settings (recon_type: str) -> Dict[str, Any]:
		"""获取对账容差设置"""
		tolerances = {
			"fund": {
				"amount_tolerance": 0.01,  # 1分钱
				"percentage_tolerance": 0.0001,  # 0.01%
				"time_tolerance": 300  # 5分钟
			},
			"position": {
				"quantity_tolerance": 0.001,  # 千分之一
				"price_tolerance": 0.01,  # 1分钱
				"value_tolerance": 0.001  # 千分之一
			},
			"events": {
				"price_tolerance": 0.0001,  # 万分之一
				"quantity_tolerance": 0,
				"time_tolerance": 60  # 1分钟
			}
		}

		return tolerances.get(recon_type, {
			"amount_tolerance": 0.01,
			"percentage_tolerance": 0.001,
			"time_tolerance": 300
		})


class AccountReconciliationCompletedEvent(BaseEvent):
	"""
	账户对账完成事件

	触发时机：
	- 对账任务完成
	- 所有对账记录处理完毕

	事件数据：
	- reconciliation_result: 对账结果摘要
	- discrepancies: 差异记录
	- match_rate: 匹配率
	- resolution_status: 差异解决状态
	"""

	def __init__ (
			self,
			reconciliation_id: str,
			reconciliation_type: str,
			total_records: int,
			matched_records: int,
			unmatched_records: int,
			discrepancies: List[Dict[str, Any]],
			duration_seconds: float,
			resolution_status: str = "pending",
			**kwargs
	):
		super().__init__(
			module="events",
			event_type="events.reconciliation.completed",  # 自定义事件类型
			priority=EventPriority.NORMAL,
			source="reconciliation_service",
			**kwargs
		)

		# 计算匹配率
		match_rate = (matched_records / total_records * 100) if total_records > 0 else 0

		# 分析差异
		discrepancy_analysis = AccountReconciliationCompletedEvent._analyze_discrepancies(discrepancies)

		self.data = {
			"reconciliation_id": reconciliation_id,
			"reconciliation_type": reconciliation_type,
			"total_records": total_records,
			"matched_records": matched_records,
			"unmatched_records": unmatched_records,
			"match_rate": round(match_rate, 2),
			"discrepancies": discrepancies,
			"discrepancy_analysis": discrepancy_analysis,
			"duration_seconds": round(duration_seconds, 2),
			"resolution_status": resolution_status,
			"completion_time": datetime.now().isoformat(),
			"reconciliation_status": AccountReconciliationCompletedEvent._determine_reconciliation_status(match_rate, discrepancies),
			"next_steps": AccountReconciliationCompletedEvent._determine_next_steps(match_rate, discrepancies, resolution_status)
		}

	@staticmethod
	def _analyze_discrepancies (discrepancies: List[Dict[str, Any]]) -> Dict[str, Any]:
		"""分析差异记录"""
		total_discrepancies = len(discrepancies)

		if total_discrepancies == 0:
			return {
				"total": 0,
				"by_severity": {},
				"by_type": {},
				"total_amount": 0
			}

		# 按严重程度分类
		by_severity = {}
		# 按差异类型分类
		by_type = {}
		# 总差异金额
		total_amount = 0

		for disc in discrepancies:
			severity = disc.get("severity", "unknown")
			disc_type = disc.get("type", "unknown")
			amount = disc.get("amount", 0)

			by_severity[severity] = by_severity.get(severity, 0) + 1
			by_type[disc_type] = by_type.get(disc_type, 0) + 1
			total_amount += amount

		return {
			"total": total_discrepancies,
			"by_severity": by_severity,
			"by_type": by_type,
			"total_amount": round(total_amount, 2)
		}

	@staticmethod
	def _determine_reconciliation_status (match_rate: float, discrepancies: List[Dict[str, Any]]) -> str:
		"""确定对账状态"""
		if match_rate == 100:
			return "perfect"
		elif match_rate >= 99:
			return "good"
		elif match_rate >= 95:
			# 检查是否有严重差异
			critical_discrepancies = [d for d in discrepancies if d.get("severity") == "critical"]
			if critical_discrepancies:
				return "needs_attention"
			else:
				return "acceptable"
		elif match_rate >= 90:
			return "needs_attention"
		else:
			return "failed"

	@staticmethod
	def _determine_next_steps (match_rate: float, discrepancies: List[Dict[str, Any]], resolution_status: str) -> \
			List[str]:
		"""确定下一步行动"""
		steps = []

		if match_rate < 100:
			steps.append(f"发现{len(discrepancies)}条差异记录，需要人工核对")

		critical_discrepancies = [d for d in discrepancies if d.get("severity") == "critical"]
		if critical_discrepancies:
			steps.append(f"发现{len(critical_discrepancies)}条严重差异，需要立即处理")

		if resolution_status == "pending" and discrepancies:
			steps.append("差异记录待处理，请及时解决")

		if match_rate >= 99.9 and not critical_discrepancies:
			steps.append("对账质量良好，可自动归档")

		if not steps:
			steps.append("对账完成，无需进一步操作")

		return steps