# -*- coding: utf-8 -*-
"""
基金复权因子数据仓库
位置：quant_server/shared/database/repositories/market/quote/fund_adj_factor_repo.py
职责：管理基金（含ETF）复权因子数据访问，继承HyperRepositoryBase实现基金专用操作
"""

from datetime import date, timedelta, datetime
from typing import List, Optional, Dict, Any

from sqlalchemy import select, text, desc
from sqlalchemy.ext.asyncio import AsyncSession

from shared.database.models.data_models import FundAdjFactor
from shared.database.repositories.base.hyper_repository_base import HyperRepositoryBase, RepositoryError


class FundAdjFactorRepository(HyperRepositoryBase[FundAdjFactor]):
	"""
	基金复权因子数据仓库 - 继承HyperRepositoryBase

	特性：
	1. 基金复权因子专用操作
	2. 支持基金分红再投资计算
	3. 提供基金复权专用分析方法
	4. 性能优化：基金批量复权计算
	"""

	def __init__ (self, session: AsyncSession):
		"""
		初始化基金复权因子Repository

		Args:
			session: 异步数据库会话
		"""
		super().__init__(session, FundAdjFactor)
		self.time_column = "trade_date"  # 设置时序字段为trade_date

	# ==================== 基础查询方法 ====================

	async def get_by_code_and_date (
			self,
			ts_code: str,
			trade_date: date
	) -> Optional[FundAdjFactor]:
		"""
		根据基金代码和日期获取复权因子

		Args:
			ts_code: 基金TS代码
			trade_date: 交易日期

		Returns:
			FundAdjFactor对象或None
		"""
		return await self.get_by(
			ts_code=ts_code,
			trade_date=trade_date
		)

	async def get_by_trade_date (
			self,
			trade_date: date,
			ts_code: Optional[str] = None
	) -> List[FundAdjFactor]:
		"""
		根据交易日期获取基金复权因子

		Args:
			trade_date: 交易日期
			ts_code: 基金TS代码（可选，不指定则返回所有基金）

		Returns:
			指定交易日的基金复权因子列表
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
			raise RepositoryError(f"根据交易日期查询基金复权因子失败: {str(e)}")

	async def get_by_code_and_date_range (
			self,
			ts_code: str,
			start_date: datetime,
			end_date: datetime,
			limit: int = 1000
	) -> List[FundAdjFactor]:
		"""
		根据基金代码和时间范围获取复权因子

		Args:
			ts_code: 基金TS代码
			start_date: 开始日期
			end_date: 结束日期
			limit: 最大返回记录数

		Returns:
			基金复权因子列表
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
		"""批量获取多只基金的最新交易日（一次 SQL 查询，用于增量同步日期推断）。

		Args:
			ts_codes: 基金 TS 代码列表

		Returns:
			dict: {ts_code: latest_trade_date 或 None}
		"""
		from sqlalchemy import func

		if not ts_codes:
			return {}

		try:
			query = (
				select(self.model.ts_code, func.max(self.model.trade_date))
				.where(self.model.ts_code.in_(ts_codes))
				.group_by(self.model.ts_code)
			)
			result = await self.session.execute(query)
			mapping = {row[0]: row[1] for row in result.fetchall()}
			for code in ts_codes:
				if code not in mapping:
					mapping[code] = None
			return mapping
		except Exception as e:
			raise RepositoryError(f"批量获取最新交易日期失败: {str(e)}")

	async def get_latest_by_code (
			self,
			ts_code: str,
			limit: int = 1
	) -> Optional[FundAdjFactor]:
		"""
		获取指定基金的最新复权因子

		Args:
			ts_code: 基金TS代码
			limit: 返回记录数

		Returns:
			最新基金复权因子或列表
		"""
		return await self.get_latest_record(symbol=ts_code, limit=limit)

	# ==================== 基金分红分析 ====================

	async def analyze_dividend_distribution (
			self,
			ts_code: str,
			start_date: datetime,
			end_date: datetime
	) -> Dict[str, Any]:
		"""
		分析基金分红分布

		Args:
			ts_code: 基金代码
			start_date: 开始日期
			end_date: 结束日期

		Returns:
			分红分析结果
		"""
		factors = await self.get_by_code_and_date_range(
			ts_code, start_date, end_date
		)

		if len(factors) < 2:
			return {}

		# 按日期排序
		factors.sort(key=lambda x: x.trade_date)

		# 分析分红事件
		dividend_events = []
		total_dividend_yield = 0

		for i in range(1, len(factors)):
			prev_factor = float(factors[i - 1].adj_factor)
			curr_factor = float(factors[i].adj_factor)

			# 复权因子减少表示分红
			if curr_factor < prev_factor:
				dividend_yield = (prev_factor - curr_factor) / prev_factor
				total_dividend_yield += dividend_yield

				dividend_events.append({
					"ex_date": factors[i].trade_date,  # 除息日
					"prev_factor": prev_factor,
					"curr_factor": curr_factor,
					"dividend_yield": dividend_yield * 100,  # 百分比
					"factor_change": (curr_factor - prev_factor) / prev_factor * 100
				})

		# 统计分红信息
		if dividend_events:
			total_events = len(dividend_events)
			avg_dividend_yield = total_dividend_yield / total_events * 100
			max_dividend_yield = max(e["dividend_yield"] for e in dividend_events)
			min_dividend_yield = min(e["dividend_yield"] for e in dividend_events)

			# 计算分红频率
			dates = [e["ex_date"] for e in dividend_events]
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
					"days": (end_date - start_date).days,
					"trading_days": len(factors)
				},
				"dividend_summary": {
					"total_dividends": total_events,
					"total_dividend_yield": total_dividend_yield * 100,
					"avg_dividend_yield": avg_dividend_yield,
					"max_dividend_yield": max_dividend_yield,
					"min_dividend_yield": min_dividend_yield,
					"avg_interval_days": avg_interval,
					"dividends_per_year": total_events / ((end_date - start_date).days / 365) if (
							                                                                             end_date - start_date).days > 0 else 0
				},
				"dividend_details": dividend_events,
				"factor_statistics": {
					"initial_factor": float(factors[0].adj_factor),
					"final_factor": float(factors[-1].adj_factor),
					"total_factor_change": (float(factors[-1].adj_factor) - float(factors[0].adj_factor)) / float(
						factors[0].adj_factor) * 100
				}
			}
		else:
			analysis = {
				"ts_code": ts_code,
				"analysis_period": {
					"start_date": start_date,
					"end_date": end_date,
					"days": (end_date - start_date).days,
					"trading_days": len(factors)
				},
				"dividend_summary": {
					"total_dividends": 0,
					"message": "在分析期间内未检测到分红事件"
				},
				"factor_statistics": {
					"initial_factor": float(factors[0].adj_factor),
					"final_factor": float(factors[-1].adj_factor),
					"total_factor_change": (float(factors[-1].adj_factor) - float(factors[0].adj_factor)) / float(
						factors[0].adj_factor) * 100
				}
			}

		return analysis

	async def calculate_total_return (
			self,
			ts_code: str,
			start_date: datetime,
			end_date: datetime,
			initial_investment: float = 10000.0
	) -> Dict[str, Any]:
		"""
		计算基金总回报（价格回报+分红再投资）

		Args:
			ts_code: 基金代码
			start_date: 开始日期
			end_date: 结束日期
			initial_investment: 初始投资金额

		Returns:
			总回报分析结果
		"""
		# 获取复权因子
		factors = await self.get_by_code_and_date_range(
			ts_code, start_date, end_date
		)

		if len(factors) < 2:
			return {"error": "数据不足"}

		# 按日期排序
		factors.sort(key=lambda x: x.trade_date)

		# 获取基金价格数据（需要从etf_daily表查询）
		price_query = text("""
            SELECT trade_date, close FROM etf_daily 
            WHERE ts_code = :ts_code 
              AND trade_date BETWEEN :start_date AND :end_date
            ORDER BY trade_date
        """)

		price_result = await self.session.execute(
			price_query,
			{"ts_code": ts_code, "start_date": start_date, "end_date": end_date}
		)
		price_rows = price_result.fetchall()

		if not price_rows:
			return {"error": "无法获取基金价格数据"}

		# 创建数据字典
		factor_dict = {f.trade_date: float(f.adj_factor) for f in factors}
		price_dict = {row.trade_date: float(row.close) for row in price_rows}

		# 找出共同交易日
		common_dates = sorted(set(factor_dict.keys()) & set(price_dict.keys()))

		if len(common_dates) < 2:
			return {"error": "共同交易日数据不足"}

		# 模拟投资
		initial_shares = initial_investment / price_dict[common_dates[0]]
		current_shares = initial_shares

		# 记录每日价值
		daily_values = []

		for i in range(len(common_dates)):
			current_date = common_dates[i]
			price = price_dict[current_date]
			factor = factor_dict[current_date]

			# 计算当日价值
			if i == 0:
				daily_value = current_shares * price
			else:
				# 检查是否有分红（因子减少）
				prev_factor = factor_dict[common_dates[i - 1]]
				if factor < prev_factor:
					# 分红收益率
					dividend_yield = (prev_factor - factor) / prev_factor
					# 分红再投资
					dividend_amount = current_shares * price * dividend_yield
					reinvested_shares = dividend_amount / price
					current_shares += reinvested_shares

				daily_value = current_shares * price

			daily_values.append({
				"date": current_date,
				"price": price,
				"shares": current_shares,
				"value": daily_value,
				"factor": factor
			})

		# 计算回报指标
		final_value = daily_values[-1]["value"]
		price_only_final = initial_shares * price_dict[common_dates[-1]]

		total_return = (final_value - initial_investment) / initial_investment * 100
		price_return = (price_dict[common_dates[-1]] - price_dict[common_dates[0]]) / price_dict[
			common_dates[0]] * 100

		# 计算年化回报
		days_elapsed = (common_dates[-1] - common_dates[0]).days
		if days_elapsed > 0:
			years_elapsed = days_elapsed / 365
			total_annual_return = ((final_value / initial_investment) ** (1 / years_elapsed) - 1) * 100
			price_annual_return = ((price_dict[common_dates[-1]] / price_dict[common_dates[0]]) ** (
				1 / years_elapsed) - 1) * 100
		else:
			total_annual_return = price_annual_return = 0

		# 计算分红贡献
		dividend_contribution = total_return - price_return

		return {
			"ts_code": ts_code,
			"analysis_period": {
				"start_date": common_dates[0],
				"end_date": common_dates[-1],
				"days": days_elapsed,
				"trading_days": len(common_dates)
			},
			"investment_summary": {
				"initial_investment": initial_investment,
				"final_value": final_value,
				"price_only_final": price_only_final,
				"total_return": total_return,
				"price_return": price_return,
				"dividend_contribution": dividend_contribution,
				"total_annual_return": total_annual_return,
				"price_annual_return": price_annual_return,
				"dividend_annual_contribution": total_annual_return - price_annual_return
			},
			"performance_metrics": {
				"ending_shares": current_shares,
				"initial_shares": initial_shares,
				"share_growth": (current_shares - initial_shares) / initial_shares * 100,
				"dividend_reinvestment_rate": (current_shares - initial_shares) / initial_shares * 100
			},
			"daily_values": daily_values
		}

	# ==================== 批量操作方法 ====================

	async def batch_insert_factors (
			self,
			records: List[Dict[str, Any]],
			conflict_strategy: str = "upsert"
	) -> int:
		"""
		批量插入基金复权因子数据

		Args:
			records: 复权因子记录列表
			conflict_strategy: 冲突处理策略

		Returns:
			成功插入的记录数
		"""
		return await self.batch_insert(records, conflict_strategy)

	async def validate_factor_consistency (
			self,
			ts_code: str,
			reference_date: datetime
	) -> Dict[str, Any]:
		"""
		验证复权因子一致性

		Args:
			ts_code: 基金代码
			reference_date: 参考日期

		Returns:
			一致性验证结果
		"""
		# 获取参考日期前后一段时间的因子
		start_date = reference_date - timedelta(days=30)
		end_date = reference_date + timedelta(days=30)

		factors = await self.get_by_code_and_date_range(
			ts_code, start_date, end_date
		)

		if not factors:
			return {"status": "no_data", "message": "未找到相关数据"}

		# 找到参考日期的因子
		reference_factor = None
		for factor in factors:
			if factor.trade_date == reference_date:
				reference_factor = factor
				break

		if not reference_factor:
			return {"status": "missing_reference", "message": "未找到参考日期的因子"}

		# 检查因子的单调性（应该随时间递减或不变）
		factors_before = [f for f in factors if f.trade_date < reference_date]
		factors_after = [f for f in factors if f.trade_date > reference_date]

		issues = []

		# 检查之前日期的因子不应大于参考因子
		for factor in factors_before:
			if float(factor.adj_factor) > float(reference_factor.adj_factor) * 1.001:  # 允许0.1%误差
				issues.append({
					"type": "inconsistency_before",
					"date": factor.trade_date,
					"factor": float(factor.adj_factor),
					"reference_factor": float(reference_factor.adj_factor),
					"difference": (float(factor.adj_factor) - float(reference_factor.adj_factor)) / float(
						reference_factor.adj_factor) * 100
				})

		# 检查之后日期的因子不应小于参考因子
		for factor in factors_after:
			if float(factor.adj_factor) < float(reference_factor.adj_factor) * 0.999:  # 允许0.1%误差
				issues.append({
					"type": "inconsistency_after",
					"date": factor.trade_date,
					"factor": float(factor.adj_factor),
					"reference_factor": float(reference_factor.adj_factor),
					"difference": (float(factor.adj_factor) - float(reference_factor.adj_factor)) / float(
						reference_factor.adj_factor) * 100
				})

		return {
			"ts_code": ts_code,
			"reference_date": reference_date,
			"reference_factor": float(reference_factor.adj_factor),
			"data_range": {
				"start_date": start_date,
				"end_date": end_date,
				"factors_found": len(factors)
			},
			"validation_results": {
				"issues_found": len(issues),
				"issues": issues,
				"status": "valid" if len(issues) == 0 else "needs_review",
				"confidence": max(0, 100 - len(issues) * 10)  # 每个问题扣10分
			}
		}