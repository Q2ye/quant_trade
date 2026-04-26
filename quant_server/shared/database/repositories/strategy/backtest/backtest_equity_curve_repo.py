# shared/database/repositories/timeseries/backtest_equity_curve_repo.py
from datetime import date, datetime
from typing import List, Dict, Any, Optional

from sqlalchemy import select, func, text
from sqlalchemy.ext.asyncio import AsyncSession

from quant_server.shared.database.models.business_models import BacktestEquityCurve
from quant_server.shared.database.repositories.base import BaseRepository


class BacktestEquityCurveRepository(BaseRepository[BacktestEquityCurve]):
	"""回测净值曲线数据仓库（超表专用）"""

	def __init__ (self, session: AsyncSession):
		super().__init__(session, BacktestEquityCurve)

	async def get_equity_curve (self, task_id: str, start_date: Optional[date] = None,
	                            end_date: Optional[date] = None) -> List[BacktestEquityCurve]:
		"""获取净值曲线数据"""
		query = select(self.model).where(self.model.task_id == task_id)

		if start_date:
			query = query.where(self.model.trade_date >= start_date)
		if end_date:
			query = query.where(self.model.trade_date <= end_date)

		query = query.order_by(self.model.trade_date)
		result = await self.session.execute(query)
		return result.scalars().all()

	async def get_equity_summary (self, task_id: str) -> Dict[str, Any]:
		"""获取净值曲线汇总统计"""
		# 基本统计
		stats_query = (
			select(
				func.min(self.model.trade_date).label('first_date'),
				func.max(self.model.trade_date).label('last_date'),
				func.count().label('total_days'),
				func.min(self.model.equity).label('min_equity'),
				func.max(self.model.equity).label('max_equity'),
				func.avg(self.model.equity).label('avg_equity')
			)
			.where(self.model.task_id == task_id)
		)

		stats_result = await self.session.execute(stats_query)
		stats = stats_result.first()

		# 获取初始和最终净值
		first_last_query = (
			select(self.model.equity, self.model.trade_date)
			.where(self.model.task_id == task_id)
			.order_by(self.model.trade_date)
		)

		first_last_result = await self.session.execute(first_last_query)
		records = first_last_result.all()

		if len(records) < 2:
			return {
				"first_date": stats.first_date,
				"last_date": stats.last_date,
				"total_days": stats.total_days,
				"total_return": 0,
				"annual_return": 0
			}

		first_equity = float(records[0].equity)
		last_equity = float(records[-1].equity)
		days = (stats.last_date - stats.first_date).days

		total_return = (last_equity - first_equity) / first_equity if first_equity > 0 else 0
		annual_return = ((1 + total_return) ** (365.25 / days) - 1) if days > 0 else 0

		return {
			"first_date": stats.first_date,
			"last_date": stats.last_date,
			"total_days": stats.total_days,
			"first_equity": first_equity,
			"last_equity": last_equity,
			"min_equity": float(stats.min_equity or 0),
			"max_equity": float(stats.max_equity or 0),
			"avg_equity": float(stats.avg_equity or 0),
			"total_return": total_return,
			"annual_return": annual_return
		}

	async def get_drawdown_analysis (self, task_id: str) -> Dict[str, Any]:
		"""获取回撤分析"""
		# 使用窗口函数计算回撤
		drawdown_query = text("""
            WITH equity_data AS (
                SELECT 
                    trade_date,
                    equity,
                    MAX(equity) OVER (ORDER BY trade_date) as peak_equity
                FROM backtest_equity_curves
                WHERE task_id = :task_id
                ORDER BY trade_date
            )
            SELECT 
                trade_date,
                equity,
                peak_equity,
                (equity - peak_equity) / peak_equity as drawdown
            FROM equity_data
            ORDER BY trade_date
        """)

		result = await self.session.execute(drawdown_query, {"task_id": task_id})
		drawdown_records = result.all()

		if not drawdown_records:
			return {"max_drawdown": 0, "drawdown_duration": 0}

		# 计算最大回撤
		max_drawdown = min(float(record.drawdown or 0) for record in drawdown_records)

		# 计算最大回撤持续时间
		in_drawdown = False
		drawdown_start = None
		max_duration = 0

		for record in drawdown_records:
			if float(record.drawdown or 0) < -0.01:  # 超过1%的回撤
				if not in_drawdown:
					in_drawdown = True
					drawdown_start = record.trade_date
			else:
				if in_drawdown and drawdown_start:
					duration = (record.trade_date - drawdown_start).days
					max_duration = max(max_duration, duration)
					in_drawdown = False

		return {
			"max_drawdown": abs(max_drawdown),
			"drawdown_duration": max_duration,
			"drawdown_records": [
				{
					"trade_date": record.trade_date,
					"equity": float(record.equity),
					"peak_equity": float(record.peak_equity),
					"drawdown": float(record.drawdown or 0)
				}
				for record in drawdown_records[:100]  # 限制返回数量
			]
		}

	async def get_monthly_returns (self, task_id: str) -> List[Dict[str, Any]]:
		"""获取月度收益率"""
		monthly_query = text("""
            SELECT 
                EXTRACT(YEAR FROM trade_date) as year,
                EXTRACT(MONTH FROM trade_date) as month,
                MIN(trade_date) as first_date,
                MAX(trade_date) as last_date,
                MIN(equity) as min_equity,
                MAX(equity) as max_equity,
                LAST_VALUE(equity) OVER (
                    PARTITION BY EXTRACT(YEAR FROM trade_date), EXTRACT(MONTH FROM trade_date)
                    ORDER BY trade_date
                    ROWS BETWEEN UNBOUNDED PRECEDING AND UNBOUNDED FOLLOWING
                ) as end_equity,
                FIRST_VALUE(equity) OVER (
                    PARTITION BY EXTRACT(YEAR FROM trade_date), EXTRACT(MONTH FROM trade_date)
                    ORDER BY trade_date
                    ROWS BETWEEN UNBOUNDED PRECEDING AND UNBOUNDED FOLLOWING
                ) as start_equity
            FROM backtest_equity_curves
            WHERE task_id = :task_id
            GROUP BY EXTRACT(YEAR FROM trade_date), EXTRACT(MONTH FROM trade_date)
            ORDER BY year, month
        """)

		result = await self.session.execute(monthly_query, {"task_id": task_id})

		monthly_returns = []
		for row in result.all():
			if row.start_equity and row.start_equity > 0:
				monthly_return = (row.end_equity - row.start_equity) / row.start_equity
			else:
				monthly_return = 0

			monthly_returns.append({
				"year": int(row.year),
				"month": int(row.month),
				"period": f"{int(row.year)}-{int(row.month):02d}",
				"start_equity": float(row.start_equity or 0),
				"end_equity": float(row.end_equity or 0),
				"monthly_return": float(monthly_return),
				"min_equity": float(row.min_equity or 0),
				"max_equity": float(row.max_equity or 0)
			})

		return monthly_returns

	async def batch_create_equity_curves (self, task_id: str, equity_data: List[Dict[str, Any]]) -> int:
		"""批量创建净值曲线记录（超表优化）"""
		now = datetime.now()
		instances = []

		for data in equity_data:
			# 确保task_id一致
			data['task_id'] = task_id
			data['created_at'] = now

			instance = self.model(**data)
			instances.append(instance)

		self.session.add_all(instances)
		await self.session.flush()
		return len(instances)
