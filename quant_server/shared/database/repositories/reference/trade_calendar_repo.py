# -*- coding: utf-8 -*-
"""
交易日历数据仓库
提供交易日历数据的统一访问接口
位置：shared/database/repositories/trade_calendar_repo.py
"""

from typing import List, Optional, Dict, Any
from datetime import date, datetime, timedelta
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, and_, or_, func, desc, between, distinct

from quant_server.shared.database.repositories.base import BaseRepository
from quant_server.shared.database.models.data_models import TradeCalendar


class TradeCalendarRepository:
	"""交易日历数据Repository - 纯数据访问"""

	def __init__ (self, session: AsyncSession):
		self.session = session
		self.base_repo = BaseRepository(session, TradeCalendar)

	# ==================== 基础CRUD操作 ====================

	async def create (self, data: Dict[str, Any]) -> TradeCalendar:
		"""创建交易日历记录"""
		return await self.base_repo.create(data)

	async def get (self, exchange: str, cal_date: date) -> Optional[TradeCalendar]:
		"""根据交易所和日期获取交易日历记录"""
		return await self.base_repo.get_one(
			and_(
				TradeCalendar.exchange == exchange,
				TradeCalendar.cal_date == cal_date
			)
		)

	async def update (
			self,
			exchange: str,
			cal_date: date,
			data: Dict[str, Any]
	) -> Optional[TradeCalendar]:
		"""更新交易日历记录"""
		record = await self.get(exchange, cal_date)
		if record:
			return await self.base_repo.update(record.id, data)
		return None

	async def delete (self, exchange: str, cal_date: date, soft: bool = True) -> bool:
		"""删除交易日历记录"""
		record = await self.get(exchange, cal_date)
		if record:
			return await self.base_repo.delete(record.id, soft)
		return False

	async def get_one (self, *filters) -> Optional[TradeCalendar]:
		"""根据条件获取单个交易日历记录"""
		return await self.base_repo.get_one(*filters)

	async def get_many (
			self,
			*filters,
			skip: int = 0,
			limit: int = 100,
			order_by: str = None
	) -> List[TradeCalendar]:
		"""根据条件获取多个交易日历记录"""
		return await self.base_repo.get_many(*filters, skip=skip, limit=limit, order_by=order_by)

	async def count (self, *filters) -> int:
		"""统计交易日历记录数"""
		return await self.base_repo.count(*filters)

	# ==================== 业务查询方法 ====================

	async def is_trade_date (
			self,
			exchange: str,
			check_date: date
	) -> bool:
		"""检查指定日期是否为交易日"""
		calendar = await self.get(exchange, check_date)
		return calendar is not None and calendar.is_open

	async def get_trade_date (
			self,
			exchange: str,
			target_date: date,
			direction: str = 'next'  # 'next' or 'previous'
	) -> Optional[date]:
		"""获取下一个或上一个交易日"""
		if direction == 'next':
			# 获取下一个交易日
			result = await self.session.execute(
				select(TradeCalendar.cal_date).where(
					and_(
						TradeCalendar.exchange == exchange,
						TradeCalendar.cal_date > target_date,
						TradeCalendar.is_open == True
					)
				).order_by(TradeCalendar.cal_date.asc()).limit(1)
			)
		else:
			# 获取上一个交易日
			result = await self.session.execute(
				select(TradeCalendar.cal_date).where(
					and_(
						TradeCalendar.exchange == exchange,
						TradeCalendar.cal_date < target_date,
						TradeCalendar.is_open == True
					)
				).order_by(TradeCalendar.cal_date.desc()).limit(1)
			)

		row = result.scalar_one_or_none()
		return row

	async def get_trade_dates (
			self,
			exchange: str,
			start_date: date,
			end_date: date,
			only_open: bool = True
	) -> List[date]:
		"""获取日期范围内的交易日列表"""
		filters = [
			TradeCalendar.exchange == exchange,
			TradeCalendar.cal_date >= start_date,
			TradeCalendar.cal_date <= end_date
		]

		if only_open:
			filters.append(TradeCalendar.is_open == True)

		result = await self.session.execute(
			select(TradeCalendar.cal_date).where(
				and_(*filters)
			).order_by(TradeCalendar.cal_date.asc())
		)

		return [row[0] for row in result.all()]

	async def get_trade_date_range (
			self,
			exchange: str
	) -> Dict[str, Optional[date]]:
		"""获取交易日历的日期范围"""
		result = await self.session.execute(
			select(
				func.min(TradeCalendar.cal_date),
				func.max(TradeCalendar.cal_date)
			).where(
				and_(
					TradeCalendar.exchange == exchange,
					TradeCalendar.is_open == True
				)
			)
		)

		min_date, max_date = result.first()

		return {
			'exchange': exchange,
			'min_date': min_date,
			'max_date': max_date
		}

	async def get_trade_days_count (
			self,
			exchange: str,
			start_date: date,
			end_date: date
	) -> int:
		"""统计交易日数量"""
		return await self.count(
			and_(
				TradeCalendar.exchange == exchange,
				TradeCalendar.cal_date >= start_date,
				TradeCalendar.cal_date <= end_date,
				TradeCalendar.is_open == True
			)
		)

	async def get_holidays (
			self,
			exchange: str,
			start_date: date,
			end_date: date
	) -> List[date]:
		"""获取假期列表（非交易日）"""
		result = await self.session.execute(
			select(TradeCalendar.cal_date).where(
				and_(
					TradeCalendar.exchange == exchange,
					TradeCalendar.cal_date >= start_date,
					TradeCalendar.cal_date <= end_date,
					TradeCalendar.is_open == False
				)
			).order_by(TradeCalendar.cal_date.asc())
		)

		return [row[0] for row in result.all()]

	async def get_weekend_dates (
			self,
			exchange: str,
			start_date: date,
			end_date: date
	) -> List[date]:
		"""获取周末日期"""
		# 假设周末是非交易日
		result = await self.session.execute(
			select(TradeCalendar.cal_date).where(
				and_(
					TradeCalendar.exchange == exchange,
					TradeCalendar.cal_date >= start_date,
					TradeCalendar.cal_date <= end_date,
					TradeCalendar.is_open == False,
					# 判断是否为周末（周六或周日）
					or_(
						func.extract('dow', TradeCalendar.cal_date) == 6,  # 周六
						func.extract('dow', TradeCalendar.cal_date) == 0  # 周日
					)
				)
			).order_by(TradeCalendar.cal_date.asc())
		)

		return [row[0] for row in result.all()]

	async def get_continuous_trade_days (
			self,
			exchange: str,
			start_date: date,
			days: int
	) -> List[date]:
		"""获取连续交易日"""
		# 从起始日期开始，找到连续的N个交易日
		trade_dates = await self.get_trade_dates(
			exchange, start_date, start_date + timedelta(days=365)
		)

		if len(trade_dates) < days:
			return []

		# 检查是否连续
		continuous_dates = []
		for i in range(len(trade_dates) - days + 1):
			date_slice = trade_dates[i:i + days]
			is_continuous = True

			# 检查日期是否连续
			for j in range(1, len(date_slice)):
				if (date_slice[j] - date_slice[j - 1]).days > 1:
					is_continuous = False
					break

			if is_continuous:
				continuous_dates.append(date_slice)

		return continuous_dates[0] if continuous_dates else []

	async def get_trading_week (
			self,
			exchange: str,
			target_date: date
	) -> Dict[str, Any]:
		"""获取交易周信息"""
		# 找到该日期所在周的第一个交易日和最后一个交易日
		# 首先找到该日期前一个交易日和后一个交易日
		prev_trade_date = await self.get_trade_date(exchange, target_date, 'previous')
		next_trade_date = await self.get_trade_date(exchange, target_date, 'next')

		# 向前找，直到找到周一或周一的交易日
		week_start = target_date
		while week_start.weekday() != 0:  # 0 表示周一
			week_start -= timedelta(days=1)

		# 向后找，直到找到周五或周五的交易日
		week_end = target_date
		while week_end.weekday() != 4:  # 4 表示周五
			week_end += timedelta(days=1)

		# 获取这一周的所有交易日
		week_trade_dates = await self.get_trade_dates(
			exchange, week_start, week_end
		)

		return {
			'target_date': target_date,
			'week_start': week_start,
			'week_end': week_end,
			'prev_trade_date': prev_trade_date,
			'next_trade_date': next_trade_date,
			'week_trade_dates': week_trade_dates,
			'trade_days_count': len(week_trade_dates)
		}

	async def get_trading_month (
			self,
			exchange: str,
			target_date: date
	) -> Dict[str, Any]:
		"""获取交易月信息"""
		# 获取该月的第一天和最后一天
		month_start = date(target_date.year, target_date.month, 1)

		if target_date.month == 12:
			month_end = date(target_date.year, 12, 31)
		else:
			month_end = date(target_date.year, target_date.month + 1, 1) - timedelta(days=1)

		# 获取该月的所有交易日
		month_trade_dates = await self.get_trade_dates(
			exchange, month_start, month_end
		)

		return {
			'target_date': target_date,
			'month_start': month_start,
			'month_end': month_end,
			'month_trade_dates': month_trade_dates,
			'trade_days_count': len(month_trade_dates),
			'calendar_days': (month_end - month_start).days + 1
		}

	async def get_trading_year (
			self,
			exchange: str,
			year: int
	) -> Dict[str, Any]:
		"""获取交易年信息"""
		# 获取该年的第一天和最后一天
		year_start = date(year, 1, 1)
		year_end = date(year, 12, 31)

		# 获取该年的所有交易日
		year_trade_dates = await self.get_trade_dates(
			exchange, year_start, year_end
		)

		return {
			'year': year,
			'year_start': year_start,
			'year_end': year_end,
			'trade_days_count': len(year_trade_dates),
			'calendar_days': 366 if year % 4 == 0 and (year % 100 != 0 or year % 400 == 0) else 365
		}

	async def get_trading_season (
			self,
			exchange: str,
			target_date: date
	) -> Dict[str, Any]:
		"""获取交易季度信息"""
		# 确定季度
		quarter = (target_date.month - 1) // 3 + 1

		# 季度开始月份
		quarter_start_month = (quarter - 1) * 3 + 1
		quarter_start = date(target_date.year, quarter_start_month, 1)

		# 季度结束月份
		quarter_end_month = quarter_start_month + 2
		if quarter_end_month == 12:
			quarter_end = date(target_date.year, 12, 31)
		else:
			quarter_end = date(target_date.year, quarter_end_month + 1, 1) - timedelta(days=1)

		# 获取该季度的所有交易日
		quarter_trade_dates = await self.get_trade_dates(
			exchange, quarter_start, quarter_end
		)

		return {
			'target_date': target_date,
			'quarter': quarter,
			'quarter_start': quarter_start,
			'quarter_end': quarter_end,
			'quarter_trade_dates': quarter_trade_dates,
			'trade_days_count': len(quarter_trade_dates),
			'calendar_days': (quarter_end - quarter_start).days + 1
		}

	async def get_exchange_statistics (
			self,
			start_date: date,
			end_date: date
	) -> Dict[str, Any]:
		"""获取交易所统计信息"""
		result = await self.session.execute(
			select(
				TradeCalendar.exchange,
				func.count(TradeCalendar.cal_date).label('total_days'),
				func.sum(case([(TradeCalendar.is_open == True, 1)], else_=0)).label('trade_days'),
				func.sum(case([(TradeCalendar.is_open == False, 1)], else_=0)).label('non_trade_days')
			).where(
				and_(
					TradeCalendar.cal_date >= start_date,
					TradeCalendar.cal_date <= end_date
				)
			).group_by(
				TradeCalendar.exchange
			).order_by(
				TradeCalendar.exchange
			)
		)

		rows = result.all()

		statistics = {}
		for row in rows:
			statistics[row.exchange] = {
				'total_days': row.total_days,
				'trade_days': row.trade_days or 0,
				'non_trade_days': row.non_trade_days or 0,
				'trade_ratio': row.trade_days / row.total_days * 100 if row.total_days > 0 else 0
			}

		return statistics

	async def get_date_statistics (
			self,
			exchange: str,
			start_year: int,
			end_year: int
	) -> Dict[str, Any]:
		"""获取年度日期统计"""
		statistics = {}

		for year in range(start_year, end_year + 1):
			year_stats = await self.get_trading_year(exchange, year)
			statistics[year] = {
				'trade_days': year_stats['trade_days_count'],
				'trade_ratio': year_stats['trade_days_count'] / year_stats['calendar_days'] * 100
			}

		return statistics

	async def batch_create (
			self,
			data_list: List[Dict[str, Any]]
	) -> List[TradeCalendar]:
		"""批量创建交易日历记录"""
		return await self.base_repo.batch_create(data_list)

	async def batch_upsert (
			self,
			data_list: List[Dict[str, Any]],
			match_fields: List[str] = ['exchange', 'cal_date']
	) -> List[TradeCalendar]:
		"""批量插入或更新交易日历记录"""
		return await self.base_repo.batch_upsert(data_list, match_fields)

	async def import_calendar_data (
			self,
			exchange: str,
			calendar_data: List[Dict[str, Any]]
	) -> Dict[str, int]:
		"""导入交易日历数据"""
		success_count = 0
		failed_count = 0

		for data in calendar_data:
			cal_date = data.get('cal_date')
			is_open = data.get('is_open', False)
			pretrade_date = data.get('pretrade_date')

			if not cal_date:
				failed_count += 1
				continue

			try:
				# 检查是否已存在
				existing = await self.get(exchange, cal_date)

				if existing:
					# 更新现有记录
					update_data = {
						'is_open': is_open,
						'pretrade_date': pretrade_date
					}
					result = await self.update(exchange, cal_date, update_data)
				else:
					# 创建新记录
					create_data = {
						'exchange': exchange,
						'cal_date': cal_date,
						'is_open': is_open,
						'pretrade_date': pretrade_date
					}
					result = await self.create(create_data)

				if result:
					success_count += 1
				else:
					failed_count += 1
			except Exception:
				failed_count += 1

		return {
			'exchange': exchange,
			'success': success_count,
			'failed': failed_count,
			'total': len(calendar_data)
		}

	async def get_calendar_summary (self) -> Dict[str, Any]:
		"""获取交易日历数据摘要"""
		# 获取所有交易所
		exchanges = await self.session.execute(
			select(TradeCalendar.exchange).distinct().order_by(TradeCalendar.exchange)
		)

		exchange_list = [row[0] for row in exchanges.all()]

		# 获取总体统计
		total_count = await self.count()

		# 获取交易日的总体统计
		trade_days_count = await self.count(TradeCalendar.is_open == True)

		# 获取日期范围
		date_range = await self.session.execute(
			select(
				func.min(TradeCalendar.cal_date),
				func.max(TradeCalendar.cal_date)
			)
		)

		min_date, max_date = date_range.first()

		# 按交易所统计
		exchange_stats = {}
		for exchange in exchange_list:
			exchange_dates = await self.session.execute(
				select(
					func.count(TradeCalendar.cal_date).label('total'),
					func.sum(case([(TradeCalendar.is_open == True, 1)], else_=0)).label('trade_days')
				).where(
					TradeCalendar.exchange == exchange
				)
			)

			row = exchange_dates.first()
			if row:
				exchange_stats[exchange] = {
					'total_days': row.total or 0,
					'trade_days': row.trade_days or 0,
					'non_trade_days': (row.total or 0) - (row.trade_days or 0)
				}

		return {
			'exchanges': exchange_list,
			'total_records': total_count,
			'trade_days_count': trade_days_count,
			'non_trade_days_count': total_count - trade_days_count,
			'date_range': {
				'min_date': min_date,
				'max_date': max_date
			},
			'exchange_stats': exchange_stats
		}