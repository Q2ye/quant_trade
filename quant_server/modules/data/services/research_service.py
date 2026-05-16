# -*- coding: utf-8 -*-
"""
因子研究仓库服务
负责因子数据的计算、研究和分析
位置：quant_server/modules/data/services/research_service.py

设计原则：
1. 模块化因子计算：每个因子独立实现
2. 可配置的研究参数：支持不同的研究设置
3. 完整的研究结果：提供详细的分析报告
4. 高性能计算：支持批量处理和缓存
"""

import asyncio
import logging
from datetime import datetime, date, timedelta
from typing import Dict, List, Any, Optional

import numpy as np
import pandas as pd
from pandas import DataFrame
from scipy import stats
from sqlalchemy.ext.asyncio import AsyncSession

# 导入核心基础设施
from core.engines.system.event_engine import EventEngine
from core.events.base import TypedEvent
# 导入数据模块常量
from modules.data.constants import (
	CacheKey,
	FactorCategoryCode,
	StandardFactors,
	ResearchStatus
)
from shared.cache.redis_cache import RedisCache
# 导入共享层组件
from shared.database.repositories import (
	StockBasicRepository,
	StockDailyRepository,
	FactorDataRepository,
	FactorDefinitionRepository,
	FactorResearchRepository,
	FinancialStatementRepository
)
# 导入工具类
from utils.core_utils.math_utils import StatisticalCalculator

# 配置日志
logger = logging.getLogger(__name__)


class FactorResearchService:
	"""
	因子研究仓库服务类
	负责因子的计算、分析和研究

	Attributes:
		session: 异步数据库会话
		event_engine: 事件引擎
		stock_repo: 股票数据仓库
		quote_repo: 行情数据仓库
		factor_repo: 因子数据仓库
		research_repo: 因子研究仓库
		stat_calculator: 统计计算器
	"""

	def __init__ (self, session: AsyncSession, event_engine: Optional[EventEngine] = None):
		"""
		初始化因子研究服务

		Args:
			session: 数据库会话
			event_engine: 事件引擎，用于发布研究事件
		"""
		self.session = session
		self.event_engine = event_engine

		# 初始化Repository
		self.stock_repo = StockBasicRepository(session)
		self.quote_repo = StockDailyRepository(session)
		self.factor_repo = FactorDataRepository(session)
		self.factor_def_repo = FactorDefinitionRepository(session)
		self.research_repo = FactorResearchRepository(session)
		self.financial_repo = FinancialStatementRepository(session)

		# 初始化计算工具
		self.stat_calculator = StatisticalCalculator()

		# 初始化缓存（懒加载）
		self._cache = None

		# 因子计算器映射
		self._factor_calculators = self._init_factor_calculators()

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
				password=settings.REDIS.PASSWORD,
			)
		return self._cache

	# ==================== 因子研究主方法 ====================

	async def research_factor (
			self,
			factor_definition: Dict[str, Any],
			universe: Optional[List[str]] = None,
			start_date: Optional[date] = None,
			end_date: Optional[date] = None,
			parameters: Optional[Dict[str, Any]] = None,
			user_id: Optional[str] = None
	) -> Dict[str, Any]:
		"""
		执行因子研究

		Args:
			factor_definition: 因子定义，包含：
				- name: 因子名称
				- formula: 因子公式
				- category: 因子类别
				- description: 因子描述
			universe: 股票池，不指定则使用全市场股票
			start_date: 开始日期，默认一年前
			end_date: 结束日期，默认今天
			parameters: 研究参数，如计算窗口、权重等
			user_id: 用户ID

		Returns:
			Dict: 研究结果，包含：
				- success: 是否成功
				- research_id: 研究ID
				- result: 研究结果详情
				- message: 状态消息
		"""
		logger.info(f"开始因子研究，因子: {factor_definition.get('name')}")

		research_id = None
		try:
			# 创建研究任务记录
			research_id = await self._create_research_task(
				factor_definition=factor_definition,
				universe=universe,
				start_date=start_date,
				end_date=end_date,
				parameters=parameters,
				user_id=user_id
			)

			# 发布研究开始事件
			await self._publish_research_event(
				event_type="started",
				research_id=research_id,
				factor_definition=factor_definition,
				user_id=user_id
			)

			# 执行研究
			research_result = await self._execute_factor_research(
				factor_definition=factor_definition,
				universe=universe,
				start_date=start_date,
				end_date=end_date,
				parameters=parameters,
				research_id=research_id,
				user_id=user_id
			)

			# 保存研究结果
			await self._save_research_result(
				research_id=research_id,
				result=research_result
			)

			# 发布研究完成事件
			await self._publish_research_event(
				event_type="completed",
				research_id=research_id,
				result=research_result,
				user_id=user_id
			)

			logger.info(f"因子研究完成，研究ID: {research_id}")

			return {
				"success": True,
				"research_id": research_id,
				"result": research_result,
				"message": "因子研究完成"
			}

		except Exception as e:
			logger.error(f"因子研究失败: {str(e)}", exc_info=True)

			# 更新研究状态为失败
			if research_id:
				await self._update_research_task(
					research_id=research_id,
					status=ResearchStatus.FAILED,
					error=str(e)
				)

			# 发布失败事件
			await self._publish_research_event(
				event_type="failed",
				research_id=research_id,
				error=str(e),
				user_id=user_id
			)

			return {
				"success": False,
				"research_id": research_id,
				"error": str(e),
				"message": "因子研究失败"
			}

	async def calculate_factor (
			self,
			factor_name: str,
			ts_codes: Optional[List[str]] = None,
			start_date: Optional[date] = None,
			end_date: Optional[date] = None,
			parameters: Optional[Dict[str, Any]] = None,
			batch_size: int = 50,
			user_id: Optional[str] = None
	) -> Dict[str, Any]:
		"""
		计算因子数据

		Args:
			factor_name: 因子名称
			ts_codes: 股票代码列表，不指定则计算所有股票
			start_date: 开始日期
			end_date: 结束日期
			parameters: 计算参数
			batch_size: 批量大小
			user_id: 用户ID

		Returns:
			Dict: 计算结果，包含：
				- success: 是否成功
				- task_id: 任务ID
				- factor_name: 因子名称
				- calculated_count: 成功计算数量
				- total_stocks: 总股票数量
				- failed_calculations: 失败列表
				- date_range: 日期范围
				- message: 状态消息
		"""
		logger.info(f"开始计算因子，因子: {factor_name}")

		task_id = None
		try:
			# 生成任务ID
			task_id = f"calc_{factor_name}_{datetime.now().strftime('%Y%m%d_%H%M%S')}"

			# 获取股票列表
			if not ts_codes:
				# 获取所有活跃股票（按市场查询）
				stocks = await self.stock_repo.get_by_market("主板", active_only=True)
				# 也获取创业板和科创板
				try:
					stocks_china = await self.stock_repo.get_by_market("创业板", active_only=True)
					stocks.extend(stocks_china)
				except Exception as e:
					logger.warning(f"获取创业板股票失败: {str(e)}")
				try:
					stocks_star = await self.stock_repo.get_by_market("科创板", active_only=True)
					stocks.extend(stocks_star)
				except Exception as e:
					logger.warning(f"获取科创板股票失败: {str(e)}")
				ts_codes = [stock.ts_code for stock in stocks]

			if not ts_codes:
				return {
					"success": False,
					"task_id": task_id,
					"error": "没有可计算的股票",
					"message": "无法计算因子数据"
				}

			# 设置默认日期范围
			if not end_date:
				end_date = datetime.now().date()
			if not start_date:
				start_date = end_date - timedelta(days=365)  # 默认一年

			total_stocks = len(ts_codes)
			calculated_count = 0
			failed_calculations = []

			# 发布计算开始事件
			await self._publish_research_event(
				event_type="calculation_started",
				research_id=task_id,
				factor_name=factor_name,
				total_stocks=total_stocks,
				user_id=user_id
			)

			# 分批计算
			for i in range(0, total_stocks, batch_size):
				batch_codes = ts_codes[i:i + batch_size]

				batch_tasks = []
				for ts_code in batch_codes:
					task = self._calculate_single_factor(
						factor_name=factor_name,
						ts_code=ts_code,
						start_date=datetime.combine(start_date, datetime.min.time()),
						end_date=datetime.combine(end_date, datetime.min.time()),
						parameters=parameters
					)
					batch_tasks.append(task)

				# 并发执行批次任务
				batch_results = await asyncio.gather(*batch_tasks, return_exceptions=True)

				# 处理批次结果
				for j, result in enumerate(batch_results):
					ts_code = batch_codes[j]

					if isinstance(result, Exception):
						logger.error(f"计算股票 {ts_code} 的因子 {factor_name} 失败: {str(result)}")
						failed_calculations.append({
							"ts_code": ts_code,
							"error": str(result)
						})
					else:
						try:
							# 保存因子数据
							await self._save_factor_data(
								factor_name=factor_name,
								ts_code=ts_code,
								factor_values=result
							)
							calculated_count += 1
						except Exception as e:
							logger.error(f"保存因子数据失败: {str(e)}")
							failed_calculations.append({
								"ts_code": ts_code,
								"error": f"保存失败: {str(e)}"
							})

				# 更新进度
				progress = ((i + len(batch_codes)) / total_stocks) * 100

				# 发布进度事件
				await self._publish_research_event(
					event_type="progress",
					research_id=task_id,
					factor_name=factor_name,
					progress=progress,
					calculated_count=calculated_count,
					total_stocks=total_stocks,
					user_id=user_id
				)

			# 清理相关缓存
			await self._clean_factor_cache(factor_name)

			# 发布计算完成事件
			await self._publish_research_event(
				event_type="calculation_completed",
				research_id=task_id,
				factor_name=factor_name,
				calculated_count=calculated_count,
				total_stocks=total_stocks,
				failed_count=len(failed_calculations),
				user_id=user_id
			)

			logger.info(f"因子计算完成，因子: {factor_name}, 计算数量: {calculated_count}")

			return {
				"success": True,
				"task_id": task_id,
				"factor_name": factor_name,
				"calculated_count": calculated_count,
				"total_stocks": total_stocks,
				"failed_calculations": failed_calculations,
				"date_range": {
					"start": start_date.isoformat(),
					"end": end_date.isoformat()
				},
				"message": f"成功计算 {calculated_count} 只股票的因子数据"
			}

		except Exception as e:
			logger.error(f"因子计算失败: {str(e)}", exc_info=True)

			# 发布失败事件
			await self._publish_research_event(
				event_type="calculation_failed",
				research_id=task_id,
				factor_name=factor_name,
				error=str(e),
				user_id=user_id
			)

			raise

	# ==================== 因子分析主方法 ====================

	async def analyze_factor_performance (
			self,
			factor_name: str,
			universe: Optional[List[str]] = None,
			start_date: Optional[datetime] = None,
			end_date: Optional[datetime] = None,
			analysis_type: str = "ic_analysis",
			parameters: Optional[Dict[str, Any]] = None,
			user_id: Optional[str] = None
	) -> Dict[str, Any]:
		"""
		分析因子表现

		Args:
			factor_name: 因子名称
			universe: 股票池，不指定则使用全市场股票
			start_date: 开始日期
			end_date: 结束日期
			analysis_type: 分析类型，支持：
				- ic_analysis: IC分析
				- quantile_analysis: 分位数分析
				- correlation_analysis: 相关性分析
				- stability_analysis: 稳定性分析
			parameters: 分析参数
			user_id: 用户ID

		Returns:
			Dict: 分析结果，包含：
				- success: 是否成功
				- factor_name: 因子名称
				- analysis_type: 分析类型
				- analysis_result: 分析结果详情
				- report: 分析报告
				- date_range: 日期范围
				- message: 状态消息
		"""
		logger.info(f"开始分析因子表现，因子: {factor_name}, 类型: {analysis_type}")

		try:
			# 获取因子数据
			# 将 datetime 类型转换为 date 类型
			start_date_date = start_date.date() if isinstance(start_date, datetime) else start_date
			end_date_date = end_date.date() if isinstance(end_date, datetime) else end_date
			factor_data = await self._get_factor_data_for_analysis(
				factor_name=factor_name,
				universe=universe,
				start_date=start_date_date,
				end_date=end_date_date
			)

			if factor_data.empty:
				return {
					"success": False,
					"factor_name": factor_name,
					"error": "没有找到因子数据",
					"message": "无法进行因子表现分析"
				}

			# 初始化收益数据
			returns_data = None

			# 检查是否需要收益数据
			if analysis_type in ["ic_analysis", "quantile_analysis"]:
				# 获取收益数据
				# 将 datetime 类型转换为 date 类型
				start_date_date = start_date.date() if isinstance(start_date, datetime) else start_date
				end_date_date = end_date.date() if isinstance(end_date, datetime) else end_date
				returns_data = await self._get_returns_data_for_analysis(
					universe=universe,
					start_date=start_date_date,
					end_date=end_date_date
				)

				if returns_data.empty:
					return {
						"success": False,
						"factor_name": factor_name,
						"error": "没有找到收益数据",
						"message": "无法进行收益相关分析"
					}

			# 执行分析
			analysis_methods = {
				"ic_analysis": self._perform_ic_analysis,
				"quantile_analysis": self._perform_quantile_analysis,
				"correlation_analysis": self._perform_correlation_analysis,
				"stability_analysis": self._perform_stability_analysis
			}

			method = analysis_methods.get(analysis_type)
			if not method:
				return {
					"success": False,
					"factor_name": factor_name,
					"error": f"不支持的分析类型: {analysis_type}",
					"message": "无法执行分析"
				}

			# 执行分析
			if analysis_type in ["ic_analysis", "quantile_analysis"]:
				analysis_result = await method(
					factor_data=factor_data,
					returns_data=returns_data,
					parameters=parameters
				)
			elif analysis_type == "correlation_analysis":
				# 实例方法需要直接调用
				analysis_result = await self._perform_correlation_analysis(
					factor_data=factor_data,
					factor_name=factor_name,
					start_date=start_date,
					end_date=end_date
				)
			else:
				analysis_result = await method(
					factor_data=factor_data,
					returns_data=returns_data
				)

			# 生成分析报告
			report = await self.generate_analysis_report(
				analysis_result=analysis_result,
				factor_name=factor_name,
				analysis_type=analysis_type
			)

			# 缓存分析结果
			cache_key = CacheKey.FACTOR_ANALYSIS.format(
				factor=factor_name,
				analysis=analysis_type,
				start=start_date.isoformat() if start_date else "all",
				end=end_date.isoformat() if end_date else "all"
			)

			await self.cache.set(
				cache_key,
				{
					"analysis_result": analysis_result,
					"report": report,
					"generated_at": datetime.now().isoformat()
				},
				ttl=86400  # 24小时
			)

			logger.info(f"因子表现分析完成，因子: {factor_name}")

			return {
				"success": True,
				"factor_name": factor_name,
				"analysis_type": analysis_type,
				"analysis_result": analysis_result,
				"report": report,
				"date_range": {
					"start": start_date.isoformat() if start_date else None,
					"end": end_date.isoformat() if end_date else None
				},
				"message": "因子表现分析完成"
			}

		except Exception as e:
			logger.error(f"因子表现分析失败: {str(e)}", exc_info=True)

			# 发布分析失败事件
			await self._publish_research_event(
				event_type="analysis_failed",
				factor_name=factor_name,
				analysis_type=analysis_type,
				error=str(e),
				user_id=user_id
			)

			raise

	async def compare_factors (
			self,
			factor_names: List[str],
			universe: Optional[List[str]] = None,
			start_date: Optional[date] = None,
			end_date: Optional[date] = None,
			metrics: Optional[List[str]] = None,
			parameters: Optional[Dict[str, Any]] = None,
			user_id: Optional[str] = None
	) -> Dict[str, Any]:
		"""
		比较多个因子表现

		Args:
			factor_names: 因子名称列表
			universe: 股票池
			start_date: 开始日期
			end_date: 结束日期
			metrics: 比较指标列表，支持：
				- ic_mean: IC均值
				- ic_ir: IC信息比率
				- ic_std: IC标准差
				- turnover: 换手率
				- sharpe_ratio: 夏普比率
				- max_drawdown: 最大回撤
			parameters: 比较参数
			user_id: 用户ID

		Returns:
			Dict: 比较结果，包含：
				- success: 是否成功
				- comparison_results: 比较结果详情
				- comparison_report: 比较报告
				- factor_count: 因子数量
				- date_range: 日期范围
				- message: 状态消息
		"""
		logger.info(f"开始比较因子，因子列表: {factor_names}")

		try:
			if not metrics:
				metrics = ["ic_mean", "ic_ir", "ic_std", "turnover", "sharpe_ratio", "max_drawdown"]

			comparison_results = {}
			failed_factors = []

			# 发布比较开始事件
			await self._publish_research_event(
				event_type="comparison_started",
				factor_names=factor_names,
				metrics=metrics,
				user_id=user_id
			)

			# 分析每个因子的表现
			for factor_name in factor_names:
				try:
					# 分析因子表现
					analysis_result = await self.analyze_factor_performance(
						factor_name=factor_name,
						universe=universe,
						start_date=start_date,
						end_date=end_date,
						analysis_type="ic_analysis",
						parameters=parameters,
						user_id=user_id
					)

					if analysis_result.get("success") and analysis_result.get("analysis_result"):
						# 提取关键指标
						factor_metrics = self._extract_factor_metrics(
							analysis_result["analysis_result"],
							metrics
						)

						comparison_results[factor_name] = factor_metrics
					else:
						failed_factors.append({
							"factor_name": factor_name,
							"error": analysis_result.get("error", "分析失败")
						})

				except Exception as e:
					logger.error(f"分析因子 {factor_name} 失败: {str(e)}")
					failed_factors.append({
						"factor_name": factor_name,
						"error": str(e)
					})

			# 生成比较报告
			comparison_report = await self._generate_comparison_report(
				comparison_results=comparison_results,
				factor_names=factor_names,
				metrics=metrics,
				failed_factors=failed_factors
			)

			# 发布比较完成事件
			await self._publish_research_event(
				event_type="comparison_completed",
				factor_names=factor_names,
				comparison_report=comparison_report,
				user_id=user_id
			)

			logger.info(f"因子比较完成，比较因子数量: {len(factor_names)}")

			return {
				"success": True,
				"comparison_results": comparison_results,
				"comparison_report": comparison_report,
				"factor_count": len(factor_names),
				"failed_factors": failed_factors,
				"date_range": {
					"start": start_date.isoformat() if start_date else None,
					"end": end_date.isoformat() if end_date else None
				},
				"message": "因子比较完成"
			}

		except Exception as e:
			logger.error(f"因子比较失败: {str(e)}", exc_info=True)

			# 发布比较失败事件
			await self._publish_research_event(
				event_type="comparison_failed",
				factor_names=factor_names,
				error=str(e),
				user_id=user_id
			)

			raise

	# ==================== 因子元数据方法 ====================

	async def get_factor_metadata (
			self,
			factor_name: Optional[str] = None,
			category: Optional[str] = None
	) -> List[Dict[str, Any]]:
		"""
		获取因子元数据

		Args:
			factor_name: 因子名称（可选，不指定则返回所有）
			category: 因子类别（可选）

		Returns:
			List[Dict]: 因子元数据列表，包含以下字段：
				- factor_name: 因子名称
				- display_name: 显示名称
				- description: 因子描述
				- category: 因子类别
				- formula: 因子公式
				- data_source: 数据来源
				- update_frequency: 更新频率
				- parameters: 计算参数
				- created_at: 创建时间
				- updated_at: 更新时间
		"""
		try:
			# 从数据库获取因子定义
			if factor_name:
				factor = await self.factor_def_repo.get_by_name(factor_name)
				factors = [factor] if factor else []
			elif category:
				factors = await self.factor_def_repo.get_by_category(category)
			else:
				# 获取所有激活的因子
				from sqlalchemy import select
				from shared.database.models.data_models import FactorDefinition
				stmt = select(FactorDefinition).where(FactorDefinition.is_active == True)
				result = await self.session.execute(stmt)
				factors = result.scalars().all()

			metadata_list = []
			for factor in factors:
				metadata_list.append({
					"factor_name": factor.factor_name,
					"display_name": factor.display_name or factor.factor_name,
					"description": factor.description,
					"category": factor.category,
					"formula": factor.formula,
					"data_source": factor.data_source,
					"update_frequency": factor.update_frequency,
					"parameters": factor.parameters,
					"created_at": factor.created_at.isoformat() if factor.created_at else None,
					"updated_at": factor.updated_at.isoformat() if factor.updated_at else None
				})

			return metadata_list

		except Exception as e:
			logger.error(f"获取因子元数据失败: {str(e)}")

			# 如果数据库中没有，返回标准因子
			return self._get_standard_factor_metadata(factor_name, category)

	async def create_factor_definition (
			self,
			factor_definition: Dict[str, Any],
			user_id: Optional[str] = None
	) -> Dict[str, Any]:
		"""
		创建因子定义

		Args:
			factor_definition: 因子定义
			user_id: 用户ID

		Returns:
			Dict: 创建结果
		"""
		try:
			# 验证因子定义
			if not factor_definition.get("factor_name"):
				return {
					"success": False,
					"error": "因子名称不能为空",
					"message": "无法创建因子定义"
				}

			# 检查是否已存在
			existing = await self.factor_def_repo.get_by_name(factor_definition["factor_name"])

			if existing:
				return {
					"success": False,
					"error": f"因子 {factor_definition['factor_name']} 已存在",
					"message": "无法创建重复的因子定义"
				}

			# 创建因子定义
			factor_data = {
				"factor_name": factor_definition["factor_name"],
				"display_name": factor_definition.get("display_name", factor_definition["factor_name"]),
				"description": factor_definition.get("description", ""),
				"category": factor_definition.get("category", "custom"),
				"formula": factor_definition.get("formula", ""),
				"data_source": factor_definition.get("data_source", "calculated"),
				"update_frequency": factor_definition.get("update_frequency", "daily"),
				"parameters": factor_definition.get("parameters", {}),
				"created_by": user_id,
				"created_at": datetime.now(),
				"updated_at": datetime.now()
			}

			await self.factor_def_repo.create(factor_data)

			# 清理缓存
			await self._clean_factor_metadata_cache()

			return {
				"success": True,
				"factor_name": factor_definition["factor_name"],
				"message": "因子定义创建成功"
			}

		except Exception as e:
			logger.error(f"创建因子定义失败: {str(e)}")
			return {
				"success": False,
				"error": str(e),
				"message": "创建因子定义失败"
			}

	# ==================== 因子计算核心方法 ====================

	async def _calculate_single_factor (
			self,
			factor_name: str,
			ts_code: str,
			start_date: datetime,
			end_date: datetime,
			parameters: Optional[Dict[str, Any]] = None
	) -> List[Dict[str, Any]]:
		"""
		计算单只股票的因子

		Args:
			factor_name: 因子名称
			ts_code: 股票代码
			start_date: 开始日期
			end_date: 结束日期
			parameters: 计算参数

		Returns:
			List[Dict]: 因子值列表，每个元素包含：
				- trade_date: 交易日期
				- factor_name: 因子名称
				- factor_value: 因子值
				- ts_code: 股票代码
				- calculated_at: 计算时间
		"""
		try:
			# 获取计算器
			calculator = self._factor_calculators.get(factor_name)
			if not calculator:
				# 默认使用技术指标计算
				calculator = self._calculate_technical_factor

			# 获取股票数据
			quotes = await self.quote_repo.get_by_code_and_date_range(
				ts_code=ts_code,
				start_date=start_date,
				end_date=end_date
			)

			if not quotes:
				return []

			# 转换为DataFrame
			df_data = []
			for quote in quotes:
				df_data.append({
					"trade_date": quote.trade_date,
					"open": float(quote.open) if quote.open else None,
					"high": float(quote.high) if quote.high else None,
					"low": float(quote.low) if quote.low else None,
					"close": float(quote.close) if quote.close else None,
					"volume": float(quote.vol) if quote.vol else None,
					"amount": float(quote.amount) if quote.amount else None,
					"pre_close": float(quote.pre_close) if quote.pre_close else None,
					"change": float(quote.change) if quote.change else None,
					"pct_chg": float(quote.pct_chg) if quote.pct_chg else None
				})

			if not df_data:
				return []

			df = pd.DataFrame(df_data)
			df.set_index("trade_date", inplace=True)
			df.sort_index(inplace=True)

			# 获取财务数据（如果需要）
			financial_data = None
			if factor_name in [StandardFactors.PE, StandardFactors.PB, StandardFactors.ROE]:
				financial_data = await self._get_financial_data(ts_code, start_date.date(), end_date.date())

			# 计算因子值
			if calculator == self._calculate_technical_factor:
				factor_series = calculator(df, parameters)
			elif calculator in [
				FactorResearchService._calculate_pe,
				FactorResearchService._calculate_pb,
				FactorResearchService._calculate_ps,
				FactorResearchService._calculate_roe,
				FactorResearchService._calculate_roa,
				FactorResearchService._calculate_gm,
				FactorResearchService._calculate_np_margin,
				FactorResearchService._calculate_debt_to_asset,
				FactorResearchService._calculate_current_ratio,
				FactorResearchService._calculate_quick_ratio,
				FactorResearchService._calculate_market_cap,
				FactorResearchService._calculate_turnover_rate
			]:
				# 静态方法，不需要parameters参数
				factor_series = calculator(df, financial_data)
			elif calculator in [
				FactorResearchService._calculate_return_1m,
				FactorResearchService._calculate_return_3m,
				FactorResearchService._calculate_return_6m,
				FactorResearchService._calculate_return_1y,
				FactorResearchService._calculate_volatility_1m,
				FactorResearchService._calculate_volatility_3m,
				FactorResearchService._calculate_volatility_6m,
				FactorResearchService._calculate_volatility_1y,
				FactorResearchService._calculate_sharpe_ratio,
				FactorResearchService._calculate_volume_ratio,
				FactorResearchService._calculate_ma,
				FactorResearchService._calculate_ema,
				FactorResearchService._calculate_macd,
				FactorResearchService._calculate_rsi,
				FactorResearchService._calculate_boll,
				FactorResearchService._calculate_kdj
			]:
				# 技术指标计算器，需要parameters参数
				factor_series = calculator(df, parameters)
			else:
				# 其他计算器，只需要df参数
				factor_series = calculator(df)

				if factor_series.empty:
					return []

			# 转换为标准格式
			result = []
			for date_val, factor_val in factor_series.items():
				# 转换日期值为Python datetime对象
				# 支持pandas Timestamp、datetime、date和字符串类型
				if isinstance(date_val, pd.Timestamp):
					trade_date = date_val.to_pydatetime()
				elif isinstance(date_val, str):
					# 尝试解析字符串日期
					try:
						trade_date = pd.to_datetime(date_val).to_pydatetime()
					except (ValueError, TypeError) as e:
						logger.warning(f"日期解析失败，使用当前时间: {str(e)}")
						trade_date = datetime.now()
				elif isinstance(date_val, datetime):
					trade_date = date_val
				elif isinstance(date_val, date):
					trade_date = datetime.combine(date_val, datetime.min.time())
				else:
					trade_date = datetime.now()

				result.append({
					"trade_date": trade_date,
					"factor_name": factor_name,
					"factor_value": float(factor_val) if not np.isnan(factor_val) else None,
					"ts_code": ts_code,
					"calculated_at": datetime.now()
				})

			return result

		except Exception as e:
			logger.error(f"计算股票 {ts_code} 的因子 {factor_name} 失败: {str(e)}")
			raise

	async def _save_factor_data (
			self,
			factor_name: str,
			ts_code: str,
			factor_values: List[Dict]
	):
		"""
		保存因子数据

		Args:
			factor_name: 因子名称
			ts_code: 股票代码
			factor_values: 因子值列表
		"""
		if not factor_values:
			return

		try:
			factor_data_list = []
			for factor_value in factor_values:
				if factor_value.get("factor_value") is None:
					continue

				# 检查是否已存在
				existing = await self.factor_repo.get_factor_data(
					factor_name=factor_name,
					ts_code=ts_code,
					trade_date=factor_value["trade_date"]
				)

				if existing:
					# 更新现有记录
					await self.factor_repo.update(existing.id, factor_value)
				else:
					factor_data_list.append(factor_value)

			# 批量创建新记录
			if factor_data_list:
				await self.factor_repo.batch_insert_factor_data(factor_data_list)

			# 批量提交
			await self.session.commit()

		except Exception as e:
			logger.error(f"保存因子数据失败: {str(e)}")
			await self.session.rollback()
			raise

	# ==================== 因子计算器实现 ====================

	def _init_factor_calculators (self) -> Dict[str, callable]:
		"""
		初始化因子计算器映射

		Returns:
			Dict: 因子计算器映射
		"""
		return {
			StandardFactors.PE: FactorResearchService._calculate_pe,
			StandardFactors.PB: FactorResearchService._calculate_pb,
			StandardFactors.PS: FactorResearchService._calculate_ps,
			StandardFactors.ROE: FactorResearchService._calculate_roe,
			StandardFactors.ROA: FactorResearchService._calculate_roa,
			StandardFactors.GROSS_MARGIN: FactorResearchService._calculate_gm,
			StandardFactors.OPERATING_MARGIN: FactorResearchService._calculate_np_margin,
			StandardFactors.DEBT_RATIO: FactorResearchService._calculate_debt_to_asset,
			"current_ratio": FactorResearchService._calculate_current_ratio,
			"quick_ratio": FactorResearchService._calculate_quick_ratio,
			StandardFactors.MARKET_CAP: FactorResearchService._calculate_market_cap,
			StandardFactors.RET_1M: FactorResearchService._calculate_return_1m,
			StandardFactors.RET_3M: FactorResearchService._calculate_return_3m,
			StandardFactors.RET_6M: FactorResearchService._calculate_return_6m,
			StandardFactors.RET_12M: FactorResearchService._calculate_return_1y,
			StandardFactors.VOLATILITY_1M: self._calculate_volatility_1m,
			StandardFactors.VOLATILITY_3M: self._calculate_volatility_3m,
			StandardFactors.VOLATILITY_12M: self._calculate_volatility_1y,
			StandardFactors.BETA: self._calculate_beta,
			"sharpe_ratio": self._calculate_sharpe_ratio,
			StandardFactors.TURNOVER_RATE: FactorResearchService._calculate_turnover_rate,
			"volume_ratio": self._calculate_volume_ratio,
			"MA": self._calculate_ma,
			"EMA": self._calculate_ema,
			"MACD": self._calculate_macd,
			"RSI": self._calculate_rsi,
			"BOLL": self._calculate_boll,
			"KDJ": self._calculate_kdj
		}

	@staticmethod
	def _calculate_technical_factor (
			df: DataFrame,
			parameters: Optional[Dict] = None
	) -> pd.Series:
		"""通用技术因子计算器"""
		factor_type = parameters.get("type", "close") if parameters else "close"

		if factor_type == "close":
			# 返回收盘价
			return df['close'] if 'close' in df.columns else pd.Series(dtype=float)
		elif factor_type == "volume":
			# 返回成交量
			return df['volume'] if 'volume' in df.columns else pd.Series(dtype=float)
		else:
			# 默认返回空序列
			return pd.Series(dtype=float)

	@staticmethod
	def _calculate_pe (
			df: DataFrame,
			financial_data: Optional[DataFrame] = None
	) -> pd.Series:
		"""计算市盈率"""
		if 'close' not in df.columns:
			return pd.Series(dtype=float, index=df.index)

		if financial_data is not None and 'eps' in financial_data.columns:
			# 使用实际财务数据
			eps = financial_data['eps']
			pe = df['close'] / eps
			return pe
		else:
			# 没有财务数据时返回空序列
			return pd.Series(dtype=float, index=df.index)

	@staticmethod
	def _calculate_pb (
			df: DataFrame,
			financial_data: Optional[DataFrame] = None
	) -> pd.Series:
		"""计算市净率"""
		if 'close' not in df.columns:
			return pd.Series(dtype=float, index=df.index)

		if financial_data is not None and 'bps' in financial_data.columns:
			# 使用实际财务数据
			bps = financial_data['bps']
			pb = df['close'] / bps
			return pb
		else:
			# 没有财务数据时返回空序列
			return pd.Series(dtype=float, index=df.index)

	@staticmethod
	def _calculate_ps (
			df: DataFrame
	) -> pd.Series:
		"""计算市销率"""
		return pd.Series(dtype=float, index=df.index)

	@staticmethod
	def _calculate_roe (
			df: DataFrame,
			financial_data: Optional[DataFrame] = None
	) -> pd.Series:
		"""计算净资产收益率"""
		if financial_data is not None and 'roe' in financial_data.columns:
			# 使用实际财务数据
			return financial_data['roe']
		else:
			# 没有财务数据时返回空序列
			return pd.Series(dtype=float, index=df.index)

	@staticmethod
	def _calculate_roa (
			df: DataFrame,
			financial_data: Optional[DataFrame] = None
	) -> pd.Series:
		"""计算总资产收益率"""
		if financial_data is not None and 'roa' in financial_data.columns:
			# 使用实际财务数据
			return financial_data['roa']
		else:
			# 没有财务数据时返回空序列
			return pd.Series(dtype=float, index=df.index)

	@staticmethod
	def _calculate_gm (
			df: DataFrame,
			financial_data: Optional[DataFrame] = None
	) -> pd.Series:
		"""计算毛利率"""
		if financial_data is not None and 'gross_margin' in financial_data.columns:
			# 使用实际财务数据
			return financial_data['gross_margin']
		else:
			# 没有财务数据时返回空序列
			return pd.Series(dtype=float, index=df.index)

	@staticmethod
	def _calculate_np_margin (
			df: DataFrame,
			financial_data: Optional[DataFrame] = None
	) -> pd.Series:
		"""计算净利率"""
		if financial_data is not None and 'net_profit_margin' in financial_data.columns:
			# 使用实际财务数据
			return financial_data['net_profit_margin']
		else:
			# 没有财务数据时返回空序列
			return pd.Series(dtype=float, index=df.index)

	@staticmethod
	def _calculate_debt_to_asset (
			df: DataFrame,
			financial_data: Optional[DataFrame] = None
	) -> pd.Series:
		"""计算资产负债率"""
		if financial_data is not None and 'debt_to_asset' in financial_data.columns:
			# 使用实际财务数据
			return financial_data['debt_to_asset']
		else:
			# 没有财务数据时返回空序列
			return pd.Series(dtype=float, index=df.index)

	@staticmethod
	def _calculate_current_ratio (
			df: DataFrame,
			financial_data: Optional[DataFrame] = None
	) -> pd.Series:
		"""计算流动比率"""
		if financial_data is not None and 'current_ratio' in financial_data.columns:
			# 使用实际财务数据
			return financial_data['current_ratio']
		else:
			# 没有财务数据时返回空序列
			return pd.Series(dtype=float, index=df.index)

	@staticmethod
	def _calculate_quick_ratio (
			df: DataFrame,
			financial_data: Optional[DataFrame] = None
	) -> pd.Series:
		"""计算速动比率"""
		if financial_data is not None and 'quick_ratio' in financial_data.columns:
			# 使用实际财务数据
			return financial_data['quick_ratio']
		else:
			# 没有财务数据时返回空序列
			return pd.Series(dtype=float, index=df.index)

	@staticmethod
	def _calculate_market_cap (
			df: DataFrame,
			financial_data: Optional[DataFrame] = None
	) -> pd.Series:
		"""计算市值"""
		if 'close' not in df.columns:
			return pd.Series(dtype=float, index=df.index)

		if financial_data is not None and 'float_shares' in financial_data.columns:
			# 使用实际流通股本数据
			float_shares = financial_data['float_shares']
			market_cap = df['close'] * float_shares
			return market_cap
		else:
			# 没有流通股本数据时返回空序列
			return pd.Series(dtype=float, index=df.index)

	@staticmethod
	def _calculate_return_1m (
			df: DataFrame,
			parameters: Optional[Dict] = None,
	) -> pd.Series:
		"""计算1个月收益率"""
		if 'close' not in df.columns:
			return pd.Series(dtype=float)

		window = parameters.get("window", 20) if parameters else 20  # 20个交易日约1个月
		returns = df['close'].pct_change(periods=window)

		return returns

	@staticmethod
	def _calculate_return_3m (
			df: DataFrame,
			parameters: Optional[Dict] = None,
	) -> pd.Series:
		"""计算3个月收益率"""
		if 'close' not in df.columns:
			return pd.Series(dtype=float)

		window = parameters.get("window", 60) if parameters else 60  # 60个交易日约3个月
		returns = df['close'].pct_change(periods=window)

		return returns

	@staticmethod
	def _calculate_return_6m (
			df: DataFrame,
			parameters: Optional[Dict] = None,
	) -> pd.Series:
		"""计算6个月收益率"""
		if 'close' not in df.columns:
			return pd.Series(dtype=float)

		window = parameters.get("window", 120) if parameters else 120  # 120个交易日约6个月
		returns = df['close'].pct_change(periods=window)

		return returns

	@staticmethod
	def _calculate_return_1y (
			df: DataFrame,
			parameters: Optional[Dict] = None,
	) -> pd.Series:
		"""计算12个月收益率"""
		if 'close' not in df.columns:
			return pd.Series(dtype=float)

		window = parameters.get("window", 240) if parameters else 240  # 240个交易日约12个月
		returns = df['close'].pct_change(periods=window)

		return returns

	@staticmethod
	def _calculate_volatility_1m (
			df: DataFrame,
			parameters: Optional[Dict] = None,
	) -> pd.Series:
		"""计算1个月波动率"""
		if 'close' not in df.columns:
			return pd.Series(dtype=float)

		window = parameters.get("window", 20) if parameters else 20
		returns = df['close'].pct_change()
		volatility = returns.rolling(window=window).std() * np.sqrt(252)  # 年化波动率

		return volatility

	@staticmethod
	def _calculate_volatility_3m (
			df: DataFrame,
			parameters: Optional[Dict] = None,
	) -> pd.Series:
		"""计算3个月波动率"""
		if 'close' not in df.columns:
			return pd.Series(dtype=float)

		window = parameters.get("window", 60) if parameters else 60
		returns = df['close'].pct_change()
		volatility = returns.rolling(window=window).std() * np.sqrt(252)  # 年化波动率

		return volatility

	@staticmethod
	def _calculate_volatility_6m (
			df: DataFrame,
			parameters: Optional[Dict] = None,
	) -> pd.Series:
		"""计算12个月波动率"""
		if 'close' not in df.columns:
			return pd.Series(dtype=float)

		window = parameters.get("window", 240) if parameters else 240
		returns = df['close'].pct_change()
		volatility = returns.rolling(window=window).std() * np.sqrt(252)  # 年化波动率

		return volatility

	@staticmethod
	def _calculate_beta (
			df: DataFrame,
	) -> pd.Series:
		"""计算Beta系数"""
		if 'close' not in df.columns:
			return pd.Series(dtype=float, index=df.index)

		# 这里应该使用实际的市场指数数据来计算Beta
		# 由于没有市场指数数据，暂时返回空序列
		# 实际实现时，需要获取市场指数的收益率数据，然后计算与个股收益率的协方差和市场指数的方差
		return pd.Series(dtype=float, index=df.index)

	@staticmethod
	def _calculate_volume_ratio (
			df: DataFrame,
			parameters: Optional[Dict] = None,
	) -> pd.Series:
		"""计算量比"""
		if 'volume' not in df.columns:
			return pd.Series(dtype=float)

		window = parameters.get("window", 5) if parameters else 5
		avg_volume = df['volume'].rolling(window=window).mean()
		volume_ratio = df['volume'] / avg_volume

		return volume_ratio

	@staticmethod
	def _calculate_sharpe_ratio (
			df: DataFrame,
			parameters: Optional[Dict] = None,
	) -> pd.Series:
		"""计算夏普比率"""
		if 'close' not in df.columns:
			return pd.Series(dtype=float)

		window = parameters.get("window", 240) if parameters else 240
		returns = df['close'].pct_change()

		# 计算年化收益和波动
		annual_return = returns.rolling(window=window).mean() * 252
		annual_vol = returns.rolling(window=window).std() * np.sqrt(252)

		# 计算夏普比率（假设无风险利率为3%）
		risk_free_rate = 0.03
		sharpe_ratio = (annual_return - risk_free_rate) / annual_vol

		return sharpe_ratio

	@staticmethod
	def _calculate_volatility_1y (
			df: DataFrame,
			parameters: Optional[Dict] = None,
	) -> pd.Series:
		"""计算12个月波动率"""
		if 'close' not in df.columns:
			return pd.Series(dtype=float)

		window = parameters.get("window", 240) if parameters else 240
		returns = df['close'].pct_change()
		volatility = returns.rolling(window=window).std() * np.sqrt(252)  # 年化波动率

		return volatility

	@staticmethod
	def _calculate_ma (
			df: pd.DataFrame,
			parameters: Optional[Dict] = None,
	) -> pd.Series:
		"""计算移动平均线"""
		if 'close' not in df.columns:
			return pd.Series(dtype=float, index=df.index)

		period = parameters.get("period", 20) if parameters else 20
		ma_type = parameters.get("type", "simple") if parameters else "simple"

		if ma_type == "simple":
			ma = df['close'].rolling(window=period).mean()
		elif ma_type == "weighted":
			# 加权移动平均线
			weights = np.arange(1, period + 1)
			ma = df['close'].rolling(window=period).apply(
				lambda x: np.average(x, weights=weights), raw=True
			)
		else:
			ma = df['close'].rolling(window=period).mean()

		return ma

	@staticmethod
	def _calculate_ema (
			df: pd.DataFrame,
			parameters: Optional[Dict] = None,
	) -> pd.Series:
		"""计算指数移动平均线"""
		if 'close' not in df.columns:
			return pd.Series(dtype=float, index=df.index)

		period = parameters.get("period", 12) if parameters else 12
		adjust = parameters.get("adjust", False) if parameters else False
		alpha = parameters.get("alpha", None) if parameters else None

		if alpha:
			ema = df['close'].ewm(alpha=alpha, adjust=adjust).mean()
		else:
			ema = df['close'].ewm(span=period, adjust=adjust).mean()

		return ema

	@staticmethod
	def _calculate_macd (
			df: DataFrame,
			parameters: Optional[Dict] = None,
	) -> pd.Series:
		"""计算MACD指标"""
		if 'close' not in df.columns:
			return pd.Series(dtype=float, index=df.index)

		fast_period = parameters.get("fast_period", 12) if parameters else 12
		slow_period = parameters.get("slow_period", 26) if parameters else 26
		# signal_period = parameters.get("signal_period", 9) if parameters else 9

		ema_fast = df['close'].ewm(span=fast_period, adjust=False).mean()
		ema_slow = df['close'].ewm(span=slow_period, adjust=False).mean()
		macd = ema_fast - ema_slow

		# 返回MACD线（DIF）
		return macd

	@staticmethod
	def _calculate_rsi (
			df: DataFrame,
			parameters: Optional[Dict] = None,
	) -> pd.Series:
		"""计算RSI指标"""
		if 'close' not in df.columns:
			return pd.Series(dtype=float, index=df.index)

		period = parameters.get("period", 14) if parameters else 14
		method = parameters.get("method", "wilder") if parameters else "wilder"

		delta = df['close'].diff()
		
		if method == "wilder":
			# Wilder's smoothing method
			gain = (delta.where(delta > 0, 0)).ewm(alpha=1/period, adjust=False).mean()
			loss = (-delta.where(delta < 0, 0)).ewm(alpha=1/period, adjust=False).mean()
		else:
			# Standard method
			gain = (delta.where(delta > 0, 0)).rolling(window=period).mean()
			loss = (-delta.where(delta < 0, 0)).rolling(window=period).mean()
		
		# 处理除零情况
		rs = gain / loss
		rs = rs.replace([np.inf, -np.inf], np.nan)
		rsi = 100 - (100 / (1 + rs))
		rsi = rsi.fillna(50)  # 当gain和loss都为0时，RSI设为50

		return rsi

	@staticmethod
	def _calculate_boll (
			df: DataFrame,
			parameters: Optional[Dict] = None,
	) -> pd.Series:
		"""计算布林带中轨"""
		if 'close' not in df.columns:
			return pd.Series(dtype=float, index=df.index)

		period = parameters.get("period", 20) if parameters else 20

		middle = df['close'].rolling(window=period).mean()

		# 返回中轨线
		return middle

	@staticmethod
	def _calculate_kdj (
			df: DataFrame,
			parameters: Optional[Dict] = None,
	) -> pd.Series:
		"""计算KDJ指标的K值"""
		required_cols = ['high', 'low', 'close']
		if not all(col in df.columns for col in required_cols):
			return pd.Series(dtype=float, index=df.index)

		n = parameters.get("n", 9) if parameters else 9
		m1 = parameters.get("m1", 3) if parameters else 3

		low_min = df['low'].rolling(window=n).min()
		high_max = df['high'].rolling(window=n).max()

		rsv = 100 * (df['close'] - low_min) / (high_max - low_min)
		rsv = rsv.fillna(50)

		k = rsv.ewm(alpha=1 / m1, adjust=False).mean()

		# 返回K值
		return k

	@staticmethod
	def _calculate_turnover_rate (
			df: DataFrame,
			financial_data: Optional[DataFrame] = None
	) -> pd.Series:
		"""计算换手率"""
		if 'volume' not in df.columns:
			return pd.Series(dtype=float, index=df.index)

		if financial_data is not None and 'float_shares' in financial_data.columns:
			# 使用实际流通股本数据
			float_shares = financial_data['float_shares']
			turnover_rate = df['volume'] / float_shares * 100
			return turnover_rate
		else:
			# 没有流通股本数据时返回空序列
			return pd.Series(dtype=float, index=df.index)

	# ==================== 因子分析方法实现 ====================
	@staticmethod
	async def _perform_ic_analysis (
			factor_data: DataFrame,
			returns_data: Optional[DataFrame] = None,
			parameters: Optional[Dict[str, Any]] = None
	) -> Dict[str, Any]:
		"""
		执行IC分析

		Args:
			factor_data: 因子数据DataFrame
			returns_data: 收益数据
			parameters: 分析参数

		Returns:
			Dict: IC分析结果
		"""
		if factor_data.empty:
			return {
				"ic_mean": 0,
				"ic_std": 0,
				"ic_ir": 0,
				"ic_series": [],
				"ic_pvalue": 1.0,
				"ic_positive_ratio": 0,
				"ic_decay": []
			}

		# 计算IC序列（因子值与未来收益的相关性）
		dates = factor_data.index
		ic_series = []
		ic_decay = []

		# 确保有收益数据
		if returns_data is None or returns_data.empty:
			logger.warning("缺少收益数据，无法计算IC")
			return {
				"ic_mean": 0,
				"ic_std": 0,
				"ic_ir": 0,
				"ic_series": [],
				"ic_pvalue": 1.0,
				"ic_positive_ratio": 0,
				"ic_decay": [],
				"sample_size": 0
			}

		# 计算每个时间点的IC值
		for dt in dates:
			try:
				# 获取当前日期的因子值
				if dt in factor_data.index:
					factor_values = factor_data.loc[dt]

					# 获取下一期的收益数据
					forward_period = int(parameters.get("forward_period", 1)) if parameters else 1
					forward_date = dt + pd.Timedelta(days=forward_period)

					if forward_date in returns_data.index:
						forward_returns = returns_data.loc[forward_date]

						# 计算相关系数（IC）
						# 确保 factor_values 和 forward_returns 是 Series 类型
						if isinstance(factor_values, pd.Series) and isinstance(forward_returns, pd.Series):
							valid_stocks = factor_values.dropna().index.intersection(forward_returns.dropna().index)
						else:
							valid_stocks = []

						if len(valid_stocks) >= 10:  # 至少需要10只股票
							try:
								corr_coef = np.corrcoef(factor_values[valid_stocks], forward_returns[valid_stocks])[
									0, 1]
								ic_series.append(corr_coef if not np.isnan(corr_coef) else 0)
							except (ValueError, TypeError):
								ic_series.append(0)
						else:
							ic_series.append(0)
					else:
						ic_series.append(0)
				else:
					ic_series.append(0)
			except Exception as e:
				logger.warning(f"计算IC值时出错: {str(e)}")
				ic_series.append(0)

		# 计算IC统计量
		ic_series = np.array(ic_series)
		ic_mean = float(np.mean(ic_series)) if len(ic_series) > 0 else 0
		ic_std = float(np.std(ic_series)) if len(ic_series) > 0 else 0
		ic_ir = ic_mean / ic_std if ic_std > 0 else 0

		# 计算t检验p值
		t_stat, ic_pvalue = stats.ttest_1samp(ic_series, 0) if len(ic_series) > 0 else (0, 1.0)

		# 计算IC正率
		ic_positive_ratio = sum(1 for x in ic_series if x > 0) / len(ic_series) if len(ic_series) > 0 else 0

		# 计算IC衰减（多期IC）
		for lag in range(1, 6):  # 1-5期衰减
			lag_ic_series = []
			for i in range(len(dates)):
				if i + lag < len(dates):
					lag_ic_series.append(ic_series[i + lag])

			if lag_ic_series:
				decay_value = np.mean(lag_ic_series)
				ic_decay.append({
					"lag": lag,
					"ic": round(decay_value, 4)
				})

		return {
			"ic_mean": round(ic_mean, 4),
			"ic_std": round(ic_std, 4),
			"ic_ir": round(ic_ir, 4),
			"ic_series": [round(x, 4) for x in ic_series],
			"ic_pvalue": round(float(ic_pvalue), 4),
			"ic_positive_ratio": round(ic_positive_ratio, 4),
			"ic_decay": ic_decay,
			"sample_size": len(dates)
		}

	@staticmethod
	async def _perform_quantile_analysis (
			factor_data: DataFrame,
			returns_data: Optional[DataFrame] = None,
			parameters: Optional[Dict[str, Any]] = None
	) -> Dict[str, Any]:
		"""
		执行分位数分析

		Args:
			factor_data: 因子数据DataFrame
			returns_data: 收益数据
			parameters: 分析参数

		Returns:
			Dict: 分位数分析结果
		"""
		if factor_data.empty:
			return {
				"quantile_returns": [],
				"top_minus_bottom": 0,
				"turnover_rate": [],
				"quantile_spread": [],
				"win_rate": 0
			}

		# 执行真实的分位数分析
		quantile_count = parameters.get("quantile_count", 5) if parameters else 5

		# 确保有收益数据
		if returns_data is None or returns_data.empty:
			logger.warning("缺少收益数据，无法进行分位数分析")
			return {
				"quantile_returns": [],
				"top_minus_bottom": 0,
				"turnover_rate": [],
				"quantile_spread": [],
				"win_rate": 0
			}

		# 计算每个时间点的分位数收益
		dates = factor_data.index
		quantile_returns_list = []
		win_rates = []

		for dt in dates:
			try:
				if dt in factor_data.index and dt in returns_data.index:
					# 确保 factor_values 和 forward_returns 是 Series 类型
					factor_values = factor_data.loc[dt]
					forward_returns = returns_data.loc[dt]
					if isinstance(factor_values, pd.Series):
						factor_values = factor_values.dropna()
					if isinstance(forward_returns, pd.Series):
						forward_returns = forward_returns.dropna()

					# 获取有效股票
					valid_stocks = factor_values.index.intersection(forward_returns.index)

					if len(valid_stocks) >= quantile_count * 10:  # 每个分位数组至少10只股票
						# 按因子值排序
						sorted_stocks = factor_values[valid_stocks].sort_values(ascending=False)

						# 计算分位数
						quantile_size = len(sorted_stocks) // quantile_count
						quantile_returns = []

						for i in range(quantile_count):
							start_idx = i * quantile_size
							end_idx = (i + 1) * quantile_size if i < quantile_count - 1 else len(sorted_stocks)

							quantile_stocks = sorted_stocks.index[start_idx:end_idx]
							quantile_return = forward_returns[quantile_stocks].mean()
							quantile_returns.append(quantile_return)

						quantile_returns_list.append(quantile_returns)

						# 计算胜率（最高分位数组是否跑赢最低分位数组）
						top_bottom_spread = quantile_returns[0] - quantile_returns[-1]
						win_rates.append(1 if top_bottom_spread > 0 else 0)
			except Exception as e:
				logger.warning(f"分位数分析时出错: {str(e)}")

		# 计算平均分位数收益
		if quantile_returns_list:
			avg_quantile_returns = np.mean(quantile_returns_list, axis=0)
			top_minus_bottom = avg_quantile_returns[0] - avg_quantile_returns[-1]
			win_rate = np.mean(win_rates) if win_rates else 0
		else:
			avg_quantile_returns = [0] * quantile_count
			top_minus_bottom = 0
			win_rate = 0

		# 计算分位价差
		quantile_spread = [
			round(avg_quantile_returns[i] - avg_quantile_returns[i + 1], 4)
			for i in range(len(avg_quantile_returns) - 1)
		]

		return {
			"quantile_count": quantile_count,
			"quantile_returns": [round(x, 4) for x in avg_quantile_returns],
			"top_minus_bottom": round(top_minus_bottom, 4),
			"turnover_rate": [],
			"quantile_spread": quantile_spread,
			"win_rate": round(win_rate, 4),
			"monotonicity": "monotonic" if all(avg_quantile_returns[i] >= avg_quantile_returns[i + 1] for i in
			                                   range(len(avg_quantile_returns) - 1)) else "non_monotonic"
		}

	async def _perform_correlation_analysis (
			self,
			factor_data: DataFrame,
			factor_name: str,
			start_date: Optional[datetime] = None,
			end_date: Optional[datetime] = None,
	) -> Dict[str, Any]:
		"""
		执行相关性分析

		Args:
			factor_data: 因子数据
			factor_name: 因子名称
			start_date: 开始日期
			end_date: 结束日期

		Returns:
			Dict: 相关性分析结果
		"""
		if factor_data.empty:
			return {
				"correlation_matrix": [],
				"mean_correlation": 0,
				"max_correlation": 0,
				"min_correlation": 0,
				"orthogonality_score": 0
			}

		# 获取其他因子数据进行比较
		category = "all"
		if factor_data.columns:
			first_column = factor_data.columns[0]
			if isinstance(first_column, str):
				parts = first_column.split('_')
				if parts:
					category = parts[0]
		other_factors = await self.factor_def_repo.get_by_category(category)
		other_factor_names = [f.factor_name for f in other_factors if f.factor_name != factor_name][:5]  # 最多比较5个其他因子

		# 构建因子数据矩阵
		factor_matrix = pd.DataFrame(index=factor_data.index)
		factor_matrix[factor_name] = factor_data.iloc[:, 0] if isinstance(factor_data, pd.DataFrame) else factor_data

		# 获取其他因子数据
		for other_factor in other_factor_names:
			try:
				other_data = await self._get_factor_data_for_analysis(
					factor_name=other_factor,
					universe=None,
					start_date=start_date,
					end_date=end_date
				)
				if not other_data.empty:
					factor_matrix[other_factor] = other_data.iloc[:, 0]
			except Exception as e:
				logger.warning(f"获取因子 {other_factor} 数据失败: {str(e)}")

		# 计算相关性矩阵
		correlation_matrix = factor_matrix.corr().values.tolist()
		correlation_values = []

		# 提取非对角线元素
		for i in range(len(correlation_matrix)):
			for j in range(i + 1, len(correlation_matrix)):
				if not np.isnan(correlation_matrix[i][j]):
					correlation_values.append(correlation_matrix[i][j])

		# 计算统计指标
		mean_correlation = np.mean(correlation_values) if correlation_values else 0
		max_correlation = np.max(correlation_values) if correlation_values else 0
		min_correlation = np.min(correlation_values) if correlation_values else 0

		# 计算正交性得分（1 - 平均绝对相关性）
		orthogonality_score = 1 - np.mean(np.abs(correlation_values)) if correlation_values else 1

		return {
			"correlation_matrix": correlation_matrix,
			"mean_correlation": float(mean_correlation),
			"max_correlation": float(max_correlation),
			"min_correlation": float(min_correlation),
			"orthogonality_score": float(orthogonality_score),
			"compared_factors": list(factor_matrix.columns)
		}

	@staticmethod
	async def _perform_stability_analysis (
			factor_data: DataFrame,
			returns_data: Optional[DataFrame] = None,
	) -> Dict[str, Any]:
		"""
		执行稳定性分析

		Args:
			factor_data: 因子数据
			returns_data: 收益数据

		Returns:
			Dict: 稳定性分析结果
		"""
		if factor_data.empty:
			return {
				"stability_score": 0,
				"period_consistency": [],
				"rank_ic": 0,
				"ic_stability": 0
			}

		# 执行真实的稳定性分析
		dates = factor_data.index
		period_consistency = []
		ic_values = []
		rank_ic_values = []

		# 确保有收益数据
		if returns_data is None or returns_data.empty:
			logger.warning("缺少收益数据，无法进行稳定性分析")
			return {
				"stability_score": 0,
				"period_consistency": [],
				"rank_ic": 0,
				"ic_stability": 0
			}

		# 将数据按季度分组
		try:
			# 转换为季度数据
			dates_quarterly = pd.to_datetime(dates).to_period("Q")
			unique_quarters = sorted(dates_quarterly.unique.tolist())

			for quarter in unique_quarters:
				try:
					# 获取该季度的数据
					quarter_dates = dates[dates_quarterly == quarter]

					if len(quarter_dates) >= 10:  # 至少需要10个交易日
						quarter_ic_values = []
						quarter_rank_ic_values = []

						for dt in quarter_dates:
							try:
								if dt in factor_data.index and dt in returns_data.index:
									# 确保 factor_values 和 forward_returns 是 Series 类型
									factor_values = factor_data.loc[dt]
									forward_returns = returns_data.loc[dt]
									if isinstance(factor_values, pd.Series):
										factor_values = factor_values.dropna()
									if isinstance(forward_returns, pd.Series):
										forward_returns = forward_returns.dropna()

									valid_stocks = factor_values.index.intersection(forward_returns.index)

									if len(valid_stocks) >= 10:
										# 计算IC值
										try:
											corr_coef = np.corrcoef(factor_values[valid_stocks], forward_returns[valid_stocks])[0, 1]
											if not np.isnan(corr_coef):
												quarter_ic_values.append(corr_coef)
										except (ValueError, TypeError):
											pass

										# 计算Rank IC值
										try:
											rank_factor_values = factor_values[valid_stocks].rank()
											rank_returns = forward_returns[valid_stocks].rank()
											rank_corr_coef = np.corrcoef(rank_factor_values, rank_returns)[0, 1]
											if not np.isnan(rank_corr_coef):
												quarter_rank_ic_values.append(rank_corr_coef)
										except (ValueError, TypeError):
											pass
							except (ValueError, TypeError):
								pass

						# 计算季度平均值
						quarter_ic = np.mean(quarter_ic_values) if quarter_ic_values else 0
						quarter_rank_ic = np.mean(quarter_rank_ic_values) if quarter_rank_ic_values else 0

						period_consistency.append({
							"period": str(quarter),
							"ic": round(quarter_ic, 4),
							"rank_ic": round(quarter_rank_ic, 4)
						})

						ic_values.append(quarter_ic)
						rank_ic_values.append(quarter_rank_ic)

				except Exception as e:
					logger.warning(f"处理季度 {quarter} 数据时出错: {str(e)}")
		except Exception as e:
			logger.warning(f"稳定性分析时出错: {str(e)}")

		# 计算稳定性指标
		if ic_values:
			# 稳定性得分（IC值的标准差越小越稳定）
			ic_std = float(np.std(ic_values))
			stability_score = max(0.0, 1 - ic_std)  # 标准差越小，稳定性得分越高

			# Rank IC平均值
			rank_ic_avg = np.mean(rank_ic_values)

			# IC稳定性（IC值的变异系数）
			ic_mean = float(np.mean(ic_values))
			if ic_mean > 0:
				ic_stability = 1 - (ic_std / ic_mean)
			else:
				ic_stability = 0
		else:
			stability_score = 0
			rank_ic_avg = 0
			ic_stability = 0

		return {
			"stability_score": round(stability_score, 4),
			"period_consistency": period_consistency,
			"rank_ic": round(rank_ic_avg, 4),
			"ic_stability": round(ic_stability, 4)
		}

	# ==================== 报告生成方法 ====================
	@staticmethod
	async def generate_analysis_report (
			analysis_result: Dict[str, Any],
			factor_name: str,
			analysis_type: str
	) -> Dict[str, Any]:
		"""
		生成分析报告

		Args:
			analysis_result: 分析结果
			factor_name: 因子名称
			analysis_type: 分析类型

		Returns:
			Dict: 分析报告
		"""
		report = {
			"factor_name": factor_name,
			"analysis_type": analysis_type,
			"generated_at": datetime.now().isoformat(),
			"summary": {},
			"details": analysis_result,
			"recommendations": [],
			"risk_warnings": []
		}

		# 根据分析结果生成总结
		if analysis_type == "ic_analysis":
			ic_mean = analysis_result.get("ic_mean", 0)
			ic_ir = analysis_result.get("ic_ir", 0)

			report["summary"] = {
				"ic_mean": ic_mean,
				"ic_ir": ic_ir,
				"significance": "significant" if abs(ic_mean) > 0.03 else "insignificant",
				"stability": "stable" if ic_ir > 0.5 else "unstable",
				"sample_size": analysis_result.get("sample_size", 0)
			}

			# 生成建议
			if ic_mean > 0.05 and ic_ir > 0.5:
				report["recommendations"].append("因子表现优秀，可以考虑用于策略")
				report["recommendations"].append("建议进行回测验证策略效果")
			elif ic_mean > 0.03:
				report["recommendations"].append("因子表现良好，需要进一步验证")
				report["recommendations"].append("建议结合其他因子使用")
			else:
				report["recommendations"].append("因子表现一般，建议优化或寻找其他因子")

			# 风险警告
			if ic_std := analysis_result.get("ic_std"):
				if ic_std > 0.2:
					report["risk_warnings"].append("因子IC波动较大，风险较高")

		elif analysis_type == "quantile_analysis":
			top_minus_bottom = analysis_result.get("top_minus_bottom", 0)
			win_rate = analysis_result.get("win_rate", 0)

			report["summary"] = {
				"top_minus_bottom": top_minus_bottom,
				"win_rate": win_rate,
				"profitability": "profitable" if top_minus_bottom > 0.05 else "unprofitable",
				"consistency": "consistent" if win_rate > 0.6 else "inconsistent"
			}

			if top_minus_bottom > 0.1:
				report["recommendations"].append("因子区分度很高，适合用于选股")
				report["recommendations"].append("建议构建多空组合")
			elif top_minus_bottom > 0.05:
				report["recommendations"].append("因子有一定区分度，可以尝试使用")
				report["recommendations"].append("建议结合风险控制")
			else:
				report["recommendations"].append("因子区分度不足，建议优化")

			# 风险警告
			turnover_rates = analysis_result.get("turnover_rate", [])
			if turnover_rates and max(turnover_rates) > 0.5:
				report["risk_warnings"].append("组合换手率较高，交易成本可能影响收益")

		elif analysis_type == "stability_analysis":
			stability_score = analysis_result.get("stability_score", 0)

			report["summary"] = {
				"stability_score": stability_score,
				"stability_level": "high" if stability_score > 0.7 else ("medium" if stability_score > 0.5 else "low")
			}

			if stability_score > 0.7:
				report["recommendations"].append("因子稳定性良好，适合长期使用")
			elif stability_score > 0.5:
				report["recommendations"].append("因子稳定性一般，需要定期评估")
			else:
				report["recommendations"].append("因子稳定性较差，建议谨慎使用")
				report["risk_warnings"].append("因子表现可能随时间变化，存在失效风险")

		return report

	@staticmethod
	async def _generate_comparison_report (
			comparison_results: Dict[str, Any],
			factor_names: List[str],
			metrics: List[str],
			failed_factors: Optional[List[Dict]] = None
	) -> Dict[str, Any]:
		"""
		生成比较报告

		Args:
			comparison_results: 比较结果
			factor_names: 因子名称列表
			metrics: 比较指标列表
			failed_factors: 失败因子列表

		Returns:
			Dict: 比较报告
		"""
		# 计算排名
		rankings = {}

		for metric in metrics:
			metric_values = []
			for factor_name in factor_names:
				if factor_name in comparison_results and metric in comparison_results[factor_name]:
					metric_values.append((factor_name, comparison_results[factor_name][metric]))

			if not metric_values:
				continue

			# 按值排序（对于IC和夏普比率，越大越好；对于最大回撤，越小越好）
			if metric in ["ic_mean", "ic_ir", "sharpe_ratio", "win_rate", "stability_score"]:
				metric_values.sort(key=lambda x: x[1] if x[1] is not None else -float('inf'), reverse=True)
			elif metric in ["max_drawdown", "ic_std", "turnover"]:
				metric_values.sort(key=lambda x: x[1] if x[1] is not None else float('inf'))
			else:
				metric_values.sort(key=lambda x: x[1] if x[1] is not None else -float('inf'), reverse=True)

			rankings[metric] = [
				{"factor_name": factor_name, "value": value, "rank": i + 1}
				for i, (factor_name, value) in enumerate(metric_values)
			]

		# 计算综合排名
		factor_scores = {factor_name: 0 for factor_name in factor_names}

		for metric, ranking in rankings.items():
			for item in ranking:
				factor_scores[item["factor_name"]] += len(factor_names) - item["rank"] + 1

		# 综合排名
		final_ranking = sorted(
			factor_scores.items(),
			key=lambda x: x[1],
			reverse=True
		)

		# 生成报告
		report: Dict[str, Any] = {
			"rankings": rankings,
			"final_ranking": [
				{"factor_name": factor_name, "score": score, "rank": i + 1}
				for i, (factor_name, score) in enumerate(final_ranking)
			],
			"best_factor": final_ranking[0][0] if final_ranking else None,
			"worst_factor": final_ranking[-1][0] if final_ranking else None,
			"failed_factors": failed_factors or [],
			"total_factors": len(factor_names),
			"successful_factors": len(comparison_results),
			"generated_at": datetime.now().isoformat(),
			"recommendations": []
		}

		# 生成建议
		if report["best_factor"]:
			report["recommendations"].append(f"表现最佳的因子是: {report['best_factor']}")

		if len(failed_factors or []) > 0:
			report["recommendations"].append(f"有 {len(failed_factors)} 个因子分析失败，需要检查数据质量")

		if len(comparison_results) >= 2:
			# 检查因子多样性
			top_factors = [item["factor_name"] for item in report["final_ranking"][:3]]
			report["recommendations"].append(f"建议考虑前3名因子: {', '.join(top_factors)}")

		return report

	# ==================== 数据获取方法 ====================

	async def _get_factor_data_for_analysis (
			self,
			factor_name: str,
			universe: Optional[List[str]] = None,
			start_date: Optional[date] = None,
			end_date: Optional[date] = None
	) -> DataFrame:
		"""
		获取用于分析的因子数据

		Args:
			factor_name: 因子名称
			universe: 股票池
			start_date: 开始日期
			end_date: 结束日期

		Returns:
			pd.DataFrame: 因子数据（行为日期，列为股票，值为因子值）
		"""
		try:
			from sqlalchemy import select, and_

			# 构建查询
			query = select(self.factor_repo.model).where(
				self.factor_repo.model.factor_name == factor_name
			)

			# 添加universe条件
			if universe and isinstance(universe, list):
				query = query.where(self.factor_repo.model.ts_code.in_(universe))

			# 添加日期范围条件
			if start_date:
				query = query.where(self.factor_repo.model.trade_date >= start_date)

			if end_date:
				query = query.where(self.factor_repo.model.trade_date <= end_date)

			# 执行查询
			result = await self.factor_repo.session.execute(query)
			factor_records = result.scalars().all()

			if not factor_records:
				return pd.DataFrame()

			# 转换为DataFrame
			data = []
			for record in factor_records:
				if record.factor_value is not None:
					data.append({
						"trade_date": record.trade_date,
						"ts_code": record.ts_code,
						"factor_value": float(record.factor_value)
					})

			if not data:
				return pd.DataFrame()

			df = pd.DataFrame(data)

			# 透视表：行为日期，列为股票，值为因子值
			pivot_df = df.pivot_table(
				index="trade_date",
				columns="ts_code",
				values="factor_value"
			)

			return pivot_df

		except Exception as e:
			logger.error(f"获取因子数据失败: {str(e)}")
			return pd.DataFrame()

	async def _get_returns_data_for_analysis (
			self,
			universe: Optional[List[str]] = None,
			start_date: Optional[date] = None,
			end_date: Optional[date] = None
	) -> DataFrame:
		"""
		获取用于分析的收益数据

		Args:
			universe: 股票池
			start_date: 开始日期
			end_date: 结束日期

		Returns:
			pd.DataFrame: 收益数据，行是日期，列是股票代码，值是收益率
		"""
		try:
			# 获取股票列表
			if not universe:
				stocks = await self.stock_repo.get_all(limit=100)
				universe = [stock.ts_code for stock in stocks]

			if not universe:
				return pd.DataFrame()

			# 初始化收益数据
			returns_data = {}

			# 批量获取每只股票的收益率
			for ts_code in universe:
				try:
					# 从StockDailyRepository获取行情数据
					# 确保日期为datetime类型
					start_datetime = datetime.combine(start_date, datetime.min.time()) if isinstance(start_date, date) else start_date
					end_datetime = datetime.combine(end_date, datetime.min.time()) if isinstance(end_date, date) else end_date
					quotes = await self.quote_repo.get_by_code_and_date_range(
						ts_code=ts_code,
						start_date=start_datetime,
						end_date=end_datetime
					)

					if quotes:
						# 转换为DataFrame
						df = pd.DataFrame([
							{
								'trade_date': quote.trade_date,
								'close': float(quote.close) if quote.close else None,
								'pre_close': float(quote.pre_close) if quote.pre_close else None
							}
							for quote in quotes
						])

						if not df.empty:
							df['trade_date'] = pd.to_datetime(df['trade_date'])
							df.set_index('trade_date', inplace=True)
							df.sort_index(inplace=True)

							# 计算每日收益率
							df['return'] = (df['close'] - df['pre_close']) / df['pre_close']
							returns_data[ts_code] = df['return']
				except Exception as e:
					logger.warning(f"获取股票 {ts_code} 收益数据失败: {str(e)}")

			# 合并所有股票的收益率
			if returns_data:
				returns_df = pd.DataFrame(returns_data)
				returns_df.index = pd.to_datetime(returns_df.index)
				return returns_df
			else:
				return pd.DataFrame()

		except Exception as e:
			logger.error(f"获取收益数据失败: {str(e)}")
			return pd.DataFrame()

	async def _get_financial_data (
			self,
			ts_code: str,
			start_date: date,
			end_date: date
	) -> Optional[pd.DataFrame]:
		"""
		获取财务数据

		Args:
			ts_code: 股票代码
			start_date: 开始日期
			end_date: 结束日期

		Returns:
			pd.DataFrame: 财务数据
		"""
		try:
				# 从FinancialStatementRepository获取财务数据
			# 获取财务报表数据
			financial_statements = await self.financial_repo.get_financial_statements(
				ts_code=ts_code,
				report_type="income_statement",  # 利润表数据
				start_date=start_date,
				end_date=end_date
			)

			# 合并数据，按报告日期匹配
			financial_data = {}
			
			# 处理财务报表数据
			for stmt in financial_statements:
				date_key = stmt.end_date
				if date_key not in financial_data:
					financial_data[date_key] = {}
				# 使用模型中实际存在的属性
				financial_data[date_key].update({
					'basic_eps': float(stmt.basic_eps) if stmt.basic_eps else None,
					'diluted_eps': float(stmt.diluted_eps) if stmt.diluted_eps else None,
					'revenue': float(stmt.revenue) if stmt.revenue else None,
					'oper_cost': float(stmt.oper_cost) if stmt.oper_cost else None,
					'operate_profit': float(stmt.operate_profit) if stmt.operate_profit else None,
					'n_income': float(stmt.n_income) if stmt.n_income else None,
					'n_income_attr_p': float(stmt.n_income_attr_p) if stmt.n_income_attr_p else None
				})
			
			# 计算财务指标
			for date_key, data in financial_data.items():
				# 计算EPS
				data['eps'] = data.get('basic_eps') or data.get('diluted_eps')
				
				# 计算毛利率
				if data.get('revenue') and data.get('revenue') > 0 and data.get('oper_cost'):
					data['gross_margin'] = (data['revenue'] - data['oper_cost']) / data['revenue']
				else:
					data['gross_margin'] = None
				
				# 计算净利率
				if data.get('revenue') and data.get('revenue') > 0 and data.get('n_income'):
					data['net_profit_margin'] = data['n_income'] / data['revenue']
				else:
					data['net_profit_margin'] = None
				
				# 由于模型中没有资产负债表数据，以下指标暂时设为None
				data['roe'] = None
				data['roa'] = None
				data['debt_to_asset'] = None
				data['current_ratio'] = None
				data['quick_ratio'] = None
				data['bps'] = None
				data['float_shares'] = None

			if not financial_data:
				return None

			# 转换为DataFrame
			df_data = []
			for report_date, data in financial_data.items():
				data['report_date'] = report_date
				df_data.append(data)

			if not df_data:
				return None

			df = pd.DataFrame(df_data)
			df['report_date'] = pd.to_datetime(df['report_date'])
			df.set_index('report_date', inplace=True)
			df.sort_index(inplace=True)

			# 向前填充财务数据，使每个交易日都有对应的数据
			# 获取日期范围
			date_range = pd.date_range(start=start_date, end=end_date, freq='D')
			result_df = pd.DataFrame(index=date_range)

			# 对于每个财务指标，使用最近的可用值
			for col in df.columns:
				result_df[col] = df[col].reindex(result_df.index, method='ffill')

			return result_df

		except Exception as e:
			logger.error(f"获取财务数据失败: {str(e)}")
			return None

	# ==================== 研究任务管理方法 ====================

	async def _create_research_task (
			self,
			factor_definition: Dict[str, Any],
			universe: Optional[List[str]] = None,
			start_date: Optional[date] = None,
			end_date: Optional[date] = None,
			parameters: Optional[Dict[str, Any]] = None,
			user_id: Optional[str] = None
	) -> str:
		"""
		创建研究任务记录

		Args:
			factor_definition: 因子定义
			universe: 股票池
			start_date: 开始日期
			end_date: 结束日期
			parameters: 研究参数
			user_id: 用户ID

		Returns:
			str: 研究ID
		"""
		research_id = f"research_{datetime.now().strftime('%Y%m%d_%H%M%S')}"

		task_data = {
			"research_id": research_id,
			"factor_name": factor_definition.get("name"),
			"factor_definition": factor_definition,
			"universe": universe,
			"start_date": start_date,
			"end_date": end_date,
			"parameters": parameters or {},
			"status": ResearchStatus.RUNNING,
			"user_id": user_id,
			"created_at": datetime.now()
		}

		await self.research_repo.create(task_data)

		return research_id

	async def _update_research_task (
			self,
			research_id: str,
			status: str,
			error: Optional[str] = None
	):
		"""
		更新研究任务状态

		Args:
			research_id: 研究ID
			status: 状态
			error: 错误信息
		"""
		task = await self.research_repo.get_by_research_id(research_id)
		if not task:
			return

		update_data = {
			"status": status,
			"updated_at": datetime.now()
		}

		if status == ResearchStatus.COMPLETED:
			update_data["completed_at"] = datetime.now()
		elif status == ResearchStatus.FAILED:
			update_data["error"] = error

		await self.research_repo.update(task.id, update_data)

	async def _execute_factor_research (
			self,
			factor_definition: Dict[str, Any],
			universe: Optional[List[str]] = None,
			start_date: Optional[date] = None,
			end_date: Optional[date] = None,
			parameters: Optional[Dict[str, Any]] = None,
			research_id: str = None,
			user_id: Optional[str] = None
	) -> Dict[str, Any]:
		"""
		执行因子研究

		Args:
			factor_definition: 因子定义
			universe: 股票池
			start_date: 开始日期
			end_date: 结束日期
			parameters: 研究参数
			research_id: 研究ID
			user_id: 用户ID

		Returns:
			Dict: 研究结果
		"""
		factor_name = factor_definition.get("name")

		# 计算因子数据
		calculation_result = await self.calculate_factor(
			factor_name=factor_name,
			ts_codes=universe,
			start_date=start_date,
			end_date=end_date,
			parameters=parameters,
			user_id=user_id
		)

		# 分析因子表现
		analysis_results = {}

		# IC分析
		ic_analysis = await self.analyze_factor_performance(
			factor_name=factor_name,
			universe=universe,
			start_date=start_date,
			end_date=end_date,
			analysis_type="ic_analysis",
			parameters=parameters,
			user_id=user_id
		)

		if ic_analysis.get("success"):
			analysis_results["ic_analysis"] = ic_analysis.get("analysis_result", {})

		# 分位数分析
		quantile_analysis = await self.analyze_factor_performance(
			factor_name=factor_name,
			universe=universe,
			start_date=start_date,
			end_date=end_date,
			analysis_type="quantile_analysis",
			parameters=parameters,
			user_id=user_id
		)

		if quantile_analysis.get("success"):
			analysis_results["quantile_analysis"] = quantile_analysis.get("analysis_result", {})

		# 稳定性分析
		stability_analysis = await self.analyze_factor_performance(
			factor_name=factor_name,
			universe=universe,
			start_date=start_date,
			end_date=end_date,
			analysis_type="stability_analysis",
			parameters=parameters,
			user_id=user_id
		)

		if stability_analysis.get("success"):
			analysis_results["stability_analysis"] = stability_analysis.get("analysis_result", {})

		# 生成研究总结
		summary = await self._generate_research_summary(
			factor_name=factor_name,
			calculation_result=calculation_result,
			analysis_results=analysis_results
		)

		return {
			"factor_name": factor_name,
			"factor_definition": factor_definition,
			"calculation_result": calculation_result,
			"analysis_results": analysis_results,
			"summary": summary,
			"research_id": research_id,
			"completed_at": datetime.now().isoformat()
		}

	async def _save_research_result (
			self,
			research_id: str,
			result: Dict[str, Any]
	):
		"""
		保存研究结果

		Args:
			research_id: 研究ID
			result: 研究结果
		"""
		task = await self.research_repo.get_by_research_id(research_id)
		if not task:
			return

		# 计算研究耗时
		duration = None
		if task.created_at:
			duration = (datetime.now() - task.created_at).total_seconds()

		update_data = {
			"status": ResearchStatus.COMPLETED,
			"completed_at": datetime.now(),
			"result": result,
			"duration_seconds": duration
		}

		await self.research_repo.update(task.id, update_data)

	# ==================== 总结生成方法 ====================
	@staticmethod
	async def _generate_research_summary (
			factor_name: str,
			calculation_result: Dict[str, Any],
			analysis_results: Dict[str, Any]
	) -> Dict[str, Any]:
		"""
		生成研究总结

		Args:
			factor_name: 因子名称
			calculation_result: 计算结果
			analysis_results: 分析结果

		Returns:
			Dict: 研究总结
		"""
		summary = {
			"factor_name": factor_name,
			"calculation_completed": calculation_result.get("success", False),
			"calculated_count": calculation_result.get("calculated_count", 0),
			"analyses_performed": list(analysis_results.keys()),
			"overall_assessment": "pending",
			"key_findings": [],
			"next_steps": [],
			"generated_at": datetime.now().isoformat()
		}

		# 评估因子表现
		ic_analysis = analysis_results.get("ic_analysis", {})
		if ic_analysis:
			ic_mean = ic_analysis.get("ic_mean", 0)
			ic_ir = ic_analysis.get("ic_ir", 0)

			if ic_mean > 0.05 and ic_ir > 0.5:
				summary["overall_assessment"] = "excellent"
				summary["key_findings"].append("因子IC均值显著为正，信息比率良好")
			elif ic_mean > 0.03:
				summary["overall_assessment"] = "good"
				summary["key_findings"].append("因子有一定预测能力")
			else:
				summary["overall_assessment"] = "poor"
				summary["key_findings"].append("因子预测能力不足")

		# 分位数分析结果
		quantile_analysis = analysis_results.get("quantile_analysis", {})
		if quantile_analysis:
			top_minus_bottom = quantile_analysis.get("top_minus_bottom", 0)

			if top_minus_bottom > 0.1:
				summary["key_findings"].append(f"因子区分度很高，多空收益差为 {top_minus_bottom:.2%}")
			elif top_minus_bottom > 0.05:
				summary["key_findings"].append(f"因子有一定区分度，多空收益差为 {top_minus_bottom:.2%}")
			else:
				summary["key_findings"].append(f"因子区分度不足，多空收益差为 {top_minus_bottom:.2%}")

		# 稳定性分析结果
		stability_analysis = analysis_results.get("stability_analysis", {})
		if stability_analysis:
			stability_score = stability_analysis.get("stability_score", 0)

			if stability_score > 0.7:
				summary["key_findings"].append(f"因子稳定性良好，得分为 {stability_score:.2f}")
			elif stability_score > 0.5:
				summary["key_findings"].append(f"因子稳定性一般，得分为 {stability_score:.2f}")
			else:
				summary["key_findings"].append(f"因子稳定性较差，得分为 {stability_score:.2f}")

		# 建议下一步
		if summary["overall_assessment"] in ["excellent", "good"]:
			summary["next_steps"].append("将因子加入因子库")
			summary["next_steps"].append("进行策略回测验证")
			if summary["overall_assessment"] == "excellent":
				summary["next_steps"].append("考虑用于实盘策略")
		else:
			summary["next_steps"].append("优化因子计算方法")
			summary["next_steps"].append("尝试其他相关因子")
			summary["next_steps"].append("调整研究参数重新分析")

		return summary

	# ==================== 指标提取方法 ====================
	@staticmethod
	def _extract_factor_metrics (
			analysis_result: Dict[str, Any],
			metrics: List[str]
	) -> Dict[str, Any]:
		"""
		从分析结果中提取指标

		Args:
			analysis_result: 分析结果
			metrics: 指标列表

		Returns:
			Dict: 提取的指标
		"""
		extracted = {}

		# 定义指标映射关系，支持复杂路径的指标提取
		metric_mapping = {
			"ic_mean": lambda r: r.get("ic_mean", 0),
			"ic_std": lambda r: r.get("ic_std", 0),
			"ic_ir": lambda r: r.get("ic_ir", 0),
			"ic_pvalue": lambda r: r.get("ic_pvalue", 1.0),
			"ic_positive_ratio": lambda r: r.get("ic_positive_ratio", 0),
			"top_minus_bottom": lambda r: r.get("top_minus_bottom", 0),
			"stability_score": lambda r: r.get("stability_score", 0),
			"rank_ic": lambda r: r.get("rank_ic", 0),
			"mean_correlation": lambda r: r.get("mean_correlation", 0),
			"orthogonality_score": lambda r: r.get("orthogonality_score", 0),
			"sample_size": lambda r: r.get("sample_size", 0),
			"calculated_count": lambda r: r.get("calculated_count", 0),
			"success_rate": lambda r: r.get("success_rate", 0)
		}

		for metric in metrics:
			if metric in metric_mapping:
				# 使用预定义的提取函数
				extracted[metric] = metric_mapping[metric](analysis_result)
			else:
				# 尝试从分析结果中直接提取
				if metric in analysis_result:
					extracted[metric] = analysis_result[metric]
				else:
					# 尝试使用点号分隔的路径
					parts = metric.split('.')
					current = analysis_result
					try:
						for part in parts:
							if isinstance(current, dict) and part in current:
								current = current[part]
							else:
								raise KeyError
						extracted[metric] = current
					except (KeyError, TypeError):
						# 没有该指标时返回默认值
						if metric.endswith('_ratio') or metric.endswith('_score'):
							extracted[metric] = 0.0
						elif metric.endswith('_count') or metric.endswith('_size'):
							extracted[metric] = 0
						else:
							extracted[metric] = 0

		return extracted

	# ==================== 缓存管理方法 ====================

	async def _clean_factor_cache (self, factor_name: str):
		"""
		清理因子相关缓存

		Args:
			factor_name: 因子名称
		"""
		patterns = [
			CacheKey.FACTOR_DATA.format(
				ts_code="*",
				factor=factor_name,
				start="*",
				end="*"
			),
			CacheKey.FACTOR_ANALYSIS.format(
				factor=factor_name,
				analysis="*",
				start="*",
				end="*"
			),
			CacheKey.FACTOR_METADATA.format(factor=factor_name)
		]

		for pattern in patterns:
			await self.cache.delete_pattern(pattern)

	async def _clean_factor_metadata_cache (self):
		"""清理因子元数据缓存"""
		patterns = [
			CacheKey.FACTOR_METADATA.format(factor="*")
		]

		for pattern in patterns:
			await self.cache.delete_pattern(pattern)

	# ==================== 标准因子元数据 ====================
	@staticmethod
	def _get_standard_factor_metadata (
			factor_name: Optional[str] = None,
			category: Optional[str] = None
	) -> List[Dict[str, Any]]:
		"""
		获取标准因子元数据

		Args:
			factor_name: 因子名称
			category: 因子类别

		Returns:
			List[Dict]: 标准因子元数据列表
		"""
		standard_factors = [
			{
				"factor_name": StandardFactors.PE,
				"display_name": "市盈率",
				"description": "股价除以每股收益，衡量股票估值水平",
				"category": FactorCategoryCode.VALUE,
				"formula": "PE = Price / EPS",
				"data_source": "财务报表",
				"update_frequency": "季度"
			},
			{
				"factor_name": StandardFactors.PB,
				"display_name": "市净率",
				"description": "股价除以每股净资产，衡量股票价值",
				"category": FactorCategoryCode.VALUE,
				"formula": "PB = Price / Book Value per Share",
				"data_source": "财务报表",
				"update_frequency": "季度"
			},
			{
				"factor_name": StandardFactors.PS,
				"display_name": "市销率",
				"description": "股价除以每股销售收入",
				"category": FactorCategoryCode.VALUE,
				"formula": "PS = Price / Sales per Share",
				"data_source": "财务报表",
				"update_frequency": "季度"
			},
			{
				"factor_name": StandardFactors.ROE,
				"display_name": "净资产收益率",
				"description": "净利润除以净资产，衡量公司盈利能力",
				"category": FactorCategoryCode.QUALITY,
				"formula": "ROE = Net Income / Equity",
				"data_source": "财务报表",
				"update_frequency": "季度"
			},
			{
				"factor_name": StandardFactors.ROA,
				"display_name": "总资产收益率",
				"description": "净利润除以总资产，衡量资产使用效率",
				"category": FactorCategoryCode.QUALITY,
				"formula": "ROA = Net Income / Total Assets",
				"data_source": "财务报表",
				"update_frequency": "季度"
			},
			{
				"factor_name": StandardFactors.GROSS_MARGIN,
				"display_name": "毛利率",
				"description": "毛利润除以营业收入，衡量产品盈利能力",
				"category": FactorCategoryCode.QUALITY,
				"formula": "GM = Gross Profit / Revenue",
				"data_source": "财务报表",
				"update_frequency": "季度"
			},
			{
				"factor_name": StandardFactors.OPERATING_MARGIN,
				"display_name": "净利率",
				"description": "净利润除以营业收入，衡量整体盈利能力",
				"category": FactorCategoryCode.QUALITY,
				"formula": "NP Margin = Net Profit / Revenue",
				"data_source": "财务报表",
				"update_frequency": "季度"
			},
			{
				"factor_name": StandardFactors.DEBT_RATIO,
				"display_name": "资产负债率",
				"description": "总负债除以总资产，衡量财务杠杆",
				"category": FactorCategoryCode.QUALITY,
				"formula": "Debt to Asset = Total Debt / Total Assets",
				"data_source": "财务报表",
				"update_frequency": "季度"
			},
			{
				"factor_name": "current_ratio",
				"display_name": "流动比率",
				"description": "流动资产除以流动负债，衡量短期偿债能力",
				"category": FactorCategoryCode.QUALITY,
				"formula": "Current Ratio = Current Assets / Current Liabilities",
				"data_source": "财务报表",
				"update_frequency": "季度"
			},
			{
				"factor_name": "quick_ratio",
				"display_name": "速动比率",
				"description": "速动资产除以流动负债，衡量即时偿债能力",
				"category": FactorCategoryCode.QUALITY,
				"formula": "Quick Ratio = (Current Assets - Inventory) / Current Liabilities",
				"data_source": "财务报表",
				"update_frequency": "季度"
			},
			{
				"factor_name": StandardFactors.MARKET_CAP,
				"display_name": "市值",
				"description": "总股本乘以股价，衡量公司规模",
				"category": FactorCategoryCode.SIZE,
				"formula": "Market Cap = Shares Outstanding × Price",
				"data_source": "行情数据",
				"update_frequency": "日度"
			},
			{
				"factor_name": StandardFactors.RET_1M,
				"display_name": "1个月收益率",
				"description": "过去1个月的收益率",
				"category": FactorCategoryCode.MOMENTUM,
				"formula": "Ret_1M = (Price_t / Price_{t-20}) - 1",
				"data_source": "行情数据",
				"update_frequency": "日度"
			},
			{
				"factor_name": StandardFactors.RET_3M,
				"display_name": "3个月收益率",
				"description": "过去3个月的收益率",
				"category": FactorCategoryCode.MOMENTUM,
				"formula": "Ret_3M = (Price_t / Price_{t-60}) - 1",
				"data_source": "行情数据",
				"update_frequency": "日度"
			},
			{
				"factor_name": StandardFactors.RET_6M,
				"display_name": "6个月收益率",
				"description": "过去6个月的收益率",
				"category": FactorCategoryCode.MOMENTUM,
				"formula": "Ret_6M = (Price_t / Price_{t-120}) - 1",
				"data_source": "行情数据",
				"update_frequency": "日度"
			},
			{
				"factor_name": StandardFactors.RET_12M,
				"display_name": "12个月收益率",
				"description": "过去12个月的收益率",
				"category": FactorCategoryCode.MOMENTUM,
				"formula": "Ret_12M = (Price_t / Price_{t-240}) - 1",
				"data_source": "行情数据",
				"update_frequency": "日度"
			},
			{
				"factor_name": StandardFactors.VOLATILITY_1M,
				"display_name": "1个月波动率",
				"description": "过去1个月的收益率波动率",
				"category": FactorCategoryCode.VOLATILITY,
				"formula": "Std(Returns, 20 days) × √252",
				"data_source": "行情数据",
				"update_frequency": "日度"
			},
			{
				"factor_name": StandardFactors.VOLATILITY_3M,
				"display_name": "3个月波动率",
				"description": "过去3个月的收益率波动率",
				"category": FactorCategoryCode.VOLATILITY,
				"formula": "Std(Returns, 60 days) × √252",
				"data_source": "行情数据",
				"update_frequency": "日度"
			},
			{
				"factor_name": StandardFactors.VOLATILITY_12M,
				"display_name": "12个月波动率",
				"description": "过去12个月的收益率波动率",
				"category": FactorCategoryCode.VOLATILITY,
				"formula": "Std(Returns, 240 days) × √252",
				"data_source": "行情数据",
				"update_frequency": "日度"
			},
			{
				"factor_name": StandardFactors.BETA,
				"display_name": "Beta系数",
				"description": "股票收益与市场收益的协方差除以市场收益的方差",
				"category": FactorCategoryCode.VOLATILITY,
				"formula": "β = Cov(Ret_stock, Ret_market) / Var(Ret_market)",
				"data_source": "行情数据",
				"update_frequency": "日度"
			},
			{
				"factor_name": "sharpe_ratio",
				"display_name": "夏普比率",
				"description": "(年化收益 - 无风险利率) / 年化波动率",
				"category": FactorCategoryCode.VOLATILITY,
				"formula": "Sharpe = (E[Ret] - Rf) / σ",
				"data_source": "行情数据",
				"update_frequency": "日度"
			},
			{
				"factor_name": StandardFactors.TURNOVER_RATE,
				"display_name": "换手率",
				"description": "成交量除以流通股本，衡量股票流动性",
				"category": FactorCategoryCode.LIQUIDITY,
				"formula": "Turnover Rate = Volume / Float Shares",
				"data_source": "行情数据",
				"update_frequency": "日度"
			},
			{
				"factor_name": "volume_ratio",
				"display_name": "量比",
				"description": "当前成交量除以过去N日平均成交量",
				"category": FactorCategoryCode.LIQUIDITY,
				"formula": "Volume Ratio = Volume_t / Avg(Volume_{t-N:t-1})",
				"data_source": "行情数据",
				"update_frequency": "日度"
			}
		]

		# 过滤因子
		filtered_factors = []
		for factor in standard_factors:
			if factor_name and factor["factor_name"] != factor_name:
				continue
			if category and factor["category"] != category:
				continue
			filtered_factors.append(factor)

		return filtered_factors

	# ==================== 事件发布方法 ====================

	async def _publish_research_event (
			self,
			event_type: str,
			research_id: Optional[str] = None,
			factor_name: Optional[str] = None,
			factor_definition: Optional[Dict] = None,
			progress: Optional[float] = None,
			calculated_count: Optional[int] = None,
			total_stocks: Optional[int] = None,
			analysis_type: Optional[str] = None,
			result: Optional[Dict] = None,
			error: Optional[str] = None,
			factor_names: Optional[List[str]] = None,
			metrics: Optional[List[str]] = None,
			comparison_report: Optional[Dict] = None,
			failed_count: Optional[int] = None,
			user_id: Optional[str] = None
	):
		"""
		发布研究事件

		Args:
			event_type: 事件类型
			research_id: 研究ID
			factor_name: 因子名称
			factor_definition: 因子定义
			progress: 进度百分比
			calculated_count: 计算数量
			total_stocks: 总股票数量
			analysis_type: 分析类型
			result: 研究结果
			error: 错误信息
			factor_names: 因子名称列表
			metrics: 指标列表
			comparison_report: 比较报告
			failed_count: 失败数量
			user_id: 用户ID
		"""
		if not self.event_engine:
			return

		try:
			event_data: Dict[str, Any] = {
				"timestamp": datetime.now().isoformat(),
				"user_id": user_id
			}

			if research_id:
				event_data["research_id"] = research_id
			if factor_name:
				event_data["factor_name"] = factor_name
			if factor_definition:
				event_data["factor_definition"] = factor_definition
			if progress is not None:
				event_data["progress"] = progress
			if calculated_count is not None:
				event_data["calculated_count"] = calculated_count
			if total_stocks is not None:
				event_data["total_stocks"] = total_stocks
			if analysis_type:
				event_data["analysis_type"] = analysis_type
			if result:
				event_data["result"] = result
			if error:
				event_data["error"] = error
			if factor_names:
				event_data["factor_names"] = factor_names
			if metrics:
				event_data["metrics"] = metrics
			if comparison_report:
				event_data["comparison_report"] = comparison_report
			if failed_count is not None:
				event_data["failed_count"] = failed_count

			# 创建一个通用的事件，使用BaseEvent而不是DataResearchStartedEvent
			from core.events.base import BaseEvent

			# 添加事件优先级
			event_priority = {
				"started": 0,  # NORMAL
				"progress": 1,  # LOW
				"completed": 2,  # HIGH
				"failed": 2,     # HIGH
				"cached": 1,     # LOW
				"comparison_completed": 0  # NORMAL
			}.get(event_type, 0)  # 默认NORMAL

			event = TypedEvent(
				event_type=f"factor.research.{event_type}",
				source="research_service",
				module="data",
				priority=event_priority,
				data=event_data
			)

			# 添加事件发布统计
			if hasattr(self, '_event_stats'):
				self._event_stats[event_type] = self._event_stats.get(event_type, 0) + 1

			await self.event_engine.put(event)

			# 记录事件发布日志
			logger.debug(f"发布研究事件: {event_type}, 优先级: {event_priority}")

		except Exception as e:
			logger.error(f"发布研究事件失败: {str(e)}")

	# ==================== 补充方法实现 ====================

	async def get_factor_data (
			self,
			factor_names: List[str],
			start_date: Optional[str] = None,
			end_date: Optional[str] = None
	) -> List[Dict[str, Any]]:
		"""
		获取因子数据

		Args:
			factor_names: 因子名称列表
			start_date: 开始日期
			end_date: 结束日期

		Returns:
			因子数据列表
		"""
		logger.info(f"获取因子数据: {factor_names}")

		try:
			# 转换日期格式
			start_date_obj = datetime.fromisoformat(start_date) if start_date else None
			end_date_obj = datetime.fromisoformat(end_date) if end_date else None

			factor_data = []

			# 首先获取股票列表
			stocks = await self.stock_repo.get_all(limit=100)  # 限制获取100只股票
			if not stocks:
				logger.warning("获取股票列表失败")
				return []

			stock_codes = [stock.ts_code for stock in stocks]

			# 批量获取因子数据
			for factor_name in factor_names:
				for stock_code in stock_codes:
					# 从数据库获取因子数据
					factor_items = await self.factor_repo.get_by_ts_code_and_date_range(
						ts_code=stock_code,
						factor_name=factor_name,
						start_date=start_date_obj,
						end_date=end_date_obj
					)
					if factor_items:
						for factor_item in factor_items:
							factor_data.append({
								'symbol': stock_code,
								'factor_name': factor_name,
								'factor_value': factor_item.factor_value,
								'date': factor_item.trade_date.isoformat()
							})

			return factor_data

		except Exception as e:
			logger.error(f"获取因子数据失败: {str(e)}")
			return []

	async def save_factor_analysis_result (
			self,
			factor_names: List[str],
			analysis_type: str,
			analysis_result: Dict[str, Any],
			task_id: str
	) -> str:
		"""
		保存因子分析结果

		Args:
			factor_names: 因子名称列表
			analysis_type: 分析类型
			analysis_result: 分析结果
			task_id: 任务ID

		Returns:
			保存结果的ID
		"""
		logger.info(f"保存因子分析结果: {factor_names}")

		try:
			# 创建研究任务记录
			result = await self.research_repo.create_research_task(
				research_id=task_id,
				research_name=f"因子分析 - {', '.join(factor_names)}",
				factor_name=factor_names[0] if factor_names else "unknown",
				user_id=1,  # 默认用户ID
				analysis_type=analysis_type,
				parameters=analysis_result
			)

			if result.success and result.data:
				return result.data.research_id
			return task_id

		except Exception as e:
			logger.error(f"保存因子分析结果失败: {str(e)}")
			return task_id

	@staticmethod
	async def generate_factor_analysis_report (
			analysis_result: Dict[str, Any],
			factor_names: List[str],
			start_date: Optional[str] = None,
			end_date: Optional[str] = None,
			analysis_params: Optional[Dict[str, Any]] = None
	) -> str:
		"""
		生成因子分析报告

		Args:
			analysis_result: 分析结果
			factor_names: 因子名称列表
			start_date: 开始日期
			end_date: 结束日期
			analysis_params: 分析参数

		Returns:
			分析报告
		"""
		logger.info(f"生成因子分析报告: {factor_names}")

		try:
			# 生成报告内容
			report = f"# 因子分析报告\n\n"
			report += f"## 分析概览\n"
			report += f"- 因子列表: {', '.join(factor_names)}\n"
			report += f"- 分析类型: {analysis_result.get('analysis_type', 'unknown')}\n"
			report += f"- 分析日期: {datetime.now().isoformat()}\n"
			report += f"- 数据范围: {start_date or '未指定'} 至 {end_date or '未指定'}\n\n"

			# 添加分析结果
			report += "## 分析结果\n"
			if 'analysis_result' in analysis_result:
				for key, value in analysis_result['analysis_result'].items():
					report += f"- {key}: {value}\n"

			# 添加参数信息
			if analysis_params:
				report += "\n## 分析参数\n"
				for key, value in analysis_params.items():
					report += f"- {key}: {value}\n"

			return report

		except Exception as e:
			logger.error(f"生成因子分析报告失败: {str(e)}")
			return "因子分析报告生成失败"

	def optimize_factor_parameters (
			self,
			factor_name: str,
			test_data: List[Dict],
			optimization_method: str,
			parameter_ranges: Dict,
			objective_function: str
	) -> Dict[str, Any]:
		"""
		优化因子参数

		Args:
			factor_name: 因子名称
			test_data: 测试数据
			optimization_method: 优化方法
			parameter_ranges: 参数范围
			objective_function: 目标函数

		Returns:
			优化结果
		"""
		logger.info(f"优化因子参数: {factor_name}")

		try:
			# 检查测试数据是否为空
			if not test_data:
				logger.warning("测试数据为空，无法进行参数优化")
				return {
					'success': False,
					'factor_name': factor_name,
					'error': "测试数据为空"
				}

			# 实现简单的参数优化逻辑
			best_parameters = {}
			best_score = -float('inf')

			# 遍历参数范围，寻找最优参数
			# 这里使用网格搜索作为简单的优化方法
			for param, range_values in parameter_ranges.items():
				if isinstance(range_values, list) and len(range_values) >= 2:
					# 对于数值型参数，使用简单的网格搜索
					if all(isinstance(x, (int, float)) for x in range_values):
						# 生成参数候选值
						candidates = np.linspace(range_values[0], range_values[1], 5)  # 生成5个候选值

						# 评估每个候选值
						for candidate in candidates:
							# 计算当前参数下的性能得分
							current_score = self._evaluate_parameter(test_data)

							# 更新最优参数
							if current_score > best_score:
								best_score = current_score
								best_parameters[param] = candidate
					else:
						# 对于非数值型参数，使用第一个值
						best_parameters[param] = range_values[0]

			# 计算性能指标
			performance_metrics = self._calculate_performance_metrics(test_data)

			return {
				'success': True,
				'factor_name': factor_name,
				'best_parameters': best_parameters,
				'optimization_method': optimization_method,
				'objective_function': objective_function,
				'performance_metrics': performance_metrics
			}

		except Exception as e:
			logger.error(f"优化因子参数失败: {str(e)}")
			return {
				'success': False,
				'factor_name': factor_name,
				'error': str(e)
			}

	@staticmethod
	def _evaluate_parameter (test_data: List[Dict]) -> float:
		"""
		评估参数性能

		Args:
			test_data: 测试数据

		Returns:
			性能得分
		"""
		if not test_data:
			return 0

		# 提取收益率数据
		returns = [data['return'] for data in test_data if 'return' in data]
		if not returns:
			return 0

		# 计算基本指标
		returns = np.array(returns)
		mean_return = np.mean(returns)
		std_return = np.std(returns)
		sharpe_ratio = mean_return / std_return if std_return > 0 else 0

		# 计算最大回撤
		cumulative_returns = np.cumprod(1 + returns)
		peak = np.maximum.accumulate(cumulative_returns)
		drawdown = (cumulative_returns - peak) / peak
		max_drawdown = np.min(drawdown)

		# 计算胜率
		win_rate = np.sum(returns > 0) / len(returns)

		# 计算平均盈亏比
		winning_returns = returns[returns > 0]
		losing_returns = returns[returns < 0]
		avg_win = np.mean(winning_returns) if len(winning_returns) > 0 else 0
		avg_loss = np.abs(np.mean(losing_returns)) if len(losing_returns) > 0 else 1
		profit_factor = avg_win / avg_loss if avg_loss > 0 else 0

		# 综合评分（权重可以根据需要调整）
		score = (
				0.3 * sharpe_ratio +
				0.2 * (1 + max_drawdown) +  # 最大回撤越小，得分越高
				0.2 * win_rate +
				0.2 * profit_factor +
				0.1 * mean_return
		)

		return float(score)

	@staticmethod
	def _calculate_performance_metrics ( test_data: List[Dict]) -> Dict[str, float]:
		"""
		计算性能指标

		Args:
			test_data: 测试数据

		Returns:
			性能指标
		"""
		# 计算基本性能指标
		returns = [data['return'] for data in test_data if 'return' in data]

		if not returns:
			return {
				'sharpe_ratio': 0,
				'max_drawdown': 0,
				'alpha': 0
			}

		# 计算收益率均值和标准差
		import numpy
		mean_return = numpy.mean(returns)
		std_return = numpy.std(returns)

		# 计算夏普比率（假设无风险利率为3%）
		risk_free_rate = 0.03
		sharpe_ratio = (mean_return - risk_free_rate) / std_return if std_return > 0 else 0

		# 计算最大回撤
		cumulative_returns = numpy.cumprod([1 + r for r in returns])
		peak = cumulative_returns[0]
		max_drawdown = 0

		for ret in cumulative_returns:
			if ret > peak:
				peak = ret
			else:
				drawdown = (peak - ret) / peak
				if drawdown > max_drawdown:
					max_drawdown = drawdown

		# 计算alpha（假设市场收益率为0）
		alpha = mean_return

		return {
			'sharpe_ratio': sharpe_ratio,
			'max_drawdown': max_drawdown,
			'alpha': alpha
		}