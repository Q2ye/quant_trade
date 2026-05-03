"""
交易费用明细表Repository

位置：quant_server/shared/database/repositories/trading/support/trade_fee_repository.py

对应模型：TradeFee (业务模型文件中的交易费用明细表)
功能：提供交易费用的CRUD操作和查询功能，如按交易ID查询费用、按费用类型统计等。
"""

from datetime import datetime
from typing import List, Optional, Dict, Any

from sqlalchemy import select, func, and_, desc
from sqlalchemy.ext.asyncio import AsyncSession

from shared.database.models.business_models import TradeFee
from shared.database.repositories.base import BaseRepository, RepositoryError


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
			fees: List[TradeFee] = result.scalars().all()
			return fees
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
			fees: List[TradeFee] = result.scalars().all()
			return fees
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

	async def get_fee_summary_by_date (self, start_date: datetime, end_date: datetime) -> List[Dict[str, Any]]:
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

	async def get_fee_summary_by_user (self, user_id: str,
	                                   start_date: datetime, end_date: datetime) -> Dict[str, Any]:
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
			from shared.database.models.business_models import Trade

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
		创建交易费用记录

		Args:
			trade_id: 成交ID
			fee_type: 费用类型
			fee_amount: 费用金额
			fee_rate: 费率（可选）
			description: 描述（可选）

		Returns:
			创建的TradeFee记录
		"""
		# 输入验证
		if not trade_id:
			raise RepositoryError('创建交易费用失败: trade_id 不能为空')
		valid_fee_types = {'commission', 'tax', 'transfer', 'stamp'}
		if fee_type not in valid_fee_types:
			raise RepositoryError(
				f'创建交易费用失败: 无效的费用类型 "{fee_type}"，'
				f'有效值: {valid_fee_types}'
			)
		if fee_amount < 0:
			raise RepositoryError(
				f'创建交易费用失败: 费用金额不能为负数，当前值 {fee_amount}'
			)

		fee_data = {
			'trade_id': trade_id,
			'fee_type': fee_type,
			'fee_amount': fee_amount,
			'fee_rate': fee_rate,
			'description': description,
			'calculated_at': datetime.now()
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
		try:
			return await self.batch_create(fees_data)
		except Exception as e:
			raise RepositoryError(f"批量创建费用记录失败: {str(e)}")

	async def get_fees_by_period (
			self,
			start_date: datetime,
			end_date: datetime,
			fee_type: Optional[str] = None,
			limit: int = 1000
	) -> List[TradeFee]:
		"""
		获取指定时间范围内的费用记录

		Args:
			start_date: 开始时间
			end_date: 结束时间
			fee_type: 费用类型筛选（可选）
			limit: 限制记录数

		Returns:
			费用记录列表
		"""
		try:
			query = select(TradeFee).where(
				and_(
					TradeFee.calculated_at >= start_date,
					TradeFee.calculated_at <= end_date
				)
			).order_by(desc(TradeFee.calculated_at))

			if fee_type:
				query = query.where(TradeFee.fee_type == fee_type)

			query = query.limit(limit)
			result = await self.session.execute(query)
			fees: List[TradeFee] = result.scalars().all()
			return fees
		except Exception as e:
			raise RepositoryError(f"获取时间段费用记录失败: {str(e)}")

	async def get_fee_statistics (
			self,
			start_date: datetime,
			end_date: datetime
	) -> Dict[str, Any]:
		"""
		获取费用统计信息

		Args:
			start_date: 开始时间
			end_date: 结束时间

		Returns:
			费用统计信息字典
		"""
		try:
			# 总费用统计
			total_query = select(
				func.sum(TradeFee.fee_amount).label('total_fees'),
				func.count(TradeFee.id).label('total_count'),
				func.avg(TradeFee.fee_amount).label('avg_fee')
			).where(
				and_(
					TradeFee.calculated_at >= start_date,
					TradeFee.calculated_at <= end_date
				)
			)
			total_result = await self.session.execute(total_query)
			total_stats = total_result.first()

			# 按费用类型统计
			type_query = select(
				TradeFee.fee_type,
				func.sum(TradeFee.fee_amount).label('total_amount'),
				func.count(TradeFee.id).label('count'),
				func.avg(TradeFee.fee_amount).label('avg_amount')
			).where(
				and_(
					TradeFee.calculated_at >= start_date,
					TradeFee.calculated_at <= end_date
				)
			).group_by(TradeFee.fee_type)

			type_result = await self.session.execute(type_query)
			type_stats = [
				{
					'fee_type': row.fee_type,
					'total_amount': float(row.total_amount) if row.total_amount else 0.0,
					'count': row.count,
					'avg_amount': float(row.avg_amount) if row.avg_amount else 0.0
				}
				for row in type_result
			]

			# 按日期统计趋势
			trend_query = select(
				func.date(TradeFee.calculated_at).label('date'),
				func.sum(TradeFee.fee_amount).label('daily_total'),
				func.count(TradeFee.id).label('daily_count')
			).where(
				and_(
					TradeFee.calculated_at >= start_date,
					TradeFee.calculated_at <= end_date
				)
			).group_by(func.date(TradeFee.calculated_at))

			trend_result = await self.session.execute(trend_query)
			trend_stats = [
				{
					'date': row.date,
					'daily_total': float(row.daily_total) if row.daily_total else 0.0,
					'daily_count': row.daily_count
				}
				for row in trend_result
			]

			return {
				'period': {'start': start_date, 'end': end_date},
				'total_fees': float(total_stats.total_fees) if total_stats.total_fees else 0.0,
				'total_count': total_stats.total_count or 0,
				'avg_fee': float(total_stats.avg_fee) if total_stats.avg_fee else 0.0,
				'by_fee_type': type_stats,
				'daily_trend': trend_stats,
				'updated_at': datetime.now()
			}
		except Exception as e:
			raise RepositoryError(f"获取费用统计失败: {str(e)}")

	async def get_high_fee_trades (
			self,
			fee_threshold: float = 1000.0,
			start_date: Optional[datetime] = None,
			end_date: Optional[datetime] = None,
			limit: int = 100
	) -> List[Dict[str, Any]]:
		"""
		获取高费用交易列表

		Args:
			fee_threshold: 费用阈值
			start_date: 开始时间（可选）
			end_date: 结束时间（可选）
			limit: 限制记录数

		Returns:
			高费用交易列表
		"""
		try:
			# 按交易ID分组统计总费用
			query = select(
				TradeFee.trade_id,
				func.sum(TradeFee.fee_amount).label('total_fee'),
				func.count(TradeFee.id).label('fee_count'),
				func.max(TradeFee.calculated_at).label('last_calculated')
			).group_by(TradeFee.trade_id)

			# 添加条件
			having_condition = func.sum(TradeFee.fee_amount) >= fee_threshold
			query = query.having(having_condition)

			if start_date and end_date:
				query = query.where(
					and_(
						TradeFee.calculated_at >= start_date,
						TradeFee.calculated_at <= end_date
					)
				)

			query = query.order_by(desc(func.sum(TradeFee.fee_amount))).limit(limit)

			result = await self.session.execute(query)
			return [
				{
					'trade_id': row.trade_id,
					'total_fee': float(row.total_fee),
					'fee_count': row.fee_count,
					'last_calculated': row.last_calculated
				}
				for row in result
			]
		except Exception as e:
			raise RepositoryError(f"获取高费用交易失败: {str(e)}")

	async def delete_fees_by_trade_id (self, trade_id: str) -> int:
		"""
		删除指定交易的所有费用记录

		Args:
			trade_id: 交易ID

		Returns:
			删除的记录数
		"""
		try:
			from sqlalchemy import delete
			stmt = delete(TradeFee).where(TradeFee.trade_id == trade_id)
			result = await self.session.execute(stmt)  # type: ignore
			return result.rowcount or 0
		except Exception as e:
			raise RepositoryError(f"删除交易费用失败: {str(e)}")


