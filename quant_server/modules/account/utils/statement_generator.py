"""
对账单生成器模块
负责生成各类账户对账单和报告
"""

import json
import logging
from datetime import datetime, date
from pathlib import Path
from typing import Dict, List, Optional

import pandas as pd

from ..calculators.asset_calculator import AssetCalculator
from ..calculators.pnl_calculator import PnLCalculator
from shared.storage.file_storage import FileStorage
from utils.core_utils.data_utils.validation import validate_account_data

logger = logging.getLogger(__name__)


class StatementGenerator:
	"""
	对账单生成器
	负责生成各类账户对账单和报告
	"""

	def __init__ (self, output_dir: Optional[str] = None, session=None):
		"""
		初始化对账单生成器

		Args:
			output_dir: 输出目录，默认为系统配置的报表目录
			session: 数据库会话
		"""
		if output_dir is None:
			from shared.config.config_manager import get_config
			settings = get_config().settings
			self.output_dir = Path(getattr(settings, 'REPORT_OUTPUT_DIR', 'output/reports')) / "account_statements"
		else:
			self.output_dir = Path(output_dir)

		# 创建输出目录
		self.output_dir.mkdir(parents=True, exist_ok=True)

		# 初始化存储
		self.file_storage = FileStorage()

		# 初始化计算器
		self.asset_calculator = AssetCalculator(session=session)
		self.pnl_calculator = PnLCalculator(session=session)

	def generate_daily_statement (
			self,
			account_id: str,
			trading_day: date,
			trades: List[Dict],
			positions: List[Dict],
			daily_pnl: Dict,
			assets: Dict,
			output_format: str = 'pdf'  # pdf, excel, csv, json
	) -> Dict:
		"""
		生成日终对账单

		Args:
			account_id: 账户ID
			trading_day: 交易日
			trades: 当日交易列表
			positions: 持仓列表
			daily_pnl: 当日盈亏
			assets: 资产信息
			output_format: 输出格式

		Returns:
			Dict: 对账单信息
		"""
		logger.info(f"生成日终对账单，账户: {account_id}, 日期: {trading_day}")

		try:
			# 1. 准备数据
			statement_data = self._prepare_daily_statement_data(
				account_id=account_id,
				trading_day=trading_day,
				trades=trades,
				positions=positions,
				daily_pnl=daily_pnl,
				assets=assets
			)

			# 2. 验证数据
			self._validate_statement_data(statement_data)

			# 3. 根据格式生成文件
			if output_format == 'pdf':
				file_path, file_name = self._generate_pdf_statement(statement_data)
			elif output_format == 'excel':
				file_path, file_name = self._generate_excel_statement(statement_data)
			elif output_format == 'csv':
				file_path, file_name = self._generate_csv_statement(statement_data)
			else:  # json
				file_path, file_name = self._generate_json_statement(statement_data)

			# 4. 上传到文件存储
			storage_url = self._upload_to_storage(file_path, file_name)

			# 5. 记录生成日志
			self._log_statement_generation(statement_data, file_path)

			logger.info(f"日终对账单生成完成: {file_name}")

			return {
				'account_id': account_id,
				'trading_day': trading_day,
				'format': output_format,
				'file_name': file_name,
				'file_path': str(file_path),
				'storage_url': storage_url,
				'generated_at': datetime.now(),
				'statement_data': statement_data
			}

		except Exception as e:
			logger.error(f"生成日终对账单失败: {str(e)}", exc_info=True)
			raise

	def generate_weekly_report (
			self,
			account_id: str,
			start_date: date,
			end_date: date,
			weekly_pnl: Dict,
			output_format: str = 'pdf'
	) -> Dict:
		"""
		生成周度报告

		Args:
			account_id: 账户ID
			start_date: 周开始日期
			end_date: 周结束日期
			weekly_pnl: 周盈亏
			output_format: 输出格式

		Returns:
			Dict: 周度报告信息
		"""
		logger.info(f"生成周度报告，账户: {account_id}, 周期: {start_date} - {end_date}")

		try:
			# 1. 准备数据
			report_data = self._prepare_weekly_report_data(
				account_id=account_id,
				start_date=start_date,
				end_date=end_date,
				weekly_pnl=weekly_pnl
			)

			# 2. 根据格式生成文件
			if output_format == 'pdf':
				file_path, file_name = self._generate_pdf_report(report_data, 'weekly')
			elif output_format == 'excel':
				file_path, file_name = self._generate_excel_report(report_data, 'weekly')
			else:  # json
				file_path, file_name = self._generate_json_report(report_data, 'weekly')

			# 3. 上传到文件存储
			storage_url = self._upload_to_storage(file_path, file_name)

			logger.info(f"周度报告生成完成: {file_name}")

			return {
				'account_id': account_id,
				'period': f"{start_date} - {end_date}",
				'format': output_format,
				'file_name': file_name,
				'file_path': str(file_path),
				'storage_url': storage_url,
				'generated_at': datetime.now()
			}

		except Exception as e:
			logger.error(f"生成周度报告失败: {str(e)}")
			raise

	def generate_monthly_report (
			self,
			account_id: str,
			start_date: date,
			end_date: date,
			monthly_pnl: Dict,
			output_format: str = 'pdf'
	) -> Dict:
		"""
		生成月度报告

		Args:
			account_id: 账户ID
			start_date: 月开始日期
			end_date: 月结束日期
			monthly_pnl: 月盈亏
			output_format: 输出格式

		Returns:
			Dict: 月度报告信息
		"""
		logger.info(f"生成月度报告，账户: {account_id}, 月份: {start_date.month}")

		try:
			# 1. 准备数据
			report_data = self._prepare_monthly_report_data(
				account_id=account_id,
				start_date=start_date,
				end_date=end_date,
				monthly_pnl=monthly_pnl
			)

			# 2. 根据格式生成文件
			if output_format == 'pdf':
				file_path, file_name = self._generate_pdf_report(report_data, 'monthly')
			elif output_format == 'excel':
				file_path, file_name = self._generate_excel_report(report_data, 'monthly')
			else:  # json
				file_path, file_name = self._generate_json_report(report_data, 'monthly')

			# 3. 上传到文件存储
			storage_url = self._upload_to_storage(file_path, file_name)

			logger.info(f"月度报告生成完成: {file_name}")

			return {
				'account_id': account_id,
				'period': f"{start_date} - {end_date}",
				'format': output_format,
				'file_name': file_name,
				'file_path': str(file_path),
				'storage_url': storage_url,
				'generated_at': datetime.now()
			}

		except Exception as e:
			logger.error(f"生成月度报告失败: {str(e)}")
			raise

	def _prepare_daily_statement_data (
			self,
			account_id: str,
			trading_day: date,
			trades: List[Dict],
			positions: List[Dict],
			daily_pnl: Dict,
			assets: Dict
	) -> Dict:
		"""
		准备日终对账单数据

		Args:
			account_id: 账户ID
			trading_day: 交易日
			trades: 交易列表
			positions: 持仓列表
			daily_pnl: 日盈亏
			assets: 资产

		Returns:
			Dict: 对账单数据
		"""
		# 基本信息
		statement_data = {
			'account_info': {
				'account_id': account_id,
				'trading_day': trading_day.isoformat(),
				'statement_type': 'daily',
				'generated_at': datetime.now().isoformat()
			},
			'assets_summary': {
				'total_asset': float(assets.get('total_asset', 0)),
				'cash_balance': float(assets.get('cash_balance', 0)),
				'market_value': float(assets.get('market_value', 0)),
				'available_cash': float(assets.get('available_cash', 0)),
				'frozen_cash': float(assets.get('frozen_cash', 0)),
				'margin': float(assets.get('margin', 0))
			},
			'daily_pnl_summary': {
				'total_pnl': float(daily_pnl.get('total_pnl', 0)),
				'realized_pnl': float(daily_pnl.get('realized_pnl', 0)),
				'unrealized_pnl': float(daily_pnl.get('unrealized_pnl', 0)),
				'pnl_rate': float(daily_pnl.get('pnl_rate', 0)),
				'benchmark_pnl': float(daily_pnl.get('benchmark_pnl', 0)),
				'alpha': float(daily_pnl.get('alpha', 0))
			},
			'trades': [],
			'positions': [],
			'fee_summary': {
				'commission': 0.0,
				'tax': 0.0,
				'transfer_fee': 0.0,
				'total_fee': 0.0
			}
		}

		# 处理交易明细
		for trade in trades:
			trade_detail = {
				'trade_id': trade.get('trade_id'),
				'security_id': trade.get('security_id'),
				'security_name': trade.get('security_name'),
				'direction': trade.get('direction'),  # buy/sell
				'price': float(trade.get('price', 0)),
				'volume': int(trade.get('volume', 0)),
				'amount': float(trade.get('amount', 0)),
				'trade_time': trade.get('trade_time'),
				'commission': float(trade.get('commission', 0)),
				'tax': float(trade.get('tax', 0)),
				'trade_type': trade.get('trade_type')
			}
			statement_data['trades'].append(trade_detail)

			# 累加费用
			statement_data['fee_summary']['commission'] += trade_detail['commission']
			statement_data['fee_summary']['tax'] += trade_detail['tax']

		# 处理持仓明细
		for position in positions:
			position_detail = {
				'security_id': position.get('security_id'),
				'security_name': position.get('security_name'),
				'current_quantity': int(position.get('current_quantity', 0)),
				'available_quantity': int(position.get('available_quantity', 0)),
				'frozen_quantity': int(position.get('frozen_quantity', 0)),
				'cost_price': float(position.get('cost_price', 0)),
				'market_price': float(position.get('market_price', 0)),
				'cost_value': float(position.get('cost_value', 0)),
				'market_value': float(position.get('market_value', 0)),
				'pnl': float(position.get('pnl', 0)),
				'pnl_rate': float(position.get('pnl_rate', 0)),
				'weight': float(position.get('weight', 0))
			}
			statement_data['positions'].append(position_detail)

		# 计算总费用
		statement_data['fee_summary']['total_fee'] = (
				statement_data['fee_summary']['commission'] +
				statement_data['fee_summary']['tax'] +
				statement_data['fee_summary']['transfer_fee']
		)

		# 计算统计数据
		statement_data['statistics'] = self._calculate_statement_statistics(statement_data)

		return statement_data

	@staticmethod
	def _prepare_weekly_report_data (
			account_id: str,
			start_date: date,
			end_date: date,
			weekly_pnl: Dict
	) -> Dict:
		"""
		准备周度报告数据

		Args:
			account_id: 账户ID
			start_date: 开始日期
			end_date: 结束日期
			weekly_pnl: 周盈亏

		Returns:
			Dict: 周度报告数据
		"""
		report_data = {
			'account_info': {
				'account_id': account_id,
				'report_type': 'weekly',
				'period': f"{start_date.isoformat()} - {end_date.isoformat()}",
				'start_date': start_date.isoformat(),
				'end_date': end_date.isoformat(),
				'generated_at': datetime.now().isoformat()
			},
			'performance_summary': {
				'weekly_return': float(weekly_pnl.get('total_return', 0)),
				'weekly_pnl': float(weekly_pnl.get('total_pnl', 0)),
				'daily_returns': weekly_pnl.get('daily_returns', []),
				'volatility': float(weekly_pnl.get('volatility', 0)),
				'sharpe_ratio': float(weekly_pnl.get('sharpe_ratio', 0)),
				'max_drawdown': float(weekly_pnl.get('max_drawdown', 0))
			},
			'trading_summary': {
				'total_trades': weekly_pnl.get('total_trades', 0),
				'winning_trades': weekly_pnl.get('winning_trades', 0),
				'losing_trades': weekly_pnl.get('losing_trades', 0),
				'win_rate': float(weekly_pnl.get('win_rate', 0)),
				'avg_win': float(weekly_pnl.get('avg_win', 0)),
				'avg_loss': float(weekly_pnl.get('avg_loss', 0)),
				'profit_factor': float(weekly_pnl.get('profit_factor', 0))
			},
			'risk_metrics': {
				'var_95': float(weekly_pnl.get('var_95', 0)),
				'cvar_95': float(weekly_pnl.get('cvar_95', 0)),
				'beta': float(weekly_pnl.get('beta', 0)),
				'alpha': float(weekly_pnl.get('alpha', 0))
			}
		}

		return report_data

	@staticmethod
	def _prepare_monthly_report_data (
			account_id: str,
			start_date: date,
			end_date: date,
			monthly_pnl: Dict
	) -> Dict:
		"""
		准备月度报告数据

		Args:
			account_id: 账户ID
			start_date: 开始日期
			end_date: 结束日期
			monthly_pnl: 月盈亏

		Returns:
			Dict: 月度报告数据
		"""
		report_data = {
			'account_info': {
				'account_id': account_id,
				'report_type': 'monthly',
				'month': start_date.strftime('%Y-%m'),
				'period': f"{start_date.isoformat()} - {end_date.isoformat()}",
				'start_date': start_date.isoformat(),
				'end_date': end_date.isoformat(),
				'generated_at': datetime.now().isoformat()
			},
			'performance_summary': {
				'monthly_return': float(monthly_pnl.get('total_return', 0)),
				'monthly_pnl': float(monthly_pnl.get('total_pnl', 0)),
				'ytd_return': float(monthly_pnl.get('ytd_return', 0)),
				'annualized_return': float(monthly_pnl.get('annualized_return', 0)),
				'volatility': float(monthly_pnl.get('volatility', 0)),
				'sharpe_ratio': float(monthly_pnl.get('sharpe_ratio', 0)),
				'sortino_ratio': float(monthly_pnl.get('sortino_ratio', 0)),
				'max_drawdown': float(monthly_pnl.get('max_drawdown', 0))
			},
			'trading_summary': {
				'total_trades': monthly_pnl.get('total_trades', 0),
				'winning_trades': monthly_pnl.get('winning_trades', 0),
				'losing_trades': monthly_pnl.get('losing_trades', 0),
				'win_rate': float(monthly_pnl.get('win_rate', 0)),
				'avg_holding_period': float(monthly_pnl.get('avg_holding_period', 0)),
				'avg_profit_per_trade': float(monthly_pnl.get('avg_profit_per_trade', 0))
			},
			'asset_allocation': {
				'equity_percentage': float(monthly_pnl.get('equity_percentage', 0)),
				'cash_percentage': float(monthly_pnl.get('cash_percentage', 0)),
				'top_holdings': monthly_pnl.get('top_holdings', [])
			},
			'risk_metrics': {
				'var_95': float(monthly_pnl.get('var_95', 0)),
				'cvar_95': float(monthly_pnl.get('cvar_95', 0)),
				'beta': float(monthly_pnl.get('beta', 0)),
				'alpha': float(monthly_pnl.get('alpha', 0)),
				'tracking_error': float(monthly_pnl.get('tracking_error', 0)),
				'information_ratio': float(monthly_pnl.get('information_ratio', 0))
			}
		}

		return report_data

	@staticmethod
	def _validate_statement_data (statement_data: Dict) -> bool:
		"""
		验证对账单数据

		Args:
			statement_data: 对账单数据

		Returns:
			bool: 是否验证通过
		"""
		try:
			# 验证必需字段
			required_fields = ['account_info', 'assets_summary', 'daily_pnl_summary']
			for field in required_fields:
				if field not in statement_data:
					raise ValueError(f"缺少必需字段: {field}")

			# 验证账户信息
			account_info = statement_data['account_info']
			if 'account_id' not in account_info:
				raise ValueError("缺少account_id")

			# 验证资产数据
			assets = statement_data['assets_summary']
			if assets['total_asset'] < 0:
				raise ValueError("总资产不能为负数")

			# 使用共享验证工具
			validate_account_data(statement_data)

			return True

		except Exception as e:
			logger.error(f"对账单数据验证失败: {str(e)}")
			raise

	def _calculate_statement_statistics (self, statement_data: Dict) -> Dict:
		"""
		计算对账单统计信息

		Args:
			statement_data: 对账单数据

		Returns:
			Dict: 统计信息
		"""
		trades = statement_data['trades']
		positions = statement_data['positions']

		stats = {
			'total_trades': len(trades),
			'buy_trades': sum(1 for t in trades if t['direction'] == 'buy'),
			'sell_trades': sum(1 for t in trades if t['direction'] == 'sell'),
			'total_trade_amount': sum(t['amount'] for t in trades),
			'total_positions': len(positions),
			'positions_with_profit': sum(1 for p in positions if p['pnl'] > 0),
			'positions_with_loss': sum(1 for p in positions if p['pnl'] < 0),
			'avg_position_size': (
				sum(p['market_value'] for p in positions) / len(positions)
				if positions else 0
			),
			'concentration_ratio': self._calculate_concentration_ratio(positions)
		}

		return stats

	@staticmethod
	def _calculate_concentration_ratio (positions: List[Dict]) -> float:
		"""
		计算持仓集中度

		Args:
			positions: 持仓列表

		Returns:
			float: 集中度比率
		"""
		if not positions:
			return 0.0

		total_value = sum(p['market_value'] for p in positions)
		if total_value == 0:
			return 0.0

		# 计算前3大持仓的市值占比
		sorted_positions = sorted(positions, key=lambda x: x['market_value'], reverse=True)
		top3_value = sum(p['market_value'] for p in sorted_positions[:3])

		return top3_value / total_value

	def _generate_pdf_statement (self, statement_data: Dict) -> tuple:
		"""
		生成PDF格式对账单 — 使用 reportlab，不可用时降级为 JSON

		Args:
			statement_data: 对账单数据

		Returns:
			tuple: (文件路径, 文件名)
		"""
		account_id = statement_data["account_info"]["account_id"]
		trading_day = statement_data["account_info"]["trading_day"].replace("-", "")

		file_name = f"statement_{account_id}_{trading_day}.pdf"
		file_path = self.output_dir / file_name

		try:
			from reportlab.lib.pagesizes import A4
			from reportlab.lib.units import mm
			from reportlab.pdfgen import canvas

			c = canvas.Canvas(str(file_path), pagesize=A4)
			width, height = A4
			y = height - 40

			c.setFont("Helvetica-Bold", 18)
			c.drawString(40, y, f"Daily Statement - {account_id}")
			y -= 30

			c.setFont("Helvetica", 11)
			c.drawString(40, y, f"Trading Day: {trading_day}")
			y -= 20

			assets = statement_data.get("assets_summary", {})
			c.drawString(40, y, f"Total Asset: {assets.get('total_asset', 0)}")
			y -= 16
			c.drawString(40, y, f"Cash Balance: {assets.get('cash_balance', 0)}")
			y -= 16
			c.drawString(40, y, f"Market Value: {assets.get('market_value', 0)}")

			pnl = statement_data.get("daily_pnl_summary", {})
			if pnl:
				y -= 30
				c.setFont("Helvetica-Bold", 14)
				c.drawString(40, y, "P&L Summary")
				y -= 20
				c.setFont("Helvetica", 11)
				for key, val in pnl.items():
					c.drawString(50, y, f"{key}: {val}")
					y -= 15

			c.save()
			logger.info(f"生成PDF对账单: {file_path}")
		except ImportError:
			logger.info("reportlab 未安装，降级为 JSON 格式")
			import json
			json_path = self.output_dir / f"statement_{account_id}_{trading_day}.json"
			with open(json_path, "w", encoding="utf-8") as f:
				json.dump(statement_data, f, indent=2, default=str)
			return json_path, json_path.name

		return file_path, file_name

	def _generate_excel_statement (self, statement_data: Dict) -> tuple:
		"""
		生成Excel格式对账单

		Args:
			statement_data: 对账单数据

		Returns:
			tuple: (文件路径, 文件名)
		"""
		account_id = statement_data['account_info']['account_id']
		trading_day = statement_data['account_info']['trading_day'].replace('-', '')

		file_name = f"statement_{account_id}_{trading_day}.xlsx"
		file_path = self.output_dir / file_name

		try:
			# 使用pandas创建Excel文件
			with pd.ExcelWriter(file_path, engine='openpyxl') as writer:
				# 写入基本信息
				info_df = pd.DataFrame([{
					'账户ID': account_id,
					'交易日': trading_day,
					'生成时间': datetime.now().isoformat()
				}])
				info_df.to_excel(writer, sheet_name='基本信息', index=False)

				# 写入资产汇总
				assets_df = pd.DataFrame([statement_data['assets_summary']])
				assets_df.to_excel(writer, sheet_name='资产汇总', index=False)

				# 写入盈亏汇总
				pnl_df = pd.DataFrame([statement_data['daily_pnl_summary']])
				pnl_df.to_excel(writer, sheet_name='盈亏汇总', index=False)

				# 写入交易明细
				if statement_data['trades']:
					trades_df = pd.DataFrame(statement_data['trades'])
					trades_df.to_excel(writer, sheet_name='交易明细', index=False)

				# 写入持仓明细
				if statement_data['positions']:
					positions_df = pd.DataFrame(statement_data['positions'])
					positions_df.to_excel(writer, sheet_name='持仓明细', index=False)

				# 写入费用汇总
				fee_df = pd.DataFrame([statement_data['fee_summary']])
				fee_df.to_excel(writer, sheet_name='费用汇总', index=False)

				# 写入统计数据
				stats_df = pd.DataFrame([statement_data['statistics']])
				stats_df.to_excel(writer, sheet_name='统计信息', index=False)

			logger.info(f"生成Excel对账单: {file_path}")
			return file_path, file_name

		except Exception as e:
			logger.error(f"生成Excel对账单失败: {str(e)}")
			raise

	def _generate_csv_statement (self, statement_data: Dict) -> tuple:
		"""
		生成CSV格式对账单

		Args:
			statement_data: 对账单数据

		Returns:
			tuple: (文件路径, 文件名)
		"""
		account_id = statement_data['account_info']['account_id']
		trading_day = statement_data['account_info']['trading_day'].replace('-', '')

		file_name = f"statement_{account_id}_{trading_day}.csv"
		file_path = self.output_dir / file_name

		try:
			import csv

			with open(file_path, 'w', newline='', encoding='utf-8') as f:
				writer = csv.writer(f)

				# 标题
				writer.writerow(['账户对账单'])
				writer.writerow([f"账户ID: {account_id}"])
				writer.writerow([f"交易日: {trading_day}"])
				writer.writerow([f"生成时间: {datetime.now().isoformat()}"])
				writer.writerow([])

				# 资产汇总
				writer.writerow(['资产汇总'])
				for key, value in statement_data['assets_summary'].items():
					writer.writerow([key, value])
				writer.writerow([])

				# 盈亏汇总
				pnl = statement_data.get('daily_pnl_summary', {})
				if pnl:
					writer.writerow(['盈亏汇总'])
					for key, value in pnl.items():
						writer.writerow([key, value])
					writer.writerow([])

				# 交易明细
				trades = statement_data.get('trades', [])
				if trades:
					writer.writerow(['交易明细'])
					headers = ['trade_id', 'security_id', 'security_name', 'direction',
							   'price', 'volume', 'amount', 'trade_time', 'commission', 'tax']
					writer.writerow(headers)
					for t in trades:
						writer.writerow([t.get(h, '') for h in headers])
					writer.writerow([])

				# 持仓明细
				positions = statement_data.get('positions', [])
				if positions:
					writer.writerow(['持仓明细'])
					pos_headers = ['security_id', 'security_name', 'current_quantity',
								   'cost_price', 'market_price', 'cost_value', 'market_value',
								   'pnl', 'pnl_rate', 'weight']
					writer.writerow(pos_headers)
					for p in positions:
						writer.writerow([p.get(h, '') for h in pos_headers])
					writer.writerow([])

				# 费用汇总
				fees = statement_data.get('fee_summary', {})
				if fees:
					writer.writerow(['费用汇总'])
					for key, value in fees.items():
						writer.writerow([key, value])
					writer.writerow([])

				# 交易统计
				stats = statement_data.get('statistics', {})
				if stats:
					writer.writerow(['交易统计'])
					for key, value in stats.items():
						writer.writerow([key, value])

			logger.info(f"生成CSV对账单: {file_path}")
			return file_path, file_name

		except Exception as e:
			logger.error(f"生成CSV对账单失败: {str(e)}")
			raise

	def _generate_json_statement (self, statement_data: Dict) -> tuple:
		"""
		生成JSON格式对账单

		Args:
			statement_data: 对账单数据

		Returns:
			tuple: (文件路径, 文件名)
		"""
		account_id = statement_data['account_info']['account_id']
		trading_day = statement_data['account_info']['trading_day'].replace('-', '')

		file_name = f"statement_{account_id}_{trading_day}.json"
		file_path = self.output_dir / file_name

		try:
			with open(file_path, 'w', encoding='utf-8') as f:
				json.dump(statement_data, f, ensure_ascii=False, indent=2)

			logger.info(f"生成JSON对账单: {file_path}")
			return file_path, file_name

		except Exception as e:
			logger.error(f"生成JSON对账单失败: {str(e)}")
			raise

	def _generate_pdf_report (self, report_data: Dict, report_type: str) -> tuple:
		"""生成PDF报告 — 使用 reportlab，不可用时降级为 JSON"""
		account_id = report_data["account_info"]["account_id"]
		period = report_data["account_info"]["period"].replace("-", "_")

		file_name = f"{report_type}_report_{account_id}_{period}.pdf"
		file_path = self.output_dir / file_name

		try:
			from reportlab.lib.pagesizes import A4
			from reportlab.pdfgen import canvas

			c = canvas.Canvas(str(file_path), pagesize=A4)
			width, height = A4
			y = height - 40

			c.setFont("Helvetica-Bold", 18)
			c.drawString(40, y, f"{report_type.capitalize()} Report - {account_id}")
			y -= 30

			c.setFont("Helvetica", 11)
			info = report_data.get("account_info", {})
			for key in ["account_id", "period", "start_date", "end_date"]:
				val = info.get(key, "")
				if val:
					c.drawString(40, y, f"{key}: {val}")
					y -= 16

			pnl = report_data.get("pnl_summary", report_data.get("weekly_pnl", report_data.get("monthly_pnl", {})))
			if pnl:
				y -= 20
				c.setFont("Helvetica-Bold", 14)
				c.drawString(40, y, "P&L Summary")
				y -= 20
				c.setFont("Helvetica", 11)
				if isinstance(pnl, dict):
					for key, val in pnl.items():
						c.drawString(50, y, f"{key}: {val}")
						y -= 15
				else:
					c.drawString(50, y, f"total_pnl: {pnl}")

			c.save()
			logger.info(f"生成PDF报告: {file_path}")
		except ImportError:
			logger.info("reportlab 未安装，降级为 JSON 格式")
			import json
			json_path = self.output_dir / f"{report_type}_report_{account_id}_{period}.json"
			with open(json_path, "w", encoding="utf-8") as f:
				json.dump(report_data, f, indent=2, default=str)
			return json_path, json_path.name

		return file_path, file_name

	def _generate_excel_report (self, report_data: Dict, report_type: str) -> tuple:
		"""生成Excel报告"""
		account_id = report_data['account_info']['account_id']
		period = report_data['account_info']['period'].replace('-', '_')

		file_name = f"{report_type}_report_{account_id}_{period}.xlsx"
		file_path = self.output_dir / file_name

		try:
			with pd.ExcelWriter(file_path, engine='openpyxl') as writer:
				# 写入报告数据
				for sheet_name, data in report_data.items():
					if isinstance(data, dict):
						df = pd.DataFrame([data])
						df.to_excel(writer, sheet_name=sheet_name, index=False)

			return file_path, file_name

		except Exception as e:
			logger.error(f"生成Excel报告失败: {str(e)}")
			raise

	def _generate_json_report (self, report_data: Dict, report_type: str) -> tuple:
		"""生成JSON报告"""
		account_id = report_data['account_info']['account_id']
		period = report_data['account_info']['period'].replace('-', '_')

		file_name = f"{report_type}_report_{account_id}_{period}.json"
		file_path = self.output_dir / file_name

		with open(file_path, 'w', encoding='utf-8') as f:
			json.dump(report_data, f, ensure_ascii=False, indent=2)

		return file_path, file_name

	def _upload_to_storage (self, file_path: Path, file_name: str) -> str:
		"""
		上传文件到存储

		Args:
			file_path: 本地文件路径
			file_name: 文件名

		Returns:
			str: 存储URL
		"""
		try:
			with open(file_path, 'rb') as f:
				file_content = f.read()

			# 上传到文件存储
			storage_path = f"account_statements/{file_name}"
			storage_url = self.file_storage.upload(
				content=file_content,
				path=storage_path,
				content_type=self._get_content_type(file_path)
			)

			logger.info(f"文件已上传到存储: {storage_url}")
			return storage_url

		except Exception as e:
			logger.error(f"文件上传失败: {str(e)}")
			# 返回本地路径作为fallback
			return f"file://{file_path}"

	@staticmethod
	def _get_content_type (file_path: Path) -> str:
		"""获取文件内容类型"""
		suffix = file_path.suffix.lower()

		if suffix == '.pdf':
			return 'application/pdf'
		elif suffix == '.xlsx':
			return 'application/vnd.openxmlformats-officedocument.spreadsheetml.sheet'
		elif suffix == '.csv':
			return 'text/csv'
		elif suffix == '.json':
			return 'application/json'
		else:
			return 'application/octet-stream'

	@staticmethod
	def _log_statement_generation (statement_data: Dict, file_path: Path) -> None:
		"""记录对账单生成日志"""
		log_data = {
			'account_id': statement_data['account_info']['account_id'],
			'trading_day': statement_data['account_info']['trading_day'],
			'file_path': str(file_path),
			'generated_at': datetime.now().isoformat(),
			'file_size': file_path.stat().st_size if file_path.exists() else 0
		}

		# 这里可以记录到数据库或日志系统
		logger.info(f"对账单生成日志: {log_data}")


# 工具函数
def generate_daily_statement (
		account_id: str,
		trading_day: date,
		trades: List[Dict],
		positions: List[Dict],
		daily_pnl: Dict,
		assets: Dict,
		output_format: str = 'pdf'
) -> Dict:
	"""生成日终对账单（快捷函数）

	Args:
		account_id: 账户ID
		trading_day: 交易日
		trades: 当日交易列表
		positions: 持仓列表
		daily_pnl: 当日盈亏
		assets: 资产信息
		output_format: 输出格式

	Returns:
		Dict: 对账单信息
	"""
	generator = StatementGenerator()
	return generator.generate_daily_statement(
		account_id, trading_day, trades, positions, daily_pnl, assets, output_format
	)


def generate_weekly_report (
		account_id: str,
		start_date: date,
		end_date: date,
		weekly_pnl: Dict,
		output_format: str = 'pdf'
) -> Dict:
	"""生成周度报告（快捷函数）

	Args:
		account_id: 账户ID
		start_date: 周开始日期
		end_date: 周结束日期
		weekly_pnl: 周盈亏
		output_format: 输出格式

	Returns:
		Dict: 周度报告信息
	"""
	generator = StatementGenerator()
	return generator.generate_weekly_report(
		account_id, start_date, end_date, weekly_pnl, output_format
	)


def generate_monthly_report (
		account_id: str,
		start_date: date,
		end_date: date,
		monthly_pnl: Dict,
		output_format: str = 'pdf'
) -> Dict:
	"""生成月度报告（快捷函数）

	Args:
		account_id: 账户ID
		start_date: 月开始日期
		end_date: 月结束日期
		monthly_pnl: 月盈亏
		output_format: 输出格式

	Returns:
		Dict: 月度报告信息
	"""
	generator = StatementGenerator()
	return generator.generate_monthly_report(
		account_id, start_date, end_date, monthly_pnl, output_format
	)
