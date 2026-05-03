"""
策略每日绩效表Repository

位置：quant_server/shared/database/repositories/account/asset/strategy_daily_performance_repo.py

对应模型：StrategyDailyPerformance (策略每日绩效指标表，超表)
功能：提供策略每日绩效数据的CRUD操作和统计分析功能。
注意：这是超表Repository，继承自HyperRepositoryBase，专门处理时序数据。
"""

from datetime import datetime, date, timedelta
from typing import List, Optional, Dict, Any

from sqlalchemy import select, func, and_, delete
from sqlalchemy.ext.asyncio import AsyncSession

from shared.database.models.business_models import StrategyDailyPerformance
from shared.database.repositories.base import RepositoryError
from shared.database.repositories.base.hyper_repository_base import HyperRepositoryBase


class StrategyDailyPerformanceRepository(HyperRepositoryBase[StrategyDailyPerformance]):
	"""
	策略每日绩效表Repository

	继承自HyperRepositoryBase，专门处理时序超表数据。
	提供策略每日绩效的时间序列查询、统计分析等功能。
	"""

	def __init__ (self, session: AsyncSession):
		"""
		初始化StrategyDailyPerformanceRepository

		Args:
			session: 异步数据库会话
		"""
		super().__init__(session, StrategyDailyPerformance)

	async def get_strategy_performance (self, strategy_id: str,
	                                    start_date: date,
	                                    end_date: date) -> List[StrategyDailyPerformance]:
		"""
		获取指定策略在指定时间范围内的每日绩效

		Args:
			strategy_id: 策略ID
			start_date: 开始日期
			end_date: 结束日期

		Returns:
			策略每日绩效记录列表，按日期升序排列
		"""
		try:
			query = select(self.model).where(
				and_(
					self.model.strategy_id == strategy_id,
					self.model.trade_date >= start_date,
					self.model.trade_date <= end_date
				)
			).order_by(self.model.trade_date.asc())

			result = await self.session.execute(query)
			return result.scalars().all()
		except Exception as e:
			raise RepositoryError(f"获取策略绩效失败: {str(e)}")

	async def get_latest_performance (self, strategy_id: str,
	                                  days: int = 30) -> List[StrategyDailyPerformance]:
		"""
		获取策略最近N天的绩效数据

		Args:
			strategy_id: 策略ID
			days: 天数（默认30天）

		Returns:
			最近N天的绩效记录列表，按日期降序排列
		"""
		try:
			# 计算最近N天的日期范围
			end_date = datetime.now().date()
			start_date = end_date - timedelta(days=days)

			query = select(self.model).where(
				and_(
					self.model.strategy_id == strategy_id,
					self.model.trade_date >= start_date,
					self.model.trade_date <= end_date
				)
			).order_by(self.model.trade_date.desc())

			result = await self.session.execute(query)
			return result.scalars().all()
		except Exception as e:
			raise RepositoryError(f"获取最近绩效失败: {str(e)}")

	async def get_performance_summary (self, strategy_id: str,
	                                   start_date: date,
	                                   end_date: date) -> Dict[str, Any]:
		"""
		获取策略在指定时间范围内的绩效汇总统计

		Args:
			strategy_id: 策略ID
			start_date: 开始日期
			end_date: 结束日期

		Returns:
			绩效汇总统计字典
		"""
		try:
			query = select(
				func.count().label('total_days'),
				func.sum(self.model.daily_return).label('total_return'),
				func.avg(self.model.daily_return).label('avg_daily_return'),
				func.stddev(self.model.daily_return).label('std_daily_return'),
				func.min(self.model.daily_return).label('min_daily_return'),
				func.max(self.model.daily_return).label('max_daily_return'),
				func.min(self.model.max_drawdown).label('max_drawdown'),
				func.avg(self.model.sharpe_ratio).label('avg_sharpe_ratio')
			).where(
				and_(
					self.model.strategy_id == strategy_id,
					self.model.trade_date >= start_date,
					self.model.trade_date <= end_date
				)
			)

			result = await self.session.execute(query)
			row = result.one()

			return {
				'strategy_id': strategy_id,
				'period': {'start': start_date, 'end': end_date},
				'summary': {
					'total_days': row.total_days,
					'total_return': float(row.total_return) if row.total_return else 0.0,
					'avg_daily_return': float(row.avg_daily_return) if row.avg_daily_return else 0.0,
					'std_daily_return': float(row.std_daily_return) if row.std_daily_return else 0.0,
					'min_daily_return': float(row.min_daily_return) if row.min_daily_return else 0.0,
					'max_daily_return': float(row.max_daily_return) if row.max_daily_return else 0.0,
					'max_drawdown': float(row.max_drawdown) if row.max_drawdown else 0.0,
					'avg_sharpe_ratio': float(row.avg_sharpe_ratio) if row.avg_sharpe_ratio else 0.0
				}
			}
		except Exception as e:
			raise RepositoryError(f"获取绩效汇总失败: {str(e)}")

	async def get_equity_curve (self, strategy_id: str,
	                            start_date: date,
	                            end_date: date) -> List[Dict[str, Any]]:
		"""
		获取策略净值曲线数据

		Args:
			strategy_id: 策略ID
			start_date: 开始日期
			end_date: 结束日期

		Returns:
			净值曲线数据列表，每个元素包含日期和累计收益率
		"""
		try:
			# 使用窗口函数计算累计收益
			# 注意：TimescaleDB支持窗口函数，但需要确保数据库支持
			query = select(
				self.model.trade_date,
				self.model.total_return
			).where(
				and_(
					self.model.strategy_id == strategy_id,
					self.model.trade_date >= start_date,
					self.model.trade_date <= end_date
				)
			).order_by(self.model.trade_date.asc())

			result = await self.session.execute(query)
			rows = result.all()

			equity_curve = []
			for row in rows:
				equity_curve.append({
					'trade_date': row.trade_date,
					'total_return': float(row.total_return) if row.total_return else 0.0
				})

			return equity_curve
		except Exception as e:
			raise RepositoryError(f"获取净值曲线失败: {str(e)}")

	async def get_drawdown_analysis (self, strategy_id: str,
	                                 start_date: date,
	                                 end_date: date) -> Dict[str, Any]:
		"""
		获取策略回撤分析

		Args:
			strategy_id: 策略ID
			start_date: 开始日期
			end_date: 结束日期

		Returns:
			回撤分析结果
		"""
		try:
			# 获取每日最大回撤
			query = select(
				self.model.trade_date,
				self.model.max_drawdown
			).where(
				and_(
					self.model.strategy_id == strategy_id,
					self.model.trade_date >= start_date,
					self.model.trade_date <= end_date
				)
			).order_by(self.model.trade_date.asc())

			result = await self.session.execute(query)
			rows = result.all()

			if not rows:
				return {
					'strategy_id': strategy_id,
					'max_drawdown': 0.0,
					'max_drawdown_date': None,
					'avg_drawdown': 0.0,
					'drawdown_days': 0
				}

			# 计算回撤统计
			drawdowns = [float(row.max_drawdown) for row in rows]
			max_drawdown = min(drawdowns)  # 回撤是负值，最小值表示最大回撤
			max_drawdown_index = drawdowns.index(max_drawdown)

			return {
				'strategy_id': strategy_id,
				'max_drawdown': max_drawdown,
				'max_drawdown_date': rows[max_drawdown_index].trade_date,
				'avg_drawdown': sum(drawdowns) / len(drawdowns),
				'drawdown_days': len([d for d in drawdowns if d < -0.01]),  # 回撤超过1%的天数
				'drawdown_series': [
					{'trade_date': row.trade_date, 'drawdown': float(row.max_drawdown)}
					for row in rows
				]
			}
		except Exception as e:
			raise RepositoryError(f"获取回撤分析失败: {str(e)}")

	async def batch_create_performance (self, performance_data: List[Dict[str, Any]]) -> List[StrategyDailyPerformance]:
		"""
		批量创建绩效记录

		Args:
			performance_data: 绩效数据列表

		Returns:
			创建的绩效记录列表
		"""
		try:
			# 验证数据完整性
			validated_data = []
			for data in performance_data:
				# 确保必要字段存在
				required_fields = ['strategy_id', 'trade_date', 'daily_return', 'total_return', 'max_drawdown']
				if not all(field in data for field in required_fields):
					raise RepositoryError(f"绩效数据缺少必要字段: {data}")

				# 添加时间戳
				if 'created_at' not in data:
					data['created_at'] = datetime.now()

				validated_data.append(data)

			return await self.batch_create(validated_data)
		except Exception as e:
			raise RepositoryError(f"批量创建绩效记录失败: {str(e)}")

	async def upsert_performance (self, strategy_id: str, trade_date: date,
	                              performance_data: Dict[str, Any]) -> StrategyDailyPerformance:
		"""
		插入或更新单日绩效记录

		Args:
			strategy_id: 策略ID
			trade_date: 交易日期
			performance_data: 绩效数据

		Returns:
			更新或创建的绩效记录
		"""
		try:
			# 构建匹配条件
			match_fields = ['strategy_id', 'trade_date']
			data = {
				'strategy_id': strategy_id,
				'trade_date': trade_date,
				**performance_data
			}

			return await self.upsert(match_fields, data)
		except Exception as e:
			raise RepositoryError(f"插入或更新绩效记录失败: {str(e)}")

	async def delete_old_records (self, cutoff_date: date) -> int:
		"""
		删除指定日期之前的旧记录（数据清理）

		Args:
			cutoff_date: 截止日期

		Returns:
			删除的记录数
		"""
		try:
			# noinspection PyNoneFunctionAssignment
			query = delete(self.model).where(
				self.model.trade_date < cutoff_date
			)

			result = await self.session.execute(query)  # type: ignore
			return result.rowcount or 0
		except Exception as e:
			raise RepositoryError(f"删除旧记录失败: {str(e)}")

	async def get_performance_by_date_range (self, start_date: date,
	                                         end_date: date,
	                                         strategy_ids: Optional[List[str]] = None) -> List[
		StrategyDailyPerformance]:
		"""
		获取指定日期范围内的绩效记录（支持多个策略）

		Args:
			start_date: 开始日期
			end_date: 结束日期
			strategy_ids: 策略ID列表（可选，不提供则返回所有策略）

		Returns:
			绩效记录列表
		"""
		try:
			query = select(self.model).where(
				and_(
					self.model.trade_date >= start_date,
					self.model.trade_date <= end_date
				)
			)

			if strategy_ids:
				query = query.where(self.model.strategy_id.in_(strategy_ids))

			query = query.order_by(self.model.strategy_id, self.model.trade_date.asc())

			result = await self.session.execute(query)
			return result.scalars().all()
		except Exception as e:
			raise RepositoryError(f"获取日期范围绩效失败: {str(e)}")

	async def calculate_monthly_performance (self, strategy_id: str,
	                                         year: int,
	                                         month: int) -> Dict[str, Any]:
		"""
		计算月度绩效统计

		Args:
			strategy_id: 策略ID
			year: 年份
			month: 月份

		Returns:
			月度绩效统计
		"""
		try:
			# 构建月份的开始和结束日期
			if month == 12:
				next_year = year + 1
				next_month = 1
			else:
				next_year = year
				next_month = month + 1

			start_date = date(year, month, 1)
			end_date = date(next_year, next_month, 1) - timedelta(days=1)

			# 获取月度数据
			query = select(
				func.count().label('trading_days'),
				func.sum(self.model.daily_return).label('monthly_return'),
				func.avg(self.model.daily_return).label('avg_daily_return'),
				func.stddev(self.model.daily_return).label('std_daily_return'),
				func.min(self.model.daily_return).label('worst_day'),
				func.max(self.model.daily_return).label('best_day'),
				func.min(self.model.max_drawdown).label('max_drawdown')
			).where(
				and_(
					self.model.strategy_id == strategy_id,
					self.model.trade_date >= start_date,
					self.model.trade_date <= end_date
				)
			)

			result = await self.session.execute(query)
			row = result.one()

			# 计算年化波动率与夏普比率
			daily_vol = float(row.std_daily_return) if row.std_daily_return else 0.0
			trading_days = row.trading_days if row.trading_days else 21
			# 月波动率 = 日波动率 × √当月交易日数
			monthly_volatility = daily_vol * (trading_days ** 0.5)
			# 年化夏普比率 = (日均收益 / 日波动率) × √252（假设无风险利率为 0）
			avg_daily = float(row.avg_daily_return) if row.avg_daily_return else 0.0
			sharpe_ratio = (avg_daily / daily_vol) * (252 ** 0.5) if daily_vol > 0 else 0.0

			return {
				'strategy_id': strategy_id,
				'year': year,
				'month': month,
				'period': {'start': start_date, 'end': end_date},
				'trading_days': row.trading_days,
				'monthly_return': float(row.monthly_return) if row.monthly_return else 0.0,
				'avg_daily_return': float(row.avg_daily_return) if row.avg_daily_return else 0.0,
				'std_daily_return': float(row.std_daily_return) if row.std_daily_return else 0.0,
				'monthly_volatility': monthly_volatility,
				'worst_day': float(row.worst_day) if row.worst_day else 0.0,
				'best_day': float(row.best_day) if row.best_day else 0.0,
				'max_drawdown': float(row.max_drawdown) if row.max_drawdown else 0.0,
				'sharpe_ratio': sharpe_ratio
			}
		except Exception as e:
			raise RepositoryError(f"计算月度绩效失败: {str(e)}")