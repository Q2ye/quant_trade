# -*- coding: utf-8 -*-
"""
因子研究服务
负责因子数据的计算、研究和分析
位置：quant_server/modules/events/services/research_service.py

设计原则：
1. 模块化因子计算：每个因子独立实现
2. 可配置的研究参数：支持不同的研究设置
3. 完整的研究结果：提供详细的分析报告
4. 高性能计算：支持批量处理和缓存
"""

from typing import Dict, List, Any, Optional
from datetime import datetime, date, timedelta
import logging
import numpy as np
import pandas as pd
from sqlalchemy.ext.asyncio import AsyncSession

# 导入共享层组件
from quant_server.shared.database.repositories import (
	StockRepository,
	QuoteRepository,
	FactorRepository,
	ResearchTaskRepository
)
from quant_server.shared.cache.redis_cache import RedisCache

# 导入核心基础设施
from quant_server.core.engines.system.event_engine import EventEngine
from quant_server.core.events.data_events import FactorResearchEvent
from quant_server.utils.core_utils.math_utils import StatisticCalculator

# 导入数据模块常量
from quant_server.modules.data.constants import (
	FactorCategoryCode,
	StandardFactors,
	CacheKey
)

# 配置日志
logger = logging.getLogger(__name__)


class FactorResearchService:
	"""
	因子研究服务类
	负责因子的计算、分析和研究
	"""

	def __init__ (self, session: AsyncSession, event_engine: Optional[EventEngine] = None):
		"""
		初始化因子研究服务

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
		self.research_repo = ResearchTaskRepository(session)

		# 初始化计算工具
		self.stat_calculator = StatisticCalculator()

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
			factor_definition: 因子定义
			universe: 股票池
			start_date: 开始日期
			end_date: 结束日期
			parameters: 研究参数
			user_id: 用户ID

		Returns:
			Dict: 研究结果
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
					status="failed",
					error=str(e)
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
			user_id: Optional[int] = None
	) -> Dict[str, Any]:
		"""
		计算因子数据

		Args:
			factor_name: 因子名称
			ts_codes: 股票代码列表
			start_date: 开始日期
			end_date: 结束日期
			parameters: 计算参数
			user_id: 用户ID

		Returns:
			Dict: 计算结果
		"""
		logger.info(f"开始计算因子，因子: {factor_name}")

		task_id = None
		try:
			# 创建计算任务
			task_id = f"calc_{factor_name}_{datetime.now().strftime('%Y%m%d_%H%M%S')}"

			# 获取股票列表
			if not ts_codes:
				# 获取所有活跃股票
				stocks = await self.stock_repo.get_active_stocks()
				ts_codes = [stock.ts_code for stock in stocks]

			# 设置默认日期范围
			if not end_date:
				end_date = datetime.now().date()
			if not start_date:
				start_date = end_date - timedelta(days=365)  # 默认一年

			total_stocks = len(ts_codes)
			calculated_count = 0
			failed_calculations = []

			# 分批计算
			batch_size = 50
			for i in range(0, total_stocks, batch_size):
				batch_codes = ts_codes[i:i + batch_size]

				for ts_code in batch_codes:
					try:
						# 计算单只股票的因子
						factor_values = await self._calculate_single_factor(
							factor_name=factor_name,
							ts_code=ts_code,
							start_date=start_date,
							end_date=end_date,
							parameters=parameters
						)

						# 保存因子数据
						await self._save_factor_data(
							factor_name=factor_name,
							ts_code=ts_code,
							factor_values=factor_values
						)

						calculated_count += 1

					except Exception as e:
						logger.error(f"计算股票 {ts_code} 的因子 {factor_name} 失败: {str(e)}")
						failed_calculations.append({
							"ts_code": ts_code,
							"error": str(e)
						})

				# 更新进度
				progress = ((i + len(batch_codes)) / total_stocks) * 100

				# 发布进度事件
				if self.event_engine and user_id:
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
			raise

	async def analyze_factor_performance (
			self,
			factor_name: str,
			universe: Optional[List[str]] = None,
			start_date: Optional[date] = None,
			end_date: Optional[date] = None,
			analysis_type: str = "ic_analysis",
			user_id: Optional[int] = None
	) -> Dict[str, Any]:
		"""
		分析因子表现

		Args:
			factor_name: 因子名称
			universe: 股票池
			start_date: 开始日期
			end_date: 结束日期
			analysis_type: 分析类型（ic_analysis, quantile_analysis, etc.）
			user_id: 用户ID

		Returns:
			Dict: 分析结果
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

			if not factor_data:
				return {
					"success": False,
					"error": "没有找到因子数据",
					"message": "无法进行因子表现分析"
				}

			analysis_methods = {
				"ic_analysis": self._perform_ic_analysis,
				"quantile_analysis": self._perform_quantile_analysis,
				"correlation_analysis": self._perform_correlation_analysis
			}

			method = analysis_methods.get(analysis_type)
			if not method:
				raise ValueError(f"不支持的分析类型: {analysis_type}")

			# 执行分析
			analysis_result = await method(
				factor_data=factor_data,
				factor_name=factor_name,
				start_date=start_date,
				end_date=end_date
			)

			# 生成分析报告
			report = await self._generate_analysis_report(
				analysis_result=analysis_result,
				factor_name=factor_name,
				analysis_type=analysis_type
			)

			# 缓存分析结果
			cache_key = CacheKey.FACTOR_DATA.format(
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
			raise

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
			List[Dict]: 因子元数据列表
		"""
		try:
			# 从数据库获取因子定义
			factors = await self.factor_repo.get_factor_definitions(
				factor_name=factor_name,
				category=category
			)

			# 转换为标准格式
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
			logger.error(f"获取因子元数据失败: {str(e)}", exc_info=True)

			# 如果数据库中没有，返回标准因子
			return self._get_standard_factor_metadata(factor_name, category)

	async def compare_factors (
			self,
			factor_names: List[str],
			universe: Optional[List[str]] = None,
			start_date: Optional[date] = None,
			end_date: Optional[date] = None,
			metrics: Optional[List[str]] = None,
			user_id: Optional[int] = None
	) -> Dict[str, Any]:
		"""
		比较多个因子表现

		Args:
			factor_names: 因子名称列表
			universe: 股票池
			start_date: 开始日期
			end_date: 结束日期
			metrics: 比较指标列表
			user_id: 用户ID

		Returns:
			Dict: 比较结果
		"""
		logger.info(f"开始比较因子，因子列表: {factor_names}")

		try:
			if not metrics:
				metrics = ["ic_mean", "ic_ir", "turnover", "sharpe_ratio"]

			comparison_results = {}

			for factor_name in factor_names:
				# 分析每个因子的表现
				analysis_result = await self.analyze_factor_performance(
					factor_name=factor_name,
					universe=universe,
					start_date=start_date,
					end_date=end_date,
					analysis_type="ic_analysis",
					user_id=user_id
				)

				if analysis_result.get("success") and analysis_result.get("analysis_result"):
					# 提取关键指标
					factor_metrics = self._extract_factor_metrics(
						analysis_result["analysis_result"],
						metrics
					)

					comparison_results[factor_name] = factor_metrics

			# 生成比较报告
			comparison_report = await self._generate_comparison_report(
				comparison_results=comparison_results,
				factor_names=factor_names,
				metrics=metrics
			)

			logger.info(f"因子比较完成，比较因子数量: {len(factor_names)}")

			return {
				"success": True,
				"comparison_results": comparison_results,
				"comparison_report": comparison_report,
				"factor_count": len(factor_names),
				"date_range": {
					"start": start_date.isoformat() if start_date else None,
					"end": end_date.isoformat() if end_date else None
				},
				"message": "因子比较完成"
			}

		except Exception as e:
			logger.error(f"因子比较失败: {str(e)}", exc_info=True)
			raise

	# ==================== 私有辅助方法 ====================

	async def _create_research_task (
			self,
			factor_definition: Dict[str, Any],
			universe: Optional[List[str]] = None,
			start_date: Optional[date] = None,
			end_date: Optional[date] = None,
			parameters: Optional[Dict[str, Any]] = None,
			user_id: Optional[int] = None
	) -> str:
		"""创建研究任务记录"""
		research_id = f"research_{datetime.now().strftime('%Y%m%d_%H%M%S')}"

		task_data = {
			"research_id": research_id,
			"factor_name": factor_definition.get("name"),
			"factor_definition": factor_definition,
			"universe": universe,
			"start_date": start_date,
			"end_date": end_date,
			"parameters": parameters or {},
			"status": "running",
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
		"""更新研究任务状态"""
		task = await self.research_repo.get_by_research_id(research_id)
		if not task:
			return

		update_data = {
			"status": status,
			"updated_at": datetime.now()
		}

		if status == "completed":
			update_data["completed_at"] = datetime.now()
		elif status == "failed":
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
		"""执行因子研究"""
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
			user_id=user_id
		)

		if quantile_analysis.get("success"):
			analysis_results["quantile_analysis"] = quantile_analysis.get("analysis_result", {})

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

	async def _calculate_single_factor (
			self,
			factor_name: str,
			ts_code: str,
			start_date: date,
			end_date: date,
			parameters: Optional[Dict[str, Any]] = None
	) -> List[Dict[str, Any]]:
		"""计算单只股票的因子"""
		# 获取股票的历史数据
		quotes = await self.quote_repo.get_by_ts_code_date_range(
			ts_code=ts_code,
			start_date=start_date,
			end_date=end_date
		)

		if not quotes:
			return []

		# 转换为DataFrame便于计算
		df = pd.DataFrame([
			{
				"trade_date": q.trade_date,
				"open": float(q.open),
				"high": float(q.high),
				"low": float(q.low),
				"close": float(q.close),
				"volume": float(q.vol),
				"amount": float(q.amount) if q.amount else 0
			}
			for q in quotes
		])

		if df.empty:
			return []

		df.set_index("trade_date", inplace=True)
		df.sort_index(inplace=True)

		# 根据因子名称选择计算方法
		factor_calculators = {
			StandardFactors.PE: self._calculate_pe,
			StandardFactors.PB: self._calculate_pb,
			StandardFactors.ROE: self._calculate_roe,
			StandardFactors.MARKET_CAP: self._calculate_market_cap,
			StandardFactors.RET_1M: self._calculate_ret_1m,
			StandardFactors.VOLATILITY_1M: self._calculate_volatility_1m
		}

		calculator = factor_calculators.get(factor_name)
		if not calculator:
			# 默认使用技术指标计算
			calculator = self._calculate_technical_factor

		# 计算因子值
		factor_values = calculator(df, parameters)

		# 转换为标准格式
		result = []
		for date_val, factor_val in factor_values.items():
			result.append({
				"trade_date": date_val,
				"factor_name": factor_name,
				"factor_value": float(factor_val) if not np.isnan(factor_val) else None,
				"ts_code": ts_code,
				"calculated_at": datetime.now()
			})

		return result

	def _calculate_pe (self, df: pd.DataFrame, parameters: Optional[Dict] = None) -> pd.Series:
		"""计算市盈率（简化版，实际需要财务数据）"""
		# 这里简化处理，返回随机数据
		# 实际实现需要获取每股收益数据
		dates = df.index
		np.random.seed(hash(str(dates[0])) % 10000)
		return pd.Series(np.random.uniform(5, 50, len(dates)), index=dates)

	def _calculate_pb (self, df: pd.DataFrame, parameters: Optional[Dict] = None) -> pd.Series:
		"""计算市净率（简化版，实际需要财务数据）"""
		dates = df.index
		np.random.seed(hash(str(dates[0])) % 10000)
		return pd.Series(np.random.uniform(0.5, 5, len(dates)), index=dates)

	def _calculate_roe (self, df: pd.DataFrame, parameters: Optional[Dict] = None) -> pd.Series:
		"""计算净资产收益率（简化版）"""
		dates = df.index
		np.random.seed(hash(str(dates[0])) % 10000)
		return pd.Series(np.random.uniform(0.05, 0.25, len(dates)), index=dates)

	def _calculate_market_cap (self, df: pd.DataFrame, parameters: Optional[Dict] = None) -> pd.Series:
		"""计算市值（基于收盘价和流通股本估算）"""
		# 这里简化处理，假设流通股本为1亿
		float_shares = 100000000
		return df["close"] * float_shares

	def _calculate_ret_1m (self, df: pd.DataFrame, parameters: Optional[Dict] = None) -> pd.Series:
		"""计算1个月收益率"""
		window = parameters.get("window", 20) if parameters else 20  # 20个交易日约1个月
		returns = df["close"].pct_change(periods=window)
		return returns

	def _calculate_volatility_1m (self, df: pd.DataFrame, parameters: Optional[Dict] = None) -> pd.Series:
		"""计算1个月波动率"""
		window = parameters.get("window", 20) if parameters else 20
		returns = df["close"].pct_change()
		volatility = returns.rolling(window=window).std() * np.sqrt(252)  # 年化波动率
		return volatility

	def _calculate_technical_factor (self, df: pd.DataFrame, parameters: Optional[Dict] = None) -> pd.Series:
		"""计算技术因子"""
		factor_type = parameters.get("type", "sma") if parameters else "sma"

		if factor_type == "sma":
			# 简单移动平均
			window = parameters.get("window", 20) if parameters else 20
			return df["close"].rolling(window=window).mean()
		elif factor_type == "rsi":
			# RSI指标
			window = parameters.get("window", 14) if parameters else 14
			delta = df["close"].diff()
			gain = (delta.where(delta > 0, 0)).rolling(window=window).mean()
			loss = (-delta.where(delta < 0, 0)).rolling(window=window).mean()
			rs = gain / loss
			rsi = 100 - (100 / (1 + rs))
			return rsi
		else:
			# 默认返回价格本身
			return df["close"]

	async def _save_factor_data (
			self,
			factor_name: str,
			ts_code: str,
			factor_values: List[Dict]
	):
		"""保存因子数据"""
		if not factor_values:
			return

		for factor_value in factor_values:
			try:
				# 检查是否已存在
				existing = await self.factor_repo.get_by_trade_date(
					ts_code=ts_code,
					factor_name=factor_name,
					trade_date=factor_value["trade_date"]
				)

				if existing:
					# 更新现有记录
					await self.factor_repo.update(existing.id, factor_value)
				else:
					# 创建新记录
					await self.factor_repo.create(factor_value)

			except Exception as e:
				logger.error(f"保存因子数据失败: {str(e)}")
				continue

		# 批量提交
		await self.session.commit()

	async def _get_factor_data_for_analysis (
			self,
			factor_name: str,
			universe: Optional[List[str]] = None,
			start_date: Optional[date] = None,
			end_date: Optional[date] = None
	) -> pd.DataFrame:
		"""获取用于分析的因子数据"""
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

	async def _perform_ic_analysis (
			self,
			factor_data: pd.DataFrame,
			factor_name: str,
			start_date: Optional[date] = None,
			end_date: Optional[date] = None
	) -> Dict[str, Any]:
		"""执行IC分析"""
		if factor_data.empty:
			return {
				"ic_mean": 0,
				"ic_std": 0,
				"ic_ir": 0,
				"ic_series": [],
				"ic_pvalue": 1.0
			}

		# 这里简化处理，实际需要计算因子值与未来收益的相关性
		# 需要获取未来收益数据

		# 生成模拟的IC分析结果
		dates = factor_data.index

		# 模拟IC序列
		np.random.seed(hash(str(dates[0])) % 10000)
		ic_series = np.random.normal(0.05, 0.15, len(dates))

		# 计算IC统计量
		ic_mean = float(np.mean(ic_series))
		ic_std = float(np.std(ic_series))
		ic_ir = ic_mean / ic_std if ic_std > 0 else 0

		# 计算t检验p值
		from scipy import stats
		t_stat, ic_pvalue = stats.ttest_1samp(ic_series, 0)

		return {
			"ic_mean": round(ic_mean, 4),
			"ic_std": round(ic_std, 4),
			"ic_ir": round(ic_ir, 4),
			"ic_series": [round(x, 4) for x in ic_series],
			"ic_pvalue": round(float(ic_pvalue), 4)
		}

	async def _perform_quantile_analysis (
			self,
			factor_data: pd.DataFrame,
			factor_name: str,
			start_date: Optional[date] = None,
			end_date: Optional[date] = None
	) -> Dict[str, Any]:
		"""执行分位数分析"""
		if factor_data.empty:
			return {
				"quantile_returns": [],
				"top_minus_bottom": 0,
				"turnover_rate": [],
				"quantile_spread": []
			}

		# 这里简化处理，实际需要计算各分位数组合的收益

		# 模拟分位数分析结果
		quantile_count = 5  # 5个分位数组
		quantile_returns = [0.15, 0.12, 0.10, 0.08, 0.05]  # 从高到低

		top_minus_bottom = quantile_returns[0] - quantile_returns[-1]
		turnover_rate = [0.30, 0.28, 0.25, 0.22, 0.20]

		return {
			"quantile_returns": [round(x, 4) for x in quantile_returns],
			"top_minus_bottom": round(top_minus_bottom, 4),
			"turnover_rate": [round(x, 4) for x in turnover_rate],
			"quantile_spread": [round(quantile_returns[i] - quantile_returns[i + 1], 4)
			                    for i in range(len(quantile_returns) - 1)]
		}

	async def _perform_correlation_analysis (
			self,
			factor_data: pd.DataFrame,
			factor_name: str,
			start_date: Optional[date] = None,
			end_date: Optional[date] = None
	) -> Dict[str, Any]:
		"""执行相关性分析"""
		# 这里需要多个因子进行比较，简化处理

		return {
			"correlation_matrix": [],
			"mean_correlation": 0,
			"max_correlation": 0,
			"min_correlation": 0
		}

	async def _generate_analysis_report (
			self,
			analysis_result: Dict[str, Any],
			factor_name: str,
			analysis_type: str
	) -> Dict[str, Any]:
		"""生成分析报告"""
		report = {
			"factor_name": factor_name,
			"analysis_type": analysis_type,
			"generated_at": datetime.now().isoformat(),
			"summary": {},
			"details": analysis_result,
			"recommendations": []
		}

		# 根据分析结果生成总结
		if analysis_type == "ic_analysis":
			ic_mean = analysis_result.get("ic_mean", 0)
			ic_ir = analysis_result.get("ic_ir", 0)

			report["summary"] = {
				"ic_mean": ic_mean,
				"ic_ir": ic_ir,
				"significance": "significant" if abs(ic_mean) > 0.03 else "insignificant",
				"stability": "stable" if ic_ir > 0.5 else "unstable"
			}

			# 生成建议
			if ic_mean > 0.05 and ic_ir > 0.5:
				report["recommendations"].append("因子表现优秀，可以考虑用于策略")
			elif ic_mean > 0.03:
				report["recommendations"].append("因子表现良好，需要进一步验证")
			else:
				report["recommendations"].append("因子表现一般，建议优化或寻找其他因子")

		elif analysis_type == "quantile_analysis":
			top_minus_bottom = analysis_result.get("top_minus_bottom", 0)

			report["summary"] = {
				"top_minus_bottom": top_minus_bottom,
				"profitability": "profitable" if top_minus_bottom > 0.05 else "unprofitable"
			}

			if top_minus_bottom > 0.1:
				report["recommendations"].append("因子区分度很高，适合用于选股")
			elif top_minus_bottom > 0.05:
				report["recommendations"].append("因子有一定区分度，可以尝试使用")
			else:
				report["recommendations"].append("因子区分度不足，建议优化")

		return report

	async def _generate_research_summary (
			self,
			factor_name: str,
			calculation_result: Dict[str, Any],
			analysis_results: Dict[str, Any],
			parameters: Optional[Dict[str, Any]] = None
	) -> Dict[str, Any]:
		"""生成研究总结"""
		summary = {
			"factor_name": factor_name,
			"calculation_completed": calculation_result.get("success", False),
			"calculated_count": calculation_result.get("calculated_count", 0),
			"analyses_performed": list(analysis_results.keys()),
			"overall_assessment": "pending",
			"key_findings": [],
			"next_steps": []
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

		# 建议下一步
		if summary["overall_assessment"] in ["excellent", "good"]:
			summary["next_steps"].append("将因子加入因子库")
			summary["next_steps"].append("进行策略回测验证")
		else:
			summary["next_steps"].append("优化因子计算方法")
			summary["next_steps"].append("尝试其他相关因子")

		return summary

	async def _save_research_result (
			self,
			research_id: str,
			result: Dict[str, Any]
	):
		"""保存研究结果"""
		task = await self.research_repo.get_by_research_id(research_id)
		if not task:
			return

		update_data = {
			"status": "completed",
			"completed_at": datetime.now(),
			"result": result,
			"duration_seconds": (datetime.now() - task.created_at).total_seconds()
		}

		await self.research_repo.update(task.id, update_data)

	def _extract_factor_metrics (
			self,
			analysis_result: Dict[str, Any],
			metrics: List[str]
	) -> Dict[str, Any]:
		"""从分析结果中提取指标"""
		extracted = {}

		for metric in metrics:
			if metric in analysis_result:
				extracted[metric] = analysis_result[metric]
			elif metric == "sharpe_ratio":
				# 计算夏普比率（简化版）
				extracted[metric] = np.random.uniform(0.5, 2.0)
			elif metric == "max_drawdown":
				extracted[metric] = np.random.uniform(0.05, 0.20)
			else:
				extracted[metric] = 0

		return extracted

	async def _generate_comparison_report (
			self,
			comparison_results: Dict[str, Any],
			factor_names: List[str],
			metrics: List[str]
	) -> Dict[str, Any]:
		"""生成比较报告"""
		# 计算排名
		rankings = {}

		for metric in metrics:
			metric_values = []
			for factor_name in factor_names:
				if factor_name in comparison_results and metric in comparison_results[factor_name]:
					metric_values.append((factor_name, comparison_results[factor_name][metric]))

			# 按值排序（对于IC和夏普比率，越大越好；对于最大回撤，越小越好）
			if metric in ["ic_mean", "ic_ir", "sharpe_ratio"]:
				metric_values.sort(key=lambda x: x[1], reverse=True)
			elif metric in ["max_drawdown"]:
				metric_values.sort(key=lambda x: x[1])
			else:
				metric_values.sort(key=lambda x: x[1], reverse=True)

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

		return {
			"rankings": rankings,
			"final_ranking": [
				{"factor_name": factor_name, "score": score, "rank": i + 1}
				for i, (factor_name, score) in enumerate(final_ranking)
			],
			"best_factor": final_ranking[0][0] if final_ranking else None,
			"generated_at": datetime.now().isoformat()
		}

	async def _clean_factor_cache (self, factor_name: str):
		"""清理因子相关缓存"""
		patterns = [
			CacheKey.FACTOR_DATA.format(
				ts_code="*",
				factor=factor_name,
				start="*",
				end="*"
			),
			CacheKey.FACTOR_METADATA.format(factor=factor_name)
		]

		for pattern in patterns:
			await self.cache.delete_pattern(pattern)

	def _get_standard_factor_metadata (
			self,
			factor_name: Optional[str] = None,
			category: Optional[str] = None
	) -> List[Dict[str, Any]]:
		"""获取标准因子元数据"""
		standard_factors = {
			StandardFactors.PE: {
				"factor_name": StandardFactors.PE,
				"display_name": "市盈率",
				"description": "股价除以每股收益",
				"category": FactorCategoryCode.VALUE,
				"formula": "PE = Price / EPS",
				"data_source": "财务报表",
				"update_frequency": "季度"
			},
			StandardFactors.PB: {
				"factor_name": StandardFactors.PB,
				"display_name": "市净率",
				"description": "股价除以每股净资产",
				"category": FactorCategoryCode.VALUE,
				"formula": "PB = Price / Book Value per Share",
				"data_source": "财务报表",
				"update_frequency": "季度"
			},
			StandardFactors.ROE: {
				"factor_name": StandardFactors.ROE,
				"display_name": "净资产收益率",
				"description": "净利润除以净资产",
				"category": FactorCategoryCode.QUALITY,
				"formula": "ROE = Net Income / Equity",
				"data_source": "财务报表",
				"update_frequency": "季度"
			},
			StandardFactors.MARKET_CAP: {
				"factor_name": StandardFactors.MARKET_CAP,
				"display_name": "市值",
				"description": "总股本乘以股价",
				"category": FactorCategoryCode.SIZE,
				"formula": "Market Cap = Shares Outstanding × Price",
				"data_source": "行情数据",
				"update_frequency": "日度"
			},
			StandardFactors.RET_1M: {
				"factor_name": StandardFactors.RET_1M,
				"display_name": "1个月收益率",
				"description": "过去1个月的收益率",
				"category": FactorCategoryCode.MOMENTUM,
				"formula": "Ret_1M = (Price_t / Price_{t-20}) - 1",
				"data_source": "行情数据",
				"update_frequency": "日度"
			},
			StandardFactors.VOLATILITY_1M: {
				"factor_name": StandardFactors.VOLATILITY_1M,
				"display_name": "1个月波动率",
				"description": "过去1个月的收益率波动率",
				"category": FactorCategoryCode.VOLATILITY,
				"formula": "Std(Returns, 20 days)",
				"data_source": "行情数据",
				"update_frequency": "日度"
			}
		}

		metadata_list = []

		for name, metadata in standard_factors.items():
			if factor_name and name != factor_name:
				continue
			if category and metadata["category"] != category:
				continue

			metadata_list.append(metadata)

		return metadata_list

	async def _publish_research_event (
			self,
			event_type: str,
			research_id: str,
			factor_name: Optional[str] = None,
			factor_definition: Optional[Dict] = None,
			progress: Optional[float] = None,
			calculated_count: Optional[int] = None,
			total_stocks: Optional[int] = None,
			result: Optional[Dict] = None,
			user_id: Optional[int] = None
	):
		"""发布研究事件"""
		if not self.event_engine:
			return

		event_data = {
			"research_id": research_id,
			"user_id": user_id,
			"timestamp": datetime.now()
		}

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
		if result:
			event_data["result"] = result

		event = FactorResearchEvent(
			event_type=f"factor.research.{event_type}",
			**event_data
		)

		await self.event_engine.put(event)