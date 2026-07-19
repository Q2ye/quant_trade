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
from typing import Callable, Dict, List, Any, Optional

import numpy as np
import pandas as pd
from pandas import DataFrame
from scipy import stats
from sqlalchemy import select, and_
from sqlalchemy.ext.asyncio import AsyncSession
from shared.database.models.data_models import StockDaily

# 导入核心基础设施
from core.engines.system.event_engine import EventEngine
from core.events.base import TypedEvent
from core.exceptions.business_exceptions import BusinessException
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
	FinancialIncomeRepository,
)
from shared.database.repositories.market.quote.etf_daily_repo import EtfDailyRepository
from shared.database.repositories.market.basic.etf_repo import ETFRepository
# 导入工具类
from utils.core_utils.math_utils import StatisticalCalculator
from modules.data.factor_calculators import (
    get_calculator,
    get_all_factors,
    get_metadata_list,
    FactorSpec,
)

# 配置日志
logger = logging.getLogger(__name__)

# factor_data 表 factor_value 列定义为 NUMERIC(18,6)
# 精度 18，小数位 6 → 整数部分最多 12 位 → 绝对值上限 ≈ 10^12
# 设置安全上限为 9.99×10^11（略低于 DB 上限）
# v3.2: MC/PS 因子已改为万元单位，正常值不会触发此上限
_MAX_FACTOR_VALUE = 9.99e11


def _safe_float(value: Any) -> Optional[float]:
    """
    安全转换为 float，处理 np.isnan 不兼容的类型（None、Decimal 等）。

    - None → None
    - Decimal → float
    - np.nan / np.inf → None
    - 普通数值 → float（溢出时截断并告警）
    """
    if value is None:
        return None
    try:
        fv = float(value)
    except (ValueError, TypeError):
        return None
    if np.isnan(fv) or np.isinf(fv):
        return None
    if abs(fv) >= _MAX_FACTOR_VALUE:
        logger.warning(
            "因子值 %s 超过安全上限 %s，截断为 %s",
            fv, _MAX_FACTOR_VALUE, _MAX_FACTOR_VALUE
        )
        return _MAX_FACTOR_VALUE if fv > 0 else -_MAX_FACTOR_VALUE
    return fv


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
		self._caller_research_id: Optional[str] = None

		# 初始化Repository
		self.stock_repo = StockBasicRepository(session)
		self.quote_repo = StockDailyRepository(session)
		self.factor_repo = FactorDataRepository(session)
		self.factor_def_repo = FactorDefinitionRepository(session)
		self.research_repo = FactorResearchRepository(session)
		self.financial_repo = FinancialIncomeRepository(session)
		# ETF 数据源（v3.4 新增）
		self.etf_basic_repo = ETFRepository(session)
		self.etf_daily_repo = EtfDailyRepository(session)
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
			user_id: Optional[str] = None,
			research_id: Optional[str] = None,
			cancel_token = None,        # asyncio.Event or None
			progress_callback = None,   # callable(step_name, progress_float) or None
	) -> Dict[str, Any]:
		"""
		执行因子研究

		Args:
			factor_definition: 因子定义
			universe: 股票池
			start_date / end_date: 日期范围
			parameters: 研究参数
			user_id: 用户ID
			research_id: 研究ID（handler 预先创建，传 None 则自动生成）
			cancel_token: asyncio.Event 取消令牌
			progress_callback: 进度回调 callable(step, progress_0_1)

		Returns:
			Dict: 研究结果
		"""
		logger.info(f"开始因子研究，因子: {factor_definition.get('name')}")

		try:
			# 使用 handler 传入的 research_id，否则自建
			if research_id:
				self._caller_research_id = research_id

			# 创建/更新研究任务记录
			research_id = await self._create_research_task(
				factor_definition=factor_definition,
				universe=universe,
				start_date=start_date,
				end_date=end_date,
				parameters=parameters,
				user_id=user_id
			)

			# 取消检查
			if cancel_token and cancel_token.is_set():
				return {"success": False, "research_id": research_id,
				        "cancelled": True, "message": "任务已取消"}

			if progress_callback:
				await progress_callback("计算因子数据", 0.15)

			# 执行研究
			research_result = await self._execute_factor_research(
				factor_definition=factor_definition,
				universe=universe,
				start_date=start_date,
				end_date=end_date,
				parameters=parameters,
				research_id=research_id,
				user_id=user_id,
				cancel_token=cancel_token,
				progress_callback=progress_callback,
			)

			# 检查取消
			if research_result.get("cancelled"):
				return research_result

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
				"result": research_result.get("analysis_results", {}),
				"analysis_results": research_result.get("analysis_results", {}),
				"summary": research_result.get("summary", {}),
				"report": research_result.get("report", {}),
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
			user_id: Optional[str] = None,
			cancel_token = None,        # asyncio.Event or None
			progress_callback = None,   # callable(step_name, progress_float) or None
			data_source: str = "stock", # "stock" | "etf" (v3.4)
	) -> Dict[str, Any]:
		"""
		计算因子数据

		Args:
			factor_name: 因子名称
			ts_codes: 股票代码列表，不指定则计算所有股票（或全部 ETF）
			start_date: 开始日期
			end_date: 结束日期
			parameters: 计算参数
			batch_size: 批量大小
			user_id: 用户ID
			cancel_token: asyncio.Event 取消令牌
			progress_callback: 进度回调 callable(step, progress_0_1)
			data_source: 数据源 ("stock"=个股stock_daily, "etf"=ETF etf_daily)

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

			# 检查因子计算器是否存在（与 _calculate_single_factor 一致的查找逻辑）
			calculator = self._factor_calculators.get(factor_name)
			if not calculator:
				_FACTOR_ALIASES = {
					"rsi_14": "rsi", "pe_ttm": "pe", "kdj_k": "kdj",
					"volume_ratio_5d": "volume_ratio", "turnover_5d": "turnover_rate",
					"gross_margin": "gm", "operating_margin": "om", "debt_ratio": "dr",
					# v3.2 新增别名（覆盖 seed_factor_definitions.sql 全部 34 个定义）
					"pb_ttm": "pb", "ps_ttm": "ps",
					"roe_ttm": "roe", "roa_ttm": "roa",
					"current_ratio": "current_ratio", "quick_ratio": "quick_ratio",
					"market_cap": "mc", "total_market_cap": "mc",
					"circulating_market_cap": "mc",
					"beta_60d": "beta", "sharpe_ratio_60d": "sharpe_ratio",
					"atr_14": "atr",
				}
				alias = _FACTOR_ALIASES.get(factor_name.lower())
				if alias:
					calculator = self._factor_calculators.get(alias) or self._factor_calculators.get(alias.upper())
			if not calculator:
				import re as _re2
				base = _re2.sub(r'_\d+[a-z]?$', '', factor_name).lower()
				for name in self._factor_calculators:
					if name.lower() == base or name.lower() == factor_name.lower():
						calculator = self._factor_calculators[name]
						break
			if not calculator:
					db_def = await self.factor_def_repo.get_by_code(factor_name) or await self.factor_def_repo.get_by_name(factor_name)
					if db_def:
						# 用 DB 中的 factor_code 重试（兼容前端传中文显示名的场景）
						code = db_def.factor_code
						calculator = (self._factor_calculators.get(code)
							or self._factor_calculators.get(code.lower())
							or self._factor_calculators.get(code.upper()))
						if calculator:
							logger.info("因子 '%s' 通过 DB factor_code='%s' 解析成功", factor_name, code)
							factor_name = code
					if db_def and not calculator:
						raise ValueError(
							f"因子 '{factor_name}' (DB 代码: {db_def.factor_code}) 已定义但缺少计算器。"
							f"请在 factor_calculators.py 中添加 @register_factor(name='{db_def.factor_code}', ...)"
						)
					if not db_def:
						raise ValueError(
							f"未知因子 '{factor_name}'，既无计算器也无定义。"
							f"可用: {list(self._factor_calculators.keys())[:15]}"
						)

			# 获取标的列表（universe 已在上游 _resolve_universe 中解析）
			if not ts_codes:
				if data_source == "etf":
					# ETF 模式：从 etf_basic 获取所有上市 ETF
					etfs = await self.etf_basic_repo.get_all()
					ts_codes = [etf.ts_code for etf in etfs if getattr(etf, 'list_status', None) == 'L']
					logger.info("ETF 模式：从 etf_basic 加载 %d 只 ETF", len(ts_codes))
				else:
					# 个股模式：获取所有活跃股票（按市场查询）
					stocks = await self.stock_repo.get_by_market("主板", active_only=True)
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

			# 串行逐只计算（AsyncSession 不支持并发协程共享，asyncio.gather 会导致随机查询失败）
			for i, ts_code in enumerate(ts_codes):
				try:
					result = await self._calculate_single_factor(
						factor_name=factor_name,
						ts_code=ts_code,
						start_date=datetime.combine(start_date, datetime.min.time()),
						end_date=datetime.combine(end_date, datetime.min.time()),
						parameters=parameters,
						data_source=data_source,
					)
					if result:
						try:
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
					else:
						failed_calculations.append({
							"ts_code": ts_code,
							"error": f"无可用行情数据"
						})
				except Exception as e:
					logger.error(f"计算股票 {ts_code} 的因子 {factor_name} 失败: {str(e)}")
					failed_calculations.append({
						"ts_code": ts_code,
						"error": str(e)
					})

				# 每处理 batch_size 只或最后一只时更新进度
				if (i + 1) % batch_size == 0 or i == total_stocks - 1:
					batch_progress = 0.15 + 0.3 * ((i + 1) / total_stocks)
					if progress_callback:
						await progress_callback(f"计算因子 {int(batch_progress*100)}%", batch_progress)
					if cancel_token and cancel_token.is_set():
						return {"success": False, "task_id": task_id,
						        "cancelled": True, "message": "任务已取消"}

					await self._publish_research_event(
						event_type="progress",
						research_id=task_id,
						factor_name=factor_name,
						progress=batch_progress * 100,
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

			# 警告：所有股票均无有效因子值（计算器未实现或数据不满足条件）
			if calculated_count == 0 and total_stocks > 0:
				logger.warning(
					"因子 %s: %d 只股票全部计算失败（success=0/%d），"
					"factor_data 表无数据写入，后续分析将为空。"
					"请检查计算器实现（如 BETA/SHARPE_RATIO 需市场指数数据）。",
					factor_name, total_stocks, total_stocks
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

			# 检查是否需要收益数据（IC、分组、稳定性分析都需要）
			if analysis_type in ["ic_analysis", "quantile_analysis", "stability_analysis"]:
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
					logger.warning(
						"因子分析失败 [%s / %s]: returns_data 为空 — "
						"stock_daily 表中无行情数据，请确认日期范围内有交易数据且 universe 解析正确",
						factor_name, analysis_type
					)
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

			try:
				await self.cache.set(
					cache_key,
					{
						"analysis_result": analysis_result,
						"report": report,
						"generated_at": datetime.now().isoformat()
					},
					ttl=86400
				)
			except Exception:
				pass  # Redis 不可用或序列化失败时跳过缓存

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
					"factor_code": factor.factor_code,  # 因子代码（唯一标识）
					"factor_name": factor.factor_name or factor.display_name or factor.factor_code,  # 显示名
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
			parameters: Optional[Dict[str, Any]] = None,
			data_source: str = "stock",
	) -> List[Dict[str, Any]]:
		"""
		计算单只股票/ETF 的因子

		Args:
			factor_name: 因子名称
			ts_code: 股票/ETF 代码
			start_date: 开始日期
			end_date: 结束日期
			parameters: 计算参数
			data_source: "stock"=stock_daily, "etf"=etf_daily

		Returns:
			List[Dict]: 因子值列表，每个元素包含：
				- trade_date: 交易日期
				- factor_name: 因子名称
				- factor_value: 因子值
				- ts_code: 股票代码
				- calculated_at: 计算时间
		"""
		try:
			# 获取计算器：精确 → 别名表 → 模糊去后缀 → 兜底
			# 因子名别名：seed SQL factor_code(参数化) → 注册计算器名
			_FACTOR_ALIASES = {
				"rsi_14": "rsi", "pe_ttm": "pe", "kdj_k": "kdj",
				"volume_ratio_5d": "volume_ratio", "turnover_5d": "turnover_rate",
				"gross_margin": "gm", "operating_margin": "om", "debt_ratio": "dr",
			}
			calculator = self._factor_calculators.get(factor_name)
			if not calculator:
				alias = _FACTOR_ALIASES.get(factor_name.lower())
				if alias:
					calculator = self._factor_calculators.get(alias)
				if not calculator and alias:
					calculator = self._factor_calculators.get(alias.upper())
			if not calculator:
				# 模糊匹配：参数化因子名去掉后缀数字再匹配（ema_12 → ema, ma_20 → ma）
				import re as _re
				base = _re.sub(r'_\d+[a-z]?$', '', factor_name).lower()
				for key, calc in self._factor_calculators.items():
					if key.lower() == base or key.lower() == factor_name.lower():
						calculator = calc
						break
			if not calculator:
					db_def = await self.factor_def_repo.get_by_code(factor_name) or await self.factor_def_repo.get_by_name(factor_name)
					if db_def:
						# 用 DB 中的 factor_code 重试（兼容前端传中文显示名的场景）
						code = db_def.factor_code
						calculator = (self._factor_calculators.get(code)
							or self._factor_calculators.get(code.lower())
							or self._factor_calculators.get(code.upper()))
						if calculator:
							logger.info("因子 '%s' 通过 DB factor_code='%s' 解析成功", factor_name, code)
							factor_name = code
					if db_def and not calculator:
						raise ValueError(
							f"因子 '{factor_name}' (DB 代码: {db_def.factor_code}) 已定义但缺少计算器。"
							f"请在 factor_calculators.py 中添加 @register_factor(name='{db_def.factor_code}', ...)"
						)
					if not db_def:
						raise ValueError(
							f"未知因子 '{factor_name}'，既无计算器也无定义。"
							f"可用: {list(self._factor_calculators.keys())[:15]}"
						)

			# 获取行情数据 — 根据 data_source 选择数据表
			if data_source == "etf":
				quotes = await self.etf_daily_repo.get_by_code_and_date_range(
					ts_code=ts_code,
					start_date=start_date.date() if hasattr(start_date, 'date') else start_date,
					end_date=end_date.date() if hasattr(end_date, 'date') else end_date,
				)
			else:
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

			# 计算因子值 — 委托因子计算器注册表统一派发（含别名/模糊匹配）
			from modules.data.factor_calculators import get_calculator as _get_spec, get_all_factors as _get_all
			calc_spec = _get_spec(factor_name)
			if not calc_spec:
				_FACTOR_ALIASES = {
					"rsi_14": "rsi", "pe_ttm": "pe", "kdj_k": "kdj",
					"volume_ratio_5d": "volume_ratio", "turnover_5d": "turnover_rate",
					"gross_margin": "gm", "operating_margin": "om", "debt_ratio": "dr",
					# v3.2 新增别名（覆盖 seed_factor_definitions.sql 全部 34 个定义）
					"pb_ttm": "pb", "ps_ttm": "ps",
					"roe_ttm": "roe", "roa_ttm": "roa",
					"current_ratio": "current_ratio", "quick_ratio": "quick_ratio",
					"market_cap": "mc", "total_market_cap": "mc",
					"circulating_market_cap": "mc",
					"beta_60d": "beta", "sharpe_ratio_60d": "sharpe_ratio",
					"atr_14": "atr",
				}
				alias = _FACTOR_ALIASES.get(factor_name.lower())
				if alias:
					calc_spec = _get_spec(alias) or _get_spec(alias.upper())
			if not calc_spec:
				import re as _re_fuzzy
				base = _re_fuzzy.sub(r'_\d+[a-z]?$', '', factor_name).lower()
				for name, spec in _get_all().items():
					if name.lower() == base or name.lower() == factor_name.lower():
						calc_spec = spec
						break

			# 从参数化因子名提取 period（如 ema_26 → 26, ma_20 → 20）
			import re as _re
			calc_params = dict(parameters) if parameters else {}
			param_match = _re.match(r'^[a-zA-Z]+_(\d+)[a-z]?$', factor_name)
			if param_match and 'period' not in calc_params:
				calc_params['period'] = int(param_match.group(1))

			# 根据 data_source 决定是否拉取财务数据（而非硬编码因子名列表）
			financial_data = None
			if calc_spec and calc_spec.data_source in ("both", "financial"):
				financial_data = await self._get_financial_data(ts_code, start_date.date(), end_date.date())

			# BETA 因子需要基准指数收益率
			beta_factor_names = {"BETA", "beta", "Beta"}
			if factor_name in beta_factor_names or (
				calc_spec and calc_spec.name in beta_factor_names
			):
				if not hasattr(self, '_benchmark_returns_cache'):
					self._benchmark_returns_cache = None  # type: ignore
				# 缓存 index returns（同一批次所有股票共用）
				cache_key = (start_date.date(), end_date.date())
				if (not hasattr(self, '_benchmark_cache_key')
						or self._benchmark_cache_key != cache_key):
					self._benchmark_returns_cache = await self._get_benchmark_returns(
						start_date.date(), end_date.date()
					)
					self._benchmark_cache_key = cache_key
				if calc_params is None:
					calc_params = {}
				calc_params['benchmark_returns'] = self._benchmark_returns_cache

			if calc_spec:
				if calc_spec.data_source in ("both", "financial"):
					factor_series = calc_spec.calculator(df, financial_data)
				elif calc_spec.category == "technical":
					factor_series = calc_spec.calculator(df, calc_params)
				else:
					factor_series = calc_spec.calculator(df, calc_params)
			else:
				# 兜底：通过别名/模糊匹配找到的计算器，回查其 data_source 以正确传参
					ds = "market"
					for spec in get_all_factors().values():
						if spec.calculator is calculator:
							ds = spec.data_source
							break
					if ds in ("both", "financial"):
						factor_series = calculator(df, financial_data)
					else:
						factor_series = calculator(df, calc_params)

			if factor_series.empty:
				logger.warning(
					"因子 %s 在 %s 上返回空序列（计算器未实现或数据不足）",
					factor_name, ts_code
				)
				return []
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
					"factor_value": _safe_float(factor_val),
					"ts_code": ts_code,
					"updated_at": datetime.now()
				})

			# 全部为 None（NaN/Inf 转换）→ 视为无有效数据，返回空列表
			# 否则 calculate_factor 会虚增 calculated_count，导致分析阶段
			# 查不到数据但页面却显示"计算完成"
			if result and all(r.get("factor_value") is None for r in result):
				return []

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
			# 直接批量插入，重复键由 DB 层处理
			factor_data_list = []
			for factor_value in factor_values:
				if factor_value.get("factor_value") is None:
					continue
				factor_data_list.append(factor_value)

			if factor_data_list:
				await self.factor_repo.batch_insert_factor_data(factor_data_list)
			else:
				logger.warning(
					"因子 %s 股票 %s: 所有因子值为 None（计算器未实现或数据不足），"
					"未写入 factor_data 表",
					factor_name, ts_code
				)

			await self.session.commit()

		except Exception as e:
			msg = str(e)
			if "没有匹配ON CONFLICT" in msg or "InvalidColumnReferenceError" in msg:
				logger.info(
					"factor_data 表缺少唯一索引 (uq_factor_data_code_name_date)，"
					"因子值未更新。请执行: "
					"psql -d quant_signals_dev -f docs/sql/migration_add_missing_unique_indexes.sql"
				)
			elif "NumericValueOutOfRange" in msg or "数字字段溢出" in msg:
				logger.warning(
					"因子 %s 股票 %s: 数值超出 NUMERIC(18,6) 范围 (>=10^12)，"
					"已跳过。建议检查计算器输出或扩大 factor_value 列精度",
					factor_name, ts_code
				)
			else:
				logger.warning(f"保存因子数据失败(非致命): {msg}")
			try:
				await self.session.rollback()
			except Exception:
				pass

	# ==================== 因子计算器实现 ====================

	def _init_factor_calculators (self) -> Dict[str, Callable]:
		"""
		初始化因子计算器映射

		calculate_factor 中的因子名查找逻辑（精确 → 别名表 → 模糊去后缀）已处理
		大小写不敏感问题，无需额外创建小写键副本。

		Returns:
			Dict: 因子计算器映射 {name: callable}
		"""
		return {name: spec.calculator for name, spec in get_all_factors().items()}

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
	# ==================== 因子分析方法实现 ====================
	async def _compute_cross_sectional_stats(
			self,
			factor_name: str,
			factor_data_items: List[Dict],
	) -> Dict[str, Any]:
		"""
		逐日横截面标准化：计算 z_score / percentile / rank（v3.2 新增）

		对每只股票 per-trade_date 的 factor_value，在全市场横截面上做标准化：
		- z_score = (winsorized_value - mean) / std   （5%/95% Winsorize）
		- percentile = rank / N                        （值越大 percentile 越接近 1）
		- rank = 1-based rank（值最大=1）

		Args:
			factor_name: 因子代码
			factor_data_items: calculate_factor 返回的原始数据列表
				[{ts_code, trade_date, factor_value}]

		Returns:
			{trade_dates: int, updated_rows: int}
		"""
		import numpy as np
		import pandas as pd
		from sqlalchemy import update as _sql_update
		from shared.database.models.data_models import FactorData as _FD

		if not factor_data_items:
			return {"trade_dates": 0, "updated_rows": 0}

		df = pd.DataFrame(factor_data_items)
		if df.empty or "factor_value" not in df.columns:
			return {"trade_dates": 0, "updated_rows": 0}

		updated_rows = 0
		trade_dates_processed = 0

		for trade_date, group in df.groupby("trade_date"):
			values = group["factor_value"].values.astype(float)
			valid_mask = ~np.isnan(values)
			n_valid = valid_mask.sum()

			if n_valid < 10:
				continue  # 样本太少，跨截面无统计意义

			# Winsorize (5%/95%)
			lo, hi = np.percentile(values[valid_mask], [5, 95])
			winsorized = np.clip(values.copy(), lo, hi)

			# z_score
			mu = np.mean(winsorized[valid_mask])
			sigma = np.std(winsorized[valid_mask])
			safe_sigma = sigma if sigma > 1e-12 else 1e-12
			z_scores = np.full_like(values, np.nan)
			z_scores[valid_mask] = (winsorized[valid_mask] - mu) / safe_sigma

			# rank (1 = 最大值，ascending=False 的效果)
			ranks = np.full(len(values), np.nan)
			rank_order = np.argsort(np.argsort(-values[valid_mask]))
			ranks[valid_mask] = rank_order.astype(float) + 1.0

			# percentile
			percentiles = np.full_like(values, np.nan)
			percentiles[valid_mask] = ranks[valid_mask] / n_valid

			# 批量更新 DB
			codes = group["ts_code"].values
			batch_updated = 0
			try:
				for i, ts in enumerate(codes):
					if not valid_mask[i]:
						continue
					stmt = (
						_sql_update(_FD)
						.where(
							_FD.ts_code == ts,
							_FD.factor_name == factor_name,
							_FD.trade_date == trade_date,
						)
						.values(
							z_score=round(float(z_scores[i]), 6),
							percentile=round(float(percentiles[i]), 6),
							rank=int(ranks[i]),
						)
					)
					result = await self.session.execute(stmt)
					batch_updated += result.rowcount
			except Exception as _up_e:
				logger.warning(
					f"更新 {factor_name} {trade_date} 横截面统计失败: {_up_e}"
				)
				continue

			updated_rows += batch_updated
			trade_dates_processed += 1

		if updated_rows > 0:
			await self.session.commit()
			logger.info(
				f"横截面标准化完成: {factor_name} "
				f"{trade_dates_processed} 个交易日, {updated_rows} 行已更新"
			)

		return {
			"trade_dates": trade_dates_processed,
			"updated_rows": updated_rows,
		}

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
			logger.warning(
				"factor_data 为空，无法执行分析 — 因子数据表中无数据，"
				"请确认 calculate_factor 已写入成功且 factor_code 匹配正确",
				)
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
		skipped_no_forward = 0
		skipped_no_stocks = 0
		valid_count = 0
		for dt in dates:
			try:
				# 获取当前日期的因子值
				if dt in factor_data.index:
					factor_values = factor_data.loc[dt]

					# 获取下一期的收益数据
					forward_period = int(parameters.get("forward_period", 1)) if parameters else 1
					try:
						dt_idx = returns_data.index.get_loc(dt)
						if dt_idx + forward_period < len(returns_data.index):
							forward_date = returns_data.index[dt_idx + forward_period]
						else:
							forward_date = None
					except KeyError:
						forward_date = None

					if forward_date is not None and forward_date in returns_data.index:
						forward_returns = returns_data.loc[forward_date]

						# 计算相关系数（IC）
						# 确保 factor_values 和 forward_returns 是 Series 类型
						if isinstance(factor_values, pd.Series) and isinstance(forward_returns, pd.Series):
							valid_stocks = factor_values.dropna().index.intersection(forward_returns.dropna().index)
						else:
							valid_stocks = []

						if len(valid_stocks) >= 10:  # 至少需要10只股票
							try:
								# v3.2: Rank IC (Spearman)
								from scipy.stats import spearmanr as _spearmanr
								rank_ic, _ = _spearmanr(
									factor_values[valid_stocks],
									forward_returns[valid_stocks]
								)
								ic_series.append(rank_ic if not np.isnan(rank_ic) else 0)
							except (ValueError, TypeError):
								ic_series.append(0)
						else:
							ic_series.append(0)
							skipped_no_stocks += 1
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
			"ic_series": [
				{"date": dt.strftime("%Y-%m-%d") if hasattr(dt, 'strftime') else str(dt)[:10],
				 "value": round(float(x), 4)}
				for dt, x in zip(dates, ic_series)
			],
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
			logger.warning(
				"factor_data 为空，无法执行分析 — 因子数据表中无数据，"
				"请确认 calculate_factor 已写入成功且 factor_code 匹配正确",
				)
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

	@staticmethod
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
			logger.warning(
				"factor_data 为空，无法执行分析 — 因子数据表中无数据，"
				"请确认 calculate_factor 已写入成功且 factor_code 匹配正确",
				)
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

		# 批量获取因子数据（单次 DB 查询替代 N+1）
		if other_factor_names:
			try:
				multi_data = await self._get_multi_factor_data_for_analysis(
					factor_names=other_factor_names,
					start_date=start_date,
					end_date=end_date
				)
				for other_factor, other_series in multi_data.items():
					if other_series is not None and not other_series.empty:
						factor_matrix[other_factor] = other_series
			except Exception as e:
				logger.warning(f"批量获取因子数据失败: {e}")
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
			logger.warning(
				"factor_data 为空，无法执行分析 — 因子数据表中无数据，"
				"请确认 calculate_factor 已写入成功且 factor_code 匹配正确",
				)
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
			unique_quarters = sorted(dates_quarterly.unique().tolist())

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

	async def _get_multi_factor_data_for_analysis(
			self,
			factor_names: List[str],
			start_date: Optional[date] = None,
			end_date: Optional[date] = None
	) -> Dict[str, Optional[pd.Series]]:
		"""
		批量获取多个因子的数据（单次DB查询，消除N+1）
		"""
		try:
			from sqlalchemy import select as _sel_mf
			query = _sel_mf(self.factor_repo.model).where(
				self.factor_repo.model.factor_name.in_(factor_names)
			)
			if start_date:
				query = query.where(self.factor_repo.model.trade_date >= start_date)
			if end_date:
				query = query.where(self.factor_repo.model.trade_date <= end_date)
			result = await self.factor_repo.session.execute(query)
			records = result.scalars().all()
			if not records:
				return {fn: None for fn in factor_names}
			df = pd.DataFrame([{
				'trade_date': r.trade_date,
				'factor_name': r.factor_name,
				'factor_value': float(r.factor_value) if r.factor_value is not None else None,
			} for r in records if r.factor_value is not None])
			if df.empty:
				return {fn: None for fn in factor_names}
			result_dict = {}
			for fn in factor_names:
				fn_df = df[df['factor_name'] == fn]
				if fn_df.empty:
					result_dict[fn] = None
				else:
					pivot = fn_df.pivot_table(index='trade_date', columns='factor_name', values='factor_value')
					result_dict[fn] = pivot.iloc[:, 0] if not pivot.empty else None
			return result_dict
		except Exception as e:
			logger.warning(f"批量获取因子数据失败: {e}")
			return {fn: None for fn in factor_names}

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
				logger.warning(
					"因子 %s: factor_data 表中无数据 — "
					"计算器可能未实现或依赖的数据（如财务数据/指数数据）不可用",
					factor_name
				)
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
			pivot_df.index = pd.to_datetime(pivot_df.index)
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
				stocks = await self.stock_repo.get_all(limit=500)
				universe = [stock.ts_code for stock in stocks]

			if not universe:
				return pd.DataFrame()

			# 构建日期过滤条件
			start_dt = datetime.combine(start_date, datetime.min.time()) if isinstance(start_date, date) else start_date
			end_dt = datetime.combine(end_date, datetime.min.time()) if isinstance(end_date, date) else end_date

			# 单次批量查询：一次 DB 往返获取所有股票的行情数据（消除 N+1）
			stmt = select(StockDaily).where(
				and_(
					StockDaily.ts_code.in_(universe),
					StockDaily.trade_date >= start_dt,
					StockDaily.trade_date <= end_dt
				)
			).order_by(StockDaily.trade_date, StockDaily.ts_code)
			result = await self.session.execute(stmt)
			quotes = result.scalars().all()

			# 按股票分组构建收益数据
			returns_data: Dict[str, List[Dict[str, Any]]] = {}
			for quote in quotes:
				if quote.close is not None and quote.pre_close is not None and quote.pre_close != 0:
					ret = (float(quote.close) - float(quote.pre_close)) / float(quote.pre_close)
					if quote.ts_code not in returns_data:
						returns_data[quote.ts_code] = []
					returns_data[quote.ts_code].append({'trade_date': quote.trade_date, 'return': ret})

			if not returns_data:
				return pd.DataFrame()

			# 构建 DataFrame: index=dates, columns=stocks, values=return
			all_dates = sorted(set(q.trade_date for q in quotes))
			df_dict: Dict[str, List[Optional[float]]] = {}
			for ts_code, recs in returns_data.items():
				rec_map = {r['trade_date']: r['return'] for r in recs}
				df_dict[ts_code] = [rec_map.get(d) for d in all_dates]
			returns_df = pd.DataFrame(df_dict, index=pd.DatetimeIndex(all_dates))
			returns_df.index = pd.to_datetime(returns_df.index)
			return returns_df

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
			if self.financial_repo is None:
				logger.warning("financial_repo 未初始化，无法获取财务数据")
				return None

			# v2.1 PIT 修复：按 f_ann_date（实际公告日）过滤，消除未来函数
			# end_date 参数表示查询时点（当前 bar 日期），
			# 只获取在该日期之前已实际公告的财报数据
			query_date = end_date  # end_date 在此上下文中为查询时点

			try:
				from sqlalchemy import select as _sel_fi
				from shared.database.models.data_models import FinancialIncome
				fi_stmt = _sel_fi(FinancialIncome).where(
					FinancialIncome.ts_code == ts_code,
					FinancialIncome.f_ann_date <= query_date,  # PIT 关键：只取已披露的
				)
				fi_result = await self.session.execute(fi_stmt)
				financial_statements = fi_result.scalars().all()
			except Exception:
				logger.debug(f"无法获取 {ts_code} 的财务数据，跳过")
				return None

			if not financial_statements:
				return None

			# 确保是列表格式
			if not isinstance(financial_statements, list):
				financial_statements = [financial_statements]

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
				
				# =====================合并资产负债表数据（若可用）
			try:
				from shared.database.models.data_models import FinancialBalance
				from sqlalchemy import select as _sel_bs
				bs_stmt = _sel_bs(FinancialBalance).where(
					FinancialBalance.ts_code == ts_code,
					FinancialBalance.end_date >= start_date,
					FinancialBalance.end_date <= end_date,
					FinancialBalance.f_ann_date <= query_date,  # PIT 关键：只取已披露的
				)
				bs_result = await self.session.execute(bs_stmt)
				bs_records = bs_result.scalars().all()
				for bs in (bs_records or []):
					bk = bs.end_date
					if bk not in financial_data:
						financial_data[bk] = {}
					fd = financial_data[bk]
					fd['total_assets'] = float(bs.total_assets) if bs.total_assets else None
					fd['total_liab'] = float(bs.total_liab) if bs.total_liab else None
					fd['total_cur_assets'] = float(bs.total_cur_assets) if bs.total_cur_assets else None
					fd['total_cur_liab'] = float(bs.total_cur_liab) if bs.total_cur_liab else None
					fd['inventories'] = float(bs.inventories) if bs.inventories else None
					fd['total_hldr_eqy'] = float(bs.total_hldr_eqy_exc_min_int) if bs.total_hldr_eqy_exc_min_int else None
					fd['total_share'] = float(bs.total_share) if bs.total_share else None
			except Exception as _bs_e:
				logger.debug(f"获取 {ts_code} 资产负债表数据失败: {_bs_e}")

			# 计算需要资产负债表数据的财务指标
			for date_key, data in financial_data.items():
				try:
					n_income = data.get('n_income') or data.get('n_income_attr_p')
					equity = data.get('total_hldr_eqy')
					total_assets = data.get('total_assets')
					total_liab = data.get('total_liab')
					cur_assets = data.get('total_cur_assets')
					cur_liab = data.get('total_cur_liab')
					inventories = data.get('inventories')
					total_share = data.get('total_share')

					# ROE = 净利润 / 净资产
					data['roe'] = n_income / equity if n_income and equity and equity > 0 else None
					# ROA = 净利润 / 总资产
					data['roa'] = n_income / total_assets if n_income and total_assets and total_assets > 0 else None
					# 资产负债率 = 总负债 / 总资产
					data['debt_to_asset'] = total_liab / total_assets if total_liab is not None and total_assets and total_assets > 0 else None
					# 流动比率 = 流动资产 / 流动负债
					data['current_ratio'] = cur_assets / cur_liab if cur_assets is not None and cur_liab and cur_liab > 0 else None
					# 速动比率 = (流动资产 - 存货) / 流动负债
					data['quick_ratio'] = (cur_assets - inventories) / cur_liab if cur_assets is not None and inventories is not None and cur_liab and cur_liab > 0 else None
					# BPS = 净资产 / 总股本
					data['bps'] = equity / total_share if equity and total_share and total_share > 0 else None
					# float_shares = 总股本（作为流通股本近似值）
					data['float_shares'] = float(total_share) if total_share else None
				except Exception as _calc_e:
					logger.debug(f"计算 {ts_code} 财务指标失败 (date={date_key}): {_calc_e}")
					data['roe'] = data.get('roe')
					data['roa'] = data.get('roa')
					data['debt_to_asset'] = data.get('debt_to_asset')
					data['current_ratio'] = data.get('current_ratio')
					data['quick_ratio'] = data.get('quick_ratio')
					data['bps'] = data.get('bps')
					data['float_shares'] = data.get('float_shares')

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

	async def _get_benchmark_returns(
		self,
		start_date: date,
		end_date: date,
		benchmark: str = "000300.SH",
	) -> pd.Series:
		"""
		获取基准指数的日收益率序列（用于 BETA 等计算）。

		Args:
			start_date: 开始日期
			end_date: 结束日期
			benchmark: 基准指数代码，默认沪深 300

		Returns:
			pd.Series: 指数日收益率，index=trade_date
		"""
		try:
			from sqlalchemy import select as _sel_idx
			from shared.database.models.data_models import IndexDaily
			start_dt = datetime.combine(start_date, datetime.min.time())
			end_dt = datetime.combine(end_date, datetime.min.time())
			stmt = (
				_sel_idx(IndexDaily)
				.where(
					IndexDaily.ts_code == benchmark,
					IndexDaily.trade_date >= start_dt,
					IndexDaily.trade_date <= end_dt,
				)
				.order_by(IndexDaily.trade_date)
			)
			result = await self.session.execute(stmt)
			records = result.scalars().all()
			if not records:
				logger.warning(
					"无法获取基准指数 %s 的日线数据（%s ~ %s），"
					"BETA 等因子将无法计算",
					benchmark, start_date, end_date
				)
				return pd.Series(dtype=float)

			df = pd.DataFrame([
				{"trade_date": r.trade_date, "close": float(r.close)}
				for r in records if r.close is not None
			])
			if df.empty:
				return pd.Series(dtype=float)

			df.set_index("trade_date", inplace=True)
			df.sort_index(inplace=True)
			returns = df["close"].pct_change().dropna()
			return returns
		except Exception as e:
			logger.warning(f"获取基准指数收益失败: {e}")
			return pd.Series(dtype=float)

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
		research_id = getattr(self, '_caller_research_id', None) \
			or f"research_{datetime.now().strftime('%Y%m%d_%H%M%S')}"

		factor_name = factor_definition.get("name", "unknown")
		task_data = {
			"research_id": research_id,
			"research_name": f"因子研究_{factor_name}",
			"factor_name": factor_name,
			"factor_definition": factor_definition,
			"universe": universe,
			"start_date": start_date,
			"end_date": end_date,
			"parameters": parameters or {},
			"status": ResearchStatus.RUNNING,
			"user_id": user_id,
			"created_at": datetime.now()
		}

		# handler 已创建记录则 update，否则 create
		existing = await self.research_repo.get_by_research_id(research_id)
		if existing.success and existing.data:
			await self.research_repo.update(existing.data.id, task_data)
		else:
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
			update_data["error_message"] = error

		await self.research_repo.update(task.id, update_data)

	async def _resolve_universe(self, universe: Optional[List[str]]) -> Optional[List[str]]:
		"""将指数代码解析为成分股列表；无法解析时抛出异常"""
		if not universe:
			return None
		from shared.database.repositories.market.basic.index_repo import IndexRepository
		idx_repo = IndexRepository(self.session)
		resolved = []
		for code in universe:
			if code.lower() == "all":
				return None  # trigger full-market fetch
			# 步骤1: 判断是否为指数代码
			is_index = False
			try:
				idx_basic = await idx_repo.get_index_basic(code)
				is_index = idx_basic is not None
			except Exception:
				pass  # 查询失败 → 当作普通股票

			if is_index:
				# 步骤2: 是指数 → 必须能查到成分股
				try:
					constituents = await idx_repo.get_latest_index_constituents(code)
					if constituents:
						stock_codes = [c.ts_code for c in constituents]
						resolved.extend(stock_codes)
						logger.info("解析指数 %s -> %d 只成分股", code, len(stock_codes))
						continue
				except Exception as e:
					logger.warning("查询指数成分股异常 %s: %s", code, e)
				# 是指数但查不到成分股 → 报错
				raise BusinessException(
					f"指数 {code} 缺少成分股数据，请先同步「指数成分股权重」"
				)
			# 步骤2.5: 判断是否为 ETF → 解析跟踪指数
			if not is_index:
				try:
					from shared.database.models.data_models import EtfBasic
					stmt = select(EtfBasic).where(EtfBasic.ts_code == code)
					etf_result = await self.session.execute(stmt)
					etf = etf_result.scalar_one_or_none()
					if etf:
						# ETF → 从 benchmark 字段提取跟踪指数代码
						benchmark = (etf.benchmark or "").upper()
						# 常见 ETF benchmark → 指数代码映射
						_ETF_INDEX_MAP = {
							"沪深300": "000300.SH", "沪深 300": "000300.SH", "CSI300": "000300.SH",
							"上证50": "000016.SH", "上证 50": "000016.SH", "SSE50": "000016.SH",
							"中证500": "000905.SH", "中证 500": "000905.SH", "CSI500": "000905.SH",
							"创业板": "399006.SZ", "创业板指": "399006.SZ",
							"科创50": "000688.SH", "科创 50": "000688.SH",
						}
						tracking_index = None
						for kw, idx_code in _ETF_INDEX_MAP.items():
							if kw in benchmark:
								tracking_index = idx_code
								break
						if tracking_index:
							constituents = await idx_repo.get_latest_index_constituents(tracking_index)
							if constituents:
								stock_codes = [c.ts_code for c in constituents]
								resolved.extend(stock_codes)
								logger.info("解析 ETF %s -> 指数 %s -> %d 只成分股", code, tracking_index, len(stock_codes))
								continue
						raise BusinessException(
							f"ETF {code} ({etf.name}) 无法解析成分股，请直接选择跟踪指数"
						)
				except BusinessException:
					raise
				except Exception:
					pass  # 不是 ETF → 当普通股票
			# 步骤3: 不是指数 → 当作普通股票代码
			resolved.append(code)
		return resolved if resolved else None

	async def _execute_factor_research (
			self,
			factor_definition: Dict[str, Any],
			universe: Optional[List[str]] = None,
			start_date: Optional[date] = None,
			end_date: Optional[date] = None,
			parameters: Optional[Dict[str, Any]] = None,
			research_id: str = None,
			user_id: Optional[str] = None,
			cancel_token = None,        # asyncio.Event or None
			progress_callback = None,   # callable(step_name, progress_float) or None
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
			cancel_token: asyncio.Event 取消令牌
			progress_callback: 进度回调 callable(step, progress_0_1)

		Returns:
			Dict: 研究结果
		"""
		factor_name = factor_definition.get("name")

		# 解析 universe：指数代码 → 成分股列表
		try:
			resolved_universe = await self._resolve_universe(universe)
		except BusinessException as e:
			return {"success": False, "error": str(e), "message": str(e)}

		# 计算因子数据
		calculation_result = await self.calculate_factor(
			factor_name=factor_name,
			ts_codes=resolved_universe,
			start_date=start_date,
			end_date=end_date,
			parameters=parameters,
			user_id=user_id,
			cancel_token=cancel_token,
			progress_callback=progress_callback,
		)

		# v3.2: 横截面标准化 — 计算 z_score / percentile / rank
		if calculation_result.get("calculated_count", 0) > 0:
			try:
				if progress_callback:
					await progress_callback("横截面标准化(z_score/percentile/rank)", 0.35)
				cs_result = await self._compute_cross_sectional_stats(
					factor_name=factor_name,
					factor_data_items=calculation_result.get("factor_data", []),
				)
				calculation_result["cross_sectional_stats"] = cs_result
			except Exception as _cs_e:
				logger.warning(f"横截面标准化失败（非致命）: {_cs_e}")

		# 分析因子表现
		analysis_results = {}

		# IC分析
		ic_analysis = await self.analyze_factor_performance(
			factor_name=factor_name,
			universe=resolved_universe,
			start_date=start_date,
			end_date=end_date,
			analysis_type="ic_analysis",
			parameters=parameters,
			user_id=user_id
		)

		if ic_analysis.get("success"):
			analysis_results["ic_analysis"] = ic_analysis.get("analysis_result", {})

		if progress_callback:
			await progress_callback("分组分析", 0.5)
		if cancel_token and cancel_token.is_set():
			return {"cancelled": True, "analysis_results": analysis_results}

		# 分位数分析
		quantile_analysis = await self.analyze_factor_performance(
			factor_name=factor_name,
			universe=resolved_universe,
			start_date=start_date,
			end_date=end_date,
			analysis_type="quantile_analysis",
			parameters=parameters,
			user_id=user_id
		)

		if quantile_analysis.get("success"):
			analysis_results["quantile_analysis"] = quantile_analysis.get("analysis_result", {})

		if progress_callback:
			await progress_callback("稳定性分析", 0.7)
		if cancel_token and cancel_token.is_set():
			return {"cancelled": True, "analysis_results": analysis_results}

		# 稳定性分析
		stability_analysis = await self.analyze_factor_performance(
			factor_name=factor_name,
			universe=resolved_universe,
			start_date=start_date,
			end_date=end_date,
			analysis_type="stability_analysis",
			parameters=parameters,
			user_id=user_id
		)

		if stability_analysis.get("success"):
			analysis_results["stability_analysis"] = stability_analysis.get("analysis_result", {})

		if progress_callback:
			await progress_callback("生成报告", 0.9)

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
		task_result = await self.research_repo.get_by_research_id(research_id)
		if not task_result.success or not task_result.data:
			logger.warning("save_result: task %s not found", research_id)
			return

		# numpy -> Python native (JSONB compatible)
		import numpy as np
		def _to_json(v):
			if isinstance(v, dict):
				return {k: _to_json(v2) for k, v2 in v.items()}
			if isinstance(v, (list, tuple)):
				return [_to_json(v2) for v2 in v]
			if isinstance(v, (np.integer,)):
				return int(v)
			if isinstance(v, (np.floating,)):
				fv = float(v)
				return None if np.isnan(fv) or np.isinf(fv) else fv
			if isinstance(v, np.ndarray):
				return _to_json(v.tolist())
			if isinstance(v, float) and (np.isnan(v) or np.isinf(v)):
				return None
			return v

		update_data = {
			"status": ResearchStatus.COMPLETED,
			"completed_at": datetime.now(),
			"result": _to_json(result),
		}
		await self.research_repo.update(task_result.data.id, update_data)

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
			try: await self.cache.delete_pattern(pattern)
			except Exception: pass  # Redis 不可用时跳过

	async def _clean_factor_metadata_cache (self):
		"""清理因子元数据缓存"""
		patterns = [
			CacheKey.FACTOR_METADATA.format(factor="*")
		]

		for pattern in patterns:
			try: await self.cache.delete_pattern(pattern)
			except Exception: pass  # Redis 不可用时跳过

	# ==================== 标准因子元数据 ====================
	@staticmethod
	def _get_standard_factor_metadata (
			factor_name: Optional[str] = None,
			category: Optional[str] = None
	) -> List[Dict[str, Any]]:
		"""
		获取标准因子元数据，委托因子计算器注册表查询。

		本方法是 get_factor_metadata() 的兜底路径（fallback）。
		优先从数据库 factor_definitions 表查询因子元数据；仅当
		数据库中无对应记录时，才使用因子计算器注册表中的硬编码标准定义。

		Args:
			factor_name: 因子名称（如 "pe"），None 时不按名称过滤
			category: 因子类别（如 FactorCategoryCode.VALUE），None 时不按类别过滤

		Returns:
			List[Dict[str, Any]]: 符合条件的标准因子元数据列表
		"""
		return get_metadata_list(factor_name=factor_name, category=category)

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
			stocks = await self.stock_repo.get_all(limit=500)  # 限制获取100只股票
			if not stocks:
				logger.warning("获取股票列表失败")
				return []

			stock_codes = [stock.ts_code for stock in stocks]

			# v3.2: 批量查询（修复 N+1），一次 SQL 替代嵌套循环
			try:
				from sqlalchemy import select as _sel_fd
				from shared.database.models.data_models import FactorData as _FD

				conditions = [
					_FD.factor_name.in_(factor_names),
					_FD.ts_code.in_(stock_codes),
				]
				if start_date_obj:
					conditions.append(_FD.trade_date >= start_date_obj)
				if end_date_obj:
					conditions.append(_FD.trade_date <= end_date_obj)

				stmt = _sel_fd(_FD).where(*conditions)
				result = await self.session.execute(stmt)
				rows = result.scalars().all()

				for row in rows:
					factor_data.append({
						'symbol': row.ts_code,
						'factor_name': getattr(row, 'factor_name', ''),
						'factor_value': row.factor_value,
						'date': row.trade_date.isoformat() if row.trade_date else '',
					})
			except Exception as _fd_e:
				logger.error(f"批量获取因子数据失败: {_fd_e}")
				return []

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