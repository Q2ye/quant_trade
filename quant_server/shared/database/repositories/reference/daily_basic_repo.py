# -*- coding: utf-8 -*-
"""
每日基本面数据仓库
位置：quant_server/shared/database/repositories/daily_basic_repo.py
职责：管理股票每日基本面指标数据访问
"""

from typing import List, Optional, Dict, Any, Tuple
from datetime import datetime, date, timedelta
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, and_, or_, desc, func, text
from sqlalchemy.orm import selectinload, joinedload

from quant_server.shared.database.repositories.base import BaseRepository
from quant_server.shared.database.models.data_models import (
	StockDailyBasic,
	StockDaily
)


class DailyBasicRepository:
	"""每日基本面数据仓库 - 负责股票每日基本面指标数据访问"""

	def __init__ (self, session: AsyncSession):
		self.session = session
		self.daily_basic_repo = BaseRepository[StockDailyBasic](session, StockDailyBasic)

	# ==================== 基本面数据操作 ====================

	async def get_daily_basic (
			self,
			ts_code: str,
			trade_date: date
	) -> Optional[StockDailyBasic]:
		"""
		获取指定日期的基本面数据

		Args:
			ts_code: 股票代码
			trade_date: 交易日期

		Returns:
			基本面数据或None
		"""
		return await self.daily_basic_repo.get_by(
			ts_code=ts_code,
			trade_date=trade_date
		)

	async def get_daily_basics_in_range (
			self,
			ts_code: str,
			start_date: date,
			end_date: date
	) -> List[StockDailyBasic]:
		"""
		获取指定时间范围内的基本面数据

		Args:
			ts_code: 股票代码
			start_date: 开始日期
			end_date: 结束日期

		Returns:
			基本面数据列表
		"""
		query = select(StockDailyBasic).where(
			and_(
				StockDailyBasic.ts_code == ts_code,
				StockDailyBasic.trade_date >= start_date,
				StockDailyBasic.trade_date <= end_date
			)
		).order_by(StockDailyBasic.trade_date)

		result = await self.session.execute(query)
		return result.scalars().all()

	async def get_latest_daily_basic (self, ts_code: str) -> Optional[StockDailyBasic]:
		"""
		获取最新的基本面数据

		Args:
			ts_code: 股票代码

		Returns:
			最新的基本面数据或None
		"""
		query = select(StockDailyBasic).where(
			StockDailyBasic.ts_code == ts_code
		).order_by(desc(StockDailyBasic.trade_date)).limit(1)

		result = await self.session.execute(query)
		return result.scalar_one_or_none()

	async def get_daily_basics_by_date (
			self,
			trade_date: date,
			limit: int = 1000,
			skip: int = 0
	) -> List[StockDailyBasic]:
		"""
		获取指定日期的所有股票基本面数据

		Args:
			trade_date: 交易日期
			limit: 返回数量限制
			skip: 跳过数量

		Returns:
			基本面数据列表
		"""
		return await self.daily_basic_repo.get_many(
			trade_date=trade_date,
			skip=skip,
			limit=limit
		)

	async def create_daily_basic (self, basic_data: Dict[str, Any]) -> StockDailyBasic:
		"""
		创建基本面数据记录

		Args:
			basic_data: 基本面数据

		Returns:
			创建的基本面数据记录
		"""
		return await self.daily_basic_repo.create(basic_data)

	async def batch_create_daily_basics (self, basics_data: List[Dict[str, Any]]) -> List[StockDailyBasic]:
		"""
		批量创建基本面数据记录

		Args:
			basics_data: 基本面数据列表

		Returns:
			创建的基本面数据记录列表
		"""
		return await self.daily_basic_repo.batch_create(basics_data)

	# ==================== 估值指标操作 ====================

	async def get_valuation_metrics (
			self,
			ts_code: str,
			start_date: date,
			end_date: date
	) -> List[Dict[str, Any]]:
		"""
		获取估值指标时间序列

		Args:
			ts_code: 股票代码
			start_date: 开始日期
			end_date: 结束日期

		Returns:
			估值指标列表
		"""
		query = select(
			StockDailyBasic.trade_date,
			StockDailyBasic.pe,
			StockDailyBasic.pe_ttm,
			StockDailyBasic.pb,
			StockDailyBasic.ps,
			StockDailyBasic.ps_ttm
		).where(
			and_(
				StockDailyBasic.ts_code == ts_code,
				StockDailyBasic.trade_date >= start_date,
				StockDailyBasic.trade_date <= end_date
			)
		).order_by(StockDailyBasic.trade_date)

		result = await self.session.execute(query)
		rows = result.fetchall()

		return [
			{
				"trade_date": row.trade_date,
				"pe": row.pe,
				"pe_ttm": row.pe_ttm,
				"pb": row.pb,
				"ps": row.ps,
				"ps_ttm": row.ps_ttm
			}
			for row in rows
		]

	async def get_current_valuation (self, ts_code: str) -> Optional[Dict[str, Any]]:
		"""
		获取当前估值指标

		Args:
			ts_code: 股票代码

		Returns:
			当前估值指标或None
		"""
		basic = await self.get_latest_daily_basic(ts_code)
		if not basic:
			return None

		return {
			"trade_date": basic.trade_date,
			"pe": basic.pe,
			"pe_ttm": basic.pe_ttm,
			"pb": basic.pb,
			"ps": basic.ps,
			"ps_ttm": basic.ps_ttm,
			"dividend_yield": basic.dv_ratio
		}

	async def get_valuation_percentile (
			self,
			ts_code: str,
			metric: str = "pe",
			lookback_days: int = 365
	) -> Optional[float]:
		"""
		获取估值指标百分位

		Args:
			ts_code: 股票代码
			metric: 指标名称（pe, pe_ttm, pb, ps, ps_ttm）
			lookback_days: 回溯天数

		Returns:
			百分位值（0-1）或None
		"""
		end_date = datetime.now().date()
		start_date = end_date - timedelta(days=lookback_days)

		# 获取指标列名
		metric_column = getattr(StockDailyBasic, metric, None)
		if metric_column is None:
			raise ValueError(f"Invalid metric: {metric}")

		# 获取历史数据
		query = select(metric_column).where(
			and_(
				StockDailyBasic.ts_code == ts_code,
				StockDailyBasic.trade_date >= start_date,
				StockDailyBasic.trade_date <= end_date,
				metric_column.isnot(None)
			)
		).order_by(metric_column)

		result = await self.session.execute(query)
		values = [row[0] for row in result.fetchall()]

		if not values:
			return None

		# 获取当前值
		current_basic = await self.get_latest_daily_basic(ts_code)
		if not current_basic:
			return None

		current_value = getattr(current_basic, metric)
		if current_value is None:
			return None

		# 计算百分位
		values.sort()
		count = len(values)
		lower_count = sum(1 for v in values if v < current_value)

		if count == 0:
			return None

		return lower_count / count

	# ==================== 财务质量指标操作 ====================

	async def get_financial_quality_metrics (
			self,
			ts_code: str,
			start_date: date,
			end_date: date
	) -> List[Dict[str, Any]]:
		"""
		获取财务质量指标时间序列

		Args:
			ts_code: 股票代码
			start_date: 开始日期
			end_date: 结束日期

		Returns:
			财务质量指标列表
		"""
		query = select(
			StockDailyBasic.trade_date,
			StockDailyBasic.turnover_rate,
			StockDailyBasic.turnover_rate_f,
			StockDailyBasic.volume_ratio,
			StockDailyBasic.dv_ratio,
			StockDailyBasic.dv_ttm,
			StockDailyBasic.total_share,
			StockDailyBasic.float_share,
			StockDailyBasic.free_share
		).where(
			and_(
				StockDailyBasic.ts_code == ts_code,
				StockDailyBasic.trade_date >= start_date,
				StockDailyBasic.trade_date <= end_date
			)
		).order_by(StockDailyBasic.trade_date)

		result = await self.session.execute(query)
		rows = result.fetchall()

		return [
			{
				"trade_date": row.trade_date,
				"turnover_rate": row.turnover_rate,
				"turnover_rate_f": row.turnover_rate_f,
				"volume_ratio": row.volume_ratio,
				"dividend_yield": row.dv_ratio,
				"dividend_yield_ttm": row.dv_ttm,
				"total_shares": row.total_share,
				"float_shares": row.float_share,
				"free_shares": row.free_share
			}
			for row in rows
		]

	async def get_market_cap_metrics (
			self,
			ts_code: str,
			start_date: date,
			end_date: date
	) -> List[Dict[str, Any]]:
		"""
		获取市值指标时间序列

		Args:
			ts_code: 股票代码
			start_date: 开始日期
			end_date: 结束日期

		Returns:
			市值指标列表
		"""
		query = select(
			StockDailyBasic.trade_date,
			StockDailyBasic.total_mv,
			StockDailyBasic.circ_mv
		).where(
			and_(
				StockDailyBasic.ts_code == ts_code,
				StockDailyBasic.trade_date >= start_date,
				StockDailyBasic.trade_date <= end_date
			)
		).order_by(StockDailyBasic.trade_date)

		result = await self.session.execute(query)
		rows = result.fetchall()

		return [
			{
				"trade_date": row.trade_date,
				"total_market_cap": row.total_mv,
				"circulating_market_cap": row.circ_mv
			}
			for row in rows
		]

	# ==================== 筛选查询操作 ====================

	async def screen_by_metrics (
			self,
			trade_date: date,
			criteria: Dict[str, Tuple[float, float]],
			limit: int = 100,
			skip: int = 0
	) -> List[Dict[str, Any]]:
		"""
		根据基本面指标筛选股票

		Args:
			trade_date: 交易日期
			criteria: 筛选条件字典，格式为 {指标名: (最小值, 最大值)}
			limit: 返回数量限制
			skip: 跳过数量

		Returns:
			筛选结果列表
		"""
		query = select(StockDailyBasic).where(
			StockDailyBasic.trade_date == trade_date
		)

		# 添加筛选条件
		for metric, (min_val, max_val) in criteria.items():
			column = getattr(StockDailyBasic, metric, None)
			if column is None:
				continue

			if min_val is not None:
				query = query.where(column >= min_val)
			if max_val is not None:
				query = query.where(column <= max_val)

		query = query.order_by(StockDailyBasic.ts_code).offset(skip).limit(limit)

		result = await self.session.execute(query)
		basics = result.scalars().all()

		return [
			{
				"ts_code": basic.ts_code,
				"trade_date": basic.trade_date,
				"pe": basic.pe,
				"pb": basic.pb,
				"ps": basic.ps,
				"turnover_rate": basic.turnover_rate,
				"total_market_cap": basic.total_mv
			}
			for basic in basics
		]

	async def find_undervalued_stocks (
			self,
			trade_date: date,
			max_pe: float = 20,
			max_pb: float = 2,
			min_market_cap: float = 1e9,
			limit: int = 50
	) -> List[Dict[str, Any]]:
		"""
		寻找低估股票

		Args:
			trade_date: 交易日期
			max_pe: 最大市盈率
			max_pb: 最大市净率
			min_market_cap: 最小市值
			limit: 返回数量限制

		Returns:
			低估股票列表
		"""
		query = select(StockDailyBasic).where(
			and_(
				StockDailyBasic.trade_date == trade_date,
				StockDailyBasic.pe.isnot(None),
				StockDailyBasic.pe <= max_pe,
				StockDailyBasic.pb.isnot(None),
				StockDailyBasic.pb <= max_pb,
				StockDailyBasic.total_mv >= min_market_cap
			)
		).order_by(
			StockDailyBasic.pe,
			StockDailyBasic.pb
		).limit(limit)

		result = await self.session.execute(query)
		basics = result.scalars().all()

		return [
			{
				"ts_code": basic.ts_code,
				"pe": basic.pe,
				"pb": basic.pb,
				"ps": basic.ps,
				"dividend_yield": basic.dv_ratio,
				"total_market_cap": basic.total_mv,
				"turnover_rate": basic.turnover_rate
			}
			for basic in basics
		]

	# ==================== 统计分析操作 ====================

	async def get_industry_averages (
			self,
			trade_date: date,
			industry: str
	) -> Optional[Dict[str, float]]:
		"""
		获取行业平均估值指标

		Args:
			trade_date: 交易日期
			industry: 行业名称

		Returns:
			行业平均指标字典或None
		"""
		# 首先需要查询股票的基本信息来获取行业分类
		# 这里简化处理，假设我们可以直接关联查询

		query = text("""
                     SELECT AVG(b.pe)            as avg_pe,
                            AVG(b.pe_ttm)        as avg_pe_ttm,
                            AVG(b.pb)            as avg_pb,
                            AVG(b.ps)            as avg_ps,
                            AVG(b.ps_ttm)        as avg_ps_ttm,
                            AVG(b.dv_ratio)      as avg_dividend_yield,
                            AVG(b.turnover_rate) as avg_turnover_rate,
                            COUNT(*)             as stock_count
                     FROM stock_daily_basic b
                              JOIN stock_basic s ON b.ts_code = s.ts_code
                     WHERE b.trade_date = :trade_date
                       AND s.industry = :industry
                       AND b.pe IS NOT NULL
		             """)

		result = await self.session.execute(
			query,
			{"trade_date": trade_date, "industry": industry}
		)
		row = result.fetchone()

		if not row or row.stock_count == 0:
			return None

		return {
			"avg_pe": float(row.avg_pe or 0),
			"avg_pe_ttm": float(row.avg_pe_ttm or 0),
			"avg_pb": float(row.avg_pb or 0),
			"avg_ps": float(row.avg_ps or 0),
			"avg_ps_ttm": float(row.avg_ps_ttm or 0),
			"avg_dividend_yield": float(row.avg_dividend_yield or 0),
			"avg_turnover_rate": float(row.avg_turnover_rate or 0),
			"stock_count": row.stock_count
		}

	async def get_market_overview (self, trade_date: date) -> Dict[str, Any]:
		"""
		获取市场概况

		Args:
			trade_date: 交易日期

		Returns:
			市场概况字典
		"""
		# 整体市场估值统计
		stats_query = text("""
                           SELECT COUNT(*)           as total_stocks,
                                  AVG(pe)            as market_pe,
                                  AVG(pb)            as market_pb,
                                  AVG(ps)            as market_ps,
                                  AVG(turnover_rate) as market_turnover,
                                  SUM(total_mv)      as total_market_cap
                           FROM stock_daily_basic
                           WHERE trade_date = :trade_date
                             AND pe IS NOT NULL
                             AND pe > 0
		                   """)

		stats_result = await self.session.execute(
			stats_query,
			{"trade_date": trade_date}
		)
		stats_row = stats_result.fetchone()

		# PE分布统计
		pe_distribution_query = text("""
                                     SELECT COUNT(CASE WHEN pe < 10 THEN 1 END)               as pe_under_10,
                                            COUNT(CASE WHEN pe >= 10 AND pe < 20 THEN 1 END)  as pe_10_20,
                                            COUNT(CASE WHEN pe >= 20 AND pe < 30 THEN 1 END)  as pe_20_30,
                                            COUNT(CASE WHEN pe >= 30 AND pe < 50 THEN 1 END)  as pe_30_50,
                                            COUNT(CASE WHEN pe >= 50 THEN 1 END)              as pe_over_50,
                                            COUNT(CASE WHEN pe IS NULL OR pe <= 0 THEN 1 END) as pe_invalid
                                     FROM stock_daily_basic
                                     WHERE trade_date = :trade_date
		                             """)

		pe_result = await self.session.execute(
			pe_distribution_query,
			{"trade_date": trade_date}
		)
		pe_row = pe_result.fetchone()

		# 交易活跃度统计
		turnover_query = text("""
                              SELECT AVG(turnover_rate) as avg_turnover,
                                     MAX(turnover_rate) as max_turnover,
                                     MIN(turnover_rate) as min_turnover
                              FROM stock_daily_basic
                              WHERE trade_date = :trade_date
                                AND turnover_rate > 0
		                      """)

		turnover_result = await self.session.execute(
			turnover_query,
			{"trade_date": trade_date}
		)
		turnover_row = turnover_result.fetchone()

		return {
			"trade_date": trade_date,
			"market_statistics": {
				"total_stocks": stats_row.total_stocks or 0,
				"average_pe": float(stats_row.market_pe or 0),
				"average_pb": float(stats_row.market_pb or 0),
				"average_ps": float(stats_row.market_ps or 0),
				"total_market_cap": float(stats_row.total_market_cap or 0)
			},
			"pe_distribution": {
				"under_10": pe_row.pe_under_10 or 0,
				"10_to_20": pe_row.pe_10_20 or 0,
				"20_to_30": pe_row.pe_20_30 or 0,
				"30_to_50": pe_row.pe_30_50 or 0,
				"over_50": pe_row.pe_over_50 or 0,
				"invalid": pe_row.pe_invalid or 0
			},
			"turnover_statistics": {
				"average": float(turnover_row.avg_turnover or 0),
				"maximum": float(turnover_row.max_turnover or 0),
				"minimum": float(turnover_row.min_turnover or 0)
			}
		}

	# ==================== 批量操作 ====================

	async def batch_upsert_daily_basics (self, basics_data: List[Dict[str, Any]]) -> List[StockDailyBasic]:
		"""
		批量插入或更新基本面数据

		Args:
			basics_data: 基本面数据列表

		Returns:
			更新后的基本面数据记录列表
		"""
		return await self.daily_basic_repo.batch_upsert(
			match_fields=["ts_code", "trade_date"],
			data_list=basics_data
		)

	async def delete_old_data (self, before_date: date) -> int:
		"""
		删除指定日期之前的数据

		Args:
			before_date: 截止日期

		Returns:
			删除的记录数
		"""
		return await self.daily_basic_repo.delete_by(
			trade_date__lt=before_date
		)