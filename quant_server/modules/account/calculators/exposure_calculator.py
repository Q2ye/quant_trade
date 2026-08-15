# quant_server/modules/events/calculators/exposure_calculator.py
"""
风险敞口计算器 - 计算账户风险敞口和集中度

职责：
1. 计算行业敞口
2. 计算个股集中度
3. 计算风险价值（VaR）
4. 计算风险指标
"""
import logging
from collections import defaultdict
from datetime import datetime
from decimal import Decimal
from typing import Dict, List, Optional

import numpy as np
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from core import BusinessException
from modules.account.models import (
	IndustryExposure,
	ConcentrationRisk,
	RiskMetrics,
	VaRResult,
)
from shared.database.repositories.account.asset.account_repo import AccountRepository
from shared.database.repositories.trading.position.position_repo import PositionRepository
from shared.sources.base_source import BaseDataSource

logger = logging.getLogger(__name__)

class ExposureCalculator:
	"""风险敞口计算器"""

	def __init__ (self, session: AsyncSession, data_source: Optional[BaseDataSource] = None):
		"""
		初始化风险敞口计算器

		Args:
			session: 数据库会话
			data_source: 数据源（用于获取股票行业信息）
		"""
		self.session = session
		self.position_repo = PositionRepository(session)
		self.account_repo = AccountRepository(session)
		self.data_source = data_source

	async def calculate_industry_exposure (self, account_id: str) -> List[IndustryExposure]:
		"""
		计算行业敞口

		Args:
			account_id: 账户ID

		Returns:
			List[IndustryExposure]: 行业敞口列表
		"""
		positions = await self.position_repo.get_account_positions(account_id)
		account = await self.account_repo.get(account_id)

		if not account or account.total_balance <= 0:
			return []

		# 按行业分组
		industry_exposure = defaultdict(lambda: {
			'market_value': Decimal('0'),
			'stocks': []
		})

		for position in positions:
			if position.volume <= 0 or not position.last_price:
				continue

			market_value = Decimal(str(position.volume)) * Decimal(str(position.last_price))

			# 获取股票行业信息
			industry = await self._get_stock_industry(position.ts_code)

			industry_exposure[industry]['market_value'] += market_value
			industry_exposure[industry]['stocks'].append({
				'ts_code': position.ts_code,
				'market_value': market_value,
				'weight': market_value / Decimal(str(account.total_balance))
			})

		# 转换为IndustryExposure对象
		result = []
		for industry, data in industry_exposure.items():
			weight = data['market_value'] / Decimal(str(account.total_balance))

			result.append(IndustryExposure(
				industry=industry,
				market_value=data['market_value'],
				weight=weight,
				stock_count=len(data['stocks']),
				stocks=data['stocks']
			))

		# 按权重排序
		result.sort(key=lambda x: x.weight, reverse=True)

		return result

	async def _get_stock_industry (self, ts_code: str) -> str:
		"""
		获取股票行业

		优先使用内存缓存，缓存未命中时查询 data_source 或数据库。

		Args:
			ts_code: 证券代码

		Returns:
			str: 行业名称
		"""
		# 使用类级别缓存避免每次全量加载
		if not hasattr(self, '_industry_cache'):
			self._industry_cache = {}

		if ts_code in self._industry_cache:
			return self._industry_cache[ts_code]

		# 尝试从数据库查询
		try:
			result = await self.session.execute(
				text("SELECT industry FROM stock_basic WHERE ts_code = :code LIMIT 1"),
				{"code": ts_code}
			)
			row = result.fetchone()
			if row and row.industry:
				self._industry_cache[ts_code] = row.industry
				return row.industry
		except BusinessException:
			pass

		# 降级：从外部数据源获取
		if self.data_source:
			try:
				stock_basic = await self.data_source.get_stock_basic()
				for stock in stock_basic:
					industry = stock.get('industry', '未知行业')
					code = stock.get('ts_code', '')
					self._industry_cache[code] = industry
				if ts_code in self._industry_cache:
					return self._industry_cache[ts_code]
			except Exception as e:
				logger.debug(f"获取股票行业信息失败: {str(e)}")

		self._industry_cache[ts_code] = "未知行业"
		return "未知行业"

	async def calculate_concentration_risk (self, account_id: str) -> ConcentrationRisk:
		"""
		计算集中度风险

		Args:
			account_id: 账户ID

		Returns:
			ConcentrationRisk: 集中度风险指标
		"""
		positions = await self.position_repo.get_account_positions(account_id)
		account = await self.account_repo.get(account_id)

		if not account or account.total_balance <= 0:
			return ConcentrationRisk(
				herfindahl_index=Decimal('0'),
				top_n_concentration={},
				single_stock_limit=Decimal('0'),
				is_violated=False
			)

		# 计算持仓权重
		position_weights = []
		for position in positions:
			if position.volume <= 0 or not position.last_price:
				continue

			market_value = Decimal(str(position.volume)) * Decimal(str(position.last_price))
			weight = market_value / Decimal(str(account.total_balance))
			position_weights.append((position.ts_code, weight))

		# 按权重排序
		position_weights.sort(key=lambda x: x[1], reverse=True)

		# 计算赫芬达尔指数（HHI）
		hhi = sum(weight ** 2 for _, weight in position_weights)

		# 计算前N集中度
		top_n_concentration = {}
		for n in [1, 3, 5, 10]:
			if len(position_weights) >= n:
				concentration = sum(weight for _, weight in position_weights[:n])
				top_n_concentration[f'top_{n}'] = concentration

		# 检查单股持仓限制（例如不超过20%）
		single_stock_limit = Decimal('0.2')  # 20%限制
		max_concentration = position_weights[0][1] if position_weights else Decimal('0')
		is_violated = max_concentration > single_stock_limit

		return ConcentrationRisk(
			herfindahl_index=Decimal(str(hhi)),
			top_n_concentration=top_n_concentration,
			single_stock_limit=single_stock_limit,
			is_violated=is_violated,
			max_concentration=max_concentration,
			max_concentration_stock=position_weights[0][0] if position_weights else None
		)

	async def calculate_var (
			self,
			account_id: str,
			confidence_level: float = 0.95,
			time_horizon: int = 1,
			method: str = "historical"
	) -> VaRResult:
		"""
		计算风险价值（VaR）

		Args:
			account_id: 账户ID
			confidence_level: 置信水平（0.95表示95%）
			time_horizon: 时间周期（天）
			method: 计算方法（historical, parametric, monte_carlo）

		Returns:
			VaRResult: VaR计算结果
		"""
		# 获取账户持仓
		positions = await self.position_repo.get_account_positions(account_id)
		account = await self.account_repo.get(account_id)

		if not account or not positions:
			return VaRResult(
				var=Decimal('0'),
				confidence_level=confidence_level,
				time_horizon=time_horizon,
				method=method,
				components=[]
			)

		# 获取持仓的历史价格数据并计算各股波动率
		var_components = []

		# 批量获取所有持仓的日收益率
		position_volatilities = {}
		position_prices = {}  # ts_code -> close_prices list
		for position in positions:
			if position.volume <= 0 or not position.last_price:
				continue
			try:
				result = await self.session.execute(
					text(
						"SELECT close FROM stock_daily "
						"WHERE ts_code = :code ORDER BY trade_date DESC LIMIT 252"
					),
					{"code": position.ts_code}
				)
				closes = [float(row.close) for row in result.fetchall() if row.close]
				if len(closes) >= 21:  # 至少1个月数据
					# v2.4: 防止零/负价格导致 np.log 产生 -inf
					valid_closes = np.array([c for c in closes if c > 0])
					if len(valid_closes) >= 2:
						log_returns = np.diff(np.log(valid_closes))
						daily_vol = float(np.std(log_returns))
						position_volatilities[position.ts_code] = daily_vol
						position_prices[position.ts_code] = closes
			except BusinessException:
				pass

		# 获取组合中所有股票的协方差矩阵（用于组合VaR）
		valid_codes = [p.ts_code for p in positions if p.volume > 0 and p.last_price and p.ts_code in position_volatilities]
		n_valid = len(valid_codes)

		# 默认波动率：使用组合平均波动率，若无数据则用20%年化
		if position_volatilities:
			default_annual_vol = float(np.mean(list(position_volatilities.values()))) * np.sqrt(252)
		else:
			default_annual_vol = 0.20

		total_var = Decimal('0')
		for position in positions:
			if position.volume <= 0 or not position.last_price:
				continue

			market_value = Decimal(str(position.volume)) * Decimal(str(position.last_price))

			# 使用实际波动率或默认波动率
			daily_vol = position_volatilities.get(position.ts_code, default_annual_vol / np.sqrt(252))

			# 正态分布Z值
			z_score = self._get_z_score(confidence_level)

			# 个股VaR: MV × σ_daily × Z × √T
			position_var = market_value * Decimal(str(daily_vol)) * Decimal(str(z_score)) * Decimal(str(time_horizon ** 0.5))

			# 若有多只持仓，使用简单协方差调整（等权重假设）
			if n_valid > 1 and position.ts_code in position_volatilities:
				# 使用各股日波动率数据估算平均两两相关系数
				avg_corr = Decimal("0.3")  # 默认保守假设
				if n_valid > 1 and len(position_prices) >= 2:
					try:
						# 从已获取的价格数据计算样本相关系数矩阵
						return_series = []
						min_len = min(len(prices) for prices in position_prices.values() if len(prices) >= 21)
						if min_len >= 21:
							for code in position_prices:
								prices_arr = np.array(position_prices[code][:min_len])
								returns = np.diff(np.log(prices_arr))
								return_series.append(returns)
							if len(return_series) >= 2:
								corr_matrix = np.corrcoef(return_series)
								# 取上三角非对角线元素均值作为平均相关系数
								n_assets = corr_matrix.shape[0]
								upper_tri = corr_matrix[np.triu_indices(n_assets, k=1)]
								avg_corr = Decimal(str(round(float(np.mean(upper_tri)), 4)))
					except BusinessException:
						pass  # 回退到默认保守假设 0.3
				position_var = position_var * (Decimal("1") + avg_corr * Decimal(str(n_valid - 1))) / Decimal(str(n_valid))

			var_components.append({
				'ts_code': position.ts_code,
				'market_value': market_value,
				'var': position_var,
				'contribution': position_var,
				'annual_volatility': float(daily_vol) * np.sqrt(252)
			})

			total_var += position_var

		cash_var = Decimal('0')

		return VaRResult(
			var=total_var + cash_var,
			confidence_level=confidence_level,
			time_horizon=time_horizon,
			method=method,
			components=var_components,
			var_percentage=(total_var + cash_var) / Decimal(
				str(account.total_balance)) if account.total_balance > 0 else Decimal('0')
		)

	@staticmethod
	def _get_z_score (confidence_level: float) -> float:
		"""
		获取正态分布Z值

		Args:
			confidence_level: 置信水平

		Returns:
			float: Z值
		"""
		z_scores = {
			0.90: 1.282,
			0.95: 1.645,
			0.975: 1.960,
			0.99: 2.326,
			0.995: 2.576,
			0.999: 3.090
		}

		return z_scores.get(confidence_level, 1.645)

	async def calculate_risk_metrics (self, account_id: str) -> RiskMetrics:
		"""
		计算综合风险指标

		Args:
			account_id: 账户ID

		Returns:
			RiskMetrics: 风险指标
		"""
		account = await self.account_repo.get(account_id)
		positions = await self.position_repo.get_account_positions(account_id)

		# 计算基础指标
		market_values = [
			Decimal(str(p.volume)) * Decimal(str(p.last_price))
			for p in positions
			if p.volume > 0 and p.last_price
		]
		total_market_value = sum(market_values) if market_values else Decimal('0')

		total_cash = Decimal(str(account.available_balance)) if account else Decimal('0')
		total_asset = Decimal(str(account.total_balance)) if account else Decimal('0')

		# 计算杠杆
		leverage = total_market_value / total_cash if total_cash > 0 else Decimal('0')

		# 计算流动性指标
		liquid_positions = [p for p in positions if p.volume > 0 and p.available_volume > 0]
		illiquid_ratio = 1 - len(liquid_positions) / len(positions) if positions else Decimal('0')
		liquidity_ratio = Decimal('1') - illiquid_ratio

		# 计算组合内股票的平均相关性风险
		correlation_risk = Decimal('0')
		active_position_codes = [p.ts_code for p in positions if p.volume > 0 and p.last_price]
		if len(active_position_codes) >= 2:
			from shared.database.models.data_models import StockDaily
			from sqlalchemy import select
			# 获取最近60个交易日的涨跌幅数据
			returns_query = (
				select(StockDaily.ts_code, StockDaily.trade_date, StockDaily.pct_chg)
				.where(
					StockDaily.ts_code.in_(active_position_codes),
					StockDaily.trade_date >= text("CURRENT_DATE - INTERVAL '90 days'")
				)
				.order_by(StockDaily.trade_date)
			)
			result = await self.session.execute(returns_query)
			rows = result.all()
			if rows:
				# 构建 pivot: {ts_code: [return, ...]} 对齐日期
				import pandas as pd
				df = pd.DataFrame(rows, columns=['ts_code', 'trade_date', 'pct_chg'])
				df['return'] = df['pct_chg'].astype(float) / 100.0
				pivot = df.pivot(index='trade_date', columns='ts_code', values='return')
				pivot = pivot.dropna(axis=0, thresh=len(active_position_codes) // 2)
				if pivot.shape[1] >= 2 and pivot.shape[0] >= 20:
					corr_matrix = pivot.corr()
					# 取上三角（不含对角线）的平均值
					mask = np.triu(np.ones(corr_matrix.shape), k=1).astype(bool)
					upper_vals = corr_matrix.where(mask).stack()
					avg_corr = float(upper_vals.mean())
					if not np.isnan(avg_corr):
						correlation_risk = Decimal(str(round(avg_corr, 4)))


		# 获取行业敞口
		industry_exposure = await self.calculate_industry_exposure(account_id)

		# 获取VaR
		var_result = await self.calculate_var(account_id)

		# 获取集中度风险
		concentration = await self.calculate_concentration_risk(account_id)

		# 计算 Sharpe Ratio、Max Drawdown、Beta、Alpha

		sharpe_ratio = None
		max_drawdown_val = None
		beta_val = None
		alpha_val = None

		try:
			# 解析 account_id -> user_id（account_daily_performance 表以 user_id 为维度）
			account_obj = await self.account_repo.get(account_id)
			user_id = account_obj.user_id if account_obj else account_id
			
			# 从每日绩效表获取账户收益率序列
			result = await self.session.execute(
				text(
					"SELECT daily_return FROM account_daily_performance "
					"WHERE user_id = :uid ORDER BY trade_date"
				),
				{"uid": user_id}
			)
			daily_returns = [float(row.daily_return) for row in result.fetchall() if row.daily_return is not None]

			if len(daily_returns) >= 20:
				returns_arr = np.array(daily_returns)

				# 修复 2026-08（C4）：rf 纳入（统一 2%），与 pnl_calculator/financial_calculator 口径一致
				_rf_daily = 0.02 / 252
				_excess = returns_arr - _rf_daily
				mean_return = float(np.mean(_excess))
				std_return = float(np.std(_excess, ddof=1))
				if std_return > 0:
					sharpe_ratio = Decimal(str(round(mean_return / std_return * np.sqrt(252), 4)))

				# Max Drawdown: 从累计收益曲线计算最大回撤
				cumulative = np.cumprod(1 + returns_arr)
				running_max = np.maximum.accumulate(cumulative)
				drawdowns = (cumulative - running_max) / running_max
				max_drawdown_val = Decimal(str(round(float(np.min(drawdowns)), 4)))

				# Beta 和 Alpha（相对沪深300）
				try:
					benchmark_result = await self.session.execute(
						text(
							"SELECT close FROM stock_daily "
							"WHERE ts_code = '000300.SH' ORDER BY trade_date"
						)
					)
					benchmark_closes = [float(row.close) for row in benchmark_result.fetchall() if row.close]
					if len(benchmark_closes) >= len(returns_arr):
						benchmark_closes = benchmark_closes[-len(returns_arr):]
						bench_returns = np.diff(np.log(benchmark_closes))
						if len(bench_returns) == len(returns_arr):
							cov_matrix = np.cov(returns_arr, bench_returns)
							beta_val = Decimal(str(round(float(cov_matrix[0, 1] / cov_matrix[1, 1]), 4)))
							# Alpha: 年化超额收益（Jensen's Alpha）
							alpha_val = Decimal(str(round(
								float(mean_return - beta_val * np.mean(bench_returns)) * 252, 4
							)))
				except BusinessException:
					pass
		except BusinessException:
			pass

		return RiskMetrics(
			account_id=account_id,
			calculation_time=datetime.now(),
			industry_exposure=industry_exposure,
			concentration_risk=concentration,
			var=var_result.var,
			sharpe_ratio=sharpe_ratio,
			max_drawdown=max_drawdown_val,
			beta=beta_val,
			alpha=alpha_val,
			total_asset=total_asset,
			leverage=leverage,
			max_concentration=concentration.max_concentration,
			liquidity_ratio=liquidity_ratio,
			var_95=var_result.var,
			var_percentage=var_result.var_percentage,
			herfindahl_index=concentration.herfindahl_index,
			is_concentration_violated=concentration.is_violated,
			position_count=len([p for p in positions if p.volume > 0]),
			industry_count=len(set(
				await self._get_stock_industry(p.ts_code)
				for p in positions
				if p.volume > 0
			)),
			total_market_value=total_market_value,
			total_cash=total_cash,
			correlation_risk=correlation_risk
		)

	async def calculate_stress_test (
			self,
			account_id: str,
			scenario: str = "market_crash"
	) -> Dict[str, Decimal]:
		"""
		压力测试

		Args:
			account_id: 账户ID
			scenario: 压力场景（market_crash, interest_rate_shock, etc.）

		Returns:
			Dict: 压力测试结果
		"""
		positions = await self.position_repo.get_account_positions(account_id)
		account = await self.account_repo.get(account_id)

		if not account:
			return {}

		# 定义压力场景
		scenarios = {
			"market_crash": {
				"equity_drop": Decimal('-0.2'),  # 股市下跌20%
				"volatility_increase": Decimal('0.5'),  # 波动率增加50%
			},
			"interest_rate_shock": {
				"equity_drop": Decimal('-0.1'),
				"bond_drop": Decimal('-0.05'),
			},
			"liquidity_crisis": {
				"equity_drop": Decimal('-0.15'),
				"illiquidity_penalty": Decimal('0.1'),  # 流动性惩罚10%
			}
		}

		params = scenarios.get(scenario, scenarios["market_crash"])

		# 计算压力下的损失
		total_loss = Decimal('0')
		for position in positions:
			if position.volume <= 0 or not position.last_price:
				continue

			market_value = Decimal(str(position.volume)) * Decimal(str(position.last_price))

			# 应用压力场景
			loss = market_value * params["equity_drop"]

			# 考虑波动率增加（对VaR的影响）
			if "volatility_increase" in params:
				# 波动率冲击：基于正态VaR框架，额外损失 = 市值 x 日波动率 x Z值 x 波动率增幅
				# 默认年化波动率20% -> 日波动率 ≈ 1.26%
				default_daily_vol = Decimal("0.0126")
				vol_impact = default_daily_vol * Decimal(str(self._get_z_score(0.95))) * params["volatility_increase"]
				loss += market_value * vol_impact

			total_loss += loss

		# 计算压力测试指标
		stress_loss_pct = total_loss / Decimal(str(account.total_balance)) if account.total_balance > 0 else Decimal(
			'0')

		return {
			"scenario": scenario,
			"total_loss": total_loss,
			"loss_percentage": stress_loss_pct,
			"remaining_asset": Decimal(str(account.total_balance)) + total_loss,
			"is_solvent": (Decimal(str(account.total_balance)) + total_loss) > Decimal('0'),
			"margin_call_risk": stress_loss_pct < Decimal('-0.3')  # 损失超过30%可能触发追加保证金
		}

	async def generate_risk_report (self, account_id: str) -> Dict:
		"""
		生成风险报告

		Args:
			account_id: 账户ID

		Returns:
			Dict: 风险报告
		"""
		# 计算各项风险指标
		risk_metrics = await self.calculate_risk_metrics(account_id)
		concentration = await self.calculate_concentration_risk(account_id)
		industry_exposure = await self.calculate_industry_exposure(account_id)
		var_result = await self.calculate_var(account_id)

		# 压力测试
		stress_tests = {}
		for scenario in ["market_crash", "interest_rate_shock", "liquidity_crisis"]:
			stress_tests[scenario] = await self.calculate_stress_test(account_id, scenario)

		# 生成报告
		report = {
			"summary": {
				"account_id": account_id,
				"report_date": datetime.now().date().isoformat(),
				"total_asset": float(risk_metrics.total_asset),
				"risk_level": self._determine_risk_level(risk_metrics),
				"overall_risk_score": self._calculate_risk_score(risk_metrics, concentration, var_result)
			},
			"risk_metrics": risk_metrics.model_dump(),
			"concentration_risk": concentration.model_dump(),
			"industry_exposure": [exp.model_dump() for exp in industry_exposure],
			"var_analysis": var_result.model_dump(),
			"stress_tests": stress_tests,
			"recommendations": self._generate_recommendations(risk_metrics, concentration, industry_exposure)
		}

		return report

	@staticmethod
	def _determine_risk_level (risk_metrics: RiskMetrics) -> str:
		"""
		确定风险等级

		Args:
			risk_metrics: 风险指标

		Returns:
			str: 风险等级（低、中、高）
		"""
		# 简单规则：根据杠杆和集中度判断
		if risk_metrics.leverage > Decimal('3') or risk_metrics.max_concentration > Decimal('0.3'):
			return "高"
		elif risk_metrics.leverage > Decimal('2') or risk_metrics.max_concentration > Decimal('0.2'):
			return "中"
		else:
			return "低"

	@staticmethod
	def _calculate_risk_score (
			risk_metrics: RiskMetrics,
			concentration: ConcentrationRisk,
			var_result: VaRResult
	) -> float:
		"""
		计算综合风险评分（0-100，越高风险越大）

		Args:
			risk_metrics: 风险指标
			concentration: 集中度风险
			var_result: VaR结果

		Returns:
			float: 风险评分
		"""
		score = 0

		# 杠杆贡献（最高40分）
		leverage_score = min(float(risk_metrics.leverage) * 10, 40)
		score += leverage_score

		# 集中度贡献（最高30分）
		concentration_score = float(concentration.herfindahl_index) * 100 * 0.3
		score += min(concentration_score, 30)

		# VaR贡献（最高20分）
		if risk_metrics.total_asset > 0:
			var_score = float(var_result.var_percentage) * 100 * 2
			score += min(var_score, 20)

		# 流动性贡献（最高10分）
		liquidity_score = (1 - float(risk_metrics.liquidity_ratio)) * 10
		score += liquidity_score

		return min(score, 100)

	@staticmethod
	def _generate_recommendations (
			risk_metrics: RiskMetrics,
			concentration: ConcentrationRisk,
			industry_exposure: List[IndustryExposure]
	) -> List[str]:
		"""
		生成风险建议

		Args:
			risk_metrics: 风险指标
			concentration: 集中度风险
			industry_exposure: 行业敞口

		Returns:
			List[str]: 建议列表
		"""
		recommendations = []

		# 杠杆建议
		if risk_metrics.leverage > Decimal('3'):
			recommendations.append("杠杆过高，建议降低杠杆至3倍以下")
		elif risk_metrics.leverage > Decimal('2'):
			recommendations.append("杠杆适中，建议关注市场波动")

		# 集中度建议
		if concentration.is_violated:
			recommendations.append(f"单股集中度超标（{concentration.max_concentration_stock}），建议降低持仓")

		if concentration.herfindahl_index > Decimal('0.15'):
			recommendations.append("持仓集中度偏高，建议分散投资")

		# 行业集中度建议
		if industry_exposure:
			top_industry = industry_exposure[0]
			if top_industry.weight > Decimal('0.4'):
				recommendations.append(f"行业集中度过高（{top_industry.industry}），建议分散行业配置")

		# 流动性建议
		if risk_metrics.liquidity_ratio < Decimal('0.7'):
			recommendations.append("组合流动性偏低，建议增加流动性资产")

		# 如果没有问题，给出正面反馈
		if not recommendations:
			recommendations.append("风险控制良好，保持当前配置")

		return recommendations