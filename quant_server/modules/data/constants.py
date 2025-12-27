"""
数据模块 - 常量定义
定义数据模块使用的所有常量，包括配置、状态码、默认值等
位置：quant_server/modules/data/constants.py

设计原则：
1. 统一管理：所有常量集中管理，避免硬编码
2. 分类清晰：按功能模块分类定义常量
3. 类型明确：使用合适的数据类型定义常量
4. 文档完整：每个常量都有清晰的注释说明
"""

from enum import Enum, IntEnum
from datetime import time


# ==================== 模块配置常量 ====================

class ModuleConfig:
	"""模块配置常量"""

	# 模块名称
	MODULE_NAME = "data"

	# 模块版本
	MODULE_VERSION = "1.0.0"

	# 默认分页大小
	DEFAULT_PAGE_SIZE = 20

	# 最大分页大小
	MAX_PAGE_SIZE = 1000

	# 默认同步任务超时时间（秒）
	DEFAULT_SYNC_TIMEOUT = 3600  # 1小时

	# 数据质量检查默认阈值
	QUALITY_THRESHOLDS = {
		"completeness": 95.0,  # 完整率阈值
		"accuracy": 99.0,  # 准确率阈值
		"timeliness": 90.0  # 及时性阈值
	}

	# 缓存过期时间（秒）
	CACHE_TTL = {
		"stock_list": 3600,  # 1小时
		"stock_detail": 300,  # 5分钟
		"historical_quotes": 600,  # 10分钟
		"factor_data": 1800,  # 30分钟
		"data_quality": 7200  # 2小时
	}

	# API请求限制
	API_RATE_LIMITS = {
		"default": "100/hour",
		"sync": "10/hour",
		"research": "5/hour"
	}

	# 数据源优先级
	DATA_SOURCE_PRIORITY = {
		"tushare": 1,  # 主数据源
		"baostock": 2,  # 备用数据源1
		"sina": 3,  # 备用数据源2
		"eastmoney": 4  # 备用数据源3
	}


# ==================== 数据同步常量 ====================

class SyncStatus(IntEnum):
	"""同步状态枚举"""
	PENDING = 0  # 等待中
	RUNNING = 1  # 运行中
	COMPLETED = 2  # 已完成
	FAILED = 3  # 失败
	CANCELLED = 4  # 已取消
	PAUSED = 5  # 已暂停

	@classmethod
	def get_display_name (cls, status):
		"""获取状态显示名称"""
		display_names = {
			cls.PENDING: "等待中",
			cls.RUNNING: "运行中",
			cls.COMPLETED: "已完成",
			cls.FAILED: "失败",
			cls.CANCELLED: "已取消",
			cls.PAUSED: "已暂停"
		}
		return display_names.get(status, "未知状态")


class SyncErrorCode(IntEnum):
	"""同步错误码枚举"""
	NO_ERROR = 0  # 无错误
	DATABASE_ERROR = 1001  # 数据库错误
	NETWORK_ERROR = 1002  # 网络错误
	API_ERROR = 1003  # API接口错误
	DATA_VALIDATION_ERROR = 1004  # 数据验证错误
	TIMEOUT_ERROR = 1005  # 超时错误
	RATE_LIMIT_ERROR = 1006  # 频率限制错误
	AUTHENTICATION_ERROR = 1007  # 认证错误
	INSUFFICIENT_DATA = 1008  # 数据不足
	UNKNOWN_ERROR = 1999  # 未知错误

	@classmethod
	def get_error_message (cls, error_code):
		"""获取错误信息"""
		error_messages = {
			cls.NO_ERROR: "操作成功",
			cls.DATABASE_ERROR: "数据库操作失败",
			cls.NETWORK_ERROR: "网络连接失败",
			cls.API_ERROR: "外部API接口错误",
			cls.DATA_VALIDATION_ERROR: "数据验证失败",
			cls.TIMEOUT_ERROR: "操作超时",
			cls.RATE_LIMIT_ERROR: "访问频率超限",
			cls.AUTHENTICATION_ERROR: "认证失败",
			cls.INSUFFICIENT_DATA: "数据不足",
			cls.UNKNOWN_ERROR: "未知错误"
		}
		return error_messages.get(error_code, "未知错误")


class SyncConfig:
	"""同步配置常量"""

	# 重试配置
	MAX_RETRIES = 3  # 最大重试次数
	RETRY_DELAY = 5  # 重试延迟（秒）
	RETRY_BACKOFF_FACTOR = 2  # 重试退避因子

	# 批量处理配置
	BATCH_SIZE = {
		"stock_list": 1000,  # 股票列表批量大小
		"daily_quotes": 500,  # 日行情批量大小
		"financial_data": 100,  # 财务数据批量大小
		"index_data": 50  # 指数数据批量大小
	}

	# 超时配置（秒）
	TIMEOUT = {
		"stock_list": 300,  # 股票列表同步超时
		"daily_quotes": 1800,  # 日行情同步超时
		"financial_data": 1200,  # 财务数据同步超时
		"index_data": 600  # 指数数据同步超时
	}

	# 同步时间窗口
	SYNC_TIME_WINDOWS = {
		"normal": (time(0, 0), time(23, 59)),  # 正常时段：全天
		"peak": (time(9, 15), time(11, 30)),  # 高峰期：上午交易时段
		"off_peak": (time(13, 0), time(15, 0)),  # 次高峰期：下午交易时段
		"maintenance": (time(2, 0), time(4, 0))  # 维护窗口：凌晨
	}


# ==================== 数据源常量 ====================

class DataSource:
	"""数据源常量"""

	# 数据源名称
	TUSHARE = "tushare"
	BAOSTOCK = "baostock"
	SINA = "sina"
	EASTMONEY = "eastmoney"
	YAHOO = "yahoo"

	# 数据源状态
	STATUS_ACTIVE = "active"  # 活跃
	STATUS_INACTIVE = "inactive"  # 不活跃
	STATUS_DEPRECATED = "deprecated"  # 已弃用

	# 数据源优先级权重
	PRIORITY_WEIGHTS = {
		TUSHARE: 1.0,
		BAOSTOCK: 0.8,
		SINA: 0.6,
		EASTMONEY: 0.7,
		YAHOO: 0.5
	}

	# 数据源支持的数据类型
	SUPPORTED_DATA_TYPES = {
		TUSHARE: ["stock_list", "daily_quotes", "financial_data", "index_data", "calendar"],
		BAOSTOCK: ["daily_quotes", "financial_data", "index_data"],
		SINA: ["realtime_quotes"],
		EASTMONEY: ["financial_data", "holders_data"],
		YAHOO: ["daily_quotes", "historical_quotes"]
	}


class DataType:
	"""数据类型常量"""

	# 基础数据
	STOCK_LIST = "stock_list"  # 股票列表
	DAILY_QUOTES = "daily_quotes"  # 日行情
	REALTIME_QUOTES = "realtime_quotes"  # 实时行情
	ADJUSTED_QUOTES = "adjusted_quotes"  # 复权行情
	FINANCIAL_DATA = "financial_data"  # 财务数据
	INDEX_DATA = "index_data"  # 指数数据
	CALENDAR = "calendar"  # 交易日历

	# 扩展数据
	HOLDERS_DATA = "holders_data"  # 股东数据
	DIVIDEND_DATA = "dividend_data"  # 分红数据
	SPLIT_DATA = "split_data"  # 拆分数据
	INDUSTRY_DATA = "industry_data"  # 行业数据
	CONCEPT_DATA = "concept_data"  # 概念数据

	# 因子数据
	FACTOR_DATA = "factor_data"  # 因子数据
	ALPHA_FACTORS = "alpha_factors"  # Alpha因子
	RISK_FACTORS = "risk_factors"  # 风险因子
	STYLE_FACTORS = "style_factors"  # 风格因子

	@classmethod
	def get_display_name (cls, data_type):
		"""获取数据类型显示名称"""
		display_names = {
			cls.STOCK_LIST: "股票列表",
			cls.DAILY_QUOTES: "日行情数据",
			cls.REALTIME_QUOTES: "实时行情",
			cls.ADJUSTED_QUOTES: "复权行情",
			cls.FINANCIAL_DATA: "财务数据",
			cls.INDEX_DATA: "指数数据",
			cls.CALENDAR: "交易日历",
			cls.FACTOR_DATA: "因子数据"
		}
		return display_names.get(data_type, data_type)


# ==================== 市场常量 ====================

class MarketCode:
	"""市场代码常量"""

	# A股市场
	SSE = "SSE"  # 上海证券交易所
	SZSE = "SZSE"  # 深圳证券交易所
	BJSE = "BJSE"  # 北京证券交易所

	# 其他市场
	HKEX = "HKEX"  # 香港交易所
	NYSE = "NYSE"  # 纽约证券交易所
	NASDAQ = "NASDAQ"  # 纳斯达克

	@classmethod
	def get_market_name (cls, market_code):
		"""获取市场名称"""
		market_names = {
			cls.SSE: "上海证券交易所",
			cls.SZSE: "深圳证券交易所",
			cls.BJSE: "北京证券交易所",
			cls.HKEX: "香港交易所",
			cls.NYSE: "纽约证券交易所",
			cls.NASDAQ: "纳斯达克"
		}
		return market_names.get(market_code, "未知市场")

	@classmethod
	def get_all_a_markets (cls):
		"""获取所有A股市场代码"""
		return [cls.SSE, cls.SZSE, cls.BJSE]


class StockStatus:
	"""股票状态常量"""

	# 上市状态
	LISTED = "L"  # 上市
	DELISTED = "D"  # 退市
	SUSPENDED = "P"  # 暂停上市
	TRANSFER = "T"  # 转板

	# 交易状态
	TRADING = "交易"  # 可交易
	HALTED = "停牌"  # 停牌
	DELISTING = "退市"  # 退市中

	@classmethod
	def get_status_display (cls, status_code):
		"""获取状态显示名称"""
		status_display = {
			cls.LISTED: "上市",
			cls.DELISTED: "退市",
			cls.SUSPENDED: "暂停上市",
			cls.TRANSFER: "转板",
			cls.TRADING: "可交易",
			cls.HALTED: "停牌",
			cls.DELISTING: "退市中"
		}
		return status_display.get(status_code, "未知状态")


# ==================== 数据质量常量 ====================

class QualityMetricCode:
	"""质量指标代码"""

	# 完整性指标
	COMPLETENESS_RATE = "completeness_rate"  # 完整率
	MISSING_RATE = "missing_rate"  # 缺失率
	DUPLICATE_RATE = "duplicate_rate"  # 重复率

	# 准确性指标
	ACCURACY_RATE = "accuracy_rate"  # 准确率
	OUTLIER_RATE = "outlier_rate"  # 异常值率
	CONSISTENCY_SCORE = "consistency_score"  # 一致性得分

	# 及时性指标
	TIMELINESS_SCORE = "timeliness_score"  # 及时性得分
	LATENCY_AVG = "latency_avg"  # 平均延迟
	FRESHNESS_SCORE = "freshness_score"  # 新鲜度得分

	@classmethod
	def get_metric_name (cls, metric_code):
		"""获取指标名称"""
		metric_names = {
			cls.COMPLETENESS_RATE: "数据完整率",
			cls.MISSING_RATE: "数据缺失率",
			cls.DUPLICATE_RATE: "数据重复率",
			cls.ACCURACY_RATE: "数据准确率",
			cls.OUTLIER_RATE: "异常值率",
			cls.CONSISTENCY_SCORE: "一致性得分",
			cls.TIMELINESS_SCORE: "及时性得分",
			cls.LATENCY_AVG: "平均延迟",
			cls.FRESHNESS_SCORE: "新鲜度得分"
		}
		return metric_names.get(metric_code, metric_code)


class QualityLevelThreshold:
	"""质量等级阈值"""

	# 质量评分阈值
	EXCELLENT_MIN = 95.0  # 优秀：>=95分
	GOOD_MIN = 85.0  # 良好：85-94分
	FAIR_MIN = 70.0  # 一般：70-84分
	POOR_MAX = 70.0  # 差：<70分

	# 各指标权重
	METRIC_WEIGHTS = {
		QualityMetricCode.COMPLETENESS_RATE: 0.4,  # 完整率权重40%
		QualityMetricCode.ACCURACY_RATE: 0.3,  # 准确率权重30%
		QualityMetricCode.TIMELINESS_SCORE: 0.2,  # 及时性权重20%
		QualityMetricCode.CONSISTENCY_SCORE: 0.1  # 一致性权重10%
	}

	@classmethod
	def get_quality_level (cls, score):
		"""根据评分获取质量等级"""
		if score >= cls.EXCELLENT_MIN:
			return "excellent"
		elif score >= cls.GOOD_MIN:
			return "good"
		elif score >= cls.FAIR_MIN:
			return "fair"
		else:
			return "poor"


# ==================== 因子常量 ====================

class FactorCategoryCode:
	"""因子类别代码"""

	# 常用因子类别
	VALUE = "value"  # 价值因子
	GROWTH = "growth"  # 成长因子
	QUALITY = "quality"  # 质量因子
	MOMENTUM = "momentum"  # 动量因子
	VOLATILITY = "volatility"  # 波动率因子
	SIZE = "size"  # 规模因子
	LIQUIDITY = "liquidity"  # 流动性因子
	TECHNICAL = "technical"  # 技术因子
	SENTIMENT = "sentiment"  # 情绪因子

	@classmethod
	def get_category_name (cls, category_code):
		"""获取类别名称"""
		category_names = {
			cls.VALUE: "价值因子",
			cls.GROWTH: "成长因子",
			cls.QUALITY: "质量因子",
			cls.MOMENTUM: "动量因子",
			cls.VOLATILITY: "波动率因子",
			cls.SIZE: "规模因子",
			cls.LIQUIDITY: "流动性因子",
			cls.TECHNICAL: "技术因子",
			cls.SENTIMENT: "情绪因子"
		}
		return category_names.get(category_code, category_code)


class StandardFactors:
	"""标准因子定义"""

	# 价值因子
	PE = "PE"  # 市盈率
	PB = "PB"  # 市净率
	PS = "PS"  # 市销率
	PC = "PC"  # 市现率
	DIVIDEND_YIELD = "DY"  # 股息率

	# 成长因子
	REVENUE_GROWTH = "RG"  # 营收增长率
	PROFIT_GROWTH = "PG"  # 利润增长率
	EPS_GROWTH = "EG"  # 每股收益增长率
	ASSET_GROWTH = "AG"  # 资产增长率

	# 质量因子
	ROE = "ROE"  # 净资产收益率
	ROA = "ROA"  # 总资产收益率
	GROSS_MARGIN = "GM"  # 毛利率
	OPERATING_MARGIN = "OM"  # 营业利润率
	DEBT_RATIO = "DR"  # 资产负债率

	# 动量因子
	RET_1M = "RET_1M"  # 1个月收益率
	RET_3M = "RET_3M"  # 3个月收益率
	RET_6M = "RET_6M"  # 6个月收益率
	RET_12M = "RET_12M"  # 12个月收益率

	# 波动率因子
	VOLATILITY_1M = "VOL_1M"  # 1个月波动率
	VOLATILITY_3M = "VOL_3M"  # 3个月波动率
	VOLATILITY_12M = "VOL_12M"  # 12个月波动率
	BETA = "BETA"  # Beta系数

	# 规模因子
	MARKET_CAP = "MC"  # 市值
	FLOAT_MARKET_CAP = "FMC"  # 流通市值
	TOTAL_ASSETS = "TA"  # 总资产

	# 流动性因子
	TURNOVER_RATE = "TR"  # 换手率
	TRADING_VOLUME = "TV"  # 交易量
	AMIHUD_ILLIQUIDITY = "AI"  # Amihud非流动性指标

	@classmethod
	def get_factor_name (cls, factor_code):
		"""获取因子名称"""
		factor_names = {
			cls.PE: "市盈率",
			cls.PB: "市净率",
			cls.PS: "市销率",
			cls.PC: "市现率",
			cls.DIVIDEND_YIELD: "股息率",
			cls.ROE: "净资产收益率",
			cls.ROA: "总资产收益率",
			cls.MARKET_CAP: "市值",
			cls.TURNOVER_RATE: "换手率",
			cls.RET_1M: "1个月收益率",
			cls.VOLATILITY_1M: "1个月波动率"
		}
		return factor_names.get(factor_code, factor_code)

	@classmethod
	def get_factor_category (cls, factor_code):
		"""获取因子类别"""
		factor_categories = {
			# 价值因子
			cls.PE: FactorCategoryCode.VALUE,
			cls.PB: FactorCategoryCode.VALUE,
			cls.PS: FactorCategoryCode.VALUE,
			cls.PC: FactorCategoryCode.VALUE,
			cls.DIVIDEND_YIELD: FactorCategoryCode.VALUE,

			# 成长因子
			cls.REVENUE_GROWTH: FactorCategoryCode.GROWTH,
			cls.PROFIT_GROWTH: FactorCategoryCode.GROWTH,
			cls.EPS_GROWTH: FactorCategoryCode.GROWTH,
			cls.ASSET_GROWTH: FactorCategoryCode.GROWTH,

			# 质量因子
			cls.ROE: FactorCategoryCode.QUALITY,
			cls.ROA: FactorCategoryCode.QUALITY,
			cls.GROSS_MARGIN: FactorCategoryCode.QUALITY,
			cls.OPERATING_MARGIN: FactorCategoryCode.QUALITY,
			cls.DEBT_RATIO: FactorCategoryCode.QUALITY,

			# 动量因子
			cls.RET_1M: FactorCategoryCode.MOMENTUM,
			cls.RET_3M: FactorCategoryCode.MOMENTUM,
			cls.RET_6M: FactorCategoryCode.MOMENTUM,
			cls.RET_12M: FactorCategoryCode.MOMENTUM,

			# 波动率因子
			cls.VOLATILITY_1M: FactorCategoryCode.VOLATILITY,
			cls.VOLATILITY_3M: FactorCategoryCode.VOLATILITY,
			cls.VOLATILITY_12M: FactorCategoryCode.VOLATILITY,
			cls.BETA: FactorCategoryCode.VOLATILITY,

			# 规模因子
			cls.MARKET_CAP: FactorCategoryCode.SIZE,
			cls.FLOAT_MARKET_CAP: FactorCategoryCode.SIZE,
			cls.TOTAL_ASSETS: FactorCategoryCode.SIZE,

			# 流动性因子
			cls.TURNOVER_RATE: FactorCategoryCode.LIQUIDITY,
			cls.TRADING_VOLUME: FactorCategoryCode.LIQUIDITY,
			cls.AMIHUD_ILLIQUIDITY: FactorCategoryCode.LIQUIDITY
		}
		return factor_categories.get(factor_code, FactorCategoryCode.TECHNICAL)


# ==================== 错误码常量 ====================

class ErrorCode:
	"""错误码常量"""

	# 通用错误 (10000-19999)
	SUCCESS = 10000  # 成功
	UNKNOWN_ERROR = 10001  # 未知错误
	PARAMETER_ERROR = 10002  # 参数错误
	PERMISSION_DENIED = 10003  # 权限不足
	RESOURCE_NOT_FOUND = 10004  # 资源不存在
	RESOURCE_EXISTS = 10005  # 资源已存在
	DATABASE_ERROR = 10006  # 数据库错误
	NETWORK_ERROR = 10007  # 网络错误
	TIMEOUT_ERROR = 10008  # 超时错误

	# 数据模块错误 (20000-29999)
	DATA_SYNC_ERROR = 20001  # 数据同步错误
	DATA_VALIDATION_ERROR = 20002  # 数据验证错误
	DATA_QUALITY_ERROR = 20003  # 数据质量错误
	DATA_SOURCE_ERROR = 20004  # 数据源错误
	DATA_NOT_FOUND = 20005  # 数据不存在
	DATA_FORMAT_ERROR = 20006  # 数据格式错误
	DATA_OVERWRITE_ERROR = 20007  # 数据覆盖错误

	# 因子模块错误 (30000-39999)
	FACTOR_CALCULATION_ERROR = 30001  # 因子计算错误
	FACTOR_VALIDATION_ERROR = 30002  # 因子验证错误
	FACTOR_DATA_MISSING = 30003  # 因子数据缺失
	FACTOR_RESEARCH_ERROR = 30004  # 因子研究错误

	@classmethod
	def get_error_message (cls, error_code):
		"""获取错误信息"""
		error_messages = {
			# 通用错误
			cls.SUCCESS: "操作成功",
			cls.UNKNOWN_ERROR: "未知错误",
			cls.PARAMETER_ERROR: "参数错误",
			cls.PERMISSION_DENIED: "权限不足",
			cls.RESOURCE_NOT_FOUND: "资源不存在",
			cls.RESOURCE_EXISTS: "资源已存在",
			cls.DATABASE_ERROR: "数据库错误",
			cls.NETWORK_ERROR: "网络错误",
			cls.TIMEOUT_ERROR: "操作超时",

			# 数据模块错误
			cls.DATA_SYNC_ERROR: "数据同步失败",
			cls.DATA_VALIDATION_ERROR: "数据验证失败",
			cls.DATA_QUALITY_ERROR: "数据质量检查失败",
			cls.DATA_SOURCE_ERROR: "数据源错误",
			cls.DATA_NOT_FOUND: "数据不存在",
			cls.DATA_FORMAT_ERROR: "数据格式错误",
			cls.DATA_OVERWRITE_ERROR: "数据覆盖失败",

			# 因子模块错误
			cls.FACTOR_CALCULATION_ERROR: "因子计算失败",
			cls.FACTOR_VALIDATION_ERROR: "因子验证失败",
			cls.FACTOR_DATA_MISSING: "因子数据缺失",
			cls.FACTOR_RESEARCH_ERROR: "因子研究失败"
		}
		return error_messages.get(error_code, "未知错误")


# ==================== 日期时间常量 ====================

class DateTimeFormat:
	"""日期时间格式常量"""

	# 日期格式
	DATE_FORMAT = "%Y-%m-%d"  # 标准日期格式
	DATE_COMPACT = "%Y%m%d"  # 紧凑日期格式
	DATE_DISPLAY = "%Y年%m月%d日"  # 显示日期格式

	# 时间格式
	TIME_FORMAT = "%H:%M:%S"  # 标准时间格式
	TIME_COMPACT = "%H%M%S"  # 紧凑时间格式

	# 日期时间格式
	DATETIME_FORMAT = "%Y-%m-%d %H:%M:%S"  # 标准日期时间格式
	DATETIME_COMPACT = "%Y%m%d%H%M%S"  # 紧凑日期时间格式
	DATETIME_ISO = "%Y-%m-%dT%H:%M:%S"  # ISO格式
	DATETIME_ISO_WITH_TZ = "%Y-%m-%dT%H:%M:%S%z"  # 带时区ISO格式

	@classmethod
	def get_format (cls, format_name):
		"""获取格式字符串"""
		formats = {
			"date": cls.DATE_FORMAT,
			"date_compact": cls.DATE_COMPACT,
			"date_display": cls.DATE_DISPLAY,
			"time": cls.TIME_FORMAT,
			"time_compact": cls.TIME_COMPACT,
			"datetime": cls.DATETIME_FORMAT,
			"datetime_compact": cls.DATETIME_COMPACT,
			"datetime_iso": cls.DATETIME_ISO,
			"datetime_iso_tz": cls.DATETIME_ISO_WITH_TZ
		}
		return formats.get(format_name, cls.DATETIME_FORMAT)


class TradingTime:
	"""交易时间常量（A股）"""

	# 上午交易时段
	MORNING_START = time(9, 15)  # 上午开盘
	MORNING_END = time(11, 30)  # 上午收盘

	# 下午交易时段
	AFTERNOON_START = time(13, 0)  # 下午开盘
	AFTERNOON_END = time(15, 0)  # 下午收盘

	# 集合竞价时间
	CALL_AUCTION_AM = time(9, 15)  # 上午集合竞价
	CALL_AUCTION_PM = time(13, 0)  # 下午集合竞价

	@classmethod
	def is_trading_time (cls, check_time):
		"""判断是否为交易时间"""
		time_obj = check_time.time() if hasattr(check_time, 'time') else check_time

		# 上午交易时段
		if cls.MORNING_START <= time_obj <= cls.MORNING_END:
			return True

		# 下午交易时段
		if cls.AFTERNOON_START <= time_obj <= cls.AFTERNOON_END:
			return True

		return False


# ==================== 表名常量 ====================

class TableName:
	"""数据库表名常量"""

	# 股票相关表
	STOCKS = "stocks"  # 股票基本信息
	STOCK_BASIC = "stock_basic"  # 股票基础信息
	STOCK_COMPANY = "stock_company"  # 上市公司信息

	# 行情相关表
	DAILY_QUOTES = "daily_quotes"  # 日行情数据
	ADJUSTED_QUOTES = "adjusted_quotes"  # 复权行情数据
	REAL_TIME_QUOTES = "real_time_quotes"  # 实时行情数据
	MINUTE_QUOTES = "minute_quotes"  # 分钟行情数据

	# 财务相关表
	FINANCIAL_DATA = "financial_data"  # 财务数据
	INCOME_STATEMENT = "income_statement"  # 利润表
	BALANCE_SHEET = "balance_sheet"  # 资产负债表
	CASH_FLOW_STATEMENT = "cash_flow_statement"  # 现金流量表

	# 因子相关表
	FACTOR_DATA = "factor_data"  # 因子数据
	FACTOR_DEFINITION = "factor_definition"  # 因子定义
	FACTOR_RESEARCH = "factor_research"  # 因子研究

	# 同步相关表
	SYNC_TASKS = "sync_tasks"  # 同步任务
	SYNC_LOGS = "sync_logs"  # 同步日志
	DATA_QUALITY = "data_quality"  # 数据质量

	# 系统相关表
	DATA_SOURCES = "data_sources"  # 数据源配置
	API_KEYS = "api_keys"  # API密钥
	USER_PREFERENCES = "user_preferences"  # 用户偏好


# ==================== API常量 ====================

class APIPath:
	"""API路径常量"""

	# 数据模块API
	DATA_PREFIX = "/api/data"

	# 基础数据查询
	STOCKS = "/stocks"  # 股票列表
	STOCK_DETAIL = "/stocks/{ts_code}"  # 股票详情
	HISTORICAL_QUOTES = "/quotes/historical"  # 历史行情

	# 数据同步
	BATCH_SYNC = "/sync/batch"  # 批量同步
	QUICK_SYNC = "/sync/quick"  # 快速同步
	SYNC_STATUS = "/sync/status"  # 同步状态
	CANCEL_SYNC = "/sync/{task_id}/cancel"  # 取消同步

	# 数据质量
	DATA_QUALITY = "/quality"  # 数据质量

	# 因子数据
	FACTOR_DATA = "/factors"  # 因子数据
	FACTOR_RESEARCH = "/factors/research"  # 因子研究

	# 健康检查
	HEALTH_CHECK = "/health"  # 健康检查
	STATISTICS = "/statistics"  # 数据统计

	# WebSocket
	WS_SUBSCRIBE = "/events/subscribe"  # 事件订阅

	@classmethod
	def get_full_path (cls, path_key):
		"""获取完整的API路径"""
		paths = {
			"stocks": cls.DATA_PREFIX + cls.STOCKS,
			"stock_detail": cls.DATA_PREFIX + cls.STOCK_DETAIL,
			"historical_quotes": cls.DATA_PREFIX + cls.HISTORICAL_QUOTES,
			"batch_sync": cls.DATA_PREFIX + cls.BATCH_SYNC,
			"quick_sync": cls.DATA_PREFIX + cls.QUICK_SYNC,
			"sync_status": cls.DATA_PREFIX + cls.SYNC_STATUS,
			"cancel_sync": cls.DATA_PREFIX + cls.CANCEL_SYNC,
			"data_quality": cls.DATA_PREFIX + cls.DATA_QUALITY,
			"factor_data": cls.DATA_PREFIX + cls.FACTOR_DATA,
			"factor_research": cls.DATA_PREFIX + cls.FACTOR_RESEARCH,
			"health_check": cls.DATA_PREFIX + cls.HEALTH_CHECK,
			"statistics": cls.DATA_PREFIX + cls.STATISTICS,
			"subscribe": cls.DATA_PREFIX + cls.WS_SUBSCRIBE
		}
		return paths.get(path_key, "")


# ==================== 缓存键常量 ====================

class CacheKey:
	"""缓存键常量"""

	# 键前缀
	PREFIX = "data:"

	# 股票相关
	STOCK_LIST = PREFIX + "stock_list:{hash}"  # 股票列表缓存
	STOCK_DETAIL = PREFIX + "stock:{ts_code}:{fields}"  # 股票详情缓存
	STOCK_BASIC = PREFIX + "stock_basic:{ts_code}"  # 股票基础信息缓存

	# 行情相关
	HISTORICAL_QUOTES = PREFIX + "quotes:{ts_code}:{start}:{end}:{freq}:{adj}"  # 历史行情缓存
	LATEST_QUOTE = PREFIX + "latest:{ts_code}"  # 最新行情缓存

	# 同步相关
	SYNC_STATUS = PREFIX + "sync:status:{task_id}"  # 同步状态缓存
	SYNC_PROGRESS = PREFIX + "sync:progress:{task_id}"  # 同步进度缓存

	# 因子相关
	FACTOR_DATA = PREFIX + "factor:{ts_code}:{factor}:{start}:{end}"  # 因子数据缓存
	FACTOR_METADATA = PREFIX + "factor:metadata:{factor}"  # 因子元数据缓存

	# 数据质量
	DATA_QUALITY = PREFIX + "quality:{data_type}:{start}:{end}"  # 数据质量缓存

	# 锁键
	SYNC_LOCK = PREFIX + "lock:sync:{data_type}"  # 同步锁
	FACTOR_LOCK = PREFIX + "lock:factor:{factor}"  # 因子计算锁

	@classmethod
	def generate_stock_list_key (cls, params_hash):
		"""生成股票列表缓存键"""
		return cls.STOCK_LIST.format(hash=params_hash)

	@classmethod
	def generate_historical_quotes_key (cls, ts_code, start_date, end_date, frequency, adjust):
		"""生成历史行情缓存键"""
		return cls.HISTORICAL_QUOTES.format(
			ts_code=ts_code,
			start=start_date,
			end=end_date,
			freq=frequency,
			adj=adjust
		)


# ==================== 事件常量 ====================

class EventType:
	"""事件类型常量"""

	# 数据同步事件
	DATA_SYNC_STARTED = "data.sync.started"  # 数据同步开始
	DATA_SYNC_PROGRESS = "data.sync.progress"  # 数据同步进度
	DATA_SYNC_COMPLETED = "data.sync.completed"  # 数据同步完成
	DATA_SYNC_FAILED = "data.sync.failed"  # 数据同步失败
	DATA_SYNC_CANCELLED = "data.sync.cancelled"  # 数据同步取消

	# 数据质量事件
	DATA_QUALITY_ALERT = "data.quality.alert"  # 数据质量警报
	DATA_QUALITY_REPORT = "data.quality.report"  # 数据质量报告

	# 因子事件
	FACTOR_UPDATE_STARTED = "factor.update.started"  # 因子更新开始
	FACTOR_UPDATE_COMPLETED = "factor.update.completed"  # 因子更新完成
	FACTOR_RESEARCH_STARTED = "factor.research.started"  # 因子研究开始
	FACTOR_RESEARCH_COMPLETED = "factor.research.completed"  # 因子研究完成

	# 系统事件
	DATA_MODULE_STARTED = "data.module.started"  # 数据模块启动
	DATA_MODULE_STOPPED = "data.module.stopped"  # 数据模块停止
	DATA_MODULE_ERROR = "data.module.error"  # 数据模块错误

	@classmethod
	def is_sync_event (cls, event_type):
		"""判断是否为同步事件"""
		return event_type.startswith("data.sync.")

	@classmethod
	def is_quality_event (cls, event_type):
		"""判断是否为质量事件"""
		return event_type.startswith("data.quality.")

	@classmethod
	def is_factor_event (cls, event_type):
		"""判断是否为因子事件"""
		return event_type.startswith("factor.")


# ==================== 权限常量 ====================

class Permission:
	"""权限常量"""

	# 数据查看权限
	VIEW_STOCK_LIST = "data:stock:view"  # 查看股票列表
	VIEW_STOCK_DETAIL = "data:stock:detail"  # 查看股票详情
	VIEW_HISTORICAL_QUOTES = "data:quotes:view"  # 查看历史行情
	VIEW_FACTOR_DATA = "data:factor:view"  # 查看因子数据

	# 数据操作权限
	SYNC_DATA = "data:sync"  # 同步数据
	CANCEL_SYNC = "data:sync:cancel"  # 取消同步
	MANUAL_UPDATE = "data:update:manual"  # 手动更新数据
	DELETE_DATA = "data:delete"  # 删除数据

	# 数据质量权限
	CHECK_QUALITY = "data:quality:check"  # 检查数据质量
	EXPORT_QUALITY_REPORT = "data:quality:export"  # 导出质量报告
	FIX_DATA_ISSUES = "data:quality:fix"  # 修复数据问题

	# 因子研究权限
	RESEARCH_FACTOR = "data:factor:research"  # 因子研究
	CREATE_FACTOR = "data:factor:create"  # 创建因子
	EDIT_FACTOR = "data:factor:edit"  # 编辑因子
	DELETE_FACTOR = "data:factor:delete"  # 删除因子

	# 配置权限
	MANAGE_DATA_SOURCES = "data:sources:manage"  # 管理数据源
	MANAGE_API_KEYS = "data:api_keys:manage"  # 管理API密钥
	CONFIGURE_MODULE = "data:config"  # 配置模块

	@classmethod
	def get_display_name (cls, permission):
		"""获取权限显示名称"""
		display_names = {
			cls.VIEW_STOCK_LIST: "查看股票列表",
			cls.VIEW_STOCK_DETAIL: "查看股票详情",
			cls.VIEW_HISTORICAL_QUOTES: "查看历史行情",
			cls.VIEW_FACTOR_DATA: "查看因子数据",
			cls.SYNC_DATA: "同步数据",
			cls.CANCEL_SYNC: "取消同步任务",
			cls.CHECK_QUALITY: "检查数据质量",
			cls.RESEARCH_FACTOR: "因子研究",
			cls.MANAGE_DATA_SOURCES: "管理数据源"
		}
		return display_names.get(permission, permission)