# -*- coding: utf-8 -*-
"""
回测模块API处理函数
负责处理HTTP请求，调用服务层完成业务逻辑
"""
from typing import Dict, Any

from fastapi import HTTPException
from sqlalchemy.ext.asyncio import AsyncSession

from modules.backtest.services.backtest_service import BacktestService


class BacktestHandler:
	"""回测API处理器"""

	def __init__ (self, db: AsyncSession):
		self.db = db
		self.backtest_service = BacktestService(db)

	async def create_backtest_task (self, request, user_id: str, background_tasks) -> Dict[str, Any]:
		"""创建回测任务"""
		try:
			result = await self.backtest_service.create_backtest_task(request, user_id)
			# 添加后台任务执行回测
			background_tasks.add_task(self.backtest_service.run_backtest, result["task_id"])
			return {
				"success": True,
				"data": result
			}
		except Exception as e:
			raise HTTPException(status_code=500, detail=f"创建回测任务失败: {str(e)}")

	async def get_backtest_task (self, task_id: str, user_id: str) -> Dict[str, Any]:
		"""获取回测任务详情"""
		try:
			result = await self.backtest_service.get_backtest_task(task_id, user_id)
			return {
				"success": True,
				"data": result
			}
		except ValueError as e:
			raise HTTPException(status_code=404, detail=str(e))
		except Exception as e:
			raise HTTPException(status_code=500, detail=f"获取回测任务详情失败: {str(e)}")

	async def get_backtest_task_list (self, request, user_id: str) -> Dict[str, Any]:
		"""获取回测任务列表"""
		try:
			result = await self.backtest_service.get_backtest_task_list(request, user_id)
			return {
				"success": True,
				"data": result["data"],
				"pagination": result["pagination"]
			}
		except Exception as e:
			raise HTTPException(status_code=500, detail=f"获取回测任务列表失败: {str(e)}")

	async def cancel_backtest_task (self, task_id: str, user_id: str) -> Dict[str, Any]:
		"""取消回测任务"""
		try:
			result = await self.backtest_service.cancel_backtest_task(task_id, user_id)
			return {
				"success": True,
				"data": result
			}
		except Exception as e:
			raise HTTPException(status_code=500, detail=f"取消回测任务失败: {str(e)}")

	async def get_backtest_equity_curve (self, task_id: str, user_id: str) -> Dict[str, Any]:
		"""获取回测净值曲线"""
		try:
			result = await self.backtest_service.get_backtest_equity_curve(task_id, user_id)
			return {
				"success": True,
				"data": result
			}
		except Exception as e:
			raise HTTPException(status_code=500, detail=f"获取回测净值曲线失败: {str(e)}")

	async def get_backtest_trades (self, task_id: str, user_id: str,
		                                   page: int = 1, page_size: int = 20) -> Dict[str, Any]:
		"""获取回测交易记录"""
		try:
			result = await self.backtest_service.get_backtest_trades(task_id, user_id, page=page, page_size=page_size)
			return {
				"success": True,
				"data": result["data"],
				"pagination": result["pagination"]
			}
		except Exception as e:
			raise HTTPException(status_code=500, detail=f"获取回测交易记录失败: {str(e)}")

	async def get_backtest_positions (self, task_id: str, trade_date: str, user_id: str) -> Dict[str, Any]:
		"""获取回测持仓快照"""
		try:
			result = await self.backtest_service.get_backtest_positions(task_id, trade_date, user_id)
			return {
				"success": True,
				"data": result
			}
		except Exception as e:
			raise HTTPException(status_code=500, detail=f"获取回测持仓快照失败: {str(e)}")

	async def get_backtest_result (self, task_id: str, user_id: str) -> Dict[str, Any]:
		"""获取回测结果"""
		try:
			result = await self.backtest_service.get_backtest_result(task_id, user_id)
			return {
				"success": True,
				"data": result
			}
		except ValueError as e:
			# 预期内状态（任务不存在/无权限），正常返回；进行中任务已在 service 层处理
			msg = str(e)
			if "不存在" in msg:
				raise HTTPException(status_code=404, detail=msg)
			if "权限" in msg:
				raise HTTPException(status_code=403, detail=msg)
			raise HTTPException(status_code=400, detail=msg)
		except Exception as e:
			raise HTTPException(status_code=500, detail=f"获取回测结果失败: {str(e)}")

	async def export_report(self, task_id: str, user_id: str, report_format: str = 'json') -> Dict[str, Any]:
		"""导出回测报告"""
		try:
			result = await self.backtest_service.export_report(task_id, user_id, report_format)
			return {"success": True, "data": result}
		except Exception as e:
			raise HTTPException(status_code=500, detail=f"导出报告失败: {str(e)}")

	async def quick_backtest(self, request, user_id: str) -> Dict[str, Any]:
		"""快速回测：创建任务 + 执行 + 返回结果（同步等待）"""
		try:
			result = await self.backtest_service.quick_backtest(request, user_id)
			return {"success": True, "data": result}
		except Exception as e:
			raise HTTPException(status_code=500, detail=f"快速回测失败: {str(e)}")

	async def delete_backtest_task(self, task_id: str, user_id: str) -> Dict[str, Any]:
		"""删除回测任务（级联删除关联数据）"""
		try:
			await self.backtest_service.delete_backtest_task(task_id, user_id)
			return {"success": True, "data": {"task_id": task_id}}
		except Exception as e:
			raise HTTPException(status_code=500, detail=f"删除回测任务失败: {str(e)}")

	async def optimize_parameters(self, request) -> Dict[str, Any]:
		"""参数优化"""
		try:
			result = await self.backtest_service.optimize_parameters(request)
			return {"success": True, "data": result}
		except Exception as e:
			raise HTTPException(status_code=500, detail=f"参数优化失败: {str(e)}")


# 导出函数供router使用
async def export_backtest_report(session: AsyncSession, task_id: str, user_id: str, report_format: str = 'json'):
	handler = BacktestHandler(session)
	return await handler.export_report(task_id, user_id, report_format)


async def quick_backtest(session: AsyncSession, request, user_id: str):
	handler = BacktestHandler(session)
	return await handler.quick_backtest(request, user_id)


async def delete_backtest_task(session: AsyncSession, task_id: str, user_id: str):
	handler = BacktestHandler(session)
	return await handler.delete_backtest_task(task_id, user_id)


async def create_backtest_task (session: AsyncSession, request, user_id: str, background_tasks):
	handler = BacktestHandler(session)
	return await handler.create_backtest_task(request, user_id, background_tasks)


async def get_backtest_task (session: AsyncSession, task_id: str, user_id: str):
	handler = BacktestHandler(session)
	return await handler.get_backtest_task(task_id, user_id)


async def get_backtest_task_list (session: AsyncSession, request, user_id: str):
	handler = BacktestHandler(session)
	return await handler.get_backtest_task_list(request, user_id)


async def cancel_backtest_task (session: AsyncSession, task_id: str, user_id: str):
	handler = BacktestHandler(session)
	return await handler.cancel_backtest_task(task_id, user_id)


async def get_backtest_equity_curve (session: AsyncSession, task_id: str, user_id: str):
	handler = BacktestHandler(session)
	return await handler.get_backtest_equity_curve(task_id, user_id)


async def get_backtest_trades (session: AsyncSession, task_id: str, user_id: str,
	                                  page: int = 1, page_size: int = 20):
	handler = BacktestHandler(session)
	return await handler.get_backtest_trades(task_id, user_id, page=page, page_size=page_size)


async def get_backtest_positions (session: AsyncSession, task_id: str, trade_date: str, user_id: str):
	handler = BacktestHandler(session)
	return await handler.get_backtest_positions(task_id, trade_date, user_id)


async def get_backtest_result (session: AsyncSession, task_id: str, user_id: str):
	handler = BacktestHandler(session)
	return await handler.get_backtest_result(task_id, user_id)


async def optimize_backtest_parameters (session: AsyncSession, request):
	handler = BacktestHandler(session)
	return await handler.optimize_parameters(request)


async def check_backtest_module_health(_session = None) -> Dict[str, Any]:
	"""检查回测模块健康状态"""
	from datetime import datetime, timezone

	if _session is not None:
		try:
			from sqlalchemy import text
			await _session.execute(text("SELECT 1"))
		except Exception as e:
			return {
				"status": "unhealthy",
				"module": "backtest",
				"error": str(e),
				"timestamp": datetime.now(timezone.utc).isoformat(),
			}

	return {
		"status": "healthy",
		"module": "backtest",
		"timestamp": datetime.now(timezone.utc).isoformat(),
	}