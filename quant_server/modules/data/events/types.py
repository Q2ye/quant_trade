"""
数据模块事件类型枚举
继承自核心事件类型，提供数据模块特定的事件类型

设计原则：
1. 继承性：基于核心事件类型进行扩展
2. 规范性：使用统一的命名约定：module.domain.action.status
3. 完整性：覆盖数据模块所有业务场景
"""

from enum import Enum, IntEnum
from typing import Dict

from quant_server.core.events.types import (
    EventPriority as CoreEventPriority,
)


class DataEventType(str, Enum):
    """
    数据模块事件类型枚举

    命名规范：data.{domain}.{action}.{status}
    - data: 模块名
    - domain: 业务领域（sync/quality/research/market/factor/clean）
    - action: 业务动作
    - status: 动作状态（started/progress/completed/failed等）
    """

    # ==================== 数据同步事件 ====================
    SYNC_STARTED = "data.sync.started"
    SYNC_PROGRESS = "data.sync.progress"
    SYNC_COMPLETED = "data.sync.completed"
    SYNC_FAILED = "data.sync.failed"
    SYNC_CANCELLED = "data.sync.cancelled"

    # ==================== 数据质量事件 ====================
    QUALITY_CHECK_STARTED = "data.quality.check.started"
    QUALITY_ISSUE_FOUND = "data.quality.issue.found"
    QUALITY_CHECK_COMPLETED = "data.quality.check.completed"
    QUALITY_CHECK_FAILED = "data.quality.check.failed"

    # ==================== 数据清洗事件 ====================
    CLEAN_STARTED = "data.clean.started"
    CLEAN_PROGRESS = "data.clean.progress"
    CLEAN_COMPLETED = "data.clean.completed"
    CLEAN_FAILED = "data.clean.failed"
    CLEAN_APPLIED = "data.clean.applied"
    CLEAN_VALIDATION_COMPLETED = "data.clean.validation.completed"
    CLEAN_STATISTICS_UPDATED = "data.clean.statistics.updated"

    # ==================== 因子研究事件 ====================
    RESEARCH_STARTED = "data.research.started"
    RESEARCH_PROGRESS = "data.research.progress"
    RESEARCH_COMPLETED = "data.research.completed"
    RESEARCH_FAILED = "data.research.failed"

    # ==================== 市场数据处理事件 ====================
    MARKET_DATA_RAW_ARRIVED = "data.market.raw.arrived"
    MARKET_DATA_PROCESSING = "data.market.processing"
    MARKET_DATA_PROCESSED = "data.market.processed"
    MARKET_DATA_VALIDATED = "data.market.validated"
    MARKET_DATA_ERROR = "data.market.error"

    # ==================== 因子计算事件 ====================
    FACTOR_CALCULATION_STARTED = "data.factor.calculation.started"
    FACTOR_CALCULATION_PROGRESS = "data.factor.calculation.progress"
    FACTOR_CALCULATION_COMPLETED = "data.factor.calculation.completed"
    FACTOR_CALCULATION_FAILED = "data.factor.calculation.failed"

    # ==================== 数据服务事件 ====================
    DATA_SERVICE_READY = "data.service.ready"
    DATA_SERVICE_ERROR = "data.service.error"
    DATA_CACHE_UPDATED = "data.cache.updated"
    DATA_EXPORT_COMPLETED = "data.export.completed"


class DataEventPriority(IntEnum):
    """
    数据模块事件优先级枚举
    基于核心优先级，提供数据模块特定的优先级常量
    """
    LOW = CoreEventPriority.LOW
    NORMAL = CoreEventPriority.NORMAL
    HIGH = CoreEventPriority.HIGH
    CRITICAL = CoreEventPriority.CRITICAL

    # 数据模块特定优先级
    DATA_CRITICAL = 90  # 数据关键操作，低于系统CRITICAL


class DataProcessingStatus(str, Enum):
    """数据处理状态枚举"""
    RAW = "raw"              # 原始数据
    CLEANING = "cleaning"    # 清洗中
    PROCESSING = "processing" # 处理中
    VALIDATING = "validating" # 验证中
    PROCESSED = "processed"   # 处理完成
    VALIDATED = "validated"   # 验证完成
    ERROR = "error"          # 处理错误
    CANCELLED = "cancelled"  # 已取消


class FactorCalculationStatus(str, Enum):
    """因子计算状态枚举"""
    PENDING = "pending"      # 等待计算
    CALCULATING = "calculating" # 计算中
    VALIDATING = "validating"  # 验证中
    COMPLETED = "completed"  # 计算完成
    FAILED = "failed"        # 计算失败
    CANCELLED = "cancelled"  # 已取消


class DataQualitySeverity(str, Enum):
    """数据质量问题严重程度"""
    LOW = "low"        # 低风险问题
    MEDIUM = "medium"  # 中风险问题
    HIGH = "high"      # 高风险问题
    CRITICAL = "critical" # 严重问题


class DataSyncType(str, Enum):
    """数据同步类型"""
    FULL = "full"      # 全量同步
    INCREMENTAL = "incremental" # 增量同步
    REAL_TIME = "real_time" # 实时同步
    MANUAL = "manual"  # 手动同步


class DataCleanStatus(str, Enum):
    """数据清洗状态枚举"""
    PENDING = "pending"      # 等待中
    RUNNING = "running"      # 运行中
    COMPLETED = "completed"  # 已完成
    FAILED = "failed"        # 失败
    APPLIED = "applied"      # 已应用
    CANCELLED = "cancelled"  # 已取消


class DataCleanRule(str, Enum):
    """数据清洗规则枚举"""
    MISSING = "missing"          # 缺失数据检查
    DUPLICATE = "duplicate"      # 重复数据检查
    OUTLIER = "outlier"          # 异常值检查
    INCONSISTENT = "inconsistent" # 不一致数据检查
    FORMAT = "format"            # 格式检查
    RANGE = "range"              # 范围检查
    CONSISTENCY = "consistency"  # 一致性检查


def get_event_type_descriptions() -> Dict[str, str]:
    """获取所有事件类型的描述"""
    descriptions = {
        # 同步事件
        DataEventType.SYNC_STARTED: "数据同步任务开始",
        DataEventType.SYNC_PROGRESS: "数据同步进度更新",
        DataEventType.SYNC_COMPLETED: "数据同步任务完成",
        DataEventType.SYNC_FAILED: "数据同步任务失败",
        DataEventType.SYNC_CANCELLED: "数据同步任务取消",

        # 质量事件
        DataEventType.QUALITY_CHECK_STARTED: "数据质量检查开始",
        DataEventType.QUALITY_ISSUE_FOUND: "发现数据质量问题",
        DataEventType.QUALITY_CHECK_COMPLETED: "数据质量检查完成",
        DataEventType.QUALITY_CHECK_FAILED: "数据质量检查失败",

        # 清洗事件
        DataEventType.CLEAN_STARTED: "数据清洗任务开始",
        DataEventType.CLEAN_PROGRESS: "数据清洗进度更新",
        DataEventType.CLEAN_COMPLETED: "数据清洗任务完成",
        DataEventType.CLEAN_FAILED: "数据清洗任务失败",
        DataEventType.CLEAN_APPLIED: "数据清洗结果已应用",
        DataEventType.CLEAN_VALIDATION_COMPLETED: "数据验证完成",
        DataEventType.CLEAN_STATISTICS_UPDATED: "数据清洗统计信息更新",

        # 研究事件
        DataEventType.RESEARCH_STARTED: "因子研究任务开始",
        DataEventType.RESEARCH_PROGRESS: "因子研究进度更新",
        DataEventType.RESEARCH_COMPLETED: "因子研究任务完成",
        DataEventType.RESEARCH_FAILED: "因子研究任务失败",

        # 市场事件
        DataEventType.MARKET_DATA_RAW_ARRIVED: "原始市场数据到达",
        DataEventType.MARKET_DATA_PROCESSING: "市场数据处理中",
        DataEventType.MARKET_DATA_PROCESSED: "市场数据处理完成",
        DataEventType.MARKET_DATA_VALIDATED: "市场数据验证完成",
        DataEventType.MARKET_DATA_ERROR: "市场数据处理错误",

        # 因子计算事件
        DataEventType.FACTOR_CALCULATION_STARTED: "因子计算开始",
        DataEventType.FACTOR_CALCULATION_PROGRESS: "因子计算进度更新",
        DataEventType.FACTOR_CALCULATION_COMPLETED: "因子计算完成",
        DataEventType.FACTOR_CALCULATION_FAILED: "因子计算失败",

        # 数据服务事件
        DataEventType.DATA_SERVICE_READY: "数据服务准备就绪",
        DataEventType.DATA_SERVICE_ERROR: "数据服务发生错误",
        DataEventType.DATA_CACHE_UPDATED: "数据缓存更新",
        DataEventType.DATA_EXPORT_COMPLETED: "数据导出完成",
    }
    return descriptions


def get_event_type_category(event_type: DataEventType) -> str:
    """根据事件类型获取业务分类"""
    type_str = event_type.value

    if "sync" in type_str:
        return "sync"
    elif "quality" in type_str:
        return "quality"
    elif "clean" in type_str:
        return "clean"  # 新增清洗分类
    elif "research" in type_str:
        return "research"
    elif "market" in type_str:
        return "market"
    elif "factor" in type_str:
        return "factor"
    elif "service" in type_str or "cache" in type_str or "export" in type_str:
        return "service"
    else:
        return "unknown"


# 导出所有类型
__all__ = [
    # 事件类型
    "DataEventType",
    "DataEventPriority",

    # 状态枚举
    "DataProcessingStatus",
    "FactorCalculationStatus",
    "DataCleanStatus",

    # 业务类型枚举
    "DataQualitySeverity",
    "DataSyncType",
    "DataCleanRule",

    # 工具函数
    "get_event_type_descriptions",
    "get_event_type_category",
]