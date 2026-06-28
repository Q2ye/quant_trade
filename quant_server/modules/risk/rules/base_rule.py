# base_rule.py         # 规则基类

from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from typing import Dict, Any, Tuple, Optional


@dataclass
class RiskCheckResult:
	"""风控规则检查结果

	Attributes:
		passed: 是否通过
		severity: 严重级别 (info | warning | error | critical)
		message: 检查消息
		action: 建议动作 (allow | reduce_size | block | kill)
		rule_name: 规则名称
	"""
	passed: bool
	severity: str = "error"
	message: str = ""
	action: str = "block"
	rule_name: str = ""

	def __post_init__(self):
		"""根据 severity 自动推导 action（如未显式指定）"""
		if self.action == "block" and self.severity != "error":
			_severity_action_map = {
				"info": "allow",
				"warning": "reduce_size",
				"error": "block",
				"critical": "kill",
			}
			self.action = _severity_action_map.get(self.severity, "block")


class RiskRule(ABC):
	"""风险规则抽象基类"""

	def __init__ (self, name: str, description: str):
		"""
		初始化风险规则

		Args:
			name: 规则名称
			description: 规则描述
		"""
		self.name = name
		self.description = description

	@abstractmethod
	async def check (self, data: Dict[str, Any]) -> Tuple[bool, str]:
		"""
		检查规则（二元 pass/fail，向后兼容）

		Args:
			data: 检查数据

		Returns:
			(是否通过, 消息)
		"""
		pass

	async def check_with_severity(self, data: Dict[str, Any]) -> RiskCheckResult:
		"""
		带严重级别的规则检查（子类可覆盖以返回非默认 severity）

		默认行为：调用 check()，根据 passed 映射 severity=error/空。
		子类覆盖此方法可返回 info/warning/error/critical。

		Args:
			data: 检查数据

		Returns:
			RiskCheckResult
		"""
		passed, message = await self.check(data)
		return RiskCheckResult(
			passed=passed,
			severity="error" if not passed else "info",
			message=message,
			rule_name=self.name,
		)

	def get_name (self) -> str:
		"""获取规则名称"""
		return self.name

	def get_description (self) -> str:
		"""获取规则描述"""
		return self.description

	def get_params(self) -> Dict[str, Any]:
		"""获取规则的可配置参数（子类可覆盖）"""
		params = {}
		for attr in dir(self):
			if attr.startswith("_") or attr in ("name", "description"):
				continue
			val = getattr(self, attr)
			if callable(val) or isinstance(val, type):
				continue
			if isinstance(val, (int, float, str, bool, list, dict)):
				params[attr] = val
		return params

	def get_inputs(self) -> list:
		"""获取规则所需的输入字段（子类应覆盖）"""
		return []
