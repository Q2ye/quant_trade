# -*- coding: utf-8 -*-
"""
图表生成器模块
负责生成各种量化分析图表，包括收益曲线、风险图表、分布图等
位置：quant_server/modules/analysis/visualizers/chart_generator.py
"""

from datetime import datetime
from typing import List, Dict, Any, Optional

import numpy as np
import pandas as pd
import plotly.graph_objects as go
from plotly.subplots import make_subplots

from modules.analysis.utils.chart_utils import ChartStyle, ChartUtils
from modules.analysis.utils.statistic_utils import StatisticUtils


class ChartGenerator:
	"""图表生成器类"""

	def __init__ (self, theme: str = 'quant', template: str = 'plotly_white'):
		"""
		初始化图表生成器

		Args:
			theme: 颜色主题
			template: 图表模板
		"""
		self.theme = theme
		self.template = template
		self.colors = ChartStyle.get_theme(theme)
		self.chart_utils = ChartUtils()
		self.stat_utils = StatisticUtils()

	def generate_equity_curve (self,
	                           dates: List[datetime],
	                           equity_values: List[float],
	                           benchmark_values: Optional[List[float]] = None,
	                           benchmark_name: str = '基准',
	                           title: str = '净值曲线',
	                           show_drawdown: bool = True) -> go.Figure:
		"""
		生成净值曲线图

		Args:
			dates: 日期序列
			equity_values: 净值序列
			benchmark_values: 基准净值序列
			benchmark_name: 基准名称
			title: 图表标题
			show_drawdown: 是否显示回撤

		Returns:
			go.Figure: 净值曲线图
		"""
		if benchmark_values is not None and len(benchmark_values) != len(equity_values):
			benchmark_values = None

		# 创建图表
		if show_drawdown and benchmark_values is None:
			# 显示净值曲线和回撤
			fig = self.chart_utils.create_figure(
				title=title,
				xaxis_title='日期',
				yaxis_title='净值',
				theme=self.theme,
				template=self.template,
				subplot_titles=['净值曲线', '回撤']
			)

			# 添加净值曲线
			fig = self.chart_utils.add_line_chart(
				fig, dates, equity_values,
				name='策略净值',
				row=1, col=1,
				color=self.colors['primary']
			)

			if benchmark_values is not None:
				fig = self.chart_utils.add_line_chart(
					fig, dates, benchmark_values,
					name=benchmark_name,
					row=1, col=1,
					color=self.colors['secondary']
				)

			# 计算并添加回撤
			drawdowns = self._calculate_drawdowns(equity_values)
			fig = self.chart_utils.add_line_chart(
				fig, dates, drawdowns,
				name='回撤',
				row=2, col=1,
				color=self.colors['danger'],
				line_width=1
			)

			# 添加水平线
			fig.add_hline(y=0, line_dash="dash", line_color=self.colors['grid'], row=2, col=1)

		else:
			# 只显示净值曲线
			fig = self.chart_utils.create_figure(
				title=title,
				xaxis_title='日期',
				yaxis_title='净值',
				theme=self.theme,
				template=self.template
			)

			# 添加净值曲线
			fig = self.chart_utils.add_line_chart(
				fig, dates, equity_values,
				name='策略净值',
				color=self.colors['primary']
			)

			if benchmark_values is not None:
				fig = self.chart_utils.add_line_chart(
					fig, dates, benchmark_values,
					name=benchmark_name,
					color=self.colors['secondary']
				)

		# 更新布局
		fig.update_layout(
			hovermode='x unified',
			legend={'orientation': 'h', 'y': -0.2}
		)

		return fig

	def generate_returns_distribution (self,
	                                   returns: List[float],
	                                   title: str = '收益率分布',
	                                   bins: int = 50) -> go.Figure:
		"""
		生成收益率分布图

		Args:
			returns: 收益率序列
			title: 图表标题
			bins: 分箱数量

		Returns:
			go.Figure: 收益率分布图
		"""
		returns = np.array(returns)

		# 创建图表
		fig = self.chart_utils.create_figure(
			title=title,
			xaxis_title='收益率',
			yaxis_title='频率',
			theme=self.theme,
			template=self.template
		)

		# 添加直方图
		fig = self.chart_utils.add_histogram(
			fig, returns,
			name='收益率分布',
			color=self.colors['primary'],
			nbins=bins
		)

		# 计算统计指标
		mean_return = np.mean(returns)
		std_return = np.std(returns)

		# 添加正态分布曲线
		x_norm = np.linspace(returns.min(), returns.max(), 1000)
		y_norm = (1 / (std_return * np.sqrt(2 * np.pi))) * np.exp(-0.5 * ((x_norm - mean_return) / std_return) ** 2)
		y_norm = y_norm * len(returns) * (returns.max() - returns.min()) / bins

		fig = self.chart_utils.add_line_chart(
			fig, x_norm, y_norm,
			name='正态分布',
			color=self.colors['secondary']
		)

		# 添加均值和标准差线
		fig.add_vline(x=mean_return, line_dash="dash",
		              line_color=self.colors['success'],
		              annotation_text=f"均值: {mean_return:.2%}")

		fig.add_vline(x=mean_return + std_return, line_dash="dot",
		              line_color=self.colors['warning'],
		              annotation_text=f"+1σ")

		fig.add_vline(x=mean_return - std_return, line_dash="dot",
		              line_color=self.colors['warning'],
		              annotation_text=f"-1σ")

		return fig

	def generate_risk_metrics_chart (self,
	                                 risk_metrics: Dict[str, float],
	                                 title: str = '风险指标') -> go.Figure:
		"""
		生成风险指标雷达图

		Args:
			risk_metrics: 风险指标字典
			title: 图表标题

		Returns:
			go.Figure: 风险指标雷达图
		"""
		# 提取指标和值
		categories = list(risk_metrics.keys())
		values = list(risk_metrics.values())

		# 标准化值到0-1 范围
		max_value = max(values)
		normalized_values = [v / max_value for v in values] if max_value > 0 else values

		# 创建雷达图
		fig = go.Figure()

		fig.add_trace(go.Scatterpolar(
			r=normalized_values,
			theta=categories,
			fill='toself',
			name='风险指标',
			line_color=self.colors['primary'],
			fillcolor=f'{self.colors["primary"]}80'  # 添加透明度
		))

		# 更新布局
		fig.update_layout(
			title={
				'text': title,
				'x': 0.5,
				'xanchor': 'center'
			},
			polar={
				'radialaxis': {
					'visible': True,
					'range': [0, 1],
					'tickfont': {'size': 10}
				},
				'angularaxis': {
					'tickfont': {'size': 11},
					'direction': 'clockwise'
				}
			},
			showlegend=False,
			template=self.template,
			width=600,
			height=500
		)

		return fig

	def generate_monthly_returns_heatmap (self,
	                                      returns_df: pd.DataFrame,
	                                      title: str = '月度收益率热图') -> go.Figure:
		"""
		生成月度收益率热图

		Args:
			returns_df: 收益率DataFrame，索引为年份，列为月份
			title: 图表标题

		Returns:
			go.Figure: 月度收益率热图
		"""
		# 创建热图
		fig = self.chart_utils.create_figure(
			title=title,
			theme=self.theme,
			template=self.template
		)

		fig = self.chart_utils.add_heatmap(
			fig, returns_df,
			title=title
		)

		# 更新布局
		fig.update_layout(
			xaxis_title='月份',
			yaxis_title='年份'
		)

		return fig

	def generate_trade_analysis_chart (self,
	                                   trades: List[Dict[str, Any]],
	                                   title: str = '交易分析') -> go.Figure:
		"""
		生成交易分析图

		Args:
			trades: 交易记录列表
			title: 图表标题

		Returns:
			go.Figure: 交易分析图
		"""
		if not trades:
			return self.chart_utils.create_figure(title="无交易数据")

		# 提取交易数据
		trade_dates = [trade.get('trade_time') for trade in trades]
		profits = [trade.get('profit', 0) for trade in trades]
		cumulative_profit = np.cumsum(profits)

		# 创建子图
		fig = make_subplots(
			rows=2, cols=2,
			subplot_titles=[
				'累计盈亏', '单笔盈亏分布',
				'盈亏时间序列', '交易统计'
			],
			vertical_spacing=0.15,
			horizontal_spacing=0.15
		)

		# 1. 累计盈亏
		fig.add_trace(
			go.Scatter(
				x=trade_dates,
				y=cumulative_profit,
				mode='lines',
				name='累计盈亏',
				line={'color': self.colors['primary'], 'width': 2}
			),
			row=1, col=1
		)

		# 2. 单笔盈亏分布
		fig.add_trace(
			go.Histogram(
				x=profits,
				name='盈亏分布',
				marker=dict(color=self.colors['secondary']),
				nbinsx=50
			),
			row=1, col=2
		)

		# 添加均值线
		mean_profit = np.mean(profits)
		fig.add_vline(x=mean_profit, line_dash="dash",
		              line_color=self.colors['success'],
		              row=1, col=2)

		# 3. 盈亏时间序列
		fig.add_trace(
			go.Scatter(
				x=trade_dates,
				y=profits,
				mode='markers',
				name='单笔盈亏',
				marker={
					'color': profits,
					'colorscale': 'RdYlGn',
					'size': 8,
					'showscale': True,
					'colorbar': {'title': '盈亏'}
				}
			),
			row=2, col=1
		)

		# 4. 交易统计（柱状图）
		winning_trades = [p for p in profits if p > 0]
		losing_trades = [p for p in profits if p < 0]

		stats_data = {
			'指标': ['胜率', '平均盈利', '平均亏损', '盈利因子'],
			'值': [
				len(winning_trades) / len(trades) if trades else 0,
				np.mean(winning_trades) if winning_trades else 0,
				abs(np.mean(losing_trades)) if losing_trades else 0,
				sum(winning_trades) / abs(sum(losing_trades)) if losing_trades else float('inf')
			]
		}

		fig.add_trace(
			go.Bar(
				x=stats_data['指标'],
				y=stats_data['值'],
				name='交易统计',
				marker=dict(color=self.colors['info'])
			),
			row=2, col=2
		)

		# 更新布局
		fig.update_layout(
			title={
				'text': title,
				'x': 0.5,
				'xanchor': 'center',
				'font': {'size': 20}
			},
			template=self.template,
			width=1200,
			height=800,
			showlegend=True
		)

		# 更新坐标轴标签
		fig.update_xaxes(title_text="日期", row=1, col=1)
		fig.update_yaxes(title_text="累计盈亏", row=1, col=1)

		fig.update_xaxes(title_text="盈亏", row=1, col=2)
		fig.update_yaxes(title_text="频数", row=1, col=2)

		fig.update_xaxes(title_text="日期", row=2, col=1)
		fig.update_yaxes(title_text="单笔盈亏", row=2, col=1)

		fig.update_xaxes(title_text="指标", row=2, col=2)
		fig.update_yaxes(title_text="值", row=2, col=2)

		return fig

	def generate_correlation_matrix (self,
	                                 data: pd.DataFrame,
	                                 title: str = '相关性矩阵') -> go.Figure:
		"""
		生成相关性矩阵热图

		Args:
			data: 数据DataFrame，每列代表一个资产
			title: 图表标题

		Returns:
			go.Figure: 相关性矩阵热图
		"""
		# 计算相关性矩阵
		corr_matrix = data.corr()

		# 创建热图
		fig = go.Figure(data=go.Heatmap(
			z=corr_matrix.values,
			x=corr_matrix.columns,
			y=corr_matrix.index,
			colorscale='RdBu',
			zmin=-1,
			zmax=1,
			colorbar={'title': '相关系数'},
			text=corr_matrix.round(2).values,
			texttemplate='%{text}',
			textfont={'size': 10}
		))

		# 更新布局
		fig.update_layout(
			title={
				'text': title,
				'x': 0.5,
				'xanchor': 'center'
			},
			template=self.template,
			width=800,
			height=600,
			xaxis={'tickangle': 45},
			yaxis={'autorange': 'reversed'}
		)

		return fig

	def generate_performance_comparison (self,
	                                     strategies: Dict[str, Dict[str, Any]],
	                                     title: str = '策略绩效比较') -> go.Figure:
		"""
		生成策略绩效比较图

		Args:
			strategies: 策略字典，key为策略名，value为策略数据
			title: 图表标题

		Returns:
			go.Figure: 策略绩效比较图
		"""
		# 提取策略名称和绩效指标
		strategy_names = list(strategies.keys())

		# 创建子图
		fig = make_subplots(
			rows=2, cols=2,
			subplot_titles=[
				'累计收益率', '年化收益率',
				'最大回撤', '夏普比率'
			],
			vertical_spacing=0.15,
			horizontal_spacing=0.15
		)

		colors = ChartStyle.generate_color_scale(len(strategy_names), self.theme)

		# 1. 累计收益率
		for idx, (name, data) in enumerate(strategies.items()):
			if 'equity_curve' in data:
				dates = data['equity_curve']['dates']
				values = data['equity_curve']['values']

				fig.add_trace(
					go.Scatter(
						x=dates,
						y=values,
						mode='lines',
						name=name,
						line={'color': colors[idx], 'width': 2}
					),
					row=1, col=1
				)

		# 2. 年化收益率柱状图
		annual_returns = [data.get('annual_return', 0) for data in strategies.values()]
		fig.add_trace(
			go.Bar(
				x=strategy_names,
				y=annual_returns,
				name='年化收益率',
				marker=dict(color=colors),
				text=[f'{r:.2%}' for r in annual_returns],
				textposition='auto'
			),
			row=1, col=2
		)

		# 3. 最大回撤柱状图
		max_drawdowns = [data.get('max_drawdown', 0) for data in strategies.values()]
		fig.add_trace(
			go.Bar(
				x=strategy_names,
				y=max_drawdowns,
				name='最大回撤',
				marker=dict(color=colors),
				text=[f'{d:.2%}' for d in max_drawdowns],
				textposition='auto'
			),
			row=2, col=1
		)

		# 4. 夏普比率柱状图
		sharpe_ratios = [data.get('sharpe_ratio', 0) for data in strategies.values()]
		fig.add_trace(
			go.Bar(
				x=strategy_names,
				y=sharpe_ratios,
				name='夏普比率',
				marker=dict(color=colors),
				text=[f'{s:.2f}' for s in sharpe_ratios],
				textposition='auto'
			),
			row=2, col=2
		)

		# 更新布局
		fig.update_layout(
			title={
				'text': title,
				'x': 0.5,
				'xanchor': 'center',
				'font': {'size': 20}
			},
			template=self.template,
			width=1200,
			height=800,
			showlegend=True,
			legend={'orientation': 'h', 'y': -0.1}
		)

		# 更新坐标轴标签
		fig.update_xaxes(title_text="日期", row=1, col=1)
		fig.update_yaxes(title_text="净值", row=1, col=1)

		fig.update_xaxes(title_text="策略", row=1, col=2)
		fig.update_yaxes(title_text="年化收益率", row=1, col=2)

		fig.update_xaxes(title_text="策略", row=2, col=1)
		fig.update_yaxes(title_text="最大回撤", row=2, col=1)

		fig.update_xaxes(title_text="策略", row=2, col=2)
		fig.update_yaxes(title_text="夏普比率", row=2, col=2)

		return fig

	def _calculate_drawdowns (self, equity_values: List[float]) -> List[float]:
		"""
		计算回撤序列

		Args:
			equity_values: 净值序列

		Returns:
			List[float]: 回撤序列
		"""
		if len(equity_values) < 2:
			return [0.0]

		equity_array = np.array(equity_values)
		peak = np.maximum.accumulate(equity_array)
		drawdown = (peak - equity_array) / peak

		return drawdown.tolist()

	def generate_performance_summary (self,
	                                  metrics: Dict[str, Any],
	                                  title: str = '绩效总结') -> go.Figure:
		"""
		生成绩效总结仪表盘

		Args:
			metrics: 绩效指标字典
			title: 图表标题

		Returns:
			go.Figure: 绩效总结仪表盘
		"""
		# 创建仪表盘
		fig = self.chart_utils.create_performance_dashboard(metrics, self.theme)

		# 这里可以根据具体的metrics数据填充各个子图
		# 由于metrics结构未知，这里留空由调用者具体实现

		return fig

	def generate_equity_curve_chart (self, chart_data: dict) -> "go.Figure":
		"""生成净值曲线图（适配器）"""
		dates = chart_data.get("dates", [])
		equity = chart_data.get("equity", [])
		return self.generate_equity_curve(dates, equity, show_drawdown=True)

	def generate_drawdown_chart (self, chart_data: dict) -> "go.Figure":
		"""生成回撤曲线图"""
		import plotly.graph_objects as go
		dates = chart_data.get("dates", [])
		drawdown = chart_data.get("drawdown", [])
		fig = go.Figure()
		fig.add_trace(go.Scatter(
			x=dates, y=drawdown,
			fill="tozeroy",
			name="回撤",
			line={"color": self.colors["danger"], "width": 1},
			fillcolor=f'{self.colors["danger"]}30'
		))
		fig.add_hline(y=0, line_dash="dash", line_color=self.colors["grid"])
		fig.update_layout(
			title={"text": "回撤曲线", "x": 0.5, "xanchor": "center"},
			xaxis_title="日期",
			yaxis_title="回撤率",
			template=self.template,
			hovermode="x unified"
		)
		return fig

	def generate_performance_radar_chart (self, chart_data: dict) -> "go.Figure":
		"""生成绩效指标雷达图"""
		import plotly.graph_objects as go
		metrics = {
			"总收益率": chart_data.get("total_return", 0),
			"夏普比率": chart_data.get("sharpe_ratio", 0),
			"最大回撤": abs(chart_data.get("max_drawdown", 0)),
			"胜率": chart_data.get("win_rate", 0),
			"盈利因子": min(chart_data.get("profit_factor", 0), 5),
		}
		categories = list(metrics.keys())
		values = list(metrics.values())
		max_val = max(values) if values and max(values) > 0 else 1
		normalized = [v / max_val for v in values] if max_val > 0 else values
		fig = go.Figure()
		fig.add_trace(go.Scatterpolar(
			r=normalized,
			theta=categories,
			fill="toself",
			name="绩效指标",
			line_color=self.colors["primary"],
			fillcolor=f'{self.colors["primary"]}50'
		))
		fig.update_layout(
			title={"text": "绩效指标雷达图", "x": 0.5, "xanchor": "center"},
			polar={"radialaxis": {"visible": True, "range": [0, 1]}},
			template=self.template,
			width=600, height=500,
			showlegend=False
		)
		return fig

	def generate_attribution_stacked_chart (self, chart_data: dict) -> "go.Figure":
		"""生成归因贡献堆叠柱状图（Brinson模型）"""
		import plotly.graph_objects as go
		categories = ["配置效应", "选择效应", "交互效应"]
		values = [
			chart_data.get("allocation_effect", 0),
			chart_data.get("selection_effect", 0),
			chart_data.get("interaction_effect", 0),
		]
		bar_colors = [self.colors["primary"], self.colors["secondary"], self.colors["info"]]
		fig = go.Figure()
		for cat, val, color in zip(categories, values, bar_colors):
			fig.add_trace(go.Bar(
				x=["归因分析"],
				y=[val],
				name=cat,
				marker=dict(color=color)
			))
		fig.update_layout(
			title={"text": "Brinson归因分析", "x": 0.5, "xanchor": "center"},
			barmode="stack",
			xaxis_title="",
			yaxis_title="收益贡献",
			template=self.template,
			width=600, height=500
		)
		return fig

	def generate_sector_attribution_chart (self, chart_data: dict) -> "go.Figure":
		"""生成行业归因水平条形图"""
		import plotly.graph_objects as go
		sectors = chart_data.get("sectors", [])
		contributions = chart_data.get("contributions", [])
		if sectors and contributions:
			pairs = sorted(zip(contributions, sectors), key=lambda x: x[0])
			sorted_vals, sorted_sectors = zip(*pairs)
		else:
			sorted_vals, sorted_sectors = [], []
		bar_colors = [
			self.colors["success"] if v >= 0 else self.colors["danger"]
			for v in sorted_vals
		]
		fig = go.Figure()
		fig.add_trace(go.Bar(
			y=list(sorted_sectors),
			x=list(sorted_vals),
			orientation="h",
			marker=dict(color=bar_colors)
		))
		fig.update_layout(
			title={"text": "行业归因分析", "x": 0.5, "xanchor": "center"},
			xaxis_title="收益贡献",
			yaxis_title="行业",
			template=self.template,
			height=max(400, len(sectors) * 30 + 100)
		)
		return fig

	def generate_comparison_bar_chart (self, chart_data: dict) -> "go.Figure":
		"""生成策略收益对比柱状图"""
		import plotly.graph_objects as go
		strategies = chart_data.get("strategies", [])
		returns = chart_data.get("returns", [])
		bar_colors = [
			self.colors["success"] if r >= 0 else self.colors["danger"]
			for r in returns
		]
		fig = go.Figure()
		fig.add_trace(go.Bar(
			x=strategies,
			y=returns,
			marker=dict(color=bar_colors),
			text=[f"{r:.2%}" for r in returns],
			textposition="auto"
		))
		fig.update_layout(
			title={"text": "策略收益对比", "x": 0.5, "xanchor": "center"},
			xaxis_title="策略",
			yaxis_title="收益率",
			template=self.template,
			width=800, height=500
		)
		return fig

	def generate_correlation_heatmap (self, chart_data: dict) -> "go.Figure":
		"""生成相关性热力图"""
		import plotly.graph_objects as go
		corr_matrix = chart_data.get("correlation_matrix", {})
		if isinstance(corr_matrix, dict):
			labels = list(corr_matrix.keys())
			if labels and isinstance(corr_matrix[labels[0]], dict):
				values = [[corr_matrix[i].get(j, 0) for j in labels] for i in labels]
			else:
				values = [list(corr_matrix.values())]
				labels = [labels, [""]]
		else:
			values = corr_matrix
			labels = [f"S{i + 1}" for i in range(len(values))] if values else []
		fig = go.Figure(data=go.Heatmap(
			z=values,
			x=labels,
			y=labels,
			colorscale="RdBu",
			zmin=-1, zmax=1,
			colorbar={"title": "相关系数"}
		))
		fig.update_layout(
			title={"text": "相关性热力图", "x": 0.5, "xanchor": "center"},
			template=self.template,
			width=700, height=600
		)
		return fig

	def generate_trade_distribution_chart (self, chart_data: dict) -> "go.Figure":
		"""生成交易盈亏分布图（环形图）"""
		import plotly.graph_objects as go
		labels = ["盈利交易", "亏损交易", "持平交易"]
		values = [
			chart_data.get("winning_trades", 0),
			chart_data.get("losing_trades", 0),
			chart_data.get("breakeven_trades", 0),
		]
		pie_colors = [self.colors["success"], self.colors["danger"], self.colors["warning"]]
		fig = go.Figure(data=go.Pie(
			labels=labels,
			values=values,
			hole=0.5,
			marker=dict(colors=pie_colors),
			textinfo="label+percent"
		))
		fig.update_layout(
			title={"text": "交易盈亏分布", "x": 0.5, "xanchor": "center"},
			template=self.template,
			width=600, height=500
		)
		return fig

	def generate_trading_day_distribution_chart (self, chart_data: dict) -> "go.Figure":
		"""生成交易日分布图"""
		import plotly.graph_objects as go
		days = chart_data.get("days", [])
		counts = chart_data.get("counts", [])
		fig = go.Figure(data=go.Bar(
			x=days, y=counts,
			marker=dict(color=self.colors["primary"]),
			text=counts,
			textposition="auto"
		))
		fig.update_layout(
			title={"text": "交易日分布", "x": 0.5, "xanchor": "center"},
			xaxis_title="星期",
			yaxis_title="交易次数",
			template=self.template,
			width=700, height=500
		)
		return fig
