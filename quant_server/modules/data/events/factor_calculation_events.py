"""
因子计算事件定义
用于因子计算过程中的事件通知

职责范围：
1. 因子计算任务开始
2. 因子计算进度更新
3. 因子计算完成
4. 因子计算结果验证

设计原则：
- 专注于因子计算过程
- 与市场数据处理事件解耦
- 支持批量因子计算
"""

from datetime import datetime
from typing import Dict, Any, List, Optional
from dataclasses import dataclass
from enum import Enum

from quant_server.core.events.base import BaseEvent
from .types import DataEventType, DataEventPriority


class FactorCalculationStatus(str, Enum):
	"""因子计算状态"""
	PENDING = "pending"  # 等待计算
	CALCULATING = "calculating"  # 计算中
	COMPLETED = "completed"  # 计算完成
	FAILED = "failed"  # 计算失败


@dataclass
class FactorMetadata:
	"""因子元数据"""
	factor_name: str  # 因子名称
	factor_type: str  # 因子类型：technical/fundamental/alternative
	calculation_method: str  # 计算方法
	parameters: Dict[str, Any]  # 计算参数
	required_fields: List[str]  # 需要的数据字段
	output_fields: List[str]  # 输出字段

	def to_dict (self) -> Dict[str, Any]:
		"""转换为字典"""
		return {
			"factor_name": self.factor_name,
			"factor_type": self.factor_type,
			"calculation_method": self.calculation_method,
			"parameters": self.parameters,
			"required_fields": self.required_fields,
			"output_fields": self.output_fields,
		}


class FactorCalculationStartedEvent(BaseEvent):
	"""
	因子计算开始事件

	触发时机：
	- 因子计算任务启动
	- 批量因子计算开始

	事件数据：
	- factor_metadata: 因子元数据列表
	- calculation_config: 计算配置
	- target_symbols: 目标标的

	订阅者：
	- 计算资源管理器：分配计算资源
	- 进度监控模块：开始监控
	"""

	def __init__ (
			self,
			calculation_id: str,
			factors: List[FactorMetadata],
			target_symbols: List[str],
			calculation_config: Dict[str, Any],
			**kwargs
	):
		super().__init__(
			module="data",
			event_type=DataEventType.FACTOR_CALCULATION_STARTED.value,
			priority=DataEventPriority.NORMAL,
			source="factor_calculator",
			**kwargs
		)

		self.data = {
			"calculation_id": calculation_id,
			"factors": [factor.to_dict() for factor in factors],
			"target_symbols": target_symbols,
			"symbol_count": len(target_symbols),
			"calculation_config": calculation_config,
			"start_time": datetime.now().isoformat(),
			"status": FactorCalculationStatus.PENDING.value,
			"estimated_complexity": self._estimate_complexity(factors, target_symbols)
		}

		self.calculation_id = calculation_id
		self.factors = factors

	def _estimate_complexity (self, factors: List[FactorMetadata], symbols: List[str]) -> str:
		"""估计计算复杂度"""
		total_complexity = len(factors) * len(symbols)
		if total_complexity > 10000:
			return "high"
		elif total_complexity > 1000:
			return "medium"
		else:
			return "low"


class FactorCalculationProgressEvent(BaseEvent):
	"""
	因子计算进度事件

	触发时机：
	- 因子计算进度更新
	- 批量计算中的进度报告

	事件数据：
	- calculation_id: 计算ID
	- progress: 计算进度
	- current_factor: 当前计算的因子
	- current_symbol: 当前计算的标的

	订阅者：
	- 进度监控模块：更新进度显示
	- 用户界面：显示计算状态
	"""

	def __init__ (
			self,
			calculation_id: str,
			progress: float,
			current_factor: Optional[str] = None,
			current_symbol: Optional[str] = None,
			processed_count: int = 0,
			failed_count: int = 0,
			**kwargs
	):
		super().__init__(
			module="data",
			event_type=DataEventType.FACTOR_CALCULATION_PROGRESS.value,
			priority=DataEventPriority.LOW,
			source="factor_calculator",
			**kwargs
		)

		self.data = {
			"calculation_id": calculation_id,
			"progress": progress,
			"current_factor": current_factor,
			"current_symbol": current_symbol,
			"processed_count": processed_count,
			"failed_count": failed_count,
			"timestamp": datetime.now().isoformat(),
			"status": FactorCalculationStatus.CALCULATING.value,
			"estimated_remaining": self._estimate_remaining(progress)
		}

	def _estimate_remaining (self, progress: float) -> Optional[float]:
		"""估计剩余时间（分钟）"""
		if progress <= 0:
			return None
		elapsed = (datetime.now() - self.timestamp).total_seconds() / 60
		if progress < 100:
			remaining = (elapsed / progress) * (100 - progress)
			return round(remaining, 1)
		return 0.0


class FactorCalculationCompletedEvent(BaseEvent):
	"""
	因子计算完成事件

	触发时机：
	- 因子计算任务完成
	- 所有因子计算完毕

	事件数据：
	- calculation_id: 计算ID
	- calculation_results: 计算结果汇总
	- storage_info: 存储信息
	- validation_results: 验证结果

	订阅者：
	- 数据存储引擎：存储因子数据
	- 策略模块：使用计算好的因子
	- 研究模块：进行因子分析
	"""

	def __init__ (
			self,
			calculation_id: str,
			factors_calculated: List[str],
			symbols_processed: int,
			calculation_duration_seconds: float,
			storage_location: str,
			validation_results: Optional[Dict[str, Any]] = None,
			calculation_stats: Optional[Dict[str, Any]] = None,
			success: bool = True,
			error_info: Optional[str] = None,
			**kwargs
	):
		super().__init__(
			module="data",
			event_type=DataEventType.FACTOR_CALCULATION_COMPLETED.value,
			priority=DataEventPriority.NORMAL,
			source="factor_calculator",
			**kwargs
		)

		# 计算成功率
		success_rate = 100.0 if success else 0.0

		self.data = {
			"calculation_id": calculation_id,
			"factors_calculated": factors_calculated,
			"symbols_processed": symbols_processed,
			"calculation_duration_seconds": round(calculation_duration_seconds, 2),
			"storage_location": storage_location,
			"validation_results": validation_results or {},
			"calculation_stats": calculation_stats or {},
			"success": success,
			"success_rate": success_rate,
			"error_info": error_info,
			"completion_time": datetime.now().isoformat(),
			"status": FactorCalculationStatus.COMPLETED.value if success else FactorCalculationStatus.FAILED.value
		}


# 导出所有事件类
__all__ = [
	"FactorCalculationStatus",
	"FactorMetadata",
	"FactorCalculationStartedEvent",
	"FactorCalculationProgressEvent",
	"FactorCalculationCompletedEvent",
]