# -*- coding: utf-8 -*-
"""
数据同步服务
基于混合架构设计，实现数据同步的核心业务逻辑
位置：quant_server/modules/events/services/sync_service.py

设计原则：
1. 使用共享Repository进行数据访问
2. 依赖事件引擎发布同步进度和结果
3. 支持同步和异步两种执行模式
4. 完整的错误处理和重试机制
"""

from typing import Dict, List, Any, Optional
from datetime import datetime, date, timedelta
import logging
from sqlalchemy.ext.asyncio import AsyncSession

# 导入共享层组件
from quant_server.shared.database.repositories import (
	StockRepository,
	QuoteRepository,
	SyncTaskRepository,
	TradeCalendarRepository
)
from quant_server.shared.sources.source_factory import DataSourceFactory
from quant_server.shared.cache.redis_cache import RedisCache

# 导入核心基础设施
from quant_server.core.engines.system.event_engine import EventEngine
from quant_server.modules.data.events import (
	DataSyncedEvent,
	SyncProgressEvent,
	SyncStartedEvent,
	SyncCompletedEvent,
	SyncFailedEvent
)

# 导入数据模块常量
from quant_server.modules.data.constants import (
	DataSource,
	DataType,
	SyncConfig,
	CacheKey
)

# 导入数据模块模型
from quant_server.modules.data.models import (
	BatchSyncRequest,
	SyncResult,
	SyncProgress
)

# 配置日志
logger = logging.getLogger(__name__)


class DataSyncService:
	"""
	数据同步服务类
	负责管理数据同步的整个生命周期
	"""

	def __init__ (self, session: AsyncSession, event_engine: Optional[EventEngine] = None):
		"""
		初始化数据同步服务

		Args:
			session: 数据库会话
			event_engine: 事件引擎，用于发布同步事件
		"""
		self.session = session
		self.event_engine = event_engine

		# 初始化Repository
		self.stock_repo = StockRepository(session)
		self.quote_repo = QuoteRepository(session)
		self.sync_task_repo = SyncTaskRepository(session)
		self.calendar_repo = TradeCalendarRepository(session)

		# 初始化数据源工厂
		self.source_factory = DataSourceFactory()

		# 初始化缓存（懒加载）
		self._cache = None

	@property
	def cache (self) -> RedisCache:
		"""获取缓存实例（懒加载）"""
		if self._cache is None:
			from quant_server.shared.config.settings import get_settings
			settings = get_settings()
			self._cache = RedisCache(
				host=settings.redis_host,
				port=settings.redis_port,
				db=settings.redis_db,
				password=settings.redis_password
			)
		return self._cache

	async def sync_market_data (
			self,
			data_type: str,
			start_date: Optional[date] = None,
			end_date: Optional[date] = None,
			ts_codes: Optional[List[str]] = None,
			user_id: Optional[int] = None
	) -> Dict[str, Any]:
		"""
		同步市场数据

		Args:
			data_type: 数据类型
			start_date: 开始日期
			end_date: 结束日期
			ts_codes: 股票代码列表
			user_id: 用户ID（用于事件发布）

		Returns:
			Dict: 同步结果
		"""
		logger.info(f"开始同步市场数据，类型: {data_type}, 用户ID: {user_id}")

		task_id = None
		try:
			# 创建同步任务记录
			task_id = await self._create_sync_task(
				data_type=data_type,
				start_date=start_date,
				end_date=end_date,
				ts_codes=ts_codes,
				user_id=user_id
			)

			# 发布同步开始事件
			await self._publish_sync_event(
				event_type="started",
				task_id=task_id,
				data_type=data_type,
				user_id=user_id
			)

			# 根据数据类型选择同步方法
			sync_result = await self._sync_by_data_type(
				data_type=data_type,
				start_date=start_date,
				end_date=end_date,
				ts_codes=ts_codes,
				task_id=task_id,
				user_id=user_id
			)

			# 更新任务状态
			await self._update_sync_task(
				task_id=task_id,
				status="completed",
				result=sync_result,
				error_message=None
			)

			# 发布同步完成事件
			await self._publish_sync_event(
				event_type="completed",
				task_id=task_id,
				data_type=data_type,
				result=sync_result,
				user_id=user_id
			)

			# 清理相关缓存
			await self._clean_cache_after_sync(data_type, ts_codes)

			logger.info(f"市场数据同步完成，任务ID: {task_id}, 结果: {sync_result}")

			return {
				"success": True,
				"task_id": task_id,
				"result": sync_result,
				"message": "数据同步完成"
			}

		except Exception as e:
			logger.error(f"市场数据同步失败: {str(e)}", exc_info=True)

			# 更新任务状态为失败
			if task_id:
				await self._update_sync_task(
					task_id=task_id,
					status="failed",
					result=None,
					error_message=str(e)
				)

				# 发布同步失败事件
				await self._publish_sync_event(
					event_type="failed",
					task_id=task_id,
					data_type=data_type,
					error=str(e),
					user_id=user_id
				)

			return {
				"success": False,
				"task_id": task_id,
				"error": str(e),
				"message": "数据同步失败"
			}

	async def batch_sync (
			self,
			request: BatchSyncRequest,
			user_id: Optional[int] = None
	) -> Dict[str, Any]:
		"""
		批量同步数据

		Args:
			request: 批量同步请求
			user_id: 用户ID

		Returns:
			Dict: 批量同步结果
		"""
		logger.info(f"开始批量同步，数据类型: {request.data_types}, 用户ID: {user_id}")

		batch_task_id = f"batch_sync_{datetime.now().strftime('%Y%m%d_%H%M%S')}"
		results = []

		try:
			# 发布批量同步开始事件
			await self._publish_sync_event(
				event_type="batch_started",
				task_id=batch_task_id,
				data_types=request.data_types,
				user_id=user_id
			)

			# 按顺序执行同步任务
			for idx, data_type in enumerate(request.data_types):
				# 计算进度
				progress = (idx / len(request.data_types)) * 100

				# 发布进度事件
				await self._publish_sync_event(
					event_type="progress",
					task_id=batch_task_id,
					data_type=data_type,
					progress=progress,
					current_task=f"正在同步 {data_type}",
					user_id=user_id
				)

				# 执行单个同步任务
				try:
					result = await self.sync_market_data(
						data_type=data_type,
						start_date=request.start_date,
						end_date=request.end_date,
						ts_codes=request.ts_codes,
						user_id=user_id
					)

					# 记录结果
					sync_result = SyncResult(
						data_type=data_type,
						success=result["success"],
						records_added=result.get("result", {}).get("records_added", 0),
						records_updated=result.get("result", {}).get("records_updated", 0),
						records_failed=result.get("result", {}).get("records_failed", 0),
						start_time=datetime.now(),
						end_time=datetime.now(),
						error_message=result.get("error")
					)
					results.append(sync_result.dict())

				except Exception as e:
					logger.error(f"同步数据类型 {data_type} 失败: {str(e)}")

					# 记录失败结果
					sync_result = SyncResult(
						data_type=data_type,
						success=False,
						records_added=0,
						records_updated=0,
						records_failed=0,
						start_time=datetime.now(),
						end_time=datetime.now(),
						error_message=str(e)
					)
					results.append(sync_result.dict())

			# 发布批量同步完成事件
			await self._publish_sync_event(
				event_type="batch_completed",
				task_id=batch_task_id,
				results=results,
				user_id=user_id
			)

			logger.info(f"批量同步完成，任务ID: {batch_task_id}")

			return {
				"success": True,
				"task_id": batch_task_id,
				"results": results,
				"total_tasks": len(request.data_types),
				"completed_tasks": len(results),
				"message": "批量同步完成"
			}

		except Exception as e:
			logger.error(f"批量同步失败: {str(e)}", exc_info=True)

			# 发布批量同步失败事件
			await self._publish_sync_event(
				event_type="batch_failed",
				task_id=batch_task_id,
				error=str(e),
				results=results,
				user_id=user_id
			)

			return {
				"success": False,
				"task_id": batch_task_id,
				"results": results,
				"error": str(e),
				"message": "批量同步失败"
			}

	async def get_sync_status (
			self,
			task_id: str,
			user_id: Optional[int] = None
	) -> Dict[str, Any]:
		"""
		获取同步任务状态

		Args:
			task_id: 任务ID
			user_id: 用户ID

		Returns:
			Dict: 任务状态
		"""
		try:
			# 从数据库获取任务
			task = await self.sync_task_repo.get_by_task_id(task_id)

			if not task:
				raise ValueError(f"任务 {task_id} 不存在")

			# 检查权限（如果指定了用户ID）
			if user_id and task.user_id != user_id:
				raise ValueError("无权查看此任务")

			# 从缓存获取实时进度（如果有）
			progress_key = CacheKey.SYNC_PROGRESS.format(task_id=task_id)
			cached_progress = await self.cache.get(progress_key)

			if cached_progress:
				progress_data = cached_progress
			else:
				progress_data = {
					"progress": task.completed_items / task.total_items * 100 if task.total_items > 0 else 0,
					"current_task": task.current_task,
					"estimated_time_remaining": task.estimated_time_remaining
				}

			return {
				"task_id": task.task_id,
				"status": task.status,
				"progress": progress_data,
				"start_time": task.started_at.isoformat() if task.started_at else None,
				"end_time": task.completed_at.isoformat() if task.completed_at else None,
				"data_type": task.data_type,
				"total_items": task.total_items,
				"completed_items": task.completed_items,
				"error_message": task.error_message,
				"results": task.results
			}

		except Exception as e:
			logger.error(f"获取同步状态失败: {str(e)}", exc_info=True)
			raise

	async def cancel_sync (
			self,
			task_id: str,
			user_id: Optional[int] = None
	) -> Dict[str, Any]:
		"""
		取消同步任务

		Args:
			task_id: 任务ID
			user_id: 用户ID

		Returns:
			Dict: 取消结果
		"""
		try:
			# 获取任务
			task = await self.sync_task_repo.get_by_task_id(task_id)

			if not task:
				raise ValueError(f"任务 {task_id} 不存在")

			# 检查权限
			if user_id and task.user_id != user_id:
				raise ValueError("无权取消此任务")

			# 检查任务状态
			if task.status not in ["pending", "running"]:
				raise ValueError(f"任务状态为 {task.status}，无法取消")

			# 更新任务状态
			await self.sync_task_repo.update(task.id, {
				"status": "cancelled",
				"cancelled_at": datetime.now(),
				"error_message": "任务被用户取消"
			})

			# 发布取消事件
			await self._publish_sync_event(
				event_type="cancelled",
				task_id=task_id,
				data_type=task.data_type,
				user_id=user_id
			)

			# 清理缓存
			await self.cache.delete(CacheKey.SYNC_PROGRESS.format(task_id=task_id))
			await self.cache.delete(CacheKey.SYNC_STATUS.format(task_id=task_id))

			logger.info(f"同步任务已取消，任务ID: {task_id}")

			return {
				"success": True,
				"task_id": task_id,
				"status": "cancelled",
				"message": "同步任务已成功取消"
			}

		except Exception as e:
			logger.error(f"取消同步任务失败: {str(e)}", exc_info=True)
			raise

	async def retry_failed_sync (
			self,
			task_id: str,
			user_id: Optional[int] = None
	) -> Dict[str, Any]:
		"""
		重试失败的同步任务

		Args:
			task_id: 任务ID
			user_id: 用户ID

		Returns:
			Dict: 重试结果
		"""
		try:
			# 获取原始任务
			original_task = await self.sync_task_repo.get_by_task_id(task_id)

			if not original_task:
				raise ValueError(f"任务 {task_id} 不存在")

			if original_task.status != "failed":
				raise ValueError("只有失败的任务才能重试")

			# 检查权限
			if user_id and original_task.user_id != user_id:
				raise ValueError("无权重试此任务")

			# 创建新的重试任务
			retry_task_id = f"retry_{task_id}_{datetime.now().strftime('%H%M%S')}"

			# 执行重试
			result = await self.sync_market_data(
				data_type=original_task.data_type,
				start_date=original_task.start_date,
				end_date=original_task.end_date,
				ts_codes=original_task.ts_codes,
				user_id=user_id
			)

			# 记录重试关系
			await self.sync_task_repo.update(original_task.id, {
				"retry_task_id": retry_task_id
			})

			return {
				"success": True,
				"original_task_id": task_id,
				"retry_task_id": retry_task_id,
				"result": result,
				"message": "重试任务已创建"
			}

		except Exception as e:
			logger.error(f"重试同步任务失败: {str(e)}", exc_info=True)
			raise

	# ==================== 私有辅助方法 ====================

	async def _create_sync_task (
			self,
			data_type: str,
			start_date: Optional[date] = None,
			end_date: Optional[date] = None,
			ts_codes: Optional[List[str]] = None,
			user_id: Optional[int] = None
	) -> str:
		"""创建同步任务记录"""
		task_id = f"sync_{data_type}_{datetime.now().strftime('%Y%m%d_%H%M%S')}"

		task_data = {
			"task_id": task_id,
			"data_type": data_type,
			"status": "pending",
			"user_id": user_id,
			"start_date": start_date,
			"end_date": end_date,
			"ts_codes": ts_codes,
			"total_items": self._estimate_total_items(data_type, ts_codes),
			"completed_items": 0,
			"created_at": datetime.now()
		}

		await self.sync_task_repo.create(task_data)

		# 缓存任务状态
		await self.cache.set(
			CacheKey.SYNC_STATUS.format(task_id=task_id),
			task_data,
			ttl=86400  # 24小时
		)

		return task_id

	async def _update_sync_task (
			self,
			task_id: str,
			status: str,
			result: Optional[Dict] = None,
			error_message: Optional[str] = None
	):
		"""更新同步任务状态"""
		task = await self.sync_task_repo.get_by_task_id(task_id)
		if not task:
			return

		update_data = {
			"status": status,
			"updated_at": datetime.now()
		}

		if status == "running":
			update_data["started_at"] = datetime.now()
		elif status in ["completed", "failed", "cancelled"]:
			update_data["completed_at"] = datetime.now()

		if result:
			update_data["result"] = result
			update_data["records_added"] = result.get("records_added", 0)
			update_data["records_updated"] = result.get("records_updated", 0)
			update_data["records_failed"] = result.get("records_failed", 0)
			update_data["completed_items"] = result.get("total_items", 0)

		if error_message:
			update_data["error_message"] = error_message

		await self.sync_task_repo.update(task.id, update_data)

		# 更新缓存
		await self.cache.set(
			CacheKey.SYNC_STATUS.format(task_id=task_id),
			update_data,
			ttl=86400
		)

	async def _sync_by_data_type (
			self,
			data_type: str,
			start_date: Optional[date],
			end_date: Optional[date],
			ts_codes: Optional[List[str]],
			task_id: str,
			user_id: Optional[int] = None
	) -> Dict[str, Any]:
		"""根据数据类型选择同步方法"""
		sync_methods = {
			DataType.STOCK_LIST: self._sync_stock_list,
			DataType.DAILY_QUOTES: self._sync_daily_quotes,
			DataType.ADJUSTED_QUOTES: self._sync_adjusted_quotes,
			DataType.FINANCIAL_DATA: self._sync_financial_data,
			DataType.INDEX_DATA: self._sync_index_data,
			DataType.CALENDAR: self._sync_calendar
		}

		method = sync_methods.get(data_type)
		if not method:
			raise ValueError(f"不支持的数据类型: {data_type}")

		return await method(
			start_date=start_date,
			end_date=end_date,
			ts_codes=ts_codes,
			task_id=task_id,
			user_id=user_id
		)

	async def _sync_stock_list (
			self,
			start_date: Optional[date],
			end_date: Optional[date],
			ts_codes: Optional[List[str]],
			task_id: str,
			user_id: Optional[int] = None
	) -> Dict[str, Any]:
		"""同步股票列表"""
		try:
			# 获取数据源
			source = self.source_factory.get_source(DataSource.TUSHARE)

			# 获取股票列表数据
			logger.info("开始同步股票列表...")
			stock_list = await source.get_stock_list()

			# 批量保存到数据库
			records_added = 0
			records_updated = 0

			for stock_data in stock_list:
				# 检查是否已存在
				existing = await self.stock_repo.get_by_ts_code(stock_data["ts_code"])

				if existing:
					# 更新现有记录
					await self.stock_repo.update(existing.id, stock_data)
					records_updated += 1
				else:
					# 创建新记录
					await self.stock_repo.create(stock_data)
					records_added += 1

				# 更新进度
				await self._update_progress(
					task_id=task_id,
					current_item=f"股票: {stock_data['ts_code']}",
					user_id=user_id
				)

			return {
				"records_added": records_added,
				"records_updated": records_updated,
				"records_failed": 0,
				"total_items": len(stock_list),
				"message": "股票列表同步完成"
			}

		except Exception as e:
			logger.error(f"同步股票列表失败: {str(e)}", exc_info=True)
			raise

	async def _sync_daily_quotes (
			self,
			start_date: Optional[date],
			end_date: Optional[date],
			ts_codes: Optional[List[str]],
			task_id: str,
			user_id: Optional[int] = None
	) -> Dict[str, Any]:
		"""同步日行情数据"""
		try:
			# 设置默认日期范围（最近30天）
			if not end_date:
				end_date = datetime.now().date()
			if not start_date:
				start_date = end_date - timedelta(days=30)

			# 获取要同步的股票列表
			if not ts_codes:
				# 获取所有活跃股票
				stocks = await self.stock_repo.get_active_stocks()
				ts_codes = [stock.ts_code for stock in stocks]

			# 获取数据源
			source = self.source_factory.get_source(DataSource.TUSHARE)

			total_records = 0
			records_added = 0
			records_updated = 0
			records_failed = 0

			# 分批处理股票
			batch_size = SyncConfig.BATCH_SIZE["daily_quotes"]
			for i in range(0, len(ts_codes), batch_size):
				batch_codes = ts_codes[i:i + batch_size]

				# 获取批量行情数据
				batch_quotes = await source.get_daily_quotes(
					ts_codes=batch_codes,
					start_date=start_date,
					end_date=end_date
				)

				# 批量保存到数据库
				for quote_data in batch_quotes:
					try:
						# 检查是否已存在
						existing = await self.quote_repo.get_by_trade_date(
							ts_code=quote_data["ts_code"],
							trade_date=quote_data["trade_date"]
						)

						if existing:
							# 更新现有记录
							await self.quote_repo.update(existing.id, quote_data)
							records_updated += 1
						else:
							# 创建新记录
							await self.quote_repo.create(quote_data)
							records_added += 1

						total_records += 1

					except Exception as e:
						logger.error(f"保存行情数据失败: {str(e)}")
						records_failed += 1

				# 更新进度
				progress = min(100, (i + len(batch_codes)) / len(ts_codes) * 100)
				await self._update_progress(
					task_id=task_id,
					progress=progress,
					current_item=f"已处理 {i + len(batch_codes)} / {len(ts_codes)} 只股票",
					user_id=user_id
				)

				# 小批量提交，避免事务过大
				if i % (batch_size * 5) == 0:
					await self.session.commit()

			await self.session.commit()

			return {
				"records_added": records_added,
				"records_updated": records_updated,
				"records_failed": records_failed,
				"total_items": total_records,
				"date_range": {
					"start": start_date.isoformat(),
					"end": end_date.isoformat()
				},
				"message": "日行情数据同步完成"
			}

		except Exception as e:
			await self.session.rollback()
			logger.error(f"同步日行情数据失败: {str(e)}", exc_info=True)
			raise

	async def _sync_adjusted_quotes (
			self,
			start_date: Optional[date],
			end_date: Optional[date],
			ts_codes: Optional[List[str]],
			task_id: str,
			user_id: Optional[int] = None
	) -> Dict[str, Any]:
		"""同步复权行情数据"""
		# 实现与日行情类似，但包含复权因子
		# 这里简化处理，实际需要调用复权数据接口
		return {
			"records_added": 0,
			"records_updated": 0,
			"records_failed": 0,
			"total_items": 0,
			"message": "复权行情数据同步完成（待实现）"
		}

	async def _sync_financial_data (
			self,
			start_date: Optional[date],
			end_date: Optional[date],
			ts_codes: Optional[List[str]],
			task_id: str,
			user_id: Optional[int] = None
	) -> Dict[str, Any]:
		"""同步财务数据"""
		# 实现财务数据同步逻辑
		return {
			"records_added": 0,
			"records_updated": 0,
			"records_failed": 0,
			"total_items": 0,
			"message": "财务数据同步完成（待实现）"
		}

	async def _sync_index_data (
			self,
			start_date: Optional[date],
			end_date: Optional[date],
			ts_codes: Optional[List[str]],
			task_id: str,
			user_id: Optional[int] = None
	) -> Dict[str, Any]:
		"""同步指数数据"""
		# 实现指数数据同步逻辑
		return {
			"records_added": 0,
			"records_updated": 0,
			"records_failed": 0,
			"total_items": 0,
			"message": "指数数据同步完成（待实现）"
		}

	async def _sync_calendar (
			self,
			start_date: Optional[date],
			end_date: Optional[date],
			ts_codes: Optional[List[str]],
			task_id: str,
			user_id: Optional[int] = None
	) -> Dict[str, Any]:
		"""同步交易日历"""
		try:
			# 获取数据源
			source = self.source_factory.get_source(DataSource.TUSHARE)

			# 获取交易日历数据
			calendar_data = await source.get_trade_calendar(
				start_date=start_date,
				end_date=end_date
			)

			# 保存到数据库
			records_added = 0
			records_updated = 0

			for calendar_item in calendar_data:
				# 检查是否已存在
				existing = await self.calendar_repo.get_by_date(
					exchange=calendar_item["exchange"],
					cal_date=calendar_item["cal_date"]
				)

				if existing:
					await self.calendar_repo.update(existing.id, calendar_item)
					records_updated += 1
				else:
					await self.calendar_repo.create(calendar_item)
					records_added += 1

			await self.session.commit()

			return {
				"records_added": records_added,
				"records_updated": records_updated,
				"records_failed": 0,
				"total_items": len(calendar_data),
				"message": "交易日历同步完成"
			}

		except Exception as e:
			await self.session.rollback()
			logger.error(f"同步交易日历失败: {str(e)}", exc_info=True)
			raise

	def _estimate_total_items (
			self,
			data_type: str,
			ts_codes: Optional[List[str]] = None
	) -> int:
		"""估算同步项目总数"""
		estimates = {
			DataType.STOCK_LIST: 5000,  # 大约5000只股票
			DataType.DAILY_QUOTES: (len(ts_codes) if ts_codes else 5000) * 250,  # 每只股票约250个交易日
			DataType.CALENDAR: 365 * 2,  # 两年约730天
		}

		return estimates.get(data_type, 100)

	async def _update_progress (
			self,
			task_id: str,
			progress: Optional[float] = None,
			current_item: Optional[str] = None,
			user_id: Optional[int] = None
	):
		"""更新同步进度"""
		# 更新缓存中的进度
		progress_key = CacheKey.SYNC_PROGRESS.format(task_id=task_id)

		current_progress = await self.cache.get(progress_key) or {
			"progress": 0,
			"current_task": "",
			"estimated_time_remaining": None
		}

		if progress is not None:
			current_progress["progress"] = progress
		if current_item:
			current_progress["current_task"] = current_item

		await self.cache.set(progress_key, current_progress, ttl=3600)

		# 发布进度事件
		await self._publish_sync_event(
			event_type="progress",
			task_id=task_id,
			progress=progress or current_progress["progress"],
			current_task=current_item or current_progress["current_task"],
			user_id=user_id
		)

	async def _publish_sync_event (
			self,
			event_type: str,
			task_id: str,
			data_type: Optional[str] = None,
			data_types: Optional[List[str]] = None,
			progress: Optional[float] = None,
			current_task: Optional[str] = None,
			result: Optional[Dict] = None,
			error: Optional[str] = None,
			user_id: Optional[int] = None
	):
		"""发布同步事件"""
		if not self.event_engine:
			return

		event_data = {
			"task_id": task_id,
			"user_id": user_id,
			"timestamp": datetime.now()
		}

		if data_type:
			event_data["data_type"] = data_type
		if data_types:
			event_data["data_types"] = data_types
		if progress is not None:
			event_data["progress"] = progress
		if current_task:
			event_data["current_task"] = current_task
		if result:
			event_data["result"] = result
		if error:
			event_data["error"] = error

		# 根据事件类型创建相应事件
		if event_type == "started":
			event = SyncStartedEvent(**event_data)
		elif event_type == "progress":
			event = SyncProgressEvent(**event_data)
		elif event_type == "completed":
			event = SyncCompletedEvent(**event_data)
		elif event_type == "failed":
			event = SyncFailedEvent(**event_data)
		elif event_type == "cancelled":
			event = DataSyncedEvent(
				data_type=data_type or "batch",
				record_count=0,
				status="cancelled",
				**event_data
			)
		else:
			event = DataSyncedEvent(
				data_type=data_type or "unknown",
				record_count=0,
				status=event_type,
				**event_data
			)

		await self.event_engine.put(event)

	async def _clean_cache_after_sync (
			self,
			data_type: str,
			ts_codes: Optional[List[str]] = None
	):
		"""同步后清理相关缓存"""
		cache_keys = []

		if data_type == DataType.STOCK_LIST:
			# 清理股票列表相关缓存
			cache_keys.append(CacheKey.STOCK_LIST.format(hash="*"))

		elif data_type == DataType.DAILY_QUOTES:
			# 清理行情数据相关缓存
			if ts_codes:
				for ts_code in ts_codes:
					cache_keys.append(CacheKey.HISTORICAL_QUOTES.format(
						ts_code=ts_code,
						start="*",
						end="*",
						freq="*",
						adj="*"
					))
			else:
				# 清理所有股票的行情缓存
				cache_keys.append(CacheKey.HISTORICAL_QUOTES.format(
					ts_code="*",
					start="*",
					end="*",
					freq="*",
					adj="*"
				))

		# 批量删除缓存
		for pattern in cache_keys:
			await self.cache.delete_pattern(pattern)

	async def cleanup_old_tasks (self, days: int = 30) -> int:
		"""
		清理旧的同步任务记录

		Args:
			days: 保留天数

		Returns:
			int: 清理的任务数
		"""
		try:
			cutoff_date = datetime.now() - timedelta(days=days)

			# 标记旧任务为已删除
			deleted_count = await self.sync_task_repo.mark_old_tasks_deleted(cutoff_date)

			logger.info(f"清理了 {deleted_count} 条超过 {days} 天的同步任务记录")

			return deleted_count

		except Exception as e:
			logger.error(f"清理旧同步任务失败: {str(e)}", exc_info=True)
			return 0

	async def get_recent_sync_tasks (
			self,
			user_id: Optional[int] = None,
			limit: int = 20
	) -> List[Dict[str, Any]]:
		"""
		获取最近的同步任务

		Args:
			user_id: 用户ID
			limit: 返回数量限制

		Returns:
			List[Dict]: 任务列表
		"""
		tasks = await self.sync_task_repo.get_recent_tasks(user_id, limit)

		result = []
		for task in tasks:
			result.append({
				"task_id": task.task_id,
				"data_type": task.data_type,
				"status": task.status,
				"created_at": task.created_at.isoformat(),
				"completed_at": task.completed_at.isoformat() if task.completed_at else None,
				"records_added": task.records_added,
				"records_updated": task.records_updated,
				"error_message": task.error_message
			})

		return result