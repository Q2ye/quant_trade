"""
账户业务模型定义
包含账户相关的领域对象，非数据库模型
"""
from datetime import date, datetime
from decimal import Decimal
from typing import Optional, List, Dict, Any

from pydantic import BaseModel, Field


class AccountDomain(BaseModel):
	"""账户领域模型"""

	id: str
	account_number: str
	account_name: str
	user_id: str
	account_type: str
	broker: Optional[str] = None
	broker_account_id: Optional[str] = None
	status: str
	status_reason: Optional[str] = None
	total_balance: Decimal
	available_balance: Decimal
	frozen_balance: Decimal
	market_value: Decimal
	initial_balance: Decimal
	credit_line: Optional[Decimal] = None
	last_trade_date: Optional[datetime] = None
	created_at: datetime
	updated_at: datetime

	def is_active (self) -> bool:
		"""检查账户是否活跃"""
		return self.status == "active"

	def is_frozen (self) -> bool:
		"""检查账户是否冻结"""
		return self.status == "frozen"

	def can_trade (self) -> bool:
		"""检查账户是否可以交易"""
		return self.is_active() and self.available_balance > 0

	def get_total_asset (self) -> Decimal:
		"""计算总资产"""
		return self.total_balance

	def get_net_asset (self) -> Decimal:
		"""计算净资产（总资产 - 冻结资金）"""
		return self.total_balance - self.frozen_balance

	def has_enough_balance (self, required_amount: Decimal) -> bool:
		"""检查账户是否有足够余额"""
		return self.available_balance >= required_amount

	def get_available_credit (self) -> Decimal:
		"""获取可用信用额度（仅信用账户）"""
		if self.account_type == "margin" and self.credit_line:
			return self.credit_line - (self.total_balance - self.initial_balance)
		return Decimal(0)


class PositionDomain(BaseModel):
	"""持仓领域模型"""

	id: str
	account_id: str
	ts_code: str
	volume: int
	available_volume: int
	frozen_volume: int
	cost_price: Decimal
	market_value: Decimal
	last_price: Optional[Decimal] = None
	pnl: Decimal
	pnl_rate: Decimal
	last_update: datetime

	def get_average_cost (self) -> Decimal:
		"""计算平均成本"""
		if self.volume > 0:
			return (self.cost_price * self.volume) / self.volume
		return Decimal(0)

	def get_market_value (self, current_price: Decimal) -> Decimal:
		"""计算当前市值"""
		return Decimal(str(current_price)) * self.volume

	def get_pnl (self, current_price: Decimal) -> Decimal:
		"""计算浮动盈亏"""
		if self.volume > 0:
			current_value = current_price * self.volume
			cost_value = self.cost_price * self.volume
			return current_value - cost_value
		return Decimal(0)

	def get_pnl_rate (self, current_price: Decimal) -> Decimal:
		"""计算盈亏率"""
		if self.cost_price > 0:
			return ((current_price - self.cost_price) / self.cost_price) * 100
		return Decimal(0)

	def has_position (self) -> bool:
		"""检查是否有持仓"""
		return self.volume > 0

	def get_available_for_sell (self) -> int:
		"""获取可卖出数量"""
		return self.available_volume


class AccountSnapshot(BaseModel):
	"""账户快照模型"""

	account_id: str
	snapshot_time: datetime
	total_balance: Decimal
	available_balance: Decimal
	frozen_balance: Decimal
	market_value: Decimal
	total_asset: Decimal
	net_asset: Decimal
	positions: List[Dict[str, Any]] = Field(default_factory=list)

	@classmethod
	def create_from_account (cls, account: AccountDomain, positions: List[PositionDomain]):
		"""从账户和持仓创建快照"""
		total_asset = account.total_balance
		net_asset = total_asset - account.frozen_balance

		position_data = [
			{
				"ts_code": p.ts_code,
				"volume": p.volume,
				"market_value": p.market_value,
				"pnl": p.pnl,
				"pnl_rate": float(p.pnl_rate)
			}
			for p in positions
		]

		return cls(
			account_id=account.id,
			snapshot_time=datetime.now(),
			total_balance=account.total_balance,
			available_balance=account.available_balance,
			frozen_balance=account.frozen_balance,
			market_value=account.market_value,
			total_asset=total_asset,
			net_asset=net_asset,
			positions=position_data
		)


class AccountOperation(BaseModel):
	"""账户操作记录模型"""

	account_id: str
	operation_type: str
	amount: Decimal
	reference_id: Optional[str] = None
	description: Optional[str] = None
	timestamp: datetime = Field(default_factory=datetime.now)

	class Config:
		json_encoders = {
			datetime: lambda dt: dt.isoformat(),
			Decimal: lambda d: float(d)
		}


class AssetBreakdown(BaseModel):
	"""资产构成模型"""

	asset_type: str
	asset_name: str
	market_value: Decimal
	weight: Decimal
	cost_basis: Decimal
	pnl: Decimal


class AssetHistory(BaseModel):
	"""资产历史模型"""

	trade_date: date
	total_asset: Decimal
	cash: Decimal
	market_value: Decimal
	daily_pnl: Decimal
	cumulative_pnl: Optional[Decimal] = None
	daily_return: Decimal


class PositionPnL(BaseModel):
	"""持仓盈亏模型"""

	ts_code: str
	position_id: str
	volume: int
	cost_price: Decimal
	last_price: Optional[Decimal] = None
	market_value: Decimal
	cost_basis: Decimal
	unrealized_pnl: Decimal
	unrealized_pnl_rate: Decimal
	realized_pnl: Decimal
	total_pnl: Decimal
	last_update: datetime


class TradePnL(BaseModel):
	"""交易盈亏模型"""

	trade_id: str
	ts_code: str
	direction: str
	volume: int
	price: Decimal
	cost_price: Decimal
	pnl: Decimal
	commission: Decimal
	tax: Decimal
	trade_time: datetime


class DailyPnLSummary(BaseModel):
	"""日度盈亏摘要模型"""

	trade_date: date
	trade_pnl: Decimal
	position_pnl_change: Decimal
	total_pnl: Decimal
	trade_volume: int
	trade_amount: Decimal
	commission: Decimal
	tax: Decimal


class PnLAnalysis(BaseModel):
	"""盈亏分析模型"""

	start_date: date
	end_date: date
	total_trades: int
	win_rate: Decimal
	total_pnl: Decimal
	avg_pnl_per_trade: Decimal
	profit_ratio: Decimal
	max_winning_trade: Decimal
	max_losing_trade: Decimal
	sharpe_ratio: Decimal
	sortino_ratio: Decimal


class IndustryExposure(BaseModel):
	"""行业敞口模型"""

	industry: str
	market_value: Decimal
	weight: Decimal
	stock_count: int
	stocks: List[Dict[str, Any]] = Field(default_factory=list)


class ConcentrationRisk(BaseModel):
	"""集中度风险模型"""

	herfindahl_index: Decimal
	top_n_concentration: Dict[str, Decimal]
	single_stock_limit: Decimal
	is_violated: bool
	max_concentration: Optional[Decimal] = None
	max_concentration_stock: Optional[str] = None


class RiskMetrics(BaseModel):
	"""风险指标模型"""

	account_id: str
	calculation_time: datetime
	industry_exposure: List[IndustryExposure]
	concentration_risk: ConcentrationRisk
	var: Optional[Decimal] = None
	sharpe_ratio: Optional[Decimal] = None
	max_drawdown: Optional[Decimal] = None
	beta: Optional[Decimal] = None
	alpha: Optional[Decimal] = None
	total_asset: Optional[Decimal] = None
	leverage: Optional[Decimal] = None
	max_concentration: Optional[Decimal] = None
	liquidity_ratio: Optional[Decimal] = None
	var_95: Optional[Decimal] = None
	var_percentage: Optional[Decimal] = None
	herfindahl_index: Optional[Decimal] = None
	is_concentration_violated: Optional[bool] = None
	position_count: Optional[int] = None
	industry_count: Optional[int] = None
	total_market_value: Optional[Decimal] = None
	correlation_risk: Optional[Decimal] = None
	total_cash: Optional[Decimal] = None


class VaRResult(BaseModel):
	"""风险价值计算结果模型"""

	var: Decimal
	confidence_level: float
	time_horizon: int
	method: str
	components: List[Dict[str, Any]] = Field(default_factory=list)
	var_percentage: Optional[Decimal] = None