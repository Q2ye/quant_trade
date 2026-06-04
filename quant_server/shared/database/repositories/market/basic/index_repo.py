# -*- coding: utf-8 -*-
"""
指数数据仓库
位置：quant_server/shared/database/repositories/market/basic/index_repo.py
职责：管理指数基础信息、行情、成分股等数据访问
设计原则：继承BaseRepository，使用统一数据访问接口
"""

from datetime import date
from typing import List, Optional, Dict, Any

from sqlalchemy import select, and_, or_, desc
from sqlalchemy.ext.asyncio import AsyncSession

from shared.database.models.data_models import (
	IndexBasic,
	IndexDaily,
	IndexWeight,
)
from shared.database.repositories.base import BaseRepository, RepositoryError


class IndexBasicRepository(BaseRepository[IndexBasic]):
	"""指数基础信息仓库 - 继承BaseRepository"""

	def __init__ (self, session: AsyncSession):
		"""初始化指数基础信息仓库"""
		super().__init__(session, IndexBasic)

	async def search_by_keyword (self, keyword: str, limit: int = 100, skip: int = 0) -> List[IndexBasic]:
		"""
		搜索指数

		Args:
			keyword: 搜索关键词（匹配代码、名称、全称）
			limit: 返回数量限制
			skip: 跳过记录数

		Returns:
			指数列表
		"""
		try:
			query = select(self.model).where(
				or_(
					self.model.ts_code.like(f"%{keyword}%"),
					self.model.name.like(f"%{keyword}%"),
					self.model.fullname.like(f"%{keyword}%")
				)
			).order_by(self.model.ts_code).offset(skip).limit(limit)

			result = await self.session.execute(query)
			return result.scalars().all()

		except Exception as e:
			raise RepositoryError(f"搜索指数失败: {str(e)}")

	async def get_by_category (self, category: str) -> List[IndexBasic]:
		"""
		根据类别获取指数

		Args:
			category: 指数类别

		Returns:
			指数列表
		"""
		return await self.get_many(category=category)

	async def get_by_publisher (self, publisher: str) -> List[IndexBasic]:
		"""
		根据发布机构获取指数

		Args:
			publisher: 发布机构

		Returns:
			指数列表
		"""
		return await self.get_many(publisher=publisher)


class IndexDailyRepository(BaseRepository[IndexDaily]):
	"""指数日线行情仓库 - 继承BaseRepository"""

	def __init__ (self, session: AsyncSession):
		"""初始化指数日线行情仓库"""
		super().__init__(session, IndexDaily)

	async def batch_insert (self, records: List[Dict[str, Any]]) -> int:
		"""全量模式批量插入，跳过冲突。比逐条 create 快 100 倍。"""
		if not records:
			return 0
		from sqlalchemy.dialects.postgresql import insert as pg_insert
		stmt = pg_insert(self.model).values(records).on_conflict_do_nothing()
		result = await self.session.execute(stmt)
		return result.rowcount

	async def get_by_date_range (
			self,
			ts_code: str,
			start_date: date,
			end_date: date
	) -> List[IndexDaily]:
		"""
		获取指定时间范围内的指数日线行情

		Args:
			ts_code: 指数代码
			start_date: 开始日期
			end_date: 结束日期

		Returns:
			指数日线行情列表
		"""
		try:
			query = select(self.model).where(
				and_(
					self.model.ts_code == ts_code,
					self.model.trade_date >= start_date,
					self.model.trade_date <= end_date
				)
			).order_by(self.model.trade_date)

			result = await self.session.execute(query)
			return result.scalars().all()

		except Exception as e:
			raise RepositoryError(f"获取指数日线行情范围失败: {str(e)}")

	async def get_latest_by_ts_code (self, ts_code: str) -> Optional[IndexDaily]:
		"""
		获取最新的指数日线行情

		Args:
			ts_code: 指数代码

		Returns:
			最新的指数日线行情或None
		"""
		try:
			query = select(self.model).where(
				self.model.ts_code == ts_code
			).order_by(desc(self.model.trade_date)).limit(1)

			result = await self.session.execute(query)
			return result.scalar_one_or_none()

		except Exception as e:
			raise RepositoryError(f"获取最新指数日线行情失败: {str(e)}")

	async def get_latest_trade_date (self, ts_code: str) -> Optional[date]:
		"""
		获取指定指数最新的交易日日期（用于 _resolve_sync_date_range 智能推断）。

		Args:
			ts_code: 指数代码

		Returns:
			最新交易日期或 None
		"""
		latest = await self.get_latest_by_ts_code(ts_code)
		return latest.trade_date if latest else None

	async def get_by_trade_date (self, ts_code: str, trade_date: date) -> List[IndexDaily]:
		"""
		按指数代码和交易日期查询记录（用于 _process_trade_date_data 去重）。

		Args:
			ts_code: 指数代码
			trade_date: 交易日期

		Returns:
			匹配的日线行情列表（通常 0 或 1 条）
		"""
		try:
			query = select(self.model).where(
				and_(
					self.model.ts_code == ts_code,
					self.model.trade_date == trade_date
				)
			)
			result = await self.session.execute(query)
			return list(result.scalars().all())
		except Exception as e:
			raise RepositoryError(f"按交易日期查询指数日线失败: {str(e)}")


class IndexWeightRepository(BaseRepository[IndexWeight]):
	"""指数成分股权重仓库 — 继承 BaseRepository

	管理 index_weight 表的 CRUD 操作，支持按指数代码和日期查询成分股，
	以及批量 upsert 用于数据同步场景。
	"""

	def __init__(self, session: AsyncSession):
		"""初始化指数成分股权重仓库"""
		super().__init__(session, IndexWeight)

	async def get_constituents(
			self,
			index_code: str,
			trade_date: date
	) -> List[IndexWeight]:
		"""
		获取指定指数在指定日期的成分股及权重

		Args:
			index_code: 指数代码（如 '000300.SH'）
			trade_date: 目标日期，查询该日期生效的权重

		Returns:
			IndexWeight 对象列表，包含 ts_code、weight 等字段
		"""
		try:
			query = select(self.model).where(
				and_(
					self.model.index_code == index_code,
					self.model.trade_date == trade_date
				)
			).order_by(self.model.weight.desc())
			result = await self.session.execute(query)
			return result.scalars().all()
		except Exception as e:
			raise RepositoryError(f"查询指数 {index_code} 成分股失败: {str(e)}")

	async def get_latest_constituents(
			self,
			index_code: str
	) -> List[IndexWeight]:
		"""
		获取指定指数最新日期的成分股及权重

		自动查询 index_weight 表中该指数的最新 trade_date，
		然后返回该日期的所有成分股。

		Args:
			index_code: 指数代码（如 '000300.SH'、'000905.SH'）

		Returns:
			IndexWeight 对象列表（按权重降序）
		"""
		try:
			# 先查最新日期
			latest_date_query = select(self.model.trade_date).where(
				self.model.index_code == index_code
			).order_by(desc(self.model.trade_date)).limit(1)
			date_result = await self.session.execute(latest_date_query)
			latest_date = date_result.scalar_one_or_none()

			if not latest_date:
				return []

			# 查该日期的全部成分股
			return await self.get_constituents(index_code, latest_date)
		except Exception as e:
			raise RepositoryError(f"查询指数 {index_code} 最新成分股失败: {str(e)}")

	async def batch_upsert(
			self,
			match_fields: List[str],
			data_list: List[Dict[str, Any]],
			update_fields: List[str] = None
		) -> List[IndexWeight]:
		"""
		批量插入或更新成分股权重数据

		用于数据同步场景：同步服务从 Tushare/Baostock 拉取数据后
		批量写入，已存在的记录（基于 match_fields）会被更新。

		Args:
			data_list: 待 upsert 的数据列表，每项包含 index_code, ts_code, weight, trade_date
			match_fields: 用于匹配已有记录的字段列表，默认 ['index_code', 'ts_code', 'trade_date']
			update_fields: 需要更新的字段列表，默认 None 表示更新全部

		Returns:
			创建的 IndexWeight 对象列表
		"""
		if match_fields is None:
			match_fields = ['index_code', 'ts_code', 'trade_date']
		return await super().batch_upsert(match_fields, data_list)


# ==================== 指数聚合仓库 ====================

class IndexRepository:
	"""指数聚合仓库 - 协调指数相关所有数据访问"""

	def __init__ (self, session: AsyncSession):
		"""初始化指数聚合仓库"""
		self.session = session
		self.index_basic_repo = IndexBasicRepository(session)
		self.index_daily_repo = IndexDailyRepository(session)
		self.index_weight_repo = IndexWeightRepository(session)

	# ==================== 基础信息操作 ====================

	async def get_index_basic (self, index_code: str) -> Optional[IndexBasic]:
		"""获取指数基础信息"""
		return await self.index_basic_repo.get_by(ts_code=index_code)

	async def search_indices (self, keyword: str, limit: int = 100, skip: int = 0) -> List[IndexBasic]:
		"""搜索指数"""
		return await self.index_basic_repo.search_by_keyword(keyword, limit, skip)

	async def get_indices_by_category (self, category: str) -> List[IndexBasic]:
		"""根据类别获取指数"""
		return await self.index_basic_repo.get_by_category(category)

	async def get_indices_by_publisher (self, publisher: str) -> List[IndexBasic]:
		"""根据发布机构获取指数"""
		return await self.index_basic_repo.get_by_publisher(publisher)

	# ==================== 行情操作 ====================

	async def get_index_daily (self, index_code: str, trade_date: date) -> Optional[IndexDaily]:
		"""获取指数日线行情"""
		return await self.index_daily_repo.get_by(
			ts_code=index_code,
			trade_date=trade_date
		)

	async def get_index_daily_range (
			self,
			index_code: str,
			start_date: date,
			end_date: date
	) -> List[IndexDaily]:
		"""获取指数日线行情范围"""
		return await self.index_daily_repo.get_by_date_range(index_code, start_date, end_date)

	async def get_latest_index_daily (self, index_code: str) -> Optional[IndexDaily]:
		"""获取最新指数日线行情"""
		return await self.index_daily_repo.get_latest_by_ts_code(index_code)

	# ==================== 成分股权重操作 ====================

	async def get_index_constituents(
			self,
			index_code: str,
			trade_date: date
	) -> List[IndexWeight]:
		"""获取指定指数在指定日期的成分股及权重"""
		return await self.index_weight_repo.get_constituents(index_code, trade_date)

	async def get_latest_index_constituents(
			self,
			index_code: str
	) -> List[IndexWeight]:
		"""获取指定指数最新日期的成分股及权重"""
		return await self.index_weight_repo.get_latest_constituents(index_code)

	async def batch_upsert_index_weights(
			self,
			data_list: List[Dict[str, Any]]
	) -> List[IndexWeight]:
		"""批量插入或更新指数成分股权重"""
		return await self.index_weight_repo.batch_upsert(
			match_fields=["index_code", "ts_code", "trade_date"],
			data_list=data_list
		)

	# ==================== 统计分析操作 ====================

	async def analyze_index_performance (
			self,
			index_code: str,
			start_date: date,
			end_date: date
	) -> Dict[str, Any]:
		"""
		分析指数表现

		Args:
			index_code: 指数代码
			start_date: 开始日期
			end_date: 结束日期

		Returns:
			指数表现分析结果
		"""
		# 获取指数行情数据
		daily_data = await self.get_index_daily_range(index_code, start_date, end_date)

		if not daily_data:
			return {"error": "没有找到行情数据"}

		# 获取指数基础信息
		index_info = await self.get_index_basic(index_code)

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
		peak = first_close
		for daily in daily_data:
			current_close = daily.close
			if current_close > peak:
				peak = current_close
			drawdown = (peak - current_close) / peak
			if drawdown > max_drawdown:
				max_drawdown = drawdown

		# 计算交易活跃度
		avg_volume = statistics.mean([d.vol for d in daily_data]) if daily_data else 0
		avg_amount = statistics.mean([d.amount for d in daily_data]) if daily_data else 0

		return {
			"index_info": index_info,
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
				"max_drawdown": max_drawdown,
				"average_daily_return": avg_return
			},
			"market_characteristics": {
				"average_volume": avg_volume,
				"average_amount": avg_amount,
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

	async def compare_indices_performance (
			self,
			index_codes: List[str],
			start_date: date,
			end_date: date
	) -> List[Dict[str, Any]]:
		"""
		比较多个指数的表现

		Args:
			index_codes: 指数代码列表
			start_date: 开始日期
			end_date: 结束日期

		Returns:
			指数比较结果列表
		"""
		comparison_results = []

		for index_code in index_codes:
			# 获取行情数据
			daily_data = await self.get_index_daily_range(index_code, start_date, end_date)

			if not daily_data:
				continue

			# 计算收益
			first_close = daily_data[0].close
			last_close = daily_data[-1].close
			total_return = (last_close - first_close) / first_close

			# 获取指数信息
			index_info = await self.get_index_basic(index_code)

			comparison_results.append({
				"index_code": index_code,
				"index_name": index_info.name if index_info else "未知",
				"category": index_info.category if index_info else "未知",
				"publisher": index_info.publisher if index_info else "未知",
				"total_return": total_return,
				"annualized_return": total_return * (252 / len(daily_data)) if len(daily_data) > 0 else 0,
				"start_close": first_close,
				"end_close": last_close,
				"data_points": len(daily_data)
			})

		# 按总收益排序
		comparison_results.sort(key=lambda x: x.get("total_return", 0), reverse=True)

		return comparison_results

	# ==================== 批量操作 ====================

	async def batch_create_index_dailies (self, daily_data_list: List[Dict[str, Any]]) -> List[IndexDaily]:
		"""批量创建指数日线行情记录"""
		return await self.index_daily_repo.batch_create(daily_data_list)

	async def batch_upsert_index_basics (self, index_data_list: List[Dict[str, Any]]) -> List[IndexBasic]:
		"""批量插入或更新指数基础信息"""
		return await self.index_basic_repo.batch_upsert(
			match_fields=["ts_code"],
			data_list=index_data_list
		)
