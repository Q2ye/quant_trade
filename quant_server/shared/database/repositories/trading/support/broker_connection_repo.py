# """
# 券商连接表Repository
#
# 位置：quant_server/shared/database/repositories/trading/support/broker_connection_repository.py
#
# 对应模型：BrokerConnection (虽然模型文件中未明确定义，但根据架构设计推断存在)
# 功能：提供券商连接配置的CRUD操作，包括连接状态管理、连接测试等。
# """
#
# from typing import List, Optional, Dict, Any
# from datetime import datetime
# from sqlalchemy import select, update, and_, or_, func, Integer
# from sqlalchemy.ext.asyncio import AsyncSession
#
# from quant_server.shared.database.repositories.base import BaseRepository
# from quant_server.shared.database.models.business_models import BrokerConnection
# from quant_server.shared.database.repositories.types import (
# 	PaginationParams,
# 	PaginationResult,
# 	FilterCondition,
# 	SortCondition
# )
#
#
# class BrokerConnectionRepository(BaseRepository[BrokerConnection]):
# 	"""
# 	券商连接表Repository
#
# 	继承自BaseRepository，提供对BrokerConnection表的标准CRUD操作。
# 	专门用于管理券商连接配置和状态。
# 	"""
#
# 	def __init__ (self, session: AsyncSession):
# 		"""
# 		初始化BrokerConnectionRepository
#
# 		Args:
# 			session: 异步数据库会话
# 		"""
# 		super().__init__(session, BrokerConnection)
#
# 	async def get_active_connections (self, user_id: Optional[int] = None) -> List[BrokerConnection]:
# 		"""
# 		获取活跃的券商连接
#
# 		Args:
# 			user_id: 用户ID（可选，如果提供则获取指定用户的连接）
#
# 		Returns:
# 			活跃的券商连接列表
# 		"""
# 		try:
# 			query = select(self.model).where(
# 				self.model.is_active == True
# 			)
#
# 			if user_id:
# 				query = query.where(self.model.user_id == user_id)
#
# 			query = query.order_by(
# 				self.model.broker_name,
# 				self.model.created_at.desc()
# 			)
#
# 			result = await self.session.execute(query)
# 			return result.scalars().all()
# 		except Exception as e:
# 			raise RepositoryError(f"获取活跃连接失败: {str(e)}")
#
# 	async def get_connection_by_broker (self, broker_name: str,
# 	                                    account_id: Optional[str] = None) -> Optional[BrokerConnection]:
# 		"""
# 		根据券商名称和账户ID获取连接配置
#
# 		Args:
# 			broker_name: 券商名称
# 			account_id: 账户ID（可选）
#
# 		Returns:
# 			券商连接配置，如果不存在则返回None
# 		"""
# 		try:
# 			query = select(self.model).where(
# 				self.model.broker_name == broker_name
# 			)
#
# 			if account_id:
# 				query = query.where(self.model.account_id == account_id)
#
# 			query = query.where(self.model.is_active == True)
#
# 			result = await self.session.execute(query)
# 			return result.scalar_one_or_none()
# 		except Exception as e:
# 			raise RepositoryError(f"获取券商连接失败: {str(e)}")
#
# 	async def update_connection_status (self, connection_id: int,
# 	                                    status: str,
# 	                                    last_connected: Optional[datetime] = None,
# 	                                    error_message: Optional[str] = None) -> bool:
# 		"""
# 		更新连接状态
#
# 		Args:
# 			connection_id: 连接ID
# 			status: 新状态（connected/disconnected/error）
# 			last_connected: 最后连接时间（可选）
# 			error_message: 错误信息（可选）
#
# 		Returns:
# 			是否更新成功
# 		"""
# 		try:
# 			update_data = {
# 				'status': status,
# 				'updated_at': datetime.now()
# 			}
#
# 			if last_connected:
# 				update_data['last_connected'] = last_connected
#
# 			if error_message:
# 				update_data['error_message'] = error_message
# 				update_data['last_error_at'] = datetime.now()
#
# 			stmt = (
# 				update(self.model)
# 				.where(self.model.id == connection_id)
# 				.values(**update_data)
# 			)
#
# 			await self.session.execute(stmt)
# 			return True
# 		except Exception as e:
# 			raise RepositoryError(f"更新连接状态失败: {str(e)}")
#
# 	async def test_connection (self, connection_id: int) -> Dict[str, Any]:
# 		"""
# 		测试连接（更新状态并返回测试结果）
#
# 		Args:
# 			connection_id: 连接ID
#
# 		Returns:
# 			测试结果字典
# 		"""
# 		try:
# 			connection = await self.get(connection_id)
# 			if not connection:
# 				raise RepositoryError(f"连接ID {connection_id} 不存在")
#
# 			# 这里模拟连接测试，实际应用中应调用券商的测试接口
# 			test_result = {
# 				'connection_id': connection_id,
# 				'broker_name': connection.broker_name,
# 				'test_time': datetime.now(),
# 				'success': True,  # 模拟成功
# 				'latency_ms': 150,  # 模拟延迟
# 				'message': '连接测试成功'
# 			}
#
# 			# 更新连接状态
# 			if test_result['success']:
# 				await self.update_connection_status(
# 					connection_id,
# 					'connected',
# 					last_connected=test_result['test_time']
# 				)
# 			else:
# 				await self.update_connection_status(
# 					connection_id,
# 					'error',
# 					error_message=test_result['message']
# 				)
#
# 			return test_result
# 		except Exception as e:
# 			await self.update_connection_status(
# 				connection_id,
# 				'error',
# 				error_message=str(e)
# 			)
# 			raise RepositoryError(f"连接测试失败: {str(e)}")
#
# 	async def get_connection_stats (self) -> Dict[str, Any]:
# 		"""
# 		获取连接统计信息
#
# 		Returns:
# 			连接统计字典
# 		"""
# 		try:
# 			# 统计总数
# 			total_query = select(func.count()).select_from(self.model)
# 			total_result = await self.session.execute(total_query)
# 			total = total_result.scalar() or 0
#
# 			# 统计活跃数
# 			active_query = select(func.count()).select_from(self.model).where(
# 				self.model.is_active == True
# 			)
# 			active_result = await self.session.execute(active_query)
# 			active = active_result.scalar() or 0
#
# 			# 按状态统计
# 			status_query = select(
# 				self.model.status,
# 				func.count().label('count')
# 			).group_by(self.model.status)
#
# 			status_result = await self.session.execute(status_query)
# 			status_stats = {row.status: row.count for row in status_result}
#
# 			# 按券商统计
# 			broker_query = select(
# 				self.model.broker_name,
# 				func.count().label('count'),
# 				func.sum(self.model.is_active.cast(Integer)).label('active_count')
# 			).group_by(self.model.broker_name)
#
# 			broker_result = await self.session.execute(broker_query)
# 			broker_stats = [
# 				{
# 					'broker_name': row.broker_name,
# 					'total_count': row.count,
# 					'active_count': row.active_count
# 				}
# 				for row in broker_result
# 			]
#
# 			return {
# 				'total_connections': total,
# 				'active_connections': active,
# 				'inactive_connections': total - active,
# 				'status_distribution': status_stats,
# 				'broker_distribution': broker_stats,
# 				'last_updated': datetime.now()
# 			}
# 		except Exception as e:
# 			raise RepositoryError(f"获取连接统计失败: {str(e)}")
#
# 	async def create_connection (self, broker_name: str, account_id: str,
# 	                             connection_config: Dict[str, Any],
# 	                             user_id: Optional[int] = None,
# 	                             description: Optional[str] = None) -> BrokerConnection:
# 		"""
# 		创建券商连接配置
#
# 		Args:
# 			broker_name: 券商名称
# 			account_id: 账户ID
# 			connection_config: 连接配置字典
# 			user_id: 用户ID（可选）
# 			description: 描述（可选）
#
# 		Returns:
# 			创建的BrokerConnection记录
# 		"""
# 		connection_data = {
# 			'broker_name': broker_name,
# 			'account_id': account_id,
# 			'connection_config': connection_config,
# 			'is_active': True,
# 			'status': 'disconnected'
# 		}
#
# 		if user_id:
# 			connection_data['user_id'] = user_id
#
# 		if description:
# 			connection_data['description'] = description
#
# 		return await self.create(connection_data)
#
# 	async def deactivate_connection (self, connection_id: int) -> bool:
# 		"""
# 		停用连接（软删除）
#
# 		Args:
# 			connection_id: 连接ID
#
# 		Returns:
# 			是否成功
# 		"""
# 		try:
# 			update_data = {
# 				'is_active': False,
# 				'status': 'disconnected',
# 				'updated_at': datetime.now()
# 			}
#
# 			stmt = (
# 				update(self.model)
# 				.where(self.model.id == connection_id)
# 				.values(**update_data)
# 			)
#
# 			await self.session.execute(stmt)
# 			return True
# 		except Exception as e:
# 			raise RepositoryError(f"停用连接失败: {str(e)}")
#
# 	async def get_connections_for_sync (self, max_age_minutes: int = 30) -> List[BrokerConnection]:
# 		"""
# 		获取需要同步的连接（长时间未更新的活跃连接）
#
# 		Args:
# 			max_age_minutes: 最大年龄（分钟），超过此时间的连接需要同步
#
# 		Returns:
# 			需要同步的连接列表
# 		"""
# 		try:
# 			from datetime import timedelta
# 			cutoff_time = datetime.now() - timedelta(minutes=max_age_minutes)
#
# 			query = select(self.model).where(
# 				and_(
# 					self.model.is_active == True,
# 					self.model.last_sync_at < cutoff_time
# 				)
# 			).order_by(self.model.last_sync_at.asc())
#
# 			result = await self.session.execute(query)
# 			return result.scalars().all()
# 		except Exception as e:
# 			raise RepositoryError(f"获取待同步连接失败: {str(e)}")
#
#
# # 异常定义
# class RepositoryError(Exception):
# 	"""Repository异常基类"""
#
# 	def __init__ (self, message: str, code: str = "BROKER_CONNECTION_REPOSITORY_ERROR"):
# 		self.message = message
# 		self.code = code
# 		super().__init__(self.message)