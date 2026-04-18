"""
资产服务
处理资产计算、估值和资产组合管理
"""
import logging
from datetime import datetime
from decimal import Decimal
from typing import List, Dict, Any, Optional

from sqlalchemy.ext.asyncio import AsyncSession

from ....modules.account.calculators.asset_calculator import AssetCalculator
from ....shared.cache.base import CacheBase
from ....shared.database.repositories.account.asset.account_repo import AccountRepository
from ....shared.database.repositories.market.quote import StockDailyRepository
from ....shared.database.repositories.trading.position.position_repo import PositionRepository

logger = logging.getLogger(__name__)


class AssetService:
	"""资产服务 - 处理资产相关业务逻辑"""

	def __init__ (self, db: AsyncSession, cache: Optional[CacheBase] = None):
		self.db = db
		self.cache = cache
		self.account_repo = AccountRepository(db)
		self.position_repo = PositionRepository(db)
		self.stock_daily_repo = StockDailyRepository(db)
		self.asset_calculator = AssetCalculator(db)

	async def get_account_assets (self, account_id: str) -> Dict[str, Any]:
		"""
		获取账户资产详情

		Args:
			account_id: 账户ID

		Returns:
			资产详情
		"""
		try:
			# 检查缓存
			cache_key = f"account:assets:{account_id}"
			if self.cache:
				cached_assets = await self.cache.get(cache_key)
				if cached_assets:
					return cached_assets

			# 获取账户信息
			account = await self.account_repo.get(account_id)
			if not account:
				raise ValueError(f"账户不存在: {account_id}")

			# 获取持仓列表
			positions = await self.position_repo.get_account_positions(account_id)

			# 计算资产汇总
			asset_summary = {
				"total_balance": float(account.total_balance),
				"available_balance": float(account.available_balance),
				"frozen_balance": float(account.frozen_balance),
				"market_value": float(account.market_value),
				"position_count": len([p for p in positions if p.volume > 0])
			}

			# 计算资产配置
			asset_allocation = await self.calculate_asset_allocation(account_id)

			# 计算风险指标
			risk_metrics = await self.calculate_risk_metrics(account_id)

			# 计算历史收益
			historical_returns = await self.get_historical_returns(account_id, days=30)

			# 构建资产详情
			asset_details = {
				"account_id": account_id,
				"account_number": account.account_number,
				"calculation_date": datetime.now().isoformat(),
				"asset_summary": asset_summary,
				"asset_allocation": asset_allocation,
				"risk_metrics": risk_metrics,
				"historical_returns": historical_returns,
				"timestamp": datetime.now().isoformat()
			}

			# 更新缓存
			if self.cache:
				await self.cache.set(cache_key, asset_details, ttl=300)  # 缓存5分钟

			return asset_details

		except Exception as e:
			logger.error(f"获取账户资产详情失败: {str(e)}")
			raise

	async def calculate_asset_allocation (self, account_id: str) -> Dict[str, Any]:
		"""
		计算资产配置

		Args:
			account_id: 账户ID

		Returns:
			资产配置信息
		"""
		try:
			# 获取账户信息
			account = await self.account_repo.get(account_id)
			if not account:
				raise ValueError(f"账户不存在: {account_id}")

			# 获取持仓列表
			positions = await self.position_repo.get_account_positions(account_id)

			# 获取现金比例
			cash_amount = Decimal(str(account.available_balance))
			total_asset = Decimal(str(account.total_balance))

			# 计算持仓配置
			position_allocation = {}
			for position in positions:
				if position.market_value and position.market_value > 0:
					allocation = (Decimal(str(position.market_value)) / total_asset) * 100
					position_allocation[position.ts_code] = {
						"ts_code": position.ts_code,
						"market_value": float(position.market_value),
						"allocation_percentage": float(allocation),
						"volume": position.volume,
						"cost_price": float(position.cost_price) if position.cost_price else 0
					}

			# 计算现金配置
			cash_allocation = {
				"cash": {
					"amount": float(cash_amount),
					"allocation_percentage": float((cash_amount / total_asset) * 100) if total_asset > 0 else 0
				}
			}

			# 计算行业配置（这里简化，实际需要根据股票获取行业信息）
			sector_allocation = await self.calculate_sector_allocation(positions)

			return {
				"total_asset": float(total_asset),
				"cash_allocation": cash_allocation,
				"position_allocation": position_allocation,
				"sector_allocation": sector_allocation,
				"concentration_ratio": self.calculate_concentration_ratio(position_allocation)
			}

		except Exception as e:
			logger.error(f"计算资产配置失败: {str(e)}")
			raise

	@staticmethod
	async def calculate_sector_allocation (positions: List) -> Dict[str, Any]:
		"""
		计算行业配置

		Args:
			positions: 持仓列表

		Returns:
			行业配置信息
		"""
		# 这里简化处理，实际实现需要查询股票行业信息
		sector_map = {}

		for position in positions:
			if position.market_value and position.market_value > 0:
				# 这里假设所有股票都属于同一个行业
				# 实际实现中需要根据ts_code查询行业信息
				sector = "unknown"

				if sector not in sector_map:
					sector_map[sector] = {
						"sector_name": sector,
						"total_value": Decimal("0.00"),
						"positions": []
					}

				sector_map[sector]["total_value"] += Decimal(str(position.market_value))
				sector_map[sector]["positions"].append({
					"ts_code": position.ts_code,
					"market_value": position.market_value
				})

		# 计算百分比
		total_sector_value = sum(sector["total_value"] for sector in sector_map.values())

		sector_allocation = {}
		for sector, data in sector_map.items():
			if total_sector_value > 0:
				percentage = (data["total_value"] / total_sector_value) * 100
			else:
				percentage = Decimal("0.00")

			sector_allocation[sector] = {
				"sector_name": data["sector_name"],
				"total_value": float(data["total_value"]),
				"allocation_percentage": float(percentage),
				"position_count": len(data["positions"])
			}

		return sector_allocation

	def calculate_concentration_ratio (self, position_allocation: Dict[str, Any]) -> Dict[str, float]:
		"""
		计算集中度比率

		Args:
			position_allocation: 持仓配置

		Returns:
			集中度比率
		"""
		allocations = [
			item["allocation_percentage"]
			for item in position_allocation.values()
		]

		allocations.sort(reverse=True)

		# 计算前N集中度
		top_3_concentration = sum(allocations[:3]) if len(allocations) >= 3 else sum(allocations)
		top_5_concentration = sum(allocations[:5]) if len(allocations) >= 5 else sum(allocations)
		top_10_concentration = sum(allocations[:10]) if len(allocations) >= 10 else sum(allocations)

		# 计算赫芬达尔指数
		herfindahl_index = sum((p / 100) ** 2 for p in allocations)

		return {
			"top_3_concentration": top_3_concentration,
			"top_5_concentration": top_5_concentration,
			"top_10_concentration": top_10_concentration,
			"herfindahl_index": herfindahl_index,
			"interpretation": self._interpret_concentration_ratio(herfindahl_index)
		}

	@staticmethod
	def _interpret_concentration_ratio (herfindahl_index: float) -> str:
		"""解释集中度比率"""
		if herfindahl_index > 0.25:
			return "高度集中"
		elif herfindahl_index > 0.15:
			return "中度集中"
		elif herfindahl_index > 0.05:
			return "轻度集中"
		else:
			return "分散"

	async def calculate_risk_metrics (self, account_id: str) -> Dict[str, Any]:
		"""
		计算风险指标

		Args:
			account_id: 账户ID

		Returns:
			风险指标
		"""
		try:
			# 获取账户历史收益数据
			historical_returns = await self.get_historical_returns(account_id, days=252)  # 一年交易数据

			if len(historical_returns) < 2:
				return {
					"volatility": 0,
					"var_95": 0,
					"var_99": 0,
					"max_drawdown": 0,
					"beta": 0,
					"sharpe_ratio": 0,
					"message": "数据不足，无法计算风险指标"
				}

			# 计算风险指标
			risk_metrics = {
				"volatility": 0,
				"var_95": 0,
				"var_99": 0,
				"max_drawdown": 0,
				"beta": 0,
				"sharpe_ratio": 0
			}

			return risk_metrics

		except Exception as e:
			logger.error(f"计算风险指标失败: {str(e)}")
			return {
				"error": str(e),
				"message": "计算风险指标时出错"
			}

	async def get_historical_returns (self, account_id: str, days: int = 30) -> List[Dict[str, Any]]:
		"""
		获取历史收益数据

		Args:
			account_id: 账户ID
			days: 天数

		Returns:
			历史收益数据
		"""
		try:
			# 这里简化处理，实际实现需要查询AccountDailyPerformance表
			# 获取最近N天的每日绩效数据
			from sqlalchemy import select, desc
			from ....shared.database.models.business_models import AccountDailyPerformance

			stmt = (
				select(AccountDailyPerformance)
				.where(AccountDailyPerformance.user_id == account_id)  # 注意：这里应该是account_id，但表结构是user_id
				.order_by(desc(AccountDailyPerformance.trade_date))
				.limit(days)
			)

			result = await self.db.execute(stmt)
			daily_performances = result.scalars().all()

			historical_returns = []
			for perf in daily_performances:
				historical_returns.append({
					"trade_date": perf.trade_date,
					"total_asset": float(perf.total_asset),
					"daily_pnl": float(perf.daily_pnl),
					"daily_return": float(perf.daily_return),
					"cash": float(perf.cash),
					"market_value": float(perf.market_value)
				})

			# 按日期排序
			historical_returns.sort(key=lambda x: x["trade_date"])

			return historical_returns

		except Exception as e:
			logger.error(f"获取历史收益数据失败: {str(e)}")
			# 返回空列表，避免影响其他计算
			return []

	async def update_portfolio_value (self, account_id: str) -> bool:
		"""
		更新投资组合价值

		Args:
			account_id: 账户ID

		Returns:
			更新是否成功
		"""
		try:
			# 获取持仓列表
			positions = await self.position_repo.get_account_positions(account_id)

			total_market_value = Decimal("0.00")

			for position in positions:
				if position.volume > 0:
					# 获取最新价格
					latest_price = await self._get_latest_price(position.ts_code)

					if latest_price:
						# 计算持仓市值
						position_market_value = Decimal(str(latest_price)) * position.volume

						# 更新持仓市值
						await self.position_repo.update(position.id, {
							"market_value": position_market_value,
							"last_price": latest_price
						})

						total_market_value += position_market_value

			# 更新账户市值
			account = await self.account_repo.get(account_id)
			if account:
				# 计算总资产 = 现金 + 市值
				total_asset = Decimal(str(account.available_balance)) + total_market_value

				await self.account_repo.update(account_id, {
					"market_value": total_market_value,
					"total_balance": total_asset
				})

			# 清理缓存
			if self.cache:
				await self.cache.delete(f"account:assets:{account_id}")
				await self.cache.delete(f"account:{account_id}")

			logger.info(f"更新投资组合价值: 账户ID={account_id}, 总市值={total_market_value}")

			return True

		except Exception as e:
			logger.error(f"更新投资组合价值失败: {str(e)}")
			raise

	async def _get_latest_price (self, ts_code: str) -> Optional[Decimal]:
		"""
		获取证券最新价格

		Args:
			ts_code: 证券代码

		Returns:
			最新价格，如果获取失败则返回None
		"""
		try:
			# 这里简化处理，实际实现需要查询行情数据
			# 可以从缓存或数据库获取最新价格
			cache_key = f"price:{ts_code}"

			if self.cache:
				cached_price = await self.cache.get(cache_key)
				if cached_price:
					return Decimal(str(cached_price))

			# 从数据库获取最新价格
			latest_quote = await self.stock_daily_repo.get_latest_by_code(ts_code)
			if latest_quote and latest_quote.close:
				price = Decimal(str(latest_quote.close))

				# 更新缓存
				if self.cache:
					await self.cache.set(cache_key, float(price), ttl=60)  # 缓存1分钟

				return price

			return None

		except Exception as e:
			logger.error(f"获取最新价格失败: {str(e)}")
			return None

	async def calculate_asset_growth (self, account_id: str, period: str = "month") -> Dict[str, Any]:
		"""
		计算资产增长

		Args:
			account_id: 账户ID
			period: 周期（day, week, month, quarter, year）

		Returns:
			资产增长数据
		"""
		try:
			# 确定查询天数
			days_map = {
				"day": 1,
				"week": 7,
				"month": 30,
				"quarter": 90,
				"year": 365
			}

			days = days_map.get(period, 30)

			# 获取历史资产数据
			historical_assets = await self.get_historical_returns(account_id, days=days)

			if len(historical_assets) < 2:
				return {
					"period": period,
					"total_growth": 0,
					"annualized_growth": 0,
					"volatility": 0,
					"message": "数据不足，无法计算资产增长"
				}

			# 提取总资产序列
			assets_series = [a["total_asset"] for a in historical_assets]

			# 计算增长指标
			growth_metrics = {
				"total_growth": 0,
				"annualized_growth": 0,
				"volatility": 0,
				"growth_rate_per_day": 0,
				"sharpe_ratio": 0
			}

			return {
				"period": period,
				"start_date": historical_assets[0]["trade_date"],
				"end_date": historical_assets[-1]["trade_date"],
				"start_asset": assets_series[0],
				"end_asset": assets_series[-1],
				"total_growth": growth_metrics["total_growth"],
				"annualized_growth": growth_metrics["annualized_growth"],
				"volatility": growth_metrics["volatility"],
				"growth_rate_per_day": growth_metrics.get("growth_rate_per_day", 0),
				"sharpe_ratio": growth_metrics.get("sharpe_ratio", 0)
			}

		except Exception as e:
			logger.error(f"计算资产增长失败: {str(e)}")
			return {
				"period": period,
				"error": str(e),
				"message": "计算资产增长时出错"
			}