# base_rule.py         # 规则基类

from abc import ABC, abstractmethod
from typing import Dict, Any, Tuple


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
		检查规则

		Args:
			data: 检查数据

		Returns:
			(是否通过, 消息)
		"""
		pass

	def get_name (self) -> str:
		"""获取规则名称"""
		return self.name

	def get_description (self) -> str:
		"""获取规则描述"""
		return self.description
