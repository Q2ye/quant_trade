# quant_server/modules/events/calculators/exposure_calculator.py
"""
风险敞口计算器 - 计算账户风险敞口和集中度

职责：
1. 计算行业敞口
2. 计算个股集中度
3. 计算风险价值（VaR）
4. 计算风险指标
"""

from typing import Dict, List, Optional, Tuple
from datetime import datetime, date
from decimal import Decimal
from collections import defaultdict
from sqlalchemy.orm import Session

from quant_server.shared.database.repositories import (
	PositionRepository,
	AccountRepository,
)
from quant_server.shared.sources import StockDataSource
from quant_server.modules.account.models import (
	IndustryExposure,
	ConcentrationRisk,
	RiskMetrics,
	VaRResult,
)


class ExposureCalculator:
	"""风险敞口计算器"""

	def __init__ (self, session: Session, data_source: Optional[StockDataSource] = None):
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

	async def calculate_industry_exposure (self, account_id: int) -> List[IndustryExposure]:
		"""
		计算行业敞口

		Args:
			account_id: 账户ID

		Returns:
			List[IndustryExposure]: 行业敞口列表
		"""
		positions = await self.position_repo.get_by_account_id(account_id)
		account = await self.account_repo.get_by_id(account_id)

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

		Args:
			ts_code: 证券代码

		Returns:
			str: 行业名称
		"""
		if self.data_source:
			try:
				stock_info = await self.data_source.get_stock_info(ts_code)
				return stock_info.get('industry', '未知行业')
			except Exception:
				pass

		# 默认返回未知行业
		return "未知行业"

	async def calculate_concentration_risk (self, account_id: int) -> ConcentrationRisk:
		"""
		计算集中度风险

		Args:
			account_id: 账户ID

		Returns:
			ConcentrationRisk: 集中度风险指标
		"""
		positions = await self.position_repo.get_by_account_id(account_id)
		account = await self.account_repo.get_by_id(account_id)

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
			account_id: int,
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
		positions = await self.position_repo.get_by_account_id(account_id)
		account = await self.account_repo.get_by_id(account_id)

		if not account or not positions:
			return VaRResult(
				var=Decimal('0'),
				confidence_level=confidence_level,
				time_horizon=time_horizon,
				method=method,
				components=[]
			)

		# 这里简化实现，实际需要：
		# 1. 获取历史收益率数据
		# 2. 计算组合收益率
		# 3. 根据方法计算VaR

		# 简化：使用参数法计算
		var_components = []
		total_var = Decimal('0')

		for position in positions:
			if position.volume <= 0 or not position.last_price:
				continue

			market_value = Decimal(str(position.volume)) * Decimal(str(position.last_price))

			# 简化：假设每只股票年化波动率20%
			annual_volatility = Decimal('0.2')
			daily_volatility = annual_volatility / Decimal('16')  # sqrt(252) ≈ 16

			# 正态分布Z值
			z_score = self._get_z_score(confidence_level)

			# 个股VaR
			position_var = market_value * daily_volatility * Decimal(str(z_score)) * Decimal(str(time_horizon ** 0.5))

			var_components.append({
				'ts_code': position.ts_code,
				'market_value': market_value,
				'var': position_var,
				'contribution': position_var  # 简化：不考虑相关性
			})

			total_var += position_var

		# 考虑现金部分（无风险）
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

	def _get_z_score (self, confidence_level: float) -> float:
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

	async def calculate_risk_metrics (self, account_id: int) -> RiskMetrics:
		"""
		计算综合风险指标

		Args:
			account_id: 账户ID

		Returns:
			RiskMetrics: 风险指标
		"""
		account = await self.account_repo.get_by_id(account_id)
		positions = await self.position_repo.get_by_account_id(account_id)

		# 计算基础指标
		total_market_value = sum(
			Decimal(str(p.volume)) * Decimal(str(p.last_price))
			for p in positions
			if p.volume > 0 and p.last_price
		)

		total_cash = Decimal(str(account.available_balance)) if account else Decimal('0')
		total_asset = Decimal(str(account.total_balance)) if account else Decimal('0')

		# 计算杠杆
		leverage = total_market_value / total_cash if total_cash > 0 else Decimal('0')

		# 计算流动性指标
		liquid_positions = [p for p in positions if p.volume > 0 and p.available_volume > 0]
		illiquid_ratio = 1 - len(liquid_positions) / len(positions) if positions else Decimal('0')

		# 计算相关性风险（简化）
		# 实际需要计算组合内股票的相关性

		# 获取VaR
		var_result = await self.calculate_var(account_id)

		# 获取集中度风险
		concentration = await self.calculate_concentration_risk(account_id)

		return RiskMetrics(
			total_asset=total_asset,
			total_market_value=total_market_value,
			total_cash=total_cash,
			leverage=leverage,
			liquidity_ratio=Decimal('1') - illiquid_ratio,
			var_95=var_result.var,
			var_percentage=var_result.var_percentage,
			herfindahl_index=concentration.herfindahl_index,
			max_concentration=concentration.max_concentration,
			is_concentration_violated=concentration.is_violated,
			position_count=len([p for p in positions if p.volume > 0]),
			industry_count=len(set(
				await self._get_stock_industry(p.ts_code)
				for p in positions
				if p.volume > 0
			))
		)

	async def calculate_stress_test (
			self,
			account_id: int,
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
		positions = await self.position_repo.get_by_account_id(account_id)
		account = await self.account_repo.get_by_id(account_id)

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
				loss += market_value * params["volatility_increase"] * Decimal('0.1')  # 简化

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

	async def generate_risk_report (self, account_id: int) -> Dict:
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
			"risk_metrics": risk_metrics.dict(),
			"concentration_risk": concentration.dict(),
			"industry_exposure": [exp.dict() for exp in industry_exposure],
			"var_analysis": var_result.dict(),
			"stress_tests": stress_tests,
			"recommendations": self._generate_recommendations(risk_metrics, concentration, industry_exposure)
		}

		return report

	def _determine_risk_level (self, risk_metrics: RiskMetrics) -> str:
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

	def _calculate_risk_score (
			self,
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

	def _generate_recommendations (
			self,
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