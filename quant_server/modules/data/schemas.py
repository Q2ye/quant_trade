"""
数据模块 - API请求/响应模型定义
基于Pydantic定义数据模块的所有API接口的请求和响应模型
位置：quant_server/modules/events/schemas.py

设计原则：
1. 独立定义：每个模块根据API需求独立定义自己的Pydantic模型
2. 与数据表模型分离：这里定义的模型用于API通信，与数据库表模型分离
3. 请求/响应分离：为每个API接口定义明确的请求和响应模型
4. 验证逻辑：包含数据验证、默认值、字段描述等
"""

from datetime import date, datetime
from enum import Enum
from typing import List, Optional, Dict, Any, Union

from pydantic import BaseModel, Field, ConfigDict, field_validator, model_validator


# ==================== 枚举类型定义 ====================

class DataSyncType(str, Enum):
	"""数据同步类型枚举"""
	STOCK_LIST = "stock_list"  # 股票列表
	DAILY_QUOTES = "daily_quotes"  # 日行情
	ADJUSTED_QUOTES = "adjusted_quotes"  # 复权行情
	FINANCIAL_DATA = "financial_data"  # 财务数据
	INDEX_DATA = "index_data"  # 指数数据
	CALENDAR = "calendar"  # 交易日历
	ALL = "all"  # 所有类型


class SyncPriority(str, Enum):
	"""同步优先级枚举"""
	LOW = "low"  # 低优先级
	MEDIUM = "medium"  # 中优先级
	HIGH = "high"  # 高优先级
	CRITICAL = "critical"  # 关键优先级


class DataQualityLevel(str, Enum):
	"""数据质量等级枚举"""
	EXCELLENT = "excellent"  # 优秀：完整率>=99%
	GOOD = "good"  # 良好：完整率>=95%
	FAIR = "fair"  # 一般：完整率>=90%
	POOR = "poor"  # 差：完整率<90%


class FactorCategory(str, Enum):
	"""因子类别枚举"""
	VALUE = "value"  # 价值因子
	GROWTH = "growth"  # 成长因子
	QUALITY = "quality"  # 质量因子
	MOMENTUM = "momentum"  # 动量因子
	VOLATILITY = "volatility"  # 波动率因子
	SIZE = "size"  # 规模因子
	LIQUIDITY = "liquidity"  # 流动性因子
	TECHNICAL = "technical"  # 技术因子


class StockListSortField(str, Enum):
	"""股票列表排序字段枚举"""
	TS_CODE = "ts_code"  # 股票代码
	NAME = "name"  # 股票名称
	MARKET_CAP = "market_cap"  # 市值
	LIST_DATE = "list_date"  # 上市日期
	INDUSTRY = "industry"  # 行业


class SortOrder(str, Enum):
	"""排序顺序枚举"""
	ASC = "asc"  # 升序
	DESC = "desc"  # 降序


# ==================== 分页和排序基类 ====================

# 导入配置化的分页和排序参数基类
from utils.api_utils.pagination_config import PaginationParams as ConfiguredPaginationParams
from utils.api_utils.pagination_config import SortParams as ConfiguredSortParams


class PaginationParams(ConfiguredPaginationParams):
	"""分页参数基类 - 配置化版本"""
	pass


class SortParams(ConfiguredSortParams):
	"""排序参数基类 - 配置化版本"""
	pass


# ==================== 基础数据查询模型 ====================

class StockListRequest(PaginationParams, SortParams):
	"""股票列表请求模型"""

	search: Optional[str] = Field(default=None, description="搜索关键词，可匹配股票代码或名称")
	market: Optional[str] = Field(default=None, description="市场类型: SSE/SZSE/BJSE")
	industry: Optional[str] = Field(default=None, description="行业分类")
	list_status: Optional[str] = Field(default="L", description="上市状态: L上市 D退市 P暂停")
	min_market_cap: Union[str, float, None] = Field(default=None, description="最小市值（亿元）")
	max_market_cap: Union[str, float, None] = Field(default=None, description="最大市值（亿元）")

	model_config = ConfigDict(
		json_schema_extra={
			"example": {
				"search": "平安",
				"market": "SSE",
				"industry": "银行",
				"sort_by": "market_cap",
				"sort_order": "desc"
			}
		}
	)

	@classmethod
	def validate_empty_string_to_none (cls, v):
		"""将空字符串转换为None"""
		if v == '':
			return None
		return v

	@field_validator('min_market_cap', 'max_market_cap')
	@classmethod
	def validate_market_cap_to_float_or_none (cls, v):
		"""将空字符串转换为None，或转换为浮点数"""
		if v is None or v == '':
			return None
		try:
			return float(v)
		except (ValueError, TypeError):
			return None

	@model_validator(mode='before')
	@classmethod
	def convert_empty_strings_to_none (cls, data):
		"""在类型验证之前将所有空字符串查询参数转换为None"""
		if isinstance(data, dict):
			for key, value in data.items():
				if value == '':
					data[key] = None
		return data


class StockBasicInfo(BaseModel):
	"""股票基础信息模型"""
	ts_code: str = Field(..., description="股票代码")
	symbol: str = Field(..., description="股票符号")
	name: str = Field(..., description="股票名称")
	area: Optional[str] = Field(default=None, description="地区")
	industry: Optional[str] = Field(default=None, description="行业")
	market: str = Field(..., description="市场类型")
	list_date: Optional[date] = Field(default=None, description="上市日期")
	is_hs: Optional[str] = Field(default=None, description="是否沪深港通标的: N否 H沪股通 S深股通")

	model_config = ConfigDict(
		from_attributes=True
	)


class StockListResponse(BaseModel):
	"""股票列表响应模型"""
	success: bool = Field(..., description="请求是否成功")
	data: List[StockBasicInfo] = Field(..., description="股票列表数据")
	pagination: Dict[str, Any] = Field(
		...,
		description="分页信息"
	)
	message: Optional[str] = Field(default=None, description="提示信息")

	model_config = ConfigDict(
		json_schema_extra={
			"example": {
				"success": True,
				"data": [
					{
						"ts_code": "000001.SZ",
						"symbol": "000001",
						"name": "平安银行",
						"area": "深圳",
						"industry": "银行",
						"market": "SZSE",
						"list_date": "1991-04-03",
						"is_hs": "S"
					}
				],
				"pagination": {
					"page": 1,
					"page_size": 20,
					"total": 5000,
					"total_pages": 250
				},
				"message": "获取成功"
			}
		}
	)


class StockDetailRequest(BaseModel):
	"""股票详情请求模型"""
	include_quote: bool = Field(default=True, description="是否包含行情数据")
	include_financial: bool = Field(default=False, description="是否包含财务数据")
	include_holders: bool = Field(default=False, description="是否包含股东信息")
	quote_start_date: Optional[date] = Field(default=None, description="行情开始日期")
	quote_end_date: Optional[date] = Field(default=None, description="行情结束日期")

	model_config = ConfigDict(
		json_schema_extra={
			"example": {
				"include_quote": True,
				"include_financial": False,
				"include_holders": False,
				"quote_start_date": "2023-01-01",
				"quote_end_date": "2023-12-31"
			}
		}
	)


class QuoteData(BaseModel):
	"""行情数据模型"""
	trade_date: date = Field(..., description="交易日期")
	open: float = Field(..., description="开盘价")
	high: float = Field(..., description="最高价")
	low: float = Field(..., description="最低价")
	close: float = Field(..., description="收盘价")
	pre_close: Optional[float] = Field(default=None, description="前收盘价")
	change: Optional[float] = Field(default=None, description="涨跌额")
	pct_chg: Optional[float] = Field(default=None, description="涨跌幅(%)")
	vol: Optional[float] = Field(default=None, description="成交量(手)")
	amount: Optional[float] = Field(default=None, description="成交额(千元)")
	adj_factor: Optional[float] = Field(default=None, description="复权因子")


class FinancialData(BaseModel):
	"""财务数据模型"""
	end_date: date = Field(..., description="报告期")
	revenue: Optional[float] = Field(default=None, description="营业收入")
	net_profit: Optional[float] = Field(default=None, description="净利润")
	eps: Optional[float] = Field(default=None, description="每股收益")
	roe: Optional[float] = Field(default=None, description="净资产收益率")
	total_assets: Optional[float] = Field(default=None, description="总资产")


class HolderInfo(BaseModel):
	"""股东信息模型"""
	holder_name: str = Field(..., description="股东名称")
	holder_type: str = Field(..., description="股东类型")
	hold_amount: float = Field(..., description="持股数量")
	hold_ratio: float = Field(..., description="持股比例")


class StockDetailResponse(BaseModel):
	"""股票详情响应模型"""
	success: bool = Field(..., description="请求是否成功")
	basic_info: StockBasicInfo = Field(..., description="股票基础信息")
	quotes: Optional[List[QuoteData]] = Field(default=None, description="行情数据")
	financials: Optional[List[FinancialData]] = Field(default=None, description="财务数据")
	holders: Optional[List[HolderInfo]] = Field(default=None, description="股东信息")
	statistics: Optional[Dict[str, Any]] = Field(default=None, description="统计信息")
	message: Optional[str] = Field(default=None, description="提示信息")

	model_config = ConfigDict(
		json_schema_extra={
			"example": {
				"success": True,
				"basic_info": {
					"ts_code": "000001.SZ",
					"symbol": "000001",
					"name": "平安银行",
					"area": "深圳",
					"industry": "银行",
					"market": "SZSE",
					"list_date": "1991-04-03",
					"is_hs": "S"
				},
				"quotes": [
					{
						"trade_date": "2023-12-29",
						"open": 10.15,
						"high": 10.25,
						"low": 10.05,
						"close": 10.20,
						"vol": 1500000,
						"amount": 15250000
					}
				],
				"message": "获取成功"
			}
		}
	)


class HistoricalQuotesRequest(BaseModel):
	"""历史行情请求模型"""
	ts_code: str = Field(..., description="股票代码，支持多个用逗号分隔")
	start_date: date = Field(..., description="开始日期")
	end_date: date = Field(..., description="结束日期")
	frequency: str = Field(default="D", description="频率: D日线 W周线 M月线")
	adjust: str = Field(default="qfq", description="复权类型: qfq前复权 hfq后复权 None不复权")
	fields: Optional[str] = Field(
		default=None,
		description="返回字段，逗号分隔，默认全部"
	)

	@field_validator('frequency')
	@classmethod
	def validate_frequency (cls, v):
		"""验证频率参数"""
		valid_frequencies = ['D', 'W', 'M', '5', '15', '30', '60']
		if v not in valid_frequencies:
			raise ValueError(f"频率必须为: {', '.join(valid_frequencies)}")
		return v

	@field_validator('adjust')
	@classmethod
	def validate_adjust (cls, v):
		"""验证复权类型"""
		valid_adjusts = ['qfq', 'hfq', 'None', '']
		if v not in valid_adjusts:
			raise ValueError(f"复权类型必须为: {', '.join(valid_adjusts[:-1])}")
		return v

	model_config = ConfigDict(
		json_schema_extra={
			"example": {
				"ts_code": "000001.SZ",
				"start_date": "2023-01-01",
				"end_date": "2023-12-31",
				"frequency": "D",
				"adjust": "qfq",
				"fields": "ts_code,trade_date,open,high,low,close,vol"
			}
		}
	)


class HistoricalQuotesResponse(BaseModel):
	"""历史行情响应模型"""
	success: bool = Field(..., description="请求是否成功")
	data: Dict[str, List[QuoteData]] = Field(..., description="按股票代码分组的历史行情数据")
	metadata: Dict[str, Any] = Field(
		...,
		description="元数据"
	)
	message: Optional[str] = Field(default=None, description="提示信息")

	model_config = ConfigDict(
		json_schema_extra={
			"example": {
				"success": True,
				"data": {
					"000001.SZ": [
						{
							"trade_date": "2023-12-29",
							"open": 10.15,
							"high": 10.25,
							"low": 10.05,
							"close": 10.20,
							"vol": 1500000,
							"amount": 15250000
						}
					]
				},
				"metadata": {
					"total_records": 240,
					"date_range": {
						"start": "2023-01-01",
						"end": "2023-12-31"
					},
					"frequency": "D",
					"adjust": "qfq"
				},
				"message": "获取成功"
			}
		}
	)


# ==================== 数据同步模型 ====================

class SyncTaskItem(BaseModel):
	"""同步任务项模型"""
	data_type: DataSyncType = Field(..., description="数据类型")
	start_date: Optional[date] = Field(default=None, description="开始日期")
	end_date: Optional[date] = Field(default=None, description="结束日期")
	force_update: bool = Field(default=False, description="是否强制更新")

	model_config = ConfigDict(
		json_schema_extra={
			"example": {
				"data_type": "daily_quotes",
				"start_date": "2023-01-01",
				"end_date": "2023-12-31",
				"force_update": False
			}
		}
	)


class BatchSyncRequest(BaseModel):
	"""批量同步请求模型"""
	tasks: List[SyncTaskItem] = Field(..., min_length=1, description="同步任务列表")
	priority: SyncPriority = Field(default=SyncPriority.MEDIUM, description="同步优先级")
	notify_on_complete: bool = Field(default=True, description="完成后是否通知")
	callback_url: Optional[str] = Field(default=None, description="回调URL")

	@field_validator('tasks')
	@classmethod
	def validate_tasks (cls, v):
		"""验证任务列表"""
		if not v:
			raise ValueError("任务列表不能为空")
		return v

	model_config = ConfigDict(
		json_schema_extra={
			"example": {
				"tasks": [
					{
						"data_type": "daily_quotes",
						"start_date": "2023-01-01",
						"end_date": "2023-12-31"
					},
					{
						"data_type": "stock_list",
						"force_update": True
					}
				],
				"priority": "medium",
				"notify_on_complete": True
			}
		}
	)


class SyncProgress(BaseModel):
	"""同步进度模型"""
	task_id: str = Field(..., description="任务ID")
	total_tasks: int = Field(..., description="总任务数")
	completed_tasks: int = Field(..., description="已完成任务数")
	current_task: Optional[str] = Field(default=None, description="当前任务")
	progress_percentage: float = Field(..., ge=0, le=100, description="进度百分比")
	estimated_time_remaining: Optional[int] = Field(
		default=None,
		description="预计剩余时间(秒)"
	)

	model_config = ConfigDict(
		json_schema_extra={
			"example": {
				"task_id": "sync_20231229_001",
				"total_tasks": 5,
				"completed_tasks": 2,
				"current_task": "同步日行情数据",
				"progress_percentage": 40.0,
				"estimated_time_remaining": 300
			}
		}
	)


class SyncResult(BaseModel):
	"""同步结果模型"""
	data_type: DataSyncType = Field(..., description="数据类型")
	success: bool = Field(..., description="是否成功")
	records_added: int = Field(default=0, description="新增记录数")
	records_updated: int = Field(default=0, description="更新记录数")
	records_failed: int = Field(default=0, description="失败记录数")
	start_time: datetime = Field(..., description="开始时间")
	end_time: datetime = Field(..., description="结束时间")
	error_message: Optional[str] = Field(default=None, description="错误信息")

	model_config = ConfigDict(
		json_schema_extra={
			"example": {
				"data_type": "daily_quotes",
				"success": True,
				"records_added": 1000,
				"records_updated": 200,
				"records_failed": 5,
				"start_time": "2023-12-29T09:00:00",
				"end_time": "2023-12-29T09:30:00"
			}
		}
	)


class BatchSyncResponse(BaseModel):
	"""批量同步响应模型"""
	success: bool = Field(..., description="请求是否成功")
	task_id: str = Field(..., description="任务ID")
	task_count: int = Field(..., description="任务总数")
	estimated_duration: Optional[int] = Field(
		default=None,
		description="预计持续时间(秒)"
	)
	start_time: datetime = Field(..., description="开始时间")
	progress_endpoint: str = Field(
		...,
		description="进度查询端点"
	)
	message: Optional[str] = Field(default=None, description="提示信息")

	model_config = ConfigDict(
		json_schema_extra={
			"example": {
				"success": True,
				"task_id": "sync_20231229_001",
				"task_count": 5,
				"estimated_duration": 1800,
				"start_time": "2023-12-29T09:00:00",
				"progress_endpoint": "/api/events/sync/status?task_id=sync_20231229_001",
				"message": "同步任务已开始，请通过进度端点查询状态"
			}
		}
	)


class SyncStatusResponse(BaseModel):
	"""同步状态响应模型"""
	success: bool = Field(..., description="请求是否成功")
	task_id: str = Field(..., description="任务ID")
	status: str = Field(..., description="任务状态: pending/running/completed/failed/cancelled")
	progress: SyncProgress = Field(..., description="进度信息")
	results: Optional[List[SyncResult]] = Field(default=None, description="同步结果")
	created_by: str = Field(..., description="创建用户")
	created_at: datetime = Field(..., description="创建时间")
	updated_at: datetime = Field(..., description="更新时间")
	message: Optional[str] = Field(default=None, description="提示信息")

	model_config = ConfigDict(
		json_schema_extra={
			"example": {
				"success": True,
				"task_id": "sync_20231229_001",
				"status": "running",
				"progress": {
					"total_tasks": 5,
					"completed_tasks": 2,
					"current_task": "同步日行情数据",
					"progress_percentage": 40.0
				},
				"created_by": "admin",
				"created_at": "2023-12-29T09:00:00",
				"updated_at": "2023-12-29T09:10:00",
				"message": "任务执行中"
			}
		}
	)


class QuickSyncRequest(BaseModel):
	"""快速同步请求模型"""
	date_range: str = Field(default="7d", description="日期范围: 7d/30d/90d/1y")
	include_stock_list: bool = Field(default=True, description="是否包含股票列表")
	include_calendar: bool = Field(default=True, description="是否包含交易日历")

	@field_validator('date_range')
	@classmethod
	def validate_date_range (cls, v):
		"""验证日期范围"""
		valid_ranges = ['1d', '7d', '30d', '90d', '1y', 'all']
		if v not in valid_ranges:
			raise ValueError(f"日期范围必须为: {', '.join(valid_ranges)}")
		return v

	model_config = ConfigDict(
		json_schema_extra={
			"example": {
				"date_range": "7d",
				"include_stock_list": True,
				"include_calendar": True
			}
		}
	)


# ==================== 数据质量模型 ====================

class QualityMetric(BaseModel):
	"""质量指标模型"""
	metric_name: str = Field(..., description="指标名称")
	metric_value: float = Field(..., description="指标值")
	threshold: Optional[float] = Field(default=None, description="阈值")
	status: str = Field(..., description="状态: pass/warning/fail")

	model_config = ConfigDict(
		json_schema_extra={
			"example": {
				"metric_name": "数据完整率",
				"metric_value": 98.5,
				"threshold": 95.0,
				"status": "pass"
			}
		}
	)


class DataQualityRequest(BaseModel):
	"""数据质量请求模型"""
	data_type: Optional[DataSyncType] = Field(default=None, description="数据类型")
	start_date: Optional[date] = Field(default=None, description="开始日期")
	end_date: Optional[date] = Field(default=None, description="结束日期")
	check_type: str = Field(default="completeness", description="检查类型: completeness/accuracy/timeliness")

	@field_validator('check_type')
	@classmethod
	def validate_check_type (cls, v):
		"""验证检查类型"""
		valid_types = ['completeness', 'accuracy', 'timeliness', 'all']
		if v not in valid_types:
			raise ValueError(f"检查类型必须为: {', '.join(valid_types)}")
		return v

	model_config = ConfigDict(
		json_schema_extra={
			"example": {
				"data_type": "daily_quotes",
				"start_date": "2023-01-01",
				"end_date": "2023-12-31",
				"check_type": "completeness"
			}
		}
	)


class DataIssue(BaseModel):
	"""数据问题模型"""
	issue_type: str = Field(..., description="问题类型: missing/duplicate/invalid/outlier")
	severity: str = Field(..., description="严重程度: low/medium/high/critical")
	count: int = Field(..., description="问题数量")
	description: str = Field(..., description="问题描述")
	affected_records: Optional[List[str]] = Field(default=None, description="受影响的记录")

	model_config = ConfigDict(
		json_schema_extra={
			"example": {
				"issue_type": "missing",
				"severity": "medium",
				"count": 15,
				"description": "15个交易日缺少行情数据"
			}
		}
	)


class DataQualityResponse(BaseModel):
	"""数据质量响应模型"""
	success: bool = Field(..., description="请求是否成功")
	data_type: Optional[DataSyncType] = Field(default=None, description="数据类型")
	date_range: Optional[Dict[str, date]] = Field(default=None, description="日期范围")
	quality_score: float = Field(..., ge=0, le=100, description="质量评分")
	quality_level: DataQualityLevel = Field(..., description="质量等级")
	metrics: List[QualityMetric] = Field(..., description="质量指标")
	issues: List[DataIssue] = Field(..., description="数据问题")
	recommendations: List[str] = Field(..., description="改进建议")
	generated_at: datetime = Field(..., description="报告生成时间")
	message: Optional[str] = Field(default=None, description="提示信息")

	model_config = ConfigDict(
		json_schema_extra={
			"example": {
				"success": True,
				"data_type": "daily_quotes",
				"date_range": {
					"start": "2023-01-01",
					"end": "2023-12-31"
				},
				"quality_score": 96.5,
				"quality_level": "good",
				"metrics": [
					{
						"metric_name": "数据完整率",
						"metric_value": 98.5,
						"status": "pass"
					}
				],
				"issues": [
					{
						"issue_type": "missing",
						"severity": "medium",
						"count": 15,
						"description": "15个交易日缺少行情数据"
					}
				],
				"recommendations": [
					"建议重新同步缺失日期的行情数据"
				],
				"generated_at": "2023-12-29T10:00:00",
				"message": "数据质量检查完成"
			}
		}
	)


# ==================== 因子数据模型 ====================

class FactorRequest(PaginationParams):
	"""因子数据请求模型"""
	ts_code: str = Field(..., description="股票代码")
	factor_name: Optional[str] = Field(default=None, description="因子名称")
	factor_category: Optional[FactorCategory] = Field(default=None, description="因子类别")
	start_date: date = Field(..., description="开始日期")
	end_date: date = Field(..., description="结束日期")
	frequency: str = Field(default="M", description="频率: D日度 W周度 M月度 Q季度 Y年度")

	@field_validator('frequency')
	@classmethod
	def validate_frequency (cls, v):
		"""验证频率参数"""
		valid_frequencies = ['D', 'W', 'M', 'Q', 'Y']
		if v not in valid_frequencies:
			raise ValueError(f"频率必须为: {', '.join(valid_frequencies)}")
		return v

	model_config = ConfigDict(
		json_schema_extra={
			"example": {
				"ts_code": "000001.SZ",
				"start_date": "2020-01-01",
				"end_date": "2023-12-31",
				"frequency": "M"
			}
		}
	)


class FactorValue(BaseModel):
	"""因子值模型"""
	trade_date: date = Field(..., description="交易日期")
	factor_name: str = Field(..., description="因子名称")
	factor_value: float = Field(..., description="因子值")
	z_score: Optional[float] = Field(default=None, description="Z分数")
	rank: Optional[float] = Field(default=None, description="排名百分位")
	category: FactorCategory = Field(..., description="因子类别")

	model_config = ConfigDict(
		json_schema_extra={
			"example": {
				"trade_date": "2023-12-01",
				"factor_name": "PE",
				"factor_value": 12.5,
				"z_score": 0.8,
				"rank": 0.75,
				"category": "value"
			}
		}
	)


class FactorMetadata(BaseModel):
	"""因子元数据模型"""
	factor_name: str = Field(..., description="因子名称")
	display_name: str = Field(..., description="显示名称")
	description: str = Field(..., description="因子描述")
	category: FactorCategory = Field(..., description="因子类别")
	formula: Optional[str] = Field(default=None, description="计算公式")
	data_source: str = Field(..., description="数据来源")
	update_frequency: str = Field(..., description="更新频率")
	last_update: datetime = Field(..., description="最后更新时间")

	model_config = ConfigDict(
		json_schema_extra={
			"example": {
				"factor_name": "PE",
				"display_name": "市盈率",
				"description": "股价除以每股收益",
				"category": "value",
				"data_source": "Tushare",
				"update_frequency": "daily",
				"last_update": "2023-12-29T09:00:00"
			}
		}
	)


class FactorResponse(BaseModel):
	"""因子数据响应模型"""
	success: bool = Field(..., description="请求是否成功")
	ts_code: str = Field(..., description="股票代码")
	factor_values: List[FactorValue] = Field(..., description="因子值列表")
	metadata: Optional[FactorMetadata] = Field(
		default=None,  # 改为可选，因为可能为空
		description="因子元数据"
	)
	statistics: Dict[str, Any] = Field(
		...,
		description="统计信息"
	)
	pagination: Optional[Dict[str, Any]] = Field(
		default=None,
		description="分页信息"
	)
	available_factors: Optional[List[FactorMetadata]] = Field(  # 可选字段
		default=None,
		description="可用的公开因子列表"
	)
	message: Optional[str] = Field(default=None, description="提示信息")

	model_config = ConfigDict(
		json_schema_extra={
			"example": {
				"success": True,
				"ts_code": "000001.SZ",
				"factor_values": [
					{
						"trade_date": "2023-12-01",
						"factor_name": "PE",
						"factor_value": 12.5,
						"category": "value"
					}
				],
				"metadata": {
					"factor_name": "PE",
					"display_name": "市盈率",
					"description": "股价除以每股收益",
					"category": "value"
				},
				"statistics": {
					"mean": 15.2,
					"std": 3.5,
					"count": 48
				},
				"message": "获取成功"
			}
		}
	)


class ResearchRequest(BaseModel):
	"""因子研究请求模型"""
	factor_names: List[str] = Field(..., min_length=1, description="因子名称列表")
	universe: List[str] = Field(..., min_length=1, description="股票池")
	start_date: date = Field(..., description="开始日期")
	end_date: date = Field(..., description="结束日期")
	frequency: str = Field(default="M", description="频率: D日度 W周度 M月度")
	group_count: int = Field(default=5, ge=2, le=10, description="分组数量")
	analysis_type: str = Field(
		default="ic_analysis",
		description="分析类型: ic_analysis/quantile_analysis/correlation_analysis"
	)

	@field_validator('analysis_type')
	@classmethod
	def validate_analysis_type (cls, v):
		"""验证分析类型"""
		valid_types = ['ic_analysis', 'quantile_analysis', 'correlation_analysis', 'all']
		if v not in valid_types:
			raise ValueError(f"分析类型必须为: {', '.join(valid_types)}")
		return v

	model_config = ConfigDict(
		json_schema_extra={
			"example": {
				"factor_names": ["PE", "PB", "ROE"],
				"universe": ["000001.SZ", "000002.SZ", "000858.SZ"],
				"start_date": "2020-01-01",
				"end_date": "2023-12-31",
				"frequency": "M",
				"group_count": 5,
				"analysis_type": "ic_analysis"
			}
		}
	)


class ICAnalysisResult(BaseModel):
	"""IC分析结果模型"""
	factor_name: str = Field(..., description="因子名称")
	ic_mean: float = Field(..., description="IC均值")
	ic_std: float = Field(..., description="IC标准差")
	ic_ir: float = Field(..., description="信息比率")
	ic_pvalue: Optional[float] = Field(default=None, description="P值")
	ic_series: List[float] = Field(..., description="IC序列")

	model_config = ConfigDict(
		json_schema_extra={
			"example": {
				"factor_name": "PE",
				"ic_mean": 0.08,
				"ic_std": 0.12,
				"ic_ir": 0.67,
				"ic_pvalue": 0.02
			}
		}
	)


class QuantileAnalysisResult(BaseModel):
	"""分位数分析结果模型"""
	factor_name: str = Field(..., description="因子名称")
	quantile_returns: List[float] = Field(..., description="各分位数组合收益率")
	top_minus_bottom: float = Field(..., description="多空收益率")
	turnover_rate: List[float] = Field(..., description="换手率")

	model_config = ConfigDict(
		json_schema_extra={
			"example": {
				"factor_name": "PE",
				"quantile_returns": [0.15, 0.12, 0.10, 0.08, 0.05],
				"top_minus_bottom": 0.10,
				"turnover_rate": [0.30, 0.28, 0.25, 0.22, 0.20]
			}
		}
	)


class CorrelationAnalysisResult(BaseModel):
	"""相关性分析结果模型"""
	factor_pairs: List[List[str]] = Field(..., description="因子对")
	correlation_matrix: List[List[float]] = Field(..., description="相关系数矩阵")
	mean_correlation: float = Field(..., description="平均相关系数")

	model_config = ConfigDict(
		json_schema_extra={
			"example": {
				"factor_pairs": [["PE", "PB"], ["PE", "ROE"], ["PB", "ROE"]],
				"correlation_matrix": [[1.0, 0.7, 0.3], [0.7, 1.0, 0.2], [0.3, 0.2, 1.0]],
				"mean_correlation": 0.4
			}
		}
	)


class ResearchResponse(BaseModel):
	"""因子研究响应模型"""
	success: bool = Field(..., description="请求是否成功")
	research_id: str = Field(..., description="研究ID")
	analysis_type: str = Field(..., description="分析类型")
	parameters: Dict[str, Any] = Field(..., description="研究参数")
	ic_analysis: Optional[List[ICAnalysisResult]] = Field(
		default=None,
		description="IC分析结果"
	)
	quantile_analysis: Optional[List[QuantileAnalysisResult]] = Field(
		default=None,
		description="分位数分析结果"
	)
	correlation_analysis: Optional[CorrelationAnalysisResult] = Field(
		default=None,
		description="相关性分析结果"
	)
	summary: Dict[str, Any] = Field(..., description="研究摘要")
	generated_at: datetime = Field(..., description="生成时间")
	message: Optional[str] = Field(default=None, description="提示信息")

	# 新增：异步任务相关字段
	status: Optional[str] = Field(
		default=None,
		description="任务状态: started/running/completed/failed"
	)
	created_at: Optional[datetime] = Field(
		default=None,
		description="任务创建时间"
	)
	estimated_time: Optional[int] = Field(
		default=None,
		description="预计执行时间(秒)"
	)
	factor_name: Optional[str] = Field(
		default=None,
		description="因子名称（用于异步任务响应）"
	)

	model_config = ConfigDict(
		json_schema_extra={
			"example": {
				"success": True,
				"research_id": "research_20231229_001",
				"analysis_type": "ic_analysis",
				"parameters": {
					"factor_names": ["PE", "PB", "ROE"],
					"start_date": "2020-01-01",
					"end_date": "2023-12-31"
				},
				"status": "started",
				"created_at": "2023-12-29T10:00:00",
				"estimated_time": 300,
				"factor_name": "PE",
				"summary": {},
				"generated_at": "2023-12-29T10:00:00",
				"message": "因子研究已开始，将在后台执行"
			}
		}
	)


# ==================== WebSocket事件模型 ====================

class DataEvent(BaseModel):
	"""数据事件基类"""
	event_type: str = Field(..., description="事件类型")
	event_id: str = Field(..., description="事件ID")
	timestamp: datetime = Field(..., description="事件时间戳")
	data: Dict[str, Any] = Field(..., description="事件数据")


class SyncProgressEvent(DataEvent):
	"""同步进度事件"""
	task_id: str = Field(..., description="任务ID")
	progress_percentage: float = Field(..., description="进度百分比")
	current_task: str = Field(..., description="当前任务")

	model_config = ConfigDict(
		json_schema_extra={
			"example": {
				"event_type": "sync_progress",
				"event_id": "event_001",
				"timestamp": "2023-12-29T09:15:00",
				"task_id": "sync_20231229_001",
				"progress_percentage": 40.0,
				"current_task": "同步日行情数据",
				"data": {
					"total_tasks": 5,
					"completed_tasks": 2
				}
			}
		}
	)


class QualityAlertEvent(DataEvent):
	"""质量警报事件"""
	alert_level: str = Field(..., description="警报级别: warning/error/critical")
	data_type: DataSyncType = Field(..., description="数据类型")
	issue_description: str = Field(..., description="问题描述")

	model_config = ConfigDict(
		json_schema_extra={
			"example": {
				"event_type": "quality_alert",
				"event_id": "alert_001",
				"timestamp": "2023-12-29T10:30:00",
				"alert_level": "warning",
				"data_type": "daily_quotes",
				"issue_description": "数据完整率低于95%",
				"data": {
					"quality_score": 92.5,
					"missing_count": 25
				}
			}
		}
	)


class FactorUpdateEvent(DataEvent):
	"""因子更新事件"""
	factor_name: str = Field(..., description="因子名称")
	update_type: str = Field(..., description="更新类型: daily/weekly/monthly")
	affected_stocks: int = Field(..., description="受影响股票数量")

	model_config = ConfigDict(
		json_schema_extra={
			"example": {
				"event_type": "factor_update",
				"event_id": "update_001",
				"timestamp": "2023-12-29T16:00:00",
				"factor_name": "PE",
				"update_type": "daily",
				"affected_stocks": 4500,
				"data": {
					"update_date": "2023-12-29",
					"factor_count": 50
				}
			}
		}
	)


# ==================== 因子元数据响应模型 ====================

class FactorMetadataRequest(PaginationParams, SortParams):
	"""因子元数据请求模型"""
	factor_name: Optional[str] = Field(default=None, description="因子名称筛选")
	factor_category: Optional[FactorCategory] = Field(default=None, description="因子类别筛选")
	search: Optional[str] = Field(default=None, description="搜索关键词，可匹配因子名称或描述")
	has_formula: Optional[bool] = Field(default=None, description="是否包含计算公式")

	model_config = ConfigDict(
		json_schema_extra={
			"example": {
				"factor_category": "value",
				"search": "市盈率",
				"sort_by": "factor_name",
				"sort_order": "asc"
			}
		}
	)


class FactorMetadataResponse(BaseModel):
	"""因子元数据响应模型"""
	success: bool = Field(..., description="请求是否成功")
	metadata_list: List[FactorMetadata] = Field(..., description="因子元数据列表")
	pagination: Dict[str, Any] = Field(
		...,
		description="分页信息"
	)
	summary: Dict[str, Any] = Field(
		default_factory=dict,
		description="摘要统计"
	)
	message: Optional[str] = Field(default=None, description="提示信息")

	model_config = ConfigDict(
		json_schema_extra={
			"example": {
				"success": True,
				"metadata_list": [
					{
						"factor_name": "PE",
						"display_name": "市盈率",
						"description": "股价除以每股收益",
						"category": "value",
						"formula": "P/E = Price per Share / Earnings per Share",
						"data_source": "Tushare",
						"update_frequency": "daily",
						"last_update": "2023-12-29T09:00:00"
					},
					{
						"factor_name": "PB",
						"display_name": "市净率",
						"description": "股价除以每股净资产",
						"category": "value",
						"formula": "P/B = Price per Share / Book Value per Share",
						"data_source": "Tushare",
						"update_frequency": "daily",
						"last_update": "2023-12-29T09:00:00"
					}
				],
				"pagination": {
					"page": 1,
					"page_size": 20,
					"total": 150,
					"total_pages": 8
				},
				"summary": {
					"total_factors": 150,
					"by_category": {
						"value": 25,
						"growth": 30,
						"quality": 35
					}
				},
				"message": "获取成功"
			}
		}
	)


# ==================== 快速同步响应模型 ====================

class QuickSyncResponse(BaseModel):
	"""快速同步响应模型"""
	success: bool = Field(..., description="请求是否成功")
	task_id: str = Field(..., description="快速同步任务ID")
	sync_type: str = Field(..., description="同步类型: quick_sync")
	date_range: str = Field(..., description="同步的日期范围")
	included_data_types: List[str] = Field(..., description="包含的数据类型")
	estimated_stocks: Optional[int] = Field(default=None, description="预计同步的股票数量")
	estimated_records: Optional[int] = Field(default=None, description="预计同步的记录数")
	start_time: datetime = Field(..., description="开始时间")
	progress_endpoint: str = Field(
		...,
		description="进度查询端点"
	)
	quick_status_endpoint: str = Field(
		...,
		description="快速状态查询端点"
	)
	message: Optional[str] = Field(default=None, description="提示信息")
	warnings: Optional[List[str]] = Field(default=None, description="警告信息")

	model_config = ConfigDict(
		json_schema_extra={
			"example": {
				"success": True,
				"task_id": "quick_sync_20231229_001",
				"sync_type": "quick_sync",
				"date_range": "7d",
				"included_data_types": ["stock_list", "daily_quotes", "calendar"],
				"estimated_stocks": 5000,
				"estimated_records": 35000,
				"start_time": "2023-12-29T09:00:00",
				"progress_endpoint": "/api/events/sync/status?task_id=quick_sync_20231229_001",
				"quick_status_endpoint": "/api/events/sync/quick-status?task_id=quick_sync_20231229_001",
				"message": "快速同步任务已开始，预计同步5000只股票共35000条记录",
				"warnings": ["请注意，快速同步可能会对系统性能产生短暂影响"]
			}
		}
	)


class QuickSyncStatusResponse(BaseModel):
	"""快速同步状态响应模型"""
	success: bool = Field(..., description="请求是否成功")
	task_id: str = Field(..., description="任务ID")
	status: str = Field(
		...,
		description="任务状态: queued/collecting_data/syncing_stock_list/syncing_quotes/syncing_calendar/completing/failed/cancelled"
	)
	progress_percentage: float = Field(..., ge=0, le=100, description="进度百分比")
	current_operation: str = Field(..., description="当前操作")
	completed_steps: List[str] = Field(..., description="已完成步骤")
	data_synced: Dict[str, Any] = Field(
		...,
		description="已同步数据统计"
	)
	estimated_time_remaining: Optional[int] = Field(
		default=None,
		description="预计剩余时间(秒)"
	)
	start_time: datetime = Field(..., description="开始时间")
	last_update: datetime = Field(..., description="最后更新时间")
	message: Optional[str] = Field(default=None, description="提示信息")

	model_config = ConfigDict(
		json_schema_extra={
			"example": {
				"success": True,
				"task_id": "quick_sync_20231229_001",
				"status": "syncing_quotes",
				"progress_percentage": 60.0,
				"current_operation": "同步日行情数据",
				"completed_steps": ["任务已排队", "收集同步参数", "同步股票列表"],
				"data_synced": {
					"stock_list": {"status": "completed", "records": 5000},
					"daily_quotes": {"status": "in_progress", "records": 12000},
					"calendar": {"status": "pending", "records": 0}
				},
				"estimated_time_remaining": 300,
				"start_time": "2023-12-29T09:00:00",
				"last_update": "2023-12-29T09:10:00",
				"message": "快速同步任务执行中，已完成60%"
			}
		}
	)


# ==================== 补充：因子批量查询模型 ====================

class BatchFactorRequest(PaginationParams):
	"""批量因子查询请求模型"""
	ts_codes: List[str] = Field(..., min_length=1, max_length=100, description="股票代码列表，最多100个")
	factor_names: List[str] = Field(..., min_length=1, max_length=20, description="因子名称列表，最多20个")
	trade_date: date = Field(..., description="查询日期")
	include_history: bool = Field(default=False, description="是否包含历史数据")
	history_days: int = Field(default=30, ge=1, le=365, description="历史天数，当include_history为True时有效")

	@field_validator('ts_codes')
	@classmethod
	def validate_ts_codes (cls, v):
		"""验证股票代码数量"""
		if len(v) > 100:
			raise ValueError("股票代码数量不能超过100个")
		return v

	@field_validator('factor_names')
	@classmethod
	def validate_factor_names (cls, v):
		"""验证因子名称数量"""
		if len(v) > 20:
			raise ValueError("因子名称数量不能超过20个")
		return v

	model_config = ConfigDict(
		json_schema_extra={
			"example": {
				"ts_codes": ["000001.SZ", "000002.SZ", "000858.SZ"],
				"factor_names": ["PE", "PB", "ROE"],
				"trade_date": "2023-12-29",
				"include_history": True,
				"history_days": 30
			}
		}
	)


class BatchFactorResponse(BaseModel):
	"""批量因子查询响应模型"""
	success: bool = Field(..., description="请求是否成功")
	trade_date: date = Field(..., description="查询日期")
	factor_data: Dict[str, Dict[str, Any]] = Field(
		...,
		description="因子数据，按股票代码分组"
	)
	metadata: Dict[str, FactorMetadata] = Field(..., description="因子元数据")
	statistics: Dict[str, Any] = Field(
		...,
		description="统计信息"
	)
	history_data: Optional[Dict[str, List[FactorValue]]] = Field(
		default=None,
		description="历史因子数据"
	)
	message: Optional[str] = Field(default=None, description="提示信息")

	model_config = ConfigDict(
		json_schema_extra={
			"example": {
				"success": True,
				"trade_date": "2023-12-29",
				"factor_data": {
					"000001.SZ": {
						"PE": 12.5,
						"PB": 1.2,
						"ROE": 0.15
					},
					"000002.SZ": {
						"PE": 18.3,
						"PB": 1.8,
						"ROE": 0.22
					}
				},
				"metadata": {
					"PE": {
						"factor_name": "PE",
						"display_name": "市盈率",
						"description": "股价除以每股收益",
						"category": "value"
					}
				},
				"statistics": {
					"stocks_count": 2,
					"factors_count": 3,
					"missing_values": 0
				},
				"message": "批量因子查询成功"
			}
		}
	)
