# -*- coding: utf-8 -*-
"""
股票数据仓库
提供股票基础信息和相关数据的统一访问接口
位置：shared/database/repositories/stock_repo.py
"""

from typing import List, Optional, Dict, Any, Tuple
from datetime import date, datetime, timedelta
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, and_, or_, func, desc, distinct, case

from .base import BaseRepository
from quant_server.shared.database.models.data_models import (
	StockBasic, StockCompany, StockDaily, StockDailyBasic,
	StockAdjFactor, StockSTList
)


class StockRepository:
	"""股票数据Repository - 纯数据访问"""

	def __init__ (self, session: AsyncSession):
		self.session = session
		self.basic_repo = BaseRepository(session, StockBasic)
		self.company_repo = BaseRepository(session, StockCompany)
		self.daily_repo = BaseRepository(session, StockDaily)
		self.daily_basic_repo = BaseRepository(session, StockDailyBasic)
		self.adj_factor_repo = BaseRepository(session, StockAdjFactor)
		self.st_list_repo = BaseRepository(session, StockSTList)

	# ==================== 股票基础信息查询 ====================

	async def get_stock_basic (self, ts_code: str) -> Optional[StockBasic]:
		"""获取股票基础信息"""
		return await self.basic_repo.get_one(StockBasic.ts_code == ts_code)

	async def get_stock_by_symbol (self, symbol: str) -> Optional[StockBasic]:
		"""根据股票符号获取股票"""
		return await self.basic_repo.get_one(StockBasic.symbol == symbol)

	async def get_stock_by_name (self, name: str) -> Optional[StockBasic]:
		"""根据股票名称获取股票"""
		return await self.basic_repo.get_one(StockBasic.name == name)

	async def search_stocks (
			self,
			keyword: str,
			market: Optional[str] = None,
			list_status: str = 'L',
			limit: int = 50
	) -> List[StockBasic]:
		"""搜索股票"""
		filters = [
			StockBasic.list_status == list_status,
			or_(
				StockBasic.ts_code.like(f"%{keyword}%"),
				StockBasic.symbol.like(f"%{keyword}%"),
				StockBasic.name.like(f"%{keyword}%")
			)
		]

		if market:
			filters.append(StockBasic.market == market)

		return await self.basic_repo.get_many(
			*filters,
			limit=limit,
			order_by=StockBasic.ts_code.asc()
		)

	async def get_stocks_by_industry (
			self,
			industry: str,
			list_status: str = 'L'
	) -> List[StockBasic]:
		"""根据行业获取股票"""
		return await self.basic_repo.get_many(
			and_(
				StockBasic.industry == industry,
				StockBasic.list_status == list_status
			),
			order_by=StockBasic.ts_code.asc()
		)

	async def get_stocks_by_market (
			self,
			market: str,
			list_status: str = 'L'
	) -> List[StockBasic]:
		"""根据市场获取股票"""
		return await self.basic_repo.get_many(
			and_(
				StockBasic.market == market,
				StockBasic.list_status == list_status
			),
			order_by=StockBasic.ts_code.asc()
		)

	async def get_active_stocks (self) -> List[StockBasic]:
		"""获取所有上市状态的股票"""
		return await self.basic_repo.get_many(
			StockBasic.list_status == 'L',
			order_by=StockBasic.ts_code.asc()
		)

	async def get_stocks_by_list_date_range (
			self,
			start_date: date,
			end_date: date
	) -> List[StockBasic]:
		"""根据上市日期范围获取股票"""
		return await self.basic_repo.get_many(
			and_(
				StockBasic.list_date >= start_date,
				StockBasic.list_date <= end_date,
				StockBasic.list_status == 'L'
			),
			order_by=StockBasic.list_date.desc()
		)

	async def get_newly_listed_stocks (self, days: int = 30) -> List[StockBasic]:
		"""获取最近上市的新股"""
		cutoff_date = datetime.now().date() - timedelta(days=days)

		return await self.basic_repo.get_many(
			and_(
				StockBasic.list_date >= cutoff_date,
				StockBasic.list_status == 'L'
			),
			order_by=StockBasic.list_date.desc()
		)

	async def get_delisted_stocks (self) -> List[StockBasic]:
		"""获取已退市股票"""
		return await self.basic_repo.get_many(
			StockBasic.list_status == 'D',
			order_by=StockBasic.delist_date.desc()
		)

	# ==================== 公司信息查询 ====================

	async def get_stock_company (self, ts_code: str) -> Optional[StockCompany]:
		"""获取公司信息"""
		return await self.company_repo.get_one(StockCompany.ts_code == ts_code)

	async def get_stock_with_company (self, ts_code: str) -> Optional[Dict[str, Any]]:
		"""获取股票及其公司信息"""
		stock = await self.get_stock_basic(ts_code)
		if not stock:
			return None

		company = await self.get_stock_company(ts_code)

		return {
			'stock': stock,
			'company': company
		}

	async def get_companies_by_province (self, province: str) -> List[StockCompany]:
		"""根据省份获取公司"""
		return await self.company_repo.get_many(
			StockCompany.province == province,
			order_by=StockCompany.ts_code.asc()
		)

	async def get_companies_by_industry (self, industry: str) -> List[StockBasic]:
		"""根据行业获取公司（通过股票表关联）"""
		return await self.basic_repo.get_many(
			and_(
				StockBasic.industry == industry,
				StockBasic.list_status == 'L'
			),
			order_by=StockBasic.ts_code.asc()
		)

	# ==================== 股票统计信息 ====================

	async def get_industry_distribution (self) -> Dict[str, int]:
		"""获取行业分布"""
		result = await self.session.execute(
			select(
				StockBasic.industry,
				func.count(StockBasic.ts_code).label('count')
			).where(
				StockBasic.list_status == 'L'
			).group_by(
				StockBasic.industry
			).order_by(
				func.count(StockBasic.ts_code).desc()
			)
		)

		return {row[0]: row[1] for row in result.all() if row[0]}

	async def get_market_distribution (self) -> Dict[str, int]:
		"""获取市场分布"""
		result = await self.session.execute(
			select(
				StockBasic.market,
				func.count(StockBasic.ts_code).label('count')
			).where(
				StockBasic.list_status == 'L'
			).group_by(
				StockBasic.market
			).order_by(
				func.count(StockBasic.ts_code).desc()
			)
		)

		return {row[0]: row[1] for row in result.all() if row[0]}

	async def get_area_distribution (self) -> Dict[str, int]:
		"""获取地区分布"""
		result = await self.session.execute(
			select(
				StockBasic.area,
				func.count(StockBasic.ts_code).label('count')
			).where(
				and_(
					StockBasic.list_status == 'L',
					StockBasic.area.isnot(None)
				)
			).group_by(
				StockBasic.area
			).order_by(
				func.count(StockBasic.ts_code).desc()
			)
		)

		return {row[0]: row[1] for row in result.all() if row[0]}

	async def get_list_date_statistics (self) -> Dict[str, Any]:
		"""获取上市日期统计"""
		# 最早上市日期
		result = await self.session.execute(
			select(func.min(StockBasic.list_date))
		)
		min_date = result.scalar()

		# 最晚上市日期
		result = await self.session.execute(
			select(func.max(StockBasic.list_date))
		)
		max_date = result.scalar()

		# 每年上市数量
		result = await self.session.execute(
			select(
				func.extract('year', StockBasic.list_date).label('year'),
				func.count(StockBasic.ts_code).label('count')
			).where(
				StockBasic.list_status == 'L'
			).group_by(
				func.extract('year', StockBasic.list_date)
			).order_by(
				func.extract('year', StockBasic.list_date).desc()
			)
		)

		yearly_stats = {}
		for row in result.all():
			if row.year:
				yearly_stats[int(row.year)] = row.count

		return {
			'min_date': min_date,
			'max_date': max_date,
			'yearly_stats': yearly_stats
		}

	async def get_stock_count_summary (self) -> Dict[str, Any]:
		"""获取股票数量摘要"""
		# 总股票数
		total_count = await self.basic_repo.count()

		# 上市股票数
		listed_count = await self.basic_repo.count(StockBasic.list_status == 'L')

		# 退市股票数
		delisted_count = await self.basic_repo.count(StockBasic.list_status == 'D')

		# 暂停上市股票数
		suspended_count = await self.basic_repo.count(StockBasic.list_status == 'P')

		# 沪深港通股票数
		sh_count = await self.basic_repo.count(
			and_(
				StockBasic.list_status == 'L',
				StockBasic.is_hs == 'S'
			)
		)

		sz_count = await self.basic_repo.count(
			and_(
				StockBasic.list_status == 'L',
				StockBasic.is_hs == 'N'
			)
		)

		return {
			'total_count': total_count,
			'listed_count': listed_count,
			'delisted_count': delisted_count,
			'suspended_count': suspended_count,
			'sh_hsgt_count': sh_count,
			'sz_hsgt_count': sz_count,
			'listed_percentage': listed_count / total_count * 100 if total_count > 0 else 0
		}

	# ==================== 基本面数据查询 ====================

	async def get_stock_daily_basic (
			self,
			ts_code: str,
			trade_date: date
	) -> Optional[StockDailyBasic]:
		"""获取股票每日基本面数据"""
		return await self.daily_basic_repo.get_one(
			and_(
				StockDailyBasic.ts_code == ts_code,
				StockDailyBasic.trade_date == trade_date
			)
		)

	async def get_latest_daily_basic (
			self,
			ts_code: str,
			before_date: Optional[date] = None
	) -> Optional[StockDailyBasic]:
		"""获取最新基本面数据"""
		query = select(StockDailyBasic).where(
			StockDailyBasic.ts_code == ts_code
		)

		if before_date:
			query = query.where(StockDailyBasic.trade_date <= before_date)

		query = query.order_by(StockDailyBasic.trade_date.desc()).limit(1)

		result = await self.session.execute(query)
		return result.scalar_one_or_none()

	async def get_daily_basic_range (
			self,
			ts_code: str,
			start_date: date,
			end_date: date,
			ascending: bool = True
	) -> List[StockDailyBasic]:
		"""获取基本面数据时间序列"""
		query = select(StockDailyBasic).where(
			and_(
				StockDailyBasic.ts_code == ts_code,
				StockDailyBasic.trade_date >= start_date,
				StockDailyBasic.trade_date <= end_date
			)
		)

		if ascending:
			query = query.order_by(StockDailyBasic.trade_date.asc())
		else:
			query = query.order_by(StockDailyBasic.trade_date.desc())

		result = await self.session.execute(query)
		return result.scalars().all()

	async def get_stocks_by_valuation (
			self,
			trade_date: date,
			metric: str = 'pe',  # 'pe', 'pb', 'ps', 'dv_ratio'
			min_value: Optional[float] = None,
			max_value: Optional[float] = None,
			limit: int = 100
	) -> List[Dict[str, Any]]:
		"""根据估值指标筛选股票"""
		query = select(
			StockDailyBasic.ts_code,
			StockDailyBasic.close,
			getattr(StockDailyBasic, metric)
		).where(
			and_(
				StockDailyBasic.trade_date == trade_date,
				getattr(StockDailyBasic, metric).isnot(None)
			)
		)

		if metric == 'pe':
			query = query.where(StockDailyBasic.pe.isnot(None))
		elif metric == 'pb':
			query = query.where(StockDailyBasic.pb.isnot(None))
		elif metric == 'ps':
			query = query.where(StockDailyBasic.ps.isnot(None))
		elif metric == 'dv_ratio':
			query = query.where(StockDailyBasic.dv_ratio.isnot(None))

		if min_value is not None:
			query = query.where(getattr(StockDailyBasic, metric) >= min_value)

		if max_value is not None:
			query = query.where(getattr(StockDailyBasic, metric) <= max_value)

		# 排序
		if metric in ['pe', 'pb', 'ps']:
			query = query.order_by(getattr(StockDailyBasic, metric).asc())  # 估值越低越好
		else:
			query = query.order_by(getattr(StockDailyBasic, metric).desc())  # 股息率越高越好

		query = query.limit(limit)

		result = await self.session.execute(query)
		rows = result.all()

		return [
			{
				'ts_code': row[0],
				'close': float(row[1]) if row[1] else 0,
				metric: float(row[2]) if row[2] else None
			}
			for row in rows
		]

	async def get_stocks_by_market_cap (
			self,
			trade_date: date,
			min_cap: Optional[float] = None,
			max_cap: Optional[float] = None,
			order_desc: bool = True,
			limit: int = 100
	) -> List[Dict[str, Any]]:
		"""根据市值筛选股票"""
		query = select(
			StockDailyBasic.ts_code,
			StockDailyBasic.close,
			StockDailyBasic.total_mv,
			StockDailyBasic.circ_mv
		).where(
			StockDailyBasic.trade_date == trade_date
		)

		if min_cap is not None:
			query = query.where(StockDailyBasic.total_mv >= min_cap)

		if max_cap is not None:
			query = query.where(StockDailyBasic.total_mv <= max_cap)

		# 排序
		if order_desc:
			query = query.order_by(StockDailyBasic.total_mv.desc())
		else:
			query = query.order_by(StockDailyBasic.total_mv.asc())

		query = query.limit(limit)

		result = await self.session.execute(query)
		rows = result.all()

		return [
			{
				'ts_code': row[0],
				'close': float(row[1]) if row[1] else 0,
				'total_mv': float(row[2]) if row[2] else 0,
				'circ_mv': float(row[3]) if row[3] else 0
			}
			for row in rows
		]

	# ==================== ST股票查询 ====================

	async def get_st_stock_status (self, ts_code: str) -> Optional[StockSTList]:
		"""获取股票ST状态"""
		return await self.st_list_repo.get_one(
			StockSTList.ts_code == ts_code
		)

	async def get_current_st_stocks (self) -> List[StockSTList]:
		"""获取当前ST股票"""
		return await self.st_list_repo.get_many(
			StockSTList.is_st == 1,
			order_by=StockSTList.ts_code.asc()
		)

	async def is_st_stock (self, ts_code: str) -> bool:
		"""判断是否为ST股票"""
		st_status = await self.get_st_stock_status(ts_code)
		return st_status is not None and st_status.is_st == 1

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

	async def get_adj_factors_range (
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

	# ==================== 批量操作 ====================

	async def batch_get_stocks (self, ts_codes: List[str]) -> List[StockBasic]:
		"""批量获取股票信息"""
		if not ts_codes:
			return []

		result = await self.session.execute(
			select(StockBasic).where(
				StockBasic.ts_code.in_(ts_codes)
			).order_by(StockBasic.ts_code)
		)

		return result.scalars().all()

	async def batch_create_stocks (
			self,
			stocks_data: List[Dict[str, Any]]
	) -> List[StockBasic]:
		"""批量创建股票记录"""
		return await self.basic_repo.batch_create(stocks_data)

	async def batch_upsert_stocks (
			self,
			stocks_data: List[Dict[str, Any]],
			match_fields: List[str] = ['ts_code']
	) -> List[StockBasic]:
		"""批量插入或更新股票记录"""
		return await self.basic_repo.batch_upsert(stocks_data, match_fields)

	async def batch_create_companies (
			self,
			companies_data: List[Dict[str, Any]]
	) -> List[StockCompany]:
		"""批量创建公司记录"""
		return await self.company_repo.batch_create(companies_data)

	async def batch_create_daily_basics (
			self,
			basics_data: List[Dict[str, Any]]
	) -> List[StockDailyBasic]:
		"""批量创建基本面记录"""
		return await self.daily_basic_repo.batch_create(basics_data)

	# ==================== 高级查询 ====================

	async def get_stock_full_info (
			self,
			ts_code: str,
			trade_date: Optional[date] = None
	) -> Dict[str, Any]:
		"""获取股票完整信息"""
		stock = await self.get_stock_basic(ts_code)
		if not stock:
			return {}

		result = {'stock': stock}

		# 公司信息
		company = await self.get_stock_company(ts_code)
		if company:
			result['company'] = company

		# 最新基本面数据
		if trade_date:
			daily_basic = await self.get_stock_daily_basic(ts_code, trade_date)
		else:
			daily_basic = await self.get_latest_daily_basic(ts_code)

		if daily_basic:
			result['daily_basic'] = daily_basic

		# ST状态
		st_status = await self.get_st_stock_status(ts_code)
		if st_status:
			result['st_status'] = st_status

		return result

	async def get_stocks_with_conditions (
			self,
			conditions: Dict[str, Any],
			page: int = 1,
			page_size: int = 20
	) -> Tuple[List[Dict[str, Any]], int]:
		"""根据复杂条件筛选股票"""
		# 构建基础查询
		query = select(
			StockBasic.ts_code,
			StockBasic.name,
			StockBasic.industry,
			StockBasic.market,
			StockDailyBasic.close,
			StockDailyBasic.pe,
			StockDailyBasic.pb,
			StockDailyBasic.total_mv
		).join(
			StockDailyBasic,
			StockBasic.ts_code == StockDailyBasic.ts_code
		).where(
			and_(
				StockBasic.list_status == 'L',
				StockDailyBasic.trade_date == conditions.get('trade_date')
			)
		)

		# 应用筛选条件
		filters = []

		if 'industry' in conditions and conditions['industry']:
			filters.append(StockBasic.industry == conditions['industry'])

		if 'market' in conditions and conditions['market']:
			filters.append(StockBasic.market == conditions['market'])

		if 'min_pe' in conditions and conditions['min_pe'] is not None:
			filters.append(StockDailyBasic.pe >= conditions['min_pe'])

		if 'max_pe' in conditions and conditions['max_pe'] is not None:
			filters.append(StockDailyBasic.pe <= conditions['max_pe'])

		if 'min_pb' in conditions and conditions['min_pb'] is not None:
			filters.append(StockDailyBasic.pb >= conditions['min_pb'])

		if 'max_pb' in conditions and conditions['max_pb'] is not None:
			filters.append(StockDailyBasic.pb <= conditions['max_pb'])

		if 'min_market_cap' in conditions and conditions['min_market_cap'] is not None:
			filters.append(StockDailyBasic.total_mv >= conditions['min_market_cap'])

		if 'max_market_cap' in conditions and conditions['max_market_cap'] is not None:
			filters.append(StockDailyBasic.total_mv <= conditions['max_market_cap'])

		if filters:
			query = query.where(and_(*filters))

		# 计数查询
		count_query = select(func.count()).select_from(query.subquery())
		count_result = await self.session.execute(count_query)
		total = count_result.scalar() or 0

		# 分页
		query = query.offset((page - 1) * page_size).limit(page_size)

		# 排序
		sort_by = conditions.get('sort_by', 'total_mv')
		sort_desc = conditions.get('sort_desc', True)

		if hasattr(StockDailyBasic, sort_by):
			sort_column = getattr(StockDailyBasic, sort_by)
			if sort_desc:
				query = query.order_by(sort_column.desc())
			else:
				query = query.order_by(sort_column.asc())
		else:
			query = query.order_by(StockDailyBasic.total_mv.desc())

		# 执行查询
		result = await self.session.execute(query)
		rows = result.all()

		stocks = []
		for row in rows:
			stock = {
				'ts_code': row[0],
				'name': row[1],
				'industry': row[2],
				'market': row[3],
				'close': float(row[4]) if row[4] else 0,
				'pe': float(row[5]) if row[5] else None,
				'pb': float(row[6]) if row[6] else None,
				'total_mv': float(row[7]) if row[7] else 0
			}
			stocks.append(stock)

		return stocks, total

	async def get_stock_summary (self) -> Dict[str, Any]:
		"""获取股票数据摘要"""
		# 基础统计
		basic_stats = await self.get_stock_count_summary()

		# 行业分布
		industry_dist = await self.get_industry_distribution()

		# 市场分布
		market_dist = await self.get_market_distribution()

		# 最新数据日期
		latest_date = await self.session.execute(
			select(func.max(StockDailyBasic.trade_date))
		)
		latest_date_value = latest_date.scalar()

		# ST股票统计
		st_stocks = await self.get_current_st_stocks()

		return {
			'basic_stats': basic_stats,
			'industry_distribution': industry_dist,
			'market_distribution': market_dist,
			'latest_data_date': latest_date_value,
			'st_stock_count': len(st_stocks),
			'st_stocks': [st.ts_code for st in st_stocks[:20]],  # 只显示前20个
			'total_industries': len(industry_dist),
			'total_markets': len(market_dist)
		}