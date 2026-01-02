"""
回测进度事件定义
用于回测执行过程中的进度通知和状态更新

业务场景：
1. 回测任务启动和初始化
2. 回测执行进度实时更新
3. 回测完成或失败通知
4. 回测资源使用情况监控
"""

from datetime import datetime
from typing import Dict, Any, List, Optional, Union
from decimal import Decimal

from quant_server.core.events.base import BaseEvent, EventPriority
from quant_server.core.events.types import BacktestEventType


class BacktestStartedEvent(BaseEvent):
	"""
	回测开始事件

	触发时机：
	- 用户启动回测任务
	- 定时回测任务开始执行
	- 策略优化过程中启动回测

	事件数据：
	- backtest_id: 回测任务ID
	- strategy_id: 策略ID
	- backtest_config: 回测配置参数
	- resource_allocation: 资源分配信息
	"""

	def __init__ (
			self,
			backtest_id: str,
			strategy_id: str,
			strategy_name: str,
			start_date: str,
			end_date: str,
			initial_capital: Decimal,
			backtest_config: Optional[Dict[str, Any]] = None,
			**kwargs
	):
		super().__init__(
			module="events",
			event_type=BacktestEventType.STARTED.value,
			priority=EventPriority.NORMAL,
			source="backtest_engine",
			**kwargs
		)

		if backtest_config is None:
			backtest_config = {}

		# 计算回测时间范围
		from datetime import datetime as dt
		start_dt = dt.fromisoformat(start_date)
		end_dt = dt.fromisoformat(end_date)
		total_days = (end_dt - start_dt).days

		self.data = {
			"backtest_id": backtest_id,
			"strategy_id": strategy_id,
			"strategy_name": strategy_name,
			"start_date": start_date,
			"end_date": end_date,
			"initial_capital": str(initial_capital),
			"total_days": total_days,
			"backtest_config": backtest_config,
			"start_time": datetime.now().isoformat(),
			"status": "initializing",
			"progress": 0.0,
			"current_step": "data_loading",
			"resource_allocation": self._allocate_resources(total_days, backtest_config),
			"estimated_completion": self._estimate_completion_time(total_days, backtest_config)
		}

	def _allocate_resources (self, total_days: int, config: Dict[str, Any]) -> Dict[str, Any]:
		"""分配回测资源"""
		# 根据回测规模和复杂度分配资源
		complexity = config.get("complexity", "medium")

		resource_map = {
			"simple": {"cpu_cores": 1, "memory_mb": 1024, "timeout_minutes": 30},
			"medium": {"cpu_cores": 2, "memory_mb": 2048, "timeout_minutes": 60},
			"complex": {"cpu_cores": 4, "memory_mb": 4096, "timeout_minutes": 120},
			"high_frequency": {"cpu_cores": 8, "memory_mb": 8192, "timeout_minutes": 180}
		}

		resources = resource_map.get(complexity, resource_map["medium"])

		# 根据天数调整
		if total_days > 365 * 5:  # 超过5年
			resources["memory_mb"] = min(resources["memory_mb"] * 2, 16384)
			resources["timeout_minutes"] = min(resources["timeout_minutes"] * 2, 360)

		return resources

	def _estimate_completion_time (self, total_days: int, config: Dict[str, Any]) -> Dict[str, Any]:
		"""估计完成时间"""
		# 基础时间估计（分钟）
		base_time_per_day = 0.1  # 每天0.1分钟基础处理时间

		# 根据配置调整
		complexity_factor = {
			"simple": 1.0,
			"medium": 2.0,
			"complex": 5.0,
			"high_frequency": 10.0
		}.get(config.get("complexity", "medium"), 2.0)

		# 数据频率因子
		frequency_factor = {
			"daily": 1.0,
			"hourly": 2.0,
			"minute": 5.0,
			"tick": 20.0
		}.get(config.get("data_frequency", "daily"), 1.0)

		# 计算总时间
		estimated_minutes = total_days * base_time_per_day * complexity_factor * frequency_factor

		# 添加固定开销
		estimated_minutes += 5  # 初始化时间

		return {
			"estimated_minutes": round(estimated_minutes, 1),
			"estimated_seconds": round(estimated_minutes * 60),
			"confidence": "medium",
			"factors": {
				"total_days": total_days,
				"complexity_factor": complexity_factor,
				"frequency_factor": frequency_factor
			}
		}


class BacktestProgressEvent(BaseEvent):
	"""
	回测进度事件

	触发时机：
	- 回测执行到关键阶段
	- 定时报告回测进度
	- 重要里程碑达成

	事件数据：
	- progress: 当前进度百分比
	- current_step: 当前执行步骤
	- step_details: 步骤详细信息
	- metrics: 当前步骤的性能指标
	"""

	def __init__ (
			self,
			backtest_id: str,
			progress: float,
			current_step: str,
			elapsed_seconds: float,
			step_details: Optional[Dict[str, Any]] = None,
			metrics: Optional[Dict[str, Union[float, int, str]]] = None,
			warnings: Optional[List[str]] = None,
			**kwargs
	):
		super().__init__(
			module="events",
			event_type=BacktestEventType.PROGRESS.value,
			priority=EventPriority.LOW,
			source="backtest_engine",
			**kwargs
		)

		# 计算剩余时间
		remaining_time = None
		if progress > 0:
			total_estimated = elapsed_seconds / (progress / 100)
			remaining_time = total_estimated - elapsed_seconds

		self.data = {
			"backtest_id": backtest_id,
			"progress": progress,
			"current_step": current_step,
			"step_details": step_details or {},
			"metrics": metrics or {},
			"elapsed_seconds": round(elapsed_seconds, 2),
			"remaining_seconds": round(remaining_time, 2) if remaining_time else None,
			"timestamp": datetime.now().isoformat(),
			"warnings": warnings or [],
			"checkpoint": self._create_checkpoint(current_step, progress),
			"performance_metrics": self._calculate_performance_metrics(metrics, elapsed_seconds)
		}

	def _create_checkpoint (self, step: str, progress: float) -> Dict[str, Any]:
		"""创建检查点信息"""
		checkpoints = {
			"data_loading": {"weight": 0.1, "critical": True},
			"data_preprocessing": {"weight": 0.15, "critical": True},
			"strategy_initialization": {"weight": 0.05, "critical": True},
			"simulation_running": {"weight": 0.6, "critical": True},
			"performance_calculation": {"weight": 0.08, "critical": False},
			"report_generation": {"weight": 0.02, "critical": False}
		}

		checkpoint = checkpoints.get(step, {"weight": 0.0, "critical": False})

		return {
			"step": step,
			"progress": progress,
			"weight": checkpoint["weight"],
			"critical": checkpoint["critical"],
			"completed": progress >= (checkpoint["weight"] * 100)
		}

	def _calculate_performance_metrics (self, metrics: Dict[str, Any], elapsed_seconds: float) -> Dict[str, Any]:
		"""计算性能指标"""
		if not metrics:
			return {}

		perf_metrics = {}

		# 处理速度（如果提供了处理记录数）
		if "processed_records" in metrics and "total_records" in metrics:
			processed = metrics["processed_records"]
			total = metrics["total_records"]

			if processed > 0 and elapsed_seconds > 0:
				records_per_second = processed / elapsed_seconds
				perf_metrics["records_per_second"] = round(records_per_second, 2)

				if total > 0:
					estimated_total_time = (total / processed) * elapsed_seconds
					perf_metrics["estimated_total_seconds"] = round(estimated_total_time, 2)

		# 内存使用（如果提供了）
		if "memory_usage_mb" in metrics:
			perf_metrics["memory_usage_mb"] = metrics["memory_usage_mb"]
			perf_metrics["memory_efficiency"] = "good" if metrics["memory_usage_mb"] < 1024 else "high"

		# CPU使用（如果提供了）
		if "cpu_usage_percent" in metrics:
			perf_metrics["cpu_usage_percent"] = metrics["cpu_usage_percent"]
			perf_metrics["cpu_efficiency"] = (
				"optimal" if metrics["cpu_usage_percent"] > 70 else
				"good" if metrics["cpu_usage_percent"] > 30 else
				"low"
			)

		return perf_metrics


class BacktestCompletedEvent(BaseEvent):
	"""
	回测完成事件

	触发时机：
	- 回测任务成功完成
	- 所有回测步骤执行完毕
	- 绩效报告生成完成

	事件数据：
	- backtest_results: 回测结果汇总
	- performance_metrics: 绩效指标
	- execution_summary: 执行摘要
	- report_info: 报告信息
	"""

	def __init__ (
			self,
			backtest_id: str,
			strategy_id: str,
			total_duration_seconds: float,
			backtest_results: Dict[str, Any],
			performance_metrics: Dict[str, Any],
			execution_summary: Optional[Dict[str, Any]] = None,
			report_path: Optional[str] = None,
			**kwargs
	):
		super().__init__(
			module="events",
			event_type=BacktestEventType.COMPLETED.value,
			priority=EventPriority.NORMAL,
			source="backtest_engine",
			**kwargs
		)

		if execution_summary is None:
			execution_summary = {}

		# 计算关键绩效指标
		key_metrics = self._extract_key_metrics(performance_metrics)

		# 评估回测质量
		quality_assessment = self._assess_backtest_quality(performance_metrics, execution_summary)

		self.data = {
			"backtest_id": backtest_id,
			"strategy_id": strategy_id,
			"total_duration_seconds": round(total_duration_seconds, 2),
			"completion_time": datetime.now().isoformat(),
			"backtest_results": backtest_results,
			"performance_metrics": performance_metrics,
			"key_metrics": key_metrics,
			"execution_summary": execution_summary,
			"report_path": report_path,
			"quality_assessment": quality_assessment,
			"success": True,
			"recommendations": self._generate_recommendations(key_metrics, quality_assessment)
		}

	def _extract_key_metrics (self, performance_metrics: Dict[str, Any]) -> Dict[str, Any]:
		"""提取关键绩效指标"""
		key_metrics = {}

		# 收益相关指标
		for metric in ["total_return", "annual_return", "sharpe_ratio", "max_drawdown"]:
			if metric in performance_metrics:
				key_metrics[metric] = performance_metrics[metric]

		# 风险相关指标
		for metric in ["volatility", "var_95", "cvar_95", "sortino_ratio"]:
			if metric in performance_metrics:
				key_metrics[metric] = performance_metrics[metric]

		# 交易相关指标
		for metric in ["total_trades", "win_rate", "profit_factor", "avg_trade"]:
			if metric in performance_metrics:
				key_metrics[metric] = performance_metrics[metric]

		# 计算综合评分
		key_metrics["composite_score"] = self._calculate_composite_score(key_metrics)

		return key_metrics

	def _calculate_composite_score (self, metrics: Dict[str, Any]) -> float:
		"""计算综合评分（0-100）"""
		score = 50.0  # 基础分

		# 夏普比率贡献
		sharpe = metrics.get("sharpe_ratio", 0)
		if sharpe > 2:
			score += 20
		elif sharpe > 1:
			score += 10
		elif sharpe > 0:
			score += 5

		# 最大回撤贡献
		max_dd = abs(metrics.get("max_drawdown", 0))
		if max_dd < 0.1:  # 小于10%
			score += 15
		elif max_dd < 0.2:  # 小于20%
			score += 10
		elif max_dd < 0.3:  # 小于30%
			score += 5

		# 胜率贡献
		win_rate = metrics.get("win_rate", 0)
		if win_rate > 0.6:  # 大于60%
			score += 10
		elif win_rate > 0.5:  # 大于50%
			score += 5

		# 总收益贡献
		total_return = metrics.get("total_return", 0)
		if total_return > 0.5:  # 大于50%
			score += 5

		return min(100, max(0, score))

	def _assess_backtest_quality (self, metrics: Dict[str, Any], summary: Dict[str, Any]) -> Dict[str, Any]:
		"""评估回测质量"""
		quality = {
			"data_quality": "good",
			"strategy_quality": "good",
			"execution_quality": "good",
			"overall": "good"
		}

		# 数据质量检查
		if "data_missing_rate" in summary and summary["data_missing_rate"] > 0.05:
			quality["data_quality"] = "poor"
		elif "data_missing_rate" in summary and summary["data_missing_rate"] > 0.01:
			quality["data_quality"] = "fair"

		# 策略质量检查
		sharpe = metrics.get("sharpe_ratio", 0)
		if sharpe < 0:
			quality["strategy_quality"] = "poor"
		elif sharpe < 0.5:
			quality["strategy_quality"] = "fair"

		# 执行质量检查
		if "errors_count" in summary and summary["errors_count"] > 10:
			quality["execution_quality"] = "poor"
		elif "warnings_count" in summary and summary["warnings_count"] > 50:
			quality["execution_quality"] = "fair"

		# 整体质量
		poor_count = list(quality.values()).count("poor")
		fair_count = list(quality.values()).count("fair")

		if poor_count > 0:
			quality["overall"] = "poor"
		elif fair_count > 1:
			quality["overall"] = "fair"
		elif fair_count > 0:
			quality["overall"] = "fair"
		else:
			quality["overall"] = "good"

		return quality

	def _generate_recommendations (self, key_metrics: Dict[str, Any], quality: Dict[str, Any]) -> List[str]:
		"""生成建议"""
		recommendations = []

		# 根据质量评估
		if quality["overall"] == "poor":
			recommendations.append("回测质量较差，建议检查数据和策略逻辑")
		elif quality["overall"] == "fair":
			recommendations.append("回测质量一般，建议优化策略参数")

		# 根据绩效指标
		sharpe = key_metrics.get("sharpe_ratio", 0)
		if sharpe < 0:
			recommendations.append("夏普比率为负，策略可能不具有盈利能力")
		elif sharpe < 0.5:
			recommendations.append("夏普比率较低，建议优化风险调整收益")

		max_dd = abs(key_metrics.get("max_drawdown", 0))
		if max_dd > 0.3:
			recommendations.append(f"最大回撤{max_dd * 100:.1f}%过高，建议加强风险控制")

		win_rate = key_metrics.get("win_rate", 0)
		if win_rate < 0.4:
			recommendations.append(f"胜率{win_rate * 100:.1f}%偏低，建议优化入场时机")

		if not recommendations:
			recommendations.append("回测结果良好，可以考虑实盘测试")

		return recommendations


class BacktestFailedEvent(BaseEvent):
	"""
	回测失败事件

	触发时机：
	- 回测任务执行失败
	- 关键步骤出现错误
	- 资源不足导致失败

	事件数据：
	- error_type: 错误类型
	- error_message: 错误信息
	- error_details: 错误详情
	- failure_stage: 失败阶段
	"""

	def __init__ (
			self,
			backtest_id: str,
			error_type: str,
			error_message: str,
			failure_stage: str,
			error_details: Optional[Dict[str, Any]] = None,
			retry_count: int = 0,
			max_retries: int = 3,
			**kwargs
	):
		super().__init__(
			module="events",
			event_type=BacktestEventType.FAILED.value,
			priority=EventPriority.HIGH,
			source="backtest_engine",
			**kwargs
		)

		# 分类错误严重程度
		severity = self._classify_error_severity(error_type, failure_stage)

		self.data = {
			"backtest_id": backtest_id,
			"error_type": error_type,
			"error_message": error_message,
			"error_details": error_details or {},
			"failure_stage": failure_stage,
			"severity": severity,
			"retry_count": retry_count,
			"max_retries": max_retries,
			"failure_time": datetime.now().isoformat(),
			"can_retry": retry_count < max_retries and self._is_retryable_error(error_type),
			"diagnosis": self._diagnose_failure(error_type, failure_stage, error_details),
			"recovery_steps": self._suggest_recovery_steps(error_type, failure_stage, retry_count)
		}

	def _classify_error_severity (self, error_type: str, failure_stage: str) -> str:
		"""分类错误严重程度"""
		# 定义严重错误类型
		critical_errors = [
			"data_corruption",
			"memory_exhaustion",
			"disk_full",
			"system_crash"
		]

		# 定义重要错误类型
		major_errors = [
			"data_missing",
			"strategy_error",
			"calculation_error",
			"timeout"
		]

		# 定义次要错误类型
		minor_errors = [
			"configuration_error",
			"resource_warning",
			"performance_warning"
		]

		if error_type in critical_errors:
			return "critical"
		elif error_type in major_errors:
			return "major"
		elif error_type in minor_errors:
			return "minor"
		else:
			return "unknown"

	def _is_retryable_error (self, error_type: str) -> bool:
		"""判断错误是否可重试"""
		non_retryable_errors = [
			"data_corruption",
			"strategy_error",
			"configuration_error"
		]

		return error_type not in non_retryable_errors

	def _diagnose_failure (self, error_type: str, failure_stage: str, details: Dict[str, Any]) -> Dict[str, Any]:
		"""诊断失败原因"""
		diagnosis = {
			"probable_cause": "unknown",
			"confidence": 0.0,
			"affected_components": [],
			"root_cause_analysis": {}
		}

		# 基于错误类型和阶段的诊断
		if error_type == "data_missing" and failure_stage == "data_loading":
			diagnosis["probable_cause"] = "数据源问题"
			diagnosis["confidence"] = 0.8
			diagnosis["affected_components"] = ["data_source", "data_loader"]

		elif error_type == "memory_exhaustion" and failure_stage == "simulation_running":
			diagnosis["probable_cause"] = "资源不足"
			diagnosis["confidence"] = 0.9
			diagnosis["affected_components"] = ["memory_manager", "simulation_engine"]

		elif error_type == "timeout" and failure_stage == "performance_calculation":
			diagnosis["probable_cause"] = "计算复杂度过高"
			diagnosis["confidence"] = 0.7
			diagnosis["affected_components"] = ["calculator", "performance_engine"]

		# 添加详细信息
		if details:
			diagnosis["root_cause_analysis"] = {
				"error_context": details.get("context", {}),
				"resource_usage": details.get("resource_usage", {}),
				"environment_info": details.get("environment", {})
			}

		return diagnosis

	def _suggest_recovery_steps (self, error_type: str, failure_stage: str, retry_count: int) -> List[str]:
		"""建议恢复步骤"""
		steps = []

		if error_type == "data_missing":
			steps.extend([
				"检查数据源连接",
				"验证数据文件完整性",
				"使用备用数据源"
			])

		elif error_type == "memory_exhaustion":
			steps.extend([
				"增加内存分配",
				"优化数据处理算法",
				"使用分批处理"
			])

		elif error_type == "timeout":
			steps.extend([
				"增加超时时间",
				"优化计算算法",
				"使用分布式计算"
			])

		elif error_type == "strategy_error":
			steps.extend([
				"检查策略逻辑",
				"验证策略参数",
				"调试策略代码"
			])

		# 通用步骤
		if retry_count < 3:
			steps.append(f"自动重试（已尝试{retry_count}次）")

		steps.append("查看详细错误日志")

		if not steps:
			steps.append("请联系技术支持")

		return steps