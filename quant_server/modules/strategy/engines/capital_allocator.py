# -*- coding: utf-8 -*-
"""
CapitalAllocator — 多策略资金分配器

================================================================================
职责
================================================================================
按市场 Regime + 可选风险平价动态分配多策略之间的资金权重。

- Regime 基准权重：熊市 ETF 多、牛市股票多
- 风险平价微调（P1）：按各策略 Universe 的逆波动率调整
- 信号权重缩放：每个策略的信号 weight × alloc_ratio → Broker 统一资金池

================================================================================
与现有系统的关系
================================================================================
- 不是 Engine（不继承 EngineBase），不响应事件
- 不是 Service（持有状态：滚动波动率缓冲区）
- 放在 modules/strategy/engines/，作为 StrategyManager 的同级编排组件
- 不改 StrategyManager / Broker / 策略代码

================================================================================
版本历史
================================================================================
P0: 固定 Regime + 固定比例分配（无风险平价）
P1: 动态 Regime（CSI500 MA）+ bar 波动率缓冲区 + 风险平价（可选）
P2: pause/resume 休眠 + resume 预热 + 主动再平衡
"""
import logging
from collections import deque
from datetime import date
from typing import Dict, List, Optional

import numpy as np

logger = logging.getLogger(__name__)


class CapitalAllocator:
    """
    多策略资金分配器。

    使用方式:
        allocator = CapitalAllocator(
            strategy_ids=["etf_bottom", "stock_low_high"],
            force_regime=1,  # 0=BEAR 1=RANGE 2=BULL
        )
        # 每日回测循环中：
        allocator.rebalance(trade_date, bar_dict)
        # 信号缩放：sig.weight *= allocator.get_weight(sig.strategy_id)
    """

    # ------------------------------------------------------------------
    # Regime → strategy_id → 基准权重
    # strategy_id 映射: etf_bottom=ETF底部策略, stock_low_high=低吸轮动策略
    # ------------------------------------------------------------------
    REGIME_BASE_ALLOCATION: Dict[int, Dict[str, float]] = {
        0: {"etf_bottom": 0.8, "stock_low_high": 0.2},   # BEAR:  防御为主
        1: {"etf_bottom": 0.5, "stock_low_high": 0.5},   # RANGE: 均衡
        2: {"etf_bottom": 0.2, "stock_low_high": 0.8},   # BULL:  进攻为主
    }

    # ------------------------------------------------------------------
    # 默认参数
    # ------------------------------------------------------------------
    DEFAULT_PARAMS = {
        "risk_parity_enabled": False,     # P1: 是否启用风险平价微调
        "vol_lookback": 60,               # 波动率回溯窗口（交易日）
        "vol_floor": 0.01,                # 年化波动率下限
        "vol_cap": 2.0,                   # 年化波动率上限
        "rp_blend_strength": 0.3,         # 风险平价混合强度: 0=纯 Regime, 1=纯 RP
        "rp_rebalance_freq": "monthly",   # RP 重算频率: daily/weekly/monthly
    }

    def __init__(
        self,
        strategy_ids: List[str],
        allocator_params: Optional[Dict] = None,
        force_regime: Optional[int] = None,
    ):
        """
        Args:
            strategy_ids: 参与分配的策略 ID 列表，如 ["etf_bottom", "stock_low_high"]
            allocator_params: 分配器参数字典（覆盖 DEFAULT_PARAMS）
            force_regime: P0 固定 Regime 值。合法值 0/1/2，超出钳制为 1。
                          None 时默认 RANGE=1。
        """
        self._strategy_ids = list(strategy_ids)
        self._params = {**self.DEFAULT_PARAMS, **(allocator_params or {})}

        # v6.13: 支持组合分组配置自定义 REGIME_BASE_ALLOCATION（覆盖类常量）。
        # 这样新增策略时只需改 composite_groups.allocator_config，无需改代码。
        # 注意 JSON 存储的 key 是字符串，需归一化为 int。
        _cfg_base = (allocator_params or {}).get("REGIME_BASE_ALLOCATION")
        if _cfg_base:
            try:
                self._base_allocation = {
                    int(k): dict(v) for k, v in _cfg_base.items()
                }
            except Exception:
                logger.warning("allocator_config.REGIME_BASE_ALLOCATION 解析失败，用类常量")
                self._base_allocation = self.REGIME_BASE_ALLOCATION
        else:
            self._base_allocation = self.REGIME_BASE_ALLOCATION

        # Regime 状态
        if force_regime is not None and force_regime not in (0, 1, 2):
            logger.warning(
                f"force_regime={force_regime} 不在 [0,2] 范围内，钳制为 RANGE=1"
            )
            force_regime = 1
        self._force_regime = force_regime
        self._regime = force_regime if force_regime is not None else 1
        self._prev_regime: Optional[int] = None

        # 当前分配权重 {strategy_id: weight}
        self._allocation: Dict[str, float] = {}
        self._last_rebalance_date: Optional[date] = None
        self._rebalance_counter = 0

        # ---- P1 字段（P0 预创建，暂不使用） ----
        # 每个策略的波动率滚动缓冲区 {strategy_id: deque(maxlen=vol_lookback)}
        self._vol_buffers: Dict[str, deque] = {
            sid: deque(maxlen=self._params["vol_lookback"])
            for sid in self._strategy_ids
        }
        # 每个策略的 Universe 代理: "etf_pool" | "csi500" | "all_stocks"
        self._strategy_universes: Dict[str, str] = {}

    # =========================================================================
    # P0: 核心方法
    # =========================================================================

    def rebalance(self, trade_date: date, bar_dict: dict) -> None:
        """
        每日调用：判定 Regime → 必要时重算权重。

        调用时机: Broker.match_orders() 之后、handle_bar_batch() 之前。

        Args:
            trade_date: 当前交易日
            bar_dict: {ts_code: BarData}，当日所有标的行情
        """
        # ---- 判定 Regime ----
        self._regime = self._get_regime(trade_date, bar_dict)

        # ---- 决定是否 rebalance ----
        regime_changed = self._regime != self._prev_regime
        need_rp_rebalance = self._should_rp_rebalance(trade_date)

        if regime_changed or need_rp_rebalance or not self._allocation:
            self._allocation = self._compute_allocation()
            self._prev_regime = self._regime
            self._last_rebalance_date = trade_date
            logger.info(
                f"CapitalAllocator rebalance @ {trade_date}: "
                f"regime={self._regime}, alloc={self._allocation}"
            )

    def get_weight(self, strategy_id: str) -> float:
        """获取某策略当前的资金分配权重（0~1）。"""
        return self._allocation.get(strategy_id, 0.0)


    # =========================================================================
    # P0: Regime 判定（固定值）
    # =========================================================================

    def _get_regime(self, trade_date: date, bar_dict: dict) -> int:
        """
        获取当前市场 Regime。

        P0: 返回构造时传入的 force_regime，默认 RANGE=1。
        P1: 从 bar_dict 中的 CSI500 计算 MA 判定（动态）。
        """
        if self._force_regime is not None:
            return self._force_regime
        # P1: 动态判定（TODO）
        return 1  # 默认 RANGE

    # =========================================================================
    # P0: 权重计算
    # =========================================================================

    def _compute_allocation(self) -> Dict[str, float]:
        """
        计算最终资金分配权重。

        P0: 直接从 REGIME_BASE_ALLOCATION 查表，归一化。
        P1: Regime 基准 + 风险平价混合 + clamp + 归一化。

        Returns:
            {strategy_id: weight}，weights sum = 1.0
        """
        if not self._strategy_ids:
            return {}

        base_raw = self._base_allocation.get(self._regime)
        if base_raw is None:
            # 未知 Regime → 均分
            n = len(self._strategy_ids)
            return {sid: 1.0 / n for sid in self._strategy_ids}

        # 过滤：仅保留配置中的 strategy_ids，对未知 ID 打 warning
        base = {}
        for sid in self._strategy_ids:
            w = base_raw.get(sid)
            if w is None:
                logger.warning(
                    f"CapitalAllocator: allocator_id='{sid}' 不在 "
                    f"REGIME_BASE_ALLOCATION[{self._regime}] 中，权重设为 0。 "
                    f"已知 key: {list(base_raw.keys())}"
                )
                base[sid] = 0.0
            else:
                base[sid] = w

        # P0: 纯 Regime 基准（无风险平价）
        if not self._params.get("risk_parity_enabled", False):
            return self._normalize_and_clamp(base)

        # P1: Regime + 风险平价混合（TODO）
        return self._blend_with_risk_parity(base)

    def _normalize_and_clamp(
        self, weights: Dict[str, float]
    ) -> Dict[str, float]:
        """
        归一化 + 上下界钳制 [5%, 95%]。

        处理两种特殊情况:
        - 全部为 0: 均分
        - 总和不为 1: 归一化
        """
        total = sum(weights.values())
        if total <= 0:
            n = len(self._strategy_ids)
            return {sid: 1.0 / n for sid in self._strategy_ids}

        clamped = {
            sid: max(0.05, min(0.95, v / total))
            for sid, v in weights.items()
        }
        # 再次归一化（钳制后总和可能偏离 1）
        total2 = sum(clamped.values())
        return {sid: v / total2 for sid, v in clamped.items()}

    # =========================================================================
    # P0: RP rebalance 调度（占位）
    # =========================================================================

    def _should_rp_rebalance(self, trade_date: date) -> bool:
        """
        判断是否需要按 RP 频率触发 rebalance。

        P0: 无风险平价，仅 Regime 变化时触发。返回 False。
        P1: 根据 rp_rebalance_freq 判断。
        """
        if not self._params.get("risk_parity_enabled", False):
            return False

        freq = self._params.get("rp_rebalance_freq", "monthly")
        if freq == "daily":
            return True
        if freq == "weekly":
            # 每 5 个交易日
            self._rebalance_counter += 1
            return self._rebalance_counter % 5 == 0
        if freq == "monthly":
            # 每 22 个交易日
            self._rebalance_counter += 1
            return self._rebalance_counter % 22 == 0
        return False

    # =========================================================================
    # P1: 风险平价混合（占位，P0 不调用）
    # =========================================================================

    def _blend_with_risk_parity(
        self, base: Dict[str, float]
    ) -> Dict[str, float]:
        """
        Regime 基准 + 风险平价微调 → 最终分配。

        P1 实现: 从 _vol_buffers 读取各策略滚动波动率，计算 RP 权重，
                 按 rp_blend_strength 混合。
        """
        # P1 TODO
        return self._normalize_and_clamp(base)

    # =========================================================================
    # 查询接口
    # =========================================================================

    @property
    def regime(self) -> int:
        """当前 Regime: 0=BEAR, 1=RANGE, 2=BULL。"""
        return self._regime

    @property
    def allocation(self) -> Dict[str, float]:
        """当前各策略资金分配权重（只读）。"""
        return dict(self._allocation)

    def __repr__(self) -> str:
        return (
            f"CapitalAllocator(regime={self._regime}, "
            f"allocation={self._allocation}, "
            f"strategies={self._strategy_ids})"
        )
