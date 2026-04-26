# -*- coding: utf-8 -*-
"""
ST股票列表Repository
位置：quant_server/shared/database/repositories/market/basic/st_list_repository.py
职责：管理ST股票列表表（StockSTList）的数据访问
设计原则：
1. 继承BaseRepository，复用CRUD操作
2. 提供ST股票特有的查询方法
3. 跟踪ST状态变化历史
"""

from datetime import datetime, date
from typing import List, Optional, Dict, Any

from sqlalchemy import select, func, desc, distinct
from sqlalchemy.ext.asyncio import AsyncSession

from quant_server.shared.database.models.data_models import StockSTList, StockBasic
from quant_server.shared.database.repositories.base import BaseRepository


class STListRepository(BaseRepository[StockSTList]):
	"""ST股票列表Repository - 管理StockSTList表的数据访问"""

	def __init__ (self, session: AsyncSession):
		"""
		初始化ST股票列表Repository

		Args:
			session: 异步数据库会话
		"""
		super().__init__(session, StockSTList)

	# ==================== ST股票查询方法 ====================

	async def get_current_st_stocks (self, query_date: date = None) -> List[StockSTList]:
		"""
		获取指定日期的ST股票列表（默认当前日期）

		Args:
			query_date: 查询日期，默认当前日期

		Returns:
			ST股票列表
		"""
		try:
			if query_date is None:
				query_date = datetime.now().date()

			# 使用窗口函数优化查询，避免子查询类型推断问题
			from sqlalchemy import over

			# 方法1：使用窗口函数直接获取最新记录
			query = (
				select(StockSTList)
				.where(StockSTList.trade_date <= query_date)
				.where(StockSTList.st_type.in_(['ST', '*ST']))
				.order_by(StockSTList.ts_code, StockSTList.trade_date.desc())
				.distinct(StockSTList.ts_code)
			)

			result = await self.session.execute(query)
			return result.scalars().all()
		except Exception as e:
			raise RepositoryError(f"获取当前ST股票失败: {str(e)}")

	async def get_st_history_by_stock (self, ts_code: str) -> List[StockSTList]:
		"""
		获取单只股票的ST历史记录

		Args:
			ts_code: 股票TS代码

		Returns:
			ST历史记录列表
		"""
		try:
			query = (
				select(self.model)
				.where(self.model.ts_code == ts_code)
				.order_by(desc(self.model.trade_date))
			)
			result = await self.session.execute(query)
			return result.scalars().all()
		except Exception as e:
			raise RepositoryError(f"获取ST历史记录失败: {str(e)}")

	async def get_stocks_by_st_type (
			self,
			st_type: str,
			query_date: date = None,
			include_history: bool = False
	) -> List[StockSTList]:
		"""
		根据ST类型获取股票列表

		Args:
			st_type: ST类型（'ST', '*ST', 'SST'等）
			query_date: 查询日期，默认当前日期
			include_history: 是否包含历史记录

		Returns:
			ST股票列表
		"""
		try:
			if query_date is None:
				query_date = datetime.now().date()

			if include_history:
				# 包含历史记录
				query = (
					select(self.model)
					.where(self.model.st_type == st_type)
					.where(self.model.trade_date <= query_date)
					.order_by(desc(self.model.trade_date), self.model.ts_code)
				)
			else:
				# 使用更简洁的查询方式获取指定日期的最新记录
				query = (
					select(self.model)
					.where(self.model.trade_date <= query_date)
					.where(self.model.st_type == st_type)
					.order_by(self.model.ts_code, self.model.trade_date.desc())
					.distinct(self.model.ts_code)
				)

			result = await self.session.execute(query)
			return result.scalars().all()
		except Exception as e:
			raise RepositoryError(f"根据ST类型查询失败: {str(e)}")

	async def get_st_stock_with_info (self, ts_code: str, query_date: date = None) -> Optional[Dict[str, Any]]:
		"""
		获取ST股票及其基础信息

		Args:
			ts_code: 股票TS代码
			query_date: 查询日期

		Returns:
			ST股票及基础信息字典
		"""
		try:
			if query_date is None:
				query_date = datetime.now().date()

			# 获取该股票指定日期的最新ST记录
			st_query = (
				select(self.model)
				.where(self.model.ts_code == ts_code)
				.where(self.model.trade_date <= query_date)
				.order_by(desc(self.model.trade_date))
				.limit(1)
			)

			st_result = await self.session.execute(st_query)
			st_record = st_result.scalar_one_or_none()

			if not st_record:
				return None

			# 获取股票基础信息
			stock_query = select(StockBasic).where(StockBasic.ts_code == ts_code)
			stock_result = await self.session.execute(stock_query)
			stock = stock_result.scalar_one_or_none()

			return {
				"st_record": st_record,
				"stock": stock,
				"combined_info": {
					"ts_code": st_record.ts_code,
					"name": st_record.name,
					"st_type": st_record.st_type,
					"st_type_name": st_record.st_type_name,
					"trade_date": st_record.trade_date,
					"stock_name": stock.name if stock else None,
					"industry": stock.industry if stock else None
				}
			}
		except Exception as e:
			raise RepositoryError(f"获取ST股票及基础信息失败: {str(e)}")

	# ==================== ST状态变化跟踪方法 ====================

	async def get_st_status_changes (
			self,
			ts_code: str,
			start_date: date = None,
			end_date: date = None
	) -> List[Dict[str, Any]]:
		"""
		获取ST状态变化历史

		Args:
			ts_code: 股票TS代码
			start_date: 开始日期
			end_date: 结束日期

		Returns:
			ST状态变化列表
		"""
		try:
			query = select(self.model).where(self.model.ts_code == ts_code)

			if start_date:
				query = query.where(self.model.trade_date >= start_date)

			if end_date:
				query = query.where(self.model.trade_date <= end_date)

			query = query.order_by(self.model.trade_date)

			result = await self.session.execute(query)
			records = result.scalars().all()

			# 分析状态变化
			changes = []
			for i, record in enumerate(records):
				change_info = {
					"trade_date": record.trade_date,
					"st_type": record.st_type,
					"st_type_name": record.st_type_name
				}

				# 与前一条记录比较
				if i > 0:
					prev_record = records[i - 1]
					if prev_record.st_type != record.st_type:
						change_info["change_type"] = "类型变更"
						change_info["from_type"] = prev_record.st_type
						change_info["to_type"] = record.st_type
					elif prev_record.st_type_name != record.st_type_name:
						change_info["change_type"] = "名称变更"
						change_info["from_name"] = prev_record.st_type_name
						change_info["to_name"] = record.st_type_name
					else:
						change_info["change_type"] = "状态延续"
				else:
					change_info["change_type"] = "首次记录"

				changes.append(change_info)

			return changes
		except Exception as e:
			raise RepositoryError(f"获取ST状态变化失败: {str(e)}")

	async def is_stock_st (self, ts_code: str, query_date: date = None) -> bool:
		"""
		判断股票在指定日期是否为ST

		Args:
			ts_code: 股票TS代码
			query_date: 查询日期

		Returns:
			是否为ST
		"""
		try:
			if query_date is None:
				query_date = datetime.now().date()

			query = (
				select(self.model)
				.where(self.model.ts_code == ts_code)
				.where(self.model.trade_date <= query_date)
				.where(self.model.st_type.in_(['ST', '*ST']))
				.order_by(desc(self.model.trade_date))
				.limit(1)
			)

			result = await self.session.execute(query)
			record = result.scalar_one_or_none()

			return record is not None
		except Exception as e:
			raise RepositoryError(f"判断ST状态失败: {str(e)}")

	# ==================== 统计分析方法 ====================

	async def get_st_type_distribution (self, query_date: date = None) -> Dict[str, int]:
		"""
		获取ST类型分布统计

		Args:
			query_date: 查询日期

		Returns:
			ST类型分布字典（类型:数量）
		"""
		try:
			current_st = await self.get_current_st_stocks(query_date)

			distribution = {}
			for record in current_st:
				st_type = record.st_type
				distribution[st_type] = distribution.get(st_type, 0) + 1

			return dict(sorted(distribution.items(), key=lambda x: x[1], reverse=True))
		except Exception as e:
			raise RepositoryError(f"获取ST类型分布失败: {str(e)}")

	async def get_st_trend_by_month (
			self,
			start_date: date,
			end_date: date
	) -> List[Dict[str, Any]]:
		"""
		获取ST数量月度趋势

		Args:
			start_date: 开始日期
			end_date: 结束日期

		Returns:
			月度趋势数据
		"""
		try:
			# 按月统计
			query = (
				select(
					func.date_trunc('month', self.model.trade_date).label('month'),
					func.count(distinct(self.model.ts_code)).label('st_count')
				)
				.where(self.model.trade_date.between(start_date, end_date))
				.group_by(func.date_trunc('month', self.model.trade_date))
				.order_by(func.date_trunc('month', self.model.trade_date))
			)

			result = await self.session.execute(query)
			rows = result.all()

			trend_data = []
			for row in rows:
				trend_data.append({
					"month": row.month,
					"st_count": row.st_count,
					"month_str": row.month.strftime("%Y-%m") if row.month else None
				})

			return trend_data
		except Exception as e:
			raise RepositoryError(f"获取ST月度趋势失败: {str(e)}")

	# ==================== 批量操作方法 ====================

	async def bulk_upsert_st_records (self, st_data_list: List[Dict[str, Any]]) -> List[StockSTList]:
		"""
		批量插入或更新ST记录

		Args:
			st_data_list: ST数据列表

		Returns:
			更新后的ST记录列表
		"""
		try:
			return await self.batch_upsert(
				match_fields=["ts_code", "trade_date"],
				data_list=st_data_list,
				update_fields=None  # 更新所有字段
			)
		except Exception as e:
			raise RepositoryError(f"批量插入或更新ST记录失败: {str(e)}")

	async def add_st_record (
			self,
			ts_code: str,
			name: str,
			st_type: str,
			trade_date: date,
			st_type_name: str = None
	) -> StockSTList:
		"""
		添加ST记录

		Args:
			ts_code: 股票TS代码
			name: 股票名称
			st_type: ST类型
			trade_date: 交易日期
			st_type_name: ST类型名称（可选）

		Returns:
			创建的ST记录
		"""
		try:
			if st_type_name is None:
				# 根据st_type生成默认名称
				st_type_names = {
					'ST': '特别处理',
					'*ST': '退市风险警示',
					'SST': '未股改的ST公司'
				}
				st_type_name = st_type_names.get(st_type, st_type)

			st_data = {
				"ts_code": ts_code,
				"name": name,
				"trade_date": trade_date,
				"st_type": st_type,
				"st_type_name": st_type_name
			}

			return await self.create(st_data)
		except Exception as e:
			raise RepositoryError(f"添加ST记录失败: {str(e)}")


class RepositoryError(Exception):
	"""Repository异常基类"""

	def __init__ (self, message: str, code: str = "ST_LIST_REPOSITORY_ERROR"):
		"""
		初始化异常

		Args:
			message: 错误信息
			code: 错误码
		"""
		self.message = message
		self.code = code
		super().__init__(self.message)
