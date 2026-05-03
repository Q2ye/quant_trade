"""
参数优化事件定义
用于策略参数优化过程中的事件通知

业务场景：
1. 参数优化任务启动和配置
2. 优化算法执行进度通知
3. 优化结果生成和比较
4. 最优参数推荐和验证
"""

from datetime import datetime
from typing import Dict, Any, List, Optional

from core.events.base import BaseEvent, EventPriority
from modules.backtest.events.types import BacktestEventTypes


class BacktestOptimizationStartedEvent(BaseEvent):
	"""
	参数优化开始事件

	触发时机：
	- 启动策略参数优化任务
	- 多参数组合优化开始
	- 优化算法初始化完成

	事件数据：
	- optimization_id: 优化任务ID
	- optimization_config: 优化配置参数
	- parameter_space: 参数空间定义
	- algorithm_config: 优化算法配置
	"""

	def __init__ (
			self,
			optimization_id: str,
			strategy_id: str,
			optimization_type: str,
			parameter_space: Dict[str, List[Any]],
			algorithm: str = "grid_search",
			optimization_config: Optional[Dict[str, Any]] = None,
			**kwargs
	):
		super().__init__(
			module="events",
			event_type=BacktestEventTypes.OPTIMIZATION_START.value,
			priority=EventPriority.NORMAL,
			source="optimization_engine",
			**kwargs
		)

		if optimization_config is None:
			optimization_config = {}

		# 计算参数组合总数
		total_combinations = BacktestOptimizationStartedEvent._calculate_total_combinations(parameter_space)

		# 估计优化时间
		estimated_time = BacktestOptimizationStartedEvent._estimate_optimization_time(total_combinations, algorithm,
		                                                                              optimization_config)

		self.data = {
			"optimization_id": optimization_id,
			"strategy_id": strategy_id,
			"optimization_type": optimization_type,
			"algorithm": algorithm,
			"parameter_space": parameter_space,
			"total_combinations": total_combinations,
			"optimization_config": optimization_config,
			"start_time": datetime.now().isoformat(),
			"estimated_duration": estimated_time,
			"optimization_goals": BacktestOptimizationStartedEvent._define_optimization_goals(optimization_type,
			                                                                                  optimization_config),
			"resource_requirements": BacktestOptimizationStartedEvent._calculate_resource_requirements(
				total_combinations, algorithm),
			"constraints": BacktestOptimizationStartedEvent._define_constraints(parameter_space, optimization_config)
		}

	@staticmethod
	def _calculate_total_combinations (parameter_space: Dict[str, List[Any]]) -> int:
		"""计算参数组合总数"""
		total = 1
		for param_name, values in parameter_space.items():
			total *= len(values)
		return total

	@staticmethod
	def _estimate_optimization_time (total_combinations: int, algorithm: str, config: Dict[str, Any]) -> Dict[
		str, Any]:
		"""估计优化时间"""
		# 基础回测时间（分钟）
		base_backtest_time = config.get("base_backtest_minutes", 1)

		# 算法效率因子
		algorithm_efficiency = {
			"grid_search": 1.0,
			"random_search": 0.8,
			"bayesian_optimization": 0.3,
			"genetic_algorithm": 0.2,
			"particle_swarm": 0.25
		}.get(algorithm, 1.0)

		# 并行因子
		parallel_factor = config.get("parallel_workers", 1)

		# 计算总时间（分钟）
		if algorithm == "grid_search":
			# 网格搜索需要测试所有组合
			total_tests = total_combinations
		elif algorithm == "random_search":
			# 随机搜索测试指定数量组合
			total_tests = config.get("random_samples", min(100, total_combinations))
		else:
			# 智能算法通常迭代次数更少
			iterations = config.get("max_iterations", 100)
			population_size = config.get("population_size", 20)
			total_tests = iterations * population_size

		# 计算时间
		total_minutes = (total_tests * base_backtest_time) / (parallel_factor * algorithm_efficiency)

		# 添加固定开销
		total_minutes += 10  # 初始化时间

		return {
			"estimated_minutes": round(total_minutes, 1),
			"estimated_hours": round(total_minutes / 60, 2),
			"total_tests": total_tests,
			"parallel_efficiency": f"{parallel_factor}x",
			"algorithm_efficiency": algorithm_efficiency
		}

	@staticmethod
	def _define_optimization_goals (optimization_type: str, config: Dict[str, Any]) -> List[Dict[str, Any]]:
		"""定义优化目标"""
		default_goals = [
			{
				"metric": "sharpe_ratio",
				"objective": "maximize",
				"weight": 0.4,
				"target": None
			},
			{
				"metric": "total_return",
				"objective": "maximize",
				"weight": 0.3,
				"target": None
			},
			{
				"metric": "max_drawdown",
				"objective": "minimize",
				"weight": 0.2,
				"target": None
			},
			{
				"metric": "win_rate",
				"objective": "maximize",
				"weight": 0.1,
				"target": None
			}
		]

		# 根据优化类型调整
		if optimization_type == "risk_adjusted":
			# 风险调整优化：更注重夏普比率和最大回撤
			for goal in default_goals:
				if goal["metric"] == "sharpe_ratio":
					goal["weight"] = 0.5
				elif goal["metric"] == "max_drawdown":
					goal["weight"] = 0.3
				elif goal["metric"] == "total_return":
					goal["weight"] = 0.1
				elif goal["metric"] == "win_rate":
					goal["weight"] = 0.1

		elif optimization_type == "high_return":
			# 高收益优化：更注重总收益
			for goal in default_goals:
				if goal["metric"] == "total_return":
					goal["weight"] = 0.6
				elif goal["metric"] == "sharpe_ratio":
					goal["weight"] = 0.2
				elif goal["metric"] == "max_drawdown":
					goal["weight"] = 0.1
				elif goal["metric"] == "win_rate":
					goal["weight"] = 0.1

		# 从配置中覆盖目标
		if "optimization_goals" in config:
			for custom_goal in config["optimization_goals"]:
				for default_goal in default_goals:
					if default_goal["metric"] == custom_goal.get("metric"):
						default_goal.update(custom_goal)
						break

		return default_goals

	@staticmethod
	def _calculate_resource_requirements (total_combinations: int, algorithm: str) -> Dict[str, Any]:
		"""计算资源需求"""
		# 基础资源需求
		base_resources = {
			"grid_search": {"cpu_cores": 4, "memory_mb": 4096, "disk_gb": 10},
			"random_search": {"cpu_cores": 4, "memory_mb": 4096, "disk_gb": 5},
			"bayesian_optimization": {"cpu_cores": 2, "memory_mb": 2048, "disk_gb": 3},
			"genetic_algorithm": {"cpu_cores": 2, "memory_mb": 2048, "disk_gb": 3},
			"particle_swarm": {"cpu_cores": 2, "memory_mb": 2048, "disk_gb": 3}
		}

		resources = base_resources.get(algorithm, {"cpu_cores": 2, "memory_mb": 2048, "disk_gb": 5})

		# 根据组合数量调整
		if total_combinations > 10000:
			resources["cpu_cores"] = min(16, resources["cpu_cores"] * 2)
			resources["memory_mb"] = min(16384, resources["memory_mb"] * 2)
			resources["disk_gb"] = min(50, resources["disk_gb"] * 2)
		elif total_combinations > 1000:
			resources["cpu_cores"] = min(8, resources["cpu_cores"] * 2)
			resources["memory_mb"] = min(8192, resources["memory_mb"] * 2)

		return resources

	@staticmethod
	def _define_constraints (parameter_space: Dict[str, List[Any]], config: Dict[str, Any]) -> List[
		Dict[str, Any]]:
		"""定义约束条件"""
		constraints = []

		# 参数范围约束
		for param_name, values in parameter_space.items():
			if isinstance(values[0], (int, float)):
				constraints.append({
					"type": "parameter_range",
					"parameter": param_name,
					"min": min(values),
					"max": max(values),
					"enforcement": "hard"
				})

		# 性能约束（从配置中获取）
		if "performance_constraints" in config:
			for constraint in config["performance_constraints"]:
				constraints.append({
					"type": "performance",
					"metric": constraint.get("metric"),
					"operator": constraint.get("operator", ">="),
					"value": constraint.get("value"),
					"enforcement": constraint.get("enforcement", "soft")
				})

		# 默认约束
		default_constraints = [
			{
				"type": "performance",
				"metric": "sharpe_ratio",
				"operator": ">",
				"value": 0,
				"enforcement": "hard",
				"description": "夏普比率必须为正"
			},
			{
				"type": "risk",
				"metric": "max_drawdown",
				"operator": "<",
				"value": -0.5,
				"enforcement": "hard",
				"description": "最大回撤不能超过50%"
			}
		]

		constraints.extend(default_constraints)

		return constraints


class BacktestOptimizationProgressEvent(BaseEvent):
	"""
	参数优化进度事件

	触发时机：
	- 优化任务执行到关键阶段
	- 定期报告优化进度
	- 发现重要优化结果

	事件数据：
	- optimization_progress: 优化进度信息
	- current_best: 当前最优参数和结果
	- algorithm_state: 优化算法状态
	- intermediate_results: 中间结果
	"""

	def __init__ (
			self,
			optimization_id: str,
			progress: float,
			completed_tests: int,
			total_tests: int,
			current_best: Optional[Dict[str, Any]] = None,
			algorithm_state: Optional[Dict[str, Any]] = None,
			intermediate_results: Optional[List[Dict[str, Any]]] = None,
			**kwargs
	):
		super().__init__(
			module="events",
			event_type=BacktestEventTypes.OPTIMIZATION_PROGRESS.value,
			priority=EventPriority.LOW,
			source="optimization_engine",
			**kwargs
		)

		if current_best is None:
			current_best = {}
		if algorithm_state is None:
			algorithm_state = {}
		if intermediate_results is None:
			intermediate_results = []

		# 计算进度统计
		progress_stats = BacktestOptimizationProgressEvent._calculate_progress_stats(completed_tests, total_tests,
		                                                                             progress)

		# 分析优化趋势
		optimization_trend = BacktestOptimizationProgressEvent._analyze_optimization_trend(intermediate_results,
		                                                                                   current_best)

		self.data = {
			"optimization_id": optimization_id,
			"progress": progress,
			"completed_tests": completed_tests,
			"total_tests": total_tests,
			"current_best": current_best,
			"algorithm_state": algorithm_state,
			"intermediate_results": intermediate_results[-10:],  # 只保留最近10个结果
			"timestamp": datetime.now().isoformat(),
			"progress_stats": progress_stats,
			"optimization_trend": optimization_trend,
			"convergence_analysis": BacktestOptimizationProgressEvent._analyze_convergence(progress,
			                                                                               intermediate_results,
			                                                                               algorithm_state),
			"resource_usage": BacktestOptimizationProgressEvent._monitor_resource_usage(completed_tests, total_tests)
		}

	@staticmethod
	def _calculate_progress_stats (completed: int, total: int, progress: float) -> Dict[str, Any]:
		"""计算进度统计"""
		from datetime import datetime, timedelta

		# 获取当前时间作为基准
		current_time = datetime.now()

		# 计算完成率
		completion_rate = (completed / total * 100) if total > 0 else 0

		# 估计剩余时间（基于平均测试时间）
		# 在实际实现中，应该从优化引擎获取实际测试时间
		average_test_time_seconds = 60  # 假设每个测试平均60秒
		estimated_remaining_seconds = (total - completed) * average_test_time_seconds

		# 计算测试速度
		tests_per_minute = completed / (progress * 100 * 60) if progress > 0 else 0

		# 计算效率评分（基于完成率和进度的一致性）
		efficiency_score = 0.0
		if total > 0:
			# 理想情况下，完成率应该等于进度百分比
			consistency = 1 - abs(completion_rate - progress * 100) / 100
			efficiency_score = max(0.0, min(100.0, consistency * 100))

		stats = {
			"completion_rate": round(completion_rate, 2),
			"tests_per_minute": round(tests_per_minute, 2),
			"estimated_remaining_tests": total - completed,
			"estimated_remaining_time_seconds": round(estimated_remaining_seconds),
			"estimated_completion_time": (current_time + timedelta(seconds=estimated_remaining_seconds)).isoformat(),
			"efficiency_score": round(efficiency_score, 1),
			"progress_percentage": round(progress * 100, 2),
			"current_phase": BacktestOptimizationProgressEvent._determine_optimization_phase(progress),
			"bottleneck_analysis": BacktestOptimizationProgressEvent._analyze_bottlenecks(completed, total, progress)
		}

		return stats

	@staticmethod
	def _determine_optimization_phase (progress: float) -> str:
		"""确定优化阶段"""
		if progress < 0.1:
			return "initialization"
		elif progress < 0.3:
			return "exploration"
		elif progress < 0.7:
			return "exploitation"
		elif progress < 0.9:
			return "refinement"
		else:
			return "finalization"

	@staticmethod
	def _analyze_bottlenecks (completed: int, total: int, progress: float) -> Dict[str, Any]:
		"""分析瓶颈"""
		bottlenecks = {
			"has_bottleneck": False,
			"bottleneck_type": "none",
			"suggestions": []
		}

		# 检测进度停滞
		if progress > 0.3 and completed < total * 0.1:
			bottlenecks["has_bottleneck"] = True
			bottlenecks["bottleneck_type"] = "slow_progress"
			bottlenecks["suggestions"].append("考虑增加并行度或优化算法参数")

		# 检测资源瓶颈（基于测试数量）
		if total > 1000 and completed < 100:
			bottlenecks["has_bottleneck"] = True
			bottlenecks["bottleneck_type"] = "resource_limited"
			bottlenecks["suggestions"].append("可能需要更多计算资源或优化算法选择")

		return bottlenecks

	@staticmethod
	def _calculate_resource_health_score (memory_usage: float, disk_usage: float, cpu_usage: float) -> float:
		"""计算资源健康评分"""
		# 健康评分基于资源使用率的加权平均
		# 使用率越低，评分越高

		# 权重分配：内存40%，磁盘30%，CPU30%
		memory_score = max(0.0, 100.0 - memory_usage)
		disk_score = max(0.0, 100.0 - disk_usage)
		cpu_score = max(0.0, 100.0 - cpu_usage)

		health_score = (memory_score * 0.4 + disk_score * 0.3 + cpu_score * 0.3)

		# 如果任何资源使用率超过90%，健康评分大幅降低
		if memory_usage > 90 or disk_usage > 90 or cpu_usage > 90:
			health_score *= 0.5

		return round(health_score, 1)

	@staticmethod
	def _analyze_optimization_trend (results: List[Dict[str, Any]], current_best: Dict[str, Any]) -> Dict[
		str, Any]:
		"""分析优化趋势"""
		if len(results) < 3:
			return {"trend": "insufficient_data", "confidence": 0}

		# 提取关键指标
		sharpe_values = [r.get("sharpe_ratio", 0) for r in results if "sharpe_ratio" in r]
		return_values = [r.get("total_return", 0) for r in results if "total_return" in r]

		if not sharpe_values or not return_values:
			return {"trend": "no_data", "confidence": 0}

		# 计算趋势
		from scipy import stats

		# 初始化变量
		sharpe_trend = 0.0
		return_trend = 0.0
		try:
			# 夏普比率趋势
			sharpe_trend = stats.linregress(range(len(sharpe_values)), sharpe_values).slope

			# 总收益趋势
			return_trend = stats.linregress(range(len(return_values)), return_values).slope

			# 判断整体趋势
			if sharpe_trend > 0.01 and return_trend > 0.01:
				trend = "improving"
				confidence = min(0.9, abs(sharpe_trend) * 10 + abs(return_trend) * 5)
			elif sharpe_trend < -0.01 or return_trend < -0.01:
				trend = "deteriorating"
				confidence = min(0.9, abs(sharpe_trend) * 10 + abs(return_trend) * 5)
			else:
				trend = "stable"
				confidence = 0.5
		except (ValueError, TypeError, AttributeError, ImportError) as e:
			trend = "unknown"
			confidence = 0

		return {
			"trend": trend,
			"confidence": round(confidence, 3),
			"sharpe_trend": sharpe_trend if 'sharpe_trend' in locals() else 0,
			"return_trend": return_trend if 'return_trend' in locals() else 0,
			"recent_improvement": BacktestOptimizationProgressEvent._calculate_recent_improvement(results)
		}

	@staticmethod
	def _calculate_recent_improvement (results: List[Dict[str, Any]]) -> Dict[str, Any]:
		"""计算近期改进"""
		if len(results) < 5:
			return {"improvement": 0, "period": "insufficient_data"}

		# 取最近5个结果
		recent = results[-5:]

		# 计算夏普比率的改进
		sharpe_values = [r.get("sharpe_ratio", 0) for r in recent if "sharpe_ratio" in r]
		if len(sharpe_values) >= 2:
			improvement = (sharpe_values[-1] - sharpe_values[0]) / abs(sharpe_values[0]) if sharpe_values[0] != 0 else 0
			return {
				"improvement": round(improvement * 100, 2),  # 百分比
				"period": "last_5_tests",
				"metric": "sharpe_ratio",
				"significant": abs(improvement) > 0.1  # 超过10%的改进被认为是显著的
			}

		return {"improvement": 0, "period": "no_data"}

	@staticmethod
	def _analyze_convergence (progress: float, results: List[Dict[str, Any]], algorithm_state: Dict[str, Any]) -> \
			Dict[str, Any]:
		"""分析收敛性"""
		convergence = {
			"converged": False,
			"convergence_rate": 0,
			"stagnation_detected": False,
			"optimality_gap": None
		}

		# 需要足够的数据来分析收敛
		if len(results) < 10:
			return convergence

		# 提取最近20个结果的夏普比率
		recent_results = results[-20:] if len(results) >= 20 else results
		sharpe_values = [r.get("sharpe_ratio", 0) for r in recent_results if "sharpe_ratio" in r]

		if len(sharpe_values) < 10:
			return convergence

		# 检查停滞：最近10次迭代改进很小
		recent_window = sharpe_values[-10:]
		if len(recent_window) >= 5:
			max_val = max(recent_window)
			min_val = min(recent_window)
			range_val = max_val - min_val

			# 如果范围很小，可能停滞了
			if range_val < 0.01:
				convergence["stagnation_detected"] = True
				convergence["stagnation_period"] = len(recent_window)

			# 检查收敛：改进速率下降
			improvements = [sharpe_values[i] - sharpe_values[i - 1] for i in range(1, len(sharpe_values))]
			avg_improvement = sum(improvements) / len(improvements) if improvements else 0
			recent_improvement = sum(improvements[-5:]) / 5 if len(improvements) >= 5 else 0

			if abs(recent_improvement) < 0.001 and progress > 0.8:
				convergence["converged"] = True
				convergence["convergence_rate"] = int(round(
					1 - (abs(recent_improvement) / max(0.001, abs(avg_improvement))), 3) * 1000)

		# 最优性间隙
		if "global_best" in algorithm_state and "current_best" in algorithm_state:
			gap = algorithm_state["global_best"] - algorithm_state["current_best"]
			if algorithm_state["global_best"] != 0:
				gap_percentage = gap / algorithm_state["global_best"]
				convergence["optimality_gap"] = round(gap_percentage * 100, 2)

		return convergence

	@staticmethod
	def _monitor_resource_usage (completed: int, total: int) -> Dict[str, Any]:
		"""监控资源使用"""
		import psutil
		import os

		# 获取系统资源使用情况
		memory_info = psutil.virtual_memory()
		disk_info = psutil.disk_usage('/')
		cpu_percent = psutil.cpu_percent(interval=1)

		# 获取当前进程的资源使用
		process = psutil.Process(os.getpid())
		process_memory_mb = process.memory_info().rss / 1024 / 1024
		process_cpu_percent = process.cpu_percent()

		# 计算资源使用趋势
		memory_usage_percent = memory_info.percent
		disk_usage_percent = (disk_info.used / disk_info.total) * 100

		# 估计优化任务的内存使用
		estimated_memory_mb = 1024 + (completed * 0.1)  # 基础1GB + 每个测试0.1MB
		estimated_disk_gb = 1 + (completed * 0.001)  # 基础1GB + 每个测试1MB

		# 分析资源瓶颈
		resource_bottlenecks = []
		if memory_usage_percent > 80:
			resource_bottlenecks.append("内存使用率过高")
		if disk_usage_percent > 85:
			resource_bottlenecks.append("磁盘空间不足")
		if cpu_percent > 90:
			resource_bottlenecks.append("CPU负载过高")

		# 生成优化建议
		suggestions = []
		if memory_usage_percent > 70:
			suggestions.append("考虑增加内存或优化内存使用")
		if disk_usage_percent > 80:
			suggestions.append("建议清理临时文件或增加磁盘空间")
		if completed > total * 0.5:
			suggestions.append("完成一半后建议清理中间结果以释放资源")

		return {
			"system_resources": {
				"memory_usage_percent": round(memory_usage_percent, 1),
				"memory_available_gb": round(memory_info.available / 1024 / 1024 / 1024, 1),
				"disk_usage_percent": round(disk_usage_percent, 1),
				"disk_available_gb": round(disk_info.free / 1024 / 1024 / 1024, 1),
				"cpu_usage_percent": round(cpu_percent, 1)
			},
			"process_resources": {
				"memory_usage_mb": round(process_memory_mb, 1),
				"cpu_usage_percent": round(process_cpu_percent, 1)
			},
			"estimated_requirements": {
				"memory_mb": round(estimated_memory_mb, 1),
				"disk_gb": round(estimated_disk_gb, 3)
			},
			"warnings": {
				"memory_warning": memory_usage_percent > 80,
				"disk_warning": disk_usage_percent > 85,
				"cpu_warning": cpu_percent > 90
			},
			"resource_bottlenecks": resource_bottlenecks,
			"suggestions": suggestions,
			"health_score": BacktestOptimizationProgressEvent._calculate_resource_health_score(
				memory_usage_percent, disk_usage_percent, cpu_percent
			)
		}


class BacktestOptimizationCompletedEvent(BaseEvent):
	"""
	参数优化完成事件

	触发时机：
	- 优化任务成功完成
	- 达到优化终止条件
	- 找到满意的最优参数

	事件数据：
	- optimization_results: 优化结果汇总
	- optimal_parameters: 最优参数组合
	- performance_comparison: 性能比较
	- validation_results: 验证结果
	"""

	def __init__ (
			self,
			optimization_id: str,
			strategy_id: str,
			total_duration_seconds: float,
			optimization_results: Dict[str, Any],
			optimal_parameters: Dict[str, Any],
			performance_comparison: Optional[Dict[str, Any]] = None,
			validation_results: Optional[Dict[str, Any]] = None,
			**kwargs
	):
		super().__init__(
			module="events",
			event_type=BacktestEventTypes.OPTIMIZATION_COMPLETE.value,
			priority=EventPriority.NORMAL,
			source="optimization_engine",
			**kwargs
		)

		if performance_comparison is None:
			performance_comparison = {}
		if validation_results is None:
			validation_results = {}

		# 分析优化效果
		optimization_effectiveness = BacktestOptimizationCompletedEvent._analyze_optimization_effectiveness(
			optimization_results,
			optimal_parameters
		)

		# 生成参数建议
		parameter_recommendations = BacktestOptimizationCompletedEvent._generate_parameter_recommendations(
			optimal_parameters,
			optimization_results
		)

		self.data = {
			"optimization_id": optimization_id,
			"strategy_id": strategy_id,
			"total_duration_seconds": round(total_duration_seconds, 2),
			"completion_time": datetime.now().isoformat(),
			"optimization_results": optimization_results,
			"optimal_parameters": optimal_parameters,
			"performance_comparison": performance_comparison,
			"validation_results": validation_results,
			"optimization_effectiveness": optimization_effectiveness,
			"parameter_recommendations": parameter_recommendations,
			"robustness_analysis": BacktestOptimizationCompletedEvent._analyze_robustness(optimal_parameters,
			                                                                              validation_results),
			"implementation_guidelines": BacktestOptimizationCompletedEvent._generate_implementation_guidelines(
				optimal_parameters)
		}

	@staticmethod
	def _analyze_optimization_effectiveness (results: Dict[str, Any], optimal_params: Dict[str, Any]) -> Dict[
		str, Any]:
		"""分析优化效果"""
		effectiveness = {
			"improvement_percentage": 0,
			"optimization_score": 0,
			"efficiency_ratio": 0,
			"overall_effectiveness": "moderate"
		}

		# 检查是否有基准性能
		if "baseline_performance" in results and "optimal_performance" in results:
			baseline = results["baseline_performance"]
			optimal = results["optimal_performance"]

			# 计算改进百分比（基于夏普比率）
			if "sharpe_ratio" in baseline and "sharpe_ratio" in optimal:
				baseline_sharpe = baseline["sharpe_ratio"]
				optimal_sharpe = optimal["sharpe_ratio"]

				if baseline_sharpe != 0:
					improvement = (optimal_sharpe - baseline_sharpe) / abs(baseline_sharpe)
					effectiveness["improvement_percentage"] = round(improvement * 100, 2)

		# 计算优化分数（0-100）
		score = 50  # 基础分

		# 改进幅度贡献（最高30分）
		improvement = effectiveness["improvement_percentage"]
		if improvement > 50:
			score += 30
		elif improvement > 20:
			score += 20
		elif improvement > 10:
			score += 10
		elif improvement > 0:
			score += 5

		# 参数合理性贡献（最高20分）
		param_count = len(optimal_params.get("parameters", {}))
		if param_count <= 5:
			score += 20
		elif param_count <= 10:
			score += 15
		elif param_count <= 20:
			score += 10
		else:
			score += 5

		# 性能稳定性贡献（最高30分）
		if "validation_sharpe_ratio" in results:
			val_sharpe = results["validation_sharpe_ratio"]
			opt_sharpe = results.get("optimal_performance", {}).get("sharpe_ratio", 0)

			if val_sharpe > 0 and opt_sharpe > 0:
				stability = min(val_sharpe, opt_sharpe) / max(val_sharpe, opt_sharpe)
				stability_score = stability * 30
				score += stability_score

		effectiveness["optimization_score"] = min(100, max(0, score))

		# 整体效果评估
		if effectiveness["optimization_score"] >= 80:
			effectiveness["overall_effectiveness"] = "excellent"
		elif effectiveness["optimization_score"] >= 60:
			effectiveness["overall_effectiveness"] = "good"
		elif effectiveness["optimization_score"] >= 40:
			effectiveness["overall_effectiveness"] = "moderate"
		else:
			effectiveness["overall_effectiveness"] = "poor"

		return effectiveness

	@staticmethod
	def _generate_parameter_recommendations (optimal_params: Dict[str, Any], results: Dict[str, Any]) -> List[
		Dict[str, Any]]:
		"""生成参数建议"""
		recommendations = []

		# 参数敏感性分析
		if "parameter_sensitivity" in results:
			sensitivity = results["parameter_sensitivity"]

			for param_name, sensitivity_data in sensitivity.items():
				if "importance" in sensitivity_data:
					importance = sensitivity_data["importance"]

					if importance > 0.8:
						recommendations.append({
							"parameter": param_name,
							"type": "critical",
							"message": f"参数'{param_name}'对策略性能影响重大（重要性：{importance:.2f}）",
							"recommendation": "应谨慎调整此参数，建议使用较小步长进行微调"
						})
					elif importance < 0.2:
						recommendations.append({
							"parameter": param_name,
							"type": "minor",
							"message": f"参数'{param_name}'对策略性能影响较小（重要性：{importance:.2f}）",
							"recommendation": "此参数可适当放宽调整范围或使用默认值"
						})

		# 参数值建议
		params = optimal_params.get("parameters", {})
		for param_name, param_value in params.items():
			# 检查参数是否在边界附近
			if "parameter_ranges" in results:
				ranges = results["parameter_ranges"]
				if param_name in ranges:
					min_val, max_val = ranges[param_name]

					# 计算相对位置
					if isinstance(param_value, (int, float)) and max_val > min_val:
						position = (param_value - min_val) / (max_val - min_val)

						if position > 0.9:
							recommendations.append({
								"parameter": param_name,
								"type": "boundary",
								"message": f"参数'{param_name}'的值{param_value}接近上限{max_val}",
								"recommendation": "考虑是否需要对参数范围进行扩展"
							})
						elif position < 0.1:
							recommendations.append({
								"parameter": param_name,
								"type": "boundary",
								"message": f"参数'{param_name}'的值{param_value}接近下限{min_val}",
								"recommendation": "检查下限是否合理，可能需要调整"
							})

		# 通用建议
		param_count = len(params)
		if param_count > 10:
			recommendations.append({
				"parameter": "all",
				"type": "general",
				"message": f"策略包含{param_count}个参数，可能过于复杂",
				"recommendation": "考虑简化策略，减少参数数量以提高稳健性"
			})

		return recommendations

	@staticmethod
	def _analyze_robustness (optimal_params: Dict[str, Any], validation_results: Dict[str, Any]) -> Dict[
		str, Any]:
		"""分析稳健性"""
		robustness = {
			"overall_robustness": "unknown",
			"out_of_sample_performance": 0,
			"parameter_stability": "unknown",
			"market_regime_sensitivity": "unknown"
		}

		# 样本外表现
		if "out_of_sample_sharpe" in validation_results:
			oos_sharpe = validation_results["out_of_sample_sharpe"]
			in_sample_sharpe = optimal_params.get("performance", {}).get("sharpe_ratio", 0)

			if in_sample_sharpe != 0:
				performance_ratio = oos_sharpe / in_sample_sharpe
				robustness["out_of_sample_performance"] = round(performance_ratio * 100, 1)

				if performance_ratio > 0.8:
					robustness["overall_robustness"] = "high"
				elif performance_ratio > 0.6:
					robustness["overall_robustness"] = "medium"
				else:
					robustness["overall_robustness"] = "low"

		# 参数稳定性
		if "parameter_perturbation" in validation_results:
			perturbation_results = validation_results["parameter_perturbation"]
			if "stability_score" in perturbation_results:
				stability = perturbation_results["stability_score"]
				robustness["parameter_stability"] = stability

		# 市场机制敏感性
		if "market_regime_performance" in validation_results:
			regime_performance = validation_results["market_regime_performance"]
			performance_values = list(regime_performance.values())

			if performance_values:
				min_perf = min(performance_values)
				max_perf = max(performance_values)
				range_perf = max_perf - min_perf

				if range_perf < 0.1:
					robustness["market_regime_sensitivity"] = "low"
				elif range_perf < 0.3:
					robustness["market_regime_sensitivity"] = "medium"
				else:
					robustness["market_regime_sensitivity"] = "high"

		return robustness

	@staticmethod
	def _generate_implementation_guidelines (optimal_params: Dict[str, Any]) -> List[Dict[str, Any]]:
		"""生成实施指南"""
		guidelines = []

		# 参数实施指南
		params = optimal_params.get("parameters", {})
		for param_name, param_value in params.items():
			if isinstance(param_value, (int, float)):
				# 建议调整步长
				if abs(param_value) < 1:
					step_size = 0.01
				elif abs(param_value) < 10:
					step_size = 0.1
				elif abs(param_value) < 100:
					step_size = 1
				else:
					step_size = 5

				guidelines.append({
					"parameter": param_name,
					"optimal_value": param_value,
					"implementation": {
						"initial_value": param_value,
						"adjustment_step": step_size,
						"allowable_range": [param_value * 0.8, param_value * 1.2],
						"monitoring_frequency": "daily"
					}
				})

		# 监控指南
		guidelines.append({
			"category": "monitoring",
			"guidelines": [
				"实盘运行前，应在模拟环境中运行至少2周",
				"监控关键绩效指标（夏普比率、最大回撤、胜率）",
				"设置性能预警阈值：夏普比率下降超过20%时报警",
				"定期（每周）进行参数稳定性检查"
			]
		})

		# 风险管理指南
		guidelines.append({
			"category": "risk_management",
			"guidelines": [
				f"初始仓位不超过总资金的{optimal_params.get('suggested_position_size', '10%')}",
				"设置动态止损：初始止损为入场价格的5%",
				"最大单日亏损限制为总资金的2%",
				"连续3次亏损后暂停交易，重新评估策略"
			]
		})

		return guidelines