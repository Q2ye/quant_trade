# -*- coding: utf-8 -*-
"""
图表工具模块
提供图表生成相关的工具函数和样式配置
位置：quant_server/modules/events/utils/chart_utils.py
"""

import plotly.graph_objects as go
import plotly.express as px
from plotly.subplots import make_subplots
import pandas as pd
import numpy as np
from typing import List, Dict, Any, Optional, Tuple, Union
import colorsys
from datetime import datetime, timedelta


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
			increasing_line_color=colors['success'],
			decreasing_line_color=colors['danger']
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
			marker_color=color,
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
			marker_color=color,
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
	def create_performance_dashboard (metrics: Dict[str, Any],
	                                  theme: str = 'quant') -> go.Figure:
		"""
		创建绩效仪表盘

		Args:
			metrics: 绩效指标字典
			theme: 颜色主题

		Returns:
			go.Figure: 仪表盘图表
		"""
		colors = ChartStyle.get_theme(theme)

		# 创建子图
		fig = make_subplots(
			rows=2, cols=3,
			subplot_titles=[
				'累计收益率', '年化收益率分布',
				'最大回撤', '月度收益率热图',
				'风险指标', '交易统计'
			],
			specs=[
				[{'type': 'xy'}, {'type': 'xy'}, {'type': 'xy'}],
				[{'type': 'xy'}, {'type': 'heatmap'}, {'type': 'bar'}]
			],
			vertical_spacing=0.12,
			horizontal_spacing=0.1
		)

		# 更新整体布局
		fig.update_layout(
			title={
				'text': '策略绩效仪表盘',
				'x': 0.5,
				'xanchor': 'center',
				'font': {'size': 24}
			},
			template=ChartStyle.get_template(),
			width=1600,
			height=1000,
			plot_bgcolor=colors['background'],
			paper_bgcolor=colors['background'],
			font={'color': colors['text']},
			showlegend=True
		)

		return fig