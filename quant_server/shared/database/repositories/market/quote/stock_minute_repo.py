# -*- coding: utf-8 -*-
"""
股票分钟行情数据仓库
位置：quant_server/shared/database/repositories/market/quote/stock_minute_repo.py
职责：管理股票分钟级行情数据访问，继承HyperRepositoryBase实现高频数据优化操作
"""

from typing import List, Optional, Dict, Any, Tuple
from datetime import datetime, date, timedelta
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, and_, or_, desc, func, text, between

from quant_server.shared.database.repositories.base.hyper_repository_base import HyperRepositoryBase
from quant_server.shared.database.models.data_models import StockMinutes


class StockMinuteRepository(HyperRepositoryBase[StockMinutes]):
	"""
	股票分钟行情数据仓库 - 继承HyperRepositoryBase

	特性：
	1. 高频数据优化查询（分钟级）
	2. 支持多频率数据（1min/5min/15min/30min/60min）
	3. 提供分钟数据专用分析方法
	4. 性能优化：分时查询、批量聚合
	"""

	def __init__ (self, session: AsyncSession):
		"""
		初始化股票分钟行情Repository

		Args:
			session: 异步数据库会话
		"""
		super().__init__(session, StockMinutes)
		self.time_column = "trade_time"  # 设置时序字段为trade_time

	# ==================== 基础查询方法 ====================

	async def get_by_code_and_time (
			self,
			ts_code: str,
			trade_time: datetime,
			freq: str = "1min"
	) -> Optional[StockMinutes]:
		"""
		根据股票代码、时间和频率获取分钟数据

		Args:
			ts_code: 股票TS代码
			trade_time: 交易时间
			freq: 频率（1min/5min/15min/30min/60min）

		Returns:
			StockMinutes对象或None
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
	) -> List[StockMinutes]:
		"""
		根据股票代码和时间范围获取分钟数据

		Args:
			ts_code: 股票TS代码
			start_time: 开始时间
			end_time: 结束时间
			freq: 频率
			limit: 最大返回记录数

		Returns:
			分钟数据列表
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
	) -> List[StockMinutes]:
		"""
		获取指定交易日的日内分钟数据

		Args:
			ts_code: 股票TS代码
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
	) -> Optional[StockMinutes]:
		"""
		获取指定股票的最新分钟数据

		Args:
			ts_code: 股票TS代码
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
		批量插入分钟数据

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
			ts_code: 股票代码
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
					resampled_record = self._aggregate_minute_group(current_group, target_freq)
					resampled_data.append(resampled_record)

				current_group = [record]
			else:
				current_group.append(record)

		# 处理最后一组
		if current_group:
			resampled_record = self._aggregate_minute_group(current_group, target_freq)
			resampled_data.append(resampled_record)

		return resampled_data

	def _aggregate_minute_group (
			self,
			group: List[StockMinutes],
			target_freq: str
	) -> Dict[str, Any]:
		"""
		聚合分钟数据组

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

	# ==================== 技术分析方法 ====================

	async def calculate_intraday_vwap (
			self,
			ts_code: str,
			trade_date: date,
			freq: str = "1min"
	) -> List[Dict[str, Any]]:
		"""
		计算日内VWAP（成交量加权平均价格）

		Args:
			ts_code: 股票代码
			trade_date: 交易日期
			freq: 频率

		Returns:
			VWAP数据列表
		"""
		intraday_data = await self.get_intraday_data(ts_code, trade_date, freq)

		if not intraday_data:
			return []

		# 按时间排序
		intraday_data.sort(key=lambda x: x.trade_time)

		vwap_data = []
		cumulative_amount = 0
		cumulative_volume = 0

		for record in intraday_data:
			price = float(record.close)
			volume = int(record.vol)
			amount = float(record.amount)

			cumulative_amount += amount
			cumulative_volume += volume

			if cumulative_volume > 0:
				vwap = cumulative_amount / cumulative_volume
			else:
				vwap = price

			vwap_data.append({
				"time": record.trade_time,
				"price": price,
				"volume": volume,
				"amount": amount,
				"vwap": vwap,
				"deviation": price - vwap,  # 价格与VWAP的偏差
				"deviation_pct": (price - vwap) / vwap * 100 if vwap > 0 else 0
			})

		return vwap_data

	async def calculate_intraday_rsi (
			self,
			ts_code: str,
			trade_date: date,
			period: int = 14,
			freq: str = "1min"
	) -> List[Dict[str, Any]]:
		"""
		计算日内RSI（相对强弱指数）

		Args:
			ts_code: 股票代码
			trade_date: 交易日期
			period: RSI周期
			freq: 频率

		Returns:
			RSI数据列表
		"""
		intraday_data = await self.get_intraday_data(ts_code, trade_date, freq)

		if len(intraday_data) < period + 1:
			return []

		# 按时间排序
		intraday_data.sort(key=lambda x: x.trade_time)
		prices = [float(d.close) for d in intraday_data]

		rsi_data = []

		for i in range(period, len(prices)):
			window_prices = prices[i - period:i + 1]

			# 计算价格变化
			changes = []
			for j in range(1, len(window_prices)):
				changes.append(window_prices[j] - window_prices[j - 1])

			# 计算平均上涨和平均下跌
			gains = [c for c in changes if c > 0]
			losses = [abs(c) for c in changes if c < 0]

			avg_gain = sum(gains) / period if gains else 0
			avg_loss = sum(losses) / period if losses else 0

			# 计算RSI
			if avg_loss == 0:
				rsi = 100
			else:
				rs = avg_gain / avg_loss
				rsi = 100 - (100 / (1 + rs))

			rsi_data.append({
				"time": intraday_data[i].trade_time,
				"price": prices[i],
				"rsi": rsi,
				"avg_gain": avg_gain,
				"avg_loss": avg_loss,
				"rs": rs if avg_loss > 0 else float('inf')
			})

		return rsi_data

	async def detect_intraday_patterns (
			self,
			ts_code: str,
			trade_date: date,
			freq: str = "1min"
	) -> Dict[str, Any]:
		"""
		检测日内交易模式

		Args:
			ts_code: 股票代码
			trade_date: 交易日期
			freq: 频率

		Returns:
			交易模式检测结果
		"""
		intraday_data = await self.get_intraday_data(ts_code, trade_date, freq)

		if not intraday_data:
			return {"patterns": [], "summary": {}}

		# 按时间排序
		intraday_data.sort(key=lambda x: x.trade_time)

		patterns = []

		# 检测模式：需要至少3根K线
		for i in range(2, len(intraday_data)):
			pattern = self._detect_candle_pattern(
				intraday_data[i - 2],
				intraday_data[i - 1],
				intraday_data[i]
			)

			if pattern:
				patterns.append({
					"time": intraday_data[i].trade_time,
					"pattern": pattern,
					"price": float(intraday_data[i].close)
				})

		# 分析日内走势
		opens = [float(d.open) for d in intraday_data]
		closes = [float(d.close) for d in intraday_data]
		highs = [float(d.high) for d in intraday_data]
		lows = [float(d.low) for d in intraday_data]

		if opens and closes:
			open_price = opens[0]
			close_price = closes[-1]
			intraday_high = max(highs) if highs else 0
			intraday_low = min(lows) if lows else 0

			summary = {
				"date": trade_date,
				"ts_code": ts_code,
				"open": open_price,
				"close": close_price,
				"high": intraday_high,
				"low": intraday_low,
				"change": close_price - open_price,
				"change_pct": (close_price - open_price) / open_price * 100 if open_price > 0 else 0,
				"range": intraday_high - intraday_low,
				"range_pct": (intraday_high - intraday_low) / open_price * 100 if open_price > 0 else 0,
				"volume": sum([int(d.vol) for d in intraday_data]),
				"amount": sum([float(d.amount) for d in intraday_data]),
				"data_points": len(intraday_data),
				"patterns_detected": len(patterns)
			}
		else:
			summary = {}

		return {
			"patterns": patterns,
			"summary": summary
		}

	def _detect_candle_pattern (
			self,
			first,
			second,
			third
	) -> Optional[str]:
		"""
		检测K线模式

		Args:
			first: 第一根K线
			second: 第二根K线
			third: 第三根K线

		Returns:
			模式名称或None
		"""
		# 简单的模式检测逻辑
		# 这里可以实现更复杂的模式识别

		o1, h1, l1, c1 = float(first.open), float(first.high), float(first.low), float(first.close)
		o2, h2, l2, c2 = float(second.open), float(second.high), float(second.low), float(second.close)
		o3, h3, l3, c3 = float(third.open), float(third.high), float(third.low), float(third.close)

		# 早晨之星
		if (c1 < o1 and  # 第一根阴线
				abs(c2 - o2) / ((o2 + c2) / 2) < 0.01 and  # 第二根十字星
				c3 > o3 and  # 第三根阳线
				c3 > (o1 + c1) / 2):  # 收盘价超过前日中点
			return "morning_star"

		# 黄昏之星
		if (c1 > o1 and  # 第一根阳线
				abs(c2 - o2) / ((o2 + c2) / 2) < 0.01 and  # 第二根十字星
				c3 < o3 and  # 第三根阴线
				c3 < (o1 + c1) / 2):  # 收盘价低于前日中点
			return "evening_star"

		# 三只乌鸦
		if (c1 < o1 and c2 < o2 and c3 < o3 and  # 连续三根阴线
				o1 > c2 and o2 > c3):  # 连续低开
			return "three_black_crows"

		# 三个白兵
		if (c1 > o1 and c2 > o2 and c3 > o3 and  # 连续三根阳线
				c1 < o2 and c2 < o3):  # 连续高开
			return "three_white_soldiers"

		return None

	# ==================== 成交量分析 ====================

	async def analyze_volume_profile (
			self,
			ts_code: str,
			trade_date: date,
			price_bins: int = 20,
			freq: str = "1min"
	) -> Dict[str, Any]:
		"""
		分析成交量分布（Volume Profile）

		Args:
			ts_code: 股票代码
			trade_date: 交易日期
			price_bins: 价格分箱数量
			freq: 频率

		Returns:
			成交量分布分析结果
		"""
		intraday_data = await self.get_intraday_data(ts_code, trade_date, freq)

		if not intraday_data:
			return {}

		# 获取价格范围
		prices = []
		volumes = []

		for record in intraday_data:
			prices.extend([float(record.high), float(record.low), float(record.close)])
			volumes.append(int(record.vol))

		if not prices:
			return {}

		min_price = min(prices)
		max_price = max(prices)
		total_volume = sum(volumes)

		# 创建价格分箱
		price_range = max_price - min_price
		bin_size = price_range / price_bins if price_range > 0 else 0

		volume_profile = {}

		for i in range(price_bins):
			bin_low = min_price + i * bin_size
			bin_high = min_price + (i + 1) * bin_size
			bin_key = f"{bin_low:.2f}-{bin_high:.2f}"
			volume_profile[bin_key] = 0

		# 计算每个价格区间的成交量
		for record in intraday_data:
			price = float(record.close)
			volume = int(record.vol)

			# 找到对应的价格区间
			if bin_size > 0:
				bin_index = int((price - min_price) / bin_size)
				bin_index = min(bin_index, price_bins - 1)

				bin_low = min_price + bin_index * bin_size
				bin_high = min_price + (bin_index + 1) * bin_size
				bin_key = f"{bin_low:.2f}-{bin_high:.2f}"

				volume_profile[bin_key] = volume_profile.get(bin_key, 0) + volume

		# 计算POC（Point of Control）
		poc_bin = max(volume_profile.items(), key=lambda x: x[1]) if volume_profile else (None, 0)

		# 计算VAH和VAL（Value Area High/Low）
		sorted_bins = sorted(volume_profile.items(), key=lambda x: x[1], reverse=True)
		cumulative_volume = 0
		value_area_bins = []

		for bin_key, volume in sorted_bins:
			cumulative_volume += volume
			value_area_bins.append(bin_key)

			if cumulative_volume >= total_volume * 0.7:  # 70%的价值区间
				break

		# 解析价格区间
		def parse_bin (bin_str):
			if '-' in bin_str:
				low, high = bin_str.split('-')
				return float(low), float(high)
			return 0, 0

		value_area_prices = []
		for bin_key in value_area_bins:
			low, high = parse_bin(bin_key)
			value_area_prices.extend([low, high])

		vah = max(value_area_prices) if value_area_prices else 0
		val = min(value_area_prices) if value_area_prices else 0

		poc_low, poc_high = parse_bin(poc_bin[0]) if poc_bin[0] else (0, 0)
		poc_price = (poc_low + poc_high) / 2

		return {
			"ts_code": ts_code,
			"trade_date": trade_date,
			"price_range": {
				"min": min_price,
				"max": max_price,
				"range": price_range
			},
			"volume_profile": volume_profile,
			"poc": {
				"price_band": poc_bin[0],
				"price": poc_price,
				"volume": poc_bin[1],
				"volume_percent": poc_bin[1] / total_volume * 100 if total_volume > 0 else 0
			},
			"value_area": {
				"high": vah,
				"low": val,
				"width": vah - val,
				"bins": value_area_bins,
				"volume_percent": cumulative_volume / total_volume * 100 if total_volume > 0 else 0
			},
			"summary": {
				"total_volume": total_volume,
				"price_bins": price_bins,
				"bin_size": bin_size,
				"data_points": len(intraday_data)
			}
		}

	# ==================== 性能优化方法 ====================

	async def create_time_partitions (self) -> Dict[str, Any]:
		"""
		创建时间分区以优化高频数据查询性能

		Returns:
			分区创建结果
		"""
		try:
			# 这里实现时间分区创建逻辑
			# 注意：具体实现取决于数据库类型

			partition_queries = [
				"""
				CREATE TABLE IF NOT EXISTS stock_minutes_y2024 PARTITION OF stock_minutes
				FOR VALUES FROM ('2024-01-01') TO ('2025-01-01');
				""",
				"""
				CREATE INDEX IF NOT EXISTS idx_stock_minutes_y2024_ts_code 
				ON stock_minutes_y2024 (ts_code);
				""",
				"""
				CREATE INDEX IF NOT EXISTS idx_stock_minutes_y2024_time 
				ON stock_minutes_y2024 (trade_time);
				""",
				"""
				CREATE INDEX IF NOT EXISTS idx_stock_minutes_y2024_freq 
				ON stock_minutes_y2024 (freq);
				"""
			]

			results = {}
			for query in partition_queries:
				try:
					await self.session.execute(text(query))
					results[query[:50] + "..."] = "success"  # 截断长查询
				except Exception as e:
					results[query[:50] + "..."] = f"failed: {str(e)}"

			await self.session.commit()
			return {"status": "completed", "results": results}

		except Exception as e:
			await self.session.rollback()
			return {"status": "failed", "error": str(e)}

	async def cleanup_old_data (
			self,
			retention_days: int = 365
	) -> Dict[str, Any]:
		"""
		清理过期的高频数据

		Args:
			retention_days: 数据保留天数

		Returns:
			清理结果
		"""
		try:
			cutoff_date = datetime.now() - timedelta(days=retention_days)

			# 删除过期数据
			delete_query = text("""
                DELETE FROM stock_minutes 
                WHERE trade_time < :cutoff_date
            """)

			result = await self.session.execute(delete_query, {"cutoff_date": cutoff_date})
			deleted_count = result.rowcount

			# 清理碎片
			vacuum_query = text("VACUUM stock_minutes;")
			await self.session.execute(vacuum_query)

			await self.session.commit()

			return {
				"status": "completed",
				"deleted_records": deleted_count,
				"cutoff_date": cutoff_date,
				"retention_days": retention_days
			}

		except Exception as e:
			await self.session.rollback()
			return {"status": "failed", "error": str(e)}