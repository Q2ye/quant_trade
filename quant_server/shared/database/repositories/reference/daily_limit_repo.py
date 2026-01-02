# -*- coding: utf-8 -*-
"""
涨跌停数据仓库
位置：quant_server/shared/database/repositories/daily_limit_repo.py
职责：管理股票每日涨跌停价格、涨跌停状态等数据访问
"""

from typing import List, Optional, Dict, Any, Tuple
from datetime import datetime, date, timedelta
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, and_, or_, desc, func, text
from sqlalchemy.orm import selectinload, joinedload

from quant_server.shared.database.repositories.base import BaseRepository
from quant_server.shared.database.models.data_models import (
	StockDailyLimit,
	StockDaily
)


class DailyLimitRepository:
	"""涨跌停数据仓库 - 负责股票涨跌停相关数据访问"""

	def __init__ (self, session: AsyncSession):
		self.session = session
		self.daily_limit_repo = BaseRepository[StockDailyLimit](session, StockDailyLimit)

	# ==================== 涨跌停数据操作 ====================

	async def get_daily_limit (
			self,
			ts_code: str,
			trade_date: date
	) -> Optional[StockDailyLimit]:
		"""
		获取指定日期的涨跌停数据

		Args:
			ts_code: 股票代码
			trade_date: 交易日期

		Returns:
			涨跌停数据或None
		"""
		return await self.daily_limit_repo.get_by(
			ts_code=ts_code,
			trade_date=trade_date
		)

	async def get_daily_limits_in_range (
			self,
			ts_code: str,
			start_date: date,
			end_date: date
	) -> List[StockDailyLimit]:
		"""
		获取指定时间范围内的涨跌停数据

		Args:
			ts_code: 股票代码
			start_date: 开始日期
			end_date: 结束日期

		Returns:
			涨跌停数据列表
		"""
		query = select(StockDailyLimit).where(
			and_(
				StockDailyLimit.ts_code == ts_code,
				StockDailyLimit.trade_date >= start_date,
				StockDailyLimit.trade_date <= end_date
			)
		).order_by(StockDailyLimit.trade_date)

		result = await self.session.execute(query)
		return result.scalars().all()

	async def get_latest_daily_limit (self, ts_code: str) -> Optional[StockDailyLimit]:
		"""
		获取最新的涨跌停数据

		Args:
			ts_code: 股票代码

		Returns:
			最新的涨跌停数据或None
		"""
		query = select(StockDailyLimit).where(
			StockDailyLimit.ts_code == ts_code
		).order_by(desc(StockDailyLimit.trade_date)).limit(1)

		result = await self.session.execute(query)
		return result.scalar_one_or_none()

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
		return await self.daily_limit_repo.get_many(
			trade_date=trade_date,
			skip=skip,
			limit=limit
		)

	async def create_daily_limit (self, limit_data: Dict[str, Any]) -> StockDailyLimit:
		"""
		创建涨跌停数据记录

		Args:
			limit_data: 涨跌停数据

		Returns:
			创建的涨跌停数据记录
		"""
		return await self.daily_limit_repo.create(limit_data)

	async def batch_create_daily_limits (self, limits_data: List[Dict[str, Any]]) -> List[StockDailyLimit]:
		"""
		批量创建涨跌停数据记录

		Args:
			limits_data: 涨跌停数据列表

		Returns:
			创建的涨跌停数据记录列表
		"""
		return await self.daily_limit_repo.batch_create(limits_data)

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
		limit_data = await self.get_daily_limit(ts_code, trade_date)
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

		close_price = daily_row.close
		pre_close = daily_row.pre_close

		# 分析涨跌停状态
		up_limit_price = limit_data.up_limit
		down_limit_price = limit_data.down_limit

		# 判断是否涨停
		is_up_limit = abs(close_price - up_limit_price) < 0.01
		is_down_limit = abs(close_price - down_limit_price) < 0.01

		# 计算接近度
		if close_price > pre_close:  # 上涨
			proximity_to_limit = (close_price - pre_close) / (up_limit_price - pre_close)
			limit_type = "up" if is_up_limit else "none"
		else:  # 下跌
			proximity_to_limit = (pre_close - close_price) / (pre_close - down_limit_price)
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
			"price_range": limit_data.price_range,
			"up_percent": limit_data.up_percent,
			"down_percent": limit_data.down_percent
		}

	async def get_limit_streak (
			self,
			ts_code: str,
			end_date: date,
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
		limit_data_list = await self.get_daily_limits_in_range(ts_code, start_date, end_date)

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

			close_price = daily_row.close
			up_limit_price = limit_data.up_limit
			down_limit_price = limit_data.down_limit

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
		up_count = up_result.fetchone()[0] or 0

		# 统计跌停股票
		down_limit_query = text("""
                                SELECT COUNT(DISTINCT d.ts_code) as down_limit_count
                                FROM stock_daily d
                                         JOIN stock_daily_limit l
                                              ON d.ts_code = l.ts_code AND d.trade_date = l.trade_date
                                WHERE d.trade_date = :trade_date
                                  AND ABS(d.close - l.down_limit) < 0.01
		                        """)

		down_result = await self.session.execute(down_limit_query, {"trade_date": trade_date})
		down_count = down_result.fetchone()[0] or 0

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
		near_up_count = near_up_result.fetchone()[0] or 0

		# 统计接近跌停的股票（跌幅<-9%）
		near_down_query = text("""
                               SELECT COUNT(DISTINCT d.ts_code) as near_down_count
                               FROM stock_daily d
                                        JOIN stock_daily_limit l
                                             ON d.ts_code = l.ts_code AND d.trade_date = l.trade_date
                               WHERE d.trade_date = :trade_date
                                 AND d.pct_chg < -9.0
                                 AND ABS(d.close - l.down_limit) >= 0.01
		                       """)

		near_down_result = await self.session.execute(near_down_query, {"trade_date": trade_date})
		near_down_count = near_down_result.fetchone()[0] or 0

		return {
			"trade_date": trade_date,
			"up_limit_count": up_count,
			"down_limit_count": down_count,
			"near_up_limit_count": near_up_count,
			"near_down_limit_count": near_down_count,
			"total_limit_count": up_count + down_count,
			"limit_ratio": (up_count + down_count) / (up_count + down_count + near_up_count + near_down_count) if (
						                                                                                                      up_count + down_count + near_up_count + near_down_count) > 0 else 0
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
				"close_price": row.close,
				"pct_change": row.pct_chg,
				"up_limit_price": row.up_limit,
				"down_limit_price": row.down_limit,
				"limit_type": row.limit_type
			}
			for row in rows
		]

	# ==================== 涨跌停板分析 ====================

	async def analyze_limit_breakout (
			self,
			ts_code: str,
			analysis_date: date,
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
		limit_data_list = await self.get_daily_limits_in_range(ts_code, start_date, analysis_date)

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

			close_price = daily_data.close
			up_limit_price = limit_data.up_limit
			down_limit_price = limit_data.down_limit

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
					next_close = next_daily_data.close
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
						"pct_change": ((next_close - close_price) / close_price) * 100
					})

		# 计算统计
		total_limits = len(limit_dates)
		total_breakouts = sum(1 for b in breakouts if b["is_breakout"])
		breakout_rate = total_breakouts / len(breakouts) if breakouts else 0

		# 按类型统计
		up_limits = [l for l in limit_dates if l["type"] == "up"]
		down_limits = [l for l in limit_dates if l["type"] == "down"]

		up_breakouts = [b for b in breakouts if b["limit_type"] == "up" and b["is_breakout"]]
		down_breakouts = [b for b in breakouts if b["limit_type"] == "down" and b["is_breakout"]]

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
				"up_breakout_rate": len(up_breakouts) / len(up_limits) if up_limits else 0,
				"down_breakout_rate": len(down_breakouts) / len(down_limits) if down_limits else 0
			},
			"limit_details": limit_dates,
			"breakout_details": breakouts
		}

	# ==================== 批量操作 ====================

	async def batch_upsert_daily_limits (self, limits_data: List[Dict[str, Any]]) -> List[StockDailyLimit]:
		"""
		批量插入或更新涨跌停数据

		Args:
			limits_data: 涨跌停数据列表

		Returns:
			更新后的涨跌停数据记录列表
		"""
		return await self.daily_limit_repo.batch_upsert(
			match_fields=["ts_code", "trade_date"],
			data_list=limits_data
		)

	async def delete_old_data (self, before_date: date) -> int:
		"""
		删除指定日期之前的数据

		Args:
			before_date: 截止日期

		Returns:
			删除的记录数
		"""
		return await self.daily_limit_repo.delete_by(
			trade_date__lt=before_date
		)

	# ==================== 辅助方法 ====================

	async def calculate_limit_prices (
			self,
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