# risk_tasks.py        # 风控任务

import asyncio
from datetime import datetime
from typing import Dict, Any

from core.engines.system import EventEngine
from modules.trade.engines.position_engine import PositionEngine
from modules.trade.engines.risk_engine import RiskEngine
from modules.trade.events.risk_events import RiskAlertEvent


class RiskTasks:
	"""风控任务类"""

	def __init__ (
			self,
			risk_engine: RiskEngine,
			position_engine: PositionEngine,
			event_engine: EventEngine
	):
		"""
		初始化风控任务

		Args:
			risk_engine: 风险引擎
			position_engine: 持仓引擎
			event_engine: 事件引擎
		"""
		self.risk_engine = risk_engine
		self.position_engine = position_engine
		self.event_engine = event_engine
		self.tasks = []

	async def start (self):
		"""启动风控任务"""
		# 启动定期风险检查任务
		self.tasks.append(asyncio.create_task(self._regular_risk_check()))
		# 启动持仓风险检查任务
		self.tasks.append(asyncio.create_task(self._position_risk_check()))
		# 启动账户风险检查任务
		self.tasks.append(asyncio.create_task(self._account_risk_check()))

	async def stop (self):
		"""停止风控任务"""
		for task in self.tasks:
			task.cancel()
		await asyncio.gather(*self.tasks, return_exceptions=True)

	async def _regular_risk_check (self):
		"""定期风险检查"""
		while True:
			try:
				# 每30秒进行一次风险检查
				await asyncio.sleep(30)
				await self.check_all_risks()
			except asyncio.CancelledError:
				break
			except Exception as e:
				print(f"定期风险检查出错: {str(e)}")

	async def _position_risk_check (self):
		"""持仓风险检查"""
		while True:
			try:
				# 每60秒检查一次持仓风险
				await asyncio.sleep(60)
				await self.check_position_risks()
			except asyncio.CancelledError:
				break
			except Exception as e:
				print(f"持仓风险检查出错: {str(e)}")

	async def _account_risk_check (self):
		"""账户风险检查"""
		while True:
			try:
				# 每120秒检查一次账户风险
				await asyncio.sleep(120)
				await self.check_account_risks()
			except asyncio.CancelledError:
				break
			except Exception as e:
				print(f"账户风险检查出错: {str(e)}")

	async def check_all_risks (self):
		"""检查所有风险"""
		# 检查持仓风险
		await self.check_position_risks()
		# 检查账户风险
		await self.check_account_risks()

	async def check_position_risks (self):
		"""检查持仓风险"""
		try:
			# 获取持仓风险
			risks = await self.risk_engine.check_position_risk()

			# 处理风险
			for risk in risks:
				# 发布风险预警事件
				if self.event_engine:
					event = RiskAlertEvent(
						risk_type=risk.get("risk_type"),
						risk_level=risk.get("level"),
						message=risk.get("message")
					)
					await self.event_engine.put(event)
		except Exception as e:
			print(f"检查持仓风险出错: {str(e)}")

	async def check_account_risks (self):
		"""检查账户风险"""
		try:
			# 获取账户信息
			account = await self.position_engine.get_account()

			# 检查账户余额
			available_cash = self.position_engine.get_available_cash()
			if available_cash < 1000:
				# 发布资金不足预警
				if self.event_engine:
					event = RiskAlertEvent(
						risk_type="account_balance",
						risk_level="warning",
						message=f"账户可用资金不足: {available_cash:.2f}"
					)
					await self.event_engine.put(event)
		except Exception as e:
			print(f"检查账户风险出错: {str(e)}")

	async def generate_risk_report (self) -> Dict[str, Any]:
		"""生成风险报告"""
		try:
			# 获取持仓风险
			position_risks = await self.risk_engine.check_position_risk()

			# 获取账户信息
			account = await self.position_engine.get_account()

			# 生成报告
			report = {
				"timestamp": datetime.now().isoformat(),
				"account": account,
				"position_risks": position_risks,
				"total_risks": len(position_risks)
			}

			return report
		except Exception as e:
			print(f"生成风险报告出错: {str(e)}")
			return {
				"timestamp": datetime.now().isoformat(),
				"error": str(e)
			}