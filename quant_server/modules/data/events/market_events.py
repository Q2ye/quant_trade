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

from datetime import datetime
from typing import Dict, Any, List, Optional
from dataclasses import dataclass, field
from enum import Enum

from quant_server.core.events import BaseEvent, EventPriority, EventCategory
from .types import DataEventType, DataProcessingStatus


@dataclass
class MarketDataMetadata:
    """
    市场数据元数据
    描述市场数据的基本信息和处理状态
    """
    # 基本信息
    data_type: str                    # 数据类型：tick/1min/5min/daily等
    symbols: List[str]                # 标的列表
    start_time: datetime              # 数据开始时间
    end_time: datetime                # 数据结束时间
    record_count: int                 # 记录数量

    # 来源信息
    source: str = "unknown"           # 数据来源：tushare/baostock等
    source_format: str = "raw"        # 原始格式：json/csv/parquet
    source_version: str = "1.0"       # 数据源版本

    # 处理信息
    processing_version: str = "1.0"   # 处理版本
    quality_score: float = 0.0        # 数据质量评分（0-100）
    status: str = DataProcessingStatus.RAW.value  # 处理状态

    # 元信息
    metadata: Dict[str, Any] = field(default_factory=dict)  # 额外元数据

    def to_dict(self) -> Dict[str, Any]:
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
    def from_dict(cls, data: Dict[str, Any]) -> "MarketDataMetadata":
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

    def __init__(
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
            "processing_requirements": self._get_processing_requirements(metadata.data_type),
        }

        # 存储元数据引用（不包含在序列化中）
        self._metadata = metadata

    def _get_processing_requirements(self, data_type: str) -> List[str]:
        """根据数据类型获取处理要求"""
        requirements = {
            "tick": ["time_alignment", "duplicate_removal", "price_validation"],
            "1min": ["time_alignment", "missing_fill", "outlier_detection"],
            "5min": ["time_alignment", "missing_fill", "consistency_check"],
            "daily": ["dividend_adjustment", "missing_fill", "consistency_check"],
        }
        return requirements.get(data_type, ["basic_cleaning"])

    @property
    def metadata(self) -> MarketDataMetadata:
        """获取元数据对象"""
        return self._metadata

    @property
    def arrival_time(self) -> datetime:
        """获取到达时间"""
        return datetime.fromisoformat(self.data["arrival_time"])


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

    def __init__(
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
            "step_metrics": self._get_step_metrics(processing_step),
        }

        self._metadata = metadata

    def _estimate_remaining(self, progress: float) -> Optional[float]:
        """估计剩余处理时间（秒）"""
        if progress <= 0:
            return None

        # 简单估计：假设线性进度
        elapsed = (datetime.now() - self.timestamp).total_seconds()
        if progress < 100:
            remaining = (elapsed / progress) * (100 - progress)
            return round(remaining, 1)
        return 0.0

    def _get_step_metrics(self, processing_step: str) -> Dict[str, str]:
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

    @property
    def metadata(self) -> MarketDataMetadata:
        """获取元数据对象"""
        return self._metadata

    @property
    def progress_percentage(self) -> float:
        """获取进度百分比"""
        return self.data["progress"]


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

    def __init__(
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
            "data_summary": self._generate_data_summary(metadata, indicators_calculated),
        }

        self._metadata = metadata

    def _generate_data_summary(
        self,
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
            "recommended_use": self._get_recommended_use(metadata.data_type),
        }

    def _get_recommended_use(self, data_type: str) -> List[str]:
        """根据数据类型获取推荐用途"""
        usage_map = {
            "tick": ["high_frequency_trading", "market_microstructure"],
            "1min": ["intraday_trading", "short_term_analysis"],
            "5min": ["swing_trading", "medium_term_analysis"],
            "daily": ["position_trading", "long_term_analysis", "backtesting"],
        }
        return usage_map.get(data_type, ["general_analysis"])

    @property
    def metadata(self) -> MarketDataMetadata:
        """获取元数据对象"""
        return self._metadata

    @property
    def completion_time(self) -> datetime:
        """获取完成时间"""
        return datetime.fromisoformat(self.data["completion_time"])


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

    def __init__(
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
            "recommendations": self._generate_recommendations(passed, quality_score, issues_found),
        }

        self._metadata = metadata

    def _generate_recommendations(
        self,
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

    @property
    def metadata(self) -> MarketDataMetadata:
        """获取元数据对象"""
        return self._metadata

    @property
    def is_ready(self) -> bool:
        """数据是否准备好使用"""
        return self.data.get("is_ready_for_use", False)


# 导出所有事件类
__all__ = [
    "MarketDataMetadata",
    "MarketDataRawArrivedEvent",
    "MarketDataProcessingEvent",
    "MarketDataProcessedEvent",
    "MarketDataValidatedEvent",
]