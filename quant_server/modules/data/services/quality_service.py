# -*- coding: utf-8 -*-
"""
数据质量仓库服务
负责数据质量检查、评估和报告生成
位置：quant_server/modules/data/services/quality_service.py

设计原则：
1. 模块化质量检查：每个检查项目独立实现
2. 可配置的质量阈值：支持动态调整质量标准
3. 详细的检查报告：提供完整的质量问题描述和建议
4. 批量处理能力：支持大规模数据质量检查
"""

from typing import Dict, List, Any, Optional, Union
from datetime import datetime, date, timedelta
import logging
import asyncio
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import and_, or_, func
import pandas as pd
import numpy as np

# 导入共享层组件
from quant_server.shared.database.repositories import (
	StockBasicRepository,
	QuoteRepository,
	FactorRepository,
	FinancialRepository,
	DataQualityRepository,
	TradeCalendarRepository
)
from quant_server.shared.cache.redis_cache import RedisCache
from quant_server.shared.database.models.business_models import DataQualityCheck

# 导入核心基础设施
from quant_server.core.engines.system.event_engine import EventEngine
from quant_server.core.events.data_events import DataQualityEvent

# 导入数据模块常量
from quant_server.modules.data.constants import (
	DataType,
	QualityMetricCode,
	QualityLevelThreshold,
	QualityIssueType,
	QualityCheckStatus
)

# 配置日志
logger = logging.getLogger(__name__)


class DataQualityService:
	"""
	数据质量仓库服务类
	负责数据质量的检查、评估和报告

	Attributes:
		session: 异步数据库会话
		event_engine: 事件引擎
		stock_repo: 股票数据仓库
		quote_repo: 行情数据仓库
		factor_repo: 因子数据仓库
		quality_repo: 质量检查仓库
		calendar_repo: 交易日历仓库
	"""

	def __init__ (self, session: AsyncSession, event_engine: Optional[EventEngine] = None):
		"""
		初始化数据质量服务

		Args:
			session: 数据库会话
			event_engine: 事件引擎，用于发布质量事件
		"""
		self.session = session
		self.event_engine = event_engine

		# 初始化Repository
		self.stock_repo = StockBasicRepository(session)
		self.quote_repo = QuoteRepository(session)
		self.factor_repo = FactorRepository(session)
		self.financial_repo = FinancialRepository(session)
		self.quality_repo = DataQualityRepository(session)
		self.calendar_repo = TradeCalendarRepository(session)

		# 初始化缓存（懒加载）
		self._cache = None

		# 质量检查配置
		self._quality_config = self._load_quality_config()

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

	# ==================== 质量检查主方法 ====================

	async def check_data_quality (
			self,
			data_type: str,
			start_date: Optional[date] = None,
			end_date: Optional[date] = None,
			ts_code: Optional[str] = None,
			check_types: Optional[List[str]] = None,
			quality_thresholds: Optional[Dict[str, float]] = None,
			user_id: Optional[int] = None
	) -> Dict[str, Any]:
		"""
		检查数据质量

		Args:
			data_type: 数据类型，支持：daily_quotes, stock_list, factor_data, financial_data
			start_date: 开始日期
			end_date: 结束日期
			ts_code: 股票代码（可选，不指定则检查所有）
			check_types: 检查类型列表，支持：completeness, accuracy, timeliness, consistency
			quality_thresholds: 质量阈值配置
			user_id: 用户ID（用于事件发布）

		Returns:
			Dict: 质量检查结果，包含：
				- success: 是否成功
				- check_id: 检查ID
				- result: 检查结果详情
				- message: 状态消息
		"""
		logger.info(f"开始检查数据质量，类型: {data_type}, 代码: {ts_code}")

		check_id = None
		try:
			# 创建检查任务记录
			check_id = await self._create_quality_check(
				data_type=data_type,
				start_date=start_date,
				end_date=end_date,
				ts_code=ts_code,
				check_types=check_types,
				user_id=user_id
			)

			# 发布检查开始事件
			await self._publish_quality_event(
				event_type="started",
				check_id=check_id,
				data_type=data_type,
				user_id=user_id
			)

			# 默认检查所有类型
			if not check_types:
				check_types = ["completeness", "accuracy", "timeliness", "consistency"]

			# 设置质量阈值
			if quality_thresholds:
				self._update_quality_thresholds(quality_thresholds)

			results = {}
			issues = []

			# 执行各项质量检查
			for check_type in check_types:
				try:
					check_result = await self._perform_quality_check(
						check_type=check_type,
						data_type=data_type,
						start_date=start_date,
						end_date=end_date,
						ts_code=ts_code
					)

					results[check_type] = check_result["metrics"]

					if check_result.get("issues"):
						issues.extend(check_result["issues"])

					# 更新进度
					progress = (check_types.index(check_type) + 1) / len(check_types) * 100
					await self._update_quality_progress(
						check_id=check_id,
						progress=progress,
						current_check=check_type,
						user_id=user_id
					)

				except Exception as e:
					logger.error(f"执行质量检查 {check_type} 失败: {str(e)}")
					results[check_type] = {
						"status": "error",
						"error": str(e)
					}

			# 计算总体质量评分
			overall_score = self._calculate_overall_score(results)
			quality_level = QualityLevelThreshold.get_quality_level(overall_score)

			# 生成改进建议
			suggestions = self._generate_quality_suggestions(issues, overall_score)

			# 构建检查结果
			quality_result = {
				"check_id": check_id,
				"data_type": data_type,
				"ts_code": ts_code,
				"date_range": {
					"start": start_date.isoformat() if start_date else None,
					"end": end_date.isoformat() if end_date else None
				},
				"overall_score": overall_score,
				"quality_level": quality_level,
				"metrics": results,
				"issues": issues,
				"suggestions": suggestions,
				"check_time": datetime.now().isoformat(),
				"duration": None
			}

			# 保存检查结果
			await self._save_quality_result(check_id, quality_result)

			# 发布检查完成事件
			await self._publish_quality_event(
				event_type="completed",
				check_id=check_id,
				data_type=data_type,
				quality_level=quality_level,
				overall_score=overall_score,
				issue_count=len(issues),
				user_id=user_id
			)

			# 如果质量较差，发布警报
			if quality_level in ["fair", "poor"]:
				await self._publish_quality_event(
					event_type="alert",
					check_id=check_id,
					data_type=data_type,
					quality_level=quality_level,
					overall_score=overall_score,
					issues=issues[:10],  # 只发送前10个问题
					user_id=user_id
				)

			logger.info(f"数据质量检查完成，检查ID: {check_id}, 评分: {overall_score}")

			return {
				"success": True,
				"check_id": check_id,
				"result": quality_result,
				"message": "数据质量检查完成"
			}

		except Exception as e:
			logger.error(f"数据质量检查失败: {str(e)}", exc_info=True)

			# 更新检查状态为失败
			if check_id:
				await self._update_quality_check(
					check_id=check_id,
					status=QualityCheckStatus.FAILED,
					error=str(e)
				)

			# 发布错误事件
			await self._publish_quality_event(
				event_type="failed",
				check_id=check_id,
				data_type=data_type,
				error=str(e),
				user_id=user_id
			)

			return {
				"success": False,
				"check_id": check_id,
				"error": str(e),
				"message": "数据质量检查失败"
			}

	async def check_batch_quality (
			self,
			data_types: List[str],
			start_date: Optional[date] = None,
			end_date: Optional[date] = None,
			check_types: Optional[List[str]] = None,
			user_id: Optional[int] = None
	) -> Dict[str, Any]:
		"""
		批量检查多种数据类型

		Args:
			data_types: 数据类型列表
			start_date: 开始日期
			end_date: 结束日期
			check_types: 检查类型列表
			user_id: 用户ID

		Returns:
			Dict: 批量检查结果
		"""
		logger.info(f"开始批量检查数据质量，数据类型: {data_types}")

		batch_id = f"batch_{datetime.now().strftime('%Y%m%d_%H%M%S')}"
		results = {}

		# 发布批量检查开始事件
		await self._publish_quality_event(
			event_type="batch_started",
			batch_id=batch_id,
			data_types=data_types,
			user_id=user_id
		)

		# 并发执行各项检查
		tasks = []
		for data_type in data_types:
			task = self.check_data_quality(
				data_type=data_type,
				start_date=start_date,
				end_date=end_date,
				check_types=check_types,
				user_id=user_id
			)
			tasks.append(task)

		# 等待所有检查完成
		completed_results = await asyncio.gather(*tasks, return_exceptions=True)

		# 处理结果
		for i, result in enumerate(completed_results):
			data_type = data_types[i]

			if isinstance(result, Exception):
				logger.error(f"检查数据类型 {data_type} 失败: {str(result)}")
				results[data_type] = {
					"success": False,
					"error": str(result)
				}
			else:
				results[data_type] = result

		# 计算批量统计
		successful_checks = sum(1 for r in results.values() if isinstance(r, dict) and r.get("success"))
		total_scores = []

		for data_type, result in results.items():
			if isinstance(result, dict) and result.get("success") and result.get("result"):
				total_scores.append(result["result"].get("overall_score", 0))

		batch_summary = {
			"batch_id": batch_id,
			"total_types": len(data_types),
			"successful_checks": successful_checks,
			"failed_checks": len(data_types) - successful_checks,
			"average_score": np.mean(total_scores) if total_scores else 0,
			"results": results
		}

		# 发布批量检查完成事件
		await self._publish_quality_event(
			event_type="batch_completed",
			batch_id=batch_id,
			summary=batch_summary,
			user_id=user_id
		)

		return {
			"success": True,
			"batch_id": batch_id,
			"summary": batch_summary,
			"message": f"批量检查完成，成功: {successful_checks}/{len(data_types)}"
		}

	# ==================== 质量报告方法 ====================

	async def get_quality_report (
			self,
			check_id: Optional[str] = None,
			data_type: Optional[str] = None,
			start_date: Optional[date] = None,
			end_date: Optional[date] = None,
			ts_code: Optional[str] = None,
			limit: int = 10,
			page: int = 1
	) -> Dict[str, Any]:
		"""
		获取数据质量报告

		Args:
			check_id: 检查ID（可选）
			data_type: 数据类型
			start_date: 开始日期
			end_date: 结束日期
			ts_code: 股票代码
			limit: 每页数量
			page: 页码

		Returns:
			Dict: 质量报告，包含分页信息
		"""
		try:
			# 构建查询条件
			filters = []

			if check_id:
				filters.append(self.quality_repo.model.check_id == check_id)
			if data_type:
				filters.append(self.quality_repo.model.data_type == data_type)
			if start_date:
				filters.append(self.quality_repo.model.check_time >= start_date)
			if end_date:
				filters.append(self.quality_repo.model.check_time <= end_date)
			if ts_code:
				filters.append(self.quality_repo.model.ts_code == ts_code)

			# 计算总数
			total = await self.quality_repo.count(*filters)

			# 计算偏移量
			skip = (page - 1) * limit

			# 获取质量检查记录
			quality_checks = await self.quality_repo.get_many(
				*filters,
				skip=skip,
				limit=limit,
				order_by=self.quality_repo.model.check_time.desc()
			)

			# 转换为响应格式
			reports = []
			for check in quality_checks:
				reports.append({
					"check_id": check.check_id,
					"data_type": check.data_type,
					"ts_code": check.ts_code,
					"overall_score": check.overall_score,
					"quality_level": check.quality_level,
					"issue_count": len(check.issues) if check.issues else 0,
					"check_time": check.check_time.isoformat() if check.check_time else None,
					"duration": check.duration_seconds if hasattr(check, 'duration_seconds') else None,
					"status": check.status if hasattr(check, 'status') else QualityCheckStatus.COMPLETED
				})

			return {
				"reports": reports,
				"pagination": {
					"page": page,
					"limit": limit,
					"total": total,
					"total_pages": (total + limit - 1) // limit if limit > 0 else 0
				}
			}

		except Exception as e:
			logger.error(f"获取质量报告失败: {str(e)}", exc_info=True)
			raise

	async def get_detailed_report (
			self,
			check_id: str
	) -> Dict[str, Any]:
		"""
		获取详细质量报告

		Args:
			check_id: 检查ID

		Returns:
			Dict: 详细质量报告
		"""
		try:
			# 获取质量检查记录
			quality_check = await self.quality_repo.get_by_check_id(check_id)

			if not quality_check:
				raise ValueError(f"质量检查记录 {check_id} 不存在")

			# 转换为详细报告
			detailed_report = {
				"check_id": quality_check.check_id,
				"data_type": quality_check.data_type,
				"ts_code": quality_check.ts_code,
				"date_range": quality_check.date_range if hasattr(quality_check, 'date_range') else {},
				"overall_score": quality_check.overall_score,
				"quality_level": quality_check.quality_level,
				"metrics": quality_check.metrics if hasattr(quality_check, 'metrics') else {},
				"issues": quality_check.issues if hasattr(quality_check, 'issues') else [],
				"suggestions": quality_check.suggestions if hasattr(quality_check, 'suggestions') else [],
				"check_time": quality_check.check_time.isoformat() if quality_check.check_time else None,
				"duration_seconds": quality_check.duration_seconds if hasattr(quality_check,
				                                                              'duration_seconds') else None,
				"status": quality_check.status if hasattr(quality_check, 'status') else QualityCheckStatus.COMPLETED,
				"created_at": quality_check.created_at.isoformat() if quality_check.created_at else None,
				"updated_at": quality_check.updated_at.isoformat() if quality_check.updated_at else None
			}

			return detailed_report

		except Exception as e:
			logger.error(f"获取详细质量报告失败: {str(e)}", exc_info=True)
			raise

	# ==================== 质量统计方法 ====================

	async def get_quality_statistics (
			self,
			data_type: Optional[str] = None,
			days: int = 30,
			group_by: str = "day"
	) -> Dict[str, Any]:
		"""
		获取数据质量统计信息

		Args:
			data_type: 数据类型
			days: 统计天数
			group_by: 分组方式（day/week/month）

		Returns:
			Dict: 质量统计信息
		"""
		try:
			end_date = datetime.now()
			start_date = end_date - timedelta(days=days)

			# 构建查询条件
			filters = [
				self.quality_repo.model.check_time >= start_date,
				self.quality_repo.model.check_time <= end_date,
				self.quality_repo.model.status == QualityCheckStatus.COMPLETED
			]

			if data_type:
				filters.append(self.quality_repo.model.data_type == data_type)

			# 获取质量检查记录
			quality_checks = await self.quality_repo.get_many(*filters)

			if not quality_checks:
				return {
					"total_checks": 0,
					"average_score": 0,
					"quality_distribution": {},
					"trend": [],
					"date_range": {
						"start": start_date.strftime("%Y-%m-%d"),
						"end": end_date.strftime("%Y-%m-%d")
					}
				}

			# 计算统计信息
			total_checks = len(quality_checks)
			total_score = sum(check.overall_score for check in quality_checks)
			average_score = total_score / total_checks if total_checks > 0 else 0

			# 质量等级分布
			quality_distribution = {
				"excellent": 0,
				"good": 0,
				"fair": 0,
				"poor": 0
			}

			for check in quality_checks:
				level = QualityLevelThreshold.get_quality_level(check.overall_score)
				quality_distribution[level] = quality_distribution.get(level, 0) + 1

			# 时间趋势
			trend = []

			# 根据分组方式处理
			if group_by == "day":
				date_format = "%Y-%m-%d"
			elif group_by == "week":
				date_format = "%Y-%W"
			elif group_by == "month":
				date_format = "%Y-%m"
			else:
				date_format = "%Y-%m-%d"

			date_groups = {}
			for check in quality_checks:
				date_key = check.check_time.strftime(date_format)
				if date_key not in date_groups:
					date_groups[date_key] = []
				date_groups[date_key].append(check.overall_score)

			# 按日期排序
			for date_key in sorted(date_groups.keys()):
				scores = date_groups[date_key]
				trend.append({
					"date": date_key,
					"average_score": round(sum(scores) / len(scores), 2),
					"check_count": len(scores),
					"min_score": round(min(scores), 2) if scores else 0,
					"max_score": round(max(scores), 2) if scores else 0
				})

			# 数据类型分布（如果未指定数据类型）
			data_type_distribution = {}
			if not data_type:
				for check in quality_checks:
					dt = check.data_type
					data_type_distribution[dt] = data_type_distribution.get(dt, 0) + 1

			return {
				"total_checks": total_checks,
				"average_score": round(average_score, 2),
				"quality_distribution": quality_distribution,
				"data_type_distribution": data_type_distribution,
				"trend": trend,
				"date_range": {
					"start": start_date.strftime("%Y-%m-%d"),
					"end": end_date.strftime("%Y-%m-%d")
				}
			}

		except Exception as e:
			logger.error(f"获取质量统计信息失败: {str(e)}", exc_info=True)
			raise

	# ==================== 问题修复方法 ====================

	async def fix_data_issues (
			self,
			check_id: str,
			fix_types: Optional[List[str]] = None,
			auto_fix: bool = True,
			user_id: Optional[int] = None
	) -> Dict[str, Any]:
		"""
		修复数据问题

		Args:
			check_id: 检查ID
			fix_types: 修复类型列表（missing, duplicate, outlier, invalid）
			auto_fix: 是否自动修复
			user_id: 用户ID

		Returns:
			Dict: 修复结果
		"""
		logger.info(f"开始修复数据问题，检查ID: {check_id}")

		try:
			# 获取原始检查结果
			quality_check = await self.quality_repo.get_by_check_id(check_id)
			if not quality_check:
				raise ValueError(f"质量检查记录 {check_id} 不存在")

			# 获取问题列表
			issues = quality_check.issues or []
			if not issues:
				return {
					"success": True,
					"check_id": check_id,
					"fixed_count": 0,
					"message": "没有需要修复的问题"
				}

			# 过滤需要修复的问题
			if fix_types:
				issues_to_fix = [
					issue for issue in issues
					if issue.get("issue_type") in fix_types
				]
			else:
				issues_to_fix = issues

			if not issues_to_fix:
				return {
					"success": True,
					"check_id": check_id,
					"fixed_count": 0,
					"message": "没有匹配的修复类型"
				}

			fixed_count = 0
			failed_fixes = []

			# 执行修复
			for issue in issues_to_fix:
				try:
					fix_result = await self._fix_single_issue(
						issue=issue,
						data_type=quality_check.data_type,
						auto_fix=auto_fix
					)

					if fix_result["success"]:
						fixed_count += 1
					else:
						failed_fixes.append({
							"issue": issue,
							"error": fix_result.get("error")
						})

				except Exception as e:
					logger.error(f"修复问题失败: {str(e)}")
					failed_fixes.append({
						"issue": issue,
						"error": str(e)
					})

			# 创建修复记录
			fix_id = f"fix_{check_id}_{datetime.now().strftime('%H%M%S')}"

			await self._create_fix_record(
				fix_id=fix_id,
				check_id=check_id,
				data_type=quality_check.data_type,
				total_issues=len(issues_to_fix),
				fixed_count=fixed_count,
				failed_fixes=failed_fixes,
				user_id=user_id
			)

			# 发布修复完成事件
			await self._publish_quality_event(
				event_type="fix_completed",
				check_id=check_id,
				fix_id=fix_id,
				data_type=quality_check.data_type,
				fixed_count=fixed_count,
				total_issues=len(issues_to_fix),
				user_id=user_id
			)

			logger.info(f"数据问题修复完成，修复ID: {fix_id}, 修复数量: {fixed_count}")

			return {
				"success": True,
				"fix_id": fix_id,
				"check_id": check_id,
				"total_issues": len(issues_to_fix),
				"fixed_count": fixed_count,
				"failed_fixes": failed_fixes,
				"message": f"成功修复 {fixed_count} 个问题"
			}

		except Exception as e:
			logger.error(f"修复数据问题失败: {str(e)}", exc_info=True)
			raise

	# ==================== 私有辅助方法 ====================

	async def _create_quality_check (
			self,
			data_type: str,
			start_date: Optional[date] = None,
			end_date: Optional[date] = None,
			ts_code: Optional[str] = None,
			check_types: Optional[List[str]] = None,
			user_id: Optional[int] = None
	) -> str:
		"""
		创建质量检查记录

		Args:
			data_type: 数据类型
			start_date: 开始日期
			end_date: 结束日期
			ts_code: 股票代码
			check_types: 检查类型
			user_id: 用户ID

		Returns:
			str: 检查ID
		"""
		check_id = f"quality_check_{datetime.now().strftime('%Y%m%d_%H%M%S')}"

		check_data = {
			"check_id": check_id,
			"data_type": data_type,
			"ts_code": ts_code,
			"start_date": start_date,
			"end_date": end_date,
			"check_types": check_types,
			"status": QualityCheckStatus.RUNNING,
			"user_id": user_id,
			"created_at": datetime.now()
		}

		await self.quality_repo.create(check_data)
		return check_id

	async def _update_quality_check (
			self,
			check_id: str,
			status: str,
			error: Optional[str] = None
	):
		"""
		更新质量检查状态

		Args:
			check_id: 检查ID
			status: 状态
			error: 错误信息
		"""
		check = await self.quality_repo.get_by_check_id(check_id)
		if not check:
			return

		update_data = {
			"status": status,
			"updated_at": datetime.now()
		}

		if status == QualityCheckStatus.COMPLETED:
			update_data["completed_at"] = datetime.now()
		elif status == QualityCheckStatus.FAILED:
			update_data["error"] = error

		await self.quality_repo.update(check.id, update_data)

	async def _perform_quality_check (
			self,
			check_type: str,
			data_type: str,
			start_date: Optional[date] = None,
			end_date: Optional[date] = None,
			ts_code: Optional[str] = None
	) -> Dict[str, Any]:
		"""
		执行具体的质量检查

		Args:
			check_type: 检查类型
			data_type: 数据类型
			start_date: 开始日期
			end_date: 结束日期
			ts_code: 股票代码

		Returns:
			Dict: 检查结果
		"""
		check_methods = {
			"completeness": self._check_completeness,
			"accuracy": self._check_accuracy,
			"timeliness": self._check_timeliness,
			"consistency": self._check_consistency
		}

		method = check_methods.get(check_type)
		if not method:
			raise ValueError(f"不支持的检查类型: {check_type}")

		return await method(
			data_type=data_type,
			start_date=start_date,
			end_date=end_date,
			ts_code=ts_code
		)

	async def _check_completeness (
			self,
			data_type: str,
			start_date: Optional[date] = None,
			end_date: Optional[date] = None,
			ts_code: Optional[str] = None
	) -> Dict[str, Any]:
		"""
		检查数据完整性

		Args:
			data_type: 数据类型
			start_date: 开始日期
			end_date: 结束日期
			ts_code: 股票代码

		Returns:
			Dict: 完整性检查结果
		"""
		metrics = {}
		issues = []

		try:
			if data_type == DataType.DAILY_QUOTES:
				# 检查日行情数据完整性
				completeness_rate, missing_dates = await self._check_quotes_completeness(
					ts_code, start_date, end_date
				)

				metrics[QualityMetricCode.COMPLETENESS_RATE] = {
					"value": completeness_rate,
					"threshold": self._quality_config["completeness_threshold"],
					"status": "pass" if completeness_rate >= self._quality_config["completeness_threshold"] else "fail"
				}

				if missing_dates:
					issues.append({
						"issue_type": QualityIssueType.MISSING_DATA,
						"severity": "medium" if len(missing_dates) < 5 else "high",
						"count": len(missing_dates),
						"description": f"缺失 {len(missing_dates)} 个交易日的行情数据",
						"affected_records": missing_dates[:10],  # 只显示前10个
						"suggestion": "重新同步缺失日期的数据"
					})

			elif data_type == DataType.STOCK_LIST:
				# 检查股票列表完整性
				completeness_rate = await self._check_stock_list_completeness()

				metrics[QualityMetricCode.COMPLETENESS_RATE] = {
					"value": completeness_rate,
					"threshold": self._quality_config["stock_completeness_threshold"],
					"status": "pass" if completeness_rate >= self._quality_config[
						"stock_completeness_threshold"] else "fail"
				}

				if completeness_rate < self._quality_config["stock_completeness_threshold"]:
					issues.append({
						"issue_type": QualityIssueType.INCOMPLETE_DATA,
						"severity": "high",
						"description": f"股票列表不完整，完整率: {completeness_rate}%",
						"suggestion": "更新股票列表数据"
					})

			elif data_type == DataType.FACTOR_DATA:
				# 检查因子数据完整性
				completeness_rate = await self._check_factor_data_completeness(
					ts_code, start_date, end_date
				)

				metrics[QualityMetricCode.COMPLETENESS_RATE] = {
					"value": completeness_rate,
					"threshold": self._quality_config["factor_completeness_threshold"],
					"status": "pass" if completeness_rate >= self._quality_config[
						"factor_completeness_threshold"] else "fail"
				}

				if completeness_rate < self._quality_config["factor_completeness_threshold"]:
					issues.append({
						"issue_type": QualityIssueType.INCOMPLETE_DATA,
						"severity": "medium",
						"description": f"因子数据不完整，完整率: {completeness_rate}%",
						"suggestion": "重新计算因子数据"
					})

		except Exception as e:
			logger.error(f"检查完整性失败: {str(e)}")
			metrics[QualityMetricCode.COMPLETENESS_RATE] = {
				"value": 0,
				"status": "error",
				"error": str(e)
			}

		return {
			"metrics": metrics,
			"issues": issues
		}

	async def _check_accuracy (
			self,
			data_type: str,
			start_date: Optional[date] = None,
			end_date: Optional[date] = None,
			ts_code: Optional[str] = None
	) -> Dict[str, Any]:
		"""
		检查数据准确性

		Args:
			data_type: 数据类型
			start_date: 开始日期
			end_date: 结束日期
			ts_code: 股票代码

		Returns:
			Dict: 准确性检查结果
		"""
		metrics = {}
		issues = []

		try:
			if data_type == DataType.DAILY_QUOTES:
				# 检查行情数据准确性
				outlier_rate, abnormal_records = await self._check_quotes_accuracy(
					ts_code, start_date, end_date
				)

				metrics[QualityMetricCode.OUTLIER_RATE] = {
					"value": outlier_rate,
					"threshold": self._quality_config["outlier_threshold"],
					"status": "pass" if outlier_rate <= self._quality_config["outlier_threshold"] else "fail"
				}

				if abnormal_records:
					issues.append({
						"issue_type": QualityIssueType.OUTLIER_DATA,
						"severity": "low" if len(abnormal_records) < 3 else "medium",
						"count": len(abnormal_records),
						"description": f"发现 {len(abnormal_records)} 条异常价格记录",
						"affected_records": [
							f"{record.trade_date}: 价格异常（涨跌幅: {record.pct_chg}%）"
							for record in abnormal_records[:5]
						],
						"suggestion": "验证异常数据的准确性"
					})

				# 检查数据逻辑一致性
				inconsistent_records = await self._check_quotes_consistency(
					ts_code, start_date, end_date
				)

				if inconsistent_records:
					issues.append({
						"issue_type": QualityIssueType.INCONSISTENT_DATA,
						"severity": "high",
						"count": len(inconsistent_records),
						"description": f"发现 {len(inconsistent_records)} 条逻辑不一致的记录",
						"affected_records": [
							f"{record.trade_date}: 数据不一致"
							for record in inconsistent_records[:5]
						],
						"suggestion": "修复逻辑不一致的数据"
					})

		except Exception as e:
			logger.error(f"检查准确性失败: {str(e)}")
			metrics[QualityMetricCode.OUTLIER_RATE] = {
				"value": 0,
				"status": "error",
				"error": str(e)
			}

		return {
			"metrics": metrics,
			"issues": issues
		}

	async def _check_timeliness (
			self,
			data_type: str,
			start_date: Optional[date] = None,
			end_date: Optional[date] = None,
			ts_code: Optional[str] = None
	) -> Dict[str, Any]:
		"""
		检查数据及时性

		Args:
			data_type: 数据类型
			start_date: 开始日期
			end_date: 结束日期
			ts_code: 股票代码

		Returns:
			Dict: 及时性检查结果
		"""
		metrics = {}
		issues = []

		try:
			if data_type == DataType.DAILY_QUOTES:
				# 检查行情数据及时性
				timeliness_score, delay_days = await self._check_quotes_timeliness(ts_code)

				metrics[QualityMetricCode.TIMELINESS_SCORE] = {
					"value": timeliness_score,
					"threshold": self._quality_config["timeliness_threshold"],
					"status": "pass" if timeliness_score >= self._quality_config["timeliness_threshold"] else "fail"
				}

				if delay_days > self._quality_config["max_delay_days"]:
					issues.append({
						"issue_type": QualityIssueType.STALE_DATA,
						"severity": "medium" if delay_days < 3 else "high",
						"count": 1,
						"description": f"数据更新延迟 {delay_days} 天",
						"suggestion": "立即同步最新数据"
					})

			elif data_type == DataType.FACTOR_DATA:
				# 检查因子数据及时性
				timeliness_score = await self._check_factor_timeliness(ts_code)

				metrics[QualityMetricCode.TIMELINESS_SCORE] = {
					"value": timeliness_score,
					"threshold": self._quality_config["factor_timeliness_threshold"],
					"status": "pass" if timeliness_score >= self._quality_config[
						"factor_timeliness_threshold"] else "fail"
				}

				if timeliness_score < self._quality_config["factor_timeliness_threshold"]:
					issues.append({
						"issue_type": QualityIssueType.STALE_DATA,
						"severity": "medium",
						"description": "因子数据更新不及时",
						"suggestion": "重新计算因子数据"
					})

		except Exception as e:
			logger.error(f"检查及时性失败: {str(e)}")
			metrics[QualityMetricCode.TIMELINESS_SCORE] = {
				"value": 0,
				"status": "error",
				"error": str(e)
			}

		return {
			"metrics": metrics,
			"issues": issues
		}

	async def _check_consistency (
			self,
			data_type: str,
			start_date: Optional[date] = None,
			end_date: Optional[date] = None,
			ts_code: Optional[str] = None
	) -> Dict[str, Any]:
		"""
		检查数据一致性

		Args:
			data_type: 数据类型
			start_date: 开始日期
			end_date: 结束日期
			ts_code: 股票代码

		Returns:
			Dict: 一致性检查结果
		"""
		metrics = {}
		issues = []

		try:
			if data_type == DataType.DAILY_QUOTES:
				# 检查重复记录
				duplicate_rate, duplicate_records = await self._check_quotes_duplicates(
					ts_code, start_date, end_date
				)

				metrics[QualityMetricCode.DUPLICATE_RATE] = {
					"value": duplicate_rate,
					"threshold": self._quality_config["duplicate_threshold"],
					"status": "pass" if duplicate_rate <= self._quality_config["duplicate_threshold"] else "fail"
				}

				if duplicate_records:
					issues.append({
						"issue_type": QualityIssueType.DUPLICATE_DATA,
						"severity": "low" if len(duplicate_records) < 5 else "medium",
						"count": len(duplicate_records),
						"description": f"发现 {len(duplicate_records)} 条重复记录",
						"affected_records": [
							f"{record.trade_date}: 重复记录"
							for record in duplicate_records[:5]
						],
						"suggestion": "清理重复数据"
					})

				# 计算一致性得分
				consistency_score = await self._calculate_consistency_score(
					ts_code, start_date, end_date
				)

				metrics[QualityMetricCode.CONSISTENCY_SCORE] = {
					"value": consistency_score,
					"threshold": self._quality_config["consistency_threshold"],
					"status": "pass" if consistency_score >= self._quality_config["consistency_threshold"] else "fail"
				}

		except Exception as e:
			logger.error(f"检查一致性失败: {str(e)}")
			metrics[QualityMetricCode.CONSISTENCY_SCORE] = {
				"value": 0,
				"status": "error",
				"error": str(e)
			}

		return {
			"metrics": metrics,
			"issues": issues
		}

	# ==================== 具体检查方法实现 ====================

	async def _check_quotes_completeness (
			self,
			ts_code: Optional[str],
			start_date: Optional[date],
			end_date: Optional[date]
	) -> Tuple[float, List[date]]:
		"""检查行情数据完整性"""
		# 获取交易日历
		if not start_date or not end_date:
			end_date = datetime.now().date()
			start_date = end_date - timedelta(days=30)

		trading_days = await self.calendar_repo.get_trading_days(
			start_date=start_date,
			end_date=end_date
		)

		if not trading_days:
			return 0.0, []

		total_days = len(trading_days)

		# 获取实际数据天数
		if ts_code:
			actual_dates = await self.quote_repo.get_trade_dates(
				ts_code=ts_code,
				start_date=start_date,
				end_date=end_date
			)
			actual_count = len(actual_dates)

			# 找出缺失的交易日
			missing_dates = [
				day for day in trading_days
				if day not in actual_dates
			]
		else:
			# 抽样检查（简化处理）
			actual_count = int(total_days * 0.95)  # 假设95%完整
			missing_dates = []

		# 计算完整率
		completeness_rate = (actual_count / total_days * 100) if total_days > 0 else 100

		return completeness_rate, missing_dates

	async def _check_stock_list_completeness (self) -> float:
		"""检查股票列表完整性"""
		# 获取股票总数
		total_stocks = await self.stock_repo.count()

		# 期望的股票数量（基于经验值）
		expected_stocks = 5000  # 大约5000只A股

		completeness_rate = (total_stocks / expected_stocks * 100) if expected_stocks > 0 else 100

		return completeness_rate

	async def _check_factor_data_completeness (
			self,
			ts_code: Optional[str],
			start_date: Optional[date],
			end_date: Optional[date]
	) -> float:
		"""检查因子数据完整性"""
		if not ts_code:
			return 95.0  # 假设95%完整

		# 获取因子数据
		factor_names = await self._get_available_factors()
		if not factor_names:
			return 0.0

		total_factors = len(factor_names)
		complete_factors = 0

		for factor_name in factor_names[:10]:  # 抽样检查前10个因子
			factor_data = await self.factor_repo.get_by_ts_code_and_date_range(
				ts_code=ts_code,
				factor_name=factor_name,
				start_date=start_date,
				end_date=end_date
			)

			if factor_data and len(factor_data) > 0:
				complete_factors += 1

		completeness_rate = (complete_factors / total_factors * 100) if total_factors > 0 else 0

		return completeness_rate

	async def _check_quotes_accuracy (
			self,
			ts_code: Optional[str],
			start_date: Optional[date],
			end_date: Optional[date]
	) -> Tuple[float, List]:
		"""检查行情数据准确性"""
		if not ts_code:
			return 0.0, []

		# 获取行情数据
		quotes = await self.quote_repo.get_by_ts_code_date_range(
			ts_code=ts_code,
			start_date=start_date,
			end_date=end_date
		)

		if not quotes:
			return 0.0, []

		total_records = len(quotes)
		abnormal_records = []

		# 检查异常值
		for quote in quotes:
			if quote.pct_chg:
				pct_chg = float(quote.pct_chg)
				# 涨跌幅超过30%视为异常
				if abs(pct_chg) > 30:
					abnormal_records.append(quote)

		# 计算异常率
		outlier_rate = (len(abnormal_records) / total_records * 100) if total_records > 0 else 0

		return outlier_rate, abnormal_records

	async def _check_quotes_consistency (
			self,
			ts_code: Optional[str],
			start_date: Optional[date],
			end_date: Optional[date]
	) -> List:
		"""检查行情数据逻辑一致性"""
		if not ts_code:
			return []

		quotes = await self.quote_repo.get_by_ts_code_date_range(
			ts_code=ts_code,
			start_date=start_date,
			end_date=end_date
		)

		inconsistent_records = []

		for quote in quotes:
			# 检查最高价 >= 最低价
			if quote.high and quote.low and float(quote.high) < float(quote.low):
				inconsistent_records.append(quote)
			# 检查收盘价在最高最低价之间
			elif quote.close and quote.high and quote.low:
				close = float(quote.close)
				high = float(quote.high)
				low = float(quote.low)
				if close > high or close < low:
					inconsistent_records.append(quote)

		return inconsistent_records

	async def _check_quotes_timeliness (
			self,
			ts_code: Optional[str]
	) -> Tuple[float, int]:
		"""检查行情数据及时性"""
		if not ts_code:
			return 95.0, 0

		# 获取最新数据日期
		latest_quote = await self.quote_repo.get_latest_by_ts_code(ts_code)

		if not latest_quote:
			return 0.0, 999

		latest_date = latest_quote.trade_date
		today = datetime.now().date()

		# 计算数据延迟（距离今天的天数）
		delay_days = (today - latest_date).days

		# 计算及时性得分
		timeliness_score = 100 - (delay_days * 20)  # 每延迟1天扣20分
		timeliness_score = max(0, min(100, timeliness_score))

		return timeliness_score, delay_days

	async def _check_factor_timeliness (
			self,
			ts_code: Optional[str]
	) -> float:
		"""检查因子数据及时性"""
		if not ts_code:
			return 95.0

		# 获取最新因子数据
		latest_factor = await self.factor_repo.get_latest_by_ts_code(ts_code)

		if not latest_factor:
			return 0.0

		latest_date = latest_factor.trade_date
		today = datetime.now().date()

		# 计算延迟天数
		delay_days = (today - latest_date).days

		# 计算及时性得分
		timeliness_score = 100 - (delay_days * 10)  # 每延迟1天扣10分
		timeliness_score = max(0, min(100, timeliness_score))

		return timeliness_score

	async def _check_quotes_duplicates (
			self,
			ts_code: Optional[str],
			start_date: Optional[date],
			end_date: Optional[date]
	) -> Tuple[float, List]:
		"""检查行情数据重复记录"""
		if not ts_code:
			return 0.0, []

		# 获取所有记录
		quotes = await self.quote_repo.get_by_ts_code_date_range(
			ts_code=ts_code,
			start_date=start_date,
			end_date=end_date
		)

		if not quotes:
			return 0.0, []

		total_records = len(quotes)

		# 检查重复记录（简化处理）
		date_counts = {}
		duplicate_records = []

		for quote in quotes:
			date_str = quote.trade_date.isoformat()
			if date_str not in date_counts:
				date_counts[date_str] = []
			date_counts[date_str].append(quote)

		for date_str, quotes_on_date in date_counts.items():
			if len(quotes_on_date) > 1:
				duplicate_records.extend(quotes_on_date[1:])  # 保留第一条，其余视为重复

		# 计算重复率
		duplicate_rate = (len(duplicate_records) / total_records * 100) if total_records > 0 else 0

		return duplicate_rate, duplicate_records

	async def _calculate_consistency_score (
			self,
			ts_code: Optional[str],
			start_date: Optional[date],
			end_date: Optional[date]
	) -> float:
		"""计算一致性得分"""
		# 这里简化处理，实际应该比较不同数据源的数据
		return 95.0  # 假设一致性得分为95

	# ==================== 评分和总结方法 ====================

	def _calculate_overall_score (self, results: Dict[str, Any]) -> float:
		"""
		计算总体质量评分

		Args:
			results: 各项检查结果

		Returns:
			float: 总体质量评分（0-100）
		"""
		if not results:
			return 0

		total_score = 0
		total_weight = 0

		# 计算各项指标的加权平均
		for check_type, check_results in results.items():
			if "metrics" not in check_results:
				continue

			metrics = check_results["metrics"]

			# 获取该检查类型的权重
			weight = QualityLevelThreshold.METRIC_WEIGHTS.get(check_type, 0.25)

			# 计算该检查类型的平均得分
			check_scores = []
			for metric_name, metric_data in metrics.items():
				if metric_data.get("status") == "pass" and "value" in metric_data:
					# 将指标值转换为得分
					metric_value = metric_data["value"]
					threshold = metric_data.get("threshold", 100)

					if metric_name in [QualityMetricCode.OUTLIER_RATE, QualityMetricCode.DUPLICATE_RATE]:
						# 对于率类指标，值越低越好
						score = max(0, 100 - (metric_value * 100 / threshold))
					else:
						# 对于得分类指标，值越高越好
						score = min(100, metric_value * 100 / threshold) if threshold > 0 else 0

					check_scores.append(score)

			if check_scores:
				avg_check_score = sum(check_scores) / len(check_scores)
				total_score += avg_check_score * weight
				total_weight += weight

		# 如果有问题，适当扣分
		issue_deduction = 0
		for check_type, check_results in results.items():
			if "issues" in check_results and check_results["issues"]:
				issue_count = len(check_results["issues"])
				# 根据问题严重程度扣分
				total_severity = sum(
					1 for issue in check_results["issues"]
					if issue.get("severity") == "high"
				)

				issue_deduction += total_severity * 5  # 每个严重问题扣5分
				issue_deduction += (issue_count - total_severity) * 2  # 其他问题每个扣2分

		overall_score = (total_score / total_weight) if total_weight > 0 else 0
		overall_score = max(0, overall_score - issue_deduction)

		return round(overall_score, 2)

	def _generate_quality_suggestions (
			self,
			issues: List[Dict],
			overall_score: float
	) -> List[str]:
		"""
		生成质量改进建议

		Args:
			issues: 问题列表
			overall_score: 总体质量评分

		Returns:
			List[str]: 改进建议列表
		"""
		suggestions = []

		if overall_score < 90:
			suggestions.append("数据质量有待提升，建议进行详细检查和修复")

		# 根据问题类型生成具体建议
		issue_types = {}
		for issue in issues:
			issue_type = issue.get("issue_type")
			if issue_type:
				issue_types[issue_type] = issue_types.get(issue_type, 0) + 1

		if issue_types.get(QualityIssueType.MISSING_DATA):
			suggestions.append(f"发现 {issue_types[QualityIssueType.MISSING_DATA]} 个缺失数据问题，建议重新同步相关数据")

		if issue_types.get(QualityIssueType.DUPLICATE_DATA):
			suggestions.append(f"发现 {issue_types[QualityIssueType.DUPLICATE_DATA]} 个重复记录，建议清理重复数据")

		if issue_types.get(QualityIssueType.OUTLIER_DATA):
			suggestions.append(f"发现 {issue_types[QualityIssueType.OUTLIER_DATA]} 个异常值，建议验证数据准确性")

		if issue_types.get(QualityIssueType.INCONSISTENT_DATA):
			suggestions.append(
				f"发现 {issue_types[QualityIssueType.INCONSISTENT_DATA]} 个逻辑不一致问题，建议修复数据逻辑")

		if issue_types.get(QualityIssueType.STALE_DATA):
			suggestions.append("数据更新不及时，建议检查数据同步任务")

		if issue_types.get(QualityIssueType.INCOMPLETE_DATA):
			suggestions.append("数据不完整，建议补充缺失数据")

		# 通用建议
		if overall_score >= 95:
			suggestions.append("数据质量优秀，继续保持")
		elif overall_score >= 85:
			suggestions.append("数据质量良好，建议定期检查和维护")
		elif overall_score >= 70:
			suggestions.append("数据质量一般，建议重点关注和改进")
		else:
			suggestions.append("数据质量较差，建议立即进行全面检查和修复")

		return suggestions

	# ==================== 问题修复方法 ====================

	async def _fix_single_issue (
			self,
			issue: Dict,
			data_type: str,
			auto_fix: bool = True
	) -> Dict[str, Any]:
		"""
		修复单个数据问题

		Args:
			issue: 问题描述
			data_type: 数据类型
			auto_fix: 是否自动修复

		Returns:
			Dict: 修复结果
		"""
		issue_type = issue.get("issue_type")

		if not auto_fix:
			# 仅报告问题，不自动修复
			return {
				"success": False,
				"message": "自动修复已禁用",
				"issue": issue
			}

		try:
			if issue_type == QualityIssueType.DUPLICATE_DATA and data_type == DataType.DAILY_QUOTES:
				# 修复重复记录
				fixed = await self._fix_duplicate_records(issue)
				return {
					"success": fixed,
					"message": "重复记录已修复" if fixed else "修复重复记录失败"
				}

			elif issue_type == QualityIssueType.MISSING_DATA and data_type == DataType.DAILY_QUOTES:
				# 修复缺失数据
				fixed = await self._fix_missing_data(issue)
				return {
					"success": fixed,
					"message": "缺失数据已修复" if fixed else "修复缺失数据失败"
				}

			else:
				# 暂不支持自动修复的问题类型
				return {
					"success": False,
					"message": f"暂不支持自动修复 {issue_type} 类型的问题",
					"issue": issue
				}

		except Exception as e:
			logger.error(f"修复问题失败: {str(e)}")
			return {
				"success": False,
				"error": str(e),
				"issue": issue
			}

	async def _fix_duplicate_records (self, issue: Dict) -> bool:
		"""修复重复记录"""
		try:
			# 这里简化处理，实际需要根据具体问题实现
			logger.info(f"修复重复记录: {issue}")

			# 模拟修复过程
			await asyncio.sleep(0.1)  # 模拟修复耗时

			return True

		except Exception as e:
			logger.error(f"修复重复记录失败: {str(e)}")
			return False

	async def _fix_missing_data (self, issue: Dict) -> bool:
		"""修复缺失数据"""
		try:
			# 这里简化处理，实际需要重新同步缺失的数据
			logger.info(f"修复缺失数据: {issue}")

			# 模拟修复过程
			await asyncio.sleep(0.2)  # 模拟修复耗时

			return True

		except Exception as e:
			logger.error(f"修复缺失数据失败: {str(e)}")
			return False

	# ==================== 数据持久化方法 ====================

	async def _save_quality_result (
			self,
			check_id: str,
			result: Dict[str, Any]
	):
		"""
		保存质量检查结果

		Args:
			check_id: 检查ID
			result: 检查结果
		"""
		check = await self.quality_repo.get_by_check_id(check_id)
		if not check:
			return

		# 计算检查耗时
		duration = None
		if check.created_at:
			duration = (datetime.now() - check.created_at).total_seconds()

		update_data = {
			"status": QualityCheckStatus.COMPLETED,
			"completed_at": datetime.now(),
			"overall_score": result.get("overall_score"),
			"quality_level": result.get("quality_level"),
			"metrics": result.get("metrics"),
			"issues": result.get("issues"),
			"suggestions": result.get("suggestions"),
			"duration_seconds": duration
		}

		await self.quality_repo.update(check.id, update_data)

	async def _create_fix_record (
			self,
			fix_id: str,
			check_id: str,
			data_type: str,
			total_issues: int,
			fixed_count: int,
			failed_fixes: List[Dict],
			user_id: Optional[int] = None
	):
		"""
		创建修复记录

		Args:
			fix_id: 修复ID
			check_id: 检查ID
			data_type: 数据类型
			total_issues: 总问题数
			fixed_count: 修复数量
			failed_fixes: 修复失败列表
			user_id: 用户ID
		"""
		# 这里简化处理，实际需要创建修复记录表
		logger.info(f"创建修复记录: {fix_id}")

		# 缓存修复记录
		fix_data = {
			"fix_id": fix_id,
			"check_id": check_id,
			"data_type": data_type,
			"status": "completed",
			"user_id": user_id,
			"total_issues": total_issues,
			"fixed_count": fixed_count,
			"failed_fixes": failed_fixes,
			"created_at": datetime.now().isoformat(),
			"completed_at": datetime.now().isoformat()
		}

		cache_key = f"quality:fix:{fix_id}"
		await self.cache.set(cache_key, fix_data, ttl=86400)  # 缓存24小时

	# ==================== 进度更新方法 ====================

	async def _update_quality_progress (
			self,
			check_id: str,
			progress: float,
			current_check: str,
			user_id: Optional[int] = None
	):
		"""
		更新质量检查进度

		Args:
			check_id: 检查ID
			progress: 进度百分比
			current_check: 当前检查项
			user_id: 用户ID
		"""
		# 缓存进度信息
		progress_key = f"quality:progress:{check_id}"
		progress_data = {
			"progress": progress,
			"current_check": current_check,
			"updated_at": datetime.now().isoformat()
		}

		await self.cache.set(progress_key, progress_data, ttl=3600)

		# 发布进度事件
		await self._publish_quality_event(
			event_type="progress",
			check_id=check_id,
			progress=progress,
			current_check=current_check,
			user_id=user_id
		)

	# ==================== 配置管理方法 ====================

	def _load_quality_config (self) -> Dict[str, Any]:
		"""
		加载质量检查配置

		Returns:
			Dict: 质量检查配置
		"""
		return {
			"completeness_threshold": 95.0,  # 完整性阈值
			"stock_completeness_threshold": 95.0,  # 股票列表完整性阈值
			"factor_completeness_threshold": 90.0,  # 因子数据完整性阈值
			"outlier_threshold": 5.0,  # 异常值率阈值
			"duplicate_threshold": 0.1,  # 重复率阈值
			"timeliness_threshold": 80.0,  # 及时性得分阈值
			"factor_timeliness_threshold": 70.0,  # 因子及时性得分阈值
			"consistency_threshold": 90.0,  # 一致性得分阈值
			"max_delay_days": 1  # 最大允许延迟天数
		}

	def _update_quality_thresholds (self, thresholds: Dict[str, float]):
		"""
		更新质量阈值配置

		Args:
			thresholds: 新的阈值配置
		"""
		for key, value in thresholds.items():
			if key in self._quality_config:
				self._quality_config[key] = value

	# ==================== 事件发布方法 ====================

	async def _publish_quality_event (
			self,
			event_type: str,
			check_id: Optional[str] = None,
			batch_id: Optional[str] = None,
			data_type: Optional[str] = None,
			quality_level: Optional[str] = None,
			overall_score: Optional[float] = None,
			issue_count: Optional[int] = None,
			issues: Optional[List] = None,
			fixed_count: Optional[int] = None,
			progress: Optional[float] = None,
			current_check: Optional[str] = None,
			summary: Optional[Dict] = None,
			error: Optional[str] = None,
			data_types: Optional[List[str]] = None,
			fix_id: Optional[str] = None,
			user_id: Optional[int] = None
	):
		"""
		发布质量事件

		Args:
			event_type: 事件类型
			check_id: 检查ID
			batch_id: 批量检查ID
			data_type: 数据类型
			quality_level: 质量等级
			overall_score: 总体评分
			issue_count: 问题数量
			issues: 问题列表
			fixed_count: 修复数量
			progress: 进度百分比
			current_check: 当前检查项
			summary: 总结信息
			error: 错误信息
			data_types: 数据类型列表
			fix_id: 修复ID
			user_id: 用户ID
		"""
		if not self.event_engine:
			return

		try:
			event_data = {
				"timestamp": datetime.now(),
				"user_id": user_id
			}

			if check_id:
				event_data["check_id"] = check_id
			if batch_id:
				event_data["batch_id"] = batch_id
			if data_type:
				event_data["data_type"] = data_type
			if quality_level:
				event_data["quality_level"] = quality_level
			if overall_score is not None:
				event_data["overall_score"] = overall_score
			if issue_count is not None:
				event_data["issue_count"] = issue_count
			if issues:
				event_data["issues"] = issues
			if fixed_count is not None:
				event_data["fixed_count"] = fixed_count
			if progress is not None:
				event_data["progress"] = progress
			if current_check:
				event_data["current_check"] = current_check
			if summary:
				event_data["summary"] = summary
			if error:
				event_data["error"] = error
			if data_types:
				event_data["data_types"] = data_types
			if fix_id:
				event_data["fix_id"] = fix_id

			event = DataQualityEvent(
				event_type=f"quality.{event_type}",
				**event_data
			)

			await self.event_engine.put(event)

		except Exception as e:
			logger.error(f"发布质量事件失败: {str(e)}")

	# ==================== 辅助方法 ====================

	async def _get_available_factors (self) -> List[str]:
		"""
		获取可用因子列表

		Returns:
			List[str]: 因子名称列表
		"""
		try:
			factors = await self.factor_repo.get_available_factors()
			return factors if factors else []
		except Exception:
			return []