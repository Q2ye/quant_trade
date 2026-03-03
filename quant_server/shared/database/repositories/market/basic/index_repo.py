# -*- coding: utf-8 -*-
"""
指数数据仓库
位置：quant_server/shared/database/repositories/market/basic/index_repo.py
职责：管理指数基础信息、行情、成分股等数据访问
设计原则：继承BaseRepository，使用统一数据访问接口
"""

from typing import List, Optional, Dict, Any, Tuple
from datetime import datetime, date
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, and_, or_, func, desc, asc, text
from sqlalchemy.orm import selectinload, joinedload

from quant_server.shared.database.repositories.base import BaseRepository, RepositoryError
from quant_server.shared.database.models.data_models import (
	IndexBasic,
	IndexDaily,
	# 假设有指数成分股模型
	# IndexComponent
)


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


# ==================== 指数聚合仓库 ====================

class IndexRepository:
	"""指数聚合仓库 - 协调指数相关所有数据访问"""

	def __init__ (self, session: AsyncSession):
		"""初始化指数聚合仓库"""
		self.session = session
		self.index_basic_repo = IndexBasicRepository(session)
		self.index_daily_repo = IndexDailyRepository(session)

	# 假设有指数成分股仓库
	# self.index_component_repo = IndexComponentRepository(session)

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