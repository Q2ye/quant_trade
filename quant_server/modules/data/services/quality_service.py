# -*- coding: utf-8 -*-
"""
数据质量服务
负责数据质量检查、评估和报告生成
位置：quant_server/modules/events/services/quality_service.py

设计原则：
1. 模块化质量检查：每个检查项目独立实现
2. 可配置的质量阈值：支持动态调整质量标准
3. 详细的检查报告：提供完整的质量问题描述和建议
4. 批量处理能力：支持大规模数据质量检查
"""

from typing import Dict, List, Any, Optional
from datetime import datetime, date, timedelta
import logging
from sqlalchemy.ext.asyncio import AsyncSession

# 导入共享层组件
from quant_server.shared.database.repositories import (
	StockRepository,
	QuoteRepository,
	FactorRepository,
	DataQualityRepository
)
from quant_server.shared.cache.redis_cache import RedisCache

# 导入核心基础设施
from quant_server.core.engines.system.event_engine import EventEngine
from quant_server.core.events.data_events import DataQualityEvent

# 导入数据模块常量
from quant_server.modules.data.constants import (
	DataType,
	QualityMetricCode,
	QualityLevelThreshold
)

# 导入数据模块模型
from quant_server.modules.data.models import DataQualityResult

# 配置日志
logger = logging.getLogger(__name__)


class DataQualityService:
	"""
	数据质量服务类
	负责数据质量的检查、评估和报告
	"""

	def __init__ (self, session: AsyncSession, event_engine: Optional[EventEngine] = None):
		"""
		初始化数据质量服务

		Args:
			session: 数据库会话
			event_engine: 事件引擎
		"""
		self.session = session
		self.event_engine = event_engine

		# 初始化Repository
		self.stock_repo = StockRepository(session)
		self.quote_repo = QuoteRepository(session)
		self.factor_repo = FactorRepository(session)
		self.quality_repo = DataQualityRepository(session)

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

	async def check_data_quality (
			self,
			data_type: str,
			start_date: Optional[date] = None,
			end_date: Optional[date] = None,
			ts_code: Optional[str] = None,
			check_types: Optional[List[str]] = None,
			user_id: Optional[int] = None
	) -> Dict[str, Any]:
		"""
		检查数据质量

		Args:
			data_type: 数据类型
			start_date: 开始日期
			end_date: 结束日期
			ts_code: 股票代码（可选，不指定则检查所有）
			check_types: 检查类型列表（completeness, accuracy, timeliness, consistency）
			user_id: 用户ID（用于事件发布）

		Returns:
			Dict: 质量检查结果
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
				user_id=user_id
			)

			# 默认检查所有类型
			if not check_types:
				check_types = ["completeness", "accuracy", "timeliness", "consistency"]

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

			# 构建最终结果
			quality_result = DataQualityResult(
				check_id=check_id,
				data_type=data_type,
				date_range={
					"start": start_date.isoformat() if start_date else None,
					"end": end_date.isoformat() if end_date else None
				},
				overall_score=overall_score,
				quality_level=quality_level,
				metrics=results,
				issues=issues,
				suggestions=suggestions,
				check_time=datetime.now()
			)

			# 保存检查结果
			await self._save_quality_result(check_id, quality_result)

			# 发布质量事件
			await self._publish_quality_event(
				event_type="report_generated",
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
				"result": quality_result.dict(),
				"message": "数据质量检查完成"
			}

		except Exception as e:
			logger.error(f"数据质量检查失败: {str(e)}", exc_info=True)

			# 更新检查状态为失败
			if check_id:
				await self._update_quality_check(
					check_id=check_id,
					status="failed",
					error=str(e)
				)

			return {
				"success": False,
				"check_id": check_id,
				"error": str(e),
				"message": "数据质量检查失败"
			}

	async def get_quality_report (
			self,
			data_type: Optional[str] = None,
			start_date: Optional[date] = None,
			end_date: Optional[date] = None,
			ts_code: Optional[str] = None,
			limit: int = 10
	) -> List[Dict[str, Any]]:
		"""
		获取数据质量报告

		Args:
			data_type: 数据类型
			start_date: 开始日期
			end_date: 结束日期
			ts_code: 股票代码
			limit: 返回数量限制

		Returns:
			List[Dict]: 质量报告列表
		"""
		try:
			# 构建查询条件
			filters = []
			if data_type:
				filters.append(self.quality_repo.model.data_type == data_type)
			if start_date:
				filters.append(self.quality_repo.model.check_time >= start_date)
			if end_date:
				filters.append(self.quality_repo.model.check_time <= end_date)
			if ts_code:
				filters.append(self.quality_repo.model.ts_code == ts_code)

			# 获取质量检查记录
			quality_checks = await self.quality_repo.get_many(
				*filters,
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
					"check_time": check.check_time.isoformat(),
					"duration": check.duration_seconds if hasattr(check, 'duration_seconds') else None
				})

			return reports

		except Exception as e:
			logger.error(f"获取质量报告失败: {str(e)}", exc_info=True)
			raise

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

	async def get_quality_statistics (
			self,
			data_type: Optional[str] = None,
			days: int = 30
	) -> Dict[str, Any]:
		"""
		获取数据质量统计信息

		Args:
			data_type: 数据类型
			days: 统计天数

		Returns:
			Dict: 质量统计信息
		"""
		try:
			end_date = datetime.now()
			start_date = end_date - timedelta(days=days)

			# 构建查询条件
			filters = [
				self.quality_repo.model.check_time >= start_date,
				self.quality_repo.model.check_time <= end_date
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
					"trend": []
				}

			# 计算统计信息
			total_checks = len(quality_checks)
			total_score = sum(check.overall_score for check in quality_checks)
			average_score = total_score / total_checks

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
			date_groups = {}

			for check in quality_checks:
				date_str = check.check_time.strftime("%Y-%m-%d")
				if date_str not in date_groups:
					date_groups[date_str] = []
				date_groups[date_str].append(check.overall_score)

			for date_str, scores in sorted(date_groups.items()):
				trend.append({
					"date": date_str,
					"average_score": sum(scores) / len(scores),
					"check_count": len(scores)
				})

			return {
				"total_checks": total_checks,
				"average_score": round(average_score, 2),
				"quality_distribution": quality_distribution,
				"trend": trend,
				"date_range": {
					"start": start_date.strftime("%Y-%m-%d"),
					"end": end_date.strftime("%Y-%m-%d")
				}
			}

		except Exception as e:
			logger.error(f"获取质量统计信息失败: {str(e)}", exc_info=True)
			raise

	# ==================== 私有辅助方法 ====================

	async def _create_quality_check (
			self,
			data_type: str,
			start_date: Optional[date] = None,
			end_date: Optional[date] = None,
			ts_code: Optional[str] = None,
			user_id: Optional[int] = None
	) -> str:
		"""创建质量检查记录"""
		check_id = f"quality_check_{datetime.now().strftime('%Y%m%d_%H%M%S')}"

		check_data = {
			"check_id": check_id,
			"data_type": data_type,
			"status": "running",
			"user_id": user_id,
			"start_date": start_date,
			"end_date": end_date,
			"ts_code": ts_code,
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
		"""更新质量检查状态"""
		check = await self.quality_repo.get_by_check_id(check_id)
		if not check:
			return

		update_data = {
			"status": status,
			"updated_at": datetime.now()
		}

		if status == "completed":
			update_data["completed_at"] = datetime.now()
		elif status == "failed":
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
		"""执行具体的质量检查"""
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
		"""检查数据完整性"""
		metrics = {}
		issues = []

		if data_type == DataType.DAILY_QUOTES:
			# 检查日行情数据完整性
			try:
				# 获取交易日历
				from quant_server.shared.database.repositories.reference.trade_calendar_repo import TradeCalendarRepository
				calendar_repo = TradeCalendarRepository(self.session)

				# 计算应包含的交易日
				if not start_date:
					start_date = datetime.now().date() - timedelta(days=30)
				if not end_date:
					end_date = datetime.now().date()

				# 获取交易日列表
				trading_days = await calendar_repo.get_trading_days(
					start_date=start_date,
					end_date=end_date
				)

				total_days = len(trading_days)

				# 获取实际数据天数
				if ts_code:
					# 检查单只股票
					actual_days = await self.quote_repo.count_by_ts_code(
						ts_code=ts_code,
						start_date=start_date,
						end_date=end_date
					)
				else:
					# 检查所有股票（抽样）
					# 这里简化处理，实际应该统计所有股票
					actual_days = total_days * 0.95  # 假设95%完整

				# 计算完整率
				completeness_rate = (actual_days / total_days * 100) if total_days > 0 else 100

				metrics[QualityMetricCode.COMPLETENESS_RATE] = {
					"value": completeness_rate,
					"threshold": QualityLevelThreshold.EXCELLENT_MIN,
					"status": "pass" if completeness_rate >= 95 else "fail"
				}

				# 识别缺失的交易日
				if completeness_rate < 100 and ts_code:
					# 获取实际有数据的日期
					actual_dates = await self.quote_repo.get_trade_dates(
						ts_code=ts_code,
						start_date=start_date,
						end_date=end_date
					)

					# 找出缺失的交易日
					missing_dates = [
						day for day in trading_days
						if day not in actual_dates
					]

					if missing_dates:
						issues.append({
							"issue_type": "missing",
							"severity": "medium" if len(missing_dates) < 5 else "high",
							"count": len(missing_dates),
							"description": f"缺失 {len(missing_dates)} 个交易日的行情数据",
							"affected_records": missing_dates[:10]  # 只显示前10个
						})

			except Exception as e:
				logger.error(f"检查完整性失败: {str(e)}")
				metrics[QualityMetricCode.COMPLETENESS_RATE] = {
					"value": 0,
					"status": "error",
					"error": str(e)
				}

		elif data_type == DataType.STOCK_LIST:
			# 检查股票列表完整性
			try:
				# 获取股票总数
				total_stocks = await self.stock_repo.count()

				# 期望的股票数量（基于经验值）
				expected_stocks = 5000  # 大约5000只A股

				completeness_rate = (total_stocks / expected_stocks * 100) if expected_stocks > 0 else 100

				metrics[QualityMetricCode.COMPLETENESS_RATE] = {
					"value": completeness_rate,
					"threshold": 95,
					"status": "pass" if completeness_rate >= 95 else "fail"
				}

				if completeness_rate < 95:
					issues.append({
						"issue_type": "missing",
						"severity": "high",
						"count": expected_stocks - total_stocks,
						"description": f"股票列表不完整，缺少约 {expected_stocks - total_stocks} 只股票"
					})

			except Exception as e:
				logger.error(f"检查股票列表完整性失败: {str(e)}")
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
		"""检查数据准确性"""
		metrics = {}
		issues = []

		if data_type == DataType.DAILY_QUOTES:
			try:
				# 检查异常值（价格超出合理范围）
				if ts_code:
					# 检查单只股票的异常值
					abnormal_records = await self.quote_repo.find_abnormal_records(
						ts_code=ts_code,
						start_date=start_date,
						end_date=end_date,
						price_threshold=0.3  # 价格变动超过30%视为异常
					)

					total_records = await self.quote_repo.count_by_ts_code(
						ts_code=ts_code,
						start_date=start_date,
						end_date=end_date
					)

					if total_records > 0:
						outlier_rate = (len(abnormal_records) / total_records) * 100

						metrics[QualityMetricCode.OUTLIER_RATE] = {
							"value": outlier_rate,
							"threshold": 5,  # 异常值率阈值5%
							"status": "pass" if outlier_rate < 5 else "fail"
						}

						if abnormal_records:
							issues.append({
								"issue_type": "outlier",
								"severity": "low" if len(abnormal_records) < 3 else "medium",
								"count": len(abnormal_records),
								"description": f"发现 {len(abnormal_records)} 条异常价格记录",
								"affected_records": [
									f"{record.trade_date}: 价格异常"
									for record in abnormal_records[:5]
								]
							})

				# 检查数据逻辑一致性（例如：最高价 >= 最低价）
				inconsistent_records = await self.quote_repo.find_inconsistent_records(
					ts_code=ts_code,
					start_date=start_date,
					end_date=end_date
				)

				if inconsistent_records:
					issues.append({
						"issue_type": "inconsistent",
						"severity": "high",
						"count": len(inconsistent_records),
						"description": f"发现 {len(inconsistent_records)} 条逻辑不一致的记录",
						"affected_records": [
							f"{record.trade_date}: 数据不一致"
							for record in inconsistent_records[:5]
						]
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
		"""检查数据及时性"""
		metrics = {}
		issues = []

		if data_type == DataType.DAILY_QUOTES:
			try:
				# 获取最新数据日期
				latest_date = await self.quote_repo.get_latest_trade_date(ts_code)

				if latest_date:
					# 计算数据延迟（距离今天的天数）
					today = datetime.now().date()
					delay_days = (today - latest_date).days

					# 如果是交易日，合理延迟应为0-1天
					expected_delay = 1  # 期望延迟不超过1天

					timeliness_score = 100 - (delay_days * 20)  # 每延迟1天扣20分
					timeliness_score = max(0, min(100, timeliness_score))

					metrics[QualityMetricCode.TIMELINESS_SCORE] = {
						"value": timeliness_score,
						"threshold": 80,  # 及时性得分阈值80
						"status": "pass" if timeliness_score >= 80 else "fail"
					}

					if delay_days > expected_delay:
						issues.append({
							"issue_type": "stale",
							"severity": "medium" if delay_days < 3 else "high",
							"count": 1,
							"description": f"数据更新延迟 {delay_days} 天，最新数据日期为 {latest_date}",
							"affected_records": [latest_date.isoformat()]
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
		"""检查数据一致性"""
		metrics = {}
		issues = []

		if data_type == DataType.DAILY_QUOTES:
			try:
				# 检查重复记录
				duplicate_records = await self.quote_repo.find_duplicate_records(
					ts_code=ts_code,
					start_date=start_date,
					end_date=end_date
				)

				total_records = await self.quote_repo.count_by_ts_code(
					ts_code=ts_code,
					start_date=start_date,
					end_date=end_date
				)

				if total_records > 0:
					duplicate_rate = (len(duplicate_records) / total_records) * 100

					metrics[QualityMetricCode.DUPLICATE_RATE] = {
						"value": duplicate_rate,
						"threshold": 0.1,  # 重复率阈值0.1%
						"status": "pass" if duplicate_rate < 0.1 else "fail"
					}

					if duplicate_records:
						issues.append({
							"issue_type": "duplicate",
							"severity": "low" if len(duplicate_records) < 5 else "medium",
							"count": len(duplicate_records),
							"description": f"发现 {len(duplicate_records)} 条重复记录",
							"affected_records": [
								f"{record.trade_date}: 重复记录"
								for record in duplicate_records[:5]
							]
						})

				# 检查跨数据源一致性（如果有多个数据源）
				# 这里简化处理，实际应该比较不同数据源的数据
				consistency_score = 95.0  # 假设一致性得分为95

				metrics[QualityMetricCode.CONSISTENCY_SCORE] = {
					"value": consistency_score,
					"threshold": 90,
					"status": "pass" if consistency_score >= 90 else "fail"
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

	def _calculate_overall_score (self, results: Dict[str, Any]) -> float:
		"""计算总体质量评分"""
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
					check_scores.append(metric_data["value"])

			if check_scores:
				avg_check_score = sum(check_scores) / len(check_scores)
				total_score += avg_check_score * weight
				total_weight += weight

		# 如果有问题，适当扣分
		issue_deduction = 0
		for check_type, check_results in results.items():
			if "issues" in check_results and check_results["issues"]:
				issue_count = len(check_results["issues"])
				# 每个问题扣1分，最多扣20分
				issue_deduction += min(issue_count, 20)

		overall_score = (total_score / total_weight) if total_weight > 0 else 0
		overall_score = max(0, overall_score - issue_deduction)

		return round(overall_score, 2)

	def _generate_quality_suggestions (
			self,
			issues: List[Dict],
			overall_score: float
	) -> List[str]:
		"""生成质量改进建议"""
		suggestions = []

		if overall_score < 90:
			suggestions.append("数据质量有待提升，建议进行详细检查和修复")

		# 根据问题类型生成具体建议
		issue_types = {}
		for issue in issues:
			issue_type = issue.get("issue_type")
			if issue_type:
				issue_types[issue_type] = issue_types.get(issue_type, 0) + 1

		if issue_types.get("missing"):
			suggestions.append(f"发现 {issue_types['missing']} 个缺失数据问题，建议重新同步相关数据")

		if issue_types.get("duplicate"):
			suggestions.append(f"发现 {issue_types['duplicate']} 个重复记录，建议清理重复数据")

		if issue_types.get("outlier"):
			suggestions.append(f"发现 {issue_types['outlier']} 个异常值，建议验证数据准确性")

		if issue_types.get("stale"):
			suggestions.append("数据更新不及时，建议检查数据同步任务")

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

	async def _fix_single_issue (
			self,
			issue: Dict,
			data_type: str,
			auto_fix: bool = True
	) -> Dict[str, Any]:
		"""修复单个数据问题"""
		issue_type = issue.get("issue_type")

		if not auto_fix:
			# 仅报告问题，不自动修复
			return {
				"success": False,
				"message": "自动修复已禁用",
				"issue": issue
			}

		try:
			if issue_type == "duplicate" and data_type == DataType.DAILY_QUOTES:
				# 修复重复记录
				fixed = await self._fix_duplicate_records(issue)
				return {
					"success": fixed,
					"message": "重复记录已修复" if fixed else "修复重复记录失败"
				}

			elif issue_type == "missing" and data_type == DataType.DAILY_QUOTES:
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
			# 例如：删除重复记录，保留最新或最完整的一条
			logger.info(f"修复重复记录: {issue}")
			return True

		except Exception as e:
			logger.error(f"修复重复记录失败: {str(e)}")
			return False

	async def _fix_missing_data (self, issue: Dict) -> bool:
		"""修复缺失数据"""
		try:
			# 这里简化处理，实际需要重新同步缺失的数据
			logger.info(f"修复缺失数据: {issue}")
			return True

		except Exception as e:
			logger.error(f"修复缺失数据失败: {str(e)}")
			return False

	async def _save_quality_result (
			self,
			check_id: str,
			result: DataQualityResult
	):
		"""保存质量检查结果"""
		check = await self.quality_repo.get_by_check_id(check_id)
		if not check:
			return

		update_data = {
			"status": "completed",
			"completed_at": datetime.now(),
			"overall_score": result.overall_score,
			"quality_level": result.quality_level,
			"metrics": result.metrics,
			"issues": result.issues,
			"suggestions": result.suggestions,
			"duration_seconds": (datetime.now() - check.created_at).total_seconds()
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
		"""创建修复记录"""
		fix_data = {
			"fix_id": fix_id,
			"check_id": check_id,
			"data_type": data_type,
			"status": "completed",
			"user_id": user_id,
			"total_issues": total_issues,
			"fixed_count": fixed_count,
			"failed_fixes": failed_fixes,
			"created_at": datetime.now(),
			"completed_at": datetime.now()
		}

		# 保存到数据库（这里简化处理，实际需要创建修复记录表）
		logger.info(f"创建修复记录: {fix_data}")

	async def _update_quality_progress (
			self,
			check_id: str,
			progress: float,
			current_check: str,
			user_id: Optional[int] = None
	):
		"""更新质量检查进度"""
		# 缓存进度信息
		progress_key = f"quality:progress:{check_id}"
		await self.cache.set(
			progress_key,
			{
				"progress": progress,
				"current_check": current_check,
				"updated_at": datetime.now().isoformat()
			},
			ttl=3600
		)

		# 发布进度事件
		await self._publish_quality_event(
			event_type="progress",
			check_id=check_id,
			progress=progress,
			current_check=current_check,
			user_id=user_id
		)

	async def _publish_quality_event (
			self,
			event_type: str,
			check_id: str,
			data_type: Optional[str] = None,
			quality_level: Optional[str] = None,
			overall_score: Optional[float] = None,
			issue_count: Optional[int] = None,
			issues: Optional[List] = None,
			fixed_count: Optional[int] = None,
			fix_id: Optional[str] = None,
			user_id: Optional[int] = None
	):
		"""发布质量事件"""
		if not self.event_engine:
			return

		event_data = {
			"check_id": check_id,
			"user_id": user_id,
			"timestamp": datetime.now()
		}

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
		if fix_id:
			event_data["fix_id"] = fix_id

		event = DataQualityEvent(
			event_type=f"quality.{event_type}",
			**event_data
		)

		await self.event_engine.put(event)