"""
数据质量仓库服务
负责数据质量检查、评估和报告生成
位置：quant_server/modules/data/services/quality_service.py

根据共享数据库仓库实现进行适配
"""

import logging
from datetime import datetime, date, timedelta
from typing import Dict, List, Any, Optional

from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import text, func

# 导入核心基础设施
from core.engines.system.event_engine import EventEngine
from modules.data.events.types import DataQualityEvent
from shared.cache.redis_cache import RedisCache
# 导入共享层组件
# v2.5: 绕过 shared.database.repositories 顶层包的循环引用，
# 直接从子模块导入，避免 StockBasicRepository 被设为 None
from shared.database.repositories.market.basic.stock_repo import StockBasicRepository
from shared.database.repositories.analysis.factor.factor_data_repo import FactorDataRepository
from shared.database.repositories.market.reference.trade_calendar_repo import TradeCalendarRepository
from shared.database.repositories.analysis.factor.data_quality_check_repo import DataQualityCheckRepository
from shared.database.repositories.market.quote.stock_daily_repo import StockDailyRepository

# 配置日志
logger = logging.getLogger(__name__)


def _is_invalid_financial_statement (statement) -> bool:
	"""检查财务报表是否有效"""
	if not statement:
		return True

	# 检查资产负债表负数
	if hasattr(statement, 'total_revenue') and statement.total_revenue and statement.total_revenue < 0:
		return True
	if hasattr(statement, 'total_cogs') and statement.total_cogs and statement.total_cogs < 0:
		return True
	if hasattr(statement, 'operate_profit') and statement.operate_profit and statement.operate_profit < 0:
		return True

	# 检查利润表负数
	if hasattr(statement, 'revenue') and statement.revenue and statement.revenue < 0:
		return True
	if hasattr(statement, 'n_income') and statement.n_income and statement.n_income < 0:
		return True

	return False


def _check_financial_consistency (statements) -> bool:
	"""检查财务报表数据一致性"""
	if len(statements) < 2:
		return True

	try:
		# 简单的变化率检查
		prev_statement = statements[0]
		for i in range(1, len(statements)):
			current = statements[i]

			# 检查收入变化率（不超过1000%）
			if (hasattr(prev_statement, 'revenue') and hasattr(current, 'revenue') and
					prev_statement.revenue and current.revenue):
				change_rate = abs(current.revenue - prev_statement.revenue) / abs(prev_statement.revenue)
				if change_rate > 10.0:  # 1000%的变化
					return False

			prev_statement = current

		return True
	except Exception as e:
		logger.error(f"检查财务一致性失败: {str(e)}")
		return False


class DataQualityService:
	"""
	数据质量仓库服务类
	负责数据质量的检查、评估和报告
	适配 DataQualityCheckRepository 实现

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
		self.quote_repo = StockDailyRepository(session)
		self.factor_repo = FactorDataRepository(session)
		self.quality_repo = DataQualityCheckRepository(session)  # 使用正确的仓库类
		self.calendar_repo = TradeCalendarRepository(session)

		# 初始化缓存（懒加载）
		self._cache = None

		# 质量检查配置
		self._quality_config = self.__class__._load_quality_config()

	@property
	def cache (self) -> RedisCache:
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

	async def check_data_quality (
			self,
			data_type: str,
			start_date: Optional[date] = None,
			end_date: Optional[date] = None,
			ts_code: Optional[str] = None,
			user_id: Optional[str] = None
	) -> Dict[str, Any]:
		"""
		检查数据质量 - 适配 DataQualityCheckRepository

		由于 DataQualityCheckRepository 使用不同的接口约定，
		这里需要重新设计实现逻辑
		"""
		# data_type 为 None 时默认为 "all"，避免 DB NOT NULL 约束报错
		effective_data_type = data_type or "all"
		logger.info("开始数据质量检查: 类型=%s, 日期=%s~%s", effective_data_type, start_date or "不限", end_date or "不限")

		try:
			# 执行数据采样和质量评估（使用标准化后的类型，None→all）
			quality_metrics = await self._collect_quality_metrics(
				effective_data_type, start_date, end_date, ts_code
			)

			logger.info("质量指标收集完成: 总数=%s, 有效=%s, 得分=%.1f",
			            quality_metrics.get("total_records", 0),
			            quality_metrics.get("valid_records", 0),
			            quality_metrics.get("overall_score", 0))

			# 生成检查记录（去重：同类型+同日期只保留最新一条）
			check_type = "adhoc"
			if not start_date or not end_date:
				check_date = datetime.now().date()
			else:
				check_date = start_date

			total_records = quality_metrics.get("total_records", 0)
			valid_records = quality_metrics.get("valid_records", 0)
			invalid_records = quality_metrics.get("invalid_records", 0)
			missing_records = quality_metrics.get("missing_records", 0)
			duplicate_records = quality_metrics.get("duplicate_records", 0)

			# 今天已检查过同类型 → 更新; 否则 → 新建
			existing = await self.quality_repo.get_by_check_date(
				check_date=check_date,
				data_type=effective_data_type,
			)
			if existing:
				existing_record = existing[0]
				existing_record.total_records = total_records
				existing_record.valid_records = valid_records
				existing_record.invalid_records = invalid_records
				existing_record.missing_records = missing_records
				existing_record.duplicate_records = duplicate_records
				existing_record.check_results = quality_metrics
				await self.session.flush()
				check_record = existing_record
				logger.debug("更新已有质量检查记录: %s/%s", effective_data_type, check_date)
			else:
				check_record = await self.quality_repo.create_quality_check(
					check_type=check_type,
					data_type=effective_data_type,
					check_date=check_date,
					total_records=total_records,
					valid_records=valid_records,
					invalid_records=invalid_records,
					check_results=quality_metrics,
				checked_by=f"user_{user_id}" if user_id else "system"
			)

			# 发布检查完成事件
			await self._publish_quality_event(
				event_type="completed",
				check_id=str(check_record.id),
				data_type=effective_data_type,
				overall_score=quality_metrics.get("overall_score", 0),
				issue_count=quality_metrics.get("issue_count", 0),
				user_id=user_id
			)

			logger.info("数据质量检查完成: check_id=%s, 类型=%s, 得分=%.1f",
			            str(check_record.id), effective_data_type,
			            quality_metrics.get("overall_score", 0))
			return {
				"success": True,
				"check_id": str(check_record.id),
				"result": quality_metrics,
				"message": "数据质量检查完成"
			}

		except Exception as e:
			logger.error(f"数据质量检查失败: {str(e)}", exc_info=True)
			return {
				"success": False,
				"error": str(e),
				"message": "数据质量检查失败"
			}

	async def _collect_quality_metrics (
			self,
			data_type: str,
			start_date: Optional[date],
			end_date: Optional[date],
			ts_code: Optional[str]
	) -> Dict[str, Any]:
		"""
		收集数据质量指标
		"""
		metrics = {
			"total_records": 0,
			"valid_records": 0,
			"invalid_records": 0,
			"missing_records": 0,
			"duplicate_records": 0,
			"issues": [],
			"overall_score": 0.0
		}

		try:
			logger.info("开始收集质量指标: 类型=%s", data_type)
			if data_type in ("daily_quotes", "all"):
				await self._check_daily_quotes_quality(metrics, ts_code, start_date, end_date)
			if data_type in ("stock_list", "all"):
				await self._check_stock_list_quality(metrics)
			if data_type in ("factor_data", "all"):
				await self._check_factor_data_quality(metrics, ts_code, start_date, end_date)

			# 计算总体得分
			if metrics["total_records"] > 0:
				metrics["overall_score"] = round(
					(metrics["valid_records"] / metrics["total_records"]) * 100, 2
				)
			else:
				metrics["overall_score"] = 0

			metrics["issue_count"] = len(metrics["issues"])

		except Exception as e:
			logger.error(f"收集质量指标失败: {str(e)}")
			metrics["error"] = [str(e)]

		return metrics

	async def _check_daily_quotes_quality (
			self,
			metrics: Dict[str, Any],
			ts_code: Optional[str],
			start_date: Optional[date],
			end_date: Optional[date]
	):
		"""检查日行情数据质量"""
		try:
			# 如果没有指定日期范围，默认检查最近30天
			if not start_date or not end_date:
				end_date = datetime.now().date()
				start_date = end_date - timedelta(days=30)

			# 使用StockDailyRepository的数据完整性检查
			# 修复 2026-08（A12）：ts_code 为空时不再返回硬编码假指标，改为全市场真实聚合统计
			integrity_result = await self.quote_repo.check_data_integrity(
				ts_code=ts_code,
				start_date=start_date,
				end_date=end_date
			) if ts_code else await self._check_market_wide_integrity(start_date, end_date)

			# 填充指标
			metrics.update({
				"total_records": integrity_result.get("actual_data_days", 0),
				"valid_records": int(integrity_result.get("actual_data_days", 0) *
				                     integrity_result.get("data_quality", {}).get("quality_score", 0.95)),
				"invalid_records": integrity_result.get("actual_data_days", 0) -
				                   int(integrity_result.get("actual_data_days", 0) *
				                       integrity_result.get("data_quality", {}).get("quality_score", 0.95)),
				"missing_records": integrity_result.get("missing_count", 0),
				"duplicate_records": 0  # 日行情数据通常不会有重复
			})

			# 添加具体问题
			if integrity_result.get("missing_count", 0) > 0:
				metrics["issues"].append({
					"issue_type": "missing_data",
					"description": f"缺失{integrity_result['missing_count']}个交易日数据",
					"severity": "high" if integrity_result["missing_count"] > 3 else "medium"
				})

			if integrity_result.get("data_quality", {}).get("null_close_count", 0) > 0:
				metrics["issues"].append({
					"issue_type": "null_value",
					"column": "close",
					"count": integrity_result["data_quality"]["null_close_count"],
					"severity": "critical"
				})

			if integrity_result.get("data_quality", {}).get("zero_volume_count", 0) > 0:
				metrics["issues"].append({
					"issue_type": "zero_volume",
					"count": integrity_result["data_quality"]["zero_volume_count"],
					"severity": "medium"
				})

		except Exception as e:
			logger.error(f"检查行情数据质量失败: {str(e)}", exc_info=True)
			metrics.update({
				"error": str(e),
				"total_records": 0,
				"valid_records": 0,
				"invalid_records": 0
			})

	async def _check_market_wide_integrity (self, start_date: date, end_date: date) -> Dict[str, Any]:
		"""全市场完整性真实聚合（修复 2026-08 A12：替代硬编码假数据）"""
		try:
			# 理论交易日数
			cal = await self.session.execute(text(
				"SELECT COUNT(*) FROM trade_calendar WHERE cal_date BETWEEN :s AND :e AND is_open = true"
			), {"s": start_date, "e": end_date})
			expected_days = cal.scalar() or 0

			# 区间内全市场总记录数 / 去重股票数 / 零成交量记录数
			agg = await self.session.execute(text("""
				SELECT COUNT(*) AS total_records,
				       COUNT(DISTINCT ts_code) AS stock_count,
				       SUM(CASE WHEN vol <= 0 THEN 1 ELSE 0 END) AS zero_volume_count,
				       SUM(CASE WHEN close IS NULL THEN 1 ELSE 0 END) AS null_close_count
				FROM stock_daily
				WHERE trade_date BETWEEN :s AND :e
			"""), {"s": start_date, "e": end_date})
			row = agg.first()
			total_records = row.total_records or 0
			stock_count = row.stock_count or 0
			zero_volume = row.zero_volume_count or 0
			null_close = row.null_close_count or 0

			# 平均每股覆盖天数；质量分 = 平均覆盖 / 理论交易日
			avg_coverage = (total_records / stock_count) if stock_count else 0
			quality_score = round(min(avg_coverage / expected_days, 1.0), 4) if expected_days else 0
			return {
				"expected_trading_days": expected_days,
				"actual_data_days": round(avg_coverage, 2),
				"missing_count": max(int(expected_days - avg_coverage) * stock_count, 0),
				"data_quality": {
					"total_records": total_records,
					"null_close_count": null_close,
					"zero_volume_count": zero_volume,
					"quality_score": quality_score
				}
			}
		except Exception as e:
			logger.warning("全市场完整性统计失败: %s", str(e), exc_info=True)
			return {
				"expected_trading_days": 0, "actual_data_days": 0, "missing_count": 0,
				"data_quality": {"total_records": 0, "null_close_count": 0,
				                 "zero_volume_count": 0, "quality_score": 0}
			}

	async def _check_stock_list_quality (self, metrics: Dict[str, Any]):
		"""检查股票列表质量"""
		try:
			total_stocks = await self.stock_repo.count()
			metrics["total_records"] = total_stocks
			# 修复 2026-08（A12）：不再硬编码 "98% 有效"，改为真实统计最近 30 日有日行情的股票数
			try:
				_active = await self.session.execute(text(
					"SELECT COUNT(DISTINCT ts_code) FROM stock_daily "
					"WHERE trade_date >= :since"
				), {"since": datetime.now().date() - timedelta(days=30)})
				_active_count = _active.scalar() or 0
			except Exception:
				logger.warning("活跃股票统计失败，降级为总数", exc_info=True)
				_active_count = total_stocks
			metrics["valid_records"] = _active_count
			metrics["invalid_records"] = max(total_stocks - _active_count, 0)
			logger.info("股票列表质量检查完成: 总数=%s, 近30日活跃=%s", total_stocks, _active_count)

		except Exception as e:
			logger.error(f"检查股票列表质量失败: {str(e)}")
			raise

	async def _check_factor_data_quality (
			self,
			metrics: Dict[str, Any],
			ts_code: Optional[str],
			start_date: Optional[date],
			end_date: Optional[date]
	):
		"""检查因子数据质量"""
		try:
			# 如果没有指定日期范围，默认检查最近30天
			if not start_date or not end_date:
				end_date = datetime.now().date()
				start_date = end_date - timedelta(days=30)

			logger.info("开始因子数据质量检查: %s~%s", start_date, end_date)
			# 获取因子覆盖度统计
			factors = await self._get_available_factors()
			if not factors:
				factors = ["pe_ratio"]  # 默认检查市盈率因子

			# 转换日期类型为 datetime
			start_datetime = datetime.combine(start_date, datetime.min.time()) if start_date else None
			end_datetime = datetime.combine(end_date, datetime.max.time()) if end_date else None
			
			coverage_stats = await self.factor_repo.get_factor_coverage(
				factor_name=factors[0],
				start_date=start_datetime,
				end_date=end_datetime,
				universe=[ts_code] if ts_code else None
			)

			# 填充指标
			metrics.update({
				"total_records": coverage_stats.get("total_records", 0),
				"valid_records": coverage_stats.get("total_records", 0),  # 因子数据要么有效要么不存在
				"invalid_records": 0,  # 因子数据没有无效概念
				"missing_records": coverage_stats.get("total_dates", 0) * (1 if ts_code else 100) -
				                   coverage_stats.get("total_records", 0),  # 估算缺失记录数
				"duplicate_records": 0  # 因子数据不应该有重复
			})

			# 检查数据质量问题
			if coverage_stats.get("total_records", 0) == 0:
				metrics["issues"].append({
					"issue_type": "no_data",
					"description": "没有找到任何因子数据",
					"severity": "critical"
				})

			# 检查极端值
			for day_stat in coverage_stats.get("daily_coverage", []):
				if day_stat.get("std_value", 0) > 3 * coverage_stats.get("overall_std", 1):
					metrics["issues"].append({
						"issue_type": "extreme_value",
						"date": day_stat["trade_date"],
						"std_dev": day_stat["std_value"],
						"severity": "medium"
					})

		except Exception as e:
			logger.error(f"检查因子数据质量失败: {str(e)}", exc_info=True)
			metrics.update({
				"error": str(e),
				"total_records": 0,
				"valid_records": 0,
				"invalid_records": 0
			})

	async def _check_financial_data_quality (
			self,
			metrics: Dict[str, Any],
			ts_code: Optional[str],
			start_date: Optional[date],
			end_date: Optional[date]
	):
		"""检查财务数据质量"""
		try:
			# 如果没有指定日期范围，默认检查最近3年
			if not start_date or not end_date:
				end_date = datetime.now().date()
				start_date = end_date - timedelta(days=365 * 3)

			logger.info("开始财务数据质量检查: %s~%s", start_date, end_date)
			finance_quality = await self._check_financial_data_integrity(
				ts_code=ts_code,
				start_date=start_date,
				end_date=end_date
			)

			# 填充指标
			metrics.update({
				"total_records": finance_quality.get("total_statements", 0),
				"valid_records": finance_quality.get("complete_statements", 0),
				"invalid_records": finance_quality.get("invalid_statements", 0),
				"missing_records": finance_quality.get("missing_statements", 0),
				"duplicate_records": 0
			})

			# 添加具体问题
			if finance_quality.get("missing_statements", 0) > 0:
				metrics["issues"].append({
					"issue_type": "missing_statement",
					"description": f"缺失{finance_quality['missing_statements']}张财务报表",
					"severity": "high"
				})

			if finance_quality.get("invalid_statements", 0) > 0:
				metrics["issues"].append({
					"issue_type": "invalid_statement",
					"description": f"有{finance_quality['invalid_statements']}张无效财务报表",
					"severity": "critical"
				})

			if finance_quality.get("inconsistent_statements", 0) > 0:
				metrics["issues"].append({
					"issue_type": "inconsistent_data",
					"description": f"有{finance_quality['inconsistent_statements']}张不一致财务报表",
					"severity": "medium"
				})

		except Exception as e:
			logger.error(f"检查财务数据质量失败: {str(e)}", exc_info=True)
			metrics.update({
				"error": str(e),
				"total_records": 0,
				"valid_records": 0,
				"invalid_records": 0
			})

	# async def _check_financial_data_integrity (
	# 		self,
	# 		ts_code: Optional[str],
	# 		start_date: date,
	# 		end_date: date
	# ) -> Dict[str, Any]:
	# 	"""
	# 	检查财务数据完整性
	# 	使用FinancialIncomeRepository的已有方法实现质量检查
	# 	"""
	# 	try:
	# 		if not ts_code:
	# 			# 示例数据用于系统级检查
	# 			return {
	# 				"total_statements": 15,
	# 				"complete_statements": 12,
	# 				"missing_statements": 2,
	# 				"invalid_statements": 1,
	# 				"inconsistent_statements": 1,
	# 				"data_quality": {
	# 					"balance_sheet_score": 0.92,
	# 					"income_statement_score": 0.88,
	# 					"cash_flow_score": 0.85,
	# 					"overall_score": 0.88
	# 				}
	# 			}
	#
	# 		result = {
	# 			"total_statements": 0,
	# 			"complete_statements": 0,
	# 			"missing_statements": 0,
	# 			"invalid_statements": 0,
	# 			"inconsistent_statements": 0
	# 		}
	#
	# 		report_types = ["balance_sheet", "income_statement", "cash_flow_statement"]
	#
	# 		for report_type in report_types:
	# 			# 获取所有报表数据
	# 			statements = await self.financial_repo.get_financial_statements(
	# 				ts_code=ts_code,
	# 				report_type=report_type,
	# 				start_date=start_date,
	# 				end_date=end_date
	# 			)
	#
	# 			# 按年度和季度分类
	# 			annual_statements = []
	# 			quarterly_statements = []
	# 			for stmt in statements:
	# 				if hasattr(stmt, 'end_date') and stmt.end_date:
	# 					if stmt.end_date.month == 12 and stmt.end_date.day == 31:
	# 						annual_statements.append(stmt)
	# 					if stmt.end_date.day == 31 and stmt.end_date.month in [3, 6, 9, 12]:
	# 						quarterly_statements.append(stmt)
	#
	# 			# 计算年度报告预期数量
	# 			expected_annual = (end_date.year - start_date.year) + 1
	# 			result["total_statements"] += expected_annual
	# 			result["complete_statements"] += len(annual_statements)
	# 			result["missing_statements"] += max(0, expected_annual - len(annual_statements))
	#
	# 			# 计算季度报告预期数量
	# 			expected_quarterly = expected_annual * 4
	# 			result["total_statements"] += expected_quarterly
	# 			result["complete_statements"] += len(quarterly_statements)
	# 			result["missing_statements"] += max(0, expected_quarterly - len(quarterly_statements))
	#
	# 			# 检查无效报表（包含负值或不合理的财务数据）
	# 			for stmt in statements:
	# 				if _is_invalid_financial_statement(stmt):
	# 					result["invalid_statements"] += 1
	#
	# 			# 检查数据一致性
	# 			if len(statements) > 1 and not _check_financial_consistency(statements):
	# 				result["inconsistent_statements"] += 1
	#
	# 		return result
	#
	# 	except Exception as e:
	# 		logger.error(f"检查财务数据完整性失败: {str(e)}")
	# 		return {
	# 			"total_statements": 0,
	# 			"complete_statements": 0,
	# 			"missing_statements": 0,
	# 			"invalid_statements": 0,
	# 			"inconsistent_statements": 0
	# 		}

	async def get_quality_report (
			self,
			data_type: Optional[str] = None,
			limit: int = 10,
			page: int = 1
	) -> Dict[str, Any]:
		"""
		获取质量报告 - 适配 DataQualityCheckRepository
		"""
		try:
			# 构建查询条件
			filters = {}
			if data_type:
				filters["data_type"] = data_type

			# 计算总数
			total = await self.quality_repo.count(**filters)

			# 计算偏移量
			skip = (page - 1) * limit

			# 获取质量检查记录
			quality_checks = await self.quality_repo.get_many(
				skip=skip,
				limit=limit,
				**filters
			)
			# Sort by created_at descending (TODO: add order_by support to BaseRepository)
			quality_checks = sorted(
				quality_checks,
				key=lambda x: getattr(x, "created_at", datetime.min),
				reverse=True,
			)

			# 转换为响应格式
			reports = []
			for check in quality_checks:
				quality_score = (check.valid_records / check.total_records * 100) if check.total_records > 0 else 0
				reports.append({
					"check_id": str(check.id),
					"data_type": check.data_type,
					"quality_score": round(quality_score, 2),
					"total_records": check.total_records,
					"valid_records": check.valid_records,
					"invalid_records": check.invalid_records,
					"check_date": check.check_date.isoformat() if check.check_date else None,
					"status": check.status
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

	async def get_quality_statistics (
			self,
			data_type: Optional[str] = None,
			days: int = 30
	) -> Dict[str, Any]:
		"""
		获取质量统计信息 - 适配 DataQualityCheckRepository
		"""
		try:
			end_date = datetime.now().date()
			start_date = end_date - timedelta(days=days)

			stats = await self.quality_repo.get_quality_statistics(
				start_date=start_date,
				end_date=end_date,
				data_type=data_type
			)

			return stats

		except Exception as e:
			logger.error(f"获取质量统计信息失败: {str(e)}", exc_info=True)
			return {
				"total_checks": 0,
				"total_records_checked": 0,
				"total_valid_records": 0,
				"total_invalid_records": 0,
				"overall_quality_score": 0
			}

	async def _get_available_factors (self) -> List[str]:
		"""获取可用因子列表"""
		try:
			factors = await self.factor_repo.get_available_factors()
			return factors if factors else ["pe_ratio", "pb_ratio", "roe"]
		except Exception as e:
			logger.error(f"获取可用因子列表失败: {str(e)}")
			return ["pe_ratio", "pb_ratio", "roe"]

	@staticmethod
	def _load_quality_config () -> Dict[str, Any]:
		"""加载质量检查配置"""
		return {
			"completeness_threshold": 95.0,
			"quality_score_threshold": 90.0
		}

	@staticmethod
	async def clean_invalid_data (
			data: List[Dict],
			data_type: str,
			cleaning_rules: Dict
	) -> Dict[str, Any]:
		"""清理无效数据"""
		logger.debug(f"开始清理无效数据，类型: {data_type}")

		try:
			original_count = len(data)
			removed_count = 0
			fixed_count = 0

			# 执行清理操作
			if cleaning_rules.get('remove_duplicates', False):
				# 移除重复数据
				seen = set()
				unique_data = []
				for item in data:
					# 根据数据类型生成唯一标识
					if data_type == "stock_quote":
						key = (item.get('ts_code'), item.get('trade_date'))
					else:
						key = tuple(item.values())
					if key not in seen:
						seen.add(key)
						unique_data.append(item)
				removed_count += len(data) - len(unique_data)
				data = unique_data

			if cleaning_rules.get('fix_missing_values', False):
				# 修复缺失值
				for item in data:
					if data_type == "stock_quote":
						# 修复股票行情数据的缺失值
						if item.get('close') is None:
							item['close'] = item.get('open', 0)
							fixed_count += 1
						if item.get('volume') is None:
							item['volume'] = 0
							fixed_count += 1
					elif data_type == "stock_basic":
						# 修复股票基础数据的缺失值
						if item.get('industry') is None:
							item['industry'] = '未知'
							fixed_count += 1

			if cleaning_rules.get('remove_outliers', False):
				# 移除异常值
				valid_data = []
				for item in data:
					if data_type == "stock_quote":
						# 检查价格异常值（涨跌幅超过20%）
						if item.get('open') and item.get('close'):
							change_rate = abs(item['close'] - item['open']) / item['open']
							if change_rate <= 0.2:
								valid_data.append(item)
						else:
								removed_count += 1
					else:
						valid_data.append(item)
				data = valid_data

			if cleaning_rules.get('validate_ranges', False):
				# 验证数据范围
				valid_data = []
				for item in data:
					if data_type == "stock_quote":
						# 验证价格和成交量范围
						if (item.get('close', 0) >= 0 and 
							item.get('volume', 0) >= 0 and 
							item.get('amount', 0) >= 0):
							valid_data.append(item)
						else:
							removed_count += 1
					else:
						valid_data.append(item)
				data = valid_data

			cleaned_count = len(data)

			return {
				'original_count': original_count,
				'cleaned_count': cleaned_count,
				'removed_count': removed_count,
				'fixed_count': fixed_count,
				'success': True,
				'message': '数据清理完成'
			}

		except Exception as e:
			logger.error(f"清理无效数据失败: {str(e)}")
			return {
				'original_count': len(data) if data else 0,
				'cleaned_count': 0,
				'removed_count': 0,
				'fixed_count': 0,
				'success': False,
				'message': str(e)
			}

	async def validate_data_consistency (
			self,
			validation_type: str,
			reference_date: str
	) -> Dict[str, Any]:
		"""验证数据一致性"""
		logger.debug(f"开始验证数据一致性，类型: {validation_type}")

		try:
			total_checks = 0
			passed_checks = 0
			failed_checks = 0
			inconsistencies = []

			# 执行一致性验证
			if validation_type == "cross_reference":
				# 跨表引用验证：股票行情数据与基础数据的一致性
				try:
					# 获取股票基础数据
					stocks = await self.stock_repo.get_all_stocks()
					stock_codes = {stock.ts_code for stock in stocks}
					total_checks += 1

					# 获取指定日期的行情数据
					quote_date = datetime.strptime(reference_date, '%Y-%m-%d').date()
					quotes = await self.quote_repo.get_quotes_by_date(quote_date)
					quote_codes = {quote.ts_code for quote in quotes}

					# 检查行情数据中的股票代码是否都在基础数据中
					invalid_codes = quote_codes - stock_codes
					if invalid_codes:
						failed_checks += 1
						inconsistencies.append({
							'type': 'invalid_stock_codes',
							'message': f'行情数据中存在无效的股票代码: {invalid_codes}',
							'count': len(invalid_codes)
						})
					else:
						passed_checks += 1

					# 检查基础数据中的股票是否都有行情数据
					missing_quotes = stock_codes - quote_codes
					if missing_quotes:
						# 允许一定比例的缺失（例如5%）
						missing_ratio = len(missing_quotes) / len(stock_codes)
						if missing_ratio > 0.05:
							failed_checks += 1
							inconsistencies.append({
								'type': 'missing_quotes',
								'message': f'基础数据中的股票缺少行情数据: {len(missing_quotes)} 个',
								'count': len(missing_quotes)
							})
					else:
						passed_checks += 1
					total_checks += 1

				except Exception as e:
					logger.error(f"跨表引用验证失败: {str(e)}")
					failed_checks += 1
					total_checks += 1

			elif validation_type == "intraday_consistency":
				# 日内数据一致性验证：开盘价、收盘价、最高价、最低价的关系
				try:
					quote_date = datetime.strptime(reference_date, '%Y-%m-%d').date()
					quotes = await self.quote_repo.get_quotes_by_date(quote_date)
					total_checks += len(quotes)

					for quote in quotes:
						# 验证价格关系
						is_valid = True
						if hasattr(quote, 'open') and hasattr(quote, 'high') and hasattr(quote, 'low') and hasattr(quote, 'close'):
							if quote.high < quote.low:
								is_valid = False
							if quote.open < quote.low or quote.open > quote.high:
								is_valid = False
							if quote.close < quote.low or quote.close > quote.high:
								is_valid = False

						if is_valid:
							passed_checks += 1
						else:
							failed_checks += 1
							inconsistencies.append({
								'type': 'price_inconsistency',
								'message': f'股票 {quote.ts_code} 价格数据不一致',
								'data': {
									'open': quote.open,
									'high': quote.high,
									'low': quote.low,
									'close': quote.close
								}
							})
				except Exception as e:
					logger.error(f"日内数据一致性验证失败: {str(e)}")
					failed_checks += 1
					total_checks += 1

			consistency_score = (passed_checks / total_checks * 100) if total_checks > 0 else 0

			return {
				'total_checks': total_checks,
				'passed_checks': passed_checks,
				'failed_checks': failed_checks,
				'inconsistencies': inconsistencies,
				'consistency_score': consistency_score,
				'success': True
			}

		except Exception as e:
			logger.error(f"验证数据一致性失败: {str(e)}")
			return {
				'total_checks': 0,
				'passed_checks': 0,
				'failed_checks': 0,
				'inconsistencies': [],
				'consistency_score': 0,
				'success': False
			}

	async def generate_quality_report (
			self,
			start_date: str,
			end_date: str,
			data_types: Optional[List[str]] = None
	) -> Dict[str, Any]:
		"""生成质量报告"""
		logger.debug(f"生成质量报告，时间范围: {start_date} 到 {end_date}")

		try:
			reports = []
			total_score = 0
			total_records = 0

			# 转换日期格式
			start_dt = datetime.strptime(start_date, '%Y-%m-%d').date()
			end_dt = datetime.strptime(end_date, '%Y-%m-%d').date()

			# 获取质量检查记录
			filters = {}
			if data_types:
				filters['data_type'] = data_types

			quality_checks = await self.quality_repo.get_many(
				skip=0,
				limit=1000,
				**filters
			)
			# Sort by created_at descending (TODO: add order_by support to BaseRepository)
			quality_checks = sorted(
				quality_checks,
				key=lambda x: getattr(x, "created_at", datetime.min),
				reverse=True,
			)

			# 按数据类型分组统计
			data_type_stats = {}
			for check in quality_checks:
				if check.check_date and start_dt <= check.check_date <= end_dt:
					data_type = check.data_type
					if data_type not in data_type_stats:
						data_type_stats[data_type] = {
							'total_checks': 0,
							'total_records': 0,
							'valid_records': 0,
							'invalid_records': 0,
							'total_score': 0
						}
					
					data_type_stats[data_type]['total_checks'] += 1
					data_type_stats[data_type]['total_records'] += check.total_records
					data_type_stats[data_type]['valid_records'] += check.valid_records
					data_type_stats[data_type]['invalid_records'] += check.invalid_records
					
					# 计算每次检查的质量分数
					if check.total_records > 0:
						score = (check.valid_records / check.total_records) * 100
						data_type_stats[data_type]['total_score'] += score

			# 生成报告
			for data_type, stats in data_type_stats.items():
				if stats['total_checks'] > 0:
					current_avg_score = stats['total_score'] / stats['total_checks']
					reports.append({
						'data_type': data_type,
						'quality_score': round(current_avg_score, 2),
						'total_records': stats['total_records'],
						'valid_records': stats['valid_records'],
						'invalid_records': stats['invalid_records'],
						'check_count': stats['total_checks']
					})
					total_score += current_avg_score
				total_records += stats['total_records']

			# 计算平均分数
			avg_score = total_score / len(reports) if reports else 0

			# 生成默认报告（如果没有数据）
			if not reports:
				if data_types:
					for data_type in data_types:
						reports.append({
							'data_type': data_type,
							'quality_score': 0,
							'total_records': 0,
							'valid_records': 0,
							'invalid_records': 0,
							'check_count': 0
						})
				else:
					reports.append({
						'data_type': 'all',
						'quality_score': 0,
						'total_records': 0,
						'valid_records': 0,
						'invalid_records': 0,
						'check_count': 0
					})

			# 返回报告
			return {
				'start_date': start_date,
				'end_date': end_date,
				'reports': reports,
				'average_quality_score': round(avg_score, 2),
				'total_records': total_records,
				'generated_at': datetime.now().isoformat()
			}

		except Exception as e:
			logger.error(f"生成质量报告失败: {str(e)}")
			return {
				'start_date': start_date,
				'end_date': end_date,
				'reports': [],
				'average_quality_score': 0,
				'total_records': 0,
				'generated_at': datetime.now().isoformat(),
				'error': str(e)
			}

	async def save_quality_result (
			self,
			data_type: str,
			check_date: str,
			check_result: Dict,
			task_id: str
	) -> str:
		"""保存质量检查结果"""
		logger.debug(f"保存质量检查结果，类型: {data_type}")

		try:
			# 解析检查结果
			total_records = check_result.get('summary', {}).get('total_records', 0)
			valid_records = total_records - check_result.get('summary', {}).get('total_issues', 0)
			invalid_records = check_result.get('summary', {}).get('total_issues', 0)

			# 转换日期格式
			check_date_obj = datetime.strptime(check_date, '%Y-%m-%d').date()

			# 保存到数据库
			check_record = await self.quality_repo.create_quality_check(
				check_type="task",
				data_type=data_type,
				check_date=check_date_obj,
				total_records=total_records,
				valid_records=valid_records,
				invalid_records=invalid_records,
				check_results=check_result,
				checked_by=f"task_{task_id}"
			)

			return str(check_record.id)

		except Exception as e:
			logger.error(f"保存质量检查结果失败: {str(e)}")
			return f"error_{task_id[:8]}"

	async def _publish_quality_event (
			self,
			event_type: str,
			check_id: Optional[str] = None,
			data_type: Optional[str] = None,
			overall_score: Optional[float] = None,
			issue_count: Optional[int] = None,
			user_id: Optional[str] = None
	):
		"""发布质量事件"""
		if not self.event_engine:
			return

		try:
			event = DataQualityEvent(
				event_type=f"quality.{event_type}",
				check_id=check_id,
				data_type=data_type,
				overall_score=overall_score,
				issue_count=issue_count,
				source="data_quality_service",
				user_id=user_id
			)

			await self.event_engine.put(event)

		except Exception as e:
			logger.error(f"发布质量事件失败: {str(e)}")