# -*- coding: utf-8 -*-
"""
ETF数据仓库
位置：quant_server/shared/database/repositories/etf_repo.py
职责：管理ETF基础信息、持仓、行情等数据访问
注意：已存在部分实现，这里提供完整版本
"""

from typing import List, Optional, Dict, Any, Tuple
from datetime import datetime, date
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, and_, or_, func, desc, text
from sqlalchemy.orm import selectinload, joinedload

from quant_server.shared.database.repositories.base import BaseRepository
from quant_server.shared.database.models.data_models import (
	EtfBasic,
	EtfIndex,
	EtfDaily,
	EtfMinute,
	FundAdjFactor
)


class ETFRepository:
	"""ETF数据仓库 - 负责ETF相关数据访问"""

	def __init__ (self, session: AsyncSession):
		self.session = session
		self.etf_basic_repo = BaseRepository[EtfBasic](session, EtfBasic)
		self.etf_index_repo = BaseRepository[EtfIndex](session, EtfIndex)
		self.etf_daily_repo = BaseRepository[EtfDaily](session, EtfDaily)
		self.etf_minute_repo = BaseRepository[EtfMinute](session, EtfMinute)
		self.adj_factor_repo = BaseRepository[FundAdjFactor](session, FundAdjFactor)

	# ==================== ETF基础信息操作 ====================

	async def get_etf_basic (self, ts_code: str) -> Optional[EtfBasic]:
		"""
		获取ETF基础信息

		Args:
			ts_code: ETF代码

		Returns:
			ETF基础信息或None
		"""
		return await self.etf_basic_repo.get_by(ts_code=ts_code)

	async def get_etf_by_fund_type (self, fund_type: str) -> List[EtfBasic]:
		"""
		根据基金类型获取ETF

		Args:
			fund_type: 基金类型

		Returns:
			ETF列表
		"""
		return await self.etf_basic_repo.get_many(etf_type=fund_type)

	async def get_etf_by_exchange (self, exchange: str) -> List[EtfBasic]:
		"""
		根据交易所获取ETF

		Args:
			exchange: 交易所代码

		Returns:
			ETF列表
		"""
		return await self.etf_basic_repo.get_many(exchange=exchange)

	async def search_etfs (
			self,
			keyword: str,
			limit: int = 100,
			skip: int = 0
	) -> List[EtfBasic]:
		"""
		搜索ETF

		Args:
			keyword: 搜索关键词（可匹配代码、名称等）
			limit: 返回数量限制
			skip: 跳过数量

		Returns:
			ETF列表
		"""
		query = select(EtfBasic).where(
			or_(
				EtfBasic.ts_code.like(f"%{keyword}%"),
				EtfBasic.csname.like(f"%{keyword}%"),
				EtfBasic.cname.like(f"%{keyword}%"),
				EtfBasic.extname.like(f"%{keyword}%")
			)
		).order_by(EtfBasic.ts_code).offset(skip).limit(limit)

		result = await self.session.execute(query)
		return result.scalars().all()

	async def get_all_etfs (self, active_only: bool = True) -> List[EtfBasic]:
		"""
		获取所有ETF

		Args:
			active_only: 是否只获取上市状态的ETF

		Returns:
			ETF列表
		"""
		if active_only:
			return await self.etf_basic_repo.get_many(list_status="L")
		else:
			return await self.etf_basic_repo.get_all()

	async def create_etf_basic (self, etf_data: Dict[str, Any]) -> EtfBasic:
		"""
		创建ETF基础信息

		Args:
			etf_data: ETF数据

		Returns:
			创建的ETF信息
		"""
		return await self.etf_basic_repo.create(etf_data)

	async def update_etf_basic (
			self,
			ts_code: str,
			update_data: Dict[str, Any]
	) -> Optional[EtfBasic]:
		"""
		更新ETF基础信息

		Args:
			ts_code: ETF代码
			update_data: 更新数据

		Returns:
			更新后的ETF信息
		"""
		etf = await self.etf_basic_repo.get_by(ts_code=ts_code)
		if not etf:
			return None

		# 由于ts_code是主键，需要使用特殊处理
		return await self.etf_basic_repo.update(etf.ts_code, update_data)

	# ==================== ETF行情数据操作 ====================

	async def get_etf_daily (
			self,
			ts_code: str,
			trade_date: date
	) -> Optional[EtfDaily]:
		"""
		获取ETF日线行情

		Args:
			ts_code: ETF代码
			trade_date: 交易日期

		Returns:
			ETF日线行情或None
		"""
		return await self.etf_daily_repo.get_by(
			ts_code=ts_code,
			trade_date=trade_date
		)

	async def get_etf_daily_in_range (
			self,
			ts_code: str,
			start_date: date,
			end_date: date
	) -> List[EtfDaily]:
		"""
		获取指定时间范围内的ETF日线行情

		Args:
			ts_code: ETF代码
			start_date: 开始日期
			end_date: 结束日期

		Returns:
			ETF日线行情列表
		"""
		query = select(EtfDaily).where(
			and_(
				EtfDaily.ts_code == ts_code,
				EtfDaily.trade_date >= start_date,
				EtfDaily.trade_date <= end_date
			)
		).order_by(EtfDaily.trade_date)

		result = await self.session.execute(query)
		return result.scalars().all()

	async def get_latest_etf_daily (self, ts_code: str) -> Optional[EtfDaily]:
		"""
		获取最新的ETF日线行情

		Args:
			ts_code: ETF代码

		Returns:
			最新的ETF日线行情或None
		"""
		query = select(EtfDaily).where(
			EtfDaily.ts_code == ts_code
		).order_by(desc(EtfDaily.trade_date)).limit(1)

		result = await self.session.execute(query)
		return result.scalar_one_or_none()

	async def get_etf_minute (
			self,
			ts_code: str,
			trade_time: datetime,
			freq: str = "1min"
	) -> Optional[EtfMinute]:
		"""
		获取ETF分钟行情

		Args:
			ts_code: ETF代码
			trade_time: 交易时间
			freq: 频率（1min/5min/15min/30min/60min）

		Returns:
			ETF分钟行情或None
		"""
		query = select(EtfMinute).where(
			and_(
				EtfMinute.ts_code == ts_code,
				EtfMinute.trade_time == trade_time,
				EtfMinute.freq == freq
			)
		)

		result = await self.session.execute(query)
		return result.scalar_one_or_none()

	async def get_etf_minutes_in_range (
			self,
			ts_code: str,
			start_time: datetime,
			end_time: datetime,
			freq: str = "1min"
	) -> List[EtfMinute]:
		"""
		获取指定时间范围内的ETF分钟行情

		Args:
			ts_code: ETF代码
			start_time: 开始时间
			end_time: 结束时间
			freq: 频率

		Returns:
			ETF分钟行情列表
		"""
		query = select(EtfMinute).where(
			and_(
				EtfMinute.ts_code == ts_code,
				EtfMinute.trade_time >= start_time,
				EtfMinute.trade_time <= end_time,
				EtfMinute.freq == freq
			)
		).order_by(EtfMinute.trade_time)

		result = await self.session.execute(query)
		return result.scalars().all()

	async def create_etf_daily (self, daily_data: Dict[str, Any]) -> EtfDaily:
		"""
		创建ETF日线行情记录

		Args:
			daily_data: 日线行情数据

		Returns:
			创建的ETF日线行情记录
		"""
		return await self.etf_daily_repo.create(daily_data)

	async def create_etf_minute (self, minute_data: Dict[str, Any]) -> EtfMinute:
		"""
		创建ETF分钟行情记录

		Args:
			minute_data: 分钟行情数据

		Returns:
			创建的ETF分钟行情记录
		"""
		return await self.etf_minute_repo.create(minute_data)

	# ==================== 指数信息操作 ====================

	async def get_etf_index (self, ts_code: str) -> Optional[EtfIndex]:
		"""
		获取ETF跟踪指数信息

		Args:
			ts_code: 指数代码

		Returns:
			指数信息或None
		"""
		return await self.etf_index_repo.get_by(ts_code=ts_code)

	async def get_etf_by_index (self, index_code: str) -> List[EtfBasic]:
		"""
		获取跟踪特定指数的ETF列表

		Args:
			index_code: 指数代码

		Returns:
			ETF列表
		"""
		return await self.etf_basic_repo.get_many(index_code=index_code)

	async def search_indices (
			self,
			keyword: str,
			limit: int = 50,
			skip: int = 0
	) -> List[EtfIndex]:
		"""
		搜索指数

		Args:
			keyword: 搜索关键词
			limit: 返回数量限制
			skip: 跳过数量

		Returns:
			指数列表
		"""
		query = select(EtfIndex).where(
			or_(
				EtfIndex.ts_code.like(f"%{keyword}%"),
				EtfIndex.indx_name.like(f"%{keyword}%"),
				EtfIndex.indx_csname.like(f"%{keyword}%")
			)
		).order_by(EtfIndex.ts_code).offset(skip).limit(limit)

		result = await self.session.execute(query)
		return result.scalars().all()

	async def create_etf_index (self, index_data: Dict[str, Any]) -> EtfIndex:
		"""
		创建指数信息

		Args:
			index_data: 指数数据

		Returns:
			创建的指数信息
		"""
		return await self.etf_index_repo.create(index_data)

	# ==================== 复权因子操作 ====================

	async def get_adj_factor (
			self,
			ts_code: str,
			trade_date: date
	) -> Optional[FundAdjFactor]:
		"""
		获取复权因子

		Args:
			ts_code: ETF代码
			trade_date: 交易日期

		Returns:
			复权因子或None
		"""
		return await self.adj_factor_repo.get_by(
			ts_code=ts_code,
			trade_date=trade_date
		)

	async def get_adj_factors_in_range (
			self,
			ts_code: str,
			start_date: date,
			end_date: date
	) -> List[FundAdjFactor]:
		"""
		获取指定时间范围内的复权因子

		Args:
			ts_code: ETF代码
			start_date: 开始日期
			end_date: 结束日期

		Returns:
			复权因子列表
		"""
		query = select(FundAdjFactor).where(
			and_(
				FundAdjFactor.ts_code == ts_code,
				FundAdjFactor.trade_date >= start_date,
				FundAdjFactor.trade_date <= end_date
			)
		).order_by(FundAdjFactor.trade_date)

		result = await self.session.execute(query)
		return result.scalars().all()

	async def get_latest_adj_factor (self, ts_code: str) -> Optional[FundAdjFactor]:
		"""
		获取最新的复权因子

		Args:
			ts_code: ETF代码

		Returns:
			最新的复权因子或None
		"""
		query = select(FundAdjFactor).where(
			FundAdjFactor.ts_code == ts_code
		).order_by(desc(FundAdjFactor.trade_date)).limit(1)

		result = await self.session.execute(query)
		return result.scalar_one_or_none()

	async def create_adj_factor (self, factor_data: Dict[str, Any]) -> FundAdjFactor:
		"""
		创建复权因子记录

		Args:
			factor_data: 复权因子数据

		Returns:
			创建的复权因子记录
		"""
		return await self.adj_factor_repo.create(factor_data)

	# ==================== ETF持仓操作 ====================

	async def get_etf_portfolio (
			self,
			ts_code: str,
			end_date: date
	) -> List[Dict[str, Any]]:
		"""
		获取ETF持仓

		Args:
			ts_code: ETF代码
			end_date: 持仓截止日期

		Returns:
			ETF持仓列表
		"""
		# 注意：ETF持仓表可能需要单独定义
		# 这里假设有一个ETF持仓表，根据实际情况调整
		query = text("""
                     SELECT ts_code,
                            end_date,
                            symbol,
                            name,
                            weight,
                            shares,
                            market_value,
                            proportion
                     FROM etf_portfolio
                     WHERE ts_code = :ts_code
                       AND end_date = :end_date
                     ORDER BY weight DESC
		             """)

		result = await self.session.execute(
			query,
			{"ts_code": ts_code, "end_date": end_date}
		)

		portfolio = []
		for row in result.fetchall():
			portfolio.append({
				"symbol": row.symbol,
				"name": row.name,
				"weight": row.weight,
				"shares": row.shares,
				"market_value": row.market_value,
				"proportion": row.proportion
			})

		return portfolio

	async def get_latest_etf_portfolio (self, ts_code: str) -> Optional[List[Dict[str, Any]]]:
		"""
		获取最新ETF持仓

		Args:
			ts_code: ETF代码

		Returns:
			最新ETF持仓或None
		"""
		# 首先找到最新的持仓日期
		query = text("""
                     SELECT MAX(end_date) as latest_date
                     FROM etf_portfolio
                     WHERE ts_code = :ts_code
		             """)

		result = await self.session.execute(query, {"ts_code": ts_code})
		row = result.fetchone()

		if not row or not row.latest_date:
			return None

		return await self.get_etf_portfolio(ts_code, row.latest_date)

	async def get_etf_by_underlying (self, underlying_symbol: str) -> List[EtfBasic]:
		"""
		根据标的成分获取ETF

		Args:
			underlying_symbol: 标的代码

		Returns:
			ETF列表
		"""
		# 通过持仓表查询持有特定标的的ETF
		query = text("""
                     SELECT DISTINCT ep.ts_code
                     FROM etf_portfolio ep
                     WHERE ep.symbol = :symbol
		             """)

		result = await self.session.execute(query, {"symbol": underlying_symbol})
		ts_codes = [row[0] for row in result.fetchall()]

		if not ts_codes:
			return []

		# 获取ETF基础信息
		query = select(EtfBasic).where(EtfBasic.ts_code.in_(ts_codes))
		result = await self.session.execute(query)
		return result.scalars().all()

	# ==================== 统计分析操作 ====================

	async def get_etf_summary (self, ts_code: str) -> Dict[str, Any]:
		"""
		获取ETF概要信息

		Args:
			ts_code: ETF代码

		Returns:
			ETF概要信息字典
		"""
		# 获取基础信息
		etf_basic = await self.get_etf_basic(ts_code)
		if not etf_basic:
			return {}

		# 获取最新行情
		latest_daily = await self.get_latest_etf_daily(ts_code)

		# 获取最新持仓
		latest_portfolio = await self.get_latest_etf_portfolio(ts_code)

		# 获取指数信息
		index_info = None
		if etf_basic.index_code:
			index_info = await self.get_etf_index(etf_basic.index_code)

		# 统计持仓
		portfolio_stats = {}
		if latest_portfolio:
			total_weight = sum(item["weight"] for item in latest_portfolio)
			top_holdings = sorted(
				latest_portfolio,
				key=lambda x: x["weight"],
				reverse=True
			)[:10]

			portfolio_stats = {
				"total_holdings": len(latest_portfolio),
				"total_weight": total_weight,
				"top_10_weight": sum(item["weight"] for item in top_holdings),
				"top_holdings": top_holdings
			}

		return {
			"basic_info": {
				"ts_code": etf_basic.ts_code,
				"name": etf_basic.cname,
				"short_name": etf_basic.csname,
				"exchange": etf_basic.exchange,
				"fund_type": etf_basic.etf_type,
				"manager": etf_basic.mgr_name,
				"setup_date": etf_basic.setup_date,
				"list_date": etf_basic.list_date,
				"management_fee": etf_basic.mgt_fee
			},
			"index_info": {
				"index_code": etf_basic.index_code,
				"index_name": etf_basic.index_name,
				"base_index": index_info.indx_name if index_info else None,
				"base_date": index_info.base_date if index_info else None
			},
			"latest_price": {
				"trade_date": latest_daily.trade_date if latest_daily else None,
				"close": latest_daily.close if latest_daily else None,
				"change": latest_daily.change if latest_daily else None,
				"pct_chg": latest_daily.pct_chg if latest_daily else None,
				"volume": latest_daily.vol if latest_daily else None,
				"amount": latest_daily.amount if latest_daily else None
			},
			"portfolio_summary": portfolio_stats
		}

	async def analyze_etf_performance (
			self,
			ts_code: str,
			start_date: date,
			end_date: date
	) -> Dict[str, Any]:
		"""
		分析ETF表现

		Args:
			ts_code: ETF代码
			start_date: 开始日期
			end_date: 结束日期

		Returns:
			ETF表现分析结果
		"""
		# 获取ETF行情数据
		daily_data = await self.get_etf_daily_in_range(ts_code, start_date, end_date)

		if not daily_data:
			return {}

		# 计算收益
		first_close = daily_data[0].close
		last_close = daily_data[-1].close
		total_return = (last_close - first_close) / first_close

		# 计算日收益
		daily_returns = []
		for i in range(1, len(daily_data)):
			prev_close = daily_data[i - 1].close
			curr_close = daily_data[i].close
			daily_return = (curr_close - prev_close) / prev_close
			daily_returns.append(daily_return)

		# 计算波动率
		import statistics
		if daily_returns:
			avg_return = statistics.mean(daily_returns)
			volatility = statistics.stdev(daily_returns) * (252 ** 0.5)  # 年化波动率
			sharpe_ratio = avg_return / statistics.stdev(daily_returns) * (252 ** 0.5) if statistics.stdev(
				daily_returns) != 0 else 0
		else:
			avg_return = 0
			volatility = 0
			sharpe_ratio = 0

		# 计算最大回撤
		max_drawdown = 0
		peak = daily_data[0].close
		for daily in daily_data:
			if daily.close > peak:
				peak = daily.close
			drawdown = (peak - daily.close) / peak
			if drawdown > max_drawdown:
				max_drawdown = drawdown

		# 计算交易活跃度
		avg_volume = statistics.mean([d.vol for d in daily_data])
		avg_amount = statistics.mean([d.amount for d in daily_data])

		return {
			"ts_code": ts_code,
			"analysis_period": {
				"start_date": start_date,
				"end_date": end_date,
				"days": len(daily_data)
			},
			"performance_metrics": {
				"total_return": total_return,
				"annualized_return": total_return * (252 / len(daily_data)) if len(daily_data) > 0 else 0,
				"volatility": volatility,
				"sharpe_ratio": sharpe_ratio,
				"max_drawdown": max_drawdown
			},
			"trading_metrics": {
				"average_volume": avg_volume,
				"average_amount": avg_amount,
				"average_daily_change": avg_return,
				"positive_days": sum(1 for d in daily_returns if d > 0),
				"negative_days": sum(1 for d in daily_returns if d < 0)
			},
			"price_summary": {
				"start_price": first_close,
				"end_price": last_close,
				"highest_price": max(d.close for d in daily_data),
				"lowest_price": min(d.close for d in daily_data)
			}
		}

	# ==================== 批量操作 ====================

	async def batch_create_etf_dailies (self, dailies_data: List[Dict[str, Any]]) -> List[EtfDaily]:
		"""
		批量创建ETF日线行情

		Args:
			dailies_data: 日线行情数据列表

		Returns:
			创建的ETF日线行情记录列表
		"""
		return await self.etf_daily_repo.batch_create(dailies_data)

	async def batch_create_etf_minutes (self, minutes_data: List[Dict[str, Any]]) -> List[EtfMinute]:
		"""
		批量创建ETF分钟行情

		Args:
			minutes_data: 分钟行情数据列表

		Returns:
			创建的ETF分钟行情记录列表
		"""
		return await self.etf_minute_repo.batch_create(minutes_data)

	async def batch_upsert_etf_basics (self, etfs_data: List[Dict[str, Any]]) -> List[EtfBasic]:
		"""
		批量插入或更新ETF基础信息

		Args:
			etfs_data: ETF数据列表

		Returns:
			更新后的ETF基础信息列表
		"""
		return await self.etf_basic_repo.batch_upsert(
			match_fields=["ts_code"],
			data_list=etfs_data
		)

	async def batch_upsert_adj_factors (self, factors_data: List[Dict[str, Any]]) -> List[FundAdjFactor]:
		"""
		批量插入或更新复权因子

		Args:
			factors_data: 复权因子数据列表

		Returns:
			更新后的复权因子列表
		"""
		return await self.adj_factor_repo.batch_upsert(
			match_fields=["ts_code", "trade_date"],
			data_list=factors_data
		)