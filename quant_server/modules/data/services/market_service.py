# -*- coding: utf-8 -*-
"""
市场数据仓库服务
提供统一的市场数据访问接口，支持缓存、数据转换和批量处理
位置：quant_server/modules/data/services/market_service.py

设计原则：
1. 统一数据访问：提供一致的数据查询接口
2. 智能缓存：基于数据类型和访问频率自动缓存
3. 高性能：支持批量查询和高效数据处理
4. 数据转换：支持多种数据格式和频率转换
"""

import logging
from datetime import datetime, date, timedelta
from typing import Dict, List, Any, Optional

import numpy as np
import pandas as pd
from sqlalchemy import or_, func
from sqlalchemy.ext.asyncio import AsyncSession

from core import BusinessException
# 导入核心基础设施
from core.engines.system.event_engine import EventEngine
from core.events.base import BaseEvent
from core.events.types import EventPriority, EventCategory
# 导入数据模块常量
from modules.data.constants import (
	CacheKey,
	Frequency,
	AdjustType,
)
from shared.cache.redis_cache import RedisCache
# 导入共享层组件
from shared.database.repositories.market.basic.stock_repo import StockBasicRepository
from shared.database.repositories.market.quote.stock_daily_repo import StockDailyRepository
from shared.database.repositories.market.reference.trade_calendar_repo import TradeCalendarRepository
from shared.database.repositories.analysis.factor.factor_data_repo import FactorDataRepository
from shared.database.repositories.market.basic.index_repo import IndexBasicRepository
from utils.core_utils.data_utils.data_transformer import DataTransformerPipeline
# 导入工具类
from utils.core_utils.time_utils.trading_calendar import TradingCalendar

# 导入事件相关

# 配置日志
logger = logging.getLogger(__name__)


def _get_default_start_date (end_date: date, freq: str) -> date:
	"""
	获取默认开始日期

	Args:
		end_date: 结束日期
		freq: 数据频率

	Returns:
		date: 默认开始日期
	"""
	if freq == Frequency.DAILY:
		return end_date - timedelta(days=365)  # 默认一年
	elif freq == Frequency.WEEKLY:
		return end_date - timedelta(weeks=52)  # 默认一年
	elif freq == Frequency.MONTHLY:
		return end_date - timedelta(days=365)  # 默认一年
	else:
		return end_date - timedelta(days=30)  # 默认一个月


def _generate_params_hash (params: Dict) -> str:
	"""
	生成查询参数哈希值

	Args:
		params: 查询参数字典

	Returns:
		str: 8位哈希字符串
	"""
	import hashlib
	import json

	# 将参数转换为JSON字符串
	params_str = json.dumps(params, sort_keys=True)

	# 计算MD5哈希
	return hashlib.md5(params_str.encode()).hexdigest()[:8]


def _format_quotes_to_dict (
		quotes: List,
		ts_code: str,
		adj: str,
		fields: Optional[List[str]] = None,
) -> List[Dict[str, Any]]:
	"""
	将行情对象列表转换为字典列表，支持按需选择字段

	Args:
		quotes: 行情对象列表
		ts_code: 股票代码
		adj: 复权类型
		fields: 需要返回的字段列表，为 None 时返回全部字段

	Returns:
		List[Dict]: 格式化后的行情数据列表
	"""
	result = []
	include_all = not fields

	for quote in quotes:
		trade_date_val = quote.trade_date.isoformat() if hasattr(quote.trade_date, 'isoformat') else str(
			quote.trade_date)

		quote_dict = {
			"trade_date": trade_date_val,
			"ts_code": ts_code,
		}

		if include_all or "open" in fields:
			quote_dict["open"] = float(quote.open) if quote.open else None
		if include_all or "high" in fields:
			quote_dict["high"] = float(quote.high) if quote.high else None
		if include_all or "low" in fields:
			quote_dict["low"] = float(quote.low) if quote.low else None
		if include_all or "close" in fields:
			quote_dict["close"] = float(quote.close) if quote.close else None
		if include_all or "pre_close" in fields:
			quote_dict["pre_close"] = float(quote.pre_close) if hasattr(quote, 'pre_close') and quote.pre_close else None
		if include_all or "change" in fields:
			quote_dict["change"] = float(quote.change) if hasattr(quote, 'change') and quote.change else None
		if include_all or "pct_chg" in fields:
			quote_dict["pct_chg"] = float(quote.pct_chg) if hasattr(quote, 'pct_chg') and quote.pct_chg else None
		if include_all or "vol" in fields or "volume" in fields:
			quote_dict["volume"] = float(quote.vol) if quote.vol else None
		if include_all or "amount" in fields:
			quote_dict["amount"] = float(quote.amount) if hasattr(quote, 'amount') and quote.amount else None

		# 添加复权因子（如果需要）
		if adj in [AdjustType.PRE, AdjustType.POST] and hasattr(quote, 'adj_factor'):
			if include_all or "adj_factor" in fields:
				quote_dict["adj_factor"] = float(quote.adj_factor) if quote.adj_factor else None

		result.append(quote_dict)

	return result


def _calculate_rsi (
		df: pd.DataFrame,
		parameters: Optional[Dict[str, Any]] = None
) -> Dict[str, Any]:
	"""
	计算RSI指标

	Args:
		df: 包含收盘价的DataFrame
		parameters: 计算参数，包含RSI周期

	Returns:
		Dict: RSI计算结果
	"""
	if 'close' not in df.columns:
		return {"error": "缺少收盘价数据", "status": "error"}

	period = parameters.get("period", 14) if parameters else 14

	if len(df) < period:
		return {
			"error": "数据长度不足",
			"status": "error",
			"required_length": period,
			"actual_length": len(df)
		}

	# 计算价格变化
	delta = df['close'].diff()

	# 分离上涨和下跌
	gain = (delta.where(delta > 0, 0)).rolling(window=period).mean()
	loss = (-delta.where(delta < 0, 0)).rolling(window=period).mean()

	# 计算RS
	rs = gain / loss

	# 计算RSI
	rsi = 100 - (100 / (1 + rs))

	return {
		"period": period,
		"values": rsi.tolist(),
		"status": "success"
	}


def _calculate_boll (
		df: pd.DataFrame,
		parameters: Optional[Dict[str, Any]] = None
) -> Dict[str, Any]:
	"""
	计算布林带指标

	Args:
		df: 包含收盘价的DataFrame
		parameters: 计算参数，包含周期和标准差倍数

	Returns:
		Dict: 布林带计算结果
	"""
	if 'close' not in df.columns:
		return {"error": "缺少收盘价数据", "status": "error"}

	period = parameters.get("period", 20) if parameters else 20
	std_multiplier = parameters.get("std_multiplier", 2) if parameters else 2

	if len(df) < period:
		return {
			"error": "数据长度不足",
			"status": "error",
			"required_length": period,
			"actual_length": len(df)
		}

	# 计算中轨（移动平均）
	middle = df['close'].rolling(window=period).mean()

	# 计算标准差
	std = df['close'].rolling(window=period).std()

	# 计算上下轨
	upper = middle + (std * std_multiplier)
	lower = middle - (std * std_multiplier)

	return {
		"parameters": {
			"period": period,
			"std_multiplier": std_multiplier
		},
		"values": {
			"upper": upper.tolist(),
			"middle": middle.tolist(),
			"lower": lower.tolist()
		},
		"status": "success"
	}


def _calculate_kdj (
		df: pd.DataFrame,
		parameters: Optional[Dict[str, Any]] = None
) -> Dict[str, Any]:
	"""
	计算KDJ指标

	Args:
		df: 包含高、低、收盘价的DataFrame
		parameters: 计算参数，包含RSV周期、K周期、D周期

	Returns:
		Dict: KDJ计算结果
	"""
	required_cols = ['high', 'low', 'close']
	if not all(col in df.columns for col in required_cols):
		return {"error": "缺少价格数据", "status": "error"}

	# 默认参数
	n = parameters.get("n", 9) if parameters else 9
	m1 = parameters.get("m1", 3) if parameters else 3
	m2 = parameters.get("m2", 3) if parameters else 3

	if len(df) < n:
		return {
			"error": "数据长度不足",
			"status": "error",
			"required_length": n,
			"actual_length": len(df)
		}

	# 计算RSV
	low_min = df['low'].rolling(window=n).min()
	high_max = df['high'].rolling(window=n).max()

	rsv = 100 * (df['close'] - low_min) / (high_max - low_min)
	rsv = rsv.fillna(50)  # 处理除零情况

	# 计算K、D、J值
	k = rsv.ewm(alpha=1 / m1, adjust=False).mean()
	d = k.ewm(alpha=1 / m2, adjust=False).mean()
	j = 3 * k - 2 * d

	return {
		"parameters": {
			"n": n,
			"m1": m1,
			"m2": m2
		},
		"values": {
			"K": k.tolist(),
			"D": d.tolist(),
			"J": j.tolist()
		},
		"status": "success"
	}




class _MarketDataNotificationEvent(BaseEvent):
	"""市场数据服务内部通知事件 — 用于记录数据访问和异常的轻量事件"""
	def __init__(self, event_data: dict):
		super().__init__(
			event_type=event_data.get("event_type", ""),
			source=event_data.get("source", "market_service"),
			module=event_data.get("module", "data"),
			priority=event_data.get("priority", EventPriority.NORMAL),
			category=event_data.get("category", EventCategory.BUSINESS),
			data=event_data,
		)


class MarketDataService:
	"""
	市场数据仓库服务类
	提供市场数据的查询、分析和处理功能

	Attributes:
		session: 异步数据库会话
		event_engine: 事件引擎
		stock_repo: 股票数据仓库
		factor_repo: 因子数据仓库
		calendar_repo: 交易日历仓库
	"""

	def __init__ (self, session: Optional[AsyncSession] = None, event_engine: Optional[EventEngine] = None):
		"""
		初始化市场数据服务

		Args:
			session: 数据库会话
			event_engine: 事件引擎，用于发布数据访问事件
		"""
		self.session = session
		self.event_engine = event_engine

		# 初始化Repository（仅当session不为None时）
		if session:
			self.stock_repo = StockBasicRepository(session)
			self.quote_repo = StockDailyRepository(session)
			self.calendar_repo = TradeCalendarRepository(session)
			self.factor_repo = FactorDataRepository(session)
			self.index_repo = IndexBasicRepository(session)
		else:
			self.stock_repo = None
			self.quote_repo = None
			self.calendar_repo = None
			self.factor_repo = None
			self.index_repo = None
			self.financial_repo = None

		# 初始化工具
		self.trading_calendar = TradingCalendar()
		self.data_transformer = DataTransformerPipeline()

		# 初始化缓存（懒加载）
		self._cache = None

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

	# ==================== 基础数据查询方法 ====================

	async def get_historical_quotes (
			self,
			ts_code: str,
			start_date: Optional[date] = None,
			end_date: Optional[date] = None,
			freq: str = "D",
			adj: str = "qfq",
			fields: Optional[List[str]] = None,
			limit: int = 0,
			use_cache: bool = True,
			user_id: Optional[str] = None
	) -> List[Dict[str, Any]]:
		"""
		获取历史行情数据

		Args:
			ts_code: 股票代码（格式：000001.SZ）
			start_date: 开始日期，默认一年前
			end_date: 结束日期，默认今天
			freq: 数据频率，支持：D-日线, W-周线, M-月线, 5-5分钟, 15-15分钟, 30-30分钟, 60-60分钟
			adj: 复权类型，支持：qfq-前复权, hfq-后复权, None-不复权
			fields: 返回字段列表，默认返回所有字段
			limit: 返回数据条数限制，0表示不限制
			use_cache: 是否使用缓存
			user_id: 用户ID，用于事件追踪

		Returns:
			List[Dict]: 行情数据列表，按交易日期倒序排列

		Raises:
			ValueError: 参数错误
			DataNotFoundException: 数据不存在
		"""
		logger.info(f"获取历史行情数据: {ts_code}, 频率: {freq}, 复权: {adj}")

		try:
			# 参数验证
			if not ts_code:
				raise ValueError("股票代码不能为空")

			# 生成缓存键
			cache_key = None
			if use_cache and self._cache is not None:
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
					logger.info(f"从缓存获取历史行情数据: {ts_code}")
					await self._publish_data_access_event(
						"cached_request", ts_code, "historical_quotes",
						user_id=user_id, cached=True
					)
					return cached_data
			elif use_cache and self._cache is None:
				logger.info(f"缓存未启动，跳过缓存检查: {ts_code}")

			# 设置默认日期范围
			if not end_date:
				end_date = datetime.now().date()
			if not start_date:
				start_date = _get_default_start_date(end_date, freq)

			# 验证日期范围
			if start_date > end_date:
				start_date, end_date = end_date, start_date

			# 获取基础行情数据
			quotes = await self.quote_repo.get_by_code_and_date_range(
				ts_code=ts_code,
				start_date=start_date,
				end_date=end_date
			)
			# 按交易日期倒序排列
			quotes.sort(key=lambda x: x.trade_date, reverse=True)
			if limit > 0:
				quotes = quotes[:limit]

			if not quotes:
				logger.warning(f"未找到行情数据: {ts_code}，尝试从模拟数据源获取")
				# 从模拟数据源获取数据
				from shared.sources.source_factory import DataSourceFactory
				from modules.data.constants import DataSource
				source_factory = DataSourceFactory()
				source = source_factory.get_source(DataSource.TUSHARE)
				start_date_str = start_date.strftime('%Y%m%d')
				end_date_str = end_date.strftime('%Y%m%d')
				daily_df = source.get_daily(
					symbol=ts_code,
					start_date=start_date_str,
					end_date=end_date_str
				)
				if not daily_df.empty:
					# 转换为行情对象列表
					class QuoteObject:
						def __init__ (self, trade_date, **kwargs):
							self.trade_date = trade_date
							for key, value in kwargs.items():
								setattr(self, key, value)
					quotes = []
					for idx, row in daily_df.iterrows():
						quote = QuoteObject(
							trade_date=row.get('trade_date').date() if hasattr(row.get('trade_date'), 'date') else row.get('trade_date'),
							open=row.get('open'),
							high=row.get('high'),
							low=row.get('low'),
							close=row.get('close'),
							pre_close=row.get('pre_close'),
							change=row.get('change'),
							pct_chg=row.get('pct_chg'),
							vol=row.get('vol'),
							amount=row.get('amount')
						)
						quotes.append(quote)
					# 按交易日期倒序排列
					quotes.sort(key=lambda x: x.trade_date, reverse=True)
					if limit > 0:
						quotes = quotes[:limit]
					logger.info(f"从模拟数据源获取行情数据: {ts_code}, 记录数: {len(quotes)}")
				else:
					logger.warning(f"模拟数据源也未找到行情数据: {ts_code}")
					await self._publish_data_access_event(
						"data_not_found", ts_code, "historical_quotes",
						user_id=user_id
					)
					return []

			# 转换为目标频率
			if freq != Frequency.DAILY:
				quotes = await self._convert_frequency(quotes, freq)

			# 处理复权
			if adj in [AdjustType.PRE, AdjustType.POST]:
				quotes = await self._adjust_prices(quotes, adj)

			# 转换为响应格式（fields 直接传入，由 _format_quotes_to_dict 按需选择字段）
			result = _format_quotes_to_dict(quotes, ts_code, adj, fields)

			# 缓存结果
			if use_cache and cache_key and result:
				await self.cache.set(
					cache_key,
					result,
					ttl=CacheKey.CACHE_TTL.get("historical_quotes", 600)
				)

			# 发布数据访问事件
			await self._publish_data_access_event(
				"data_request", ts_code, "historical_quotes",
				record_count=len(result), user_id=user_id
			)

			logger.info(f"获取历史行情数据完成: {ts_code}, 记录数: {len(result)}")
			return result

		except Exception as e:
			logger.error(f"获取历史行情数据失败: {str(e)}", exc_info=True)
			await self._publish_error_event("historical_quotes", str(e), ts_code, user_id)
			raise

	async def get_multiple_historical_quotes (
			self,
			ts_codes: List[str],
			start_date: Optional[date] = None,
			end_date: Optional[date] = None,
			freq: str = "D",
			adj: str = "qfq",
			use_cache: bool = True,
			user_id: Optional[str] = None
	) -> Dict[str, List[Dict[str, Any]]]:
		"""
		批量获取多只股票的历史行情数据

		Args:
			ts_codes: 股票代码列表
			start_date: 开始日期
			end_date: 结束日期
			freq: 数据频率
			adj: 复权类型
			use_cache: 是否使用缓存
			user_id: 用户ID

		Returns:
			Dict[str, List[Dict]]: 每只股票的行情数据
		"""
		logger.info(f"批量获取历史行情数据: {len(ts_codes)}只股票")

		results = {}
		for ts_code in ts_codes:
			try:
				quotes = await self.get_historical_quotes(
					ts_code=ts_code,
					start_date=start_date,
					end_date=end_date,
					freq=freq,
					adj=adj,
					use_cache=use_cache,
					user_id=user_id
				)
				results[ts_code] = quotes
			except Exception as e:
				logger.error(f"获取股票 {ts_code} 历史行情失败: {str(e)}")
				results[ts_code] = []

		return results

	async def get_latest_quote (
			self,
			ts_code: str,
			use_cache: bool = True,
			user_id: Optional[str] = None
	) -> Optional[Dict[str, Any]]:
		"""
		获取最新行情数据

		Args:
			ts_code: 股票代码
			use_cache: 是否使用缓存
			user_id: 用户ID

		Returns:
			Dict: 最新行情数据，包含以下字段：
				- ts_code: 股票代码
				- trade_date: 交易日期
				- open: 开盘价
				- high: 最高价
				- low: 最低价
				- close: 收盘价
				- pre_close: 前收盘价
				- change: 涨跌额
				- pct_chg: 涨跌幅
				- vol: 成交量
				- amount: 成交额
				- updated_at: 更新时间
		"""
		logger.info(f"获取最新行情数据: {ts_code}")

		try:
			# 参数验证
			if not ts_code:
				raise ValueError("股票代码不能为空")

			# 生成缓存键
			cache_key = None
			if use_cache and self._cache is not None:
				cache_key = CacheKey.LATEST_QUOTE.format(ts_code=ts_code)

				# 尝试从缓存获取
				cached_quote = await self.cache.get(cache_key)
				if cached_quote:
					logger.info(f"从缓存获取最新行情: {ts_code}")
					await self._publish_data_access_event(
						"cached_request", ts_code, "latest_quote",
						user_id=user_id, cached=True
					)
					return cached_quote
			elif use_cache and self._cache is None:
				logger.info(f"缓存未启动，跳过缓存检查: {ts_code}")

			# 从数据库获取最新行情
			latest_quote = await self.quote_repo.get_latest_by_code(ts_code)

			if not latest_quote:
				logger.warning(f"未找到最新行情: {ts_code}")
				await self._publish_data_access_event(
					"data_not_found", ts_code, "latest_quote",
					user_id=user_id
				)
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
			if use_cache and cache_key and self._cache is not None:
				await self.cache.set(
					cache_key,
					result,
					ttl=300  # 最新行情缓存5分钟
				)

			# 发布数据访问事件
			await self._publish_data_access_event(
				"data_request", ts_code, "latest_quote",
				user_id=user_id
			)

			logger.info(f"获取最新行情数据完成: {ts_code}, 日期: {result['trade_date']}")
			return result

		except Exception as e:
			logger.error(f"获取最新行情数据失败: {str(e)}", exc_info=True)
			await self._publish_error_event("latest_quote", str(e), ts_code, user_id)
			raise

	# ==================== 股票信息查询方法 ====================

	async def get_stock_basic_info (
			self,
			ts_code: str,
			include_quote: bool = False,
			include_financial: bool = False,
			include_factor: bool = False,
			use_cache: bool = True,
			user_id: Optional[str] = None
	) -> Dict[str, Any]:
		"""
		获取股票基础信息

		Args:
			ts_code: 股票代码
			include_quote: 是否包含最新行情
			include_financial: 是否包含财务数据摘要
			include_factor: 是否包含因子数据
			use_cache: 是否使用缓存
			user_id: 用户ID

		Returns:
			Dict: 股票基础信息，包含以下字段：
				- ts_code: 股票代码
				- symbol: 股票简称
				- name: 股票名称
				- area: 地区
				- industry: 行业
				- market: 市场类型
				- exchange: 交易所
				- list_date: 上市日期
				- delist_date: 退市日期
				- is_hs: 是否沪深港通
				- list_status: 上市状态
				- created_at: 创建时间
				- updated_at: 更新时间
		"""
		logger.info(f"获取股票基础信息: {ts_code}")

		try:
			# 参数验证
			if not ts_code:
				raise ValueError("股票代码不能为空")

			# 生成缓存键
			cache_key = None
			if use_cache and self._cache is not None:
				field_suffix = ""
				if include_quote:
					field_suffix += "_quote"
				if include_financial:
					field_suffix += "_financial"
				if include_factor:
					field_suffix += "_factor"

				cache_key = CacheKey.STOCK_DETAIL.format(
					ts_code=ts_code,
					fields=f"basic{field_suffix}"
				)

				# 尝试从缓存获取
				cached_info = await self.cache.get(cache_key)
				if cached_info:
					logger.info(f"从缓存获取股票基础信息: {ts_code}")
					await self._publish_data_access_event(
						"cached_request", ts_code, "stock_basic",
						user_id=user_id, cached=True
					)
					return cached_info
			elif use_cache and self._cache is None:
				logger.info(f"缓存未启动，跳过缓存检查: {ts_code}")

			# 获取股票基础信息
			stock = await self.stock_repo.get_by_ts_code(ts_code)

			if not stock:
				logger.warning(f"未找到股票基础信息: {ts_code}")
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

			# 包含财务数据
			if include_financial:
				financial_summary = await self._get_financial_summary(ts_code)
				result["financial_summary"] = financial_summary

			# 包含因子数据
			if include_factor:
				factor_exposure = await self.get_factor_exposure(
					ts_code=ts_code,
					factor_names=None,
					user_id=user_id
				)
				result["factor_exposure"] = factor_exposure.get("factor_exposures", {})

			# 缓存结果
			if use_cache and cache_key and self._cache is not None:
				await self.cache.set(
					cache_key,
					result,
					ttl=CacheKey.CACHE_TTL.get("stock_detail", 300)
				)

			# 发布数据访问事件
			await self._publish_data_access_event(
				"data_request", ts_code, "stock_basic",
				user_id=user_id
			)

			logger.info(f"获取股票基础信息完成: {ts_code}")
			return result

		except Exception as e:
			logger.error(f"获取股票基础信息失败: {str(e)}", exc_info=True)
			await self._publish_error_event("stock_basic", str(e), ts_code, user_id)
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
			user_id: Optional[str] = None
	) -> Dict[str, Any]:
		"""
		获取股票列表

		Args:
			search: 搜索关键词（股票代码或名称）
			market: 市场类型（SH/SZ/BJ）
			industry: 行业分类
			list_status: 上市状态（L-上市，D-退市，P-暂停上市）
			min_market_cap: 最小市值（亿元）
			max_market_cap: 最大市值（亿元）
			page: 页码（从1开始）
			page_size: 每页数量
			sort_by: 排序字段（ts_code/name/list_date/industry/market_cap）
			sort_order: 排序顺序（asc/desc）
			use_cache: 是否使用缓存
			user_id: 用户ID

		Returns:
			Dict: 股票列表和分页信息，包含以下字段：
				- stocks: 股票列表
				- pagination: 分页信息
				- filters: 查询条件
		"""
		logger.info(f"获取股票列表，搜索: {search}, 市场: {market}, 行业: {industry}")

		try:
			# 生成缓存键
			cache_key = None
			if use_cache and self._cache is not None:
				params_hash = _generate_params_hash({
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
					logger.info(f"从缓存获取股票列表: {params_hash}")
					await self._publish_data_access_event(
						"cached_request", None, "stock_list",
						user_id=user_id, cached=True
					)
					return cached_list
			elif use_cache and self._cache is None:
				logger.info(f"缓存未启动，跳过缓存检查: stock_list")

			# 构建查询条件
			filters = []

			# 搜索条件
			if search:
				filters.append(
					or_(
						self.stock_repo.model.ts_code.ilike(f"%{search}%"),
						self.stock_repo.model.name.ilike(f"%{search}%")
					)
				)

			# 市场条件
			if market:
				filters.append(self.stock_repo.model.market == market)

			# 行业条件
			if industry:
				filters.append(self.stock_repo.model.industry == industry)

			# 上市状态
			if list_status:
				filters.append(self.stock_repo.model.list_status == list_status)

			# 市值筛选（如果有市值字段）
			if min_market_cap and hasattr(self.stock_repo.model, 'market_cap'):
				filters.append(self.stock_repo.model.market_cap >= min_market_cap * 1e8)  # 转换为元

			if max_market_cap and hasattr(self.stock_repo.model, 'market_cap'):
				filters.append(self.stock_repo.model.market_cap <= max_market_cap * 1e8)  # 转换为元

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

			# 计算偏移量
			skip = (page - 1) * page_size

			# 获取股票数据
			from sqlalchemy import select
			query = select(self.stock_repo.model)
			for condition in filters:
				query = query.where(condition)
			if order_column:
				query = query.order_by(order_column)
			query = query.offset(skip).limit(page_size)
			result = await self.stock_repo.session.execute(query)
			stocks = result.scalars().all()

			# 获取总数
			count_query = select(func.count()).select_from(self.stock_repo.model)
			for condition in filters:
				count_query = count_query.where(condition)
			count_result = await self.stock_repo.session.execute(count_query)
			total = count_result.scalar()

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
					stock_info["market_cap"] = float(stock.market_cap) / 1e8  # 转换为亿元

				stock_list.append(stock_info)

			# 构建响应
			result = {
				"stocks": stock_list,
				"pagination": {
					"page": page,
					"page_size": page_size,
					"total": total,
					"total_pages": (total + page_size - 1) // page_size if page_size > 0 else 0
				},
				"filters": {
					"search": search,
					"market": market,
					"industry": industry,
					"list_status": list_status,
					"min_market_cap": min_market_cap,
					"max_market_cap": max_market_cap
				}
			}

			# 缓存结果
			if use_cache and cache_key and self._cache is not None:
				await self.cache.set(
					cache_key,
					result,
					ttl=CacheKey.CACHE_TTL.get("stock_list", 3600)
				)

			# 发布数据访问事件
			await self._publish_data_access_event(
				"data_request", None, "stock_list",
				record_count=len(stock_list), user_id=user_id
			)

			logger.info(f"获取股票列表完成，数量: {len(stock_list)}, 总数: {total}")
			return result

		except Exception as e:
			logger.error(f"获取股票列表失败: {str(e)}", exc_info=True)
			await self._publish_error_event("stock_list", str(e), None, user_id)
			raise

	# ==================== 市场分析数据方法 ====================

	async def get_market_overview (
			self,
			market: Optional[str] = None,
			target_date: Optional[date] = None,
			indicators: Optional[List[str]] = None,
			user_id: Optional[str] = None
	) -> Dict[str, Any]:
		"""
		获取市场概览数据

		Args:
			market: 市场类型（SH/SZ/BJ，不指定则返回全市场）
			target_date: 日期（默认今天）
			indicators: 需要计算的指标列表，支持：
				- total_stocks: 总股票数量
				- advance_decline: 涨跌家数
				- turnover: 成交数据
				- market_cap: 总市值
				- index_performance: 指数表现
			user_id: 用户ID

		Returns:
			Dict: 市场概览数据，包含以下字段：
				- date: 数据日期
				- market: 市场类型
				- indicators: 指标数据
				- summary: 市场总结
		"""
		logger.info(f"获取市场概览，市场: {market}, 日期: {target_date}")

		try:
			# 设置默认日期
			if not target_date:
				target_date = datetime.now().date()

			# 设置默认指标
			if not indicators:
				indicators = ["total_stocks", "advance_decline", "turnover", "market_cap"]

			# 生成缓存键
			cache_key = CacheKey.MARKET_OVERVIEW.format(
				market=market or "all",
				date=target_date.strftime("%Y%m%d")
			)

			# 尝试从缓存获取
			cached_overview = await self.cache.get(cache_key)
			if cached_overview:
				logger.info(f"从缓存获取市场概览: {market or 'all'}")
				await self._publish_data_access_event(
					"cached_request", None, "market_overview",
					market=market, target_date=target_date.isoformat(),
					user_id=user_id, cached=True
				)
				return cached_overview

			# 初始化结果
			result = {
				"date": target_date.isoformat(),
				"market": market or "all",
				"indicators": {},
				"summary": {}
			}

			# 计算各项指标
			for indicator in indicators:
				try:
					if indicator == "total_stocks":
						count = await self._get_total_stocks(market)
						result["indicators"]["total_stocks"] = count

					elif indicator == "advance_decline":
						ad_data = await self._get_advance_decline(target_date, market)
						result["indicators"]["advance_decline"] = ad_data

					elif indicator == "turnover":
						turnover_data = await self._get_turnover(target_date, market)
						result["indicators"]["turnover"] = turnover_data

					elif indicator == "market_cap":
						market_cap = await self._get_total_market_cap(market)
						result["indicators"]["market_cap"] = market_cap

					elif indicator == "index_performance":
						index_data = self._get_index_performance(market)
						result["indicators"]["index_performance"] = index_data

				except Exception as e:
					logger.error(f"计算指标 {indicator} 失败: {str(e)}")
					result["indicators"][indicator] = {"error": str(e), "status": "error"}

			# 生成市场总结
			result["summary"] = self._generate_market_summary(result["indicators"])

			# 缓存结果
			await self.cache.set(
				cache_key,
				result,
				ttl=3600  # 市场概览缓存1小时
			)

			# 发布数据访问事件
			await self._publish_data_access_event(
				"data_request", None, "market_overview",
				market=market, target_date=target_date.isoformat(),
				user_id=user_id
			)

			logger.info(f"获取市场概览完成，市场: {market}, 日期: {target_date}")
			return result

		except Exception as e:
			logger.error(f"获取市场概览失败: {str(e)}", exc_info=True)
			await self._publish_error_event("market_overview", str(e), None, user_id)
			raise

	async def get_factor_exposure (
			self,
			ts_code: str,
			factor_names: Optional[List[str]] = None,
			start_date: Optional[date] = None,
			end_date: Optional[date] = None,
			user_id: Optional[str] = None
	) -> Dict[str, Any]:
		"""
		获取股票因子暴露度

		Args:
			ts_code: 股票代码
			factor_names: 因子名称列表，不指定则返回所有可用因子
			start_date: 开始日期
			end_date: 结束日期
			user_id: 用户ID

		Returns:
			Dict: 因子暴露度数据，包含以下字段：
				- ts_code: 股票代码
				- date_range: 日期范围
				- factor_exposures: 因子暴露度统计
				- summary: 暴露度总结
		"""
		logger.info(f"获取因子暴露度，股票: {ts_code}, 因子: {factor_names}")

		try:
			# 参数验证
			if not ts_code:
				raise ValueError("股票代码不能为空")

			# 设置默认日期范围
			if not end_date:
				end_date = datetime.now().date()
			if not start_date:
				start_date = end_date - timedelta(days=365)  # 默认一年

			# 验证日期范围
			if start_date > end_date:
				start_date, end_date = end_date, start_date

			# 转换日期为datetime类型
			start_datetime = datetime.combine(start_date, datetime.min.time())
			end_datetime = datetime.combine(end_date, datetime.max.time())

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
						start_date=start_datetime,
						end_date=end_datetime
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
								"count": len(values),
								"data_points": len(factor_data)
							}

							factor_exposures[factor_name] = exposure_stats
					else:
						factor_exposures[factor_name] = {
							"current": None,
							"mean": None,
							"count": 0,
							"data_points": 0,
							"status": "no_data"
						}

				except Exception as e:
					logger.error(f"获取因子 {factor_name} 暴露度失败: {str(e)}")
					factor_exposures[factor_name] = {
						"error": str(e),
						"status": "error"
					}

			# 构建结果
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
			await self._publish_data_access_event(
				"data_request", ts_code, "factor_exposure",
				factor_count=len(factor_exposures),
				user_id=user_id
			)

			logger.info(f"获取因子暴露度完成，股票: {ts_code}, 因子数量: {len(factor_exposures)}")
			return result

		except Exception as e:
			logger.error(f"获取因子暴露度失败: {str(e)}", exc_info=True)
			await self._publish_error_event("factor_exposure", str(e), ts_code, user_id)
			raise

	# ==================== 技术指标计算方法 ====================

	async def calculate_technical_indicators (
			self,
			ts_code: str,
			indicators: List[str],
			start_date: Optional[date] = None,
			end_date: Optional[date] = None,
			parameters: Optional[Dict[str, Any]] = None,
			user_id: Optional[str] = None
	) -> Dict[str, Any]:
		"""
		计算技术指标

		Args:
			ts_code: 股票代码
			indicators: 技术指标列表，支持：
				- MA: 移动平均线
				- EMA: 指数移动平均线
				- MACD: 移动平均收敛发散指标
				- RSI: 相对强弱指数
				- BOLL: 布林带
				- KDJ: 随机指标
			start_date: 开始日期
			end_date: 结束日期
			parameters: 指标参数
			user_id: 用户ID

		Returns:
			Dict: 技术指标计算结果
		"""
		logger.info(f"计算技术指标，股票: {ts_code}, 指标: {indicators}")

		try:
			# 获取历史行情数据
			quotes = await self.get_historical_quotes(
				ts_code=ts_code,
				start_date=start_date,
				end_date=end_date,
				freq="D",
				adj="qfq",
				use_cache=True,
				user_id=user_id
			)

			if not quotes:
				logger.warning(f"未找到行情数据，无法计算技术指标: {ts_code}")
				return {"ts_code": ts_code, "indicators": {}, "message": "No data available"}

			# 转换为DataFrame
			df = pd.DataFrame(quotes)
			df['trade_date'] = pd.to_datetime(df['trade_date'])
			df.set_index('trade_date', inplace=True)
			df.sort_index(inplace=True)

			# 计算技术指标
			results = {}
			for indicator in indicators:
				try:
					if indicator == "MA":
						results["MA"] = self._calculate_ma(df, parameters)
					elif indicator == "EMA":
						results["EMA"] = self._calculate_ema(df, parameters)
					elif indicator == "MACD":
						results["MACD"] = self._calculate_macd(df, parameters)
					elif indicator == "RSI":
						results["RSI"] = _calculate_rsi(df, parameters)
					elif indicator == "BOLL":
						results["BOLL"] = _calculate_boll(df, parameters)
					elif indicator == "KDJ":
						results["KDJ"] = _calculate_kdj(df, parameters)
				except Exception as e:
					logger.error(f"计算指标 {indicator} 失败: {str(e)}")
					results[indicator] = {"error": str(e), "status": "error"}

			return {
				"ts_code": ts_code,
				"date_range": {
					"start": df.index.min().strftime("%Y-%m-%d"),
					"end": df.index.max().strftime("%Y-%m-%d")
				},
				"indicators": results,
				"message": "Technical indicators calculated successfully"
			}

		except Exception as e:
			logger.error(f"计算技术指标失败: {str(e)}", exc_info=True)
			await self._publish_error_event("technical_indicators", str(e), ts_code, user_id)
			raise

	# ==================== 私有辅助方法 ====================

	async def _convert_frequency (
			self,
			daily_quotes: List,
			target_freq: str
	) -> List:
		"""
		转换数据频率

		Args:
			daily_quotes: 日线数据列表
			target_freq: 目标频率

		Returns:
			List: 转换后的数据列表
		"""
		if target_freq == Frequency.DAILY:
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

		# 根据目标频率进行转换
		if target_freq == Frequency.WEEKLY:
			# 转换为周线
			weekly_df = df.resample('W-FRI').agg({
				'open': 'first',
				'high': 'max',
				'low': 'min',
				'close': 'last',
				'vol': 'sum',
				'amount': 'sum'
			})
			weekly_df.dropna(inplace=True)
			return self._df_to_quote_objects(weekly_df)

		elif target_freq == Frequency.MONTHLY:
			# 转换为月线
			monthly_df = df.resample('M').agg({
				'open': 'first',
				'high': 'max',
				'low': 'min',
				'close': 'last',
				'vol': 'sum',
				'amount': 'sum'
			})
			monthly_df.dropna(inplace=True)
			return self._df_to_quote_objects(monthly_df)

		elif target_freq in ["5", "15", "30", "60"]:
			# 转换为分钟线（需要原始分钟数据）
			logger.warning(f"分钟线转换需要原始分钟数据，当前仅支持日线转换")
			return daily_quotes

		return daily_quotes

	def _df_to_quote_objects (self, df: pd.DataFrame) -> List:
		"""
		将DataFrame转换回行情对象列表

		Args:
			df: 包含行情数据的DataFrame

		Returns:
			List: 行情对象列表
		"""
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
		"""
		价格复权处理

		Args:
			quotes: 行情数据列表
			adj_type: 复权类型（qfq/hfq）

		Returns:
			List: 复权后的行情数据
		"""
		if not quotes:
			return quotes

		# 按日期排序（从旧到新）
		sorted_quotes = sorted(quotes, key=lambda x: x.trade_date)

		# 从数据库获取真实复权因子
		adj_factors = {}
		try:
			from sqlalchemy import text

			# 获取区间内所有涉及股票的复权因子
			codes = list(set(getattr(q, 'ts_code', '') for q in sorted_quotes if hasattr(q, 'ts_code')))
			if codes and hasattr(self, 'session'):
				# 使用 IN 子句批量查询
				placeholders = ','.join(f"'{c}'" for c in codes[:500])  # 限制500个
				result = self.session.execute(
					text(
						f"SELECT ts_code, trade_date, adj_factor FROM stock_adj_factor "
						f"WHERE ts_code IN ({placeholders}) ORDER BY trade_date"
					)
				)
				for row in result.fetchall():
					key = (row.ts_code, row.trade_date)
					adj_factors[key] = float(row.adj_factor)
		except Exception as e:
			logger.warning(f"获取复权因子失败，使用不复权数据: {e}")

		for quote in sorted_quotes:
			ts_code = getattr(quote, 'ts_code', '')
			trade_date = getattr(quote, 'trade_date', None)
			factor = adj_factors.get((ts_code, trade_date), 1.0)

			if adj_type == AdjustType.PRE and factor != 1.0:
				if hasattr(quote, 'open') and quote.open:
					quote.open *= factor
				if hasattr(quote, 'high') and quote.high:
					quote.high *= factor
				if hasattr(quote, 'low') and quote.low:
					quote.low *= factor
				if hasattr(quote, 'close') and quote.close:
					quote.close *= factor
				if hasattr(quote, 'pre_close') and quote.pre_close:
					quote.pre_close *= factor
			elif adj_type == AdjustType.POST and factor != 1.0:
				if hasattr(quote, 'open') and quote.open:
					quote.open /= factor
				if hasattr(quote, 'high') and quote.high:
					quote.high /= factor
				if hasattr(quote, 'low') and quote.low:
					quote.low /= factor
				if hasattr(quote, 'close') and quote.close:
					quote.close /= factor
				if hasattr(quote, 'pre_close') and quote.pre_close:
					quote.pre_close /= factor

			if not hasattr(quote, 'adj_factor'):
				quote.adj_factor = factor

		return sorted_quotes

	async def _get_total_stocks (self, market: Optional[str] = None) -> int:
		"""
		获取总股票数量

		Args:
			market: 市场类型

		Returns:
			int: 股票数量
		"""
		from sqlalchemy import select
		query = select(func.count()).select_from(self.stock_repo.model)
		if market is not None:
			query = query.where(self.stock_repo.model.market == market)
		result = await self.stock_repo.session.execute(query)
		return result.scalar()

	async def _get_advance_decline (
			self,
			target_date: date,
			market: Optional[str] = None
	) -> Dict[str, Any]:
		"""
		获取涨跌家数

		Args:
			target_date: 交易日期
			market: 市场类型

		Returns:
			Dict: 涨跌家数统计
		"""
		try:
			# 获取当日所有股票的行情数据
			query = await self._build_quote_query(target_date, market)
			result = await self.quote_repo.session.execute(query)
			quotes = result.scalars().all()

			if not quotes:
				return {
					"advance": 0,
					"decline": 0,
					"unchanged": 0,
					"limit_up": 0,
					"limit_down": 0,
					"total": 0
				}

			# 统计涨跌
			advance = 0
			decline = 0
			unchanged = 0
			limit_up = 0
			limit_down = 0

			for quote in quotes:
				if quote.pct_chg:
					pct_chg = float(quote.pct_chg)
					if pct_chg > 0:
						advance += 1
						if pct_chg >= 9.9:  # 涨停
							limit_up += 1
					elif pct_chg < 0:
						decline += 1
						if pct_chg <= -9.9:  # 跌停
							limit_down += 1
					else:
						unchanged += 1

			return {
				"advance": advance,
				"decline": decline,
				"unchanged": unchanged,
				"limit_up": limit_up,
				"limit_down": limit_down,
				"total": advance + decline + unchanged
			}

		except Exception as e:
			logger.error(f"获取涨跌家数失败: {str(e)}")
			return {
				"advance": 0,
				"decline": 0,
				"unchanged": 0,
				"limit_up": 0,
				"limit_down": 0,
				"total": 0,
				"error": str(e)
			}

	async def _get_turnover (
			self,
			target_date: date,
			market: Optional[str] = None
	) -> Dict[str, Any]:
		"""
		获取成交数据

		Args:
			target_date: 交易日期
			market: 市场类型

		Returns:
			Dict: 成交数据统计
		"""
		try:
			# 构建查询条件
			query = await self._build_quote_query(target_date, market)
			# 获取当日成交数据
			result = await self.quote_repo.session.execute(query)
			quotes = result.scalars().all()

			if not quotes:
				return {
					"total_volume": 0,
					"total_amount": 0,
					"avg_turnover_rate": 0,
					"stock_count": 0
				}

			# 计算总成交额和成交量
			total_volume = sum(float(q.vol) for q in quotes if q.vol)
			total_amount = sum(float(q.amount) for q in quotes if q.amount)

			# 计算平均换手率：优先使用行情数据中的 turnover_rate 字段
			turnover_rates = []
			for q in quotes:
				if hasattr(q, 'turnover_rate') and q.turnover_rate:
					turnover_rates.append(float(q.turnover_rate))
			avg_turnover_rate = sum(turnover_rates) / len(turnover_rates) if turnover_rates else 0

			return {
				"total_volume": round(total_volume, 2),
				"total_amount": round(total_amount, 2),
				"avg_turnover_rate": round(avg_turnover_rate, 4),
				"stock_count": len(quotes)
			}

		except Exception as e:
			logger.error(f"获取成交数据失败: {str(e)}")
			return {
				"total_volume": 0,
				"total_amount": 0,
				"avg_turnover_rate": 0,
				"stock_count": 0,
				"error": str(e)
			}

	async def _get_total_market_cap (self, market: Optional[str] = None) -> float:
		"""
		获取总市值

		Args:
			market: 市场类型

		Returns:
			float: 总市值（亿元）
		"""
		try:
			# 获取所有股票
			kwargs = {}
			if market:
				kwargs["market"] = market

			stocks = await self.stock_repo.get_many(**kwargs)

			if not stocks:
				return 0

			total_market_cap = 0

			for stock in stocks:
				if hasattr(stock, 'market_cap') and stock.market_cap:
					total_market_cap += float(stock.market_cap)

			# 转换为亿元
			return round(total_market_cap / 1e8, 2)

		except Exception as e:
			logger.error(f"获取总市值失败: {str(e)}")
			return 0

	@staticmethod
	async def _get_index_performance (
			market: Optional[str] = None
	) -> Dict[str, Any]:
		"""
		获取指数表现

		Args:
			market: 市场类型

		Returns:
			Dict: 指数表现数据
		"""
		# 从 index_daily 表查询主要指数最新数据
		market_index_map = {
			"SH": ["000001.SH", "000016.SH", "000300.SH"],  # 上证指数、上证50、沪深300
			"SZ": ["399001.SZ", "399006.SZ"],                # 深证成指、创业板指
		}
		name_map = {
			"000001.SH": "上证指数", "000016.SH": "上证50", "000300.SH": "沪深300",
			"399001.SZ": "深证成指", "399006.SZ": "创业板指",
		}
		if market and market in market_index_map:
			index_codes = market_index_map[market]
		else:
			index_codes = ["000001.SH", "000016.SH", "000300.SH", "399001.SZ", "399006.SZ"]

		try:
			from shared.database.session import get_session_manager
			from sqlalchemy import text

			session_manager = get_session_manager()
			async with session_manager.get_session() as session:
				placeholders = ','.join(f"'{c}'" for c in index_codes)
				result = await session.execute(
					text(
						f"SELECT ts_code, close, change, pct_chg FROM index_daily "
						f"WHERE ts_code IN ({placeholders}) "
						f"ORDER BY trade_date DESC LIMIT :limit"
					),
					{"limit": len(index_codes)}
				)
				rows = result.fetchall()

				performance = {}
				for row in rows:
					name = name_map.get(row.ts_code, row.ts_code)
					performance[name] = {
						"close": round(float(row.close), 2) if row.close else None,
						"change": round(float(row.change), 2) if row.change else 0,
						"pct_chg": round(float(row.pct_chg), 2) if row.pct_chg else 0,
					}
				return performance if performance else {}
		except BusinessException as e:
			logger.error(f"获取指数表现失败: {str(e)}")
			return {}

	async def _build_quote_query (self, target_date: date, market: Optional[str] = None):
		"""
		构建行情数据查询

		Args:
			target_date: 交易日期
			market: 市场类型

		Returns:
			Select: SQLAlchemy查询对象
		"""
		from sqlalchemy import select
		query = select(self.quote_repo.model).where(
			self.quote_repo.model.trade_date == target_date  # type: ignore[arg-type]
		)

		if market is not None:
			# 获取该市场的所有股票
			market_query = select(self.stock_repo.model).where(
				self.stock_repo.model.market == market
			)
			market_result = await self.stock_repo.session.execute(market_query)
			market_stocks = market_result.scalars().all()
			ts_codes = [stock.ts_code for stock in market_stocks]
			if ts_codes:
				query = query.where(self.quote_repo.model.ts_code.in_(ts_codes))

		return query

	@staticmethod
	def _generate_market_summary (indicators: Dict) -> Dict[str, Any]:
		"""
		生成市场总结

		Args:
			indicators: 市场指标数据

		Returns:
			Dict: 市场总结
		"""
		summary = {
			"market_status": "normal",
			"sentiment": "neutral",
			"trend": "sideways",
			"risk_level": "medium",
			"timestamp": datetime.now().isoformat()
		}

		# 基于指标生成总结
		if "advance_decline" in indicators:
			ad_data = indicators["advance_decline"]
			if isinstance(ad_data, dict):
				advance = ad_data.get("advance", 0)
				decline = ad_data.get("decline", 0)
				total = ad_data.get("total", 0)

				if total > 0:
					advance_ratio = advance / total
					decline_ratio = decline / total

					if advance_ratio > 0.6:
						summary["sentiment"] = "bullish"
						summary["trend"] = "up"
					elif decline_ratio > 0.6:
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

		# 基于其他指标更新总结
		if "index_performance" in indicators:
			index_data = indicators["index_performance"]
			if isinstance(index_data, dict):
				# 检查主要指数的表现
				positive_count = 0
				total_count = 0

				for index_name, index_info in index_data.items():
					if isinstance(index_info, dict):
						pct_chg = index_info.get("pct_chg", 0)
						if pct_chg > 0:
							positive_count += 1
						total_count += 1

				if total_count > 0:
					positive_ratio = positive_count / total_count
					if positive_ratio >= 0.8:
						summary["sentiment"] = "very_bullish"
					elif positive_ratio >= 0.6:
						summary["sentiment"] = "bullish"
					elif positive_ratio <= 0.2:
						summary["sentiment"] = "very_bearish"
					elif positive_ratio <= 0.4:
						summary["sentiment"] = "bearish"

		return summary

	async def _get_available_factors (self) -> List[str]:
		"""
		获取可用因子列表

		Returns:
			List[str]: 因子名称列表
		"""
		try:
			# 从数据库获取因子定义
			factors = await self.factor_repo.get_available_factors()
			if factors:
				return factors

			# 如果获取失败，返回标准因子列表
			return [
				"PE",  # 市盈率
				"PB",  # 市净率
				"PS",  # 市销率
				"ROE",  # 净资产收益率
				"ROA",  # 总资产收益率
				"GM",  # 毛利率
				"NP_MARGIN",  # 净利率
				"DEBT_TO_ASSET",  # 资产负债率
				"CURRENT_RATIO",  # 流动比率
				"QUICK_RATIO",  # 速动比率
				"MARKET_CAP",  # 市值
				"RETURN_1M",  # 1个月收益率
				"RETURN_3M",  # 3个月收益率
				"RETURN_6M",  # 6个月收益率
				"RETURN_12M",  # 12个月收益率
				"VOLATILITY_1M",  # 1个月波动率
				"VOLATILITY_3M",  # 3个月波动率
				"VOLATILITY_12M",  # 12个月波动率
				"BETA",  # Beta系数
				"SHARPE_RATIO",  # 夏普比率
				"TURNOVER_RATE",  # 换手率
				"VOLUME_RATIO"  # 量比
			]

		except Exception as e:
			logger.error(f"获取可用因子列表失败: {str(e)}")
			return []

	@staticmethod
	def _calculate_percentile (
			value: float,
			values: List[float]
	) -> float:
		"""
		计算百分位数

		Args:
			value: 当前值
			values: 历史值列表

		Returns:
			float: 百分位数（0-100）
		"""
		if not values or value is None:
			return 0

		sorted_values = sorted(values)

		# 计算小于等于当前值的数量
		count_less_equal = sum(1 for v in sorted_values if v <= value)

		# 计算百分位数
		percentile = (count_less_equal / len(sorted_values)) * 100

		return round(percentile, 2)

	@staticmethod
	def _generate_exposure_summary (factor_exposures: Dict) -> Dict[str, Any]:
		"""
		生成因子暴露度总结

		Args:
			factor_exposures: 因子暴露度数据

		Returns:
			Dict: 暴露度总结
		"""
		if not factor_exposures:
			return {
				"note": "无因子暴露度数据",
				"factor_count": 0,
				"timestamp": datetime.now().isoformat()
			}

		# 计算各因子的当前暴露度
		current_exposures = {}
		for factor_name, stats in factor_exposures.items():
			if isinstance(stats, dict) and "current" in stats:
				current_exposures[factor_name] = stats["current"]

		# 找出最大值和最小值
		if current_exposures:
			valid_exposures = {k: v for k, v in current_exposures.items() if v is not None}

			if valid_exposures:
				max_factor = max(valid_exposures.items(), key=lambda x: x[1] if x[1] is not None else -float('inf'))
				min_factor = min(valid_exposures.items(), key=lambda x: x[1] if x[1] is not None else float('inf'))

				# 计算平均值
				valid_values = [v for v in valid_exposures.values() if v is not None]
				avg_exposure = np.mean(valid_values) if valid_values else None

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
					"average_exposure": round(float(avg_exposure), 4) if avg_exposure is not None else None,
					"timestamp": datetime.now().isoformat()
				}

		return {
			"factor_count": len(factor_exposures),
			"note": "无当前暴露度数据",
			"timestamp": datetime.now().isoformat()
		}

	async def _get_financial_summary (self, ts_code: str) -> Dict[str, Any]:
		"""
		获取财务数据摘要

		Args:
			ts_code: 股票代码

		Returns:
			Dict: 财务数据摘要
		"""
		try:
			# 获取最新财务数据
			financial_data = await self.financial_repo.get_latest_by_ts_code(ts_code)

			if not financial_data:
				return {
					"note": "暂无财务数据",
					"status": "no_data"
				}

			# 构建财务摘要
			summary = {
				"report_date": financial_data.report_date.isoformat() if hasattr(financial_data,
																				 'report_date') else None,
				"total_revenue": float(financial_data.total_revenue) if hasattr(financial_data,
																				'total_revenue') else None,
				"net_profit": float(financial_data.net_profit) if hasattr(financial_data, 'net_profit') else None,
				"total_assets": float(financial_data.total_assets) if hasattr(financial_data, 'total_assets') else None,
				"total_liabilities": float(financial_data.total_liabilities) if hasattr(financial_data,
																						'total_liabilities') else None,
				"roe": float(financial_data.roe) if hasattr(financial_data, 'roe') else None,
				"roa": float(financial_data.roa) if hasattr(financial_data, 'roa') else None,
				"gross_margin": float(financial_data.gross_margin) if hasattr(financial_data, 'gross_margin') else None,
				"net_margin": float(financial_data.net_margin) if hasattr(financial_data, 'net_margin') else None,
				"debt_to_asset": float(financial_data.debt_to_asset) if hasattr(financial_data,
																				'debt_to_asset') else None,
				"status": "available",
				"updated_at": financial_data.updated_at.isoformat() if hasattr(financial_data, 'updated_at') else None
			}

			return summary

		except Exception as e:
			logger.error(f"获取财务数据摘要失败: {str(e)}")
			return {
				"note": f"获取财务数据失败: {str(e)}",
				"status": "error"
			}

	# ==================== 技术指标计算方法 ====================

	@staticmethod
	def _calculate_ma (
			df: pd.DataFrame,
			parameters: Optional[Dict[str, Any]] = None
	) -> Dict[str, Any]:
		"""
		计算移动平均线

		Args:
			df: 包含收盘价的DataFrame
			parameters: 计算参数，包含周期列表

		Returns:
			Dict: MA计算结果
		"""
		if 'close' not in df.columns:
			return {"error": "缺少收盘价数据", "status": "error"}

		periods = parameters.get("periods", [5, 10, 20, 30, 60]) if parameters else [5, 10, 20, 30, 60]

		result = {}
		for period in periods:
			if 0 < period <= len(df):
				ma_series = df['close'].rolling(window=period).mean()
				result[f"MA{period}"] = ma_series.tolist()
			else:
				result[f"MA{period}"] = []

		return {
			"periods": periods,
			"values": result,
			"status": "success"
		}

	@staticmethod
	def _calculate_ema (
			df: pd.DataFrame,
			parameters: Optional[Dict[str, Any]] = None
	) -> Dict[str, Any]:
		"""
		计算指数移动平均线

		Args:
			df: 包含收盘价的DataFrame
			parameters: 计算参数，包含周期列表

		Returns:
			Dict: EMA计算结果
		"""
		if 'close' not in df.columns:
			return {"error": "缺少收盘价数据", "status": "error"}

		periods = parameters.get("periods", [12, 26]) if parameters else [12, 26]

		result = {}
		for period in periods:
			if 0 < period <= len(df):
				ema_series = df['close'].ewm(span=period, adjust=False).mean()
				result[f"EMA{period}"] = ema_series.tolist()
			else:
				result[f"EMA{period}"] = []

		return {
			"periods": periods,
			"values": result,
			"status": "success"
		}

	@staticmethod
	def _calculate_macd (
			df: pd.DataFrame,
			parameters: Optional[Dict[str, Any]] = None
	) -> Dict[str, Any]:
		"""
		计算MACD指标

		Args:
			df: 包含收盘价的DataFrame
			parameters: 计算参数，包含快线、慢线、信号线周期

		Returns:
			Dict: MACD计算结果
		"""
		if 'close' not in df.columns:
			return {"error": "缺少收盘价数据", "status": "error"}

		# 默认参数
		fast_period = parameters.get("fast_period", 12) if parameters else 12
		slow_period = parameters.get("slow_period", 26) if parameters else 26
		signal_period = parameters.get("signal_period", 9) if parameters else 9

		if len(df) < slow_period:
			return {
				"error": "数据长度不足",
				"status": "error",
				"required_length": slow_period,
				"actual_length": len(df)
			}

		# 计算EMA
		ema_fast = df['close'].ewm(span=fast_period, adjust=False).mean()
		ema_slow = df['close'].ewm(span=slow_period, adjust=False).mean()

		# 计算DIF
		dif = ema_fast - ema_slow

		# 计算DEA
		dea = dif.ewm(span=signal_period, adjust=False).mean()

		# 计算MACD柱
		macd_bar = (dif - dea) * 2

		return {
			"parameters": {
				"fast_period": fast_period,
				"slow_period": slow_period,
				"signal_period": signal_period
			},
			"values": {
				"DIF": dif.tolist(),
				"DEA": dea.tolist(),
				"MACD": macd_bar.tolist()
			},
			"status": "success"
		}

	# ==================== 事件发布方法 ====================

	async def _publish_data_access_event (
			self,
			event_type: str,
			ts_code: Optional[str] = None,
			data_type: Optional[str] = None,
			record_count: Optional[int] = None,
			market: Optional[str] = None,
			target_date: Optional[str] = None,
			factor_count: Optional[int] = None,
			cached: bool = False,
			user_id: Optional[str] = None
	):
		"""
		发布数据访问事件

		Args:
			event_type: 事件类型
			ts_code: 股票代码
			data_type: 数据类型
			record_count: 记录数量
			market: 市场类型
			target_date: 日期
			factor_count: 因子数量
			cached: 是否从缓存获取
			user_id: 用户ID
		"""
		if not self.event_engine:
			return

		try:
			event_data = {
				"event_type": f"market.data.{event_type}",
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
			if target_date:
				event_data["date"] = target_date
			if factor_count is not None:
				event_data["factor_count"] = factor_count

			# 这里需要创建一个简单的数据请求对象，因为MarketDataRequestEvent需要MarketDataRequest参数
			# 临时创建一个简单的事件对象
			from modules.data.events.types import DataEventType
			from core.events.types import EventPriority, EventCategory

			event_data.update({
				"event_type": DataEventType.MARKET_DATA_REQUEST.value,
				"source": event_data.get("ts_code", "market_service"),
				"module": "data",
				"priority": EventPriority.NORMAL,
				"category": EventCategory.BUSINESS
			})

			event = _MarketDataNotificationEvent(event_data)
			await self.event_engine.put(event)

		except Exception as e:
			logger.error(f"发布数据访问事件失败: {str(e)}")

	async def _publish_error_event (
			self,
			data_type: str,
			error_message: str,
			ts_code: Optional[str] = None,
			user_id: Optional[str] = None
	):
		"""
		发布错误事件

		Args:
			data_type: 数据类型
			error_message: 错误信息
			ts_code: 股票代码
			user_id: 用户ID
		"""
		if not self.event_engine:
			return

		try:
			event_data = {
				"event_type": "market.data.error",
				"timestamp": datetime.now(),
				"data_type": data_type,
				"error_message": error_message,
				"user_id": user_id
			}

			if ts_code:
				event_data["ts_code"] = ts_code

			# 使用简单的事件对象
			from modules.data.events.types import DataEventType
			from core.events.types import EventPriority, EventCategory

			event_data.update({
				"event_type": DataEventType.MARKET_DATA_REQUEST.value,
				"source": event_data.get("ts_code", "market_service"),
				"module": "data",
				"priority": EventPriority.NORMAL,
				"category": EventCategory.BUSINESS
			})
			event = _MarketDataNotificationEvent(event_data)
			await self.event_engine.put(event)

		except Exception as e:
			logger.error(f"发布错误事件失败: {str(e)}")