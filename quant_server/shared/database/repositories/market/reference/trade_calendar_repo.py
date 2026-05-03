# quant_server/shared/database/repositories/market/reference/trade_calendar_repo.py
"""
交易日历数据仓库 - 继承HyperRepositoryBase
专为时序数据优化，提供交易日历相关的高效数据访问接口

设计说明：
1. TradeCalendar是时序数据表（按日期组织），适合继承HyperRepositoryBase
2. 提供交易日判断、日期范围查询、交易日统计等业务方法
3. 支持批量导入和更新日历数据
4. 为交易系统提供核心的日期服务支持
"""

from datetime import date, datetime, timedelta
from typing import List, Dict, Any, Optional

from sqlalchemy import select, and_, or_, func, case, delete
from sqlalchemy.ext.asyncio import AsyncSession

from shared.database.models.data_models import TradeCalendar
from shared.database.repositories.base.hyper_repository_base import HyperRepositoryBase, RepositoryError
from shared.database.repositories.types import TimeRange, PaginationParams, PaginationResult, FilterCondition, SortCondition, FilterOperator


class TradeCalendarRepository(HyperRepositoryBase[TradeCalendar]):
	"""
	交易日历数据仓库 - 继承HyperRepositoryBase

	专为时序数据优化，提供高效的交易日历数据访问服务
	支持时间范围查询、批量操作、时序聚合等特性
	"""

	async def _count_with_expression (self, *expressions) -> int:
		"""
		使用表达式统计记录数

		Args:
			*expressions: SQLAlchemy 表达式

		Returns:
			记录数
		"""
		try:
			query = select(func.count()).select_from(self.model)

			for expr in expressions:
				query = query.where(expr)

			result = await self.session.execute(query)
			return result.scalar() or 0

		except Exception as e:
			raise RepositoryError(f"使用表达式统计记录数失败: {str(e)}")

	def __init__ (self, session: AsyncSession):
		"""
		初始化交易日历Repository

		Args:
			session: 数据库会话
		"""
		super().__init__(session, TradeCalendar)
		# TradeCalendar使用cal_date作为时间列
		self.time_column = "cal_date"

	# ==================== 基础CRUD操作（复用基类） ====================

	# 以下方法直接从HyperRepositoryBase继承：
	# - get_by_time_range: 按时间范围查询
	# - get_latest_record: 获取最新记录
	# - batch_insert: 批量插入数据
	# - delete_by_time_range: 按时间范围删除

	async def get_by_exchange_and_date (
			self,
			exchange: str,
			cal_date: date
	) -> Optional[TradeCalendar]:
		"""
		根据交易所和日期获取交易日历记录

		Args:
			exchange: 交易所代码
			cal_date: 日历日期

		Returns:
			交易日历记录或None
		"""
		try:
			query = select(self.model).where(
				and_(
					self.model.exchange == exchange,
					self.model.cal_date == cal_date
				)
			)

			result = await self.session.execute(query)
			return result.scalar_one_or_none()

		except Exception as e:
			raise RepositoryError(f"获取交易日历记录失败: {str(e)}")

	async def get_by_date (
			self,
			cal_date: date,
			exchange: Optional[str] = None
	) -> List[TradeCalendar]:
		"""
		根据日期获取交易日历记录

		Args:
			cal_date: 日历日期
			exchange: 交易所代码（可选，不指定则返回所有交易所）

		Returns:
			指定日期的交易日历记录列表
		"""
		try:
			query = select(self.model).where(
				self.model.cal_date == cal_date
			)

			if exchange:
				query = query.where(self.model.exchange == exchange)

			result = await self.session.execute(query)
			return result.scalars().all()
		except Exception as e:
			raise RepositoryError(f"根据日期查询交易日历失败: {str(e)}")

	async def upsert_calendar_record (
			self,
			exchange: str,
			cal_date: date,
			data: Dict[str, Any]
	) -> TradeCalendar:
		"""
		插入或更新交易日历记录

		Args:
			exchange: 交易所代码
			cal_date: 日历日期
			data: 更新数据

		Returns:
			更新后的交易日历记录
		"""
		try:
			# 检查是否已存在
			existing = await self.get_by_exchange_and_date(exchange, cal_date)

			if existing:
				# 更新现有记录
				update_data = data.copy()
				if hasattr(self.model, 'updated_at'):
					update_data['updated_at'] = datetime.now()

				# 使用复合主键进行更新
				await self.update_by(
					{"exchange": exchange, "cal_date": cal_date},
					update_data
				)
				return await self.get_by_exchange_and_date(exchange, cal_date)
			else:
				# 创建新记录
				create_data = data.copy()
				create_data['exchange'] = exchange
				create_data['cal_date'] = cal_date

				if hasattr(self.model, 'created_at'):
					create_data['created_at'] = create_data.get('created_at', datetime.now())
				if hasattr(self.model, 'updated_at'):
					create_data['updated_at'] = create_data.get('updated_at', datetime.now())

				return await self.create(create_data)

		except Exception as e:
			raise RepositoryError(f"插入或更新交易日历记录失败: {str(e)}")

	# ==================== 业务查询方法 ====================

	async def is_trade_date (
			self,
			exchange: str,
			check_date: date
	) -> bool:
		"""
		检查指定日期是否为交易日

		Args:
			exchange: 交易所代码
			check_date: 检查日期

		Returns:
			如果是交易日返回True，否则返回False
		"""
		try:
			calendar = await self.get_by_exchange_and_date(exchange, check_date)
			return calendar is not None and calendar.is_open

		except Exception as e:
			raise RepositoryError(f"检查交易日失败: {str(e)}")

	async def get_trade_date (
			self,
			exchange: str,
			target_date: date,
			direction: str = 'next'
	) -> Optional[date]:
		"""
		获取下一个或上一个交易日

		Args:
			exchange: 交易所代码
			target_date: 目标日期
			direction: 方向，'next'（下一个交易日）或'previous'（上一个交易日）

		Returns:
			交易日日期或None
		"""
		try:
			if direction == 'next':
				# 获取下一个交易日
				query = select(self.model.cal_date).where(
					and_(
						self.model.exchange == exchange,
						self.model.cal_date > target_date,
						self.model.is_open == True
					)
				).order_by(self.model.cal_date.asc()).limit(1)
			else:
				# 获取上一个交易日
				query = select(self.model.cal_date).where(
					and_(
						self.model.exchange == exchange,
						self.model.cal_date < target_date,
						self.model.is_open == True
					)
				).order_by(self.model.cal_date.desc()).limit(1)

			result = await self.session.execute(query)
			return result.scalar_one_or_none()

		except Exception as e:
			raise RepositoryError(f"获取交易日失败: {str(e)}")

	async def get_trade_dates (
			self,
			exchange: str,
			start_date: date,
			end_date: date,
			only_open: bool = True
	) -> List[date]:
		"""
		获取日期范围内的交易日列表

		Args:
			exchange: 交易所代码
			start_date: 开始日期
			end_date: 结束日期
			only_open: 是否只返回交易日

		Returns:
			交易日日期列表
		"""
		try:
			filters = [
				self.model.exchange == exchange,
				self.model.cal_date >= start_date,
				self.model.cal_date <= end_date
			]

			if only_open:
				filters.append(self.model.is_open == True)

			query = select(self.model.cal_date).where(
				and_(*filters)
			).order_by(self.model.cal_date.asc())

			result = await self.session.execute(query)
			return [row[0] for row in result.all()]

		except Exception as e:
			raise RepositoryError(f"获取交易日列表失败: {str(e)}")

	async def get_trade_date_range (
			self,
			exchange: str
	) -> Dict[str, Optional[date]]:
		"""
		获取交易日历的日期范围

		Args:
			exchange: 交易所代码

		Returns:
			包含最小和最大交易日的字典
		"""
		try:
			result = await self.session.execute(
				select(
					func.min(self.model.cal_date),
					func.max(self.model.cal_date)
				).where(
					and_(
						self.model.exchange == exchange,
						self.model.is_open == True
					)
				)
			)

			min_date, max_date = result.first()

			return {
				'exchange': exchange,
				'min_date': min_date,
				'max_date': max_date,
				'date_range': TimeRange(start=min_date, end=max_date) if min_date and max_date else None
			}

		except Exception as e:
			raise RepositoryError(f"获取交易日历范围失败: {str(e)}")

	async def get_trade_days_count (
			self,
			exchange: str,
			start_date: date,
			end_date: date
	) -> int:
		"""
		统计交易日数量

		Args:
			exchange: 交易所代码
			start_date: 开始日期
			end_date: 结束日期

		Returns:
			交易日数量
		"""
		try:
			return await self._count_with_expression(
				and_(
					self.model.exchange == exchange,
					self.model.cal_date >= start_date,
					self.model.cal_date <= end_date,
					self.model.is_open == True
				)
			)

		except Exception as e:
			raise RepositoryError(f"统计交易日数量失败: {str(e)}")

	async def get_holidays (
			self,
			exchange: str,
			start_date: date,
			end_date: date
	) -> List[date]:
		"""
		获取假期列表（非交易日）

		Args:
			exchange: 交易所代码
			start_date: 开始日期
			end_date: 结束日期

		Returns:
			假期日期列表
		"""
		try:
			query = select(self.model.cal_date).where(
				and_(
					self.model.exchange == exchange,
					self.model.cal_date >= start_date,
					self.model.cal_date <= end_date,
					self.model.is_open == False
				)
			).order_by(self.model.cal_date.asc())

			result = await self.session.execute(query)
			return [row[0] for row in result.all()]

		except Exception as e:
			raise RepositoryError(f"获取假期列表失败: {str(e)}")

	async def get_weekend_dates (
			self,
			exchange: str,
			start_date: date,
			end_date: date
	) -> List[date]:
		"""
		获取周末日期

		Args:
			exchange: 交易所代码
			start_date: 开始日期
			end_date: 结束日期

		Returns:
			周末日期列表
		"""
		try:
			# 假设周末是非交易日
			query = select(self.model.cal_date).where(
				and_(
					self.model.exchange == exchange,
					self.model.cal_date >= start_date,
					self.model.cal_date <= end_date,
					self.model.is_open == False,
					# 判断是否为周末（周六或周日）
					or_(
						func.extract('dow', self.model.cal_date) == 6,  # 周六
						func.extract('dow', self.model.cal_date) == 0  # 周日
					)
				)
			).order_by(self.model.cal_date.asc())

			result = await self.session.execute(query)
			return [row[0] for row in result.all()]

		except Exception as e:
			raise RepositoryError(f"获取周末日期失败: {str(e)}")

	async def get_continuous_trade_days (
			self,
			exchange: str,
			start_date: date,
			days: int
	) -> List[date]:
		"""
		获取连续交易日

		Args:
			exchange: 交易所代码
			start_date: 起始日期
			days: 需要的连续交易天数

		Returns:
			连续交易日列表
		"""
		try:
			# 从起始日期开始，找到连续的N个交易日
			trade_dates = await self.get_trade_dates(
				exchange, start_date, start_date + timedelta(days=365)
			)

			if len(trade_dates) < days:
				return []

			# 检查是否连续
			for i in range(len(trade_dates) - days + 1):
				date_slice = trade_dates[i:i + days]
				is_continuous = True

				# 检查日期是否连续
				for j in range(1, len(date_slice)):
					if (date_slice[j] - date_slice[j - 1]).days > 1:
						is_continuous = False
						break

				if is_continuous:
					return date_slice

			return []

		except Exception as e:
			raise RepositoryError(f"获取连续交易日失败: {str(e)}")

	# ==================== 时间周期分析 ====================

	async def get_trading_week (
			self,
			exchange: str,
			target_date: date
	) -> Dict[str, Any]:
		"""
		获取交易周信息

		Args:
			exchange: 交易所代码
			target_date: 目标日期

		Returns:
			交易周信息字典
		"""
		try:
			# 找到该日期前一个交易日和后一个交易日
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

		except Exception as e:
			raise RepositoryError(f"获取交易周信息失败: {str(e)}")

	async def get_trading_month (
			self,
			exchange: str,
			target_date: date
	) -> Dict[str, Any]:
		"""
		获取交易月信息

		Args:
			exchange: 交易所代码
			target_date: 目标日期

		Returns:
			交易月信息字典
		"""
		try:
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

		except Exception as e:
			raise RepositoryError(f"获取交易月信息失败: {str(e)}")

	async def get_trading_year (
			self,
			exchange: str,
			year: int
	) -> Dict[str, Any]:
		"""
		获取交易年信息

		Args:
			exchange: 交易所代码
			year: 年份

		Returns:
			交易年信息字典
		"""
		try:
			# 获取该年的第一天和最后一天
			year_start = date(year, 1, 1)
			year_end = date(year, 12, 31)

			# 获取该年的所有交易日
			year_trade_dates = await self.get_trade_dates(
				exchange, year_start, year_end
			)

			# 判断是否为闰年
			is_leap_year = year % 4 == 0 and (year % 100 != 0 or year % 400 == 0)

			return {
				'year': year,
				'year_start': year_start,
				'year_end': year_end,
				'trade_dates': year_trade_dates,
				'trade_days_count': len(year_trade_dates),
				'calendar_days': 366 if is_leap_year else 365,
				'trade_ratio': len(year_trade_dates) / (366 if is_leap_year else 365) * 100
			}

		except Exception as e:
			raise RepositoryError(f"获取交易年信息失败: {str(e)}")

	async def get_trading_season (
			self,
			exchange: str,
			target_date: date
	) -> Dict[str, Any]:
		"""
		获取交易季度信息

		Args:
			exchange: 交易所代码
			target_date: 目标日期

		Returns:
			交易季度信息字典
		"""
		try:
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

		except Exception as e:
			raise RepositoryError(f"获取交易季度信息失败: {str(e)}")

	# ==================== 统计分析 ====================

	async def get_exchange_statistics (
			self,
			start_date: date,
			end_date: date
	) -> Dict[str, Any]:
		"""
		获取交易所统计信息

		Args:
			start_date: 开始日期
			end_date: 结束日期

		Returns:
			交易所统计信息字典
		"""
		try:
			result = await self.session.execute(
				select(
					self.model.exchange,
					func.count(self.model.cal_date).label('total_days'),
					func.sum(case((self.model.is_open == True, 1), else_=0)).label('trade_days'),
					func.sum(case((self.model.is_open == False, 1), else_=0)).label('non_trade_days')
				).where(
					and_(
						self.model.cal_date >= start_date,
						self.model.cal_date <= end_date
					)
				).group_by(
					self.model.exchange
				).order_by(
					self.model.exchange
				)
			)

			rows = result.all()

			statistics = {}
			for row in rows:
				total_days = row.total_days or 0
				trade_days = row.trade_days or 0

				statistics[row.exchange] = {
					'total_days': total_days,
					'trade_days': trade_days,
					'non_trade_days': row.non_trade_days or 0,
					'trade_ratio': trade_days / total_days * 100 if total_days > 0 else 0
				}

			return statistics

		except Exception as e:
			raise RepositoryError(f"获取交易所统计信息失败: {str(e)}")

	async def get_date_statistics (
			self,
			exchange: str,
			start_year: int,
			end_year: int
	) -> Dict[str, Any]:
		"""
		获取年度日期统计

		Args:
			exchange: 交易所代码
			start_year: 开始年份
			end_year: 结束年份

		Returns:
			年度日期统计字典
		"""
		try:
			statistics = {}

			for year in range(start_year, end_year + 1):
				year_stats = await self.get_trading_year(exchange, year)

				statistics[year] = {
					'trade_days': year_stats['trade_days_count'],
					'trade_ratio': year_stats['trade_ratio'],
					'year_start': year_stats['year_start'],
					'year_end': year_stats['year_end']
				}

			return statistics

		except Exception as e:
			raise RepositoryError(f"获取年度日期统计失败: {str(e)}")

	# ==================== 批量操作 ====================

	async def import_calendar_data (
			self,
			exchange: str,
			calendar_data: List[Dict[str, Any]]
	) -> Dict[str, int]:
		"""
		导入交易日历数据

		Args:
			exchange: 交易所代码
			calendar_data: 日历数据列表

		Returns:
			导入结果统计
		"""
		try:
			success_count = 0
			failed_count = 0
			records = []

			for data in calendar_data:
				cal_date = data.get('cal_date')
				is_open = data.get('is_open', False)
				pretrade_date = data.get('pretrade_date')

				if not cal_date:
					failed_count += 1
					continue

				try:
					# 构建记录数据
					record_data = {
						'exchange': exchange,
						'cal_date': cal_date,
						'is_open': is_open,
						'pretrade_date': pretrade_date
					}

					# 检查是否已存在
					existing = await self.get_by_exchange_and_date(exchange, cal_date)

					if existing:
						# 更新现有记录
						update_data = {
							'is_open': is_open,
							'pretrade_date': pretrade_date
						}
						if hasattr(self.model, 'updated_at'):
							update_data['updated_at'] = datetime.now()

						# 使用复合主键进行更新
						await self.update_by(
							{"exchange": exchange, "cal_date": cal_date},
							update_data
						)
					else:
						# 添加到批量插入列表
						if hasattr(self.model, 'created_at'):
							record_data['created_at'] = record_data.get('created_at', datetime.now())
						if hasattr(self.model, 'updated_at'):
							record_data['updated_at'] = record_data.get('updated_at', datetime.now())

						records.append(record_data)

					success_count += 1
				except Exception as e:
					# 记录异常信息
					print(f"处理日历数据失败 {cal_date}: {str(e)}")
					failed_count += 1

			# 批量插入新记录
			if records:
				await self.batch_insert(records, conflict_strategy="ignore")

			return {
				'exchange': exchange,
				'success': success_count,
				'failed': failed_count,
				'total': len(calendar_data)
			}

		except Exception as e:
			raise RepositoryError(f"导入交易日历数据失败: {str(e)}")

	async def clear_exchange_data (
			self,
			exchange: str,
			start_date: Optional[date] = None,
			end_date: Optional[date] = None
	) -> int:
		"""
		清空交易所的日历数据

		Args:
			exchange: 交易所代码
			start_date: 开始日期（可选）
			end_date: 结束日期（可选）

		Returns:
			删除的记录数
		"""
		try:
			filters = [self.model.exchange == exchange]

			if start_date:
				filters.append(self.model.cal_date >= start_date)
			if end_date:
				filters.append(self.model.cal_date <= end_date)

			query = delete(self.model).where(and_(*filters))

			result = await self.session.execute(query) #type:ignore
			return result.rowcount or 0

		except Exception as e:
			raise RepositoryError(f"清空交易所数据失败: {str(e)}")

	# ==================== 数据摘要 ====================

	async def get_calendar_summary (self) -> Dict[str, Any]:
		"""
		获取交易日历数据摘要

		Returns:
			日历数据摘要字典
		"""
		try:
			# 获取所有交易所
			exchanges = await self.session.execute(
				select(self.model.exchange).distinct().order_by(self.model.exchange)
			)

			exchange_list = [row[0] for row in exchanges.all()]

			# 获取总体统计
			total_count = await self.count()

			# 获取交易日的总体统计
			trade_days_count = await self._count_with_expression(self.model.is_open == True)

			# 获取日期范围
			date_range = await self.session.execute(
				select(
					func.min(self.model.cal_date),
					func.max(self.model.cal_date)
				)
			)

			min_date, max_date = date_range.first()

			# 按交易所统计
			exchange_stats = {}
			for exchange in exchange_list:
				exchange_dates = await self.session.execute(
					select(
						func.count(self.model.cal_date).label('total'),
						func.sum(case((self.model.is_open == True, 1), else_=0)).label('trade_days')
					).where(
						self.model.exchange == exchange
					)
				)

				row = exchange_dates.first()
				if row:
					total = row.total or 0
					trade_days = row.trade_days or 0

					exchange_stats[exchange] = {
						'total_days': total,
						'trade_days': trade_days,
						'non_trade_days': total - trade_days,
						'trade_ratio': trade_days / total * 100 if total > 0 else 0
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
				'exchange_stats': exchange_stats,
				'summary': f"共{len(exchange_list)}个交易所，{total_count}条记录，{trade_days_count}个交易日"
			}

		except Exception as e:
			raise RepositoryError(f"获取日历数据摘要失败: {str(e)}")

	# ==================== 高级查询 ====================

	async def paginate_by_date_range (
			self,
			exchange: str,
			start_date: date,
			end_date: date,
			pagination: PaginationParams,
			only_open: Optional[bool] = None
	) -> PaginationResult[TradeCalendar]:
		"""
		按日期范围分页查询

		Args:
			exchange: 交易所代码
			start_date: 开始日期
			end_date: 结束日期
			pagination: 分页参数
			only_open: 是否只查询交易日

		Returns:
			分页结果
		"""
		try:
			filters = [
				self.model.exchange == exchange,
				self.model.cal_date >= start_date,
				self.model.cal_date <= end_date
			]

			if only_open is not None:
				filters.append(self.model.is_open == only_open)

			filter_conditions = [
				FilterCondition(field="cal_date", operator=FilterOperator.GE, value=start_date),
				FilterCondition(field="cal_date", operator=FilterOperator.LE, value=end_date),
				FilterCondition(field="exchange", operator=FilterOperator.EQ, value=exchange)
			]
			if only_open is not None:
				filter_conditions.append(FilterCondition(field="is_open", operator=FilterOperator.EQ, value=only_open))

			return await self.paginate(
				pagination=pagination,
				filters=filter_conditions,
				sorts=[SortCondition(field="cal_date", descending=False)]
			)

		except Exception as e:
			raise RepositoryError(f"分页查询失败: {str(e)}")

	async def find_trade_date_gaps (
			self,
			exchange: str,
			start_date: date,
			end_date: date
	) -> List[Dict[str, Any]]:
		"""
		查找交易日之间的间隔

		Args:
			exchange: 交易所代码
			start_date: 开始日期
			end_date: 结束日期

		Returns:
			间隔信息列表
		"""
		try:
			# 获取所有交易日
			trade_dates = await self.get_trade_dates(exchange, start_date, end_date)

			if len(trade_dates) <= 1:
				return []

			gaps = []
			for i in range(1, len(trade_dates)):
				prev_date = trade_dates[i - 1]
				curr_date = trade_dates[i]
				gap_days = (curr_date - prev_date).days - 1

				if gap_days > 0:
					gaps.append({
						'prev_trade_date': prev_date,
						'next_trade_date': curr_date,
						'gap_days': gap_days,
						'gap_start': prev_date + timedelta(days=1),
						'gap_end': curr_date - timedelta(days=1)
					})

			return gaps

		except Exception as e:
			raise RepositoryError(f"查找交易日间隔失败: {str(e)}")