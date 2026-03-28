# quant_server/shared/database/repositories/analysis/factor/factor_data_repository.py
"""
因子数据Repository
负责因子数据表（超表）的数据访问操作

继承自HyperRepositoryBase，专门针对时序数据优化
提供因子数据的CRUD操作、统计分析、相关性计算等功能
"""

from typing import Optional, List, Dict, Any
from datetime import datetime
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, update, delete, and_, func, text, desc, asc

from quant_server.shared.database.models.data_models import FactorData
from quant_server.shared.database.repositories.base.hyper_repository_base import HyperRepositoryBase
from quant_server.shared.database.repositories.base.repository_base import RepositoryError


class FactorDataRepository(HyperRepositoryBase[FactorData]):
	"""
	因子数据Repository
	继承自HyperRepositoryBase，提供时序数据专用方法
	"""

	def __init__ (self, session: AsyncSession):
		"""
		初始化因子数据Repository

		Args:
			session: 数据库会话
		"""
		super().__init__(session, FactorData)
		self.time_column = "trade_date"  # 设置时间列名为trade_date

	async def create_factor_data (
			self,
			factor_name: str,
			ts_code: str,
			trade_date: datetime,
			factor_value: float,
			z_score: Optional[float] = None,
			percentile: Optional[float] = None,
			rank: Optional[int] = None,
			universe_rank: Optional[int] = None,
			metadata: Optional[Dict[str, Any]] = None
	) -> FactorData:
		"""
		创建单条因子数据

		Args:
			factor_name: 因子名称
			ts_code: 股票代码
			trade_date: 交易日
			factor_value: 因子值
			z_score: Z分数（可选）
			percentile: 百分位（可选）
			rank: 排名（可选）
			universe_rank: 全市场排名（可选）
			metadata: 元数据（可选）

		Returns:
			FactorData: 创建的因子数据对象

		Raises:
			RepositoryError: 创建失败时抛出
		"""
		try:
			factor_data = {
				'factor_name': factor_name,
				'ts_code': ts_code,
				'trade_date': trade_date,
				'factor_value': factor_value,
				'z_score': z_score,
				'percentile': percentile,
				'rank': rank,
				'universe_rank': universe_rank,
				'metadata': metadata or {}
			}
			return await self.create(factor_data)
		except Exception as e:
			raise RepositoryError(f"创建因子数据失败: {str(e)}")

	async def batch_insert_factor_data (
			self,
			factor_data_list: List[Dict[str, Any]],
			conflict_strategy: str = "upsert"
	) -> int:
		"""
		批量插入因子数据（使用超表优化）

		Args:
			factor_data_list: 因子数据列表
			conflict_strategy: 冲突处理策略（upsert/ignore/replace）

		Returns:
			int: 成功插入的记录数
		"""
		return await self.batch_insert(factor_data_list, conflict_strategy)

	async def get_factor_data (
			self,
			factor_name: str,
			ts_code: str,
			trade_date: datetime
	) -> Optional[FactorData]:
		"""
		获取指定因子、股票、日期的因子数据

		Args:
			factor_name: 因子名称
			ts_code: 股票代码
			trade_date: 交易日

		Returns:
			Optional[FactorData]: 因子数据对象或None
		"""
		try:
			stmt = select(FactorData).where(
				and_(
					FactorData.factor_name == factor_name,
					FactorData.ts_code == ts_code,
					FactorData.trade_date == trade_date
				)
			)
			result = await self.session.execute(stmt)
			return result.scalar_one_or_none()
		except Exception as e:
			raise RepositoryError(f"获取因子数据失败: {str(e)}")

	async def get_stock_factor_history (
			self,
			factor_name: str,
			ts_code: str,
			start_date: Optional[datetime] = None,
			end_date: Optional[datetime] = None,
			limit: int = 1000,
			order_desc: bool = True
	) -> List[FactorData]:
		"""
		获取单只股票的因子历史数据（时序查询）

		Args:
			factor_name: 因子名称
			ts_code: 股票代码
			start_date: 开始日期（可选）
			end_date: 结束日期（可选）
			limit: 限制记录数
			order_desc: 是否按时间降序

		Returns:
			List[FactorData]: 因子数据列表
		"""
		try:
			conditions = [
				FactorData.factor_name == factor_name,
				FactorData.ts_code == ts_code
			]

			if start_date:
				conditions.append(FactorData.trade_date >= start_date)

			if end_date:
				conditions.append(FactorData.trade_date <= end_date)

			stmt = select(FactorData).where(and_(*conditions))

			# 按时间排序
			if order_desc:
				stmt = stmt.order_by(desc(FactorData.trade_date))
			else:
				stmt = stmt.order_by(asc(FactorData.trade_date))

			stmt = stmt.limit(limit)
			result = await self.session.execute(stmt)
			return result.scalars().all()
		except Exception as e:
			raise RepositoryError(f"获取股票因子历史失败: {str(e)}")
	async def get_cross_sectional_data (
			self,
			factor_name: str,
			trade_date: datetime,
			universe: Optional[List[str]] = None,
			min_value: Optional[float] = None,
			max_value: Optional[float] = None,
			limit: int = 5000
	) -> List[FactorData]:
		"""
		获取横截面因子数据（同一时间点，不同股票）

		Args:
			factor_name: 因子名称
			trade_date: 交易日
			universe: 股票池（可选）
			min_value: 最小值过滤（可选）
			max_value: 最大值过滤（可选）
			limit: 限制记录数

		Returns:
			List[FactorData]: 横截面因子数据
		"""
		try:
			conditions = [
				FactorData.factor_name == factor_name,
				FactorData.trade_date == trade_date,
				FactorData.factor_value.isnot(None)
			]

			if universe:
				conditions.append(FactorData.ts_code.in_(universe))

			if min_value is not None:
				conditions.append(FactorData.factor_value >= min_value)

			if max_value is not None:
				conditions.append(FactorData.factor_value <= max_value)

			stmt = select(FactorData).where(and_(*conditions))
			stmt = stmt.order_by(desc(FactorData.factor_value)).limit(limit)
			result = await self.session.execute(stmt)
			return result.scalars().all()
		except Exception as e:
			raise RepositoryError(f"获取横截面数据失败: {str(e)}")

	async def get_time_series_data (
			self,
			factor_name: str,
			ts_codes: List[str],
			start_date: datetime,
			end_date: datetime,
			batch_size: int = 100
	) -> Dict[str, List[FactorData]]:
		"""
		获取时间序列因子数据（多只股票，时间范围）

		Args:
			factor_name: 因子名称
			ts_codes: 股票代码列表
			start_date: 开始日期
			end_date: 结束日期
			batch_size: 分批处理大小

		Returns:
			Dict[str, List[FactorData]]: 按股票代码分组的时间序列数据
		"""
		try:
			# 分批查询避免SQL语句过长
			result_dict = {}

			for i in range(0, len(ts_codes), batch_size):
				batch_codes = ts_codes[i:i + batch_size]

				stmt = select(FactorData).where(
					and_(
						FactorData.factor_name == factor_name,
						FactorData.ts_code.in_(batch_codes),
						FactorData.trade_date >= start_date,
						FactorData.trade_date <= end_date
					)
				).order_by(FactorData.ts_code, FactorData.trade_date)

				result = await self.session.execute(stmt)
				data_list = result.scalars().all()

				# 按股票代码分组
				for data in data_list:
					if data.ts_code not in result_dict:
						result_dict[data.ts_code] = []
					result_dict[data.ts_code].append(data)

			return result_dict
		except Exception as e:
			raise RepositoryError(f"获取时间序列数据失败: {str(e)}")
	async def get_latest_factor_data (
			self,
			factor_name: str,
			ts_code: Optional[str] = None,
			limit: int = 1
	) -> Optional[FactorData]:
		"""
		获取最新的因子数据

		Args:
			factor_name: 因子名称
			ts_code: 股票代码（可选）
			limit: 限制记录数

		Returns:
			Optional[FactorData]: 最新因子数据
		"""
		try:
			return await self.get_latest_record(symbol=ts_code, limit=limit)
		except Exception as e:
			raise RepositoryError(f"获取最新因子数据失败: {str(e)}")

	async def get_factor_universe (
			self,
			factor_name: str,
			trade_date: datetime,
			top_n: Optional[int] = None,
			bottom_n: Optional[int] = None,
			universe: Optional[List[str]] = None
	) -> List[FactorData]:
		"""
		获取因子排序的股票列表（用于构建因子投资组合）

		Args:
			factor_name: 因子名称
			t trade_date: 交易日
			top_n: 获取前N名（可选）
			bottom_n: 获取后N名（可选）
			universe: 股票池限制（可选）

		Returns:
			List[FactorData]: 排序后的因子数据
		"""
		try:
			conditions = [
				FactorData.factor_name == factor_name,
				FactorData.trade_date == trade_date,
				FactorData.factor_value.isnot(None)
			]

			if universe:
				conditions.append(FactorData.ts_code.in_(universe))

			stmt = select(FactorData).where(and_(*conditions))

			# 确定排序方向
			if bottom_n is not None:
				# 获取底部，按升序排序
				stmt = stmt.order_by(asc(FactorData.factor_value))
				limit_n = bottom_n
			else:
				# 默认获取顶部，按降序排序
				stmt = stmt.order_by(desc(FactorData.factor_value))
				limit_n = top_n

			if limit_n is not None:
				stmt = stmt.limit(limit_n)

			result = await self.session.execute(stmt)
			return result.scalars().all()
		except Exception as e:
			raise RepositoryError(f"获取因子排序列表失败: {str(e)}")

	async def update_factor_value (
			self,
			factor_name: str,
			ts_code: str,
			trade_date: datetime,
			factor_value: float,
			z_score: Optional[float] = None,
			percentile: Optional[float] = None,
			rank: Optional[int] = None,
			universe_rank: Optional[int] = None,
			metadata: Optional[Dict[str, Any]] = None
	) -> bool:
		"""
		更新因子数据

		Args:
			factor_name: 因子名称
			ts_code: 股票代码
			trade_date: 交易日
			factor_value: 因子值
			z_score: Z分数（可选）
			percentile: 百分位（可选）
			rank: 排名（可选）
			universe_rank: 全市场排名（可选）
			metadata: 元数据（可选）

		Returns:
			bool: 更新是否成功
		"""
		try:
			update_data = {'factor_value': factor_value}

			if z_score is not None:
				update_data['z_score'] = z_score

			if percentile is not None:
				update_data['percentile'] = percentile

			if rank is not None:
				update_data['rank'] = rank

			if universe_rank is not None:
				update_data['universe_rank'] = universe_rank

			if metadata is not None:
				update_data['metadata'] = metadata

			stmt = update(FactorData).where(
				and_(
					FactorData.factor_name == factor_name,
					FactorData.ts_code == ts_code,
					FactorData.trade_date == trade_date
				)
			).values(**update_data)

			result = await self.session.execute(stmt)
			await self.session.commit()
			return result.rowcount > 0
		except Exception as e:
			await self.session.rollback()
			raise RepositoryError(f"更新因子数据失败: {str(e)}")

	async def delete_factor_data_by_time_range (
			self,
			factor_name: str,
			start_date: datetime,
			end_date: datetime,
			ts_code: Optional[str] = None
	) -> int:
		"""
		删除时间范围内的因子数据（超表专用方法）

		Args:
			factor_name: 因子名称
			start_date: 开始日期
			end_date: 结束日期
			ts_code: 股票代码（可选）

		Returns:
			int: 删除的记录数
		"""
		try:
			conditions = [
				FactorData.factor_name == factor_name,
				FactorData.trade_date >= start_date,
				FactorData.trade_date <= end_date
			]

			if ts_code:
				conditions.append(FactorData.ts_code == ts_code)

			stmt = delete(FactorData).where(and_(*conditions))
			result = await self.session.execute(stmt)
			await self.session.commit()
			return result.rowcount or 0
		except Exception as e:
			await self.session.rollback()
			raise RepositoryError(f"删除因子数据失败: {str(e)}")

	async def get_factor_coverage (
			self,
			factor_name: str,
			start_date: datetime,
			end_date: datetime,
			universe: Optional[List[str]] = None
	) -> Dict[str, Any]:
		"""
		获取因子覆盖度统计

		Args:
			factor_name: 因子名称
			start_date: 开始日期
			end_date: 结束日期
			universe: 股票池（可选）

		Returns:
			Dict[str, Any]: 覆盖度统计信息
		"""
		try:
			conditions = [
				FactorData.factor_name == factor_name,
				FactorData.trade_date >= start_date,
				FactorData.trade_date <= end_date,
				FactorData.factor_value.isnot(None)
			]
			if universe:
				conditions.append(FactorData.ts_code.in_(universe))

			# 统计每日覆盖股票数
			stmt = select(
				FactorData.trade_date,
				func.count(FactorData.ts_code).label('stock_count'),
				func.avg(FactorData.factor_value).label('avg_value'),
				func.stddev(FactorData.factor_value).label('std_value'),
				func.min(FactorData.factor_value).label('min_value'),
				func.max(FactorData.factor_value).label('max_value')
			).where(
				and_(*conditions)
			).group_by(FactorData.trade_date).order_by(FactorData.trade_date)

			result = await self.session.execute(stmt)
			coverage_stats = []

			for row in result.all():
				coverage_stats.append({
					'trade_date': row[0],
					'stock_count': row[1],
					'avg_value': float(row[2]) if row[2] is not None else None,
					'std_value': float(row[3]) if row[3] is not None else None,
					'min_value': float(row[4]) if row[4] is not None else None,
					'max_value': float(row[5]) if row[5] is not None else None
				})

			# 统计总体覆盖度
			stmt_total = select(
				func.count(func.distinct(FactorData.ts_code)).label('total_stocks'),
				func.count(func.distinct(FactorData.trade_date)).label('total_dates'),
				func.count().label('total_records'),
				func.avg(FactorData.factor_value).label('overall_avg'),
				func.stddev(FactorData.factor_value).label('overall_std')
			).where(and_(*conditions))

			result_total = await self.session.execute(stmt_total)
			total_row = result_total.first()

			return {
				'factor_name': factor_name,
				'start_date': start_date,
				'end_date': end_date,
				'universe_size': len(universe) if universe else 'all',
				'total_stocks': total_row[0] if total_row else 0,
				'total_dates': total_row[1] if total_row else 0,
				'total_records': total_row[2] if total_row else 0,
				'overall_avg': float(total_row[3]) if total_row and total_row[3] is not None else None,
				'overall_std': float(total_row[4]) if total_row and total_row[4] is not None else None,
				'daily_coverage': coverage_stats
			}
		except Exception as e:
			raise RepositoryError(f"获取因子覆盖度失败: {str(e)}")

	async def calculate_factor_statistics (
			self,
			factor_name: str,
			trade_date: datetime,
			universe: Optional[List[str]] = None
	) -> Dict[str, Any]:
		"""
		计算因子统计特征

		Args:
			factor_name: 因子名称
			trade_date: 交易日
			universe: 股票池（可选）

		Returns:
			Dict[str, Any]: 因子统计特征
		"""
		try:
			conditions = [
				FactorData.factor_name == factor_name,
				FactorData.trade_date == trade_date,
				FactorData.factor_value.isnot(None)
			]

			if universe:
				conditions.append(FactorData.ts_code.in_(universe))

			stmt = select(
				func.count(FactorData.factor_value).label('count'),
				func.avg(FactorData.factor_value).label('mean'),
				func.stddev(FactorData.factor_value).label('std'),
				func.min(FactorData.factor_value).label('min'),
				func.max(FactorData.factor_value).label('max'),
				func.percentile_cont(0.25).within_group(FactorData.factor_value).label('q1'),
				func.percentile_cont(0.5).within_group(FactorData.factor_value).label('median'),
				func.percentile_cont(0.75).within_group(FactorData.factor_value).label('q3')
			).where(and_(*conditions))

			result = await self.session.execute(stmt)
			stats_row = result.first()

			if not stats_row or stats_row[0] == 0:
				return {
					'trade_date': trade_date,
					'factor_name': factor_name,
					'count': 0,
					'error': 'No data available'
				}

			# 计算偏度和峰度（可能需要数据库支持）
			# 这里使用子查询计算近似值
			mean_val = float(stats_row[1]) if stats_row[1] is not None else 0
			std_val = float(stats_row[2]) if stats_row[2] is not None else 0

			return {
				'trade_date': trade_date,
				'factor_name': factor_name,
				'count': stats_row[0],
				'mean': mean_val,
				'std': std_val,
				'min': float(stats_row[3]) if stats_row[3] is not None else None,
				'max': float(stats_row[4]) if stats_row[4] is not None else None,
				'q1': float(stats_row[5]) if stats_row[5] is not None else None,
				'median': float(stats_row[6]) if stats_row[6] is not None else None,
				'q3': float(stats_row[7]) if stats_row[7] is not None else None,
				'cv': std_val / mean_val if mean_val != 0 else None  # 变异系数
			}
		except Exception as e:
			raise RepositoryError(f"计算因子统计失败: {str(e)}")

	async def get_factor_correlation (
			self,
			factor_name1: str,
			factor_name2: str,
			trade_date: datetime,
			universe: Optional[List[str]] = None,
			min_pair_count: int = 10
	) -> Optional[float]:
		"""
		计算两个因子之间的相关系数

		Args:
			factor_name1: 第一个因子名称
			factor_name2: 第二个因子名称
			trade_date: 交易日
			universe: 股票池（可选）
			min_pair_count: 最小配对数据要求

		Returns:
			Optional[float]: 相关系数，None表示数据不足
		"""
		try:
			# 构建公共股票列表的查询
			subq1 = select(
				FactorData.ts_code,
				FactorData.factor_value.label('value1')
			).where(
				and_(
					FactorData.factor_name == factor_name1,
					FactorData.trade_date == trade_date
				)
			)

			if universe:
				subq1 = subq1.where(FactorData.ts_code.in_(universe))

			subq1 = subq1.subquery()

			subq2 = select(
				FactorData.ts_code,
				FactorData.factor_value.label('value2')
			).where(
				and_(
					FactorData.factor_name == factor_name2,
					FactorData.trade_date == trade_date
				)
			)

			if universe:
				subq2 = subq2.where(FactorData.ts_code.in_(universe))

			subq2 = subq2.subquery()

			# 使用SQL计算相关系数
			sql = text("""
                SELECT 
                    CORR(a.value1, b.value2) as correlation,
                    COUNT(*) as pair_count
                FROM :subq1 a
                JOIN :subq2 b ON a.ts_code = b.ts_code
                WHERE a.value1 IS NOT NULL AND b.value2 IS NOT NULL
            """).bindparams(
				subq1=subq1,
				subq2=subq2
			)

			result = await self.session.execute(sql)
			row = result.first()

			if row and row[1] >= min_pair_count:
				return float(row[0]) if row[0] is not None else None
			return None
		except Exception as e:
			raise RepositoryError(f"计算因子相关性失败: {str(e)}")

	async def get_factor_ic_analysis (
			self,
			factor_name: str,
			start_date: datetime,
			end_date: datetime,
			return_type: str = "next_day_return"
	) -> List[Dict[str, Any]]:
		"""
		获取因子IC分析结果（需要与收益率数据关联）

		Args:
			factor_name: 因子名称
			start_date: 开始日期
			end_date: 结束日期
			return_type: 收益率类型（next_day_return, next_week_return等）

		Returns:
			List[Dict[str, Any]]: IC分析结果列表
		"""
		try:
			# 这里需要与收益率表进行关联查询
			# 由于收益率表可能不存在，这里提供框架代码

			# 实际实现需要根据具体的收益率表结构进行调整
			# 这里返回空列表作为占位符

			# 示例SQL（需要根据实际表结构调整）：
			# SELECT
			#     f.trade_date,
			#     CORR(f.factor_value, r.return_value) as ic,
			#     COUNT(*) as stock_count
			# FROM factor_data f
			# JOIN stock_returns r ON f.ts_code = r.ts_code
			#     AND f.trade_date = r.trade_date
			# WHERE f.factor_name = :factor_name
			#     AND f.trade_date BETWEEN :start_date AND :end_date
			#     AND r.return_type = :return_type
			# GROUP BY f.trade_date
			# ORDER BY f.trade_date

			return []
		except Exception as e:
			raise RepositoryError(f"获取因子IC分析失败: {str(e)}")

	async def get_time_range_statistics (
			self,
			start_date: datetime,
			end_date: datetime,
			symbol: Optional[str] = None
	) -> Dict[str, Any]:
		"""
		获取时间范围内的统计信息（超表基类方法的重写）

		Args:
			start_date: 开始时间
			end_date: 结束时间
			symbol: 股票代码（可选）

		Returns:
			Dict[str, Any]: 统计信息
		"""
		return await self.get_statistics(start_date, end_date, symbol)

	async def get_available_factors(self) -> List[str]:
		"""
		获取系统中可用的因子名称列表

		Returns:
			List[str]: 因子名称列表
		"""
		try:
			stmt = select(
				func.distinct(FactorData.factor_name)
			).order_by(FactorData.factor_name)

			result = await self.session.execute(stmt)
			return [row[0] for row in result.all()]
		except Exception as e:
			raise RepositoryError(f"获取可用因子列表失败: {str(e)}")

	async def get_by_ts_code_and_date_range(
			self,
			ts_code: str,
			factor_name: str,
			start_date: datetime,
			end_date: datetime,
			limit: int = 1000,
			order_desc: bool = True
	) -> List[FactorData]:
		"""
		获取指定股票在时间范围内的因子数据（get_stock_factor_history的别名方法）

		Args:
			ts_code: 股票代码
			factor_name: 因子名称
			start_date: 开始日期
			end_date: 结束日期
			limit: 限制记录数
			order_desc: 是否按时间降序

		Returns:
			List[FactorData]: 因子数据列表
		"""
		return await self.get_stock_factor_history(
			factor_name=factor_name,
			ts_code=ts_code,
			start_date=start_date,
			end_date=end_date,
			limit=limit,
			order_desc=order_desc
		)