# -*- coding: utf-8 -*-
"""
涨跌停数据仓库
位置：quant_server/shared/database/repositories/market/quote/stock_daily_limit_repo.py
职责：管理股票每日涨跌停价格、涨跌停状态等数据访问，继承HyperRepositoryBase
"""

from datetime import date, timedelta, datetime
from typing import List, Optional, Dict, Any

from sqlalchemy import select, text
from sqlalchemy.ext.asyncio import AsyncSession

from shared.database.models.data_models import StockDailyLimit
from shared.database.repositories.base.hyper_repository_base import HyperRepositoryBase


class StockDailyLimitRepository(HyperRepositoryBase[StockDailyLimit]):
	"""
	涨跌停数据仓库 - 继承HyperRepositoryBase

	特性：
	1. 涨跌停数据专用操作
	2. 支持涨跌停状态分析
	3. 提供涨跌停专用分析方法
	4. 性能优化：批量操作和时间范围查询
	"""

	def __init__ (self, session: AsyncSession):
		"""
		初始化涨跌停数据Repository

		Args:
			session: 异步数据库会话
		"""
		super().__init__(session, StockDailyLimit)
		self.time_column = "trade_date"  # 设置时序字段为trade_date

	# ==================== 基础查询方法 ====================

	async def get_by_code_and_date (
			self,
			ts_code: str,
			trade_date: date
	) -> Optional[StockDailyLimit]:
		"""
		根据股票代码和日期获取涨跌停数据

		Args:
			ts_code: 股票TS代码
			trade_date: 交易日期

		Returns:
			StockDailyLimit对象或None
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
	) -> List[StockDailyLimit]:
		"""
		根据股票代码和时间范围获取涨跌停数据

		Args:
			ts_code: 股票TS代码
			start_date: 开始日期
			end_date: 结束日期
			limit: 最大返回记录数

		Returns:
			涨跌停数据列表
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
	) -> Optional[StockDailyLimit]:
		"""
		获取指定股票的最新涨跌停数据

		Args:
			ts_code: 股票TS代码
			limit: 返回记录数

		Returns:
			最新涨跌停数据或列表
		"""
		return await self.get_latest_record(symbol=ts_code, limit=limit)

	async def get_daily_limits_by_date (
			self,
			trade_date: date,
			limit: int = 1000,
			skip: int = 0
	) -> List[StockDailyLimit]:
		"""
		获取指定日期的所有股票涨跌停数据

		Args:
			trade_date: 交易日期
			limit: 返回数量限制
			skip: 跳过数量

		Returns:
			涨跌停数据列表
		"""
		query = select(self.model).where(
			self.model.trade_date == trade_date
		).offset(skip).limit(limit)

		result = await self.session.execute(query)
		return result.scalars().all()

	# ==================== 批量操作方法 ====================

	async def batch_insert_limits (
			self,
			records: List[Dict[str, Any]],
			conflict_strategy: str = "upsert"
	) -> int:
		"""
		批量插入涨跌停数据

		Args:
			records: 涨跌停数据记录列表
			conflict_strategy: 冲突处理策略

		Returns:
			成功插入的记录数
		"""
		return await self.batch_insert(records, conflict_strategy)

	async def batch_upsert_daily_limits (
			self,
			limits_data: List[Dict[str, Any]]
	) -> int:
		"""
		批量插入或更新涨跌停数据

		Args:
			limits_data: 涨跌停数据列表

		Returns:
			成功处理的记录数
		"""
		return await self.batch_insert(limits_data, "upsert")

	async def delete_by_date_range (
			self,
			start_date: datetime,
			end_date: datetime,
			ts_code: Optional[str] = None
	) -> int:
		"""
		删除指定时间范围内的涨跌停数据

		Args:
			start_date: 开始日期
			end_date: 结束日期
			ts_code: 股票代码（可选）

		Returns:
			删除的记录数
		"""
		return await self.delete_by_time_range(
			start_time=start_date,
			end_time=end_date,
			symbol=ts_code
		)

	# ==================== 涨跌停状态分析 ====================

	async def get_limit_status (
			self,
			ts_code: str,
			trade_date: date
	) -> Optional[Dict[str, Any]]:
		"""
		获取涨跌停状态分析

		Args:
			ts_code: 股票代码
			trade_date: 交易日期

		Returns:
			涨跌停状态字典或None
		"""
		limit_data = await self.get_by_code_and_date(ts_code, trade_date)
		if not limit_data:
			return None

		# 获取当日的行情数据
		daily_query = text("""
            SELECT close, pre_close
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
			return None

		close_price = float(daily_row.close)
		pre_close = float(daily_row.pre_close)

		# 分析涨跌停状态
		up_limit_price = float(limit_data.up_limit)
		down_limit_price = float(limit_data.down_limit)

		# 判断是否涨停（考虑到价格精度）
		is_up_limit = abs(close_price - up_limit_price) < 0.01
		is_down_limit = abs(close_price - down_limit_price) < 0.01

		# 计算接近度
		if close_price > pre_close:  # 上涨
			if up_limit_price > pre_close:
				proximity_to_limit = (close_price - pre_close) / (up_limit_price - pre_close)
			else:
				proximity_to_limit = 1.0
			limit_type = "up" if is_up_limit else "none"
		else:  # 下跌
			if pre_close > down_limit_price:
				proximity_to_limit = (pre_close - close_price) / (pre_close - down_limit_price)
			else:
				proximity_to_limit = 1.0
			limit_type = "down" if is_down_limit else "none"

		return {
			"ts_code": ts_code,
			"trade_date": trade_date,
			"close_price": close_price,
			"previous_close": pre_close,
			"up_limit_price": up_limit_price,
			"down_limit_price": down_limit_price,
			"is_up_limit": is_up_limit,
			"is_down_limit": is_down_limit,
			"limit_type": limit_type,
			"proximity_to_limit": proximity_to_limit,
			"price_range": float(limit_data.price_range) if limit_data.price_range else None,
			"up_percent": float(limit_data.up_percent) if limit_data.up_percent else None,
			"down_percent": float(limit_data.down_percent) if limit_data.down_percent else None
		}

	async def get_limit_streak (
			self,
			ts_code: str,
			end_date: datetime,
			max_days: int = 10
	) -> Dict[str, Any]:
		"""
		获取连续涨跌停记录

		Args:
			ts_code: 股票代码
			end_date: 结束日期
			max_days: 最大回溯天数

		Returns:
			连续涨跌停记录
		"""
		start_date = end_date - timedelta(days=max_days)

		# 获取日期范围内的涨跌停数据
		limit_data_list = await self.get_by_code_and_date_range(ts_code, start_date, end_date)

		if not limit_data_list:
			return {
				"ts_code": ts_code,
				"end_date": end_date,
				"streak_days": 0,
				"limit_type": "none",
				"dates": []
			}

		# 获取对应的行情数据来分析涨跌停
		streak_days = 0
		limit_type = "none"
		limit_dates = []

		# 按日期降序排列
		limit_data_list.sort(key=lambda x: x.trade_date, reverse=True)

		for limit_data in limit_data_list:
			# 获取当日行情
			daily_query = text("""
                SELECT close, pre_close
                FROM stock_daily
                WHERE ts_code = :ts_code
                  AND trade_date = :trade_date
            """)

			daily_result = await self.session.execute(
				daily_query,
				{"ts_code": ts_code, "trade_date": limit_data.trade_date}
			)
			daily_row = daily_result.fetchone()

			if not daily_row:
				break

			close_price = float(daily_row.close)
			up_limit_price = float(limit_data.up_limit)
			down_limit_price = float(limit_data.down_limit)

			# 判断涨跌停
			is_up_limit = abs(close_price - up_limit_price) < 0.01
			is_down_limit = abs(close_price - down_limit_price) < 0.01

			if not is_up_limit and not is_down_limit:
				break  # 非涨跌停日，终止连续记录

			# 确定涨跌停类型
			current_type = "up" if is_up_limit else "down"

			if streak_days == 0:
				# 第一个涨跌停日
				limit_type = current_type
				streak_days = 1
				limit_dates.append(limit_data.trade_date)
			elif current_type == limit_type:
				# 相同类型的连续涨跌停
				streak_days += 1
				limit_dates.append(limit_data.trade_date)
			else:
				# 类型改变，终止记录
				break

		return {
			"ts_code": ts_code,
			"end_date": end_date,
			"streak_days": streak_days,
			"limit_type": limit_type,
			"dates": limit_dates
		}

	# ==================== 市场涨跌停统计 ====================

	async def get_market_limit_stats (
			self,
			trade_date: date
	) -> Dict[str, Any]:
		"""
		获取市场涨跌停统计

		Args:
			trade_date: 交易日期

		Returns:
			市场涨跌停统计字典
		"""
		# 统计涨停股票
		up_limit_query = text("""
            SELECT COUNT(DISTINCT d.ts_code) as up_limit_count
            FROM stock_daily d
            JOIN stock_daily_limit l ON d.ts_code = l.ts_code AND d.trade_date = l.trade_date
            WHERE d.trade_date = :trade_date
              AND ABS(d.close - l.up_limit) < 0.01
        """)

		up_result = await self.session.execute(up_limit_query, {"trade_date": trade_date})
		up_count = up_result.scalar() or 0

		# 统计跌停股票
		down_limit_query = text("""
            SELECT COUNT(DISTINCT d.ts_code) as down_limit_count
            FROM stock_daily d
            JOIN stock_daily_limit l ON d.ts_code = l.ts_code AND d.trade_date = l.trade_date
            WHERE d.trade_date = :trade_date
              AND ABS(d.close - l.down_limit) < 0.01
        """)

		down_result = await self.session.execute(down_limit_query, {"trade_date": trade_date})
		down_count = down_result.scalar() or 0

		# 统计接近涨停的股票（涨幅>9%）
		near_up_query = text("""
            SELECT COUNT(DISTINCT d.ts_code) as near_up_count
            FROM stock_daily d
            JOIN stock_daily_limit l ON d.ts_code = l.ts_code AND d.trade_date = l.trade_date
            WHERE d.trade_date = :trade_date
              AND d.pct_chg > 9.0
              AND ABS(d.close - l.up_limit) >= 0.01
        """)

		near_up_result = await self.session.execute(near_up_query, {"trade_date": trade_date})
		near_up_count = near_up_result.scalar() or 0

		# 统计接近跌停的股票（跌幅<-9%）
		near_down_query = text("""
            SELECT COUNT(DISTINCT d.ts_code) as near_down_count
            FROM stock_daily d
            JOIN stock_daily_limit l ON d.ts_code = l.ts_code AND d.trade_date = l.trade_date
            WHERE d.trade_date = :trade_date
              AND d.pct_chg < -9.0
              AND ABS(d.close - l.down_limit) >= 0.01
        """)

		near_down_result = await self.session.execute(near_down_query, {"trade_date": trade_date})
		near_down_count = near_down_result.scalar() or 0

		# 获取当日交易股票总数
		total_query = text("""
            SELECT COUNT(DISTINCT ts_code) as total_stocks
            FROM stock_daily
            WHERE trade_date = :trade_date
        """)

		total_result = await self.session.execute(total_query, {"trade_date": trade_date})
		total_stocks = total_result.scalar() or 0

		total_limit_count = up_count + down_count
		total_near_limit_count = near_up_count + near_down_count

		if total_stocks > 0:
			limit_ratio = total_limit_count / total_stocks * 100
			active_ratio = (total_limit_count + total_near_limit_count) / total_stocks * 100
		else:
			limit_ratio = active_ratio = 0

		return {
			"trade_date": trade_date,
			"statistics": {
				"up_limit_count": up_count,
				"down_limit_count": down_count,
				"near_up_limit_count": near_up_count,
				"near_down_limit_count": near_down_count,
				"total_limit_count": total_limit_count,
				"total_near_limit_count": total_near_limit_count,
				"total_stocks": total_stocks
			},
			"ratios": {
				"limit_ratio": limit_ratio,
				"active_ratio": active_ratio,
				"up_ratio": up_count / total_stocks * 100 if total_stocks > 0 else 0,
				"down_ratio": down_count / total_stocks * 100 if total_stocks > 0 else 0
			},
			"market_sentiment": self._assess_market_sentiment(up_count, down_count, total_stocks)
		}

	@staticmethod
	def _assess_market_sentiment (
			up_count: int,
			down_count: int,
			total_stocks: int
	) -> Dict[str, Any]:
		"""
		评估市场情绪

		Args:
			up_count: 涨停数量
			down_count: 跌停数量
			total_stocks: 总股票数

		Returns:
			市场情绪评估
		"""
		if total_stocks == 0:
			return {"sentiment": "neutral", "strength": 0}

		# 计算涨跌停比例
		up_ratio = up_count / total_stocks
		down_ratio = down_count / total_stocks

		# 计算情绪得分（-100到100）
		sentiment_score = (up_ratio - down_ratio) * 100

		# 确定情绪类型
		if sentiment_score > 20:
			sentiment = "extremely_bullish"
		elif sentiment_score > 10:
			sentiment = "bullish"
		elif sentiment_score > 5:
			sentiment = "slightly_bullish"
		elif sentiment_score > -5:
			sentiment = "neutral"
		elif sentiment_score > -10:
			sentiment = "slightly_bearish"
		elif sentiment_score > -20:
			sentiment = "bearish"
		else:
			sentiment = "extremely_bearish"

		return {
			"sentiment": sentiment,
			"strength": abs(sentiment_score),
			"score": sentiment_score,
			"up_ratio": up_ratio * 100,
			"down_ratio": down_ratio * 100,
			"dominance": "bullish" if up_count > down_count else "bearish" if down_count > up_count else "balanced"
		}

	async def get_limit_stocks_by_date (
			self,
			trade_date: date,
			limit_type: str = "up",  # "up", "down", or "all"
			limit: int = 100,
			skip: int = 0
	) -> List[Dict[str, Any]]:
		"""
		获取指定日期的涨跌停股票列表

		Args:
			trade_date: 交易日期
			limit_type: 涨跌停类型
			limit: 返回数量限制
			skip: 跳过数量

		Returns:
			涨跌停股票列表
		"""
		if limit_type == "up":
			condition = "ABS(d.close - l.up_limit) < 0.01"
		elif limit_type == "down":
			condition = "ABS(d.close - l.down_limit) < 0.01"
		else:  # all
			condition = "(ABS(d.close - l.up_limit) < 0.01 OR ABS(d.close - l.down_limit) < 0.01)"

		query = text(f"""
            SELECT 
                d.ts_code,
                d.close,
                d.pct_chg,
                l.up_limit,
                l.down_limit,
                CASE 
                    WHEN ABS(d.close - l.up_limit) < 0.01 THEN 'up'
                    WHEN ABS(d.close - l.down_limit) < 0.01 THEN 'down'
                    ELSE 'none'
                END as limit_type
            FROM stock_daily d
            JOIN stock_daily_limit l ON d.ts_code = l.ts_code AND d.trade_date = l.trade_date
            WHERE d.trade_date = :trade_date 
              AND {condition}
            ORDER BY ABS(d.pct_chg) DESC
            LIMIT :limit OFFSET :skip
        """)

		result = await self.session.execute(
			query,
			{"trade_date": trade_date, "limit": limit, "skip": skip}
		)
		rows = result.fetchall()

		return [
			{
				"ts_code": row.ts_code,
				"close_price": float(row.close),
				"pct_change": float(row.pct_chg),
				"up_limit_price": float(row.up_limit),
				"down_limit_price": float(row.down_limit),
				"limit_type": row.limit_type
			}
			for row in rows
		]

	# ==================== 涨跌停板分析 ====================

	async def analyze_limit_breakout (
			self,
			ts_code: str,
			analysis_date: datetime,
			lookback_days: int = 20
	) -> Optional[Dict[str, Any]]:
		"""
		分析涨跌停突破情况

		Args:
			ts_code: 股票代码
			analysis_date: 分析日期
			lookback_days: 回溯天数

		Returns:
			突破分析结果或None
		"""
		start_date = analysis_date - timedelta(days=lookback_days)

		# 获取历史涨跌停数据
		limit_data_list = await self.get_by_code_and_date_range(ts_code, start_date, analysis_date)

		if not limit_data_list:
			return None

		# 获取历史行情数据
		daily_query = text("""
            SELECT trade_date, close, pct_chg
            FROM stock_daily
            WHERE ts_code = :ts_code
              AND trade_date >= :start_date
              AND trade_date <= :end_date
            ORDER BY trade_date
        """)

		daily_result = await self.session.execute(
			daily_query,
			{"ts_code": ts_code, "start_date": start_date, "end_date": analysis_date}
		)
		daily_rows = daily_result.fetchall()

		if not daily_rows:
			return None

		# 分析突破情况
		limit_dates = []
		breakouts = []

		for limit_data in limit_data_list:
			# 找到对应的行情数据
			daily_data = None
			for row in daily_rows:
				if row.trade_date == limit_data.trade_date:
					daily_data = row
					break

			if not daily_data:
				continue

			close_price = float(daily_data.close)
			up_limit_price = float(limit_data.up_limit)
			down_limit_price = float(limit_data.down_limit)

			# 检查是否涨跌停
			is_up_limit = abs(close_price - up_limit_price) < 0.01
			is_down_limit = abs(close_price - down_limit_price) < 0.01

			if is_up_limit or is_down_limit:
				limit_type = "up" if is_up_limit else "down"
				limit_dates.append({
					"date": limit_data.trade_date,
					"type": limit_type,
					"price": close_price,
					"limit_price": up_limit_price if is_up_limit else down_limit_price
				})

				# 检查后续是否突破
				next_day = limit_data.trade_date + timedelta(days=1)
				next_daily_data = None
				for row in daily_rows:
					if row.trade_date == next_day:
						next_daily_data = row
						break

				if next_daily_data:
					next_close = float(next_daily_data.close)
					if limit_type == "up":
						is_breakout = next_close > up_limit_price
						breakout_type = "突破" if is_breakout else "未突破"
					else:
						is_breakout = next_close < down_limit_price
						breakout_type = "跌破" if is_breakout else "未跌破"

					breakouts.append({
						"limit_date": limit_data.trade_date,
						"limit_type": limit_type,
						"next_date": next_day,
						"next_close": next_close,
						"is_breakout": is_breakout,
						"breakout_type": breakout_type,
						"price_change": next_close - close_price,
						"pct_change": ((next_close - close_price) / close_price) * 100 if close_price > 0 else 0
					})

		# 计算统计
		total_limits = len(limit_dates)
		total_breakouts = sum(1 for b in breakouts if b["is_breakout"])
		breakout_rate = total_breakouts / len(breakouts) * 100 if breakouts else 0

		# 按类型统计
		up_limits = [l for l in limit_dates if l["type"] == "up"]
		down_limits = [l for l in limit_dates if l["type"] == "down"]

		up_breakouts = [b for b in breakouts if b["limit_type"] == "up" and b["is_breakout"]]
		down_breakouts = [b for b in breakouts if b["limit_type"] == "down" and b["is_breakout"]]

		up_breakout_rate = len(up_breakouts) / len(up_limits) * 100 if up_limits else 0
		down_breakout_rate = len(down_breakouts) / len(down_limits) * 100 if down_limits else 0

		return {
			"ts_code": ts_code,
			"analysis_date": analysis_date,
			"lookback_days": lookback_days,
			"summary": {
				"total_limit_days": total_limits,
				"up_limit_days": len(up_limits),
				"down_limit_days": len(down_limits),
				"total_breakouts": total_breakouts,
				"breakout_rate": breakout_rate,
				"up_breakout_rate": up_breakout_rate,
				"down_breakout_rate": down_breakout_rate
			},
			"limit_details": limit_dates,
			"breakout_details": breakouts,
			"analysis_conclusion": self._generate_breakout_conclusion(
				total_limits, breakout_rate, up_breakout_rate, down_breakout_rate
			)
		}

	@staticmethod
	def _generate_breakout_conclusion (
			total_limits: int,
			breakout_rate: float,
			up_breakout_rate: float,
			down_breakout_rate: float
	) -> Dict[str, Any]:
		"""生成突破分析结论"""
		if total_limits == 0:
			return {"message": "分析期间内无涨跌停记录", "confidence": 0}

		conclusions = []
		confidence = 0

		# 涨停突破分析
		if up_breakout_rate > 70:
			conclusions.append("涨停后突破概率较高，显示强势特征")
			confidence += 30
		elif up_breakout_rate < 30:
			conclusions.append("涨停后突破概率较低，可能存在压力")
			confidence += 20

		# 跌停突破分析
		if down_breakout_rate > 70:
			conclusions.append("跌停后跌破概率较高，显示弱势特征")
			confidence += 30
		elif down_breakout_rate < 30:
			conclusions.append("跌停后跌破概率较低，可能存在支撑")
			confidence += 20

		# 总体突破率
		if breakout_rate > 60:
			conclusions.append("总体突破率较高，市场活跃")
			confidence += 20
		elif breakout_rate < 40:
			conclusions.append("总体突破率较低，市场谨慎")
			confidence += 10

		# 置信度调整
		if total_limits < 5:
			confidence *= 0.7  # 样本少，置信度降低
			conclusions.append("样本数量较少，结论仅供参考")

		return {
			"message": "; ".join(conclusions) if conclusions else "无明显规律",
			"confidence": min(confidence, 100),
			"recommendation": "进一步分析" if confidence < 60 else "可参考"
		}

	# ==================== 辅助方法 ====================

	@staticmethod
	async def calculate_limit_prices (
			pre_close: float,
			limit_percent: float = 10.0
	) -> Dict[str, float]:
		"""
		计算涨跌停价格

		Args:
			pre_close: 前收盘价
			limit_percent: 涨跌停幅度百分比

		Returns:
			涨跌停价格字典
		"""
		up_limit = round(pre_close * (1 + limit_percent / 100), 2)
		down_limit = round(pre_close * (1 - limit_percent / 100), 2)

		return {
			"up_limit": up_limit,
			"down_limit": down_limit,
			"price_range": up_limit - down_limit,
			"up_percent": limit_percent,
			"down_percent": limit_percent
		}

	async def validate_limit_data (
			self,
			ts_code: str,
			trade_date: date
	) -> Dict[str, Any]:
		"""
		验证涨跌停数据

		Args:
			ts_code: 股票代码
			trade_date: 交易日期

		Returns:
			验证结果
		"""
		limit_data = await self.get_by_code_and_date(ts_code, trade_date)
		if not limit_data:
			return {"status": "missing", "message": "涨跌停数据缺失"}

		# 获取行情数据验证
		daily_query = text("""
            SELECT close, pre_close
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

		close_price = float(daily_row.close)
		pre_close = float(daily_row.pre_close)

		# 验证涨跌停价格计算
		calculated = await self.calculate_limit_prices(pre_close)

		issues = []

		# 检查涨停价
		if abs(float(limit_data.up_limit) - calculated["up_limit"]) > 0.02:
			issues.append(f"涨停价计算偏差较大: 实际{limit_data.up_limit}, 计算{calculated['up_limit']}")

		# 检查跌停价
		if abs(float(limit_data.down_limit) - calculated["down_limit"]) > 0.02:
			issues.append(f"跌停价计算偏差较大: 实际{limit_data.down_limit}, 计算{calculated['down_limit']}")

		# 检查价格是否在涨跌停范围内
		if close_price > float(limit_data.up_limit) + 0.01:
			issues.append("收盘价高于涨停价")
		elif close_price < float(limit_data.down_limit) - 0.01:
			issues.append("收盘价低于跌停价")

		return {
			"status": "valid" if not issues else "issues",
			"issues": issues,
			"validation_details": {
				"actual_up_limit": float(limit_data.up_limit),
				"calculated_up_limit": calculated["up_limit"],
				"actual_down_limit": float(limit_data.down_limit),
				"calculated_down_limit": calculated["down_limit"],
				"close_price": close_price,
				"pre_close": pre_close,
				"deviation_up": abs(float(limit_data.up_limit) - calculated["up_limit"]),
				"deviation_down": abs(float(limit_data.down_limit) - calculated["down_limit"])
			}
		}
