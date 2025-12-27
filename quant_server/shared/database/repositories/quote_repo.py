# -*- coding: utf-8 -*-
"""
行情数据仓库
提供股票行情数据的统一访问接口
位置：shared/database/repositories/quote_repo.py
"""

from typing import List, Optional, Dict, Any, Tuple, Union
from datetime import date, datetime, timedelta
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, and_, or_, func, desc, between, distinct, case
from sqlalchemy.orm import aliased

from .base import BaseRepository
from quant_server.shared.database.models.data_models import (
	StockDaily, StockWeekly, StockMonthly, StockMinutes,
	StockMoneyflow, StockDailyLimit, StockAdjFactor,
	EtfDaily, EtfMinute
)


class QuoteRepository:
	"""行情数据Repository - 纯数据访问"""

	def __init__ (self, session: AsyncSession):
		self.session = session
		self.daily_repo = BaseRepository(session, StockDaily)
		self.weekly_repo = BaseRepository(session, StockWeekly)
		self.monthly_repo = BaseRepository(session, StockMonthly)
		self.minutes_repo = BaseRepository(session, StockMinutes)
		self.moneyflow_repo = BaseRepository(session, StockMoneyflow)
		self.limit_repo = BaseRepository(session, StockDailyLimit)
		self.adj_factor_repo = BaseRepository(session, StockAdjFactor)
		self.etf_daily_repo = BaseRepository(session, EtfDaily)
		self.etf_minute_repo = BaseRepository(session, EtfMinute)

	# ==================== 日行情查询 ====================

	async def get_daily_quote (
			self,
			ts_code: str,
			trade_date: date
	) -> Optional[StockDaily]:
		"""获取指定日期的日行情数据"""
		return await self.daily_repo.get_one(
			and_(
				StockDaily.ts_code == ts_code,
				StockDaily.trade_date == trade_date
			)
		)

	async def get_daily_quotes (
			self,
			ts_code: str,
			start_date: date,
			end_date: date,
			fields: Optional[List[str]] = None,
			ascending: bool = True
	) -> List[StockDaily]:
		"""获取日行情数据时间序列"""
		query = select(StockDaily).where(
			and_(
				StockDaily.ts_code == ts_code,
				StockDaily.trade_date >= start_date,
				StockDaily.trade_date <= end_date
			)
		)

		# 可选字段选择
		if fields:
			columns = []
			for field in fields:
				if hasattr(StockDaily, field):
					columns.append(getattr(StockDaily, field))
			if columns:
				query = query.with_only_columns(*columns)

		# 排序
		if ascending:
			query = query.order_by(StockDaily.trade_date.asc())
		else:
			query = query.order_by(StockDaily.trade_date.desc())

		result = await self.session.execute(query)
		return result.scalars().all()

	async def get_latest_daily_quote (
			self,
			ts_code: str,
			before_date: Optional[date] = None
	) -> Optional[StockDaily]:
		"""获取最新日行情数据"""
		query = select(StockDaily).where(
			StockDaily.ts_code == ts_code
		)

		if before_date:
			query = query.where(StockDaily.trade_date <= before_date)

		query = query.order_by(StockDaily.trade_date.desc()).limit(1)

		result = await self.session.execute(query)
		return result.scalar_one_or_none()

	async def get_daily_quotes_by_date (
			self,
			trade_date: date,
			ts_codes: Optional[List[str]] = None,
			limit: int = 1000
	) -> List[StockDaily]:
		"""获取指定交易日的所有股票行情"""
		query = select(StockDaily).where(
			StockDaily.trade_date == trade_date
		)

		if ts_codes:
			query = query.where(StockDaily.ts_code.in_(ts_codes))

		query = query.order_by(StockDaily.ts_code).limit(limit)

		result = await self.session.execute(query)
		return result.scalars().all()

	async def get_daily_quotes_batch (
			self,
			ts_codes: List[str],
			start_date: date,
			end_date: date
	) -> Dict[str, List[StockDaily]]:
		"""批量获取多只股票的日行情数据"""
		if not ts_codes:
			return {}

		result = await self.session.execute(
			select(StockDaily).where(
				and_(
					StockDaily.ts_code.in_(ts_codes),
					StockDaily.trade_date >= start_date,
					StockDaily.trade_date <= end_date
				)
			).order_by(StockDaily.ts_code, StockDaily.trade_date.asc())
		)

		quotes = result.scalars().all()

		# 按股票代码分组
		grouped = {}
		for quote in quotes:
			if quote.ts_code not in grouped:
				grouped[quote.ts_code] = []
			grouped[quote.ts_code].append(quote)

		return grouped

	async def get_daily_price_range (
			self,
			ts_code: str,
			start_date: date,
			end_date: date
	) -> Dict[str, Any]:
		"""获取价格范围（最高价、最低价、平均价）"""
		result = await self.session.execute(
			select(
				func.min(StockDaily.low).label('min_price'),
				func.max(StockDaily.high).label('max_price'),
				func.avg(StockDaily.close).label('avg_price'),
				func.count(StockDaily.id).label('count')
			).where(
				and_(
					StockDaily.ts_code == ts_code,
					StockDaily.trade_date >= start_date,
					StockDaily.trade_date <= end_date
				)
			)
		)

		row = result.first()
		if row:
			return {
				'min_price': float(row[0]) if row[0] else None,
				'max_price': float(row[1]) if row[1] else None,
				'avg_price': float(row[2]) if row[2] else None,
				'count': row[3] or 0
			}
		return {}

	# ==================== 周/月行情查询 ====================

	async def get_weekly_quote (
			self,
			ts_code: str,
			trade_date: date
	) -> Optional[StockWeekly]:
		"""获取周行情数据"""
		return await self.weekly_repo.get_one(
			and_(
				StockWeekly.ts_code == ts_code,
				StockWeekly.trade_date == trade_date
			)
		)

	async def get_weekly_quotes (
			self,
			ts_code: str,
			start_date: date,
			end_date: date,
			ascending: bool = True
	) -> List[StockWeekly]:
		"""获取周行情数据时间序列"""
		query = select(StockWeekly).where(
			and_(
				StockWeekly.ts_code == ts_code,
				StockWeekly.trade_date >= start_date,
				StockWeekly.trade_date <= end_date
			)
		)

		if ascending:
			query = query.order_by(StockWeekly.trade_date.asc())
		else:
			query = query.order_by(StockWeekly.trade_date.desc())

		result = await self.session.execute(query)
		return result.scalars().all()

	async def get_monthly_quote (
			self,
			ts_code: str,
			trade_date: date
	) -> Optional[StockMonthly]:
		"""获取月行情数据"""
		return await self.monthly_repo.get_one(
			and_(
				StockMonthly.ts_code == ts_code,
				StockMonthly.trade_date == trade_date
			)
		)

	async def get_monthly_quotes (
			self,
			ts_code: str,
			start_date: date,
			end_date: date,
			ascending: bool = True
	) -> List[StockMonthly]:
		"""获取月行情数据时间序列"""
		query = select(StockMonthly).where(
			and_(
				StockMonthly.ts_code == ts_code,
				StockMonthly.trade_date >= start_date,
				StockMonthly.trade_date <= end_date
			)
		)

		if ascending:
			query = query.order_by(StockMonthly.trade_date.asc())
		else:
			query = query.order_by(StockMonthly.trade_date.desc())

		result = await self.session.execute(query)
		return result.scalars().all()

	# ==================== 分钟行情查询 ====================

	async def get_minute_quote (
			self,
			ts_code: str,
			trade_time: datetime,
			freq: str = '1min'
	) -> Optional[StockMinutes]:
		"""获取指定时间的分钟行情数据"""
		return await self.minutes_repo.get_one(
			and_(
				StockMinutes.ts_code == ts_code,
				StockMinutes.trade_time == trade_time,
				StockMinutes.freq == freq
			)
		)

	async def get_minute_quotes (
			self,
			ts_code: str,
			trade_date: date,
			freq: str = '1min',
			start_time: Optional[str] = None,
			end_time: Optional[str] = None
	) -> List[StockMinutes]:
		"""获取分钟行情数据"""
		filters = [
			StockMinutes.ts_code == ts_code,
			func.date(StockMinutes.trade_time) == trade_date,
			StockMinutes.freq == freq
		]

		if start_time:
			filters.append(StockMinutes.trade_time >= start_time)
		if end_time:
			filters.append(StockMinutes.trade_time <= end_time)

		result = await self.session.execute(
			select(StockMinutes).where(
				and_(*filters)
			).order_by(StockMinutes.trade_time.asc())
		)

		return result.scalars().all()

	async def get_intraday_quotes (
			self,
			ts_code: str,
			trade_date: date,
			start_time: str = '09:30:00',
			end_time: str = '15:00:00',
			freq: str = '1min'
	) -> List[StockMinutes]:
		"""获取日内指定时间段行情数据"""
		return await self.get_minute_quotes(
			ts_code, trade_date, freq, start_time, end_time
		)

	async def get_last_n_minutes (
			self,
			ts_code: str,
			n: int = 30,
			freq: str = '1min'
	) -> List[StockMinutes]:
		"""获取最近N分钟的行情数据"""
		# 计算开始时间
		end_time = datetime.now()
		start_time = end_time - timedelta(minutes=n)

		result = await self.session.execute(
			select(StockMinutes).where(
				and_(
					StockMinutes.ts_code == ts_code,
					StockMinutes.trade_time >= start_time,
					StockMinutes.trade_time <= end_time,
					StockMinutes.freq == freq
				)
			).order_by(StockMinutes.trade_time.asc())
		)

		return result.scalars().all()

	# ==================== 资金流查询 ====================

	async def get_moneyflow (
			self,
			ts_code: str,
			trade_date: date
	) -> Optional[StockMoneyflow]:
		"""获取资金流数据"""
		return await self.moneyflow_repo.get_one(
			and_(
				StockMoneyflow.ts_code == ts_code,
				StockMoneyflow.trade_date == trade_date
			)
		)

	async def get_moneyflows (
			self,
			ts_code: str,
			start_date: date,
			end_date: date,
			ascending: bool = True
	) -> List[StockMoneyflow]:
		"""获取资金流数据时间序列"""
		query = select(StockMoneyflow).where(
			and_(
				StockMoneyflow.ts_code == ts_code,
				StockMoneyflow.trade_date >= start_date,
				StockMoneyflow.trade_date <= end_date
			)
		)

		if ascending:
			query = query.order_by(StockMoneyflow.trade_date.asc())
		else:
			query = query.order_by(StockMoneyflow.trade_date.desc())

		result = await self.session.execute(query)
		return result.scalars().all()

	async def get_moneyflow_summary (
			self,
			trade_date: date,
			top_n: int = 20,
			direction: str = 'inflow'  # 'inflow' 或 'outflow'
	) -> List[Dict[str, Any]]:
		"""获取资金流汇总（主力净流入/流出排名）"""
		if direction == 'inflow':
			order_column = StockMoneyflow.net_mf_amount.desc()
			where_condition = StockMoneyflow.net_mf_amount > 0
		else:
			order_column = StockMoneyflow.net_mf_amount.asc()
			where_condition = StockMoneyflow.net_mf_amount < 0

		query = select(
			StockMoneyflow.ts_code,
			StockMoneyflow.net_mf_amount,
			StockMoneyflow.buy_lg_amount,
			StockMoneyflow.sell_lg_amount,
			StockMoneyflow.large_net_ratio
		).where(
			and_(
				StockMoneyflow.trade_date == trade_date,
				where_condition
			)
		).order_by(
			order_column
		).limit(top_n)

		result = await self.session.execute(query)
		rows = result.all()

		return [
			{
				'ts_code': row[0],
				'net_mf_amount': float(row[1]) if row[1] else 0,
				'buy_lg_amount': float(row[2]) if row[2] else 0,
				'sell_lg_amount': float(row[3]) if row[3] else 0,
				'large_net_ratio': float(row[4]) if row[4] else 0
			}
			for row in rows
		]

	# ==================== 涨跌停查询 ====================

	async def get_daily_limit (
			self,
			ts_code: str,
			trade_date: date
	) -> Optional[StockDailyLimit]:
		"""获取涨跌停数据"""
		return await self.limit_repo.get_one(
			and_(
				StockDailyLimit.ts_code == ts_code,
				StockDailyLimit.trade_date == trade_date
			)
		)

	async def get_limit_stocks (
			self,
			trade_date: date,
			limit_type: str = 'up'  # 'up' 涨停, 'down' 跌停
	) -> List[StockDailyLimit]:
		"""获取涨跌停股票列表"""
		query = select(StockDailyLimit).where(
			and_(
				StockDailyLimit.trade_date == trade_date,
				StockDailyLimit.limit_type == limit_type
			)
		).order_by(StockDailyLimit.ts_code)

		result = await self.session.execute(query)
		return result.scalars().all()

	async def get_limit_history (
			self,
			ts_code: str,
			start_date: Optional[date] = None,
			end_date: Optional[date] = None,
			limit_type: Optional[str] = None
	) -> List[StockDailyLimit]:
		"""获取股票的涨跌停历史"""
		filters = [StockDailyLimit.ts_code == ts_code]

		if start_date:
			filters.append(StockDailyLimit.trade_date >= start_date)
		if end_date:
			filters.append(StockDailyLimit.trade_date <= end_date)
		if limit_type:
			filters.append(StockDailyLimit.limit_type == limit_type)

		result = await self.session.execute(
			select(StockDailyLimit).where(
				and_(*filters)
			).order_by(StockDailyLimit.trade_date.desc())
		)

		return result.scalars().all()

	# ==================== 复权因子查询 ====================

	async def get_adj_factor (
			self,
			ts_code: str,
			trade_date: date
	) -> Optional[StockAdjFactor]:
		"""获取复权因子"""
		return await self.adj_factor_repo.get_one(
			and_(
				StockAdjFactor.ts_code == ts_code,
				StockAdjFactor.trade_date == trade_date
			)
		)

	async def get_adj_factors (
			self,
			ts_code: str,
			start_date: date,
			end_date: date,
			ascending: bool = True
	) -> List[StockAdjFactor]:
		"""获取复权因子时间序列"""
		query = select(StockAdjFactor).where(
			and_(
				StockAdjFactor.ts_code == ts_code,
				StockAdjFactor.trade_date >= start_date,
				StockAdjFactor.trade_date <= end_date
			)
		)

		if ascending:
			query = query.order_by(StockAdjFactor.trade_date.asc())
		else:
			query = query.order_by(StockAdjFactor.trade_date.desc())

		result = await self.session.execute(query)
		return result.scalars().all()

	async def get_latest_adj_factor (
			self,
			ts_code: str,
			before_date: Optional[date] = None
	) -> Optional[StockAdjFactor]:
		"""获取最新复权因子"""
		query = select(StockAdjFactor).where(
			StockAdjFactor.ts_code == ts_code
		)

		if before_date:
			query = query.where(StockAdjFactor.trade_date <= before_date)

		query = query.order_by(StockAdjFactor.trade_date.desc()).limit(1)

		result = await self.session.execute(query)
		return result.scalar_one_or_none()

	# ==================== ETF行情查询 ====================

	async def get_etf_daily_quote (
			self,
			ts_code: str,
			trade_date: date
	) -> Optional[EtfDaily]:
		"""获取ETF日行情数据"""
		return await self.etf_daily_repo.get_one(
			and_(
				EtfDaily.ts_code == ts_code,
				EtfDaily.trade_date == trade_date
			)
		)

	async def get_etf_daily_quotes (
			self,
			ts_code: str,
			start_date: date,
			end_date: date,
			ascending: bool = True
	) -> List[EtfDaily]:
		"""获取ETF日行情数据时间序列"""
		query = select(EtfDaily).where(
			and_(
				EtfDaily.ts_code == ts_code,
				EtfDaily.trade_date >= start_date,
				EtfDaily.trade_date <= end_date
			)
		)

		if ascending:
			query = query.order_by(EtfDaily.trade_date.asc())
		else:
			query = query.order_by(EtfDaily.trade_date.desc())

		result = await self.session.execute(query)
		return result.scalars().all()

	async def get_etf_minute_quote (
			self,
			ts_code: str,
			trade_time: datetime,
			freq: str = '1min'
	) -> Optional[EtfMinute]:
		"""获取ETF分钟行情数据"""
		return await self.etf_minute_repo.get_one(
			and_(
				EtfMinute.ts_code == ts_code,
				EtfMinute.trade_time == trade_time,
				EtfMinute.freq == freq
			)
		)

	async def get_etf_minute_quotes (
			self,
			ts_code: str,
			trade_date: date,
			freq: str = '1min'
	) -> List[EtfMinute]:
		"""获取ETF分钟行情数据"""
		result = await self.session.execute(
			select(EtfMinute).where(
				and_(
					EtfMinute.ts_code == ts_code,
					func.date(EtfMinute.trade_time) == trade_date,
					EtfMinute.freq == freq
				)
			).order_by(EtfMinute.trade_time.asc())
		)

		return result.scalars().all()

	# ==================== 批量操作 ====================

	async def batch_insert_daily_quotes (
			self,
			quotes_data: List[Dict[str, Any]]
	) -> List[StockDaily]:
		"""批量插入日行情数据"""
		return await self.daily_repo.batch_create(quotes_data)

	async def batch_upsert_daily_quotes (
			self,
			quotes_data: List[Dict[str, Any]],
			match_fields: List[str] = ['ts_code', 'trade_date']
	) -> List[StockDaily]:
		"""批量插入或更新日行情数据"""
		return await self.daily_repo.batch_upsert(quotes_data, match_fields)

	async def batch_insert_minute_quotes (
			self,
			quotes_data: List[Dict[str, Any]]
	) -> List[StockMinutes]:
		"""批量插入分钟行情数据"""
		return await self.minutes_repo.batch_create(quotes_data)

	async def batch_insert_moneyflows (
			self,
			moneyflows_data: List[Dict[str, Any]]
	) -> List[StockMoneyflow]:
		"""批量插入资金流数据"""
		return await self.moneyflow_repo.batch_create(moneyflows_data)

	async def batch_insert_adj_factors (
			self,
			factors_data: List[Dict[str, Any]]
	) -> List[StockAdjFactor]:
		"""批量插入复权因子数据"""
		return await self.adj_factor_repo.batch_create(factors_data)

	# ==================== 统计查询 ====================

	async def get_trading_dates (
			self,
			start_date: date,
			end_date: date
	) -> List[date]:
		"""获取交易日列表"""
		result = await self.session.execute(
			select(distinct(StockDaily.trade_date)).where(
				and_(
					StockDaily.trade_date >= start_date,
					StockDaily.trade_date <= end_date
				)
			).order_by(StockDaily.trade_date.asc())
		)

		return [row[0] for row in result.all()]

	async def get_market_summary (
			self,
			trade_date: date
	) -> Dict[str, Any]:
		"""获取市场概况统计"""
		# 统计上涨/下跌/平盘股票数
		result = await self.session.execute(
			select(
				func.sum(case([(StockDaily.pct_chg > 0, 1)], else_=0)).label('up'),
				func.sum(case([(StockDaily.pct_chg < 0, 1)], else_=0)).label('down'),
				func.sum(case([(StockDaily.pct_chg == 0, 1)], else_=0)).label('unchanged'),
				func.count(StockDaily.ts_code).label('total')
			).where(
				StockDaily.trade_date == trade_date
			)
		)

		row = result.first()
		if not row:
			return {}

		summary = {
			'trade_date': trade_date,
			'up_count': row.up or 0,
			'down_count': row.down or 0,
			'unchanged_count': row.unchanged or 0,
			'total_count': row.total or 0
		}

		# 计算涨跌比例
		if summary['total_count'] > 0:
			summary['up_ratio'] = summary['up_count'] / summary['total_count']
			summary['down_ratio'] = summary['down_count'] / summary['total_count']
			summary['unchanged_ratio'] = summary['unchanged_count'] / summary['total_count']

		# 获取涨跌停股票数
		limit_result = await self.session.execute(
			select(
				StockDailyLimit.limit_type,
				func.count(StockDailyLimit.ts_code).label('count')
			).where(
				StockDailyLimit.trade_date == trade_date
			).group_by(StockDailyLimit.limit_type)
		)

		for limit_row in limit_result.all():
			if limit_row.limit_type == 'up':
				summary['limit_up_count'] = limit_row.count
			elif limit_row.limit_type == 'down':
				summary['limit_down_count'] = limit_row.count

		return summary

	async def get_price_change_stats (
			self,
			trade_date: date,
			pct_ranges: Optional[List[Tuple[float, float]]] = None
	) -> Dict[str, int]:
		"""获取涨跌幅分布统计"""
		if pct_ranges is None:
			pct_ranges = [
				(-float('inf'), -7),
				(-7, -3),
				(-3, 0),
				(0, 3),
				(3, 7),
				(7, float('inf'))
			]

		stats = {}

		for min_val, max_val in pct_ranges:
			query = select(func.count(StockDaily.ts_code)).where(
				StockDaily.trade_date == trade_date
			)

			if min_val != -float('inf'):
				query = query.where(StockDaily.pct_chg >= min_val)

			if max_val != float('inf'):
				query = query.where(StockDaily.pct_chg < max_val)

			result = await self.session.execute(query)
			count = result.scalar() or 0

			key = f"{min_val:.1f}_{max_val:.1f}"
			stats[key] = count

		return stats

	# ==================== 技术指标计算辅助 ====================

	async def get_closing_prices (
			self,
			ts_code: str,
			start_date: date,
			end_date: date,
			include_dates: bool = False
	) -> Union[List[float], List[Tuple[date, float]]]:
		"""获取收盘价序列（用于技术指标计算）"""
		if include_dates:
			result = await self.session.execute(
				select(
					StockDaily.trade_date,
					StockDaily.close
				).where(
					and_(
						StockDaily.ts_code == ts_code,
						StockDaily.trade_date >= start_date,
						StockDaily.trade_date <= end_date
					)
				).order_by(StockDaily.trade_date.asc())
			)

			return [(row[0], float(row[1]) if row[1] else 0) for row in result.all()]
		else:
			result = await self.session.execute(
				select(StockDaily.close).where(
					and_(
						StockDaily.ts_code == ts_code,
						StockDaily.trade_date >= start_date,
						StockDaily.trade_date <= end_date
					)
				).order_by(StockDaily.trade_date.asc())
			)

			return [float(row[0]) if row[0] else 0 for row in result.all()]

	async def get_volume_series (
			self,
			ts_code: str,
			start_date: date,
			end_date: date
	) -> List[int]:
		"""获取成交量序列"""
		result = await self.session.execute(
			select(StockDaily.vol).where(
				and_(
					StockDaily.ts_code == ts_code,
					StockDaily.trade_date >= start_date,
					StockDaily.trade_date <= end_date
				)
			).order_by(StockDaily.trade_date.asc())
		)

		return [row[0] or 0 for row in result.all()]

	async def get_ohlc_series (
			self,
			ts_code: str,
			start_date: date,
			end_date: date
	) -> List[Dict[str, Any]]:
		"""获取OHLC序列（开盘、最高、最低、收盘、成交量）"""
		result = await self.session.execute(
			select(
				StockDaily.trade_date,
				StockDaily.open,
				StockDaily.high,
				StockDaily.low,
				StockDaily.close,
				StockDaily.vol,
				StockDaily.amount
			).where(
				and_(
					StockDaily.ts_code == ts_code,
					StockDaily.trade_date >= start_date,
					StockDaily.trade_date <= end_date
				)
			).order_by(StockDaily.trade_date.asc())
		)

		series = []
		for row in result.all():
			series.append({
				'date': row[0],
				'open': float(row[1]) if row[1] else 0,
				'high': float(row[2]) if row[2] else 0,
				'low': float(row[3]) if row[3] else 0,
				'close': float(row[4]) if row[4] else 0,
				'volume': row[5] or 0,
				'amount': float(row[6]) if row[6] else 0
			})

		return series

	async def get_price_moving_averages (
			self,
			ts_code: str,
			end_date: date,
			periods: List[int] = [5, 10, 20, 30, 60]
	) -> Dict[int, Optional[float]]:
		"""获取移动平均线值"""
		ma_values = {}

		for period in periods:
			# 计算period日的移动平均
			subquery = select(
				func.avg(StockDaily.close).label(f'ma{period}')
			).where(
				and_(
					StockDaily.ts_code == ts_code,
					StockDaily.trade_date <= end_date
				)
			).order_by(
				StockDaily.trade_date.desc()
			).limit(period).subquery()

			result = await self.session.execute(
				select(func.avg(subquery.c[f'ma{period}']))
			)

			ma_value = result.scalar()
			ma_values[period] = float(ma_value) if ma_value else None

		return ma_values

	# ==================== 数据完整性检查 ====================

	async def check_data_gaps (
			self,
			ts_code: str,
			start_date: date,
			end_date: date,
			freq: str = 'daily'
	) -> List[Tuple[date, date]]:
		"""检查数据缺失的日期区间"""
		if freq == 'daily':
			model = StockDaily
		elif freq == 'weekly':
			model = StockWeekly
		elif freq == 'monthly':
			model = StockMonthly
		else:
			raise ValueError(f"不支持的频率: {freq}")

		# 获取所有交易日
		result = await self.session.execute(
			select(model.trade_date).where(
				and_(
					model.ts_code == ts_code,
					model.trade_date >= start_date,
					model.trade_date <= end_date
				)
			).order_by(model.trade_date.asc())
		)

		existing_dates = [row[0] for row in result.all()]

		# 找出缺失的日期区间
		gaps = []
		if existing_dates:
			current_date = start_date

			for existing_date in existing_dates:
				if existing_date > current_date:
					# 找到缺失区间
					gap_start = current_date
					gap_end = existing_date - timedelta(days=1)
					gaps.append((gap_start, gap_end))

				current_date = existing_date + timedelta(days=1)

			# 检查最后一天之后是否还有缺失
			if current_date <= end_date:
				gaps.append((current_date, end_date))
		else:
			# 如果没有任何数据，整个区间都是缺失的
			gaps.append((start_date, end_date))

		return gaps

	async def get_last_trade_date (self) -> Optional[date]:
		"""获取最新的交易日"""
		result = await self.session.execute(
			select(StockDaily.trade_date)
			.order_by(StockDaily.trade_date.desc())
			.limit(1)
		)

		return result.scalar_one_or_none()

	async def get_quote_statistics (self) -> Dict[str, Any]:
		"""获取行情数据统计信息"""
		# 日行情统计
		daily_count = await self.session.execute(
			select(func.count(StockDaily.id))
		)
		daily_count_value = daily_count.scalar() or 0

		# 分钟行情统计
		minute_count = await self.session.execute(
			select(func.count(StockMinutes.id))
		)
		minute_count_value = minute_count.scalar() or 0

		# 资金流统计
		moneyflow_count = await self.session.execute(
			select(func.count(StockMoneyflow.id))
		)
		moneyflow_count_value = moneyflow_count.scalar() or 0

		# 日期范围
		date_range = await self.session.execute(
			select(
				func.min(StockDaily.trade_date),
				func.max(StockDaily.trade_date)
			)
		)
		min_date, max_date = date_range.first()

		# 股票数量
		stock_count = await self.session.execute(
			select(func.count(func.distinct(StockDaily.ts_code)))
		)
		stock_count_value = stock_count.scalar() or 0

		return {
			'daily_count': daily_count_value,
			'minute_count': minute_count_value,
			'moneyflow_count': moneyflow_count_value,
			'total_count': daily_count_value + minute_count_value + moneyflow_count_value,
			'date_range': {
				'min_date': min_date,
				'max_date': max_date
			},
			'unique_stocks': stock_count_value
		}