# -*- coding: utf-8 -*-
"""
跨市场动量避险轮动策略 v1.0
====================================================================================
来源：移植聚宽「五福52+单etf」策略（docs/05_策略示例/五福52+单etf.py），做减法适配本项目框架。

第一性原理：
  A股走弱时，多数行业 ETF 同跌、相关性趋同，此时「避」比「选」更重要——
  把资金从 A股资产切到低相关的跨市场/商品 ETF（黄金、纳指、标普、德国、日经、恒生、豆粕），
  在 A股强势期则回到 A股宽基/行业 ETF 做动量轮动。

移植取舍（相对原版）：
  ✅ 保留  L2 走弱期 regime（4指数 MA10 投票切换全球池）
  ✅ 保留  L3 动量得分 = 加权 log 斜率年化 × R²（趋势质量惩罚）
  ✅ 保留  L4 过滤（动量区间 + R² + MA + 量比 + 3日跌幅）
  ✅ 保留  L5 B型阶梯主线（score 5~20 早期识别，绕过 max_score 天花板）
  ✅ 保留  L6 组合（top-N + score×ratio 阈值 + 保留持仓防换手 + 相关性守卫）
  ✅ 保留  L8 仓位（score^1.5 加权 + 单只上限）
  ❌ 砍掉  L7 日内分钟趋势择时（本项目仅日线，改收盘信号→次日开盘成交 order_mode=open）
  ❌ 砍掉  L0 溢价率（需基金 NAV，本项目数据层无）、拉普拉斯滤波、量价背离（依赖分钟/震荡市）
  ❌ 砍掉  L1 动态行业池（依赖全市场 ETF 名称清洗，脆弱且幸存者偏差重，改固定池）
  ➕ 补充  硬止损 stop_loss_pct（本项目 audit-strategy.md 硬性要求：每笔开仓必须附止损价，原版无止损）

执行模型：收盘(on_bar_batch_end)决策 → 信号 order_mode=open → 次日开盘成交（对齐实盘 T+1）。
"""
import logging
import math
import uuid
from datetime import date, datetime
from typing import Any, Dict, List, Optional, Set, Tuple

import numpy as np
import pandas as pd

from core.engines.types.entities import BarData
from modules.strategy.constants import StrategyType, SignalDirection, SignalType
from modules.strategy.models import TradingSignal
from modules.strategy.strategies.base.base_strategy import BaseStrategy
from shared.utils.time_utils import BEIJING_TZ, beijing_now

logger = logging.getLogger(__name__)


class CrossMarketMomentumStrategy(BaseStrategy):
    """跨市场动量避险轮动策略 v1.0（A股弱切海外 · R²惩罚动量 · 单ETF轮动）"""

    strategy_type: StrategyType = StrategyType.ROTATION

    DEFAULT_PARAMS: Dict[str, Any] = {
        # —— 标的池（固定池，探针确认 DB 有数据；走弱期只用 global，正常期 global+china）——
        "global_etf_pool": [
            "518880.SH",  # 黄金ETF
            "513100.SH",  # 纳指100
            "513500.SH",  # 标普500
            "513030.SH",  # 德国DAX
            "513520.SH",  # 日经225
            "159920.SZ",  # 恒生ETF
            "513050.SH",  # 中概互联
            "513330.SH",  # 恒生互联
            "513180.SH",  # 恒指科技
            "159980.SZ",  # 有色
            "159985.SZ",  # 豆粕
        ],
        "china_etf_pool": [
            "510050.SH",  # 上证50
            "510300.SH",  # 沪深300
            "510500.SH",  # 中证500
            "512100.SH",  # 中证1000
            "159915.SZ",  # 创业板
            "159949.SZ",  # 创业板50
            "588080.SH",  # 科创板50
            "512880.SH",  # 证券
            "515880.SH",  # 通信
            "512480.SH",  # 半导体
            "512400.SH",  # 有色
            "512660.SH",  # 军工
            "512800.SH",  # 银行
            "512690.SH",  # 酒
            "512170.SH",  # 医疗
            "512010.SH",  # 医药
            "515030.SH",  # 新能源车
        ],
        "defensive_etf": "511010.SH",  # 国债ETF（无候选时避险）

        # —— 走弱期 regime（4 指数 MA10 投票；000510 中证A500 数据太短，换中证500）——
        "weak_indices": ["000300.SH", "000905.SH", "399006.SZ", "399101.SZ"],
        "weak_period_ma_lookback": 10,   # 指数 MA 周期
        "weak_enter_votes": 3,            # below >= 3 → 进入走弱期
        "weak_exit_votes": 3,             # above >= 3 → 退出走弱期
        "max_weak_days": 20,              # 走弱期最长持续交易日，超时强制退出

        # —— 动量打分 ——
        "lookback_days": 25,              # 动量得分回溯窗口
        "min_score_threshold": 0.0,       # 动量得分下限（排除负动量）
        "max_score_threshold": 5.0,       # 动量得分上限（排除已暴涨的极端高分）

        # —— 过滤 ——
        "enable_r2_filter": True, "r2_threshold": 0.4,        # R² 趋势质量
        "enable_ma_filter": True, "ma_lookback": 10, "ma_threshold": 1.0,  # 站上 MA10
        "enable_volume_check": True, "volume_lookback": 5, "volume_threshold": 1.8,  # 量比 <1.8 拒绝放量冲顶
        "enable_loss_filter": True, "loss": 0.97,             # 近3日单日跌幅 >=3% 剔除

        # —— B型阶梯主线（score 5~20 早期识别，绕过 max_score=5 天花板）——
        "enable_super_mainline": True,
        "mainline_score_min": 5.0,
        "mainline_score_max": 20.0,
        "mainline_days": 5,
        "mainline_min_r2": 0.85,          # 当日 R² 高位
        "mainline_min_r2_avg": 0.90,      # 近 N 日 R² 均值高位
        "mainline_min_volume_avg": 1.8,   # 近 N 日量比均值（持续放量）
        "mainline_min_score_up_days": 4,  # 近 N 日 score 抬升天数
        "mainline_min_score_growth": 2.0, # 近 N 日 score 增长倍数

        # —— 组合 ——
        "normal_holdings_num": 1,         # 正常期持仓数
        "weak_holdings_num": 1,           # 走弱期持仓数
        "score_threshold_ratio": 0.9,     # top-N 阈值系数（正常期）
        "enable_corr_filter": False,      # 相关性守卫（仅 N>1 时生效；单ETF模式无意义）
        "corr_threshold": 0.8,
        "corr_lookback_days": 60,

        # —— 仓位 ——
        "enable_position_mgmt": True,
        "position_weight_power": 1.5,     # score 幂指数
        "max_single_position": 0.5,       # 多只时单只上限
        "single_etf_max_position": 0.9,   # 仅1只时上限

        # —— 风控（本项目补充，原版无止损）——
        "stop_loss_pct": 0.08,            # 硬止损：现价 <= 入场价×(1-此值) → 卖出
        "min_hold_days": 3,               # 最小持有交易日数：未满且未止损不换仓（降换手，~28% 成本损耗）

        # —— 资金 ——
        "allocated_capital": 1000000.0,

        # —— 运行 ——
        "verbose_logging": True,
    }

    def __init__(
        self,
        name: str = "跨市场动量避险轮动v1.0",
        strategy_type: StrategyType = StrategyType.ROTATION,
        parameters: Optional[Dict[str, Any]] = None,
    ):
        super().__init__(name=name, strategy_type=strategy_type, parameters=parameters)
        merged = dict(self.DEFAULT_PARAMS)
        merged.update(parameters or {})
        self.parameters = dict(merged)

        # 标的池
        self.global_pool: List[str] = list(merged["global_etf_pool"])
        self.china_pool: List[str] = list(merged["china_etf_pool"])
        self.defensive_etf: str = str(merged["defensive_etf"])
        self._universe = list(dict.fromkeys(self.global_pool + self.china_pool + [self.defensive_etf]))

        # regime
        self.weak_indices: List[str] = list(merged["weak_indices"])
        self.weak_period_ma_lookback = int(merged["weak_period_ma_lookback"])
        self.weak_enter_votes = int(merged["weak_enter_votes"])
        self.weak_exit_votes = int(merged["weak_exit_votes"])
        self.max_weak_days = int(merged["max_weak_days"])

        # 动量
        self.lookback_days = int(merged["lookback_days"])
        self.min_score_threshold = float(merged["min_score_threshold"])
        self.max_score_threshold = float(merged["max_score_threshold"])

        # 过滤
        self.enable_r2_filter = bool(merged["enable_r2_filter"])
        self.r2_threshold = float(merged["r2_threshold"])
        self.enable_ma_filter = bool(merged["enable_ma_filter"])
        self.ma_lookback = int(merged["ma_lookback"])
        self.ma_threshold = float(merged["ma_threshold"])
        self.enable_volume_check = bool(merged["enable_volume_check"])
        self.volume_lookback = int(merged["volume_lookback"])
        self.volume_threshold = float(merged["volume_threshold"])
        self.enable_loss_filter = bool(merged["enable_loss_filter"])
        self.loss = float(merged["loss"])

        # 主线
        self.enable_super_mainline = bool(merged["enable_super_mainline"])
        self.mainline_score_min = float(merged["mainline_score_min"])
        self.mainline_score_max = float(merged["mainline_score_max"])
        self.mainline_days = int(merged["mainline_days"])
        self.mainline_min_r2 = float(merged["mainline_min_r2"])
        self.mainline_min_r2_avg = float(merged["mainline_min_r2_avg"])
        self.mainline_min_volume_avg = float(merged["mainline_min_volume_avg"])
        self.mainline_min_score_up_days = int(merged["mainline_min_score_up_days"])
        self.mainline_min_score_growth = float(merged["mainline_min_score_growth"])

        # 组合
        self.normal_holdings_num = int(merged["normal_holdings_num"])
        self.weak_holdings_num = int(merged["weak_holdings_num"])
        self.score_threshold_ratio = float(merged["score_threshold_ratio"])
        self.enable_corr_filter = bool(merged["enable_corr_filter"])
        self.corr_threshold = float(merged["corr_threshold"])
        self.corr_lookback_days = int(merged["corr_lookback_days"])

        # 仓位
        self.enable_position_mgmt = bool(merged["enable_position_mgmt"])
        self.position_weight_power = float(merged["position_weight_power"])
        self.max_single_position = float(merged["max_single_position"])
        self.single_etf_max_position = float(merged["single_etf_max_position"])

        # 风控
        self.stop_loss_pct = float(merged["stop_loss_pct"])
        self.min_hold_days = int(merged.get("min_hold_days", 3))
        self.verbose_logging = bool(merged.get("verbose_logging", True))

        # ---- 状态 ----
        self._data_cache: Dict[str, pd.DataFrame] = {}
        self._index_cache: Dict[str, Dict[str, float]] = {}  # {index_code: {date: close}}
        self._holdings: Dict[str, Dict] = {}    # {code: {entry_price, weight, shares, entry_date, fill_date, peak_high}}
        self._pending_buys: Dict[str, dict] = {}  # 已发买入信号待次日成交
        self._exit_pending: Set[str] = set()
        self._pending_rows: Dict[str, list] = {}  # on_bar 累积待 flush
        self._is_weak: bool = False
        self._weak_start_date: Optional[str] = None
        self._weak_days_count: int = 0
        self._last_trade_date: str = ""
        self._bar_dates: Dict[str, str] = {}
        self._held_days: Dict[str, int] = {}  # {code: 持有交易日数}，最小持有期守卫用

    # =========================================================================
    # 生命周期
    # =========================================================================
    def on_init(self) -> None:
        logger.info(
            f"[{self.name}] 初始化: 全球池{len(self.global_pool)}只 + 中国池{len(self.china_pool)}只 + "
            f"防御{self.defensive_etf} | 持仓≤{self.normal_holdings_num}只 | "
            f"动量={self.lookback_days}d score∈[{self.min_score_threshold},{self.max_score_threshold}] "
            f"R²>{self.r2_threshold} | 硬止损{self.stop_loss_pct:.0%}"
        )

    async def on_start(self) -> None:
        self._data_cache.clear()
        self._index_cache.clear()
        self._holdings.clear()
        self._pending_buys.clear()
        self._exit_pending.clear()
        self._pending_rows.clear()
        self._is_weak = False
        self._weak_start_date = None
        self._weak_days_count = 0
        self._last_trade_date = ""
        self._bar_dates.clear()
        self._held_days.clear()

        # 加载 regime 指数日线（走弱期 MA10 判定用）
        sf = getattr(self, "_db_session_factory", None)
        if sf:
            try:
                from sqlalchemy import text
                async with sf() as db:
                    for code in self.weak_indices:
                        rows = (await db.execute(text(
                            "SELECT trade_date, close FROM index_daily "
                            "WHERE ts_code = :c ORDER BY trade_date"
                        ), {"c": code})).fetchall()
                        self._index_cache[code] = {str(r[0])[:10]: float(r[1]) for r in rows}
                logger.info(f"[{self.name}] regime 指数加载: {[(c, len(v)) for c, v in self._index_cache.items()]}")
            except Exception as e:
                logger.warning(f"[{self.name}] regime 指数加载失败（走弱期判定降级为常正常）: {e}")

    def on_stop(self) -> None:
        self._data_cache.clear()
        self._index_cache.clear()
        self._holdings.clear()
        self._pending_buys.clear()
        self._exit_pending.clear()
        self._pending_rows.clear()
        self._held_days.clear()

    # =========================================================================
    # 数据流
    # =========================================================================
    def on_bar(self, bar: BarData) -> List[TradingSignal]:
        try:
            self._append_data(bar.ts_code, bar)
            td = str(getattr(bar, "trade_date", "") or getattr(bar, "datetime", ""))[:10]
            if td:
                self._last_trade_date = td
        except Exception as e:
            logger.error(f"[{self.name}] on_bar 异常 {bar.ts_code}: {e}", exc_info=True)
        return []

    def on_bar_batch_end(self, trade_date: Any = None) -> List[TradingSignal]:
        signals: List[TradingSignal] = []
        try:
            td = str(trade_date)[:10] if trade_date else self._last_trade_date
            if not td:
                return signals
            self._last_trade_date = td
            self._flush_pending_rows()
            signals = self._run_rebalance(td)
        except Exception as e:
            logger.error(f"[{self.name}] on_bar_batch_end 异常 {trade_date}: {e}", exc_info=True)
        return signals

    # =========================================================================
    # 主调仓
    # =========================================================================
    def _run_rebalance(self, td: str) -> List[TradingSignal]:
        signals: List[TradingSignal] = []
        if len(self._data_cache) < 3:
            return signals

        # 0. 昨日买入信号今日开盘已成交 → 搬进 holdings
        self._move_pending_to_holdings(td)
        # 0.5 与 broker 对账（实盘/完整引擎；smoke test context=None 跳过）
        self._reconcile_holdings()
        # 0.6 持有交易日数 +1（最小持有期守卫用）
        for _code in list(self._holdings.keys()):
            self._held_days[_code] = self._held_days.get(_code, 0) + 1

        # 1. 走弱期判定
        self._update_weak_period(td)

        # 2. 硬止损（持仓）
        signals.extend(self._check_stop_loss(td))

        # 2.5 最小持有期守卫（降换手）：持仓未满 min_hold_days 且本次未触发止损 → 跳过换仓。
        # 止损优先：止损卖出已进 signals，此时须继续换仓补位，不受最小持有期约束。
        if self.min_hold_days > 0 and self._holdings and not signals:
            if all(self._held_days.get(_c, 0) < self.min_hold_days for _c in self._holdings):
                return signals

        # 3. 选股
        metrics = [self._score_candidate(c) for c in self._candidate_pool()]
        metrics = [m for m in metrics if m is not None]
        targets = self._select_targets(metrics)

        # 4. 无候选 → 防御
        if not targets:
            targets = self._defensive_target()

        target_codes = [m["etf"] for m in targets]

        # 5. 卖出：持仓不在目标池（order_mode=open，次日开盘成交，broker 会提前释放现金）
        has_t1_locked_sell = False
        for code in list(self._holdings.keys()):
            if code in target_codes:
                continue
            if self._holdings[code].get("fill_date") == td:
                has_t1_locked_sell = True  # T+1 未解锁，当日买入不可卖，现金未释放
                continue
            if code in self._exit_pending:
                continue
            self._exit_pending.add(code)
            sig = self._make_exit_signal(code, "轮动换仓: 不在目标池")
            if sig:
                signals.append(sig)

        # 6. 买入：目标不在持仓。若存在 T+1 锁定持仓待卖（现金被占），买入推迟到次日，防「卖出被 T+1 跳过→买入超现金」。
        if has_t1_locked_sell:
            return signals

        weights = self._compute_position_weights(targets)
        for m in targets:
            code = m["etf"]
            if code in self._holdings or code in self._pending_buys or code in self._exit_pending:
                continue
            price = self._get_price(code)
            if price <= 0:
                continue
            weight = float(weights.get(code, 0.0))
            if weight <= 0:
                continue
            sig = self._make_entry_signal(code, m, weight, price)
            if sig:
                signals.append(sig)
                self._pending_buys[code] = {
                    "weight": weight, "price": price, "signal_date": td, "shares": sig.quantity,
                }

        return signals

    # =========================================================================
    # 走弱期 regime（L2）
    # =========================================================================
    def _update_weak_period(self, td: str) -> None:
        """4 指数 MA10 投票判走弱期，状态跨日保持，带 max_weak_days 强制退出。"""
        if not self._index_cache:
            return
        above, below = 0, 0
        for code in self.weak_indices:
            closes_map = self._index_cache.get(code, {})
            dates = sorted(d for d in closes_map if d <= td)
            if len(dates) < self.weak_period_ma_lookback:
                continue
            recent = [closes_map[d] for d in dates[-self.weak_period_ma_lookback:]]
            current = float(recent[-1])
            ma = float(np.mean(recent))
            if current > ma:
                above += 1
            elif current < ma:
                below += 1

        enter_cond = below >= self.weak_enter_votes
        exit_cond = above >= self.weak_exit_votes

        if self._is_weak:
            self._weak_days_count += 1
            if self._weak_days_count >= self.max_weak_days:
                self._is_weak = False
                self._weak_start_date = None
                self._weak_days_count = 0
            elif exit_cond:
                self._is_weak = False
                self._weak_start_date = None
                self._weak_days_count = 0
            elif enter_cond:
                self._weak_start_date = td
                self._weak_days_count = 0
        else:
            if enter_cond:
                self._is_weak = True
                self._weak_start_date = td
                self._weak_days_count = 0

        if self.verbose_logging:
            logger.info(
                f"[{self.name}] 走弱期={self._is_weak} above={above} below={below} "
                f"days={self._weak_days_count}/{self.max_weak_days}"
            )

    def _candidate_pool(self) -> List[str]:
        """走弱期只用全球/商品池，正常期用全球+中国池（排除防御标的）。"""
        if self._is_weak:
            return [c for c in self.global_pool if c in self._data_cache]
        return [c for c in (self.global_pool + self.china_pool) if c in self._data_cache]

    # =========================================================================
    # 动量打分（L3）+ 过滤（L4）+ 主线（L5）
    # =========================================================================
    def _calc_momentum_score(
        self, closes: np.ndarray, lookback: int
    ) -> Tuple[Optional[float], Optional[float], Optional[float]]:
        """动量得分 = 加权 log 斜率年化 × R²（移植五福 calculate_momentum_score，保持原口径）。"""
        closes = np.asarray(closes, dtype=np.float64)
        if closes.size < lookback + 1:
            return None, None, None
        recent = closes[-(lookback + 1):]
        if np.any(recent <= 0):
            return None, None, None
        y = np.log(recent)
        x = np.arange(len(y), dtype=np.float64)
        weights = np.linspace(1.0, 2.0, len(y))
        W = weights ** 2
        W_sum = float(np.sum(W))
        if W_sum <= 0:
            return None, None, None
        x_bar = float(np.sum(W * x) / W_sum)
        y_bar = float(np.sum(W * y) / W_sum)
        dx = x - x_bar
        dy = y - y_bar
        var_x = float(np.sum(W * dx ** 2))
        if var_x <= 0:
            return 0.0, 0.0, 0.0
        slope = float(np.sum(W * dx * dy) / var_x)
        intercept = y_bar - slope * x_bar
        annualized = float(math.exp(slope * 250.0) - 1.0)
        y_pred = slope * x + intercept
        ss_res = float(np.sum(weights * (y - y_pred) ** 2))
        ss_tot = float(np.sum(weights * (y - float(np.mean(y))) ** 2))
        r2 = 1.0 - ss_res / ss_tot if ss_tot > 0 else 0.0
        return float(annualized * r2), annualized, r2

    def _calc_volume_ratio(self, vols: np.ndarray, lookback: int) -> Optional[float]:
        """量比 = 今日量 / 前 N 日均量（拒绝放量冲顶）。"""
        vols = np.asarray(vols, dtype=np.float64)
        if vols.size < lookback + 1:
            return None
        today = float(vols[-1])
        base = vols[-(lookback + 1):-1]
        if np.any(base <= 0) or np.any(np.isnan(base)):
            return None
        avg = float(np.mean(base))
        if avg <= 0:
            return None
        return today / avg

    def _eval_mainline(self, closes: np.ndarray, vols: np.ndarray) -> Tuple[bool, Dict]:
        """B型阶梯主线：score∈(min,max] 且近N日阶梯抬升 + R²高位 + 持续放量。"""
        if not self.enable_super_mainline:
            return False, {}
        days = self.mainline_days
        lb = self.lookback_days
        if closes.size < lb + days + 1:
            return False, {}
        scores, r2s, vrs = [], [], []
        for offset in range(days - 1, -1, -1):
            end = closes.size - offset
            sub = closes[:end]
            if sub.size < lb + 1:
                return False, {}
            score, _ann, r2 = self._calc_momentum_score(sub, lb)
            if score is None or r2 is None:
                return False, {}
            scores.append(float(score))
            r2s.append(float(r2))
            vrs.append(self._calc_volume_ratio(vols[:end], self.volume_lookback))

        valid_vrs = [v for v in vrs if v is not None]
        if len(valid_vrs) < 3:
            return False, {"reason": "volume_none"}
        fallback = float(np.mean(valid_vrs))
        vrs = [fallback if v is None else float(v) for v in vrs]

        current_score = scores[-1]
        current_r2 = r2s[-1]
        r2_avg = float(np.mean(r2s))
        vol_avg = float(np.mean(vrs))
        score_up_days = sum(1 for i in range(1, len(scores)) if scores[i] >= scores[i - 1])
        start_score = scores[0]
        if start_score > 0:
            score_growth = current_score / start_score
        else:
            score_growth = float("inf") if current_score > 0 else 0.0

        passed = (
            self.mainline_score_min < current_score <= self.mainline_score_max
            and current_r2 >= self.mainline_min_r2
            and r2_avg >= self.mainline_min_r2_avg
            and vol_avg >= self.mainline_min_volume_avg
            and score_up_days >= self.mainline_min_score_up_days
            and score_growth >= self.mainline_min_score_growth
        )
        info = {
            "current_score": current_score, "current_r2": current_r2,
            "r2_avg": r2_avg, "vol_avg": vol_avg, "score_up_days": score_up_days,
            "score_growth": score_growth, "reason": "pass" if passed else "fail",
        }
        return passed, info

    def _score_candidate(self, code: str) -> Optional[Dict]:
        df = self._data_cache.get(code)
        if df is None or df.empty:
            return None
        closes = df["close"].values.astype(np.float64)
        vols = df["volume"].values.astype(np.float64) if "volume" in df.columns else np.zeros_like(closes)
        if closes.size < self.lookback_days + 1:
            return None
        current = float(closes[-1])
        if current <= 0:
            return None

        score, annualized, r2 = self._calc_momentum_score(closes, self.lookback_days)
        if score is None:
            return None
        passed_momentum = self.min_score_threshold <= score <= self.max_score_threshold
        vr = self._calc_volume_ratio(vols, self.volume_lookback)
        passed_volume = vr is not None and vr < self.volume_threshold

        passed_loss = True
        if closes.size >= 4:
            day1 = closes[-1] / closes[-2]
            day2 = closes[-2] / closes[-3]
            day3 = closes[-3] / closes[-4]
            if min(day1, day2, day3) < self.loss:
                passed_loss = False

        passed_r2 = r2 > self.r2_threshold

        passed_ma = True
        ma_val = None
        if closes.size >= self.ma_lookback:
            ma_val = float(np.mean(closes[-self.ma_lookback:]))
            passed_ma = current > ma_val * self.ma_threshold
        else:
            passed_ma = False

        passed_mainline, mainline_info = self._eval_mainline(closes, vols)

        return {
            "etf": code,
            "score": float(score),
            "annualized": float(annualized) if annualized is not None else 0.0,
            "r2": float(r2) if r2 is not None else 0.0,
            "volume_ratio": vr,
            "passed_momentum": passed_momentum,
            "passed_r2": passed_r2,
            "passed_ma": passed_ma,
            "passed_volume": passed_volume,
            "passed_loss": passed_loss,
            "passed_mainline": passed_mainline,
            "mainline_info": mainline_info,
        }

    def _apply_filters(self, metrics: List[Dict]) -> List[Dict]:
        """走弱期只保留动量+R²，正常期全量过滤（移植五福 apply_filters）。"""
        steps: List[Tuple[str, Any, bool]] = [
            ("动量得分", lambda m: m["passed_momentum"], True),
            ("R²", lambda m: m["passed_r2"], self.enable_r2_filter),
        ]
        if not self._is_weak:
            steps += [
                ("均线", lambda m: m["passed_ma"], self.enable_ma_filter),
                ("成交量", lambda m: m["passed_volume"], self.enable_volume_check),
                ("短期风控", lambda m: m["passed_loss"], self.enable_loss_filter),
            ]
        filtered = metrics[:]
        for _name, cond, enabled in steps:
            if enabled:
                filtered = [m for m in filtered if cond(m)]
        return filtered

    # =========================================================================
    # 组合（L6）
    # =========================================================================
    def _select_targets(self, metrics: List[Dict]) -> List[Dict]:
        filtered = self._apply_filters(metrics)
        if self.enable_super_mainline:
            normal_codes = {m["etf"] for m in filtered}
            mainline = [
                m for m in metrics
                if m["passed_mainline"] and m["etf"] not in normal_codes
                and (not self.enable_loss_filter or m["passed_loss"])
                and (not (self.enable_ma_filter and self._is_weak) or m["passed_ma"])
            ]
            filtered = filtered + mainline
        filtered.sort(key=lambda m: m["score"], reverse=True)
        top_10 = filtered[:10]
        if not top_10:
            return []

        n = self.weak_holdings_num if self._is_weak else self.normal_holdings_num
        if len(top_10) >= n:
            ref_score = top_10[n - 1]["score"]
            ratio = self.score_threshold_ratio if not self._is_weak else 1.0
            thr = ref_score * ratio
            candidates = [m for m in top_10 if m["score"] >= thr]
        else:
            candidates = top_10[:]

        # 保留持仓优先（防频繁换手）
        held = [m for m in candidates if m["etf"] in self._holdings]
        if len(held) >= n:
            final = sorted(held, key=lambda m: m["score"], reverse=True)[:n]
        else:
            need = n - len(held)
            held_codes = {h["etf"] for h in held}
            remaining = [m for m in candidates if m["etf"] not in held_codes]
            if self.enable_corr_filter and n > 1:
                additional = self._apply_corr_guard(remaining, held, need)
            else:
                additional = remaining[:need]
            final = held + additional

        if self.verbose_logging:
            logger.info(
                f"[{self.name}] 候选={len(filtered)} 目标={[m['etf'] for m in final]} "
                f"top1={final[0]['etf']}(score={final[0]['score']:.2f})" if final else "[无候选]"
            )
        return final

    def _defensive_target(self) -> List[Dict]:
        if self.defensive_etf and self.defensive_etf in self._data_cache:
            price = self._get_price(self.defensive_etf)
            if price > 0:
                return [{"etf": self.defensive_etf, "score": 0.0}]
        return []

    def _apply_corr_guard(self, ordered: List[Dict], already: List[Dict], need: int) -> List[Dict]:
        selected: List[Dict] = []
        if need <= 0 or not ordered:
            return selected
        chosen = [m["etf"] for m in already]
        for m in ordered:
            if len(selected) >= need:
                break
            skip = False
            for held in chosen:
                corr = self._pair_corr(m["etf"], held)
                if corr is not None and corr >= self.corr_threshold:
                    skip = True
                    break
            if skip:
                continue
            selected.append(m)
            chosen.append(m["etf"])
        return selected

    def _pair_corr(self, a: str, b: str) -> Optional[float]:
        da, db = self._data_cache.get(a), self._data_cache.get(b)
        if da is None or db is None:
            return None
        ca = da["close"].values.astype(np.float64)
        cb = db["close"].values.astype(np.float64)
        n = min(len(ca), len(cb), self.corr_lookback_days + 1)
        if n < 20:
            return None
        ra = np.diff(np.log(ca[-n:]))
        rb = np.diff(np.log(cb[-n:]))
        if np.std(ra) == 0 or np.std(rb) == 0:
            return None
        return float(np.corrcoef(ra, rb)[0, 1])

    # =========================================================================
    # 仓位（L8）
    # =========================================================================
    def _compute_position_weights(self, targets: List[Dict]) -> Dict[str, float]:
        n = len(targets)
        if n == 0:
            return {}
        if not self.enable_position_mgmt:
            return {m["etf"]: 1.0 / n for m in targets}
        raw: Dict[str, float] = {}
        for m in targets:
            v = max(float(m.get("score", 0.0)), 0.0)
            raw[m["etf"]] = v ** self.position_weight_power
        total = float(sum(raw.values()))
        if total <= 0:
            weights = {m["etf"]: 1.0 / n for m in targets}
        else:
            weights = {k: v / total for k, v in raw.items()}
        cap = self.single_etf_max_position if n == 1 else self.max_single_position
        return self._apply_cap(weights, cap)

    @staticmethod
    def _apply_cap(weights: Dict[str, float], cap: float) -> Dict[str, float]:
        """将权重限制在 cap 内，超出部分按比例注水给未触顶标的。"""
        cap = max(0.0, min(1.0, float(cap)))
        w = dict(weights)
        etfs = list(w.keys())
        for _ in range(len(etfs) + 1):
            over = [e for e in etfs if w[e] > cap + 1e-12]
            if not over:
                break
            excess = float(sum(w[e] - cap for e in over))
            for e in over:
                w[e] = cap
            uncapped = [e for e in etfs if e not in over]
            sub = float(sum(w[e] for e in uncapped))
            if sub <= 0:
                break
            for e in uncapped:
                w[e] += excess * (w[e] / sub)
        for e in etfs:
            if w[e] > cap:
                w[e] = cap
        return w

    # =========================================================================
    # 风控（L9 本项目补充硬止损）
    # =========================================================================
    def _check_stop_loss(self, td: str) -> List[TradingSignal]:
        signals: List[TradingSignal] = []
        for code in list(self._holdings.keys()):
            if code in self._exit_pending:
                continue
            if self._holdings[code].get("fill_date") == td:
                continue  # T+1 未解锁
            entry = float(self._holdings[code].get("entry_price", 0) or 0)
            if entry <= 0:
                continue
            price = self._get_price(code)
            if price <= 0:
                continue
            stop_price = entry * (1.0 - self.stop_loss_pct)
            if price <= stop_price:
                self._exit_pending.add(code)
                sig = self._make_exit_signal(
                    code,
                    f"硬止损: 现价{price:.3f} <= 入场{entry:.3f}×(1-{self.stop_loss_pct:.0%})",
                    SignalType.STOP_LOSS,
                )
                if sig:
                    signals.append(sig)
        return signals

    # =========================================================================
    # 信号构造（四大模块）
    # =========================================================================
    def _make_entry_signal(self, code: str, metrics: Dict, weight: float, price: float) -> Optional[TradingSignal]:
        capital = self.resolve_sizing_capital()
        # 满仓买入：金额 = 基准资本×权重，不封顶到 available_capital。
        # 轮动时序为「先卖出（broker 提前释放资金）→ 后买入」，封顶到陈旧现金会致长期半仓闲置。
        # T+1 锁定持仓未卖（现金未释放）时由 _run_rebalance 的 has_t1_locked_sell 跳过买入，
        # 兜底由 broker 资金校验拒单（策略留在旧满仓位置，符合动量逻辑）。
        amount = capital * weight
        if amount < price * 100:
            return None  # 现金不足一手，不买
        shares = int(amount / price / 100) * 100
        if shares < 100:
            return None
        sig = TradingSignal(
            id=self._gen_id(),
            strategy_id=self.name,
            strategy_name=self.name,
            ts_code=code,
            signal_type=SignalType.ENTRY,
            direction=SignalDirection.LONG,
            price=price,
            quantity=shares,
            amount=shares * price,
            confidence=0.7,
            reason=(
                f"跨市场轮动买入: score={metrics.get('score', 0):.2f} "
                f"R²={metrics.get('r2', 0):.2f} 仓{weight:.0%}"
            ),
            timestamp=beijing_now(),
            order_mode="open",
            stop_loss_price=round(price * (1.0 - self.stop_loss_pct), 4),
        )
        sig.weight = weight
        return sig

    def _make_exit_signal(
        self, code: str, reason: str, signal_type: SignalType = SignalType.EXIT
    ) -> Optional[TradingSignal]:
        price = self._get_price(code)
        if price <= 0:
            return None
        shares = int(self._holdings.get(code, {}).get("shares", 0) or 0)
        # 满仓买入可能被 broker「资金不足缩减」，策略自维护 shares 会高估实际持仓，
        # 导致卖出「可卖数量不足」被拒 → 资金不释放 → 后续买入死锁。以 broker 实际持仓数量为准。
        bp = getattr(self.context, "positions", None) if self.context else None
        if bp:
            _pos = bp.get(code)
            _qty = int(getattr(_pos, "quantity", 0) or 0) if _pos is not None else 0
            if _qty > 0:
                shares = _qty
        return TradingSignal(
            id=self._gen_id(),
            strategy_id=self.name,
            strategy_name=self.name,
            ts_code=code,
            signal_type=signal_type,
            direction=SignalDirection.CLOSE_LONG,
            price=price,
            quantity=shares,
            amount=shares * price,
            confidence=0.8,
            reason=reason,
            timestamp=beijing_now(),
            order_mode="open",
        )

    # 四大模块纯函数（审计契约）
    def generate_entry_signals(self, target: Dict[str, float], reason: str = "") -> List[TradingSignal]:
        signals: List[TradingSignal] = []
        for code, weight in target.items():
            price = self._get_price(code)
            if price <= 0:
                continue
            sig = self._make_entry_signal(code, {"score": 0.0, "r2": 0.0}, weight, price)
            if sig:
                signals.append(sig)
        return signals

    def generate_exit_signals(
        self, codes: List[str], reason: str = "", signal_type: SignalType = SignalType.EXIT
    ) -> List[TradingSignal]:
        signals: List[TradingSignal] = []
        for code in codes:
            sig = self._make_exit_signal(code, reason, signal_type)
            if sig:
                signals.append(sig)
        return signals

    def check_stop_profit_stop_loss(
        self, code: str, entry_price: float, current_price: float
    ) -> Optional[Tuple[str, str]]:
        if entry_price <= 0 or current_price <= 0:
            return None
        if current_price <= entry_price * (1.0 - self.stop_loss_pct):
            return (SignalType.STOP_LOSS.value, f"硬止损: {current_price:.3f} <= {entry_price*(1-self.stop_loss_pct):.3f}")
        return None

    def calculate_position_size(self, weight: float) -> float:
        return max(0.0, min(1.0, float(weight)))

    # =========================================================================
    # 持仓状态机
    # =========================================================================
    def _move_pending_to_holdings(self, td: str) -> None:
        """昨日买入信号（order_mode=open）今日开盘已成交 → 搬进 holdings。"""
        for code, pinfo in self._pending_buys.items():
            entry = float(pinfo.get("price", 0) or 0)
            df = self._data_cache.get(code)
            if df is not None and len(df) > 0 and "open" in df.columns:
                o = float(df["open"].iloc[-1])
                if o > 0:
                    entry = o
            self._holdings[code] = {
                "entry_price": entry,
                "weight": float(pinfo.get("weight", 0.0)),
                "shares": int(pinfo.get("shares", 0)),
                "entry_date": str(pinfo.get("signal_date", td))[:10],
                "fill_date": td,
                "peak_high": entry,
            }
            self._held_days[code] = 0
        self._pending_buys.clear()

    def _reconcile_holdings(self) -> None:
        """与 broker 对账（smoke test context=None 跳过）。"""
        if self.context is None:
            return
        broker_positions = getattr(self.context, "positions", None)
        if broker_positions is None:
            return
        for code in list(self._exit_pending):
            bp = broker_positions.get(code)
            if bp is None or int(getattr(bp, "quantity", 0) or 0) <= 0:
                self._holdings.pop(code, None)
                self._held_days.pop(code, None)
                self._exit_pending.discard(code)
        for code in list(self._holdings.keys()):
            bp = broker_positions.get(code)
            if bp is None or int(getattr(bp, "quantity", 0) or 0) <= 0:
                self._holdings.pop(code, None)
                self._held_days.pop(code, None)

    # =========================================================================
    # 工具
    # =========================================================================
    def _get_price(self, code: str) -> float:
        df = self._data_cache.get(code)
        if df is not None and len(df) > 0:
            return float(df["close"].iloc[-1])
        return 0.0

    def _append_data(self, ts_code: str, bar: BarData) -> None:
        bar_date = str(getattr(bar, "trade_date", "") or getattr(bar, "datetime", ""))[:10]
        if bar_date:
            self._bar_dates[ts_code] = bar_date
        self._pending_rows.setdefault(ts_code, []).append([
            bar_date,
            getattr(bar, "open", bar.close),
            getattr(bar, "high", bar.close),
            getattr(bar, "low", bar.close),
            bar.close,
            getattr(bar, "volume", 0.0),
            getattr(bar, "amount", 0.0),
        ])

    def _flush_pending_rows(self) -> None:
        if not self._pending_rows:
            return
        cols = ["trade_date", "open", "high", "low", "close", "volume", "amount"]
        for code, rows in self._pending_rows.items():
            if not rows:
                continue
            new_df = pd.DataFrame(rows, columns=cols)
            df = self._data_cache.get(code)
            if df is None or len(df) == 0:
                self._data_cache[code] = new_df
            else:
                self._data_cache[code] = pd.concat([df, new_df], ignore_index=True)
            keep = self.lookback_days + self.mainline_days + 30
            if len(self._data_cache[code]) > keep:
                self._data_cache[code] = self._data_cache[code].tail(keep).reset_index(drop=True)
        self._pending_rows.clear()

    @staticmethod
    def _gen_id() -> str:
        return str(uuid.uuid4())

    # =========================================================================
    # 查询接口
    # =========================================================================
    def get_parameters(self) -> Dict[str, Any]:
        return {
            "strategy_version": "v1.0",
            "universe_size": len(self._universe),
            "is_weak": self._is_weak,
            "holding_count": len(self._holdings),
            "normal_holdings_num": self.normal_holdings_num,
            "stop_loss_pct": self.stop_loss_pct,
        }

    def get_daily_diagnostic(self) -> Optional[Dict[str, Any]]:
        try:
            return {
                "holdings": list(self._holdings.keys()),
                "pending_buys": list(self._pending_buys.keys()),
                "is_weak": self._is_weak,
                "weak_days": self._weak_days_count,
            }
        except Exception:
            return None
