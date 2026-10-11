# cost_calculator.py   # 成本计算器

import logging
from typing import Dict, Any, Optional

from shared.utils.instrument import is_etf

logger = logging.getLogger(__name__)


class CostCalculator:
	"""成本计算器类"""

	def __init__ (self, config: Optional[Dict[str, Any]] = None):
		"""
		初始化成本计算器

		Args:
			config: 成本计算配置
		"""
		self.config = config or {}
		# 默认费率配置（v2.6 统一费率：万一免五 / 印花税 0.05% / 过户费万0.1 沪深双边无最低）
		# ⚠️ 下列为**股票**费率；场内基金（ETF/LOF）免征印花税与过户费 —— 由
		#    `calculate_trade_cost` 按 `is_etf(ts_code)` 归零（见该方法的免税分支）。
		self.default_rates = {
			"commission_rate": 0.0001,  # 佣金费率（万一）
			"min_commission": 0,  # 免五：无最低佣金
			"stamp_duty_rate": 0.0005,  # 印花税 0.05%（仅卖出，2023-08-28 起减半）
			"transfer_fee_rate": 0.0001,  # 过户费 万0.1（沪深两市、买卖双向，2022-04-29 起）
			"min_transfer_fee": 0,  # 过户费无最低
		}
		# 合并配置
		self.rates = {**self.default_rates, **self.config.get("rates", {})}

	def calculate_trade_cost (self, direction: str, price: float, quantity: int, ts_code: str = None) -> Dict[
		str, float]:
		"""
		计算交易成本

		Args:
			direction: 交易方向，buy 或 sell
			price: 交易价格
			quantity: 交易数量
			ts_code: 标的代码。⚠️ **必须传** —— 场内基金（ETF/LOF）免征印花税与过户费，
			    不传则无法判别，按**股票**口径收费（保守方向：宁可多收，不静默免税）并 WARNING。

		Returns:
			Dict[str, float]: 成本明细

		免税规则（2026-10-09 修复 B2）：
			场内基金（ETF/LOF）免征印花税与过户费 —— 证券交易印花税仅对股票及以股票为
			基础的存托凭证征收，基金免征；过户费为股票登记结算费用，场内基金不收。
			⚠️ 修复前该分支缺失（`ts_code` 形参被接收却从未使用）→ 实盘对 ETF 卖出多计
			    0.05% 印花税、双向多计 0.01% 过户费，而回测侧 `backtest_broker._fee_rates`
			    早已正确豁免 ⇒ 回测↔实盘费率口径不一致。
			判别复用 `shared.utils.instrument.is_etf`（唯一事实源，与回测侧同一实现）。
		"""
		# 计算成交金额
		amount = price * quantity

		# 计算佣金（股票与场内基金同费率，不做豁免）
		commission = amount * self.rates["commission_rate"]
		commission = max(commission, self.rates["min_commission"])

		# 判别场内基金（ETF/LOF）→ 免征印花税与过户费；未传代码则按股票口径（保守）
		if not ts_code:
			logger.warning(
				"calculate_trade_cost 未传 ts_code（direction=%s price=%s quantity=%s）→ "
				"按【股票】口径计费（含印花税/过户费），可能高估场内基金成本",
				direction, price, quantity,
			)
			exempt_fund_fees = False
		else:
			exempt_fund_fees = is_etf(ts_code)

		# 计算过户费（沪深两市、买卖双向收取，无最低；场内基金免征）
		transfer_fee = 0.0 if exempt_fund_fees else amount * self.rates["transfer_fee_rate"]

		# 计算印花税（仅卖出；场内基金免征）
		stamp_duty = 0.0
		if direction == "sell" and not exempt_fund_fees:
			stamp_duty = amount * self.rates["stamp_duty_rate"]

		# 计算总成本
		total_cost = commission + transfer_fee + stamp_duty

		return {
			"amount": amount,
			"commission": commission,
			"transfer_fee": transfer_fee,
			"stamp_duty": stamp_duty,
			"total_cost": total_cost
		}

	@staticmethod
	def calculate_position_cost(current_price: float, quantity: int, average_cost: float) -> Dict[str, float]:
		"""
		计算持仓成本

		Args:
			current_price: 当前价格
			quantity: 持仓数量
			average_cost: 平均成本

		Returns:
			Dict[str, float]: 持仓成本明细
		"""
		# 计算当前市值
		market_value = current_price * quantity

		# 计算持仓成本
		position_cost = average_cost * quantity

		# 计算盈亏
		profit_loss = market_value - position_cost

		# 计算盈亏比例
		profit_loss_ratio = 0
		if position_cost > 0:
			profit_loss_ratio = (profit_loss / position_cost) * 100

		return {
			"market_value": market_value,
			"position_cost": position_cost,
			"profit_loss": profit_loss,
			"profit_loss_ratio": profit_loss_ratio,
			"average_cost": average_cost,
			"current_price": current_price,
			"quantity": quantity
		}

	def calculate_batch_trade_cost (self, trades: list) -> Dict[str, float]:
		"""
		计算批量交易成本

		Args:
			trades: 交易列表，每个元素包含 direction, price, quantity, ts_code

		Returns:
			Dict[str, float]: 总成本明细
		"""
		total_amount = 0
		total_commission = 0
		total_transfer_fee = 0
		total_stamp_duty = 0
		total_cost = 0

		for trade in trades:
			cost = self.calculate_trade_cost(
				direction=trade.get("direction"),
				price=trade.get("price"),
				quantity=trade.get("quantity"),
				ts_code=trade.get("ts_code")
			)
			total_amount += cost["amount"]
			total_commission += cost["commission"]
			total_transfer_fee += cost["transfer_fee"]
			total_stamp_duty += cost["stamp_duty"]
			total_cost += cost["total_cost"]

		return {
			"total_amount": total_amount,
			"total_commission": total_commission,
			"total_transfer_fee": total_transfer_fee,
			"total_stamp_duty": total_stamp_duty,
			"total_cost": total_cost
		}


# ---- v2.4: 模块级统一入口 ----

# 默认费率常量（A 股标准，v2.6 统一）
# ⚠️ 均为**股票**费率。场内基金（ETF/LOF）免征印花税与过户费 ——
#    须经 `calculate_fee(..., ts_code=...)` 走 `CostCalculator` 的免税分支，勿直接套用本组常量。
DEFAULT_COMMISSION_RATE = 0.0001    # 万一佣金（免五）
DEFAULT_MIN_COMMISSION = 0          # 免五：无最低佣金
DEFAULT_STAMP_DUTY_RATE = 0.0005    # 印花税 0.05%（仅卖出，股票）
DEFAULT_TRANSFER_FEE_RATE = 0.0001  # 过户费万0.1（沪深两市、买卖双向，股票）

# 模块级默认实例，无需重复创建
_default_calculator = CostCalculator()


def calculate_fee(direction: str, price: float, quantity: int, ts_code: str = None):
    """v2.4: 统一费率计算入口 -- 所有模块通过此函数获取费用，确保一致性

    用法: from modules.trade.utils.cost_calculator import calculate_fee
    """
    return _default_calculator.calculate_trade_cost(direction, price, quantity, ts_code)
