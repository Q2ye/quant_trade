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
from typing import Any, Dict, List, Optional, Tuple

import numpy as np
import pandas as pd

from core.engines.types.entities import BarData
from modules.strategy.constants import RunMode, StrategyType, SignalDirection, SignalType
from modules.strategy.models import TradingSignal
from modules.strategy.strategies.base.base_strategy import BaseStrategy
from shared.utils.time_utils import BEIJING_TZ, beijing_now

logger = logging.getLogger(__name__)


def _finite_or(value: Any, fallback: float = 0.0) -> float:
    """转 float 并拦截 NaN/Inf，非法值回退 fallback。

    F5 修复（对齐 high_vol_momentum_strategy._finite_or）：NaN 参与比较恒为 False，
    会绕过 `price <= 0` 这类判据——静默关闭止损、放行异常价、让异常值穿过打分门槛。
    故所有价格类取值统一经此收口。
    """
    try:
        _v = float(value)
    except (TypeError, ValueError):
        return fallback
    return _v if np.isfinite(_v) else fallback


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
        # ⚠️ 实测（2021-2026 全区间）：该守卫**从未触发过**。`_weak_days_count` 的历史最大值
        #    只有 4（分布 0×2307 / 1×103 / 2×26 / 3×12 / 4×2），远达不到 20（甚至 10）。
        #    根因：弱态分支里的 `elif enter_cond` 每日重置计数器，只有「模糊投票区」
        #    （below<3 且 above<3）才累积，而该区间从未连续超过 4 天。
        #    保留不删（语义上仍是兜底），但**不要指望它能限制走弱期时长**。
        "max_weak_days": 20,
        # regime 连续确认天数：需连续 N 天满足投票条件才允许翻转（去抖）。
        #   取值范围 1~5；1 = 当日即翻转（原行为，与本参数引入前逐字等价）；
        #   调参方向：调大 → 翻转更少、更抗震荡，但进/出更滞后。
        #   离线实测（4 指数 MA10 投票，5269 个交易日）：N=1 年均翻转 15.8 次，
        #   N=2 → 9.8、N=3 → 7.6、N=5 → 5.0；而走弱期天数占比仅 43.6% → 41.4%（N=3），
        #   即「去抖而不改变长期仓位分布」。
        "weak_confirm_days": 1,

        # —— 动量打分 ——
        "lookback_days": 25,              # 动量得分回溯窗口
        "min_score_threshold": 0.0,       # 动量得分下限（排除负动量）
        "max_score_threshold": 5.0,       # 动量得分上限（排除已暴涨的极端高分）

        # —— 过滤 ——
        # R² 趋势质量门槛。0.40 是聚宽原版移植的**未优化值**；2026-09-12 经四层验证上调至 0.47：
        #   ① 全窗口：243.94% → 293.58%
        #   ② 两段样本外（观察段 2021-07~2023-12 / 验证段 2024-01~2026-09）收益/夏普/MDD 全改善
        #   ③ 6 个滚动起始日：6/6 收益胜、6/6 回撤胜
        #      （注：6 个窗口均结束于 2026-09-11，重叠度高，不等于 6 份独立证据）
        #   ④ 候选区邻域扫描 {0.42,0.45,0.47,0.50,0.52}：**0.47 是唯一在两段都不低于
        #      各段最优值 95% 的取值**（观察段 100.0% / 验证段 99.1%）；
        #      该结论对 90%~95% 的阈值不敏感（0.47 始终在交集内）。
        #   机制：门槛越高只留「走得干净、像直线趋势」的标的——与趋势跟随第一性原理一致。
        #         太松（0.42）选进走势零散的噪音标的（两段均仅 85.3%）；
        #         太严（0.52）候选过少、持仓切换时资金调度失败（验证段 177.75% → 126.83%）。
        #   取值范围 0.45~0.50 为平坦区；⚠️ **上沿在 0.50~0.52 之间，不要再往上调**。
        "enable_r2_filter": True, "r2_threshold": 0.47,
        "enable_ma_filter": True, "ma_lookback": 10, "ma_threshold": 1.0,  # 站上 MA10
        "enable_volume_check": True, "volume_lookback": 5, "volume_threshold": 1.8,  # 量比 <1.8 拒绝放量冲顶
        "enable_loss_filter": True, "loss": 0.97,             # 近3日单日跌幅 >=3% 剔除
        # 入场涨幅门：信号日单日涨幅超过阈值则不买。
        #   机制：策略用 25 日动量在「月频尺度」选标的，却在信号**次日开盘**进场（日频尺度）。
        #         日频短期反转与月频动量方向相反 → 「当日已大涨」是负期望的入场点。
        #   实证（240 笔往返分组）：信号日涨 2~5% → 胜率 31%、平均 -0.55%、合计 -553,835；
        #         信号日下跌 0~-2% → 胜率 58%、平均 +1.38%、合计 +2,149,476。
        #   取值范围 0.01~0.20；调小 → 门更严（可能误伤真突破）；调大 → 更宽松。
        #   默认 False = 不改变引入该参数前的行为（便于 A/B 对照）。
        "enable_entry_gain_filter": False,
        "entry_max_gain_pct": 0.05,

        # —— B型阶梯主线（score 5~20 早期识别，绕过 max_score=5 天花板）——
        # ⚠️ 实测（2021-2026 全区间）：该旁路**从未触发过**。它要求 current_score > 5.0，
        #    而 1323 个 score 样本中无一超过 5.0（最高 4.99，顶在 max_score_threshold 上）；
        #    开/关该开关的 2 段回测结果**逐位相同**。
        #    保留不删：score>5 在极端趋势行情下理论可达（需 25 日约 +18.7% 且 R²≈0.9），
        #    删除会改变未来极端市况下的行为。
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
        # 退出信号重发间隔（调仓日）。原实现 `_exit_pending` 是单向阀：登记后卖出/买入/止损
        # 三处全部跳过，唯一出口是 broker 持仓归零 → 一旦退出信号丢失（价格缺失/订单被拒/
        # 长期不可成交），持仓被永久冻结且硬止损同时失效。
        #   取值范围 1~10；调小 → 重发更积极（可能重复挂单）；调大 → 更保守。
        "exit_retry_days": 3,

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
        self.weak_confirm_days = max(1, int(merged["weak_confirm_days"]))

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
        self.enable_entry_gain_filter = bool(merged["enable_entry_gain_filter"])
        self.entry_max_gain_pct = float(merged["entry_max_gain_pct"])

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
        self.exit_retry_days = max(1, int(merged.get("exit_retry_days", 3)))
        self.verbose_logging = bool(merged.get("verbose_logging", True))

        # ---- 状态 ----
        self._data_cache: Dict[str, pd.DataFrame] = {}
        self._index_cache: Dict[str, Dict[str, float]] = {}  # {index_code: {date: close}}
        self._holdings: Dict[str, Dict] = {}    # {code: {entry_price, weight, shares, entry_date, fill_date, peak_high}}
        self._pending_buys: Dict[str, dict] = {}  # 已发买入信号待次日成交
        # {code: 上次发出退出信号时的 _rebalance_seq}，用于超期重发（F3 修复）
        self._exit_pending: Dict[str, int] = {}
        self._rebalance_seq: int = 0   # 调仓序号（每调用一次 _run_rebalance 自增）
        self._pending_rows: Dict[str, list] = {}  # on_bar 累积待 flush
        self._is_weak: bool = False
        self._weak_start_date: Optional[str] = None
        self._weak_days_count: int = 0
        self._enter_streak: int = 0   # 连续满足进入条件的天数（weak_confirm_days 去抖用）
        self._exit_streak: int = 0    # 连续满足退出条件的天数
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
        self._rebalance_seq = 0
        self._pending_rows.clear()
        self._is_weak = False
        self._weak_start_date = None
        self._weak_days_count = 0
        self._enter_streak = 0
        self._exit_streak = 0
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
        self._rebalance_seq += 1

        # 0. 昨日买入信号今日开盘已成交 → 搬进 holdings
        self._move_pending_to_holdings(td)
        # 0.4 归一化持仓结构（框架恢复路径写入的字典缺 entry_date / peak_high）
        self._normalize_holdings(td)
        # 0.5 与 broker 对账（实盘/完整引擎；smoke test context=None 跳过）
        self._reconcile_holdings()
        # 0.6 持有交易日数 +1（最小持有期守卫用）
        for _code in list(self._holdings.keys()):
            self._held_days[_code] = self._held_days.get(_code, 0) + 1

        # 1. 走弱期判定
        self._update_weak_period(td)

        # 1.5 F9 守卫：当日行情整体缺失时不调仓（见 _has_fresh_data）。
        #     必须早于止损与选股——两者都以价格为判据，数据缺失时会用陈旧收盘价
        #     误触发止损、或误判「无候选」而卖出持仓切国债。
        #     放在 _update_weak_period 之后：判据依赖 _is_weak 决定候选池范围。
        if not self._has_fresh_data(td):
            logger.warning(
                f"[{self.name}] 候选池无任何标的带当日({td})行情，判定为数据缺失，"
                f"跳过本次调仓（不发信号、不动仓）"
            )
            return signals

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
        #    F4 修复：已登记退出的标的（含刚触发的硬止损）即便今日仍在目标池也不保留，
        #             否则「止损卖出成交 → 次日对账摘除 → 再被选为目标 → 立刻买回」。
        has_t1_locked_sell = False
        for code in list(self._holdings.keys()):
            if code in target_codes and code not in self._exit_pending:
                continue
            if self._holdings[code].get("fill_date") == td:
                has_t1_locked_sell = True  # T+1 未解锁，当日买入不可卖，现金未释放
                continue
            # F3 修复：已登记且未到重发间隔 → 跳过；到期仍持有则重发退出信号，
            #          防「退出信号丢失（价格缺失/订单被拒/长期不可成交）→ 持仓永久冻结」。
            if not self._should_retry_exit(code):
                continue
            self._exit_pending[code] = self._rebalance_seq
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
        """4 指数 MA10 投票判走弱期，状态跨日保持。

        - `weak_confirm_days`：需连续 N 天满足投票条件才允许翻转（去抖，默认 1 = 当日即翻转，
          与引入该参数前逐字等价）。震荡市中 MA10 被反复击穿会导致 regime 高频翻转，
          资金被在「全球池 / 中国池」之间来回甩，每次踩在错误一边。
        - `max_weak_days`：走弱期最长持续交易日，超时强制退出。
        """
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

        # 连续确认计数：条件不成立的当天即清零（要求「连续」而非「累计」）
        self._enter_streak = self._enter_streak + 1 if enter_cond else 0
        self._exit_streak = self._exit_streak + 1 if exit_cond else 0
        enter_ready = enter_cond and self._enter_streak >= self.weak_confirm_days
        exit_ready = exit_cond and self._exit_streak >= self.weak_confirm_days

        if self._is_weak:
            self._weak_days_count += 1
            if self._weak_days_count >= self.max_weak_days:
                self._is_weak = False
                self._weak_start_date = None
                self._weak_days_count = 0
            elif exit_ready:
                self._is_weak = False
                self._weak_start_date = None
                self._weak_days_count = 0
            elif enter_cond:
                self._weak_start_date = td
                self._weak_days_count = 0
        else:
            if enter_ready:
                self._is_weak = True
                self._weak_start_date = td
                self._weak_days_count = 0

        if self.verbose_logging:
            logger.info(
                f"[{self.name}] 走弱期={self._is_weak} above={above} below={below} "
                f"days={self._weak_days_count}/{self.max_weak_days}"
            )

    def _has_fresh_data(self, td: str) -> bool:
        """池内是否至少有一个标的带**当日** bar（F9 数据完整性守卫）。

        背景：F6 停牌守卫（`_bar_dates.get(code) == _last_trade_date`）会在标的
        当日无 bar 时排除该候选。若某日 ETF 数据**整体缺失**（同步故障），29 只
        候选会被全部排除 → 误判「无候选」→ `_defensive_target()` 卖出当前持仓并
        切国债 → 数据恢复后再切回来，白付两轮换手成本，且期间的止损判据也不可信。

        故：**当前 regime 下的候选池**无一带当日 bar 时，判定为数据缺失，
        `_run_rebalance` 直接返回、不动仓。

        判据用「候选池」（全球池 / 走弱期下的全球+中国池），**不含防御标的**——
        否则「只有国债有数据、候选全缺」会被误判为数据到位，仍然导致切国债。
        也正因为依赖 `_is_weak`，本守卫须在 `_update_weak_period()` 之后调用。

        Args:
            td: 本次调仓对应的交易日（调仓日，非 `_last_trade_date`——后者在
                今日无任何 bar 时会停留在昨日，导致判据失效）。
        """
        pool = self.global_pool if self._is_weak else (self.global_pool + self.china_pool)
        return any(self._bar_dates.get(c) == td for c in pool)

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
        # F5: np.any(recent <= 0) 对 NaN 恒 False，NaN 会穿透到 np.log → 打分污染
        if not np.all(np.isfinite(recent)) or np.any(recent <= 0):
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
        today = _finite_or(vols[-1], 0.0)
        if today <= 0:
            return None  # F6: 停牌/无成交（volume==0）不得按「量比 0 < 阈值」放行
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
        # F6: 停牌/无当日行情不得用陈旧数据打分——否则停牌 ETF 会被反复选中反复挂单
        if self._bar_dates.get(code) != self._last_trade_date:
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

        # 入场涨幅门：信号日单日涨幅（t 时刻已知，无未来函数）。
        # 见 DEFAULT_PARAMS 注释——月频动量选股 + 次日开盘进场，当日已大涨是负期望入场点。
        gain_1d: Optional[float] = None
        passed_entry_gain = True
        if closes.size >= 2 and closes[-2] > 0:
            gain_1d = float(closes[-1] / closes[-2] - 1.0)
            passed_entry_gain = gain_1d <= self.entry_max_gain_pct
        else:
            passed_entry_gain = False  # 数据不足 fail-closed，不产生信号

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
            "gain_1d": gain_1d,
            "passed_entry_gain": passed_entry_gain,
            "passed_mainline": passed_mainline,
            "mainline_info": mainline_info,
        }

    def _apply_filters(self, metrics: List[Dict]) -> List[Dict]:
        """走弱期保留动量+R²+入场涨幅门，正常期再叠加均线/量比/短期风控。"""
        steps: List[Tuple[str, Any, bool]] = [
            ("动量得分", lambda m: m["passed_momentum"], True),
            ("R²", lambda m: m["passed_r2"], self.enable_r2_filter),
            # 入场涨幅门对两个时期都生效：机制是「信号次日开盘接盘」，与候选池无关
            ("入场涨幅", lambda m: m["passed_entry_gain"], self.enable_entry_gain_filter),
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
                and (not self.enable_entry_gain_filter or m["passed_entry_gain"])
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
    def _stop_loss_triggered(self, entry_price: float, current_price: float) -> bool:
        """硬止损判定核（纯函数）。

        供 `_check_stop_loss`（主流程）与 `check_stop_profit_stop_loss`（审计契约）
        共用同一判据，避免两处实现分叉。
        """
        if entry_price <= 0 or current_price <= 0:
            return False
        return current_price <= entry_price * (1.0 - self.stop_loss_pct)

    def _should_retry_exit(self, code: str) -> bool:
        """退出信号是否已到重发间隔（F3）。

        `_exit_pending[code]` 记录上次发出退出信号时的调仓序号。未登记，或距上次
        已满 `exit_retry_days` 个调仓日 → 允许（重）发。原实现把 `_exit_pending`
        当作单向阀，卖出/买入/止损三处全部跳过，退出信号一旦丢失即永久冻结持仓。
        """
        last = self._exit_pending.get(code)
        if last is None:
            return True
        return (self._rebalance_seq - last) >= self.exit_retry_days

    def _check_stop_loss(self, td: str) -> List[TradingSignal]:
        signals: List[TradingSignal] = []
        for code in list(self._holdings.keys()):
            # F3: 已登记退出且未到重发间隔 → 跳过；到期仍持有则重发止损单
            if not self._should_retry_exit(code):
                continue
            if self._holdings[code].get("fill_date") == td:
                continue  # T+1 未解锁
            entry = _finite_or(self._holdings[code].get("entry_price", 0), 0.0)
            if entry <= 0:
                continue
            price = self._get_price(code)
            if price <= 0:
                continue
            if self._stop_loss_triggered(entry, price):
                self._exit_pending[code] = self._rebalance_seq
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
        # 满仓买入：金额 = 基准资本×权重，不封顶到 available_capital。
        # 轮动时序为「先卖出（broker 提前释放资金）→ 后买入」，封顶到陈旧现金会致长期半仓闲置。
        # T+1 锁定持仓未卖（现金未释放）时由 _run_rebalance 的 has_t1_locked_sell 跳过买入，
        # 兜底由 broker 资金校验拒单（策略留在旧满仓位置，符合动量逻辑）。
        # 注：这是对资金契约 §2.1 `min(capital×weight, available)` 的**有意偏离**，已在案；
        #     股数计算统一走 calculate_position_size()，与审计契约函数同源，避免分叉。
        shares = self.calculate_position_size(weight, price)
        if shares < 100:
            return None  # 不足一手，不买
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

    # 四大模块（审计契约）—— 均为**真实路径的薄封装**，不与主流程分叉。
    #   开仓：generate_entry_signals → _make_entry_signal（仓位走 calculate_position_size）
    #   平仓：generate_exit_signals  → _make_exit_signal
    #   止损：check_stop_profit_stop_loss → _stop_loss_triggered（与 _check_stop_loss 同判据）
    #   仓位：calculate_position_size → 主流程 _make_entry_signal 直接调用它
    def generate_entry_signals(self, target: Dict[str, float], reason: str = "") -> List[TradingSignal]:
        """开仓信号（契约接口）。

        Args:
            target: {标的代码: 目标权重}。
            reason: 附加说明（当前未拼入信号 reason，保留契约签名）。

        Returns:
            开仓信号列表；价格非法或不足一手的标的被跳过。

        Note:
            主流程走 `_run_rebalance`（携带完整 metrics）。此处 metrics 占位为
            {"score": 0.0, "r2": 0.0}——score/r2 仅出现在信号 reason 文案中，
            **不参与仓位计算**（仓位由显式 weight 决定），故不影响下单结果。
        """
        _ = reason
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
        """平仓信号（契约接口）：委托 `_make_exit_signal`，与主流程同源。

        卖出数量取 broker 实际持仓（`self.context.positions`），非策略自维护 shares，
        避免「broker 缩减过数量 → 策略高估 → 卖出被拒 → 资金不释放」的死锁。
        """
        signals: List[TradingSignal] = []
        for code in codes:
            sig = self._make_exit_signal(code, reason, signal_type)
            if sig:
                signals.append(sig)
        return signals

    def check_stop_profit_stop_loss(
        self, code: str, entry_price: float, current_price: float
    ) -> Optional[Tuple[str, str]]:
        """止盈止损（契约接口）：委托 `_stop_loss_triggered`，与 `_check_stop_loss` 同判据。

        Returns:
            (SignalType.value, 原因文案)；未触发返回 None。

        Note:
            本策略**不含止盈**——出场由选股轮动驱动（标的跌出目标池即换仓），
            主动止盈会截断动量。故此处只可能返回止损。
        """
        _ = code  # 判定不依赖标的代码，保留参数以符合契约签名
        entry_price = _finite_or(entry_price, 0.0)
        current_price = _finite_or(current_price, 0.0)
        if self._stop_loss_triggered(entry_price, current_price):
            stop_price = entry_price * (1.0 - self.stop_loss_pct)
            return (
                SignalType.STOP_LOSS.value,
                f"硬止损: {current_price:.3f} <= {stop_price:.3f}",
            )
        return None

    def calculate_position_size(self, weight: float, price: float) -> int:
        """仓位管理（契约接口）：按真实 sizing 口径算目标股数。

        主流程 `_make_entry_signal` 直接调用本函数，杜绝「契约函数是摆设、与主流程分叉」。

        口径：`amount = resolve_sizing_capital() × weight`，**不封顶可用现金**
        （有意偏离资金契约 §2.1 的 `min(capital×weight, available)`，理由见
        `_make_entry_signal` 注释：轮动时序下封顶陈旧现金会致长期半仓闲置），
        再向下取整到 100 股整手。

        Args:
            weight: 目标权重（0~1，超出范围按 0 取）。
            price: 委托价（元）。

        Returns:
            目标股数（100 的整数倍）；价格非法时返回 0。
        """
        price = _finite_or(price, 0.0)
        if price <= 0:
            return 0
        amount = self.resolve_sizing_capital() * max(0.0, float(weight))
        return int(amount / price / 100) * 100

    # =========================================================================
    # 持仓状态机
    # =========================================================================
    def _move_pending_to_holdings(self, td: str) -> None:
        """昨日买入信号（order_mode=open）今日开盘已成交 → 搬进 holdings。"""
        for code, pinfo in self._pending_buys.items():
            entry = _finite_or(pinfo.get("price", 0), 0.0)
            df = self._data_cache.get(code)
            if df is not None and len(df) > 0 and "open" in df.columns:
                o = _finite_or(df["open"].iloc[-1], 0.0)
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

    def _normalize_holdings(self, td: str) -> None:
        """补齐 `_holdings` 条目缺失的非关键字段。

        框架 `strategy_manager._restore_positions_from_db` 恢复持仓时写入的字典只含
        `{entry_price, weight, shares, locked}`，缺 `entry_date` / `peak_high`。
        本方法补这两个（纯记录性字段，无判据依赖）。

        ⚠️ **绝不可补 `fill_date`**（2026-09-12 修正）：
        该字典在**实盘每日被 `_restore_positions_from_db` 清空重建**
        （调用点 `strategy_manager._run_live_strategies` 每日循环），而 T+1 守卫判据是
        `fill_date == td`。若在此补为「当日」，则**每一天都成立** → 步骤 5 对每个持仓
        都置 `has_t1_locked_sell=True` 并 continue → **既不卖出、也因该标志跳过全部买入
        → 实盘永久冻结**。
        容忍的代价：框架恢复的持仓在恢复当日可被卖出（T+1 语义不完备）。该风险可接受——
        DB 中的持仓通常是往日成交；且半自动模式下卖出信号仍需人工在券商端下单，
        券商/结算会拦截真正的 T+1 违规。
        """
        for _code, h in self._holdings.items():
            if not h.get("entry_date"):
                h["entry_date"] = td
            if not h.get("peak_high"):
                h["peak_high"] = _finite_or(h.get("entry_price", 0), 0.0)
            # B4 兜底（正常路径由 state_snapshot 精确恢复，见 strategy_manager
            # `_recover_running_strategies`）：框架 `_restore_positions_from_db` 每日
            # 重建 `_holdings`，且 positions 表无建仓日信息，故重启后 `_held_days`
            # 会缺记录 → `min_hold_days` 守卫把持仓当「刚买入」多锁 N 天；
            # **重启间隔小于 N 个交易日时计数永远到不了阈值 → 策略永不轮动**。
            # 判据：有持仓但无计数 = 非本策略这些天买入的（本策略买入的经
            # `_move_pending_to_holdings` 写入 fill_date 并置 _held_days=0）。
            # 恢复来源无建仓日，保守假设「已持有足够久」，方向取不至于冻结的一侧。
            if not h.get("fill_date") and _code not in self._held_days:
                self._held_days[_code] = self.min_hold_days

    def _reconcile_holdings(self) -> None:
        """与持仓真相源对账（只做「幽灵删除」，不新增）。

        真相源优先级：
          1. `context.positions` —— 回测引擎每日 `sync_backtest_account` 注入；
             **实盘路径从不写该字段，恒为空 dict**。
          2. `self._active_positions` —— 框架 `load_live_state` 注入的 DB 持仓真相（实盘有）。

        F1 修复：原实现把空 dict 当作「broker 已无持仓」的可信证据，导致实盘每日把
        `_restore_positions_from_db` 刚恢复的 `_holdings` 全部 pop 掉，策略永久自认空仓
        并反复发建仓信号。空快照不携带信息，故两个真相源都为空时 fail-open 返回；
        回测路径仍按「broker 空仓」处理（引擎每日注入，空即真无持仓），保留幽灵清理。
        """
        if self.context is None:
            return
        source = getattr(self.context, "positions", None)
        using_context = bool(source)
        if not using_context:
            source = getattr(self, "_active_positions", None) or None
        if not source:
            if getattr(self.context, "run_mode", None) is not RunMode.BACKTEST:
                return  # 实盘/模拟盘：无真相源 → fail-open，不做任何抹除
            source = {}
        for code in list(self._exit_pending):
            bp = source.get(code)
            if bp is None or int(getattr(bp, "quantity", 0) or 0) <= 0:
                self._holdings.pop(code, None)
                self._held_days.pop(code, None)
                self._exit_pending.pop(code, None)
        if not using_context and source:
            # `_active_positions` 是 DB 真相但无成本/T+1 语义，只用于「卖出确认」，
            # 不做整体幽灵删除，避免误删刚恢复且尚未回填的持仓。
            return
        for code in list(self._holdings.keys()):
            bp = source.get(code)
            if bp is None or int(getattr(bp, "quantity", 0) or 0) <= 0:
                self._holdings.pop(code, None)
                self._held_days.pop(code, None)

    # =========================================================================
    # 工具
    # =========================================================================
    def _get_price(self, code: str) -> float:
        df = self._data_cache.get(code)
        if df is not None and len(df) > 0:
            # F5: 统一经 _finite_or 收口——NaN 比较恒 False 会绕过 price<=0 判据
            return _finite_or(df["close"].iloc[-1], 0.0)
        return 0.0

    def _append_data(self, ts_code: str, bar: BarData) -> None:
        bar_date = str(getattr(bar, "trade_date", "") or getattr(bar, "datetime", ""))[:10]
        # F5: 丢弃 close 非法（NaN/Inf/<=0）的 bar——不入缓存、不登记 bar_date，
        #     使其同时被 _score_candidate 的「当日有行情」守卫（F6）拦截。
        close = _finite_or(getattr(bar, "close", 0.0), 0.0)
        if close <= 0:
            logger.warning(
                f"[{self.name}] 丢弃非法 bar: {ts_code} {bar_date} close={getattr(bar, 'close', None)}"
            )
            return
        if bar_date:
            self._bar_dates[ts_code] = bar_date
        self._pending_rows.setdefault(ts_code, []).append([
            bar_date,
            _finite_or(getattr(bar, "open", close), close),
            _finite_or(getattr(bar, "high", close), close),
            _finite_or(getattr(bar, "low", close), close),
            close,
            _finite_or(getattr(bar, "volume", 0.0), 0.0),
            _finite_or(getattr(bar, "amount", 0.0), 0.0),
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
        except Exception as e:
            logger.warning(f"[{self.name}] 诊断信息生成失败: {e}")
            return None
