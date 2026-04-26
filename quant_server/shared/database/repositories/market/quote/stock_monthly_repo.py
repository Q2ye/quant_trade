# -*- coding: utf-8 -*-
"""
股票月行情数据仓库
位置：quant_server/shared/database/repositories/market/quote/stock_monthly_repo.py
职责：管理股票月线行情数据访问，继承HyperRepositoryBase实现月线数据操作
"""

from datetime import date, timedelta, datetime
from typing import List, Optional, Dict, Any

from sqlalchemy import select, desc
from sqlalchemy.ext.asyncio import AsyncSession

from quant_server.shared.database.models.data_models import StockMonthly
from quant_server.shared.database.repositories.base.hyper_repository_base import HyperRepositoryBase


class StockMonthlyRepository(HyperRepositoryBase[StockMonthly]):
	"""
	股票月行情数据仓库 - 继承HyperRepositoryBase

	特性：
	1. 月线数据专用操作
	2. 支持月线技术指标计算
	3. 提供月线数据专用分析方法
	4. 性能优化：月线长期趋势分析
	"""

	def __init__ (self, session: AsyncSession):
		"""
		初始化股票月行情Repository

		Args:
			session: 异步数据库会话
		"""
		super().__init__(session, StockMonthly)
		self.time_column = "trade_date"  # 设置时序字段为trade_date

	# ==================== 基础查询方法 ====================

	async def get_by_code_and_month (
			self,
			ts_code: str,
			trade_date: date
	) -> Optional[StockMonthly]:
		"""
		根据股票代码和交易月获取月线数据

		Args:
			ts_code: 股票TS代码
			trade_date: 交易月结束日期

		Returns:
			StockMonthly对象或None
		"""
		return await self.get_by(
			ts_code=ts_code,
			trade_date=trade_date
		)

	async def get_by_code_and_date_range (
			self,
			ts_code: str,
			start_date: datetime,
			end_date: datetime,
			limit: int = 1000
	) -> List[StockMonthly]:
		"""
		根据股票代码和时间范围获取月线数据

		Args:
			ts_code: 股票TS代码
			start_date: 开始日期
			end_date: 结束日期
			limit: 最大返回记录数

		Returns:
			月线数据列表
		"""
		return await self.get_by_time_range(
			start_time=start_date,
			end_time=end_date,
			symbol=ts_code,
			limit=limit
		)

	async def get_latest_by_code (
			self,
			ts_code: str,
			limit: int = 1
	) -> Optional[StockMonthly]:
		"""
		获取指定股票的最新月线数据

		Args:
			ts_code: 股票TS代码
			limit: 返回记录数

		Returns:
			最新月线数据或列表
		"""
		return await self.get_latest_record(symbol=ts_code, limit=limit)

	async def get_monthly_summary (
			self,
			trade_date: date,
			limit: int = 50
	) -> List[Dict[str, Any]]:
		"""
		获取指定月的交易概况

		Args:
			trade_date: 交易月结束日期
			limit: 返回数量限制

		Returns:
			月交易概况列表
		"""
		query = select(StockMonthly).where(
			StockMonthly.trade_date == trade_date
		).order_by(desc(StockMonthly.pct_chg)).limit(limit)

		result = await self.session.execute(query)
		monthly_records = result.scalars().all()

		summary = []
		for record in monthly_records:
			summary.append({
				"ts_code": record.ts_code,
				"close": record.close,
				"pct_chg": record.pct_chg,
				"volume": record.vol,
				"amount": record.amount,
				"month_start": record.month_start,
				"month_end": record.month_end,
				"range": float(record.high) - float(record.low) if record.high and record.low else 0
			})

		return summary

	# ==================== 长期趋势分析 ====================

	async def analyze_long_term_trend (
			self,
			ts_code: str,
			end_date: datetime,
			years: int = 5
	) -> Dict[str, Any]:
		"""
		分析长期趋势（年为单位）

		Args:
			ts_code: 股票代码
			end_date: 截止日期
			years: 分析年数

		Returns:
			长期趋势分析结果
		"""
		start_date = end_date - timedelta(days=years * 365)

		monthly_data = await self.get_by_code_and_date_range(
			ts_code, start_date, end_date
		)

		if len(monthly_data) < 12:  # 至少需要一年数据
			return {}

		# 按日期排序
		monthly_data.sort(key=lambda x: x.trade_date)

		# 提取价格数据
		closes = [float(d.close) for d in monthly_data]
		dates = [d.trade_date for d in monthly_data]

		# 计算年化收益率
		if len(closes) >= 12:
			years_elapsed = (dates[-1] - dates[0]).days / 365
			if years_elapsed > 0 and closes[0] > 0:
				cagr = (closes[-1] / closes[0]) ** (1 / years_elapsed) - 1
			else:
				cagr = 0
		else:
			cagr = 0
			years_elapsed = 0

		# 计算月度收益率
		monthly_returns = []
		for i in range(1, len(closes)):
			if closes[i - 1] > 0:
				monthly_return = (closes[i] - closes[i - 1]) / closes[i - 1]
				monthly_returns.append(monthly_return)

		# 统计月度表现
		positive_months = sum(1 for r in monthly_returns if r > 0)
		negative_months = sum(1 for r in monthly_returns if r < 0)

		# 计算年化波动率
		if len(monthly_returns) >= 2:
			mean_return = sum(monthly_returns) / len(monthly_returns)
			variance = sum((r - mean_return) ** 2 for r in monthly_returns) / len(monthly_returns)
			monthly_volatility = variance ** 0.5
			annual_volatility = monthly_volatility * (12 ** 0.5)
		else:
			monthly_volatility = annual_volatility = 0
			mean_return = 0

		# 计算最大回撤
		max_drawdown = 0
		peak = closes[0]

		for price in closes:
			if price > peak:
				peak = price
			else:
				drawdown = (peak - price) / peak
				if drawdown > max_drawdown:
					max_drawdown = drawdown

		# 夏普比率（假设无风险利率3%）
		risk_free_rate = 0.03 / 12  # 月无风险利率
		sharpe_ratio = (mean_return - risk_free_rate) / monthly_volatility if monthly_volatility > 0 else 0

		# 趋势强度（通过线性回归）
		trend_strength = self._calculate_trend_strength(dates, closes)

		return {
			"ts_code": ts_code,
			"analysis_period": {
				"start_date": dates[0],
				"end_date": dates[-1],
				"months": len(monthly_data),
				"years": years_elapsed
			},
			"performance_summary": {
				"start_price": closes[0],
				"end_price": closes[-1],
				"total_return": (closes[-1] - closes[0]) / closes[0] * 100,
				"cagr": cagr * 100,
				"annualized_return": cagr * 100
			},
			"monthly_statistics": {
				"total_months": len(monthly_returns),
				"positive_months": positive_months,
				"negative_months": negative_months,
				"win_rate": positive_months / len(monthly_returns) * 100 if monthly_returns else 0,
				"avg_monthly_return": mean_return * 100,
				"best_month": max(monthly_returns) * 100 if monthly_returns else 0,
				"worst_month": min(monthly_returns) * 100 if monthly_returns else 0
			},
			"risk_metrics": {
				"monthly_volatility": monthly_volatility * 100,
				"annual_volatility": annual_volatility * 100,
				"max_drawdown": max_drawdown * 100,
				"sharpe_ratio": sharpe_ratio,
				"calmar_ratio": cagr / max_drawdown if max_drawdown > 0 else 0
			},
			"trend_analysis": {
				"trend_strength": trend_strength,
				"trend_direction": "up" if cagr > 0 else "down",
				"consistency": positive_months / len(monthly_returns) * 100 if monthly_returns else 0
			}
		}

	@staticmethod
	def _calculate_trend_strength (
			dates: List[date],
			prices: List[float]
	) -> float:
		"""
		计算趋势强度（R-squared）

		Args:
			dates: 日期列表
			prices: 价格列表

		Returns:
			趋势强度（0-1之间）
		"""
		if len(prices) < 2:
			return 0

		# 将日期转换为数值（从第一个日期开始的天数）
		date_nums = [(d - dates[0]).days for d in dates]

		# 线性回归计算R-squared
		n = len(date_nums)
		sum_x = sum(date_nums)
		sum_y = sum(prices)
		sum_xy = sum(x * y for x, y in zip(date_nums, prices))
		sum_x2 = sum(x * x for x in date_nums)
		sum_y2 = sum(y * y for y in prices)

		# 计算相关系数
		numerator = n * sum_xy - sum_x * sum_y
		denominator = ((n * sum_x2 - sum_x ** 2) * (n * sum_y2 - sum_y ** 2)) ** 0.5

		if denominator == 0:
			return 0

		correlation = numerator / denominator
		r_squared = correlation ** 2

		return r_squared

	# ==================== 季节性分析 ====================

	async def analyze_seasonality (
			self,
			ts_code: str,
			end_date: date,
			years: int = 10
	) -> Dict[str, Any]:
		"""
		分析股票季节性模式

		Args:
			ts_code: 股票代码
			end_date: 截止日期
			years: 分析年数

		Returns:
			季节性分析结果
		"""
		from datetime import datetime
		start_date = end_date - timedelta(days=years * 365)

		# 转换为datetime类型
		start_datetime = datetime.combine(start_date, datetime.min.time())
		end_datetime = datetime.combine(end_date, datetime.max.time())

		monthly_data = await self.get_by_code_and_date_range(
			ts_code, start_datetime, end_datetime
		)

		if len(monthly_data) < 12:  # 至少需要一年数据
			return {}

		# 按日期排序
		monthly_data.sort(key=lambda x: x.trade_date)

		# 按月份分组
		monthly_returns = {month: [] for month in range(1, 13)}
		monthly_prices = {month: [] for month in range(1, 13)}

		for i in range(1, len(monthly_data)):
			prev_month = monthly_data[i - 1]
			curr_month = monthly_data[i]

			month_num = curr_month.trade_date.month

			if prev_month.close > 0:
				monthly_return = (curr_month.close - prev_month.close) / prev_month.close
				monthly_returns[month_num].append(monthly_return)
				monthly_prices[month_num].append(float(curr_month.close))

		# 计算各月统计
		month_statistics = {}
		for month in range(1, 13):
			returns = monthly_returns[month]
			prices = monthly_prices[month]

			if returns:
				avg_return = sum(returns) / len(returns)
				positive_count = sum(1 for r in returns if r > 0)
				win_rate = positive_count / len(returns) * 100

				# 计算波动率
				if len(returns) >= 2:
					mean_return = sum(returns) / len(returns)
					variance = sum((r - mean_return) ** 2 for r in returns) / len(returns)
					volatility = variance ** 0.5
				else:
					volatility = 0

				month_statistics[month] = {
					"month_name": self._get_month_name(month),
					"sample_size": len(returns),
					"avg_return": avg_return * 100,
					"win_rate": win_rate,
					"volatility": volatility * 100,
					"best_return": max(returns) * 100 if returns else 0,
					"worst_return": min(returns) * 100 if returns else 0,
					"avg_price": sum(prices) / len(prices) if prices else 0
				}
			else:
				month_statistics[month] = {
					"month_name": self._get_month_name(month),
					"sample_size": 0,
					"avg_return": 0,
					"win_rate": 0,
					"volatility": 0,
					"best_return": 0,
					"worst_return": 0,
					"avg_price": 0
				}

		# 找出表现最好和最差的月份
		months_with_data = {k: v for k, v in month_statistics.items() if v["sample_size"] > 0}

		if months_with_data:
			best_month = max(months_with_data.items(), key=lambda x: x[1]["avg_return"])
			worst_month = min(months_with_data.items(), key=lambda x: x[1]["avg_return"])

			seasonal_strength = self._calculate_seasonal_strength(month_statistics)
		else:
			best_month = worst_month = (0, {})
			seasonal_strength = 0

		return {
			"ts_code": ts_code,
			"analysis_period": {
				"start_date": start_date,
				"end_date": end_date,
				"years": years
			},
			"monthly_statistics": month_statistics,
			"seasonal_patterns": {
				"best_month": {
					"month": best_month[0],
					"month_name": best_month[1]["month_name"],
					"avg_return": best_month[1]["avg_return"],
					"win_rate": best_month[1]["win_rate"]
				},
				"worst_month": {
					"month": worst_month[0],
					"month_name": worst_month[1]["month_name"],
					"avg_return": worst_month[1]["avg_return"],
					"win_rate": worst_month[1]["win_rate"]
				},
				"seasonal_strength": seasonal_strength
			},
			"recommendations": self._generate_seasonal_recommendations(month_statistics)
		}

	@staticmethod
	def _get_month_name (month_num: int) -> str:
		"""获取月份名称"""
		month_names = [
			"January", "February", "March", "April", "May", "June",
			"July", "August", "September", "October", "November", "December"
		]
		return month_names[month_num - 1] if 1 <= month_num <= 12 else "Unknown"

	@staticmethod
	def _calculate_seasonal_strength (
			month_statistics: Dict[int, Dict[str, Any]]
	) -> float:
		"""
		计算季节性强度

		Args:
			month_statistics: 月份统计信息

		Returns:
			季节性强度（0-1之间）
		"""
		# 使用ANOVA方法计算季节性强度
		valid_months = [stats for stats in month_statistics.values() if stats["sample_size"] > 0]

		if len(valid_months) < 2:
			return 0



		# 简化实现：返回月份间差异的度量
		returns = [stats["avg_return"] for stats in valid_months]
		if returns:
			mean_return = sum(returns) / len(returns)
			variance = sum((r - mean_return) ** 2 for r in returns) / len(returns)
			max_variance = max(abs(r - mean_return) for r in returns) ** 2

			if max_variance > 0:
				return variance / max_variance
			else:
				return 0

		return 0

	@staticmethod
	def _generate_seasonal_recommendations (
			month_statistics: Dict[int, Dict[str, Any]]
	) -> List[Dict[str, Any]]:
		"""
		生成季节性投资建议

		Args:
			month_statistics: 月份统计信息

		Returns:
			投资建议列表
		"""
		recommendations = []

		# 找出表现持续好的月份
		good_months = []
		for month, stats in month_statistics.items():
			if (stats["sample_size"] >= 3 and  # 至少3个样本
					stats["avg_return"] > 2 and  # 平均收益率>2%
					stats["win_rate"] > 60):  # 胜率>60%
				good_months.append((month, stats))

		# 找出表现持续差的月份
		bad_months = []
		for month, stats in month_statistics.items():
			if (stats["sample_size"] >= 3 and  # 至少3个样本
					stats["avg_return"] < -1 and  # 平均收益率<-1%
					stats["win_rate"] < 40):  # 胜率<40%
				bad_months.append((month, stats))

		# 生成建议
		if good_months:
			for month, stats in good_months[:2]:  # 最多推荐2个月份
				recommendations.append({
					"type": "buy_seasonality",
					"month": month,
					"month_name": stats["month_name"],
					"reason": f"历史平均收益率{stats['avg_return']:.1f}%，胜率{stats['win_rate']:.1f}%",
					"confidence": min(stats["sample_size"] / 10, 1.0)  # 基于样本量的置信度
				})

		if bad_months:
			for month, stats in bad_months[:2]:  # 最多警告2个月份
				recommendations.append({
					"type": "avoid_seasonality",
					"month": month,
					"month_name": stats["month_name"],
					"reason": f"历史平均收益率{stats['avg_return']:.1f}%，胜率{stats['win_rate']:.1f}%",
					"confidence": min(stats["sample_size"] / 10, 1.0)
				})

		return recommendations

	# ==================== 批量操作方法 ====================

	async def batch_insert_monthly (
			self,
			records: List[Dict[str, Any]],
			conflict_strategy: str = "upsert"
	) -> int:
		"""
		批量插入月线数据

		Args:
			records: 月线数据记录列表
			conflict_strategy: 冲突处理策略

		Returns:
			成功插入的记录数
		"""
		return await self.batch_insert(records, conflict_strategy)