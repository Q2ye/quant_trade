# -*- coding: utf-8 -*-
"""
股票周行情数据仓库
位置：quant_server/shared/database/repositories/market/quote/stock_weekly_repo.py
职责：管理股票周线行情数据访问，继承HyperRepositoryBase实现周线数据操作
"""

from datetime import date, timedelta, datetime
from typing import List, Optional, Dict, Any

from sqlalchemy import select, desc
from sqlalchemy.ext.asyncio import AsyncSession

from quant_server.shared.database.models.data_models import StockWeekly
from quant_server.shared.database.repositories.base.hyper_repository_base import HyperRepositoryBase


class StockWeeklyRepository(HyperRepositoryBase[StockWeekly]):
	"""
	股票周行情数据仓库 - 继承HyperRepositoryBase

	特性：
	1. 周线数据专用操作
	2. 支持周线技术指标计算
	3. 提供周线数据专用分析方法
	4. 性能优化：周线聚合查询
	"""

	def __init__ (self, session: AsyncSession):
		"""
		初始化股票周行情Repository

		Args:
			session: 异步数据库会话
		"""
		super().__init__(session, StockWeekly)
		self.time_column = "trade_date"  # 设置时序字段为trade_date

	# ==================== 基础查询方法 ====================

	async def get_by_code_and_week (
			self,
			ts_code: str,
			trade_date: date
	) -> Optional[StockWeekly]:
		"""
		根据股票代码和交易周获取周线数据

		Args:
			ts_code: 股票TS代码
			trade_date: 交易周结束日期

		Returns:
			StockWeekly对象或None
		"""
		return await self.get_by(
			ts_code=ts_code,
			trade_date=trade_date
		)

	async def get_by_code_and_date_range (
			self,
			ts_code: str,
			start_date: datetime,
			end_date: datetime,
			limit: int = 1000
	) -> List[StockWeekly]:
		"""
		根据股票代码和时间范围获取周线数据

		Args:
			ts_code: 股票TS代码
			start_date: 开始日期
			end_date: 结束日期
			limit: 最大返回记录数

		Returns:
			周线数据列表
		"""
		return await self.get_by_time_range(
			start_time=start_date,
			end_time=end_date,
			symbol=ts_code,
			limit=limit
		)

	async def get_latest_by_code (
			self,
			ts_code: str,
			limit: int = 1
	) -> Optional[StockWeekly]:
		"""
		获取指定股票的最新周线数据

		Args:
			ts_code: 股票TS代码
			limit: 返回记录数

		Returns:
			最新周线数据或列表
		"""
		return await self.get_latest_record(symbol=ts_code, limit=limit)

	async def get_weekly_summary (
			self,
			trade_date: date,
			limit: int = 100
	) -> List[Dict[str, Any]]:
		"""
		获取指定周的交易概况

		Args:
			trade_date: 交易周结束日期
			limit: 返回数量限制

		Returns:
			周交易概况列表
		"""
		query = select(StockWeekly).where(
			StockWeekly.trade_date == trade_date
		).order_by(desc(StockWeekly.pct_chg)).limit(limit)

		result = await self.session.execute(query)
		weekly_records = result.scalars().all()

		summary = []
		for record in weekly_records:
			summary.append({
				"ts_code": record.ts_code,
				"close": record.close,
				"pct_chg": record.pct_chg,
				"volume": record.vol,
				"amount": record.amount,
				"week_start": record.week_start,
				"week_end": record.week_end,
				"range": float(record.high) - float(record.low) if record.high and record.low else 0
			})

		return summary

	# ==================== 技术分析方法 ====================

	async def calculate_weekly_moving_averages (
			self,
			ts_code: str,
			end_date: datetime,
			periods: Optional[List[int]] = None
	) -> Dict[str, Any]:
		"""
		计算周线移动平均线

		Args:
			ts_code: 股票代码
			end_date: 截止日期
			periods: 移动平均周期列表

		Returns:
			移动平均线计算结果
		"""
		# 初始化默认周期
		if periods is None:
			periods = [5, 10, 20, 50]

		# 获取足够的周线数据
		max_period = max(periods)
		start_date = end_date - timedelta(weeks=max_period * 2)

		weekly_data = await self.get_by_code_and_date_range(
			ts_code, start_date, end_date, limit=max_period * 2
		)

		if not weekly_data:
			return {}

		# 按日期排序
		weekly_data.sort(key=lambda x: x.trade_date)
		closes = [float(d.close) for d in weekly_data]

		# 计算各周期移动平均
		ma_results = {}
		for period in periods:
			if len(closes) >= period:
				ma_value = sum(closes[-period:]) / period
				ma_results[f"MA{period}"] = ma_value
			else:
				ma_results[f"MA{period}"] = None

		current_price = closes[-1] if closes else None

		# 计算均线排列
		ma_values = [v for v in ma_results.values() if v is not None]
		if len(ma_values) >= 2:
			is_bullish = all(ma_values[i] > ma_values[i + 1] for i in range(len(ma_values) - 1))
			is_bearish = all(ma_values[i] < ma_values[i + 1] for i in range(len(ma_values) - 1))
		else:
			is_bullish = is_bearish = False

		return {
			"ts_code": ts_code,
			"end_date": end_date,
			"current_price": current_price,
			"moving_averages": ma_results,
			"trend_analysis": {
				"is_bullish_arrangement": is_bullish,
				"is_bearish_arrangement": is_bearish,
				"price_vs_ma": {
					f"above_MA{period}": current_price > ma_value if ma_value and current_price else None
					for period, ma_value in ma_results.items()
				}
			},
			"data_points": len(closes)
		}

	async def analyze_weekly_momentum (
			self,
			ts_code: str,
			end_date: datetime,
			lookback_weeks: int = 12
	) -> Dict[str, Any]:
		"""
		分析周线动量

		Args:
			ts_code: 股票代码
			end_date: 截止日期
			lookback_weeks: 回溯周数

		Returns:
			动量分析结果
		"""
		start_date = end_date - timedelta(weeks=lookback_weeks)

		weekly_data = await self.get_by_code_and_date_range(
			ts_code, start_date, end_date, limit=lookback_weeks + 1
		)

		if len(weekly_data) < 2:
			return {}

		# 按日期排序
		weekly_data.sort(key=lambda x: x.trade_date)

		# 计算每周收益率
		returns = []
		price_changes = []

		for i in range(1, len(weekly_data)):
			prev_close = float(weekly_data[i - 1].close)
			curr_close = float(weekly_data[i].close)

			if prev_close > 0:
				weekly_return = (curr_close - prev_close) / prev_close
				returns.append(weekly_return)
				price_changes.append(curr_close - prev_close)

		if not returns:
			return {}

		# 动量指标计算
		positive_weeks = sum(1 for r in returns if r > 0)
		negative_weeks = sum(1 for r in returns if r < 0)

		cumulative_return = (float(weekly_data[-1].close) - float(weekly_data[0].close)) / float(weekly_data[0].close)
		avg_weekly_return = sum(returns) / len(returns)

		# 计算动量得分
		momentum_score = 0
		if len(returns) >= 4:
			# 最近4周动量
			recent_returns = returns[-4:] if len(returns) >= 4 else returns
			momentum_score = sum(recent_returns) / len(recent_returns) * 100

		# 波动率计算
		if len(returns) >= 2:
			mean_return = sum(returns) / len(returns)
			variance = sum((r - mean_return) ** 2 for r in returns) / len(returns)
			weekly_volatility = variance ** 0.5
			annualized_volatility = weekly_volatility * (52 ** 0.5)  # 年化波动率
		else:
			weekly_volatility = annualized_volatility = 0

		# 夏普比率（假设无风险利率为3%）
		risk_free_rate = 0.03 / 52  # 周无风险利率
		sharpe_ratio = (avg_weekly_return - risk_free_rate) / weekly_volatility if weekly_volatility > 0 else 0

		return {
			"ts_code": ts_code,
			"end_date": end_date,
			"analysis_period": {
				"start_date": weekly_data[0].trade_date,
				"end_date": weekly_data[-1].trade_date,
				"weeks": len(weekly_data) - 1
			},
			"price_summary": {
				"start_price": float(weekly_data[0].close),
				"end_price": float(weekly_data[-1].close),
				"total_change": float(weekly_data[-1].close) - float(weekly_data[0].close),
				"total_return": cumulative_return * 100
			},
			"return_statistics": {
				"avg_weekly_return": avg_weekly_return * 100,
				"max_weekly_return": max(returns) * 100 if returns else 0,
				"min_weekly_return": min(returns) * 100 if returns else 0,
				"positive_weeks": positive_weeks,
				"negative_weeks": negative_weeks,
				"win_rate": positive_weeks / len(returns) * 100 if returns else 0
			},
			"momentum_indicators": {
				"momentum_score": momentum_score,
				"trend_strength": abs(cumulative_return) * 100,
				"consistency": (positive_weeks - negative_weeks) / len(returns) * 100 if returns else 0
			},
			"risk_metrics": {
				"weekly_volatility": weekly_volatility * 100,
				"annualized_volatility": annualized_volatility * 100,
				"sharpe_ratio": sharpe_ratio,
				"max_drawdown": self._calculate_max_drawdown([float(d.close) for d in weekly_data])
			}
		}

	@staticmethod
	def _calculate_max_drawdown (prices: List[float]) -> float:
		"""
		计算最大回撤

		Args:
			prices: 价格列表

		Returns:
			最大回撤（百分比）
		"""
		if not prices or len(prices) < 2:
			return 0

		peak = prices[0]
		max_drawdown = 0

		for price in prices[1:]:
			if price > peak:
				peak = price
			else:
				drawdown = (peak - price) / peak
				if drawdown > max_drawdown:
					max_drawdown = drawdown

		return max_drawdown * 100

	# ==================== 周线模式检测 ====================

	async def detect_weekly_patterns (
			self,
			ts_code: str,
			end_date: datetime,
			lookback_weeks: int = 52
	) -> Dict[str, Any]:
		"""
		检测周线技术形态

		Args:
			ts_code: 股票代码
			end_date: 截止日期
			lookback_weeks: 回溯周数

		Returns:
			技术形态检测结果
		"""
		start_date = end_date - timedelta(weeks=lookback_weeks)

		weekly_data = await self.get_by_code_and_date_range(
			ts_code, start_date, end_date, limit=lookback_weeks
		)

		if len(weekly_data) < 5:  # 至少需要5周数据检测形态
			return {"patterns": [], "summary": {}}

		# 按日期排序
		weekly_data.sort(key=lambda x: x.trade_date)

		patterns = []

		# 检测常见周线形态
		for i in range(4, len(weekly_data)):
			# 获取最近5周数据
			recent_weeks = weekly_data[i - 4:i + 1]

			pattern = self._detect_weekly_pattern(recent_weeks)
			if pattern:
				patterns.append({
					"end_date": recent_weeks[-1].trade_date,
					"pattern": pattern,
					"price": float(recent_weeks[-1].close),
					"weeks_involved": [w.trade_date for w in recent_weeks]
				})

		# 汇总分析
		pattern_types = [p["pattern"] for p in patterns]
		pattern_counts = {}
		for pattern in pattern_types:
			pattern_counts[pattern] = pattern_counts.get(pattern, 0) + 1

		return {
			"ts_code": ts_code,
			"analysis_period": {
				"start_date": start_date,
				"end_date": end_date,
				"weeks": len(weekly_data)
			},
			"patterns_detected": patterns,
			"pattern_statistics": pattern_counts,
			"pattern_frequency": len(patterns) / len(weekly_data) * 100 if weekly_data else 0,
			"recent_patterns": patterns[-5:] if len(patterns) >= 5 else patterns
		}

	@staticmethod
	def _detect_weekly_pattern (
			weeks: List[StockWeekly]
	) -> Optional[str]:
		"""
		检测周线技术形态

		Args:
			weeks: 周线数据列表（通常5周）

		Returns:
			形态名称或None
		"""
		if len(weeks) < 5:
			return None

		# 提取价格数据
		opens = [float(w.open) for w in weeks]
		highs = [float(w.high) for w in weeks]
		lows = [float(w.low) for w in weeks]
		closes = [float(w.close) for w in weeks]

		# 判断周线实体
		weekly_bodies = [closes[i] - opens[i] for i in range(len(weeks))]
		weekly_ranges = [highs[i] - lows[i] for i in range(len(weeks))]

		# 1. 上升三法 /下降三法
		if len(weeks) >= 5:
			# 上升三 法：第一周大阳线，中间三周小实体整理，第五周大阳线突破
			if (weekly_bodies[0] > 0 and weekly_bodies[0] > weekly_ranges[0] * 0.6 and  # 第一周大阳线
					all(abs(b) < weekly_ranges[i] * 0.3 for i, b in enumerate(weekly_bodies[1:4])) and  # 中间三周小实体
					weekly_bodies[4] > 0 and weekly_bodies[4] > weekly_ranges[4] * 0.6 and  # 第五周大阳线
					closes[4] > closes[0]):  # 突破前高
				return "rising_three_methods"

			# 下降三 法：第一周大阴线，中间三周小实体整理，第五周大阴线突破
			if (weekly_bodies[0] < 0 and abs(weekly_bodies[0]) > weekly_ranges[0] * 0.6 and  # 第一周大阴线
					all(abs(b) < weekly_ranges[i] * 0.3 for i, b in enumerate(weekly_bodies[1:4])) and  # 中间三周小实体
					weekly_bodies[4] < 0 and abs(weekly_bodies[4]) > weekly_ranges[4] * 0.6 and  # 第五周大阴线
					closes[4] < closes[0]):  # 突破前低
				return "falling_three_methods"

		# 2. 周线突破
		if len(weeks) >= 2:
			# 最近一周突破前几周高点
			if highs[-1] > max(highs[:-1]) and weekly_bodies[-1] > 0:
				return "weekly_breakout_high"

			# 最近一周跌破前几周低点
			if lows[-1] < min(lows[:-1]) and weekly_bodies[-1] < 0:
				return "weekly_breakout_low"

		# 3. 周线支撑/阻力
		if len(weeks) >= 3:
			# 形成支撑：最近两周低点接近
			if abs(lows[-1] - lows[-2]) / lows[-2] < 0.02:
				if weekly_bodies[-1] > 0:  # 本周上涨
					return "weekly_support_bounce"

			# 形成阻力：最近两周高点接近
			if abs(highs[-1] - highs[-2]) / highs[-2] < 0.02:
				if weekly_bodies[-1] < 0:  # 本周下跌
					return "weekly_resistance_rejection"

		return None

	# ==================== 批量操作方法 ====================

	async def batch_insert_weekly (
			self,
			records: List[Dict[str, Any]],
			conflict_strategy: str = "upsert"
	) -> int:
		"""
		批量插入周线数据

		Args:
			records: 周线数据记录列表
			conflict_strategy: 冲突处理策略

		Returns:
			成功插入的记录数
		"""
		return await self.batch_insert(records, conflict_strategy)

	async def generate_weekly_from_daily (
			self,
			ts_code: str,
			start_date: date,
			end_date: date
	) -> List[Dict[str, Any]]:
		"""
		从日线数据生成周线数据

		Args:
			ts_code: 股票代码
			start_date: 开始日期
			end_date: 结束日期

		Returns:
			生成的周线数据列表
		"""
		# 导入必要的Repository
		from quant_server.shared.database.repositories import repository_factory
		
		# 创建StockDailyRepository实例
		daily_repo = repository_factory.create_repository("stock_daily_repo", self.session)
		
		# 获取指定时间范围内的日线数据
		daily_data = await daily_repo.get_by_code_and_date_range(
			ts_code=ts_code,
			start_date=start_date,
			end_date=end_date,
			limit=1000  # 限制最大返回记录数
		)
		
		if not daily_data:
			return []
		
		# 按日期排序
		daily_data.sort(key=lambda x: x.trade_date)
		
		# 按周分组（以每周一为周开始）
		weekly_groups = {}
		for daily_record in daily_data:
			# 计算该日期所属的周开始日期（周一）
			week_start = self._get_week_start_date(daily_record.trade_date)
			
			if week_start not in weekly_groups:
				weekly_groups[week_start] = []
			
			weekly_groups[week_start].append(daily_record)
		
		# 生成周线数据
		weekly_data = []
		for week_start, week_daily_data in weekly_groups.items():
			if len(week_daily_data) < 1:  # 至少需要一天数据
				continue
			
			# 计算周线OHLCV指标
			weekly_record = self._aggregate_weekly_data(week_daily_data, week_start, ts_code)
			if weekly_record:
				weekly_data.append(weekly_record)
		
		# 按交易日期排序
		weekly_data.sort(key=lambda x: x["trade_date"])
		
		return weekly_data

	@staticmethod
	def _get_week_start_date (trade_date: date) -> date:
		"""
		计算指定日期所属周的周一日期

		Args:
			trade_date: 交易日期

		Returns:
			周一开始日期
		"""
		# 计算距离周一的偏移天数（周一为0，周日为6）
		weekday = trade_date.weekday()  # 周一=0, 周日=6
		
		# 如果是周一，直接返回；否则计算前一个周一
		if weekday == 0:
			return trade_date
		else:
			return trade_date - timedelta(days=weekday)

	@staticmethod
	def _aggregate_weekly_data (
			week_daily_data: List,
			week_start: date,
			ts_code: str
	) -> Dict[str, Any]:
		"""
		聚合周线数据

		Args:
			week_daily_data: 一周内的日线数据列表
			week_start: 周开始日期（周一）
			ts_code: 股票代码

		Returns:
			周线数据记录
		"""
		if not week_daily_data:
			return {}

		# 按日期排序
		week_daily_data.sort(key=lambda x: x.trade_date)
		
		# 提取价格数据
		opens = [float(d.open) for d in week_daily_data]
		highs = [float(d.high) for d in week_daily_data]
		lows = [float(d.low) for d in week_daily_data]
		closes = [float(d.close) for d in week_daily_data]
		volumes = [float(d.vol) for d in week_daily_data]
		amounts = [float(d.amount) for d in week_daily_data]
		
		# 计算周线OHLCV
		week_open = opens[0] if opens else 0
		week_high = max(highs) if highs else 0
		week_low = min(lows) if lows else 0
		week_close = closes[-1] if closes else 0
		week_volume = sum(volumes) if volumes else 0
		week_amount = sum(amounts) if amounts else 0
		
		# 计算周涨跌幅
		if week_open > 0:
			week_change = (week_close - week_open) / week_open * 100
		else:
			week_change = 0
		
		# 计算周均价
		week_avg_price = sum(closes) / len(closes) if closes else 0
		
		# 构建周线数据记录
		weekly_record = {
			"ts_code": ts_code,
			"trade_date": week_start,  # 使用周一作为周线交易日期
			"open": week_open,
			"high": week_high,
			"low": week_low,
			"close": week_close,
			"pre_close": week_open,  # 上周收盘价（即本周开盘价）
			"change": week_change,
			"pct_chg": week_change,  # 百分比变化
			"vol": week_volume,
			"amount": week_amount,
			"avg_price": week_avg_price,
			"trade_days": len(week_daily_data),  # 本周交易天数
			"week_start": week_start,
			"week_end": week_daily_data[-1].trade_date if week_daily_data else week_start
		}
		
		return weekly_record