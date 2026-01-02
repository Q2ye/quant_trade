#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
报告管理器

负责分析报告的生成、存储、查询和导出。
"""

from typing import Dict, List, Optional, Any, BinaryIO
from datetime import datetime, date, timedelta
import json
import csv
import pandas as pd
from sqlalchemy.ext.asyncio import AsyncSession
import aiofiles
from pathlib import Path

from modules.analysis.models import AnalysisReport
from shared.database.repositories.base import BaseRepository
from shared.database.repositories.strategy_repo import StrategyRepository
from shared.database.repositories.account_repo import AccountRepository
from modules.analysis.visualizers.chart_generator import ChartGenerator
from modules.analysis.visualizers.report_generator import ReportGenerator


class ReportManager:
	"""报告管理器"""

	def __init__ (
			self,
			session: AsyncSession,
			report_storage_path: str = "./reports",
			strategy_repo: StrategyRepository = None,
			account_repo: AccountRepository = None
	):
		"""
		初始化报告管理器

		Args:
			session: 数据库会话
			report_storage_path: 报告存储路径
			strategy_repo: 策略Repository
			account_repo: 账户Repository
		"""
		self.session = session
		self.report_storage_path = Path(report_storage_path)

		# 创建存储目录
		self.report_storage_path.mkdir(parents=True, exist_ok=True)

		# 初始化Repository
		self.strategy_repo = strategy_repo or StrategyRepository(session)
		self.account_repo = account_repo or AccountRepository(session)

		# 初始化生成器
		self.chart_generator = ChartGenerator()
		self.report_generator = ReportGenerator()

		# 内存中的报告缓存
		self.report_cache: Dict[str, AnalysisReport] = {}

	async def generate_report (
			self,
			report_data: Dict[str, Any],
			report_type: str,
			user_id: str,
			title: str,
			description: Optional[str] = None
	) -> AnalysisReport:
		"""
		生成分析报告

		Args:
			report_data: 报告数据
			report_type: 报告类型
			user_id: 用户ID
			title: 报告标题
			description: 报告描述

		Returns:
			AnalysisReport: 分析报告对象
		"""
		try:
			# 生成报告ID
			report_id = f"report_{report_type}_{datetime.now().strftime('%Y%m%d_%H%M%S')}"

			# 创建报告对象
			report = AnalysisReport(
				report_id=report_id,
				user_id=user_id,
				report_type=report_type,
				title=title,
				description=description,
				parameters=report_data.get('parameters', {}),
				status='generating',
				progress=0.0
			)

			# 根据报告类型处理数据
			if report_type == 'performance':
				# 绩效报告
				await self._add_performance_charts(report, report_data)

			elif report_type == 'attribution':
				# 归因报告
				await self._add_attribution_charts(report, report_data)

			elif report_type == 'comparison':
				# 对比报告
				await self._add_comparison_charts(report, report_data)

			elif report_type == 'trade_analysis':
				# 交易分析报告
				await self._add_trade_analysis_charts(report, report_data)

			elif report_type == 'comprehensive':
				# 综合分析报告
				await self._add_comprehensive_charts(report, report_data)

			# 更新报告状态
			report.status = 'completed'
			report.progress = 100.0
			report.completed_at = datetime.now()

			# 缓存报告
			self.report_cache[report_id] = report

			# 保存报告到文件
			await self._save_report_to_file(report)

			return report

		except Exception as e:
			raise ValueError(f"生成报告失败: {str(e)}")

	async def get_report (self, report_id: str) -> Optional[AnalysisReport]:
		"""
		获取报告

		Args:
			report_id: 报告ID

		Returns:
			AnalysisReport: 分析报告对象，如果不存在则返回None
		"""
		# 首先检查缓存
		if report_id in self.report_cache:
			return self.report_cache[report_id]

		# 从文件加载
		report = await self._load_report_from_file(report_id)

		if report:
			# 添加到缓存
			self.report_cache[report_id] = report

		return report

	async def list_reports (
			self,
			user_id: Optional[str] = None,
			report_type: Optional[str] = None,
			start_date: Optional[date] = None,
			end_date: Optional[date] = None,
			limit: int = 100,
			offset: int = 0
	) -> List[AnalysisReport]:
		"""
		列出报告

		Args:
			user_id: 用户ID（可选）
			report_type: 报告类型（可选）
			start_date: 开始日期（可选）
			end_date: 结束日期（可选）
			limit: 返回数量限制
			offset: 偏移量

		Returns:
			报告列表
		"""
		try:
			# 获取报告文件列表
			report_files = list(self.report_storage_path.glob("*.json"))

			reports = []

			for file_path in report_files[offset:offset + limit]:
				try:
					# 从文件加载报告
					async with aiofiles.open(file_path, 'r', encoding='utf-8') as f:
						content = await f.read()
						report_data = json.loads(content)

					# 创建报告对象
					report = AnalysisReport(
						report_id=report_data['report_id'],
						user_id=report_data['user_id'],
						report_type=report_data['report_type'],
						title=report_data['title'],
						description=report_data.get('description'),
						parameters=report_data.get('parameters', {}),
						status=report_data['status'],
						progress=report_data['progress'],
						created_at=datetime.fromisoformat(report_data['created_at'])
					)

					# 设置完成时间
					if report_data.get('completed_at'):
						report.completed_at = datetime.fromisoformat(report_data['completed_at'])

					# 应用筛选条件
					if user_id and report.user_id != user_id:
						continue

					if report_type and report.report_type != report_type:
						continue

					if start_date and report.created_at.date() < start_date:
						continue

					if end_date and report.created_at.date() > end_date:
						continue

					reports.append(report)

				except Exception as e:
					print(f"加载报告文件失败 {file_path}: {str(e)}")
					continue

			return reports

		except Exception as e:
			raise ValueError(f"列出报告失败: {str(e)}")

	async def export_report (
			self,
			report_id: str,
			export_format: str = 'json'
	) -> bytes:
		"""
		导出报告

		Args:
			report_id: 报告ID
			export_format: 导出格式 ('json', 'csv', 'pdf', 'html')

		Returns:
			报告数据字节
		"""
		try:
			# 获取报告
			report = await self.get_report(report_id)

			if not report:
				raise ValueError(f"报告不存在: {report_id}")

			# 根据格式导出
			if export_format == 'json':
				return await self._export_json(report)
			elif export_format == 'csv':
				return await self._export_csv(report)
			elif export_format == 'pdf':
				return await self._export_pdf(report)
			elif export_format == 'html':
				return await self._export_html(report)
			else:
				raise ValueError(f"不支持的导出格式: {export_format}")

		except Exception as e:
			raise ValueError(f"导出报告失败: {str(e)}")

	async def delete_report (self, report_id: str) -> bool:
		"""
		删除报告

		Args:
			report_id: 报告ID

		Returns:
			是否删除成功
		"""
		try:
			# 从缓存中删除
			if report_id in self.report_cache:
				del self.report_cache[report_id]

			# 删除文件
			report_file = self.report_storage_path / f"{report_id}.json"

			if report_file.exists():
				report_file.unlink()
				return True

			return False

		except Exception as e:
			raise ValueError(f"删除报告失败: {str(e)}")

	async def cleanup_old_reports (
			self,
			days_to_keep: int = 30
	) -> int:
		"""
		清理旧报告

		Args:
			days_to_keep: 保留天数

		Returns:
			清理的报告数量
		"""
		try:
			cutoff_date = datetime.now() - timedelta(days=days_to_keep)

			deleted_count = 0

			# 遍历报告文件
			for file_path in self.report_storage_path.glob("*.json"):
				# 检查文件修改时间
				stat = file_path.stat()
				file_date = datetime.fromtimestamp(stat.st_mtime)

				if file_date < cutoff_date:
					# 删除旧报告
					file_path.unlink()
					deleted_count += 1

			return deleted_count

		except Exception as e:
			raise ValueError(f"清理旧报告失败: {str(e)}")

	async def _add_performance_charts (
			self,
			report: AnalysisReport,
			report_data: Dict[str, Any]
	):
		"""
		为绩效报告添加图表

		Args:
			report: 报告对象
			report_data: 报告数据
		"""
		try:
			charts = []

			# 净值曲线图
			if 'performance_metrics' in report_data:
				metrics = report_data['performance_metrics']

				if 'equity_curve' in metrics:
					equity_data = metrics['equity_curve']

					if equity_data:
						# 生成净值曲线图
						chart_data = {
							'dates': [item['date'] for item in equity_data],
							'equity': [item['equity'] for item in equity_data]
						}

						chart = self.chart_generator.generate_equity_curve_chart(chart_data)
						charts.append(chart)

			# 回撤曲线图
			if 'performance_metrics' in report_data:
				metrics = report_data['performance_metrics']

				if 'drawdown_curve' in metrics:
					drawdown_data = metrics['drawdown_curve']

					if drawdown_data:
						# 生成回撤曲线图
						chart_data = {
							'dates': [item['date'] for item in drawdown_data],
							'drawdown': [item['drawdown'] for item in drawdown_data]
						}

						chart = self.chart_generator.generate_drawdown_chart(chart_data)
						charts.append(chart)

			# 月度收益热力图
			if 'performance_metrics' in report_data:
				metrics = report_data['performance_metrics']

				if 'monthly_returns' in metrics:
					monthly_returns = metrics['monthly_returns']

					if monthly_returns:
						# 生成月度收益热力图
						chart_data = {
							'monthly_returns': monthly_returns
						}

						chart = self.chart_generator.generate_monthly_returns_heatmap(chart_data)
						charts.append(chart)

			# 绩效指标雷达图
			if 'performance_metrics' in report_data:
				metrics = report_data['performance_metrics']

				# 生成雷达图
				chart_data = {
					'total_return': float(metrics.get('total_return', 0)),
					'sharpe_ratio': float(metrics.get('sharpe_ratio', 0)),
					'max_drawdown': float(metrics.get('max_drawdown', 0)),
					'win_rate': float(metrics.get('win_rate', 0)),
					'profit_factor': float(metrics.get('profit_factor', 0))
				}

				chart = self.chart_generator.generate_performance_radar_chart(chart_data)
				charts.append(chart)

			# 添加到报告
			report.charts = charts

		except Exception as e:
			print(f"添加绩效图表失败: {str(e)}")

	async def _add_attribution_charts (
			self,
			report: AnalysisReport,
			report_data: Dict[str, Any]
	):
		"""
		为归因报告添加图表

		Args:
			report: 报告对象
			report_data: 报告数据
		"""
		try:
			charts = []

			# 归因贡献堆叠图
			if 'attribution_analysis' in report_data:
				attribution = report_data['attribution_analysis']

				if 'brinson_attribution' in attribution:
					brinson_data = attribution['brinson_attribution']

					# 生成归因贡献堆叠图
					chart_data = {
						'allocation_effect': float(brinson_data.get('allocation_effect', 0)),
						'selection_effect': float(brinson_data.get('selection_effect', 0)),
						'interaction_effect': float(brinson_data.get('interaction_effect', 0))
					}

					chart = self.chart_generator.generate_attribution_stacked_chart(chart_data)
					charts.append(chart)

			# 行业归因条形图
			if 'attribution_analysis' in report_data:
				attribution = report_data['attribution_analysis']

				if 'sector_attribution' in attribution:
					sector_data = attribution['sector_attribution']

					if 'attributions' in sector_data:
						# 生成行业归因条形图
						chart_data = {
							'sectors': list(sector_data['attributions'].keys()),
							'contributions': list(sector_data['attributions'].values())
						}

						chart = self.chart_generator.generate_sector_attribution_chart(chart_data)
						charts.append(chart)

			# 添加到报告
			report.charts = charts

		except Exception as e:
			print(f"添加归因图表失败: {str(e)}")

	async def _add_comparison_charts (
			self,
			report: AnalysisReport,
			report_data: Dict[str, Any]
	):
		"""
		为对比报告添加图表

		Args:
			report: 报告对象
			report_data: 报告数据
		"""
		try:
			charts = []

			# 策略对比条形图
			if 'comparison_analysis' in report_data:
				comparison = report_data['comparison_analysis']

				if 'performance_comparison' in comparison:
					perf_comparison = comparison['performance_comparison']

					# 生成总收益对比条形图
					chart_data = {
						'strategies': list(perf_comparison.keys()),
						'returns': [
							perf['returns']['total_return']
							for perf in perf_comparison.values()
						]
					}

					chart = self.chart_generator.generate_comparison_bar_chart(chart_data)
					charts.append(chart)

			# 相关性热力图
			if 'comparison_analysis' in report_data:
				comparison = report_data['comparison_analysis']

				if 'correlations' in comparison:
					correlations = comparison['correlations']

					if correlations:
						# 生成相关性热力图
						chart_data = {
							'correlation_matrix': correlations
						}

						chart = self.chart_generator.generate_correlation_heatmap(chart_data)
						charts.append(chart)

			# 添加到报告
			report.charts = charts

		except Exception as e:
			print(f"添加对比图表失败: {str(e)}")

	async def _add_trade_analysis_charts (
			self,
			report: AnalysisReport,
			report_data: Dict[str, Any]
	):
		"""
		为交易分析报告添加图表

		Args:
			report: 报告对象
			report_data: 报告数据
		"""
		try:
			charts = []

			# 交易盈亏分布图
			if 'trade_analysis' in report_data:
				trade_analysis = report_data['trade_analysis']

				# 生成交易盈亏分布图
				chart_data = {
					'winning_trades': trade_analysis.get('winning_trades', 0),
					'losing_trades': trade_analysis.get('losing_trades', 0),
					'breakeven_trades': trade_analysis.get('breakeven_trades', 0)
				}

				chart = self.chart_generator.generate_trade_distribution_chart(chart_data)
				charts.append(chart)

			# 交易时间分布图
			if 'trade_analysis' in report_data:
				trade_analysis = report_data['trade_analysis']

				if 'time_analysis' in trade_analysis:
					time_analysis = trade_analysis['time_analysis']

					if 'day_of_week' in time_analysis:
						# 生成交易日分布图
						chart_data = {
							'days': list(time_analysis['day_of_week'].keys()),
							'counts': list(time_analysis['day_of_week'].values())
						}

						chart = self.chart_generator.generate_trading_day_distribution_chart(chart_data)
						charts.append(chart)

			# 添加到报告
			report.charts = charts

		except Exception as e:
			print(f"添加交易分析图表失败: {str(e)}")

	async def _add_comprehensive_charts (
			self,
			report: AnalysisReport,
			report_data: Dict[str, Any]
	):
		"""
		为综合分析报告添加图表

		Args:
			report: 报告对象
			report_data: 报告数据
		"""
		try:
			charts = []

			# 根据报告数据添加各种图表
			if 'performance_metrics' in report_data:
				await self._add_performance_charts(report, report_data)
				charts.extend(report.charts)

			if 'attribution_analysis' in report_data:
				await self._add_attribution_charts(report, report_data)
				charts.extend(report.charts[len(charts):])

			if 'comparison_analysis' in report_data:
				await self._add_comparison_charts(report, report_data)
				charts.extend(report.charts[len(charts):])

			if 'trade_analysis' in report_data:
				await self._add_trade_analysis_charts(report, report_data)
				charts.extend(report.charts[len(charts):])

			# 更新报告图表
			report.charts = charts

		except Exception as e:
			print(f"添加综合分析图表失败: {str(e)}")

	async def _save_report_to_file (self, report: AnalysisReport):
		"""
		保存报告到文件

		Args:
			report: 报告对象
		"""
		try:
			# 构建文件路径
			report_file = self.report_storage_path / f"{report.report_id}.json"

			# 转换为字典
			report_dict = report.to_dict()

			# 保存到文件
			async with aiofiles.open(report_file, 'w', encoding='utf-8') as f:
				await f.write(json.dumps(report_dict, ensure_ascii=False, indent=2))

			# 添加到导出文件列表
			report.export_files['json'] = str(report_file)

		except Exception as e:
			raise ValueError(f"保存报告到文件失败: {str(e)}")

	async def _load_report_from_file (self, report_id: str) -> Optional[AnalysisReport]:
		"""
		从文件加载报告

		Args:
			report_id: 报告ID

		Returns:
			AnalysisReport: 分析报告对象，如果文件不存在则返回None
		"""
		try:
			# 构建文件路径
			report_file = self.report_storage_path / f"{report_id}.json"

			if not report_file.exists():
				return None

			# 从文件加载
			async with aiofiles.open(report_file, 'r', encoding='utf-8') as f:
				content = await f.read()
				report_data = json.loads(content)

			# 重新创建报告对象
			report = AnalysisReport(
				report_id=report_data['report_id'],
				user_id=report_data['user_id'],
				report_type=report_data['report_type'],
				title=report_data['title'],
				description=report_data.get('description'),
				parameters=report_data.get('parameters', {}),
				status=report_data['status'],
				progress=report_data['progress'],
				created_at=datetime.fromisoformat(report_data['created_at']),
				updated_at=datetime.fromisoformat(report_data['updated_at']),
				charts=report_data.get('charts', [])
			)

			# 设置完成时间
			if report_data.get('completed_at'):
				report.completed_at = datetime.fromisoformat(report_data['completed_at'])

			# 设置导出文件
			if 'export_files' in report_data:
				report.export_files = report_data['export_files']

			return report

		except Exception as e:
			print(f"从文件加载报告失败 {report_id}: {str(e)}")
			return None

	async def _export_json (self, report: AnalysisReport) -> bytes:
		"""
		导出为JSON格式

		Args:
			report: 报告对象

		Returns:
			JSON字节数据
		"""
		try:
			report_dict = report.to_dict()
			return json.dumps(report_dict, ensure_ascii=False, indent=2).encode('utf-8')

		except Exception as e:
			raise ValueError(f"导出JSON失败: {str(e)}")

	async def _export_csv (self, report: AnalysisReport) -> bytes:
		"""
		导出为CSV格式

		Args:
			report: 报告对象

		Returns:
			CSV字节数据
		"""
		try:
			# 将报告数据转换为扁平结构
			csv_data = []

			# 添加基本报告信息
			csv_data.append(["报告ID", report.report_id])
			csv_data.append(["报告类型", report.report_type])
			csv_data.append(["标题", report.title])
			csv_data.append(["创建时间", report.created_at.isoformat()])

			# 根据报告类型添加具体数据
			if report.report_type == 'performance' and report.performance_metrics:
				metrics = report.performance_metrics

				csv_data.append([])
				csv_data.append(["绩效指标"])
				csv_data.append(["总收益", f"{float(metrics.total_return):.2%}"])
				csv_data.append(["年化收益", f"{float(metrics.annual_return):.2%}"])
				csv_data.append(["夏普比率", f"{float(metrics.sharpe_ratio):.2f}"])
				csv_data.append(["最大回撤", f"{float(metrics.max_drawdown):.2%}"])

			# 转换为CSV字符串
			output = ""
			for row in csv_data:
				output += ",".join(str(cell) for cell in row) + "\n"

			return output.encode('utf-8')

		except Exception as e:
			raise ValueError(f"导出CSV失败: {str(e)}")

	async def _export_pdf (self, report: AnalysisReport) -> bytes:
		"""
		导出为PDF格式

		Args:
			report: 报告对象

		Returns:
			PDF字节数据
		"""
		try:
			# 使用报告生成器创建PDF
			pdf_content = await self.report_generator.generate_pdf_report(report)
			return pdf_content

		except Exception as e:
			raise ValueError(f"导出PDF失败: {str(e)}")

	async def _export_html (self, report: AnalysisReport) -> bytes:
		"""
		导出为HTML格式

		Args:
			report: 报告对象

		Returns:
			HTML字节数据
		"""
		try:
			# 使用报告生成器创建HTML
			html_content = await self.report_generator.generate_html_report(report)
			return html_content.encode('utf-8')

		except Exception as e:
			raise ValueError(f"导出HTML失败: {str(e)}")