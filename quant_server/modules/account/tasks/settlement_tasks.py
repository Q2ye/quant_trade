"""
账户结算任务模块
负责账户的日终、周末、月末结算处理
"""

import logging
from datetime import datetime, date, timedelta
from typing import Dict, List, Optional, Any

from quant_server.modules.system.events import SettlementEvent, SystemEvent
from quant_server.shared.database.repositories.account.asset.account_repo import AccountRepository
from quant_server.shared.database.repositories.trading.order.trade_repo import TradeRepository
from quant_server.shared.database.repositories.trading.position.position_repo import PositionRepository
from ....modules.account.services.account_service import AccountService
from ....modules.account.services.asset_service import AssetService
from ....modules.account.calculators.pnl_calculator import PnLCalculator
from ....modules.account.calculators.asset_calculator import AssetCalculator

logger = logging.getLogger(__name__)


class SettlementTasks:
	"""
	结算任务管理器
	负责调度和执行各类结算任务
	"""

	def __init__ (
			self,
			account_repo: AccountRepository,
			trade_repo: TradeRepository,
			position_repo: PositionRepository,
			event_engine: Any = None
	):
		"""
		初始化结算任务管理器

		Args:
			account_repo: 账户仓库
			trade_repo: 交易仓库
			position_repo: 持仓仓库
			event_engine: 事件引擎
		"""
		self.account_repo = account_repo
		self.trade_repo = trade_repo
		self.position_repo = position_repo
		self.event_engine = event_engine

		# 初始化服务
		self.account_service = AccountService(account_repo)
		self.asset_service = AssetService(
			account_repo=account_repo,
			position_repo=position_repo,
			trade_repo=trade_repo
		)

		# 初始化计算器
		self.pnl_calculator = PnLCalculator()
		self.asset_calculator = AssetCalculator()

	async def daily_settlement_task (self, trading_day: Optional[date] = None) -> Dict:
		"""
		日终结算任务
		每日收盘后执行，计算当日盈亏、更新资产、生成对账单

		Args:
			trading_day: 交易日，默认使用当日

		Returns:
			Dict: 结算结果
		"""
		if not trading_day:
			trading_day = datetime.now().date()

		logger.info(f"开始执行日终结算任务，交易日: {trading_day}")

		try:
			# 1. 获取当日所有账户
			accounts = await self.account_service.get_active_accounts()

			results = {}
			for account in accounts:
				account_id = account.account_id
				logger.info(f"处理账户 {account_id} 的日终结算")

				try:
					# 2. 计算当日盈亏
					daily_pnl = await self._calculate_daily_pnl(account_id, trading_day)

					# 3. 更新账户资产
					updated_assets = await self._update_account_assets(
						account_id,
						daily_pnl,
						trading_day
					)

					# 4. 更新持仓成本
					updated_positions = await self._update_position_cost(account_id)

					# 5. 生成日终对账单
					statement = await self._generate_daily_statement(
						account_id,
						trading_day,
						daily_pnl,
						updated_assets
					)

					# 6. 记录结算结果
					settlement_record = await self.account_repo.create_settlement_record({
						'account_id': account_id,
						'trading_day': trading_day,
						'settlement_type': 'daily',
						'pnl': float(daily_pnl['total_pnl']),
						'assets_snapshot': updated_assets,
						'statement_path': statement['file_path'],
						'status': 'completed'
					})

					results[account_id] = {
						'status': 'success',
						'daily_pnl': daily_pnl,
						'updated_assets': updated_assets,
						'updated_positions': len(updated_positions),
						'statement': statement,
						'settlement_id': settlement_record.id
					}

					logger.info(f"账户 {account_id} 日终结算完成")

				except Exception as e:
					logger.error(f"账户 {account_id} 日终结算失败: {str(e)}", exc_info=True)
					results[account_id] = {
						'status': 'failed',
						'error': str(e)
					}

			# 7. 发布结算完成事件
			if self.event_engine:
				await self.event_engine.put(SettlementEvent(
					settlement_type='daily',
					trading_day=trading_day,
					results=results
				))

			logger.info(f"日终结算任务完成，共处理 {len(accounts)} 个账户")
			return {
				'task': 'daily_settlement',
				'trading_day': trading_day,
				'total_accounts': len(accounts),
				'results': results
			}

		except Exception as e:
			logger.error(f"日终结算任务执行失败: {str(e)}", exc_info=True)
			raise

	async def weekly_settlement_task (self, week_end_date: Optional[date] = None) -> Dict:
		"""
		周末结算任务
		每周五收盘后执行，生成周度报告

		Args:
			week_end_date: 周结束日期，默认使用本周五

		Returns:
			Dict: 周结算结果
		"""
		if not week_end_date:
			# 默认使用上周五
			today = datetime.now().date()
			week_end_date = today - timedelta(days=today.weekday() - 4)

		logger.info(f"开始执行周末结算任务，周结束日: {week_end_date}")

		try:
			# 获取本周所有交易日
			week_start_date = week_end_date - timedelta(days=4)

			# 获取所有账户
			accounts = await self.account_service.get_active_accounts()

			results = {}
			for account in accounts:
				account_id = account.account_id

				try:
					# 计算周度盈亏
					weekly_pnl = await self._calculate_period_pnl(
						account_id,
						week_start_date,
						week_end_date
					)

					# 生成周度报告
					weekly_report = await self._generate_weekly_report(
						account_id,
						week_start_date,
						week_end_date,
						weekly_pnl
					)

					# 记录周结算
					settlement_record = await self.account_repo.create_settlement_record({
						'account_id': account_id,
						'trading_day': week_end_date,
						'settlement_type': 'weekly',
						'pnl': float(weekly_pnl['total_pnl']),
						'statement_path': weekly_report['file_path'],
						'status': 'completed'
					})

					results[account_id] = {
						'status': 'success',
						'weekly_pnl': weekly_pnl,
						'report': weekly_report,
						'settlement_id': settlement_record.id
					}

				except Exception as e:
					logger.error(f"账户 {account_id} 周末结算失败: {str(e)}")
					results[account_id] = {
						'status': 'failed',
						'error': str(e)
					}

			logger.info(f"周末结算任务完成")
			return {
				'task': 'weekly_settlement',
				'week_end_date': week_end_date,
				'results': results
			}

		except Exception as e:
			logger.error(f"周末结算任务执行失败: {str(e)}")
			raise

	async def monthly_settlement_task (self, month_end_date: Optional[date] = None) -> Dict:
		"""
		月末结算任务
		每月最后一个交易日执行，生成月度报告

		Args:
			month_end_date: 月结束日期

		Returns:
			Dict: 月结算结果
		"""
		if not month_end_date:
			today = datetime.now().date()
			month_end_date = date(today.year, today.month, 1) - timedelta(days=1)

		logger.info(f"开始执行月末结算任务，月结束日: {month_end_date}")

		try:
			# 计算月初日期
			month_start_date = date(month_end_date.year, month_end_date.month, 1)

			accounts = await self.account_service.get_active_accounts()

			results = {}
			for account in accounts:
				account_id = account.account_id

				try:
					# 计算月度盈亏
					monthly_pnl = await self._calculate_period_pnl(
						account_id,
						month_start_date,
						month_end_date
					)

					# 生成月度报告
					monthly_report = await self._generate_monthly_report(
						account_id,
						month_start_date,
						month_end_date,
						monthly_pnl
					)

					# 记录月结算
					settlement_record = await self.account_repo.create_settlement_record({
						'account_id': account_id,
						'trading_day': month_end_date,
						'settlement_type': 'monthly',
						'pnl': float(monthly_pnl['total_pnl']),
						'statement_path': monthly_report['file_path'],
						'status': 'completed'
					})

					results[account_id] = {
						'status': 'success',
						'monthly_pnl': monthly_pnl,
						'report': monthly_report,
						'settlement_id': settlement_record.id
					}

				except Exception as e:
					logger.error(f"账户 {account_id} 月末结算失败: {str(e)}")
					results[account_id] = {
						'status': 'failed',
						'error': str(e)
					}

			logger.info(f"月末结算任务完成")
			return {
				'task': 'monthly_settlement',
				'month_end_date': month_end_date,
				'results': results
			}

		except Exception as e:
			logger.error(f"月末结算任务执行失败: {str(e)}")
			raise

	async def _calculate_daily_pnl (self, account_id: str, trading_day: date) -> Dict:
		"""
		计算账户当日盈亏

		Args:
			account_id: 账户ID
			trading_day: 交易日

		Returns:
			Dict: 盈亏计算结果
		"""
		# 获取当日所有成交
		trades = await self.trade_repo.get_trades_by_account_and_date(
			account_id,
			trading_day
		)

		# 获取前日持仓
		previous_day = trading_day - timedelta(days=1)
		previous_positions = await self.position_repo.get_positions_by_date(
			account_id,
			previous_day
		)

		# 获取当日收盘价（这里需要调用市场数据服务）
		# 实际实现中需要集成市场数据模块
		closing_prices = {}  # 待实现

		# 计算当日盈亏
		pnl_result = self.pnl_calculator.calculate_daily_pnl(
			account_id=account_id,
			trades=trades,
			previous_positions=previous_positions,
			closing_prices=closing_prices,
			trading_day=trading_day
		)

		return pnl_result

	async def _update_account_assets (
			self,
			account_id: str,
			daily_pnl: Dict,
			trading_day: date
	) -> Dict:
		"""
		更新账户资产

		Args:
			account_id: 账户ID
			daily_pnl: 当日盈亏
			trading_day: 交易日

		Returns:
			Dict: 更新后的资产快照
		"""
		# 获取当前资产
		current_assets = await self.asset_service.get_account_assets(account_id)

		# 计算更新后的资产
		updated_assets = self.asset_calculator.update_assets_with_pnl(
			current_assets,
			daily_pnl
		)

		# 保存资产快照
		asset_snapshot = {
			'account_id': account_id,
			'trading_day': trading_day,
			'total_asset': float(updated_assets['total_asset']),
			'cash_balance': float(updated_assets['cash_balance']),
			'market_value': float(updated_assets['market_value']),
			'available_cash': float(updated_assets['available_cash']),
			'frozen_cash': float(updated_assets['frozen_cash']),
			'pnl': float(daily_pnl['total_pnl']),
			'pnl_rate': float(daily_pnl['pnl_rate'])
		}

		await self.account_repo.create_asset_snapshot(asset_snapshot)

		return updated_assets

	async def _update_position_cost (self, account_id: str) -> List:
		"""
		更新持仓成本

		Args:
			account_id: 账户ID

		Returns:
			List: 更新的持仓列表
		"""
		# 获取当日所有成交
		today = datetime.now().date()
		trades = await self.trade_repo.get_trades_by_account_and_date(account_id, today)

		# 按证券分组计算平均成本
		position_updates = []

		# 实现持仓成本更新逻辑
		# 这里简化为示例
		for trade in trades:
			# 计算新的持仓成本
			# 实际实现中需要根据买卖方向更新成本

			position_updates.append({
				'security_id': trade.security_id,
				'cost_price': trade.price,  # 示例，实际需要计算
				'update_time': datetime.now()
			})

		return position_updates

	async def _generate_daily_statement (
			self,
			account_id: str,
			trading_day: date,
			daily_pnl: Dict,
			assets: Dict
	) -> Dict:
		"""
		生成日终对账单

		Args:
			account_id: 账户ID
			trading_day: 交易日
			daily_pnl: 当日盈亏
			assets: 资产信息

		Returns:
			Dict: 对账单信息
		"""
		from modules.account.utils.statement_generator import StatementGenerator

		generator = StatementGenerator()

		# 获取当日交易明细
		trades = await self.trade_repo.get_trades_by_account_and_date(
			account_id,
			trading_day
		)

		# 获取持仓明细
		positions = await self.position_repo.get_current_positions(account_id)

		# 生成对账单
		statement = generator.generate_daily_statement(
			account_id=account_id,
			trading_day=trading_day,
			trades=trades,
			positions=positions,
			daily_pnl=daily_pnl,
			assets=assets
		)

		return statement

	async def _calculate_period_pnl (
			self,
			account_id: str,
			start_date: date,
			end_date: date
	) -> Dict:
		"""
		计算期间盈亏

		Args:
			account_id: 账户ID
			start_date: 开始日期
			end_date: 结束日期

		Returns:
			Dict: 期间盈亏
		"""
		# 获取期间所有成交
		trades = await self.trade_repo.get_trades_by_account_and_period(
			account_id,
			start_date,
			end_date
		)

		# 计算期间盈亏
		pnl_result = self.pnl_calculator.calculate_period_pnl(
			account_id=account_id,
			trades=trades,
			start_date=start_date,
			end_date=end_date
		)

		return pnl_result

	async def _generate_weekly_report (
			self,
			account_id: str,
			start_date: date,
			end_date: date,
			weekly_pnl: Dict
	) -> Dict:
		"""
		生成周度报告

		Args:
			account_id: 账户ID
			start_date: 周开始日期
			end_date: 周结束日期
			weekly_pnl: 周盈亏

		Returns:
			Dict: 周度报告信息
		"""
		from modules.account.utils.statement_generator import StatementGenerator

		generator = StatementGenerator()

		# 生成周度报告
		report = generator.generate_weekly_report(
			account_id=account_id,
			start_date=start_date,
			end_date=end_date,
			weekly_pnl=weekly_pnl
		)

		return report

	async def _generate_monthly_report (
			self,
			account_id: str,
			start_date: date,
			end_date: date,
			monthly_pnl: Dict
	) -> Dict:
		"""
		生成月度报告

		Args:
			account_id: 账户ID
			start_date: 月开始日期
			end_date: 月结束日期
			monthly_pnl: 月盈亏

		Returns:
			Dict: 月度报告信息
		"""
		from modules.account.utils.statement_generator import StatementGenerator

		generator = StatementGenerator()

		# 生成月度报告
		report = generator.generate_monthly_report(
			account_id=account_id,
			start_date=start_date,
			end_date=end_date,
			monthly_pnl=monthly_pnl
		)

		return report


# 创建全局任务实例（实际使用时通过依赖注入）
_settlement_tasks: Optional[SettlementTasks] = None


def get_settlement_tasks () -> SettlementTasks:
	"""获取结算任务实例"""
	global _settlement_tasks
	if _settlement_tasks is None:
		# 这里应该从依赖注入容器获取，这里简化为直接创建
		from shared.database.session import get_session_manager

		session_manager = get_session_manager()
		with session_manager.get_session() as session:
			from shared.database.repositories import (
				AccountRepository, TradeRepository, PositionRepository
			)

			_settlement_tasks = SettlementTasks(
				account_repo=AccountRepository(session),
				trade_repo=TradeRepository(session),
				position_repo=PositionRepository(session)
			)
	return _settlement_tasks


# 定义Celery任务（如果使用Celery）
try:
	from celery import shared_task


	@shared_task
	def daily_settlement_task (trading_day: Optional[str] = None):
		"""Celery日终结算任务"""
		import asyncio

		if trading_day:
			from datetime import datetime
			trading_date = datetime.strptime(trading_day, '%Y-%m-%d').date()
		else:
			trading_date = None

		tasks = get_settlement_tasks()
		result = asyncio.run(tasks.daily_settlement_task(trading_date))
		return result


	@shared_task
	def weekly_settlement_task (week_end_date: Optional[str] = None):
		"""Celery周末结算任务"""
		import asyncio

		if week_end_date:
			from datetime import datetime
			week_end = datetime.strptime(week_end_date, '%Y-%m-%d').date()
		else:
			week_end = None

		tasks = get_settlement_tasks()
		result = asyncio.run(tasks.weekly_settlement_task(week_end))
		return result


	@shared_task
	def monthly_settlement_task (month_end_date: Optional[str] = None):
		"""Celery月末结算任务"""
		import asyncio

		if month_end_date:
			from datetime import datetime
			month_end = datetime.strptime(month_end_date, '%Y-%m-%d').date()
		else:
			month_end = None

		tasks = get_settlement_tasks()
		result = asyncio.run(tasks.monthly_settlement_task(month_end))
		return result

except ImportError:
	# Celery未安装时的占位函数
	def daily_settlement_task (*args, **kwargs):
		raise NotImplementedError("Celery is not installed")


	def weekly_settlement_task (*args, **kwargs):
		raise NotImplementedError("Celery is not installed")


	def monthly_settlement_task (*args, **kwargs):
		raise NotImplementedError("Celery is not installed")