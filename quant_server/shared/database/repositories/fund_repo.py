# -*- coding: utf-8 -*-
"""
基金数据仓库
位置：quant_server/shared/database/repositories/fund_repo.py
职责：管理基金基础信息、净值、持仓等数据访问
注意：基金数据包括公募基金、私募基金等各类基金产品
"""

from typing import List, Optional, Dict, Any, Tuple
from datetime import datetime, date
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, and_, or_, func, desc, text, distinct
from sqlalchemy.orm import selectinload, joinedload

from quant_server.shared.database.repositories.base import BaseRepository


# 假设的基金数据模型类
class FundBasic:
	"""基金基础信息模型"""
	__tablename__ = 'fund_basic'
	pass


class FundNav:
	"""基金净值数据模型"""
	__tablename__ = 'fund_nav'
	pass


class FundPortfolio:
	"""基金持仓模型"""
	__tablename__ = 'fund_portfolio'
	pass


class FundManager:
	"""基金经理模型"""
	__tablename__ = 'fund_managers'
	pass


class FundRepository:
	"""基金数据仓库 - 负责基金相关数据访问"""

	def __init__ (self, session: AsyncSession):
		self.session = session
		self.fund_basic_repo = BaseRepository[FundBasic](session, FundBasic)
		self.fund_nav_repo = BaseRepository[FundNav](session, FundNav)
		self.fund_portfolio_repo = BaseRepository[FundPortfolio](session, FundPortfolio)
		self.fund_manager_repo = BaseRepository[FundManager](session, FundManager)

	# ==================== 基金基础信息操作 ====================

	async def get_fund_basic (self, fund_code: str) -> Optional[Dict[str, Any]]:
		"""
		获取基金基础信息

		Args:
			fund_code: 基金代码

		Returns:
			基金基础信息或None
		"""
		query = text("""
                     SELECT fund_code,
                            fund_name,
                            fund_type,
                            setup_date,
                            maturity_date,
                            fund_scale,
                            manager_code,
                            manager_name,
                            custodian,
                            benchmark_index,
                            investment_style,
                            risk_level
                     FROM fund_basic
                     WHERE fund_code = :fund_code
                     LIMIT 1
		             """)

		result = await self.session.execute(query, {"fund_code": fund_code})
		row = result.fetchone()

		if row:
			return dict(row)

		return None

	async def search_funds (
			self,
			keyword: str,
			fund_type: str = None,
			limit: int = 100,
			skip: int = 0
	) -> List[Dict[str, Any]]:
		"""
		搜索基金

		Args:
			keyword: 搜索关键词（可匹配代码、名称等）
			fund_type: 基金类型过滤（可选）
			limit: 返回数量限制
			skip: 跳过数量

		Returns:
			基金列表
		"""
		conditions = ["(fund_code LIKE :keyword OR fund_name LIKE :keyword)"]
		params = {
			"keyword": f"%{keyword}%",
			"limit": limit,
			"skip": skip
		}

		if fund_type:
			conditions.append("fund_type = :fund_type")
			params["fund_type"] = fund_type

		query_text = f"""
            SELECT 
                fund_code, fund_name, fund_type, 
                setup_date, fund_scale, manager_name
            FROM fund_basic 
            WHERE {' AND '.join(conditions)}
            ORDER BY fund_code
            LIMIT :limit OFFSET :skip
        """

		result = await self.session.execute(text(query_text), params)
		rows = result.fetchall()

		return [dict(row) for row in rows]

	async def get_funds_by_manager (self, manager_code: str) -> List[Dict[str, Any]]:
		"""
		获取基金经理管理的基金

		Args:
			manager_code: 基金经理代码

		Returns:
			基金列表
		"""
		query = text("""
                     SELECT fund_code,
                            fund_name,
                            fund_type,
                            setup_date,
                            fund_scale
                     FROM fund_basic
                     WHERE manager_code = :manager_code
                     ORDER BY setup_date DESC
		             """)

		result = await self.session.execute(query, {"manager_code": manager_code})
		rows = result.fetchall()

		return [dict(row) for row in rows]

	async def get_funds_by_type (self, fund_type: str) -> List[Dict[str, Any]]:
		"""
		根据类型获取基金

		Args:
			fund_type: 基金类型

		Returns:
			基金列表
		"""
		query = text("""
                     SELECT fund_code,
                            fund_name,
                            setup_date,
                            fund_scale,
                            manager_name
                     FROM fund_basic
                     WHERE fund_type = :fund_type
                     ORDER BY fund_scale DESC
		             """)

		result = await self.session.execute(query, {"fund_type": fund_type})
		rows = result.fetchall()

		return [dict(row) for row in rows]

	async def create_fund_basic (self, fund_data: Dict[str, Any]) -> Dict[str, Any]:
		"""
		创建基金基础信息

		Args:
			fund_data: 基金数据

		Returns:
			创建结果
		"""
		query = text("""
                     INSERT INTO fund_basic
                     (fund_code, fund_name, fund_type, setup_date, fund_scale, manager_code, manager_name)
                     VALUES (:fund_code, :fund_name, :fund_type, :setup_date, :fund_scale, :manager_code, :manager_name)
                     RETURNING fund_code
		             """)

		result = await self.session.execute(query, fund_data)
		row = result.fetchone()

		if row:
			return {"fund_code": row[0], "status": "created"}

		return {"status": "failed"}

	# ==================== 基金净值操作 ====================

	async def get_fund_nav (
			self,
			fund_code: str,
			nav_date: date
	) -> Optional[Dict[str, Any]]:
		"""
		获取基金净值

		Args:
			fund_code: 基金代码
			nav_date: 净值日期

		Returns:
			基金净值数据或None
		"""
		query = text("""
                     SELECT nav_date,
                            unit_nav,
                            accumulated_nav,
                            daily_return,
                            weekly_return,
                            monthly_return,
                            annualized_return,
                            max_drawdown,
                            sharpe_ratio
                     FROM fund_nav
                     WHERE fund_code = :fund_code
                       AND nav_date = :nav_date
                     LIMIT 1
		             """)

		result = await self.session.execute(
			query,
			{"fund_code": fund_code, "nav_date": nav_date}
		)

		row = result.fetchone()
		if row:
			return dict(row)

		return None

	async def get_fund_nav_in_range (
			self,
			fund_code: str,
			start_date: date,
			end_date: date
	) -> List[Dict[str, Any]]:
		"""
		获取指定时间范围内的基金净值

		Args:
			fund_code: 基金代码
			start_date: 开始日期
			end_date: 结束日期

		Returns:
			基金净值列表
		"""
		query = text("""
                     SELECT nav_date,
                            unit_nav,
                            accumulated_nav,
                            daily_return
                     FROM fund_nav
                     WHERE fund_code = :fund_code
                       AND nav_date >= :start_date
                       AND nav_date <= :end_date
                     ORDER BY nav_date
		             """)

		result = await self.session.execute(
			query,
			{
				"fund_code": fund_code,
				"start_date": start_date,
				"end_date": end_date
			}
		)

		rows = result.fetchall()
		return [dict(row) for row in rows]

	async def get_latest_fund_nav (self, fund_code: str) -> Optional[Dict[str, Any]]:
		"""
		获取最新基金净值

		Args:
			fund_code: 基金代码

		Returns:
			最新基金净值或None
		"""
		query = text("""
                     SELECT nav_date,
                            unit_nav,
                            accumulated_nav,
                            daily_return
                     FROM fund_nav
                     WHERE fund_code = :fund_code
                     ORDER BY nav_date DESC
                     LIMIT 1
		             """)

		result = await self.session.execute(query, {"fund_code": fund_code})
		row = result.fetchone()

		if row:
			return dict(row)

		return None

	async def create_fund_nav (self, nav_data: Dict[str, Any]) -> Dict[str, Any]:
		"""
		创建基金净值记录

		Args:
			nav_data: 净值数据

		Returns:
			创建结果
		"""
		query = text("""
                     INSERT INTO fund_nav
                         (fund_code, nav_date, unit_nav, accumulated_nav, daily_return)
                     VALUES (:fund_code, :nav_date, :unit_nav, :accumulated_nav, :daily_return)
                     ON CONFLICT (fund_code, nav_date)
                         DO UPDATE SET unit_nav        = EXCLUDED.unit_nav,
                                       accumulated_nav = EXCLUDED.accumulated_nav,
                                       daily_return    = EXCLUDED.daily_return,
                                       updated_at      = NOW()
                     RETURNING id
		             """)

		result = await self.session.execute(query, nav_data)
		row = result.fetchone()

		if row:
			return {"id": row[0], "fund_code": nav_data["fund_code"], "nav_date": nav_data["nav_date"]}

		return {"status": "failed"}

	# ==================== 基金持仓操作 ====================

	async def get_fund_portfolio (
			self,
			fund_code: str,
			report_date: date
	) -> List[Dict[str, Any]]:
		"""
		获取基金持仓

		Args:
			fund_code: 基金代码
			report_date: 报告日期

		Returns:
			基金持仓列表
		"""
		query = text("""
                     SELECT stock_code,
                            stock_name,
                            industry,
                            holding_shares,
                            holding_value,
                            weight,
                            cost_price,
                            market_price,
                            unrealized_pnl
                     FROM fund_portfolio
                     WHERE fund_code = :fund_code
                       AND report_date = :report_date
                     ORDER BY weight DESC
		             """)

		result = await self.session.execute(
			query,
			{"fund_code": fund_code, "report_date": report_date}
		)

		rows = result.fetchall()
		return [dict(row) for row in rows]

	async def get_latest_fund_portfolio (self, fund_code: str) -> Optional[List[Dict[str, Any]]]:
		"""
		获取最新基金持仓

		Args:
			fund_code: 基金代码

		Returns:
			最新基金持仓或None
		"""
		# 首先找到最新的报告日期
		query = text("""
                     SELECT MAX(report_date) as latest_date
                     FROM fund_portfolio
                     WHERE fund_code = :fund_code
		             """)

		result = await self.session.execute(query, {"fund_code": fund_code})
		row = result.fetchone()

		if not row or not row.latest_date:
			return None

		return await self.get_fund_portfolio(fund_code, row.latest_date)

	async def get_funds_holding_stock (self, stock_code: str, report_date: date = None) -> List[Dict[str, Any]]:
		"""
		获取持有某股票的基金

		Args:
			stock_code: 股票代码
			report_date: 报告日期（可选，默认最新）

		Returns:
			基金列表
		"""
		if report_date is None:
			# 获取最新的报告日期
			query = text("""
                         SELECT MAX(report_date) as latest_date
                         FROM fund_portfolio
                         WHERE stock_code = :stock_code
			             """)

			result = await self.session.execute(query, {"stock_code": stock_code})
			row = result.fetchone()

			if not row or not row.latest_date:
				return []

			report_date = row.latest_date

		query = text("""
                     SELECT fp.fund_code,
                            fb.fund_name,
                            fb.fund_type,
                            fp.holding_shares,
                            fp.holding_value,
                            fp.weight
                     FROM fund_portfolio fp
                              JOIN fund_basic fb ON fp.fund_code = fb.fund_code
                     WHERE fp.stock_code = :stock_code
                       AND fp.report_date = :report_date
                     ORDER BY fp.holding_value DESC
		             """)

		result = await self.session.execute(
			query,
			{"stock_code": stock_code, "report_date": report_date}
		)

		rows = result.fetchall()
		return [dict(row) for row in rows]

	# ==================== 基金经理操作 ====================

	async def get_fund_manager (self, manager_code: str) -> Optional[Dict[str, Any]]:
		"""
		获取基金经理信息

		Args:
			manager_code: 基金经理代码

		Returns:
			基金经理信息或None
		"""
		query = text("""
                     SELECT manager_code,
                            manager_name,
                            gender,
                            education,
                            certification,
                            experience_years,
                            start_date,
                            investment_style,
                            performance_rating
                     FROM fund_managers
                     WHERE manager_code = :manager_code
                     LIMIT 1
		             """)

		result = await self.session.execute(query, {"manager_code": manager_code})
		row = result.fetchone()

		if row:
			return dict(row)

		return None

	async def search_managers (
			self,
			keyword: str,
			limit: int = 50,
			skip: int = 0
	) -> List[Dict[str, Any]]:
		"""
		搜索基金经理

		Args:
			keyword: 搜索关键词
			limit: 返回数量限制
			skip: 跳过数量

		Returns:
			基金经理列表
		"""
		query = text("""
                     SELECT manager_code,
                            manager_name,
                            experience_years,
                            investment_style,
                            performance_rating
                     FROM fund_managers
                     WHERE manager_name LIKE :keyword
                     ORDER BY performance_rating DESC
                     LIMIT :limit OFFSET :skip
		             """)

		result = await self.session.execute(
			query,
			{"keyword": f"%{keyword}%", "limit": limit, "skip": skip}
		)

		rows = result.fetchall()
		return [dict(row) for row in rows]

	async def get_manager_performance (
			self,
			manager_code: str,
			start_date: date,
			end_date: date
	) -> Dict[str, Any]:
		"""
		获取基金经理绩效

		Args:
			manager_code: 基金经理代码
			start_date: 开始日期
			end_date: 结束日期

		Returns:
			基金经理绩效
		"""
		# 获取经理管理的基金
		funds = await self.get_funds_by_manager(manager_code)

		if not funds:
			return {"error": "该经理没有管理基金"}

		fund_codes = [fund["fund_code"] for fund in funds]

		# 获取这些基金的净值数据
		query = text("""
                     SELECT fund_code,
                            AVG(annualized_return) as avg_annual_return,
                            AVG(sharpe_ratio)      as avg_sharpe_ratio,
                            AVG(max_drawdown)      as avg_max_drawdown
                     FROM fund_nav
                     WHERE fund_code IN :fund_codes
                       AND nav_date >= :start_date
                       AND nav_date <= :end_date
                     GROUP BY fund_code
		             """)

		result = await self.session.execute(
			query,
			{"fund_codes": tuple(fund_codes), "start_date": start_date, "end_date": end_date}
		)

		rows = result.fetchall()

		if not rows:
			return {"error": "没有找到净值数据"}

		# 计算平均绩效
		total_return = 0
		total_sharpe = 0
		total_drawdown = 0
		count = 0

		for row in rows:
			total_return += row.avg_annual_return or 0
			total_sharpe += row.avg_sharpe_ratio or 0
			total_drawdown += row.avg_max_drawdown or 0
			count += 1

		avg_return = total_return / count if count > 0 else 0
		avg_sharpe = total_sharpe / count if count > 0 else 0
		avg_drawdown = total_drawdown / count if count > 0 else 0

		# 绩效评级
		if avg_return > 0.15 and avg_sharpe > 1.5:
			rating = "优秀"
		elif avg_return > 0.10 and avg_sharpe > 1.0:
			rating = "良好"
		elif avg_return > 0.05:
			rating = "一般"
		else:
			rating = "较差"

		return {
			"manager_code": manager_code,
			"analysis_period": {
				"start_date": start_date,
				"end_date": end_date
			},
			"managed_funds": len(funds),
			"performance_metrics": {
				"average_annual_return": avg_return,
				"average_sharpe_ratio": avg_sharpe,
				"average_max_drawdown": avg_drawdown
			},
			"performance_rating": rating,
			"fund_details": [
				{
					"fund_code": row.fund_code,
					"annual_return": row.avg_annual_return,
					"sharpe_ratio": row.avg_sharpe_ratio,
					"max_drawdown": row.avg_max_drawdown
				}
				for row in rows
			]
		}

	# ==================== 基金分析操作 ====================

	async def analyze_fund_performance (
			self,
			fund_code: str,
			start_date: date,
			end_date: date
	) -> Dict[str, Any]:
		"""
		分析基金表现

		Args:
			fund_code: 基金代码
			start_date: 开始日期
			end_date: 结束日期

		Returns:
			基金表现分析
		"""
		# 获取基金净值数据
		nav_data = await self.get_fund_nav_in_range(fund_code, start_date, end_date)

		if not nav_data:
			return {"error": "没有找到净值数据"}

		# 获取基金基础信息
		fund_info = await self.get_fund_basic(fund_code)

		# 计算收益
		first_nav = nav_data[0]["unit_nav"]
		last_nav = nav_data[-1]["unit_nav"]
		total_return = (last_nav - first_nav) / first_nav

		# 计算日收益
		daily_returns = []
		for i in range(1, len(nav_data)):
			prev_nav = nav_data[i - 1]["unit_nav"]
			curr_nav = nav_data[i]["unit_nav"]
			daily_return = (curr_nav - prev_nav) / prev_nav
			daily_returns.append(daily_return)

		# 计算统计指标
		import statistics
		if daily_returns:
			avg_return = statistics.mean(daily_returns)
			volatility = statistics.stdev(daily_returns) * (252 ** 0.5)  # 年化波动率
			sharpe_ratio = (avg_return * 252) / volatility if volatility != 0 else 0
		else:
			avg_return = 0
			volatility = 0
			sharpe_ratio = 0

		# 计算最大回撤
		max_drawdown = 0
		peak = first_nav
		for nav in nav_data:
			current_nav = nav["unit_nav"]
			if current_nav > peak:
				peak = current_nav
			drawdown = (peak - current_nav) / peak
			if drawdown > max_drawdown:
				max_drawdown = drawdown

		# 获取最新持仓
		latest_portfolio = await self.get_latest_fund_portfolio(fund_code)

		# 行业分布
		industry_distribution = {}
		if latest_portfolio:
			for holding in latest_portfolio:
				industry = holding.get("industry", "未知")
				weight = holding.get("weight", 0)
				if industry not in industry_distribution:
					industry_distribution[industry] = 0
				industry_distribution[industry] += weight

		# 持仓集中度
		if latest_portfolio:
			top_10_weight = sum(h["weight"] for h in latest_portfolio[:10])
			concentration = top_10_weight / sum(h["weight"] for h in latest_portfolio) if latest_portfolio else 0
		else:
			concentration = 0

		return {
			"fund_info": fund_info,
			"analysis_period": {
				"start_date": start_date,
				"end_date": end_date,
				"days": len(nav_data)
			},
			"performance_metrics": {
				"total_return": total_return,
				"annualized_return": total_return * (252 / len(nav_data)) if len(nav_data) > 0 else 0,
				"volatility": volatility,
				"sharpe_ratio": sharpe_ratio,
				"max_drawdown": max_drawdown,
				"average_daily_return": avg_return
			},
			"portfolio_analysis": {
				"total_holdings": len(latest_portfolio) if latest_portfolio else 0,
				"industry_distribution": industry_distribution,
				"concentration_ratio": concentration,
				"top_holdings": latest_portfolio[:10] if latest_portfolio else []
			},
			"risk_assessment": {
				"risk_level": fund_info.get("risk_level", "未知") if fund_info else "未知",
				"volatility_rank": "高" if volatility > 0.25 else "中" if volatility > 0.15 else "低",
				"drawdown_rank": "高" if max_drawdown > 0.20 else "中" if max_drawdown > 0.10 else "低"
			}
		}

	async def compare_funds_performance (
			self,
			fund_codes: List[str],
			start_date: date,
			end_date: date
	) -> List[Dict[str, Any]]:
		"""
		比较多个基金的表现

		Args:
			fund_codes: 基金代码列表
			start_date: 开始日期
			end_date: 结束日期

		Returns:
			基金比较结果
		"""
		comparison_results = []

		for fund_code in fund_codes:
			# 获取净值数据
			nav_data = await self.get_fund_nav_in_range(fund_code, start_date, end_date)

			if not nav_data:
				continue

			# 计算收益
			first_nav = nav_data[0]["unit_nav"]
			last_nav = nav_data[-1]["unit_nav"]
			total_return = (last_nav - first_nav) / first_nav

			# 获取基金信息
			fund_info = await self.get_fund_basic(fund_code)

			comparison_results.append({
				"fund_code": fund_code,
				"fund_name": fund_info.get("fund_name", "未知") if fund_info else "未知",
				"fund_type": fund_info.get("fund_type", "未知") if fund_info else "未知",
				"manager": fund_info.get("manager_name", "未知") if fund_info else "未知",
				"total_return": total_return,
				"annualized_return": total_return * (252 / len(nav_data)) if len(nav_data) > 0 else 0,
				"start_nav": first_nav,
				"end_nav": last_nav,
				"data_points": len(nav_data)
			})

		# 按总收益排序
		comparison_results.sort(key=lambda x: x["total_return"], reverse=True)

		return comparison_results

	# ==================== 批量操作 ====================

	async def batch_create_fund_nav (self, nav_data_list: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
		"""
		批量创建基金净值记录

		Args:
			nav_data_list: 净值数据列表

		Returns:
			创建结果列表
		"""
		results = []

		for nav_data in nav_data_list:
			result = await self.create_fund_nav(nav_data)
			results.append(result)

		return results

	async def batch_create_fund_portfolio (
			self,
			portfolio_data_list: List[Dict[str, Any]]
	) -> List[Dict[str, Any]]:
		"""
		批量创建基金持仓记录

		Args:
			portfolio_data_list: 持仓数据列表

		Returns:
			创建结果列表
		"""
		results = []

		for data in portfolio_data_list:
			query = text("""
                         INSERT INTO fund_portfolio
                         (fund_code, report_date, stock_code, stock_name, holding_shares, weight)
                         VALUES (:fund_code, :report_date, :stock_code, :stock_name, :holding_shares, :weight)
                         ON CONFLICT (fund_code, report_date, stock_code)
                             DO UPDATE SET holding_shares = EXCLUDED.holding_shares,
                                           weight         = EXCLUDED.weight,
                                           updated_at     = NOW()
                         RETURNING id
			             """)

			result = await self.session.execute(query, data)
			row = result.fetchone()
			if row:
				results.append({
					"id": row[0],
					"fund_code": data["fund_code"],
					"report_date": data["report_date"],
					"stock_code": data["stock_code"]
				})

		return results

	async def batch_upsert_fund_basics (self, fund_data_list: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
		"""
		批量插入或更新基金基础信息

		Args:
			fund_data_list: 基金数据列表

		Returns:
			更新结果列表
		"""
		results = []

		for data in fund_data_list:
			query = text("""
                         INSERT INTO fund_basic
                             (fund_code, fund_name, fund_type, setup_date, manager_code)
                         VALUES (:fund_code, :fund_name, :fund_type, :setup_date, :manager_code)
                         ON CONFLICT (fund_code)
                             DO UPDATE SET fund_name    = EXCLUDED.fund_name,
                                           fund_type    = EXCLUDED.fund_type,
                                           manager_code = EXCLUDED.manager_code,
                                           updated_at   = NOW()
                         RETURNING fund_code
			             """)

			result = await self.session.execute(query, data)
			row = result.fetchone()
			if row:
				results.append({"fund_code": row[0], "status": "upserted"})

		return results