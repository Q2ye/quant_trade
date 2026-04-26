"""
市场数据处理事件定义
用于市场数据从接收到处理完成的完整流程事件通知

职责范围：
1. 原始数据到达通知
2. 数据处理状态更新
3. 数据验证结果通知
4. 处理完成通知

事件流程：
原始数据到达 → 数据处理中 → 数据处理完成 → 数据验证完成

订阅者示例：
- 数据清洗引擎：监听原始数据到达事件
- 策略模块：监听数据处理完成事件
- 监控模块：监听所有事件进行监控
- 缓存模块：监听数据验证完成事件更新缓存
"""

from dataclasses import dataclass, field
from datetime import date
from datetime import datetime
from typing import Dict, Any, List
from typing import Optional

from quant_server.core.events import BaseEvent, EventPriority, EventCategory
from quant_server.modules.data.constants import AdjustType
from .types import DataEventType, DataProcessingStatus


@dataclass
class MarketDataRequest:
	"""
	市场数据请求参数
	描述市场数据请求的基本参数和要求
	"""
	# 基础信息
	symbol: str  # 股票代码
	data_type: str  # 数据类型：daily_quotes/minute_quotes等
	frequency: str  # 数据频率：daily/1min/5min等

	# 时间范围
	start_date: Optional[date] = None  # 开始日期
	end_date: Optional[date] = None  # 结束日期
	limit: Optional[int] = None  # 数据条数限制

	# 处理选项
	adjust_type: str = AdjustType.NONE  # 复权类型
	fields: Optional[list] = None  # 请求的字段列表
	fill_missing: bool = True  # 是否填充缺失数据
	normalize: bool = False  # 是否标准化数据

	# 来源选项
	source_preference: Optional[list] = None  # 数据源偏好
	use_cache: bool = True  # 是否使用缓存
	force_refresh: bool = False  # 是否强制刷新

	def to_dict (self) -> Dict[str, Any]:
		"""转换为字典"""
		return {
			"symbol": self.symbol,
			"data_type": self.data_type,
			"frequency": self.frequency,
			"start_date": self.start_date.isoformat() if self.start_date else None,
			"end_date": self.end_date.isoformat() if self.end_date else None,
			"limit": self.limit,
			"adjust_type": self.adjust_type,
			"fields": self.fields,
			"fill_missing": self.fill_missing,
			"normalize": self.normalize,
			"source_preference": self.source_preference,
			"use_cache": self.use_cache,
			"force_refresh": self.force_refresh
		}

	@classmethod
	def from_dict (cls, data: Dict[str, Any]) -> "MarketDataRequest":
		"""从字典创建"""
		start_date = date.fromisoformat(data["start_date"]) if data.get("start_date") else None
		end_date = date.fromisoformat(data["end_date"]) if data.get("end_date") else None

		return cls(
			symbol=data["symbol"],
			data_type=data["data_type"],
			frequency=data["frequency"],
			start_date=start_date,
			end_date=end_date,
			limit=data.get("limit"),
			adjust_type=data.get("adjust_type", AdjustType.NONE),
			fields=data.get("fields"),
			fill_missing=data.get("fill_missing", True),
			normalize=data.get("normalize", False),
			source_preference=data.get("source_preference"),
			use_cache=data.get("use_cache", True),
			force_refresh=data.get("force_refresh", False)
		)


@dataclass
class MarketDataMetadata:
	"""
	市场数据元数据
	描述市场数据的基本信息和处理状态
	"""
	# 基本信息
	data_type: str  # 数据类型：tick/1min/5min/daily等
	symbols: List[str]  # 标的列表
	start_time: datetime  # 数据开始时间
	end_time: datetime  # 数据结束时间
	record_count: int  # 记录数量

	# 来源信息
	source: str = "unknown"  # 数据来源：tushare/baostock等
	source_format: str = "raw"  # 原始格式：json/csv/parquet
	source_version: str = "1.0"  # 数据源版本

	# 处理信息
	processing_version: str = "1.0"  # 处理版本
	quality_score: float = 0.0  # 数据质量评分（0-100）
	status: str = DataProcessingStatus.RAW.value  # 处理状态

	# 元信息
	metadata: Dict[str, Any] = field(default_factory=dict)  # 额外元数据

	def to_dict (self) -> Dict[str, Any]:
		"""转换为字典"""
		return {
			"data_type": self.data_type,
			"symbols": self.symbols,
			"symbol_count": len(self.symbols),
			"start_time": self.start_time.isoformat(),
			"end_time": self.end_time.isoformat(),
			"record_count": self.record_count,
			"source": self.source,
			"source_format": self.source_format,
			"source_version": self.source_version,
			"processing_version": self.processing_version,
			"quality_score": self.quality_score,
			"status": self.status,
			"metadata": self.metadata,
		}

	@classmethod
	def from_dict (cls, data: Dict[str, Any]) -> "MarketDataMetadata":
		"""从字典创建"""
		return cls(
			data_type=data["data_type"],
			symbols=data["symbols"],
			start_time=datetime.fromisoformat(data["start_time"]),
			end_time=datetime.fromisoformat(data["end_time"]),
			record_count=data["record_count"],
			source=data.get("source", "unknown"),
			source_format=data.get("source_format", "raw"),
			source_version=data.get("source_version", "1.0"),
			processing_version=data.get("processing_version", "1.0"),
			quality_score=data.get("quality_score", 0.0),
			status=data.get("status", DataProcessingStatus.RAW.value),
			metadata=data.get("metadata", {}),
		)


def _get_processing_requirements (data_type: str) -> List[str]:
	"""根据数据类型获取处理要求"""
	requirements = {
		"tick": ["time_alignment", "duplicate_removal", "price_validation"],
		"1min": ["time_alignment", "missing_fill", "outlier_detection"],
		"5min": ["time_alignment", "missing_fill", "consistency_check"],
		"daily": ["dividend_adjustment", "missing_fill", "consistency_check"],
	}
	return requirements.get(data_type, ["basic_cleaning"])


class MarketDataRawArrivedEvent(BaseEvent):
	"""
	市场原始数据到达事件

	触发时机：从外部数据源接收到原始数据
	业务场景：数据采集、文件导入、网络推送

	典型订阅者：
	- DataCleaningEngine: 开始数据清洗
	- DataValidationEngine: 开始数据验证
	- DataMonitor: 记录数据到达

	事件数据包含：
	- metadata: 数据元数据
	- raw_data_info: 原始数据信息（格式、大小等）
	- arrival_context: 到达上下文（来源、时间等）
	"""

	def __init__ (
			self,
			metadata: MarketDataMetadata,
			raw_format: str,
			raw_size_bytes: int,
			source_channel: str = "api",
			checksum: Optional[str] = None,
			arrival_context: Optional[Dict[str, Any]] = None,
			**kwargs
	):
		super().__init__(
			event_type=DataEventType.MARKET_DATA_RAW_ARRIVED.value,
			source="data_receiver",
			module="data",
			priority=EventPriority.NORMAL,
			category=EventCategory.BUSINESS,
			**kwargs
		)

		# 更新元数据状态
		metadata.status = DataProcessingStatus.RAW.value

		self.data = {
			"metadata": metadata.to_dict(),
			"raw_format": raw_format,
			"raw_size_bytes": raw_size_bytes,
			"source_channel": source_channel,
			"checksum": checksum,
			"arrival_context": arrival_context or {},
			"arrival_time": datetime.now().isoformat(),
			"status": DataProcessingStatus.RAW.value,
			"next_steps": ["cleaning", "validation", "storage"],
			"processing_requirements": _get_processing_requirements(metadata.data_type),
		}

		# 存储元数据引用（不包含在序列化中）
		self._metadata = metadata

	@property
	def metadata (self) -> MarketDataMetadata:
		"""获取元数据对象"""
		return self._metadata

	@property
	def arrival_time (self) -> datetime:
		"""获取到达时间"""
		return datetime.fromisoformat(self.data["arrival_time"])


def _get_step_metrics (processing_step: str) -> Dict[str, str]:
	"""获取步骤度量指标"""
	metrics_map = {
		"cleaning": ["records_cleaned", "errors_fixed", "time_taken"],
		"validation": ["records_validated", "errors_found", "validation_score"],
		"transformation": ["records_transformed", "features_generated", "transformation_time"],
		"enrichment": ["records_enriched", "indicators_calculated", "enrichment_time"],
	}
	return {
		"step": processing_step,
		"metrics": metrics_map.get(processing_step, ["records_processed"]),
	}


class MarketDataProcessingEvent(BaseEvent):
	"""
	市场数据处理中事件

	触发时机：数据清洗、转换、指标计算等处理过程中
	业务场景：数据处理进度更新、状态报告

	典型订阅者：
	- ProgressMonitor: 更新处理进度
	- UserInterface: 显示处理状态
	- DataQualityEngine: 监控处理质量

	事件数据包含：
	- metadata: 数据元数据
	- processing_step: 当前处理步骤
	- progress: 处理进度（0-100）
	- step_details: 步骤详细信息
	"""

	def __init__ (
			self,
			metadata: MarketDataMetadata,
			processing_step: str,
			progress: float,
			current_symbol: Optional[str] = None,
			processed_count: int = 0,
			step_details: Optional[Dict[str, Any]] = None,
			**kwargs
	):
		# 根据进度设置优先级
		priority = EventPriority.LOW
		if progress >= 90:
			priority = EventPriority.NORMAL  # 接近完成，提高优先级

		super().__init__(
			event_type=DataEventType.MARKET_DATA_PROCESSING.value,
			source="data_processor",
			module="data",
			priority=priority,
			category=EventCategory.BUSINESS,
			**kwargs
		)

		# 更新元数据状态
		metadata.status = DataProcessingStatus.PROCESSING.value

		self.data = {
			"metadata": metadata.to_dict(),
			"processing_step": processing_step,
			"progress": progress,
			"current_symbol": current_symbol,
			"processed_count": processed_count,
			"step_details": step_details or {},
			"timestamp": datetime.now().isoformat(),
			"status": DataProcessingStatus.PROCESSING.value,
			"estimated_remaining": self._estimate_remaining(progress),
			"step_metrics": _get_step_metrics(processing_step),
		}

		self._metadata = metadata

	def _estimate_remaining (self, progress: float) -> Optional[float]:
		"""估计剩余处理时间（秒）"""
		if progress <= 0:
			return None

		# 简单估计：假设线性进度
		elapsed = (datetime.now() - self.timestamp).total_seconds()
		if progress < 100:
			remaining = (elapsed / progress) * (100 - progress)
			return round(remaining, 1)
		return 0.0

	@property
	def metadata (self) -> MarketDataMetadata:
		"""获取元数据对象"""
		return self._metadata

	@property
	def progress_percentage (self) -> float:
		"""获取进度百分比"""
		return self.data["progress"]


def _get_recommended_use (data_type: str) -> List[str]:
	"""根据数据类型获取推荐用途"""
	usage_map = {
		"tick": ["high_frequency_trading", "market_microstructure"],
		"1min": ["intraday_trading", "short_term_analysis"],
		"5min": ["swing_trading", "medium_term_analysis"],
		"daily": ["position_trading", "long_term_analysis", "backtesting"],
	}
	return usage_map.get(data_type, ["general_analysis"])


def _generate_data_summary (
		metadata: MarketDataMetadata,
		indicators: List[str]
) -> Dict[str, Any]:
	"""生成数据摘要"""
	return {
		"data_type": metadata.data_type,
		"symbol_count": len(metadata.symbols),
		"time_range": {
			"start": metadata.start_time.isoformat(),
			"end": metadata.end_time.isoformat(),
		},
		"record_count": metadata.record_count,
		"indicators_available": indicators,
		"quality_score": metadata.quality_score,
		"recommended_use": _get_recommended_use(metadata.data_type),
	}


class MarketDataProcessedEvent(BaseEvent):
	"""
	市场数据处理完成事件

	触发时机：数据清洗、转换、指标计算等处理完成
	业务场景：数据处理完成通知、触发下游处理

	典型订阅者：
	- DataStorageEngine: 存储处理后的数据
	- StrategyModule: 获取处理后的数据
	- AnalysisModule: 进行数据分析
	- CacheModule: 更新数据缓存

	事件数据包含：
	- metadata: 数据元数据
	- processing_results: 处理结果汇总
	- indicators_calculated: 已计算的指标列表
	- storage_info: 存储信息
	"""

	def __init__ (
			self,
			metadata: MarketDataMetadata,
			processing_duration_seconds: float,
			indicators_calculated: List[str],
			storage_location: str,
			processing_stats: Optional[Dict[str, Any]] = None,
			quality_metrics: Optional[Dict[str, Any]] = None,
			**kwargs
	):
		super().__init__(
			event_type=DataEventType.MARKET_DATA_PROCESSED.value,
			source="data_processor",
			module="data",
			priority=EventPriority.NORMAL,
			category=EventCategory.BUSINESS,
			**kwargs
		)

		# 更新元数据状态和质量评分
		metadata.status = DataProcessingStatus.PROCESSED.value
		if quality_metrics and "overall_score" in quality_metrics:
			metadata.quality_score = quality_metrics["overall_score"]

		self.data = {
			"metadata": metadata.to_dict(),
			"processing_duration_seconds": round(processing_duration_seconds, 2),
			"indicators_calculated": indicators_calculated,
			"indicator_count": len(indicators_calculated),
			"storage_location": storage_location,
			"processing_stats": processing_stats or {},
			"quality_metrics": quality_metrics or {},
			"completion_time": datetime.now().isoformat(),
			"status": DataProcessingStatus.PROCESSED.value,
			"available_for": ["strategy", "backtest", "analysis", "research"],
			"data_summary": _generate_data_summary(metadata, indicators_calculated),
		}

		self._metadata = metadata

	@property
	def metadata (self) -> MarketDataMetadata:
		"""获取元数据对象"""
		return self._metadata

	@property
	def completion_time (self) -> datetime:
		"""获取完成时间"""
		return datetime.fromisoformat(self.data["completion_time"])


def _generate_recommendations (
		passed: bool,
		quality_score: float,
		issues_found: Optional[List[Dict[str, Any]]]
) -> List[str]:
	"""根据验证结果生成建议"""
	recommendations = []

	if not passed:
		recommendations.append("数据验证未通过，建议检查数据源")

	if quality_score < 80:
		recommendations.append(f"数据质量评分较低 ({quality_score})，建议进行数据清洗")

	if issues_found:
		critical_issues = [i for i in issues_found if i.get("severity") == "critical"]
		if critical_issues:
			recommendations.append(f"发现 {len(critical_issues)} 个严重问题，建议立即处理")

	if passed and quality_score >= 90:
		recommendations.append("数据质量优秀，可以用于生产环境")

	if not recommendations:
		recommendations.append("数据验证通过，可以正常使用")

	return recommendations


class MarketDataValidatedEvent(BaseEvent):
	"""
	市场数据验证完成事件

	触发时机：数据验证完成、质量检查完成
	业务场景：数据质量确认、可用性通知

	典型订阅者：
	- QualityMonitor: 记录质量指标
	- AlertModule: 处理验证失败
	- UserInterface: 显示数据质量
	- StrategyModule: 确认数据可用性

	事件数据包含：
	- metadata: 数据元数据
	- validation_results: 验证结果
	- quality_metrics: 质量指标
	- is_ready_for_use: 是否可用标记
	"""

	def __init__ (
			self,
			metadata: MarketDataMetadata,
			validation_results: Dict[str, Any],
			quality_score: float,
			validation_rules_applied: List[str],
			passed: bool = True,
			issues_found: Optional[List[Dict[str, Any]]] = None,
			**kwargs
	):
		super().__init__(
			event_type=DataEventType.MARKET_DATA_VALIDATED.value,
			source="data_validator",
			module="data",
			priority=EventPriority.NORMAL,
			category=EventCategory.BUSINESS,
			**kwargs
		)

		# 更新元数据状态和质量评分
		metadata.status = DataProcessingStatus.VALIDATED.value
		metadata.quality_score = quality_score

		self.data = {
			"metadata": metadata.to_dict(),
			"validation_results": validation_results,
			"quality_score": quality_score,
			"validation_rules_applied": validation_rules_applied,
			"rule_count": len(validation_rules_applied),
			"passed": passed,
			"issues_found": issues_found or [],
			"issue_count": len(issues_found or []),
			"validation_time": datetime.now().isoformat(),
			"status": DataProcessingStatus.VALIDATED.value,
			"is_ready_for_use": passed and quality_score >= 80.0,
			"recommendations": _generate_recommendations(passed, quality_score, issues_found),
		}

		self._metadata = metadata

	@property
	def metadata (self) -> MarketDataMetadata:
		"""获取元数据对象"""
		return self._metadata

	@property
	def is_ready (self) -> bool:
		"""数据是否准备好使用"""
		return self.data.get("is_ready_for_use", False)


class MarketDataRequestEvent(BaseEvent):
	"""
	市场数据请求事件

	触发时机：策略、分析或其他模块需要市场数据时
	业务场景：数据获取、缓存查询、数据源选择

	典型订阅者：
	- MarketDataService: 处理数据请求
	- CacheModule: 检查缓存数据
	- DataSourceRouter: 选择合适的数据源
	- MonitoringModule: 记录数据请求

	事件数据包含：
	- request: 数据请求参数
	- requester: 请求者信息
	- priority: 请求优先级
	- expected_response_time: 期望响应时间
	"""

	def __init__ (
			self,
			request: MarketDataRequest,
			requester: str,
			requester_type: str = "strategy",
			request_id: Optional[str] = None,
			priority: int = EventPriority.NORMAL,
			expected_response_seconds: Optional[float] = None,
			callback_url: Optional[str] = None,
			**kwargs
	):
		super().__init__(
			event_type=DataEventType.MARKET_DATA_REQUEST.value,
			source=requester,
			module="data",
			priority=priority,
			category=EventCategory.BUSINESS,
			**kwargs
		)

		self.data = {
			"request": request.to_dict(),
			"requester": requester,
			"requester_type": requester_type,
			"request_id": request_id or self.event_id,
			"expected_response_seconds": expected_response_seconds,
			"callback_url": callback_url,
			"request_time": datetime.now().isoformat(),
			"status": "pending",
			"attempts": 0,
			"timeout_seconds": expected_response_seconds or 30.0  # 默认30秒超时
		}

		# 存储请求对象引用（不包含在序列化中）
		self._request = request

	@property
	def request (self) -> MarketDataRequest:
		"""获取请求对象"""
		return self._request

	@property
	def request_id (self) -> str:
		"""获取请求ID"""
		return self.data["request_id"]

	@property
	def symbol (self) -> str:
		"""获取股票代码"""
		return self._request.symbol

	@property
	def data_type (self) -> str:
		"""获取数据类型"""
		return self._request.data_type

	def mark_processing (self, attempt: int = 1) -> None:
		"""标记请求开始处理"""
		self.data["status"] = "processing"
		self.data["attempts"] = attempt
		self.data["processing_start_time"] = datetime.now().isoformat()

	def mark_completed (self, result_count: int = 0, source: Optional[str] = None) -> None:
		"""标记请求完成"""
		self.data["status"] = "completed"
		self.data["result_count"] = result_count
		self.data["completed_time"] = datetime.now().isoformat()
		if source:
			self.data["data_source"] = source

	def mark_failed (self, error: str, retryable: bool = True) -> None:
		"""标记请求失败"""
		self.data["status"] = "failed"
		self.data["error"] = error
		self.data["retryable"] = retryable
		self.data["failed_time"] = datetime.now().isoformat()

	def mark_timeout (self) -> None:
		"""标记请求超时"""
		self.data["status"] = "timeout"
		self.data["timeout_time"] = datetime.now().isoformat()

	def is_completed (self) -> bool:
		"""检查请求是否完成"""
		return self.data.get("status") == "completed"

	def is_failed (self) -> bool:
		"""检查请求是否失败"""
		return self.data.get("status") == "failed"

	def is_timeout (self) -> bool:
		"""检查请求是否超时"""
		return self.data.get("status") == "timeout"

	def can_retry (self) -> bool:
		"""检查是否可以重试"""
		return (self.data.get("status") in ["failed", "timeout"] and
		        self.data.get("retryable", True) and
		        self.data.get("attempts", 0) < 3)  # 最多重试3次


# 导出所有事件类
__all__ = [
	"MarketDataRequest",
	"MarketDataMetadata",
	"MarketDataRawArrivedEvent",
	"MarketDataProcessingEvent",
	"MarketDataProcessedEvent",
	"MarketDataValidatedEvent",
	"MarketDataRequestEvent",
]
