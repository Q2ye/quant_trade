"""
交易费用明细表Repository

位置：quant_server/shared/database/repositories/trading/support/trade_fee_repository.py

对应模型：TradeFee (业务模型文件中的交易费用明细表)
功能：提供交易费用的CRUD操作和查询功能，如按交易ID查询费用、按费用类型统计等。
"""

from typing import List, Optional, Dict, Any
from sqlalchemy import select, func, and_
from sqlalchemy.ext.asyncio import AsyncSession

from quant_server.shared.database.repositories.base import BaseRepository
from quant_server.shared.database.models.business_models import TradeFee
from quant_server.shared.database.repositories.types import (
	PaginationParams,
	PaginationResult,
	FilterCondition,
	SortCondition
)


class TradeFeeRepository(BaseRepository[TradeFee]):
	"""
	交易费用明细表Repository

	继承自BaseRepository，提供对TradeFee表的标准CRUD操作。
	同时提供针对交易费用的特定查询方法。
	"""

	def __init__ (self, session: AsyncSession):
		"""
		初始化TradeFeeRepository

		Args:
			session: 异步数据库会话
		"""
		super().__init__(session, TradeFee)

	async def get_fees_by_trade_id (self, trade_id: str) -> List[TradeFee]:
		"""
		根据成交ID获取所有费用明细

		Args:
			trade_id: 成交ID

		Returns:
			该成交的所有费用明细列表
		"""
		try:
			query = select(self.model).where(
				self.model.trade_id == trade_id
			).order_by(self.model.created_at)

			result = await self.session.execute(query)
			return result.scalars().all()
		except Exception as e:
			raise RepositoryError(f"获取成交费用失败: {str(e)}")

	async def get_fees_by_type (self, fee_type: str,
	                            skip: int = 0, limit: int = 100) -> List[TradeFee]:
		"""
		根据费用类型获取费用记录

		Args:
			fee_type: 费用类型(commission/tax/transfer/stamp)
			skip: 跳过记录数
			limit: 限制记录数

		Returns:
			指定类型的费用记录列表
		"""
		try:
			query = select(self.model).where(
				self.model.fee_type == fee_type
			).order_by(self.model.calculated_at.desc())

			query = query.offset(skip).limit(limit)
			result = await self.session.execute(query)
			return result.scalars().all()
		except Exception as e:
			raise RepositoryError(f"获取费用类型记录失败: {str(e)}")

	async def get_total_fees_by_trade (self, trade_id: str) -> float:
		"""
		计算单笔成交的总费用

		Args:
			trade_id: 成交ID

		Returns:
			该成交的总费用金额
		"""
		try:
			query = select(
				func.sum(self.model.fee_amount)
			).where(self.model.trade_id == trade_id)

			result = await self.session.execute(query)
			total = result.scalar()
			return float(total) if total else 0.0
		except Exception as e:
			raise RepositoryError(f"计算成交总费用失败: {str(e)}")

	async def get_fee_summary_by_date (self, start_date, end_date) -> List[Dict[str, Any]]:
		"""
		按日期统计费用汇总

		Args:
			start_date: 开始日期
			end_date: 结束日期

		Returns:
			费用统计汇总列表，每个元素包含日期和费用汇总
		"""
		try:
			# 使用SQLAlchemy的func.date提取日期部分
			query = select(
				func.date(self.model.calculated_at).label('fee_date'),
				self.model.fee_type,
				func.sum(self.model.fee_amount).label('total_amount'),
				func.count(self.model.id).label('fee_count')
			).where(
				and_(
					self.model.calculated_at >= start_date,
					self.model.calculated_at <= end_date
				)
			).group_by(
				func.date(self.model.calculated_at),
				self.model.fee_type
			).order_by(
				func.date(self.model.calculated_at).desc(),
				self.model.fee_type
			)

			result = await self.session.execute(query)
			rows = result.all()

			# 转换为字典列表
			return [
				{
					'fee_date': row.fee_date,
					'fee_type': row.fee_type,
					'total_amount': float(row.total_amount),
					'fee_count': row.fee_count
				}
				for row in rows
			]
		except Exception as e:
			raise RepositoryError(f"统计费用汇总失败: {str(e)}")

	async def get_fee_summary_by_user (self, user_id: int,
	                                   start_date, end_date) -> Dict[str, Any]:
		"""
		按用户统计交易费用

		Args:
			user_id: 用户ID
			start_date: 开始日期
			end_date: 结束日期

		Returns:
			用户费用统计汇总
		"""
		try:
			# 需要关联查询Trade表获取用户信息
			from quant_server.shared.database.models.business_models import Trade

			query = select(
				func.sum(TradeFee.fee_amount).label('total_fees'),
				func.count(TradeFee.id).label('total_count'),
				TradeFee.fee_type,
				func.avg(TradeFee.fee_rate).label('avg_rate')
			).join(
				Trade, TradeFee.trade_id == Trade.trade_id
			).where(
				and_(
					TradeFee.calculated_at >= start_date,
					TradeFee.calculated_at <= end_date
				)
			).group_by(TradeFee.fee_type)

			result = await self.session.execute(query)
			rows = result.all()

			return {
				'user_id': user_id,
				'period': {'start': start_date, 'end': end_date},
				'summary': [
					{
						'fee_type': row.fee_type,
						'total_fees': float(row.total_fees) if row.total_fees else 0.0,
						'total_count': row.total_count,
						'avg_rate': float(row.avg_rate) if row.avg_rate else 0.0
					}
					for row in rows
				]
			}
		except Exception as e:
			raise RepositoryError(f"统计用户费用失败: {str(e)}")

	async def create_fee (self, trade_id: str, fee_type: str, fee_amount: float,
	                      fee_rate: Optional[float] = None, description: Optional[str] = None) -> TradeFee:
		"""
		创建交易费用记录（简化接口）

		Args:
			trade_id: 成交ID
			fee_type: 费用类型
			fee_amount: 费用金额
			fee_rate: 费率（可选）
			description: 描述（可选）

		Returns:
			创建的TradeFee记录
		"""
		fee_data = {
			'trade_id': trade_id,
			'fee_type': fee_type,
			'fee_amount': fee_amount,
			'fee_rate': fee_rate,
			'description': description
		}

		return await self.create(fee_data)

	async def batch_create_fees (self, fees_data: List[Dict[str, Any]]) -> List[TradeFee]:
		"""
		批量创建交易费用记录

		Args:
			fees_data: 费用数据列表

		Returns:
			创建的TradeFee记录列表
		"""
		return await self.batch_create(fees_data)


# 异常定义
class RepositoryError(Exception):
	"""Repository异常基类"""

	def __init__ (self, message: str, code: str = "TRADE_FEE_REPOSITORY_ERROR"):
		self.message = message
		self.code = code
		super().__init__(self.message)