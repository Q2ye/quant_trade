# -*- coding: utf-8 -*-
"""
股票复权因子数据仓库
位置：quant_server/shared/database/repositories/market/quote/stock_adj_factor_repo.py
职责：管理股票复权因子数据访问，继承HyperRepositoryBase实现复权因子计算和查询
"""

from datetime import date, timedelta, datetime
from typing import List, Optional, Dict, Any

from sqlalchemy import select, text, desc
from sqlalchemy.ext.asyncio import AsyncSession

from shared.database.models.data_models import StockAdjFactor
from shared.database.repositories.base.hyper_repository_base import HyperRepositoryBase, RepositoryError


class StockAdjFactorRepository(HyperRepositoryBase[StockAdjFactor]):
	"""
	股票复权因子数据仓库 - 继承HyperRepositoryBase

	特性：
	1. 复权因子专用操作
	2. 支持复权价格计算
	3. 提供复权因子专用分析方法
	4. 性能优化：批量复权计算
	"""

	def __init__ (self, session: AsyncSession):
		"""
		初始化股票复权因子Repository

		Args:
			session: 异步数据库会话
		"""
		super().__init__(session, StockAdjFactor)
		self.time_column = "trade_date"  # 设置时序字段为trade_date

	# ==================== 基础查询方法 ====================

	async def get_by_code_and_date (
			self,
			ts_code: str,
			trade_date: date
	) -> Optional[StockAdjFactor]:
		"""
		根据股票代码和日期获取复权因子

		Args:
			ts_code: 股票TS代码
			trade_date: 交易日期

		Returns:
			StockAdjFactor对象或None
		"""
		return await self.get_by(
			ts_code=ts_code,
			trade_date=trade_date
		)

	async def get_by_trade_date (
			self,
			trade_date: date,
			ts_code: Optional[str] = None
	) -> List[StockAdjFactor]:
		"""
		根据交易日期获取复权因子

		Args:
			trade_date: 交易日期
			ts_code: 股票TS代码（可选，不指定则返回所有股票）

		Returns:
			指定交易日的复权因子列表
		"""
		try:
			query = select(self.model).where(
				self.model.trade_date == trade_date
			)

			if ts_code:
				query = query.where(self.model.ts_code == ts_code)

			result = await self.session.execute(query)
			return result.scalars().all()
		except Exception as e:
			raise RepositoryError(f"根据交易日期查询复权因子失败: {str(e)}")

	async def get_by_code_and_date_range (
			self,
			ts_code: str,
			start_date: datetime,
			end_date: datetime,
			limit: int = 1000
	) -> List[StockAdjFactor]:
		"""
		根据股票代码和时间范围获取复权因子

		Args:
			ts_code: 股票TS代码
			start_date: 开始日期
			end_date: 结束日期
			limit: 最大返回记录数

		Returns:
			复权因子列表
		"""
		return await self.get_by_time_range(
			start_time=start_date,
			end_time=end_date,
			symbol=ts_code,
			limit=limit
		)

	async def get_existing_trade_dates (
			self,
			ts_code: str,
			start_date=None,
			end_date=None,
	) -> set:
		"""
		批量获取已有交易日期集合（一次查询替代 N 次逐条查询）
		"""
		try:
			query = select(self.model.trade_date).where(
				self.model.ts_code == ts_code
			)
			if start_date:
				query = query.where(self.model.trade_date >= start_date)
			if end_date:
				query = query.where(self.model.trade_date <= end_date)
			result = await self.session.execute(query)
			return {row.trade_date for row in result.fetchall()}
		except Exception as e:
			raise RepositoryError(f"批量获取已有交易日期失败: {str(e)}")

	async def get_latest_trade_date (
			self,
			ts_code: str
	) -> Optional[date]:
		"""
		获取指定标的的最新数据日期（用于增量同步日期推断）
		"""
		try:
			query = select(self.model.trade_date).where(
				self.model.ts_code == ts_code
			).order_by(desc(self.model.trade_date)).limit(1)
			result = await self.session.execute(query)
			row = result.first()
			return row.trade_date if row else None
		except Exception as e:
			raise RepositoryError(f"获取最新数据日期失败: {str(e)}")


	async def get_latest_trade_dates_batch(
			self,
			ts_codes: list
	) -> dict:
		"""
		批量获取多只股票的最新交易日期（一次 SQL 查询）。

		用于数据同步的批量日期推断，替代逐股调用 ``get_latest_trade_date``，
		将 N 次 DB 查询合并为 1 次。

		Args:
			ts_codes: 股票 TS 代码列表

		Returns:
			Dict[str, Optional[date]]: ``{ts_code: latest_date}``，无数据时为 None
		"""
		from typing import Dict, Optional as Opt
		from datetime import date as d
		from sqlalchemy import func

		if not ts_codes:
			return {}

		query = (
			select(self.model.ts_code, func.max(self.model.trade_date))
			.where(self.model.ts_code.in_(ts_codes))
			.group_by(self.model.ts_code)
		)
		result = await self.session.execute(query)
		mapping: Dict[str, Opt[d]] = {row[0]: row[1] for row in result.fetchall()}
		# 确保所有传入的代码都有值（无记录的返回 None）
		for code in ts_codes:
			if code not in mapping:
				mapping[code] = None
		return mapping

	async def get_latest_by_code (
			self,
			ts_code: str,
			limit: int = 1
	) -> Optional[StockAdjFactor]:
		"""
		获取指定股票的最新复权因子

		Args:
			ts_code: 股票TS代码
			limit: 返回记录数

		Returns:
			最新复权因子或列表
		"""
		return await self.get_latest_record(symbol=ts_code, limit=limit)

	# ==================== 复权计算方法 ====================

	async def calculate_adjusted_price (
			self,
			ts_code: str,
			base_date: date,
			target_date: date,
			base_price: float,
			adjust_type: str = "qfq"
	) -> float:
		"""
		计算复权价格

		Args:
			ts_code: 股票代码
			base_date: 基期日期
			target_date: 目标日期
			base_price: 基期价格
			adjust_type: 复权类型（qfq-前复权，hfq-后复权）

		Returns:
			复权后的价格
		"""
		# 获取复权因子
		base_factor = await self.get_by_code_and_date(ts_code, base_date)
		target_factor = await self.get_by_code_and_date(ts_code, target_date)

		if not base_factor or not target_factor:
			return base_price

		if adjust_type == "qfq":  # 前复权：以最新价格为基准
			adjusted_price = base_price * (float(target_factor.adj_factor) / float(base_factor.adj_factor))
		else:  # 后复权：以历史价格为基准
			adjusted_price = base_price * (float(base_factor.adj_factor) / float(target_factor.adj_factor))

		return adjusted_price

	async def calculate_adjusted_prices_batch (
			self,
			ts_code: str,
			base_date: datetime,
			base_price: float,
			target_dates: List[datetime],
			adjust_type: str = "qfq"
	) -> Dict[datetime, float]:
		"""
		批量计算复权价格

		Args:
			ts_code: 股票代码
			base_date: 基期日期
			base_price: 基期价格
			target_dates: 目标日期列表
			adjust_type: 复权类型

		Returns:
			日期到复权价格的映射
		"""
		# 获取所有日期的复权因子
		start_date = min(min(target_dates), base_date)
		end_date = max(max(target_dates), base_date)

		factors = await self.get_by_code_and_date_range(
			ts_code, start_date, end_date, limit=10000
		)

		# 创建因子字典
		factor_dict = {f.trade_date: float(f.adj_factor) for f in factors}

		# 获取基期因子
		base_factor = factor_dict.get(base_date)
		if not base_factor:
			return {}

		# 计算复权价格
		adjusted_prices = {}
		for target_date in target_dates:
			target_factor = factor_dict.get(target_date)
			if target_factor:
				if adjust_type == "qfq":
					adjusted_price = base_price * (target_factor / base_factor)
				else:
					adjusted_price = base_price * (base_factor / target_factor)

				adjusted_prices[target_date] = adjusted_price

		return adjusted_prices

	async def generate_adjusted_price_series (
			self,
			ts_code: str,
			start_date: datetime,
			end_date: datetime,
			base_price: float,
			base_date: datetime,
			adjust_type: str = "qfq"
	) -> List[Dict[str, Any]]:
		"""
		生成复权价格序列

		Args:
			ts_code: 股票代码
			start_date: 开始日期
			end_date: 结束日期
			base_price: 基期价格
			base_date: 基期日期
			adjust_type: 复权类型

		Returns:
			复权价格序列
		"""
		# 获取复权因子
		factors = await self.get_by_code_and_date_range(
			ts_code, start_date, end_date
		)

		if not factors:
			return []

		# 按日期排序
		factors.sort(key=lambda x: x.trade_date)

		# 获取基期因子
		base_factor_record = await self.get_by_code_and_date(ts_code, base_date)
		if not base_factor_record:
			return []

		base_factor = float(base_factor_record.adj_factor)

		# 生成复权价格序列
		price_series = []
		for factor in factors:
			current_factor = float(factor.adj_factor)

			if adjust_type == "qfq":
				adjusted_price = base_price * (current_factor / base_factor)
			else:
				adjusted_price = base_price * (base_factor / current_factor)

			price_series.append({
				"date": factor.trade_date,
				"adj_factor": current_factor,
				"adjusted_price": adjusted_price,
				"adjust_type": adjust_type,
				"base_date": base_date,
				"base_price": base_price
			})

		return price_series

	# ==================== 除权除息分析 ====================

	async def analyze_dividend_impact (
			self,
			ts_code: str,
			start_date: datetime,
			end_date: datetime
	) -> Dict[str, Any]:
		"""
		分析除权除息对价格的影响

		Args:
			ts_code: 股票代码
			start_date: 开始日期
			end_date: 结束日期

		Returns:
			除权除息分析结果
		"""
		factors = await self.get_by_code_and_date_range(
			ts_code, start_date, end_date
		)

		if len(factors) < 2:
			return {}

		# 按日期排序
		factors.sort(key=lambda x: x.trade_date)

		# 分析因子变化
		dividend_events = []
		for i in range(1, len(factors)):
			prev_factor = float(factors[i - 1].adj_factor)
			curr_factor = float(factors[i].adj_factor)

			# 检查因子是否有显著变化（表示除权除息）
			factor_change = (curr_factor - prev_factor) / prev_factor

			# 通常除权除息会导致复权因子显著变化
			if abs(factor_change) > 0.001:  # 变化超过0.1%
				# 计算除权除息幅度
				if factor_change < 0:  # 因子减少，表示分红或送股
					adjustment_rate = -factor_change / (1 + factor_change)
				else:  # 因子增加，表示配股
					adjustment_rate = factor_change

				dividend_events.append({
					"date": factors[i].trade_date,
					"prev_factor": prev_factor,
					"curr_factor": curr_factor,
					"factor_change": factor_change * 100,  # 百分比
					"adjustment_rate": adjustment_rate * 100,  # 百分比
					"event_type": self._classify_dividend_event(factor_change)
				})

		# 统计除权除息事件
		if dividend_events:
			total_events = len(dividend_events)
			cash_dividends = sum(1 for e in dividend_events if e["event_type"] == "cash_dividend")
			stock_dividends = sum(1 for e in dividend_events if e["event_type"] == "stock_dividend")
			rights_issues = sum(1 for e in dividend_events if e["event_type"] == "rights_issue")

			avg_adjustment = sum(e["adjustment_rate"] for e in dividend_events) / total_events

			# 计算平均间隔
			dates = [e["date"] for e in dividend_events]
			intervals = []
			for i in range(1, len(dates)):
				interval = (dates[i] - dates[i - 1]).days
				intervals.append(interval)

			avg_interval = sum(intervals) / len(intervals) if intervals else 0

			analysis = {
				"ts_code": ts_code,
				"analysis_period": {
					"start_date": start_date,
					"end_date": end_date,
					"days": (end_date - start_date).days
				},
				"event_summary": {
					"total_events": total_events,
					"cash_dividends": cash_dividends,
					"stock_dividends": stock_dividends,
					"rights_issues": rights_issues,
					"avg_adjustment_rate": avg_adjustment,
					"avg_interval_days": avg_interval,
					"events_per_year": total_events / ((end_date - start_date).days / 365) if (
							                                                                          end_date - start_date).days > 0 else 0
				},
				"event_details": dividend_events,
				"factor_statistics": {
					"initial_factor": float(factors[0].adj_factor),
					"final_factor": float(factors[-1].adj_factor),
					"total_factor_change": (float(factors[-1].adj_factor) - float(factors[0].adj_factor)) / float(
						factors[0].adj_factor) * 100,
					"avg_daily_change": self._calculate_average_daily_change(factors)
				}
			}
		else:
			analysis = {
				"ts_code": ts_code,
				"analysis_period": {
					"start_date": start_date,
					"end_date": end_date,
					"days": (end_date - start_date).days
				},
				"event_summary": {
					"total_events": 0,
					"message": "在分析期间内未检测到明显的除权除息事件"
				},
				"factor_statistics": {
					"initial_factor": float(factors[0].adj_factor),
					"final_factor": float(factors[-1].adj_factor),
					"total_factor_change": (float(factors[-1].adj_factor) - float(factors[0].adj_factor)) / float(
						factors[0].adj_factor) * 100,
					"avg_daily_change": self._calculate_average_daily_change(factors)
				}
			}

		return analysis

	@staticmethod
	def _classify_dividend_event (factor_change: float) -> str:
		"""
		分类除权除息事件类型

		Args:
			factor_change: 复权因子变化率

		Returns:
			事件类型
		"""
		if factor_change < -0.01:  # 因子大幅减少，可能是大比例送股
			return "stock_dividend"
		elif -0.01 <= factor_change < -0.001:  # 因子中等减少，可能是现金分红
			return "cash_dividend"
		elif factor_change > 0.001:  # 因子增加，可能是配股
			return "rights_issue"
		else:
			return "minor_adjustment"

	@staticmethod
	def _calculate_average_daily_change (
			factors: List[StockAdjFactor]
	) -> float:
		"""
		计算复权因子的日均变化

		Args:
			factors: 复权因子列表

		Returns:
			日均变化率（百分比）
		"""
		if len(factors) < 2:
			return 0

		# 按日期排序
		factors.sort(key=lambda x: x.trade_date)

		total_change = 0
		total_days = 0

		for i in range(1, len(factors)):
			prev_factor = float(factors[i - 1].adj_factor)
			curr_factor = float(factors[i].adj_factor)

			if prev_factor > 0:
				daily_change = (curr_factor - prev_factor) / prev_factor
				total_change += abs(daily_change)
				total_days += 1

		avg_daily_change = (total_change / total_days) * 100 if total_days > 0 else 0
		return avg_daily_change

	# ==================== 数据完整性检查 ====================

	async def check_factor_consistency (
			self,
			ts_code: str,
			start_date: datetime,
			end_date: datetime
	) -> Dict[str, Any]:
		"""
		检查复权因子的连续性和一致性

		Args:
			ts_code: 股票代码
			start_date: 开始日期
			end_date: 结束日期

		Returns:
			一致性检查结果
		"""
		factors = await self.get_by_code_and_date_range(
			ts_code, start_date, end_date
		)

		if len(factors) < 2:
			return {
				"ts_code": ts_code,
				"status": "insufficient_data",
				"message": "数据不足，无法进行一致性检查"
			}

		# 按日期排序
		factors.sort(key=lambda x: x.trade_date)

		# 检查连续性
		missing_dates = []
		for i in range(1, len(factors)):
			expected_next = factors[i - 1].trade_date + timedelta(days=1)
			while expected_next < factors[i].trade_date:
				# 检查是否是交易日
				calendar_query = text("""
                    SELECT is_open FROM trade_calendar 
                    WHERE cal_date = :date
                """)

				calendar_result = await self.session.execute(
					calendar_query,
					{"date": expected_next}
				)
				calendar_row = calendar_result.fetchone()

				if calendar_row and calendar_row.is_open:
					missing_dates.append(expected_next)

				expected_next += timedelta(days=1)

		# 检查因子单调性（复权因子应该随时间递减或不变）
		non_decreasing = []
		for i in range(1, len(factors)):
			prev_factor = float(factors[i - 1].adj_factor)
			curr_factor = float(factors[i].adj_factor)

			# 复权因子应该递减或不变（因为除权除息）
			if curr_factor > prev_factor * 1.001:  # 允许0.1%的误差
				non_decreasing.append({
					"date": factors[i].trade_date,
					"prev_factor": prev_factor,
					"curr_factor": curr_factor,
					"increase": (curr_factor - prev_factor) / prev_factor * 100
				})

		# 检查因子范围
		factor_values = [float(f.adj_factor) for f in factors]
		min_factor = min(factor_values) if factor_values else 0
		max_factor = max(factor_values) if factor_values else 0

		# 统计异常值
		if factor_values:
			mean_factor = sum(factor_values) / len(factor_values)
			std_factor = (sum((f - mean_factor) ** 2 for f in factor_values) / len(factor_values)) ** 0.5

			outliers = []
			for i, factor in enumerate(factor_values):
				if abs(factor - mean_factor) > 3 * std_factor and std_factor > 0:
					outliers.append({
						"date": factors[i].trade_date,
						"factor": factor,
						"deviation": (factor - mean_factor) / std_factor
					})
		else:
			mean_factor = std_factor = 0
			outliers = []

		return {
			"ts_code": ts_code,
			"analysis_period": {
				"start_date": start_date,
				"end_date": end_date,
				"total_days": (end_date - start_date).days,
				"factor_days": len(factors)
			},
			"completeness": {
				"missing_trading_dates": missing_dates,
				"missing_count": len(missing_dates),
				"completeness_rate": len(factors) / ((end_date - start_date).days + 1) * 100
			},
			"consistency": {
				"non_decreasing_events": non_decreasing,
				"non_decreasing_count": len(non_decreasing),
				"factor_range": {
					"min": min_factor,
					"max": max_factor,
					"range": max_factor - min_factor
				},
				"statistics": {
					"mean": mean_factor,
					"std": std_factor,
					"cv": std_factor / mean_factor * 100 if mean_factor > 0 else 0  # 变异系数
				}
			},
			"anomalies": {
				"outliers": outliers,
				"outlier_count": len(outliers)
			},
			"overall_assessment": {
				"status": "good" if len(missing_dates) == 0 and len(non_decreasing) == 0 and len(
					outliers) == 0 else "needs_review",
				"score": self._calculate_consistency_score(
					len(missing_dates), len(non_decreasing), len(outliers), len(factors)
				)
			}
		}

	@staticmethod
	def _calculate_consistency_score (
			missing_count: int,
			non_decreasing_count: int,
			outlier_count: int,
			total_factors: int
	) -> float:
		"""
		计算一致性评分

		Args:
			missing_count: 缺失日期数量
			non_decreasing_count: 非递减事件数量
			outlier_count: 异常值数量
			total_factors: 总因子数量

		Returns:
			一致性评分（0-100）
		"""
		if total_factors == 0:
			return 0

		# 计算各项扣分
		missing_penalty = (missing_count / total_factors) * 100
		consistency_penalty = (non_decreasing_count / total_factors) * 100
		outlier_penalty = (outlier_count / total_factors) * 100

		# 总分100分
		score = 100 - missing_penalty - consistency_penalty - outlier_penalty

		return max(0.0, min(100.0, score))

	async def get_batch_by_date_range (
			self,
			symbols: List[str],
			start_date: date,
			end_date: date,
	) -> Dict[str, Dict[date, float]]:
		"""
		批量获取多只股票在时间范围内的每日复权因子。

		Args:
			symbols: 股票 TS 代码列表
			start_date: 开始日期
			end_date: 结束日期

		Returns:
			{ts_code: {trade_date: adj_factor}} — 用于在线计算复权价格
		"""
		from collections import defaultdict
		result: Dict[str, Dict[date, float]] = defaultdict(dict)
		try:
			query = select(self.model).where(
				self.model.ts_code.in_(symbols),
				self.model.trade_date.between(start_date, end_date),
			).order_by(self.model.ts_code, self.model.trade_date)
			rows = await self.session.execute(query)
			for row in rows.scalars().all():
				result[row.ts_code][row.trade_date] = float(row.adj_factor)
		except Exception as e:
			raise RepositoryError(f"批量查询复权因子失败: {e}")
		return dict(result)

	# ==================== 批量操作方法 ====================

	async def batch_insert_factors (
			self,
			records: List[Dict[str, Any]],
			conflict_strategy: str = "upsert"
	) -> int:
		"""
		批量插入复权因子数据

		Args:
			records: 复权因子记录列表
			conflict_strategy: 冲突处理策略

		Returns:
			成功插入的记录数
		"""
		return await self.batch_insert(records, conflict_strategy)