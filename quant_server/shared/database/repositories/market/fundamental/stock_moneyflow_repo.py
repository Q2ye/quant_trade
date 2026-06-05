# -*- coding: utf-8 -*-
"""
资金流数据仓库（时序数据）
继承HyperRepositoryBase，针对时序数据优化
位置：quant_server/shared/database/repositories/market/fundamental/stock_moneyflow_repo.py
"""

from datetime import date, datetime, timedelta
from typing import List, Optional, Dict, Any

from sqlalchemy import select, and_, func
from sqlalchemy.ext.asyncio import AsyncSession

from shared.database.models.data_models import StockMoneyflow
from shared.database.repositories.base.hyper_repository_base import HyperRepositoryBase


class StockMoneyflowRepository(HyperRepositoryBase[StockMoneyflow]):
	"""资金流数据Repository - 继承HyperRepositoryBase，时序数据专用"""

	def __init__ (self, session: AsyncSession):
		"""初始化资金流数据仓库"""
		super().__init__(session, StockMoneyflow)
		self.time_column = "trade_date"  # 指定时间列名

	# ==================== 时序数据专用方法 ====================

	async def get_by_time_range (
			self,
			start_date: datetime,
			end_date: datetime,
			ts_code: Optional[str] = None,
			limit: int = 1000
	) -> List[StockMoneyflow]:
		"""
		根据时间范围查询资金流数据

		Args:
			start_date: 开始日期
			end_date: 结束日期
			ts_code: 股票代码（可选）
			limit: 限制记录数

		Returns:
			资金流数据列表
		"""
		return await super().get_by_time_range(
			start_time=start_date,
			end_time=end_date,
			symbol=ts_code,
			limit=limit
		)

	async def get_latest_record (
			self,
			ts_code: Optional[str] = None,
			limit: int = 1
	) -> Optional[StockMoneyflow]:
		"""
		获取最新资金流数据

		Args:
			ts_code: 股票代码（可选）
			limit: 限制记录数

		Returns:
			最新资金流数据
		"""
		return await super().get_latest_record(symbol=ts_code, limit=limit)

	async def batch_insert (
			self,
			records: List[Dict[str, Any]],
			conflict_strategy: str = "upsert"
	) -> int:
		"""
		批量插入资金流数据

		Args:
			records: 记录列表
			conflict_strategy: 冲突处理策略

		Returns:
			插入的记录数
		"""
		return await super().batch_insert(records, conflict_strategy)

	async def get_latest_trade_date (self, ts_code: str) -> Optional[date]:
		"""获取指定股票最新资金流交易日（用于 _resolve_sync_date_range 智能推断）"""
		latest = await self.get_latest_record(ts_code=ts_code)
		return latest.trade_date if latest else None

	async def get_latest_trade_dates_batch(
			self,
			ts_codes: list
	) -> dict:
		"""
		批量获取多只股票的最新交易日期（一次 SQL 查询）。

		Args:
			ts_codes: 股票 TS 代码列表

		Returns:
			Dict[str, Optional[date]]: ``{ts_code: latest_date}``
		"""
		from typing import Dict, Optional as Opt
		from datetime import date as d
		from sqlalchemy import func

		if not ts_codes:
			return {}

		query = (
			select(self.model.ts_code, func.max(self.model.trade_date))
			.where(self.model.ts_code.in_(ts_codes))
			.group_by(self.model.ts_code)
		)
		result = await self.session.execute(query)
		mapping: Dict[str, Opt[d]] = {row[0]: row[1] for row in result.fetchall()}
		for code in ts_codes:
			if code not in mapping:
				mapping[code] = None
		return mapping

	# ==================== 业务查询方法 ====================

	async def get_by_ts_code_and_date (
				self,
				ts_code: str,
				trade_date: date
			) -> Optional[StockMoneyflow]:
		"""
		根据股票代码和交易日期获取资金流数据

		Args:
			ts_code: 股票代码
			trade_date: 交易日期

		Returns:
			资金流数据或None
		"""
		results = await self.get_many(
			ts_code=ts_code,
			trade_date=trade_date,
			limit=1
		)
		return results[0] if results else None

	async def get_by_ts_code (
			self,
			ts_code: str,
			start_date: Optional[date] = None,
			end_date: Optional[date] = None,
			limit: int = 100
	) -> List[StockMoneyflow]:
		"""
		根据股票代码获取资金流数据

		Args:
			ts_code: 股票代码
			start_date: 开始日期
			end_date: 结束日期
			limit: 限制记录数

		Returns:
			资金流数据列表
		"""
		filters = {"ts_code": ts_code}

		if start_date or end_date:
			# 使用时间范围查询
			end_date = end_date or datetime.now().date()
			start_date = start_date or (end_date - timedelta(days=365))
			# 转换为datetime类型
			start_datetime = datetime.combine(start_date, datetime.min.time())
			end_datetime = datetime.combine(end_date, datetime.max.time())
			return await self.get_by_time_range(start_datetime, end_datetime, ts_code, limit)

		return await self.get_many(limit=limit, **filters)

	async def get_by_trade_date (
			self,
			trade_date: date,
			ts_codes: Optional[List[str]] = None,
			limit: int = 1000
	) -> List[StockMoneyflow]:
		"""
		根据交易日期获取资金流数据

		Args:
			trade_date: 交易日期
			ts_codes: 股票代码列表（可选）
			limit: 限制记录数

		Returns:
			资金流数据列表
		"""
		filters = {"trade_date": trade_date}

		if ts_codes:
			return await self.get_many(limit=limit, trade_date=trade_date, ts_code=ts_codes)

		return await self.get_many(limit=limit, **filters)

	async def get_net_inflow_top (
			self,
			trade_date: date,
			top_n: int = 20,
			direction: str = 'buy'  # 'buy' 或 'sell'
	) -> List[Dict[str, Any]]:
		"""
		获取主力资金净流入/流出排名

		Args:
			trade_date: 交易日期
			top_n: 排名数量
			direction: 方向（buy/sell）

		Returns:
			排名结果列表
		"""
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
		"""
		获取大单净占比排名

		Args:
			trade_date: 交易日期
			top_n: 排名数量

		Returns:
			排名结果列表
		"""
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
		"""
		获取资金流汇总统计

		Args:
			trade_date: 交易日期

		Returns:
			汇总统计字典
		"""
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
			) -> List[StockMoneyflow]:
		"""
		获取资金流趋势

		Args:
			ts_code: 股票代码
			days: 天数

		Returns:
			资金流趋势列表
		"""
		end_date = datetime.now().date()
		start_date = end_date - timedelta(days=days - 1)
		# 转换为datetime类型
		start_datetime = datetime.combine(start_date, datetime.min.time())
		end_datetime = datetime.combine(end_date, datetime.max.time())

		return await self.get_by_time_range(start_datetime, end_datetime, ts_code, days)

	async def get_institutional_flow (
				self,
				trade_date: datetime,
				flow_type: str = 'all'  # 'all', 'buy', 'sell'
			) -> Dict[str, Any]:
		"""
		获取机构资金流向统计

		Args:
			trade_date: 交易日期
			flow_type: 流向类型

		Returns:
			机构资金流向统计
		"""
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

	async def batch_upsert (
				self,
				match_fields: List[str],
				data_list: List[Dict[str, Any]],
				update_fields: List[str] = None
			) -> List[StockMoneyflow]:
		"""
		批量插入或更新资金流记录

		Args:
			match_fields: 匹配字段
			data_list: 数据列表
			update_fields: 更新字段

		Returns:
			更新后的记录列表
		"""
		return await super().batch_upsert(
			match_fields=match_fields,
			data_list=data_list,
			update_fields=update_fields
		)

	async def get_date_range (
			self,
			ts_code: Optional[str] = None
	) -> Dict[str, Optional[date]]:
		"""
		获取数据日期范围

		Args:
			ts_code: 股票代码（可选）

		Returns:
			日期范围字典
		"""
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