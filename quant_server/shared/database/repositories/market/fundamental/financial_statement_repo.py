# -*- coding: utf-8 -*-
"""
财务报表数据仓库（非时序数据）
继承BaseRepository，常规CRUD操作
位置：quant_server/shared/database/repositories/market/fundamental/financial_statement_repo.py
"""

from typing import List, Optional, Dict, Any, Tuple
from datetime import date, datetime
from enum import Enum
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, and_, or_, func, desc, asc, text, Column, Numeric
from sqlalchemy.sql import Select
from decimal import Decimal

from quant_server.shared.database.repositories.base.repository_base import BaseRepository, RepositoryError
from quant_server.shared.database.models.data_models import FinancialStatement


class ReportType(Enum):
	"""财务报表类型枚举"""
	BALANCE_SHEET = "balance_sheet"  # 资产负债表
	INCOME_STATEMENT = "income_statement"  # 利润表
	CASH_FLOW_STATEMENT = "cash_flow_statement"  # 现金流量表


class FinancialStatementRepository(BaseRepository[FinancialStatement]):
	"""财务报表数据Repository - 继承BaseRepository，非时序数据"""

	def __init__ (self, session: AsyncSession):
		"""初始化财务报表仓库"""
		super().__init__(session, FinancialStatement)

	# ==================== 业务查询方法 ====================

	async def get_by_ts_code_and_period (
			self,
			ts_code: str,
			report_type: str,
			end_date: date,
			period: str = "year"  # year, quarter, half_year
	) -> Optional[FinancialStatement]:
		"""
		根据股票代码、报表类型和期间获取财务报表

		Args:
			ts_code: 股票代码
			report_type: 报表类型
			end_date: 报告期截止日期
			period: 报告期间

		Returns:
			财务报表记录
		"""
		return await self.get_by(
			ts_code=ts_code,
			report_type=report_type,
			end_date=end_date,
			period=period
		)

	async def get_by_unique (
			self,
			ts_code: str,
			ann_date: date,
			report_type: str
	) -> Optional[FinancialStatement]:
		"""
		根据唯一键获取财务报表

		Args:
			ts_code: 股票代码
			ann_date: 公告日期
			report_type: 报表类型

		Returns:
			财务报表记录或None
		"""
		try:
			return await self.get_by(
				ts_code=ts_code,
				ann_date=ann_date,
				report_type=report_type
			)
		except Exception as e:
			raise RepositoryError(f"根据唯一键查询财务报表失败: {str(e)}")

	async def get_financial_statements (
			self,
			ts_code: str,
			report_type: str,
			start_date: Optional[date] = None,
			end_date: Optional[date] = None,
			limit: int = 20
	) -> List[FinancialStatement]:
		"""
		获取财务报表时间序列

		Args:
			ts_code: 股票代码
			report_type: 报表类型
			start_date: 开始日期
			end_date: 结束日期
			limit: 返回数量限制

		Returns:
			财务报表列表
		"""
		filters = {
			"ts_code": ts_code,
			"report_type": report_type
		}

		statements = await self.get_many(limit=limit, **filters)

		# 过滤日期范围
		if start_date or end_date:
			filtered = []
			for stmt in statements:
				stmt_date = stmt.end_date
				if start_date and stmt_date < start_date:
					continue
				if end_date and stmt_date > end_date:
					continue
				filtered.append(stmt)
			return filtered

		return statements

	async def get_latest_financial_statement (
			self,
			ts_code: str,
			report_type: str,
			period: str = "year"
	) -> Optional[FinancialStatement]:
		"""
		获取最新财务报表

		Args:
			ts_code: 股票代码
			report_type: 报表类型
			period: 报告期间

		Returns:
			最新财务报表
		"""
		query = select(FinancialStatement).where(
			and_(
				FinancialStatement.ts_code == ts_code,
				FinancialStatement.report_type == report_type,
				FinancialStatement.period == period
			)
		).order_by(
			desc(FinancialStatement.end_date)
		).limit(1)

		result = await self.session.execute(query)
		return result.scalar_one_or_none()

	async def get_balance_sheet (
			self,
			ts_code: str,
			end_date: date
	) -> Optional[FinancialStatement]:
		"""
		获取资产负债表

		Args:
			ts_code: 股票代码
			end_date: 报告期截止日期

		Returns:
			资产负债表记录
		"""
		return await self.get_by_ts_code_and_period(
			ts_code=ts_code,
			report_type=ReportType.BALANCE_SHEET.value,
			end_date=end_date
		)

	async def get_income_statement (
			self,
			ts_code: str,
			end_date: date
	) -> Optional[FinancialStatement]:
		"""
		获取利润表

		Args:
			ts_code: 股票代码
			end_date: 报告期截止日期

		Returns:
			利润表记录
		"""
		return await self.get_by_ts_code_and_period(
			ts_code=ts_code,
			report_type=ReportType.INCOME_STATEMENT.value,
			end_date=end_date
		)

	async def get_cash_flow_statement (
			self,
			ts_code: str,
			end_date: date
	) -> Optional[FinancialStatement]:
		"""
		获取现金流量表

		Args:
			ts_code: 股票代码
			end_date: 报告期截止日期

		Returns:
			现金流量表记录
		"""
		return await self.get_by_ts_code_and_period(
			ts_code=ts_code,
			report_type=ReportType.CASH_FLOW_STATEMENT.value,
			end_date=end_date
		)

	async def get_quarterly_statements (
			self,
			ts_code: str,
			report_type: str,
			year: int,
			quarter: Optional[int] = None
	) -> List[FinancialStatement]:
		"""
		获取季度报表

		Args:
			ts_code: 股票代码
			report_type: 报表类型
			year: 年份
			quarter: 季度（1-4，None表示全年）

		Returns:
			季度报表列表
		"""
		filters = {
			"ts_code": ts_code,
			"report_type": report_type,
			"period": "quarter"
		}

		statements = await self.get_many(**filters)

		# 按年份和季度过滤
		filtered = []
		for stmt in statements:
			if stmt.end_date.year == year:
				if quarter is None or stmt.quarter == quarter:
					filtered.append(stmt)

		return sorted(filtered, key=lambda x: x.end_date)

	async def get_annual_statements (
			self,
			ts_code: str,
			report_type: str,
			years: Optional[List[int]] = None
	) -> List[FinancialStatement]:
		"""
		获取年度报表

		Args:
			ts_code: 股票代码
			report_type: 报表类型
			years: 年份列表

		Returns:
			年度报表列表
		"""
		filters = {
			"ts_code": ts_code,
			"report_type": report_type,
			"period": "year"
		}

		statements = await self.get_many(**filters)

		# 按年份过滤
		if years:
			filtered = []
			for stmt in statements:
				if stmt.end_date.year in years:
					filtered.append(stmt)
			return filtered

		return statements

	# ==================== 财务指标计算 ====================

	async def calculate_financial_ratios (
			self,
			ts_code: str,
			end_date: date
	) -> Dict[str, Any]:
		"""
		计算财务比率

		Args:
			ts_code: 股票代码
			end_date: 报告期截止日期

		Returns:
			财务比率字典
		"""
		ratios = {}

		# 获取三张报表
		balance_sheet = await self.get_balance_sheet(ts_code, end_date)
		income_stmt = await self.get_income_statement(ts_code, end_date)
		cash_flow_stmt = await self.get_cash_flow_statement(ts_code, end_date)

		if not balance_sheet or not income_stmt:
			return ratios

		# 盈利能力比率
		if income_stmt.revenue and income_stmt.revenue > 0:
			# 毛利率
			if income_stmt.gross_profit:
				ratios["gross_margin"] = float(income_stmt.gross_profit / income_stmt.revenue)

			# 净利率
			if income_stmt.net_profit:
				ratios["net_margin"] = float(income_stmt.net_profit / income_stmt.revenue)

		# 偿债能力比率
		if balance_sheet.total_assets and balance_sheet.total_assets > 0:
			# 资产负债率
			if balance_sheet.total_liabilities:
				ratios["debt_to_assets"] = float(balance_sheet.total_liabilities / balance_sheet.total_assets)

			# 权益乘数
			if balance_sheet.total_equity and balance_sheet.total_equity > 0:
				ratios["equity_multiplier"] = float(balance_sheet.total_assets / balance_sheet.total_equity)

		# 营运能力比率
		if balance_sheet.total_assets and income_stmt.revenue:
			# 总资产周转率
			ratios["asset_turnover"] = float(income_stmt.revenue / balance_sheet.total_assets)

		return ratios

	async def get_profitability_metrics (
			self,
			ts_code: str,
			start_date: date,
			end_date: date
	) -> List[Dict[str, Any]]:
		"""
		获取盈利能力指标时间序列

		Args:
			ts_code: 股票代码
			start_date: 开始日期
			end_date: 结束日期

		Returns:
			盈利能力指标列表
		"""
		metrics = []

		# 获取利润表历史数据
		income_statements = await self.get_financial_statements(
			ts_code=ts_code,
			report_type=ReportType.INCOME_STATEMENT.value,
			start_date=start_date,
			end_date=end_date
		)

		for stmt in income_statements:
			metric = {
				"end_date": stmt.end_date,
				"revenue": float(stmt.revenue) if stmt.revenue else None,
				"gross_profit": float(stmt.gross_profit) if stmt.gross_profit else None,
				"operating_profit": float(stmt.operating_profit) if stmt.operating_profit else None,
				"net_profit": float(stmt.net_profit) if stmt.net_profit else None
			}

			# 计算比率
			if stmt.revenue and stmt.revenue > 0:
				if stmt.gross_profit:
					metric["gross_margin"] = float(stmt.gross_profit / stmt.revenue)
				if stmt.net_profit:
					metric["net_margin"] = float(stmt.net_profit / stmt.revenue)

			metrics.append(metric)

		return metrics

	async def get_liquidity_metrics (
			self,
			ts_code: str,
			start_date: date,
			end_date: date
	) -> List[Dict[str, Any]]:
		"""
		获取流动性指标时间序列

		Args:
			ts_code: 股票代码
			start_date: 开始日期
			end_date: 结束日期

		Returns:
			流动性指标列表
		"""
		metrics = []

		# 获取资产负债表历史数据
		balance_sheets = await self.get_financial_statements(
			ts_code=ts_code,
			report_type=ReportType.BALANCE_SHEET.value,
			start_date=start_date,
			end_date=end_date
		)

		for sheet in balance_sheets:
			metric = {
				"end_date": sheet.end_date,
				"current_assets": float(sheet.current_assets) if sheet.current_assets else None,
				"current_liabilities": float(sheet.current_liabilities) if sheet.current_liabilities else None,
				"cash_and_equivalents": float(sheet.cash_and_equivalents) if sheet.cash_and_equivalents else None
			}

			# 计算流动比率
			if sheet.current_assets and sheet.current_liabilities and sheet.current_liabilities > 0:
				metric["current_ratio"] = float(sheet.current_assets / sheet.current_liabilities)

			# 计算速动比率（假设存货为0，简化计算）
			if sheet.cash_and_equivalents and sheet.current_liabilities and sheet.current_liabilities > 0:
				metric["quick_ratio"] = float(sheet.cash_and_equivalents / sheet.current_liabilities)

			metrics.append(metric)

		return metrics

	async def get_cash_flow_metrics (
			self,
			ts_code: str,
			start_date: date,
			end_date: date
	) -> List[Dict[str, Any]]:
		"""
		获取现金流指标时间序列

		Args:
			ts_code: 股票代码
			start_date: 开始日期
			end_date: 结束日期

		Returns:
			现金流指标列表
		"""
		metrics = []

		# 获取现金流量表历史数据
		cash_flow_statements = await self.get_financial_statements(
			ts_code=ts_code,
			report_type=ReportType.CASH_FLOW_STATEMENT.value,
			start_date=start_date,
			end_date=end_date
		)

		for stmt in cash_flow_statements:
			metric = {
				"end_date": stmt.end_date,
				"operating_cash_flow": float(stmt.operating_cash_flow) if stmt.operating_cash_flow else None,
				"investing_cash_flow": float(stmt.investing_cash_flow) if stmt.investing_cash_flow else None,
				"financing_cash_flow": float(stmt.financing_cash_flow) if stmt.financing_cash_flow else None,
				"net_cash_flow": float(stmt.net_cash_flow) if stmt.net_cash_flow else None
			}

			metrics.append(metric)

		return metrics

	# ==================== 统计分析 ====================

	async def get_industry_comparison (
			self,
			ts_code: str,
			end_date: date,
			industry: str
	) -> Dict[str, Any]:
		"""
		获取行业对比数据

		Args:
			ts_code: 股票代码
			end_date: 报告期截止日期
			industry: 行业名称

		Returns:
			行业对比数据
		"""
		query = text("""
            SELECT 
                AVG(bs.total_assets) as avg_total_assets,
                AVG(is.revenue) as avg_revenue,
                AVG(is.net_profit) as avg_net_profit,
                COUNT(*) as company_count
            FROM financial_statements bs
            JOIN financial_statements is ON bs.ts_code = is.ts_code 
                AND bs.end_date = is.end_date
                AND bs.report_type = 'balance_sheet'
                AND is.report_type = 'income_statement'
            JOIN stock_basic sb ON bs.ts_code = sb.ts_code
            WHERE bs.end_date = :end_date
                AND sb.industry = :industry
                AND bs.period = 'year'
                AND is.period = 'year'
        """)

		result = await self.session.execute(
			query,
			{"end_date": end_date, "industry": industry}
		)
		row = result.fetchone()

		if not row:
			return {}

		# 获取当前公司的数据
		company_balance = await self.get_balance_sheet(ts_code, end_date)
		company_income = await self.get_income_statement(ts_code, end_date)

		return {
			"industry_averages": {
				"avg_total_assets": float(row.avg_total_assets) if row.avg_total_assets else None,
				"avg_revenue": float(row.avg_revenue) if row.avg_revenue else None,
				"avg_net_profit": float(row.avg_net_profit) if row.avg_net_profit else None
			},
			"company_count": row.company_count,
			"company_data": {
				"total_assets": float(
					company_balance.total_assets) if company_balance and company_balance.total_assets else None,
				"revenue": float(company_income.revenue) if company_income and company_income.revenue else None,
				"net_profit": float(company_income.net_profit) if company_income and company_income.net_profit else None
			}
		}

	async def get_financial_summary (
			self,
			ts_code: str,
			end_date: date
	) -> Dict[str, Any]:
		"""
		获取财务摘要

		Args:
			ts_code: 股票代码
			end_date: 报告期截止日期

		Returns:
			财务摘要字典
		"""
		summary = {}

		# 获取三张报表
		balance_sheet = await self.get_balance_sheet(ts_code, end_date)
		income_stmt = await self.get_income_statement(ts_code, end_date)
		cash_flow_stmt = await self.get_cash_flow_statement(ts_code, end_date)

		if balance_sheet:
			summary["balance_sheet"] = {
				"total_assets": float(balance_sheet.total_assets) if balance_sheet.total_assets else None,
				"total_liabilities": float(
					balance_sheet.total_liabilities) if balance_sheet.total_liabilities else None,
				"total_equity": float(balance_sheet.total_equity) if balance_sheet.total_equity else None,
				"current_ratio": None
			}

			# 计算流动比率
			if balance_sheet.current_assets and balance_sheet.current_liabilities:
				if balance_sheet.current_liabilities > 0:
					summary["balance_sheet"]["current_ratio"] = float(
						balance_sheet.current_assets / balance_sheet.current_liabilities
					)

		if income_stmt:
			summary["income_statement"] = {
				"revenue": float(income_stmt.revenue) if income_stmt.revenue else None,
				"gross_profit": float(income_stmt.gross_profit) if income_stmt.gross_profit else None,
				"operating_profit": float(income_stmt.operating_profit) if income_stmt.operating_profit else None,
				"net_profit": float(income_stmt.net_profit) if income_stmt.net_profit else None,
				"eps": float(income_stmt.eps) if income_stmt.eps else None
			}

			# 计算毛利率和净利率
			if income_stmt.revenue and income_stmt.revenue > 0:
				if income_stmt.gross_profit:
					summary["income_statement"]["gross_margin"] = float(
						income_stmt.gross_profit / income_stmt.revenue
					)
				if income_stmt.net_profit:
					summary["income_statement"]["net_margin"] = float(
						income_stmt.net_profit / income_stmt.revenue
					)

		if cash_flow_stmt:
			summary["cash_flow_statement"] = {
				"operating_cash_flow": float(
					cash_flow_stmt.operating_cash_flow) if cash_flow_stmt.operating_cash_flow else None,
				"investing_cash_flow": float(
					cash_flow_stmt.investing_cash_flow) if cash_flow_stmt.investing_cash_flow else None,
				"financing_cash_flow": float(
					cash_flow_stmt.financing_cash_flow) if cash_flow_stmt.financing_cash_flow else None,
				"net_cash_flow": float(cash_flow_stmt.net_cash_flow) if cash_flow_stmt.net_cash_flow else None
			}

		return summary

	# ==================== 批量操作 ====================

	async def batch_upsert_statements (
			self,
			data_list: List[Dict[str, Any]]
	) -> List[FinancialStatement]:
		"""
		批量插入或更新财务报表记录

		Args:
			data_list: 数据列表

		Returns:
			更新后的财务报表记录列表
		"""
		return await self.batch_upsert(
			match_fields=["ts_code", "report_type", "end_date", "period"],
			data_list=data_list
		)

	async def delete_old_statements (
			self,
			before_date: date,
			ts_code: Optional[str] = None
	) -> int:
		"""
		删除指定日期之前的财务报表

		Args:
			before_date: 截止日期
			ts_code: 股票代码（可选）

		Returns:
			删除的记录数
		"""
		filters = {"end_date__lt": before_date}

		if ts_code:
			filters["ts_code"] = ts_code

		return await self.delete_by(**filters)

	async def get_date_range (
			self,
			ts_code: str,
			report_type: str,
			period: str = "year"
	) -> Dict[str, Optional[date]]:
		"""
		获取财务报表日期范围

		Args:
			ts_code: 股票代码
			report_type: 报表类型
			period: 报告期间

		Returns:
			日期范围字典
		"""
		query = select(
			func.min(FinancialStatement.end_date),
			func.max(FinancialStatement.end_date)
		).where(
			and_(
				FinancialStatement.ts_code == ts_code,
				FinancialStatement.report_type == report_type,
				FinancialStatement.period == period
			)
		)

		result = await self.session.execute(query)
		min_date, max_date = result.first()

		return {
			"min_date": min_date,
			"max_date": max_date
		}

	async def get_latest_by_ts_code(
			self,
			ts_code: str,
			report_type: Optional[str] = None
	) -> Optional[FinancialStatement]:
		"""
		获取指定股票代码的最新财务报表

		Args:
			ts_code: 股票代码
			report_type: 报表类型（可选），如果为None则返回任何类型的最新报表

		Returns:
			Optional[FinancialStatement]: 最新财务报表记录或None
		"""
		try:
			if report_type:
				# 获取指定报表类型的最新数据
				return await self.get_latest_financial_statement(
					ts_code=ts_code,
					report_type=report_type,
					period="year"  # 默认获取年度报告，可以调整
				)
			else:
				# 获取所有报表类型中的最新数据
				query = select(FinancialStatement).where(
					FinancialStatement.ts_code == ts_code
				).order_by(
					desc(FinancialStatement.end_date)
				).limit(1)

				result = await self.session.execute(query)
				return result.scalar_one_or_none()

		except Exception as e:
			raise RepositoryError(f"获取最新财务报表失败: {str(e)}")