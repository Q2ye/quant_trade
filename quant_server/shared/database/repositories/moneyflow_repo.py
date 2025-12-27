# -*- coding: utf-8 -*-
"""
资金流数据仓库
提供股票资金流数据的统一访问接口
位置：shared/database/repositories/moneyflow_repo.py
"""

from typing import List, Optional, Dict, Any
from datetime import date, datetime, timedelta
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, and_, or_, func, desc, between
from sqlalchemy.sql import case

from .base import BaseRepository
from quant_server.shared.database.models.data_models import StockMoneyflow


class MoneyflowRepository:
	"""资金流数据Repository - 纯数据访问"""

	def __init__ (self, session: AsyncSession):
		self.session = session
		self.base_repo = BaseRepository(session, StockMoneyflow)

	# ==================== 基础CRUD操作 ====================

	async def create (self, data: Dict[str, Any]) -> StockMoneyflow:
		"""创建资金流记录"""
		return await self.base_repo.create(data)

	async def get (self, id: int) -> Optional[StockMoneyflow]:
		"""根据ID获取资金流记录"""
		return await self.base_repo.get(id)

	async def update (self, id: int, data: Dict[str, Any]) -> Optional[StockMoneyflow]:
		"""更新资金流记录"""
		return await self.base_repo.update(id, data)

	async def delete (self, id: int, soft: bool = True) -> bool:
		"""删除资金流记录"""
		return await self.base_repo.delete(id, soft)

	async def get_one (self, *filters) -> Optional[StockMoneyflow]:
		"""根据条件获取单个资金流记录"""
		return await self.base_repo.get_one(*filters)

	async def get_many (
			self,
			*filters,
			skip: int = 0,
			limit: int = 100,
			order_by: str = None
	) -> List[StockMoneyflow]:
		"""根据条件获取多个资金流记录"""
		return await self.base_repo.get_many(*filters, skip=skip, limit=limit, order_by=order_by)

	async def count (self, *filters) -> int:
		"""统计资金流记录数"""
		return await self.base_repo.count(*filters)

	# ==================== 业务查询方法 ====================

	async def get_by_ts_code_and_date (
			self,
			ts_code: str,
			trade_date: date
	) -> Optional[StockMoneyflow]:
		"""根据股票代码和交易日期获取资金流数据"""
		return await self.get_one(
			and_(
				StockMoneyflow.ts_code == ts_code,
				StockMoneyflow.trade_date == trade_date
			)
		)

	async def get_by_ts_code (
			self,
			ts_code: str,
			start_date: Optional[date] = None,
			end_date: Optional[date] = None,
			limit: int = 100
	) -> List[StockMoneyflow]:
		"""根据股票代码获取资金流数据"""
		filters = [StockMoneyflow.ts_code == ts_code]

		if start_date:
			filters.append(StockMoneyflow.trade_date >= start_date)
		if end_date:
			filters.append(StockMoneyflow.trade_date <= end_date)

		return await self.get_many(
			*filters,
			limit=limit,
			order_by=StockMoneyflow.trade_date.desc()
		)

	async def get_by_trade_date (
			self,
			trade_date: date,
			ts_codes: Optional[List[str]] = None,
			limit: int = 1000
	) -> List[StockMoneyflow]:
		"""根据交易日期获取资金流数据"""
		filters = [StockMoneyflow.trade_date == trade_date]

		if ts_codes:
			filters.append(StockMoneyflow.ts_code.in_(ts_codes))

		return await self.get_many(*filters, limit=limit, order_by=StockMoneyflow.ts_code)

	async def get_net_inflow_top (
			self,
			trade_date: date,
			top_n: int = 20,
			direction: str = 'buy'  # 'buy' 或 'sell'
	) -> List[Dict[str, Any]]:
		"""获取主力资金净流入/流出排名"""
		net_amount_column = StockMoneyflow.net_mf_amount

		query = select(
			StockMoneyflow.ts_code,
			StockMoneyflow.net_mf_amount,
			StockMoneyflow.buy_lg_amount,
			StockMoneyflow.sell_lg_amount,
			StockMoneyflow.net_mf_vol,
			StockMoneyflow.large_net_ratio
		).where(
			and_(
				StockMoneyflow.trade_date == trade_date,
				net_amount_column != 0  # 排除净流入为0的
			)
		)

		if direction == 'buy':
			query = query.where(net_amount_column > 0)
			query = query.order_by(net_amount_column.desc())
		else:
			query = query.where(net_amount_column < 0)
			query = query.order_by(net_amount_column.asc())

		query = query.limit(top_n)

		result = await self.session.execute(query)
		rows = result.all()

		return [
			{
				'ts_code': row[0],
				'net_mf_amount': float(row[1]) if row[1] else 0,
				'buy_lg_amount': float(row[2]) if row[2] else 0,
				'sell_lg_amount': float(row[3]) if row[3] else 0,
				'net_mf_vol': row[4] if row[4] else 0,
				'large_net_ratio': float(row[5]) if row[5] else 0
			}
			for row in rows
		]

	async def get_large_net_ratio_top (
			self,
			trade_date: date,
			top_n: int = 20
	) -> List[Dict[str, Any]]:
		"""获取大单净占比排名"""
		query = select(
			StockMoneyflow.ts_code,
			StockMoneyflow.large_net_ratio,
			StockMoneyflow.buy_lg_amount,
			StockMoneyflow.sell_lg_amount,
			StockMoneyflow.net_mf_amount
		).where(
			and_(
				StockMoneyflow.trade_date == trade_date,
				StockMoneyflow.large_net_ratio.isnot(None)
			)
		).order_by(
			StockMoneyflow.large_net_ratio.desc()
		).limit(top_n)

		result = await self.session.execute(query)
		rows = result.all()

		return [
			{
				'ts_code': row[0],
				'large_net_ratio': float(row[1]) if row[1] else 0,
				'buy_lg_amount': float(row[2]) if row[2] else 0,
				'sell_lg_amount': float(row[3]) if row[3] else 0,
				'net_mf_amount': float(row[4]) if row[4] else 0
			}
			for row in rows
		]

	async def get_moneyflow_summary (
			self,
			trade_date: date
	) -> Dict[str, Any]:
		"""获取资金流汇总统计"""
		# 统计主力资金净流入总额
		total_net_inflow = await self.session.execute(
			select(func.sum(StockMoneyflow.net_mf_amount)).where(
				and_(
					StockMoneyflow.trade_date == trade_date,
					StockMoneyflow.net_mf_amount.isnot(None)
				)
			)
		)
		total_net_inflow_value = total_net_inflow.scalar() or 0

		# 统计净流入股票数
		inflow_count = await self.session.execute(
			select(func.count()).where(
				and_(
					StockMoneyflow.trade_date == trade_date,
					StockMoneyflow.net_mf_amount > 0
				)
			)
		)
		inflow_count_value = inflow_count.scalar() or 0

		# 统计净流出股票数
		outflow_count = await self.session.execute(
			select(func.count()).where(
				and_(
					StockMoneyflow.trade_date == trade_date,
					StockMoneyflow.net_mf_amount < 0
				)
			)
		)
		outflow_count_value = outflow_count.scalar() or 0

		# 统计大单净占比大于5%的股票数
		large_ratio_count = await self.session.execute(
			select(func.count()).where(
				and_(
					StockMoneyflow.trade_date == trade_date,
					StockMoneyflow.large_net_ratio > 5.0
				)
			)
		)
		large_ratio_count_value = large_ratio_count.scalar() or 0

		return {
			'trade_date': trade_date,
			'total_net_inflow': float(total_net_inflow_value),
			'inflow_count': inflow_count_value,
			'outflow_count': outflow_count_value,
			'large_ratio_count': large_ratio_count_value,
			'total_count': inflow_count_value + outflow_count_value
		}

	async def get_moneyflow_trend (
			self,
			ts_code: str,
			days: int = 20
	) -> List[Dict[str, Any]]:
		"""获取资金流趋势"""
		end_date = datetime.now().date()
		start_date = end_date - timedelta(days=days - 1)

		query = select(
			StockMoneyflow.trade_date,
			StockMoneyflow.net_mf_amount,
			StockMoneyflow.buy_lg_amount,
			StockMoneyflow.sell_lg_amount,
			StockMoneyflow.large_net_ratio
		).where(
			and_(
				StockMoneyflow.ts_code == ts_code,
				StockMoneyflow.trade_date >= start_date,
				StockMoneyflow.trade_date <= end_date
			)
		).order_by(
			StockMoneyflow.trade_date.asc()
		)

		result = await self.session.execute(query)
		rows = result.all()

		return [
			{
				'trade_date': row[0],
				'net_mf_amount': float(row[1]) if row[1] else 0,
				'buy_lg_amount': float(row[2]) if row[2] else 0,
				'sell_lg_amount': float(row[3]) if row[3] else 0,
				'large_net_ratio': float(row[4]) if row[4] else 0
			}
			for row in rows
		]

	async def get_institutional_flow (
			self,
			trade_date: date,
			flow_type: str = 'all'  # 'all', 'buy', 'sell'
	) -> Dict[str, float]:
		"""获取机构资金流向统计"""
		if flow_type == 'buy':
			# 买入金额统计
			query = select(
				func.sum(StockMoneyflow.buy_lg_amount + StockMoneyflow.buy_elg_amount)
			).where(
				StockMoneyflow.trade_date == trade_date
			)
		elif flow_type == 'sell':
			# 卖出金额统计
			query = select(
				func.sum(StockMoneyflow.sell_lg_amount + StockMoneyflow.sell_elg_amount)
			).where(
				StockMoneyflow.trade_date == trade_date
			)
		else:
			# 净流入统计
			query = select(
				func.sum(
					StockMoneyflow.buy_lg_amount +
					StockMoneyflow.buy_elg_amount -
					StockMoneyflow.sell_lg_amount -
					StockMoneyflow.sell_elg_amount
				)
			).where(
				StockMoneyflow.trade_date == trade_date
			)

		result = await self.session.execute(query)
		total = result.scalar() or 0

		return {
			'trade_date': trade_date,
			'flow_type': flow_type,
			'total_amount': float(total)
		}

	async def batch_create (
			self,
			data_list: List[Dict[str, Any]]
	) -> List[StockMoneyflow]:
		"""批量创建资金流记录"""
		return await self.base_repo.batch_create(data_list)

	async def batch_upsert (
			self,
			data_list: List[Dict[str, Any]],
			match_fields: List[str] = ['ts_code', 'trade_date']
	) -> List[StockMoneyflow]:
		"""批量插入或更新资金流记录"""
		return await self.base_repo.batch_upsert(data_list, match_fields)

	async def get_date_range (
			self,
			ts_code: Optional[str] = None
	) -> Dict[str, Optional[date]]:
		"""获取数据日期范围"""
		query = select(
			func.min(StockMoneyflow.trade_date),
			func.max(StockMoneyflow.trade_date)
		)

		if ts_code:
			query = query.where(StockMoneyflow.ts_code == ts_code)

		result = await self.session.execute(query)
		min_date, max_date = result.first()

		return {
			'min_date': min_date,
			'max_date': max_date
		}