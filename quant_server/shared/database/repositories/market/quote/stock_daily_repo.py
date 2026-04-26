# -*- coding: utf-8 -*-
"""
股票日行情数据仓库
位置：quant_server/shared/database/repositories/market/quote/stock_daily_repo.py
职责：管理股票日线行情数据访问，继承HyperRepositoryBase实现时序数据优化操作
"""

from datetime import date, timedelta, datetime
from typing import List, Optional, Dict, Any

from sqlalchemy import select, and_, desc, func, text, case
from sqlalchemy.ext.asyncio import AsyncSession

from quant_server.shared.database.models.data_models import StockDaily, StockBasic
from quant_server.shared.database.repositories import RepositoryError
from quant_server.shared.database.repositories.base.hyper_repository_base import HyperRepositoryBase


class StockDailyRepository(HyperRepositoryBase[StockDaily]):
	"""
	股票日行情数据仓库 - 继承HyperRepositoryBase

	特性：
	1. 时序数据优化查询
	2. 支持按时间范围批量操作
	3. 提供股票日线专用分析方法
	4. 性能优化：批量插入、时间分片查询
	"""

	def __init__ (self, session: AsyncSession):
		"""
		初始化股票日行情Repository

		Args:
			session: 异步数据库会话
		"""
		super().__init__(session, StockDaily)
		self.time_column = "trade_date"  # 设置时序字段为trade_date

	# ==================== 基础查询方法 ====================

	async def get_by_code_and_date (
			self,
			ts_code: str,
			trade_date: date
	) -> Optional[StockDaily]:
		"""
		根据股票代码和交易日期获取日线数据

		Args:
			ts_code: 股票TS代码
			trade_date: 交易日期

		Returns:
			StockDaily对象或None（如果不存在）
		"""
		return await self.get_by(
			ts_code=ts_code,
			trade_date=trade_date
		)

	async def get_by_trade_date (
			self,
			trade_date: date,
			ts_code: Optional[str] = None
	) -> List[StockDaily]:
		"""
		根据交易日期获取日线数据

		Args:
			trade_date: 交易日期
			ts_code: 股票TS代码（可选，不指定则返回所有股票）

		Returns:
			指定交易日的日线数据列表
		"""
		try:
			query = select(self.model).where(
				self.model.trade_date == trade_date
			)

			if ts_code:
				query = query.where(self.model.ts_code == ts_code)

			result = await self.session.execute(query)
			return result.scalars().all()
		except Exception as e:
			raise RepositoryError(f"根据交易日期查询失败: {str(e)}")

	async def get_by_code_and_date_range (
			self,
			ts_code: str,
			start_date: datetime,
			end_date: datetime,
			limit: int = 1000
	) -> List[StockDaily]:
		"""
		根据股票代码和时间范围获取日线数据

		Args:
			ts_code: 股票TS代码
			start_date: 开始日期
			end_date: 结束日期
			limit: 最大返回记录数

		Returns:
			日线数据列表
		"""
		return await self.get_by_time_range(
			start_time=start_date,
			end_time=end_date,
			symbol=ts_code,
			limit=limit
		)

	async def get_quotes_by_date (self, trade_date: date) -> List[StockDaily]:
		"""
		根据交易日期获取所有股票的行情数据

		Args:
			trade_date: 交易日期

		Returns:
			指定交易日的所有股票行情数据
		"""
		return await self.get_by_trade_date(trade_date)

	async def get_quotes_by_date_range (
			self,
			start_date: str,
			end_date: str,
			limit: int = 10000
	) -> List[StockDaily]:
		"""
		根据日期范围获取行情数据

		Args:
			start_date: 开始日期（字符串格式）
			end_date: 结束日期（字符串格式）
			limit: 最大返回记录数

		Returns:
			行情数据列表
		"""
		try:
			# 转换日期格式
			start_dt = datetime.strptime(start_date, '%Y-%m-%d').date()
			end_dt = datetime.strptime(end_date, '%Y-%m-%d').date()

			# 查询指定日期范围内的数据
			query = select(self.model).where(
				self.model.trade_date.between(start_dt, end_dt)
			).limit(limit)

			result = await self.session.execute(query)
			return result.scalars().all()
		except Exception as e:
			raise RepositoryError(f"根据日期范围查询行情数据失败: {str(e)}")

	async def get_latest_by_code (
			self,
			ts_code: str,
			limit: int = 1
	) -> Optional[StockDaily]:
		"""
		获取指定股票的最新日线数据

		Args:
			ts_code: 股票TS代码
			limit: 返回记录数（默认1）

		Returns:
			最新日线数据或列表
		"""
		return await self.get_latest_record(symbol=ts_code, limit=limit)

	# ==================== 批量操作方法 ====================

	async def batch_insert_daily (
			self,
			records: List[Dict[str, Any]],
			conflict_strategy: str = "upsert"
	) -> int:
		"""
		批量插入日线数据

		Args:
			records: 日线数据记录列表
			conflict_strategy: 冲突处理策略（upsert/ignore/replace）

		Returns:
			成功插入的记录数
		"""
		return await self.batch_insert(records, conflict_strategy)

	async def delete_by_date_range (
			self,
			start_date: datetime,
			end_date: datetime,
			ts_code: Optional[str] = None
	) -> int:
		"""
		删除指定时间范围内的日线数据

		Args:
			start_date: 开始日期
			end_date: 结束日期
			ts_code: 股票代码（可选，不指定则删除所有）

		Returns:
			删除的记录数
		"""
		return await self.delete_by_time_range(
			start_time=start_date,
			end_time=end_date,
			symbol=ts_code
		)

	# ==================== 统计分析方法 ====================

	async def get_daily_statistics (
			self,
			ts_code: str,
			start_date: datetime,
			end_date: datetime
	) -> Dict[str, Any]:
		"""
		获取日线数据统计信息

		Args:
			ts_code: 股票代码
			start_date: 开始日期
			end_date: 结束日期

		Returns:
			统计信息字典
		"""
		stats = await self.get_statistics(start_date, end_date, ts_code)

		# 获取价格统计
		query = select(
			func.avg(StockDaily.close).label("avg_close"),
			func.max(StockDaily.close).label("max_close"),
			func.min(StockDaily.close).label("min_close"),
			func.stddev(StockDaily.close).label("std_close"),
			func.sum(StockDaily.vol).label("total_vol"),
			func.sum(StockDaily.amount).label("total_amount"),
			func.avg(StockDaily.pct_chg).label("avg_pct_chg")
		).where(
			and_(
				StockDaily.ts_code == ts_code,
				StockDaily.trade_date.between(start_date, end_date)
			)
		)

		result = await self.session.execute(query)
		price_stats = result.first()

		return {
			**stats,
			"price_statistics": {
				"avg_close": price_stats.avg_close,
				"max_close": price_stats.max_close,
				"min_close": price_stats.min_close,
				"std_close": price_stats.std_close,
				"total_volume": price_stats.total_vol,
				"total_amount": price_stats.total_amount,
				"avg_daily_return": price_stats.avg_pct_chg
			} if price_stats else {}
		}

	async def calculate_technical_indicators (
			self,
			ts_code: str,
			end_date: datetime,
			period: int = 20
	) -> Dict[str, Any]:
		"""
		计算技术指标

		Args:
			ts_code: 股票代码
			end_date: 截止日期
			period: 计算周期

		Returns:
			技术指标计算结果
		"""
		# 获取最近period天的数据
		start_date = end_date - timedelta(days=period * 2)  # 获取更多数据用于计算
		daily_data = await self.get_by_code_and_date_range(
			ts_code, start_date, end_date, limit=period * 2
		)

		if not daily_data:
			return {}

		# 按日期排序
		daily_data.sort(key=lambda x: x.trade_date)
		closes = [float(d.close) for d in daily_data]

		# 计算移动平均线
		if len(closes) >= period:
			ma_values = {
				"MA5": sum(closes[-5:]) / 5 if len(closes) >= 5 else None,
				"MA10": sum(closes[-10:]) / 10 if len(closes) >= 10 else None,
				"MA20": sum(closes[-20:]) / 20 if len(closes) >= 20 else None,
				"MA60": sum(closes[-60:]) / 60 if len(closes) >= 60 else None,
			}
		else:
			ma_values = {}

		# 计算收益率
		returns = []
		for i in range(1, len(closes)):
			if closes[i - 1] > 0:
				returns.append((closes[i] - closes[i - 1]) / closes[i - 1])

		return {
			"ts_code": ts_code,
			"end_date": end_date,
			"current_price": closes[-1] if closes else None,
			"moving_averages": ma_values,
			"return_statistics": {
				"mean_return": sum(returns) / len(returns) if returns else 0,
				"std_return": (sum([(r - sum(returns) / len(returns)) ** 2 for r in returns]) / len(
					returns)) ** 0.5 if returns else 0,
				"max_return": max(returns) if returns else 0,
				"min_return": min(returns) if returns else 0,
			} if returns else {},
			"data_points": len(closes)
		}

	async def get_price_volatility (
			self,
			ts_code: str,
			start_date: datetime,
			end_date: datetime,
			window: int = 20
	) -> List[Dict[str, Any]]:
		"""
		计算价格波动率

		Args:
			ts_code: 股票代码
			start_date: 开始日期
			end_date: 结束日期
			window: 滑动窗口大小

		Returns:
			波动率数据列表
		"""
		daily_data = await self.get_by_code_and_date_range(
			ts_code, start_date, end_date
		)

		if len(daily_data) < window:
			return []

		# 按日期排序
		daily_data.sort(key=lambda x: x.trade_date)

		volatility_data = []
		for i in range(window - 1, len(daily_data)):
			window_data = daily_data[i - window + 1:i + 1]
			prices = [float(d.close) for d in window_data]

			# 计算收益率
			returns = []
			for j in range(1, len(prices)):
				if prices[j - 1] > 0:
					returns.append((prices[j] - prices[j - 1]) / prices[j - 1])

			if returns:
				mean_return = sum(returns) / len(returns)
				variance = sum([(r - mean_return) ** 2 for r in returns]) / len(returns)
				volatility = variance ** 0.5 * (252 ** 0.5)  # 年化波动率

				volatility_data.append({
					"date": window_data[-1].trade_date,
					"volatility": volatility,
					"window_size": window,
					"price": prices[-1],
					"mean_return": mean_return
				})

		return volatility_data

	# ==================== 市场分析方法 ====================

	async def get_top_gainers (
			self,
			trade_date: date,
			limit: int = 10
	) -> List[Dict[str, Any]]:
		"""
		获取涨幅最大的股票

		Args:
			trade_date: 交易日期
			limit: 返回数量

		Returns:
			涨幅排行榜
		"""
		query = select(StockDaily).where(
			and_(
				StockDaily.trade_date == trade_date,
				StockDaily.pct_chg.isnot(None)
			)
		).order_by(desc(StockDaily.pct_chg)).limit(limit)

		result = await self.session.execute(query)
		daily_records = result.scalars().all()

		# 关联股票基本信息
		top_gainers = []
		for record in daily_records:
			# 查询股票基本信息
			stock_query = select(StockBasic).where(
				StockBasic.ts_code == record.ts_code
			)
			stock_result = await self.session.execute(stock_query)
			stock_info = stock_result.scalar_one_or_none()

			top_gainers.append({
				"ts_code": record.ts_code,
				"symbol": record.ts_code.split('.')[0] if '.' in record.ts_code else record.ts_code,
				"name": stock_info.name if stock_info else "",
				"close": record.close,
				"pct_chg": record.pct_chg,
				"volume": record.vol,
				"amount": record.amount,
				"change": record.change
			})

		return top_gainers

	async def get_top_losers (
			self,
			trade_date: date,
			limit: int = 10
	) -> List[Dict[str, Any]]:
		"""
		获取跌幅最大的股票

		Args:
			trade_date: 交易日期
			limit: 返回数量

		Returns:
			跌幅排行榜
		"""
		query = select(StockDaily).where(
			and_(
				StockDaily.trade_date == trade_date,
				StockDaily.pct_chg.isnot(None)
			)
		).order_by(StockDaily.pct_chg).limit(limit)

		result = await self.session.execute(query)
		daily_records = result.scalars().all()

		top_losers = []
		for record in daily_records:
			# 查询股票基本信息
			stock_query = select(StockBasic).where(
				StockBasic.ts_code == record.ts_code
			)
			stock_result = await self.session.execute(stock_query)
			stock_info = stock_result.scalar_one_or_none()

			top_losers.append({
				"ts_code": record.ts_code,
				"symbol": record.ts_code.split('.')[0] if '.' in record.ts_code else record.ts_code,
				"name": stock_info.name if stock_info else "",
				"close": record.close,
				"pct_chg": record.pct_chg,
				"volume": record.vol,
				"amount": record.amount,
				"change": record.change
			})

		return top_losers

	async def get_volume_leaders (
			self,
			trade_date: date,
			limit: int = 10
	) -> List[Dict[str, Any]]:
		"""
		获取成交量最大的股票

		Args:
			trade_date: 交易日期
			limit: 返回数量

		Returns:
			成交量排行榜
		"""
		query = select(StockDaily).where(
			StockDaily.trade_date == trade_date
		).order_by(desc(StockDaily.vol)).limit(limit)

		result = await self.session.execute(query)
		daily_records = result.scalars().all()

		volume_leaders = []
		for record in daily_records:
			# 查询股票基本信息
			stock_query = select(StockBasic).where(
				StockBasic.ts_code == record.ts_code
			)
			stock_result = await self.session.execute(stock_query)
			stock_info = stock_result.scalar_one_or_none()

			volume_leaders.append({
				"ts_code": record.ts_code,
				"symbol": record.ts_code.split('.')[0] if '.' in record.ts_code else record.ts_code,
				"name": stock_info.name if stock_info else "",
				"close": record.close,
				"volume": record.vol,
				"amount": record.amount,
				"pct_chg": record.pct_chg,
				"turnover_rate": None  # 可以从daily_basic表获取
			})

		return volume_leaders

	# ==================== 数据完整性检查 ====================

	async def check_data_integrity (
			self,
			ts_code: str,
			start_date: date,
			end_date: date
	) -> Dict[str, Any]:
		"""
		检查数据完整性

		Args:
			ts_code: 股票代码
			start_date: 开始日期
			end_date: 结束日期

		Returns:
			完整性检查结果
		"""
		# 计算理论交易日数量
		calendar_query = text("""
            SELECT COUNT(*) as trading_days
            FROM trade_calendar
            WHERE cal_date BETWEEN :start_date AND :end_date
              AND is_open = true
        """)

		calendar_result = await self.session.execute(
			calendar_query,
			{"start_date": start_date, "end_date": end_date}
		)
		expected_days = calendar_result.scalar() or 0

		# 获取实际数据数量
		actual_count = await self.count_by(
			ts_code=ts_code,
			trade_date__between=(start_date, end_date)
		)

		# 检查缺失日期
		date_query = text("""
            SELECT tc.cal_date as missing_date
            FROM trade_calendar tc
            LEFT JOIN stock_daily sd ON tc.cal_date = sd.trade_date AND sd.ts_code = :ts_code
            WHERE tc.cal_date BETWEEN :start_date AND :end_date
              AND tc.is_open = true
              AND sd.id IS NULL
            ORDER BY tc.cal_date
        """)

		date_result = await self.session.execute(
			date_query,
			{"ts_code": ts_code, "start_date": start_date, "end_date": end_date}
		)
		missing_dates = [row.missing_date for row in date_result.fetchall()]

		# 检查数据质量
		quality_query = select(
			func.count().label("total"),
			func.sum(case((StockDaily.close.is_(None), 1), else_=0)).label("null_close"),
			func.sum(case((StockDaily.vol <= 0, 1), else_=0)).label("zero_volume"),
			func.sum(case((StockDaily.amount <= 0, 1), else_=0)).label("zero_amount")
		).where(
			and_(
				StockDaily.ts_code == ts_code,
				StockDaily.trade_date.between(start_date, end_date)
			)
		)

		quality_result = await self.session.execute(quality_query)
		quality_stats = quality_result.first()

		return {
			"ts_code": ts_code,
			"date_range": {"start": start_date, "end": end_date},
			"expected_trading_days": expected_days,
			"actual_data_days": actual_count,
			"completeness_rate": actual_count / expected_days if expected_days > 0 else 0,
			"missing_dates": missing_dates,
			"missing_count": len(missing_dates),
			"data_quality": {
				"total_records": quality_stats.total if quality_stats else 0,
				"null_close_count": quality_stats.null_close if quality_stats else 0,
				"zero_volume_count": quality_stats.zero_volume if quality_stats else 0,
				"zero_amount_count": quality_stats.zero_amount if quality_stats else 0,
				"quality_score": (
					(quality_stats.total - quality_stats.null_close - quality_stats.zero_volume) /
					quality_stats.total if quality_stats and quality_stats.total > 0 else 0
				)
			}
		}

	# ==================== 性能优化方法 ====================

	async def create_partitioned_index (
			self,
			partition_column: str = "trade_date",
			index_type: str = "btree"
	) -> bool:
		"""
		创建分区索引以提高查询性能

		Args:
			partition_column: 分区列
			index_type: 索引类型

		Returns:
			是否成功创建索引
		"""
		try:
			# 这里实现具体的分区索引创建逻辑
			# 注意：具体实现取决于数据库类型（PostgreSQL, MySQL等）

			# 示例：创建按年分区的索引
			index_sql = text(f"""
                CREATE INDEX IF NOT EXISTS idx_stock_daily_partitioned 
                ON stock_daily USING {index_type} (ts_code, {partition_column})
                WHERE {partition_column} >= '2020-01-01';
            """)

			await self.session.execute(index_sql)
			await self.session.commit()
			return True

		except Exception as e:
			await self.session.rollback()
			print(f"创建分区索引失败: {str(e)}")
			return False

	async def optimize_table_storage (self) -> Dict[str, Any]:
		"""
		优化表存储结构

		Returns:
			优化结果
		"""
		try:
			# 这里实现表存储优化逻辑
			# 例如：重建索引、清理碎片等

			optimize_queries = [
				"VACUUM ANALYZE stock_daily;",
				"REINDEX TABLE stock_daily;",
				"CLUSTER stock_daily USING idx_stock_daily_trade_date;"
			]

			results = {}
			for query in optimize_queries:
				try:
					await self.session.execute(text(query))
					results[query] = "success"
				except Exception as e:
					results[query] = f"failed: {str(e)}"

			await self.session.commit()
			return {"status": "completed", "results": results}

		except Exception as e:
			await self.session.rollback()
			return {"status": "failed", "error": str(e)}