# -*- coding: utf-8 -*-
"""
报告生成器模块
负责生成PDF/HTML格式的分析报告，包括绩效报告、风险报告等
位置：quant_server/modules/analysis/visualizers/report_generator.py
"""

import base64
import warnings
from datetime import datetime
from pathlib import Path
from typing import List, Dict, Any, Optional

import jinja2
import numpy as np
import pdfkit

from quant_server.modules.analysis.utils.statistic_utils import StatisticUtils
from quant_server.modules.analysis.visualizers.chart_generator import ChartGenerator


class ReportGenerator:
	"""报告生成器类"""

	def __init__ (self, output_dir: str = './reports', theme: str = 'quant'):
		"""
		初始化报告生成器

		Args:
			output_dir: 输出目录
			theme: 主题风格
		"""
		self.output_dir = Path(output_dir)
		self.output_dir.mkdir(parents=True, exist_ok=True)

		self.theme = theme
		self.chart_generator = ChartGenerator(theme=theme)
		self.stat_utils = StatisticUtils()

		# 加载Jinja2模板
		self.template_dir = Path(__file__).parent / 'templates'
		self.template_env = jinja2.Environment(
			loader=jinja2.FileSystemLoader(self.template_dir),
			autoescape=jinja2.select_autoescape(['html', 'xml'])
		)

	def generate_performance_report (self,
	                                 strategy_name: str,
	                                 equity_data: Dict[str, Any],
	                                 trade_data: List[Dict[str, Any]],
	                                 benchmark_data: Optional[Dict[str, Any]] = None,
	                                 output_format: str = 'html',
	                                 include_charts: bool = True) -> str:
		"""
		生成绩效报告

		Args:
			strategy_name: 策略名称
			equity_data: 净值数据
			trade_data: 交易数据
			benchmark_data: 基准数据
			output_format: 输出格式 ('html', 'pdf')
			include_charts: 是否包含图表

		Returns:
			str: 报告文件路径
		"""
		# 计算绩效指标
		metrics = self._calculate_performance_metrics(
			equity_data, trade_data, benchmark_data
		)

		# 生成图表
		charts = {}
		if include_charts:
			charts = self._generate_report_charts(
				equity_data, trade_data, benchmark_data
			)

		# 准备报告数据
		report_data = {
			'strategy_name': strategy_name,
			'generation_date': datetime.now().strftime('%Y-%m-%d %H:%M:%S'),
			'period': self._get_period_string(equity_data),
			'metrics': metrics,
			'charts': charts,
			'trade_summary': self._summarize_trades(trade_data)
		}

		# 生成报告
		if output_format == 'html':
			return self._generate_html_report(report_data, 'performance_report.html')
		elif output_format == 'pdf':
			return self._generate_pdf_report(report_data, 'performance_report.pdf')
		else:
			raise ValueError(f"不支持的输出格式: {output_format}")

	def generate_risk_report (self,
	                          strategy_name: str,
	                          returns: List[float],
	                          positions: List[Dict[str, Any]],
	                          risk_metrics: Dict[str, Any],
	                          output_format: str = 'html') -> str:
		"""
		生成风险报告

		Args:
			strategy_name: 策略名称
			returns: 收益率序列
			positions: 持仓数据
			risk_metrics: 风险指标
			output_format: 输出格式

		Returns:
			str: 报告文件路径
		"""
		# 计算风险指标
		detailed_metrics = self._calculate_risk_metrics(returns, positions)
		detailed_metrics.update(risk_metrics)

		# 生成风险图表
		charts = self._generate_risk_charts(returns, positions, detailed_metrics)

		# 准备报告数据
		report_data = {
			'strategy_name': strategy_name,
			'generation_date': datetime.now().strftime('%Y-%m-%d %H:%M:%S'),
			'metrics': detailed_metrics,
			'charts': charts,
			'position_summary': self._summarize_positions(positions),
			'risk_assessment': self._assess_risk_level(detailed_metrics)
		}

		# 生成报告
		if output_format == 'html':
			return self._generate_html_report(report_data, 'risk_report.html')
		elif output_format == 'pdf':
			return self._generate_pdf_report(report_data, 'risk_report.pdf')
		else:
			raise ValueError(f"不支持的输出格式: {output_format}")

	def generate_comparison_report (self,
	                                strategies: Dict[str, Dict[str, Any]],
	                                comparison_metrics: List[str],
	                                output_format: str = 'html') -> str:
		"""
		生成策略比较报告

		Args:
			strategies: 策略数据字典
			comparison_metrics: 比较指标列表
			output_format: 输出格式

		Returns:
			str: 报告文件路径
		"""
		# 计算比较指标
		comparison_data = self._calculate_comparison_metrics(strategies, comparison_metrics)

		# 生成比较图表
		charts = self._generate_comparison_charts(strategies, comparison_metrics)

		# 准备报告数据
		report_data = {
			'strategies': list(strategies.keys()),
			'generation_date': datetime.now().strftime('%Y-%m-%d %H:%M:%S'),
			'comparison_metrics': comparison_data,
			'charts': charts,
			'ranking': self._rank_strategies(comparison_data)
		}

		# 生成报告
		if output_format == 'html':
			return self._generate_html_report(report_data, 'comparison_report.html')
		elif output_format == 'pdf':
			return self._generate_pdf_report(report_data, 'comparison_report.pdf')
		else:
			raise ValueError(f"不支持的输出格式: {output_format}")

	def generate_trade_analysis_report (self,
	                                    trades: List[Dict[str, Any]],
	                                    strategy_name: str,
	                                    output_format: str = 'html') -> str:
		"""
		生成交易分析报告

		Args:
			trades: 交易记录
			strategy_name: 策略名称
			output_format: 输出格式

		Returns:
			str: 报告文件路径
		"""
		# 分析交易数据
		trade_analysis = self._analyze_trades(trades)

		# 生成交易图表
		charts = self._generate_trade_charts(trades)

		# 准备报告数据
		report_data = {
			'strategy_name': strategy_name,
			'generation_date': datetime.now().strftime('%Y-%m-%d %H:%M:%S'),
			'trade_count': len(trades),
			'events': trade_analysis,
			'charts': charts,
			'recommendations': self._generate_trade_recommendations(trade_analysis)
		}

		# 生成报告
		if output_format == 'html':
			return self._generate_html_report(report_data, 'trade_analysis_report.html')
		elif output_format == 'pdf':
			return self._generate_pdf_report(report_data, 'trade_analysis_report.pdf')
		else:
			raise ValueError(f"不支持的输出格式: {output_format}")

	async def generate_html_report (self, report) -> str:
		"""根据 AnalysisReport 业务模型生成 HTML 报告内容"""
		report_data = report.to_dict()
		report_data["generation_date"] = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
		try:
			template = self.template_env.get_template("report_template.html")
			html_content = template.render(**report_data)
		except jinja2.TemplateNotFound:
			html_content = self._build_fallback_html(report_data)
		return html_content

	async def generate_pdf_report (self, report) -> bytes:
		"""根据 AnalysisReport 业务模型生成 PDF 报告内容"""
		html_content = await self.generate_html_report(report)
		try:
			pdf_bytes = pdfkit.from_string(html_content, False)
			return pdf_bytes
		except Exception as e:
			warnings.warn(f"PDF生成失败，降级为HTML: {e}")
			return html_content.encode("utf-8")

	def _build_fallback_html (self, report_data: dict) -> str:
		"""模板缺失时构建备用HTML报告"""
		rows = []
		for key, value in report_data.items():
			if isinstance(value, (dict, list)):
				value = str(value)[:500]
			rows.append("<tr><td>" + str(key) + "</td><td>" + str(value) + "</td></tr>")
		title = report_data.get("title", "分析报告")
		gen_time = report_data.get("generation_date", "")
		html = "<!DOCTYPE html>\n"
		html += "<html><head><meta charset=\"utf-8\"/><title>" + str(title) + "</title></head>\n"
		html += "<body>\n"
		html += "<h1>" + str(title) + "</h1>\n"
		html += "<p>生成时间: " + str(gen_time) + "</p>\n"
		html += "<table border=\"1\"><tr><th>字段</th><th>值</th></tr>"
		html += "".join(rows)
		html += "</table></body></html>"
		return html

	def _calculate_performance_metrics (self,
	                                    equity_data: Dict[str, Any],
	                                    trade_data: List[Dict[str, Any]],
	                                    benchmark_data: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
		"""计算绩效指标"""
		dates = equity_data.get('dates', [])
		equity_values = equity_data.get('values', [])

		if len(equity_values) < 2:
			return {}

		# 计算基本指标
		returns = self.stat_utils.calculate_returns(equity_values)

		metrics = {
			# 收益指标
			'total_return': (equity_values[-1] / equity_values[0] - 1) if equity_values[0] != 0 else 0,
			'annual_return': np.mean(returns) * 252 if len(returns) > 0 else 0,
			'monthly_return': np.mean(returns) * 21 if len(returns) > 0 else 0,

			# 风险指标
			'volatility': np.std(returns) * np.sqrt(252) if len(returns) > 0 else 0,
			'sharpe_ratio': self.stat_utils.calculate_sharpe_ratio(returns),
			'sortino_ratio': self.stat_utils.calculate_sortino_ratio(returns),

			# 回撤指标
			'max_drawdown': self.stat_utils.calculate_max_drawdown(equity_values)[0],
			'calmar_ratio': 0,  # 稍后计算
		}

		# 计算卡玛比率
		if metrics['max_drawdown'] > 0:
			metrics['calmar_ratio'] = abs(metrics['annual_return'] / metrics['max_drawdown'])

		# 计算交易相关指标
		if trade_data:
			profits = [trade.get('profit', 0) for trade in trade_data]
			winning_trades = [p for p in profits if p > 0]
			losing_trades = [p for p in profits if p < 0]

			metrics.update({
				'win_rate': len(winning_trades) / len(trade_data),
				'profit_factor': sum(winning_trades) / abs(sum(losing_trades)) if losing_trades else float('inf'),
				'avg_win': np.mean(winning_trades) if winning_trades else 0,
				'avg_loss': abs(np.mean(losing_trades)) if losing_trades else 0,
				'avg_trade': np.mean(profits),
				'total_trades': len(trade_data)
			})

		# 如果有基准，计算相对指标
		if benchmark_data:
			benchmark_values = benchmark_data.get('values', [])
			if len(benchmark_values) == len(equity_values):
				benchmark_returns = self.stat_utils.calculate_returns(benchmark_values)

				beta, alpha = self.stat_utils.calculate_beta_alpha(
					returns, benchmark_returns
				)

				metrics.update({
					'alpha': alpha,
					'beta': beta,
					'information_ratio': self.stat_utils.calculate_information_ratio(
						returns, benchmark_returns
					),
					'tracking_error': np.std(np.array(returns) - np.array(benchmark_returns)) * np.sqrt(252),
				})

		# 格式化指标
		formatted_metrics = {}
		for key, value in metrics.items():
			if isinstance(value, float):
				if 'rate' in key or 'ratio' in key or key in ['alpha', 'beta']:
					formatted_metrics[key] = f"{value:.4f}"
				elif 'return' in key or 'drawdown' in key:
					formatted_metrics[key] = f"{value:.2%}"
				elif 'volatility' in key:
					formatted_metrics[key] = f"{value:.2%}"
				else:
					formatted_metrics[key] = f"{value:.2f}"
			else:
				formatted_metrics[key] = value

		return formatted_metrics

	def _generate_report_charts (self,
	                             equity_data: Dict[str, Any],
	                             trade_data: List[Dict[str, Any]],
	                             benchmark_data: Optional[Dict[str, Any]] = None) -> Dict[str, str]:
		"""生成报告图表"""
		charts = {}

		try:
			# 生成净值曲线图
			dates = equity_data.get('dates', [])
			equity_values = equity_data.get('values', [])

			if benchmark_data:
				benchmark_values = benchmark_data.get('values', [])
			else:
				benchmark_values = None

			fig = self.chart_generator.generate_equity_curve(
				dates, equity_values, benchmark_values,
				title='策略净值曲线'
			)

			# 保存图表为base64
			equity_chart = self._figure_to_base64(fig)
			charts['equity_curve'] = equity_chart

			# 生成收益率分布图
			if len(equity_values) > 2:
				returns = self.stat_utils.calculate_returns(equity_values)
				fig = self.chart_generator.generate_returns_distribution(
					returns, title='收益率分布'
				)
				returns_chart = self._figure_to_base64(fig)
				charts['returns_distribution'] = returns_chart

			# 生成交易分析图
			if trade_data:
				fig = self.chart_generator.generate_trade_analysis_chart(
					trade_data, title='交易分析'
				)
				trade_chart = self._figure_to_base64(fig)
				charts['trade_analysis'] = trade_chart

		except Exception as e:
			warnings.warn(f"生成图表时出错: {e}")

		return charts

	def _generate_html_report (self, data: Dict[str, Any], filename: str) -> str:
		"""生成HTML报告"""
		# 加载模板
		template = self.template_env.get_template('report_template.html')

		# 渲染模板
		html_content = template.render(**data)

		# 保存文件
		filepath = self.output_dir / filename
		filepath.write_text(html_content, encoding='utf-8')

		return str(filepath)

	def _generate_pdf_report (self, data: Dict[str, Any], filename: str) -> str:
		"""生成PDF报告"""
		# 首先生成HTML
		html_filepath = self._generate_html_report(data, filename.replace('.pdf', '.html'))

		# 转换为PDF
		pdf_filepath = self.output_dir / filename

		try:
			# 需要安装wkhtmltopdf
			pdfkit.from_file(html_filepath, str(pdf_filepath))
		except Exception as e:
			warnings.warn(f"PDF生成失败: {e}")
			# 如果PDF生成失败，返回HTML文件
			return html_filepath

		return str(pdf_filepath)

	def _figure_to_base64 (self, fig) -> str:
		"""将Plotly图表转换为base64字符串"""
		try:
			# 将图表保存为图片
			img_bytes = fig.to_image(format="png", width=1200, height=600)
			base64_str = base64.b64encode(img_bytes).decode('utf-8')
			return f"data:image/png;base64,{base64_str}"
		except Exception as e:
			warnings.warn(f"图表转换失败: {e}")
			return ""

	def _get_period_string (self, equity_data: Dict[str, Any]) -> str:
		"""获取期间 字符串"""
		dates = equity_data.get('dates', [])
		if len(dates) >= 2:
			start_date = dates[0].strftime('%Y-%m-%d') if isinstance(dates[0], datetime) else dates[0]
			end_date = dates[-1].strftime('%Y-%m-%d') if isinstance(dates[-1], datetime) else dates[-1]
			return f"{start_date} 至 {end_date}"
		return "未知期间"

	def _summarize_trades (self, trades: List[Dict[str, Any]]) -> Dict[str, Any]:
		"""总结交易数据"""
		if not trades:
			return {}

		profits = [trade.get('profit', 0) for trade in trades]
		winning_trades = [p for p in profits if p > 0]
		losing_trades = [p for p in profits if p < 0]

		return {
			'total_trades': len(trades),
			'winning_trades': len(winning_trades),
			'losing_trades': len(losing_trades),
			'total_profit': sum(profits),
			'max_win': max(winning_trades) if winning_trades else 0,
			'max_loss': min(losing_trades) if losing_trades else 0,
			'avg_trade_duration': self._calculate_avg_trade_duration(trades)
		}

	def _calculate_avg_trade_duration (self, trades: List[Dict[str, Any]]) -> str:
		"""计算平均持仓时间"""
		if not trades:
			return "N/A"

		durations = []
		for trade in trades:
			entry_time = trade.get('entry_time')
			exit_time = trade.get('exit_time')

			if entry_time and exit_time:
				if isinstance(entry_time, str):
					entry_time = datetime.fromisoformat(entry_time.replace('Z', '+00:00'))
				if isinstance(exit_time, str):
					exit_time = datetime.fromisoformat(exit_time.replace('Z', '+00:00'))

				duration = (exit_time - entry_time).total_seconds() / 3600  # 转换为小时
				durations.append(duration)

		if durations:
			avg_hours = np.mean(durations)
			if avg_hours < 24:
				return f"{avg_hours:.1f} 小时"
			else:
				return f"{avg_hours / 24:.1f} 天"

		return "N/A"

	def _calculate_risk_metrics (self,
	                             returns: List[float],
	                             positions: List[Dict[str, Any]]) -> Dict[str, Any]:
		"""计算风险指标"""
		if len(returns) < 2:
			return {}

		returns_array = np.array(returns)

		metrics = {
			'volatility': np.std(returns_array) * np.sqrt(252),
			'var_95': self.stat_utils.calculate_var_cvar(returns_array, 0.95)[0],
			'cvar_95': self.stat_utils.calculate_var_cvar(returns_array, 0.95)[1],
			'skewness': self.stat_utils.calculate_skewness_kurtosis(returns_array)[0],
			'kurtosis': self.stat_utils.calculate_skewness_kurtosis(returns_array)[1],
		}

		# 格式化
		formatted_metrics = {}
		for key, value in metrics.items():
			if isinstance(value, float):
				if key in ['skewness', 'kurtosis']:
					formatted_metrics[key] = f"{value:.4f}"
				else:
					formatted_metrics[key] = f"{value:.2%}"
			else:
				formatted_metrics[key] = value

		return formatted_metrics

	def _generate_risk_charts (self,
	                           returns: List[float],
	                           positions: List[Dict[str, Any]],
	                           metrics: Dict[str, Any]) -> Dict[str, str]:
		"""生成风险图表"""
		charts = {}

		try:
			# 生成风险指标雷达图
			fig = self.chart_generator.generate_risk_metrics_chart(
				{k: float(v.strip('%')) / 100 if '%' in str(v) else float(v)
				 for k, v in metrics.items() if isinstance(v, str)},
				title='风险指标'
			)
			risk_chart = self._figure_to_base64(fig)
			charts['risk_metrics'] = risk_chart

			# 生成收益率分布图（显示风险）
			fig = self.chart_generator.generate_returns_distribution(
				returns, title='收益率分布与风险'
			)
			returns_chart = self._figure_to_base64(fig)
			charts['returns_with_risk'] = returns_chart

		except Exception as e:
			warnings.warn(f"生成风险图表时出错: {e}")

		return charts

	def _summarize_positions (self, positions: List[Dict[str, Any]]) -> Dict[str, Any]:
		"""总结持仓数据"""
		if not positions:
			return {}

		# 按证券分组
		position_by_symbol = {}
		for position in positions:
			symbol = position.get('symbol')
			if symbol:
				if symbol not in position_by_symbol:
					position_by_symbol[symbol] = {
						'total_position': 0,
						'market_value': 0,
						'avg_cost': 0
					}

				position_by_symbol[symbol]['total_position'] += position.get('quantity', 0)
				position_by_symbol[symbol]['market_value'] += position.get('market_value', 0)

		return {
			'total_positions': len(positions),
			'unique_symbols': len(position_by_symbol),
			'position_concentration': self._calculate_concentration(position_by_symbol),
			'largest_position': max(position_by_symbol.values(),
			                        key=lambda x: x['market_value']) if position_by_symbol else {}
		}

	def _calculate_concentration (self, positions: Dict[str, Dict]) -> float:
		"""计算持仓集中度"""
		if not positions:
			return 0.0

		total_value = sum(pos['market_value'] for pos in positions.values())
		if total_value == 0:
			return 0.0

		# 计算前3大持仓的集中度
		sorted_values = sorted([pos['market_value'] for pos in positions.values()], reverse=True)
		top3_value = sum(sorted_values[:3])

		return top3_value / total_value

	def _assess_risk_level (self, metrics: Dict[str, Any]) -> Dict[str, Any]:
		"""评估风险等级"""
		risk_level = '低'
		warnings = []

		# 基于波动率评估
		volatility = float(metrics.get('volatility', '0%').strip('%')) / 100
		if volatility > 0.3:
			risk_level = '高'
			warnings.append(f"波动率过高: {volatility:.1%}")
		elif volatility > 0.2:
			risk_level = '中'
			warnings.append(f"波动率较高: {volatility:.1%}")

		# 基于最大回撤评估
		max_drawdown = float(metrics.get('max_drawdown', '0%').strip('%')) / 100
		if max_drawdown > 0.3:
			risk_level = '高'
			warnings.append(f"最大回撤过大: {max_drawdown:.1%}")
		elif max_drawdown > 0.2:
			if risk_level != '高':
				risk_level = '中'
			warnings.append(f"最大回撤较大: {max_drawdown:.1%}")

		# 基于VaR评估
		var_95 = float(metrics.get('var_95', '0%').strip('%')) / 100
		if var_95 > 0.05:
			warnings.append(f"95%置信度下日损失可能超过: {var_95:.1%}")

		return {
			'risk_level': risk_level,
			'warnings': warnings,
			'recommendations': self._generate_risk_recommendations(risk_level, warnings)
		}

	def _generate_risk_recommendations (self, risk_level: str, warnings: List[str]) -> List[str]:
		"""生成风险建议"""
		recommendations = []

		if risk_level == '高':
			recommendations.extend([
				"建议降低仓位或增加对冲",
				"考虑增加止损策略",
				"定期监控风险指标"
			])
		elif risk_level == '中':
			recommendations.extend([
				"建议适当分散投资",
				"设置合理的止损点",
				"定期评估风险承受能力"
			])
		else:
			recommendations.append("当前风险水平适中，继续保持")

		return recommendations

	def _calculate_comparison_metrics (self,
	                                   strategies: Dict[str, Dict[str, Any]],
	                                   metrics_list: List[str]) -> Dict[str, Dict[str, Any]]:
		"""计算比较指标"""
		comparison_data = {}

		for metric in metrics_list:
			comparison_data[metric] = {}
			for strategy_name, strategy_data in strategies.items():
				if metric in strategy_data.get('metrics', {}):
					comparison_data[metric][strategy_name] = strategy_data['metrics'][metric]
				else:
					comparison_data[metric][strategy_name] = 'N/A'

		return comparison_data

	def _generate_comparison_charts (self,
	                                 strategies: Dict[str, Dict[str, Any]],
	                                 metrics_list: List[str]) -> Dict[str, str]:
		"""生成比较图表"""
		charts = {}

		try:
			# 生成策略比较图
			fig = self.chart_generator.generate_performance_comparison(
				strategies, title='策略绩效比较'
			)
			comparison_chart = self._figure_to_base64(fig)
			charts['strategy_comparison'] = comparison_chart

		except Exception as e:
			warnings.warn(f"生成比较图表时出错: {e}")

		return charts

	def _rank_strategies (self, comparison_data: Dict[str, Dict[str, Any]]) -> List[Dict[str, Any]]:
		"""对策略进行排名"""
		if not comparison_data:
			return []

		strategies = list(next(iter(comparison_data.values())).keys())
		scores = {strategy: 0 for strategy in strategies}

		for metric, strategy_values in comparison_data.items():
			# 过滤出可比较的数值
			numeric_values = {}
			for strategy, value in strategy_values.items():
				try:
					if isinstance(value, str) and '%' in value:
						numeric_values[strategy] = float(value.strip('%')) / 100
					else:
						numeric_values[strategy] = float(value)
				except (ValueError, TypeError):
					continue

			if numeric_values:
				# 对每个指标进行排名（值越大越好，除了回撤等）
				if 'drawdown' in metric.lower() or 'var' in metric.lower():
					# 对于风险指标，值越小越好
					sorted_strategies = sorted(numeric_values.items(), key=lambda x: x[1])
				else:
					# 对于收益指标，值越大越好
					sorted_strategies = sorted(numeric_values.items(), key=lambda x: x[1], reverse=True)

				# 分配分数
				for rank, (strategy, _) in enumerate(sorted_strategies, 1):
					scores[strategy] += (len(strategies) - rank + 1)

		# 按总分排序
		ranked_strategies = sorted(scores.items(), key=lambda x: x[1], reverse=True)

		return [{'events': s, 'score': score} for s, score in ranked_strategies]

	def _analyze_trades (self, trades: List[Dict[str, Any]]) -> Dict[str, Any]:
		"""分析交易数据"""
		if not trades:
			return {}

		profits = [trade.get('profit', 0) for trade in trades]
		winning_trades = [p for p in profits if p > 0]
		losing_trades = [p for p in profits if p < 0]

		analysis = {
			'basic_stats': {
				'total_trades': len(trades),
				'winning_trades': len(winning_trades),
				'losing_trades': len(losing_trades),
				'win_rate': len(winning_trades) / len(trades) if trades else 0,
				'total_profit': sum(profits),
				'avg_profit_per_trade': np.mean(profits) if profits else 0
			},
			'performance_stats': {
				'avg_win': np.mean(winning_trades) if winning_trades else 0,
				'avg_loss': abs(np.mean(losing_trades)) if losing_trades else 0,
				'largest_win': max(winning_trades) if winning_trades else 0,
				'largest_loss': min(losing_trades) if losing_trades else 0,
				'profit_factor': sum(winning_trades) / abs(sum(losing_trades)) if losing_trades else float('inf')
			},
			'time_analysis': {
				'best_month': self._find_best_month(trades),
				'worst_month': self._find_worst_month(trades),
				'avg_holding_period': self._calculate_avg_trade_duration(trades)
			}
		}

		return analysis

	def _find_best_month (self, trades: List[Dict[str, Any]]) -> Dict[str, Any]:
		"""找出表现最好的月份"""
		monthly_profits = {}

		for trade in trades:
			trade_time = trade.get('trade_time')
			if trade_time:
				if isinstance(trade_time, str):
					trade_time = datetime.fromisoformat(trade_time.replace('Z', '+00:00'))

				month_key = trade_time.strftime('%Y-%m')
				monthly_profits[month_key] = monthly_profits.get(month_key, 0) + trade.get('profit', 0)

		if monthly_profits:
			best_month = max(monthly_profits.items(), key=lambda x: x[1])
			return {'month': best_month[0], 'profit': best_month[1]}

		return {'month': 'N/A', 'profit': 0}

	def _find_worst_month (self, trades: List[Dict[str, Any]]) -> Dict[str, Any]:
		"""找出表现最差的月份"""
		monthly_profits = {}

		for trade in trades:
			trade_time = trade.get('trade_time')
			if trade_time:
				if isinstance(trade_time, str):
					trade_time = datetime.fromisoformat(trade_time.replace('Z', '+00:00'))

				month_key = trade_time.strftime('%Y-%m')
				monthly_profits[month_key] = monthly_profits.get(month_key, 0) + trade.get('profit', 0)

		if monthly_profits:
			worst_month = min(monthly_profits.items(), key=lambda x: x[1])
			return {'month': worst_month[0], 'profit': worst_month[1]}

		return {'month': 'N/A', 'profit': 0}

	def _generate_trade_charts (self, trades: List[Dict[str, Any]]) -> Dict[str, str]:
		"""生成交易图表"""
		charts = {}

		try:
			# 生成交易分析图
			fig = self.chart_generator.generate_trade_analysis_chart(
				trades, title='交易分析'
			)
			trade_chart = self._figure_to_base64(fig)
			charts['trade_analysis'] = trade_chart

		except Exception as e:
			warnings.warn(f"生成交易图表时出错: {e}")

		return charts

	def _generate_trade_recommendations (self, analysis: Dict[str, Any]) -> List[str]:
		"""生成交易建议"""
		recommendations = []
		stats = analysis.get('basic_stats', {})
		perf_stats = analysis.get('performance_stats', {})

		win_rate = stats.get('win_rate', 0)
		profit_factor = perf_stats.get('profit_factor', 0)
		avg_win = perf_stats.get('avg_win', 0)
		avg_loss = perf_stats.get('avg_loss', 0)

		if win_rate < 0.3:
			recommendations.append("胜率较低，建议优化入场时机或增加过滤条件")
		elif win_rate > 0.7:
			recommendations.append("胜率较高，但需注意可能过度拟合")

		if profit_factor < 1.0:
			recommendations.append("盈利因子小于1，总体亏损，建议重新评估策略")
		elif profit_factor < 1.5:
			recommendations.append("盈利因子一般，有改进空间")
		else:
			recommendations.append("盈利因子良好，继续保持")

		if avg_loss > avg_win * 2 and win_rate < 0.5:
			recommendations.append("平均亏损远大于平均盈利，建议加强风险管理")

		if stats.get('total_trades', 0) < 30:
			recommendations.append("交易样本较少，建议在更多数据上测试")

		return recommendations
