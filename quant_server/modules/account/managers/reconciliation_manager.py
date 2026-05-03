"""
对账管理器
负责账户资金、持仓的对账和差错处理
"""
import asyncio
import logging
from datetime import datetime, date
from decimal import Decimal
from typing import Dict, Any, List, Optional

from sqlalchemy.ext.asyncio import AsyncSession

from modules.account.calculators.asset_calculator import AssetCalculator
from modules.account.services.account_service import AccountService
from modules.account.services.position_service import PositionService
from shared.cache.base import CacheBase
from shared.database.repositories.account.asset.account_repo import AccountRepository
from shared.database.repositories.analysis.performance.analysis_report_repo import AnalysisReportRepository
from shared.database.repositories.trading.order.order_repo import OrderRepository
from shared.database.repositories.trading.order.trade_repo import TradeRepository
from shared.database.repositories.trading.position.position_repo import PositionRepository
from shared.messaging.producer import MessageProducer

logger = logging.getLogger(__name__)


class ReconciliationManager:
	"""对账管理器 - 处理账户资金和持仓的对账"""

	def __init__ (
			self,
			db: AsyncSession,
			cache: Optional[CacheBase] = None,
			message_producer: Optional[MessageProducer] = None
	):
		self.db = db
		self.cache = cache
		self.message_producer = message_producer

		# 初始化Repository
		self.account_repo = AccountRepository(db)
		self.position_repo = PositionRepository(db)
		self.trade_repo = TradeRepository(db)
		self.order_repo = OrderRepository(db)

		# 初始化服务
		self.account_service = AccountService(db)
		self.position_service = PositionService(db)

		# 初始化计算器
		self.asset_calculator = AssetCalculator(db)

		# 初始化报告仓库
		self.analysis_report_repo = AnalysisReportRepository(db)

	async def reconcile_account_balance (
			self,
			account_id: str,
			reference_date: Optional[date] = None
	) -> Dict[str, Any]:
		"""
		对账账户资金

		Args:
			account_id: 账户ID
			reference_date: 对账基准日（默认今天）

		Returns:
			对账结果
		"""
		try:
			if reference_date is None:
				reference_date = date.today()

			logger.info(f"开始资金对账: 账户ID={account_id}, 基准日={reference_date}")

			# 1. 获取账户信息
			account = await self.account_service.get_account(account_id)
			if not account:
				raise ValueError("账户不存在")

			# 2. 计算预期余额（根据交易记录）
			expected_balance = await self._calculate_expected_balance(account_id, reference_date)

			# 3. 获取实际余额
			actual_balance = {
				"total_balance": account.total_balance,
				"available_balance": account.available_balance,
				"frozen_balance": account.frozen_balance
			}

			# 4. 比较并分析差异
			differences = ReconciliationManager._analyze_balance_differences(expected_balance, actual_balance)

			# 5. 记录对账结果
			reconciliation_result = {
				"account_id": account_id,
				"account_number": account.account_number,
				"reference_date": reference_date.isoformat(),
				"expected_balance": expected_balance,
				"actual_balance": actual_balance,
				"differences": differences,
				"reconciled": len(differences["items"]) == 0,
				"timestamp": datetime.now().isoformat()
			}

			# 6. 如果有差异，生成差错报告
			if not reconciliation_result["reconciled"]:
				await self._generate_discrepancy_report(account_id, reconciliation_result)

			# 7. 发布对账完成事件
			if self.message_producer:
				await self.message_producer.publish(
					"events.reconciliation",
					{
						"account_id": account_id,
						"reconciled": reconciliation_result["reconciled"],
						"differences_count": len(differences["items"]),
						"total_difference": float(differences["total_difference"]),
						"timestamp": datetime.now().isoformat()
					}
				)

			logger.info(f"资金对账完成: 账户ID={account_id}, 结果={reconciliation_result['reconciled']}")

			return reconciliation_result

		except Exception as e:
			logger.error(f"资金对账失败: {str(e)}")
			raise

	async def reconcile_positions (
			self,
			account_id: str,
			reference_date: Optional[date] = None
	) -> Dict[str, Any]:
		"""
		对账持仓

		Args:
			account_id: 账户ID
			reference_date: 对账基准日（默认今天）

		Returns:
			持仓对账结果
		"""
		try:
			if reference_date is None:
				reference_date = date.today()

			logger.info(f"开始持仓对账: 账户ID={account_id}, 基准日={reference_date}")

			# 1. 获取账户当前持仓
			current_positions = await self.position_service.get_account_positions(account_id)

			# 2. 计算预期持仓（根据交易记录）
			expected_positions = await self._calculate_expected_positions(account_id, reference_date)

			# 3. 比较持仓
			position_comparison = ReconciliationManager._compare_positions(current_positions, expected_positions)

			# 4. 分析差异
			differences = ReconciliationManager._analyze_position_differences(position_comparison)

			# 5. 记录对账结果
			reconciliation_result = {
				"account_id": account_id,
				"reference_date": reference_date.isoformat(),
				"current_positions_count": len(current_positions),
				"expected_positions_count": len(expected_positions),
				"position_comparison": position_comparison,
				"differences": differences,
				"reconciled": differences["total_differences"] == 0,
				"timestamp": datetime.now().isoformat()
			}

			# 6. 如果有差异，生成差错报告
			if not reconciliation_result["reconciled"]:
				await self._generate_position_discrepancy_report(account_id, reconciliation_result)

			logger.info(f"持仓对账完成: 账户ID={account_id}, 结果={reconciliation_result['reconciled']}")

			return reconciliation_result

		except Exception as e:
			logger.error(f"持仓对账失败: {str(e)}")
			raise

	async def auto_reconcile_daily (self, batch_size: int = 100) -> Dict[str, Any]:
		"""
		每日自动对账（批量处理）

		Args:
			batch_size: 批量处理数量

		Returns:
			批量对账结果
		"""
		try:
			logger.info(f"开始每日自动对账，批量大小={batch_size}")

			start_time = datetime.now()

			# 1. 获取所有活跃账户
			active_accounts = await self.account_repo.get_active_accounts(limit=batch_size)

			# 2. 并行对账
			tasks = []
			for account in active_accounts:
				task = asyncio.create_task(self._reconcile_single_account(account.id))
				tasks.append(task)

			# 3. 等待所有对账完成
			results = await asyncio.gather(*tasks, return_exceptions=True)

			# 4. 统计结果
			success_count = 0
			failed_count = 0
			total_differences = 0

			successful_reconciliations = []
			failed_reconciliations = []

			for i, result in enumerate(results):
				account = active_accounts[i]
				if isinstance(result, Exception):
					failed_count += 1
					failed_reconciliations.append({
						"account_id": account.id,
						"account_number": account.account_number,
						"error": str(result)
					})
					logger.error(f"账户对账失败: {account.account_number} - {str(result)}")
				else:
					success_count += 1
					if not result["reconciled"]:
						total_differences += len(result["differences"].get("items", []))

					successful_reconciliations.append({
						"account_id": account.id,
						"account_number": account.account_number,
						"reconciled": result["reconciled"],
						"differences_count": len(
							result["differences"].get("items", [])) if "differences" in result else 0
					})

			# 5. 生成汇总报告
			end_time = datetime.now()
			duration = (end_time - start_time).total_seconds()

			summary_report = {
				"batch_id": f"recon_{datetime.now().strftime('%Y%m%d_%H%M%S')}",
				"start_time": start_time.isoformat(),
				"end_time": end_time.isoformat(),
				"duration_seconds": duration,
				"total_accounts": len(active_accounts),
				"success_count": success_count,
				"failed_count": failed_count,
				"success_rate": success_count / len(active_accounts) if active_accounts else 0,
				"total_differences": total_differences,
				"summary": {
					"all_reconciled": total_differences == 0,
					"accounts_with_differences": len([r for r in successful_reconciliations if not r["reconciled"]]),
					"average_differences_per_account": total_differences / success_count if success_count > 0 else 0
				},
				"successful_reconciliations": successful_reconciliations,
				"failed_reconciliations": failed_reconciliations,
				"timestamp": end_time.isoformat()
			}

			# 6. 保存对账报告
			await self._save_reconciliation_report(summary_report)

			# 7. 发送通知（如果有差异）
			if total_differences > 0 and self.message_producer:
				await self.message_producer.publish(
					"events.reconciliation.batch",
					{
						"batch_id": summary_report["batch_id"],
						"total_differences": total_differences,
						"accounts_with_differences": summary_report["summary"]["accounts_with_differences"],
						"timestamp": end_time.isoformat()
					}
				)

			logger.info(f"每日自动对账完成: 成功={success_count}, 失败={failed_count}, 差异数={total_differences}")

			return summary_report

		except Exception as e:
			logger.error(f"每日自动对账失败: {str(e)}")
			raise

	async def fix_balance_discrepancy (
			self,
			account_id: str,
			discrepancy_type: str,
			expected_amount: Decimal,
			actual_amount: Decimal,
			reason: str
	) -> Dict[str, Any]:
		"""
		修复资金差异

		Args:
			account_id: 账户ID
			discrepancy_type: 差异类型（total_balance, available_balance, frozen_balance）
			expected_amount: 预期金额
			actual_amount: 实际金额
			reason: 修复原因

		Returns:
			修复结果
		"""
		try:
			logger.info(f"开始修复资金差异: 账户ID={account_id}, 类型={discrepancy_type}")

			# 1. 计算差异金额
			difference = expected_amount - actual_amount

			# 2. 执行修复
			async with self.db.begin():
				if discrepancy_type == "total_balance":
					await self.account_service.adjust_total_balance(account_id, difference, reason)
				elif discrepancy_type == "available_balance":
					await self.account_service.adjust_available_balance(account_id, difference, reason)
				elif discrepancy_type == "frozen_balance":
					await self.account_service.adjust_frozen_balance(account_id, difference, reason)
				else:
					raise ValueError(f"不支持的差异类型: {discrepancy_type}")

			# 3. 记录修复操作
			await self._record_discrepancy_fix(
				account_id=account_id,
				discrepancy_type=discrepancy_type,
				expected_amount=expected_amount,
				actual_amount=actual_amount,
				difference=difference,
				reason=reason,
				fixed_by="events"
			)

			# 4. 重新对账验证
			verification_result = await self.reconcile_account_balance(account_id)

			logger.info(f"资金差异修复完成: 账户ID={account_id}, 差异={difference}")

			return {
				"success": True,
				"account_id": account_id,
				"discrepancy_type": discrepancy_type,
				"difference": float(difference),
				"fixed": True,
				"verification_reconciled": verification_result["reconciled"],
				"message": "资金差异修复完成"
			}

		except Exception as e:
			await self.db.rollback()
			logger.error(f"资金差异修复失败: {str(e)}")
			return {
				"success": False,
				"error": str(e)
			}

	async def _calculate_expected_balance (
			self,
			account_id: str,
			reference_date: date
	) -> Dict[str, Decimal]:
		"""计算预期余额"""
		# 获取账户初始余额
		account = await self.account_service.get_account(account_id)
		initial_balance = account.initial_balance

		# 获取从开户日到参考日期的所有交易
		start_date = account.created_at.date()
		end_date = reference_date

		# 计算期间所有交易对资金的影响
		from datetime import datetime
		start_datetime = datetime.combine(start_date, datetime.min.time())
		end_datetime = datetime.combine(end_date, datetime.max.time())
		trades = await self.trade_repo.get_by_account_id(account_id, start_datetime, end_datetime, limit=1000)

		total_deposit = Decimal("0.00")
		total_withdrawal = Decimal("0.00")
		total_buy_cost = Decimal("0.00")     # 买入总支出
		total_sell_proceed = Decimal("0.00") # 卖出总收入
		total_fee = Decimal("0.00")

		for trade in trades:
			trade_value = Decimal(str(trade.price)) * Decimal(str(trade.volume))
			trade_fee = Decimal(str(trade.commission or 0)) + Decimal(str(trade.tax or 0))
			total_fee += trade_fee

			# 根据交易方向分别累计
			direction = getattr(trade, 'direction', 'buy')
			if direction == 'buy':
				total_buy_cost += trade_value
			elif direction == 'sell':
				total_sell_proceed += trade_value

		# 预期余额 = 初始余额 + 存款 - 取款 + 卖出收入 - 买入支出 - 费用
		expected_total = (
			initial_balance +
			total_deposit -
			total_withdrawal +
			total_sell_proceed -
			total_buy_cost -
			total_fee
		)

		# 可用余额 = 总余额 - 冻结资金（当前未平仓买单占用的保证金估算为买入成本的20%）
		estimated_margin = total_buy_cost * Decimal("0.2") if total_buy_cost > 0 else Decimal("0.00")
		available_expected = expected_total - estimated_margin

		return {
			"total_balance": expected_total,
			"available_balance": max(available_expected, Decimal("0.00")),
			"frozen_balance": estimated_margin
		}


	@staticmethod
	async def reconcile_trades (
			system_trades: List,
			broker_trades: List[Dict]
	) -> Dict[str, Any]:
		"""
		对账交易记录

		Args:
			system_trades: 系统交易记录
			broker_trades: 券商交易记录

		Returns:
			交易对账结果
		"""
		try:
			# 转换系统交易记录为字典格式
			system_trades_dict = {}
			for trade in system_trades:
				system_trades_dict[trade.trade_id] = {
					'trade_id': trade.trade_id,
					'security_id': trade.ts_code,
					'direction': getattr(trade, 'direction', 'buy'),
					'price': trade.price,
					'quantity': trade.volume,
					'trade_time': trade.trade_time,
					'status': 'filled'
				}

			# 转换券商交易记录为字典格式
			broker_trades_dict = {}
			for trade in broker_trades:
				broker_trades_dict[trade['trade_id']] = trade

			# 比较交易记录
			system_trade_ids = set(system_trades_dict.keys())
			broker_trade_ids = set(broker_trades_dict.keys())

			# 找出差异
			missing_in_system = broker_trade_ids - system_trade_ids
			missing_in_broker = system_trade_ids - broker_trade_ids
			discrepancies = []

			# 处理缺失的交易
			for trade_id in missing_in_system:
				discrepancies.append({
					'trade_id': trade_id,
					'action': 'add_missing_trade',
					'trade_data': broker_trades_dict[trade_id],
					'type': 'trade_missing'
				})

			for trade_id in missing_in_broker:
				discrepancies.append({
					'trade_id': trade_id,
					'action': 'remove_extra_trade',
					'trade_data': system_trades_dict[trade_id],
					'type': 'trade_extra'
				})

			# 比较相同ID的交易记录
			common_trade_ids = system_trade_ids & broker_trade_ids
			for trade_id in common_trade_ids:
				system_trade = system_trades_dict[trade_id]
				broker_trade = broker_trades_dict[trade_id]

				# 比较关键字段
				if (system_trade['security_id'] != broker_trade['security_id'] or
					system_trade['price'] != broker_trade['price'] or
					system_trade['quantity'] != broker_trade['quantity'] or
					system_trade['direction'] != broker_trade['direction']):
					discrepancies.append({
						'trade_id': trade_id,
						'action': 'update_trade',
						'trade_data': broker_trade,
						'type': 'trade_mismatch'
					})

			# 构建对账结果
			result = {
				'reconciled': len(discrepancies) == 0,
				'has_discrepancy': len(discrepancies) > 0,
				'discrepancies': discrepancies,
				'system_trades_count': len(system_trades),
				'broker_trades_count': len(broker_trades),
				'timestamp': datetime.now().isoformat()
			}

			return result

		except Exception as e:
			logger.error(f"交易对账失败: {str(e)}")
			raise

	async def _calculate_expected_positions (
			self,
			account_id: str,
			reference_date: date
	) -> List[Dict[str, Any]]:
		"""计算预期持仓"""
		# 获取从开户日到参考日期的所有交易
		account = await self.account_service.get_account(account_id)
		start_date = account.created_at.date()

		from datetime import datetime
		start_datetime = datetime.combine(start_date, datetime.min.time())
		end_datetime = datetime.combine(reference_date, datetime.max.time())
		trades = await self.trade_repo.get_by_account_id(account_id, start_datetime, end_datetime, limit=1000)

		# 按证券代码分组计算净持仓
		position_map = {}

		for trade in trades:
			ts_code = trade.ts_code

			if ts_code not in position_map:
				position_map[ts_code] = {
					"ts_code": ts_code,
					"total_volume": 0,
					"total_cost": Decimal("0.00"),
					"trades": []
				}

			position = position_map[ts_code]

			# 根据交易方向更新持仓
			direction = getattr(trade, 'direction', 'buy')
			position["trades"].append({
				"trade_id": trade.trade_id,
				"direction": direction,
				"price": trade.price,
				"volume": trade.volume,
				"time": trade.trade_time
			})

			# 根据买卖方向计算持仓量和成本
			if trade.price and trade.volume:
				trade_qty = Decimal(str(trade.volume))
				if direction == 'buy':
					position["total_volume"] += trade_qty
					position["total_cost"] += Decimal(str(trade.price)) * trade_qty
				elif direction == 'sell':
					position["total_volume"] -= trade_qty
					# 卖出时按移动加权平均成本减少持仓成本
					if position["total_volume"] > 0:
						position["total_cost"] -= Decimal(str(trade.price)) * trade_qty
					else:
						position["total_cost"] = Decimal("0.00")

		# 转换为预期持仓列表
		expected_positions = []
		for ts_code, data in position_map.items():
			if data["total_volume"] > 0:
				avg_cost = data["total_cost"] / data["total_volume"] if data["total_volume"] > 0 else Decimal("0.00")

				expected_positions.append({
					"ts_code": ts_code,
					"volume": data["total_volume"],
					"cost_price": avg_cost,
					"market_value": Decimal("0.00"),  # 需要最新价格计算
					"last_price": None,
					"pnl": Decimal("0.00"),
					"pnl_rate": Decimal("0.00")
				})

		return expected_positions

	@staticmethod
	def _analyze_balance_differences (
			expected: Dict[str, Decimal],
			actual: Dict[str, Decimal]
	) -> Dict[str, Any]:
		"""分析资金差异"""
		differences = {
			"items": [],
			"total_difference": Decimal("0.00")
		}

		for balance_type in ["total_balance", "available_balance", "frozen_balance"]:
			expected_value = expected.get(balance_type, Decimal("0.00"))
			actual_value = actual.get(balance_type, Decimal("0.00"))

			if expected_value != actual_value:
				difference = expected_value - actual_value

				differences["items"].append({
					"balance_type": balance_type,
					"expected": float(expected_value),
					"actual": float(actual_value),
					"difference": float(difference),
					"difference_percentage": float((difference / expected_value) * 100 if expected_value != 0 else 0)
				})

				differences["total_difference"] += abs(difference)

		return differences

	@staticmethod
	def _compare_positions (
			current_positions: List,
			expected_positions: List[Dict[str, Any]]
	) -> Dict[str, Any]:
		"""比较持仓"""
		comparison = {
			"matched": [],
			"missing_in_current": [],
			"missing_in_expected": [],
			"volume_differences": []
		}

		# 将当前持仓转换为字典
		current_dict = {pos.ts_code: pos for pos in current_positions}
		expected_dict = {pos["ts_code"]: pos for pos in expected_positions}

		# 查找匹配的持仓
		all_codes = set(current_dict.keys()) | set(expected_dict.keys())

		for ts_code in all_codes:
			current_pos = current_dict.get(ts_code)
			expected_pos = expected_dict.get(ts_code)

			if current_pos and expected_pos:
				# 比较持仓量
				if current_pos.volume != expected_pos["volume"]:
					comparison["volume_differences"].append({
						"ts_code": ts_code,
						"current_volume": current_pos.volume,
						"expected_volume": expected_pos["volume"],
						"difference": current_pos.volume - expected_pos["volume"]
					})
				else:
					comparison["matched"].append({
						"ts_code": ts_code,
						"volume": current_pos.volume,
						"cost_price": current_pos.cost_price
					})

			elif current_pos and not expected_pos:
				comparison["missing_in_expected"].append({
					"ts_code": ts_code,
					"volume": current_pos.volume,
					"cost_price": current_pos.cost_price
				})

			elif not current_pos and expected_pos:
				comparison["missing_in_current"].append({
					"ts_code": ts_code,
					"volume": expected_pos["volume"],
					"cost_price": expected_pos["cost_price"]
				})

		return comparison

	@staticmethod
	def _analyze_position_differences (comparison: Dict[str, Any]) -> Dict[str, Any]:
		"""分析持仓差异"""
		total_differences = (
				len(comparison["missing_in_current"]) +
				len(comparison["missing_in_expected"]) +
				len(comparison["volume_differences"])
		)

		volume_difference_sum = sum(
			abs(item["difference"]) for item in comparison["volume_differences"]
		)

		return {
			"total_differences": total_differences,
			"missing_in_current_count": len(comparison["missing_in_current"]),
			"missing_in_expected_count": len(comparison["missing_in_expected"]),
			"volume_differences_count": len(comparison["volume_differences"]),
			"volume_difference_sum": volume_difference_sum,
			"items": {
				"missing_in_current": comparison["missing_in_current"],
				"missing_in_expected": comparison["missing_in_expected"],
				"volume_differences": comparison["volume_differences"]
			}
		}

	async def _reconcile_single_account (self, account_id: str) -> Dict[str, Any]:
		"""对账单个账户"""
		try:
			# 执行资金对账
			balance_result = await self.reconcile_account_balance(account_id)

			# 执行持仓对账
			position_result = await self.reconcile_positions(account_id)

			return {
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

		except Exception as e:
			logger.error(f"单个账户对账失败: 账户ID={account_id}, 错误={str(e)}")
			raise

	async def _generate_discrepancy_report (
			self,
			account_id: str,
			reconciliation_result: Dict[str, Any]
	) -> None:
		"""生成资金差异报告"""
		try:
			# 生成资金差异报告
			report = {
				"report_type": "balance_discrepancy",
				"account_id": account_id,
				"generated_at": datetime.now().isoformat(),
				"reconciliation_result": reconciliation_result,
				"suggested_actions": ReconciliationManager._suggest_balance_fix_actions(reconciliation_result["differences"]),
				"priority": ReconciliationManager._calculate_discrepancy_priority(reconciliation_result["differences"])
			}

			# 保存报告到数据库
			report_name = f"资金差异报告_{account_id}_{datetime.now().strftime('%Y%m%d_%H%M%S')}"
			report_type = "balance_discrepancy"
			report_config = {
				"account_id": account_id,
				"difference_count": len(reconciliation_result['differences']['items']),
				"priority": report["priority"]
			}

			# 创建分析报告
			analysis_report = await self.analysis_report_repo.create_report(
				report_type=report_type,
				report_name=report_name,
				report_config=report_config,
				report_data=report,
				is_public=False,
				tags=["reconciliation", "balance", "discrepancy"]
			)

			# 标记报告为已完成
			await self.analysis_report_repo.mark_as_completed(
				report_id=analysis_report.id,
				file_path=f"discrepancy/balance_{account_id}_{datetime.now().strftime('%Y%m%d_%H%M%S')}.json",
				file_size=len(str(report))
			)

			logger.warning(
				f"生成资金差异报告: 账户ID={account_id}, 差异数={len(reconciliation_result['differences']['items'])}, 报告ID={analysis_report.id}")

		except Exception as e:
			logger.error(f"保存资金差异报告失败: {str(e)}")
			raise

	async def _generate_position_discrepancy_report (
			self,
			account_id: str,
			reconciliation_result: Dict[str, Any]
	) -> None:
		"""生成持仓差异报告"""
		try:
			# 生成持仓差异报告
			report = {
				"report_type": "position_discrepancy",
				"account_id": account_id,
				"generated_at": datetime.now().isoformat(),
				"reconciliation_result": reconciliation_result,
				"suggested_actions": ReconciliationManager._suggest_position_fix_actions(reconciliation_result["differences"]),
				"priority": ReconciliationManager._calculate_position_discrepancy_priority(reconciliation_result["differences"])
			}

			# 保存报告到数据库
			report_name = f"持仓差异报告_{account_id}_{datetime.now().strftime('%Y%m%d_%H%M%S')}"
			report_type = "position_discrepancy"
			report_config = {
				"account_id": account_id,
				"difference_count": reconciliation_result['differences']['total_differences'],
				"priority": report["priority"]
			}

			# 创建分析报告
			analysis_report = await self.analysis_report_repo.create_report(
				report_type=report_type,
				report_name=report_name,
				report_config=report_config,
				report_data=report,
				is_public=False,
				tags=["reconciliation", "position", "discrepancy"]
			)

			# 标记报告为已完成
			await self.analysis_report_repo.mark_as_completed(
				report_id=analysis_report.id,
				file_path=f"discrepancy/position_{account_id}_{datetime.now().strftime('%Y%m%d_%H%M%S')}.json",
				file_size=len(str(report))
			)

			logger.warning(
				f"生成持仓差异报告: 账户ID={account_id}, 差异数={reconciliation_result['differences']['total_differences']}, 报告ID={analysis_report.id}")

		except Exception as e:
			logger.error(f"保存持仓差异报告失败: {str(e)}")
			raise

	async def _record_discrepancy_fix (
			self,
			account_id: str,
			discrepancy_type: str,
			expected_amount: Decimal,
			actual_amount: Decimal,
			difference: Decimal,
			reason: str,
			fixed_by: str
	) -> None:
		"""记录差异修复操作"""
		try:
			# 生成差异修复记录
			fix_record = {
				"account_id": account_id,
				"discrepancy_type": discrepancy_type,
				"expected_amount": float(expected_amount),
				"actual_amount": float(actual_amount),
				"difference": float(difference),
				"reason": reason,
				"fixed_by": fixed_by,
				"fixed_at": datetime.now().isoformat()
			}

			# 保存修复记录到数据库
			report_name = f"差异修复记录_{account_id}_{datetime.now().strftime('%Y%m%d_%H%M%S')}"
			report_type = "discrepancy_fix"
			report_config = {
				"account_id": account_id,
				"discrepancy_type": discrepancy_type,
				"difference": float(difference)
			}

			# 创建分析报告
			analysis_report = await self.analysis_report_repo.create_report(
				report_type=report_type,
				report_name=report_name,
				report_config=report_config,
				report_data=fix_record,
				is_public=False,
				tags=["reconciliation", "fix", "discrepancy"]
			)

			# 标记报告为已完成
			await self.analysis_report_repo.mark_as_completed(
				report_id=analysis_report.id,
				file_path=f"fix/discrepancy_{account_id}_{datetime.now().strftime('%Y%m%d_%H%M%S')}.json",
				file_size=len(str(fix_record))
			)

			logger.info(f"记录差异修复: 账户ID={account_id}, 类型={discrepancy_type}, 差异={difference}, 报告ID={analysis_report.id}")

		except Exception as e:
			logger.error(f"保存差异修复记录失败: {str(e)}")
			raise

	async def _save_reconciliation_report (self, report: Dict[str, Any]) -> None:
		"""保存对账报告"""
		try:
			# 保存对账报告到数据库
			report_name = f"对账报告_{report['batch_id']}"
			report_type = "reconciliation"
			report_config = {
				"batch_id": report['batch_id'],
				"total_accounts": report['total_accounts'],
				"success_count": report['success_count'],
				"failed_count": report['failed_count']
			}

			# 创建分析报告
			analysis_report = await self.analysis_report_repo.create_report(
				report_type=report_type,
				report_name=report_name,
				report_config=report_config,
				report_data=report,
				is_public=False,
				tags=["reconciliation", "daily"]
			)

			# 标记报告为已完成
			await self.analysis_report_repo.mark_as_completed(
				report_id=analysis_report.id,
				file_path=f"reconciliation/{report['batch_id']}.json",
				file_size=len(str(report))
			)

			report_id = report["batch_id"]
			logger.info(f"保存对账报告: {report_id}, 账户数={report['total_accounts']}, 报告ID={analysis_report.id}")

		except Exception as e:
			logger.error(f"保存对账报告失败: {str(e)}")
			raise

	@staticmethod
	def _suggest_balance_fix_actions (differences: Dict[str, Any]) -> List[Dict[str, Any]]:
		"""建议资金修复措施"""
		suggestions = []

		for item in differences.get("items", []):
			if item["difference"] > 0:
				action = "增加资金"
				amount = item["difference"]
			else:
				action = "减少资金"
				amount = -item["difference"]

			suggestions.append({
				"balance_type": item["balance_type"],
				"action": action,
				"amount": amount,
				"reason": f"修正{item['balance_type']}差异"
			})

		return suggestions

	@staticmethod
	def _suggest_position_fix_actions (differences: Dict[str, Any]) -> List[Dict[str, Any]]:
		"""建议持仓修复措施"""
		suggestions = []

		# 处理缺失持仓
		for item in differences.get("items", {}).get("missing_in_current", []):
			suggestions.append({
				"ts_code": item["ts_code"],
				"action": "补登持仓",
				"volume": item["volume"],
				"cost_price": item["cost_price"],
				"reason": "持仓在对账中缺失"
			})

		# 处理多余持仓
		for item in differences.get("items", {}).get("missing_in_expected", []):
			suggestions.append({
				"ts_code": item["ts_code"],
				"action": "移除持仓",
				"volume": item["volume"],
				"reason": "持仓在预期中不存在"
			})

		# 处理数量差异
		for item in differences.get("items", {}).get("volume_differences", []):
			if item["difference"] > 0:
				action = "减少持仓"
				volume = item["difference"]
			else:
				action = "增加持仓"
				volume = -item["difference"]

			suggestions.append({
				"ts_code": item["ts_code"],
				"action": action,
				"volume": volume,
				"reason": f"修正持仓数量差异: 当前{item['current_volume']}, 预期{item['expected_volume']}"
			})

		return suggestions

	@staticmethod
	def _calculate_discrepancy_priority (differences: Dict[str, Any]) -> str:
		"""计算差异优先级"""
		total_difference = differences.get("total_difference", Decimal("0.00"))

		if total_difference > Decimal("10000.00"):
			return "high"
		elif total_difference > Decimal("1000.00"):
			return "medium"
		else:
			return "low"

	@staticmethod
	def _calculate_position_discrepancy_priority (differences: Dict[str, Any]) -> str:
		"""计算持仓差异优先级"""
		total_differences = differences.get("total_differences", 0)

		if total_differences > 10:
			return "high"
		elif total_differences > 3:
			return "medium"
		else:
			return "low"