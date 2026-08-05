# -*- coding: utf-8 -*-
"""
回测引擎 — BacktestEngine

================================================================================
职责边界
================================================================================
BacktestEngine 是回测模块的「核心编排器」，参照 Backtrader 的 Cerebro 设计。
负责：
  1. 编排回测流水线：DataFeedEngine → StrategyManager → BacktestBroker
  2. 逐日驱动回测循环（数据推送 → 策略执行 → 信号转订单 → 撮合 → 盯市）
  3. 从 Broker 的 equity_curve + trade_list 计算绩效指标
  4. 结果持久化到数据库（净值曲线、交易记录、持仓快照）
  5. 提供旧接口兼容层（同步 DataFrame 驱动回测、手动策略注册）

================================================================================
架构定位
================================================================================
位置：modules/backtest/engines/          （灵活层 — 业务模块引擎）
继承：core/engines/base/engine_base.py  （EngineBase）

依赖方向（严格单向）：
  modules/backtest/engines/ → modules/strategy/engines/ （DataFeedEngine, StrategyManager）
                            → modules/backtest/engines/ （BacktestBroker, BacktestBrokerConfig）
                            → core/                     （EngineBase, BarData）
                            → numpy / pandas            （绩效计算）

编排模式（v1.1 重构）：
  ┌─────────────────────────────────────────────────────────────┐
  │                      BacktestEngine.run()                    │
  │                                                              │
  │  ① DataFeedEngine.load_historical_data()  ← 加载行情数据     │
  │  ② DataFeedEngine.iter_bars()             ← 按交易日迭代     │
  │  ③ Broker.match_orders()                  ← 撮合昨日挂单     │
  │  ④ StrategyManager.handle_bar_batch()     ← 策略生成信号     │
  │  ⑤ Broker.submit_order()                  ← 信号转订单       │
  │  ⑥ Broker.mark_to_market()                ← 盯市计价         │
  │  ⑦ Broker.get_equity_curve()              ← 收集绩效数据     │
  │  ⑧ _calculate_metrics_from_broker()       ← 计算绩效指标     │
  │  ⑨ _save_results()                        ← 持久化到数据库   │
  └─────────────────────────────────────────────────────────────┘

================================================================================
回测循环日内执行顺序（单日）
================================================================================
match_orders     → 撮合前一日挂单（以今日开盘/第一笔价成交）
handle_bar_batch → 推送今日 BarData 给所有运行中策略，收集信号
submit_order     → 信号转订单（挂单，T+1 成交）
mark_to_market   → 按收盘价重估持仓，更新净值曲线

================================================================================
数据结构
================================================================================
BacktestResult（dataclass）：
  - 核心绩效字段：total_return, annual_return, sharpe_ratio, max_drawdown
  - 交易统计字段：win_rate, profit_factor, num_trades, avg_trade_return
  - 时序数据字段：equity_curve, drawdown_curve, trades, monthly_returns, benchmark_curve

================================================================================
版本历史
================================================================================
v1.1: 重构为编排模式 — 注入 DataFeedEngine + StrategyManager + BacktestBroker
      新增 run() async 逐日循环、_calculate_metrics_from_broker()、
      _save_results() 持久化
v1.0: 初始版本 — 同步 DataFrame 驱动回测、手动策略注册
"""
import logging
from dataclasses import dataclass
from datetime import datetime
from typing import Dict, List, Any, Type

import asyncio
import numpy as np
import pandas as pd

# ---------------------------------------------------------------------------
# 核心框架导入
# ---------------------------------------------------------------------------
from core.engines.base.engine_base import EngineBase
from core.engines.types.entities import BarData, EngineConfigEntity
from modules.backtest.engines.backtest_broker import BacktestBroker, BacktestBrokerConfig
# ---------------------------------------------------------------------------
# 策略模块导入
# ---------------------------------------------------------------------------
from modules.strategy.constants import StrategyType, StrategyLifecycleStatus
from modules.strategy.engines.strategy_manager import StrategyManager
from modules.strategy.engines.data_feed_engine import DataFeedEngine
from modules.strategy.models import (
	StrategyInstance,
	StrategyConfig,
)
from modules.strategy.strategies.base.base_strategy import BaseStrategy
from modules.strategy.strategies.base.strategy_context import StrategyContext

logger = logging.getLogger(__name__)


# =============================================================================
# BacktestResult — 回测结果数据结构
# =============================================================================

@dataclass
class BacktestResult:
	"""
	回测结果数据结构（dataclass）。

	包含两部分数据：
	1. 核心绩效指标 — 总收益、年化收益、夏普比率、最大回撤、胜率等
	2. 时序数据 — 净值曲线、回撤曲线、交易明细、月度收益、基准对比

	使用方式：
		result = BacktestEngine.run(...)           # 返回 BacktestResult
		result_dict = result.to_dict()              # 序列化为 JSON，存入 DB

	Note:
		- __post_init__ 保证列表字段不为 None（避免下游 .append() 报错）
		- monthly_returns / benchmark_curve 当前为占位字段（v1.2+ 计划实现）
	"""

	# ---- 标识 ----
	task_id: str = ""  # 回测任务 ID
	strategy_id: str = ""  # 关联策略 ID

	# ---- 核心绩效指标 ----
	total_return: float = 0.0  # 总收益率（final_assets / initial_capital - 1）
	annual_return: float = 0.0  # 年化收益率（(1 + total_return) ^ (365/days) - 1）
	sharpe_ratio: float = 0.0  # 夏普比率（日收益均值 / 日收益标准差 × √252）
	max_drawdown: float = 0.0  # 最大回撤（历史峰值到当前净值的最低点跌幅）
	win_rate: float = 0.0  # 胜率（盈利交易数 / 总交易数）
	profit_factor: float = 0.0  # 盈亏比（总盈利 / |总亏损|）
	num_trades: int = 0  # 交易总笔数
	avg_trade_return: float = 0.0  # 平均每笔交易收益
	volatility: float = 0.0  # 波动率（日收益率标准差）

	# ---- 时序数据（列表字段，__post_init__ 保证非 None） ----
	equity_curve: List[Dict] = None  # 净值曲线 [{trade_date, total_assets, cumulative_return}, ...]
	drawdown_curve: List[Dict] = None  # 回撤曲线 [{trade_date, drawdown}, ...]
	trades: List[Dict] = None  # 交易明细列表
	monthly_returns: List[Dict] = None  # 月度收益
	benchmark_curve: List[Dict] = None  # 基准对比曲线
	daily_returns: List[Dict] = None  # 每日收益率/盈亏 [{trade_date, daily_return, daily_pnl}]
	daily_turnover: List[Dict] = None  # 每日成交额 [{trade_date, turnover}]

	# ---- v1.4: 基准对比指标 ----
	excess_metrics: Dict = None  # {alpha, beta, information_ratio, tracking_error, excess_annual_return, low_confidence}

	# ---- v3.0: 回测风控违规明细 ----
	risk_violations: List[Dict] = None  # [{ts_code, direction, message, trade_date}]

	def __post_init__(self):
		"""dataclass 初始化后钩子：确保列表字段不为 None，避免下游空指针。"""
		if self.equity_curve is None:
			self.equity_curve = []
		if self.drawdown_curve is None:
			self.drawdown_curve = []
		if self.trades is None:
			self.trades = []
		if self.monthly_returns is None:
			self.monthly_returns = []
		if self.benchmark_curve is None:
			self.benchmark_curve = []
		if self.daily_returns is None:
			self.daily_returns = []
		if self.daily_turnover is None:
			self.daily_turnover = []
		if self.excess_metrics is None:
			self.excess_metrics = {}
		if self.risk_violations is None:
			self.risk_violations = []

	def to_dict(self) -> Dict[str, Any]:
		"""
		序列化为字典，用于 JSON 存入数据库或 API 响应。

		Returns:
			扁平字典，monthly_returns / benchmark_curve 兜底为空列表。
		"""
		return {
			"task_id": self.task_id,
			"strategy_id": self.strategy_id,
			"total_return": self._sanitize_float(self.total_return),
			"annual_return": self._sanitize_float(self.annual_return),
			"sharpe_ratio": self._sanitize_float(self.sharpe_ratio),
			"max_drawdown": self._sanitize_float(self.max_drawdown),
			"win_rate": self._sanitize_float(self.win_rate),
			"profit_factor": self._sanitize_float(self.profit_factor),
			"num_trades": self.num_trades,
			"avg_trade_return": self._sanitize_float(self.avg_trade_return),
			"volatility": self._sanitize_float(self.volatility),
			"equity_curve": self._sanitize_json(self.equity_curve),
			"drawdown_curve": self._sanitize_json(self.drawdown_curve),
			"trades": self._sanitize_json(self.trades),
			"monthly_returns": self._sanitize_json(self.monthly_returns or []),
			"benchmark_curve": self._sanitize_json(self.benchmark_curve or []),
			"daily_returns": self._sanitize_json(self.daily_returns or []),
		"daily_turnover": self._sanitize_json(self.daily_turnover or []),
		"excess_metrics": self.excess_metrics or {},
			"risk_violations": self._sanitize_json(self.risk_violations or []),
		}

	@staticmethod
	def _sanitize_json(obj):
		"""递归转换 date/datetime 为 ISO 字符串，确保 JSONB 兼容。"""
		from datetime import date, datetime as dt
		if isinstance(obj, (dt, date)):
			return obj.isoformat()
		if isinstance(obj, dict):
			return {k: BacktestResult._sanitize_json(v) for k, v in obj.items()}
		if isinstance(obj, list):
			return [BacktestResult._sanitize_json(i) for i in obj]
		if isinstance(obj, float):
			return BacktestResult._sanitize_float(obj)
		return obj

	@staticmethod
	def _sanitize_float(v):
		"""Replace NaN/Inf with 0.0 for PostgreSQL JSONB compatibility."""
		import math
		if isinstance(v, float) and (math.isnan(v) or math.isinf(v)):
			return 0.0
		return v


# =============================================================================
# BacktestEngine — 回测核心编排器
# =============================================================================

class BacktestEngine(EngineBase):
	"""
	回测引擎（v1.1 重构 — 编排模式）。

	职责变化：
		之前（v1.0）：自己加载策略 + 自己驱动循环 + 自己计算指标
		之后（v1.1）：编排 DataFeedEngine + StrategyManager + BacktestBroker

	参照：Backtrader 的 Cerebro — 回测的 orchestrator，只做编排不做具体实现。

	核心方法：
		run()               — 单策略回测（v1.1 异步编排链路）
		run_multi()         — 多策略并行回测（每策略独立虚拟账户）
		run_backtest()      — 旧接口兼容层（同步 DataFrame 驱动）

	Attributes:
		data_feed:         DataFeedEngine 引用（注入），负责数据加载和迭代
		strategy_manager:  StrategyManager 引用（注入），负责策略生命周期和 on_bar 分发
		broker:            BacktestBroker 引用（注入），负责虚拟账户 / 撮合 / 盯市
		strategies:        策略实例字典 {strategy_id: StrategyInstance}
		_strategy_registry: 策略类注册表 {StrategyType: BaseStrategy subclass}
		results:           回测结果缓存 {strategy_id: result_dict}
		_data_cache:       数据缓存 {key: DataFrame}
		_strategy_instances: 策略对象缓存 {strategy_id: BaseStrategy 实例}
	"""

	def __init__(
			self,
			config=None,
			event_engine=None,
			resource_pool=None,
			data_feed: DataFeedEngine = None,
			strategy_manager: StrategyManager = None,
			broker: BacktestBroker = None,
	):
		"""
		初始化回测引擎。

		Args:
			config: EngineConfigEntity，引擎配置（名称、类型等），缺省时自动创建。
			event_engine: 事件引擎（可选），用于进度推送和模块间通信。
			resource_pool: 资源池（可选），共享资源管理。
			data_feed: **注入** DataFeedEngine，负责行情数据加载与迭代。
			strategy_manager: **注入** StrategyManager，负责策略生命周期管理。
			broker: **注入** BacktestBroker，负责虚拟账户 / 撮合 / 盯市。
				   若为 None，run() 会在运行时自动创建默认配置的 Broker。
		"""
		if config is None:
			config = EngineConfigEntity(
				name="BacktestEngine", engine_type="backtest"
			)
		super().__init__(
			config=config, event_engine=event_engine, resource_pool=resource_pool
		)

		# ---- v1.1 注入的三个核心组件（依赖反转，外部组装） ----
		self.data_feed = data_feed
		self.strategy_manager = strategy_manager
		self.broker = broker

		# ---- 策略实例管理 ----
		self.strategies: Dict[str, StrategyInstance] = {}
		self._strategy_registry: Dict[StrategyType, Type[BaseStrategy]] = {}

		# ---- 结果与缓存 ----
		self.results: Dict[str, Dict[str, Any]] = {}
		self._data_cache: Dict[str, pd.DataFrame] = {}
		self._strategy_instances: Dict[str, BaseStrategy] = {}

	# ---- 公开 API：DB 会话注入（v1.3 新增） ----

	# ---- 进度更新（v1.3 新增） ----

	async def _update_task_progress(self, task_id: str, pct: int) -> None:
		"""更新回测任务的进度百分比到 DB（供前端轮询使用）。"""
		try:
			db = getattr(self, "_db_session", None)
			if db is None:
				return
			from sqlalchemy import update
			from shared.database.models.business_models import BacktestTask
			from datetime import datetime
			stmt = (
				update(BacktestTask)
				.where(BacktestTask.id == task_id)
				.values(progress=pct, updated_at=datetime.now())
			)
			await db.execute(stmt)
			await db.commit()
		except Exception as e:
			logger.warning(f"进度更新失败 ({task_id} {pct}%): {e}")

	def set_db_session(self, session) -> None:
		"""
		注入数据库会话（供 BacktestService 在后台任务中调用）。

		替代直接访问 protected 成员 _db_session。
		每个回测任务拥有独立的 DB 会话，避免跨请求 session 关闭问题。

		Args:
		    session: AsyncSession 实例
		"""
		self._db_session = session

	# =========================================================================
	# v1.1 核心回测方法
	# =========================================================================

	async def run(
			self,
			task_id: str,
			strategy_id: str,
			symbols: List[str],
			start_date: str,
			end_date: str,
			initial_capital: float = 1_000_000,
			parameters: Dict[str, Any] = None,
			commission_rate: float = 0.0001,
			slippage: float = 0.001,
			benchmark_ts_code: str = None,
	) -> BacktestResult:
		"""
		执行一次完整回测（v1.1 异步编排链路）。

		┌────────────────────────────────────────────────────────────────┐
		│ 流程（9 步）：                                                  │
		│                                                                │
		│ 第 1 步：配置 Broker                                            │
		│   └─ 创建 BacktestBrokerConfig → 设置初始资金/佣金/滑点         │
		│   └─ 若外部未注入 Broker，自动创建；否则复用并 reset            │
		│                                                                │
		│ 第 2 步：检查策略是否已在 StrategyManager 中注册                │
		│   └─ 若未注册则打 warn 日志（上游应在调用前完成注册）           │
		│                                                                │
		│ 第 3 步：通过 DataFeedEngine 加载历史行情数据                    │
		│   └─ load_historical_data(symbols, start_date, end_date)       │
		│   └─ 返回 DataFrame，若为空则返回空 BacktestResult              │
		│                                                                │
		│ 第 4 步：统计交易日 → 逐日回测循环                              │
		│   └─ iter_bars(df) 按交易日分组迭代 BarData 列表                │
		│   └─ 每个交易日内执行以下子步骤：                               │
		│     4a. match_orders()    — 撮合前一日挂单（T+1 成交）          │
		│     4b. handle_bar_batch() — 推送 BarData → 策略产生信号        │
		│     4c. submit_order()    — 信号转订单（价格/数量兜底处理）     │
		│     4d. mark_to_market()  — 按收盘价重估持仓，更新净值          │
		│   └─ 进度日志：每 10%/25%/50%/75%/90% 输出一次                  │
		│                                                                │
		│ 第 5 步：计算绩效指标                                            │
		│   └─ 从 Broker.get_equity_curve() + get_trade_list() 获取原始   │
		│   └─ _calculate_metrics_from_broker() 计算所有指标              │
		│                                                                │
		│ 第 6 步：持久化到数据库                                          │
		│   └─ _save_results() 写入 equity_curves + trades 表             │
		│                                                                │
		│ 第 7 步：返回 BacktestResult                                    │
		└────────────────────────────────────────────────────────────────┘

		Args:
			task_id: 回测任务 ID（UUID 字符串）。
			strategy_id: 策略 ID，用于关联 StrategyManager 中的策略实例。
			symbols: 股票代码列表，如 ["000001.SZ", "600000.SH"]。
			start_date: 回测起始日期（YYYY-MM-DD）。
			end_date: 回测结束日期（YYYY-MM-DD）。
			initial_capital: 初始资金，默认 100 万。
			parameters: 策略参数字典（传递给策略实例），默认 None。
			commission_rate: 佣金费率，默认万一（0.0001），万一免五。
			slippage: 滑点比例，默认千一（0.001）。

		Returns:
			BacktestResult 包含完整的绩效指标和时序数据。

		Note:
			- 信号 → 订单时会做价格/数量兜底处理：
			  price=0 → 使用当日 bar 的收盘价
			  quantity=0 且 amount>0 → 按资金分配计算股数 integer(amount/price)
			- DataFeedEngine 为 None 时直接返回空结果（不抛异常，
			  兼容无数据环境的测试场景）
		"""
		# ---- 延迟导入避免循环依赖 ----
		from modules.backtest.engines.backtest_broker import (
			BacktestBroker,
			BacktestBrokerConfig,
		)

		# =====================================================================
		# 第 1 步：配置 Broker（创建或复用，确保从干净状态开始）
		# =====================================================================
		broker_config = BacktestBrokerConfig(
			initial_capital=initial_capital,
			commission_rate=commission_rate,
			slippage=slippage,
		)
		broker = self.broker or BacktestBroker(config=broker_config)
		broker.reset(initial_capital)
		self._data_cache.clear()  # v2.4: 多次回测间释放积压数据，防止内存泄漏

		# =====================================================================
		# 第 2 步：检查策略注册状态
		# =====================================================================
		manager = self.strategy_manager
		if manager and strategy_id not in manager.strategies:
			logger.warning(f"策略 {strategy_id} 未在 StrategyManager 中加载，尝试直接注册")

		# =====================================================================
		# 第 3 步：加载历史行情数据 + 基准指数数据（顺序执行）
		#
		# v1.4: 基准数据与策略数据先后加载。不使用 asyncio.gather 并行，
		# 因为两次调用共用同一个 DataFeedEngine/AsyncSession，并发查询
		# 会破坏 session 事务状态，导致后续 _update_task_progress 的
		# db.commit() 静默失败，前端轮询永远读到 progress=0。
		# =====================================================================
		if not self.data_feed:
			logger.error("DataFeedEngine 未注入，无法加载数据")
			return BacktestResult(task_id=task_id, strategy_id=strategy_id)

		df = await self.data_feed.load_historical_data(
			symbols=symbols,
			start_date=start_date,
			end_date=end_date,
		)

		bm_df = None
		if benchmark_ts_code:
			logger.info(f"加载基准数据: {benchmark_ts_code} ({start_date}~{end_date})")
			bm_df = await self._load_benchmark_data(
				benchmark_ts_code, start_date, end_date
			)
			if bm_df is not None and not bm_df.empty:
				logger.info(f"基准数据已加载: {benchmark_ts_code} ({len(bm_df)} 行)")
			else:
				logger.warning(f"基准数据为空: {benchmark_ts_code}，三源（stock/index/etf）均无数据")

		if df.empty:
			logger.warning(f"回测数据为空: {symbols} {start_date}~{end_date}")
			return BacktestResult(task_id=task_id, strategy_id=strategy_id)

		# ---- 交易日统计 ----
		trading_days = sorted(df["trade_date"].unique())
		total_days = len(trading_days)
		logger.info(
			f"回测 {task_id}: 数据加载完成, {len(symbols)} 只股票, "
			f"{df.shape[0]} 行, {total_days} 个交易日 "
			f"({trading_days[0]} ~ {trading_days[-1]})"
			f"{f', 基准={benchmark_ts_code}' if benchmark_ts_code else ''}"
		)

		# =====================================================================
		# 第 4 步：逐日回测循环
		#
		# 使用 DataFeedEngine.iter_bars() 异步迭代器按交易日分组 BarData。
		# 每日执行顺序（与 Backtrader 一致）：
		#   match_orders → handle_bar_batch → submit_order → mark_to_market
		#
		# 关键设计：
		#   - 信号当日产生，订单 T+1 成交（match_orders 撮合前一日的挂单）
		#   - mark_to_market 以当日收盘价重估所有持仓
		#   - 进度日志在关键里程碑（10%/25%/50%/75%/90%）输出
		# =====================================================================
		day_idx = 0
		progress_milestones = {int(total_days * p) for p in (0.1, 0.25, 0.5, 0.75, 0.9)}
		signal_count = 0

		async for trade_date, bars in self.data_feed.iter_bars(df):
			# v1.3: 取消检查点 — 每交易日检查是否被外部取消
			cancel_event = getattr(self, "_cancel_event", None)
			if cancel_event and cancel_event.is_set():
				logger.info(f"回测 {task_id}: 收到取消信号，在第 {day_idx} 个交易日停止")
				raise asyncio.CancelledError(f"回测 {task_id} 被用户取消")
			day_idx += 1

			# 构建 bar_dict（{ts_code: BarData}），供撮合和盯市快速查找
			bar_dict = {b.ts_code: b for b in bars}

			# ---- 4a. 撮合昨日挂单（T+1 成交） ----
			broker.match_orders(trade_date, bar_dict)

			# ---- 4b. 推送 BarData 给策略 → 生成信号 ----
			day_signals = 0
			if manager:
				signals = await manager.handle_bar_batch(trade_date, bars)

			# ---- 4c. 信号转订单（v1.5: Sizer 计算数量 → Broker 挂单） ----
			from modules.backtest.engines.sizer import select_sizer

			for sig in signals:
				ts_code = getattr(sig, "ts_code", "")
				direction = (
					sig.direction.value
					if hasattr(sig, "direction") and hasattr(sig.direction, "value")
					else str(sig.direction)
				)
				price = getattr(sig, "price", 0.0) or 0.0

				# 价格兜底
				if price <= 0 and ts_code in bar_dict:
					price = float(bar_dict[ts_code].close or 0.0)
				if price <= 0:
					continue

				# Sizer 计算数量（策略层不关心具体股数）
				sizer = select_sizer(sig)
				current_qty = 0
				pos = broker.positions.get(ts_code)
				if pos:
					current_qty = pos.quantity
				quantity = sizer.calculate(sig, bar_dict.get(ts_code), broker.cash, current_qty)
				if quantity <= 0:
					continue

				reason = getattr(sig, "reason", "") or ""
				order_mode = getattr(sig, "order_mode", "open") or "open"
				trigger_price = getattr(sig, "trigger_price", None)
				await broker.submit_order(
					ts_code, direction, price, quantity,
					reason=reason, order_mode=order_mode, trigger_price=trigger_price,
				)
				signal_count += 1
				day_signals += 1
			# ---- v6.11: 结算当日 close/trigger 单（收盘确认买入 / 日内止损） ----
			broker.settle_intraday_orders(bar_dict, trade_date=trade_date)
			# ---- 4d. 盯市计价（按当日收盘价重估持仓，更新净值曲线） ----
			broker.mark_to_market(bar_dict, trade_date=trade_date)

			# ---- 当日信号（仅DEBUG级别，里程碑用INFO） ----
			if day_signals and logger.isEnabledFor(logging.DEBUG):
				snap = broker.get_account_snapshot()
				logger.debug(
					f"回测 {task_id}: [{trade_date}] "
					f"信号={len(day_signals)}, 权益={snap['total_assets']:,.0f}, "
					f"收益={snap['total_return']:+.2%}"
				)

			# ---- 进度日志 + DB 进度更新（v1.3） ----
			if day_idx in progress_milestones:
				pct = day_idx * 100 // total_days
				snap = broker.get_account_snapshot()
				logger.info(
					f"回测 {task_id}: 进度 {pct}% ({day_idx}/{total_days}), "
					f"权益={snap['total_assets']:,.0f}, "
					f"收益={snap['total_return']:+.2%}, "
					f"信号累计={signal_count}"
				)
				# 更新 DB 进度，前端轮询可见
				await self._update_task_progress(task_id, pct)

		# =====================================================================
		# 第 5 步：从 Broker 获取原始绩效数据 → 计算所有指标
		# =====================================================================
		equity_df = broker.get_equity_curve()
		trades = broker.get_trade_list()
		result = self._calculate_metrics_from_broker(
			task_id=task_id,
			strategy_id=strategy_id,
			equity_df=equity_df,
			trades=trades,
			initial_capital=initial_capital,
		)

		# 基准曲线计算（v1.4: 使用 Step 3 预加载的 bm_df，无需再次 DB 查询）
		if bm_df is not None and not bm_df.empty:
			result.benchmark_curve = self._build_benchmark_curve(
				bm_df=bm_df,
				initial_capital=initial_capital,
			)
		elif benchmark_ts_code:
			logger.warning(f"基准数据为空: {benchmark_ts_code}")

		# 超额收益指标（v1.4: 基准非空时计算 Alpha / Beta / 信息比率）
		if result.benchmark_curve:
			result.excess_metrics = self._calculate_excess_metrics(
				result=result,
				benchmark_curve=result.benchmark_curve,
				annual_return=result.annual_return,
			)
			logger.info(
				f"超额指标已计算: alpha={result.excess_metrics.get('alpha', '?')}, "
				f"beta={result.excess_metrics.get('beta', '?')}, "
				f"bm_annual={result.excess_metrics.get('benchmark_annual_return', '?')}"
			)

		# =====================================================================
		# 第 6 步：收集风控违规明细（v3.0）
		# =====================================================================
		if self.broker:
			result.risk_violations = self.broker.get_risk_violations()
			if result.risk_violations:
				logger.info(f"收集到 {len(result.risk_violations)} 条风控违规记录")

		# =====================================================================
		# 第 7 步：结果持久化到数据库
		# =====================================================================
		await self._save_results(result, equity_df, trades)

		# =====================================================================
		# 第 8 步：日志输出核心指标摘要
		# =====================================================================
		logger.info(
			f"回测完成: {task_id} "
			f"总收益={result.total_return:.2%} "
			f"夏普={result.sharpe_ratio:.2f} "
			f"最大回撤={result.max_drawdown:.2%}"
		)

		return result

	# =========================================================================
	# 多策略并行回测
	# =========================================================================

	async def run_multi(
			self,
			task_id: str,
			strategy_configs: List[Dict],
			symbols: List[str],
			start_date: str,
			end_date: str,
	) -> List[BacktestResult]:
		"""
		多策略并行回测。

		每个策略拥有独立的虚拟账户（Broker 在 run() 内部创建），
		但共享同一份历史行情数据（DataFeedEngine 的 load_historical_data
		不重复拉取，仅查询一次）。

		Args:
			task_id: 父级任务 ID（各子任务 ID = {task_id}_{strategy_id}）。
			strategy_configs: 策略配置列表，每项包含：
				- strategy_id: 策略 ID
				- initial_capital: 初始资金（可选，默认 100 万）
				- parameters: 策略参数字典（可选）
			symbols: 股票代码列表（所有策略共享）。
			start_date / end_date: 回测区间。

		Returns:
			List[BacktestResult] — 成功完成的结果列表（异常策略会被过滤掉）。

		Note:
			- v1.3 起改为顺序执行，避免共享 StrategyManager/Broker 的并发竞态。
			  如需并发，请使用独立 BacktestEngine 实例 + asyncio.gather。
		"""
		# v1.3: 顺序执行（避免共享 StrategyManager/Broker 竞态）
		results = []
		for cfg in strategy_configs:
			try:
				r = await self.run(
					task_id=f"{task_id}_{cfg.get('strategy_id', 'unknown')}",
					strategy_id=cfg["strategy_id"],
					symbols=symbols,
					start_date=start_date,
					end_date=end_date,
					initial_capital=cfg.get("initial_capital", 1_000_000),
					parameters=cfg.get("parameters"),
				)
				results.append(r)
			except Exception as e:
				logger.error(f"多策略回测 [{cfg.get('strategy_id')}] 失败: {e}")
		return results
	# =========================================================================
	# 组合回测 — 多策略共享资金池 + CapitalAllocator 动态分配
	# =========================================================================

	async def run_composite(
		self,
		task_id: str,
		strategy_configs: List[Dict],
		symbols: List[str],
		start_date: str,
		end_date: str,
		initial_capital: float = 1_000_000,
		commission_rate: float = 0.0001,
		slippage: float = 0.001,
		benchmark_ts_code: str = None,
		allocator_params: Dict[str, Any] = None,
		force_regime: int = None,
	) -> "BacktestResult":
		"""
		多策略组合回测 — 所有策略共享一个 Broker，按 Regime 动态分配资金。

		与 run_multi() 的核心区别：
		- run_multi: 每个策略独立 Broker，各自生成净值曲线（并行但隔离）
		- run_composite: 所有策略共享一个 Broker，一条净值曲线（真正的组合）

		逐日循环:
		  match_orders → allocator.rebalance() → handle_bar_batch
		  → allocator.scale_signals() → submit_order → mark_to_market

		Args:
			task_id: 回测任务 ID。
			strategy_configs: 策略配置列表，每项包含:
				- strategy_id: 策略 ID
				- allocator_id: 分配器中的权重键
				- parameters: 策略参数字典（可选）
			symbols: 股票代码列表（合并所有策略的 Universe）。
			start_date / end_date: 回测区间。
			initial_capital: 共享初始资金。
			allocator_params: CapitalAllocator 参数。
			force_regime: P0 固定 Regime（None=默认RANGE）。

		Returns:
			BacktestResult — 组合净值曲线的完整绩效指标。
		"""
		from modules.backtest.engines.backtest_broker import (
			BacktestBroker,
			BacktestBrokerConfig,
		)
		from modules.strategy.engines.capital_allocator import CapitalAllocator

		broker_config = BacktestBrokerConfig(
			initial_capital=initial_capital,
			commission_rate=commission_rate,
			slippage=slippage,
		)
		broker = self.broker or BacktestBroker(config=broker_config)
		broker.reset(initial_capital)
		self._data_cache.clear()

		manager = self.strategy_manager
		if not manager:
			raise RuntimeError("StrategyManager 未注入，无法运行组合回测")

		strategy_ids = []
		allocator_id_map: Dict[str, str] = {}
		for cfg in strategy_configs:
			sid = cfg["strategy_id"]
			aid = cfg.get("allocator_id", sid)
			strategy_ids.append(sid)
			allocator_id_map[sid] = aid
			if sid not in manager.strategies:
				logger.warning(
					f"策略 {sid} 未注册, 请在上游完成注册"
				)

		alloc_ids = list(dict.fromkeys(allocator_id_map.values()))
		allocator = CapitalAllocator(
			strategy_ids=alloc_ids,
			allocator_params=allocator_params,
			force_regime=force_regime,
		)
		logger.info(
			f"组合回测 {task_id}: {len(strategy_ids)} 策略, "
			f"allocator_ids={alloc_ids}, force_regime={force_regime}"
		)

		if not self.data_feed:
			logger.error("DataFeedEngine 未注入")
			return BacktestResult(task_id=task_id, strategy_id="composite")

		df = await self.data_feed.load_historical_data(
			symbols=symbols,
			start_date=start_date,
			end_date=end_date,
		)

		bm_df = None
		if benchmark_ts_code:
			bm_df = await self._load_benchmark_data(
				benchmark_ts_code, start_date, end_date
			)

		if df.empty:
			logger.warning(f"组合回测数据为空")
			return BacktestResult(task_id=task_id, strategy_id="composite")

		trading_days = sorted(df["trade_date"].unique())
		total_days = len(trading_days)
		logger.info(
			f"组合回测 {task_id}: {len(symbols)} 标的, "
			f"{df.shape[0]} 行, {total_days} 交易日"
		)

		day_idx = 0
		progress_milestones = {
			int(total_days * p) for p in (0.1, 0.25, 0.5, 0.75, 0.9)
		}
		signal_count = 0

		async for trade_date, bars in self.data_feed.iter_bars(df):
			cancel_event = getattr(self, "_cancel_event", None)
			if cancel_event and cancel_event.is_set():
				raise asyncio.CancelledError(f"组合回测 {task_id} 被取消")
			day_idx += 1

			bar_dict = {b.ts_code: b for b in bars}

			broker.match_orders(trade_date, bar_dict)
			allocator.rebalance(trade_date, bar_dict)
			signals = await manager.handle_bar_batch(trade_date, bars)

			# ---- 信号权重缩放 + 统计 ----
			scale_stats: Dict[str, int] = {}
			for sig in signals:
				sid = getattr(sig, "strategy_id", "")
				if sid and sid in allocator_id_map:
					aid = allocator_id_map[sid]
					w = allocator.get_weight(aid)
					orig_w = getattr(sig, "weight", 1.0) or 1.0
					sig.weight = orig_w * w
					scale_stats[aid] = scale_stats.get(aid, 0) + 1

			# ---- 每日信号日志（首日或有信号时 INFO） ----
			if scale_stats:
				snap = broker.get_account_snapshot()
				logger.info(
					f"组合 {task_id} [{trade_date}] "
					f"regime={allocator.regime} alloc={allocator.allocation} "
					f"信号={scale_stats} 现金={broker.cash:,.0f} 权益={snap['total_assets']:,.0f}"
				)

			from modules.backtest.engines.sizer import select_sizer
			day_signals = 0
			for sig in signals:
				ts_code = getattr(sig, "ts_code", "")
				direction = (
					sig.direction.value
					if hasattr(sig, "direction")
					and hasattr(sig.direction, "value")
					else str(sig.direction)
				)
				price = getattr(sig, "price", 0.0) or 0.0
				if price <= 0 and ts_code in bar_dict:
					price = float(bar_dict[ts_code].close or 0.0)
				if price <= 0:
					continue
				sizer = select_sizer(sig)
				current_qty = 0
				pos = broker.positions.get(ts_code)
				if pos:
					current_qty = pos.quantity
				quantity = sizer.calculate(
					sig, bar_dict.get(ts_code), broker.cash, current_qty
				)
				if quantity <= 0:
					continue
				reason = getattr(sig, "reason", "") or ""
				order_mode = getattr(sig, "order_mode", "open") or "open"
				trigger_price = getattr(sig, "trigger_price", None)
				await broker.submit_order(
					ts_code, direction, price, quantity,
					reason=reason, order_mode=order_mode, trigger_price=trigger_price,
				)
				signal_count += 1
				day_signals += 1

			broker.settle_intraday_orders(bar_dict, trade_date=trade_date)
			broker.mark_to_market(bar_dict, trade_date=trade_date)

			if day_idx in progress_milestones:
				pct = day_idx * 100 // total_days
				snap = broker.get_account_snapshot()
				logger.info(
					f"组合回测 {task_id}: {pct}% ({day_idx}/{total_days}), "
					f"权益={snap['total_assets']:,.0f}, "
					f"信号={signal_count}, regime={allocator.regime}, "
					f"alloc={allocator.allocation}"
				)
				await self._update_task_progress(task_id, pct)

		equity_df = broker.get_equity_curve()
		trades = broker.get_trade_list()
		composite_id = "composite_" + "_".join(strategy_ids)
		result = self._calculate_metrics_from_broker(
			task_id=task_id,
			strategy_id=composite_id,
			equity_df=equity_df,
			trades=trades,
			initial_capital=initial_capital,
		)

		if bm_df is not None and not bm_df.empty:
			result.benchmark_curve = self._build_benchmark_curve(
				bm_df=bm_df, initial_capital=initial_capital
			)

		if self.broker:
			result.risk_violations = self.broker.get_risk_violations()
		await self._save_results(result, equity_df, trades)

		logger.info(
			f"组合回测完成: {task_id} "
			f"收益={result.total_return:.2%} "
			f"夏普={result.sharpe_ratio:.2f} "
			f"回撤={result.max_drawdown:.2%}"
		)

		return result



	# =========================================================================
	# 绩效计算（v1.1 — 从 Broker 的 equity_curve + trades 计算）
	# =========================================================================

	def _calculate_metrics_from_broker(
			self,
			task_id: str,
			strategy_id: str,
			equity_df: pd.DataFrame,
			trades: List[Dict],
			initial_capital: float,
	) -> BacktestResult:
		"""
		从 Broker 的净值曲线和交易记录计算所有绩效指标。

		计算指标：
		┌───────────────────┬──────────────────────────────────────────────┐
		│ 指标              │ 计算方式                                     │
		├───────────────────┼──────────────────────────────────────────────┤
		│ total_return      │ (final_assets - initial_capital) / initial   │
		│ annual_return     │ (1 + total_return) ^ (365 / trading_days) - 1│
		│ sharpe_ratio      │ mean(daily_returns) / std(daily_returns)     │
		│                   │ × √252                                       │
		│ max_drawdown      │ max(equity_df["max_drawdown"])（由 Broker    │
		│                   │ mark_to_market 中实时计算）                   │
		│ volatility        │ std(daily_returns)                           │
		│ win_rate          │ 盈利交易数 / 总交易数                        │
		│ profit_factor     │ 总盈利 / |总亏损|                             │
		│ avg_trade_return  │ sum(trade_pnls) / len(trade_pnls)            │
		│ num_trades        │ len(trades)                                  │
		└───────────────────┴──────────────────────────────────────────────┘

		Args:
			task_id: 任务 ID。
			strategy_id: 策略 ID。
			equity_df: Broker 的净值曲线 DataFrame（含 total_assets,
					   cumulative_return, max_drawdown 列）。
			trades: Broker 的交易明细列表。
			initial_capital: 初始资金。

		Returns:
			填充了所有指标字段的 BacktestResult。

		Note:
			- 交易盈亏计算当前为简化版（仅计算手续费/印花税等成本），
			  完整的买卖配对盈亏待 v1.2+ 实现。
			- 当 equity_df 为空时，返回仅有 task_id/strategy_id 的空结果。
		"""
		result = BacktestResult(task_id=task_id, strategy_id=strategy_id)
		result.trades = trades

		# 无净值数据 → 返回空结果
		if equity_df.empty:
			return result

		# ---- 净值曲线序列化 ----
		result.equity_curve = equity_df[
			["trade_date", "total_assets", "cumulative_return"]
		].to_dict("records")

		# ---- 总收益率 ----
		if len(equity_df) > 0:
			final_assets = equity_df["total_assets"].iloc[-1]
			result.total_return = (
				(final_assets - initial_capital) / initial_capital
				if initial_capital > 0
				else 0.0
			)

		# ---- 年化收益率 + 夏普比率 + 波动率 ----
		if len(equity_df) >= 2:
			# v1.3: 使用交易日数（而非日历天数）计算年化收益
			trading_days = len(equity_df)
			if result.total_return <= -1:
				result.annual_return = -1.0
			else:
				result.annual_return = (1 + result.total_return) ** (252 / max(trading_days, 1)) - 1

			# 日收益率序列（v1.3: 使用总资产的百分比变化 pct_change）
			daily_returns = equity_df["total_assets"].pct_change().dropna()
			if len(daily_returns) > 1:
				result.volatility = float(daily_returns.std())
				if result.volatility > 0:
					result.sharpe_ratio = float(
						daily_returns.mean() / result.volatility * np.sqrt(252)
					)

		# ---- 最大回撤（Broker 在 mark_to_market 中已实时追踪） ----
		if "max_drawdown" in equity_df.columns:
			result.max_drawdown = float(equity_df["max_drawdown"].max())

		# ---- 回撤曲线（v1.5: 逐点当前回撤，非累计最大值） ----
		peak = initial_capital
		dds = []
		for _, row in equity_df.iterrows():
			ta = float(row["total_assets"])
			if ta > peak:
				peak = ta
			dd = (peak - ta) / peak if peak > 0 else 0.0
			dds.append({"trade_date": str(row["trade_date"])[:10], "drawdown": round(dd, 6)})
		result.drawdown_curve = dds

		# ---- 交易分析 ----
		result.num_trades = len(trades)
		if trades:
			# v1.3: 买卖配对盈亏计算（FIFO 匹配）
			# 按股票分组，每只股票内按时间排序，FIFO 匹配买卖
			trade_pnls = self._calculate_trade_pnls_fifo(trades)

			wins = [p for p in trade_pnls if p > 0]
			losses = [p for p in trade_pnls if p <= 0]
			result.win_rate = len(wins) / len(trade_pnls) if trade_pnls else 0
			if losses and sum(losses) != 0:
				result.profit_factor = sum(wins) / abs(sum(losses))
			elif wins:
				result.profit_factor = 999999.0  # 全胜，无亏损
			else:
				result.profit_factor = 0.0
			result.avg_trade_return = (
				sum(trade_pnls) / len(trade_pnls) if trade_pnls else 0.0
			)

		# ---- 每日收益率（供前端每日盈亏图使用） ----
		if len(equity_df) >= 2:
			daily_rets = equity_df[["trade_date", "total_assets"]].copy()
			daily_rets["daily_return"] = daily_rets["total_assets"].pct_change()
			daily_rets["daily_pnl"] = daily_rets["total_assets"].diff()
			result.daily_returns = (
				daily_rets[["trade_date", "daily_return", "daily_pnl"]]
				.dropna()
				.to_dict("records")
			)
		else:
			result.daily_returns = []

		# ---- 每日成交额（从 trades 按交易日聚合） ----
		if trades:
			from collections import defaultdict
			daily_amt = defaultdict(float)
			for t in trades:
				raw = t.get("trade_date") or t.get("datetime") or ""
				d = str(raw)[:10] if raw else ""
				if d:
					daily_amt[d] += float(t.get("amount", 0) or 0)
			result.daily_turnover = [
				{"trade_date": k, "turnover": round(v, 2)}
				for k, v in sorted(daily_amt.items())
			]
		else:
			result.daily_turnover = []

		# ---- 月度收益（v1.5: 按月分组计算，排除首尾不完整月份） ----
		if len(equity_df) >= 2:
			equity_df_copy = equity_df.copy()
			equity_df_copy["month"] = equity_df_copy["trade_date"].astype(str).str[:7]
			monthly_groups = equity_df_copy.groupby("month")  # DataFrame groupby，get_group 返回 DataFrame
			months = sorted(monthly_groups.groups.keys())
			monthly = []
			for i, m in enumerate(months):
				try:
					grp = monthly_groups.get_group(m)
				except Exception:
					continue
				if i == 0 or i == len(months) - 1:
					if len(grp) < 10:
						continue
				start_eq = float(grp["total_assets"].iloc[0])
				end_eq = float(grp["total_assets"].iloc[-1])
				ret = (end_eq - start_eq) / start_eq if start_eq > 0 else 0.0
				monthly.append({"month": m, "return": round(ret, 6)})
			result.monthly_returns = monthly
			if monthly:
				logger.info(f"月度收益: {len(monthly)}/{len(months)} 个完整月份")

		return result

	async def _load_benchmark_data(
		self, ts_code: str, start_date: str, end_date: str
	) -> pd.DataFrame:
		"""统一基准数据加载：按 stock / index / ETF 三源依次 fallback 查询。

		三类数据源分别对应不同表：
		  ① stock_adjusted_prices — 个股（如 600519.SH）
		  ② index_daily           — 指数（如 000300.SH）
		  ③ etf_daily             — ETF （如 510300.SH）
		只要任一个表返回数据即停止，均无数据时返回空 DataFrame。
		"""
		try:
			db = getattr(self, "_db_session", None)
			if db is None:
				return pd.DataFrame()
			from sqlalchemy import text
			from datetime import date as _date_class
			sd = _date_class.fromisoformat(start_date) if isinstance(start_date, str) else start_date
			ed = _date_class.fromisoformat(end_date) if isinstance(end_date, str) else end_date

			# 统一查询模板：各表列名不同但都可以映射到统一输出列
			sources = [
				(
					"stock_adjusted_prices",
					"SELECT ts_code, trade_date, open, high, low, close, vol, amount "
					"FROM stock_adjusted_prices "
					"WHERE ts_code = :code AND trade_date BETWEEN :start AND :end "
					"AND adj_type = 'qfq' AND freq = 'D' "
					"ORDER BY trade_date ASC",
				),
				(
					"index_daily",
					"SELECT ts_code, trade_date, open, high, low, close, vol, amount "
					"FROM index_daily "
					"WHERE ts_code = :code AND trade_date BETWEEN :start AND :end "
					"ORDER BY trade_date ASC",
				),
				(
					"etf_daily",
					"SELECT ts_code, trade_date, open, high, low, close, vol, amount "
					"FROM etf_daily "
					"WHERE ts_code = :code AND trade_date BETWEEN :start AND :end "
					"ORDER BY trade_date ASC",
				),
			]

			params = {"code": ts_code, "start": sd, "end": ed}
			for table_name, query in sources:
				try:
					result = await db.execute(text(query), params)
					rows = result.fetchall()
					if rows:
						logger.info(f"基准数据来源: {table_name} ({len(rows)} 行)")
						return pd.DataFrame([
							{
								"ts_code": r.ts_code,
								"trade_date": r.trade_date,
								"open": float(r.open or 0),
								"high": float(r.high or 0),
								"low": float(r.low or 0),
								"close": float(r.close or 0),
								"volume": float(r.vol or 0),
								"amount": float(r.amount or 0),
							}
							for r in rows
						])
				except Exception:
					continue  # 表不存在或字段不匹配，尝试下一个
			logger.warning(f"基准数据: 三源均无 {ts_code} 数据 ({sd}~{ed})")
			return pd.DataFrame()
		except Exception as e:
			logger.warning(f"加载基准数据失败 ({ts_code}): {e}")
			return pd.DataFrame()

	def _build_benchmark_curve(
		self,
		bm_df: pd.DataFrame,
		initial_capital: float,
	) -> List[Dict]:
		"""从预加载的基准 DataFrame 构建归一化基准曲线（v1.4：同步，无 DB 查询）。"""
		try:
			if bm_df.empty:
				return []
			bm_daily = (
				bm_df.groupby("trade_date")["close"]
				.mean()
				.reset_index()
				.sort_values("trade_date")
			)
			if bm_daily.empty:
				return []
			first_close = float(bm_daily["close"].iloc[0])
			curve = []
			last_close = float(bm_daily["close"].iloc[-1])
			bm_return = (last_close - first_close) / first_close if first_close > 0 else 0.0
			logger.info(
				f"基准曲线: {len(bm_daily)} 日, close {first_close:.2f}→{last_close:.2f}, "
				f"累计收益={bm_return:.2%}"
			)
			for _, row in bm_daily.iterrows():
				cumulative_return = float(row["close"]) / first_close - 1.0 if first_close > 0 else 0.0
				curve.append({
					"trade_date": str(row["trade_date"])[:10],
					"cumulative_return": round(cumulative_return, 6),
					"total_assets": round(initial_capital * (1 + cumulative_return), 2),
				})
			return curve
		except Exception as e:
			logger.warning(f"基准曲线计算失败: {e}")
			return []

	@staticmethod
	def _calculate_excess_metrics(
		result: "BacktestResult",
		benchmark_curve: List[Dict],
		annual_return: float,
	) -> Dict[str, Any]:
		"""计算基准对比指标：Alpha / Beta / 信息比率 / 跟踪误差（v1.4）。

		要求 benchmark_curve 和 result.equity_curve 均非空且 ≥2 个对齐交易日。
		< 60 个对齐交易日时正常计算但标记 low_confidence=True。
		基准方差 ≈ 0 时 Beta=0 并 log warning。
		"""
		metrics: Dict[str, Any] = {}
		if not benchmark_curve or not result.equity_curve:
			return metrics
		if len(benchmark_curve) < 2 or len(result.equity_curve) < 2:
			return metrics

		try:
			# ---- 日期对齐：内连接策略与基准的 trade_date ----
			bm_map = {str(r["trade_date"])[:10]: float(r["cumulative_return"]) for r in benchmark_curve}
			strategy_returns: List[float] = []
			benchmark_returns: List[float] = []
			prev_s = prev_b = None
			for eq in result.equity_curve:
				d = str(eq.get("trade_date", ""))[:10]
				bm_cr = bm_map.get(d)
				if bm_cr is None:
					continue
				s_cr = float(eq.get("cumulative_return", 0))
				if prev_s is not None and prev_b is not None:
					strategy_returns.append(s_cr - prev_s)
					benchmark_returns.append(bm_cr - prev_b)
				prev_s = s_cr
				prev_b = bm_cr

			n = len(strategy_returns)
			if n < 2:
				logger.info(f"超额指标: 对齐交易日不足 ({n}), 跳过")
				return metrics

			logger.info(
				f"超额指标: 对齐 {n} 个交易日 "
				f"(策略 {len(result.equity_curve)} / 基准 {len(benchmark_curve)})"
			)

			# ---- Beta = Cov(s, b) / Var(b) ----
			s_arr = np.array(strategy_returns)
			b_arr = np.array(benchmark_returns)
			b_var = float(np.var(b_arr))
			if b_var > 1e-12:
				beta = float(np.cov(s_arr, b_arr)[0, 1] / b_var)
			else:
				logger.warning("基准方差 ≈ 0，Beta 设为 0")
				beta = 0.0

			# ---- 基准年化收益率 ----
			bm_total = float(benchmark_curve[-1]["cumulative_return"])
			trading_days = max(n, 1)
			bm_annual = (1 + bm_total) ** (252 / trading_days) - 1 if bm_total > -1 else -1.0

			# ---- Alpha = strategy_annual - beta × benchmark_annual ----
			alpha = annual_return - beta * bm_annual

			# ---- 超额收益日序列 → 跟踪误差 / 信息比率 ----
			excess = s_arr - b_arr
			tracking_error = float(np.std(excess)) * np.sqrt(252)
			excess_annual = annual_return - bm_annual
			info_ratio = excess_annual / tracking_error if tracking_error > 0 else 0.0

			metrics = {
				"alpha": round(alpha, 6),
				"beta": round(beta, 4),
				"information_ratio": round(info_ratio, 4),
				"tracking_error": round(tracking_error, 6),
				"excess_annual_return": round(excess_annual, 6),
				"benchmark_annual_return": round(bm_annual, 6),
				"low_confidence": n < 60,
				"aligned_days": n,
			}
		except Exception as e:
			logger.warning(f"超额指标计算失败: {e}")

		return metrics

	# =========================================================================
	# 持久化（v1.1 新增）
	# =========================================================================

	async def _save_results(
			self,
			result: BacktestResult,
			equity_df: pd.DataFrame,
			trades: List[Dict],
	) -> None:
		"""
		将回测结果写入数据库（v1.3: 实现 ORM 批量写入）。

		写入表：
		- backtest_equity_curves: 每日净值点
		- backtest_trades: 每笔交易明细

		Args:
			result: 已计算完成的 BacktestResult。
			equity_df: Broker 的净值曲线 DataFrame。
			trades: Broker 的交易明细列表。
		"""
		try:
			db = getattr(self, "_db_session", None)
			if db is None:
				logger.error(
					"回测结果持久化跳过：_db_session 未注入到 BacktestEngine。"
					"结果仅存在于内存中，不会写入数据库。"
					"请确保初始化 BacktestEngine 时传入了 db_session 参数。"
				)
				return

			from shared.database.repositories.strategy.backtest.backtest_equity_curve_repo import (
				BacktestEquityCurveRepository,
			)
			from shared.database.repositories.strategy.backtest.trade_repo import (
				BacktestTradeRepository,
			)

			equity_repo = BacktestEquityCurveRepository(db)
			trade_repo = BacktestTradeRepository(db)

			# 1. 写入净值曲线
			if not equity_df.empty:
				equity_records = []
				for _, row in equity_df.iterrows():
					equity_records.append({
						"trade_date": row["trade_date"],
						"equity": float(row["total_assets"]),
						"cash": float(row.get("available_cash", 0)),
						"market_value": float(row.get("market_value", 0)),
					})
				await equity_repo.batch_create_equity_curves(
					result.task_id, equity_records
				)
				logger.info(
					f"净值曲线已持久化: {result.task_id} ({len(equity_records)} 条)"
				)

			# 2. 写入交易明细 — 映射 Broker Trade → ORM（v1.3: task前缀防ID冲突）
			if trades:
				import uuid
				trade_records = []
				for i, t in enumerate(trades):
					# v2.4: 统一方向映射（修复非LONG全部映射为sell的bug）
					_DIRECTION_MAP = {"LONG": "buy", "BUY": "buy", "SHORT": "short", "SELL": "sell", "CLOSE_LONG": "sell", "CLOSE_SHORT": "cover"}
					direction = t.get("direction", "")
					orm_direction = _DIRECTION_MAP.get(direction.upper(), "buy")  # v2.4: 统一方向映射
					# 使用 task_id 前缀 + 序号确保全局唯一（Broker 的 trade_id 跨任务会重复）
					unique_id = f"{result.task_id[:8]}_trade_{i+1:06d}"
					trade_records.append({
						"id": unique_id,
						"trade_time": t.get("trade_date"),
						"ts_code": t.get("ts_code", ""),
						"direction": orm_direction,
						"price": float(t.get("price", 0)),
						"volume": int(t.get("quantity", 0)),
						"value": float(t.get("amount", 0)),
						"commission": float(t.get("commission", 0)),
						"tax": float(t.get("stamp_tax", 0)),
					})
				await trade_repo.batch_create_trades(
					result.task_id, trade_records
				)
				logger.info(
					f"交易明细已持久化: {result.task_id} ({len(trade_records)} 笔)"
				)
			# 2.5 提前提交净值曲线+交易明细（避免后续步骤3/4的异常导致回滚）
			try:
				await db.commit()
			except Exception as _ce:
				logger.error(f"净值曲线+交易明细提交失败: {_ce}", exc_info=True)
				try:
					await db.rollback()
				except Exception:
					pass
				# 不 return，继续尝试保存持仓快照和绩效（best-effort）


			# 3. 写入持仓快照（v3.3 新增 — 字段已对齐 BacktestPosition 模型）
			try:
				from shared.database.repositories.strategy.backtest.position_repo import (
					BacktestPositionRepository,
				)
				position_repo = BacktestPositionRepository(db)
				position_records = []
				if self.broker is not None:
					for snap in self.broker.snapshots:
						if snap.positions:
							for ps in snap.positions:
								position_records.append({
									"trade_date": snap.trade_date,
									"ts_code": ps.ts_code,
									"volume": ps.quantity,
									"cost_price": ps.avg_cost,
									"market_value": ps.market_value,
								})
				if position_records:
					await position_repo.batch_create_positions(result.task_id, position_records)
					logger.info(
						f"持仓快照已持久化: {result.task_id} ({len(position_records)} 条)"
					)
			except Exception as _pos_e:
				logger.warning(f"持仓快照持久化跳过（非致命）: {_pos_e}")

			# 4. (v6.13 移除) 回测结果不再写入 strategy_daily_performance —
			# 该表是实盘策略每日绩效（由 performance_service/performance_tracker 写入）。
			# 回测写它会污染实盘收益曲线（混入 +35% 回测 / -100% 幽灵）。
			# 回测结果只持久化到 backtest_equity_curves / backtest_trades / backtest_positions。

			# 3. Commit
			await db.commit()

		except Exception as e:
			logger.error(f"结果持久化失败: {e}", exc_info=True)
			try:
				await db.rollback()
			except Exception:
				pass

	def register_strategy(
			self,
			strategy_type: StrategyType,
			strategy_class: Type[BaseStrategy],
	) -> None:
		"""
		注册策略类（旧接口兼容层）。

		v1.1 已迁移到 StrategyManager + StrategyRegistry，此方法保留用于
		未迁移的调用方和独立测试场景。

		Args:
			strategy_type: 策略类型枚举（StrategyType.CTA / ALPHA / AI 等）。
			strategy_class: 策略类对象（BaseStrategy 的子类）。
		"""
		self._strategy_registry[strategy_type] = strategy_class
		logger.info(f"注册策略类: {strategy_type.value} -> {strategy_class.__name__}")

	def load_strategy(
			self,
			strategy_id: str,
			name: str,
			strategy_type: StrategyType,
			code: str,
			parameters: Dict[str, Any],
			config: StrategyConfig,
	) -> StrategyInstance:
		"""
		加载策略实例（旧接口兼容层）。

		创建 StrategyInstance 并存入 self.strategies 字典。
		v1.1 已迁移到 StrategyManager.load_strategy()。

		Args:
			strategy_id: 策略 ID。
			name: 策略名称。
			strategy_type: 策略类型。
			code: 策略源代码（字符串）。
			parameters: 策略参数字典。
			config: StrategyConfig 配置对象（含 initial_capital 等）。

		Returns:
			创建的 StrategyInstance。
		"""
		instance = StrategyInstance(
			id=strategy_id,
			name=name,
			strategy_type=strategy_type,
			status=StrategyLifecycleStatus.COMPILED,
			user_id=config.user_id if hasattr(config, "user_id") else 0,
			code=code,
			parameters=parameters,
			capital=config.initial_capital,
		)
		self.strategies[strategy_id] = instance
		return instance

	def initialize_strategy(
			self,
			strategy_id: str,
			context: StrategyContext,
	) -> BaseStrategy:
		"""
		初始化策略 — 实例化策略类并注入 StrategyContext（旧接口兼容层）。

		流程：
		1. 检查策略实例是否已在 self._strategy_instances 中缓存
		   - 若已缓存：直接更新 context 并返回（避免重复初始化）
		2. 从 _strategy_registry 获取策略类
		3. 实例化策略对象 → 注入 context → 调用 initialize()

		Args:
			strategy_id: 策略 ID。
			context: StrategyContext 运行时上下文。

		Returns:
			初始化完成的 BaseStrategy 实例。

		Raises:
			ValueError: 策略未加载或策略类型未注册。
		"""
		if strategy_id not in self.strategies:
			raise ValueError(f"策略 {strategy_id} 未加载")

		# 已缓存 → 仅更新 context
		if strategy_id in self._strategy_instances:
			strategy = self._strategy_instances[strategy_id]
			strategy.context = context
			return strategy

		# 首次初始化 → 从注册表获取策略类 → 实例化 → init
		strategy_instance = self.strategies[strategy_id]
		strategy_class = self._strategy_registry.get(strategy_instance.strategy_type)
		if not strategy_class:
			raise ValueError(f"未注册的策略类型: {strategy_instance.strategy_type}")

		strategy = strategy_class(
			name=strategy_instance.name,
			strategy_type=strategy_instance.strategy_type,
			parameters=strategy_instance.parameters,
		)
		strategy.context = context
		strategy.initialize()
		self._strategy_instances[strategy_id] = strategy
		return strategy

	def run_backtest(
			self,
			strategy_id: str,
			data: Dict[str, pd.DataFrame],
			context: StrategyContext,
	) -> Dict[str, Any]:
		"""
		旧接口回测执行（同步，DataFrame 直接驱动）。

		与 v1.1 run() 的区别：
		- run()：异步，通过 DataFeedEngine 加载 + 迭代 BarData
		- run_backtest()：同步，直接遍历传入的 DataFrame

		适用场景：单元测试、独立回测验证（不依赖 DataFeedEngine）。

		Args:
			strategy_id: 策略 ID。
			data: 按股票代码分组的行情 DataFrame 字典
				  {ts_code: DataFrame(columns=[open, high, low, close, volume])}。
			context: StrategyContext 运行时上下文。

		Returns:
			结果字典：{signals, initial_capital, final_capital, start_time, end_time}。

		Raises:
			ValueError: 策略未加载或数据缺少必要列。
		"""
		if strategy_id not in self.strategies:
			raise ValueError(f"策略 {strategy_id} 未加载")

		# ---- 校验数据列完整性 ----
		for symbol, df in data.items():
			required_columns = ["open", "high", "low", "close", "volume"]
			if not all(col in df.columns for col in required_columns):
				raise ValueError(f"数据缺少必要的列: {required_columns}")

		# ---- 初始化策略 ----
		strategy = self.initialize_strategy(strategy_id, context)

		# ---- 遍历每只股票的每行数据，逐行构造 BarData → on_bar ----
		signals = []
		for symbol, df in data.items():
			for _, row in df.iterrows():
				# 兼容 row 可能是 Series 或 DataFrame 列（解包 .iloc 取标量值）
				open_val = float(row["open"].iloc[0]) if hasattr(row["open"], "iloc") else float(row["open"])
				high_val = float(row["high"].iloc[0]) if hasattr(row["high"], "iloc") else float(row["high"])
				low_val = float(row["low"].iloc[0]) if hasattr(row["low"], "iloc") else float(row["low"])
				close_val = float(row["close"].iloc[0]) if hasattr(row["close"], "iloc") else float(row["close"])
				volume_val = float(row["volume"].iloc[0]) if hasattr(row["volume"], "iloc") else float(row["volume"])

				bar = BarData(
					ts_code=symbol,
					period="daily",
					open=open_val,
					high=high_val,
					low=low_val,
					close=close_val,
					volume=volume_val,
					amount=volume_val * close_val,  # 成交额估算
					trade_date=row.name,
				)
				sigs = strategy.on_bar(bar)
				if sigs:
					signals.extend(sigs if isinstance(sigs, list) else [sigs])

		# ---- 构造结果 ----
		result = {
			"signals": signals,
			"initial_capital": context.initial_capital,
			"final_capital": context.available_capital,
			"start_time": datetime.now(),
			"end_time": datetime.now(),
		}
		self.results[strategy_id] = result
		return result

	def calculate_metrics(self, strategy_id: Any) -> Dict[str, float]:
		"""
		旧接口绩效计算（从 self.results 缓存读取结果后计算）。

		与 v1.1 _calculate_metrics_from_broker() 的区别：
		- 旧接口：从 signals 列表和 results 字典计算
		- 新接口：从 Broker 的 equity_curve + trades DataFrame 计算

		Args:
			strategy_id: 策略 ID（字符串或可 hash 的 key）。

		Returns:
			指标字典：{total_return, annualized_return, num_signals, win_rate,
					   profit_factor, duration_days, max_drawdown, sharpe_ratio}。

		Raises:
			ValueError: 策略没有回测结果缓存。
		"""
		if strategy_id not in self.results:
			raise ValueError(f"策略 {strategy_id} 没有回测结果")

		result = self.results[strategy_id]
		signals = result["signals"]
		initial = result["initial_capital"]
		final = result["final_capital"]

		# ---- 收益率 ----
		total_return = (final - initial) / initial if initial > 0 else 0
		duration_days = max((result["end_time"] - result["start_time"]).days, 1)
		annualized_return = (1 + total_return) ** (365 / duration_days) - 1

		# ---- 胜率 ----
		win_count = sum(1 for s in signals if getattr(s, "profit_pct", 0) > 0)
		win_rate = win_count / len(signals) if signals else 0

		# ---- 盈亏比 ----
		profit_pcts = [getattr(s, "profit_pct", 0) for s in signals]
		gross_profit = sum(p for p in profit_pcts if p > 0)
		gross_loss = abs(sum(p for p in profit_pcts if p <= 0))
		profit_factor = gross_profit / gross_loss if gross_loss > 0 else 0.0

		# ---- 最大回撤 + 夏普比率（辅助函数计算） ----
		max_dd = self._calculate_max_drawdown(signals, initial)
		sharpe = self._calculate_sharpe_ratio(signals, annualized_return)

		return {
			"total_return": total_return,
			"annualized_return": annualized_return,
			"num_signals": len(signals),
			"win_rate": win_rate,
			"profit_factor": profit_factor,
			"duration_days": duration_days,
			"max_drawdown": max_dd,
			"sharpe_ratio": sharpe,
		}

	# =========================================================================
	# 并行回测（旧接口兼容）
	# =========================================================================

	async def run_parallel_backtests(
			self,
			strategy_ids: List[str],
			data: Dict[str, pd.DataFrame],
			contexts: Dict[int, StrategyContext],
	) -> Dict[int, Dict[str, Any]]:
		"""
		并行执行多个策略的回测（旧接口兼容）。

		使用 asyncio.to_thread 将同步 run_backtest 放到线程池中执行，
		避免阻塞事件循环。

		Args:
			strategy_ids: 策略 ID 列表。
			data: 共享的行情数据（{ts_code: DataFrame}），所有策略复用。
			contexts: 策略上下文字典 {strategy_id: StrategyContext}。

		Returns:
			{strategy_id: result_dict} — 异常策略的 result 包含 {"error": str}。
		"""
		import asyncio

		async def _one(sid):
			"""单个策略的并行执行闭包。"""
			try:
				ctx = contexts[sid]
				result = await asyncio.to_thread(
					self.run_backtest, sid, data, ctx
				)
				return sid, result
			except Exception as e:
				logger.error(f"策略 {sid} 回测失败: {e}")
				return sid, {"error": str(e)}

		tasks = [_one(sid) for sid in strategy_ids]
		results = await asyncio.gather(*tasks)
		return {sid: result for sid, result in results}

	# =========================================================================
	# 静态辅助函数 — 绩效计算
	# =========================================================================

	@staticmethod
	def _calculate_trade_pnls_fifo(trades: List[Dict]) -> List[float]:
		"""
		FIFO 买卖配对计算每笔交易的实现盈亏（v1.3）。

		算法：
		1. 按 ts_code 分组
		2. 每组内按时间排序
		3. 买入加入队列，卖出从队列头部（FIFO）匹配
		4. 每笔匹配 = (卖出价 - 买入价) × 匹配数量 - 卖出费用
		5. 未匹配的卖出（无对应买入）按成本均价估算

		Returns:
			每笔交易的 PnL 列表（与 trades 同顺序）
		"""
		if not trades:
			return []

		# 按股票分组
		by_stock: Dict[str, List[Dict]] = {}
		for i, t in enumerate(trades):
			ts = t.get("ts_code", "")
			if ts not in by_stock:
				by_stock[ts] = []
			by_stock[ts].append((i, t))  # 保存原始索引

		pnls = [0.0] * len(trades)

		for ts_code, stock_trades in by_stock.items():
			# 按时间排序
			stock_trades.sort(key=lambda x: str(x[1].get("trade_date", "")))

			buy_queue = []  # FIFO: [(idx, price, quantity, commission, stamp_tax, transfer_fee), ...]
			buy_matched_pnl: Dict[int, float] = {}  # 追踪买入侧匹配利润

			for orig_idx, t in stock_trades:
				direction = str(t.get("direction", ""))
				price = float(t.get("price", 0))
				quantity = int(t.get("quantity", 0))
				commission = float(t.get("commission", 0))
				stamp_tax = float(t.get("stamp_tax", 0))
				transfer_fee = float(t.get("transfer_fee", 0))
				fee = commission + stamp_tax + transfer_fee

				if direction == "LONG":
					# 买入 → 入队
					buy_queue.append((orig_idx, price, quantity, commission, stamp_tax, transfer_fee))
					pnls[orig_idx] = -fee  # 初始 = -手续费，匹配后更新
				else:
					# 卖出 → FIFO 匹配
					remaining = quantity
					realized_pnl = -fee  # 先扣除卖出费用

					while remaining > 0 and buy_queue:
						buy_idx, buy_price, buy_qty, buy_comm, buy_stamp, buy_tf = buy_queue[0]
						match_qty = min(remaining, buy_qty)
						# 匹配盈亏 = (卖出价 - 买入价) × 匹配数量
						match_profit = (price - buy_price) * match_qty
						realized_pnl += match_profit

						# 更新买入侧匹配利润（按比例分摊买入手续费）
						buy_fee_ratio = match_qty / buy_qty
						buy_match_profit = match_profit - (buy_comm + buy_stamp + buy_tf) * buy_fee_ratio
						buy_matched_pnl[buy_idx] = buy_matched_pnl.get(buy_idx, 0) + buy_match_profit

						if buy_qty > match_qty:
							# v6.11: 部分成交时按比例缩减费用，避免后续匹配重复计入
							remain_ratio = (buy_qty - match_qty) / buy_qty
							buy_queue[0] = (buy_idx, buy_price, buy_qty - match_qty,
							               buy_comm * remain_ratio, buy_stamp * remain_ratio, buy_tf * remain_ratio)
						else:
							buy_queue.pop(0)

						remaining -= match_qty

					# 剩余未匹配部分（卖空或数据不完整）按成本 0 估算
					if remaining > 0:
						realized_pnl += price * remaining

					pnls[orig_idx] = realized_pnl

			# 回填买入侧 PnL（初始 -fee + 匹配利润）
			for _buy_idx, _matched_pnl in buy_matched_pnl.items():
				pnls[_buy_idx] += _matched_pnl

		return pnls

	@staticmethod
	def _calculate_max_drawdown(signals, initial_capital):
		"""
		计算最大回撤（从信号 profit 序列）。

		算法：遍历每笔信号，逐笔累加 profit 得到净值序列，
		追踪历史最大净值，计算当前回撤 = (max_equity - equity) / max_equity，
		取所有回撤中的最大值。

		Args:
			signals: 信号列表，每个信号需包含 profit 属性（单笔交易损益）。
			initial_capital: 初始资金（作为净值序列起点）。

		Returns:
			最大回撤比例（float，0.0 ~ 1.0）。
		"""
		if not signals:
			return 0.0

		# ---- 构造净值序列 ----
		equity = initial_capital
		equity_curve = [equity]
		for s in signals:
			if hasattr(s, "profit"):
				equity += s.profit
				equity_curve.append(equity)

		# ---- 滚动计算最大回撤 ----
		max_eq = equity_curve[0]
		max_dd = 0.0
		for eq in equity_curve[1:]:
			if eq > max_eq:
				max_eq = eq  # 创新高 → 重置最大净值
			else:
				dd = (max_eq - eq) / max_eq
				if dd > max_dd:
					max_dd = dd  # 记录更大的回撤

		return max_dd

	@staticmethod
	def _calculate_sharpe_ratio(signals, annualized_return):
		"""
		计算夏普比率（旧接口兼容，从信号 profit_pct 序列）。

		公式：sharpe = annualized_return / (std(daily_returns) × √252)

		Args:
			signals: 信号列表，每个信号需包含 profit_pct 属性。
			annualized_return: 已计算的年化收益率。

		Returns:
			夏普比率（float），无信号或标准差为 0 时返回 0.0。
		"""
		if not signals:
			return 0.0

		daily_returns = [getattr(s, "profit_pct", 0) for s in signals]
		if not daily_returns:
			return 0.0

		std_dev = np.std(daily_returns)
		if std_dev == 0:
			return 0.0

		return float(annualized_return / std_dev * np.sqrt(252))

	# =========================================================================
	# 生命周期（EngineBase 钩子）
	# =========================================================================

	async def _on_initialize(self):
		"""引擎初始化回调 — 加载配置、预热分析器、验证数据库连接"""
		logger.info(f"回测引擎 {self.config.name} 初始化")
		try:
			# 验证数据库可用性
			from sqlalchemy import text
			if hasattr(self, '_db_session') and self._db_session:
				await self._db_session.execute(text("SELECT 1"))
			# 预热核心分析器（延迟加载到首次使用时）
			self._analyzers_ready = False
			logger.info(f"回测引擎 {self.config.name} 初始化完成（分析器延迟加载）")
		except Exception as e:
			logger.warning(f"回测引擎初始化警告: {e}")

	async def _on_start(self):
		"""引擎启动回调 — 订阅回测任务事件，恢复孤儿任务"""
		logger.info(f"回测引擎 {self.config.name} 启动")
		# 订阅回测相关事件
		if self._event_engine:
			self._event_engine.subscribe(
				"backtest.task.created", self._on_task_created
			)
		# 恢复意外中断的孤儿任务
		try:
			from modules.backtest.services.backtest_service import BacktestService
			if hasattr(self, '_db_session') and self._db_session:
				service = BacktestService(self._db_session)
				await service.recover_orphan_tasks()
		except Exception as e:
			logger.info(f"无孤儿回测任务或恢复失败: {e}")

	async def _on_task_created(self, event) -> None:
		"""回测任务创建事件处理（预留扩展）"""
		pass

	async def _on_stop(self):
		"""
		引擎停止回调。

		清理内存缓存（数据缓存 + 策略实例缓存），释放内存。
		"""
		logger.info(f"回测引擎 {self.config.name} 停止")
		self._data_cache.clear()
		self._strategy_instances.clear()

	async def _on_pause(self):
		"""引擎暂停回调（当前无操作）。"""
		pass

	async def _on_resume(self):
		"""引擎恢复回调（当前无操作）。"""
		pass

	async def _on_force_stop(self):
		"""
		引擎强制停止回调。

		比 _on_stop 更激进，不等待当前任务完成即清理所有内存数据。
		"""
		self._data_cache.clear()
		self._strategy_instances.clear()

	async def _on_health_check(self) -> Dict[str, Any]:
		"""
		健康检查回调 — 返回引擎当前状态快照。

		Returns:
			{
				strategies_loaded: 已加载策略数,
				results_cached: 结果缓存数,
				data_cache_size: 数据缓存条目数
			}
		"""
		return {
			"strategies_loaded": len(self.strategies),
			"results_cached": len(self.results),
			"data_cache_size": len(self._data_cache),
		}
