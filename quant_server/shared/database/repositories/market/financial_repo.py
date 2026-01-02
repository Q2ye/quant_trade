# -*- coding: utf-8 -*-
"""
财务数据仓库
位置：quant_server/shared/database/repositories/financial_repo.py
职责：管理财务报表数据访问（利润表、资产负债表、现金流量表等）
注意：假设存在相应的财务数据模型，需要根据实际模型调整
"""

from typing import List, Optional, Dict, Any, Tuple
from datetime import datetime, date
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, and_, or_, func, desc, text, distinct
from sqlalchemy.orm import selectinload, joinedload

from quant_server.shared.database.repositories.base import BaseRepository


# 假设的财务数据模型类
# 实际项目中应从实际的模型文件中导入
class IncomeStatement:
	"""利润表模型"""
	__tablename__ = 'income_statements'

	# 这里定义字段，实际模型可能不同
	pass


class BalanceSheet:
	"""资产负债表模型"""
	__tablename__ = 'balance_sheets'
	pass


class CashFlowStatement:
	"""现金流量表模型"""
	__tablename__ = 'cashflow_statements'
	pass


class FinancialIndicator:
	"""财务指标模型"""
	__tablename__ = 'financial_indicators'
	pass


class FinancialRepository:
	"""财务数据仓库 - 负责财务报表数据访问"""

	def __init__ (self, session: AsyncSession):
		self.session = session
		# 假设使用BaseRepository，实际模型需替换
		self.income_repo = BaseRepository[IncomeStatement](session, IncomeStatement)
		self.balance_repo = BaseRepository[BalanceSheet](session, BalanceSheet)
		self.cashflow_repo = BaseRepository[CashFlowStatement](session, CashFlowStatement)
		self.indicator_repo = BaseRepository[FinancialIndicator](session, FinancialIndicator)

	# ==================== 利润表操作 ====================

	async def get_income_statement (
			self,
			ts_code: str,
			report_date: date,
			report_type: str = "Q1"  # Q1, Q2, Q3, Q4, H1, H2, FY
	) -> Optional[IncomeStatement]:
		"""
		获取利润表

		Args:
			ts_code: 股票代码
			report_date: 报告日期
			report_type: 报告类型

		Returns:
			利润表数据或None
		"""
		query = text("""
                     SELECT *
                     FROM income_statements
                     WHERE ts_code = :ts_code
                       AND report_date = :report_date
                       AND report_type = :report_type
                     LIMIT 1
		             """)

		result = await self.session.execute(
			query,
			{
				"ts_code": ts_code,
				"report_date": report_date,
				"report_type": report_type
			}
		)

		row = result.fetchone()
		if row:
			# 将结果转换为IncomeStatement对象
			return IncomeStatement(**dict(row))

		return None

	async def get_income_statements_in_range (
			self,
			ts_code: str,
			start_date: date,
			end_date: date,
			report_type: str = None
	) -> List[Dict[str, Any]]:
		"""
		获取指定时间范围内的利润表数据

		Args:
			ts_code: 股票代码
			start_date: 开始日期
			end_date: 结束日期
			report_type: 报告类型（可选）

		Returns:
			利润表数据列表
		"""
		conditions = ["ts_code = :ts_code", "report_date >= :start_date", "report_date <= :end_date"]
		params = {
			"ts_code": ts_code,
			"start_date": start_date,
			"end_date": end_date
		}

		if report_type:
			conditions.append("report_type = :report_type")
			params["report_type"] = report_type

		query_text = f"""
            SELECT 
                report_date, report_type, 
                total_revenue, operating_income, net_profit,
                gross_profit_margin, operating_margin, net_margin
            FROM income_statements 
            WHERE {' AND '.join(conditions)}
            ORDER BY report_date DESC
        """

		result = await self.session.execute(text(query_text), params)
		rows = result.fetchall()

		return [
			{
				"report_date": row.report_date,
				"report_type": row.report_type,
				"total_revenue": row.total_revenue,
				"operating_income": row.operating_income,
				"net_profit": row.net_profit,
				"gross_profit_margin": row.gross_profit_margin,
				"operating_margin": row.operating_margin,
				"net_margin": row.net_margin
			}
			for row in rows
		]

	async def get_latest_income_statement (self, ts_code: str) -> Optional[Dict[str, Any]]:
		"""
		获取最新利润表

		Args:
			ts_code: 股票代码

		Returns:
			最新利润表数据或None
		"""
		query = text("""
                     SELECT report_date,
                            report_type,
                            total_revenue,
                            operating_income,
                            net_profit,
                            gross_profit_margin,
                            operating_margin,
                            net_margin
                     FROM income_statements
                     WHERE ts_code = :ts_code
                     ORDER BY report_date DESC
                     LIMIT 1
		             """)

		result = await self.session.execute(query, {"ts_code": ts_code})
		row = result.fetchone()

		if row:
			return {
				"report_date": row.report_date,
				"report_type": row.report_type,
				"total_revenue": row.total_revenue,
				"operating_income": row.operating_income,
				"net_profit": row.net_profit,
				"gross_profit_margin": row.gross_profit_margin,
				"operating_margin": row.operating_margin,
				"net_margin": row.net_margin
			}

		return None

	# ==================== 资产负债表操作 ====================

	async def get_balance_sheet (
			self,
			ts_code: str,
			report_date: date,
			report_type: str = "Q1"
	) -> Optional[Dict[str, Any]]:
		"""
		获取资产负债表

		Args:
			ts_code: 股票代码
			report_date: 报告日期
			report_type: 报告类型

		Returns:
			资产负债表数据或None
		"""
		query = text("""
                     SELECT total_assets,
                            total_liabilities,
                            total_equity,
                            current_assets,
                            current_liabilities,
                            fixed_assets,
                            intangible_assets,
                            debt_ratio,
                            current_ratio
                     FROM balance_sheets
                     WHERE ts_code = :ts_code
                       AND report_date = :report_date
                       AND report_type = :report_type
                     LIMIT 1
		             """)

		result = await self.session.execute(
			query,
			{
				"ts_code": ts_code,
				"report_date": report_date,
				"report_type": report_type
			}
		)

		row = result.fetchone()
		if row:
			return dict(row)

		return None

	async def get_balance_sheets_in_range (
			self,
			ts_code: str,
			start_date: date,
			end_date: date
	) -> List[Dict[str, Any]]:
		"""
		获取指定时间范围内的资产负债表数据

		Args:
			ts_code: 股票代码
			start_date: 开始日期
			end_date: 结束日期

		Returns:
			资产负债表数据列表
		"""
		query = text("""
                     SELECT report_date,
                            report_type,
                            total_assets,
                            total_liabilities,
                            total_equity,
                            current_assets,
                            current_liabilities,
                            debt_ratio,
                            current_ratio
                     FROM balance_sheets
                     WHERE ts_code = :ts_code
                       AND report_date >= :start_date
                       AND report_date <= :end_date
                     ORDER BY report_date DESC
		             """)

		result = await self.session.execute(
			query,
			{
				"ts_code": ts_code,
				"start_date": start_date,
				"end_date": end_date
			}
		)

		rows = result.fetchall()
		return [dict(row) for row in rows]

	# ==================== 现金流量表操作 ====================

	async def get_cashflow_statement (
			self,
			ts_code: str,
			report_date: date,
			report_type: str = "Q1"
	) -> Optional[Dict[str, Any]]:
		"""
		获取现金流量表

		Args:
			ts_code: 股票代码
			report_date: 报告日期
			report_type: 报告类型

		Returns:
			现金流量表数据或None
		"""
		query = text("""
                     SELECT operating_cashflow,
                            investing_cashflow,
                            financing_cashflow,
                            net_cashflow,
                            free_cashflow,
                            operating_cashflow_margin
                     FROM cashflow_statements
                     WHERE ts_code = :ts_code
                       AND report_date = :report_date
                       AND report_type = :report_type
                     LIMIT 1
		             """)

		result = await self.session.execute(
			query,
			{
				"ts_code": ts_code,
				"report_date": report_date,
				"report_type": report_type
			}
		)

		row = result.fetchone()
		if row:
			return dict(row)

		return None

	async def get_cashflow_statements_in_range (
			self,
			ts_code: str,
			start_date: date,
			end_date: date
	) -> List[Dict[str, Any]]:
		"""
		获取指定时间范围内的现金流量表数据

		Args:
			ts_code: 股票代码
			start_date: 开始日期
			end_date: 结束日期

		Returns:
			现金流量表数据列表
		"""
		query = text("""
                     SELECT report_date,
                            report_type,
                            operating_cashflow,
                            investing_cashflow,
                            financing_cashflow,
                            net_cashflow,
                            free_cashflow
                     FROM cashflow_statements
                     WHERE ts_code = :ts_code
                       AND report_date >= :start_date
                       AND report_date <= :end_date
                     ORDER BY report_date DESC
		             """)

		result = await self.session.execute(
			query,
			{
				"ts_code": ts_code,
				"start_date": start_date,
				"end_date": end_date
			}
		)

		rows = result.fetchall()
		return [dict(row) for row in rows]

	# ==================== 财务指标操作 ====================

	async def get_financial_indicators (
			self,
			ts_code: str,
			indicator_date: date
	) -> Optional[Dict[str, Any]]:
		"""
		获取财务指标

		Args:
			ts_code: 股票代码
			indicator_date: 指标日期

		Returns:
			财务指标数据或None
		"""
		query = text("""
                     SELECT roe,
                            roa,
                            gross_margin,
                            operating_margin,
                            net_margin,
                            asset_turnover,
                            inventory_turnover,
                            debt_to_equity,
                            current_ratio,
                            quick_ratio,
                            eps,
                            bps,
                            dps
                     FROM financial_indicators
                     WHERE ts_code = :ts_code
                       AND indicator_date = :indicator_date
                     LIMIT 1
		             """)

		result = await self.session.execute(
			query,
			{
				"ts_code": ts_code,
				"indicator_date": indicator_date
			}
		)

		row = result.fetchone()
		if row:
			return dict(row)

		return None

	async def get_indicators_in_range (
			self,
			ts_code: str,
			start_date: date,
			end_date: date
	) -> List[Dict[str, Any]]:
		"""
		获取指定时间范围内的财务指标

		Args:
			ts_code: 股票代码
			start_date: 开始日期
			end_date: 结束日期

		Returns:
			财务指标列表
		"""
		query = text("""
                     SELECT indicator_date,
                            roe,
                            roa,
                            gross_margin,
                            net_margin,
                            eps,
                            bps,
                            dps,
                            debt_to_equity,
                            current_ratio
                     FROM financial_indicators
                     WHERE ts_code = :ts_code
                       AND indicator_date >= :start_date
                       AND indicator_date <= :end_date
                     ORDER BY indicator_date DESC
		             """)

		result = await self.session.execute(
			query,
			{
				"ts_code": ts_code,
				"start_date": start_date,
				"end_date": end_date
			}
		)

		rows = result.fetchall()
		return [dict(row) for row in rows]

	# ==================== 财务分析操作 ====================

	async def analyze_financial_health (
			self,
			ts_code: str,
			analysis_date: date
	) -> Dict[str, Any]:
		"""
		分析财务健康状况

		Args:
			ts_code: 股票代码
			analysis_date: 分析日期

		Returns:
			财务健康状况分析
		"""
		# 获取最新的财务数据
		latest_income = await self.get_latest_income_statement(ts_code)
		latest_balance = await self.get_balance_sheets_in_range(
			ts_code,
			analysis_date - timedelta(days=365),
			analysis_date
		)
		latest_cashflow = await self.get_cashflow_statements_in_range(
			ts_code,
			analysis_date - timedelta(days=365),
			analysis_date
		)

		if not latest_income or not latest_balance or not latest_cashflow:
			return {"error": "财务数据不足"}

		# 提取最新资产负债表
		if latest_balance:
			latest_balance_data = latest_balance[0]
		else:
			return {"error": "资产负债表数据不足"}

		# 盈利能力分析
		profitability = {
			"roe": latest_income.get("net_profit", 0) / latest_balance_data.get("total_equity",
			                                                                    1) if latest_balance_data.get(
				"total_equity", 0) != 0 else 0,
			"roa": latest_income.get("net_profit", 0) / latest_balance_data.get("total_assets",
			                                                                    1) if latest_balance_data.get(
				"total_assets", 0) != 0 else 0,
			"gross_margin": latest_income.get("gross_profit_margin", 0),
			"net_margin": latest_income.get("net_margin", 0)
		}

		# 偿债能力分析
		solvency = {
			"debt_ratio": latest_balance_data.get("debt_ratio", 0),
			"current_ratio": latest_balance_data.get("current_ratio", 0),
			"quick_ratio": (latest_balance_data.get("current_assets", 0) - 0) / latest_balance_data.get(
				"current_liabilities", 1) if latest_balance_data.get("current_liabilities", 0) != 0 else 0
		}

		# 运营能力分析
		if latest_cashflow:
			latest_cashflow_data = latest_cashflow[0]
			operating_efficiency = {
				"operating_cashflow_ratio": latest_cashflow_data.get("operating_cashflow", 0) / latest_income.get(
					"total_revenue", 1) if latest_income.get("total_revenue", 0) != 0 else 0,
				"free_cashflow": latest_cashflow_data.get("free_cashflow", 0)
			}
		else:
			operating_efficiency = {}

		# 增长性分析
		growth = {}
		if len(latest_balance) > 1:
			prev_balance = latest_balance[1]
			asset_growth = (latest_balance_data.get("total_assets", 0) - prev_balance.get("total_assets",
			                                                                              0)) / prev_balance.get(
				"total_assets", 1) if prev_balance.get("total_assets", 0) != 0 else 0
			equity_growth = (latest_balance_data.get("total_equity", 0) - prev_balance.get("total_equity",
			                                                                               0)) / prev_balance.get(
				"total_equity", 1) if prev_balance.get("total_equity", 0) != 0 else 0

			growth = {
				"asset_growth": asset_growth,
				"equity_growth": equity_growth
			}

		# 综合评分
		score = 0
		if profitability["roe"] > 0.15:
			score += 20
		elif profitability["roe"] > 0.10:
			score += 15
		elif profitability["roe"] > 0.05:
			score += 10

		if solvency["debt_ratio"] < 0.5:
			score += 20
		elif solvency["debt_ratio"] < 0.7:
			score += 15
		elif solvency["debt_ratio"] < 0.9:
			score += 10

		if solvency["current_ratio"] > 2:
			score += 20
		elif solvency["current_ratio"] > 1.5:
			score += 15
		elif solvency["current_ratio"] > 1:
			score += 10

		if operating_efficiency.get("operating_cashflow_ratio", 0) > 0.1:
			score += 20
		elif operating_efficiency.get("operating_cashflow_ratio", 0) > 0.05:
			score += 15
		elif operating_efficiency.get("operating_cashflow_ratio", 0) > 0:
			score += 10

		if operating_efficiency.get("free_cashflow", 0) > 0:
			score += 20

		health_status = "优秀" if score >= 80 else "良好" if score >= 60 else "一般" if score >= 40 else "较差"

		return {
			"ts_code": ts_code,
			"analysis_date": analysis_date,
			"profitability_analysis": profitability,
			"solvency_analysis": solvency,
			"operating_efficiency": operating_efficiency,
			"growth_analysis": growth,
			"financial_score": score,
			"health_status": health_status,
			"recommendation": "买入" if score >= 70 else "持有" if score >= 50 else "观望" if score >= 30 else "卖出"
		}

	async def compare_financial_metrics (
			self,
			ts_codes: List[str],
			metric: str = "roe",
			report_date: date = None
	) -> List[Dict[str, Any]]:
		"""
		比较多个股票的财务指标

		Args:
			ts_codes: 股票代码列表
			metric: 比较的指标
			report_date: 报告日期（可选，默认最新）

		Returns:
			比较结果列表
		"""
		if not ts_codes:
			return []

		if report_date is None:
			# 获取最新报告日期
			query = text("""
                         SELECT MAX(report_date) as latest_date
                         FROM income_statements
                         WHERE ts_code = :ts_code
			             """)

			# 为每个股票获取最新日期
			latest_dates = {}
			for ts_code in ts_codes:
				result = await self.session.execute(query, {"ts_code": ts_code})
				row = result.fetchone()
				if row and row.latest_date:
					latest_dates[ts_code] = row.latest_date
		else:
			latest_dates = {ts_code: report_date for ts_code in ts_codes}

		# 获取指标数据
		comparison_data = []
		for ts_code, date_value in latest_dates.items():
			indicators = await self.get_financial_indicators(ts_code, date_value)
			if indicators and metric in indicators:
				comparison_data.append({
					"ts_code": ts_code,
					"report_date": date_value,
					"metric_value": indicators[metric],
					"metric_name": metric
				})

		# 排序
		comparison_data.sort(key=lambda x: x["metric_value"], reverse=True)

		return comparison_data

	# ==================== 批量操作 ====================

	async def batch_create_income_statements (
			self,
			statements_data: List[Dict[str, Any]]
	) -> List[Dict[str, Any]]:
		"""
		批量创建利润表记录

		Args:
			statements_data: 利润表数据列表

		Returns:
			创建结果列表
		"""
		results = []

		for data in statements_data:
			query = text("""
                         INSERT INTO income_statements
                         (ts_code, report_date, report_type, total_revenue, operating_income, net_profit)
                         VALUES (:ts_code, :report_date, :report_type, :total_revenue, :operating_income, :net_profit)
                         ON CONFLICT (ts_code, report_date, report_type)
                             DO UPDATE SET total_revenue    = EXCLUDED.total_revenue,
                                           operating_income = EXCLUDED.operating_income,
                                           net_profit       = EXCLUDED.net_profit,
                                           updated_at       = NOW()
                         RETURNING id
			             """)

			result = await self.session.execute(query, data)
			row = result.fetchone()
			if row:
				results.append({"id": row[0], "ts_code": data["ts_code"], "report_date": data["report_date"]})

		return results

	async def batch_create_balance_sheets (
			self,
			sheets_data: List[Dict[str, Any]]
	) -> List[Dict[str, Any]]:
		"""
		批量创建资产负债表记录

		Args:
			sheets_data: 资产负债表数据列表

		Returns:
			创建结果列表
		"""
		results = []

		for data in sheets_data:
			query = text("""
                         INSERT INTO balance_sheets
                         (ts_code, report_date, report_type, total_assets, total_liabilities, total_equity)
                         VALUES (:ts_code, :report_date, :report_type, :total_assets, :total_liabilities, :total_equity)
                         ON CONFLICT (ts_code, report_date, report_type)
                             DO UPDATE SET total_assets      = EXCLUDED.total_assets,
                                           total_liabilities = EXCLUDED.total_liabilities,
                                           total_equity      = EXCLUDED.total_equity,
                                           updated_at        = NOW()
                         RETURNING id
			             """)

			result = await self.session.execute(query, data)
			row = result.fetchone()
			if row:
				results.append({"id": row[0], "ts_code": data["ts_code"], "report_date": data["report_date"]})

		return results

	async def batch_create_financial_indicators (
			self,
			indicators_data: List[Dict[str, Any]]
	) -> List[Dict[str, Any]]:
		"""
		批量创建财务指标记录

		Args:
			indicators_data: 财务指标数据列表

		Returns:
			创建结果列表
		"""
		results = []

		for data in indicators_data:
			query = text("""
                         INSERT INTO financial_indicators
                             (ts_code, indicator_date, roe, roa, eps)
                         VALUES (:ts_code, :indicator_date, :roe, :roa, :eps)
                         ON CONFLICT (ts_code, indicator_date)
                             DO UPDATE SET roe        = EXCLUDED.roe,
                                           roa        = EXCLUDED.roa,
                                           eps        = EXCLUDED.eps,
                                           updated_at = NOW()
                         RETURNING id
			             """)

			result = await self.session.execute(query, data)
			row = result.fetchone()
			if row:
				results.append({"id": row[0], "ts_code": data["ts_code"], "indicator_date": data["indicator_date"]})

		return results