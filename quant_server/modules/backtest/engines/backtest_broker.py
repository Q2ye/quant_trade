# -*- coding: utf-8 -*-
"""
BacktestBroker — 虚拟券商

================================================================================
职责边界
================================================================================
BacktestBroker 是回测系统的「虚拟券商」，模拟 A 股真实交易环境下的：
  1. 订单管理 — 接收策略信号 → 创建订单 → 挂单队列
  2. 撮合成交 — T+1 次日开盘价成交（考虑涨跌停 / 滑点）
  3. 持仓管理 — T+1 制度下可用持仓追踪、成本均价计算
  4. 费用计算 — 佣金（≥5 元/笔）+ 印花税（仅卖出 0.1%）+ 过户费（0.002%）
  5. 盯市结算 — 每日按收盘价重估持仓，记录账户快照和净值曲线
  6. 查询接口 — 提供净值曲线、交易记录、持仓、账户快照给绩效计算和前端

================================================================================
模拟链路
================================================================================
TradingSignal → BrokerOrder(pending) → match_orders(次日 open) → Trade(filled)
    → BrokerPosition(持仓更新) → mark_to_market(盯市) → AccountSnapshot(快照)
    → get_equity_curve() → BacktestEngine._calculate_metrics_from_broker()

================================================================================
A 股核心规则实现
================================================================================
┌─────────────┬──────────────────────────────────────────────────────────┐
│ 规则        │ 实现                                                      │
├─────────────┼──────────────────────────────────────────────────────────┤
│ T+1 制度    │ 当日买入 → available_quantity = 0，次日释放              │
│ 涨跌停限制  │ 主板 ±10% / 科创板 688 ±20% / ST ±5%，涨停不买跌停不卖   │
│ 最低佣金    │ max(成交额 × 0.03%, 5 元)                                │
│ 印花税      │ 成交额 × 0.1%（仅卖出方向征收）                           │
│ 过户费      │ 成交额 × 0.002%（买卖双向）                               │
│ 滑点        │ 买入 × (1 + slippage)，卖出 × (1 - slippage)              │
│ 最小交易单位│ 100 股（1 手），数量自动取整                              │
│ 涨停价成交  │ 涨停价 = 前收 × (1 + 涨跌幅)，触及涨停则买单无法成交      │
│ 跌停价成交  │ 跌停价 = 前收 × (1 - 涨跌幅)，触及跌停则卖单无法成交      │
└─────────────┴──────────────────────────────────────────────────────────┘

================================================================================
数据结构
================================================================================
BrokerOrder          — 内部订单对象（order_id, ts_code, direction, price, ...）
BrokerPosition       — 内部持仓对象（ts_code, quantity, available_qty, avg_cost, ...）
AccountSnapshot      — 每日账户快照（total_assets, cumulative_return, max_drawdown, ...）
BacktestBrokerConfig — 券商配置（初始资金、费率、滑点、涨跌停参数）

================================================================================
参照设计
================================================================================
- Backtrader BackBroker:  订单队列 → 成交 → 持仓 → 账户更新
- VN.PY BacktestingEngine: 逐日结算 + 滑点 + 佣金

================================================================================
版本历史
================================================================================
v1.0: 初始实现 — 订单管理 / 撮合 / 持仓 / 费用 / 盯市 / 查询
"""
import logging
from copy import deepcopy
from dataclasses import dataclass, field
from datetime import date, datetime, timezone
from decimal import Decimal
from typing import Dict, List, Optional, Any

import pandas as pd

from core.engines.base.engine_base import EngineBase, EngineConfigEntity
from core.engines.types.entities import BarData
from core.engines.types.enums import EngineType

logger = logging.getLogger(__name__)


# =============================================================================
# 内部数据类 — 订单 / 持仓 / 快照
# =============================================================================

@dataclass
class BrokerOrder:
    """
    内部订单对象 — 代表一笔由策略信号生成的待执行或已执行订单。

    生命周期：
        submit_order() 创建（status=pending） → 进入 pending_orders 挂单队列
        → match_orders() 撮合（status=filled） → 从队列移除 → 加入 trade_history

    Note:
        - commission / stamp_tax / transfer_fee 在成交时由 match_orders 填充
        - fill_date 和 fill_price 在成交时设置，撮合前均为 None
    """

    order_id: str                            # 订单唯一 ID（"order_000001" 格式）
    ts_code: str                             # 股票代码（如 "000001.SZ"）
    direction: str                           # 买卖方向：LONG(买入) / SHORT(卖出)
    price: float                             # 委托价格（策略信号指定价）
    quantity: int                            # 委托数量（股），已按手数取整
    order_type: str                          # 订单类型：market(市价) / limit(限价)
    status: str                              # 状态：pending(挂单中) / filled(已成交) / cancelled(已取消)
    create_date: date                        # 订单创建日期（挂单日）
    reason: str = ""                         # 信号原因（如"底部概率 65%, 权重 32%"）
    fill_date: Optional[date] = None         # 成交日期（T+1），未成交时为 None
    fill_price: Optional[float] = None       # 实际成交价（考虑滑点后的开盘价）
    commission: float = 0.0                  # 佣金（成交时计算）
    stamp_tax: float = 0.0                   # 印花税（仅卖出方向，成交时计算）
    transfer_fee: float = 0.0                # 过户费（买卖双向，成交时计算）
    # v6.11: 执行模式
    #   "open"    — 次日开盘价成交（默认，T+1 传统撮合）
    #   "close"   — 当日收盘价成交（收盘确认买入）
    #   "trigger" — 当日触发价成交（日内止损：盘中触及 trigger_price 即成交）
    order_mode: str = "open"
    trigger_price: Optional[float] = None    # trigger 模式的触发价（如止损价 = entry × (1 + stop_loss)）


@dataclass
class BrokerPosition:
    """
    内部持仓对象 — 代表某只股票的当前持仓状态。

    T+1 制度下的关键字段：
        quantity:            总持仓数（含当日买入但不可卖的部分）
        available_quantity:  可卖数量（当日买入部分为 0，次日释放为 quantity）

    示例：
        持仓 1000 股，当日买入 300 股 →
            quantity = 1300, available_quantity = 1000
    """

    ts_code: str                  # 股票代码
    quantity: int                 # 总持仓股数（含 T+1 锁定部分）
    available_quantity: int       # 可卖股数（T+1 制度下，当日买入部分为 0）
    avg_cost: float               # 加权平均成本价（多次买入按数量加权）
    current_price: float = 0.0    # 当前市价（mark_to_market 时更新为当日收盘价）
    market_value: float = 0.0     # 持仓市值 = quantity × current_price
    pnl: float = 0.0              # 浮动盈亏 = (current_price - avg_cost) × quantity
    pnl_rate: float = 0.0         # 盈亏比例 = (current_price - avg_cost) / avg_cost


@dataclass
class PositionSnapshot:
    """单只股票在某个交易日的持仓快照"""

    ts_code: str                  # 股票代码
    quantity: int                 # 持仓数量（股）
    available_quantity: int       # 可用数量（T+1 解锁后）
    avg_cost: float               # 持仓均价
    current_price: float          # 当日收盘价
    market_value: float           # 当日市值 = quantity × close
    pnl: float                    # 当日浮动盈亏
    pnl_rate: float               # 浮动盈亏率 = (close - avg_cost) / avg_cost


@dataclass
class AccountSnapshot:
    """
    每日账户快照 — 记录每个交易日结束后的账户状态。

    由 mark_to_market() 在每个交易日末尾创建并追加到 self.snapshots 列表。
    净值曲线、最大回撤等绩效指标的原始数据来源。
    """

    trade_date: date              # 交易日
    total_assets: float           # 总资产 = cash + frozen_cash + 持仓市值 - 提前释放现金
    available_cash: float         # 可用资金（可立即用于新买入）
    frozen_cash: float            # 冻结资金（已提交买单但尚未成交的预扣款）
    market_value: float           # 持仓总市值
    positions_value: float        # 同 market_value（兼容字段）
    daily_pnl: float              # 当日浮动盈亏合计
    cumulative_return: float      # 累计收益率 = (total_assets - initial_capital) / initial_capital
    max_drawdown: float = 0.0     # 截至当日的最大回撤（滚动追踪历史峰值）
    positions: list = None        # v2.0: 当日持仓明细快照列表 List[PositionSnapshot]

    def __post_init__(self):
        if self.positions is None:
            self.positions = []


# =============================================================================
# BacktestBrokerConfig — 券商配置
# =============================================================================

@dataclass
class BacktestBrokerConfig:
    """
    回测券商配置 — 控制交易成本、制度限制、风控参数。

    所有费率均为 A 股市场默认值，可通过构造时传入覆盖。
    """

    # ---- 资金 ----
    initial_capital: float = 1_000_000    # 初始资金（默认 100 万）

    # ---- 费率（A 股标准） ----
    commission_rate: float = 0.0001       # 佣金费率 万分之一（0.01%），万一免五
    min_commission: float = 0.0           # 最低佣金 0 元（免五，无最低限制）
    stamp_tax: float = 0.001              # 印花税 千分之一（0.1%），仅卖出方向征收
    transfer_fee_rate: float = 0.00002    # 过户费 十万分之二（0.002%），买卖双向

    # ---- 执行 ----
    slippage: float = 0.001               # 滑点 0.1%（买入向上滑，卖出向下滑）

    # ---- A 股制度 ----
    t_plus_1: bool = True                 # T+1 制度开关（True 时当日买入不可卖）
    price_limit: bool = True              # 涨跌停限制开关
    limit_up_down: float = 0.10           # 默认涨跌停幅度（主板 10%，科创板/ST 自动覆盖）

    # ---- 交易单位 ----
    lot_size: int = 100                   # 1 手 = 100 股，数量自动向下取整到手的整数倍


# =============================================================================
# BacktestBroker — 虚拟券商引擎
# =============================================================================

class BacktestBroker(EngineBase):
    """
    虚拟券商 — 模拟回测环境下的订单执行和账户管理。

    继承 EngineBase，可作为独立引擎注册到 EventEngine，也可直接由
    BacktestEngine 注入并直接调用其方法。

    核心方法（按日内调用顺序）：
        submit_order()    — 信号 → 订单（挂单队列，冻结资金）
        match_orders()    — 撮合昨日挂单（T+1 open 成交，计算费用，更新持仓）
        mark_to_market()  — 盯市结算（按收盘价重估，记录账户快照）

    查询方法（供 BacktestEngine 和前端 API 调用）：
        get_equity_curve()      — 完整净值曲线 DataFrame
        get_trade_list()        — 所有成交记录
        get_position_list()     — 当前持仓列表
        get_account_snapshot()  — 当前账户状态摘要

    Attributes:
        config:           券商配置（BacktestBrokerConfig）
        initial_capital:  初始资金
        cash:             当前可用资金
        frozen_cash:      冻结资金（已下单未成交）
        positions:        持仓字典 {ts_code: BrokerPosition}
        orders:           所有订单 {order_id: BrokerOrder}
        pending_orders:   挂单队列（待撮合的订单列表）
        trade_history:    成交记录列表
        snapshots:        每日账户快照列表
        _prev_close:      前收价缓存 {ts_code: float}（用于涨跌停判断）
        _star_market_stocks: 科创板识别集合
        _st_stocks:       ST 股票识别集合
    """

    def __init__(
        self,
        config: BacktestBrokerConfig = None,
        event_engine=None,
        risk_engine=None,
    ):
        """
        初始化虚拟券商。

        Args:
            config: 券商配置（BacktestBrokerConfig），为 None 时使用默认配置。
            event_engine: 事件引擎（可选），用于将成交 / 持仓变化发布为事件。
            risk_engine: 风控引擎（可选），用于在 submit_order 时执行 19 条规则检查。
        """
        super().__init__(
            EngineConfigEntity(
                name="BacktestBroker",
                engine_type="backtest_broker",
            ),
            event_engine=event_engine,
        )

        # ---- 配置 ----
        self.config = config or BacktestBrokerConfig()

        # ---- 账户资金 ----
        self.initial_capital: float = self.config.initial_capital
        self.cash: float = self.config.initial_capital    # 可用资金
        self.frozen_cash: float = 0.0                      # 冻结资金（已下单未成交的预扣款）
        # 已提前释放现金但对应卖出持仓尚未撮合成交的累计金额。
        # 卖出下单当日即把预估所得打入 self.cash（支持同日卖→买），
        # 但持仓要到次日撮合才移除；总资产计算须扣除此项，避免重复计价（净值幻影）。
        self._early_released_cash: float = 0.0

        # ---- 持仓管理 {ts_code: BrokerPosition} ----
        self.positions: Dict[str, BrokerPosition] = {}

        # ---- 订单管理 ----
        self.orders: Dict[str, BrokerOrder] = {}             # 全量订单索引
        self.pending_orders: List[BrokerOrder] = []          # 挂单队列（FIFO）

        # ---- 历史记录 ----
        self.trade_history: List[Dict[str, Any]] = []        # 成交记录（Trade Record）
        self.snapshots: List[AccountSnapshot] = []           # 每日账户快照
        self._equity_curve: pd.DataFrame = None               # 净值曲线缓存

        # ---- 风控引擎（v2.0 统一规则） ----
        self._risk_engine = risk_engine

        # ---- 风控辅助 ----
        self._prev_close: Dict[str, float] = {}               # 前收价缓存（涨跌停判断依据）
        self._star_market_stocks: set = set()                 # 科创板股票集合（688xxx）
        self._st_stocks: set = set()                          # ST 股票集合
        self._risk_violations: List[Dict[str, Any]] = []      # 回测中收集的风控违规明细

        # ---- 交易日追踪 ----
        self._trade_date: Optional[date] = None
        self._peak_equity: float = self.initial_capital  # v1.4: O(1) 峰值追踪
        self._prev_day_equity: float = self.initial_capital  # v6.11: 前日权益（供风控日亏损规则）

    # =========================================================================
    # 订单处理 — 信号 → 订单
    # =========================================================================


    def _validate_order(self, ts_code: str, direction: str, price: float,
                        quantity: int) -> None:
        """v1.5: 独立订单验证，所有拒绝原因以 ValueError 抛出。"""
        if price <= 0:
            raise ValueError(f"[{ts_code}] 价格无效: {price}")
        if quantity <= 0:
            raise ValueError(f"[{ts_code}] 数量无效: {quantity}")
        if direction == "LONG":
            # v1.6: 估算成本 = 成交金额 + 佣金 + 滑点。
            # 允许 ≤1% 微小超支通过验证 — submit_order 会触发自动数量缩减，
            # match_orders 依据实际开盘价做最终资金校验，不会产生负现金。
            estimated = price * quantity * (1 + self.config.commission_rate
                                            + self.config.slippage)
            if estimated > self.cash * 1.01:
                raise ValueError(f"[{ts_code}] 资金不足: 需{estimated:.0f}, 可用{self.cash:.0f}")
        if direction in ("SHORT", "CLOSE_LONG"):
            pos = self.positions.get(ts_code)
            # 修复 2026-08（C7）：T+1 可卖校验——用可卖数量而非总持仓，
            # 此前当日买入部分也可卖出（违反 T+1）
            if not pos:
                raise ValueError(f"[{ts_code}] 持仓不足: 需{quantity}, 可用0")
            avail = pos.available_quantity if self.config.t_plus_1 else pos.quantity
            if avail < quantity:
                raise ValueError(f"[{ts_code}] 可卖数量不足(T+1): 需{quantity}, 可卖{avail}")

    async def submit_order(
        self,
        ts_code: str,
        direction: str,
        price: float,
        quantity: int,
        order_type: str = "market",
        reason: str = "",
        order_mode: str = "open",
        trigger_price: Optional[float] = None,
    ) -> BrokerOrder:
        """
        接收策略信号 → 创建订单并加入 T+1 挂单队列。

        处理流程（按顺序）：
        1. 方向标准化 — CLOSE_LONG/CLOSE_SHORT → SHORT
        2. 手数取整 — quantity 向下取整到 100 的倍数
        3. quantity=0 哨兵处理：
           - LONG + quantity=0 → 按可用资金全量计算最大可买股数
           - SHORT + quantity=0 → 按可用持仓全量平仓
        4. 资金检查（买入方向）：
           - 预估成本 = price × quantity × (1 + commission_rate)
           - 不足时自动下调数量到可买上限
        5. 冻结资金（买入方向）：
           - 从 cash 扣除预估成本 → frozen_cash
        6. 创建 BrokerOrder → 加入 pending_orders 挂单队列

        Args:
            ts_code: 股票代码（如 "000001.SZ"）。
            direction: 交易方向 LONG / SHORT / CLOSE_LONG / CLOSE_SHORT。
            price: 委托价格（策略信号指定价，实际成交价在 match_orders 中确定）。
            quantity: 委托数量（股）。传入 0 表示：
                - 买入方向：按全部可用资金计算最大买入量
                - 卖出方向：平掉全部可用持仓
            order_type: 订单类型，"market"（市价单，次日 open 无条件成交）
                        或 "limit"（限价单，需 check 价格触及）。
            order_mode: 执行模式，"open"（次日开盘成交）/ "close"（当日收盘成交）/
                        "trigger"（当日触发价成交，盘中触及 trigger_price 即成交）。
            trigger_price: order_mode="trigger" 时的触发价。

        Returns:
            创建的 BrokerOrder 对象，或 None（资金不足 / 无可用持仓 等拒绝下单场景）。

        Note:
            - 此方法仅创建订单（挂单），实际成交在次日 match_orders() 中执行。
            - 冻结资金使用委托价估算，次日成交后按实际成交价多退少补。
        """
        # ---- 1. 方向标准化 ----
        # v1.4: 统一转为大写。SignalDirection 枚举值为 "long"/"short"（小写），
        # 策略代码中也常使用 "buy"/"sell"，必须全部归一化为 LONG/SHORT，
        # 否则后续的资金冻结、持仓更新、FIFO 配对全部失效。
        direction = direction.upper()
        if direction in ("BUY", "LONG"):
            direction = "LONG"
        elif direction in ("SELL", "SHORT"):
            direction = "SHORT"
        if direction == "CLOSE_LONG":
            direction = "SHORT"  # 平多 = 卖出
        elif direction == "CLOSE_SHORT":
            direction = "LONG"   # 平空 = 买入

        # ---- v2.0: 统一风控规则检查（19 条规则） ----
        risk_engine = self._risk_engine
        if not risk_engine:
            try:
                from core.engines.system.engine_registry import EngineRegistry
                registry = EngineRegistry()
                risk_engine = registry.get_engine("risk_engine")
            except Exception:
                risk_engine = None
        if risk_engine and getattr(risk_engine, 'risk_check_enabled', False):
            # 收集当前持仓的行业分布（供行业集中度规则使用）
            sector = ""
            is_st = ts_code in self._st_stocks
            for pos_ts, pos in self.positions.items():
                if pos_ts == ts_code and hasattr(pos, 'sector'):
                    sector = pos.sector

            # 计算总资产和持仓市值
            total_asset = self.cash + self.frozen_cash + sum(
                p.quantity * p.current_price for p in self.positions.values()
            ) - self._early_released_cash
            position_value = sum(
                p.quantity * p.current_price for p in self.positions.values()
            )

            # 风控检查（sumbit_order 已改为 async，可以直接 await）
            # v6.11: 回测中排除账户级日终监控规则 + limit_up_down。
            # - 账户级规则（capital_change 等）用盘中不一致快照误杀正常卖单（幽灵持仓根因）。
            # - limit_up_down 若在此处丢弃订单，跌停时的止损卖单会被永久丢弃（订单不重试），
            #   而策略 _finalize_exits 仍会把持仓从 _holdings 清除 → 孤儿持仓。
            #   涨跌停改由 broker 的 _can_trade 在 match_orders/settle 中挂起重试。
            _account_rules = (
                "account_balance", "loss_limit", "drawdown_limit",
                "capital_change", "trade_count", "limit_up_down",
            )
            passed, msg = await risk_engine.check_signal({
                    "ts_code": ts_code,
                    "direction": "buy" if direction == "LONG" else "sell",
                    "price": price,
                    "quantity": quantity,
                    "trade_amount": price * quantity,
                    "total_asset": total_asset,
                    "available_cash": self.cash,
                    "position_value": position_value,
                    "initial_capital": self.initial_capital,
                    "peak_asset": self._peak_equity,
                    "previous_asset": getattr(self, '_prev_day_equity', total_asset),
                    "positions": [
                        {
                            "ts_code": pos_ts,
                            "quantity": p.quantity,
                            "current_price": p.current_price,
                            "cost_price": getattr(p, 'cost_price', p.current_price),
                            "sector": getattr(p, 'sector', ""),
                        }
                        for pos_ts, p in self.positions.items()
                    ],
                    "market": ts_code.split(".")[-1] if "." in ts_code else "",
                    "sector": sector,
                    "volume": 0,
                    "close": price,
                    "high": price,
                    "low": price,
                    "pre_close": self._prev_close.get(ts_code, price),
                    "is_st": is_st,
                    "volatility": 0.0,
                    "liquidity": price * 10000,
                    "market_status": "normal",
                    "suspended": False,
                    "daily_trade_count": len(self.trade_history),
                }, exclude_rules=_account_rules)
            if not passed:
                logger.info("[风控拦截 %s] %s → 拒绝下单", ts_code, msg)
                # v3.0: 收集违规明细，供回测报告展示
                self._risk_violations.append({
                    "ts_code": ts_code,
                    "direction": direction,
                    "price": price,
                    "quantity": quantity,
                    "message": msg,
                    "trade_date": str(self._trade_date) if self._trade_date else None,
                    "created_at": datetime.now(timezone.utc).isoformat(),
                })
                return None

        # ---- v1.5: 独立验证 ----
        try:
            self._validate_order(ts_code, direction, price, quantity)
        except ValueError as e:
            logger.warning(f"订单验证失败: {e}")
            return None

        # ---- 2. 手数取整（向下取到 lot_size 的整数倍） ----
        quantity = (quantity // self.config.lot_size) * self.config.lot_size
        if quantity <= 0:
            # quantity=0 哨兵值处理
            if direction == "LONG" and price > 0:
                # 买入方向：按可用资金全量计算最大可买股数
                quantity = int(
                    self.cash / (price * (1 + self.config.commission_rate))
                    // self.config.lot_size
                    * self.config.lot_size
                )
                if quantity <= 0:
                    logger.warning(f"资金不足无法买入: {ts_code}")
                    return None
            elif direction in ("SHORT", "CLOSE_LONG", "CLOSE_SHORT"):
                # 卖出方向：平掉全部可用持仓
                pos = self.positions.get(ts_code)
                if pos and pos.available_quantity > 0:
                    quantity = (pos.available_quantity // self.config.lot_size) * self.config.lot_size
                if quantity <= 0:
                    logger.warning(f"无可用持仓平仓: {ts_code}")
                    return None
            else:
                logger.warning(f"订单数量为 0，跳过: {ts_code}")
                return None

        # ---- 3. 资金检查（买入方向） ----
        if direction == "LONG":
            estimated_cost = price * quantity * (1 + self.config.commission_rate)
            if estimated_cost > self.cash:
                # 资金不足 → 自动下调数量到可买上限
                max_qty = int(
                    self.cash / (price * (1 + self.config.commission_rate))
                    // self.config.lot_size
                    * self.config.lot_size
                )
                if max_qty <= 0:
                    logger.warning(
                        f"资金不足: 需要 {estimated_cost:.2f}, "
                        f"可用 {self.cash:.2f}, 跳过 {ts_code}"
                    )
                    return None
                quantity = max_qty
                logger.info(f"资金不足，调整数量: {ts_code} → {quantity} 股")

        # ---- 4. 冻结资金（买入方向预扣，v6.11: 含佣金+过户费避免 settlement 时资金缺口） ----
        estimated_cost = price * quantity * (1 + self.config.commission_rate + self.config.transfer_fee_rate)
        if direction == "LONG":
            self.frozen_cash += estimated_cost
            self.cash -= estimated_cost

        # ---- 5. 创建订单 ----
        order_id = f"order_{len(self.orders) + 1:06d}"
        order = BrokerOrder(
            order_id=order_id,
            ts_code=ts_code,
            direction=direction,
            price=price,
            quantity=quantity,
            order_type=order_type,
            status="pending",
            create_date=self._trade_date or date.today(),
            reason=reason,
            order_mode=order_mode,
            trigger_price=trigger_price,
        )

        self.orders[order_id] = order
        self.pending_orders.append(order)

        # ---- 卖出订单提前释放资金（支持同日卖→买） ----
        # 回测 T+1 结算导致卖出次日才释放资金，同日买入因 cash 不足被拒。
        # 此处预释放，标记订单避免 match_orders 重复入账。
        # 同步累计到 _early_released_cash：持仓此刻尚未移除，总资产计算须扣除此金额
        # 避免重复计价；成交/过期时按 order._early_released_amount 精确回冲。
        if direction == "SHORT" and price > 0:
            estimated_proceeds = price * quantity * (1 - self.config.commission_rate)
            self.cash += estimated_proceeds
            self._early_released_cash += estimated_proceeds
            order._early_released = True
            order._early_released_amount = estimated_proceeds

        logger.debug(
            f"订单创建: {order_id} {direction} {ts_code} "
            f"{quantity}股 @ {price:.2f}"
        )
        return order

    # =========================================================================
    # 撮合成交 — 挂单 → 成交
    # =========================================================================

    def match_orders(
        self,
        trade_date: date,
        bars: Dict[str, BarData],
    ) -> List[Dict[str, Any]]:
        """
        撮合昨日挂单 — 用当日 Bar 的 open price 模拟 T+1 成交。

        撮合规则（按优先级）：
        ┌──────┬─────────────────────────────────────────────────────────┐
        │ 优先级│ 规则                                                   │
        ├──────┼─────────────────────────────────────────────────────────┤
        │  1   │ 停牌/无数据 → 保留挂单到下一交易日                      │
        │  2   │ 涨跌停限制：涨停价买单无法成交，跌停价卖单无法成交       │
        │  3   │ 市价单：以次日 open 成交（加滑点）                      │
        │  4   │ 限价单：买入时 open ≤ 限价才成交；卖出时 open ≥ 限价    │
        └──────┴─────────────────────────────────────────────────────────┘

        成交后处理：
        - 更新订单状态（filled）→ 从 pending_orders 移除
        - 计算费用（佣金 ≥ 5 元 + 印花税 + 过户费）
        - 冻结资金解冻 + 实际扣款 / 入账
        - 更新持仓（_update_position）
        - 记录成交到 trade_history

        Args:
            trade_date: 当前交易日（撮合日）。
            bars: 当日所有股票的 BarData 字典 {ts_code: BarData}。

        Returns:
            当日成交记录列表（List[Dict]），每项包含 trade_id, order_id, ts_code,
            direction, price, quantity, amount, commission, stamp_tax, transfer_fee,
            trade_date。
        """
        self._trade_date = trade_date
        trades = []

        # ---- v6.11: 前收价用于涨跌停——应在今日 close 更新前使用昨日值。
        # _prev_close 在 mark_to_market() 末尾更新，此处不再覆盖。

        # ---- NaN 防护：过滤无效价格 ----
        for ts_code, bar in list(bars.items()):
            if hasattr(bar, 'open') and (bar.open is None or bar.open != bar.open):
                logger.warning(f"match_orders: {ts_code} open 为 NaN/None, 跳过")
                del bars[ts_code]
        # _prev_close 在 mark_to_market() 末尾更新，此处不再覆盖。

        # ---- 逐笔撮合昨日挂单 ----
        remaining_orders = []
        for order in self.pending_orders:
            bar = bars.get(order.ts_code)
            if bar is None:
                # 停牌或数据缺失 → 超时取消 (v1.5)
                age = (trade_date - order.create_date).days if order.create_date else 0
                if age > 20:
                    logger.warning(f"订单过期取消: {order.order_id} {order.ts_code}")
                    if order.direction == "LONG":
                        # v6.11: 解冻金额须与 freeze 一致（含佣金+过户费）
                        refund = order.price * order.quantity * (1 + self.config.commission_rate + self.config.transfer_fee_rate)
                        self.cash += refund
                        self.frozen_cash -= refund
                    elif getattr(order, '_early_released', False):
                        released = getattr(order, '_early_released_amount', 0.0)
                        self.cash -= released
                        self._early_released_cash -= released
                    order.status = "cancelled"
                    continue
                # v6.11: 停牌/无数据但未过期 → 保留挂单到下一交易日
                remaining_orders.append(order)
                continue

            # ---- v6.11: trigger-mode（日内止损/止盈，触发价成交） ----
            # 止损单在盘中触及 trigger_price 即成交，无需等到次日开盘，
            # 用当日 bar 的 low/high 判断触发（决策时戳 = 成交时戳，无未来函数）。
            _trigger_mode = (order.order_mode == "trigger")
            if _trigger_mode:
                _tp = order.trigger_price
                if (order.direction == "SHORT" and _tp and _tp > 0
                        and bar.low is not None and bar.low <= _tp):
                    # 多头止损触发：开盘已跳穿止损 → 按更差的开盘价；否则按止损价
                    _raw = _tp
                    if bar.open is not None and bar.open > 0 and bar.open < _raw:
                        _raw = bar.open
                    fill_price = _raw * (1 - self.config.slippage)  # 卖出向下滑点
                else:
                    # 未触发 → 保留挂单到下一交易日
                    remaining_orders.append(order)
                    continue

            # ---- 涨跌停检查（trigger 模式跳过：盘中触及即视为有对手盘） ----
            if self.config.price_limit and not _trigger_mode:
                if not self._can_trade(order.ts_code, order.direction, bar.open):
                    logger.debug(
                        f"涨跌停限制，无法成交: {order.ts_code} "
                        f"{order.direction} @ {bar.open:.2f}"
                    )
                    remaining_orders.append(order)
                    continue

            # ---- 确定成交价 = 开盘价（考虑滑点；trigger 模式已在上面确定） ----
            if _trigger_mode:
                pass  # fill_price 已在 trigger 分支计算
            else:
                fill_price = bar.open
                if self.config.slippage > 0:
                    if order.direction == "LONG":
                        fill_price *= (1 + self.config.slippage)  # 买入：向上滑点（买得更贵）
                    else:
                        fill_price *= (1 - self.config.slippage)  # 卖出：向下滑点（卖得更便宜）

            # ---- 限价单额外检查 ----
            if order.order_type == "limit":
                if order.direction == "LONG" and fill_price > order.price:
                    # 买入限价：实际成交价高于限价 → 不成交
                    remaining_orders.append(order)
                    continue
                if order.direction == "SHORT" and fill_price < order.price:
                    # 卖出限价：实际成交价低于限价 → 不成交
                    remaining_orders.append(order)
                    continue

            # ================================================================
            # 以下：订单满足成交条件，执行撮合（v6.11 抽为 _execute_fill 复用）
            # ================================================================
            rec = self._execute_fill(order, fill_price, trade_date)
            if rec is not None:
                trades.append(rec)

        # ---- 更新挂单队列（移除已成交的） ----
        self.pending_orders = remaining_orders
        return trades

    def _execute_fill(
        self,
        order: "BrokerOrder",
        fill_price: float,
        trade_date: date,
    ) -> Optional[Dict[str, Any]]:
        """按成交价执行订单撮合（费用计算 / 资金结算 / 持仓更新 / 成交记录）。

        v6.11: 从 match_orders 抽出的公共撮合逻辑，供 match_orders（open 成交）
        和 settle_intraday_orders（close/trigger 成交）复用。

        Returns:
            trade_record（成交记录 dict），或 None（资金不足取消，订单作废）。
        """
        fill_amount = fill_price * order.quantity

        # ---- 2026-08 修复：卖出前校验实际持仓 ----
        # 策略在信号层记录持仓（发买入信号即记 _holdings），但 broker 撮合可能拒单
        # （如涨停买不进/资金不足）→ broker 实际无持仓。此后策略发卖出信号 → 无持仓可卖
        # 原逻辑在 _update_position 抛 ValueError 致整个回测崩溃。改为订单作废：
        # 不结算现金/不更新持仓/不记录成交，与 LONG 资金不足作废逻辑一致。
        if order.direction == "SHORT" and order.ts_code not in self.positions:
            logger.warning(
                f"[{order.ts_code}] 无持仓可卖，卖出订单作废（策略信号与实际持仓不一致）"
            )
            order.status = "cancelled"
            return None

        # ---- 计算交易费用 ----
        commission = max(
            fill_amount * self.config.commission_rate,
            self.config.min_commission,    # A 股最低佣金 5 元
        )
        stamp_tax = (
            fill_amount * self.config.stamp_tax
            if order.direction == "SHORT"   # 印花税仅卖出方向征收
            else 0.0
        )
        transfer_fee = fill_amount * self.config.transfer_fee_rate  # 过户费双向

        # ---- 资金结算（在标记成交之前，LONG 方向可能需要缩减/取消） ----
        total_cost = fill_amount + commission + stamp_tax + transfer_fee
        if order.direction == "LONG":
            # 解冻预扣资金（按委托价+费用估算）→ 按实际成交价扣款
            estimated = order.price * order.quantity * (1 + self.config.commission_rate + self.config.transfer_fee_rate)
            self.frozen_cash -= estimated
            self.cash += estimated
            # ---- v2.0: 现金充足性校验 ----
            # 原逻辑直接 self.cash -= total_cost，若实际成交价远高于委托价
            #（开盘跳空），现金可能变为负数 → total_assets 虚增 → 净值幻影。
            if self.cash < total_cost:
                # 资金不足 → 按实际可用现金缩减买入量
                affordable_qty = int(
                    self.cash / (fill_price * (1 + self.config.commission_rate))
                    // self.config.lot_size * self.config.lot_size
                )
                if affordable_qty <= 0:
                    # 一股都买不起 → 取消订单。
                    # 资金已在上面解冻，不重新冻结（订单已作废）。
                    logger.warning(
                        f"资金不足取消买入: {order.ts_code} "
                        f"需要={total_cost:,.0f} 可用={self.cash:,.0f}"
                    )
                    order.status = "cancelled"
                    return None  # 不加入挂单队列，直接丢弃
                # 按可负担量重算：缩减 fill_amount / commission / stamp_tax / transfer_fee
                fill_amount = fill_price * affordable_qty
                commission = max(fill_amount * self.config.commission_rate, self.config.min_commission)
                stamp_tax = 0.0  # 买入无印花税
                transfer_fee = fill_amount * self.config.transfer_fee_rate
                total_cost = fill_amount + commission + stamp_tax + transfer_fee
                order.quantity = affordable_qty
                order.fill_price = fill_price
                order.commission = commission
                order.stamp_tax = stamp_tax
                order.transfer_fee = transfer_fee
                logger.info(
                    f"买入量缩减: {order.ts_code} {order.quantity}股 "
                    f"@ {fill_price:.2f} (资金不足, 缩减至可负担量)"
                )
            self.cash -= total_cost
        else:
            # 卖出：入账（不涉及冻结资金，卖出从不冻结）
            # 注意：如果订单已提前释放资金（_early_released），此处只做差价调整
            if getattr(order, '_early_released', False):
                estimated = order.price * order.quantity * (1 - self.config.commission_rate)
                actual = fill_amount - commission - stamp_tax - transfer_fee
                self.cash += (actual - estimated)  # 多退少补
                # 幻影解除：持仓即将随成交移除，回冲提前释放的累计额（精确按下单时存额）
                self._early_released_cash -= getattr(order, '_early_released_amount', estimated)
            else:
                self.cash += (fill_amount - commission - stamp_tax - transfer_fee)

        # ---- 标记成交状态 ----
        order.status = "filled"
        order.fill_date = trade_date
        order.fill_price = fill_price
        order.commission = commission
        order.stamp_tax = stamp_tax
        order.transfer_fee = transfer_fee

        # ---- v1.6: 保存入场均价（_update_position 会删除卖出持仓，须提前取值） ----
        is_exit = order.direction in ("SHORT", "CLOSE_LONG", "close_long")
        entry_avg_cost = None
        if is_exit and order.ts_code in self.positions:
            entry_avg_cost = self.positions[order.ts_code].avg_cost

        # ---- 更新持仓（T+1 制度下的 available_quantity 调整） ----
        self._update_position(order, fill_price, trade_date)

        # ---- 记录成交 ----
        trade_record = {
            "trade_id": f"trade_{len(self.trade_history) + 1:06d}",
            "order_id": order.order_id,
            "ts_code": order.ts_code,
            "direction": order.direction,
            "price": fill_price,
            "quantity": order.quantity,
            "amount": fill_amount,
            "commission": commission,
            "stamp_tax": stamp_tax,
            "transfer_fee": transfer_fee,
            "trade_date": trade_date,
        }
        self.trade_history.append(trade_record)

        # 计算该笔交易的 PnL（平仓时从预先保存的入场均价推算）
        trade_pnl_str = ""
        if is_exit:
            if entry_avg_cost is None:
                trade_pnl_str = "PnL=N/A(pos_gone)"
            elif entry_avg_cost <= 0:
                trade_pnl_str = f"PnL=N/A(avg_cost={entry_avg_cost})"
            else:
                trade_pnl = (fill_price - entry_avg_cost) / entry_avg_cost
                trade_pnl_str = f"PnL={trade_pnl:+.2%}"

        pnl_display = f" {trade_pnl_str}" if trade_pnl_str else ""
        label = "卖出" if is_exit else "买入"
        reason_str = f" | {order.reason}" if getattr(order, 'reason', '') else ""
        logger.debug(
            f"  [{order.create_date}] {label} {order.ts_code} "
            f"{order.quantity}股 @ {fill_price:.2f} "
            f"费用={commission + stamp_tax + transfer_fee:.2f}{pnl_display}{reason_str}"
        )

        return trade_record

    def settle_intraday_orders(
        self,
        bars: Dict[str, BarData],
        trade_date: date = None,
    ) -> List[Dict[str, Any]]:
        """v6.11: 处理当日提交的 close/trigger 模式订单。

        调用时机：handle_bar_batch（策略生成信号并 submit_order）之后、
        mark_to_market 之前。

        - close 模式（收盘确认买入，Model B）：按当日收盘价成交
        - trigger 模式（日内止损，Model A）：当日 low 触及触发价即成交

        match_orders 处理"昨日挂单"（open 成交 + 跨日 trigger 检查）；
        本方法处理"今日新提交"的 close/trigger 单，两者互补、互不重复。
        决策时戳 = 成交时戳（当日 close/low 触发 → 当日成交），无未来函数。
        """
        trades: List[Dict[str, Any]] = []
        if not bars:
            return trades

        remaining_orders = []
        for order in self.pending_orders:
            # 仅处理今日提交的 close/trigger 单；open 单留给下一日 match_orders
            if order.create_date != trade_date or order.order_mode in ("open", None):
                remaining_orders.append(order)
                continue

            bar = bars.get(order.ts_code)
            if bar is None:
                remaining_orders.append(order)
                continue

            # ---- v6.11: close/trigger 模式无条件当日成交（不设涨跌停门） ----
            # limit_up_down 规则已从 submit_order 风控排除。此处 close/trigger 单
            # 一律成交，防止"跌停卖单被挂起/丢弃 → 孤儿持仓巨亏"（000681 曾 -49%）。
            # - trigger（止损）：按 min(open, trigger) 立即成交，快速斩断亏损。
            # - close（买入确认/轮动/止盈）：按当日收盘价成交。
            # open 模式（次日开盘）仍由 match_orders 的 _can_trade 挂起涨跌停重试。
            fill_price = None
            if order.order_mode == "close":
                # 收盘确认买入：按当日收盘价成交（买入向上滑点）
                if bar.close is not None and bar.close > 0:
                    fill_price = bar.close
                    if self.config.slippage > 0:
                        fill_price *= (1 + self.config.slippage)
            elif order.order_mode == "trigger":
                # 日内止损：low 触及触发价即成交（开盘跳穿 → 按开盘价）
                _tp = order.trigger_price
                if (order.direction == "SHORT" and _tp and _tp > 0
                        and bar.low is not None and bar.low <= _tp):
                    _raw = _tp
                    if bar.open is not None and bar.open > 0 and bar.open < _raw:
                        _raw = bar.open
                    fill_price = _raw * (1 - self.config.slippage)

            if fill_price is None or fill_price <= 0:
                remaining_orders.append(order)
                continue

            rec = self._execute_fill(order, fill_price, trade_date)
            if rec is not None:
                trades.append(rec)

        self.pending_orders = remaining_orders
        return trades

    # =========================================================================
    # 盯市结算 — 逐日重估
    # =========================================================================

    def mark_to_market(self, bars: Dict[str, BarData], trade_date: date = None):
        """
        逐日盯市 — 用当日收盘价更新所有持仓的市值和浮动盈亏。

        在每个交易日结束后调用，执行以下操作：
        1. 遍历 bars 中所有股票，更新对应持仓的：
           - current_price → 当日收盘价
           - market_value → quantity × close
           - pnl → (close - avg_cost) × quantity
           - pnl_rate → (close - avg_cost) / avg_cost
        2. 计算总资产 = cash + frozen_cash + 持仓总市值
        3. 计算累计收益率 = (total_assets - initial_capital) / initial_capital
        4. 滚动计算最大回撤：
           - 历史峰值 = max(所有历史快照的 total_assets)
           - 当前回撤 = (峰值 - 当前总资产) / 峰值
           - 最大回撤 = max(历史最大回撤, 当前回撤)
        5. 创建 AccountSnapshot → 追加到 self.snapshots

        Args:
            bars: 当日所有股票的 BarData 字典 {ts_code: BarData}。
                  只有出现在 bars 中的股票持仓会被重估（不在 bars 中的
                  持仓保持上期市值不变 — 通常是停牌或未获取到数据）。

        Note:
            - frozen_cash（冻结资金）也算入总资产 — 已下单未成交的买单
              其资金虽被预扣但仍属于账户资产的一部分。
        """
        # v1.5: 初始化时包含全部持仓市值（含停牌股），bars 遍历时则替换为当日最新值
        total_market_value = sum(p.market_value for p in self.positions.values())
        total_pnl = 0.0

        # ---- 逐只股票重估持仓 + T+1 锁定释放 ----
        for ts_code, bar in bars.items():
            # v6.11: NaN 防护
            if hasattr(bar, 'close') and (bar.close is None or bar.close != bar.close):
                continue
            # v1.3: T+1 解锁 — 昨日买入今日可卖
            if ts_code in self.positions:
                pos = self.positions[ts_code]
                if self.config.t_plus_1 and pos.available_quantity < pos.quantity:
                    # 所有持仓在次日变为可用（简化处理：每个新交易日释放全部锁定）
                    pos.available_quantity = pos.quantity
            if ts_code in self.positions:
                pos = self.positions[ts_code]
                pos.current_price = bar.close
                old_mv = pos.market_value
                pos.market_value = pos.quantity * bar.close
                pos.pnl = (bar.close - pos.avg_cost) * pos.quantity
                pos.pnl_rate = (
                    (bar.close - pos.avg_cost) / pos.avg_cost
                    if pos.avg_cost > 0
                    else 0.0
                )
                total_market_value += (pos.market_value - old_mv)
                total_pnl += pos.pnl

        # 总资产 = 可用资金 + 冻结资金 + 持仓市值 - 提前释放现金
        # 注：冻结资金本质仍是账户资产（已下单未成交），计入总资产
        # 扣除 _early_released_cash：卖单当日已把预估所得计入 cash，但持仓尚未移除，
        # 若不扣除则该笔被 cash 与 market_value 重复计价（净值幻影，见 __init__ 说明）。
        total_assets = (
            self.cash + self.frozen_cash + total_market_value
            - self._early_released_cash
        )
# ---- v1.4: 持仓市值一致性校验 ----
        for ts_code, pos in self.positions.items():
            computed_mv = pos.quantity * pos.current_price
            if abs(pos.market_value - computed_mv) > 0.01:
                logger.warning(
                    f"持仓市值不一致 [{self._trade_date}] {ts_code}: "
                    f"market_value={pos.market_value:.2f} vs "
                    f"qty({pos.quantity}) × price({pos.current_price:.2f})"
                    f"={computed_mv:.2f}, diff={pos.market_value - computed_mv:.4f}"
                )

        # ---- 计算累计收益率 ----
        if self._trade_date and self.initial_capital > 0:
            cumulative_return = (
                (total_assets - self.initial_capital) / self.initial_capital
            )
        else:
            cumulative_return = 0.0

        # ---- 滚动计算最大回撤（v1.4: O(1) 峰值追踪） ----
        if total_assets > self._peak_equity:
            self._peak_equity = total_assets
        current_drawdown = (
            (self._peak_equity - total_assets) / self._peak_equity
            if self._peak_equity > 0 else 0.0
        )
        max_drawdown = current_drawdown
        if self.snapshots:
            max_drawdown = max(
                self.snapshots[-1].max_drawdown,  # 仅取上一快照的累积 max_drawdown
                current_drawdown,
            )

        # ---- 记录快照 ----
        # v2.0: 收集当日持仓明细快照，用于事后分析持仓变化
        position_snapshots = []
        for ts_code, pos in self.positions.items():
            if pos.quantity > 0:
                position_snapshots.append(PositionSnapshot(
                    ts_code=ts_code,
                    quantity=pos.quantity,
                    available_quantity=pos.available_quantity,
                    avg_cost=pos.avg_cost,
                    current_price=pos.current_price,
                    market_value=pos.market_value,
                    pnl=pos.pnl,
                    pnl_rate=pos.pnl_rate,
                ))

        snapshot = AccountSnapshot(
            trade_date=trade_date or self._trade_date,
            total_assets=total_assets,
            available_cash=self.cash,
            frozen_cash=self.frozen_cash,
            market_value=total_market_value,
            positions_value=total_market_value,
            daily_pnl=total_pnl,
            cumulative_return=cumulative_return,
            max_drawdown=max_drawdown,
            positions=position_snapshots,
        )
        self.snapshots.append(snapshot)

        # ---- v6.11: 更新前收价 + 前日权益（供次日涨跌停判定和风控规则使用） ----
        for ts_code, bar in bars.items():
            self._prev_close[ts_code] = bar.close
        self._prev_day_equity = total_assets

    # =========================================================================
    # 查询接口 — 供 BacktestEngine 和前端 API 调用
    # =========================================================================

    def get_equity_curve(self) -> pd.DataFrame:
        """
        返回完整净值曲线 DataFrame。

        从 self.snapshots 列表构造，每个快照对应一个交易日。

        Returns:
            DataFrame，列：
            - trade_date:         交易日
            - total_assets:       当日总资产
            - available_cash:     可用资金
            - market_value:       持仓市值
            - daily_pnl:          当日浮动盈亏
            - cumulative_return:  累计收益率
            - max_drawdown:       截至当日的最大回撤

            无快照时返回仅含列名的空 DataFrame。
        """
        if not self.snapshots:
            return pd.DataFrame(
                columns=["trade_date", "total_assets", "cumulative_return", "max_drawdown"]
            )

        df = pd.DataFrame([
            {
                "trade_date": s.trade_date,
                "total_assets": s.total_assets,
                "available_cash": s.available_cash,
                "market_value": s.market_value,
                "daily_pnl": s.daily_pnl,
                "cumulative_return": s.cumulative_return,
                "max_drawdown": s.max_drawdown,
            }
            for s in self.snapshots
        ])
        return df

    def get_trade_list(self) -> List[Dict[str, Any]]:
        """
        返回所有成交记录（深拷贝）。

        Returns:
            成交记录列表，每项包含 trade_id, order_id, ts_code, direction,
            price, quantity, amount, commission, stamp_tax, transfer_fee, trade_date。

        Note:
            使用 deepcopy 防止外部修改影响内部状态。
        """
        return deepcopy(self.trade_history)

    def get_position_list(self) -> List[Dict[str, Any]]:
        """
        返回当前持仓列表。

        Returns:
            持仓摘要列表，每项包含 ts_code, quantity, available_quantity,
            avg_cost, current_price, market_value, pnl, pnl_rate。
        """
        return [
            {
                "ts_code": pos.ts_code,
                "quantity": pos.quantity,
                "available_quantity": pos.available_quantity,
                "avg_cost": pos.avg_cost,
                "current_price": pos.current_price,
                "market_value": pos.market_value,
                "pnl": pos.pnl,
                "pnl_rate": pos.pnl_rate,
            }
            for pos in self.positions.values()
        ]

    def get_account_snapshot(self) -> Dict[str, Any]:
        """
        返回当前账户状态摘要（即时计算，不依赖快照列表）。

        用于回测过程中实时获取账户状态（如日志输出、进度推送）。

        Returns:
            {
                initial_capital:    初始资金
                cash:               当前可用资金
                frozen_cash:        冻结资金
                market_value:       持仓总市值
                total_assets:       总资产 = cash + frozen + 市值 - 提前释放现金
                total_return:       累计收益率
                trade_date:         当前交易日
                position_count:     持仓数
                pending_order_count: 挂单数
                total_trades:       累计成交笔数
            }
        """
        total_mv = sum(p.market_value for p in self.positions.values())
        total_assets = self.cash + self.frozen_cash + total_mv - self._early_released_cash
        return {
            "initial_capital": self.initial_capital,
            "cash": self.cash,
            "frozen_cash": self.frozen_cash,
            "market_value": total_mv,
            "total_assets": total_assets,
            "total_return": (
                (total_assets - self.initial_capital) / self.initial_capital
                if self.initial_capital > 0
                else 0.0
            ),
            "trade_date": self._trade_date,
            "position_count": len(self.positions),
            "pending_order_count": len(self.pending_orders),
            "total_trades": len(self.trade_history),
        }

    # =========================================================================
    # 生命周期管理
    # =========================================================================

    def reset(self, initial_capital: float = None):
        """
        重置账户到初始状态（用于新的回测运行）。

        清空所有持仓、订单、成交记录、快照、价格缓存，
        将资金恢复到初始值。

        Args:
            initial_capital: 新的初始资金。为 None 时沿用 config 中的配置值。

        Note:
            每次 BacktestEngine.run() 调用前应执行 reset() 确保从干净状态开始。
        """
        if initial_capital is not None:
            self.initial_capital = initial_capital
            self.config.initial_capital = initial_capital

        self.cash = self.initial_capital
        self.frozen_cash = 0.0
        self._early_released_cash = 0.0
        self.positions.clear()
        self.orders.clear()
        self.pending_orders.clear()
        self.trade_history.clear()
        self.snapshots.clear()
        self._equity_curve = None
        self._prev_close.clear()
        self._trade_date = None
        self._peak_equity = self.initial_capital  # v1.4: 重置峰值
        self._prev_day_equity = self.initial_capital  # v6.11
        # v1.3: 重置 ST/科创板识别集合（后续可从 DB 加载）
        self._star_market_stocks = set()
        self._st_stocks = set()
        self._risk_violations.clear()
        logger.info(f"券商已重置: 初始资金={self.initial_capital:,.0f}")

    def get_risk_violations(self) -> List[Dict[str, Any]]:
        """获取回测期间收集的风控违规明细"""
        return list(self._risk_violations)

    # =========================================================================
    # 私有方法 — 持仓更新 / 涨跌停检查
    # =========================================================================

    def _update_position(
        self,
        order: BrokerOrder,
        fill_price: float,
        trade_date: date,
    ):
        """
        根据成交订单更新持仓。

        买入（LONG）：
        - 已有持仓 → 加权平均更新 avg_cost = (旧成本×旧数量 + 新成交×新数量) / 总数量
        - 无持仓 → 新建 BrokerPosition，avg_cost = 成交价
        - T+1 下 available_quantity = 原可用（当日买入部分为 0）

        卖出（SHORT）：
        - 已有持仓 → 减持 quantity，quantity ≤ 0 时删除持仓
        - available_quantity = min(原可用, 剩余总持仓)

        Args:
            order: 已成交的 BrokerOrder。
            fill_price: 实际成交价。
            trade_date: 成交日期（当前未使用，保留用于后续扩展如持仓时间统计）。
        """
        ts_code = order.ts_code

        if order.direction == "LONG":
            if ts_code in self.positions:
                # 已有持仓 → 加权平均更新成本价
                pos = self.positions[ts_code]
                total_cost = pos.avg_cost * pos.quantity + fill_price * order.quantity
                pos.quantity += order.quantity
                pos.avg_cost = total_cost / pos.quantity if pos.quantity > 0 else 0.0

                # T+1 制度：当日买入部分锁定为不可卖
                # v6.11: 用 min 避免同一日多次买入时误放大可用量
                if self.config.t_plus_1:
                    pos.available_quantity = min(
                        pos.available_quantity,
                        pos.quantity - order.quantity
                    )
                else:
                    pos.available_quantity = pos.quantity
            else:
                # 无持仓 → 新建
                self.positions[ts_code] = BrokerPosition(
                    ts_code=ts_code,
                    quantity=order.quantity,
                    available_quantity=(
                        0 if self.config.t_plus_1 else order.quantity
                    ),
                    avg_cost=fill_price,
                )

        elif order.direction == "SHORT":
            # 修复 2026-08（C6）：成交路径超卖校验——同日两笔卖出时第二笔此前无校验，
            # 持仓被减为负后直接删除致现金虚增
            if ts_code not in self.positions:
                raise ValueError(f"[{ts_code}] 无持仓可卖，成交拒绝")
            pos = self.positions[ts_code]
            if pos.quantity < order.quantity:
                raise ValueError(f"[{ts_code}] 卖出数量超过持仓: 持仓{pos.quantity}, 卖出{order.quantity}")
            pos.quantity -= order.quantity
            if pos.quantity <= 0:
                # 全部平仓 → 删除持仓
                del self.positions[ts_code]
            else:
                # available_quantity 不能超过剩余总持仓
                pos.available_quantity = min(
                    pos.available_quantity, pos.quantity
                )

    def _can_trade(
        self,
        ts_code: str,
        direction: str,
        price: float,
    ) -> bool:
        """
        涨跌停限制检查 — 判断当前价格下是否可以成交。

        涨停价 = 前收价 × (1 + 涨跌幅比例)
        跌停价 = 前收价 × (1 - 涨跌幅比例)

        规则：
        - 涨停价买入 → False（涨停买不进）
        - 跌停价卖出 → False（跌停卖不出）

        涨跌幅自动识别：
        - 688xxx → 科创板 20%
        - ST / *ST → 5%
        - 其他 → 主板 10%（config.limit_up_down）

        Args:
            ts_code: 股票代码。
            direction: 交易方向（LONG / SHORT / CLOSE_LONG / CLOSE_SHORT）。
            price: 当日开盘价（用于与涨跌停价比较）。

        Returns:
            True 如果可以成交，False 表示被涨跌停限制。
        """
        prev_close = self._prev_close.get(ts_code)
        if prev_close is None or prev_close <= 0:
            return True  # 无前收价（新股首日等），不限制

        # ---- 确定涨跌幅比例 ----
        if ts_code in self._star_market_stocks or ts_code.startswith("688"):
            limit_pct = 0.20          # 科创板 ±20%
        elif ts_code in self._st_stocks or "ST" in ts_code:
            limit_pct = 0.05          # ST ±5%
        else:
            limit_pct = self.config.limit_up_down  # 主板默认 ±10%

        limit_up = prev_close * (1 + limit_pct)     # 涨停价
        limit_down = prev_close * (1 - limit_pct)   # 跌停价

        if direction == "LONG" and price >= limit_up:
            return False  # 涨停 → 买不进
        if direction in ("SHORT", "CLOSE_LONG", "CLOSE_SHORT") and price <= limit_down:
            return False  # 跌停 → 卖不出

        return True

    # =========================================================================
    # EngineBase 生命周期钩子
    # =========================================================================

    async def _on_initialize(self) -> None:
        """引擎初始化回调 — 输出核心配置到日志。"""
        logger.info(
            f"BacktestBroker 初始化完成: "
            f"初始资金={self.initial_capital:,.0f}, "
            f"佣金={self.config.commission_rate:.4%} (万一免五), "
            f"印花税={self.config.stamp_tax:.3%}"
        )

    async def _on_start(self) -> None:
        """引擎启动回调 — 重置交易状态 + 订阅事件"""
        self.trade_history.clear()
        self.positions.clear()
        self.cash = self.initial_capital
        self._early_released_cash = 0.0
        self._commission_total = 0.0
        self._stamp_tax_total = 0.0
        logger.info("BacktestBroker 已启动（状态已重置）")


    async def _on_stop(self) -> None:
        """
        引擎停止回调 — 输出回测终止时的账户摘要。

        打印累计成交笔数和最终资产（用于快速审阅回测结果）。
        """
        logger.info(
            f"BacktestBroker 已停止: "
            f"总成交 {len(self.trade_history)} 笔, "
            f"最终资产 "
            f"{self.cash + self.frozen_cash + sum(p.market_value for p in self.positions.values()) - self._early_released_cash:,.2f}"
        )
