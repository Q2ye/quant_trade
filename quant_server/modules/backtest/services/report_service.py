# -*- coding: utf-8 -*-
"""
报告服务

负责生成回测报告
"""
import logging
from typing import Dict, Any

from sqlalchemy.ext.asyncio import AsyncSession

from core.engines.types.entities import EngineConfigEntity
from modules.backtest.engines.report_engine import ReportEngine
from shared.database.repositories import BacktestEquityCurveRepository
from shared.database.repositories.strategy.backtest.task_repo import BacktestTaskRepository
from shared.database.repositories.strategy.backtest.trade_repo import BacktestTradeRepository
from shared.database.repositories.strategy.backtest.position_repo import BacktestPositionRepository

logger = logging.getLogger(__name__)


class ReportService:
	"""
	报告服务

	负责生成回测报告
	"""

	def __init__ (self, db: AsyncSession):
		"""
		初始化报告服务

		Args:
			db: 数据库会话
		"""
		self.db = db

		# 导入EngineConfig

		self.report_engine = ReportEngine(EngineConfigEntity(name="ReportEngine", engine_type="report"))

	async def generate_report (self, backtest_id: str) -> Dict[str, Any]:
		"""
		生成回测报告

		Args:
			backtest_id: 回测任务ID

		Returns:
			回测报告
		"""
		try:
			logger.info(f"生成回测报告: backtest_id={backtest_id}")

			# 初始化仓库
			task_repo = BacktestTaskRepository(self.db)
			trade_repo = BacktestTradeRepository(self.db)
			equity_curve_repo = BacktestEquityCurveRepository(self.db)
			position_repo = BacktestPositionRepository(self.db)

			# 获取回测任务
			task = await task_repo.get(str(backtest_id))
			if not task:
				raise ValueError(f"回测任务不存在: {backtest_id}")

			# 检查任务状态
			if task.status != "completed":
				raise ValueError(f"回测任务尚未完成，当前状态: {task.status}")

			# 获取回测结果数据
			backtest_result = {}

			# 1. 从任务结果中获取基础指标
			if task.result:
				backtest_result["metrics"] = task.result.get("metrics", {})
			else:
				backtest_result["metrics"] = {}

			# 2. 获取交易记录
			trades = await trade_repo.get_by_task_id(str(backtest_id))
			backtest_result["trades"] = [
				{
					"symbol": trade.ts_code,
					"side": trade.direction,
					"price": float(trade.price),
					"quantity": trade.volume,
					"datetime": trade.trade_time.isoformat() if trade.trade_time else "",
					"profit": float(trade.profit) if hasattr(trade, 'profit') else 0.0,
					"commission": float(trade.commission) if hasattr(trade, 'commission') else 0.0
				}
				for trade in trades
			]

			# 3. 获取净值曲线
			equity_curves = await equity_curve_repo.get_equity_curve(str(backtest_id))
			backtest_result["equity_curve"] = [
				{
					"date": curve.trade_date.isoformat() if curve.trade_date else "",
					"equity": float(curve.equity),
					"drawdown": float(curve.drawdown) if hasattr(curve, 'drawdown') else 0.0
				}
				for curve in equity_curves
			]

			# 4. 获取持仓快照（可选）
			try:
				positions = await position_repo.get_by_task_id(str(backtest_id))
				backtest_result["positions"] = [
					{
						"symbol": position.ts_code,
						"volume": position.volume,
						"cost_price": float(position.cost_price),
						"current_price": float(position.current_price) if hasattr(position, 'current_price') else 0.0,
						"profit": float(position.profit) if hasattr(position, 'profit') else 0.0
					}
					for position in positions
				]
			except Exception as e:
				logger.warning(f"获取持仓数据失败: {str(e)}")
				backtest_result["positions"] = []

			# 5. 补充缺失的指标（如果任务结果中没有）
			if not backtest_result["metrics"]:
				# 计算基础指标
				if backtest_result["equity_curve"]:
					initial_equity = backtest_result["equity_curve"][0]["equity"]
					final_equity = backtest_result["equity_curve"][-1]["equity"]
					total_return = (final_equity - initial_equity) / initial_equity
					
					# 计算最大回撤
					max_equity = initial_equity
					max_drawdown = 0.0
					for point in backtest_result["equity_curve"]:
						if point["equity"] > max_equity:
							max_equity = point["equity"]
						drawdown = (max_equity - point["equity"]) / max_equity
						if drawdown > max_drawdown:
							max_drawdown = drawdown
					
					# 计算胜率和盈亏比
					trades_list = backtest_result["trades"]
					if trades_list:
						winning_trades = [t for t in trades_list if t.get("profit", 0) > 0]
						win_rate = len(winning_trades) / len(trades_list)
						gross_profit = sum(t.get("profit", 0) for t in trades_list if t.get("profit", 0) > 0)
						gross_loss = abs(sum(t.get("profit", 0) for t in trades_list if t.get("profit", 0) < 0))
						profit_factor = gross_profit / gross_loss if gross_loss > 0 else (gross_profit if gross_profit > 0 else 0.0)
					else:
						win_rate = 0.0
						profit_factor = 0.0

					backtest_result["metrics"] = {
						"total_return": total_return,
						"max_drawdown": max_drawdown,
						"num_trades": len(backtest_result["trades"]),
						"win_rate": win_rate,
						"profit_factor": profit_factor
					}

			# 生成报告
			report = self.report_engine.generate_report(backtest_result)

			logger.info(f"回测报告生成成功: backtest_id={backtest_id}")
			return report
		except Exception as e:
			logger.error(f"生成回测报告失败: {str(e)}")
			raise

	async def get_report (self, backtest_id: str) -> Dict[str, Any]:
		"""
		获取回测报告

		Args:
			backtest_id: 回测任务ID

		Returns:
			回测报告
		"""
		try:
			logger.info(f"获取回测报告: backtest_id={backtest_id}")

			# 初始化仓库
			task_repo = BacktestTaskRepository(self.db)

			# 获取回测任务
			task = await task_repo.get(str(backtest_id))
			if not task:
				raise ValueError(f"回测任务不存在: {backtest_id}")

			# 检查任务状态
			if task.status != "completed":
				raise ValueError(f"回测任务尚未完成，当前状态: {task.status}")

			# 如果任务结果中已经有报告，直接返回
			if task.result and "report" in task.result:
				logger.info(f"从任务结果中获取回测报告: backtest_id={backtest_id}")
				return task.result["report"]

			# 如果任务结果中没有报告，但包含回测数据，则生成报告
			if task.result and "metrics" in task.result:
				logger.info(f"从任务结果数据生成回测报告: backtest_id={backtest_id}")
				return self.report_engine.generate_report(task.result)

			# 如果任务结果中没有足够的数据，则重新生成报告
			logger.info(f"重新生成回测报告: backtest_id={backtest_id}")
			return await self.generate_report(backtest_id)
		except Exception as e:
			logger.error(f"获取回测报告失败: {str(e)}")
			raise