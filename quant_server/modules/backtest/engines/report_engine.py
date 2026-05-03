# -*- coding: utf-8 -*-
"""
报告生成引擎

负责:
- 生成回测报告
- 计算绩效指标
- 生成图表数据
- 导出报告
"""
import json
import logging
from datetime import datetime
from typing import Dict, List, Any

import pandas as pd

from core.engines.base.engine_base import EngineBase
from modules.backtest.analyzers.performance_analyzer import PerformanceAnalyzer
from modules.backtest.analyzers.risk_analyzer import RiskAnalyzer
from modules.backtest.analyzers.trade_analyzer import TradeAnalyzer
from modules.backtest.utils.chart_generator import ChartGenerator

logger = logging.getLogger(__name__)


class ReportEngine(EngineBase):
	"""
	报告生成引擎

	负责生成回测报告
	"""

	def __init__ (self, config, event_engine=None, resource_pool=None):
		"""
		初始化报告生成引擎
		"""
		super().__init__(config=config, event_engine=event_engine, resource_pool=resource_pool)

		# 分析器
		self.performance_analyzer = PerformanceAnalyzer()
		self.risk_analyzer = RiskAnalyzer()
		self.trade_analyzer = TradeAnalyzer()

		# 图表生成器
		self.chart_generator = ChartGenerator()

	async def _on_initialize (self):
		"""
		引擎初始化逻辑
		"""
		logger.info(f"报告生成引擎 {self.config.name} 初始化")
		# 初始化分析器
		self.performance_analyzer = PerformanceAnalyzer()
		self.risk_analyzer = RiskAnalyzer()
		self.trade_analyzer = TradeAnalyzer()
		# 初始化图表生成器
		self.chart_generator = ChartGenerator()

	async def _on_start(self):
		"""
		引擎启动逻辑
		"""
		logger.info(f"报告生成引擎 {self.config.name} 启动")

	async def _on_stop (self):
		"""
		引擎停止逻辑
		"""
		logger.info(f"报告生成引擎 {self.config.name} 停止")

	async def _on_pause (self):
		"""
		引擎暂停逻辑
		"""
		logger.info(f"报告生成引擎 {self.config.name} 暂停")

	async def _on_resume (self):
		"""
		引擎恢复逻辑
		"""
		logger.info(f"报告生成引擎 {self.config.name} 恢复")

	async def _on_force_stop (self):
		"""
		引擎强制停止逻辑
		"""
		logger.warning(f"报告生成引擎 {self.config.name} 强制停止")

	async def _on_health_check (self) -> Dict[str, Any]:
		"""
		健康检查逻辑
		"""
		return {
			"analyzers_initialized": 3,  # 性能、风险、交易分析器
			"chart_generator_ready": True
		}

	def _validate_config (self):
		"""
		验证配置
		"""
		if not self.config:
			raise ValueError("报告生成引擎配置不能为空")

	def generate_report (self, backtest_result: Dict[str, Any]) -> Dict[str, Any]:
		"""
		生成回测报告

		Args:
			backtest_result: 回测结果

		Returns:
			回测报告
		"""
		try:
			logger.info("开始生成回测报告")

			# 提取数据
			metrics = backtest_result.get("metrics", {})
			trades = backtest_result.get("trades", [])
			equity_curve = backtest_result.get("equity_curve", [])

			# 计算绩效指标
			performance_metrics = self.performance_analyzer.analyze(metrics, trades)

			# 计算风险指标
			risk_metrics = self.risk_analyzer.analyze(metrics, equity_curve)

			# 分析交易
			trade_analysis = self.trade_analyzer.analyze(trades)

			# 生成图表数据
			charts = self.generate_charts(equity_curve, trades)

			# 生成报告
			report = {
				"summary": {
					"total_return": metrics.get("total_return", 0.0),
					"annualized_return": metrics.get("annualized_return", 0.0),
					"sharpe_ratio": metrics.get("sharpe_ratio", 0.0),
					"max_drawdown": metrics.get("max_drawdown", 0.0),
					"win_rate": metrics.get("win_rate", 0.0),
					"profit_factor": metrics.get("profit_factor", 0.0),
					"num_trades": metrics.get("num_signals", 0),
					"duration_days": metrics.get("duration_days", 0)
				},
				"performance": performance_metrics,
				"risk": risk_metrics,
				"trade_analysis": trade_analysis,
				"charts": charts,
				"timestamp": datetime.now().isoformat()
			}

			logger.info("回测报告生成完成")

			return report
		except Exception as e:
			logger.error(f"生成回测报告失败: {str(e)}")
			raise

	def generate_charts (self, equity_curve: List[Dict[str, Any]], trades: List[Dict[str, Any]]) -> Dict[str, Any]:
		"""
		生成图表数据

		Args:
			equity_curve: 净值曲线
			trades: 交易记录

		Returns:
			图表数据
		"""
		try:
			charts = {}

			# 净值曲线
			if equity_curve:
				charts["equity_curve"] = self.chart_generator.generate_equity_curve(equity_curve)
			
			# 回撤曲线
			if equity_curve:
				charts["drawdown_curve"] = self.chart_generator.generate_drawdown(equity_curve)
			
			# 收益分布
			if trades:
				profits = [trade.get("profit", 0) for trade in trades]
				charts["profit_distribution"] = self.chart_generator.generate_returns_distribution(profits)

			return charts
		except Exception as e:
			logger.error(f"生成图表数据失败: {str(e)}")
			return {}

	@staticmethod
	def export_report (report: Dict[str, Any], export_format: str = "json") -> Any:
		"""
		导出报告

		Args:
			report: 回测报告
			export_format: 导出格式 (json/csv)

		Returns:
			导出结果
		"""
		try:
			if export_format == "json":
				return json.dumps(report, ensure_ascii=False, indent=2)
			elif export_format == "csv":
				# 转换为CSV格式
				csv_data = [["摘要", "", ""], ["指标", "值", "单位"]]
				# 导出摘要
				for key, value in report["summary"].items():
					csv_data.append([key, value, ""])

				# 导出交易记录
				if "trade_analysis" in report and "trades" in report["trade_analysis"]:
					csv_data.append([])
					csv_data.append(["交易记录", "", ""])
					csv_data.append(["日期", "标的", "方向", "价格", "数量", "收益"])
					for trade in report["trade_analysis"]["trades"]:
						csv_data.append([
							trade.get("datetime", ""),
							trade.get("symbol", ""),
							trade.get("side", ""),
							trade.get("price", ""),
							trade.get("volume", ""),
							trade.get("profit", "")
						])

				# 转换为DataFrame并导出
				df = pd.DataFrame(csv_data)
				return df.to_csv(index=False, header=False)
			else:
				raise ValueError(f"不支持的导出格式: {export_format}")
		except Exception as e:
			logger.error(f"导出报告失败: {str(e)}")
			raise

	@staticmethod
	def generate_performance_summary (metrics: Dict[str, Any]) -> Dict[str, Any]:
		"""
		生成绩效摘要

		Args:
			metrics: 绩效指标

		Returns:
			绩效摘要
		"""
		try:
			summary = {
				"总收益率": f"{metrics.get('total_return', 0) * 100:.2f}%",
				"年化收益率": f"{metrics.get('annualized_return', 0) * 100:.2f}%",
				"夏普比率": f"{metrics.get('sharpe_ratio', 0):.2f}",
				"最大回撤": f"{metrics.get('max_drawdown', 0) * 100:.2f}%",
				"胜率": f"{metrics.get('win_rate', 0) * 100:.2f}%",
				"盈亏比": f"{metrics.get('profit_factor', 0):.2f}",
				"交易次数": f"{metrics.get('num_signals', 0)}",
				"回测天数": f"{metrics.get('duration_days', 0)}"
			}

			return summary
		except Exception as e:
			logger.error(f"生成绩效摘要失败: {str(e)}")
			return {}