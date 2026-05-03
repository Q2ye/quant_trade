#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
报告管理器

负责分析报告的生成、存储、查询和导出。
"""

import json
from datetime import datetime, date, timedelta
from pathlib import Path
from typing import Dict, List, Optional, Any

from sqlalchemy.ext.asyncio import AsyncSession

from modules.analysis.models import AnalysisReport
from modules.analysis.visualizers.chart_generator import ChartGenerator
from modules.analysis.visualizers.report_generator import ReportGenerator
from shared.database.repositories import AccountRepository, StrategyRepository
from shared.database.repositories.analysis.performance.analysis_report_repo import AnalysisReportRepository


class ReportManager:
	"""报告管理器"""

	def __init__ (
			self,
			session: AsyncSession,
			report_storage_path: str = "./reports",
			strategy_repo: Optional[StrategyRepository] = None,
			account_repo: Optional[AccountRepository] = None,
			report_repo: Optional[AnalysisReportRepository] = None
	):
		"""
		初始化报告管理器

		Args:
			session: 数据库会话
			report_storage_path: 报告存储路径
			strategy_repo: 策略Repository
			account_repo: 账户Repository
			report_repo: 分析报告Repository（DB持久化）
		"""
		self.session = session
		self.report_storage_path = Path(report_storage_path)

		# 创建存储目录
		self.report_storage_path.mkdir(parents=True, exist_ok=True)

		# 初始化Repository
		self.strategy_repo = strategy_repo or StrategyRepository(session)
		self.account_repo = account_repo or AccountRepository(session)
		self.report_repo = report_repo or AnalysisReportRepository(session)

		# 初始化生成器
		self.chart_generator = ChartGenerator()
		self.report_generator = ReportGenerator()

		# 内存中的报告缓存
		self.report_cache: Dict[str, AnalysisReport] = {}

	async def generate_report (
			self,
			report_data: Dict[str, Any],
			report_type: str,
			user_id: str,
			title: str,
			description: Optional[str] = None
	) -> AnalysisReport:
		"""
		生成分析报告

		Args:
			report_data: 报告数据
			report_type: 报告类型
			user_id: 用户ID
			title: 报告标题
			description: 报告描述

		Returns:
			AnalysisReport: 分析报告对象
		"""
		try:
			# 生成报告ID
			report_id = f"report_{report_type}_{datetime.now().strftime('%Y%m%d_%H%M%S')}"

			# 创建报告对象
			report = AnalysisReport(
				report_id=report_id,
				user_id=user_id,
				report_type=report_type,
				title=title,
				description=description,
				parameters=report_data.get('parameters', {}),
				status='generating',
				progress=0.0
			)

			# 根据报告类型处理数据
			if report_type == 'performance':
				# 绩效报告
				await self._add_performance_charts(report, report_data)

			elif report_type == 'attribution':
				# 归因报告
				await self._add_attribution_charts(report, report_data)

			elif report_type == 'comparison':
				# 对比报告
				await self._add_comparison_charts(report, report_data)

			elif report_type == 'trade_analysis':
				# 交易分析报告
				await self._add_trade_analysis_charts(report, report_data)

			elif report_type == 'comprehensive':
				# 综合分析报告
				await self._add_comprehensive_charts(report, report_data)

			# 更新报告状态
			report.status = 'completed'
			report.progress = 100.0
			report.completed_at = datetime.now()

			# 缓存报告
			self.report_cache[report_id] = report

			# 保存报告到文件
			await self._save_report_to_file(report)

			return report

		except Exception as e:
			raise ValueError(f"生成报告失败: {str(e)}")

	async def get_report (self, report_id: str) -> Optional[AnalysisReport]:
		"""
		获取报告

		Args:
			report_id: 报告ID

		Returns:
			AnalysisReport: 分析报告对象，如果不存在则返回None
		"""
		# 首先检查缓存
		if report_id in self.report_cache:
			return self.report_cache[report_id]

		# 从文件加载
		report = await self._load_report_from_file(report_id)

		if report:
			# 添加到缓存
			self.report_cache[report_id] = report

		return report

	async def list_reports (
			self,
			user_id: Optional[str] = None,
			report_type: Optional[str] = None,
			start_date: Optional[date] = None,
			end_date: Optional[date] = None,
			limit: int = 100,
			offset: int = 0
	) -> List[AnalysisReport]:
		"""
		列出报告

		Args:
			user_id: 用户ID（可选）
			report_type: 报告类型（可选）
			start_date: 开始日期（可选）
			end_date: 结束日期（可选）
			limit: 返回数量限制
			offset: 偏移量

		Returns:
			报告列表
		"""
		try:
			# 获取报告文件列表
			report_files = list(self.report_storage_path.glob("*.json"))

			reports = []

			for file_path in report_files[offset:offset + limit]:
				try:
					# 从文件加载报告
					with open(file_path, 'r', encoding='utf-8') as f:
						content = f.read()
						report_data = json.loads(content)

					# 创建报告对象
					report = AnalysisReport(
						report_id=report_data['report_id'],
						user_id=report_data['user_id'],
						report_type=report_data['report_type'],
						title=report_data['title'],
						description=report_data.get('description'),
						parameters=report_data.get('parameters', {}),
						status=report_data['status'],
						progress=report_data['progress'],
						created_at=datetime.fromisoformat(report_data['created_at'])
					)

					# 设置完成时间
					if report_data.get('completed_at'):
						report.completed_at = datetime.fromisoformat(report_data['completed_at'])

					# 应用筛选条件
					if user_id and report.user_id != user_id:
						continue

					if report_type and report.report_type != report_type:
						continue

					if start_date and report.created_at.date() < start_date:
						continue

					if end_date and report.created_at.date() > end_date:
						continue

					reports.append(report)

				except Exception as e:
					print(f"加载报告文件失败 {file_path}: {str(e)}")
					continue

			return reports

		except Exception as e:
			raise ValueError(f"列出报告失败: {str(e)}")

	async def export_report (
			self,
			report_id: str,
			export_format: str = 'json'
	) -> bytes:
		"""
		导出报告

		Args:
			report_id: 报告ID
			export_format: 导出格式 ('json', 'csv', 'pdf', 'html')

		Returns:
			报告数据字节
		"""
		try:
			# 获取报告
			report = await self.get_report(report_id)

			if not report:
				raise ValueError(f"报告不存在: {report_id}")

			# 根据格式导出
			if export_format == 'json':
				return await self._export_json(report)
			elif export_format == 'csv':
				return await self._export_csv(report)
			elif export_format == 'pdf':
				return await self._export_pdf(report)
			elif export_format == 'html':
				return await self._export_html(report)
			else:
				raise ValueError(f"不支持的导出格式: {export_format}")

		except Exception as e:
			raise ValueError(f"导出报告失败: {str(e)}")

	async def delete_report (self, report_id: str) -> bool:
		"""
		删除报告

		Args:
			report_id: 报告ID

		Returns:
			是否删除成功
		"""
		try:
			# 从缓存中删除
			if report_id in self.report_cache:
				del self.report_cache[report_id]

			# 删除文件
			report_file = self.report_storage_path / f"{report_id}.json"

			if report_file.exists():
				report_file.unlink()
				return True

			return False

		except Exception as e:
			raise ValueError(f"删除报告失败: {str(e)}")

	async def cleanup_old_reports (
			self,
			days_to_keep: int = 30
	) -> int:
		"""
		清理旧报告

		Args:
			days_to_keep: 保留天数

		Returns:
			清理的报告数量
		"""
		try:
			cutoff_date = datetime.now() - timedelta(days=days_to_keep)

			deleted_count = 0

			# 遍历报告文件
			for file_path in self.report_storage_path.glob("*.json"):
				# 检查文件修改时间
				stat = file_path.stat()
				file_date = datetime.fromtimestamp(stat.st_mtime)

				if file_date < cutoff_date:
					# 删除旧报告
					file_path.unlink()
					deleted_count += 1

			return deleted_count

		except Exception as e:
			raise ValueError(f"清理旧报告失败: {str(e)}")

	async def update_report (
			self,
			report_id: str,
			title: Optional[str] = None,
			description: Optional[str] = None,
			is_public: Optional[bool] = None,
			tags: Optional[List[str]] = None
	) -> bool:
		"""更新报告元数据"""
		try:
			# 更新缓存
			if report_id in self.report_cache:
				report = self.report_cache[report_id]
				if title is not None:
					report.title = title
				if description is not None:
					report.description = description

			# 更新文件
			report_file = self.report_storage_path / f"{report_id}.json"
			if report_file.exists():
				with open(report_file, 'r', encoding='utf-8') as f:
					file_data = json.loads(f.read())

				if title is not None:
					file_data['title'] = title
				if description is not None:
					file_data['description'] = description
				if is_public is not None:
					file_data['is_public'] = is_public
				if tags is not None:
					file_data['tags'] = tags

				with open(report_file, 'w', encoding='utf-8') as f:
					f.write(json.dumps(file_data, ensure_ascii=False, indent=2))

			# 更新数据库
			update_data: Dict[str, Any] = {}
			if title is not None:
				update_data['report_name'] = title
			if is_public is not None:
				update_data['is_public'] = is_public
			if tags is not None:
				update_data['tags'] = tags

			if update_data:
				await self.report_repo.update(report_id, update_data)

			return True

		except Exception as e:
			raise ValueError(f"更新报告失败: {str(e)}")

	async def update_report_status (
			self,
			report_id: str,
			status: str,
			progress: Optional[float] = None,
			error_message: Optional[str] = None,
			file_path: Optional[str] = None,
			file_size: Optional[int] = None
	) -> bool:
		"""更新报告状态"""
		try:
			# 更新缓存
			if report_id in self.report_cache:
				report = self.report_cache[report_id]
				report.status = status
				if progress is not None:
					report.progress = progress
				if error_message is not None:
					report.error_message = error_message
				if status == 'completed':
					report.completed_at = datetime.now()

			# 更新数据库
			return await self.report_repo.update_report_status(
				report_id=report_id,
				status=status,
				file_path=file_path,
				file_size=file_size,
				error_message=error_message
			)

		except Exception as e:
			raise ValueError(f"更新报告状态失败: {str(e)}")

	async def get_report_statistics (
			self,
			days: Optional[int] = None
	) -> Dict[str, Any]:
		"""获取报告统计信息"""
		try:
			return await self.report_repo.get_report_statistics(days=days)
		except Exception as e:
			raise ValueError(f"获取报告统计失败: {str(e)}")

	async def search_reports (
			self,
			keyword: str,
			report_type: Optional[str] = None,
			status: Optional[str] = None,
			is_public: Optional[bool] = None,
			limit: int = 50
	) -> List[Dict[str, Any]]:
		"""搜索报告"""
		try:
			reports = await self.report_repo.search_reports(
				keyword=keyword,
				report_type=report_type,
				status=status,
				is_public=is_public,
				limit=limit
			)
			return [self._report_to_summary(r) for r in reports]
		except Exception as e:
			raise ValueError(f"搜索报告失败: {str(e)}")

	async def get_reports_by_type (
			self,
			report_type: str,
			only_public: bool = False,
			limit: int = 100,
			offset: int = 0
	) -> Dict[str, Any]:
		"""按类型获取报告"""
		try:
			reports, total = await self.report_repo.get_reports_by_type(
				report_type=report_type,
				only_public=only_public,
				limit=limit,
				offset=offset
			)
			return {
				'reports': [self._report_to_summary(r) for r in reports],
				'total': total,
				'limit': limit,
				'offset': offset
			}
		except Exception as e:
			raise ValueError(f"获取类型报告失败: {str(e)}")

	async def get_recent_reports (
			self,
			days: int = 7,
			report_type: Optional[str] = None,
			status: Optional[str] = None,
			limit: int = 50
	) -> List[Dict[str, Any]]:
		"""获取最近报告"""
		try:
			reports = await self.report_repo.get_recent_reports(
				days=days,
				report_type=report_type,
				status=status,
				limit=limit
			)
			return [self._report_to_summary(r) for r in reports]
		except Exception as e:
			raise ValueError(f"获取最近报告失败: {str(e)}")

	async def add_report_tag (
			self,
			report_id: str,
			tag: str
	) -> bool:
		"""为报告添加标签"""
		try:
			# 更新文件中的标签
			report_file = self.report_storage_path / f"{report_id}.json"
			if report_file.exists():
				with open(report_file, 'r', encoding='utf-8') as f:
					file_data = json.loads(f.read())
				current_tags = file_data.get('tags', [])
				if tag not in current_tags:
					current_tags.append(tag)
					file_data['tags'] = current_tags
					with open(report_file, 'w', encoding='utf-8') as f:
						f.write(json.dumps(file_data, ensure_ascii=False, indent=2))

			return await self.report_repo.add_report_tag(report_id, tag)
		except Exception as e:
			raise ValueError(f"添加报告标签失败: {str(e)}")

	async def remove_report_tag (
			self,
			report_id: str,
			tag: str
	) -> bool:
		"""移除报告标签"""
		try:
			# 更新文件中的标签
			report_file = self.report_storage_path / f"{report_id}.json"
			if report_file.exists():
				with open(report_file, 'r', encoding='utf-8') as f:
					file_data = json.loads(f.read())
				current_tags = file_data.get('tags', [])
				if tag in current_tags:
					current_tags.remove(tag)
					file_data['tags'] = current_tags
					with open(report_file, 'w', encoding='utf-8') as f:
						f.write(json.dumps(file_data, ensure_ascii=False, indent=2))

			return await self.report_repo.remove_report_tag(report_id, tag)
		except Exception as e:
			raise ValueError(f"移除报告标签失败: {str(e)}")

	async def get_report_summary (
			self,
			report_id: str
	) -> Optional[Dict[str, Any]]:
		"""获取报告摘要（不含图表大数据）"""
		try:
			# 先检查缓存
			if report_id in self.report_cache:
				report = self.report_cache[report_id]
				return {
					'report_id': report.report_id,
					'user_id': report.user_id,
					'report_type': report.report_type,
					'title': report.title,
					'description': report.description,
					'status': report.status,
					'progress': report.progress,
					'created_at': report.created_at.isoformat(),
					'completed_at': report.completed_at.isoformat() if report.completed_at else None,
					'chart_count': len(report.charts) if report.charts else 0
				}

			# 从文件加载摘要
			report_file = self.report_storage_path / f"{report_id}.json"
			if not report_file.exists():
				return None

			with open(report_file, 'r', encoding='utf-8') as f:
				file_data = json.loads(f.read())

			return {
				'report_id': file_data.get('report_id'),
				'user_id': file_data.get('user_id'),
				'report_type': file_data.get('report_type'),
				'title': file_data.get('title'),
				'description': file_data.get('description'),
				'status': file_data.get('status'),
				'progress': file_data.get('progress'),
				'created_at': file_data.get('created_at'),
				'completed_at': file_data.get('completed_at'),
				'chart_count': len(file_data.get('charts', []))
			}

		except Exception as e:
			raise ValueError(f"获取报告摘要失败: {str(e)}")

	async def regenerate_report (
			self,
			report_id: str
	) -> AnalysisReport:
		"""使用已有参数重新生成报告"""
		try:
			existing = await self.get_report(report_id)
			if not existing:
				raise ValueError(f"报告不存在: {report_id}")

			# 还原参数
			report_data = {
				'parameters': existing.parameters,
				'performance_metrics': existing.performance_metrics.to_dict() if existing.performance_metrics else {},
			}

			return await self.generate_report(
				report_data=report_data,
				report_type=existing.report_type,
				user_id=existing.user_id,
				title=existing.title,
				description=existing.description
			)

		except Exception as e:
			raise ValueError(f"重新生成报告失败: {str(e)}")

	async def duplicate_report (
			self,
			report_id: str,
			new_title: Optional[str] = None
	) -> AnalysisReport:
		"""克隆报告"""
		try:
			existing = await self.get_report(report_id)
			if not existing:
				raise ValueError(f"报告不存在: {report_id}")

			report_data = existing.to_dict()
			report_data['parameters'] = existing.parameters

			new_title = new_title or f"{existing.title} (副本)"

			return await self.generate_report(
				report_data=report_data,
				report_type=existing.report_type,
				user_id=existing.user_id,
				title=new_title,
				description=existing.description
			)

		except Exception as e:
			raise ValueError(f"克隆报告失败: {str(e)}")

	async def batch_delete_reports (
			self,
			report_ids: List[str]
	) -> Dict[str, Any]:
		"""批量删除报告"""
		try:
			success_count = 0
			failed_ids: List[str] = []

			for report_id in report_ids:
				try:
					await self.delete_report(report_id)
					success_count += 1
				except (ValueError, IOError):
					failed_ids.append(report_id)

			return {
				'total': len(report_ids),
				'success': success_count,
				'failed': len(failed_ids),
				'failed_ids': failed_ids
			}

		except Exception as e:
			raise ValueError(f"批量删除报告失败: {str(e)}")

	@staticmethod
	async def get_available_report_types () -> List[Dict[str, Any]]:
		"""获取可用的报告类型"""
		return [
			{
				'type': 'performance',
				'name': '绩效报告',
				'description': '分析策略或账户的绩效指标，含净值曲线、回撤、夏普比率等',
				'formats': ['json', 'csv', 'pdf', 'html'],
				'icon': 'chart-line'
			},
			{
				'type': 'attribution',
				'name': '归因报告',
				'description': '收益归因分析，含Brinson归因和因子归因',
				'formats': ['json', 'pdf', 'html'],
				'icon': 'pie-chart'
			},
			{
				'type': 'comparison',
				'name': '对比报告',
				'description': '多策略/基准对比分析，含相关性热力图',
				'formats': ['json', 'pdf', 'html'],
				'icon': 'bar-chart'
			},
			{
				'type': 'trade_analysis',
				'name': '交易分析报告',
				'description': '交易行为分析，含盈亏分布和时间分布',
				'formats': ['json', 'csv', 'pdf', 'html'],
				'icon': 'activity'
			},
			{
				'type': 'comprehensive',
				'name': '综合分析报告',
				'description': '全面的多维度分析，整合绩效、归因、交易',
				'formats': ['json', 'pdf', 'html'],
				'icon': 'file-text'
			}
		]

	@staticmethod
	async def get_available_export_formats () -> List[Dict[str, Any]]:
		"""获取可用的导出格式"""
		return [
			{
				'format': 'json',
				'name': 'JSON',
				'description': '结构化数据格式，适合程序处理',
				'extension': '.json',
				'mime_type': 'application/json'
			},
			{
				'format': 'csv',
				'name': 'CSV',
				'description': '表格数据格式，适合Excel打开',
				'extension': '.csv',
				'mime_type': 'text/csv'
			},
			{
				'format': 'pdf',
				'name': 'PDF',
				'description': '便携式文档，适合打印和分享',
				'extension': '.pdf',
				'mime_type': 'application/pdf'
			},
			{
				'format': 'html',
				'name': 'HTML',
				'description': '网页格式，适合浏览器查看',
				'extension': '.html',
				'mime_type': 'text/html'
			}
		]

	@staticmethod
	def _report_to_summary (db_report) -> Dict[str, Any]:
		"""将ORM报告对象转换为摘要字典"""
		return {
			'id': db_report.id,
			'report_type': db_report.report_type,
			'report_name': db_report.report_name,
			'status': db_report.status,
			'format': db_report.format,
			'generated_by': db_report.generated_by,
			'is_public': db_report.is_public,
			'tags': db_report.tags or [],
			'file_size': db_report.file_size,
			'created_at': db_report.created_at.isoformat() if db_report.created_at else None,
			'generated_at': db_report.generated_at.isoformat() if hasattr(db_report,
			                                                              'generated_at') and db_report.generated_at else None
		}

	async def save_report_to_db (self, report: AnalysisReport) -> Optional[str]:
		"""将报告持久化到数据库"""
		try:
			report_config = {
				'report_type': report.report_type,
				'title': report.title,
				'parameters': report.parameters,
			}
			report_data = report.to_dict()

			db_report = await self.report_repo.create_report(
				report_type=report.report_type,
				report_name=report.title,
				report_config=report_config,
				report_data=report_data,
				generated_by=report.user_id,
				report_format='json',
				is_public=False
			)
			return db_report.id
		except Exception as e:
			raise ValueError(f"保存报告到数据库失败: {str(e)}")

	async def load_report_from_db (self, report_id: str) -> Optional[Dict[str, Any]]:
		"""从数据库加载报告"""
		try:
			db_report = await self.report_repo.get(report_id)
			if not db_report:
				return None
			return {
				'id': db_report.id,
				'report_type': db_report.report_type,
				'report_name': db_report.report_name,
				'status': db_report.status,
				'format': db_report.format,
				'report_data': db_report.report_data,
				'report_config': db_report.report_config,
				'generated_by': db_report.generated_by,
				'is_public': db_report.is_public,
				'tags': db_report.tags or [],
				'file_path': db_report.file_path,
				'file_size': db_report.file_size,
				'created_at': db_report.created_at.isoformat() if db_report.created_at else None,
				'generated_at': db_report.generated_at.isoformat() if hasattr(db_report,
				                                                              'generated_at') and db_report.generated_at else None
			}
		except Exception as e:
			raise ValueError(f"从数据库加载报告失败: {str(e)}")

	async def get_user_reports (
			self,
			user_id: str,
			report_type: Optional[str] = None,
			limit: int = 100,
			offset: int = 0
	) -> Dict[str, Any]:
		"""获取用户相关报告（含公开报告）"""
		try:
			reports, total = await self.report_repo.get_user_reports(
				user_id=user_id,
				report_type=report_type,
				limit=limit,
				offset=offset
			)
			return {
				'reports': [self._report_to_summary(r) for r in reports],
				'total': total,
				'limit': limit,
				'offset': offset
			}
		except Exception as e:
			raise ValueError(f"获取用户报告失败: {str(e)}")

	async def get_reports_by_tags (
			self,
			tags: List[str],
			match_all: bool = False,
			limit: int = 50
	) -> List[Dict[str, Any]]:
		"""根据标签获取报告"""
		try:
			reports = await self.report_repo.get_reports_by_tags(
				tags=tags,
				match_all=match_all,
				limit=limit
			)
			return [self._report_to_summary(r) for r in reports]
		except Exception as e:
			raise ValueError(f"根据标签获取报告失败: {str(e)}")

	async def get_report_trend (
			self,
			days: int = 30,
			report_type: Optional[str] = None
	) -> List[Dict[str, Any]]:
		"""获取报告生成趋势"""
		try:
			return await self.report_repo.get_report_trend(
				days=days,
				report_type=report_type
			)
		except Exception as e:
			raise ValueError(f"获取报告趋势失败: {str(e)}")

	@staticmethod
	def validate_report_parameters (
			report_type: str,
			parameters: Dict[str, Any]
	) -> Dict[str, Any]:
		"""验证报告参数，返回验证结果"""
		errors = []
		warnings = []

		valid_types = ['performance', 'attribution', 'comparison', 'trade_analysis', 'comprehensive']
		if report_type not in valid_types:
			errors.append(f"不支持的报告类型: {report_type}，有效类型: {', '.join(valid_types)}")

		if report_type in ('performance', 'comprehensive'):
			entity_type = parameters.get('entity_type')
			if entity_type and entity_type not in ('strategy', 'account', 'portfolio'):
				errors.append(f"不支持的实体类型: {entity_type}")
			if not parameters.get('entity_id') and not parameters.get('strategy_id'):
				errors.append("缺少实体ID（entity_id 或 strategy_id）")

		if report_type == 'attribution':
			if not parameters.get('portfolio_id'):
				errors.append("归因分析缺少 portfolio_id")
			model = parameters.get('model', 'brinson')
			if model == 'brinson' and not parameters.get('benchmark'):
				warnings.append("Brinson归因建议提供基准")

		if report_type == 'comparison':
			if not parameters.get('strategy_ids') and not parameters.get('category'):
				errors.append("对比分析需要 strategy_ids 或 category")

		if report_type == 'trade_analysis':
			if not parameters.get('strategy_id') and not parameters.get('account_id'):
				errors.append("交易分析需要 strategy_id 或 account_id")

		start_date = parameters.get('start_date')
		end_date = parameters.get('end_date')
		if start_date and end_date:
			from datetime import date
			if isinstance(start_date, str):
				start_date = date.fromisoformat(start_date)
			if isinstance(end_date, str):
				end_date = date.fromisoformat(end_date)
			if start_date > end_date:
				errors.append("开始日期不能晚于结束日期")

		return {
			'valid': len(errors) == 0,
			'errors': errors,
			'warnings': warnings
		}

	async def archive_reports (
			self,
			report_ids: Optional[List[str]] = None,
			days_older_than: Optional[int] = 90,
			archive_path: Optional[str] = None
	) -> Dict[str, Any]:
		"""归档报告到压缩文件"""
		import zipfile

		try:
			archive_path = Path(archive_path or str(self.report_storage_path / 'archives'))
			archive_path.mkdir(parents=True, exist_ok=True)

			# 确定要归档的报告
			if report_ids:
				files_to_archive = [
					self.report_storage_path / f"{rid}.json"
					for rid in report_ids
				]
			else:
				cutoff = datetime.now() - timedelta(days=days_older_than)
				files_to_archive = []
				for f in self.report_storage_path.glob("*.json"):
					if f.name.startswith('archive_') or f.name.startswith('archives'):
						continue
					stat = f.stat()
					if datetime.fromtimestamp(stat.st_mtime) < cutoff:
						files_to_archive.append(f)

			if not files_to_archive:
				return {'archived': 0, 'archive_file': None, 'message': '没有需要归档的报告'}

			# 创建压缩文件
			archive_name = f"archive_{datetime.now().strftime('%Y%m%d_%H%M%S')}.zip"
			archive_file = archive_path / archive_name

			archived_count = 0
			with zipfile.ZipFile(str(archive_file), 'w', zipfile.ZIP_DEFLATED) as zf:
				for file_path in files_to_archive:
					if file_path.exists():
						zf.write(str(file_path), file_path.name)
						archived_count += 1

			return {
				'archived': archived_count,
				'archive_file': str(archive_file),
				'archive_size': archive_file.stat().st_size if archive_file.exists() else 0
			}

		except Exception as e:
			raise ValueError(f"归档报告失败: {str(e)}")

	async def compare_reports (
			self,
			report_id_1: str,
			report_id_2: str
	) -> Dict[str, Any]:
		"""对比两个报告的摘要"""
		try:
			summary_1 = await self.get_report_summary(report_id_1)
			summary_2 = await self.get_report_summary(report_id_2)

			if not summary_1 or not summary_2:
				raise ValueError("一个或多个报告不存在")

			return {
				'report_1': summary_1,
				'report_2': summary_2,
				'comparison': {
					'same_type': summary_1.get('report_type') == summary_2.get('report_type'),
					'same_status': summary_1.get('status') == summary_2.get('status'),
					'chart_count_diff': (
							summary_1.get('chart_count', 0) - summary_2.get('chart_count', 0)
					)
				}
			}

		except Exception as e:
			raise ValueError(f"对比报告失败: {str(e)}")

	async def preview_report (
			self,
			report_id: str,
			output_format: str = 'html'
	) -> Optional[str]:
		"""预览报告内容（返回字符串）"""
		try:
			report = await self.get_report(report_id)
			if not report:
				return None

			if output_format == 'html':
				content = await self.report_generator.generate_html_report(report)
				return content
			elif output_format == 'json':
				return json.dumps(report.to_dict(), ensure_ascii=False, indent=2)
			else:
				raise ValueError(f"不支持的预览格式: {output_format}")

		except Exception as e:
			raise ValueError(f"预览报告失败: {str(e)}")

	async def get_report_data_section (
			self,
			report_id: str,
			section: str
	) -> Optional[Dict[str, Any]]:
		"""提取报告的特定数据部分"""
		try:
			report = await self.get_report(report_id)
			if not report:
				return None

			section_map = {
				'performance_metrics': report.performance_metrics,
				'risk_metrics': report.risk_metrics,
				'attribution_analysis': report.attribution_analysis,
				'comparison_analysis': report.comparison_analysis,
				'trade_analysis': report.trade_analysis,
				'charts': report.charts,
				'parameters': report.parameters,
			}

			value = section_map.get(section)
			if value is None:
				return None

			if hasattr(value, 'to_dict'):
				return value.to_dict()
			return value if isinstance(value, dict) else {'data': value}

		except Exception as e:
			raise ValueError(f"获取报告数据部分失败: {str(e)}")

	async def _add_performance_charts (
			self,
			report: AnalysisReport,
			report_data: Dict[str, Any]
	):
		"""
		为绩效报告添加图表

		Args:
			report: 报告对象
			report_data: 报告数据
		"""
		try:
			charts = []

			# 净值曲线图
			if 'performance_metrics' in report_data:
				metrics = report_data['performance_metrics']

				if 'equity_curve' in metrics:
					equity_data = metrics['equity_curve']

					if equity_data:
						# 生成净值曲线图
						chart_data = {
							'dates': [item['date'] for item in equity_data],
							'equity': [item['equity'] for item in equity_data]
						}

						chart = self.chart_generator.generate_equity_curve_chart(chart_data)
						charts.append(chart)

			# 回撤曲线图
			if 'performance_metrics' in report_data:
				metrics = report_data['performance_metrics']

				if 'drawdown_curve' in metrics:
					drawdown_data = metrics['drawdown_curve']

					if drawdown_data:
						# 生成回撤曲线图
						chart_data = {
							'dates': [item['date'] for item in drawdown_data],
							'drawdown': [item['drawdown'] for item in drawdown_data]
						}

						chart = self.chart_generator.generate_drawdown_chart(chart_data)
						charts.append(chart)

			# 月度收益热力图
			if 'performance_metrics' in report_data:
				metrics = report_data['performance_metrics']

				if 'monthly_returns' in metrics:
					monthly_returns = metrics['monthly_returns']

					if monthly_returns:
						import pandas as pd
						returns_df = pd.DataFrame(monthly_returns)
						chart = self.chart_generator.generate_monthly_returns_heatmap(returns_df)
						charts.append(chart)

			# 绩效指标雷达图
			if 'performance_metrics' in report_data:
				metrics = report_data['performance_metrics']

				# 生成雷达图
				chart_data = {
					'total_return': float(metrics.get('total_return', 0)),
					'sharpe_ratio': float(metrics.get('sharpe_ratio', 0)),
					'max_drawdown': float(metrics.get('max_drawdown', 0)),
					'win_rate': float(metrics.get('win_rate', 0)),
					'profit_factor': float(metrics.get('profit_factor', 0))
				}

				chart = self.chart_generator.generate_performance_radar_chart(chart_data)
				charts.append(chart)

			# 添加到报告
			report.charts = charts

		except Exception as e:
			print(f"添加绩效图表失败: {str(e)}")

	async def _add_attribution_charts (
			self,
			report: AnalysisReport,
			report_data: Dict[str, Any]
	):
		"""
		为归因报告添加图表

		Args:
			report: 报告对象
			report_data: 报告数据
		"""
		try:
			charts = []

			# 归因贡献堆叠图
			if 'attribution_analysis' in report_data:
				attribution = report_data['attribution_analysis']

				if 'brinson_attribution' in attribution:
					brinson_data = attribution['brinson_attribution']

					# 生成归因贡献堆叠图
					chart_data = {
						'allocation_effect': float(brinson_data.get('allocation_effect', 0)),
						'selection_effect': float(brinson_data.get('selection_effect', 0)),
						'interaction_effect': float(brinson_data.get('interaction_effect', 0))
					}

					chart = self.chart_generator.generate_attribution_stacked_chart(chart_data)
					charts.append(chart)

			# 行业归因条形图
			if 'attribution_analysis' in report_data:
				attribution = report_data['attribution_analysis']

				if 'sector_attribution' in attribution:
					sector_data = attribution['sector_attribution']

					if 'attributions' in sector_data:
						# 生成行业归因条形图
						chart_data = {
							'sectors': list(sector_data['attributions'].keys()),
							'contributions': list(sector_data['attributions'].values())
						}

						chart = self.chart_generator.generate_sector_attribution_chart(chart_data)
						charts.append(chart)

			# 添加到报告
			report.charts = charts

		except Exception as e:
			print(f"添加归因图表失败: {str(e)}")

	async def _add_comparison_charts (
			self,
			report: AnalysisReport,
			report_data: Dict[str, Any]
	):
		"""
		为对比报告添加图表

		Args:
			report: 报告对象
			report_data: 报告数据
		"""
		try:
			charts = []

			# 策略对比条形图
			if 'comparison_analysis' in report_data:
				comparison = report_data['comparison_analysis']

				if 'performance_comparison' in comparison:
					perf_comparison = comparison['performance_comparison']

					# 生成总收益对比条形图
					chart_data = {
						'strategies': list(perf_comparison.keys()),
						'returns': [
							perf['returns']['total_return']
							for perf in perf_comparison.values()
						]
					}

					chart = self.chart_generator.generate_comparison_bar_chart(chart_data)
					charts.append(chart)

			# 相关性热力图
			if 'comparison_analysis' in report_data:
				comparison = report_data['comparison_analysis']

				if 'correlations' in comparison:
					correlations = comparison['correlations']

					if correlations:
						# 生成相关性热力图
						chart_data = {
							'correlation_matrix': correlations
						}

						chart = self.chart_generator.generate_correlation_heatmap(chart_data)
						charts.append(chart)

			# 添加到报告
			report.charts = charts

		except Exception as e:
			print(f"添加对比图表失败: {str(e)}")

	async def _add_trade_analysis_charts (
			self,
			report: AnalysisReport,
			report_data: Dict[str, Any]
	):
		"""
		为交易分析报告添加图表

		Args:
			report: 报告对象
			report_data: 报告数据
		"""
		try:
			charts = []

			# 交易盈亏分布图
			if 'trade_analysis' in report_data:
				trade_analysis = report_data['trade_analysis']

				# 生成交易盈亏分布图
				chart_data = {
					'winning_trades': trade_analysis.get('winning_trades', 0),
					'losing_trades': trade_analysis.get('losing_trades', 0),
					'breakeven_trades': trade_analysis.get('breakeven_trades', 0)
				}

				chart = self.chart_generator.generate_trade_distribution_chart(chart_data)
				charts.append(chart)

			# 交易时间分布图
			if 'trade_analysis' in report_data:
				trade_analysis = report_data['trade_analysis']

				if 'time_analysis' in trade_analysis:
					time_analysis = trade_analysis['time_analysis']

					if 'day_of_week' in time_analysis:
						# 生成交易日分布图
						chart_data = {
							'days': list(time_analysis['day_of_week'].keys()),
							'counts': list(time_analysis['day_of_week'].values())
						}

						chart = self.chart_generator.generate_trading_day_distribution_chart(chart_data)
						charts.append(chart)

			# 添加到报告
			report.charts = charts

		except Exception as e:
			print(f"添加交易分析图表失败: {str(e)}")

	async def _add_comprehensive_charts (
			self,
			report: AnalysisReport,
			report_data: Dict[str, Any]
	):
		"""
		为综合分析报告添加图表

		Args:
			report: 报告对象
			report_data: 报告数据
		"""
		try:
			charts = []

			# 根据报告数据添加各种图表
			if 'performance_metrics' in report_data:
				await self._add_performance_charts(report, report_data)
				charts.extend(report.charts)

			if 'attribution_analysis' in report_data:
				await self._add_attribution_charts(report, report_data)
				charts.extend(report.charts[len(charts):])

			if 'comparison_analysis' in report_data:
				await self._add_comparison_charts(report, report_data)
				charts.extend(report.charts[len(charts):])

			if 'trade_analysis' in report_data:
				await self._add_trade_analysis_charts(report, report_data)
				charts.extend(report.charts[len(charts):])

			# 更新报告图表
			report.charts = charts

		except Exception as e:
			print(f"添加综合分析图表失败: {str(e)}")

	async def _save_report_to_file (self, report: AnalysisReport):
		"""
		保存报告到文件

		Args:
			report: 报告对象
		"""
		try:
			# 构建文件路径
			report_file = self.report_storage_path / f"{report.report_id}.json"

			# 转换为字典
			report_dict = report.to_dict()

			# 保存到文件
			with open(report_file, 'w', encoding='utf-8') as f:
				f.write(json.dumps(report_dict, ensure_ascii=False, indent=2))

			# 添加到导出文件列表
			report.export_files['json'] = str(report_file)

		except Exception as e:
			raise ValueError(f"保存报告到文件失败: {str(e)}")

	async def _load_report_from_file (self, report_id: str) -> Optional[AnalysisReport]:
		"""
		从文件加载报告

		Args:
			report_id: 报告ID

		Returns:
			AnalysisReport: 分析报告对象，如果文件不存在则返回None
		"""
		try:
			# 构建文件路径
			report_file = self.report_storage_path / f"{report_id}.json"

			if not report_file.exists():
				return None

			# 从文件加载
			with open(report_file, 'r', encoding='utf-8') as f:
				content = f.read()
				report_data = json.loads(content)

			# 重新创建报告对象
			report = AnalysisReport(
				report_id=report_data['report_id'],
				user_id=report_data['user_id'],
				report_type=report_data['report_type'],
				title=report_data['title'],
				description=report_data.get('description'),
				parameters=report_data.get('parameters', {}),
				status=report_data['status'],
				progress=report_data['progress'],
				created_at=datetime.fromisoformat(report_data['created_at']),
				updated_at=datetime.fromisoformat(report_data['updated_at']),
				charts=report_data.get('charts', [])
			)

			# 设置完成时间
			if report_data.get('completed_at'):
				report.completed_at = datetime.fromisoformat(report_data['completed_at'])

			# 设置导出文件
			if 'export_files' in report_data:
				report.export_files = report_data['export_files']

			return report

		except Exception as e:
			print(f"从文件加载报告失败 {report_id}: {str(e)}")
			return None

	@staticmethod
	async def _export_json (report: AnalysisReport) -> bytes:
		"""
		导出为JSON格式

		Args:
			report: 报告对象

		Returns:
			JSON字节数据
		"""
		try:
			report_dict = report.to_dict()
			return json.dumps(report_dict, ensure_ascii=False, indent=2).encode('utf-8')

		except Exception as e:
			raise ValueError(f"导出JSON失败: {str(e)}")

	@staticmethod
	async def _export_csv (report: AnalysisReport) -> bytes:
		"""
		导出为CSV格式

		Args:
			report: 报告对象

		Returns:
			CSV字节数据
		"""
		try:
			csv_data = [
				["报告ID", report.report_id],
				["报告类型", report.report_type],
				["标题", report.title],
				["创建时间", report.created_at.isoformat()]
			]

			if report.report_type == 'performance' and report.performance_metrics:
				metrics = report.performance_metrics
				csv_data.extend([
					[],
					["绩效指标"],
					["总收益", f"{float(metrics.total_return):.2%}"],
					["年化收益", f"{float(metrics.annual_return):.2%}"],
					["夏普比率", f"{float(metrics.sharpe_ratio):.2f}"],
					["最大回撤", f"{float(metrics.max_drawdown):.2%}"]
				])

			# 转换为CSV字符串
			output = ""
			for row in csv_data:
				output += ",".join(str(cell) for cell in row) + "\n"

			return output.encode('utf-8')

		except Exception as e:
			raise ValueError(f"导出CSV失败: {str(e)}")

	async def _export_pdf (self, report: AnalysisReport) -> bytes:
		"""
		导出为PDF格式

		Args:
			report: 报告对象

		Returns:
			PDF字节数据
		"""
		try:
			# 使用报告生成器创建PDF
			pdf_content = await self.report_generator.generate_pdf_report(report)
			return pdf_content

		except Exception as e:
			raise ValueError(f"导出PDF失败: {str(e)}")

	async def _export_html (self, report: AnalysisReport) -> bytes:
		"""
		导出为HTML格式

		Args:
			report: 报告对象

		Returns:
			HTML字节数据
		"""
		try:
			# 使用报告生成器创建HTML
			html_content = await self.report_generator.generate_html_report(report)
			return html_content.encode('utf-8')

		except Exception as e:
			raise ValueError(f"导出HTML失败: {str(e)}")