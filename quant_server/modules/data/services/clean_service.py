# -*- coding: utf-8 -*-
"""
数据清洗服务
负责数据清洗、标准化和预处理
位置：modules/data/services/clean_service.py

设计原则：
1. 模块化清洗规则：每条清洗规则独立实现
2. 可配置的清洗参数：支持不同的清洗策略
3. 原子性操作：每条清洗记录可追溯
4. 高性能处理：支持批量清洗操作

架构位置：根据混合架构设计，本服务属于数据模块的业务服务层
"""

import json
import logging
from datetime import datetime, date, timedelta
from typing import Dict, List, Any, Optional

import pandas as pd
from sqlalchemy import or_, select, func
from sqlalchemy.ext.asyncio import AsyncSession

# 导入核心基础设施
from core.engines.system.event_engine import EventEngine
# 导入数据模块常量
from modules.data.constants import DataType
from modules.data.events.clean_events import DataCleanEvent
from shared.cache.redis_cache import RedisCache
from shared.database.repositories.analysis.factor.data_quality_check_repo import DataQualityCheckRepository
# 导入共享层组件 - 根据架构设计调整导入路径
from shared.database.repositories.market.quote import StockDailyRepository, StockMinuteRepository
from shared.database.repositories.operation.task import DataSyncTaskRepository
from utils.core_utils.data_utils.data_validator import DataValidator

# 配置日志
logger = logging.getLogger(__name__)


class DataCleanService:
	"""
	数据清洗服务类
	负责数据的清洗、标准化和预处理
	"""

	def __init__(self, session: AsyncSession, event_engine: Optional[EventEngine] = None):
		"""
		初始化数据清洗服务

		Args:
			session: 数据库会话
			event_engine: 事件引擎
		"""
		self.session = session
		self.event_engine = event_engine

		# 初始化Repository - 根据架构设计使用共享层Repository
		self.daily_quote_repo = StockDailyRepository(session)
		self.minute_quote_repo = StockMinuteRepository(session)
		self.quality_repo = DataQualityCheckRepository(session)
		self.sync_task_repo = DataSyncTaskRepository(session)

		# 初始化工具
		self.validator = DataValidator()
		self.transformer = None

		# 初始化缓存（懒加载）
		self._cache = None

		# 初始化交易日历工具
		self.trading_calendar = None

	@property
	def cache(self) -> RedisCache:
		"""获取缓存实例（懒加载）"""
		if self._cache is None:
			from shared.config.config_manager import get_config
			settings = get_config().settings
			self._cache = RedisCache(
				host=settings.REDIS.HOST,
				port=settings.REDIS.PORT,
				db=settings.REDIS.DB,
				password=settings.REDIS.PASSWORD
			)
		return self._cache

	async def clean_data(
			self,
			data_type: str,
			start_date: Optional[date] = None,
			end_date: Optional[date] = None,
			ts_codes: Optional[List[str]] = None,
			clean_rules: Optional[List[str]] = None,
			auto_apply: bool = False,
			user_id: Optional[str] = None
	) -> Dict[str, Any]:
		"""
		清洗数据

		Args:
			data_type: 数据类型
			start_date: 开始日期
			end_date: 结束日期
			ts_codes: 股票代码列表
			clean_rules: 清洗规则列表
			auto_apply: 是否自动应用清洗结果
			user_id: 用户ID

		Returns:
			Dict: 清洗结果
		"""
		logger.info(f"开始清洗数据，类型: {data_type}, 规则: {clean_rules}")

		clean_id = None
		try:
			# 创建清洗任务记录
			clean_id = await self._create_clean_task(
				data_type=data_type,
				start_date=start_date,
				end_date=end_date,
				ts_codes=ts_codes,
				clean_rules=clean_rules,
				user_id=user_id
			)

			# 发布清洗开始事件
			await self._publish_clean_event(
				event_type="started",
				clean_id=clean_id,
				data_type=data_type,
				user_id=user_id
			)

			# 执行清洗
			clean_result = await self._execute_cleaning(
				data_type=data_type,
				start_date=start_date,
				end_date=end_date,
				ts_codes=ts_codes,
				clean_rules=clean_rules,
				clean_id=clean_id,
				user_id=user_id
			)

			# 如果启用自动应用，应用清洗结果
			if auto_apply and clean_result.get("issues"):
				apply_result = await self._apply_cleaning_results(
					clean_id=clean_id,
					user_id=user_id
				)
				clean_result["applied"] = apply_result

			# 保存清洗结果
			await self._save_clean_result(
				clean_id=clean_id,
				result=clean_result
			)

			# 发布清洗完成事件
			await self._publish_clean_event(
				event_type="completed",
				clean_id=clean_id,
				data_type=data_type,
				result=clean_result,
				user_id=user_id
			)

			logger.info(f"数据清洗完成，清洗ID: {clean_id}")

			return {
				"success": True,
				"clean_id": clean_id,
				"result": clean_result,
				"message": "数据清洗完成"
			}

		except Exception as e:
			logger.error(f"数据清洗失败: {str(e)}", exc_info=True)

			# 更新清洗状态为失败
			if clean_id:
				await self._update_clean_task(
					clean_id=clean_id,
					status="failed",
					error=str(e)
				)

			return {
				"success": False,
				"clean_id": clean_id,
				"error": str(e),
				"message": "数据清洗失败"
			}

	async def apply_cleaning_results(
			self,
			clean_id: str,
			apply_rules: Optional[List[str]] = None,
			dry_run: bool = False,
			user_id: Optional[str] = None
	) -> Dict[str, Any]:
		"""
		应用清洗结果

		Args:
			clean_id: 清洗ID
			apply_rules: 要应用的规则列表
			dry_run: 试运行（不实际修改数据）
			user_id: 用户ID

		Returns:
			Dict: 应用结果
		"""
		logger.info(f"应用清洗结果，清洗ID: {clean_id}, 试运行: {dry_run}")

		try:
			# 通过 clean_id（存储在 check_results JSON 中）直接查询匹配的任务
			clean_task = await self.quality_repo.get_by_clean_id(clean_id)

			if not clean_task:
				raise ValueError(f"清洗任务 {clean_id} 不存在")

			# 获取清洗结果
			clean_result = clean_task.check_results

			if not clean_result or "issues" not in clean_result:
				return {
					"success": True,
					"clean_id": clean_id,
					"applied_count": 0,
					"message": "没有需要应用的清洗结果"
				}

			# 过滤要应用的问题
			issues_to_apply = clean_result["issues"]
			if apply_rules:
				issues_to_apply = [
					issue for issue in issues_to_apply
					if issue.get("rule") in apply_rules
				]

			if not issues_to_apply:
				return {
					"success": True,
					"clean_id": clean_id,
					"applied_count": 0,
					"message": "没有匹配的清洗规则"
				}

			# 应用清洗
			applied_count = 0
			failed_applications = []

			for issue in issues_to_apply:
				try:
					if not dry_run:
						# 实际应用清洗
						applied = await self._apply_single_issue(
							issue=issue,
							data_type=clean_task.data_type
						)

						if applied:
							applied_count += 1
						else:
							failed_applications.append({
								"issue": issue,
								"error": "应用失败"
							})
					else:
						# 试运行，只计数
						applied_count += 1

				except Exception as e:
					logger.error(f"应用清洗问题失败: {str(e)}")
					failed_applications.append({
						"issue": issue,
						"error": str(e)
					})

			# 创建应用记录
			apply_id = f"apply_{clean_id}_{datetime.now().strftime('%H%M%S')}"

			await self._create_apply_record(
				apply_id=apply_id,
				clean_id=clean_id,
				data_type=clean_task.data_type,
				dry_run=dry_run,
				total_issues=len(issues_to_apply),
				applied_count=applied_count,
				failed_applications=failed_applications,
				user_id=user_id
			)

			# 清理相关缓存
			await self.__class__._clean_cache_after_cleaning(clean_task.data_type)

			# 发布应用完成事件
			await self._publish_clean_event(
				event_type="applied",
				clean_id=clean_id,
				apply_id=apply_id,
				data_type=clean_task.data_type,
				applied_count=applied_count,
				dry_run=dry_run,
				user_id=user_id
			)

			logger.info(f"清洗结果应用完成，应用ID: {apply_id}, 应用数量: {applied_count}")

			return {
				"success": True,
				"apply_id": apply_id,
				"clean_id": clean_id,
				"total_issues": len(issues_to_apply),
				"applied_count": applied_count,
				"failed_applications": failed_applications,
				"dry_run": dry_run,
				"message": f"成功应用 {applied_count} 个清洗结果"
			}

		except Exception as e:
			logger.error(f"应用清洗结果失败: {str(e)}", exc_info=True)
			raise

	async def get_cleaning_history(
			self,
			data_type: Optional[str] = None,
			start_date: Optional[date] = None,
			end_date: Optional[date] = None,
			limit: int = 20
	) -> List[Dict[str, Any]]:
		"""
		获取清洗历史记录

		Args:
			data_type: 数据类型
			start_date: 开始日期
			end_date: 结束日期
			limit: 返回数量限制

		Returns:
			List[Dict]: 清洗历史记录
		"""
		try:
			# 构建查询条件
			kwargs = {"check_type": "clean"}
			if data_type:
				kwargs["data_type"] = data_type

			# 获取清洗记录
			clean_tasks = await self.quality_repo.get_many(
				**kwargs,
				limit=limit,
			)
			# Post-filter by date range (TODO: add comparison filter support to BaseRepository)
			if start_date:
				clean_tasks = [t for t in clean_tasks if hasattr(t, "check_date") and t.check_date >= start_date]
			if end_date:
				clean_tasks = [t for t in clean_tasks if hasattr(t, "check_date") and t.check_date <= end_date]
			# Sort by created_at descending
			clean_tasks = sorted(
				clean_tasks,
				key=lambda x: getattr(x, "created_at", datetime.min),
				reverse=True,
			)

			# 转换为响应格式
			history = []
			for task in clean_tasks:
				check_results = task.check_results or {}
				history.append({
					"clean_id": check_results.get("clean_id", str(task.id)),
					"data_type": task.data_type,
					"status": task.status,
					"clean_rules": check_results.get("clean_rules", []),
					"issue_count": len(check_results.get("issues", [])),
					"applied": check_results.get("applied", False),
					"created_at": task.created_at.isoformat() if task.created_at else None,
					"completed_at": task.created_at.isoformat() if task.status == "completed" else None,
					"duration_seconds": check_results.get("duration_seconds")
				})

			return history

		except Exception as e:
			logger.error(f"获取清洗历史失败: {str(e)}", exc_info=True)
			raise

	async def get_cleaning_statistics(
			self,
			data_type: Optional[str] = None,
			days: int = 30
	) -> Dict[str, Any]:
		"""
		获取清洗统计信息

		Args:
			data_type: 数据类型
			days: 统计天数

		Returns:
			Dict: 清洗统计信息
		"""
		try:
			end_date = datetime.now().date()
			start_date = end_date - timedelta(days=days)

			# 构建查询条件并获取清洗记录
			kwargs = {"check_type": "clean"}
			if data_type:
				kwargs["data_type"] = data_type
			clean_tasks = await self.quality_repo.get_many(**kwargs)
			# Post-filter by date range (TODO: add comparison filter support to BaseRepository)
			clean_tasks = [
				t for t in clean_tasks
				if hasattr(t, "check_date") and start_date <= t.check_date <= end_date
			]

			if not clean_tasks:
				return {
					"total_cleans": 0,
					"total_issues": 0,
					"average_issues": 0,
					"rule_distribution": {},
					"trend": []
				}

			# 计算统计信息
			total_cleans = len(clean_tasks)
			total_issues = 0
			rule_distribution = {}

			for task in clean_tasks:
				check_results = task.check_results or {}
				issues = check_results.get("issues", [])
				issue_count = len(issues)
				total_issues += issue_count

				# 统计规则分布
				clean_rules = check_results.get("clean_rules", [])
				for rule in clean_rules:
					rule_distribution[rule] = rule_distribution.get(rule, 0) + 1

			average_issues = total_issues / total_cleans if total_cleans > 0 else 0

			# 时间趋势
			trend = []
			date_groups = {}

			for task in clean_tasks:
				date_str = task.check_date.strftime("%Y-%m-%d") if task.check_date else "unknown"
				if date_str not in date_groups:
					date_groups[date_str] = []

				check_results = task.check_results or {}
				issue_count = len(check_results.get("issues", []))
				date_groups[date_str].append({
					"clean_id": check_results.get("clean_id", str(task.id)),
					"issue_count": issue_count
				})

			for date_str, tasks in sorted(date_groups.items()):
				total_daily_issues = sum(task["issue_count"] for task in tasks)
				trend.append({
					"date": date_str,
					"clean_count": len(tasks),
					"issue_count": total_daily_issues,
					"average_issues": total_daily_issues / len(tasks) if tasks else 0
				})

			return {
				"total_cleans": total_cleans,
				"total_issues": total_issues,
				"average_issues": round(average_issues, 2),
				"rule_distribution": rule_distribution,
				"trend": trend,
				"date_range": {
					"start": start_date.strftime("%Y-%m-%d"),
					"end": end_date.strftime("%Y-%m-%d")
				}
			}

		except Exception as e:
			logger.error(f"获取清洗统计信息失败: {str(e)}", exc_info=True)
			raise

	async def validate_data(
			self,
			data_type: str,
			ts_code: str,
			trade_date: date,
			data: Dict[str, Any],
			validation_rules: Optional[List[str]] = None
	) -> Dict[str, Any]:
		"""
		验证数据

		Args:
			data_type: 数据类型
			ts_code: 股票代码
			trade_date: 交易日期
			data: 待验证数据
			validation_rules: 验证规则列表

		Returns:
			Dict: 验证结果
		"""
		logger.info(f"验证数据，股票: {ts_code}, 日期: {trade_date}")

		try:
			if not validation_rules:
				validation_rules = ["basic", "range", "consistency"]

			validation_results = {}
			validation_errors = []

			# 应用验证规则
			for rule in validation_rules:
				try:
					rule_result = await self._apply_validation_rule(
						rule=rule,
						data_type=data_type,
						data=data
					)

					validation_results[rule] = rule_result

					if not rule_result.get("valid", True):
						validation_errors.extend(rule_result.get("errors", []))

				except Exception as e:
					logger.error(f"应用验证规则 {rule} 失败: {str(e)}")
					validation_results[rule] = {
						"valid": False,
						"error": str(e)
					}
					validation_errors.append(f"规则 {rule} 验证失败: {str(e)}")

			# 生成验证总结
			is_valid = len(validation_errors) == 0

			validation_summary = {
				"valid": is_valid,
				"error_count": len(validation_errors),
				"passed_rules": [rule for rule, result in validation_results.items()
				                 if result.get("valid", False)],
				"failed_rules": [rule for rule, result in validation_results.items()
				                 if not result.get("valid", True)]
			}

			logger.info(f"数据验证完成，股票: {ts_code}, 有效: {is_valid}")

			return {
				"valid": is_valid,
				"validation_results": validation_results,
				"validation_errors": validation_errors,
				"summary": validation_summary
			}

		except Exception as e:
			logger.error(f"数据验证失败: {str(e)}", exc_info=True)
			raise

	# ==================== 私有辅助方法 ====================

	async def _create_clean_task(
			self,
			data_type: str,
			start_date: Optional[date] = None,
			end_date: Optional[date] = None,
			ts_codes: Optional[List[str]] = None,
			clean_rules: Optional[List[str]] = None,
			user_id: Optional[str] = None
	) -> str:
		"""创建清洗任务记录"""
		clean_id = f"clean_{datetime.now().strftime('%Y%m%d_%H%M%S')}"

		# 将清洗任务信息存储在check_results中
		check_results = {
			"clean_id": clean_id,
			"clean_rules": clean_rules or ["default"],
			"start_date": start_date.isoformat() if start_date else None,
			"end_date": end_date.isoformat() if end_date else None,
			"ts_codes": ts_codes,
			"user_id": user_id,
			"issues": [],
			"applied": False
		}

		task_data = {
			"check_type": "clean",
			"data_type": data_type,
			"check_date": datetime.now().date(),
			"status": "running",
			"total_records": 0,
			"valid_records": 0,
			"invalid_records": 0,
			"missing_records": 0,
			"duplicate_records": 0,
			"check_results": check_results,
			"checked_by": f"user_{user_id}" if user_id else "system"
		}

		await self.quality_repo.create_quality_check(**task_data)
		return clean_id

	async def _update_clean_task(
			self,
			clean_id: str,
			status: str,
			error: Optional[str] = None
	):
		"""更新清洗任务状态"""
		# 查找对应的清洗任务
		clean_task = await self.quality_repo.get_by_clean_id(clean_id)
		if clean_task:
			update_data = {
				"status": status,
				"updated_at": datetime.now()
			}

			if status == "completed":
				if clean_task.check_results:
					clean_task.check_results["completed_at"] = datetime.now().isoformat()
				update_data["check_results"] = clean_task.check_results
			elif status == "failed" and error:
				if clean_task.check_results:
					clean_task.check_results["error"] = error
				update_data["check_results"] = clean_task.check_results

			await self.quality_repo.update(clean_task.id, update_data)

	async def _execute_cleaning(
			self,
			data_type: str,
			start_date: Optional[date],
			end_date: Optional[date],
			ts_codes: Optional[List[str]],
			clean_rules: Optional[List[str]],
			clean_id: str,
			user_id: Optional[str] = None
	) -> Dict[str, Any]:
		"""执行数据清洗"""
		if not clean_rules:
			clean_rules = ["missing", "duplicate", "outlier", "inconsistent"]

		issues = []

		# 根据数据类型选择清洗方法
		if data_type == DataType.DAILY_QUOTES:
			# 清洗日行情数据
			for rule in clean_rules:
				try:
					rule_issues = await self._clean_daily_quotes_by_rule(
						rule=rule,
						start_date=start_date,
						end_date=end_date,
						ts_codes=ts_codes
					)

					issues.extend(rule_issues)

					# 更新进度
					progress = (clean_rules.index(rule) + 1) / len(clean_rules) * 100
					await self._update_clean_progress(
						clean_id=clean_id,
						progress=progress,
						current_rule=rule,
						user_id=user_id
					)

				except Exception as e:
					logger.error(f"执行清洗规则 {rule} 失败: {str(e)}")
					issues.append({
						"rule": rule,
						"type": "execution_error",
						"severity": "high",
						"description": f"执行清洗规则失败: {str(e)}"
					})

		elif data_type == DataType.STOCK_LIST:
			# 清洗股票列表数据
			for rule in clean_rules:
				try:
					rule_issues = await self._clean_stock_list_by_rule(rule=rule)
					issues.extend(rule_issues)

				except Exception as e:
					logger.error(f"执行清洗规则 {rule} 失败: {str(e)}")

		# 统计问题分布
		issue_distribution = {}
		for issue in issues:
			issue_type = issue.get("type", "unknown")
			issue_distribution[issue_type] = issue_distribution.get(issue_type, 0) + 1

		# 按严重程度分组
		severity_groups = {}
		for issue in issues:
			severity = issue.get("severity", "medium")
			severity_groups[severity] = severity_groups.get(severity, 0) + 1

		return {
			"data_type": data_type,
			"clean_rules": clean_rules,
			"total_issues": len(issues),
			"issues": issues,
			"issue_distribution": issue_distribution,
			"severity_groups": severity_groups,
			"date_range": {
				"start": start_date.isoformat() if start_date else None,
				"end": end_date.isoformat() if end_date else None
			},
			"cleaned_at": datetime.now().isoformat()
		}

	async def _clean_daily_quotes_by_rule(
			self,
			rule: str,
			start_date: Optional[date],
			end_date: Optional[date],
			ts_codes: Optional[List[str]]
	) -> List[Dict]:
		"""按规则清洗日行情数据"""
		issues = []

		if rule == "missing":
			# 检查缺失数据
			missing_issues = await self._check_missing_data(
				start_date=start_date,
				end_date=end_date,
				ts_codes=ts_codes
			)
			issues.extend(missing_issues)

		elif rule == "duplicate":
			# 检查重复数据
			duplicate_issues = await self._check_duplicate_data(
				start_date=start_date,
				end_date=end_date,
				ts_codes=ts_codes
			)
			issues.extend(duplicate_issues)

		elif rule == "outlier":
			# 检查异常值
			outlier_issues = await self._check_outliers(
				start_date=start_date,
				end_date=end_date,
				ts_codes=ts_codes
			)
			issues.extend(outlier_issues)

		elif rule == "inconsistent":
			# 检查不一致数据
			inconsistent_issues = await self._check_inconsistent_data(
				start_date=start_date,
				end_date=end_date,
				ts_codes=ts_codes
			)
			issues.extend(inconsistent_issues)

		return issues

	async def _check_missing_data(
			self,
			start_date: Optional[date],
			end_date: Optional[date],
			ts_codes: Optional[List[str]]
	) -> List[Dict]:
		"""检查缺失数据"""
		issues = []

		# 设置默认日期范围
		if not end_date:
			end_date = datetime.now().date()
		if not start_date:
			start_date = end_date - timedelta(days=30)

		# 获取要检查的股票列表
		if not ts_codes:
			# 获取股票基础信息Repository
			from shared.database.repositories.market.basic import StockBasicRepository
			stock_repo = StockBasicRepository(self.session)
			stocks = await stock_repo.get_active_stocks()
			ts_codes = [stock.ts_code for stock in stocks]

		for ts_code in ts_codes[:10]:  # 限制检查数量，避免性能问题
			try:
				# 获取该股票的实际数据日期
				actual_dates = await self._get_trade_dates(
					ts_code=ts_code,
					start_date=start_date,
					end_date=end_date
				)

				# 获取交易日历
				trading_days = await self._get_trading_days(start_date, end_date)

				# 找出缺失的交易日
				missing_dates = [
					day for day in trading_days
					if day not in actual_dates
				]

				if missing_dates:
					issues.append({
						"type": "missing",
						"severity": "medium" if len(missing_dates) < 5 else "high",
						"ts_code": ts_code,
						"count": len(missing_dates),
						"description": f"股票 {ts_code} 缺失 {len(missing_dates)} 个交易日的行情数据",
						"dates": [d.isoformat() for d in missing_dates[:10]],  # 只显示前10个日期
						"date_range": {
							"start": start_date.isoformat(),
							"end": end_date.isoformat()
						}
					})

			except Exception as e:
				logger.error(f"检查股票 {ts_code} 缺失数据失败: {str(e)}")
				continue

		return issues

	async def _check_duplicate_data(
			self,
			start_date: Optional[date],
			end_date: Optional[date],
			ts_codes: Optional[List[str]]
	) -> List[Dict]:
		"""检查重复数据"""
		issues = []

		for ts_code in (ts_codes or [])[:10]:  # 限制检查数量
			try:
				duplicate_records = await self._find_duplicate_records(
					ts_code=ts_code,
					start_date=start_date,
					end_date=end_date
				)

				if duplicate_records:
					issues.append({
						"type": "duplicate",
						"severity": "low" if len(duplicate_records) < 3 else "medium",
						"ts_code": ts_code,
						"count": len(duplicate_records),
						"description": f"股票 {ts_code} 有 {len(duplicate_records)} 条重复记录",
						"records": [
							{"trade_date": record.trade_date.isoformat()}
							for record in duplicate_records[:5]
						]
					})

			except Exception as e:
				logger.error(f"检查股票 {ts_code} 重复数据失败: {str(e)}")
				continue

		return issues

	async def _check_outliers(
			self,
			start_date: Optional[date],
			end_date: Optional[date],
			ts_codes: Optional[List[str]]
	) -> List[Dict]:
		"""检查异常值"""
		issues = []

		for ts_code in (ts_codes or [])[:10]:  # 限制检查数量
			try:
				# 获取股票的历史数据
				quotes = await self._get_by_ts_code_date_range(
					ts_code=ts_code,
					start_date=start_date,
					end_date=end_date
				)

				if not quotes:
					continue

				# 计算价格变动百分比
				price_changes = []
				outlier_dates = []

				for i in range(1, len(quotes)):
					prev_close = float(quotes[i - 1].close) if quotes[i - 1].close else 0
					curr_close = float(quotes[i].close) if quotes[i].close else 0

					if prev_close > 0:
						pct_change = abs((curr_close - prev_close) / prev_close) * 100
						price_changes.append(pct_change)

						# 如果变动超过阈值，标记为异常
						if pct_change > 20:  # 20%的阈值
							outlier_dates.append(quotes[i].trade_date)

				if outlier_dates:
					issues.append({
						"type": "outlier",
						"severity": "medium" if len(outlier_dates) < 3 else "high",
						"ts_code": ts_code,
						"count": len(outlier_dates),
						"description": f"股票 {ts_code} 有 {len(outlier_dates)} 个异常价格变动",
						"dates": [d.isoformat() for d in outlier_dates[:5]],
						"threshold": "20%",
						"max_change": max(price_changes) if price_changes else 0
					})

			except Exception as e:
				logger.error(f"检查股票 {ts_code} 异常值失败: {str(e)}")
				continue

		return issues

	async def _check_inconsistent_data(
			self,
			start_date: Optional[date],
			end_date: Optional[date],
			ts_codes: Optional[List[str]]
	) -> List[Dict]:
		"""检查不一致数据"""
		issues = []

		for ts_code in (ts_codes or [])[:10]:  # 限制检查数量
			try:
				inconsistent_records = await self._find_inconsistent_records(
					ts_code=ts_code,
					start_date=start_date,
					end_date=end_date
				)

				if inconsistent_records:
					issues.append({
						"type": "inconsistent",
						"severity": "high",
						"ts_code": ts_code,
						"count": len(inconsistent_records),
						"description": f"股票 {ts_code} 有 {len(inconsistent_records)} 条不一致记录",
						"records": [
							{
								"trade_date": record.trade_date.isoformat(),
								"issue": "数据逻辑不一致（如最高价低于最低价）"
							}
							for record in inconsistent_records[:5]
						]
					})

			except Exception as e:
				logger.error(f"检查股票 {ts_code} 不一致数据失败: {str(e)}")
				continue

		return issues

	async def _clean_stock_list_by_rule(
			self,
			rule: str
	) -> List[Dict]:
		"""按规则清洗股票列表数据"""
		issues = []

		if rule == "invalid_symbol":
			# 检查无效的股票代码
			invalid_stocks = await self._check_invalid_stock_symbols()
			if invalid_stocks:
				issues.append({
					"type": "invalid_symbol",
					"severity": "medium",
					"count": len(invalid_stocks),
					"description": f"发现 {len(invalid_stocks)} 个无效股票代码",
					"stocks": invalid_stocks[:10]
				})

		elif rule == "missing_info":
			# 检查缺失的必要信息
			stocks_missing_info = await self._check_missing_stock_info()
			if stocks_missing_info:
				issues.append({
					"type": "missing_info",
					"severity": "low",
					"count": len(stocks_missing_info),
					"description": f"发现 {len(stocks_missing_info)} 只股票缺失必要信息",
					"stocks": stocks_missing_info[:10]
				})

		return issues

	@staticmethod
	async def _check_invalid_stock_symbols(
		df: "pd.DataFrame", df_columns: Optional[List[str]] = None
	) -> List[Dict]:
		"""检查无效的股票代码 — 基于正则格式校验 + 数据库二次验证

		Args:
			df: 待检查的 DataFrame
			df_columns: DataFrame 的列名列表，为 None 时自动从 df.columns 获取
		"""
		import re
		from shared.database.session import get_session_manager
		from sqlalchemy import text

		if df_columns is None:
			columns_list = list(df.columns)
		else:
			columns_list = list(df_columns)

		if not columns_list:
			return []

		# 识别证券代码列
		ts_code_col = None
		for col in columns_list:
			if "ts_code" in col.lower() or "code" in col.lower() or "symbol" in col.lower():
				ts_code_col = col
				break

		if not ts_code_col:
			return []  # 非数据同步流程，跳过；若为行情数据则需调整 col 名检测逻辑

		# 格式校验：{数字6位}.{SZ|SH|BJ}
		symbol_pattern = re.compile(r"^\d{6}\.(SZ|SH|BJ)$")
		# 整表去重后集中验证，上限 5000 避免查询过大
		codes_to_check = df[ts_code_col].dropna().drop_duplicates().head(5000).tolist()
		if not codes_to_check:
			return []

		invalid_format = [
			{"ts_code": c, "reason": "格式不符合 {6位数字}.{SZ|SH|BJ}"}
			for c in codes_to_check if not symbol_pattern.match(str(c))
		]

		# 数据库二次验证：检查是否存在于 stocks 表
		valid_format_codes = [c for c in codes_to_check if symbol_pattern.match(str(c))]
		db_invalid = []
		if valid_format_codes:
			try:
				session_manager = get_session_manager()
				async with session_manager.get_session() as session:
					result = await session.execute(
						text("SELECT ts_code FROM stocks WHERE ts_code = ANY(:codes)"),
						{"codes": valid_format_codes}
					)
					existing = {row.ts_code for row in result.fetchall()}
					db_invalid = [
						{"ts_code": c, "reason": "数据库中不存在该证券代码"}
						for c in valid_format_codes if c not in existing
					]
			except Exception as e:
				logger.warning(f"数据库股票代码验证失败，仅保留格式检查结果: {e}")

		return invalid_format + db_invalid

	async def _check_missing_stock_info(self) -> List[Dict]:
		"""检查缺失的股票信息"""
		issues = []

		try:
			# 获取股票基础信息Repository
			from shared.database.repositories.market.basic import StockBasicRepository
			stock_repo = StockBasicRepository(self.session)

			# 获取缺少必要信息的股票
			stocks = await stock_repo.get_many(
				or_(
					stock_repo.model.name.is_(None),
					stock_repo.model.market.is_(None),
					stock_repo.model.list_date.is_(None)
				),
				limit=50
			)

			for stock in stocks:
				missing_fields = []

				if not stock.name:
					missing_fields.append("name")
				if not stock.market:
					missing_fields.append("market")
				if not stock.list_date:
					missing_fields.append("list_date")

				if missing_fields:
					issues.append({
						"ts_code": stock.ts_code,
						"missing_fields": missing_fields
					})

		except Exception as e:
			logger.error(f"检查缺失股票信息失败: {str(e)}")

		return issues

	async def _get_trading_days(
			self,
			start_date: date,
			end_date: date
	) -> List[date]:
		"""获取交易日列表"""
		try:
			# 从数据库获取交易日历
			trading_days = await self._get_trading_days_from_db()

			if not trading_days:
				# 如果数据库中没有，使用工具类生成
				if self.trading_calendar is None:
					from utils.core_utils.time_utils.trading_calendar import TradingCalendar
					self.trading_calendar = TradingCalendar()

				trading_days = self.trading_calendar.get_trading_days(start_date, end_date)

			return trading_days

		except Exception as e:
			logger.error(f"获取交易日列表失败: {str(e)}")
			# 返回一个近似的交易日列表
			return self._generate_approximate_trading_days(start_date, end_date)

	@staticmethod
	async def _get_trading_days_from_db() -> List[date]:
		"""从数据库获取交易日历"""
		# 这里需要实现从数据库查询交易日历的逻辑
		# 根据架构设计，交易日历表在shared.database.repositories.market.reference
		# 暂时返回空列表，表示需要实现
		return []

	@staticmethod
	def _generate_approximate_trading_days(start_date: date, end_date: date) -> List[date]:
		"""生成近似的交易日列表（含节假日过滤）"""
		trading_days = []
		current_date = start_date

		# 中国主要节假日（月 → 日集合），覆盖元旦/春节/清明/劳动/端午/中秋/国庆
		holidays_by_month = {
			1: {1, 2, 3},  # 元旦 + 春节近似
			4: {4, 5},  # 清明节
			5: {1, 2, 3},  # 劳动节
			6: {(5, 10), (15, 20)},  # 端午节(农历,用中旬近似)
			9: {(10, 15), (20, 25)},  # 中秋节(农历,用中下旬近似)
			10: {1, 2, 3, 4, 5, 6, 7},  # 国庆节
		}

		def _is_holiday(d: date) -> bool:
			m, day = d.month, d.day
			candidates = holidays_by_month.get(m, set())
			for c in candidates:
				if isinstance(c, int) and day == c:
					return True
				if isinstance(c, tuple) and c[0] <= day <= c[1]:
					return True
			return False

		while current_date <= end_date:
			# 周一到周五 且 非法定节假日
			if current_date.weekday() < 5 and not _is_holiday(current_date):
				trading_days.append(current_date)

			current_date += timedelta(days=1)

		return trading_days

	async def _update_clean_progress(
			self,
			clean_id: str,
			progress: float,
			current_rule: str,
			user_id: Optional[str] = None
	):
		"""更新清洗进度"""
		# 缓存进度信息
		progress_key = f"clean:progress:{clean_id}"
		progress_data = {
			"progress": str(progress),  # 转换为字符串
			"current_rule": current_rule,
			"updated_at": datetime.now().isoformat()
		}

		# 使用set方法，确保传递正确的类型
		await self.cache.set(
			progress_key,
			json.dumps(progress_data),  # 转换为JSON字符串
			ttl=3600
		)

		# 发布进度事件
		await self._publish_clean_event(
			event_type="progress",
			clean_id=clean_id,
			progress=progress,
			current_rule=current_rule,
			user_id=user_id
		)

	async def _save_clean_result(
			self,
			clean_id: str,
			result: Dict[str, Any]
	):
		"""保存清洗结果"""
		# 查找对应的清洗任务
		clean_task = await self.quality_repo.get_by_clean_id(clean_id)
		if clean_task:
			# 更新check_results
			if clean_task.check_results:
				clean_task.check_results.update({
					"result": result,
					"duration_seconds": (
							datetime.now() - clean_task.created_at).total_seconds() if clean_task.created_at else 0,
					"completed_at": datetime.now().isoformat()
				})

			update_data = {
				"status": "completed",
				"check_results": clean_task.check_results,
				"total_records": result.get("total_issues", 0),
				"valid_records": result.get("total_issues", 0) - len(result.get("issues", [])),
				"invalid_records": len(result.get("issues", []))
			}

			await self.quality_repo.update(clean_task.id, update_data)

	async def _apply_cleaning_results(
			self,
			clean_id: str,
			user_id: Optional[str] = None
	) -> Dict[str, Any]:
		"""应用清洗结果"""
		return await self.apply_cleaning_results(
			clean_id=clean_id,
			apply_rules=None,
			dry_run=False,
			user_id=user_id
		)

	async def _apply_single_issue(
			self,
			issue: Dict,
			data_type: str
	) -> bool:
		"""应用单个清洗问题"""
		issue_type = issue.get("type")

		try:
			if issue_type == "missing" and data_type == DataType.DAILY_QUOTES:
				# 修复缺失数据
				return await self._fix_missing_quotes(issue)

			elif issue_type == "duplicate" and data_type == DataType.DAILY_QUOTES:
				# 修复重复数据
				return await self._fix_duplicate_quotes(issue)

			elif issue_type == "outlier" and data_type == DataType.DAILY_QUOTES:
				# 修复异常值
				return await self._fix_outlier_quotes(issue)

			else:
				logger.warning(f"不支持的应用类型: {issue_type} for {data_type}")
				return False

		except Exception as e:
			logger.error(f"应用清洗问题失败: {str(e)}")
			return False

	@staticmethod
	async def _fix_missing_quotes(issue: Dict) -> bool:
		"""修复缺失的行情数据 — 前向填充缺失记录"""
		try:
			from shared.database.session import get_session_manager
			from sqlalchemy import text

			ts_code = issue.get("ts_code")
			missing_dates = issue.get("dates", [])
			if not ts_code or not missing_dates:
				return False

			fixed = 0
			session_manager = get_session_manager()
			async with session_manager.get_session() as session:
				for trade_date in missing_dates:
					# 获取前一个交易日的数据进行前向填充
					result = await session.execute(
						text(
							"SELECT open, high, low, close, pre_close, vol, amount "
							"FROM daily_quotes WHERE ts_code = :code AND trade_date < :td "
							"ORDER BY trade_date DESC LIMIT 1"
						),
						{"code": ts_code, "td": trade_date}
					)
					prev_row = result.fetchone()
					if not prev_row:
						continue

					# 插入填充记录
					await session.execute(
						text(
							"INSERT INTO daily_quotes (ts_code, trade_date, open, high, low, close, "
							"pre_close, vol, amount, is_restored) "
							"VALUES (:code, :td, :o, :h, :l, :c, :pc, :v, :a, 1) "
							"ON CONFLICT (ts_code, trade_date) DO NOTHING"
						),
						{
							"code": ts_code, "td": trade_date,
							"o": prev_row.open, "h": prev_row.high, "l": prev_row.low,
							"c": prev_row.close, "pc": prev_row.pre_close,
							"v": 0, "a": 0
						}
					)
					fixed += 1
				await session.commit()
			logger.info(f"前向填充 {ts_code} 缺失数据 {fixed} 条")
			return fixed > 0
		except Exception as e:
			logger.error(f"修复缺失行情数据失败: {e}")
			return False

	@staticmethod
	async def _fix_duplicate_quotes(issue: Dict) -> bool:
		"""修复重复的行情数据 — 保留成交量最大的一条，删除其余"""
		try:
			from shared.database.session import get_session_manager
			from sqlalchemy import text

			ts_code = issue.get("ts_code")
			records = issue.get("records", [])
			if not ts_code or not records:
				return False

			dup_dates = [r.get("trade_date") for r in records if r.get("trade_date")]
			if not dup_dates:
				return False

			fixed = 0
			session_manager = get_session_manager()
			async with session_manager.get_session() as session:
				for trade_date in dup_dates:
					# 保留成交量最大的记录，删除其余
					await session.execute(
						text(
							"DELETE FROM daily_quotes WHERE ts_code = :code AND trade_date = :td "
							"AND id NOT IN ("
							"  SELECT id FROM daily_quotes WHERE ts_code = :code2 AND trade_date = :td2 "
							"  ORDER BY vol DESC NULLS LAST LIMIT 1"
							")"
						),
						{"code": ts_code, "td": trade_date, "code2": ts_code, "td2": trade_date}
					)
					fixed += 1
				await session.commit()
			logger.info(f"去重 {ts_code} {len(dup_dates)} 个日期")
			return fixed > 0
		except Exception as e:
			logger.error(f"修复重复行情数据失败: {e}")
			return False

	@staticmethod
	async def _fix_outlier_quotes(issue: Dict) -> bool:
		"""修复异常值 — 基于Z-Score检测并用前值替换离群收盘价"""
		try:
			from shared.database.session import get_session_manager
			from sqlalchemy import text
			import numpy as np

			ts_code = issue.get("ts_code")
			outlier_dates = issue.get("dates", [])
			if not ts_code or not outlier_dates:
				return False

			fixed = 0
			session_manager = get_session_manager()
			async with session_manager.get_session() as session:
				# 获取该股票最近60天的收盘价序列
				result = await session.execute(
					text(
						"SELECT trade_date, close FROM daily_quotes "
						"WHERE ts_code = :code ORDER BY trade_date DESC LIMIT 60"
					),
					{"code": ts_code}
				)
				rows = result.fetchall()
				closes = [float(row.close) for row in rows if row.close and row.close > 0]
				if len(closes) < 10:
					return False

				# 计算Z-Score
				mean_c = np.mean(closes)
				std_c = np.std(closes, ddof=1)
				if std_c == 0:
					return False

				for trade_date in outlier_dates:
					# 获取当日收盘价
					current = next((float(row.close) for row in rows if str(row.trade_date) == str(trade_date)), None)
					if current is None:
						continue

					z_score = abs(current - mean_c) / std_c
					if z_score < 3.0:
						continue

					# 用前一日收盘价替换
					prev_close = closes[0] if closes[0] != current else (closes[1] if len(closes) > 1 else None)
					if prev_close is None:
						continue

					await session.execute(
						text(
							"UPDATE daily_quotes SET close = :pc, is_restored = 1 "
							"WHERE ts_code = :code AND trade_date = :td"
						),
						{"pc": prev_close, "code": ts_code, "td": trade_date}
					)
					fixed += 1
				await session.commit()
			logger.warning(f"修正 {ts_code} 异常收盘价 {fixed} 条")
			return fixed > 0
		except Exception as e:
			logger.error(f"修复异常值失败: {e}")
			return False

	@staticmethod
	async def _create_apply_record(
			apply_id: str,
			clean_id: str,
			data_type: str,
			dry_run: bool,
			total_issues: int,
			applied_count: int,
			failed_applications: List[Dict],
			user_id: Optional[str] = None
	):
		"""创建应用记录 — 持久化到 data_quality_checks 表"""
		apply_data = {
			"apply_id": apply_id,
			"clean_id": clean_id,
			"data_type": data_type,
			"status": "completed",
			"user_id": user_id,
			"dry_run": dry_run,
			"total_issues": total_issues,
			"applied_count": applied_count,
			"failed_applications": failed_applications,
			"created_at": datetime.now().isoformat(),
			"completed_at": datetime.now().isoformat()
		}

		try:
			from shared.database.session import get_session_manager
			from shared.database.repositories.analysis.factor.data_quality_check_repo import DataQualityCheckRepository
			session_manager = get_session_manager()
			async with session_manager.get_session() as session:
				quality_repo = DataQualityCheckRepository(session)
				await quality_repo.create_quality_check(
					check_type="apply",
					data_type=data_type,
					check_date=datetime.now().date(),
					status="completed",
					total_records=total_issues,
					valid_records=applied_count,
					invalid_records=len(failed_applications),
					check_results=apply_data,
					checked_by=f"user_{user_id}" if user_id else "system"
				)
			logger.info(f"已持久化应用记录: {apply_id}, 应用 {applied_count}/{total_issues}")
		except Exception as e:
			logger.warning(f"持久化应用记录失败: {e}, 降级为日志")
			logger.info(f"应用记录(降级): {apply_data}")

	@staticmethod
	async def _clean_cache_after_cleaning(data_type: str):
		"""清洗后清理相关缓存"""
		cache_key_prefix = {
			"daily_quotes": "daily_quotes",
			"stock_list": "stock_list",
		}.get(data_type, data_type)

		if not cache_key_prefix:
			logger.debug("未提供缓存前缀，跳过缓存清理")
			return

		try:
			from shared.cache.redis_cache import RedisCache
			cache = RedisCache()
			pattern = f"{cache_key_prefix}:*"
			deleted = await cache.delete_pattern(pattern)
			if deleted > 0:
				logger.info(f"清洗后缓存已清理: pattern={pattern}, 删除 {deleted} 个键")
			else:
				logger.debug(f"无匹配缓存需要清理: pattern={pattern}")
		except Exception as e:
			logger.warning(f"缓存清理失败: {e}")

	async def _apply_validation_rule(
			self,
			rule: str,
			data_type: str,
			data: Dict[str, Any]
	) -> Dict[str, Any]:
		"""应用验证规则"""
		if rule == "basic":
			return await self._validate_basic(data_type, data)
		elif rule == "range":
			return await self._validate_range(data_type, data)
		elif rule == "consistency":
			return await self._validate_consistency(data_type, data)
		else:
			return {
				"valid": True,
				"note": f"规则 {rule} 未实现"
			}

	@staticmethod
	async def _validate_basic(
			data_type: str,
			data: Dict[str, Any]
	) -> Dict[str, Any]:
		"""验证基本数据"""
		errors = []

		# 检查必要字段是否存在
		required_fields = {
			"daily_quotes": ["open", "high", "low", "close", "vol"],
			"stock_list": ["name", "market", "list_date"]
		}

		required = required_fields.get(data_type, [])
		for field in required:
			if field not in data or data[field] is None:
				errors.append(f"缺少必要字段: {field}")

		# 检查数据格式
		for field, value in data.items():
			if value is not None:
				if field in ["open", "high", "low", "close"]:
					if not isinstance(value, (int, float)):
						errors.append(f"字段 {field} 必须是数值类型")
					elif value <= 0:
						errors.append(f"字段 {field} 必须大于0")
				elif field == "vol":
					if not isinstance(value, (int, float)):
						errors.append(f"字段 {field} 必须是数值类型")
					elif value < 0:
						errors.append(f"字段 {field} 不能为负数")

		return {
			"valid": len(errors) == 0,
			"errors": errors,
			"checked_fields": list(data.keys())
		}

	@staticmethod
	async def _validate_range(
			data_type: str,
			data: Dict[str, Any]
	) -> Dict[str, Any]:
		"""验证数据范围"""
		errors = []

		if data_type == DataType.DAILY_QUOTES:
			# 验证价格范围
			open_price = data.get("open")
			high_price = data.get("high")
			low_price = data.get("low")
			close_price = data.get("close")

			if all(v is not None for v in [open_price, high_price, low_price, close_price]):
				# 检查价格逻辑
				if high_price < low_price:
					errors.append("最高价不能低于最低价")

				if not (low_price <= open_price <= high_price):
					errors.append("开盘价必须在最高价和最低价之间")

				if not (low_price <= close_price <= high_price):
					errors.append("收盘价必须在最高价和最低价之间")

				# 检查涨跌幅合理性
				pre_close = data.get("pre_close")
				if pre_close and close_price:
					pct_change = abs((close_price - pre_close) / pre_close) * 100
					if pct_change > 20:  # 超过20%的变动需要特别关注
						errors.append(f"价格变动过大: {pct_change:.2f}%")

		return {
			"valid": len(errors) == 0,
			"errors": errors
		}

	@staticmethod
	async def _validate_consistency(
			data_type: str,
			data: Dict[str, Any]
	) -> Dict[str, Any]:
		"""验证数据一致性"""
		errors = []

		if data_type == DataType.DAILY_QUOTES:
			# 检查成交额和成交量的关系
			amount = data.get("amount")
			vol = data.get("vol")
			close_price = data.get("close")

			if all(v is not None for v in [amount, vol, close_price]) and vol > 0:
				# 估算平均成交价
				estimated_avg_price = amount / (vol * 100)  # vol通常是手数，需要乘以100
				# 检查平均成交价与收盘价的差异是否过大
				if abs(estimated_avg_price - close_price) / close_price > 0.5:
					errors.append("成交均价与收盘价差异过大")

		return {
			"valid": len(errors) == 0,
			"errors": errors
		}

	async def _publish_clean_event(
			self,
			event_type: str,
			clean_id: str,
			data_type: Optional[str] = None,
			progress: Optional[float] = None,
			current_rule: Optional[str] = None,
			result: Optional[Dict] = None,
			applied_count: Optional[int] = None,
			apply_id: Optional[str] = None,
			dry_run: Optional[bool] = None,
			user_id: Optional[str] = None
	):
		"""发布清洗事件"""
		if not self.event_engine:
			return

		event_data = {
			"clean_id": clean_id,
			"user_id": user_id,
			"timestamp": datetime.now().isoformat()
		}

		if data_type:
			event_data["data_type"] = data_type
		if progress is not None:
			event_data["progress"] = str(progress)
		if current_rule:
			event_data["current_rule"] = current_rule
		if result:
			event_data["result"] = json.dumps(result)
		if applied_count is not None:
			event_data["applied_count"] = str(applied_count)
		if apply_id:
			event_data["apply_id"] = apply_id
		if dry_run is not None:
			event_data["dry_run"] = str(dry_run)

		event = DataCleanEvent(
			event_type=f"events.clean.{event_type}",
			**event_data
		)

		await self.event_engine.put(event)

	# ==================== 添加缺失的Repository方法 ====================

	async def _get_trade_dates(
			self,
			ts_code: str,
			start_date: Optional[date] = None,
			end_date: Optional[date] = None
	) -> List[date]:
		"""获取交易日期列表"""
		try:
			# 使用Repository的基础查询方法
			query = select(self.daily_quote_repo.model.trade_date).where(
				self.daily_quote_repo.model.ts_code == ts_code
			)

			if start_date:
				query = query.where(self.daily_quote_repo.model.trade_date >= start_date)  # type: ignore[arg-type]
			if end_date:
				query = query.where(self.daily_quote_repo.model.trade_date <= end_date)  # type: ignore[arg-type]

			query = query.order_by(self.daily_quote_repo.model.trade_date)
			result = await self.session.execute(query)

			return [record.trade_date for record in result.scalars().all() if record.trade_date]
		except Exception as e:
			logger.error(f"获取交易日期失败: {str(e)}")
			return []

	async def _find_duplicate_records(
			self,
			ts_code: str,
			start_date: Optional[date] = None,
			end_date: Optional[date] = None
	) -> List[Any]:
		"""查找重复记录"""
		try:
			# 查找同一日期有多个记录的
			# 构建子查询
			from sqlalchemy import and_

			# 首先构建基础查询
			base_query = select(
				self.daily_quote_repo.model.trade_date,
				func.count().label('count')
			).where(
				self.daily_quote_repo.model.ts_code == ts_code
			).group_by(
				self.daily_quote_repo.model.trade_date
			).having(
				func.count() > 1  # type: ignore[arg-type]
			)

			# 执行子查询
			duplicate_dates_result = await self.session.execute(base_query)
			duplicate_dates = [row[0] for row in duplicate_dates_result.all()]

			# 如果没有重复日期，返回空列表
			if not duplicate_dates:
				return []

			# 构建主查询
			query = select(self.daily_quote_repo.model).where(
				self.daily_quote_repo.model.ts_code == ts_code,
				self.daily_quote_repo.model.trade_date.in_(duplicate_dates)
			)

			if start_date:
				query = query.where(self.daily_quote_repo.model.trade_date >= start_date)  # type: ignore[arg-type]
			if end_date:
				query = query.where(self.daily_quote_repo.model.trade_date <= end_date)  # type: ignore[arg-type]

			result = await self.session.execute(query)
			return list(result.scalars().all())
		except Exception as e:
			logger.error(f"查找重复记录失败: {str(e)}")
			return []

	async def _get_by_ts_code_date_range(
			self,
			ts_code: str,
			start_date: Optional[date] = None,
			end_date: Optional[date] = None
	) -> List[Any]:
		"""按股票代码和日期范围获取数据"""
		try:
			query = select(self.daily_quote_repo.model).where(
				self.daily_quote_repo.model.ts_code == ts_code
			)

			if start_date:
				query = query.where(self.daily_quote_repo.model.trade_date >= start_date)  # type: ignore[arg-type]
			if end_date:
				query = query.where(self.daily_quote_repo.model.trade_date <= end_date)  # type: ignore[arg-type]

			query = query.order_by(self.daily_quote_repo.model.trade_date)
			result = await self.session.execute(query)
			return list(result.scalars().all())
		except Exception as e:
			logger.error(f"按日期范围获取数据失败: {str(e)}")
			return []

	async def _find_inconsistent_records(
			self,
			ts_code: str,
			start_date: Optional[date] = None,
			end_date: Optional[date] = None
	) -> List[Any]:
		"""查找不一致记录"""
		try:
			query = select(self.daily_quote_repo.model).where(
				self.daily_quote_repo.model.ts_code == ts_code
			)

			if start_date:
				query = query.where(self.daily_quote_repo.model.trade_date >= start_date)  # type: ignore[arg-type]
			if end_date:
				query = query.where(self.daily_quote_repo.model.trade_date <= end_date)  # type: ignore[arg-type]

			# 查找逻辑不一致的 记录（如最高价低于最低价）
			query = query.where(
				or_(
					self.daily_quote_repo.model.high < self.daily_quote_repo.model.low,
					self.daily_quote_repo.model.open > self.daily_quote_repo.model.high,
					self.daily_quote_repo.model.open < self.daily_quote_repo.model.low,
					self.daily_quote_repo.model.close > self.daily_quote_repo.model.high,
					self.daily_quote_repo.model.close < self.daily_quote_repo.model.low
				)
			)

			result = await self.session.execute(query)
			return list(result.scalars().all())
		except Exception as e:
			logger.error(f"查找不一致记录失败: {str(e)}")
			return []
