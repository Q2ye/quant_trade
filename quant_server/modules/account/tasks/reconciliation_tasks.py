"""
账户对账任务模块
负责账户的交易对账、持仓对账、资金对账等
"""

import logging
from datetime import datetime, date
from typing import Dict, List, Optional, Any

from quant_server.modules.account.events.reconciliation_events import ReconciliationEvent
from quant_server.modules.account.managers.reconciliation_manager import ReconciliationManager
from quant_server.modules.account.services.account_service import AccountService
from quant_server.shared.database.repositories.account.asset.account_repo import AccountRepository
from quant_server.shared.database.repositories.trading.order.trade_repo import TradeRepository
from quant_server.shared.database.repositories.trading.position.position_repo import PositionRepository

logger = logging.getLogger(__name__)


class ReconciliationTasks:
	"""
	对账任务管理器
	负责调度和执行各类对账任务
	"""

	def __init__ (
			self,
			account_repo: AccountRepository,
			trade_repo: TradeRepository,
			position_repo: PositionRepository,
			reconciliation_manager: Optional[ReconciliationManager] = None,
			event_engine: Any = None
	):
		"""
		初始化对账任务管理器

		Args:
			account_repo: 账户仓库
			trade_repo: 交易仓库
			position_repo: 持仓仓库
			reconciliation_manager: 对账管理器
			event_engine: 事件引擎
		"""
		self.account_repo = account_repo
		self.trade_repo = trade_repo
		self.position_repo = position_repo
		self.event_engine = event_engine

		# 初始化管理器
		if reconciliation_manager is None:
			from quant_server.modules.account.managers.reconciliation_manager import ReconciliationManager
			self.reconciliation_manager = ReconciliationManager(
				db=account_repo.session
			)
		else:
			self.reconciliation_manager = reconciliation_manager

		# 初始化服务
		self.account_service = AccountService(db=account_repo.session)

	async def get_active_accounts (self):
		"""
		获取所有活跃账户

		Returns:
			List[Account]: 活跃账户列表
		"""
		return await self.account_repo.get_many(status="active")

	async def daily_reconciliation_task (self, trading_day: Optional[date] = None) -> Dict:
		"""
		日终对账任务
		每日收盘后执行，核对交易、持仓、资金

		Args:
			trading_day: 交易日

		Returns:
			Dict: 对账结果
		"""
		if not trading_day:
			trading_day = datetime.now().date()

		logger.info(f"开始执行日终对账任务，交易日: {trading_day}")

		try:
			# 1. 获取所有活跃账户
			accounts = await self.get_active_accounts()

			results = {}
			for account in accounts:
				account_id = account.account_id
				logger.info(f"对账账户: {account_id}")

				try:
					# 2. 执行对账
					# 先执行资金对账
					balance_result = await self.reconciliation_manager.reconcile_account_balance(account_id)
					# 再执行持仓对账
					position_result = await self.reconciliation_manager.reconcile_positions(account_id)
					# 构建对账结果
					reconciliation_result = {
						"account_id": account_id,
						"balance_reconciled": balance_result["reconciled"],
						"position_reconciled": position_result["reconciled"],
						"reconciled": balance_result["reconciled"] and position_result["reconciled"],
						"differences": {
							"balance": balance_result["differences"],
							"position": position_result["differences"]
						},
						"timestamp": datetime.now().isoformat()
					}

					# 3. 记录对账结果
					recon_record = await self._record_reconciliation_result(
						account_id=account_id,
						trading_day=trading_day,
						result=reconciliation_result
					)

					results[account_id] = {
						'status': 'success',
						'reconciliation': reconciliation_result,
						'record_id': recon_record.id
					}

					logger.info(f"账户 {account_id} 对账完成")

					# 4. 如果发现差异，触发处理流程
					if not reconciliation_result.get('reconciled', False):
						await self._handle_reconciliation_discrepancy(
							account_id=account_id,
							discrepancies=reconciliation_result['differences']
						)

				except Exception as e:
					logger.error(f"账户 {account_id} 对账失败: {str(e)}", exc_info=True)
					results[account_id] = {
						'status': 'failed',
						'error': str(e)
					}

			# 5. 发布对账完成事件
			if self.event_engine:
				await self.event_engine.put(ReconciliationEvent(
					reconciliation_type='daily',
					trading_day=trading_day,
					results=results
				))

			logger.info(f"日终对账任务完成，共处理 {len(accounts)} 个账户")
			return {
				'task': 'daily_reconciliation',
				'trading_day': trading_day,
				'total_accounts': len(accounts),
				'results': results
			}

		except Exception as e:
			logger.error(f"日终对账任务执行失败: {str(e)}", exc_info=True)
			raise

	async def trade_reconciliation_task (
			self,
			account_id: str,
			start_time: datetime,
			end_time: datetime
	) -> Dict:
		"""
		交易对账任务
		核对系统交易记录与券商交易记录

		Args:
			account_id: 账户ID
			start_time: 开始时间
			end_time: 结束时间

		Returns:
			Dict: 交易对账结果
		"""
		logger.info(f"开始交易对账，账户: {account_id}, 时间段: {start_time} - {end_time}")

		try:
			# 1. 获取系统交易记录
			system_trades = await self.trade_repo.get_trades_by_account_and_period(
				account_id=account_id,
				start_date=start_time.date(),
				end_date=end_time.date(),
				start_time=start_time.time(),
				end_time=end_time.time()
			)

			# 2. 获取券商交易记录（需要集成券商接口）
			# 这里调用券商适配器获取实际成交记录
			broker_trades = await self._get_broker_trades(
				account_id=account_id,
				start_time=start_time,
				end_time=end_time
			)

			# 3. 执行交易对账
			# 调用 ReconciliationManager 的 reconcile_trades 方法
			trade_reconciliation = await self.reconciliation_manager.reconcile_trades(
				system_trades=system_trades,
				broker_trades=broker_trades
			)

			# 4. 记录结果
			record = await self._record_trade_reconciliation(
				account_id=account_id,
				start_time=start_time,
				end_time=end_time,
				result=trade_reconciliation
			)

			# 5. 处理差异
			if trade_reconciliation.get('has_discrepancy', False):
				await self._handle_trade_discrepancy(
					account_id=account_id,
					discrepancies=trade_reconciliation['discrepancies']
				)

			logger.info(f"交易对账完成，账户: {account_id}")
			return {
				'account_id': account_id,
				'reconciliation': trade_reconciliation,
				'record_id': record.id
			}

		except Exception as e:
			logger.error(f"交易对账失败，账户: {account_id}, 错误: {str(e)}", exc_info=True)
			raise

	async def position_reconciliation_task (self, account_id: str) -> Dict:
		"""
		持仓对账任务
		核对系统持仓与券商实际持仓

		Args:
			account_id: 账户ID

		Returns:
			Dict: 持仓对账结果
		"""
		logger.info(f"开始持仓对账，账户: {account_id}")

		try:
			# 1. 获取系统持仓
			system_positions = await self.position_repo.get_current_positions(account_id)

			# 2. 获取券商持仓
			broker_positions = await self._get_broker_positions(account_id)

			# 3. 执行持仓对账
			# 先获取账户信息
			account = await self.account_repo.get(account_id)
			if not account:
				raise ValueError(f"账户不存在: {account_id}")
			
			# 调用 ReconciliationManager 的 reconcile_positions 方法
			position_reconciliation = await self.reconciliation_manager.reconcile_positions(
				account_id=account_id
			)

			# 4. 记录结果
			record = await self._record_position_reconciliation(
				account_id=account_id,
				result=position_reconciliation
			)

			# 5. 处理差异
			if position_reconciliation.get('has_discrepancy', False):
				await self._handle_position_discrepancy(
					account_id=account_id,
					discrepancies=position_reconciliation['discrepancies']
				)

			logger.info(f"持仓对账完成，账户: {account_id}")
			return {
				'account_id': account_id,
				'reconciliation': position_reconciliation,
				'record_id': record.id
			}

		except Exception as e:
			logger.error(f"持仓对账失败，账户: {account_id}, 错误: {str(e)}", exc_info=True)
			raise

	async def _get_broker_trades (
			self,
			account_id: str,
			start_time: datetime,
			end_time: datetime
	) -> List[Dict]:
		"""
		从数据库获取交易记录（替代从券商获取）

		Args:
			account_id: 账户ID
			start_time: 开始时间
			end_time: 结束时间

		Returns:
			List[Dict]: 交易记录
		"""
		try:
			# 从数据库获取交易记录
			trades = await self.trade_repo.get_by_account_id(
				account_id=account_id,
				start_time=start_time,
				end_time=end_time
			)

			# 将交易记录转换为与券商接口返回格式一致的字典列表
			broker_trades = []
			for trade in trades:
				broker_trades.append({
					'trade_id': trade.trade_id,
					'security_id': trade.ts_code,
					'direction': getattr(trade, 'direction', 'buy'),
					'price': trade.price,
					'quantity': trade.volume,
					'trade_time': trade.trade_time,
					'status': 'filled'
				})

			return broker_trades

		except Exception as e:
			logger.error(f"从数据库获取交易记录失败: {str(e)}")
			return []

	async def _get_broker_positions (self, account_id: str) -> List[Dict]:
		"""
		从数据库获取持仓记录（替代从券商获取）

		Args:
			account_id: 账户ID

		Returns:
			List[Dict]: 持仓记录
		"""
		try:
			# 从数据库获取持仓记录
			positions = await self.position_repo.get_account_positions(
				account_id=account_id,
				include_zero=False
			)

			# 将持仓记录转换为与券商接口返回格式一致的字典列表
			broker_positions = []
			for position in positions:
				broker_positions.append({
					'security_id': position.ts_code,
					'quantity': position.volume,
					'cost_price': position.cost_price,
					'current_price': position.last_price,
					'market_value': position.market_value,
					'available_quantity': position.available_volume,
					'frozen_quantity': position.frozen_volume
				})

			return broker_positions

		except Exception as e:
			logger.error(f"从数据库获取持仓记录失败: {str(e)}")
			return []

	async def _record_reconciliation_result (
			self,
			account_id: str,
			trading_day: date,
			result: Dict
	) -> Any:
		"""
		记录对账结果

		Args:
			account_id: 账户ID
			trading_day: 交易日
			result: 对账结果

		Returns:
			对账记录
		"""
		# 记录对账结果到数据库
		recon_data = {
			'account_id': account_id,
			'reconciliation_date': trading_day,
			'reconciliation_type': 'daily',
			'balance_reconciled': result['balance_reconciled'],
			'position_reconciled': result['position_reconciled'],
			'reconciled': result['reconciled'],
			'differences': result['differences'],
			'timestamp': result['timestamp']
		}

		# 调用 AccountRepository 的方法创建对账记录
		return await self.account_repo.create_reconciliation_record(recon_data)

	async def _record_trade_reconciliation (
			self,
			account_id: str,
			start_time: datetime,
			end_time: datetime,
			result: Dict
	) -> Any:
		"""
		记录交易对账结果

		Args:
			account_id: 账户ID
			start_time: 开始时间
			end_time: 结束时间
			result: 对账结果

		Returns:
			交易对账记录
		"""
		# 记录交易对账结果到数据库
		trade_recon_data = {
			'account_id': account_id,
			'start_time': start_time,
			'end_time': end_time,
			'reconciliation_type': 'trade',
			'has_discrepancy': result.get('has_discrepancy', False),
			'discrepancies': result.get('discrepancies', []),
			'reconciled': result.get('reconciled', True),
			'timestamp': result.get('timestamp', datetime.now().isoformat())
		}

		# 调用 TradeRepository 的方法创建交易对账记录
		return await self.trade_repo.create_reconciliation_record(trade_recon_data)

	async def _record_position_reconciliation (
			self,
			account_id: str,
			result: Dict
	) -> Any:
		"""
		记录持仓对账结果

		Args:
			account_id: 账户ID
			result: 对账结果

		Returns:
			持仓对账记录
		"""
		# 记录持仓对账结果到数据库
		position_recon_data = {
			'account_id': account_id,
			'reconciliation_type': 'position',
			'has_discrepancy': result.get('has_discrepancy', False),
			'discrepancies': result.get('discrepancies', []),
			'reconciled': result.get('reconciled', True),
			'timestamp': result.get('timestamp', datetime.now().isoformat())
		}

		# 调用 PositionRepository 的方法创建持仓对账记录
		return await self.position_repo.create_reconciliation_record(position_recon_data)

	async def _handle_reconciliation_discrepancy (
			self,
			account_id: str,
			discrepancies: List[Dict]
	) -> None:
		"""
		处理对账差异

		Args:
			account_id: 账户ID
			discrepancies: 差异列表
		"""
		logger.warning(f"账户 {account_id} 发现对账差异: {len(discrepancies)} 处")

		for discrepancy in discrepancies:
			discrepancy_type = discrepancy.get('type')

			if discrepancy_type == 'trade_missing':
				# 处理缺失的交易
				await self._handle_missing_trade(account_id, discrepancy)
			elif discrepancy_type == 'position_mismatch':
				# 处理持仓不匹配
				await self._handle_position_mismatch(account_id, discrepancy)
			elif discrepancy_type == 'cash_mismatch':
				# 处理资金不匹配
				await self._handle_cash_mismatch(account_id, discrepancy)

	async def _handle_trade_discrepancy (
			self,
			account_id: str,
			discrepancies: List[Dict]
	) -> None:
		"""
		处理交易差异

		Args:
			account_id: 账户ID
			discrepancies: 差异列表
		"""
		logger.info(f"处理交易差异，账户: {account_id}")
		for discrepancy in discrepancies:
			trade_id = discrepancy.get('trade_id')
			action = discrepancy.get('action')

			if action == 'add_missing_trade':
				# 添加缺失的交易
				trade_data = discrepancy.get('trade_data')
				if trade_data:
					await self.trade_repo.create(trade_data)
					logger.info(f"账户 {account_id} 添加缺失交易: {trade_id}")

			elif action == 'update_trade':
				# 更新交易信息
				trade_data = discrepancy.get('trade_data')
				if trade_data:
					await self.trade_repo.update(trade_id, trade_data)
					logger.info(f"账户 {account_id} 更新交易: {trade_id}")

	async def _handle_position_discrepancy (
			self,
			account_id: str,
			discrepancies: List[Dict]
	) -> None:
		"""
		处理持仓对账差异

		Args:
			account_id: 账户ID
			discrepancies: 差异列表
		"""
		logger.info(f"处理持仓对账差异，账户: {account_id}")

		for discrepancy in discrepancies:
			security_id = discrepancy.get('security_id')
			action = discrepancy.get('action')

			if action == 'update_position':
				# 更新持仓
				position_data = discrepancy.get('position_data')
				if position_data:
					# 调用 PositionRepository 的方法更新持仓
					await self.position_repo.update_position(
						account_id=account_id,
						security_id=security_id,
						position_data=position_data
					)
					logger.info(f"账户 {account_id} 更新持仓: {security_id}")

			elif action == 'create_position':
				# 创建新持仓
				position_data = discrepancy.get('position_data')
				if position_data:
					# 调用 PositionRepository 的方法创建持仓
					await self.position_repo.create(position_data)
					logger.info(f"账户 {account_id} 创建持仓: {security_id}")

	@staticmethod
	async def _handle_missing_trade (account_id: str, discrepancy: Dict) -> None:
		"""处理缺失的交易"""
		# 实现交易同步逻辑
		logger.info(f"处理缺失交易: 账户ID={account_id}, 差异={discrepancy}")

	@staticmethod
	async def _handle_position_mismatch (account_id: str, discrepancy: Dict) -> None:
		"""处理持仓不匹配"""
		# 实现持仓同步逻辑
		logger.info(f"处理持仓不匹配: 账户ID={account_id}, 差异={discrepancy}")

	@staticmethod
	async def _handle_cash_mismatch (account_id: str, discrepancy: Dict) -> None:
		"""处理资金不匹配"""
		# 实现资金同步逻辑
		logger.info(f"处理资金不匹配: 账户ID={account_id}, 差异={discrepancy}")


# 创建全局任务实例
_reconciliation_tasks: Optional[ReconciliationTasks] = None


async def _create_reconciliation_tasks () -> ReconciliationTasks:
	"""创建对账任务实例（异步）"""
	from quant_server.shared.database.session.connection_pool import get_connection_pool

	# 获取连接池
	connection_pool = get_connection_pool()

	# 确保连接池已初始化
	try:
		# 尝试获取会话工厂，如果未初始化会抛出异常
		session_factory = connection_pool.get_session_factory()
	except RuntimeError:
		# 连接池未初始化，需要初始化
		await connection_pool.initialize()
		session_factory = connection_pool.get_session_factory()

	# 创建会话
	session = session_factory()

	return ReconciliationTasks(
		account_repo=AccountRepository(session),
		trade_repo=TradeRepository(session),
		position_repo=PositionRepository(session)
	)


def get_reconciliation_tasks () -> ReconciliationTasks:
	"""获取对账任务实例"""
	global _reconciliation_tasks
	if _reconciliation_tasks is None:
		import asyncio
		_reconciliation_tasks = asyncio.run(_create_reconciliation_tasks())
	return _reconciliation_tasks

	# 定义Celery任务（如果Celery已安装）
	# 这些任务目前未被使用，保留以备将来扩展
	# try:
	#	 from celery import shared_task


	#	 @shared_task
	#	 def daily_reconciliation_task (trading_day: Optional[str] = None):
	#		 """Celery日终对账任务"""
	#		 import asyncio

	#		 if trading_day:
	#			 from datetime import datetime
	#			 trading_date = datetime.strptime(trading_day, '%Y-%m-%d').date()
	#		 else:
	#			 trading_date = None

	#		 tasks = get_reconciliation_tasks()
	#		 result = asyncio.run(tasks.daily_reconciliation_task(trading_date))
	#		 return result


	#	 @shared_task
	#	 def trade_reconciliation_task (account_id: str, start_time: str, end_time: str):
	#		 """Celery交易对账任务"""
	#		 import asyncio

	#		 from datetime import datetime
	#		 start_dt = datetime.fromisoformat(start_time)
	#		 end_dt = datetime.fromisoformat(end_time)

	#		 tasks = get_reconciliation_tasks()
	#		 result = asyncio.run(tasks.trade_reconciliation_task(
	#			 account_id=account_id,
	#			 start_time=start_dt,
	#			 end_time=end_dt
	#		 ))
	#		 return result


	#	 @shared_task
	#	 def position_reconciliation_task (account_id: str):
	#		 """Celery持仓对账任务"""
	#		 import asyncio

	#		 tasks = get_reconciliation_tasks()
	#		 result = asyncio.run(tasks.position_reconciliation_task(account_id))
	#		 return result

	# except ImportError:
	#	 # Celery未安装时的占位函数
	#	 def daily_reconciliation_task (trading_day=None):
	#		 _ = trading_day  # 避免未使用变量警告
	#		 raise NotImplementedError("Celery is not installed")


	#	 def trade_reconciliation_task (account_id, start_time, end_time):
	#		 _ = account_id, start_time, end_time  # 避免未使用变量警告
	#		 raise NotImplementedError("Celery is not installed")


	#	 def position_reconciliation_task (account_id):
	#		 _ = account_id  # 避免未使用变量警告
	#		 raise NotImplementedError("Celery is not installed")