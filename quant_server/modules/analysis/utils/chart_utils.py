# -*- coding: utf-8 -*-
"""
图表工具模块
提供图表生成相关的工具函数和样式配置
位置：quant_server/modules/analysis/utils/chart_utils.py
"""

import colorsys
from typing import List, Dict, Any, Union

import numpy as np
import pandas as pd
import plotly.graph_objects as go
from plotly.subplots import make_subplots


class ChartStyle:
	"""图表样式配置类"""

	# 颜色主题
	COLOR_THEMES = {
		'quant': {
			'primary': '#1f77b4',
			'secondary': '#ff7f0e',
			'success': '#2ca02c',
			'danger': '#d62728',
			'warning': '#ffbb78',
			'info': '#98df8a',
			'background': '#ffffff',
			'grid': '#e6e6e6',
			'text': '#333333'
		},
		'dark': {
			'primary': '#636efa',
			'secondary': '#ef553b',
			'success': '#00cc96',
			'danger': '#ab63fa',
			'warning': '#ffa15a',
			'info': '#19d3f3',
			'background': '#1e1e1e',
			'grid': '#424242',
			'text': '#ffffff'
		},
		'light': {
			'primary': '#3366cc',
			'secondary': '#dc3912',
			'success': '#109618',
			'danger': '#ff9900',
			'warning': '#990099',
			'info': '#0099c6',
			'background': '#f9f9f9',
			'grid': '#dddddd',
			'text': '#000000'
		}
	}

	# 图表模板
	TEMPLATES = {
		'plotly': 'plotly',
		'plotly_white': 'plotly_white',
		'plotly_dark': 'plotly_dark',
		'ggplot2': 'ggplot2',
		'seaborn': 'seaborn',
		'simple_white': 'simple_white'
	}

	@classmethod
	def get_theme (cls, theme_name: str = 'quant') -> Dict[str, str]:
		"""
		获取颜色主题

		Args:
			theme_name: 主题名称

		Returns:
			Dict[str, str]: 颜色主题字典
		"""
		return cls.COLOR_THEMES.get(theme_name, cls.COLOR_THEMES['quant'])

	@classmethod
	def generate_color_scale (cls, n_colors: int, theme: str = 'quant') -> List[str]:
		"""
		生成颜色序列

		Args:
			n_colors: 颜色数量
			theme: 主题名称

		Returns:
			List[str]: 颜色序列
		"""
		if theme in cls.COLOR_THEMES:
			base_color = cls.COLOR_THEMES[theme]['primary']
		else:
			base_color = cls.COLOR_THEMES['quant']['primary']

		# 将hex颜色转换为hsv
		hex_color = base_color.lstrip('#')
		r, g, b = tuple(int(hex_color[i:i + 2], 16) for i in (0, 2, 4))
		h, s, v = colorsys.rgb_to_hsv(r / 255, g / 255, b / 255)

		colors = []
		for i in range(n_colors):
			# 调整色调生成不同颜色
			hue = (h + i * 0.618) % 1.0  # 使用黄金比例
			rgb = colorsys.hsv_to_rgb(hue, s, v)
			hex_color = '#{:02x}{:02x}{:02x}'.format(
				int(rgb[0] * 255), int(rgb[1] * 255), int(rgb[2] * 255)
			)
			colors.append(hex_color)

		return colors

	@classmethod
	def get_template (cls, template_name: str = 'plotly_white') -> str:
		"""
		获取图表模板

		Args:
			template_name: 模板名称

		Returns:
			str: 模板名称
		"""
		return cls.TEMPLATES.get(template_name, 'plotly_white')


class ChartUtils:
	"""图表工具类"""

	@staticmethod
	def create_figure (title: str = '',
	                   xaxis_title: str = '',
	                   yaxis_title: str = '',
	                   theme: str = 'quant',
	                   template: str = 'plotly_white',
	                   width: int = 1200,
	                   height: int = 600,
	                   subplot_titles: List[str] = None) -> go.Figure:
		"""
		创建图表基础框架

		Args:
			title: 图表标题
			xaxis_title: X轴标题
			yaxis_title: Y轴标题
			theme: 颜色主题
			template: 图表模板
			width: 图表宽度
			height: 图表高度
			subplot_titles: 子图标题列表

		Returns:
			go.Figure: Plotly图表对象
		"""
		colors = ChartStyle.get_theme(theme)
		fig_template = ChartStyle.get_template(template)

		if subplot_titles:
			rows = len(subplot_titles)
			fig = make_subplots(
				rows=rows, cols=1,
				subplot_titles=subplot_titles,
				vertical_spacing=0.1
			)
		else:
			fig = go.Figure()

		# 更新布局
		fig.update_layout(
			title={
				'text': title,
				'x': 0.5,
				'xanchor': 'center',
				'font': {'size': 20}
			},
			template=fig_template,
			width=width,
			height=height,
			plot_bgcolor=colors['background'],
			paper_bgcolor=colors['background'],
			font={'color': colors['text']},
			xaxis={
				'title': xaxis_title,
				'gridcolor': colors['grid'],
				'showgrid': True
			},
			yaxis={
				'title': yaxis_title,
				'gridcolor': colors['grid'],
				'showgrid': True
			},
			legend={
				'x': 1.02,
				'y': 1,
				'xanchor': 'left',
				'yanchor': 'top'
			},
			margin={'l': 80, 'r': 80, 't': 100, 'b': 80}
		)

		return fig

	@staticmethod
	def add_line_chart (fig: go.Figure,
	                    x_data: List,
	                    y_data: List,
	                    name: str = '',
	                    row: int = 1,
	                    col: int = 1,
	                    color: str = None,
	                    theme: str = 'quant',
	                    show_legend: bool = True,
	                    line_width: int = 2) -> go.Figure:
		"""
		添加折线图

		Args:
			fig: Plotly图表对象
			x_data: X轴数据
			y_data: Y轴数据
			name: 线条名称
			row: 子图行号
			col: 子图列号
			color: 线条颜色
			theme: 颜色主题
			show_legend: 是否显示图例
			line_width: 线条宽度

		Returns:
			go.Figure: 更新后的图表对象
		"""
		if color is None:
			colors = ChartStyle.get_theme(theme)
			color = colors['primary']

		trace = go.Scatter(
			x=x_data,
			y=y_data,
			mode='lines',
			name=name,
			line={'color': color, 'width': line_width},
			showlegend=show_legend
		)

		fig.add_trace(trace, row=row, col=col)
		return fig

	@staticmethod
	def add_candlestick_chart (fig: go.Figure,
	                           dates: List,
	                           open_prices: List,
	                           high_prices: List,
	                           low_prices: List,
	                           close_prices: List,
	                           name: str = 'K线图',
	                           row: int = 1,
	                           col: int = 1,
	                           theme: str = 'quant') -> go.Figure:
		"""
		添加K线图

		Args:
			fig: Plotly图表对象
			dates: 日期序列
			open_prices: 开盘价
			high_prices: 最高价
			low_prices: 最低价
			close_prices: 收盘价
			name: 图表名称
			row: 子图行号
			col: 子图列号
			theme: 颜色主题

		Returns:
			go.Figure: 更新后的图表对象
		"""
		colors = ChartStyle.get_theme(theme)

		trace = go.Candlestick(
			x=dates,
			open=open_prices,
			high=high_prices,
			low=low_prices,
			close=close_prices,
			name=name,
			increasing=dict(line=dict(color=colors['success'])),
			decreasing=dict(line=dict(color=colors['danger']))
		)

		fig.add_trace(trace, row=row, col=col)

		# 更新X轴格式
		fig.update_xaxes(
			rangeslider_visible=False,
			row=row, col=col
		)

		return fig

	@staticmethod
	def add_bar_chart (fig: go.Figure,
	                   x_data: List,
	                   y_data: List,
	                   name: str = '',
	                   row: int = 1,
	                   col: int = 1,
	                   color: str = None,
	                   theme: str = 'quant',
	                   orientation: str = 'v') -> go.Figure:
		"""
		添加柱状图

		Args:
			fig: Plotly图表对象
			x_data: X轴数据
			y_data: Y轴数据
			name: 图表名称
			row: 子图行号
			col: 子图列号
			color: 柱状颜色
			theme: 颜色主题
			orientation: 方向 ('v'垂直, 'h'水平)

		Returns:
			go.Figure: 更新后的图表对象
		"""
		if color is None:
			colors = ChartStyle.get_theme(theme)
			color = colors['primary']

		trace = go.Bar(
			x=x_data,
			y=y_data,
			name=name,
			marker=dict(color=color),
			orientation=orientation
		)

		fig.add_trace(trace, row=row, col=col)
		return fig

	@staticmethod
	def add_histogram (fig: go.Figure,
	                   data: List,
	                   name: str = '',
	                   row: int = 1,
	                   col: int = 1,
	                   color: str = None,
	                   theme: str = 'quant',
	                   nbins: int = 50) -> go.Figure:
		"""
		添加直方图

		Args:
			fig: Plotly图表对象
			data: 数据
			name: 图表名称
			row: 子图行号
			col: 子图列号
			color: 颜色
			theme: 颜色主题
			nbins: 分箱数量

		Returns:
			go.Figure: 更新后的图表对象
		"""
		if color is None:
			colors = ChartStyle.get_theme(theme)
			color = colors['primary']

		trace = go.Histogram(
			x=data,
			name=name,
			marker=dict(color=color),
			nbinsx=nbins,
			opacity=0.7
		)

		fig.add_trace(trace, row=row, col=col)
		return fig

	@staticmethod
	def add_scatter_plot (fig: go.Figure,
	                      x_data: List,
	                      y_data: List,
	                      name: str = '',
	                      row: int = 1,
	                      col: int = 1,
	                      color: str = None,
	                      theme: str = 'quant',
	                      mode: str = 'markers',
	                      size: int = 8) -> go.Figure:
		"""
		添加散点图

		Args:
			fig: Plotly图表对象
			x_data: X轴数据
			y_data: Y轴数据
			name: 图表名称
			row: 子图行号
			col: 子图列号
			color: 颜色
			theme: 颜色主题
			mode: 模式 ('markers', 'lines+markers', 'lines')
			size: 点的大小

		Returns:
			go.Figure: 更新后的图表对象
		"""
		if color is None:
			colors = ChartStyle.get_theme(theme)
			color = colors['primary']

		trace = go.Scatter(
			x=x_data,
			y=y_data,
			mode=mode,
			name=name,
			marker={
				'color': color,
				'size': size
			}
		)

		fig.add_trace(trace, row=row, col=col)
		return fig

	@staticmethod
	def add_heatmap (fig: go.Figure,
	                 data: pd.DataFrame,
	                 title: str = '热力图',
	                 row: int = 1,
	                 col: int = 1,
	                 theme: str = 'quant') -> go.Figure:
		"""
		添加热力图

		Args:
			fig: Plotly图表对象
			data: 数据DataFrame
			title: 图表标题
			row: 子图行号
			col: 子图列号
			theme: 颜色主题

		Returns:
			go.Figure: 更新后的图表对象
		"""
		colors = ChartStyle.get_theme(theme)

		trace = go.Heatmap(
			z=data.values,
			x=data.columns.tolist(),
			y=data.index.tolist(),
			colorscale='Viridis',
			showscale=True,
			colorbar={
				'title': '值',
				'titleside': 'right'
			}
		)

		fig.add_trace(trace, row=row, col=col)

		# 更新布局
		fig.update_xaxes(title_text='', row=row, col=col)
		fig.update_yaxes(title_text='', row=row, col=col)

		return fig

	@staticmethod
	def add_annotation (fig: go.Figure,
	                    text: str,
	                    x: float,
	                    y: float,
	                    row: int = 1,
	                    col: int = 1,
	                    theme: str = 'quant',
	                    arrow: bool = False) -> go.Figure:
		"""
		添加注解

		Args:
			fig: Plotly图表对象
			text: 注解文本
			x: X坐标
			y: Y坐标
			row: 子图行号
			col: 子图列号
			theme: 颜色主题
			arrow: 是否显示箭头

		Returns:
			go.Figure: 更新后的图表对象
		"""
		colors = ChartStyle.get_theme(theme)

		annotation = {
			'x': x,
			'y': y,
			'text': text,
			'showarrow': arrow,
			'arrowhead': 2,
			'arrowsize': 1,
			'arrowwidth': 2,
			'arrowcolor': colors['text'],
			'font': {
				'size': 12,
				'color': colors['text']
			},
			'align': 'center',
			'bordercolor': colors['grid'],
			'borderwidth': 1,
			'borderpad': 4,
			'bgcolor': colors['background'],
			'opacity': 0.8
		}

		# 添加注解
		fig.add_annotation(annotation, row=row, col=col)
		return fig

	@staticmethod
	def add_shaded_area (fig: go.Figure,
	                     x_data: List,
	                     y_lower: List,
	                     y_upper: List,
	                     name: str = '',
	                     row: int = 1,
	                     col: int = 1,
	                     color: str = None,
	                     theme: str = 'quant',
	                     opacity: float = 0.3) -> go.Figure:
		"""
		添加阴影区域

		Args:
			fig: Plotly图表对象
			x_data: X轴数据
			y_lower: Y轴下界
			y_upper: Y轴上界
			name: 区域名称
			row: 子图行号
			col: 子图列号
			color: 颜色
			theme: 颜色主题
			opacity: 透明度

		Returns:
			go.Figure: 更新后的图表对象
		"""
		if color is None:
			colors = ChartStyle.get_theme(theme)
			color = colors['primary']

		# 创建阴影区域
		trace = go.Scatter(
			x=x_data + x_data[::-1],
			y=y_upper + y_lower[::-1],
			fill='toself',
			fillcolor=f'rgba{tuple(int(color.lstrip("#")[i:i + 2], 16) for i in (0, 2, 4)) + (opacity,)}',
			line={'color': 'rgba(255,255,255,0)'},
			name=name,
			showlegend=True
		)

		fig.add_trace(trace, row=row, col=col)
		return fig

	@staticmethod
	def save_figure (fig: go.Figure,
	                 filepath: str,
	                 format: str = 'html',
	                 width: int = 1200,
	                 height: int = 600) -> str:
		"""
		保存图表

		Args:
			fig: Plotly图表对象
			filepath: 文件路径
			format: 保存格式 ('html', 'png', 'pdf', 'svg')
			width: 宽度
			height: 高度

		Returns:
			str: 保存的文件路径
		"""
		if format == 'html':
			fig.write_html(filepath, include_plotlyjs='cdn')
		elif format == 'png':
			fig.write_image(filepath, width=width, height=height)
		elif format == 'pdf':
			fig.write_image(filepath, format='pdf', width=width, height=height)
		elif format == 'svg':
			fig.write_image(filepath, format='svg', width=width, height=height)
		else:
			raise ValueError(f"不支持的格式: {format}")

		return filepath

	@staticmethod
	def create_equity_curve(
			equity_curve: Union[List[float], pd.Series],
			dates: Union[List, pd.DatetimeIndex] = None,
			benchmark_equity: Union[List[float], pd.Series] = None,
			title: str = '净值曲线',
			theme: str = 'quant'
	) -> go.Figure:
		"""
		创建净值曲线图

		Args:
			equity_curve: 策略累计净值序列
			dates: 日期序列
			benchmark_equity: 基准累计净值序列
			title: 图表标题
			theme: 颜色主题

		Returns:
			go.Figure: 净值曲线图表
		"""
		colors = ChartStyle.get_theme(theme)
		eq = list(equity_curve)
		x_vals = list(dates) if dates is not None else list(range(len(eq)))

		fig = go.Figure()

		fig.add_trace(go.Scatter(
			x=x_vals, y=eq, mode='lines',
			name='策略净值',
			line={'color': colors['primary'], 'width': 2.5},
			hovertemplate='日期: %{x}<br>净值: %{y:.4f}<extra></extra>'
		))

		if benchmark_equity is not None and len(benchmark_equity) == len(eq):
			bm = list(benchmark_equity)
			fig.add_trace(go.Scatter(
				x=x_vals, y=bm, mode='lines',
				name='基准净值',
				line={'color': colors['secondary'], 'width': 1.5, 'dash': 'dash'},
				hovertemplate='日期: %{x}<br>基准: %{y:.4f}<extra></extra>'
			))

		# 基准线 y=1
		fig.add_hline(y=1.0, line_dash='dot', line_color=colors['grid'],
		              annotation_text='初始净值', annotation_position='bottom right')

		fig.update_layout(
			title={'text': title, 'x': 0.5, 'xanchor': 'center', 'font': {'size': 20}},
			template=ChartStyle.get_template(),
			width=1200, height=600,
			plot_bgcolor=colors['background'],
			paper_bgcolor=colors['background'],
			font={'color': colors['text']},
			xaxis={'title': '日期', 'gridcolor': colors['grid']},
			yaxis={'title': '净值', 'gridcolor': colors['grid']},
			legend={'x': 0.02, 'y': 0.98, 'xanchor': 'left', 'yanchor': 'top'},
			hovermode='x unified',
			margin={'l': 60, 'r': 40, 't': 80, 'b': 60}
		)

		return fig

	@staticmethod
	def create_drawdown_chart(
			drawdowns: Union[List[float], pd.Series],
			dates: Union[List, pd.DatetimeIndex] = None,
			title: str = '回撤曲线',
			theme: str = 'quant'
	) -> go.Figure:
		"""
		创建回撤曲线图

		Args:
			drawdowns: 回撤序列（正值表示回撤深度）
			dates: 日期序列
			title: 图表标题
			theme: 颜色主题

		Returns:
			go.Figure: 回撤图表
		"""
		colors = ChartStyle.get_theme(theme)
		dd = list(drawdowns)
		dd_negative = [-abs(v) for v in dd]
		x_vals = list(dates) if dates is not None else list(range(len(dd)))

		fig = go.Figure()

		fig.add_trace(go.Scatter(
			x=x_vals, y=dd_negative, mode='lines',
			fill='tozeroy',
			fillcolor=f'rgba({",".join(str(int(colors["danger"].lstrip("#")[i:i+2], 16)) for i in (0, 2, 4))}, 0.25)',
			line={'color': colors['danger'], 'width': 1.5},
			name='回撤',
			hovertemplate='日期: %{x}<br>回撤: %{y:.2%}<extra></extra>'
		))

		fig.add_hline(y=0, line_dash='solid', line_color=colors['grid'])

		fig.update_layout(
			title={'text': title, 'x': 0.5, 'xanchor': 'center', 'font': {'size': 20}},
			template=ChartStyle.get_template(),
			width=1200, height=400,
			plot_bgcolor=colors['background'],
			paper_bgcolor=colors['background'],
			font={'color': colors['text']},
			xaxis={'title': '日期', 'gridcolor': colors['grid']},
			yaxis={'title': '回撤', 'gridcolor': colors['grid'], 'tickformat': '.0%'},
			showlegend=False,
			hovermode='x unified',
			margin={'l': 60, 'r': 40, 't': 80, 'b': 60}
		)

		return fig

	@staticmethod
	def create_returns_distribution(
			returns: Union[List[float], pd.Series],
			benchmark_returns: Union[List[float], pd.Series] = None,
			title: str = '收益率分布',
			theme: str = 'quant'
	) -> go.Figure:
		"""
		创建收益率分布图（直方图 + KDE + 正态分布叠加）

		Args:
			returns: 日收益率序列
			benchmark_returns: 基准日收益率序列（可选）
			title: 图表标题
			theme: 颜色主题

		Returns:
			go.Figure: 收益率分布图表
		"""
		colors = ChartStyle.get_theme(theme)
		r = np.array(returns)

		fig = go.Figure()

		# 策略收益直方图
		fig.add_trace(go.Histogram(
			x=r, name='策略收益',
			marker=dict(color=colors['primary']),
			opacity=0.6, nbinsx=60,
			histnorm='probability density',
			hovertemplate='收益: %{x:.2%}<br>密度: %{y:.4f}<extra></extra>'
		))

		# 基准收益直方图
		if benchmark_returns is not None and len(benchmark_returns) > 0:
			bm = np.array(benchmark_returns)
			fig.add_trace(go.Histogram(
				x=bm, name='基准收益',
				marker=dict(color=colors['secondary']),
				opacity=0.4, nbinsx=60,
				histnorm='probability density',
				hovertemplate='收益: %{x:.2%}<br>密度: %{y:.4f}<extra></extra>'
			))

		# 叠加正态分布曲线
		if len(r) > 2:
			x_range = np.linspace(r.min(), r.max(), 200)
			mu, sigma = float(np.mean(r)), float(np.std(r))
			normal_pdf = (1 / (sigma * np.sqrt(2 * np.pi))) * np.exp(-0.5 * ((x_range - mu) / sigma) ** 2)

			fig.add_trace(go.Scatter(
				x=x_range, y=normal_pdf, mode='lines',
				name=f'正态分布 (μ={mu:.4f})',
				line={'color': colors['success'], 'width': 2, 'dash': 'dash'},
				hovertemplate='收益: %{x:.2%}<br>正态PDF: %{y:.4f}<extra></extra>'
			))

		# 标注均值线和0线
		mean_ret = float(np.mean(r))
		fig.add_vline(x=mean_ret, line_dash='dot', line_color=colors['text'],
		              annotation_text=f'均值: {mean_ret:.2%}')
		fig.add_vline(x=0, line_dash='solid', line_color=colors['grid'],
		              annotation_text='零线')

		fig.update_layout(
			title={'text': title, 'x': 0.5, 'xanchor': 'center', 'font': {'size': 20}},
			template=ChartStyle.get_template(),
			width=1000, height=500,
			plot_bgcolor=colors['background'],
			paper_bgcolor=colors['background'],
			font={'color': colors['text']},
			xaxis={'title': '收益率', 'gridcolor': colors['grid'], 'tickformat': '.1%'},
			yaxis={'title': '概率密度', 'gridcolor': colors['grid']},
			bargap=0.05,
			legend={'x': 0.02, 'y': 0.98, 'xanchor': 'left', 'yanchor': 'top'},
			margin={'l': 60, 'r': 40, 't': 80, 'b': 60}
		)

		return fig

	@staticmethod
	def create_performance_dashboard(
			equity_curve: Union[List[float], pd.Series],
			dates: Union[List, pd.DatetimeIndex] = None,
			returns: Union[List[float], pd.Series] = None,
			benchmark_returns: Union[List[float], pd.Series] = None,
			drawdowns: Union[List[float], pd.Series] = None,
			monthly_returns: pd.DataFrame = None,
			trade_stats: Dict[str, Any] = None,
			theme: str = 'quant'
	) -> go.Figure:
		"""
		创建策略绩效仪表盘（Bento Grid 布局）

		Args:
			equity_curve: 累计净值序列
			dates: 日期序列（与净值对应）
			returns: 日收益率序列
			benchmark_returns: 基准日收益率序列
			drawdowns: 回撤序列
			monthly_returns: 月度收益率矩阵 (index=年, columns=月)
			trade_stats: 交易统计字典
			theme: 颜色主题

		Returns:
			go.Figure: 绩效仪表盘图表
		"""
		colors = ChartStyle.get_theme(theme)

		fig = make_subplots(
			rows=3, cols=4,
			subplot_titles=[
				'累计净值', '年化收益率', '最大回撤',
				'收益分布', '月度收益热力图', '滚动夏普比率',
				'风险指标仪表盘', '交易统计', '周收益分布',
				'水下曲线', 'Beta 滚动', '回撤恢复分析'
			],
			specs=[
				[{'type': 'xy'}, {'type': 'indicator'}, {'type': 'xy'}, {'type': 'xy'}],
				[{'type': 'heatmap'}, {'type': 'xy'}, {'type': 'indicator'}, {'type': 'bar'}],
				[{'type': 'xy'}, {'type': 'xy'}, {'type': 'xy'}, {'type': 'xy'}],
			],
			vertical_spacing=0.10,
			horizontal_spacing=0.08
		)

		# --- Row 1 Col 1: 累计净值曲线 ---
		if equity_curve is not None and len(equity_curve) > 0:
			eq = list(equity_curve)
			x_vals = list(dates) if dates is not None else list(range(len(eq)))
			fig.add_trace(go.Scatter(
				x=x_vals, y=eq, mode='lines',
				name='策略净值',
				line={'color': colors['primary'], 'width': 2},
				showlegend=False
			), row=1, col=1)

			if benchmark_returns is not None and len(benchmark_returns) == len(equity_curve):
				bm_eq = (1 + np.array(benchmark_returns)).cumprod()
				fig.add_trace(go.Scatter(
					x=x_vals, y=bm_eq, mode='lines',
					name='基准净值',
					line={'color': colors['secondary'], 'width': 1.5, 'dash': 'dash'},
					showlegend=False
				), row=1, col=1)

		# --- Row 1 Col 2: 年化收益率指标 ---
		if returns is not None and len(returns) > 0:
			r = np.array(returns)
			ann_return = float(np.mean(r) * 252 * 100)
			fig.add_trace(go.Indicator(
				mode='number+gauge',
				value=ann_return,
				number={'suffix': '%', 'font': {'size': 28}},
				gauge={'axis': {'range': [-50, 100]},
				       'bar': {'color': colors['success'] if ann_return > 0 else colors['danger']}},
				title={'text': '年化收益率'},
				domain={'row': 0, 'column': 1}
			), row=1, col=2)

		# --- Row 1 Col 3: 最大回撤曲线 ---
		if drawdowns is not None and len(drawdowns) > 0:
			dd = list(drawdowns)
			x_vals = list(dates) if dates is not None else list(range(len(dd)))
			fig.add_trace(go.Scatter(
				x=x_vals, y=[-v for v in dd], mode='lines',
				fill='tozeroy',
				fillcolor=f'rgba({",".join(str(int(colors["danger"].lstrip("#")[i:i+2], 16)) for i in (0, 2, 4))}, 0.3)',
				line={'color': colors['danger'], 'width': 1},
				name='回撤',
				showlegend=False
			), row=1, col=3)

		# --- Row 1 Col 4: 日收益分布直方图 ---
		if returns is not None and len(returns) > 0:
			fig.add_trace(go.Histogram(
				x=list(returns),
				marker=dict(color=colors['primary']),
				opacity=0.7,
				nbinsx=50,
				name='日收益分布',
				showlegend=False
			), row=1, col=4)

		# --- Row 2 Col 1: 月度收益热力图 ---
		if monthly_returns is not None and not monthly_returns.empty:
			fig.add_trace(go.Heatmap(
				z=monthly_returns.values,
				x=monthly_returns.columns.tolist(),
				y=monthly_returns.index.tolist(),
				colorscale='RdYlGn',
				zsmooth=False,
				colorbar={'title': '收益率'},
				showscale=True
			), row=2, col=1)

		# --- Row 2 Col 2: 滚动夏普比率 ---
		if returns is not None and len(returns) > 60:
			r = np.array(returns)
			roll_sharpe = (pd.Series(r).rolling(60).mean() / pd.Series(r).rolling(60).std() * np.sqrt(252)).values
			x_vals = list(dates)[60:] if dates is not None else list(range(len(roll_sharpe)))
			fig.add_trace(go.Scatter(
				x=x_vals, y=roll_sharpe, mode='lines',
				line={'color': colors['info'], 'width': 1.5},
				name='滚动夏普(60日)',
				showlegend=False
			), row=2, col=2)
			fig.add_hline(y=1.0, line_dash='dash', line_color=colors['warning'],
			              annotation_text='Sharpe=1', row=2, col=2)

		# --- Row 2 Col 3: 风险指标 ---
		if returns is not None and len(returns) > 0:
			r = np.array(returns)
			vol = float(np.std(r) * np.sqrt(252) * 100)
			fig.add_trace(go.Indicator(
				mode='number+gauge',
				value=vol,
				number={'suffix': '%', 'font': {'size': 28}},
				gauge={'axis': {'range': [0, 80]},
				       'bar': {'color': colors['warning'] if vol > 25 else colors['info']}},
				title={'text': '年化波动率'},
				domain={'row': 1, 'column': 2}
			), row=2, col=3)

		# --- Row 2 Col 4: 交易统计 ---
		if trade_stats:
			labels = list(trade_stats.keys())
			values = list(trade_stats.values())
			fig.add_trace(go.Bar(
				x=labels, y=values,
				marker=dict(color=colors['primary']),
				showlegend=False
			), row=2, col=4)

		# --- Row 3 Col 1: 水下曲线 (累计回撤深度) ---
		if drawdowns is not None and len(drawdowns) > 0:
			dd = np.array(drawdowns)
			underwater = np.where(dd > 0, -dd, 0)
			x_vals = list(dates) if dates is not None else list(range(len(underwater)))
			fig.add_trace(go.Scatter(
				x=x_vals, y=underwater, mode='lines',
				fill='tozeroy',
				fillcolor=f'rgba({",".join(str(int(colors["danger"].lstrip("#")[i:i+2], 16)) for i in (0, 2, 4))}, 0.15)',
				line={'color': colors['danger'], 'width': 1},
				name='水下曲线',
				showlegend=False
			), row=3, col=1)

		# --- Row 3 Col 2: Beta 滚动 ---
		if returns is not None and benchmark_returns is not None and len(returns) > 60:
			r = np.array(returns)
			bm = np.array(benchmark_returns)
			window = 60
			roll_betas = []
			for i in range(window, len(r) + 1):
				r_win = r[i - window:i]
				bm_win = bm[i - window:i]
				cov = np.cov(r_win, bm_win)[0, 1]
				var = np.var(bm_win)
				roll_betas.append(cov / var if var > 0 else 0)
			x_vals = list(dates)[window:] if dates is not None else list(range(len(roll_betas)))
			fig.add_trace(go.Scatter(
				x=x_vals, y=roll_betas, mode='lines',
				line={'color': colors['info'], 'width': 1.5},
				name='滚动Beta(60日)',
				showlegend=False
			), row=3, col=2)
			fig.add_hline(y=1.0, line_dash='dash', line_color=colors['secondary'],
			              annotation_text='Beta=1', row=3, col=2)

		# --- Row 3 Col 3 & 4: 回撤恢复分析 ---
		if drawdowns is not None and len(drawdowns) > 0:
			dd = np.array(drawdowns)
			x_vals = list(dates) if dates is not None else list(range(len(dd)))
			fig.add_trace(go.Scatter(
				x=x_vals, y=dd, mode='lines',
				line={'color': colors['danger'], 'width': 1},
				name='回撤深度',
				showlegend=False
			), row=3, col=3)

			# 恢复天数直方图
			recovery_periods = []
			in_drawdown = False
			start_dd = 0
			for i, d in enumerate(dd.tolist()):
				if d > 0 and not in_drawdown:
					in_drawdown = True
					start_dd = i
				elif d == 0 and in_drawdown:
					in_drawdown = False
					recovery_periods.append(i - start_dd)
			if recovery_periods:
				fig.add_trace(go.Histogram(
					x=recovery_periods,
					marker=dict(color=colors['warning']),
					opacity=0.7,
					name='恢复天数',
					showlegend=False
				), row=3, col=4)

		fig.update_layout(
			title={
				'text': '策略绩效仪表盘',
				'x': 0.5, 'xanchor': 'center',
				'font': {'size': 22}
			},
			template=ChartStyle.get_template(),
			width=1800,
			height=1200,
			plot_bgcolor=colors['background'],
			paper_bgcolor=colors['background'],
			font={'color': colors['text']},
			margin={'l': 60, 'r': 60, 't': 100, 'b': 60},
			showlegend=False
		)

		return fig
