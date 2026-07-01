# -*- coding: utf-8 -*-
"""
股票复权价格数据仓库
位置：quant_server/shared/database/repositories/market/quote/stock_adjusted_price_repo.py
职责：管理股票复权价格数据访问，继承HyperRepositoryBase实现复权价格专用操作
"""

from datetime import date, timedelta
from typing import List, Optional, Dict, Any, Tuple

from sqlalchemy import select, and_, desc, text, delete
from sqlalchemy.ext.asyncio import AsyncSession

from shared.database import RepositoryError
from shared.database.models.data_models import StockAdjustedPrices, StockAdjFactor
from shared.database.repositories.base.hyper_repository_base import HyperRepositoryBase


class StockAdjustedPriceRepository(HyperRepositoryBase[StockAdjustedPrices]):
	"""
	股票复权价格数据仓库 - 继承HyperRepositoryBase

	特性：
	1. 复权价格专用操作
	2. 支持多种复权类型（qfq/hfq）和频率（D/W/M）
	3. 提供复权价格专用分析方法
	4. 性能优化：批量复权计算和查询
	"""

	def __init__ (self, session: AsyncSession):
		"""
		初始化股票复权价格Repository

		Args:
			session: 异步数据库会话
		"""
		super().__init__(session, StockAdjustedPrices)
		self.time_column = "trade_date"  # 设置时序字段为trade_date

	# ==================== 基础查询方法 ====================

	async def get_by_code_and_date (
			self,
			ts_code: str,
			trade_date: date,
			adj_type: str = "qfq",
			freq: str = "D"
	) -> Optional[StockAdjustedPrices]:
		"""
		根据股票代码、日期、复权类型和频率获取复权价格数据

		Args:
			ts_code: 股票TS代码
			trade_date: 交易日期
			adj_type: 复权类型（qfq/hfq）
			freq: 频率（D/W/M）

		Returns:
			StockAdjustedPrices对象或None
		"""
		return await self.get_by(
			ts_code=ts_code,
			trade_date=trade_date,
			adj_type=adj_type,
			freq=freq
		)

	async def get_by_code_and_date_range (
			self,
			ts_code: str,
			start_date: date,
			end_date: date,
			adj_type: str = "qfq",
			freq: str = "D",
			limit: int = 1000
	) -> List[StockAdjustedPrices]:
		"""
		根据股票代码和时间范围获取复权价格数据

		Args:
			ts_code: 股票TS代码
			start_date: 开始日期
			end_date: 结束日期
			adj_type: 复权类型
			freq: 频率
			limit: 最大返回记录数

		Returns:
			复权价格数据列表
		"""
		query = select(self.model).where(
			and_(
				self.model.ts_code == ts_code,
				self.model.adj_type == adj_type,
				self.model.freq == freq,
				self.model.trade_date.between(start_date, end_date)
			)
		).order_by(self.model.trade_date).limit(limit)

		result = await self.session.execute(query)
		return result.scalars().all()

	async def get_latest_by_code (
			self,
			ts_code: str,
			adj_type: str = "qfq",
			freq: str = "D",
			limit: int = 1
	) -> Optional[StockAdjustedPrices]:
		"""
		获取指定股票的最新复权价格数据

		Args:
			ts_code: 股票TS代码
			adj_type: 复权类型
			freq: 频率
			limit: 返回记录数

		Returns:
			最新复权价格数据或列表
		"""
		query = select(self.model).where(
			and_(
				self.model.ts_code == ts_code,
				self.model.adj_type == adj_type,
				self.model.freq == freq
			)
		).order_by(desc(self.model.trade_date)).limit(limit)

		result = await self.session.execute(query)
		if limit == 1:
			return result.scalar_one_or_none()
		return result.scalars().all()

	# ==================== 批量查询方法 ====================

	async def get_batch_by_date_range(
			self,
			symbols: List[str],
			start_date: date,
			end_date: date,
			adj_type: str = "qfq",
			freq: str = "D",
			limit: int = 100_000,
	) -> List[StockAdjustedPrices]:
		"""
		批量获取多只股票在时间范围内的复权价格（一次 SQL IN 查询）。
		"""
		try:
			query = (
				select(self.model)
				.where(
					self.model.ts_code.in_(symbols),
					self.model.adj_type == adj_type,
					self.model.freq == freq,
					self.model.trade_date.between(start_date, end_date),
				)
				.order_by(self.model.trade_date, self.model.ts_code)
				.limit(limit)
			)
			result = await self.session.execute(query)
			return list(result.scalars().all())
		except Exception as e:
			raise RepositoryError(f"批量查询复权价格失败: {e}")

	# ==================== 批量操作方法 ====================

	async def batch_insert_adjusted_prices (
			self,
			records: List[Dict[str, Any]],
			conflict_strategy: str = "upsert"
	) -> int:
		"""
		批量插入复权价格数据

		Args:
			records: 复权价格数据记录列表
			conflict_strategy: 冲突处理策略

		Returns:
			成功插入的记录数
		"""
		return await self.batch_insert(records, conflict_strategy)

	async def batch_upsert_adjusted_prices (
			self,
			prices_data: List[Dict[str, Any]]
	) -> int:
		"""
		批量插入或更新复权价格数据

		Args:
			prices_data: 价格数据列表

		Returns:
			成功处理的记录数
		"""
		return await self.batch_insert(prices_data, "upsert")

	async def delete_by_date_range (
			self,
			start_date: date,
			end_date: date,
			ts_code: Optional[str] = None,
			adj_type: Optional[str] = None,
			freq: Optional[str] = None
	) -> int:
		"""
		删除指定时间范围内的复权价格数据

		Args:
			start_date: 开始日期
			end_date: 结束日期
			ts_code: 股票代码（可选）
			adj_type: 复权类型（可选）
			freq: 频率（可选）

		Returns:
			删除的记录数
		"""
		conditions = [
			self.model.trade_date >= start_date,
			self.model.trade_date <= end_date
		]

		if ts_code:
			conditions.append(self.model.ts_code == ts_code)

		if adj_type:
			conditions.append(self.model.adj_type == adj_type)

		if freq:
			conditions.append(self.model.freq == freq)

		query = delete(self.model).where(and_(*conditions))

		result = await self.session.execute(query) # type: ignore
		await self.session.commit()
		return result.rowcount or 0

	# ==================== 复权价格分析 ====================

	async def calculate_return_series (
			self,
			ts_code: str,
			start_date: date,
			end_date: date,
			adj_type: str = "qfq",
			freq: str = "D"
	) -> List[Dict[str, Any]]:
		"""
		计算复权收益率序列

		Args:
			ts_code: 股票代码
			start_date: 开始日期
			end_date: 结束日期
			adj_type: 复权类型
			freq: 频率

		Returns:
			收益率序列
		"""
		price_data = await self.get_by_code_and_date_range(
			ts_code, start_date, end_date, adj_type, freq
		)

		if len(price_data) < 2:
			return []

		# 按日期排序
		price_data.sort(key=lambda x: x.trade_date)

		return_series = []

		for i in range(1, len(price_data)):
			prev_price = float(price_data[i - 1].close)
			curr_price = float(price_data[i].close)

			if prev_price > 0:
				daily_return = (curr_price - prev_price) / prev_price
				cumulative_return = (curr_price - float(price_data[0].close)) / float(price_data[0].close)

				return_series.append({
					"date": price_data[i].trade_date,
					"price": curr_price,
					"daily_return": daily_return * 100,
					"cumulative_return": cumulative_return * 100,
					"log_return": self._calculate_log_return(prev_price, curr_price) * 100,
					"price_change": curr_price - prev_price
				})

		return return_series

	@staticmethod
	def _calculate_log_return (
			prev_price: float,
			curr_price: float
	) -> float:
		"""计算对数收益率"""
		if prev_price > 0 and curr_price > 0:
			import math
			return math.log(curr_price / prev_price)
		return 0.0

	async def analyze_price_trend (
			self,
			ts_code: str,
			start_date: date,
			end_date: date,
			adj_type: str = "qfq",
			freq: str = "D"
	) -> Dict[str, Any]:
		"""
		分析价格趋势

		Args:
			ts_code: 股票代码
			start_date: 开始日期
			end_date: 结束日期
			adj_type: 复权类型
			freq: 频率

		Returns:
			趋势分析结果
		"""
		price_data = await self.get_by_code_and_date_range(
			ts_code, start_date, end_date, adj_type, freq
		)

		if len(price_data) < 2:
			return {}

		# 按日期排序
		price_data.sort(key=lambda x: x.trade_date)

		prices = [float(d.close) for d in price_data]
		dates = [d.trade_date for d in price_data]

		# 计算基本统计
		start_price = prices[0]
		end_price = prices[-1]
		max_price = max(prices)
		min_price = min(prices)

		# 计算总收益率
		total_return = (end_price - start_price) / start_price * 100 if start_price > 0 else 0

		# 计算年化收益率
		days_elapsed = (dates[-1] - dates[0]).days
		if days_elapsed > 0:
			years_elapsed = days_elapsed / 365
			cagr = ((end_price / start_price) ** (1 / years_elapsed) - 1) * 100 if start_price > 0 else 0
		else:
			cagr = 0

		# 计算波动率
		returns = []
		for i in range(1, len(prices)):
			if prices[i - 1] > 0:
				returns.append((prices[i] - prices[i - 1]) / prices[i - 1])

		if len(returns) >= 2:
			mean_return = sum(returns) / len(returns)
			variance = sum((r - mean_return) ** 2 for r in returns) / len(returns)
			volatility = variance ** 0.5

			if freq == "D":
				annual_volatility = volatility * (252 ** 0.5)
			elif freq == "W":
				annual_volatility = volatility * (52 ** 0.5)
			elif freq == "M":
				annual_volatility = volatility * (12 ** 0.5)
			else:
				annual_volatility = volatility
		else:
			volatility = annual_volatility = 0
		mean_return = 0

		# 计算夏普比率（假设无风险利率3%）
		risk_free_rate = 0.03
		if freq == "D":
			period_risk_free = risk_free_rate / 252
		elif freq == "W":
			period_risk_free = risk_free_rate / 52
		elif freq == "M":
			period_risk_free = risk_free_rate / 12
		else:
			period_risk_free = risk_free_rate

		sharpe_ratio = (mean_return - period_risk_free) / volatility if volatility > 0 else 0

		# 计算最大回撤
		max_drawdown, max_drawdown_period = self._calculate_max_drawdown(prices, dates)

		# 趋势强度分析
		trend_strength = self._calculate_trend_strength(dates, prices)

		return {
			"ts_code": ts_code,
			"adj_type": adj_type,
			"freq": freq,
			"analysis_period": {
				"start_date": start_date,
				"end_date": end_date,
				"days": days_elapsed,
				"data_points": len(prices)
			},
			"price_statistics": {
				"start_price": start_price,
				"end_price": end_price,
				"max_price": max_price,
				"min_price": min_price,
				"price_range": max_price - min_price,
				"avg_price": sum(prices) / len(prices)
			},
			"return_statistics": {
				"total_return": total_return,
				"cagr": cagr,
				"avg_period_return": mean_return * 100,
				"volatility": volatility * 100,
				"annual_volatility": annual_volatility * 100
			},
			"risk_metrics": {
				"max_drawdown": max_drawdown * 100,
				"max_drawdown_period": max_drawdown_period,
				"sharpe_ratio": sharpe_ratio,
				"calmar_ratio": cagr / (max_drawdown * 100) if max_drawdown > 0 else 0
			},
			"trend_analysis": {
				"trend_strength": trend_strength,
				"trend_direction": "up" if total_return > 0 else "down",
				"consistency": self._calculate_consistency(prices)
			}
		}

	@staticmethod
	def _calculate_max_drawdown (
			prices: List[float],
			dates: List[date]
	) -> Tuple[float, Dict[str, date]]:
		"""计算最大回撤"""
		if not prices or len(prices) < 2:
			return 0.0, {}

		peak = prices[0]
		peak_date = dates[0]
		max_drawdown = 0.0
		drawdown_start = dates[0]
		drawdown_end = dates[0]

		for i, price in enumerate(prices):
			if price > peak:
				peak = price
				peak_date = dates[i]

			drawdown = (peak - price) / peak if peak > 0 else 0

			if drawdown > max_drawdown:
				max_drawdown = drawdown
				drawdown_start = peak_date
				drawdown_end = dates[i]

		return max_drawdown, {
			"start_date": drawdown_start,
			"end_date": drawdown_end,
			"duration_days": (drawdown_end - drawdown_start).days,
			"peak_price": peak,
			"trough_price": prices[dates.index(drawdown_end)] if drawdown_end in dates else 0
		}

	@staticmethod
	def _calculate_trend_strength (
			dates: List[date],
			prices: List[float]
	) -> float:
		"""计算趋势强度（R-squared）"""
		if len(prices) < 2:
			return 0.0

		# 将日期转换为数值（从第一个日期开始的天数）
		date_nums = [(d - dates[0]).days for d in dates]

		# 线性回归计算R-squared
		n = len(date_nums)
		sum_x = sum(date_nums)
		sum_y = sum(prices)
		sum_xy = sum(x * y for x, y in zip(date_nums, prices))
		sum_x2 = sum(x * x for x in date_nums)
		sum_y2 = sum(y * y for y in prices)

		# 计算相关系数
		numerator = n * sum_xy - sum_x * sum_y
		denominator = ((n * sum_x2 - sum_x ** 2) * (n * sum_y2 - sum_y ** 2)) ** 0.5

		if denominator == 0:
			return 0.0

		correlation = numerator / denominator
		r_squared = correlation ** 2

		return r_squared

	@staticmethod
	def _calculate_consistency (
			prices: List[float]
	) -> float:
		"""计算价格一致性"""
		if len(prices) < 2:
			return 0.0

		positive_days = 0
		for i in range(1, len(prices)):
			if prices[i] > prices[i - 1]:
				positive_days += 1

		consistency = positive_days / (len(prices) - 1) * 100
		return consistency

	# ==================== 移动平均计算 ====================

	async def calculate_moving_averages (
			self,
			ts_code: str,
			trade_date: date,
			periods: Optional[List[int]] = None,
			adj_type: str = "qfq",
			freq: str = "D"
	) -> Dict[str, Any]:
		"""
		计算移动平均线

		Args:
			ts_code: 股票代码
			trade_date: 交易日期
			periods: 移动平均周期列表
			adj_type: 复权类型
			freq: 频率

		Returns:
			移动平均线计算结果
		"""
		# 初始化默认周期
		if periods is None:
			periods = [5, 10, 20, 60]

		# 获取足够的复权价格数据
		max_period = max(periods)
		start_date = trade_date - timedelta(days=max_period * 3)  # 获取3倍周期的数据

		price_data = await self.get_by_code_and_date_range(
			ts_code, start_date, trade_date, adj_type, freq, limit=max_period * 3
		)

		if not price_data:
			return {}

		# 按日期排序
		price_data.sort(key=lambda x: x.trade_date)
		prices = [float(d.close) for d in price_data]

		# 计算各周期移动平均
		ma_results = {}
		for period in periods:
			if len(prices) >= period:
				ma_value = sum(prices[-period:]) / period
				ma_results[f"MA{period}"] = ma_value
			else:
				ma_results[f"MA{period}"] = None

		current_price = prices[-1] if prices else None

		# 分析均线排列
		valid_ma_values = [v for v in ma_results.values() if v is not None]
		if len(valid_ma_values) >= 2:
			# 检查是否多头排列（短期>中期>长期）
			is_bullish = all(valid_ma_values[i] > valid_ma_values[i + 1] for i in range(len(valid_ma_values) - 1))
			# 检查是否空头排列（短期<中期<长期）
			is_bearish = all(valid_ma_values[i] < valid_ma_values[i + 1] for i in range(len(valid_ma_values) - 1))
		else:
			is_bullish = is_bearish = False

		# 检查价格与均线关系
		price_vs_ma = {}
		for period, ma_value in ma_results.items():
			if ma_value and current_price:
				price_vs_ma[f"above_{period}"] = current_price > ma_value
				price_vs_ma[f"deviation_{period}"] = (current_price - ma_value) / ma_value * 100

		return {
			"ts_code": ts_code,
			"trade_date": trade_date,
			"adj_type": adj_type,
			"freq": freq,
			"current_price": current_price,
			"moving_averages": ma_results,
			"trend_analysis": {
				"is_bullish_arrangement": is_bullish,
				"is_bearish_arrangement": is_bearish,
				"price_vs_ma": price_vs_ma,
				"ma_support_resistance": self._analyze_ma_support_resistance(current_price, ma_results)
			},
			"data_points": len(prices),
			"analysis_period": {
				"start_date": start_date,
				"end_date": trade_date,
				"days": (trade_date - start_date).days
			}
		}

	def _analyze_ma_support_resistance (
			self,
			current_price: Optional[float],
			ma_results: Dict[str, Optional[float]]
	) -> Dict[str, Any]:
		"""分析均线支撑阻力"""
		if not current_price:
			return {}

		support_levels = []
		resistance_levels = []

		for ma_name, ma_value in ma_results.items():
			if ma_value:
				deviation = (current_price - ma_value) / ma_value * 100

				if deviation > 0:
					# 价格在均线上方，均线是支撑
					support_levels.append({
						"level": ma_name,
						"price": ma_value,
						"distance": abs(deviation),
						"strength": self._calculate_support_strength(ma_name, deviation)
					})
				else:
					# 价格在均线下方，均线是阻力
					resistance_levels.append({
						"level": ma_name,
						"price": ma_value,
						"distance": abs(deviation),
						"strength": self._calculate_resistance_strength(ma_name, deviation)
					})

		# 排序
		support_levels.sort(key=lambda x: x["distance"])
		resistance_levels.sort(key=lambda x: x["distance"])

		return {
			"nearest_support": support_levels[0] if support_levels else None,
			"nearest_resistance": resistance_levels[0] if resistance_levels else None,
			"support_levels": support_levels,
			"resistance_levels": resistance_levels,
			"support_count": len(support_levels),
			"resistance_count": len(resistance_levels)
		}

	@staticmethod
	def _calculate_support_strength (
			ma_name: str,
			deviation: float
	) -> str:
		"""计算支撑强度"""
		# 根据均线周期和偏离程度判断强度
		if "MA5" in ma_name or "MA10" in ma_name:
			if deviation < 2:
				return "strong"
			elif deviation < 5:
				return "medium"
			else:
				return "weak"
		elif "MA20" in ma_name or "MA30" in ma_name:
			if deviation < 3:
				return "strong"
			elif deviation < 8:
				return "medium"
			else:
				return "weak"
		else:  # 长期均线
			if deviation < 5:
				return "strong"
			elif deviation < 12:
				return "medium"
			else:
				return "weak"

	def _calculate_resistance_strength (
			self,
			ma_name: str,
			deviation: float
	) -> str:
		"""计算阻力强度"""
		# 逻辑与支撑类似，但方向相反
		return self._calculate_support_strength(ma_name, abs(deviation))

	# ==================== 复权因子辅助操作 ====================

	async def calculate_adjusted_price_from_factor (
			self,
			ts_code: str,
			base_price: float,
			base_date: date,
			target_date: date,
			adj_type: str = "qfq"
	) -> Optional[float]:
		"""
		使用复权因子计算复权价格

		Args:
			ts_code: 股票代码
			base_price: 基期价格
			base_date: 基期日期
			target_date: 目标日期
			adj_type: 复权类型

		Returns:
			复权后的价格或None
		"""
		# 获取复权因子
		factor_query = select(StockAdjFactor).where(
			and_(
				StockAdjFactor.ts_code == ts_code,
				StockAdjFactor.trade_date.in_([base_date, target_date])
			)
		)

		factor_result = await self.session.execute(factor_query)
		factors = factor_result.scalars().all()

		if len(factors) != 2:
			return None

		# 找到对应日期的因子
		base_factor = None
		target_factor = None

		for factor in factors:
			if factor.trade_date == base_date:
				base_factor = float(factor.adj_factor)
			elif factor.trade_date == target_date:
				target_factor = float(factor.adj_factor)

		if base_factor is None or target_factor is None:
			return None

		# 计算复权价格
		if adj_type == "qfq":  # 前复权：以最新价格为基准
			adjusted_price = base_price * (target_factor / base_factor)
		else:  # 后复权：以历史价格为基准
			adjusted_price = base_price * (base_factor / target_factor)

		return adjusted_price

	async def generate_adjusted_price_series (
			self,
			ts_code: str,
			start_date: date,
			end_date: date,
			base_price: float,
			base_date: date,
			adj_type: str = "qfq",
			freq: str = "D"
	) -> List[Dict[str, Any]]:
		"""
		生成复权价格序列

		Args:
			ts_code: 股票代码
			start_date: 开始日期
			end_date: 结束日期
			base_price: 基期价格
			base_date: 基期日期
			adj_type: 复权类型
			freq: 频率

		Returns:
			复权价格序列
		"""
		# 获取复权因子
		factor_query = select(StockAdjFactor).where(
			and_(
				StockAdjFactor.ts_code == ts_code,
				StockAdjFactor.trade_date.between(start_date, end_date)
			)
		).order_by(StockAdjFactor.trade_date)

		factor_result = await self.session.execute(factor_query)
		factors = factor_result.scalars().all()

		if not factors:
			return []

		# 获取基期因子
		base_factor_query = select(StockAdjFactor).where(
			and_(
				StockAdjFactor.ts_code == ts_code,
				StockAdjFactor.trade_date == base_date
			)
		)

		base_factor_result = await self.session.execute(base_factor_query)
		base_factor_record = base_factor_result.scalar_one_or_none()

		if not base_factor_record:
			return []

		base_factor = float(base_factor_record.adj_factor)

		# 生成复权价格序列
		price_series = []
		for factor in factors:
			current_factor = float(factor.adj_factor)

			if adj_type == "qfq":
				adjusted_price = base_price * (current_factor / base_factor)
			else:
				adjusted_price = base_price * (base_factor / current_factor)

			price_series.append({
				"date": factor.trade_date,
				"adj_factor": current_factor,
				"adjusted_price": adjusted_price,
				"adjust_type": adj_type,
				"base_date": base_date,
				"base_price": base_price,
				"freq": freq
			})

		return price_series

	# ==================== 数据完整性检查 ====================

	async def validate_adjusted_data (
			self,
			ts_code: str,
			trade_date: date,
			adj_type: str = "qfq",
			freq: str = "D"
	) -> Dict[str, Any]:
		"""
		验证复权数据完整性

		Args:
			ts_code: 股票代码
			trade_date: 交易日期
			adj_type: 复权类型
			freq: 频率

		Returns:
			验证结果
		"""
		# 获取复权价格数据
		adj_price_data = await self.get_by_code_and_date(ts_code, trade_date, adj_type, freq)

		if not adj_price_data:
			return {"status": "missing", "message": "复权价格数据缺失"}

		# 获取原始日线数据
		daily_query = text("""
            SELECT close, pre_close, vol, amount
            FROM stock_daily
            WHERE ts_code = :ts_code
              AND trade_date = :trade_date
        """)

		daily_result = await self.session.execute(
			daily_query,
			{"ts_code": ts_code, "trade_date": trade_date}
		)
		daily_row = daily_result.fetchone()

		if not daily_row:
			return {"status": "missing_daily", "message": "日线数据缺失"}

		# 获取复权因子
		factor_query = select(StockAdjFactor).where(
			and_(
				StockAdjFactor.ts_code == ts_code,
				StockAdjFactor.trade_date == trade_date
			)
		)

		factor_result = await self.session.execute(factor_query)
		factor_data = factor_result.scalar_one_or_none()

		issues = []
		validations = {}

		# 验证价格一致性
		daily_close = float(daily_row.close)
		adj_close = float(adj_price_data.close)

		if factor_data:
			adj_factor = float(factor_data.adj_factor)

			# 验证前复权价格
			if adj_type == "qfq":
				calculated_price = daily_close * adj_factor
				deviation = abs(adj_close - calculated_price) / calculated_price * 100

				if deviation > 1:  # 允许1%的误差
					issues.append(f"前复权价格偏差较大: {deviation:.2f}%")

				validations["qfq_calculation"] = {
					"daily_close": daily_close,
					"adj_factor": adj_factor,
					"calculated_price": calculated_price,
					"actual_price": adj_close,
					"deviation": deviation
				}

			# 验证后复权价格
			elif adj_type == "hfq":
				calculated_price = daily_close / adj_factor if adj_factor > 0 else 0
				deviation = abs(adj_close - calculated_price) / calculated_price * 100 if calculated_price > 0 else 100

				if deviation > 1:
					issues.append(f"后复权价格偏差较大: {deviation:.2f}%")

				validations["hfq_calculation"] = {
					"daily_close": daily_close,
					"adj_factor": adj_factor,
					"calculated_price": calculated_price,
					"actual_price": adj_close,
					"deviation": deviation
				}

		# 验证其他字段
		if abs(float(adj_price_data.vol) - int(daily_row.vol)) > 0.01:
			issues.append("成交量数据不一致")

		if abs(float(adj_price_data.amount) - float(daily_row.amount)) > 0.01:
			issues.append("成交额数据不一致")

		return {
			"status": "valid" if not issues else "issues",
			"issues": issues,
			"validations": validations,
			"summary": {
				"adj_price_exists": adj_price_data is not None,
				"daily_data_exists": daily_row is not None,
				"factor_data_exists": factor_data is not None,
				"total_checks": 3,
				"passed_checks": sum([
					1 if adj_price_data else 0,
					1 if daily_row else 0,
					1 if factor_data else 0
				])
			}
		}