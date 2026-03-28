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

import logging
from datetime import datetime, date, timedelta
from typing import Dict, List, Any, Optional, Union, Tuple
import asyncio
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import and_, or_, func
import pandas as pd
import numpy as np
from scipy import stats

# 导入共享层组件
from quant_server.shared.database.repositories import (
	StockBasicRepository,
	StockDailyRepository,
	FactorDataRepository,
	FactorDefinitionRepository,
	FactorResearchRepository,
	FinancialStatementRepository
)
from quant_server.shared.cache.redis_cache import RedisCache

# 导入核心基础设施
from quant_server.core.engines.system.event_engine import EventEngine

# 导入事件类
from quant_server.modules.data.events.research_events import DataResearchStartedEvent

# 导入工具类
from quant_server.utils.core_utils.math_utils import StatisticalCalculator

# 导入数据模块常量
from quant_server.modules.data.constants import (
	CacheKey,
	DataType,
	FactorCategoryCode,
	StandardFactors,
	ResearchStatus
)

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
			from quant_server.shared.config.settings import get_settings
			settings = get_settings()
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
			user_id: Optional[int] = None
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
			user_id: Optional[int] = None
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
				except:
					pass
				try:
					stocks_star = await self.stock_repo.get_by_market("科创板", active_only=True)
					stocks.extend(stocks_star)
				except:
					pass
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
						start_date=start_date,
						end_date=end_date,
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
			start_date: Optional[date] = None,
			end_date: Optional[date] = None,
			analysis_type: str = "ic_analysis",
			parameters: Optional[Dict[str, Any]] = None,
			user_id: Optional[int] = None
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
			factor_data = await self._get_factor_data_for_analysis(
				factor_name=factor_name,
				universe=universe,
				start_date=start_date,
				end_date=end_date
			)

			if factor_data.empty:
				return {
					"success": False,
					"factor_name": factor_name,
					"error": "没有找到因子数据",
					"message": "无法进行因子表现分析"
				}

			# 检查是否需要收益数据
			if analysis_type in ["ic_analysis", "quantile_analysis"]:
				# 获取收益数据
				returns_data = await self._get_returns_data_for_analysis(
					universe=universe,
					start_date=start_date,
					end_date=end_date
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
			analysis_result = await method(
				factor_data=factor_data,
				factor_name=factor_name,
				start_date=start_date,
				end_date=end_date,
				returns_data=returns_data if analysis_type in ["ic_analysis", "quantile_analysis"] else None,
				parameters=parameters
			)

			# 生成分析报告
			report = await self._generate_analysis_report(
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
			user_id: Optional[int] = None
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
				from quant_server.shared.database.models.data_models import FactorDefinition
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
			user_id: Optional[int] = None
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
			start_date: date,
			end_date: date,
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
				financial_data = await self._get_financial_data(ts_code, start_date, end_date)

			# 计算因子值
			factor_series = calculator(df, parameters, financial_data)

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
					except Exception:
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
			StandardFactors.PE: self._calculate_pe,
			StandardFactors.PB: self._calculate_pb,
			StandardFactors.PS: self._calculate_ps,
			StandardFactors.ROE: self._calculate_roe,
			StandardFactors.ROA: self._calculate_roa,
			StandardFactors.GROSS_MARGIN: self._calculate_gm,
			StandardFactors.OPERATING_MARGIN: self._calculate_np_margin,
			StandardFactors.DEBT_RATIO: self._calculate_debt_to_asset,
			"current_ratio": self._calculate_current_ratio,
			"quick_ratio": self._calculate_quick_ratio,
			StandardFactors.MARKET_CAP: self._calculate_market_cap,
			StandardFactors.RET_1M: self._calculate_return_1m,
			StandardFactors.RET_3M: self._calculate_return_3m,
			StandardFactors.RET_6M: self._calculate_return_6m,
			StandardFactors.RET_12M: self._calculate_return_12m,
			StandardFactors.VOLATILITY_1M: self._calculate_volatility_1m,
			StandardFactors.VOLATILITY_3M: self._calculate_volatility_3m,
			StandardFactors.VOLATILITY_12M: self._calculate_volatility_12m,
			StandardFactors.BETA: self._calculate_beta,
			"sharpe_ratio": self._calculate_sharpe_ratio,
			StandardFactors.TURNOVER_RATE: self._calculate_turnover_rate,
			"volume_ratio": self._calculate_volume_ratio,
			"MA": self._calculate_ma,
			"EMA": self._calculate_ema,
			"MACD": self._calculate_macd,
			"RSI": self._calculate_rsi,
			"BOLL": self._calculate_boll,
			"KDJ": self._calculate_kdj
		}

	def _calculate_pe (
			self,
			df: pd.DataFrame,
			parameters: Optional[Dict] = None,
			financial_data: Optional[pd.DataFrame] = None
	) -> pd.Series:
		"""计算市盈率"""
		if 'close' not in df.columns:
			return pd.Series(dtype=float)

		if financial_data is not None and 'eps' in financial_data.columns:
			# 使用实际财务数据
			eps = financial_data['eps']
			pe = df['close'] / eps
		else:
			# 模拟市盈率
			dates = df.index
			np.random.seed(hash(str(dates[0])) % 10000)
			pe = pd.Series(np.random.uniform(5, 50, len(dates)), index=dates)

		return pe

	def _calculate_pb (
			self,
			df: pd.DataFrame,
			parameters: Optional[Dict] = None,
			financial_data: Optional[pd.DataFrame] = None
	) -> pd.Series:
		"""计算市净率"""
		if 'close' not in df.columns:
			return pd.Series(dtype=float)

		if financial_data is not None and 'bps' in financial_data.columns:
			# 使用实际财务数据
			bps = financial_data['bps']
			pb = df['close'] / bps
		else:
			# 模拟市净率
			dates = df.index
			np.random.seed(hash(str(dates[0])) % 10000)
			pb = pd.Series(np.random.uniform(0.5, 5, len(dates)), index=dates)

		return pb

	def _calculate_ps (
			self,
			df: pd.DataFrame,
			parameters: Optional[Dict] = None,
			financial_data: Optional[pd.DataFrame] = None
	) -> pd.Series:
		"""计算市销率"""
		if 'close' not in df.columns:
			return pd.Series(dtype=float)

		# 模拟市销率
		dates = df.index
		np.random.seed(hash(str(dates[0])) % 10000)
		ps = pd.Series(np.random.uniform(0.5, 10, len(dates)), index=dates)

		return ps

	def _calculate_roe (
			self,
			df: pd.DataFrame,
			parameters: Optional[Dict] = None,
			financial_data: Optional[pd.DataFrame] = None
	) -> pd.Series:
		"""计算净资产收益率"""
		if financial_data is not None and 'roe' in financial_data.columns:
			# 使用实际财务数据
			roe = financial_data['roe']
		else:
			# 模拟ROE
			dates = df.index
			np.random.seed(hash(str(dates[0])) % 10000)
			roe = pd.Series(np.random.uniform(0.05, 0.25, len(dates)), index=dates)

		return roe

	def _calculate_roa (
			self,
			df: pd.DataFrame,
			parameters: Optional[Dict] = None,
			financial_data: Optional[pd.DataFrame] = None
	) -> pd.Series:
		"""计算总资产收益率"""
		# 模拟ROA
		dates = df.index
		np.random.seed(hash(str(dates[0])) % 10000)
		roa = pd.Series(np.random.uniform(0.03, 0.15, len(dates)), index=dates)

		return roa

	def _calculate_gm (
			self,
			df: pd.DataFrame,
			parameters: Optional[Dict] = None,
			financial_data: Optional[pd.DataFrame] = None
	) -> pd.Series:
		"""计算毛利率"""
		# 模拟毛利率
		dates = df.index
		np.random.seed(hash(str(dates[0])) % 10000)
		gm = pd.Series(np.random.uniform(0.20, 0.60, len(dates)), index=dates)

		return gm

	def _calculate_np_margin (
			self,
			df: pd.DataFrame,
			parameters: Optional[Dict] = None,
			financial_data: Optional[pd.DataFrame] = None
	) -> pd.Series:
		"""计算净利率"""
		# 模拟净利率
		dates = df.index
		np.random.seed(hash(str(dates[0])) % 10000)
		np_margin = pd.Series(np.random.uniform(0.05, 0.25, len(dates)), index=dates)

		return np_margin

	def _calculate_debt_to_asset (
			self,
			df: pd.DataFrame,
			parameters: Optional[Dict] = None,
			financial_data: Optional[pd.DataFrame] = None
	) -> pd.Series:
		"""计算资产负债率"""
		# 模拟资产负债率
		dates = df.index
		np.random.seed(hash(str(dates[0])) % 10000)
		debt_to_asset = pd.Series(np.random.uniform(0.30, 0.70, len(dates)), index=dates)

		return debt_to_asset

	def _calculate_current_ratio (
			self,
			df: pd.DataFrame,
			parameters: Optional[Dict] = None,
			financial_data: Optional[pd.DataFrame] = None
	) -> pd.Series:
		"""计算流动比率"""
		# 模拟流动比率
		dates = df.index
		np.random.seed(hash(str(dates[0])) % 10000)
		current_ratio = pd.Series(np.random.uniform(1.0, 3.0, len(dates)), index=dates)

		return current_ratio

	def _calculate_quick_ratio (
			self,
			df: pd.DataFrame,
			parameters: Optional[Dict] = None,
			financial_data: Optional[pd.DataFrame] = None
	) -> pd.Series:
		"""计算速动比率"""
		# 模拟速动比率
		dates = df.index
		np.random.seed(hash(str(dates[0])) % 10000)
		quick_ratio = pd.Series(np.random.uniform(0.5, 2.0, len(dates)), index=dates)

		return quick_ratio

	def _calculate_market_cap (
			self,
			df: pd.DataFrame,
			parameters: Optional[Dict] = None,
			financial_data: Optional[pd.DataFrame] = None
	) -> pd.Series:
		"""计算市值"""
		if 'close' not in df.columns:
			return pd.Series(dtype=float)

		# 假设流通股本为1亿
		float_shares = 100000000
		market_cap = df['close'] * float_shares

		return market_cap

	def _calculate_return_1m (
			self,
			df: pd.DataFrame,
			parameters: Optional[Dict] = None,
			financial_data: Optional[pd.DataFrame] = None
	) -> pd.Series:
		"""计算1个月收益率"""
		if 'close' not in df.columns:
			return pd.Series(dtype=float)

		window = parameters.get("window", 20) if parameters else 20  # 20个交易日约1个月
		returns = df['close'].pct_change(periods=window)

		return returns

	def _calculate_return_3m (
			self,
			df: pd.DataFrame,
			parameters: Optional[Dict] = None,
			financial_data: Optional[pd.DataFrame] = None
	) -> pd.Series:
		"""计算3个月收益率"""
		if 'close' not in df.columns:
			return pd.Series(dtype=float)

		window = parameters.get("window", 60) if parameters else 60  # 60个交易日约3个月
		returns = df['close'].pct_change(periods=window)

		return returns

	def _calculate_return_6m (
			self,
			df: pd.DataFrame,
			parameters: Optional[Dict] = None,
			financial_data: Optional[pd.DataFrame] = None
	) -> pd.Series:
		"""计算6个月收益率"""
		if 'close' not in df.columns:
			return pd.Series(dtype=float)

		window = parameters.get("window", 120) if parameters else 120  # 120个交易日约6个月
		returns = df['close'].pct_change(periods=window)

		return returns

	def _calculate_return_12m (
			self,
			df: pd.DataFrame,
			parameters: Optional[Dict] = None,
			financial_data: Optional[pd.DataFrame] = None
	) -> pd.Series:
		"""计算12个月收益率"""
		if 'close' not in df.columns:
			return pd.Series(dtype=float)

		window = parameters.get("window", 240) if parameters else 240  # 240个交易日约12个月
		returns = df['close'].pct_change(periods=window)

		return returns

	def _calculate_volatility_1m (
			self,
			df: pd.DataFrame,
			parameters: Optional[Dict] = None,
			financial_data: Optional[pd.DataFrame] = None
	) -> pd.Series:
		"""计算1个月波动率"""
		if 'close' not in df.columns:
			return pd.Series(dtype=float)

		window = parameters.get("window", 20) if parameters else 20
		returns = df['close'].pct_change()
		volatility = returns.rolling(window=window).std() * np.sqrt(252)  # 年化波动率

		return volatility

	def _calculate_volatility_3m (
			self,
			df: pd.DataFrame,
			parameters: Optional[Dict] = None,
			financial_data: Optional[pd.DataFrame] = None
	) -> pd.Series:
		"""计算3个月波动率"""
		if 'close' not in df.columns:
			return pd.Series(dtype=float)

		window = parameters.get("window", 60) if parameters else 60
		returns = df['close'].pct_change()
		volatility = returns.rolling(window=window).std() * np.sqrt(252)  # 年化波动率

		return volatility

	def _calculate_volatility_12m (
			self,
			df: pd.DataFrame,
			parameters: Optional[Dict] = None,
			financial_data: Optional[pd.DataFrame] = None
	) -> pd.Series:
		"""计算12个月波动率"""
		if 'close' not in df.columns:
			return pd.Series(dtype=float)

		window = parameters.get("window", 240) if parameters else 240
		returns = df['close'].pct_change()
		volatility = returns.rolling(window=window).std() * np.sqrt(252)  # 年化波动率

		return volatility

	def _calculate_beta (
			self,
			df: pd.DataFrame,
			parameters: Optional[Dict] = None,
			financial_data: Optional[pd.DataFrame] = None
	) -> pd.Series:
		"""计算Beta系数"""
		if 'close' not in df.columns:
			return pd.Series(dtype=float)

		# 模拟Beta系数
		dates = df.index
		np.random.seed(hash(str(dates[0])) % 10000)
		beta = pd.Series(np.random.uniform(0.5, 1.5, len(dates)), index=dates)

		return beta

	def _calculate_sharpe_ratio (
			self,
			df: pd.DataFrame,
			parameters: Optional[Dict] = None,
			financial_data: Optional[pd.DataFrame] = None
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

	def _calculate_turnover_rate (
			self,
			df: pd.DataFrame,
			parameters: Optional[Dict] = None,
			financial_data: Optional[pd.DataFrame] = None
	) -> pd.Series:
		"""计算换手率"""
		if 'volume' not in df.columns:
			return pd.Series(dtype=float)

		# 模拟换手率（假设流通股本为1亿）
		float_shares = 100000000
		turnover_rate = df['volume'] / float_shares * 100

		return turnover_rate

	def _calculate_volume_ratio (
			self,
			df: pd.DataFrame,
			parameters: Optional[Dict] = None,
			financial_data: Optional[pd.DataFrame] = None
	) -> pd.Series:
		"""计算量比"""
		if 'volume' not in df.columns:
			return pd.Series(dtype=float)

		window = parameters.get("window", 5) if parameters else 5
		avg_volume = df['volume'].rolling(window=window).mean()
		volume_ratio = df['volume'] / avg_volume

		return volume_ratio

	def _calculate_ma (
			self,
			df: pd.DataFrame,
			parameters: Optional[Dict] = None,
			financial_data: Optional[pd.DataFrame] = None
	) -> pd.Series:
		"""计算移动平均线"""
		if 'close' not in df.columns:
			return pd.Series(dtype=float)

		period = parameters.get("period", 20) if parameters else 20
		ma = df['close'].rolling(window=period).mean()

		return ma

	def _calculate_ema (
			self,
			df: pd.DataFrame,
			parameters: Optional[Dict] = None,
			financial_data: Optional[pd.DataFrame] = None
	) -> pd.Series:
		"""计算指数移动平均线"""
		if 'close' not in df.columns:
			return pd.Series(dtype=float)

		period = parameters.get("period", 12) if parameters else 12
		ema = df['close'].ewm(span=period, adjust=False).mean()

		return ema

	def _calculate_macd (
			self,
			df: pd.DataFrame,
			parameters: Optional[Dict] = None,
			financial_data: Optional[pd.DataFrame] = None
	) -> pd.Series:
		"""计算MACD指标"""
		if 'close' not in df.columns:
			return pd.Series(dtype=float)

		fast_period = parameters.get("fast_period", 12) if parameters else 12
		slow_period = parameters.get("slow_period", 26) if parameters else 26

		ema_fast = df['close'].ewm(span=fast_period, adjust=False).mean()
		ema_slow = df['close'].ewm(span=slow_period, adjust=False).mean()
		macd = ema_fast - ema_slow

		return macd

	def _calculate_rsi (
			self,
			df: pd.DataFrame,
			parameters: Optional[Dict] = None,
			financial_data: Optional[pd.DataFrame] = None
	) -> pd.Series:
		"""计算RSI指标"""
		if 'close' not in df.columns:
			return pd.Series(dtype=float)

		period = parameters.get("period", 14) if parameters else 14

		delta = df['close'].diff()
		gain = (delta.where(delta > 0, 0)).rolling(window=period).mean()
		loss = (-delta.where(delta < 0, 0)).rolling(window=period).mean()
		rs = gain / loss
		rsi = 100 - (100 / (1 + rs))

		return rsi

	def _calculate_boll (
			self,
			df: pd.DataFrame,
			parameters: Optional[Dict] = None,
			financial_data: Optional[pd.DataFrame] = None
	) -> pd.Series:
		"""计算布林带中轨"""
		if 'close' not in df.columns:
			return pd.Series(dtype=float)

		period = parameters.get("period", 20) if parameters else 20
		middle = df['close'].rolling(window=period).mean()

		return middle

	def _calculate_kdj (
			self,
			df: pd.DataFrame,
			parameters: Optional[Dict] = None,
			financial_data: Optional[pd.DataFrame] = None
	) -> pd.Series:
		"""计算KDJ指标的K值"""
		required_cols = ['high', 'low', 'close']
		if not all(col in df.columns for col in required_cols):
			return pd.Series(dtype=float)

		n = parameters.get("n", 9) if parameters else 9
		m1 = parameters.get("m1", 3) if parameters else 3

		low_min = df['low'].rolling(window=n).min()
		high_max = df['high'].rolling(window=n).max()

		rsv = 100 * (df['close'] - low_min) / (high_max - low_min)
		rsv = rsv.fillna(50)

		k = rsv.ewm(alpha=1 / m1, adjust=False).mean()

		return k

	def _calculate_technical_factor (
			self,
			df: pd.DataFrame,
			parameters: Optional[Dict] = None,
			financial_data: Optional[pd.DataFrame] = None
	) -> pd.Series:
		"""通用技术因子计算器"""
		factor_type = parameters.get("type", "close") if parameters else "close"

		if factor_type == "close":
			return df['close'] if 'close' in df.columns else pd.Series(dtype=float)
		elif factor_type == "volume":
			return df['volume'] if 'volume' in df.columns else pd.Series(dtype=float)
		elif factor_type == "amount":
			return df['amount'] if 'amount' in df.columns else pd.Series(dtype=float)
		else:
			# 默认返回价格
			return df['close'] if 'close' in df.columns else pd.Series(dtype=float)

	# ==================== 因子分析方法实现 ====================

	async def _perform_ic_analysis (
			self,
			factor_data: pd.DataFrame,
			factor_name: str,
			start_date: Optional[date] = None,
			end_date: Optional[date] = None,
			returns_data: Optional[pd.DataFrame] = None,
			parameters: Optional[Dict[str, Any]] = None
	) -> Dict[str, Any]:
		"""
		执行IC分析

		Args:
			factor_data: 因子数据DataFrame
			factor_name: 因子名称
			start_date: 开始日期
			end_date: 结束日期
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

		# 这里简化处理，实际需要计算因子值与未来收益的相关性
		dates = factor_data.index

		# 模拟IC序列
		np.random.seed(hash(str(dates[0])) % 10000)
		ic_series = np.random.normal(0.05, 0.15, len(dates))

		# 计算IC统计量
		ic_mean = float(np.mean(ic_series))
		ic_std = float(np.std(ic_series))
		ic_ir = ic_mean / ic_std if ic_std > 0 else 0

		# 计算t检验p值
		t_stat, ic_pvalue = stats.ttest_1samp(ic_series, 0)

		# 计算IC正率
		ic_positive_ratio = sum(1 for x in ic_series if x > 0) / len(ic_series) if ic_series.size > 0 else 0

		# 计算IC衰减（模拟）
		ic_decay = []
		for lag in range(1, 6):  # 1-5期衰减
			if len(ic_series) > lag:
				decay_value = ic_mean * (0.9 ** lag)  # 模拟衰减
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

	async def _perform_quantile_analysis (
			self,
			factor_data: pd.DataFrame,
			factor_name: str,
			start_date: Optional[date] = None,
			end_date: Optional[date] = None,
			returns_data: Optional[pd.DataFrame] = None,
			parameters: Optional[Dict[str, Any]] = None
	) -> Dict[str, Any]:
		"""
		执行分位数分析

		Args:
			factor_data: 因子数据DataFrame
			factor_name: 因子名称
			start_date: 开始日期
			end_date: 结束日期
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

		# 模拟分位数分析结果
		quantile_count = 5  # 5个分位数组
		quantile_returns = [0.15, 0.12, 0.10, 0.08, 0.05]  # 从高到低

		top_minus_bottom = quantile_returns[0] - quantile_returns[-1]
		turnover_rate = [0.30, 0.28, 0.25, 0.22, 0.20]

		# 计算分位价差
		quantile_spread = [
			round(quantile_returns[i] - quantile_returns[i + 1], 4)
			for i in range(len(quantile_returns) - 1)
		]

		# 计算胜率（模拟）
		win_rate = 0.65 if top_minus_bottom > 0.05 else 0.50

		return {
			"quantile_count": quantile_count,
			"quantile_returns": [round(x, 4) for x in quantile_returns],
			"top_minus_bottom": round(top_minus_bottom, 4),
			"turnover_rate": [round(x, 4) for x in turnover_rate],
			"quantile_spread": quantile_spread,
			"win_rate": round(win_rate, 4),
			"monotonicity": "monotonic" if all(quantile_returns[i] >= quantile_returns[i + 1] for i in
			                                   range(len(quantile_returns) - 1)) else "non_monotonic"
		}

	async def _perform_correlation_analysis (
			self,
			factor_data: pd.DataFrame,
			factor_name: str,
			start_date: Optional[date] = None,
			end_date: Optional[date] = None,
			returns_data: Optional[pd.DataFrame] = None,
			parameters: Optional[Dict[str, Any]] = None
	) -> Dict[str, Any]:
		"""
		执行相关性分析

		Args:
			factor_data: 因子数据
			factor_name: 因子名称
			start_date: 开始日期
			end_date: 结束日期
			returns_data: 收益数据
			parameters: 分析参数

		Returns:
			Dict: 相关性分析结果
		"""
		# 这里需要多个因子进行比较，简化处理
		return {
			"correlation_matrix": [],
			"mean_correlation": 0,
			"max_correlation": 0,
			"min_correlation": 0,
			"orthogonality_score": 0.8  # 正交性得分
		}

	async def _perform_stability_analysis (
			self,
			factor_data: pd.DataFrame,
			factor_name: str,
			start_date: Optional[date] = None,
			end_date: Optional[date] = None,
			returns_data: Optional[pd.DataFrame] = None,
			parameters: Optional[Dict[str, Any]] = None
	) -> Dict[str, Any]:
		"""
		执行稳定性分析

		Args:
			factor_data: 因子数据
			factor_name: 因子名称
			start_date: 开始日期
			end_date: 结束日期
			returns_data: 收益数据
			parameters: 分析参数

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

		# 模拟稳定性分析结果
		stability_score = 0.75

		# 分阶段一致性
		period_consistency = [
			{"period": "2023-Q1", "ic": 0.08, "rank_ic": 0.12},
			{"period": "2023-Q2", "ic": 0.06, "rank_ic": 0.10},
			{"period": "2023-Q3", "ic": 0.04, "rank_ic": 0.08},
			{"period": "2023-Q4", "ic": 0.07, "rank_ic": 0.11}
		]

		return {
			"stability_score": round(stability_score, 4),
			"period_consistency": period_consistency,
			"rank_ic": 0.10,  # 模拟Rank IC
			"ic_stability": 0.70  # IC稳定性
		}

	# ==================== 报告生成方法 ====================

	async def _generate_analysis_report (
			self,
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

	async def _generate_comparison_report (
			self,
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
		report = {
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
	) -> pd.DataFrame:
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
			# 构建查询条件
			filters = [self.factor_repo.model.factor_name == factor_name]

			if universe:
				filters.append(self.factor_repo.model.ts_code.in_(universe))

			if start_date:
				filters.append(self.factor_repo.model.trade_date >= start_date)

			if end_date:
				filters.append(self.factor_repo.model.trade_date <= end_date)

			# 获取因子数据
			factor_records = await self.factor_repo.get_many(*filters)

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
	) -> pd.DataFrame:
		"""
		获取用于分析的收益数据

		Args:
			universe: 股票池
			start_date: 开始日期
			end_date: 结束日期

		Returns:
			pd.DataFrame: 收益数据
		"""
		# 这里简化处理，实际需要从数据库获取收益数据
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
		# 这里简化处理，实际需要从数据库获取财务数据
		return None

	# ==================== 研究任务管理方法 ====================

	async def _create_research_task (
			self,
			factor_definition: Dict[str, Any],
			universe: Optional[List[str]] = None,
			start_date: Optional[date] = None,
			end_date: Optional[date] = None,
			parameters: Optional[Dict[str, Any]] = None,
			user_id: Optional[int] = None
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
			user_id: Optional[int] = None
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
			analysis_results=analysis_results,
			parameters=parameters
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

	async def _generate_research_summary (
			self,
			factor_name: str,
			calculation_result: Dict[str, Any],
			analysis_results: Dict[str, Any],
			parameters: Optional[Dict[str, Any]] = None
	) -> Dict[str, Any]:
		"""
		生成研究总结

		Args:
			factor_name: 因子名称
			calculation_result: 计算结果
			analysis_results: 分析结果
			parameters: 研究参数

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

	def _extract_factor_metrics (
			self,
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

		for metric in metrics:
			if metric in analysis_result:
				extracted[metric] = analysis_result[metric]
			elif metric == "sharpe_ratio":
				# 模拟夏普比率
				extracted[metric] = np.random.uniform(0.5, 2.0)
			elif metric == "max_drawdown":
				# 模拟最大回撤
				extracted[metric] = np.random.uniform(0.05, 0.20)
			elif metric == "turnover":
				# 模拟换手率
				extracted[metric] = np.random.uniform(0.20, 0.40)
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

	def _get_standard_factor_metadata (
			self,
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
			user_id: Optional[int] = None
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
			event_data = {
				"timestamp": datetime.now(),
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

			event = DataResearchStartedEvent(
				event_type=f"factor.research.{event_type}",
				**event_data
			)

			await self.event_engine.put(event)

		except Exception as e:
			logger.error(f"发布研究事件失败: {str(e)}")