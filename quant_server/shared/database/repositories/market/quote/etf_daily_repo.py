# -*- coding: utf-8 -*-
"""
ETF日行情数据仓库
位置：quant_server/shared/database/repositories/market/quote/etf_daily_repo.py
职责：管理ETF日线行情数据访问，继承HyperRepositoryBase实现ETF专用操作
"""

from datetime import date, timedelta, datetime
from typing import List, Optional, Dict, Any

from sqlalchemy import select, desc, text
from sqlalchemy.ext.asyncio import AsyncSession

from shared.database.models.data_models import EtfDaily, EtfBasic, IndexDaily
from shared.database.repositories import RepositoryError
from shared.database.repositories.base.hyper_repository_base import HyperRepositoryBase


class EtfDailyRepository(HyperRepositoryBase[EtfDaily]):
	"""
	ETF日行情数据仓库 - 继承HyperRepositoryBase

	特性：
	1. ETF日线数据专用操作
	2. 支持ETF与基准指数对比分析
	3. 提供ETF专用分析方法（折溢价、跟踪误差等）
	4. 性能优化：ETF批量操作
	"""

	def __init__ (self, session: AsyncSession):
		"""
		初始化ETF日行情Repository

		Args:
			session: 异步数据库会话
		"""
		super().__init__(session, EtfDaily)
		self.time_column = "trade_date"  # 设置时序字段为trade_date

	# ==================== 基础查询方法 ====================

	async def get_by_code_and_date (
			self,
			ts_code: str,
			trade_date: date
	) -> Optional[EtfDaily]:
		"""
		根据ETF代码和日期获取日线数据

		Args:
			ts_code: ETF TS代码
			trade_date: 交易日期

		Returns:
			EtfDaily对象或None
		"""
		return await self.get_by(
			ts_code=ts_code,
			trade_date=trade_date
		)

	async def get_by_trade_date (
			self,
			trade_date: date,
			ts_code: Optional[str] = None
	) -> List[EtfDaily]:
		"""
		根据交易日期获取ETF日线数据

		Args:
			trade_date: 交易日期
			ts_code: ETF TS代码（可选，不指定则返回所有ETF）

		Returns:
			指定交易日的ETF日线数据列表
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
			raise RepositoryError(f"根据交易日期查询ETF日线数据失败: {str(e)}")

	async def get_by_code_and_date_range (
			self,
			ts_code: str,
			start_date: datetime,
			end_date: datetime,
			limit: int = 1000
	) -> List[EtfDaily]:
		"""
		根据ETF代码和时间范围获取日线数据

		Args:
			ts_code: ETF TS代码
			start_date: 开始日期
			end_date: 结束日期
			limit: 最大返回记录数

		Returns:
			ETF日线数据列表
		"""
		return await self.get_by_time_range(
			start_time=start_date,
			end_time=end_date,
			symbol=ts_code,
			limit=limit
		)

	async def get_existing_trade_dates (
			self,
			ts_code: str,
			start_date=None,
			end_date=None,
	) -> set:
		"""
		批量获取已有交易日期集合（一次查询替代 N 次逐条查询）
		"""
		try:
			query = select(self.model.trade_date).where(
				self.model.ts_code == ts_code
			)
			if start_date:
				query = query.where(self.model.trade_date >= start_date)
			if end_date:
				query = query.where(self.model.trade_date <= end_date)
			result = await self.session.execute(query)
			return {row.trade_date for row in result.fetchall()}
		except Exception as e:
			raise RepositoryError(f"批量获取已有交易日期失败: {str(e)}")

	async def get_latest_trade_date (
			self,
			ts_code: str
	) -> Optional[date]:
		"""
		获取指定标的的最新数据日期（用于增量同步日期推断）
		"""
		try:
			query = select(self.model.trade_date).where(
				self.model.ts_code == ts_code
			).order_by(desc(self.model.trade_date)).limit(1)
			result = await self.session.execute(query)
			row = result.first()
			return row.trade_date if row else None
		except Exception as e:
			raise RepositoryError(f"获取最新数据日期失败: {str(e)}")

	async def get_latest_trade_dates_batch(
			self,
			ts_codes: list
	) -> dict:
		"""批量获取多只ETF的最新交易日（一次 SQL 查询）。"""
		from sqlalchemy import func

		if not ts_codes:
			return {}

		query = (
			select(self.model.ts_code, func.max(self.model.trade_date))
			.where(self.model.ts_code.in_(ts_codes))
			.group_by(self.model.ts_code)
		)
		result = await self.session.execute(query)
		mapping = {row[0]: row[1] for row in result.fetchall()}
		for code in ts_codes:
			if code not in mapping:
				mapping[code] = None
		return mapping

	async def get_latest_by_code (
			self,
			ts_code: str,
			limit: int = 1
	) -> Optional[EtfDaily]:
		"""
		获取指定ETF的最新日线数据

		Args:
			ts_code: ETF TS代码
			limit: 返回记录数

		Returns:
			最新ETF日线数据或列表
		"""
		return await self.get_latest_record(symbol=ts_code, limit=limit)

	# ==================== ETF特有分析方法 ====================

	async def calculate_premium_discount (
			self,
			ts_code: str,
			trade_date: date
	) -> Optional[Dict[str, Any]]:
		"""
		计算ETF折溢价率

		Args:
			ts_code: ETF代码
			trade_date: 交易日期

		Returns:
			折溢价分析结果或None
		"""
		# 获取ETF日线数据
		etf_data = await self.get_by_code_and_date(ts_code, trade_date)
		if not etf_data:
			return None

		# 获取ETF基本信息（包含跟踪指数）
		etf_basic_query = select(EtfBasic).where(
			EtfBasic.ts_code == ts_code
		)
		etf_basic_result = await self.session.execute(etf_basic_query)
		etf_basic = etf_basic_result.scalar_one_or_none()

		if not etf_basic or not etf_basic.index_code:
			return None

		# 获取指数日线数据（通过ORM查询IndexDaily）
		index_query = select(IndexDaily.close).where(
			IndexDaily.ts_code == etf_basic.index_code,
			IndexDaily.trade_date == trade_date
		)
		index_result = await self.session.execute(index_query)
		index_close = index_result.scalar_one_or_none()

		if index_close is None:
			return None

		index_price = float(index_close)
		etf_price = float(etf_data.close)

		# 计算折溢价率
		if index_price > 0:
			premium_discount = (etf_price - index_price) / index_price * 100
		else:
			premium_discount = 0

		return {
			"ts_code": ts_code,
			"trade_date": trade_date,
			"etf_price": etf_price,
			"index_price": index_price,
			"premium_discount_rate": premium_discount,
			"absolute_difference": etf_price - index_price,
			"index_code": etf_basic.index_code,
			"index_name": etf_basic.index_name
		}

	async def analyze_tracking_error (
			self,
			ts_code: str,
			start_date: datetime,
			end_date: datetime
	) -> Dict[str, Any]:
		"""
		分析ETF跟踪误差

		Args:
			ts_code: ETF代码
			start_date: 开始日期
			end_date: 结束日期

		Returns:
			跟踪误差分析结果
		"""
		# 获取ETF日线数据
		etf_data = await self.get_by_code_and_date_range(
			ts_code, start_date, end_date
		)

		if not etf_data:
			return {}

		# 获取ETF基本信息
		etf_basic_query = select(EtfBasic).where(
			EtfBasic.ts_code == ts_code
		)
		etf_basic_result = await self.session.execute(etf_basic_query)
		etf_basic = etf_basic_result.scalar_one_or_none()

		if not etf_basic or not etf_basic.index_code:
			return {"error": "无法获取ETF跟踪指数信息"}

		# 获取指数日线数据
		index_query = text("""
            SELECT trade_date, close FROM index_daily 
            WHERE ts_code = :index_code 
              AND trade_date BETWEEN :start_date AND :end_date
            ORDER BY trade_date
        """)

		index_result = await self.session.execute(
			index_query,
			{"index_code": etf_basic.index_code, "start_date": start_date, "end_date": end_date}
		)
		index_rows = index_result.fetchall()

		if not index_rows:
			return {"error": "无法获取指数日线数据"}

		# 创建数据字典
		etf_dict = {d.trade_date: float(d.close) for d in etf_data}
		index_dict = {row.trade_date: float(row.close) for row in index_rows}

		# 找出共同交易日
		common_dates = sorted(set(etf_dict.keys()) & set(index_dict.keys()))

		if len(common_dates) < 2:
			return {"error": "共同交易日数据不足"}

		# 计算日收益率和跟踪误差
		etf_returns = []
		index_returns = []
		differences = []

		for i in range(1, len(common_dates)):
			date_prev = common_dates[i - 1]
			date_curr = common_dates[i]

			etf_prev = etf_dict[date_prev]
			etf_curr = etf_dict[date_curr]

			index_prev = index_dict[date_prev]
			index_curr = index_dict[date_curr]

			if etf_prev > 0 and index_prev > 0:
				etf_return = (etf_curr - etf_prev) / etf_prev
				index_return = (index_curr - index_prev) / index_prev

				etf_returns.append(etf_return)
				index_returns.append(index_return)
				differences.append(etf_return - index_return)

		if not differences:
			return {}

		# 计算跟踪误差
		mean_difference = sum(differences) / len(differences)
		tracking_error = (sum((d - mean_difference) ** 2 for d in differences) / len(differences)) ** 0.5

		# 年化跟踪误差
		annual_tracking_error = tracking_error * (252 ** 0.5)

		# 计算信息比率（超额收益/跟踪误差）
		if tracking_error > 0:
			information_ratio = mean_difference / tracking_error
		else:
			information_ratio = 0

		# 计算相关系数
		if len(etf_returns) >= 2:
			mean_etf = sum(etf_returns) / len(etf_returns)
			mean_index = sum(index_returns) / len(index_returns)

			covariance = sum((etf_returns[i] - mean_etf) * (index_returns[i] - mean_index)
			                 for i in range(len(etf_returns))) / len(etf_returns)

			var_etf = sum((r - mean_etf) ** 2 for r in etf_returns) / len(etf_returns)
			var_index = sum((r - mean_index) ** 2 for r in index_returns) / len(index_returns)

			correlation = covariance / ((var_etf ** 0.5) * (var_index ** 0.5)) if var_etf > 0 and var_index > 0 else 0
		else:
			correlation = 0

		return {
			"ts_code": ts_code,
			"index_code": etf_basic.index_code,
			"index_name": etf_basic.index_name,
			"analysis_period": {
				"start_date": start_date,
				"end_date": end_date,
				"trading_days": len(common_dates),
				"common_days": len(common_dates)
			},
			"tracking_metrics": {
				"daily_tracking_error": tracking_error * 100,
				"annual_tracking_error": annual_tracking_error * 100,
				"avg_daily_difference": mean_difference * 100,
				"information_ratio": information_ratio,
				"correlation": correlation,
				"r_squared": correlation ** 2
			},
			"return_statistics": {
				"etf_total_return": (etf_dict[common_dates[-1]] - etf_dict[common_dates[0]]) / etf_dict[
					common_dates[0]] * 100,
				"index_total_return": (index_dict[common_dates[-1]] - index_dict[common_dates[0]]) / index_dict[
					common_dates[0]] * 100,
				"excess_return": ((etf_dict[common_dates[-1]] - etf_dict[common_dates[0]]) / etf_dict[common_dates[0]] -
				                  (index_dict[common_dates[-1]] - index_dict[common_dates[0]]) / index_dict[
					                  common_dates[0]]) * 100,
				"etf_avg_daily_return": (sum(etf_returns) / len(etf_returns)) * 100 if etf_returns else 0,
				"index_avg_daily_return": (sum(index_returns) / len(index_returns)) * 100 if index_returns else 0
			},
			"summary": {
				"status": "excellent" if annual_tracking_error < 2 else
				"good" if annual_tracking_error < 5 else
				"fair" if annual_tracking_error < 10 else "poor",
				"assessment": f"年化跟踪误差{annual_tracking_error * 100:.2f}%，"
				              f"与基准指数相关性{correlation:.3f}"
			}
		}

	async def analyze_etf_liquidity (
			self,
			ts_code: str,
			trade_date: datetime,
			lookback_days: int = 20
	) -> Dict[str, Any]:
		"""
		分析ETF流动性

		Args:
			ts_code: ETF代码
			trade_date: 分析日期
			lookback_days: 回溯天数

		Returns:
			流动性分析结果
		"""
		start_date = trade_date - timedelta(days=lookback_days)

		etf_data = await self.get_by_code_and_date_range(
			ts_code, start_date, trade_date
		)

		if not etf_data:
			return {}

		# 计算流动性指标
		volumes = [int(d.vol) for d in etf_data]
		amounts = [float(d.amount) for d in etf_data]
		closes = [float(d.close) for d in etf_data]

		avg_volume = sum(volumes) / len(volumes) if volumes else 0
		avg_amount = sum(amounts) / len(amounts) if amounts else 0
		avg_price = sum(closes) / len(closes) if closes else 0

		# 计算波动率
		if len(closes) >= 2:
			returns = []
			for i in range(1, len(closes)):
				if closes[i - 1] > 0:
					returns.append((closes[i] - closes[i - 1]) / closes[i - 1])

			if returns:
				mean_return = sum(returns) / len(returns)
				volatility = (sum((r - mean_return) ** 2 for r in returns) / len(returns)) ** 0.5
				annual_volatility = volatility * (252 ** 0.5)
			else:
				volatility = annual_volatility = 0
		else:
			volatility = annual_volatility = 0

		# 计算换手率 — 基于回溯期95%分位成交量估算流通份额
		# EtfBasic表无total_share字段，以高分位成交量作为流通份额代理变量
		if volumes and len(volumes) >= 5:
			sorted_volumes = sorted(volumes)
			float_idx = min(int(len(sorted_volumes) * 0.95), len(sorted_volumes) - 1)
			estimated_float = sorted_volumes[float_idx]
			if estimated_float > 0:
				turnover_rates = [v / estimated_float * 100 for v in volumes]
				avg_turnover_rate = sum(turnover_rates) / len(turnover_rates)
				recent_turnover_rate = turnover_rates[-1]
				max_turnover_rate = max(turnover_rates)
				min_turnover_rate = min(turnover_rates)
			else:
				avg_turnover_rate = recent_turnover_rate = max_turnover_rate = min_turnover_rate = 0.0
				estimated_float = 0
		else:
			avg_turnover_rate = recent_turnover_rate = max_turnover_rate = min_turnover_rate = 0.0
			estimated_float = 0

		# Amihud非流动性指标 ILLIQ = avg(|return| / dollar_volume) × 10^6
		if len(closes) >= 2 and amounts:
			amihud_vals = []
			for i in range(1, len(closes)):
				if closes[i-1] > 0 and amounts[i] > 0:
					daily_ret = abs((closes[i] - closes[i-1]) / closes[i-1])
					dollar_vol = amounts[i] * 1000  # amount单位为千元，转为元
					amihud_vals.append(daily_ret / dollar_vol)
			amihud_illiquidity = (sum(amihud_vals) / len(amihud_vals)) * 1e6 if amihud_vals else 0.0
		else:
			amihud_illiquidity = 0.0

		return {
			"ts_code": ts_code,
			"trade_date": trade_date,
			"analysis_period": {
				"start_date": start_date,
				"end_date": trade_date,
				"days": lookback_days,
				"trading_days": len(etf_data)
			},
			"volume_metrics": {
				"avg_daily_volume": avg_volume,
				"avg_daily_amount": avg_amount,
				"max_volume": max(volumes) if volumes else 0,
				"min_volume": min(volumes) if volumes else 0,
				"volume_volatility": (max(volumes) - min(volumes)) / avg_volume * 100 if avg_volume > 0 else 0
			},
			"turnover_metrics": {
				"estimated_float": estimated_float,
				"avg_turnover_rate": round(avg_turnover_rate, 4),
				"recent_turnover_rate": round(recent_turnover_rate, 4),
				"max_turnover_rate": round(max_turnover_rate, 4),
				"min_turnover_rate": round(min_turnover_rate, 4)
			},
			"price_metrics": {
				"avg_price": avg_price,
				"current_price": closes[-1] if closes else 0,
				"price_volatility": volatility * 100,
				"annual_price_volatility": annual_volatility * 100
			},
			"liquidity_assessment": {
				"volume_liquidity": "high" if avg_volume > 1000000 else
				"medium" if avg_volume > 100000 else "low",
				"amount_liquidity": "high" if avg_amount > 10000000 else
				"medium" if avg_amount > 1000000 else "low",
				"stability": "stable" if volatility < 0.02 else
				"moderate" if volatility < 0.05 else "volatile",
				"amihud_illiquidity": round(amihud_illiquidity, 8),
				"amihud_assessment": "high" if amihud_illiquidity < 0.1 else
				"moderate" if amihud_illiquidity < 1.0 else "low"
			}
		}

		# ==================== 批量查询方法 ====================

		async def get_batch_by_date_range(
				self,
				symbols: List[str],
				start_date: date,
				end_date: date,
				limit: int = 100_000,
		) -> List[EtfDaily]:
			"""
			批量获取多只 ETF 在时间范围内的日线数据（一次 SQL IN 查询）。
			返回按 trade_date ASC, ts_code ASC 排序。
			"""
			try:
				query = (
					select(self.model)
					.where(
						self.model.ts_code.in_(symbols),
						self.model.trade_date.between(start_date, end_date),
					)
					.order_by(self.model.trade_date, self.model.ts_code)
					.limit(limit)
				)
				result = await self.session.execute(query)
				return list(result.scalars().all())
			except Exception as e:
				raise RepositoryError(f"批量查询 ETF 日线数据失败: {e}")

		async def get_batch_by_trade_date(
				self,
				trade_date: date,
				symbols: Optional[List[str]] = None,
		) -> List[EtfDaily]:
			"""
			批量获取指定交易日多只 ETF 的日线数据。
			"""
			try:
				query = select(self.model).where(self.model.trade_date == trade_date)
				if symbols:
					query = query.where(self.model.ts_code.in_(symbols))
				query = query.order_by(self.model.ts_code)
				result = await self.session.execute(query)
				return list(result.scalars().all())
			except Exception as e:
				raise RepositoryError(f"批量查询交易日 ETF 日线数据失败: {e}")

	# ==================== 批量操作方法 ====================

	async def batch_insert_etf_daily (
			self,
			records: List[Dict[str, Any]],
			conflict_strategy: str = "upsert"
	) -> int:
		"""
		批量插入ETF日线数据

		Args:
			records: ETF日线数据记录列表
			conflict_strategy: 冲突处理策略

		Returns:
			成功插入的记录数
		"""
		return await self.batch_insert(records, conflict_strategy)

	async def get_etf_performance_ranking (
			self,
			trade_date: date,
			category: Optional[str] = None,
			limit: int = 20
	) -> List[Dict[str, Any]]:
		"""
		获取ETF表现排名

		Args:
			trade_date: 交易日期
			category: ETF类别（可选）
			limit: 返回数量

		Returns:
			ETF表现排名列表
		"""
		# 基础查询
		query = select(EtfDaily).where(
			EtfDaily.trade_date == trade_date
		).order_by(desc(EtfDaily.pct_chg)).limit(limit)

		result = await self.session.execute(query)
		etf_records = result.scalars().all()

		# 关联ETF基本信息
		ranking = []
		for record in etf_records:
			# 查询ETF基本信息
			etf_basic_query = select(EtfBasic).where(
				EtfBasic.ts_code == record.ts_code
			)
			etf_basic_result = await self.session.execute(etf_basic_query)
			etf_basic = etf_basic_result.scalar_one_or_none()

			# 筛选类别
			if category and etf_basic and etf_basic.etf_type != category:
				continue

			ranking.append({
				"rank": len(ranking) + 1,
				"ts_code": record.ts_code,
				"name": etf_basic.csname if etf_basic else "",
				"etf_type": etf_basic.etf_type if etf_basic else "",
				"close": record.close,
				"pct_chg": record.pct_chg,
				"volume": record.vol,
				"amount": record.amount,
				"index_code": etf_basic.index_code if etf_basic else "",
				"index_name": etf_basic.index_name if etf_basic else ""
			})

			if len(ranking) >= limit:
				break

		return ranking
