# -*- coding: utf-8 -*-
"""
ETF分钟行情数据仓库
位置：quant_server/shared/database/repositories/market/quote/etf_minute_repo.py
职责：管理ETF分钟级行情数据访问，继承HyperRepositoryBase实现ETF高频数据操作
"""

from datetime import datetime, date, timedelta
from typing import List, Optional, Dict, Any

from sqlalchemy import select, and_, desc, text, delete
from sqlalchemy.ext.asyncio import AsyncSession

from core import BusinessException
from shared.database.models.data_models import EtfMinute, EtfBasic
from shared.database.repositories.base.hyper_repository_base import HyperRepositoryBase
from shared.database.repositories.types import TimeRange


class EtfMinuteRepository(HyperRepositoryBase[EtfMinute]):
	"""
	ETF分钟行情数据仓库 - 继承HyperRepositoryBase

	特性：
	1. ETF高频数据优化查询（分钟级）
	2. 支持多频率数据（1min/5min/15min/30min/60min）
	3. 提供ETF分钟数据专用分析方法
	4. 性能优化：高频数据批量操作
	"""

	def __init__ (self, session: AsyncSession):
		"""
		初始化ETF分钟行情Repository

		Args:
			session: 异步数据库会话
		"""
		super().__init__(session, EtfMinute)
		self.time_column = "trade_time"  # 设置时序字段为trade_time

	# ==================== 基础查询方法 ====================

	async def get_by_code_and_time (
			self,
			ts_code: str,
			trade_time: datetime,
			freq: str = "1min"
	) -> Optional[EtfMinute]:
		"""
		根据ETF代码、时间和频率获取分钟数据

		Args:
			ts_code: ETF TS代码
			trade_time: 交易时间
			freq: 频率（1min/5min/15min/30min/60min）

		Returns:
			EtfMinute对象或None
		"""
		return await self.get_by(
			ts_code=ts_code,
			trade_time=trade_time,
			freq=freq
		)

	async def get_by_code_and_time_range (
			self,
			ts_code: str,
			start_time: datetime,
			end_time: datetime,
			freq: str = "1min",
			limit: int = 1000
	) -> List[EtfMinute]:
		"""
		根据ETF代码和时间范围获取分钟数据

		Args:
			ts_code: ETF TS代码
			start_time: 开始时间
			end_time: 结束时间
			freq: 频率
			limit: 最大返回记录数

		Returns:
			ETF分钟数据列表
		"""
		query = select(self.model).where(
			and_(
				self.model.ts_code == ts_code,
				self.model.freq == freq,
				self.model.trade_time.between(start_time, end_time)
			)
		).order_by(self.model.trade_time).limit(limit)

		result = await self.session.execute(query)
		return result.scalars().all()

	async def get_intraday_data (
			self,
			ts_code: str,
			trade_date: date,
			freq: str = "1min"
	) -> List[EtfMinute]:
		"""
		获取指定交易日的日内分钟数据

		Args:
			ts_code: ETF TS代码
			trade_date: 交易日期
			freq: 频率

		Returns:
			日内分钟数据列表
		"""
		start_time = datetime.combine(trade_date, datetime.min.time())
		end_time = datetime.combine(trade_date, datetime.max.time())

		return await self.get_by_code_and_time_range(
			ts_code, start_time, end_time, freq
		)

	async def get_latest_minute (
			self,
			ts_code: str,
			freq: str = "1min",
			limit: int = 1
	) -> Optional[EtfMinute]:
		"""
		获取指定ETF的最新分钟数据

		Args:
			ts_code: ETF TS代码
			freq: 频率
			limit: 返回记录数

		Returns:
			最新分钟数据或列表
		"""
		query = select(self.model).where(
			and_(
				self.model.ts_code == ts_code,
				self.model.freq == freq
			)
		).order_by(desc(self.model.trade_time)).limit(limit)

		result = await self.session.execute(query)
		if limit == 1:
			return result.scalar_one_or_none()
		return result.scalars().all()

	# ==================== 批量操作方法 ====================

	async def batch_insert_minutes (
			self,
			records: List[Dict[str, Any]],
			freq: str = "1min",
			conflict_strategy: str = "upsert"
	) -> int:
		"""
		批量插入ETF分钟数据

		Args:
			records: 分钟数据记录列表
			freq: 频率
			conflict_strategy: 冲突处理策略

		Returns:
			成功插入的记录数
		"""
		# 为所有记录设置频率
		for record in records:
			record['freq'] = freq

		return await self.batch_insert(records, conflict_strategy)

	async def delete_by_time_range (
			self,
			start_time: datetime,
			end_time: datetime,
			ts_code: Optional[str] = None,
			freq: Optional[str] = None
	) -> int:
		"""
		删除时间范围内的ETF分钟数据

		Args:
			start_time: 开始时间
			end_time: 结束时间
			ts_code: ETF代码（可选）
			freq: 频率（可选）

		Returns:
			删除的记录数
		"""
		conditions = [
			self.model.trade_time >= start_time,
			self.model.trade_time <= end_time
		]

		if ts_code:
			conditions.append(self.model.ts_code == ts_code)

		if freq:
			conditions.append(self.model.freq == freq)

		query = delete(self.model).where(and_(*conditions))

		result = await self.session.execute(query) # type: ignore
		await self.session.commit()
		return result.rowcount or 0

	# ==================== 数据转换方法 ====================

	async def resample_frequency (
			self,
			ts_code: str,
			start_time: datetime,
			end_time: datetime,
			source_freq: str = "1min",
			target_freq: str = "5min"
	) -> List[Dict[str, Any]]:
		"""
		重新采样到不同频率

		Args:
			ts_code: ETF代码
			start_time: 开始时间
			end_time: 结束时间
			source_freq: 源频率
			target_freq: 目标频率

		Returns:
			重采样后的数据列表
		"""
		# 获取源频率数据
		source_data = await self.get_by_code_and_time_range(
			ts_code, start_time, end_time, source_freq
		)

		if not source_data:
			return []

		# 按时间排序
		source_data.sort(key=lambda x: x.trade_time)

		# 确定目标频率的分钟数
		freq_minutes = {
			"1min": 1,
			"5min": 5,
			"15min": 15,
			"30min": 30,
			"60min": 60
		}

		target_minutes = freq_minutes.get(target_freq, 5)

		# 重采样逻辑
		resampled_data = []
		current_group = []

		for record in source_data:
			if not current_group:
				current_group.append(record)
				continue

			# 检查是否开始新的分组
			time_diff = (record.trade_time - current_group[0].trade_time).total_seconds() / 60

			if time_diff >= target_minutes:
				# 处理当前分组
				if current_group:
					resampled_record = self._aggregate_etf_minute_group(current_group, target_freq)
					resampled_data.append(resampled_record)

				current_group = [record]
			else:
				current_group.append(record)

		# 处理最后一组
		if current_group:
			resampled_record = self._aggregate_etf_minute_group(current_group, target_freq)
			resampled_data.append(resampled_record)

		return resampled_data

	@staticmethod
	def _aggregate_etf_minute_group (
			group: List[EtfMinute],
			target_freq: str
	) -> Dict[str, Any]:
		"""
		聚合ETF分钟数据组

		Args:
			group: 分钟数据组
			target_freq: 目标频率

		Returns:
			聚合后的数据字典
		"""
		if not group:
			return {}

		# 按时间排序
		group.sort(key=lambda x: x.trade_time)

		opens = [float(r.open) for r in group]
		highs = [float(r.high) for r in group]
		lows = [float(r.low) for r in group]
		closes = [float(r.close) for r in group]
		volumes = [int(r.vol) for r in group]
		amounts = [float(r.amount) for r in group]

		return {
			"ts_code": group[0].ts_code,
			"freq": target_freq,
			"trade_time": group[-1].trade_time,  # 使用最后一根K线的时间
			"open": opens[0] if opens else 0,
			"high": max(highs) if highs else 0,
			"low": min(lows) if lows else 0,
			"close": closes[-1] if closes else 0,
			"vol": sum(volumes),
			"amount": sum(amounts),
			"group_count": len(group),
			"start_time": group[0].trade_time,
			"end_time": group[-1].trade_time
		}

	# ==================== ETF特有分析方法 ====================

	async def analyze_intraday_premium (
			self,
			ts_code: str,
			trade_date: date,
			freq: str = "1min"
	) -> List[Dict[str, Any]]:
		"""
		分析日内折溢价率

		Args:
			ts_code: ETF代码
			trade_date: 交易日期
			freq: 频率

		Returns:
			日内折溢价率分析结果
		"""
		# 获取ETF日内数据
		etf_data = await self.get_intraday_data(ts_code, trade_date, freq)
		if not etf_data:
			return []

		# 获取ETF基本信息（包含跟踪指数）
		etf_basic_query = select(EtfBasic).where(
			EtfBasic.ts_code == ts_code
		)
		etf_basic_result = await self.session.execute(etf_basic_query)
		etf_basic = etf_basic_result.scalar_one_or_none()

		if not etf_basic or not etf_basic.index_code:
			return []

		# 获取指数分钟数据（这里需要假设有相应的指数分钟数据表）
		# 由于实际表结构未知，这里提供框架逻辑
		premium_data = []

		# 批量查询对应时点的指数分钟数据（若index_minute表存在）
		index_prices = {}
		try:
			from sqlalchemy import text
			index_data = await self.session.execute(
				text("SELECT trade_time, close FROM index_minute "
				     "WHERE ts_code = :idx_code AND trade_date = :td AND freq = :f"),
				{"idx_code": etf_basic.index_code, "td": trade_date, "f": freq}
			)
			for row in index_data.fetchall():
				index_prices[row.trade_time] = float(row.close)
		except BusinessException:
			pass  # index_minute 表可能不存在，降级处理

		for etf_record in etf_data:
			etf_price = float(etf_record.close)
			# 查询对应时间的指数价格，若无数据则标注为不可用
			index_price = index_prices.get(etf_record.trade_time)

			if index_price and index_price > 0:
				premium_rate = (etf_price - index_price) / index_price * 100
			else:
				premium_rate = None  # 指数数据不可用时折溢价率标记为空

			premium_data.append({
				"time": etf_record.trade_time,
				"etf_price": etf_price,
				"index_price": index_price,
				"premium_rate": premium_rate,
				"volume": etf_record.vol,
				"amount": etf_record.amount,
				"freq": freq
			})

		return premium_data

	async def calculate_intraday_liquidity (
			self,
			ts_code: str,
			trade_date: date,
			freq: str = "1min"
	) -> Dict[str, Any]:
		"""
		计算日内流动性指标

		Args:
			ts_code: ETF代码
			trade_date: 交易日期
			freq: 频率

		Returns:
			流动性分析结果
		"""
		intraday_data = await self.get_intraday_data(ts_code, trade_date, freq)

		if not intraday_data:
			return {}

		# 计算流动性指标
		volumes = [int(d.vol) for d in intraday_data]
		amounts = [float(d.amount) for d in intraday_data]
		price_changes = []

		for i in range(1, len(intraday_data)):
			prev_close = float(intraday_data[i - 1].close)
			curr_close = float(intraday_data[i].close)
			if prev_close > 0:
				price_changes.append(abs(curr_close - prev_close) / prev_close)

		# 基础统计
		total_volume = sum(volumes)
		total_amount = sum(amounts)
		avg_volume = total_volume / len(volumes) if volumes else 0
		avg_amount = total_amount / len(amounts) if amounts else 0

		# 计算流动性得分
		liquidity_score = 0
		if avg_amount > 0:
			# 基于成交金额的流动性评分
			if avg_amount > 10000000:  # 1000万
				liquidity_score = 100
			elif avg_amount > 1000000:  # 100万
				liquidity_score = 80
			elif avg_amount > 100000:  # 10万
				liquidity_score = 60
			elif avg_amount > 10000:  # 1万
				liquidity_score = 40
			else:
				liquidity_score = 20

		# 计算价格冲击成本 — Amihud日内非流动性指标
		# λ_i = |r_i| / dollar_vol_i，price_impact = avg(λ_i) × 10^7 (% per 10万元)
		if price_changes and avg_amount > 0:
			amihud_vals = []
			for i, pc in enumerate(price_changes):
				idx = i + 1  # price_changes[i] 对应 intraday_data[i+1]
				minute_amount = amounts[idx]
				if minute_amount > 0:
					dollar_vol = minute_amount * 1000  # amount单位为千元，转为元
					amihud_vals.append(pc / dollar_vol)
			if amihud_vals:
				amihud_avg = sum(amihud_vals) / len(amihud_vals)
				# 标准化：每10万元成交额的预期价格冲击百分比
				price_impact = amihud_avg * 1e7
				amihud_intraday = amihud_avg * 1e6  # 常规Amihud量级(×10^6)
				valid_intervals = len(amihud_vals)
			else:
				amihud_avg = 0
				price_impact = 0
				amihud_intraday = 0
				valid_intervals = 0
		else:
			amihud_intraday = 0
			price_impact = 0
			valid_intervals = 0

		return {
			"ts_code": ts_code,
			"trade_date": trade_date,
			"freq": freq,
			"summary": {
				"total_volume": total_volume,
				"total_amount": total_amount,
				"avg_volume": avg_volume,
				"avg_amount": avg_amount,
				"trading_periods": len(intraday_data),
				"liquidity_score": liquidity_score,
				"liquidity_level": self._get_liquidity_level(liquidity_score)
			},
			"volume_analysis": {
				"max_volume": max(volumes) if volumes else 0,
				"min_volume": min(volumes) if volumes else 0,
				"volume_volatility": (max(volumes) - min(volumes)) / avg_volume * 100 if avg_volume > 0 else 0
			},
			"price_analysis": {
				"price_impact": round(price_impact, 6),
				"impact_level": "low" if price_impact < 0.1 else "medium" if price_impact < 0.5 else "high",
				"amihud_intraday": round(amihud_intraday, 6),
				"valid_intervals": valid_intervals,
				"total_intervals": len(price_changes),
				"avg_price_change_bps": round(sum(price_changes) / len(price_changes) * 10000, 2) if price_changes else 0
			},
			"time_distribution": self._analyze_time_distribution(intraday_data, volumes)
		}

	@staticmethod
	def _get_liquidity_level (score: float) -> str:
		"""获取流动性等级"""
		if score >= 80:
			return "excellent"
		elif score >= 60:
			return "good"
		elif score >= 40:
			return "fair"
		else:
			return "poor"

	@staticmethod
	def _analyze_time_distribution (
			data: List[EtfMinute],
			volumes: List[int]
	) -> Dict[str, Any]:
		"""分析成交量时间分布"""
		if not data or not volumes:
			return {}

		# 按小时分组
		hour_groups = {}
		for record, volume in zip(data, volumes):
			hour = record.trade_time.hour
			if hour not in hour_groups:
				hour_groups[hour] = {"volume": 0, "count": 0, "start_time": record.trade_time}
			hour_groups[hour]["volume"] += volume
			hour_groups[hour]["count"] += 1

		# 找出活跃时段
		sorted_hours = sorted(hour_groups.items(), key=lambda x: x[1]["volume"], reverse=True)

		return {
			"total_hours": len(hour_groups),
			"hourly_distribution": {
				hour: {
					"volume": info["volume"],
					"count": info["count"],
					"avg_volume": info["volume"] / info["count"] if info["count"] > 0 else 0
				}
				for hour, info in hour_groups.items()
			},
			"active_periods": [
				{
					"hour": hour,
					"volume": info["volume"],
					"percentage": info["volume"] / sum(volumes) * 100 if sum(volumes) > 0 else 0
				}
				for hour, info in sorted_hours[:3]  # 最活跃的3个时段
			]
		}

	async def detect_arbitrage_opportunities (
			self,
			ts_code: str,
			trade_date: date,
			threshold: float = 0.5
	) -> List[Dict[str, Any]]:
		"""
		检测套利机会

		Args:
			ts_code: ETF代码
			trade_date: 交易日期
			threshold: 套利阈值（百分比）

		Returns:
			套利机会列表
		"""
		# 获取日内数据
		intraday_data = await self.get_intraday_data(ts_code, trade_date, "1min")
		if len(intraday_data) < 2:
			return []

		# 获取ETF基本信息
		etf_basic_query = select(EtfBasic).where(
			EtfBasic.ts_code == ts_code
		)
		etf_basic_result = await self.session.execute(etf_basic_query)
		etf_basic = etf_basic_result.scalar_one_or_none()

		if not etf_basic or not etf_basic.index_code:
			return []

		# 获取对应时点的指数价格用于精确套利分析
		index_prices = {}
		try:
			from sqlalchemy import text
			index_data = await self.session.execute(
				text("SELECT trade_time, close FROM index_minute "
				     "WHERE ts_code = :idx_code AND trade_date = :td AND freq = '1min'"),
				{"idx_code": etf_basic.index_code, "td": trade_date}
			)
			for row in index_data.fetchall():
				index_prices[row.trade_time] = float(row.close)
		except BusinessException:
			pass

		# 若分钟级指数数据不可用，尝试用日线指数价格作为基准
		index_daily_price = None
		if not index_prices:
			try:
				from sqlalchemy import text
				idx_result = await self.session.execute(
					text("SELECT close FROM index_daily WHERE ts_code = :idx_code AND trade_date = :td"),
					{"idx_code": etf_basic.index_code, "td": trade_date}
				)
				idx_row = idx_result.fetchone()
				if idx_row:
					index_daily_price = float(idx_row.close)
			except BusinessException:
				pass

		# 分析套利机会
		opportunities = []

		for i in range(1, len(intraday_data)):
			current_record = intraday_data[i]
			prev_record = intraday_data[i - 1]

			current_price = float(current_record.close)
			prev_price = float(prev_record.close)

			if prev_price > 0:
				price_change = (current_price - prev_price) / prev_price * 100

				# 获取对应时点指数价格：优先分钟数据 → 日线数据 → 跳过
				index_price = index_prices.get(current_record.trade_time, index_daily_price)
				if index_price is None:
					continue  # 无指数基准数据，跳过该时点

				deviation = (current_price - index_price) / index_price * 100

				if abs(deviation) > threshold:
					opportunities.append({
						"time": current_record.trade_time,
						"etf_price": current_price,
						"index_price": index_price,
						"deviation": deviation,
						"volume": current_record.vol,
						"opportunity_type": "premium" if deviation > 0 else "discount",
						"magnitude": abs(deviation),
						"price_change_since_prev": price_change,
						"volume_change": current_record.vol - prev_record.vol
					})

		# 按套利幅度排序
		opportunities.sort(key=lambda x: x["magnitude"], reverse=True)

		return opportunities

	# ==================== 统计分析方法 ====================

	async def get_minute_statistics (
			self,
			ts_code: str,
			start_time: datetime,
			end_time: datetime,
			freq: str = "1min"
	) -> Dict[str, Any]:
		"""
		获取分钟数据统计信息

		Args:
			ts_code: ETF代码
			start_time: 开始时间
			end_time: 结束时间
			freq: 频率

		Returns:
			统计信息字典
		"""
		data = await self.get_by_code_and_time_range(
			ts_code, start_time, end_time, freq
		)

		if not data:
			return {}

		# 计算基础统计
		closes = [float(d.close) for d in data]
		volumes = [int(d.vol) for d in data]
		amounts = [float(d.amount) for d in data]

		# 价格统计
		if closes:
			avg_price = sum(closes) / len(closes)
			max_price = max(closes)
			min_price = min(closes)
			price_range = max_price - min_price

			# 计算收益率
			returns = []
			for i in range(1, len(closes)):
				if closes[i - 1] > 0:
					returns.append((closes[i] - closes[i - 1]) / closes[i - 1])

			if returns:
				avg_return = sum(returns) / len(returns)
				volatility = (sum((r - avg_return) ** 2 for r in returns) / len(returns)) ** 0.5
				annual_volatility = volatility * (252 * 240 ** 0.5)  # 年化波动率（假设240个分钟交易日）
			else:
				avg_return = volatility = annual_volatility = 0
		else:
			avg_price = max_price = min_price = price_range = 0
			avg_return = volatility = annual_volatility = 0

		# 成交量统计
		if volumes:
			avg_volume = sum(volumes) / len(volumes)
			total_volume = sum(volumes)
		else:
			avg_volume = total_volume = 0

		# 成交额统计
		if amounts:
			avg_amount = sum(amounts) / len(amounts)
			total_amount = sum(amounts)
		else:
			avg_amount = total_amount = 0

		# 时间统计
		times = [d.trade_time for d in data]
		time_range = TimeRange(
			start=min(times) if times else None,
			end=max(times) if times else None
		)

		return {
			"ts_code": ts_code,
			"freq": freq,
			"time_range": {
				"start": start_time,
				"end": end_time,
				"data_start": time_range.start,
				"data_end": time_range.end
			},
			"data_points": len(data),
			"price_statistics": {
				"avg_price": avg_price,
				"max_price": max_price,
				"min_price": min_price,
				"price_range": price_range,
				"avg_return": avg_return * 100,
				"volatility": volatility * 100,
				"annual_volatility": annual_volatility * 100
			},
			"volume_statistics": {
				"total_volume": total_volume,
				"avg_volume": avg_volume,
				"max_volume": max(volumes) if volumes else 0,
				"min_volume": min(volumes) if volumes else 0
			},
			"amount_statistics": {
				"total_amount": total_amount,
				"avg_amount": avg_amount,
				"max_amount": max(amounts) if amounts else 0,
				"min_amount": min(amounts) if amounts else 0
			}
		}

	# ==================== 批量操作方法 ====================

	async def batch_upsert_minutes (
			self,
			records: List[Dict[str, Any]],
			freq: str = "1min"
	) -> int:
		"""
		批量插入或更新分钟数据

		Args:
			records: 分钟数据记录列表
			freq: 频率

		Returns:
			成功处理的记录数
		"""
		# 为所有记录设置频率
		for record in records:
			record['freq'] = freq

		# 使用基类的批量插入方法
		return await self.batch_insert(records, "upsert")

	async def cleanup_old_data (
			self,
			retention_days: int = 30,
			freq: Optional[str] = None
	) -> Dict[str, Any]:
		"""
		清理过期的高频数据

		Args:
			retention_days: 数据保留天数
			freq: 频率（可选，不指定则清理所有频率）

		Returns:
			清理结果
		"""
		try:
			cutoff_time = datetime.now() - timedelta(days=retention_days)

			conditions = [self.model.trade_time < cutoff_time]
			if freq:
				conditions.append(self.model.freq == freq)

			query = delete(self.model).where(and_(*conditions))

			result = await self.session.execute(query) # type: ignore
			deleted_count = result.rowcount

			# 清理碎片
			vacuum_query = text("VACUUM ANALYZE etf_minute;")
			await self.session.execute(vacuum_query)

			await self.session.commit()

			return {
				"status": "completed",
				"deleted_records": deleted_count,
				"cutoff_time": cutoff_time,
				"retention_days": retention_days,
				"freq_cleaned": freq or "all"
			}

		except Exception as e:
			await self.session.rollback()
			return {"status": "failed", "error": str(e)}

	# ==================== 辅助方法 ====================

	async def get_available_frequencies (
			self,
			ts_code: str,
			start_time: datetime,
			end_time: datetime
	) -> List[str]:
		"""
		获取可用的数据频率

		Args:
			ts_code: ETF代码
			start_time: 开始时间
			end_time: 结束时间

		Returns:
			可用频率列表
		"""
		query = select(self.model.freq).where(
			and_(
				self.model.ts_code == ts_code,
				self.model.trade_time.between(start_time, end_time)
			)
		).distinct()

		result = await self.session.execute(query)
		frequencies = result.scalars().all()

		return list(frequencies)

	async def check_data_gaps (
			self,
			ts_code: str,
			start_time: datetime,
			end_time: datetime,
			freq: str = "1min",
			expected_interval: int = 1
	) -> List[Dict[str, Any]]:
		"""
		检查数据间隙

		Args:
			ts_code: ETF代码
			start_time: 开始时间
			end_time: 结束时间
			freq: 频率
			expected_interval: 预期间隔（分钟）

		Returns:
			数据间隙列表
		"""
		data = await self.get_by_code_and_time_range(
			ts_code, start_time, end_time, freq, limit=10000
		)

		if len(data) < 2:
			return []

		# 按时间排序
		data.sort(key=lambda x: x.trade_time)

		gaps = []

		for i in range(1, len(data)):
			time_diff = (data[i].trade_time - data[i - 1].trade_time).total_seconds() / 60

			# 检查是否超过预期间隔
			if time_diff > expected_interval * 1.5:  # 允许50%的误差
				gaps.append({
					"gap_start": data[i - 1].trade_time,
					"gap_end": data[i].trade_time,
					"gap_duration_minutes": time_diff,
					"expected_interval": expected_interval,
					"missing_records": int(time_diff / expected_interval) - 1
				})

		return gaps