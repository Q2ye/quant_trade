# -*- coding: utf-8 -*-
"""
图表生成器

负责生成回测报告中的图表
"""
import base64
import io
import logging
from typing import Dict, Any, List

import matplotlib.pyplot as plt

logger = logging.getLogger(__name__)


class ChartGenerator:
	"""
	图表生成器

	负责生成回测报告中的图表
	"""

	def __init__ (self):
		"""
		初始化图表生成器
		"""
		pass

	@staticmethod
	def generate_equity_curve (equity_curve: List[Dict[str, Any]]) -> str:

		"""
		生成净值曲线图表

		Args:
			equity_curve: 净值曲线数据

		Returns:
			图表的base64编码
		"""
		try:
			# 提取数据
			dates = [item["date"] for item in equity_curve]
			equity = [item["equity"] for item in equity_curve]

			# 创建图表
			plt.figure(figsize=(12, 6))
			plt.plot(dates, equity, label="Equity Curve")
			plt.title("Equity Curve")
			plt.xlabel("Date")
			plt.ylabel("Equity")
			plt.grid(True)
			plt.legend()

			# 转换为base64
			img_buffer = io.BytesIO()
			plt.savefig(img_buffer, format="png")
			img_buffer.seek(0)
			img_base64 = base64.b64encode(img_buffer.read()).decode("utf-8")
			plt.close()

			return img_base64
		except Exception as e:
			logger.error(f"生成净值曲线图表失败: {str(e)}")
			return ""

	@staticmethod
	def generate_drawdown (equity_curve: List[Dict[str, Any]]) -> str:

		"""
		生成回撤图表

		Args:
			equity_curve: 净值曲线数据

		Returns:
			图表的base64编码
		"""
		try:
			# 计算回撤
			equity = [item["equity"] for item in equity_curve]
			dates = [item["date"] for item in equity_curve]

			drawdowns = []
			peak = equity[0]
			for value in equity:
				if value > peak:
					peak = value
				drawdown = (peak - value) / peak
				drawdowns.append(drawdown)

			# 创建图表
			plt.figure(figsize=(12, 6))
			plt.plot(dates, drawdowns, label="Drawdown")
			plt.title("Drawdown")
			plt.xlabel("Date")
			plt.ylabel("Drawdown")
			plt.grid(True)
			plt.legend()

			# 转换为base64
			img_buffer = io.BytesIO()
			plt.savefig(img_buffer, format="png")
			img_buffer.seek(0)
			img_base64 = base64.b64encode(img_buffer.read()).decode("utf-8")
			plt.close()

			return img_base64
		except Exception as e:
			logger.error(f"生成回撤图表失败: {str(e)}")
			return ""

	@staticmethod
	def generate_returns_distribution (returns: List[float]) -> str:

		"""
		生成收益率分布图表

		Args:
			returns: 收益率数据

		Returns:
			图表的base64编码
		"""
		try:
			# 创建图表
			plt.figure(figsize=(12, 6))
			plt.hist(returns, bins=50, label="Returns Distribution")
			plt.title("Returns Distribution")
			plt.xlabel("Return")
			plt.ylabel("Frequency")
			plt.grid(True)
			plt.legend()

			# 转换为base64
			img_buffer = io.BytesIO()
			plt.savefig(img_buffer, format="png")
			img_buffer.seek(0)
			img_base64 = base64.b64encode(img_buffer.read()).decode("utf-8")
			plt.close()

			return img_base64
		except Exception as e:
			logger.error(f"生成收益率分布图表失败: {str(e)}")
			return ""

	@staticmethod
	def generate_trade_pnl (trades: List[Dict[str, Any]]) -> str:

		"""
		生成交易盈亏图表

		Args:
			trades: 交易记录

		Returns:
			图表的base64编码
		"""
		try:
			# 提取数据
			pnl = [trade.get("profit", 0) for trade in trades]
			trade_indices = range(len(trades))

			# 创建图表
			plt.figure(figsize=(12, 6))
			plt.bar(trade_indices, pnl, label="Trade P&L")
			plt.title("Trade P&L")
			plt.xlabel("Trade Index")
			plt.ylabel("P&L")
			plt.grid(True)
			plt.legend()

			# 转换为base64
			img_buffer = io.BytesIO()
			plt.savefig(img_buffer, format="png")
			img_buffer.seek(0)
			img_base64 = base64.b64encode(img_buffer.read()).decode("utf-8")
			plt.close()

			return img_base64
		except Exception as e:
			logger.error(f"生成交易盈亏图表失败: {str(e)}")
			return ""
