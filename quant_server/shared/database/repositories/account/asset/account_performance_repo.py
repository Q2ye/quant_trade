# shared/database/repositories/timeseries/account_performance_repo.py
from typing import List, Dict, Any, Optional, Tuple
from datetime import date, datetime, timedelta
from decimal import Decimal
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, func, and_, desc, text
from sqlalchemy.sql import literal_column

from quant_server.shared.database.models.business_models import AccountDailyPerformance
from quant_server.shared.database.repositories.base import BaseRepository


class AccountDailyPerformanceRepository(BaseRepository[AccountDailyPerformance]):
	"""账户每日绩效数据仓库（超表专用）"""

	def __init__ (self, session: AsyncSession):
		super().__init__(session, AccountDailyPerformance)

	async def get_user_performance (self, user_id: int, start_date: Optional[date] = None,
	                                end_date: Optional[date] = None) -> List[AccountDailyPerformance]:
		"""获取用户账户绩效时间序列"""
		query = select(self.model).where(self.model.user_id == user_id)

		if start_date:
			query = query.where(self.model.trade_date >= start_date)
		if end_date:
			query = query.where(self.model.trade_date <= end_date)

		query = query.order_by(self.model.trade_date)
		result = await self.session.execute(query)
		return result.scalars().all()

	async def get_performance_summary (self, user_id: int, start_date: Optional[date] = None,
	                                   end_date: Optional[date] = None) -> Dict[str, Any]:
		"""获取账户绩效汇总统计"""
		query = select(self.model).where(self.model.user_id == user_id)

		if start_date:
			query = query.where(self.model.trade_date >= start_date)
		if end_date:
			query = query.where(self.model.trade_date <= end_date)

		query = query.order_by(self.model.trade_date)
		result = await self.session.execute(query)
		records = result.scalars().all()

		if not records:
			return {
				"total_days": 0,
				"total_pnl": 0,
				"total_return": 0,
				"sharpe_ratio": 0,
				"max_drawdown": 0,
				"win_rate": 0
			}

		# 计算基本统计
		total_days = len(records)
		returns = [float(record.daily_return) for record in records]
		pnls = [float(record.daily_pnl) for record in records]

		total_pnl = sum(pnls)
		total_return = (float(records[-1].total_asset) - float(records[0].total_asset)) / float(
			records[0].total_asset) if float(records[0].total_asset) > 0 else 0

		# 计算夏普比率（假设无风险利率为0.02）
		import numpy as np
		returns_array = np.array(returns)
		if len(returns_array) > 1 and returns_array.std() > 0:
			sharpe_ratio = (returns_array.mean() - 0.02 / 252) / returns_array.std() * np.sqrt(252)
		else:
			sharpe_ratio = 0

		# 计算最大回撤
		assets = [float(record.total_asset) for record in records]
		max_drawdown = self._calculate_max_drawdown(assets)

		# 计算胜率
		win_days = sum(1 for pnl in pnls if pnl > 0)
		win_rate = win_days / total_days if total_days > 0 else 0

		return {
			"total_days": total_days,
			"total_pnl": total_pnl,
			"total_return": total_return,
			"sharpe_ratio": float(sharpe_ratio),
			"max_drawdown": max_drawdown,
			"win_rate": win_rate,
			"start_date": records[0].trade_date,
			"end_date": records[-1].trade_date,
			"start_asset": float(records[0].total_asset),
			"end_asset": float(records[-1].total_asset)
		}

	async def get_performance_by_period (self, user_id: int, period: str = 'daily') -> List[Dict[str, Any]]:
		"""获取不同时间周期的绩效数据"""
		if period == 'daily':
			# 直接返回日数据
			query = (
				select(self.model)
				.where(self.model.user_id == user_id)
				.order_by(self.model.trade_date)
			)
			result = await self.session.execute(query)
			records = result.scalars().all()

			return [
				{
					"period": record.trade_date.strftime('%Y-%m-%d'),
					"total_asset": float(record.total_asset),
					"cash": float(record.cash),
					"market_value": float(record.market_value),
					"daily_pnl": float(record.daily_pnl),
					"daily_return": float(record.daily_return)
				}
				for record in records
			]

		elif period == 'weekly':
			# 按周聚合
			weekly_query = text("""
                SELECT 
                    DATE_TRUNC('week', trade_date)::date as week_start,
                    COUNT(*) as days,
                    MAX(total_asset) as max_asset,
                    MIN(total_asset) as min_asset,
                    FIRST_VALUE(total_asset) OVER w as week_start_asset,
                    LAST_VALUE(total_asset) OVER w as week_end_asset
                FROM account_daily_performance
                WHERE user_id = :user_id
                WINDOW w AS (
                    PARTITION BY DATE_TRUNC('week', trade_date)
                    ORDER BY trade_date
                    ROWS BETWEEN UNBOUNDED PRECEDING AND UNBOUNDED FOLLOWING
                )
                GROUP BY DATE_TRUNC('week', trade_date)
                ORDER BY week_start
            """)

			result = await self.session.execute(weekly_query, {"user_id": user_id})
			weekly_data = []

			for row in result.all():
				if row.week_start_asset and row.week_start_asset > 0:
					weekly_return = (row.week_end_asset - row.week_start_asset) / row.week_start_asset
				else:
					weekly_return = 0

				weekly_data.append({
					"period": row.week_start.strftime('%Y-W%W'),
					"week_start": row.week_start,
					"days": row.days,
					"start_asset": float(row.week_start_asset or 0),
					"end_asset": float(row.week_end_asset or 0),
					"max_asset": float(row.max_asset or 0),
					"min_asset": float(row.min_asset or 0),
					"weekly_return": float(weekly_return)
				})

			return weekly_data

		elif period == 'monthly':
			# 按月聚合
			monthly_query = text("""
                SELECT 
                    DATE_TRUNC('month', trade_date)::date as month_start,
                    EXTRACT(YEAR FROM trade_date) as year,
                    EXTRACT(MONTH FROM trade_date) as month,
                    COUNT(*) as days,
                    MAX(total_asset) as max_asset,
                    MIN(total_asset) as min_asset,
                    FIRST_VALUE(total_asset) OVER w as month_start_asset,
                    LAST_VALUE(total_asset) OVER w as month_end_asset
                FROM account_daily_performance
                WHERE user_id = :user_id
                WINDOW w AS (
                    PARTITION BY DATE_TRUNC('month', trade_date)
                    ORDER BY trade_date
                    ROWS BETWEEN UNBOUNDED PRECEDING AND UNBOUNDED FOLLOWING
                )
                GROUP BY DATE_TRUNC('month', trade_date), EXTRACT(YEAR FROM trade_date), EXTRACT(MONTH FROM trade_date)
                ORDER BY month_start
            """)

			result = await self.session.execute(monthly_query, {"user_id": user_id})
			monthly_data = []

			for row in result.all():
				if row.month_start_asset and row.month_start_asset > 0:
					monthly_return = (row.month_end_asset - row.month_start_asset) / row.month_start_asset
				else:
					monthly_return = 0

				monthly_data.append({
					"period": f"{int(row.year)}-{int(row.month):02d}",
					"month_start": row.month_start,
					"days": row.days,
					"start_asset": float(row.month_start_asset or 0),
					"end_asset": float(row.month_end_asset or 0),
					"max_asset": float(row.max_asset or 0),
					"min_asset": float(row.min_asset or 0),
					"monthly_return": float(monthly_return)
				})

			return monthly_data

		else:
			raise ValueError(f"Unsupported period: {period}")

	async def get_rolling_statistics (self, user_id: int, window_days: int = 20) -> List[Dict[str, Any]]:
		"""获取滚动统计数据"""
		rolling_query = text("""
            SELECT 
                trade_date,
                total_asset,
                daily_return,
                AVG(daily_return) OVER (
                    ORDER BY trade_date 
                    ROWS BETWEEN :window_days PRECEDING AND CURRENT ROW
                ) as rolling_return,
                STDDEV(daily_return) OVER (
                    ORDER BY trade_date 
                    ROWS BETWEEN :window_days PRECEDING AND CURRENT ROW
                ) as rolling_volatility,
                MIN(total_asset) OVER (
                    ORDER BY trade_date 
                    ROWS BETWEEN :window_days PRECEDING AND CURRENT ROW
                ) as rolling_min,
                MAX(total_asset) OVER (
                    ORDER BY trade_date 
                    ROWS BETWEEN :window_days PRECEDING AND CURRENT ROW
                ) as rolling_max
            FROM account_daily_performance
            WHERE user_id = :user_id
            ORDER BY trade_date
        """)

		result = await self.session.execute(
			rolling_query,
			{"user_id": user_id, "window_days": window_days}
		)

		rolling_stats = []
		for row in result.all():
			rolling_stats.append({
				"trade_date": row.trade_date,
				"total_asset": float(row.total_asset or 0),
				"daily_return": float(row.daily_return or 0),
				"rolling_return": float(row.rolling_return or 0),
				"rolling_volatility": float(row.rolling_volatility or 0),
				"rolling_min": float(row.rolling_min or 0),
				"rolling_max": float(row.rolling_max or 0)
			})

		return rolling_stats

	async def batch_create_performance (self, performance_data: List[Dict[str, Any]]) -> int:
		"""批量创建绩效记录（超表优化）"""
		now = datetime.now()
		instances = []

		for data in performance_data:
			data['created_at'] = now
			instance = self.model(**data)
			instances.append(instance)

		self.session.add_all(instances)
		await self.session.flush()
		return len(instances)

	def _calculate_max_drawdown (self, assets: List[float]) -> float:
		"""计算最大回撤"""
		if not assets:
			return 0

		max_drawdown = 0
		peak = assets[0]

		for asset in assets:
			if asset > peak:
				peak = asset

			drawdown = (peak - asset) / peak if peak > 0 else 0
			max_drawdown = max(max_drawdown, drawdown)

		return max_drawdown