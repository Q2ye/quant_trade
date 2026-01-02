# -*- coding: utf-8 -*-
"""
ST股票列表数据仓库
提供ST股票列表数据的统一访问接口
位置：shared/database/repositories/st_list_repo.py
"""

from typing import List, Optional, Dict, Any
from datetime import date, datetime, timedelta
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, and_, or_, func, desc, distinct

from quant_server.shared.database.repositories.base import BaseRepository
from quant_server.shared.database.models.data_models import StockSTList


class STListRepository:
	"""ST股票列表数据Repository - 纯数据访问"""

	def __init__ (self, session: AsyncSession):
		self.session = session
		self.base_repo = BaseRepository(session, StockSTList)

	# ==================== 基础CRUD操作 ====================

	async def create (self, data: Dict[str, Any]) -> StockSTList:
		"""创建ST股票记录"""
		return await self.base_repo.create(data)

	async def get (self, id: int) -> Optional[StockSTList]:
		"""根据ID获取ST股票记录"""
		return await self.base_repo.get(id)

	async def update (self, id: int, data: Dict[str, Any]) -> Optional[StockSTList]:
		"""更新ST股票记录"""
		return await self.base_repo.update(id, data)

	async def delete (self, id: int, soft: bool = True) -> bool:
		"""删除ST股票记录"""
		return await self.base_repo.delete(id, soft)

	async def get_one (self, *filters) -> Optional[StockSTList]:
		"""根据条件获取单个ST股票记录"""
		return await self.base_repo.get_one(*filters)

	async def get_many (
			self,
			*filters,
			skip: int = 0,
			limit: int = 100,
			order_by: str = None
	) -> List[StockSTList]:
		"""根据条件获取多个ST股票记录"""
		return await self.base_repo.get_many(*filters, skip=skip, limit=limit, order_by=order_by)

	async def count (self, *filters) -> int:
		"""统计ST股票记录数"""
		return await self.base_repo.count(*filters)

	# ==================== 业务查询方法 ====================

	async def get_by_ts_code (
			self,
			ts_code: str,
			trade_date: Optional[date] = None
	) -> Optional[StockSTList]:
		"""根据股票代码获取ST记录"""
		filters = [StockSTList.ts_code == ts_code]

		if trade_date:
			filters.append(StockSTList.trade_date == trade_date)
		else:
			# 如果没有指定日期，获取最新的记录
			result = await self.session.execute(
				select(StockSTList).where(
					StockSTList.ts_code == ts_code
				).order_by(
					StockSTList.trade_date.desc()
				).limit(1)
			)
			return result.scalar_one_or_none()

		return await self.get_one(*filters)

	async def get_st_history (
			self,
			ts_code: str,
			start_date: Optional[date] = None,
			end_date: Optional[date] = None
	) -> List[StockSTList]:
		"""获取股票的ST历史记录"""
		filters = [StockSTList.ts_code == ts_code]

		if start_date:
			filters.append(StockSTList.trade_date >= start_date)
		if end_date:
			filters.append(StockSTList.trade_date <= end_date)

		return await self.get_many(
			*filters,
			order_by=StockSTList.trade_date.asc()
		)

	async def get_current_st_stocks (
			self,
			trade_date: Optional[date] = None
	) -> List[StockSTList]:
		"""获取当前ST股票列表"""
		if not trade_date:
			trade_date = datetime.now().date()

		# 获取指定日期或之前的最新ST状态
		subquery = select(
			StockSTList.ts_code,
			func.max(StockSTList.trade_date).label('max_date')
		).where(
			StockSTList.trade_date <= trade_date
		).group_by(
			StockSTList.ts_code
		).subquery()

		query = select(StockSTList).join(
			subquery,
			and_(
				StockSTList.ts_code == subquery.c.ts_code,
				StockSTList.trade_date == subquery.c.max_date
			)
		).where(
			StockSTList.is_st == 1  # 只返回ST状态为1的记录
		).order_by(
			StockSTList.ts_code
		)

		result = await self.session.execute(query)
		return result.scalars().all()

	async def get_stocks_by_st_type (
			self,
			st_type: str,
			trade_date: Optional[date] = None
	) -> List[StockSTList]:
		"""根据ST类型获取股票"""
		if not trade_date:
			trade_date = datetime.now().date()

		# 获取指定日期或之前的最新记录
		subquery = select(
			StockSTList.ts_code,
			func.max(StockSTList.trade_date).label('max_date')
		).where(
			StockSTList.trade_date <= trade_date
		).group_by(
			StockSTList.ts_code
		).subquery()

		query = select(StockSTList).join(
			subquery,
			and_(
				StockSTList.ts_code == subquery.c.ts_code,
				StockSTList.trade_date == subquery.c.max_date
			)
		).where(
			and_(
				StockSTList.st_type == st_type,
				StockSTList.is_st == 1
			)
		).order_by(
			StockSTList.ts_code
		)

		result = await self.session.execute(query)
		return result.scalars().all()

	async def get_st_status_changes (
			self,
			start_date: date,
			end_date: date
	) -> List[Dict[str, Any]]:
		"""获取ST状态变更记录"""
		# 获取每个股票在开始日期和结束日期的状态
		start_subquery = select(
			StockSTList.ts_code,
			StockSTList.is_st.label('start_is_st'),
			StockSTList.st_type.label('start_st_type')
		).where(
			StockSTList.trade_date == start_date
		).subquery()

		end_subquery = select(
			StockSTList.ts_code,
			StockSTList.is_st.label('end_is_st'),
			StockSTList.st_type.label('end_st_type')
		).where(
			StockSTList.trade_date == end_date
		).subquery()

		query = select(
			start_subquery.c.ts_code,
			start_subquery.c.start_is_st,
			start_subquery.c.start_st_type,
			end_subquery.c.end_is_st,
			end_subquery.c.end_st_type
		).join(
			end_subquery,
			start_subquery.c.ts_code == end_subquery.c.ts_code,
			isouter=True
		).where(
			or_(
				start_subquery.c.start_is_st != end_subquery.c.end_is_st,
				start_subquery.c.start_st_type != end_subquery.c.end_st_type,
				end_subquery.c.ts_code.is_(None)
			)
		).order_by(
			start_subquery.c.ts_code
		)

		result = await self.session.execute(query)
		rows = result.all()

		changes = []
		for row in rows:
			change_type = None
			if row.end_is_st is None:
				change_type = '退市或数据缺失'
			elif row.start_is_st == 0 and row.end_is_st == 1:
				change_type = '新ST'
			elif row.start_is_st == 1 and row.end_is_st == 0:
				change_type = '摘帽'
			elif row.start_is_st == 1 and row.end_is_st == 1 and row.start_st_type != row.end_st_type:
				change_type = 'ST类型变更'

			changes.append({
				'ts_code': row.ts_code,
				'change_type': change_type,
				'start_status': {
					'is_st': row.start_is_st,
					'st_type': row.start_st_type
				},
				'end_status': {
					'is_st': row.end_is_st,
					'st_type': row.end_st_type
				}
			})

		return changes

	async def get_st_statistics (
			self,
			trade_date: Optional[date] = None
	) -> Dict[str, Any]:
		"""获取ST股票统计信息"""
		if not trade_date:
			trade_date = datetime.now().date()

		# 获取当前ST股票
		current_st = await self.get_current_st_stocks(trade_date)

		# 按ST类型统计
		type_stats = {}
		for st in current_st:
			st_type = st.st_type or '未知'
			if st_type not in type_stats:
				type_stats[st_type] = 0
			type_stats[st_type] += 1

		# 统计新增ST（最近30天）
		thirty_days_ago = trade_date - timedelta(days=30)

		# 获取30天前的ST股票
		old_st = await self.get_current_st_stocks(thirty_days_ago)
		old_st_codes = {st.ts_code for st in old_st}

		# 获取现在的ST股票
		current_st_codes = {st.ts_code for st in current_st}

		# 新增ST股票
		new_st_codes = current_st_codes - old_st_codes
		new_st_count = len(new_st_codes)

		# 摘帽股票
		removed_st_codes = old_st_codes - current_st_codes
		removed_st_count = len(removed_st_codes)

		return {
			'trade_date': trade_date,
			'total_st_count': len(current_st),
			'type_stats': type_stats,
			'new_st_count': new_st_count,
			'removed_st_count': removed_st_count,
			'new_st_codes': list(new_st_codes),
			'removed_st_codes': list(removed_st_codes)
		}

	async def get_st_duration (
			self,
			ts_code: str
	) -> Dict[str, Any]:
		"""获取股票的ST持续时间"""
		# 获取所有ST记录
		st_history = await self.get_st_history(ts_code)

		if not st_history:
			return {'ts_code': ts_code, 'has_st_history': False}

		# 找出连续的ST期间
		periods = []
		current_period = None

		for record in sorted(st_history, key=lambda x: x.trade_date):
			if record.is_st == 1:
				if current_period is None:
					current_period = {
						'start_date': record.trade_date,
						'end_date': record.trade_date,
						'st_type': record.st_type
					}
				else:
					# 如果类型相同且日期连续，则扩展当前期间
					if (record.st_type == current_period['st_type'] and
							(record.trade_date - current_period['end_date']).days <= 1):
						current_period['end_date'] = record.trade_date
					else:
						# 开始新的期间
						periods.append(current_period)
						current_period = {
							'start_date': record.trade_date,
							'end_date': record.trade_date,
							'st_type': record.st_type
						}
			else:
				if current_period is not None:
					periods.append(current_period)
					current_period = None

		if current_period is not None:
			periods.append(current_period)

		# 计算总ST天数
		total_days = 0
		for period in periods:
			days = (period['end_date'] - period['start_date']).days + 1
			period['days'] = days
			total_days += days

		# 当前是否ST
		latest = await self.get_by_ts_code(ts_code)
		is_currently_st = latest.is_st == 1 if latest else False

		return {
			'ts_code': ts_code,
			'has_st_history': True,
			'total_periods': len(periods),
			'total_days': total_days,
			'periods': periods,
			'is_currently_st': is_currently_st,
			'current_st_type': latest.st_type if is_currently_st else None
		}

	async def search_st_stocks (
			self,
			keyword: Optional[str] = None,
			st_type: Optional[str] = None,
			trade_date: Optional[date] = None,
			limit: int = 100
	) -> List[StockSTList]:
		"""搜索ST股票"""
		if not trade_date:
			trade_date = datetime.now().date()

		# 获取指定日期的最新记录
		subquery = select(
			StockSTList.ts_code,
			func.max(StockSTList.trade_date).label('max_date')
		).where(
			StockSTList.trade_date <= trade_date
		).group_by(
			StockSTList.ts_code
		).subquery()

		query = select(StockSTList).join(
			subquery,
			and_(
				StockSTList.ts_code == subquery.c.ts_code,
				StockSTList.trade_date == subquery.c.max_date
			)
		).where(
			StockSTList.is_st == 1
		)

		filters = []
		if keyword:
			filters.append(
				or_(
					StockSTList.ts_code.like(f"%{keyword}%"),
					StockSTList.name.like(f"%{keyword}%")
				)
			)

		if st_type:
			filters.append(StockSTList.st_type == st_type)

		if filters:
			query = query.where(and_(*filters))

		query = query.order_by(StockSTList.ts_code).limit(limit)

		result = await self.session.execute(query)
		return result.scalars().all()

	async def batch_create (
			self,
			data_list: List[Dict[str, Any]]
	) -> List[StockSTList]:
		"""批量创建ST股票记录"""
		return await self.base_repo.batch_create(data_list)

	async def batch_upsert (
			self,
			data_list: List[Dict[str, Any]],
			match_fields: List[str] = ['ts_code', 'trade_date']
	) -> List[StockSTList]:
		"""批量插入或更新ST股票记录"""
		return await self.base_repo.batch_upsert(data_list, match_fields)

	async def get_st_summary (self) -> Dict[str, Any]:
		"""获取ST股票数据摘要"""
		# 总记录数
		total_count = await self.count()

		# 涉及股票数
		stock_count = await self.session.execute(
			select(func.count(func.distinct(StockSTList.ts_code)))
		)
		stock_count_value = stock_count.scalar() or 0

		# 当前ST股票数
		current_st = await self.get_current_st_stocks()
		current_st_count = len(current_st)

		# ST类型分布
		type_dist = await self.session.execute(
			select(
				StockSTList.st_type,
				func.count(StockSTList.id).label('count')
			).where(
				StockSTList.is_st == 1
			).group_by(
				StockSTList.st_type
			).order_by(
				func.count(StockSTList.id).desc()
			)
		)

		type_stats = {row[0]: row[1] for row in type_dist.all()}

		# 日期范围
		date_range = await self.session.execute(
			select(
				func.min(StockSTList.trade_date),
				func.max(StockSTList.trade_date)
			)
		)
		min_date, max_date = date_range.first()

		# 最近30天变化
		today = datetime.now().date()
		thirty_days_ago = today - timedelta(days=30)
		st_statistics = await self.get_st_statistics(today)

		return {
			'total_records': total_count,
			'unique_stocks': stock_count_value,
			'current_st_count': current_st_count,
			'type_stats': type_stats,
			'date_range': {
				'min_date': min_date,
				'max_date': max_date
			},
			'recent_changes': {
				'new_st_count': st_statistics.get('new_st_count', 0),
				'removed_st_count': st_statistics.get('removed_st_count', 0)
			}
		}