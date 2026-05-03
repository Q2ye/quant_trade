# -*- coding: utf-8 -*-
"""
FileAttachmentRepository - 文件附件数据访问层

基于BaseRepository实现，支持文件附件的CRUD操作和管理
位置：quant_server/shared/database/repositories/operation/file/file_attachment_repo.py

设计原则：
1. 继承BaseRepository，使用普通表模型（非超表）
2. 提供文件附件的完整生命周期管理
3. 支持按引用类型、文件类型等多种方式查询
"""

import os
from datetime import datetime, timezone, timedelta
from typing import List, Dict, Any, Optional, Callable

from sqlalchemy import select, func, and_, or_, desc
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from shared.database.models.business_models import FileAttachment
from shared.database.repositories.base.repository_base import BaseRepository, RepositoryError
from shared.database.repositories.types import (
	PaginationParams,
	PaginationResult
)


class FileAttachmentRepository(BaseRepository[FileAttachment]):
	"""文件附件Repository - 继承BaseRepository"""

	def __init__ (self, session: AsyncSession):
		"""初始化文件附件Repository"""
		super().__init__(session, FileAttachment)

	# ==================== 业务特定方法 ====================

	async def get_by_file_id (self, file_id: str) -> Optional[FileAttachment]:
		"""
		根据文件UUID获取文件附件

		Args:
			file_id: 文件UUID

		Returns:
			文件附件对象或None

		Raises:
			RepositoryError: 查询失败时抛出
		"""
		try:
			query = select(self.model).where(self.model.file_id == file_id)

			result = await self.session.execute(query)
			return result.scalar_one_or_none()

		except Exception as e:
			raise RepositoryError(f"根据文件ID获取附件失败: {str(e)}")

	async def get_attachments_by_reference (
			self,
			reference_type: str,
			reference_id: str,
			with_uploader: bool = False
	) -> List[FileAttachment]:
		"""
		根据引用类型和引用ID获取附件列表

		Args:
			reference_type: 引用类型（如'report', 'strategy', 'trade'等）
			reference_id: 引用ID
			with_uploader: 是否预加载上传者信息

		Returns:
			文件附件列表
		"""
		try:
			query = select(self.model).where(
				and_(
					self.model.reference_type == reference_type,
					self.model.reference_id == reference_id
				)
			)

			if with_uploader:
				query = query.options(selectinload(FileAttachment.uploader))

			# 默认按上传时间倒序排列
			query = query.order_by(desc(self.model.upload_date))

			result = await self.session.execute(query)
			return result.scalars().all()

		except Exception as e:
			raise RepositoryError(f"获取引用附件失败: {str(e)}")

	async def get_user_attachments (
			self,
			user_id: str,
			file_type: str = None,
			pagination: PaginationParams = None
	) -> PaginationResult[FileAttachment]:
		"""
		获取用户上传的文件附件

		Args:
			user_id: 用户ID
			file_type: 文件类型筛选（可选）
			pagination: 分页参数

		Returns:
			分页结果
		"""
		try:
			# 构建查询条件
			conditions = [self.model.uploaded_by == user_id]

			if file_type:
				conditions.append(self.model.file_type == file_type)

			query = select(self.model).where(and_(*conditions))

			# 默认按上传时间倒序
			query = query.order_by(desc(self.model.upload_date))

			# 获取总数
			count_query = select(func.count()).select_from(self.model).where(and_(*conditions))
			total_result = await self.session.execute(count_query)
			total = total_result.scalar() or 0

			# 应用分页
			if pagination:
				query = query.offset(pagination.get_offset()).limit(pagination.get_limit())

			# 获取数据
			result = await self.session.execute(query)
			items = result.scalars().all()

			if pagination:
				return PaginationResult.create(
					items=items,
					total=total,
					page=pagination.page,
					page_size=pagination.page_size
				)
			else:
				return PaginationResult.create(
					items=items,
					total=total,
					page=1,
					page_size=total
				)

		except Exception as e:
			raise RepositoryError(f"获取用户附件失败: {str(e)}")

	async def search_attachments (
			self,
			keyword: str,
			file_type: str = None,
			reference_type: str = None,
			start_date: datetime = None,
			end_date: datetime = None,
			pagination: PaginationParams = None
	) -> PaginationResult[FileAttachment]:
		"""
		搜索文件附件（按文件名、描述等）

		Args:
			keyword: 搜索关键词
			file_type: 文件类型筛选
			reference_type: 引用类型筛选
			start_date: 开始日期
			end_date: 结束日期
			pagination: 分页参数

		Returns:
			分页搜索结果
		"""
		try:
			# 构建查询条件
			conditions = []

			# 关键词搜索
			if keyword:
				keyword_condition = or_(
					self.model.file_name.like(f"%{keyword}%"),
					self.model.description.like(f"%{keyword}%")
				)
				conditions.append(keyword_condition)

			# 文件类型筛选
			if file_type:
				conditions.append(self.model.file_type == file_type)

			# 引用类型筛选
			if reference_type:
				conditions.append(self.model.reference_type == reference_type)

			# 时间范围筛选
			if start_date:
				conditions.append(self.model.upload_date >= start_date)
			if end_date:
				conditions.append(self.model.upload_date <= end_date)

			query = select(self.model)
			if conditions:
				query = query.where(and_(*conditions))

			# 默认按上传时间倒序
			query = query.order_by(desc(self.model.upload_date))

			# 获取总数
			count_query = select(func.count()).select_from(self.model)
			if conditions:
				count_query = count_query.where(and_(*conditions))

			total_result = await self.session.execute(count_query)
			total = total_result.scalar() or 0

			# 应用分页
			if pagination:
				query = query.offset(pagination.get_offset()).limit(pagination.get_limit())

			# 获取搜索结果
			result = await self.session.execute(query)
			items = result.scalars().all()

			if pagination:
				return PaginationResult.create(
					items=items,
					total=total,
					page=pagination.page,
					page_size=pagination.page_size
				)
			else:
				return PaginationResult.create(
					items=items,
					total=total,
					page=1,
					page_size=total
				)

		except Exception as e:
			raise RepositoryError(f"搜索文件附件失败: {str(e)}")

	async def get_attachments_by_type (
			self,
			file_type: str,
			pagination: PaginationParams = None
	) -> PaginationResult[FileAttachment]:
		"""
		根据文件类型获取附件

		Args:
			file_type: 文件类型（report/data/strategy/log等）
			pagination: 分页参数

		Returns:
			分页结果
		"""
		try:
			query = select(self.model).where(self.model.file_type == file_type)

			# 默认按上传时间倒序
			query = query.order_by(desc(self.model.upload_date))

			# 获取总数
			count_query = select(func.count()).select_from(self.model).where(
				self.model.file_type == file_type
			)
			total_result = await self.session.execute(count_query)
			total = total_result.scalar() or 0

			# 应用分页
			if pagination:
				query = query.offset(pagination.get_offset()).limit(pagination.get_limit())

			# 获取数据
			result = await self.session.execute(query)
			items = result.scalars().all()

			if pagination:
				return PaginationResult.create(
					items=items,
					total=total,
					page=pagination.page,
					page_size=pagination.page_size
				)
			else:
				return PaginationResult.create(
					items=items,
					total=total,
					page=1,
					page_size=total
				)

		except Exception as e:
			raise RepositoryError(f"获取文件类型附件失败: {str(e)}")

	async def get_attachment_statistics (
			self,
			start_date: datetime = None,
			end_date: datetime = None
	) -> Dict[str, Any]:
		"""
		获取文件附件统计信息

		Args:
			start_date: 开始日期
			end_date: 结束日期

		Returns:
			统计信息字典
		"""
		try:
			# 构建条件
			conditions = []
			if start_date:
				conditions.append(self.model.upload_date >= start_date)
			if end_date:
				conditions.append(self.model.upload_date <= end_date)

			where_clause = and_(*conditions) if conditions else True

			# 1. 总数统计
			total_query = select(func.count()).select_from(self.model).where(where_clause)
			total_result = await self.session.execute(total_query)
			total_count = total_result.scalar() or 0

			# 2. 按文件类型统计
			type_stats_query = (
				select(self.model.file_type, func.count().label('count'),
				       func.sum(self.model.file_size).label('total_size'))
				.where(where_clause)
				.group_by(self.model.file_type)
			)
			type_stats_result = await self.session.execute(type_stats_query)
			type_stats = [
				{
					"file_type": row.file_type,
					"count": row.count,
					"total_size": row.total_size or 0
				}
				for row in type_stats_result.all()
			]

			# 3. 按引用类型统计
			ref_type_stats_query = (
				select(self.model.reference_type, func.count().label('count'))
				.where(where_clause)
				.group_by(self.model.reference_type)
			)
			ref_type_stats_result = await self.session.execute(ref_type_stats_query)
			ref_type_stats = [
				{
					"reference_type": row.reference_type,
					"count": row.count
				}
				for row in ref_type_stats_result.all()
			]

			# 4. 总文件大小
			total_size_query = select(func.sum(self.model.file_size)).where(where_clause)
			total_size_result = await self.session.execute(total_size_query)
			total_size = total_size_result.scalar() or 0

			# 5. 最近上传的文件
			recent_query = (
				select(self.model)
				.where(where_clause)
				.order_by(desc(self.model.upload_date))
				.limit(10)
			)
			recent_result = await self.session.execute(recent_query)
			recent_files = recent_result.scalars().all()

			return {
				"total_count": total_count,
				"total_size_bytes": total_size,
				"total_size_mb": total_size / (1024 * 1024) if total_size > 0 else 0,
				"type_statistics": type_stats,
				"reference_statistics": ref_type_stats,
				"recent_files": [
					{
						"file_id": file.file_id,
						"file_name": file.file_name,
						"file_type": file.file_type,
						"upload_date": file.upload_date.isoformat() if file.upload_date else None,
						"file_size_mb": file.file_size / (1024 * 1024) if file.file_size else 0
					}
					for file in recent_files
				],
				"statistics_date_range": {
					"start_date": start_date.isoformat() if start_date else None,
					"end_date": end_date.isoformat() if end_date else None
				}
			}

		except Exception as e:
			raise RepositoryError(f"获取附件统计失败: {str(e)}")

	async def create_file_attachment (
			self,
			file_data: Dict[str, Any],
			user_id: str
	) -> FileAttachment:
		"""
		创建文件附件记录

		Args:
			file_data: 文件数据
			user_id: 上传用户ID

		Returns:
			创建的文件附件对象

		Raises:
			RepositoryError: 创建失败时抛出
		"""
		try:
			# 验证必要字段
			required_fields = ['file_id', 'file_name', 'file_type', 'storage_path',
			                   'reference_type', 'reference_id']
			for field in required_fields:
				if field not in file_data:
					raise RepositoryError(f"缺少必要字段: {field}")

			# 设置上传者
			file_data['uploaded_by'] = user_id

			# 设置文件大小（如果未提供）
			if 'file_size' not in file_data:
				# 尝试从存储路径获取文件大小
				storage_path = file_data['storage_path']
				if os.path.exists(storage_path):
					file_data['file_size'] = os.path.getsize(storage_path)
				else:
					file_data['file_size'] = 0

			# 设置MIME类型（如果未提供）
			if 'mime_type' not in file_data:
				file_data['mime_type'] = self._guess_mime_type(file_data['file_name'])

			# 创建记录
			return await self.create(file_data)

		except Exception as e:
			raise RepositoryError(f"创建文件附件失败: {str(e)}")

	@staticmethod
	def _guess_mime_type (filename: str) -> str:
		"""
		根据文件名猜测MIME类型

		Args:
			filename: 文件名

		Returns:
			MIME类型字符串
		"""
		import mimetypes

		# 初始化MIME类型数据库
		mimetypes.init()

		# 根据扩展名猜测MIME类型
		mime_type, _ = mimetypes.guess_type(filename)

		if mime_type:
			return mime_type

		# 常见文件类型的默认值
		extension = os.path.splitext(filename)[1].lower()

		mime_map = {
			'.csv': 'text/csv',
			'.json': 'application/json',
			'.txt': 'text/plain',
			'.pdf': 'application/pdf',
			'.xlsx': 'application/vnd.openxmlformats-officedocument.spreadsheetml.sheet',
			'.xls': 'application/vnd.ms-excel',
			'.docx': 'application/vnd.openxmlformats-officedocument.wordprocessingml.document',
			'.doc': 'application/msword',
			'.png': 'image/png',
			'.jpg': 'image/jpeg',
			'.jpeg': 'image/jpeg',
			'.gif': 'image/gif',
			'.zip': 'application/zip',
			'.tar': 'application/x-tar',
			'.gz': 'application/gzip',
		}

		return mime_map.get(extension, 'application/octet-stream')

	async def update_file_metadata (
			self,
			file_id: str,
			metadata_updates: Dict[str, Any]
	) -> Optional[FileAttachment]:
		"""
		更新文件元数据

		Args:
			file_id: 文件UUID
			metadata_updates: 元数据更新

		Returns:
			更新后的文件附件对象或None
		"""
		try:
			# 获取文件记录
			file_attachment = await self.get_by_file_id(file_id)
			if not file_attachment:
				raise RepositoryError(f"文件不存在: {file_id}")

			# 过滤允许更新的字段
			allowed_fields = ['file_name', 'description', 'metadata']
			update_data = {}

			for field in allowed_fields:
				if field in metadata_updates:
					update_data[field] = metadata_updates[field]

			if not update_data:
				raise RepositoryError("没有有效的更新字段")

			# 更新记录
			updated = await self.update(file_attachment.id, update_data)
			return updated

		except Exception as e:
			if isinstance(e, RepositoryError):
				raise e
			else:
				raise RepositoryError(f"更新文件元数据失败: {str(e)}")

	async def delete_file_attachment (
			self,
			file_id: str,
			delete_physical_file: bool = False
	) -> bool:
		"""
		删除文件附件记录（可选删除物理文件）

		Args:
			file_id: 文件UUID
			delete_physical_file: 是否同时删除物理文件

		Returns:
			是否成功

		Raises:
			RepositoryError: 删除失败时抛出
		"""
		try:
			# 获取文件记录
			file_attachment = await self.get_by_file_id(file_id)
			if not file_attachment:
				raise RepositoryError(f"文件不存在: {file_id}")

			# 开始事务
			await self.begin_transaction()

			# 如果需要，删除物理文件
			if delete_physical_file and file_attachment.storage_path:
				try:
					if os.path.exists(file_attachment.storage_path):
						os.remove(file_attachment.storage_path)
				except Exception as e:
					await self.rollback()
					raise RepositoryError(f"删除物理文件失败: {str(e)}")

			# 删除数据库记录
			success = await self.delete(file_attachment.id, soft=False)

			# 提交事务
			await self.commit()

			return success

		except Exception as e:
			await self.rollback()
			if isinstance(e, RepositoryError):
				raise e
			else:
				raise RepositoryError(f"删除文件附件失败: {str(e)}")

	async def delete_orphaned_attachments (
			self,
			reference_check_query: Optional[Callable] = None
	) -> Dict[str, Any]:
		"""
		删除孤儿文件附件（引用已删除但文件还在）

		Args:
			reference_check_query: 自定义的引用检查函数，用于验证引用是否存在
			函数签名：async def check_reference_exists(reference_type: str, reference_id: str) -> bool

		Returns:
			删除统计信息
		"""
		try:
			# 1. 获取所有文件附件记录
			all_files_query = select(self.model).where(
				and_(
					self.model.reference_type != 'temp',  # 排除临时文件
					self.model.reference_type.isnot(None),  # 排除无引用类型的文件
					self.model.reference_id.isnot(None)  # 排除无引用ID的文件
				)
			)
			
			result = await self.session.execute(all_files_query)
			all_files = result.scalars().all()

			# 2. 检测孤儿文件
			orphaned_files = []
			
			for file_attachment in all_files:
				if reference_check_query:
					# 使用自定义的引用检查函数
					reference_exists = await reference_check_query(
						file_attachment.reference_type,
						file_attachment.reference_id
					)
					if not reference_exists:
						orphaned_files.append(file_attachment)
				else:
					# 默认逻辑：基于时间判断孤儿文件
					# 超过90天且无引用的文件视为孤儿文件
					ninety_days_ago = datetime.now(timezone.utc) - timedelta(days=90)
					if file_attachment.upload_date < ninety_days_ago:
						orphaned_files.append(file_attachment)

			# 3. 处理临时文件（超过30天的临时文件）
			thirty_days_ago = datetime.now(timezone.utc) - timedelta(days=30)
			temp_files_query = select(self.model).where(
				and_(
					self.model.reference_type == 'temp',
					self.model.upload_date < thirty_days_ago
				)
			)
			
			temp_result = await self.session.execute(temp_files_query)
			temp_files = temp_result.scalars().all()
			
			# 合并孤儿文件和临时文件
			files_to_delete = orphaned_files + temp_files

			# 4. 删除孤儿文件和临时文件
			deleted_count = 0
			failed_count = 0
			
			for file_attachment in files_to_delete:
				try:
					# 删除物理文件
					if file_attachment.storage_path and os.path.exists(file_attachment.storage_path):
						os.remove(file_attachment.storage_path)

					# 删除数据库记录
					await self.delete(file_attachment.id, soft=False)
					deleted_count += 1

				except Exception as e:
					# 记录异常信息
					print(f"删除文件附件失败 {file_attachment.id}: {str(e)}")
					failed_count += 1

			# 5. 返回统计信息
			return {
				"deleted_count": deleted_count,
				"failed_count": failed_count,
				"total_orphaned_files": len(orphaned_files),
				"total_temp_files": len(temp_files),
				"total_processed": len(files_to_delete),
				"orphaned_files": [f.id for f in orphaned_files],
				"temp_files": [f.id for f in temp_files]
			}

		except Exception as e:
			raise RepositoryError(f"删除孤儿附件失败: {str(e)}")

	async def get_file_download_info (
			self,
			file_id: str
	) -> Dict[str, Any]:
		"""
		获取文件下载信息

		Args:
			file_id: 文件UUID

		Returns:
			文件下载信息字典

		Raises:
			RepositoryError: 文件不存在或无法访问时抛出
		"""
		try:
			file_attachment = await self.get_by_file_id(file_id)
			if not file_attachment:
				raise RepositoryError(f"文件不存在: {file_id}")

			# 检查物理文件是否存在
			file_exists = False
			file_size = 0

			if file_attachment.storage_path and os.path.exists(file_attachment.storage_path):
				file_exists = True
				file_size = os.path.getsize(file_attachment.storage_path)

			return {
				"file_id": file_attachment.file_id,
				"file_name": file_attachment.file_name,
				"file_type": file_attachment.file_type,
				"mime_type": file_attachment.mime_type,
				"file_size_bytes": file_attachment.file_size,
				"file_size_mb": file_attachment.file_size / (1024 * 1024) if file_attachment.file_size else 0,
				"storage_path": file_attachment.storage_path,
				"physical_file_exists": file_exists,
				"physical_file_size": file_size,
				"upload_date": file_attachment.upload_date.isoformat() if file_attachment.upload_date else None,
				"uploaded_by": file_attachment.uploaded_by,
				"description": file_attachment.description,
				"reference_info": {
					"type": file_attachment.reference_type,
					"id": file_attachment.reference_id
				},
				"metadata": file_attachment.metadata or {}
			}

		except Exception as e:
			if isinstance(e, RepositoryError):
				raise e
			else:
				raise RepositoryError(f"获取文件下载信息失败: {str(e)}")

	async def increment_download_count (
			self,
			file_id: str
	) -> bool:
		"""
		增加文件下载次数（在metadata中记录）

		Args:
			file_id: 文件UUID

		Returns:
			是否成功
		"""
		try:
			file_attachment = await self.get_by_file_id(file_id)
			if not file_attachment:
				return False

			# 获取当前metadata
			metadata = file_attachment.metadata or {}

			# 更新下载次数
			current_count = metadata.get('download_count', 0)
			metadata['download_count'] = current_count + 1
			metadata['last_downloaded'] = datetime.now(timezone.utc).isoformat()

			# 更新记录
			await self.update(file_attachment.id, {"metadata": metadata})
			return True

		except Exception as e:
			raise RepositoryError(f"更新下载次数失败: {str(e)}")