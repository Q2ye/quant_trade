# -*- coding: utf-8 -*-
"""
市场数据服务
负责提供市场数据的查询、分析和处理功能
位置：quant_server/modules/events/services/market_service.py

设计原则：
1. 统一数据访问接口：为上层提供一致的数据查询接口
2. 智能缓存策略：根据数据类型和访问频率自动缓存
3. 高性能查询：支持批量查询和高效的数据处理
4. 数据转换：提供多种数据格式和频率的转换
"""

from typing import Dict, List, Any, Optional
from datetime import datetime, date, timedelta
import logging
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import or_, desc

# 导入共享层组件
from quant_server.shared.database.repositories import (
	StockRepository,
	QuoteRepository,
	TradeCalendarRepository,
	FactorRepository
)
from quant_server.shared.cache.redis_cache import RedisCache

# 导入核心基础设施
from quant_server.core.engines.system.event_engine import EventEngine
from quant_server.core.events.data_events import MarketDataRequestEvent
from quant_server.utils.core_utils.time_utils.trading_calendar import TradingCalendar
from quant_server.utils.core_utils.data_utils.data_transformer import DataTransformer

# 导入数据模块常量
from quant_server.modules.data.constants import (
	CacheKey
)

# 配置日志
logger = logging.getLogger(__name__)


class MarketDataService:
	"""
	市场数据服务类
	提供市场数据的查询、分析和处理功能
	"""

	def __init__ (self, session: AsyncSession, event_engine: Optional[EventEngine] = None):
		"""
		初始化市场数据服务

		Args:
			session: 数据库会话
			event_engine: 事件引擎
		"""
		self.session = session
		self.event_engine = event_engine

		# 初始化Repository
		self.stock_repo = StockRepository(session)
		self.quote_repo = QuoteRepository(session)
		self.calendar_repo = TradeCalendarRepository(session)
		self.factor_repo = FactorRepository(session)

		# 初始化工具
		self.trading_calendar = TradingCalendar()
		self.data_transformer = DataTransformer()

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

	async def get_historical_quotes (
			self,
			ts_code: str,
			start_date: Optional[date] = None,
			end_date: Optional[date] = None,
			freq: str = "D",
			adj: str = "qfq",
			fields: Optional[List[str]] = None,
			use_cache: bool = True,
			user_id: Optional[int] = None
	) -> List[Dict[str, Any]]:
		"""
		获取历史行情数据

		Args:
			ts_code: 股票代码
			start_date: 开始日期
			end_date: 结束日期
			freq: 频率（D:日线, W:周线, M:月线）
			adj: 复权类型（qfq:前复权, hfq:后复权, None:不复权）
			fields: 返回字段列表
			use_cache: 是否使用缓存
			user_id: 用户ID（用于事件发布）

		Returns:
			List[Dict]: 行情数据列表
		"""
		logger.info(f"获取历史行情，股票: {ts_code}, 频率: {freq}, 复权: {adj}")

		try:
			# 生成缓存键
			cache_key = None
			if use_cache:
				cache_key = CacheKey.generate_historical_quotes_key(
					ts_code=ts_code,
					start_date=start_date.strftime("%Y%m%d") if start_date else "all",
					end_date=end_date.strftime("%Y%m%d") if end_date else "all",
					frequency=freq,
					adjust=adj
				)

				# 尝试从缓存获取
				cached_data = await self.cache.get(cache_key)
				if cached_data:
					logger.info(f"从缓存获取历史行情数据，股票: {ts_code}")

					# 发布数据访问事件
					await self._publish_market_data_event(
						event_type="cached_request",
						ts_code=ts_code,
						data_type="historical_quotes",
						cached=True,
						user_id=user_id
					)

					return cached_data

			# 设置默认日期范围
			if not end_date:
				end_date = datetime.now().date()
			if not start_date:
				if freq == "D":
					start_date = end_date - timedelta(days=365)  # 默认一年
				elif freq == "W":
					start_date = end_date - timedelta(weeks=52)  # 默认一年
				elif freq == "M":
					start_date = end_date - timedelta(days=365)  # 默认一年

			# 获取基础行情数据
			quotes = await self.quote_repo.get_by_ts_code_date_range(
				ts_code=ts_code,
				start_date=start_date,
				end_date=end_date,
				order_by=desc(self.quote_repo.model.trade_date)
			)

			if not quotes:
				logger.warning(f"未找到行情数据，股票: {ts_code}")
				return []

			# 转换为目标频率
			if freq != "D":
				quotes = await self._convert_frequency(quotes, freq)

			# 处理复权
			if adj in ["qfq", "hfq"]:
				quotes = await self._adjust_prices(quotes, adj)

			# 选择返回字段
			if fields:
				quotes = self._select_fields(quotes, fields)

			# 转换为响应格式
			result = []
			for quote in quotes:
				quote_dict = {
					"trade_date": quote.trade_date.isoformat() if hasattr(quote.trade_date, 'isoformat') else str(
						quote.trade_date),
					"ts_code": ts_code,
					"open": float(quote.open) if quote.open else None,
					"high": float(quote.high) if quote.high else None,
					"low": float(quote.low) if quote.low else None,
					"close": float(quote.close) if quote.close else None,
					"pre_close": float(quote.pre_close) if hasattr(quote, 'pre_close') and quote.pre_close else None,
					"change": float(quote.change) if hasattr(quote, 'change') and quote.change else None,
					"pct_chg": float(quote.pct_chg) if hasattr(quote, 'pct_chg') and quote.pct_chg else None,
					"vol": float(quote.vol) if quote.vol else None,
					"amount": float(quote.amount) if hasattr(quote, 'amount') and quote.amount else None
				}

				# 添加复权因子（如果需要）
				if adj in ["qfq", "hfq"] and hasattr(quote, 'adj_factor'):
					quote_dict["adj_factor"] = float(quote.adj_factor) if quote.adj_factor else None

				result.append(quote_dict)

			# 缓存结果
			if use_cache and cache_key and result:
				await self.cache.set(
					cache_key,
					result,
					ttl=CacheKey.CACHE_TTL.get("historical_quotes", 600)
				)

			# 发布数据访问事件
			await self._publish_market_data_event(
				event_type="data_request",
				ts_code=ts_code,
				data_type="historical_quotes",
				record_count=len(result),
				cached=False,
				user_id=user_id
			)

			logger.info(f"获取历史行情完成，股票: {ts_code}, 记录数: {len(result)}")

			return result

		except Exception as e:
			logger.error(f"获取历史行情失败: {str(e)}", exc_info=True)
			raise

	async def get_latest_quote (
			self,
			ts_code: str,
			use_cache: bool = True,
			user_id: Optional[int] = None
	) -> Optional[Dict[str, Any]]:
		"""
		获取最新行情数据

		Args:
			ts_code: 股票代码
			use_cache: 是否使用缓存
			user_id: 用户ID

		Returns:
			Dict: 最新行情数据，如果不存在则返回None
		"""
		logger.info(f"获取最新行情，股票: {ts_code}")

		try:
			# 生成缓存键
			cache_key = None
			if use_cache:
				cache_key = CacheKey.LATEST_QUOTE.format(ts_code=ts_code)

				# 尝试从缓存获取
				cached_quote = await self.cache.get(cache_key)
				if cached_quote:
					logger.info(f"从缓存获取最新行情，股票: {ts_code}")

					# 发布数据访问事件
					await self._publish_market_data_event(
						event_type="cached_request",
						ts_code=ts_code,
						data_type="latest_quote",
						cached=True,
						user_id=user_id
					)

					return cached_quote

			# 从数据库获取最新行情
			latest_quote = await self.quote_repo.get_latest_by_ts_code(ts_code)

			if not latest_quote:
				logger.warning(f"未找到最新行情，股票: {ts_code}")
				return None

			# 转换为响应格式
			result = {
				"ts_code": ts_code,
				"trade_date": latest_quote.trade_date.isoformat(),
				"open": float(latest_quote.open) if latest_quote.open else None,
				"high": float(latest_quote.high) if latest_quote.high else None,
				"low": float(latest_quote.low) if latest_quote.low else None,
				"close": float(latest_quote.close) if latest_quote.close else None,
				"pre_close": float(latest_quote.pre_close) if latest_quote.pre_close else None,
				"change": float(latest_quote.change) if latest_quote.change else None,
				"pct_chg": float(latest_quote.pct_chg) if latest_quote.pct_chg else None,
				"vol": float(latest_quote.vol) if latest_quote.vol else None,
				"amount": float(latest_quote.amount) if latest_quote.amount else None,
				"updated_at": latest_quote.updated_at.isoformat() if latest_quote.updated_at else None
			}

			# 缓存结果
			if use_cache and cache_key and result:
				await self.cache.set(
					cache_key,
					result,
					ttl=300  # 最新行情缓存5分钟
				)

			# 发布数据访问事件
			await self._publish_market_data_event(
				event_type="data_request",
				ts_code=ts_code,
				data_type="latest_quote",
				cached=False,
				user_id=user_id
			)

			logger.info(f"获取最新行情完成，股票: {ts_code}, 日期: {result['trade_date']}")

			return result

		except Exception as e:
			logger.error(f"获取最新行情失败: {str(e)}", exc_info=True)
			raise

	async def get_stock_basic_info (
			self,
			ts_code: str,
			include_quote: bool = False,
			include_financial: bool = False,
			use_cache: bool = True,
			user_id: Optional[int] = None
	) -> Dict[str, Any]:
		"""
		获取股票基础信息

		Args:
			ts_code: 股票代码
			include_quote: 是否包含最新行情
			include_financial: 是否包含财务数据
			use_cache: 是否使用缓存
			user_id: 用户ID

		Returns:
			Dict: 股票基础信息
		"""
		logger.info(f"获取股票基础信息，股票: {ts_code}")

		try:
			# 生成缓存键
			cache_key = None
			if use_cache:
				cache_key = CacheKey.STOCK_DETAIL.format(
					ts_code=ts_code,
					fields="basic" + ("_quote" if include_quote else "") + ("_financial" if include_financial else "")
				)

				# 尝试从缓存获取
				cached_info = await self.cache.get(cache_key)
				if cached_info:
					logger.info(f"从缓存获取股票基础信息，股票: {ts_code}")

					# 发布数据访问事件
					await self._publish_market_data_event(
						event_type="cached_request",
						ts_code=ts_code,
						data_type="stock_basic",
						cached=True,
						user_id=user_id
					)

					return cached_info

			# 获取股票基础信息
			stock = await self.stock_repo.get_by_ts_code(ts_code)

			if not stock:
				logger.warning(f"未找到股票基础信息，股票: {ts_code}")
				raise ValueError(f"股票 {ts_code} 不存在")

			# 构建基础信息
			result = {
				"ts_code": stock.ts_code,
				"symbol": stock.symbol if hasattr(stock, 'symbol') else ts_code.split('.')[0],
				"name": stock.name,
				"area": stock.area,
				"industry": stock.industry,
				"market": stock.market,
				"exchange": stock.exchange if hasattr(stock, 'exchange') else None,
				"list_date": stock.list_date.isoformat() if stock.list_date else None,
				"delist_date": stock.delist_date.isoformat() if hasattr(stock,
				                                                        'delist_date') and stock.delist_date else None,
				"is_hs": stock.is_hs,
				"list_status": stock.list_status if hasattr(stock, 'list_status') else "L",
				"created_at": stock.created_at.isoformat() if stock.created_at else None,
				"updated_at": stock.updated_at.isoformat() if stock.updated_at else None
			}

			# 包含最新行情
			if include_quote:
				latest_quote = await self.get_latest_quote(ts_code, use_cache=use_cache)
				if latest_quote:
					result["latest_quote"] = latest_quote

			# 包含财务数据（简化版）
			if include_financial:
				# 这里可以添加获取财务数据的逻辑
				result["financial_summary"] = {
					"note": "财务数据功能待实现"
				}

			# 缓存结果
			if use_cache and cache_key and result:
				await self.cache.set(
					cache_key,
					result,
					ttl=CacheKey.CACHE_TTL.get("stock_detail", 300)
				)

			# 发布数据访问事件
			await self._publish_market_data_event(
				event_type="data_request",
				ts_code=ts_code,
				data_type="stock_basic",
				cached=False,
				user_id=user_id
			)

			logger.info(f"获取股票基础信息完成，股票: {ts_code}")

			return result

		except Exception as e:
			logger.error(f"获取股票基础信息失败: {str(e)}", exc_info=True)
			raise

	async def get_stock_list (
			self,
			search: Optional[str] = None,
			market: Optional[str] = None,
			industry: Optional[str] = None,
			list_status: str = "L",
			min_market_cap: Optional[float] = None,
			max_market_cap: Optional[float] = None,
			page: int = 1,
			page_size: int = 20,
			sort_by: str = "ts_code",
			sort_order: str = "asc",
			use_cache: bool = True,
			user_id: Optional[int] = None
	) -> Dict[str, Any]:
		"""
		获取股票列表

		Args:
			search: 搜索关键词
			market: 市场类型
			industry: 行业
			list_status: 上市状态
			min_market_cap: 最小市值
			max_market_cap: 最大市值
			page: 页码
			page_size: 每页数量
			sort_by: 排序字段
			sort_order: 排序顺序
			use_cache: 是否使用缓存
			user_id: 用户ID

		Returns:
			Dict: 股票列表和分页信息
		"""
		logger.info(f"获取股票列表，搜索: {search}, 市场: {market}, 行业: {industry}")

		try:
			# 生成缓存键（基于查询参数）
			if use_cache:
				params_hash = self._generate_params_hash({
					"search": search,
					"market": market,
					"industry": industry,
					"list_status": list_status,
					"min_market_cap": min_market_cap,
					"max_market_cap": max_market_cap,
					"page": page,
					"page_size": page_size,
					"sort_by": sort_by,
					"sort_order": sort_order
				})

				cache_key = CacheKey.generate_stock_list_key(params_hash)

				# 尝试从缓存获取
				cached_list = await self.cache.get(cache_key)
				if cached_list:
					logger.info(f"从缓存获取股票列表，参数哈希: {params_hash}")

					# 发布数据访问事件
					await self._publish_market_data_event(
						event_type="cached_request",
						data_type="stock_list",
						cached=True,
						user_id=user_id
					)

					return cached_list

			# 构建查询条件
			filters = []

			if search:
				# 搜索股票代码或名称
				filters.append(
					or_(
						self.stock_repo.model.ts_code.ilike(f"%{search}%"),
						self.stock_repo.model.name.ilike(f"%{search}%")
					)
				)

			if market:
				filters.append(self.stock_repo.model.market == market)

			if industry:
				filters.append(self.stock_repo.model.industry == industry)

			if list_status:
				filters.append(self.stock_repo.model.list_status == list_status)

			# 市值筛选（如果有市值字段）
			if min_market_cap and hasattr(self.stock_repo.model, 'market_cap'):
				filters.append(self.stock_repo.model.market_cap >= min_market_cap)

			if max_market_cap and hasattr(self.stock_repo.model, 'market_cap'):
				filters.append(self.stock_repo.model.market_cap <= max_market_cap)

			# 构建排序
			order_column = None
			if sort_by == "ts_code":
				order_column = self.stock_repo.model.ts_code
			elif sort_by == "name":
				order_column = self.stock_repo.model.name
			elif sort_by == "list_date":
				order_column = self.stock_repo.model.list_date
			elif sort_by == "industry":
				order_column = self.stock_repo.model.industry
			elif sort_by == "market_cap" and hasattr(self.stock_repo.model, 'market_cap'):
				order_column = self.stock_repo.model.market_cap

			if order_column:
				if sort_order == "desc":
					order_column = order_column.desc()

			# 获取股票数据
			stocks = await self.stock_repo.get_many(
				*filters,
				skip=(page - 1) * page_size,
				limit=page_size,
				order_by=order_column
			)

			# 获取总数
			total = await self.stock_repo.count(*filters)

			# 转换为响应格式
			stock_list = []
			for stock in stocks:
				stock_info = {
					"ts_code": stock.ts_code,
					"symbol": stock.symbol if hasattr(stock, 'symbol') else stock.ts_code.split('.')[0],
					"name": stock.name,
					"area": stock.area,
					"industry": stock.industry,
					"market": stock.market,
					"list_date": stock.list_date.isoformat() if stock.list_date else None,
					"is_hs": stock.is_hs,
					"list_status": stock.list_status if hasattr(stock, 'list_status') else "L"
				}

				# 添加市值信息（如果有）
				if hasattr(stock, 'market_cap') and stock.market_cap:
					stock_info["market_cap"] = float(stock.market_cap)

				stock_list.append(stock_info)

			# 构建响应
			result = {
				"stocks": stock_list,
				"pagination": {
					"page": page,
					"page_size": page_size,
					"total": total,
					"total_pages": (total + page_size - 1) // page_size
				},
				"filters": {
					"search": search,
					"market": market,
					"industry": industry,
					"list_status": list_status
				}
			}

			# 缓存结果
			if use_cache and cache_key and result:
				await self.cache.set(
					cache_key,
					result,
					ttl=CacheKey.CACHE_TTL.get("stock_list", 3600)
				)

			# 发布数据访问事件
			await self._publish_market_data_event(
				event_type="data_request",
				data_type="stock_list",
				record_count=len(stock_list),
				cached=False,
				user_id=user_id
			)

			logger.info(f"获取股票列表完成，数量: {len(stock_list)}, 总数: {total}")

			return result

		except Exception as e:
			logger.error(f"获取股票列表失败: {str(e)}", exc_info=True)
			raise

	async def get_market_overview (
			self,
			market: Optional[str] = None,
			date: Optional[date] = None,
			indicators: Optional[List[str]] = None,
			user_id: Optional[int] = None
	) -> Dict[str, Any]:
		"""
		获取市场概览数据

		Args:
			market: 市场类型
			date: 日期（默认今天）
			indicators: 需要计算的指标
			user_id: 用户ID

		Returns:
			Dict: 市场概览数据
		"""
		logger.info(f"获取市场概览，市场: {market}, 日期: {date}")

		try:
			if not date:
				date = datetime.now().date()

			if not indicators:
				indicators = ["total_stocks", "advance_decline", "turnover", "market_cap"]

			# 生成缓存键
			cache_key = f"market:overview:{market or 'all'}:{date.strftime('%Y%m%d')}"

			# 尝试从缓存获取
			cached_overview = await self.cache.get(cache_key)
			if cached_overview:
				logger.info(f"从缓存获取市场概览，市场: {market}, 日期: {date}")

				# 发布数据访问事件
				await self._publish_market_data_event(
					event_type="cached_request",
					data_type="market_overview",
					market=market,
					date=date.isoformat(),
					cached=True,
					user_id=user_id
				)

				return cached_overview

			result = {
				"date": date.isoformat(),
				"market": market or "all",
				"indicators": {},
				"summary": {}
			}

			# 计算各项指标
			for indicator in indicators:
				try:
					if indicator == "total_stocks":
						# 总股票数量
						count = await self._get_total_stocks(market)
						result["indicators"]["total_stocks"] = count

					elif indicator == "advance_decline":
						# 涨跌家数
						ad_data = await self._get_advance_decline(date, market)
						result["indicators"]["advance_decline"] = ad_data

					elif indicator == "turnover":
						# 成交额和成交量
						turnover_data = await self._get_turnover(date, market)
						result["indicators"]["turnover"] = turnover_data

					elif indicator == "market_cap":
						# 总市值
						market_cap = await self._get_total_market_cap(market)
						result["indicators"]["market_cap"] = market_cap

				except Exception as e:
					logger.error(f"计算指标 {indicator} 失败: {str(e)}")
					result["indicators"][indicator] = {"error": str(e)}

			# 生成市场总结
			result["summary"] = await self._generate_market_summary(result["indicators"])

			# 缓存结果
			if result:
				await self.cache.set(
					cache_key,
					result,
					ttl=3600  # 市场概览缓存1小时
				)

			# 发布数据访问事件
			await self._publish_market_data_event(
				event_type="data_request",
				data_type="market_overview",
				market=market,
				date=date.isoformat(),
				cached=False,
				user_id=user_id
			)

			logger.info(f"获取市场概览完成，市场: {market}, 日期: {date}")

			return result

		except Exception as e:
			logger.error(f"获取市场概览失败: {str(e)}", exc_info=True)
			raise

	async def get_factor_exposure (
			self,
			ts_code: str,
			factor_names: Optional[List[str]] = None,
			start_date: Optional[date] = None,
			end_date: Optional[date] = None,
			user_id: Optional[int] = None
	) -> Dict[str, Any]:
		"""
		获取股票因子暴露度

		Args:
			ts_code: 股票代码
			factor_names: 因子名称列表
			start_date: 开始日期
			end_date: 结束日期
			user_id: 用户ID

		Returns:
			Dict: 因子暴露度数据
		"""
		logger.info(f"获取因子暴露度，股票: {ts_code}, 因子: {factor_names}")

		try:
			# 设置默认日期范围
			if not end_date:
				end_date = datetime.now().date()
			if not start_date:
				start_date = end_date - timedelta(days=365)  # 默认一年

			# 获取因子数据
			factor_exposures = {}

			if not factor_names:
				# 获取所有可用因子
				factor_names = await self._get_available_factors()

			for factor_name in factor_names:
				try:
					# 获取因子数据
					factor_data = await self.factor_repo.get_by_ts_code_and_date_range(
						ts_code=ts_code,
						factor_name=factor_name,
						start_date=start_date,
						end_date=end_date
					)

					if factor_data:
						# 计算因子暴露度统计
						values = [float(f.factor_value) for f in factor_data if f.factor_value is not None]

						if values:
							exposure_stats = {
								"current": values[-1] if values else None,
								"mean": float(np.mean(values)) if values else None,
								"std": float(np.std(values)) if len(values) > 1 else None,
								"min": float(np.min(values)) if values else None,
								"max": float(np.max(values)) if values else None,
								"percentile": self._calculate_percentile(values[-1], values) if values and values[
									-1] is not None else None,
								"count": len(values)
							}

							factor_exposures[factor_name] = exposure_stats

				except Exception as e:
					logger.error(f"获取因子 {factor_name} 暴露度失败: {str(e)}")
					factor_exposures[factor_name] = {"error": str(e)}

			result = {
				"ts_code": ts_code,
				"date_range": {
					"start": start_date.isoformat(),
					"end": end_date.isoformat()
				},
				"factor_exposures": factor_exposures,
				"summary": self._generate_exposure_summary(factor_exposures)
			}

			# 发布数据访问事件
			await self._publish_market_data_event(
				event_type="data_request",
				ts_code=ts_code,
				data_type="factor_exposure",
				factor_count=len(factor_exposures),
				user_id=user_id
			)

			logger.info(f"获取因子暴露度完成，股票: {ts_code}, 因子数量: {len(factor_exposures)}")

			return result

		except Exception as e:
			logger.error(f"获取因子暴露度失败: {str(e)}", exc_info=True)
			raise

	# ==================== 私有辅助方法 ====================

	async def _convert_frequency (
			self,
			daily_quotes: List,
			target_freq: str
	) -> List:
		"""转换数据频率"""
		if target_freq == "D":
			return daily_quotes

		# 转换为DataFrame便于处理
		df_data = []
		for quote in daily_quotes:
			df_data.append({
				"trade_date": quote.trade_date,
				"open": float(quote.open) if quote.open else None,
				"high": float(quote.high) if quote.high else None,
				"low": float(quote.low) if quote.low else None,
				"close": float(quote.close) if quote.close else None,
				"vol": float(quote.vol) if quote.vol else None,
				"amount": float(quote.amount) if hasattr(quote, 'amount') and quote.amount else None
			})

		if not df_data:
			return []

		df = pd.DataFrame(df_data)
		df.set_index("trade_date", inplace=True)
		df.sort_index(inplace=True)

		if target_freq == "W":
			# 转换为周线
			weekly_df = df.resample('W').agg({
				'open': 'first',
				'high': 'max',
				'low': 'min',
				'close': 'last',
				'vol': 'sum',
				'amount': 'sum'
			})

			# 转换回对象列表
			return self._df_to_quote_objects(weekly_df, freq="W")

		elif target_freq == "M":
			# 转换为月线
			monthly_df = df.resample('M').agg({
				'open': 'first',
				'high': 'max',
				'low': 'min',
				'close': 'last',
				'vol': 'sum',
				'amount': 'sum'
			})

			return self._df_to_quote_objects(monthly_df, freq="M")

		return daily_quotes

	def _df_to_quote_objects (self, df: pd.DataFrame, freq: str) -> List:
		"""将DataFrame转换回行情对象列表"""
		quotes = []

		for idx, row in df.iterrows():
			# 创建一个简单的类来模拟行情对象
			class QuoteObject:
				def __init__ (self, trade_date, **kwargs):
					self.trade_date = trade_date
					for key, value in kwargs.items():
						setattr(self, key, value)

			quote = QuoteObject(
				trade_date=idx,
				open=row.get('open'),
				high=row.get('high'),
				low=row.get('low'),
				close=row.get('close'),
				vol=row.get('vol'),
				amount=row.get('amount')
			)

			quotes.append(quote)

		return quotes

	async def _adjust_prices (
			self,
			quotes: List,
			adj_type: str
	) -> List:
		"""价格复权处理"""
		# 这里简化处理，实际需要从数据库获取复权因子
		# 并计算复权价格

		if not quotes:
			return quotes

		# 模拟复权因子（实际应从数据库获取）
		adj_factor = 1.0

		for quote in quotes:
			if adj_type == "qfq":
				# 前复权：将历史价格调整到当前
				if hasattr(quote, 'open') and quote.open:
					quote.open = quote.open * adj_factor
				if hasattr(quote, 'high') and quote.high:
					quote.high = quote.high * adj_factor
				if hasattr(quote, 'low') and quote.low:
					quote.low = quote.low * adj_factor
				if hasattr(quote, 'close') and quote.close:
					quote.close = quote.close * adj_factor
				if hasattr(quote, 'pre_close') and quote.pre_close:
					quote.pre_close = quote.pre_close * adj_factor

			elif adj_type == "hfq":
				# 后复权：将当前价格调整到历史
				if hasattr(quote, 'open') and quote.open:
					quote.open = quote.open / adj_factor
				if hasattr(quote, 'high') and quote.high:
					quote.high = quote.high / adj_factor
				if hasattr(quote, 'low') and quote.low:
					quote.low = quote.low / adj_factor
				if hasattr(quote, 'close') and quote.close:
					quote.close = quote.close / adj_factor
				if hasattr(quote, 'pre_close') and quote.pre_close:
					quote.pre_close = quote.pre_close / adj_factor

			# 添加复权因子字段
			if not hasattr(quote, 'adj_factor'):
				quote.adj_factor = adj_factor

		return quotes

	def _select_fields (
			self,
			quotes: List,
			fields: List[str]
	) -> List:
		"""选择返回字段"""
		if not fields or not quotes:
			return quotes

		# 创建一个简化的对象，只包含指定字段
		filtered_quotes = []

		for quote in quotes:
			filtered_quote = type('FilteredQuote', (), {})()

			for field in fields:
				if hasattr(quote, field):
					setattr(filtered_quote, field, getattr(quote, field))

			# 确保trade_date总是包含
			if hasattr(quote, 'trade_date'):
				filtered_quote.trade_date = quote.trade_date

			filtered_quotes.append(filtered_quote)

		return filtered_quotes

	def _generate_params_hash (self, params: Dict) -> str:
		"""生成查询参数哈希值"""
		import hashlib
		import json

		# 将参数转换为JSON字符串
		params_str = json.dumps(params, sort_keys=True)

		# 计算MD5哈希
		return hashlib.md5(params_str.encode()).hexdigest()[:8]

	async def _get_total_stocks (self, market: Optional[str] = None) -> int:
		"""获取总股票数量"""
		filters = []
		if market:
			filters.append(self.stock_repo.model.market == market)

		return await self.stock_repo.count(*filters)

	async def _get_advance_decline (
			self,
			date: date,
			market: Optional[str] = None
	) -> Dict[str, Any]:
		"""获取涨跌家数"""
		# 这里简化处理，实际需要统计当日涨跌股票数量

		return {
			"advance": 1500,  # 上涨家数
			"decline": 1000,  # 下跌家数
			"unchanged": 500,  # 平盘家数
			"limit_up": 50,  # 涨停家数
			"limit_down": 30  # 跌停家数
		}

	async def _get_turnover (
			self,
			date: date,
			market: Optional[str] = None
	) -> Dict[str, Any]:
		"""获取成交数据"""
		# 这里简化处理，实际需要统计当日成交数据

		return {
			"total_volume": 1000000000,  # 总成交量（股）
			"total_amount": 80000000000,  # 总成交额（元）
			"avg_turnover_rate": 2.5  # 平均换手率（%）
		}

	async def _get_total_market_cap (self, market: Optional[str] = None) -> float:
		"""获取总市值"""
		# 这里简化处理，实际需要计算所有股票市值总和

		return 80000000000000  # 80万亿

	async def _generate_market_summary (self, indicators: Dict) -> Dict[str, Any]:
		"""生成市场总结"""
		summary = {
			"market_status": "normal",
			"sentiment": "neutral",
			"trend": "sideways",
			"risk_level": "medium"
		}

		# 基于指标生成总结
		if "advance_decline" in indicators:
			ad_data = indicators["advance_decline"]
			if isinstance(ad_data, dict):
				advance = ad_data.get("advance", 0)
				decline = ad_data.get("decline", 0)

				if advance > decline * 1.5:
					summary["sentiment"] = "bullish"
					summary["trend"] = "up"
				elif decline > advance * 1.5:
					summary["sentiment"] = "bearish"
					summary["trend"] = "down"

		if "turnover" in indicators:
			turnover_data = indicators["turnover"]
			if isinstance(turnover_data, dict):
				turnover_rate = turnover_data.get("avg_turnover_rate", 0)

				if turnover_rate > 3:
					summary["market_status"] = "active"
					summary["risk_level"] = "high"
				elif turnover_rate < 1:
					summary["market_status"] = "quiet"
					summary["risk_level"] = "low"

		return summary

	async def _get_available_factors (self) -> List[str]:
		"""获取可用因子列表"""
		try:
			factors = await self.factor_repo.get_available_factors()
			return factors
		except Exception:
			# 如果获取失败，返回标准因子列表
			return [
				StandardFactors.PE,
				StandardFactors.PB,
				StandardFactors.ROE,
				StandardFactors.MARKET_CAP,
				StandardFactors.RET_1M,
				StandardFactors.VOLATILITY_1M
			]

	def _calculate_percentile (
			self,
			value: float,
			values: List[float]
	) -> float:
		"""计算百分位数"""
		if not values or value is None:
			return 0

		sorted_values = sorted(values)

		# 计算小于等于当前值的数量
		count_less_equal = sum(1 for v in sorted_values if v <= value)

		# 计算百分位数
		percentile = (count_less_equal / len(sorted_values)) * 100

		return round(percentile, 2)

	def _generate_exposure_summary (self, factor_exposures: Dict) -> Dict[str, Any]:
		"""生成因子暴露度总结"""
		if not factor_exposures:
			return {"note": "无因子暴露度数据"}

		# 计算各因子的当前暴露度
		current_exposures = {}
		for factor_name, stats in factor_exposures.items():
			if isinstance(stats, dict) and "current" in stats:
				current_exposures[factor_name] = stats["current"]

		# 找出最大值和最小值
		if current_exposures:
			max_factor = max(current_exposures.items(), key=lambda x: x[1] if x[1] is not None else -float('inf'))
			min_factor = min(current_exposures.items(), key=lambda x: x[1] if x[1] is not None else float('inf'))

			return {
				"factor_count": len(factor_exposures),
				"highest_exposure": {
					"factor": max_factor[0],
					"value": max_factor[1]
				},
				"lowest_exposure": {
					"factor": min_factor[0],
					"value": min_factor[1]
				},
				"average_exposure": np.mean(
					[v for v in current_exposures.values() if v is not None]) if current_exposures else None
			}
		else:
			return {"factor_count": len(factor_exposures), "note": "无当前暴露度数据"}

	async def _publish_market_data_event (
			self,
			event_type: str,
			ts_code: Optional[str] = None,
			data_type: Optional[str] = None,
			record_count: Optional[int] = None,
			market: Optional[str] = None,
			date: Optional[str] = None,
			factor_count: Optional[int] = None,
			cached: bool = False,
			user_id: Optional[int] = None
	):
		"""发布市场数据事件"""
		if not self.event_engine:
			return

		event_data = {
			"event_type": f"market.events.{event_type}",
			"timestamp": datetime.now(),
			"user_id": user_id,
			"cached": cached
		}

		if ts_code:
			event_data["ts_code"] = ts_code
		if data_type:
			event_data["data_type"] = data_type
		if record_count is not None:
			event_data["record_count"] = record_count
		if market:
			event_data["market"] = market
		if date:
			event_data["date"] = date
		if factor_count is not None:
			event_data["factor_count"] = factor_count

		event = MarketDataRequestEvent(**event_data)

		await self.event_engine.put(event)