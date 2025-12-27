# -*- coding: utf-8 -*-
"""
绩效数据仓库
提供账户和策略绩效数据的统一访问接口
位置：shared/database/repositories/performance_repo.py
"""

from typing import List, Optional, Dict, Any
from datetime import date, datetime, timedelta
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, and_, or_, func, desc, between

from .base import BaseRepository
from quant_server.shared.database.models.business_models import (
	AccountDailyPerformance,
	StrategyDailyPerformance
)


class PerformanceRepository:
	"""绩效数据Repository - 纯数据访问"""

	def __init__ (self, session: AsyncSession):
		self.session = session
		self.account_repo = BaseRepository(session, AccountDailyPerformance)
		self.strategy_repo = BaseRepository(session, StrategyDailyPerformance)

	# ==================== 账户绩效操作 ====================

	async def create_account_performance (
			self,
			data: Dict[str, Any]
	) -> AccountDailyPerformance:
		"""创建账户绩效记录"""
		return await self.account_repo.create(data)

	async def get_account_performance (
			self,
			user_id: int,
			trade_date: date
	) -> Optional[AccountDailyPerformance]:
		"""获取账户绩效记录"""
		return await self.account_repo.get_one(
			and_(
				AccountDailyPerformance.user_id == user_id,
				AccountDailyPerformance.trade_date == trade_date
			)
		)

	async def get_account_performance_range (
			self,
			user_id: int,
			start_date: date,
			end_date: date
	) -> List[AccountDailyPerformance]:
		"""获取账户绩效时间范围数据"""
		return await self.account_repo.get_many(
			and_(
				AccountDailyPerformance.user_id == user_id,
				AccountDailyPerformance.trade_date >= start_date,
				AccountDailyPerformance.trade_date <= end_date
			),
			order_by=AccountDailyPerformance.trade_date.asc()
		)

	async def get_latest_account_performance (
			self,
			user_id: int,
			days: int = 30
	) -> List[AccountDailyPerformance]:
		"""获取最新的账户绩效数据"""
		end_date = datetime.now().date()
		start_date = end_date - timedelta(days=days - 1)

		return await self.get_account_performance_range(user_id, start_date, end_date)

	async def get_account_performance_summary (
			self,
			user_id: int,
			start_date: date,
			end_date: date
	) -> Dict[str, Any]:
		"""获取账户绩效汇总统计"""
		# 获取基础数据
		performances = await self.get_account_performance_range(user_id, start_date, end_date)

		if not performances:
			return {}

		# 计算统计指标
		total_asset_values = [p.total_asset for p in performances]
		daily_returns = [p.daily_return for p in performances]
		daily_pnls = [p.daily_pnl for p in performances]

		# 找到最高和最低
		max_asset = max(total_asset_values) if total_asset_values else 0
		min_asset = min(total_asset_values) if total_asset_values else 0
		max_drawdown = 0

		# 计算最大回撤
		peak = total_asset_values[0] if total_asset_values else 0
		for asset in total_asset_values:
			if asset > peak:
				peak = asset
			drawdown = (peak - asset) / peak if peak > 0 else 0
			if drawdown > max_drawdown:
				max_drawdown = drawdown

		# 计算总收益
		if len(total_asset_values) >= 2:
			first_asset = total_asset_values[0]
			last_asset = total_asset_values[-1]
			total_return = (last_asset - first_asset) / first_asset if first_asset > 0 else 0
		else:
			total_return = 0

		# 计算日均收益
		avg_daily_return = sum(daily_returns) / len(daily_returns) if daily_returns else 0

		# 计算胜率（正收益天数比例）
		positive_days = sum(1 for r in daily_returns if r > 0)
		win_rate = positive_days / len(daily_returns) if daily_returns else 0

		return {
			'user_id': user_id,
			'start_date': start_date,
			'end_date': end_date,
			'total_return': float(total_return),
			'avg_daily_return': float(avg_daily_return),
			'max_drawdown': float(max_drawdown),
			'win_rate': float(win_rate),
			'max_asset': float(max_asset),
			'min_asset': float(min_asset),
			'last_asset': float(total_asset_values[-1]) if total_asset_values else 0,
			'total_days': len(performances),
			'positive_days': positive_days
		}

	async def get_account_performance_comparison (
			self,
			user_ids: List[int],
			trade_date: date
	) -> List[Dict[str, Any]]:
		"""获取多个账户的绩效对比"""
		query = select(AccountDailyPerformance).where(
			and_(
				AccountDailyPerformance.user_id.in_(user_ids),
				AccountDailyPerformance.trade_date == trade_date
			)
		)

		result = await self.session.execute(query)
		performances = result.scalars().all()

		return [
			{
				'user_id': p.user_id,
				'trade_date': p.trade_date,
				'total_asset': float(p.total_asset),
				'cash': float(p.cash),
				'market_value': float(p.market_value),
				'daily_pnl': float(p.daily_pnl),
				'daily_return': float(p.daily_return)
			}
			for p in performances
		]

	# ==================== 策略绩效操作 ====================

	async def create_strategy_performance (
			self,
			data: Dict[str, Any]
	) -> StrategyDailyPerformance:
		"""创建策略绩效记录"""
		return await self.strategy_repo.create(data)

	async def get_strategy_performance (
			self,
			strategy_id: str,
			trade_date: date
	) -> Optional[StrategyDailyPerformance]:
		"""获取策略绩效记录"""
		return await self.strategy_repo.get_one(
			and_(
				StrategyDailyPerformance.strategy_id == strategy_id,
				StrategyDailyPerformance.trade_date == trade_date
			)
		)

	async def get_strategy_performance_range (
			self,
			strategy_id: str,
			start_date: date,
			end_date: date
	) -> List[StrategyDailyPerformance]:
		"""获取策略绩效时间范围数据"""
		return await self.strategy_repo.get_many(
			and_(
				StrategyDailyPerformance.strategy_id == strategy_id,
				StrategyDailyPerformance.trade_date >= start_date,
				StrategyDailyPerformance.trade_date <= end_date
			),
			order_by=StrategyDailyPerformance.trade_date.asc()
		)

	async def get_latest_strategy_performance (
			self,
			strategy_id: str,
			days: int = 30
	) -> List[StrategyDailyPerformance]:
		"""获取最新的策略绩效数据"""
		end_date = datetime.now().date()
		start_date = end_date - timedelta(days=days - 1)

		return await self.get_strategy_performance_range(strategy_id, start_date, end_date)

	async def get_strategy_performance_summary (
			self,
			strategy_id: str,
			start_date: date,
			end_date: date
	) -> Dict[str, Any]:
		"""获取策略绩效汇总统计"""
		# 获取基础数据
		performances = await self.get_strategy_performance_range(strategy_id, start_date, end_date)

		if not performances:
			return {}

		# 提取数据
		daily_returns = [p.daily_return for p in performances]
		total_returns = [p.total_return for p in performances]
		max_drawdowns = [p.max_drawdown for p in performances]
		sharpe_ratios = [p.sharpe_ratio for p in performances if p.sharpe_ratio]

		# 计算统计指标
		avg_daily_return = sum(daily_returns) / len(daily_returns) if daily_returns else 0
		avg_total_return = sum(total_returns) / len(total_returns) if total_returns else 0
		avg_max_drawdown = sum(max_drawdowns) / len(max_drawdowns) if max_drawdowns else 0
		avg_sharpe_ratio = sum(sharpe_ratios) / len(sharpe_ratios) if sharpe_ratios else 0

		# 计算波动率（标准差）
		if len(daily_returns) > 1:
			import statistics
			volatility = statistics.stdev(daily_returns)
		else:
			volatility = 0

		# 计算胜率
		positive_days = sum(1 for r in daily_returns if r > 0)
		win_rate = positive_days / len(daily_returns) if daily_returns else 0

		# 找到最佳和最差表现
		best_return = max(daily_returns) if daily_returns else 0
		worst_return = min(daily_returns) if daily_returns else 0

		return {
			'strategy_id': strategy_id,
			'start_date': start_date,
			'end_date': end_date,
			'avg_daily_return': float(avg_daily_return),
			'avg_total_return': float(avg_total_return),
			'avg_max_drawdown': float(avg_max_drawdown),
			'avg_sharpe_ratio': float(avg_sharpe_ratio),
			'volatility': float(volatility),
			'win_rate': float(win_rate),
			'best_return': float(best_return),
			'worst_return': float(worst_return),
			'total_days': len(performances),
			'positive_days': positive_days
		}

	async def get_strategy_ranking (
			self,
			trade_date: date,
			metric: str = 'total_return',  # 'total_return', 'sharpe_ratio', 'daily_return'
			top_n: int = 20
	) -> List[Dict[str, Any]]:
		"""获取策略排名"""
		if metric == 'total_return':
			order_column = StrategyDailyPerformance.total_return.desc()
		elif metric == 'sharpe_ratio':
			order_column = StrategyDailyPerformance.sharpe_ratio.desc()
		elif metric == 'daily_return':
			order_column = StrategyDailyPerformance.daily_return.desc()
		else:
			order_column = StrategyDailyPerformance.total_return.desc()

		query = select(
			StrategyDailyPerformance
		).where(
			StrategyDailyPerformance.trade_date == trade_date
		).order_by(
			order_column
		).limit(top_n)

		result = await self.session.execute(query)
		performances = result.scalars().all()

		return [
			{
				'rank': idx + 1,
				'strategy_id': p.strategy_id,
				'trade_date': p.trade_date,
				'daily_return': float(p.daily_return),
				'total_return': float(p.total_return),
				'max_drawdown': float(p.max_drawdown),
				'sharpe_ratio': float(p.sharpe_ratio) if p.sharpe_ratio else 0
			}
			for idx, p in enumerate(performances)
		]

	async def get_strategy_performance_comparison (
			self,
			strategy_ids: List[str],
			trade_date: date
	) -> List[Dict[str, Any]]:
		"""获取多个策略的绩效对比"""
		query = select(StrategyDailyPerformance).where(
			and_(
				StrategyDailyPerformance.strategy_id.in_(strategy_ids),
				StrategyDailyPerformance.trade_date == trade_date
			)
		)

		result = await self.session.execute(query)
		performances = result.scalars().all()

		return [
			{
				'strategy_id': p.strategy_id,
				'trade_date': p.trade_date,
				'daily_return': float(p.daily_return),
				'total_return': float(p.total_return),
				'max_drawdown': float(p.max_drawdown),
				'sharpe_ratio': float(p.sharpe_ratio) if p.sharpe_ratio else 0
			}
			for p in performances
		]

	# ==================== 批量操作 ====================

	async def batch_create_account_performance (
			self,
			data_list: List[Dict[str, Any]]
	) -> List[AccountDailyPerformance]:
		"""批量创建账户绩效记录"""
		return await self.account_repo.batch_create(data_list)

	async def batch_create_strategy_performance (
			self,
			data_list: List[Dict[str, Any]]
	) -> List[StrategyDailyPerformance]:
		"""批量创建策略绩效记录"""
		return await self.strategy_repo.batch_create(data_list)

	async def batch_upsert_account_performance (
			self,
			data_list: List[Dict[str, Any]],
			match_fields: List[str] = ['user_id', 'trade_date']
	) -> List[AccountDailyPerformance]:
		"""批量插入或更新账户绩效记录"""
		return await self.account_repo.batch_upsert(data_list, match_fields)

	async def batch_upsert_strategy_performance (
			self,
			data_list: List[Dict[str, Any]],
			match_fields: List[str] = ['strategy_id', 'trade_date']
	) -> List[StrategyDailyPerformance]:
		"""批量插入或更新策略绩效记录"""
		return await self.strategy_repo.batch_upsert(data_list, match_fields)

	# ==================== 统计查询 ====================

	async def get_performance_dates (
			self,
			user_id: Optional[int] = None,
			strategy_id: Optional[str] = None
	) -> List[date]:
		"""获取有绩效数据的日期列表"""
		if user_id:
			# 账户绩效日期
			query = select(AccountDailyPerformance.trade_date).where(
				AccountDailyPerformance.user_id == user_id
			).distinct().order_by(
				AccountDailyPerformance.trade_date.desc()
			)
		elif strategy_id:
			# 策略绩效日期
			query = select(StrategyDailyPerformance.trade_date).where(
				StrategyDailyPerformance.strategy_id == strategy_id
			).distinct().order_by(
				StrategyDailyPerformance.trade_date.desc()
			)
		else:
			# 所有绩效日期
			account_dates = select(AccountDailyPerformance.trade_date).distinct()
			strategy_dates = select(StrategyDailyPerformance.trade_date).distinct()
			query = account_dates.union(strategy_dates)

		result = await self.session.execute(query)
		return [row[0] for row in result.all()]

	async def get_performance_stats (
			self,
			start_date: date,
			end_date: date
	) -> Dict[str, Any]:
		"""获取绩效数据统计"""
		# 账户绩效统计
		account_count = await self.session.execute(
			select(func.count()).select_from(AccountDailyPerformance).where(
				and_(
					AccountDailyPerformance.trade_date >= start_date,
					AccountDailyPerformance.trade_date <= end_date
				)
			)
		)
		account_count_value = account_count.scalar() or 0

		# 策略绩效统计
		strategy_count = await self.session.execute(
			select(func.count()).select_from(StrategyDailyPerformance).where(
				and_(
					StrategyDailyPerformance.trade_date >= start_date,
					StrategyDailyPerformance.trade_date <= end_date
				)
			)
		)
		strategy_count_value = strategy_count.scalar() or 0

		# 最新日期
		latest_account_date = await self.session.execute(
			select(func.max(AccountDailyPerformance.trade_date))
		)
		latest_account_date_value = latest_account_date.scalar()

		latest_strategy_date = await self.session.execute(
			select(func.max(StrategyDailyPerformance.trade_date))
		)
		latest_strategy_date_value = latest_strategy_date.scalar()

		return {
			'start_date': start_date,
			'end_date': end_date,
			'account_record_count': account_count_value,
			'strategy_record_count': strategy_count_value,
			'total_record_count': account_count_value + strategy_count_value,
			'latest_account_date': latest_account_date_value,
			'latest_strategy_date': latest_strategy_date_value
		}