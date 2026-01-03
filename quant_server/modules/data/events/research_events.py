"""
因子研究事件定义
用于因子研究过程中的事件通知

业务场景：
1. 因子挖掘和计算
2. 因子有效性检验
3. 因子组合优化
4. 研究报告生成
"""

from datetime import datetime
from typing import Dict, Any, List, Optional
from dataclasses import field

from quant_server.core.events.base import BaseEvent, EventPriority
from quant_server.modules.data.events.types import DataEventType


class DataResearchStartedEvent(BaseEvent):
	"""
	因子研究开始事件

	触发时机：
	- 启动因子研究任务
	- 因子批量计算开始

	事件数据：
	- research_type: 研究类型（单因子/多因子/组合）
	- research_target: 研究目标（IC分析/收益率分析等）
	- parameters: 研究参数配置
	"""

	def __init__ (
			self,
			research_id: str,
			research_type: str,
			target_factors: List[str],
			universe: str = "all",
			time_range: Dict[str, str] = None,
			**kwargs
	):
		super().__init__(
			module="events",
			event_type=DataEventType.RESEARCH_STARTED.value,
			priority=EventPriority.NORMAL,
			source="data_research_engine",
			**kwargs
		)

		if time_range is None:
			time_range = {"start": "2020-01-01", "end": datetime.now().strftime("%Y-%m-%d")}

		self.data = {
			"research_id": research_id,
			"research_type": research_type,
			"target_factors": target_factors,
			"universe": universe,
			"time_range": time_range,
			"start_time": datetime.now().isoformat(),
			"status": "running",
			"progress": 0.0,
			"current_step": "initializing"
		}


class DataResearchProgressEvent(BaseEvent):
	"""
	因子研究进度事件

	触发时机：
	- 研究任务执行到关键节点
	- 定时报告研究进度

	事件数据：
	- progress: 当前进度（0-100）
	- current_step: 当前执行步骤
	- metrics: 当前步骤的指标
	"""

	def __init__ (
			self,
			research_id: str,
			progress: float,
			current_step: str,
			step_details: Optional[Dict[str, Any]] = None,
			metrics: Optional[Dict[str, float]] = None,
			**kwargs
	):
		super().__init__(
			module="events",
			event_type=DataEventType.RESEARCH_PROGRESS.value,
			priority=EventPriority.LOW,
			source="data_research_engine",
			**kwargs
		)

		self.data = {
			"research_id": research_id,
			"progress": progress,
			"current_step": current_step,
			"step_details": step_details or {},
			"metrics": metrics or {},
			"timestamp": datetime.now().isoformat(),
			"estimated_remaining": self._estimate_remaining(progress)
		}

	def _estimate_remaining (self, progress: float) -> Optional[float]:
		"""估计剩余时间（分钟）"""
		if progress <= 0:
			return None
		elapsed = (datetime.now() - self.timestamp).total_seconds() / 60  # 分钟
		if progress < 100:
			remaining = (elapsed / progress) * (100 - progress)
			return round(remaining, 1)
		return 0.0


class DataResearchCompletedEvent(BaseEvent):
	"""
	因子研究完成事件

	触发时机：
	- 因子研究任务完成
	- 所有分析步骤执行完毕

	事件数据：
	- results: 研究结果汇总
	- key_findings: 关键发现
	- report_data: 报告数据
	"""

	def __init__ (
			self,
			research_id: str,
			research_type: str,
			duration_seconds: float,
			results: Dict[str, Any],
			key_findings: List[str],
			report_data: Optional[Dict[str, Any]] = None,
			success: bool = True,
			error_info: Optional[str] = None,
			**kwargs
	):
		super().__init__(
			module="events",
			event_type=DataEventType.RESEARCH_COMPLETED.value,
			priority=EventPriority.NORMAL,
			source="data_research_engine",
			**kwargs
		)

		self.data = {
			"research_id": research_id,
			"research_type": research_type,
			"duration_seconds": round(duration_seconds, 2),
			"success": success,
			"results_summary": self._summarize_results(results),
			"key_findings": key_findings,
			"report_data": report_data or {},
			"completion_time": datetime.now().isoformat(),
			"error_info": error_info,
			"recommendations": self._generate_recommendations(results, research_type)
		}

	def _summarize_results (self, results: Dict[str, Any]) -> Dict[str, Any]:
		"""汇总研究结果"""
		summary = {}

		# 提取关键指标
		if "ic_analysis" in results:
			ic_data = results["ic_analysis"]
			summary["ic_mean"] = ic_data.get("mean_ic", 0)
			summary["ic_ir"] = ic_data.get("ic_ir", 0)
			summary["ic_pvalue"] = ic_data.get("ic_pvalue", 0)

		if "return_analysis" in results:
			return_data = results["return_analysis"]
			summary["annual_return"] = return_data.get("annual_return", 0)
			summary["sharpe_ratio"] = return_data.get("sharpe_ratio", 0)
			summary["max_drawdown"] = return_data.get("max_drawdown", 0)

		return summary

	def _generate_recommendations (self, results: Dict[str, Any], research_type: str) -> List[str]:
		"""根据研究结果生成建议"""
		recommendations = []

		# 根据IC分析结果
		if "ic_analysis" in results:
			ic_mean = results["ic_analysis"].get("mean_ic", 0)
			ic_ir = results["ic_analysis"].get("ic_ir", 0)

			if ic_mean > 0.05:
				recommendations.append("因子IC值较高，建议加入策略组合")
			elif ic_mean < 0.02:
				recommendations.append("因子IC值较低，建议进一步优化或放弃")

			if ic_ir > 0.5:
				recommendations.append("因子信息比率较高，预测能力稳定")

		# 根据收益率分析
		if "return_analysis" in results:
			sharpe = results["return_analysis"].get("sharpe_ratio", 0)
			if sharpe > 1.5:
				recommendations.append("夏普比率优秀，风险调整后收益良好")

		if not recommendations:
			recommendations.append("建议进一步优化参数或尝试其他因子")

		return recommendations