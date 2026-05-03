"""
回测结果事件定义
用于回测结果分析、报告生成和绩效评估相关事件通知

业务场景：
1. 回测报告生成完成
2. 绩效指标计算完成
3. 风险分析结果出炉
4. 回测结果归档和分享
"""

from datetime import datetime
from typing import Dict, Any, List, Optional

from core.events.base import BaseEvent, EventPriority
from modules.backtest.events.types import BacktestEventTypes


class BacktestReportGeneratedEvent(BaseEvent):
	"""
	回测报告生成事件

	触发时机：
	- 回测报告生成完成
	- 绩效报告自动生成
	- 用户手动生成报告

	事件数据：
	- report_type: 报告类型（详细/摘要/定制）
	- report_content: 报告内容摘要
	- report_metadata: 报告元数据
	- distribution_info: 分发信息
	"""

	def __init__ (
			self,
			backtest_id: str,
			report_id: str,
			report_type: str,
			report_format: str = "pdf",
			report_size_kb: Optional[int] = None,
			report_content: Optional[Dict[str, Any]] = None,
			report_metadata: Optional[Dict[str, Any]] = None,
			download_url: Optional[str] = None,
			**kwargs
	):
		super().__init__(
			module="events",
			event_type=BacktestEventTypes.REPORT_GENERATED.value,
			priority=EventPriority.NORMAL,
			source="report_engine",
			**kwargs
		)

		if report_content is None:
			report_content = {}
		if report_metadata is None:
			report_metadata = {}

		# 分析报告内容
		content_analysis = self._analyze_report_content(report_content)

		self.data = {
			"backtest_id": backtest_id,
			"report_id": report_id,
			"report_type": report_type,
			"report_format": report_format,
			"report_size_kb": report_size_kb,
			"download_url": download_url,
			"generation_time": datetime.now().isoformat(),
			"report_content_summary": self._create_content_summary(report_content),
			"report_metadata": report_metadata,
			"content_analysis": content_analysis,
			"access_control": self._setup_access_control(report_type),
			"distribution_channels": self._setup_distribution_channels(report_type, report_format)
		}

	@staticmethod
	def _analyze_report_content ( content: Dict[str, Any]) -> Dict[str, Any]:
		"""分析报告内容"""
		analysis = {
			"section_count": 0,
			"chart_count": 0,
			"table_count": 0,
			"metric_count": 0,
			"estimated_reading_time": 0
		}

		# 统计各种元素
		if "sections" in content:
			analysis["section_count"] = len(content["sections"])

			# 统计图表和表格
			for section in content["sections"]:
				if "charts" in section:
					analysis["chart_count"] += len(section["charts"])
				if "tables" in section:
					analysis["table_count"] += len(section["tables"])
				if "metrics" in section:
					analysis["metric_count"] += len(section["metrics"])

		# 估计阅读时间（分钟）
		# 假设：每段文字1分钟，每个图表2分钟，每个表格3分钟
		estimated_time = (
				analysis["section_count"] * 1 +
				analysis["chart_count"] * 2 +
				analysis["table_count"] * 3
		)
		analysis["estimated_reading_time"] = max(5, estimated_time)  # 至少5分钟

		# 内容复杂度评估
		total_elements = analysis["chart_count"] + analysis["table_count"] + analysis["metric_count"]
		if total_elements > 50:
			analysis["complexity"] = 3
		elif total_elements > 20:
			analysis["complexity"] = 2
		else:
			analysis["complexity"] = 1

		return analysis

	@staticmethod
	def _create_content_summary (content: Dict[str, Any]) -> Dict[str, Any]:
		"""创建内容摘要"""
		summary = {
			"title": content.get("title", "回测报告"),
			"overview": content.get("overview", ""),
			"key_findings": content.get("key_findings", []),
			"recommendations": content.get("recommendations", []),
			"risk_warnings": content.get("risk_warnings", [])
		}

		# 提取关键指标
		if "performance_metrics" in content:
			metrics = content["performance_metrics"]
			summary["key_metrics"] = [
				f"total_return: {metrics.get('total_return', 0)}",
				f"sharpe_ratio: {metrics.get('sharpe_ratio', 0)}",
				f"max_drawdown: {metrics.get('max_drawdown', 0)}",
				f"win_rate: {metrics.get('win_rate', 0)}"
			]

		return summary

	@staticmethod
	def _setup_access_control ( report_type: str) -> Dict[str, Any]:
		"""设置访问控制"""
		access_levels = {
			"detailed": {"level": "confidential", "password_protected": True},
			"summary": {"level": "internal", "password_protected": False},
			"executive": {"level": "confidential", "password_protected": True},
			"public": {"level": "public", "password_protected": False}
		}

		return access_levels.get(report_type, {"level": "internal", "password_protected": False})

	@staticmethod
	def _setup_distribution_channels ( report_type: str, report_format: str) -> List[Dict[str, str]]:
		"""设置分发渠道"""
		channels = []

		# 根据报告类型和格式确定分发渠道
		if report_type in ["detailed", "summary", "executive"]:
			channels.append({"channel": "email", "format": report_format, "priority": "high"})
			channels.append({"channel": "web_portal", "format": "html", "priority": "medium"})

		if report_type == "public":
			channels.append({"channel": "api", "format": "json", "priority": "high"})
			channels.append({"channel": "file_download", "format": report_format, "priority": "medium"})

		# 总是添加到归档
		channels.append({"channel": "archive", "format": report_format, "priority": "low"})

		return channels


class BacktestPerformanceCalculatedEvent(BaseEvent):
	"""
	回测绩效计算事件

	触发时机：
	- 绩效指标计算完成
	- 绩效分析模块处理完毕
	- 自定义绩效计算完成

	事件数据：
	- performance_metrics: 绩效指标集合
	- benchmark_comparison: 基准比较
	- statistical_analysis: 统计分析
	- performance_grade: 绩效评级
	"""

	def __init__ (
			self,
			backtest_id: str,
			performance_metrics: Dict[str, Any],
			benchmark_comparison: Optional[Dict[str, Any]] = None,
			statistical_analysis: Optional[Dict[str, Any]] = None,
			calculation_method: str = "standard",
			**kwargs
	):
		super().__init__(
			module="events",
			event_type=BacktestEventTypes.METRICS_CALCULATED.value,
			priority=EventPriority.NORMAL,
			source="performance_engine",
			**kwargs
		)

		if benchmark_comparison is None:
			benchmark_comparison = {}
		if statistical_analysis is None:
			statistical_analysis = {}

		# 计算绩效评级
		performance_grade = self._calculate_performance_grade(performance_metrics)

		# 生成绩效洞察
		performance_insights = self._generate_performance_insights(performance_metrics, benchmark_comparison)

		self.data = {
			"backtest_id": backtest_id,
			"performance_metrics": performance_metrics,
			"benchmark_comparison": benchmark_comparison,
			"statistical_analysis": statistical_analysis,
			"calculation_method": calculation_method,
			"calculation_time": datetime.now().isoformat(),
			"performance_grade": performance_grade,
			"performance_insights": performance_insights,
			"risk_adjusted_metrics": self._calculate_risk_adjusted_metrics(performance_metrics),
			"strategy_classification": self._classify_strategy(performance_metrics)
		}

	@staticmethod
	def _calculate_performance_grade ( metrics: Dict[str, Any]) -> Dict[str, Any]:
		"""计算绩效评级（A-F）"""
		grade_scores = {
			"A": 90,
			"B": 80,
			"C": 70,
			"D": 60,
			"F": 0
		}

		# 计算综合得分（0-100）
		total_score = 0
		max_score = 0

		# 夏普比率贡献（最高40分）
		sharpe = metrics.get("sharpe_ratio", 0)
		sharpe_score = min(40, max(0, sharpe * 10))
		total_score += sharpe_score
		max_score += 40

		# 最大回撤贡献（最高30分）
		max_dd = abs(metrics.get("max_drawdown", 0))
		dd_score = max(0, 30 - (max_dd * 100))
		total_score += dd_score
		max_score += 30

		# 胜率贡献（最高20分）
		win_rate = metrics.get("win_rate", 0)
		win_rate_score = win_rate * 20
		total_score += win_rate_score
		max_score += 20

		# 总收益贡献（最高10分）
		total_return = metrics.get("total_return", 0)
		return_score = min(10, total_return * 10)
		total_score += return_score
		max_score += 10

		# 计算百分比分数
		if max_score > 0:
			percentage = (total_score / max_score) * 100
		else:
			percentage = 0

		# 确定等级
		grade = "F"
		for g, threshold in sorted(grade_scores.items(), key=lambda x: x[1], reverse=True):
			if percentage >= threshold:
				grade = g
				break

		return {
			"grade": grade,
			"score": round(percentage, 1),
			"components": {
				"sharpe_ratio": sharpe_score,
				"max_drawdown": dd_score,
				"win_rate": win_rate_score,
				"total_return": return_score
			}
		}

	@staticmethod
	def _generate_performance_insights ( metrics: Dict[str, Any], benchmark: Dict[str, Any]) -> List[
		Dict[str, Any]]:
		"""生成绩效洞察"""
		insights = []

		# 夏普比率洞察
		sharpe = metrics.get("sharpe_ratio", 0)
		if sharpe > 2:
			insights.append({
				"type": "strength",
				"metric": "sharpe_ratio",
				"message": f"夏普比率{sharpe:.2f}表现优秀，风险调整后收益良好",
				"recommendation": "可考虑增加仓位或杠杆"
			})
		elif sharpe < 0.5:
			insights.append({
				"type": "weakness",
				"metric": "sharpe_ratio",
				"message": f"夏普比率{sharpe:.2f}较低，风险调整后收益不理想",
				"recommendation": "建议优化风险控制或收益来源"
			})

		# 最大回撤洞察
		max_dd = abs(metrics.get("max_drawdown", 0))
		if max_dd < 0.1:
			insights.append({
				"type": "strength",
				"metric": "max_drawdown",
				"message": f"最大回撤{max_dd * 100:.1f}%控制良好，风险较低",
				"recommendation": "风险承受能力强的投资者可考虑"
			})
		elif max_dd > 0.3:
			insights.append({
				"type": "weakness",
				"metric": "max_drawdown",
				"message": f"最大回撤{max_dd * 100:.1f}%偏高，风险较大",
				"recommendation": "建议加强止损或降低仓位"
			})

		# 胜率洞察
		win_rate = metrics.get("win_rate", 0)
		if win_rate > 0.6:
			insights.append({
				"type": "strength",
				"metric": "win_rate",
				"message": f"胜率{win_rate * 100:.1f}%较高，交易策略具有一致性",
				"recommendation": "适合追求稳定收益的投资者"
			})
		elif win_rate < 0.4:
			insights.append({
				"type": "weakness",
				"metric": "win_rate",
				"message": f"胜率{win_rate * 100:.1f}%偏低，需关注交易质量",
				"recommendation": "建议优化入场和出场策略"
			})

		# 基准比较洞察
		if benchmark and "outperformance" in benchmark:
			outperformance = benchmark["outperformance"]
			if outperformance > 0:
				insights.append({
					"type": "strength",
					"metric": "benchmark",
					"message": f"超额收益{outperformance * 100:.1f}%，表现优于基准",
					"recommendation": "策略具有alpha创造能力"
				})
			else:
				insights.append({
					"type": "weakness",
					"metric": "benchmark",
					"message": f"跑输基准{abs(outperformance) * 100:.1f}%，需优化策略",
					"recommendation": "建议分析跑输原因并调整"
				})

		return insights

	@staticmethod
	def _calculate_risk_adjusted_metrics ( metrics: Dict[str, Any]) -> Dict[str, Any]:
		"""计算风险调整后指标"""
		risk_metrics = {}

		# 夏普比率
		sharpe = metrics.get("sharpe_ratio", 0)
		risk_metrics["sharpe_ratio"] = sharpe

		# 索提诺比率
		sortino = metrics.get("sortino_ratio", 0)
		risk_metrics["sortino_ratio"] = sortino

		# 卡玛比率
		annual_return = metrics.get("annual_return", 0)
		max_dd = abs(metrics.get("max_drawdown", 0))
		if max_dd > 0:
			calmar = annual_return / max_dd
			risk_metrics["calmar_ratio"] = round(calmar, 3)

		# 信息比率
		tracking_error = metrics.get("tracking_error", 0)
		if tracking_error > 0:
			excess_return = metrics.get("excess_return", 0)
			info_ratio = excess_return / tracking_error
			risk_metrics["information_ratio"] = round(info_ratio, 3)

		# 风险价值
		var_95 = metrics.get("var_95", 0)
		risk_metrics["var_95"] = var_95

		# 条件风险价值
		cvar_95 = metrics.get("cvar_95", 0)
		risk_metrics["cvar_95"] = cvar_95

		return risk_metrics

	@staticmethod
	def _classify_strategy ( metrics: Dict[str, Any]) -> Dict[str, Any]:
		"""分类策略类型"""
		classification = {
			"return_profile": "unknown",
			"risk_profile": "unknown",
			"trading_style": "unknown",
			"suitability": "unknown"
		}

		# 根据收益特征分类
		total_return = metrics.get("total_return", 0)
		if total_return > 1.0:  # 100%以上
			classification["return_profile"] = "high_return"
		elif total_return > 0.3:  # 30%以上
			classification["return_profile"] = "medium_return"
		elif total_return > 0:  # 正收益
			classification["return_profile"] = "low_return"
		else:
			classification["return_profile"] = "negative_return"

		# 根据风险特征分类
		max_dd = abs(metrics.get("max_drawdown", 0))
		if max_dd < 0.1:  # 小于10%
			classification["risk_profile"] = "low_risk"
		elif max_dd < 0.2:  # 小于20%
			classification["risk_profile"] = "medium_risk"
		else:
			classification["risk_profile"] = "high_risk"

		# 根据交易特征分类
		total_trades = metrics.get("total_trades", 0)
		avg_trade_duration = metrics.get("avg_trade_duration", 0)

		if total_trades > 1000:
			classification["trading_style"] = "high_frequency"
		elif total_trades > 100:
			classification["trading_style"] = "medium_frequency"
		else:
			classification["trading_style"] = "low_frequency"

		if avg_trade_duration < 5:  # 小于5天
			classification["holding_period"] = "short_term"
		elif avg_trade_duration < 20:  # 小于20天
			classification["holding_period"] = "medium_term"
		else:
			classification["holding_period"] = "long_term"

		# 评估适合性
		sharpe = metrics.get("sharpe_ratio", 0)
		if sharpe > 1.5 and max_dd < 0.15:
			classification["suitability"] = "conservative_investors"
		elif sharpe > 1.0 and max_dd < 0.25:
			classification["suitability"] = "moderate_investors"
		elif sharpe > 0.5:
			classification["suitability"] = "aggressive_investors"
		else:
			classification["suitability"] = "speculative_only"

		return classification


class BacktestRiskAnalysisCompletedEvent(BaseEvent):
	"""
	回测风险分析完成事件

	触发时机：
	- 风险分析计算完成
	- 压力测试执行完毕
	- 风险报告生成完成

	事件数据：
	- risk_metrics: 风险指标集合
	- stress_test_results: 压力测试结果
	- scenario_analysis: 情景分析
	- risk_assessment: 风险评估
	"""

	def __init__ (
			self,
			backtest_id: str,
			risk_metrics: Dict[str, Any],
			stress_test_results: Optional[Dict[str, Any]] = None,
			scenario_analysis: Optional[Dict[str, Any]] = None,
			risk_assessment: Optional[Dict[str, Any]] = None,
			**kwargs
	):
		super().__init__(
			module="events",
			event_type=BacktestEventTypes.METRICS_CALCULATED.value,
			priority=EventPriority.NORMAL,
			source="risk_engine",
			**kwargs
		)

		if stress_test_results is None:
			stress_test_results = {}
		if scenario_analysis is None:
			scenario_analysis = {}
		if risk_assessment is None:
			risk_assessment = self._assess_risk(risk_metrics, stress_test_results)

		# 生成风险洞察
		risk_insights = self._generate_risk_insights(risk_metrics, stress_test_results)

		# 计算风险评分
		risk_score = self._calculate_risk_score(risk_metrics, stress_test_results)

		self.data = {
			"backtest_id": backtest_id,
			"risk_metrics": risk_metrics,
			"stress_test_results": stress_test_results,
			"scenario_analysis": scenario_analysis,
			"risk_assessment": risk_assessment,
			"analysis_time": datetime.now().isoformat(),
			"risk_insights": risk_insights,
			"risk_score": risk_score,
			"risk_mitigation": self._suggest_risk_mitigation(risk_metrics, risk_assessment),
			"compliance_check": self._check_compliance(risk_metrics)
		}

	@staticmethod
	def _assess_risk ( metrics: Dict[str, Any], stress_tests: Dict[str, Any]) -> Dict[str, Any]:
		"""进行风险评估"""
		assessment = {
			"market_risk": "medium",
			"credit_risk": "low",
			"liquidity_risk": "low",
			"operational_risk": "low",
			"overall_risk": "medium"
		}

		# 市场风险评估
		volatility = metrics.get("volatility", 0)
		if volatility > 0.3:
			assessment["market_risk"] = "high"
		elif volatility > 0.15:
			assessment["market_risk"] = "medium"
		else:
			assessment["market_risk"] = "low"

		# 最大回撤评估
		max_dd = abs(metrics.get("max_drawdown", 0))
		if max_dd > 0.3:
			assessment["market_risk"] = "high"
		elif max_dd > 0.2:
			assessment["market_risk"] = max(assessment["market_risk"], "medium")

		# 压力测试评估
		if stress_tests and "worst_case_loss" in stress_tests:
			worst_loss = abs(stress_tests["worst_case_loss"])
			if worst_loss > 0.5:
				assessment["market_risk"] = "high"
			elif worst_loss > 0.3:
				assessment["market_risk"] = max(assessment["market_risk"], "medium")

		# 流动性风险评估
		avg_trade_size = metrics.get("avg_trade_size", 0)
		if avg_trade_size > 1000000:  # 100万以上
			assessment["liquidity_risk"] = "medium"

		# 整体风险评估
		risk_levels = {"low": 1, "medium": 2, "high": 3}
		total_score = sum(risk_levels[level] for level in assessment.values() if level in risk_levels)
		avg_score = total_score / len([v for v in assessment.values() if v in risk_levels])

		if avg_score >= 2.5:
			assessment["overall_risk"] = "high"
		elif avg_score >= 1.5:
			assessment["overall_risk"] = "medium"
		else:
			assessment["overall_risk"] = "low"

		return assessment

	@staticmethod
	def _generate_risk_insights ( metrics: Dict[str, Any], stress_tests: Dict[str, Any]) -> List[Dict[str, Any]]:
		"""生成风险洞察"""
		insights = []

		# 波动率洞察
		volatility = metrics.get("volatility", 0)
		if volatility > 0.25:
			insights.append({
				"type": "warning",
				"category": "market_risk",
				"title": "高波动率风险",
				"description": f"策略波动率{volatility * 100:.1f}%偏高，可能面临较大价格波动风险",
				"severity": "high"
			})

		# 最大回撤洞察
		max_dd = abs(metrics.get("max_drawdown", 0))
		if max_dd > 0.3:
			insights.append({
				"type": "warning",
				"category": "drawdown_risk",
				"title": "大幅回撤风险",
				"description": f"最大回撤{max_dd * 100:.1f}%过高，在不利市场条件下可能遭受重大损失",
				"severity": "high"
			})

		# 风险价值洞察
		var_95 = metrics.get("var_95", 0)
		if var_95 < -0.1:
			insights.append({
				"type": "warning",
				"category": "tail_risk",
				"title": "尾部风险",
				"description": f"95%置信度下单日最大损失可能超过{abs(var_95) * 100:.1f}%",
				"severity": "medium"
			})

		# 压力测试洞察
		if stress_tests and "stress_scenarios" in stress_tests:
			failed_scenarios = [s for s in stress_tests["stress_scenarios"] if s.get("passed") == False]
			if failed_scenarios:
				insights.append({
					"type": "alert",
					"category": "stress_test",
					"title": "压力测试失败",
					"description": f"{len(failed_scenarios)}个压力测试场景未通过",
					"severity": "medium",
					"details": failed_scenarios[:3]  # 只显示前3个
				})

		return insights

	@staticmethod
	def _calculate_risk_score ( metrics: Dict[str, Any], stress_tests: Dict[str, Any]) -> Dict[str, Any]:
		"""计算风险评分（0-100，越高风险越大）"""
		score = 50  # 基础分

		# 波动率贡献（最高20分）
		volatility = metrics.get("volatility", 0)
		volatility_score = min(20, volatility * 100)
		score += volatility_score

		# 最大回撤贡献（最高30分）
		max_dd = abs(metrics.get("max_drawdown", 0))
		dd_score = min(30, max_dd * 100)
		score += dd_score

		# 风险价值贡献（最高20分）
		var_95 = abs(metrics.get("var_95", 0))
		var_score = min(20, var_95 * 200)  # 放大影响
		score += var_score

		# 压力测试贡献（最高30分）
		stress_score = 0
		if stress_tests and "worst_case_loss" in stress_tests:
			worst_loss = abs(stress_tests["worst_case_loss"])
			stress_score = min(30, worst_loss * 60)  # 放大影响
			score += stress_score

		# 确保分数在0-100之间
		final_score = max(0, min(100, score))

		# 风险等级
		if final_score >= 80:
			risk_level = "high"
		elif final_score >= 60:
			risk_level = "medium_high"
		elif final_score >= 40:
			risk_level = "medium"
		elif final_score >= 20:
			risk_level = "medium_low"
		else:
			risk_level = "low"

		return {
			"score": round(final_score, 1),
			"level": risk_level,
			"components": {
				"volatility": round(volatility_score, 1),
				"max_drawdown": round(dd_score, 1),
				"value_at_risk": round(var_score, 1),
				"stress_test": round(stress_score, 1) if 'stress_score' in locals() else 0
			}
		}

	@staticmethod
	def _suggest_risk_mitigation ( metrics: Dict[str, Any], assessment: Dict[str, Any]) -> List[str]:
		"""建议风险缓解措施"""
		mitigations = []

		# 根据风险评估建议措施
		if assessment.get("market_risk") == "high":
			mitigations.extend([
				"降低仓位规模以减少市场风险暴露",
				"增加对冲策略以抵消市场风险",
				"设置更严格的价格止损"
			])

		max_dd = abs(metrics.get("max_drawdown", 0))
		if max_dd > 0.3:
			mitigations.append(f"最大回撤{max_dd * 100:.1f}%过高，建议设置动态止损和仓位管理")

		volatility = metrics.get("volatility", 0)
		if volatility > 0.25:
			mitigations.append(f"波动率{volatility * 100:.1f}%偏高，建议增加低波动性资产配置")

		# 通用建议
		mitigations.extend([
			"定期进行压力测试和情景分析",
			"建立风险监控和预警机制",
			"制定应急预案以应对极端市场情况"
		])

		return mitigations


	@staticmethod
	def _check_compliance ( metrics: Dict[str, Any]) -> Dict[str, Any]:
		"""检查合规性"""
		compliance = {
			"regulatory_requirements": [],
			"internal_policies": [],
			"overall_compliance": "compliant"
		}

		# 检查监管要求
		max_dd = abs(metrics.get("max_drawdown", 0))
		if max_dd > 0.5:  # 超过50%回撤
			compliance["regulatory_requirements"].append({
				"requirement": "最大回撤限制",
				"status": "violation",
				"description": f"最大回撤{max_dd * 100:.1f}%超过50%限制",
				"action_required": True
			})

		# 检查内部政策
		sharpe = metrics.get("sharpe_ratio", 0)
		if sharpe < 0:  # 负夏普比率
			compliance["internal_policies"].append({
				"policy": "最低绩效要求",
				"status": "violation",
				"description": f"夏普比率{sharpe:.2f}为负，不符合最低要求",
				"action_required": True
			})

		# 总体合规状态
		violations = [v for v in compliance["regulatory_requirements"] + compliance["internal_policies"]
		              if v.get("status") == "violation"]

		if violations:
			compliance["overall_compliance"] = "non_compliant"

		return compliance