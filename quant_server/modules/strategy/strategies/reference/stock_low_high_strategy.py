# -*- coding: utf-8 -*-
"""
沪深主板强势股低吸轮动策略 — 行业黑名单v3 — 移植自聚宽高抛低吸策略

聚宽原文: https://www.joinquant.com/post/75503

核心逻辑：
  1. 选股：全市场扫描，筛选条件：
     - 仅 00/60 开头主板股（排除双创/北交所）
     - 排除 ST、新股（上市不满30日）、停牌、涨停
     - 昨日收阳线 + 涨幅 >= 0.7%
     - MA5 > MA20（多头排列）
     - 成交量 >= 近20日均量 1.2 倍
     - ROC > 5 且 MACD 金叉
     - 价格低于 20 日新高 >= 0.15%（低吸位置）
  2. 持仓：最多 3 只，半仓轮动
  3. 风控：通用止损 4%，非池内止盈（从高点回落 2%）

适配说明（与聚宽原版的区别）：
  - 你
    系统策略改为单次 rebalance 中完成（9:40 初筛 → 9:51 复检一次完成）
  - 原版使用 talib，改为 numpy/pandas 实现
  - 原版使用 get_price/attribute_history，改为策略内 DataFrame 缓存
  - 原版有半仓轮动逻辑，系统回测中通过 Broker 资金管理自动实现
  - v6.2: 调仓在 on_bar_batch_end（当日全部 bar 推送完毕后由框架调用）执行，
    确保全市场缓存统一包含当日数据，"今日/昨日"语义一致；信号 T+1 撮合，无前视。
    注意：旧接口 BacktestEngine.run_backtest()（仅单元测试用）逐股推送、
    不触发该 hook，本策略在该路径下不产生调仓信号。
"""

import logging
import numpy as np
import pandas as pd
from datetime import datetime, date, timedelta
from typing import Any, Dict, List, Optional, Set, Tuple

from core.engines.types.entities import BarData
from modules.strategy.constants import StrategyType, SignalDirection, SignalType
from modules.strategy.models import TradingSignal
from modules.strategy.strategies.base.base_strategy import BaseStrategy

logger = logging.getLogger(__name__)


class StockLowHighStrategy(BaseStrategy):
    """
    沪深主板强势股低吸轮动策略 — 行业黑名单v3。

    策略类型：CUSTOM
    全市场扫描选股 + 半仓轮动。

    ============================================================================
    不同市场环境下的表现特征（基于 2021.07~2026.07 五年回测实证）
    ============================================================================

    A 股牛市（如 2024-2025）:
      年化可达 40-60%。策略核心引擎（涨放量+均线多头+MACD金叉+低吸位）
      与趋势牛高度共振——每天都有大量符合条件的强势股回调买点。
      池内股「不止盈」机制让利润充分奔跑，单票贡献可达 100%+。
      年线门（CSI500 > MA250）全程放行，仓位上限 = max_positions。

    A 股熊市（如 2022）:
      年线门（csi500_annual_gate）是跨周期生存的绝对关键。
      → 2022 全年 CSI500 运行于 250 日均线下方 → 年线门强制停买。
      → 关闭年线门的 5 年期总收益从 +47.5% 恶化为 -53%。
      存量持仓仍按统一止损管理，但不开新仓——避免在下跌趋势中持续抄底。
      策略净值在熊市年通常轻微下跌（-5% ~ -15%），远优于满仓持有。

    震荡市（如 2023）:
      每日选股条件在无趋势的市场中产出大量脉冲式假信号（今日入选、
      明日跌出池 → 止损 -4%）。震荡市成交量过滤（只买流动性前 50%）
      和池内池外止盈区分（池内不止盈防过早卖出）共同将磨损控制住。
      年化通常 0 ~ +10%，不会大亏但也不会大赚。

    跨周期复利结构:
      ┌─────────┬──────────┬─────────────────────────────┐
      │  年份   │ 市场环境 │  策略表现      │  关键机制   │
      ├─────────┼──────────┼─────────────────────────────┤
      │ 2021H2  │ 震荡转弱 │  ~0%           │ 年线门守卫  │
      │ 2022    │ 全面熊市 │  -8% ~ -15%    │ 年线门停买  │
      │ 2023    │ 震荡     │  +5% ~ +10%    │ 池内不止盈  │
      │ 2024    │ 趋势牛   │ +30% ~ +60%    │ 强势股奔跑  │
      │ 2025    │ 结构牛   │ +20% ~ +40%    │ 低吸+轮动   │
      │ 2026H1  │ 震荡     │  0% ~ +5%      │ 三档风控    │
      ├─────────┼──────────┼─────────────────────────────┤
      │ 5年累计 │ 混合     │ +50% ~ +60%    │ 年化 9-10%  │
      └─────────┴──────────┴─────────────────────────────┘

    为什么五年年化只有 ~10% 而单年可达 60%：
      这是复利数学，不是策略退化。5 年总收益 60% 不是每年平分 12%，
      而是 -10% → +5% → +30% → +25% → +5% 的连乘。单年 60% 只看
      最好的 1 年，5 年回测把它和熊市年、震荡年放在同一个复利公式里。
      三窗口（3/5/10年）的分层验证保证参数在每种市场中都稳定，而非
      只在特定的市场环境中有效。
    """

    strategy_type: StrategyType = StrategyType.CUSTOM

    # 主板股票前缀（与聚宽原版一致）
    ALLOW_PREFIX: Tuple[str, ...] = ('000', '002', '600', '603', '601', '605')
    FORBID_PREFIX: Tuple[str, ...] = ('300', '688', '8', '4', '001', '003')

    # v6.8 regime ETF 宽度门数据池（与多资产趋势轮动 DEFAULT_ETF_POOL 一致；
    # 刻意复制而非 import——本策略代码经 DB exec 部署，须自包含）
    REGIME_ETF_POOL: Tuple[str, ...] = (
        "510050.SH", "510300.SH", "510500.SH", "159915.SZ", "588000.SH", "512100.SH",
        "512880.SH", "512660.SH", "512800.SH", "512690.SH", "516110.SH", "512980.SH",
        "159825.SZ", "515210.SH", "516950.SH", "512480.SH", "515050.SH", "512170.SH",
        "512710.SH", "159996.SZ", "512580.SH",
        "513100.SH", "513520.SH", "513020.SH", "159941.SZ",
        "518880.SH", "501018.SH",
        "511090.SH", "511260.SH",
    )

    DEFAULT_PARAMS: Dict[str, Any] = {
        # —— 选股 ——
        "universe": "all_market",       # 股票池："all_market"=全A股主板(00/60开头)
        "min_daily_volume": 500,        # 近5日日均成交量 ≥ 500 手
        "min_yesterday_rise": 0.007,    # 昨日涨幅 ≥ 0.7%
        "min_volume_ratio": 1.2,        # 当日成交量 ≥ 近20日均量 1.2 倍
        "roc_threshold": 5.0,           # ROC(10) > 5
        "buy_below_high_rate": 0.0015,  # 价格低于20日新高 >= 0.15%
        "new_stock_days": 30,           # 新股过滤：上市不足 N 个交易日
        # v6.12: 方案B 已验证有害，回退关闭（entry_close_in_range=0）。
        # 5y 实测：收盘位置过滤与"低吸"逻辑矛盾——回调日通常收盘软弱，
        # 过滤后只剩追涨票 → 2026 从 +34% 崩到 -0.1%、2023 新增 -12.8% 亏损。
        "entry_close_in_range": 0,      # 0=关闭（默认，方案B不生效）
        "lookback_days": 60,            # 选股回溯天数（预加载）

        # —— 持仓 ——
        "max_positions": 3,             # 最大持仓数
        "max_candidates": 2,            # v6.14: 持仓满时仍产生的候选上限（转正时决定替换）
        "rebalance_frequency": 1,       # 每天调仓
        "allocated_capital": 100000,    # 分配资金（回退默认值，优先从 context 读取）
        "min_lot_size": 100,            # 最小交易股数（A 股 1 手=100 股）

        # —— 三档行情风控（方案C：中证500指数）——
        # 判定依据：中证500（000905.SH）收盘价与均线位置
        "csi500_ma_short": 20,          # 短期均线周期
        "csi500_ma_long": 60,           # 长期均线周期
        "csi500_sideways_pct": 0.03,    # 震荡市判定：近N日涨跌幅 ≤ 3%

        # —— 下跌市风控（暂停新买入，存量持仓按统一止损管理） ——
        "bear_max_pos": 2,              # 下跌市持仓上限（当前下跌市暂停新买入，仅在恢复买入逻辑时生效）
        "bear_stop_loss": -0.04,        # 下跌市止损（与上涨市统一）

        # —— 震荡市风控 ——
        "sideways_max_pos": 2,          # 震荡市最多 2 只
        # v6.11: 单票仓位上限（防震荡市 max_pos=2 → 50% 仓位过重）。
        # 震荡市 weight 从 1/2 降到 1/3：单笔止损损失 2%→1.3%，降低磨损。
        "max_single_position": 0.33,    # 单票权重上限（默认 1/3）

        # —— 风控 ——
        # v6.13 分行情止损实验已回退：5y 实测 +0.97%（最差），比全 -4%（+33.58%）和
        # 全 -6%（+21.57%）都差——regime 翻转导致止损跳变、行为不一致。
        # 恢复基线：全行情统一 -4% 止损。
        "stop_loss": -0.04,             # 个股止损 -4%
        "sideways_stop_loss": -0.04,    # 震荡市止损（与上涨市统一）
        # v6.11: 收盘确认买入的低点过滤 — 确认日盘中最低价相对信号价的允许跌幅。
        # 若确认日 low < 信号价×(1-buy_confirm_max_drop)（盘中深跌/触及跌停），
        # 放弃买入（不接飞刀）。0=关闭。默认 3%。
        "buy_confirm_max_drop": 0.03,

        # —— 动态再平衡 ——
        "rebalance_threshold": 1.0,     # 持仓浮盈超过 100% 时强制卖半仓
        # v6.12: 池外抛物线止盈（方案C 已验证有害，回退原版紧阈值）。
        # 5y 实测：放宽止盈（8-15%）毁掉右尾（15-30天长持 +58.6万→+13.1万），
        # 因赢家回落过深才卖、资金被占无法再入场。恢复紧止盈（2-8%）：
        # 涨40%回落4%即卖 → 锁定+36% → 释放资金再入场，右尾反而更大。
        "tp_dd_80": 0.02,               # 浮盈≥80% 回落 2% 卖
        "tp_dd_40": 0.04,               # 浮盈≥40% 回落 4% 卖
        "tp_dd_20": 0.06,               # 浮盈≥20% 回落 6% 卖
        "tp_dd_10": 0.08,               # 浮盈≥10% 回落 8% 卖

        # —— 组合回撤保护（0=关闭；>0 时组合回撤超过阈值暂停新买入） ——
        "portfolio_dd_limit": 0.12,
        "dd_recovery_days": 10,         # 刹车恢复：触发后空仓满 N 个交易日，以当前净值为新基准重启

        # —— 行情判定来源 ——
        # "bullish_pct" = 全市场多头占比（方案B，历史最优）
        # "csi500" = 中证500指数MA判定（方案C，v6.9 定稿）
        "regime_source": "csi500",

        # —— 震荡市跌入阈值（regime_source=bullish_pct 时生效） ——
        "csi500_lower_fallback": 0.18,  # 多头占比低于此值→下跌市（收窄震荡档防误判）

        # —— v6.8 上涨市附加门（默认 0=关闭，不改变既有行为） ——
        # 针对 5 年期验证失败根因：MA 结构无法区分"低效率熊市反弹"与"牛市启动"
        "csi500_min_ef": 0.0,       # EF效率门：CSI500 近 N 日效率比 ≥ 阈值才确认上涨市
        "csi500_ef_window": 20,     # EF 计算窗口
        "regime_width_min": 0.0,    # ETF宽度门：多头排列(MA20>MA60) ETF 占比 ≥ 阈值才确认上涨市

        # —— v6.9 年线门（Phase1 预注册测试B通过，定稿默认开启） ——
        # Phase1 教训：20-60日尺度指标无法区分熊市反弹与牛市启动（1a/1b 双败），
        # 且"降级震荡市"力度不足。年线门用年线级尺度 + 直接停买：
        # CSI500 收盘 < MA250 → 强制下跌市。规则标准无可调阈值。
        # 5年+47.5%/3年+41.7% 的跨周期生存关键机制，关闭前请阅读
        # docs/进攻防御双策略体系验证报告-2026-07.md（关闭后5年期=-53%）。
        "csi500_annual_gate": True,

        # —— 调试 —— :日志会输出行情判定、选股/复检数量、每次止盈止损的触发原因，方便你复盘确认策略行为是否符合预期。
        "verbose_logging": True,

        # —— 拉高出货检测（多信号模型，防连板陷阱） ——
        # ⚠️ v6.10 5年回测: +45.86% vs 基线+86.77%，拦截大赢家→收益腰斩。默认关闭。
        "pump_dump_filter_enabled": False,             # 开启拉高出货过滤（不推荐）
        "pd_vol_climax_ratio": 1.5,                    # 放量见顶：末次涨停量 / 前几次均量 > 此值
        "pd_distribution_vol_ratio": 1.5,              # 出货日：量 > 20日均量 × 此值
        "pd_distribution_range_pct": 0.05,             # 出货日：振幅 > 此值
        "pd_parabolic_consecutive": 3,                 # 连续涨停 ≥ 此数 → 抛物线衰竭
        "pd_parabolic_dd_threshold": 0.05,             # 高位回落 > 此值 → 确认衰竭
        "pd_signal_threshold": 2,                      # 命中 ≥ 此数信号 → 拦截（1=记录, 2+=拦截）

        # —— 行业黑名单 ——
        "industry_blacklist": ["商贸零售", "汽车", "建筑装饰", "钢铁", "电力设备"],

    }

    def __init__(
        self,
        name: str = "低吸轮动",
        strategy_type: StrategyType = StrategyType.CUSTOM,
        parameters: Optional[Dict[str, Any]] = None,
    ):
        merged = dict(self.DEFAULT_PARAMS)
        if parameters:
            merged.update(parameters)
        super().__init__(name=name, strategy_type=strategy_type, parameters=merged)

        self.verbose_logging: bool = bool(merged.get("verbose_logging", False))

        # —— 数据缓存 ——
        # {ts_code: DataFrame[close, volume, high, low, open]}
        self._data_cache: Dict[str, pd.DataFrame] = {}
        # v6.10: 原始 bar 缓存（list of tuples），避免逐 bar pd.concat 的 O(n²) 拷贝
        # 在 rebalance 时一次转为 DataFrame
        self._raw_cache: Dict[str, list] = {}
        self._bar_dates: Dict[str, str] = {}       # {ts_code: 最后一根实时 bar 的日期}（新鲜度守卫）
        self._st_stocks: Set[str] = set()         # ST 股票代码集合
        self._listing_dates: Dict[str, str] = {}   # {ts_code: 上市日期}
        self._bar_count: int = 0
        self._last_rebalance_date: str = ""
        self._last_trade_date: str = ""

        # 手动持仓跟踪（回测引擎不将 Broker 持仓同步回策略，必须自己管理）
        # {ts_code: {"entry_price": float, "weight": float, "shares": int, "locked": bool}}
        self._holdings: Dict[str, Dict] = {}
        self._track_high: Dict[str, float] = {}    # {ts_code: 持仓期间最高价}
        self._exit_pending: Set[str] = set()
        # v6.11: 待确认买入候选（Model B — 收盘确认）
        # {ts_code: {"signal_price": float, "weight": float}}
        # Day T 选股入池 → Day T+1 收盘确认（close > signal_price）→ 买入（收盘成交）
        self._buy_pending: Dict[str, dict] = {}
        self._industry_map: Dict[str, str] = {}    # {ts_code: l1_name}
        # 中证500指数日线数据缓存（方案C：用于行情判定，通过 IndexDailyRepository 加载）
        self._csi500_cache: pd.DataFrame = pd.DataFrame()
        # v6.8 regime ETF 宽度门数据缓存 {ts_code: DataFrame[trade_date(str), close]}
        self._etf_width_cache: Dict[str, pd.DataFrame] = {}
        # 组合复利净值乘数（已结算回合按 1 + pnl×weight 连乘；v6.4 取代
        # 旧"累计投入/回收账本"——旧算法按笔数稀释，返回平均单笔收益而非复利净值，
        # 导致 portfolio_dd_limit 回撤保护实际失效）
        self._nav_realized: float = 1.0
        self._peak_return: float = -999.0       # 组合收益峰值（回撤计算用）
        self._dd_flat_days: int = 0             # 回撤刹车触发后连续空仓天数（恢复机制用）

    # =============================================================================
    # 生命周期
    # =============================================================================

    def on_init(self) -> None:
        """初始化（不设置 _universe，让 BacktestEngine 或用户配置决定候选池）"""
        logger.info(f"低吸轮动策略初始化: {self.name}, 最大持仓={self.parameters.get('max_positions', 3)}")

    # =========================================================================
    # v6.12: 候选池持久化（signals 表 pending_confirm 状态，跨重启保留）
    # 生命周期: 候选入池(pending_confirm) → 次日确认 → 转正(promoted)/丢弃(expired)
    # =========================================================================

    def _is_live_mode(self) -> bool:
        """判断是否实盘/模拟盘模式（仅实盘持久化候选，回测不写 signals 表）。"""
        rm = getattr(getattr(self, "context", None), "run_mode", None)
        return rm in ("live", "paper")

    def _fire_db(self, coro) -> None:
        """在同步策略方法中调度异步 DB 写任务（fire-and-forget）。

        策略 on_bar_batch_end 为同步方法，DB 会话为异步；用事件循环
        调度后台任务执行 DB 写入，避免把整条信号链改为 async。
        """
        try:
            import asyncio
            asyncio.get_running_loop().create_task(coro)
        except RuntimeError:
            logger.debug("事件循环未运行，跳过候选 DB 写入")

    async def _persist_candidate(self, code: str, pinfo: dict) -> None:
        """将单个候选写/更新到 signals 表（signal_status='pending_confirm'）。"""
        sf = getattr(self, "_db_session_factory", None)
        if not sf or not self._is_live_mode():
            return
        sid = getattr(getattr(self, "context", None), "strategy_id", "") or self.name
        sig_id = pinfo.get("signal_id")
        if not sid or not sig_id:
            return
        try:
            from shared.database.repositories.strategy.signal.signal_repo import SignalRepository
            async with sf() as db:
                repo = SignalRepository(db)
                # signal_time 用交易日（候选生成日），而非落库时刻，保证恢复后 signal_date 正确
                _td = getattr(self, "_last_trade_date", None)
                # 实盘 _last_trade_date 是 "YYYY-MM-DD" 字符串，需转 date 供 combine
                if isinstance(_td, str):
                    try:
                        _td = date.fromisoformat(_td[:10])
                    except ValueError:
                        _td = None
                elif hasattr(_td, "date"):
                    _td = _td.date()
                _sig_time = datetime.combine(_td, datetime.min.time()) if _td else datetime.now()
                data = {
                    "strategy_id": sid,
                    "ts_code": code,
                    "direction": "long",
                    "signal_type": "buy",
                    "signal_time": _sig_time,
                    "price": float(pinfo.get("signal_price", 0) or 0),
                    "strength": float(pinfo.get("weight", 0.33) or 0.33),
                    "signal_status": "pending_confirm",
                    "reason": "低吸候选，待次日收盘确认",
                }
                existing = await repo.get(sig_id)
                if not existing:
                    # 幂等：同代码已存在 pending_confirm 候选 → 复用其行，防重复触发建重复行
                    _dups = await repo.get_by_stock(ts_code=code, strategy_id=sid, limit=20)
                    for _d in _dups:
                        if _d.signal_status == "pending_confirm":
                            sig_id = _d.id
                            pinfo["signal_id"] = sig_id
                            existing = _d
                            break
                if existing:
                    await repo.update(sig_id, data)
                else:
                    data["id"] = sig_id
                    await repo.create(data)
                await db.commit()
        except Exception as e:
            logger.warning(f"候选持久化失败: {code}: {e}")

    async def _restore_buy_pending_from_db(self) -> None:
        """从 signals 表读回 pending_confirm 候选，重建 _buy_pending（重启恢复）。

        过期的候选（距 signal_date 超 5 天，错过确认窗口）直接标记 expired。
        """
        sf = getattr(self, "_db_session_factory", None)
        if not sf:
            return
        sid = getattr(getattr(self, "context", None), "strategy_id", "") or self.name
        if not sid:
            return
        try:
            from sqlalchemy import select
            from shared.database.models.business_models import Signal
            async with sf() as db:
                rows = (await db.execute(select(Signal).where(
                    Signal.strategy_id == sid,
                    Signal.signal_status == "pending_confirm",
                ))).scalars().all()
                restored = 0
                for r in rows:
                    _sd = r.signal_time.strftime("%Y-%m-%d") if r.signal_time else ""
                    if _sd:
                        try:
                            if (date.today() - date.fromisoformat(_sd)).days > 5:
                                await self._mark_candidate_status(r.id, "expired", "过期未确认")
                                continue
                        except (ValueError, TypeError):
                            pass
                    self._buy_pending[r.ts_code] = {
                        "signal_price": float(r.price or 0),
                        "weight": float(r.strength or 0.33) if getattr(r, "strength", None) else 0.33,
                        "signal_id": r.id,
                        "signal_date": _sd,
                    }
                    restored += 1
                if restored:
                    logger.info(f"重启恢复: 候选池 {restored} 只 (pending_confirm)")
        except Exception as e:
            logger.warning(f"候选池恢复失败: {e}")

    async def _mark_candidate_status(self, sig_id, status: str, reason: str = "") -> None:
        """更新候选信号行的状态（promoted 转正 / expired 丢弃）。

        P1 修复：加 _is_live_mode 检查——回测中候选为内存 signal_id（未落库），
        状态更新是无意义 DB 写，堆积导致 QueuePool 连接超时。
        """
        if not self._is_live_mode():
            return
        sf = getattr(self, "_db_session_factory", None)
        if not sf or not sig_id:
            return
        try:
            from shared.database.repositories.strategy.signal.signal_repo import SignalRepository
            async with sf() as db:
                await SignalRepository(db).update(sig_id, {"signal_status": status})
                await db.commit()
        except Exception as e:
            logger.warning(f"候选状态更新失败({status}): {e}")

    async def on_start(self) -> None:
        """重置状态 + 加载 ST 列表"""
        self._data_cache.clear()
        self._bar_dates.clear()
        self._listing_dates.clear()
        self._track_high.clear()
        self._holdings.clear()
        self._exit_pending.clear()
        self._nav_realized = 1.0
        self._peak_return = -999.0
        self._dd_flat_days = 0
        self._csi500_cache = pd.DataFrame()
        self._etf_width_cache.clear()
        self._bar_count = 0
        self._last_rebalance_date = ""
        self._st_stocks = set()
        # v6.12: 候选池持久化 — 实盘重启后从 signals 表恢复 pending_confirm 候选
        self._buy_pending.clear()
        if self._is_live_mode():
            await self._restore_buy_pending_from_db()

        # 从 DB 加载中证500指数数据（通过 IndexDailyRepository，非原始 SQL）
        session_factory = getattr(self, "_db_session_factory", None)
        if session_factory:
            try:
                from shared.database.repositories.market.basic.index_repo import IndexDailyRepository
                async with session_factory() as db:
                    idx_repo = IndexDailyRepository(db)
                    # v6.2 防前视：固定早期起点加载全量历史（单指数数据量小），
                    # 实际判定时在 _calc_csi500_regime 中按当前回测日截断，
                    # 避免用 date.today() 的"最新行情"判定历史回测日的 regime。
                    start = date(2018, 1, 1)
                    records = await idx_repo.get_by_date_range('000905.SH', start, date.today())
                    if records:
                        df = pd.DataFrame([{
                            # 统一为 ISO 字符串（与 _last_trade_date 同格式，便于截断比较）
                            "trade_date": str(r.trade_date)[:10],
                            "close": float(r.close or 0),
                            "open": float(r.open or 0),
                            "high": float(r.high or 0),
                            "low": float(r.low or 0),
                            "volume": float(r.vol or 0),
                        } for r in records])
                        self._csi500_cache = df.sort_values("trade_date").reset_index(drop=True)
                        logger.info(f"中证500指数数据已加载: {len(self._csi500_cache)} 条")
                    else:
                        logger.warning("中证500指数数据为空，将回退到 bullish_pct 判定")
            except Exception as e:
                logger.warning(f"中证500指数数据加载失败（非致命，回退到 bullish_pct）: {e}")
        else:
            logger.info("DB 会话不可用，行情判定将使用 bullish_pct 代理")

        # ---- v6.8 ETF 宽度门数据加载（仅在宽度门启用时加载，判定时按回测日截断防前视）----
        if float(self.parameters.get("regime_width_min", 0.0)) > 0 and session_factory:
            try:
                from modules.strategy.engines.data_feed_engine import DataFeedEngine as _DFE
                async with session_factory() as db:
                    engine = _DFE(db)
                    df = await engine.load_historical_data(
                        symbols=list(self.REGIME_ETF_POOL),
                        start_date="2018-01-01",
                        end_date=date.today().isoformat(),
                    )
                if df is not None and not df.empty:
                    for code in df["ts_code"].unique():
                        sub = df[df["ts_code"] == code][["trade_date", "close"]].copy()
                        sub["trade_date"] = sub["trade_date"].astype(str).str[:10]
                        self._etf_width_cache[code] = (
                            sub.sort_values("trade_date").reset_index(drop=True)
                        )
                    logger.info(f"regime ETF宽度数据已加载: {len(self._etf_width_cache)} 只")
                else:
                    logger.warning("regime ETF宽度数据为空，宽度门将不生效")
            except Exception as e:
                logger.warning(f"regime ETF宽度数据加载失败（宽度门降级不生效）: {e}")

        # ---- 加载策略自有股票池：全 A 股主板（00/60 开头、L 在市股）----
        # 回测 backtest_service Step7 经 strategy.universe 读取 → 喂满全主板，
        # 取代"全市场兜底 1000 只"，使 bullish_pct 成为真实市场宽度、选股覆盖全市场。
        # v6.2: 同时填充 _st_stocks（ST 过滤生效）与 _listing_dates（新股真实日期过滤）。
        # ---- 加载行业映射 ----
        blacklist = self.parameters.get("industry_blacklist", [])
        if blacklist and session_factory:
            try:
                from sqlalchemy import select
                from shared.database.models.data_models import IndexSwMember
                async with session_factory() as db:
                    result = await db.execute(
                        select(IndexSwMember.ts_code, IndexSwMember.l1_name)
                        .where(IndexSwMember.out_date == None)
                    )
                    rows = result.fetchall()
                    self._industry_map = {r[0]: r[1] for r in rows}
                logger.info(f"行业映射已加载: {len(self._industry_map)} 只, 黑名单: {blacklist}")
            except Exception as e:
                logger.warning(f"行业映射加载失败({e}), 黑名单不生效")

        # ---- 加载策略自有股票池 ----
        if session_factory:
            try:
                from shared.database.repositories.market.basic.stock_repo import (
                    StockBasicRepository,
                )
                async with session_factory() as db:
                    all_stocks = await StockBasicRepository(db).get_active_stocks()
                universe: List[str] = []
                for s in all_stocks:
                    code = s.ts_code
                    if not self._is_tradable(code):
                        continue
                    # ST 过滤：按当前名称判定（保守方向——历史回测会误杀
                    # "当时未 ST 现已 ST"的个股；精确判定需名称变更历史表）
                    stock_name = str(getattr(s, "name", "") or "")
                    if "ST" in stock_name.upper():
                        self._st_stocks.add(code)
                        continue
                    # 真实上市日期（供 _is_new_stock 过滤，取代缓存行数近似）
                    list_dt = getattr(s, "list_date", None)
                    if list_dt:
                        self._listing_dates[code] = str(list_dt)[:10]
                    universe.append(code)
                self._universe = universe
                logger.info(
                    f"低吸轮动股票池已加载: {len(self._universe)} 只主板股 "
                    f"(剔除 ST {len(self._st_stocks)} 只)"
                )
            except Exception as e:
                logger.warning(f"股票池加载失败（回退→回测走兜底 1000）: {e}")

        logger.info(f"低吸轮动策略已启动: 数据缓存={len(self._data_cache)}")

    def on_stop(self) -> None:
        self._data_cache.clear()
        self._bar_dates.clear()
        self._track_high.clear()
        self._holdings.clear()
        self._exit_pending.clear()
        self._nav_realized = 1.0
        self._peak_return = -999.0
        self._dd_flat_days = 0
        self._csi500_cache = pd.DataFrame()
        self._etf_width_cache.clear()
        self._st_stocks.clear()
        self._industry_map.clear()
        logger.info("低吸轮动策略已停止")

    # =============================================================================
    # 核心入口：on_bar（仅缓存） + on_bar_batch_end（调仓）
    # =============================================================================

    def on_bar(self, bar: BarData) -> List[TradingSignal]:
        """
        v6.2: on_bar 仅负责缓存数据，不再触发调仓。

        调仓移至 on_bar_batch_end —— 由框架在当日全部 bar 推送完毕后调用，
        确保全市场缓存统一包含当日数据（修复旧版"当日第一根 bar 触发调仓、
        其余股票数据仍停留在 T-1"的数据不齐问题）。
        """
        try:
            self._append_data(bar.ts_code, bar)

            trade_date = getattr(bar, "trade_date", "") or getattr(bar, "datetime", "")
            trade_date = str(trade_date)[:10] if trade_date else ""
            if trade_date:
                self._last_trade_date = trade_date
        except Exception as e:
            logger.error(f"低吸轮动 on_bar 异常: {bar.ts_code}: {e}", exc_info=True)

        return []

    def on_bar_batch_end(self, trade_date: Any = None) -> List[TradingSignal]:
        """
        当日批次结束回调（strategy_manager.handle_bar_batch / optimization_engine 调用）。

        此时所有股票的缓存均已包含当日数据："今日"= closes[-1]，"昨日"= closes[-2]，
        与聚宽原版盘中决策语义对齐；信号经引擎 T+1 撮合成交，无前视。
        """
        signals: List[TradingSignal] = []
        try:
            td = str(trade_date)[:10] if trade_date else self._last_trade_date
            if td:
                self._last_trade_date = td

            if self._last_rebalance_date and td == self._last_rebalance_date:
                return signals

            # 按交易日计数，每 N 个交易日调仓一次（数据不足时不计为已调仓，
            # 避免首日就标记 _last_rebalance_date 导致后续被跳过）
            self._bar_count += 1
            # v6.11: 先将 raw_cache 转为 DataFrame，避免鸡生蛋死锁——
            # _run_rebalance 内部也调 _build_dataframe_cache，但只有
            # _data_cache 非空时才会进入 _run_rebalance。首次运行时
            # _data_cache 为空，必须在此先构建后方可突破死锁。
            self._build_dataframe_cache()
            freq = int(self.parameters.get("rebalance_frequency", 1))
            if self._bar_count % freq == 0 and len(self._data_cache) >= 10:
                signals = self._run_rebalance()
                self._last_rebalance_date = td

        except Exception as e:
            logger.error(f"低吸轮动 on_bar_batch_end 异常: {trade_date}: {e}", exc_info=True)

        return signals

    # =============================================================================
    # 主调仓（选股 + 买卖）
    # =============================================================================

    def _run_rebalance(self) -> List[TradingSignal]:
        """
        主调仓流程（对应原版 9:40 初筛 + 9:51 二次筛选 + 9:52 买入）。

        v6.2（问题修复版，on_bar_batch_end 中调用）：
          0. 【结算待卖出】
          1. 【大盘环境】三档行情 → 确定 effective_max_pos / 止损 / 是否停买
          1b.【组合回撤保护】portfolio_dd_limit > 0 时，回撤超阈值暂停新买入
          2. 【提前选股】→ 获得今日选股池（供池内池外止盈 + 半仓轮动使用）
          3. 【P0 池内池外止盈】池内股只止损，池外股止损+抛物线止盈
          4. 【差异三 两步复检】用今日 bar 重新验证候选股
          5. 【差异二 半仓轮动】有新标无空位时，清仓最差池内股腾位
          6. 【买入】用动态上限计算
        """
        signals: List[TradingSignal] = []
        # v6.13: 非交易日守卫 — 周末/节假日手动运行不触发调仓/确认，
        # 避免候选在非交易日被误判过期或确认（8-08 周末候选误判根因）。
        if not self._is_trading_day(self._last_trade_date):
            return signals

        # v6.10: 将 raw_cache 转为 DataFrame（一次性构建，替代逐 bar pd.concat）
        self._build_dataframe_cache()
        if len(self._data_cache) < 10:
            return signals

        # ---- 0. 结算昨日的待确认卖出 ----
        self._finalize_exits()

        # ---- 1. 三档行情判定（方案C：中证500指数）----
        max_pos = int(self.parameters.get("max_positions", 3))
        regime, bullish_pct = self._calc_csi500_regime()

        if regime == "上涨市":
            regime_max_pos = max_pos
            regime_stop_loss = float(self.parameters.get("stop_loss", -0.04))
            regime_no_new_buy = False
        elif regime == "震荡市":
            regime_max_pos = int(self.parameters.get("sideways_max_pos", 2))
            # v6.13 分行情止损已回退：震荡市与上涨市统一 -4%
            regime_stop_loss = float(self.parameters.get("sideways_stop_loss", -0.04))
            regime_no_new_buy = False
        else:
            # 下跌市：暂停新买入（存量持仓按统一止损管理）
            regime = "下跌市"
            regime_max_pos = int(self.parameters.get("bear_max_pos", 2))
            regime_stop_loss = float(self.parameters.get("bear_stop_loss", -0.04))
            regime_no_new_buy = True

        effective_max_pos = regime_max_pos

        # ---- 1b. 组合回撤保护（portfolio_dd_limit=0 时关闭，不影响既有行为）----
        dd_limit = float(self.parameters.get("portfolio_dd_limit", 0.0))
        if dd_limit > 0:
            port_dd = self._check_portfolio_drawdown()

            # v6.5 刹车恢复机制：回撤触发且已完全空仓（亏损全部兑现）连续
            # dd_recovery_days 日后，以当前净值为新基准重启——把每轮亏损
            # 战役深度限制在 dd_limit 附近，而非永久停机（单向自杀开关）。
            if port_dd >= dd_limit and not self._holdings and not self._exit_pending:
                self._dd_flat_days += 1
                recovery_days = int(self.parameters.get("dd_recovery_days", 10))
                if self._dd_flat_days >= recovery_days:
                    self._peak_return = self._calc_portfolio_return()
                    self._dd_flat_days = 0
                    port_dd = 0.0
                    if self.verbose_logging:
                        logger.info(f"回撤刹车重启: 空仓{recovery_days}日, 峰值重置为当前净值")
            else:
                self._dd_flat_days = 0

            if port_dd >= dd_limit and not regime_no_new_buy:
                regime_no_new_buy = True
                if self.verbose_logging:
                    logger.info(
                        f"组合回撤保护: 回撤{port_dd:.1%} ≥ {dd_limit:.0%}，暂停新买入"
                    )

        if self.verbose_logging:
            logger.info(
                f"行情判定: {regime} (多头占比={bullish_pct:.1%}, "
                f"上限={regime_max_pos}, 止损={regime_stop_loss:.1%})"
            )

        # ---- v6.11: 确认昨日待买候选（Model B — 收盘确认买入） ----
        # Day T 选股入池 _buy_pending（signal_price=当日收盘），Day T+1 在此确认：
        # close[T+1] > signal_price → 发买入信号（order_mode="close"，当日收盘成交）。
        # 下跌市/暂停买入 → 放弃全部待确认候选。
        if effective_max_pos > 0 and not regime_no_new_buy:
            signals.extend(self._confirm_pending_buys(effective_max_pos))
        else:
            if self._buy_pending:
                if self.verbose_logging:
                    logger.info(f"暂停买入/下跌市: 放弃 {len(self._buy_pending)} 只待确认候选")
                # v6.12: 门控清空 → DB 候选标记 expired
                for _c, _p in list(self._buy_pending.items()):
                    self._fire_db(self._mark_candidate_status(_p.get("signal_id"), "expired", "暂停买入/下跌市"))
                self._buy_pending.clear()

        # ---- 2. 获取当前持仓（v3.4: 合并框架注入的_active_positions） ----
        current_holdings = set(self._holdings.keys()) | set(self._active_positions.keys())
        effective_count = len(current_holdings - self._exit_pending)

        # ---- 3. 提前选股（在止盈止损之前，获得今日选股池用于 P0）----
        if effective_max_pos > 0 and not regime_no_new_buy:
            buy_list = self._screen_stocks(current_holdings)
        else:
            buy_list = []

        # P0（v6.7 趋势健康度判定）：today_pool = 新候选股 + 「趋势仍健康的持仓」。
        # 持仓只用 _holding_in_pool（MA5≥MA20 / MACD多头 / 未深跌），不拷问入场时机
        # （条件1/3/4/6）→ 均线未死叉就让它跑；趋势破位 → 抛物线止盈锁盈。
        held_active = current_holdings - self._exit_pending
        today_pool = (set(buy_list) if buy_list else set()) | {
            c for c in held_active if self._holding_in_pool(c)
        }

        # ---- 4. P0 池内池外区分止盈（传入动态止损参数）----
        exit_signals = self._check_all_stop_profit(today_pool=today_pool, stop_loss=regime_stop_loss)
        signals.extend(exit_signals)

        # ---- 5. 差异三 两步合一步复检 ----
        confirmed = self._recheck_buy_list(buy_list) if buy_list else []

        if self.verbose_logging:
            logger.info(
                f"低吸轮动调仓: 持仓={len(current_holdings)}, "
                f"待卖出={len(self._exit_pending)}, 有效={effective_count}, "
                f"上限={effective_max_pos}, 行情={regime}, "
                f"多头占比={bullish_pct:.1%}, 初筛={len(buy_list)}, "
                f"复检={len(confirmed)}, {'暂停买入' if regime_no_new_buy else ''}"
            )

        # ---- 6. 震荡市成交量排名过滤（方案C）----
        if regime == "震荡市" and confirmed:
            confirmed = self._filter_sideways_volume(confirmed)

        # ---- 7. 候选入池（v6.14: 持仓满也产生候选，转正时决定保留/替换）----
        # 持仓上限不再阻断候选产生：持仓有空位 → 入池到持仓上限；持仓满 →
        # 仍入池 max_candidates 个候选（供次日 _confirm_pending_buys 转正时替换决策）。
        if effective_max_pos <= 0 or regime_no_new_buy:
            return signals

        new_stocks = [s for s in confirmed if s not in current_holdings and s not in self._exit_pending]
        if not new_stocks:
            return signals

        slots = effective_max_pos - effective_count
        max_candidates = int(self.parameters.get("max_candidates", 2))
        target_limit = max(slots, 1) if slots > 0 else max_candidates
        targets = new_stocks[:target_limit]

        for target in targets:
            price = self._get_price(target)
            if price <= 0:
                continue

            # v6.11: 单票仓位上限（震荡市 1/2 → 1/3，防仓位过重磨损）
            _max_w = float(self.parameters.get("max_single_position", 0.33))
            weight = min(1.0 / effective_max_pos, _max_w)
            # v6.11: Model B — 候选入池，次日收盘确认后再买入。
            # 不再立即发买入信号/加入 _holdings，由 _confirm_pending_buys 处理，
            # 避免"策略以为已买、broker 未成交"的状态脱节。
            self._buy_pending[target] = {
                "signal_price": price,
                "weight": weight,
                "signal_date": str(self._last_trade_date)[:10],
                "signal_id": self._gen_id(),
            }
            # v6.12: 候选落库（signals 表 pending_confirm，跨重启保留）
            self._fire_db(self._persist_candidate(target, self._buy_pending[target]))

            if self.verbose_logging:
                logger.info(
                    f"低吸轮动候选入池: {target}, 信号价={price:.2f}, "
                    f"仓位={weight:.0%}（待次日收盘确认）"
                )

        return signals

    def _find_replaceable_holding(self) -> Optional[str]:
        """v6.14: 持仓满时，找可替换的弱势持仓（供转正替换决策）。

        规则：
          - 排除待卖出（_exit_pending）与当日新买入（T+1 锁定）
          - 优先趋势破位（not _holding_in_pool）；无破位持仓 → 返回 None
            （不强制替换健康持仓，保留当前持仓）
        """
        today = str(self._last_trade_date)[:10]
        candidates = [
            c for c in self._holdings
            if c not in self._exit_pending
            and self._holdings.get(c, {}).get("entry_date", "") != today
        ]
        broken = [c for c in candidates if not self._holding_in_pool(c)]
        return broken[0] if broken else None

    def _confirm_pending_buys(self, effective_max_pos: int) -> List[TradingSignal]:
        """v6.11: 确认昨日待买候选（Model B — 收盘确认买入）。

        Day T 选股入池 _buy_pending（signal_price = 当日收盘价），Day T+1 在此确认：
        若 close[T+1] > signal_price（净确认，过滤假突破/低开走弱）→ 发买入信号
        （order_mode="close"，broker 当日收盘价成交）；否则放弃。

        决策时戳（close[T+1]）= 成交时戳（当日收盘），无未来函数。
        确认后即加入 _holdings（entry_date=今日），当日止损检查被 T+1 锁定守卫跳过。

        Args:
            effective_max_pos: 当前行情下的最大持仓数（用于仓位上限保护）。

        Returns:
            确认通过的买入信号列表。
        """
        signals: List[TradingSignal] = []
        if not self._buy_pending:
            return signals

        today = str(self._last_trade_date)[:10]
        lot_size = int(self.parameters.get("min_lot_size", 100))
        capital = float(
            getattr(self.context, "initial_capital", 0)
            or self.parameters.get("allocated_capital", 100000)
        )

        pending = dict(self._buy_pending)
        self._buy_pending.clear()

        for code, pinfo in pending.items():
            # v6.12: 过期守卫 — 距 signal_date 超 5 天视为错过确认窗口 → expired；
            # 同日/未来（gap<=0）未到确认窗口 → 保留候选待次日（防重启同日重跑误过期）
            _sd = pinfo.get("signal_date", "")
            if _sd:
                try:
                    _today_d = self._last_trade_date
                    # 实盘 _last_trade_date 是 "YYYY-MM-DD" 字符串，统一转 date
                    if isinstance(_today_d, str):
                        _today_d = date.fromisoformat(_today_d[:10])
                    elif hasattr(_today_d, "date"):
                        _today_d = _today_d.date()
                    if _today_d:
                        _gap = (_today_d - date.fromisoformat(_sd)).days
                        if _gap <= 0:
                            self._buy_pending[code] = pinfo
                            continue
                        if _gap > 5:
                            self._fire_db(self._mark_candidate_status(pinfo.get("signal_id"), "expired", "过期未确认"))
                            if self.verbose_logging:
                                logger.info(f"买入确认过期: {code} 候选日期{_sd}，放弃")
                            continue
                except (ValueError, TypeError):
                    pass
            # v6.14: 持仓满时，转正评估替换（不再 break 丢弃候选）
            if len(self._holdings) >= effective_max_pos:
                victim = self._find_replaceable_holding()
                if victim is None:
                    # 持仓健康无弱势可替换 → 候选放弃（不强制替换健康持仓）
                    self._fire_db(self._mark_candidate_status(pinfo.get("signal_id"), "expired", "持仓健康无可替换"))
                    if self.verbose_logging:
                        logger.info(f"买入确认放弃: {code} 持仓满且无弱势持仓可替换")
                    continue
                # 转正替换：立即结算弱势持仓收益并腾位（与 _finalize_exits 同逻辑），再买入新候选
                _ventry = self._holdings.get(victim, {}).get("entry_price", 0)
                _vw = self._holdings.get(victim, {}).get("weight", 1.0)
                _vprice = self._get_price(victim)
                if _ventry > 0 and _vprice > 0:
                    self._nav_realized *= 1.0 + ((_vprice - _ventry) / _ventry) * _vw
                if victim in self._track_high:
                    del self._track_high[victim]
                del self._holdings[victim]
                signals.append(self._make_exit_signal(
                    victim, reason=f"转正替换: 新候选{code}确认，清仓弱势持仓{victim}",
                    order_mode="close",
                ))
                if self.verbose_logging:
                    logger.info(f"转正替换: 清仓{victim}，买入{code}")
            price = self._get_price(code)  # close[T+1]
            if price <= 0:
                continue
            signal_price = float(pinfo["signal_price"])
            # 净确认：收盘价必须高于信号价（上涨确认）
            if price <= signal_price:
                self._fire_db(self._mark_candidate_status(pinfo.get("signal_id"), "expired", "收盘确认失败"))
                if self.verbose_logging:
                    logger.info(
                        f"买入确认失败: {code} 收盘{price:.2f} ≤ 信号价{signal_price:.2f}，放弃"
                    )
                continue

            # v6.11: 低点过滤 — 确认日盘中最低价不能深跌过多（避免买入"盘中触跌停、
            # 收盘回升"的飞刀）。确认日 low < 信号价×(1-max_drop) → 放弃。
            _max_drop = float(self.parameters.get("buy_confirm_max_drop", 0.03))
            _df = self._data_cache.get(code)
            if _max_drop > 0 and _df is not None and len(_df) > 0 and "low" in _df.columns:
                _day_low = float(_df["low"].iloc[-1])
                _floor = signal_price * (1 - _max_drop)
                if _day_low < _floor:
                    self._fire_db(self._mark_candidate_status(pinfo.get("signal_id"), "expired", "低点过滤"))
                    if self.verbose_logging:
                        logger.info(
                            f"买入确认失败(低点过滤): {code} 当日最低{_day_low:.2f} "
                            f"< 信号价{signal_price:.2f}×{(1-_max_drop):.2f}={_floor:.2f}，"
                            f"盘中深跌不接飞刀"
                        )
                    continue

            # v6.11: 单票仓位上限兜底（与入池时一致）
            _max_w = float(self.parameters.get("max_single_position", 0.33))
            weight = min(
                float(pinfo.get("weight", 1.0 / max(effective_max_pos, 1))),
                _max_w,
            )
            amount = capital * weight
            shares = max(int(amount / price / lot_size) * lot_size, lot_size)

            sig = TradingSignal(
                id=self._gen_id(),
                strategy_id=self.name,
                strategy_name=self.name,
                ts_code=code,
                signal_type=SignalType.ENTRY,
                direction=SignalDirection.LONG,
                price=price,
                quantity=shares,
                amount=amount,
                confidence=0.75,
                reason=f"低吸轮动买入(收盘确认): {code} 收盘{price:.2f} > 信号价{signal_price:.2f}",
                timestamp=datetime.now(),
                order_mode="close",
            )
            sig.weight = weight
            # v3.4: 父信号ID = 候选 signal_id，串起 候选→买入信号 链路
            sig.parent_id = pinfo.get("signal_id")
            signals.append(sig)
            self._holdings[code] = {
                "entry_price": price, "weight": weight, "shares": shares,
                "entry_date": today,
            }
            self._track_high[code] = price
            # v6.12: 转正 — 候选行标记 promoted
            self._fire_db(self._mark_candidate_status(pinfo.get("signal_id"), "promoted", "收盘确认转正"))

            if self.verbose_logging:
                logger.info(
                    f"低吸轮动买入(收盘确认): {code}, 收盘{price:.2f} > 信号价{signal_price:.2f}, "
                    f"仓位={weight:.0%}"
                )

        return signals

    # =============================================================================
    # 大盘环境过滤
    # =============================================================================

    def _calc_bullish_pct(self) -> float:
        """
        计算数据缓存中 MA5 > MA20（多头排列）的股票占比。

        用作市场环境代理指标：多头占比越低说明市场越弱势。
        低于 min_bullish_pct 阈值时策略应降低仓位。
        """
        total = 0
        bullish = 0
        for code, df in self._data_cache.items():
            closes = df["close"].values.astype(np.float64)
            if len(closes) < 20:
                continue
            total += 1
            ma5 = float(np.mean(closes[-5:]))
            ma20 = float(np.mean(closes[-20:]))
            if ma5 > ma20:
                bullish += 1
        return bullish / total if total > 0 else 0.0

    # =============================================================================
    # 三档行情判定（方案C：中证500指数，通过 IndexDailyRepository 加载）
    # =============================================================================

    def _calc_csi500_regime(self) -> Tuple[str, float]:
        """
        基于中证500（000905.SH）的行情判定。

        判定规则：
          上涨市：close > MA20 > MA60 且 MA20斜率正
          震荡市：近20日涨跌幅 ≤ 3% 且 MA20走平
          下跌市：close < MA20 < MA60 且 MA20斜率为负

        回退：中证500数据不足或未加载时，使用 bullish_pct 代理判定。

        Returns:
            (regime_name, bullish_pct) — regime_name 用于仓位决策，bullish_pct 用于日志
        """
        bullish_pct = self._calc_bullish_pct()

        # --- v6.9 年线门（预注册测试B）：优先于一切判定来源，命中即停买 ---
        if self._annual_line_gate():
            return "下跌市", bullish_pct

        # --- v6.1: regime_source 参数控制行情判定来源 ---
        regime_source = str(self.parameters.get("regime_source", "bullish_pct"))
        if regime_source == "bullish_pct":
            # 直接用 bullish_pct 三档（方案B，历史三年期最优 +47%）
            up_th = float(self.parameters.get("csi500_upper_fallback", 0.25))
            dn_th = float(self.parameters.get("csi500_lower_fallback", 0.10))
            if bullish_pct > up_th:
                return self._apply_uptrend_gates(), bullish_pct
            elif bullish_pct > dn_th:
                return "震荡市", bullish_pct
            else:
                return "下跌市", bullish_pct

        # --- v6.2 防前视：只使用当前回测日（_last_trade_date）及之前的指数数据 ---
        # 缓存在 on_start 一次性加载到真实"今天"，历史回测日必须截断后再判定，
        # 否则 closes[-1] 恒为最新真实行情 → regime 全程静态且引入未来数据。
        cache = self._csi500_cache
        if not cache.empty and self._last_trade_date:
            cache = cache[cache["trade_date"].astype(str) <= self._last_trade_date]

        # 数据不足时回退到 bullish_pct 代理
        if cache.empty or len(cache) < 65:
            up_th = float(self.parameters.get("csi500_upper_fallback", 0.25))
            dn_th = float(self.parameters.get("csi500_lower_fallback", 0.10))
            if bullish_pct > up_th:
                return self._apply_uptrend_gates(), bullish_pct
            elif bullish_pct > dn_th:
                return "震荡市", bullish_pct
            else:
                return "下跌市", bullish_pct

        closes = cache["close"].values.astype(np.float64)
        ma_short = int(self.parameters.get("csi500_ma_short", 20))
        ma_long = int(self.parameters.get("csi500_ma_long", 60))
        sideways_pct = float(self.parameters.get("csi500_sideways_pct", 0.03))

        close_now = closes[-1]
        n = len(closes)
        ma20 = float(np.mean(closes[-ma_short:])) if n >= ma_short else close_now
        ma60 = float(np.mean(closes[-ma_long:])) if n >= ma_long else close_now

        # MA20斜率（当前MA20 vs 3天前的MA20）
        if n >= ma_short + 3:
            ma20_3d_ago = float(np.mean(closes[-(ma_short + 3):-3]))
            ma20_slope = (ma20 - ma20_3d_ago) / ma20_3d_ago if ma20_3d_ago > 0 else 0
        else:
            ma20_slope = 0

        # 近20日涨跌幅
        recent_return = (close_now - closes[-21]) / closes[-21] if n >= 21 else 0

        # 上涨市：close > MA20 > MA60, MA20斜率正
        if close_now > ma20 > ma60 and ma20_slope > 0:
            return self._apply_uptrend_gates(), bullish_pct
        # 下跌市：close < MA20 < MA60, MA20斜率为负
        if close_now < ma20 < ma60 and ma20_slope < 0:
            return "下跌市", bullish_pct
        # 震荡市：涨跌幅小或MA20走平
        if abs(recent_return) <= sideways_pct or abs(ma20_slope) < 0.005:
            return "震荡市", bullish_pct
        # 兜底
        if close_now > ma20:
            return self._apply_uptrend_gates(), bullish_pct
        elif close_now < ma20:
            return "下跌市", bullish_pct
        return "震荡市", bullish_pct

    # =============================================================================
    # v6.8 上涨市附加门（EF 效率门 + ETF 宽度门）
    # =============================================================================

    @staticmethod
    def _efficiency_ratio(closes: np.ndarray, window: int = 20) -> float:
        """
        市场效率比（两仪四象 EF 改进版）：max(区间振幅, |净位移|) / Σ|日变动|。

        ≈1 = 近似直线的纯净趋势；≈0 = 原地打转的宽幅震荡。
        分子取 max(振幅, 净位移)：V 形走势净位移≈0 但振幅大，不误判为低效率。
        数据不足或路径为 0 时返回 1.0（门失效开——不拦）。
        """
        if len(closes) < window + 1:
            return 1.0
        seg = closes[-(window + 1):]
        path = float(np.sum(np.abs(np.diff(seg))))
        if path <= 0:
            return 1.0
        span = float(np.max(seg) - np.min(seg))
        net = abs(float(seg[-1] - seg[0]))
        return min(1.0, max(span, net) / path)

    def _calc_etf_width_pct(self) -> Optional[float]:
        """
        多资产池多头排列（MA20>MA60）ETF 占比。

        分母 = 截至当前回测日已有 ≥60 日数据的 ETF 数（占比制——部分 ETF
        上市晚，绝对数阈值在早期永远不达标）。可用 ETF <5 或数据未加载
        时返回 None（门降级不生效）。
        """
        if not self._etf_width_cache or not self._last_trade_date:
            return None
        total = 0
        bullish = 0
        for code, df in self._etf_width_cache.items():
            closes = df.loc[
                df["trade_date"] <= self._last_trade_date, "close"
            ].values.astype(np.float64)
            if len(closes) < 60:
                continue
            total += 1
            if float(np.mean(closes[-20:])) > float(np.mean(closes[-60:])):
                bullish += 1
        if total < 5:
            return None
        return bullish / total

    def _annual_line_gate(self) -> bool:
        """
        v6.9 年线门（Phase1 预注册测试B）：CSI500 收盘 < MA250 → 强制下跌市（停买）。

        年线是公认牛熊分界，无可调阈值：2022 全年 CSI500 运行于年线下方
        （反弹从未站上），2021H2 与 2024-10 后在上方——恰好切分 5 年期的
        亏损段与盈利段。数据不足 250 日或门未启用时返回 False（失效开）。
        """
        if not bool(self.parameters.get("csi500_annual_gate", False)):
            return False
        cache = self._csi500_cache
        if cache.empty or not self._last_trade_date:
            return False
        sliced = cache[cache["trade_date"].astype(str) <= self._last_trade_date]
        closes = sliced["close"].values.astype(np.float64)
        if len(closes) < 250:
            return False
        return bool(closes[-1] < float(np.mean(closes[-250:])))

    def _apply_uptrend_gates(self) -> str:
        """
        v6.8: 上涨市判定的两道附加门，任一不达标降级为震荡市。

        针对 5 年期验证失败根因——2022 高波动熊市反弹中 MA 结构走牛但
        趋势纯净度/市场宽度不足。默认参数（0）下两门均关闭，行为与 v6.7 一致。
        所有数据不可用场景均失效开（不拦），确保门是收紧项而非故障点。
        """
        # 门1: EF 效率门
        min_ef = float(self.parameters.get("csi500_min_ef", 0.0))
        if min_ef > 0 and not self._csi500_cache.empty and self._last_trade_date:
            sliced = self._csi500_cache[
                self._csi500_cache["trade_date"].astype(str) <= self._last_trade_date
            ]
            if len(sliced) > 0:
                ef = self._efficiency_ratio(
                    sliced["close"].values.astype(np.float64),
                    int(self.parameters.get("csi500_ef_window", 20)),
                )
                if ef < min_ef:
                    if self.verbose_logging:
                        logger.info(f"EF效率门拦截: EF={ef:.2f} < {min_ef:.2f} → 降级震荡市")
                    return "震荡市"

        # 门2: ETF 宽度门
        width_min = float(self.parameters.get("regime_width_min", 0.0))
        if width_min > 0:
            width = self._calc_etf_width_pct()
            if width is not None and width < width_min:
                if self.verbose_logging:
                    logger.info(f"ETF宽度门拦截: {width:.0%} < {width_min:.0%} → 降级震荡市")
                return "震荡市"

        return "上涨市"

    # =============================================================================
    # 组合回撤保护（累计退出价值法，无 phantom drawdown）
    # =============================================================================

    def _calc_portfolio_return(self) -> float:
        """
        计算组合复利净值收益率。

        v6.4: _nav_realized 为已结算回合的复利净值乘数（_finalize_exits 中
        每笔按 1 + pnl×weight 连乘），当前持仓的浮动盈亏在其基础上继续连乘。

        修复旧算法缺陷：旧版按"累计投入/累计回收"计算，分母随交易笔数增长
        而稀释，返回的是历次交易的平均单笔收益率（长期徘徊在 ±4% 内），
        而非组合复利收益 → 基于它的回撤保护几乎永不触发。
        """
        nav = self._nav_realized
        for code, holding in self._holdings.items():
            entry = holding.get("entry_price", 0)
            if entry <= 0:
                continue
            current = self._get_price(code)
            # 修复 2026-08（C8）：NaN 防护——NaN <= 0 为 False 会穿透污染 nav
            if current is None or current != current or current <= 0:
                continue
            w = holding.get("weight", 1.0)
            nav *= 1.0 + (current - entry) / entry * w
        return nav - 1.0

    def _check_portfolio_drawdown(self) -> float:
        """
        计算组合从收益峰值的回撤比例。

        回撤 = (peak_return - current_return) / (1 + peak_return)
        创新高时更新 _peak_return 并返回 0。
        """
        current_ret = self._calc_portfolio_return()
        if current_ret > self._peak_return:
            self._peak_return = current_ret
            return 0.0
        if self._peak_return <= -0.999:
            return 0.0
        dd = (self._peak_return - current_ret) / (1 + self._peak_return)
        return max(0.0, dd)

    # =============================================================================
    # 选股引擎
    # =============================================================================

    def _passes_screen(self, code: str) -> bool:
        """
        今日选股条件检查（v6.6：新候选筛选与持仓池内判定共用同一套条件）。

        六大条件 + 基本过滤，与原版 9:40 初筛一致。持仓股每日用本方法
        判定是否"仍在今日选股池"：跌出池（动量衰竭/涨至新高/回落过深）
        → _check_all_stop_profit 启用池外抛物线止盈。
        """
        df = self._data_cache.get(code)
        if df is None:
            return False
        try:
            # 基本过滤
            if not self._is_tradable(code):
                return False
            if code in self._st_stocks:
                return False

            # 行业黑名单过滤
            blacklist = self.parameters.get("industry_blacklist", [])
            if blacklist and self._industry_map:
                ind = self._industry_map.get(code)
                if ind is not None and ind in blacklist:
                    return False

            # v6.3 幽灵持仓修复：仅"当日有新 bar"的股票可在池内。
            # 缓存中存在（如全市场预热注入）但引擎未推送当日数据的股票，
            # 买入后订单永不成交、价格冻结 → 永久占用持仓槽（幽灵持仓）；
            # 同时天然排除当日停牌股。bullish_pct 市场宽度不受此守卫影响。
            if self._bar_dates.get(code) != self._last_trade_date:
                return False

            # 新股过滤
            if self._is_new_stock(code):
                return False

            closes = df["close"].values.astype(np.float64)
            volumes = df["volume"].values.astype(np.float64)
            opens = df["open"].values.astype(np.float64) if "open" in df.columns else closes
            highs = df["high"].values.astype(np.float64) if "high" in df.columns else closes
            lows = df["low"].values.astype(np.float64) if "low" in df.columns else closes

            if len(closes) < 25:
                return False

            # ---- 条件0: 方案B 收盘位置确认（过滤弱势收盘） ----
            # (close - low)/(high - low) 偏低 → 当日收盘软弱（接近最低），
            # 说明买盘未承接，次日继续跌概率高（假低吸）。
            _range_min = float(self.parameters.get("entry_close_in_range", 0.0))
            if _range_min > 0:
                _rng = highs[-1] - lows[-1]
                if _rng > 0:
                    _pos = (closes[-1] - lows[-1]) / _rng
                    if _pos < _range_min:
                        if self.verbose_logging:
                            logger.debug(
                                f"收盘位置过滤: {code} 收盘位{_pos:.2f} < {_range_min:.2f}"
                            )
                        return False
                else:
                    # 一字板（high==low）无法判定位 → 视为满足
                    pass

            # ---- 条件1: 昨日收阳 + 涨幅 >= 0.7% ----
            close_yest = closes[-2]
            open_yest = opens[-2]
            close_pre = closes[-3] if len(closes) >= 3 else close_yest
            if close_pre <= 0:
                return False

            is_up_bar = close_yest > open_yest
            rise_rate = (close_yest - close_pre) / close_pre
            if not (is_up_bar and rise_rate >= float(self.parameters.get("min_yesterday_rise", 0.007))):
                return False

            # ---- 条件2: MA5 > MA20（多头） ----
            ma5 = float(np.mean(closes[-5:]))
            ma20 = float(np.mean(closes[-20:]))
            if ma5 < ma20:
                return False

            # ---- 条件3: 量比 >= 1.2 ----
            avg_vol_20 = float(np.mean(volumes[-20:]))
            last_vol = float(volumes[-1])
            if avg_vol_20 > 0 and last_vol / avg_vol_20 < float(self.parameters.get("min_volume_ratio", 1.2)):
                return False

            # ---- 条件4: ROC(10) > 5 ----
            roc_10 = (closes[-1] - closes[-11]) / closes[-11] * 100 if len(closes) >= 11 else 0
            if roc_10 < float(self.parameters.get("roc_threshold", 5.0)):
                return False

            # ---- 条件5: MACD 金叉（简化：DIF > DEA） ----
            if not self._check_macd_bullish(closes):
                return False

            # ---- 条件6: 价格低于 20 日新高 >= 0.15% ----
            hhv_20 = float(np.max(closes[-20:]))
            if hhv_20 <= 0:
                return False
            below_high = (hhv_20 - closes[-1]) / hhv_20
            if below_high < float(self.parameters.get("buy_below_high_rate", 0.0015)):
                return False
            # P1: 买入价下限——不买从 20 日新高跌超 8% 的（不接飞刀）
            if closes[-1] < hhv_20 * 0.92:
                return False
            # P2: 拉高出货检测（多信号模型）——命中 ≥ pd_signal_threshold 个信号 → 拦截
            pump_score, pump_reasons = self._detect_pump_and_dump(code)
            threshold = int(self.parameters.get("pd_signal_threshold", 2))
            if pump_score >= threshold:
                if self.verbose_logging and pump_score >= 2:
                    logger.info(f"P2拦截 {code}: {', '.join(pump_reasons)}")
                return False

            return True
        except Exception:
            return False

    def _screen_stocks(self, current_holdings: Set[str]) -> List[str]:
        """
        全市场选股（合并原版 9:40 初筛 + 9:51 二次筛选）。

        返回按 成交额降序 排列的候选股票代码列表。
        """
        candidates: List[str] = []

        for code in self._data_cache.keys():
            # v3.4: 跳过已持仓（本地_holdings + 框架注入_active_positions）
            if code in current_holdings or code in self._active_positions:
                continue
            # v3.4: 跳过已有待确认买入信号的股票
            if code in self._pending_signals:
                continue
            if self._passes_screen(code):
                candidates.append(code)

        # 按成交量降序排列（流动机优先）
        candidates.sort(
            key=lambda c: float(np.mean(
                self._data_cache[c]["volume"].values.astype(np.float64)[-5:]
            )) if c in self._data_cache and len(self._data_cache[c]) >= 5 else 0,
            reverse=True,
        )

        if self.verbose_logging:
            logger.info(f"低吸轮动选股: {len(candidates)} 只通过筛选")

        return candidates

    def _holding_in_pool(self, code: str) -> bool:
        """
        趋势健康度复检（v6.7）：持仓股只用趋势条件判定"池内/池外"，不拷问入场时机。

        保留（趋势破位的信号）：
          - 条件2: MA5 >= MA20（均线未死叉）
          - 条件5: MACD DIF > DEA 且 DIF > 0（动量未衰竭）
          - P1:   未从 20 日高点回落 > 8%（非暴力反转）

        剔除（入场时机条件——持仓一根阴线就因条件1被踢出池、抛物线止盈
        天天在岗，是实验5 右尾灭绝的直接原因）：
          - 条件1 昨日收阳 + 涨幅 >= 0.7%
          - 条件3 量比 >= 1.2
          - 条件4 ROC > 5
          - 条件6 低吸位 <= 0.15%
        """
        df = self._data_cache.get(code)
        if df is None:
            return False
        try:
            # 新鲜度：当天无 bar（停牌等）仍可视为在池，避免误杀。
            # 选股时已有幽灵持仓守卫保证买入只在当日有 bar 的股票上发生。
            closes = df["close"].values.astype(np.float64)
            if len(closes) < 25:
                return True  # 数据不足时偏向"在池"

            # 条件2: MA5 >= MA20
            ma5 = float(np.mean(closes[-5:]))
            ma20 = float(np.mean(closes[-20:]))
            if ma5 < ma20:
                return False

            # 条件5: MACD 多头
            if not self._check_macd_bullish(closes):
                return False

            # P1: 未从 20 日新高回落 > 8%
            hhv_20 = float(np.max(closes[-20:]))
            if hhv_20 > 0 and closes[-1] < hhv_20 * 0.92:
                return False

            return True
        except Exception:
            return True  # 异常时偏向"在池"，让止损兜底

    # =============================================================================
    # 两步合一步复检（差异三：用今日 bar 数据二次验证候选股）
    # =============================================================================

    def _recheck_buy_list(self, buy_list: List[str]) -> List[str]:
        """
        两步合一步复检：用今日已收到的 Bar 数据重新验证候选股。

        相当于源策略 9:51 二次筛选的核心功能，但不依赖时间片调度：
          1. 今日成交量 > 0（非停牌/无交易）
          2. 今日开盘未涨停
          3. 今日跳空 < 3%（避免追高）
          4. 用今日开盘价重新验证 20 日新高低吸条件

        Args:
            buy_list: _screen_stocks 输出的候选列表。

        Returns:
            通过复检的候选列表。
        """
        confirmed: List[str] = []
        below_rate = float(self.parameters.get("buy_below_high_rate", 0.0015))

        for code in buy_list:
            df = self._data_cache.get(code)
            if df is None or len(df) < 2:
                continue

            opens = df["open"].values.astype(np.float64)
            volumes = df["volume"].values.astype(np.float64)
            closes = df["close"].values.astype(np.float64)

            today_open = float(opens[-1])
            today_vol = float(volumes[-1])
            prev_close = float(closes[-2]) if len(closes) >= 2 else 0

            # 检查1: 今日有成交量（非停牌/无交易）
            if today_vol <= 0:
                continue

            # 检查2: 今日开盘未涨停（open < 前收 × 1.095）
            if prev_close > 0 and today_open >= prev_close * 1.095:
                continue

            # 检查3: 今日跳空未超过 3%
            if prev_close > 0 and (today_open - prev_close) / prev_close > 0.03:
                continue

            # 检查4: 用今日开盘价重新验证 20 日新高条件
            hhv_20 = float(np.max(closes[-20:])) if len(closes) >= 20 else 0
            if hhv_20 > 0:
                below = (hhv_20 - today_open) / hhv_20
                if below < below_rate:
                    continue

            confirmed.append(code)

        return confirmed

    # =============================================================================
    # 震荡市成交量排名过滤（方案C：只买流动性前50%的候选股）
    # =============================================================================

    def _filter_sideways_volume(self, candidates: List[str]) -> List[str]:
        """
        震荡市中，按近5日均量排序，只保留成交量前50%的候选股。

        逻辑：震荡市中大量"脉冲一日游"的伪信号，
        成交量大的股票至少说明有资金关注，失败概率更低。

        Args:
            candidates: 复检后的候选列表。

        Returns:
            成交量前50%的候选列表（最少保留1只）。
        """
        if len(candidates) <= 2:
            return candidates

        vol_list = []
        for code in candidates:
            df = self._data_cache.get(code)
            if df is None or len(df) < 5:
                continue
            volumes = df["volume"].values.astype(np.float64)
            avg_vol = float(np.mean(volumes[-5:]))
            vol_list.append((code, avg_vol))

        if len(vol_list) <= 2:
            return [c[0] for c in vol_list]

        vol_list.sort(key=lambda x: x[1], reverse=True)
        cutoff = max(1, len(vol_list) // 2)
        filtered = [c[0] for c in vol_list[:cutoff]]

        if self.verbose_logging:
            logger.info(
                f"震荡市成交量过滤: {len(candidates)} → {len(filtered)} 只 "
                f"(保留成交量前50%)"
            )
        return filtered

    # =============================================================================
    # MACD 检查（numpy 版）
    # =============================================================================

    @staticmethod
    def _check_macd_bullish(closes: np.ndarray) -> bool:
        """
        MACD 多头检查：DIF > DEA（DIF 在信号线上方）且 DIF > 0，确认上升趋势。
        比原版仅 DIF > 0 更严格，避免高位钝化时误入。

        v6.2: 用 pandas ewm 标准递推（adjust=False，与 talib 一致）向量化计算
        DIF 全序列与 DEA，修复旧版滑窗切片长度不足导致 DEA 恒为死代码、
        实际退化为 DIF > 0 的问题。
        """
        if len(closes) < 35:   # 26 期 EMA 收敛 + 9 期 DEA
            return False

        s = pd.Series(closes, dtype="float64")
        ema12 = s.ewm(span=12, adjust=False).mean()
        ema26 = s.ewm(span=26, adjust=False).mean()
        dif = ema12 - ema26
        dea = dif.ewm(span=9, adjust=False).mean()

        dif_now = float(dif.iloc[-1])
        dea_now = float(dea.iloc[-1])
        return dif_now > dea_now and dif_now > 0

    # =============================================================================
    # 止盈止损（v2.0 纯净版 — -4% 止损 + 抛物线止盈）
    # =============================================================================

    def _finalize_exits(self) -> None:
        """
        结算前一日标记为待卖出的股票。

        将已确认卖出的股票从 _holdings 中移除，并将该回合的收益按
        1 + pnl×weight 复利进 _nav_realized（v6.4）——已兑现利润
        以复利净值形式保留，组合回撤计算无 phantom drawdown、不被笔数稀释。
        """
        for code in list(self._exit_pending):
            if code in self._holdings:
                entry = self._holdings[code].get("entry_price", 0)
                w = self._holdings[code].get("weight", 1.0)
                exit_price = self._get_price(code)
                if entry > 0 and exit_price > 0:
                    pnl = (exit_price - entry) / entry
                    self._nav_realized *= 1.0 + pnl * w
                if self.verbose_logging:
                    logger.info(f"结算出场: {code} entry={entry:.2f} exit={exit_price:.2f} pnl={pnl:.1%}")
                del self._holdings[code]
            if code in self._track_high:
                del self._track_high[code]
        self._exit_pending.clear()

    def _check_all_stop_profit(self, today_pool: Set[str] = None, stop_loss: float = -0.04) -> List[TradingSignal]:
        """
        P0: 池内池外区分止盈（源策略核心逻辑）。

        池内股（仍在今日选股池）→ 只止损，不止盈（让强势股自由奔跑）
        池外股（已跌出选股池）→ 止损 + 抛物线止盈（原版逻辑）

        Args:
            today_pool: 今日选股池（新候选股 + 仍通过今日筛选条件的持仓，v6.6）
            stop_loss: 动态止损比例（由三档行情决定，上涨市 -4%，下跌市 -2.5%）
        """
        signals: List[TradingSignal] = []

        for code in list(self._holdings.keys()):
            if code in self._exit_pending:
                continue

            entry = self._holdings[code]["entry_price"]
            if entry <= 0:
                self._holdings.pop(code, None)
                continue

            df = self._data_cache.get(code)
            if df is None or len(df) == 0:
                continue
            current_price = float(df["close"].iloc[-1])

            # 更新最高价
            if code not in self._track_high:
                self._track_high[code] = current_price
            else:
                self._track_high[code] = max(self._track_high[code], current_price)

            high = self._track_high[code]
            pnl = (current_price - entry) / entry
            dd = (high - current_price) / high if high > 0 else 0

            # 是否为今日选股池内股
            is_in_pool = today_pool is not None and code in today_pool

            # ---- 动态再平衡（在止损前执行，防集中度风险）----
            rebalance_th = float(self.parameters.get("rebalance_threshold", 1.0))
            if pnl >= rebalance_th:
                old_shares = self._holdings[code].get("shares", 0)
                half_shares = max(int(old_shares / 2 / 100) * 100, 100)
                self._holdings[code]["shares"] = old_shares - half_shares
                self._holdings[code]["weight"] = self._holdings[code].get("weight", 1.0) / 2
                sig = self._make_exit_signal(
                    code, reason=f"动态再平衡: 浮盈{pnl:.1%}>={rebalance_th:.0%}，减半仓({old_shares}→{old_shares-half_shares}股)",
                    signal_type=SignalType.TAKE_PROFIT,
                    order_mode="close",
                )
                sig.half_exit = True
                signals.append(sig)
                if self.verbose_logging:
                    logger.info(
                        f"动态再平衡: {code} 浮盈{pnl:.1%}>={rebalance_th:.0%}，"
                        f"减半仓({old_shares}→{old_shares - half_shares}股)"
                    )
                # 重置最高价（减半仓后重新追踪）
                self._track_high[code] = current_price
                continue

            # ---- 止损（所有持仓统一执行）----
            # v6.11: 日内止损 — 用当日 low 判定（盘中触及止损价即触发，而非只看收盘价）。
            # 出场信号携带 trigger_price=止损价，broker 按触发价当日成交（Model A）。
            day_low = float(df["low"].iloc[-1]) if "low" in df.columns else current_price
            low_pnl = (day_low - entry) / entry if entry > 0 else 0.0

            # 同日买入的持仓（entry_date == 今日）不触发止损（T+1 锁定，当日无法卖）
            _same_day_buy = (
                self._holdings[code].get("entry_date", "")
                == str(self._last_trade_date)[:10]
            )

            if (low_pnl < stop_loss or pnl < stop_loss) and not _same_day_buy:
                self._exit_pending.add(code)
                stop_price = entry * (1 + stop_loss)
                if self.verbose_logging:
                    logger.info(
                        f"止损触发: {code} entry={entry:.2f} low={day_low:.2f} "
                        f"low_pnl={low_pnl:.1%} close_pnl={pnl:.1%} stop={stop_loss:.1%} "
                        f"trigger={stop_price:.2f}"
                    )
                signals.append(self._make_exit_signal(
                    code,
                    reason=f"止损: 日内最低{low_pnl:.1%} 收盘{pnl:.1%} < {stop_loss:.1%}",
                    signal_type=SignalType.STOP_LOSS,
                    order_mode="trigger",
                    trigger_price=stop_price,
                ))
                continue
            elif self.verbose_logging and (low_pnl < stop_loss or pnl < stop_loss) and _same_day_buy:
                logger.info(f"止损跳过(同日买入): {code} low_pnl={low_pnl:.1%} < {stop_loss:.1%}")

            # ---- 池内股：只止损，不止盈，跳过所有止盈逻辑 ----
            # 集中度风险由「动态再平衡」（浮盈≥100%卖半仓）处理，更精准
            if is_in_pool:
                continue

            # ---- 池外股：抛物线止盈（v6.12 放宽阈值，让右尾跑更久）----
            # v6.11: 当日收盘价成交（order_mode="close"），与止损同日内完成
            tp_drawdown = 0.0
            if pnl >= 0.80:
                tp_drawdown = float(self.parameters.get("tp_dd_80", 0.08))
            elif pnl >= 0.40:
                tp_drawdown = float(self.parameters.get("tp_dd_40", 0.12))
            elif pnl >= 0.20:
                tp_drawdown = float(self.parameters.get("tp_dd_20", 0.14))
            elif pnl >= 0.10:
                tp_drawdown = float(self.parameters.get("tp_dd_10", 0.15))

            if tp_drawdown > 0 and dd >= tp_drawdown:
                self._exit_pending.add(code)
                signals.append(self._make_exit_signal(
                    code, reason=f"池外止盈: 浮盈{pnl:.1%} 高点回落{dd:.1%}>{tp_drawdown:.0%}",
                    signal_type=SignalType.TAKE_PROFIT,
                    order_mode="close",
                ))

        return signals

    # =============================================================================
    # 工具方法
    # =============================================================================

    @classmethod
    def _is_tradable(cls, code: str) -> bool:
        """判断是否可交易的主板股票"""
        if not code:
            return False
        stock_code = code.split(".")[0]
        if not stock_code:
            return False
        if stock_code.startswith(cls.FORBID_PREFIX):
            return False
        if not stock_code.startswith(cls.ALLOW_PREFIX):
            return False
        return True


    def _is_trading_day(self, d: Any) -> bool:
        """
        v6.13: 判断日期是否为交易日（排除周末 + 节假日）。

        周末/节假日手动运行策略时，不触发调仓/候选确认，避免候选在非交易日被误判过期。
        快速路径：先判周末（无需 DB），再走 TradingCalendar（节假日）。

        Args:
            d: 日期（str "YYYY-MM-DD" / date / datetime / None）

        Returns:
            True = 交易日；数据缺失/解析失败时 fail-open（True），不阻塞回测。
        """
        if not d:
            return True
        try:
            if isinstance(d, str):
                d = date.fromisoformat(d[:10])
            elif hasattr(d, "date"):
                d = d.date()
            # 快速路径：周末直接 False，避免 TradingCalendar 实例化开销
            if d.weekday() >= 5:
                return False
            from utils.core_utils.time_utils.trading_calendar import TradingCalendar
            return TradingCalendar().is_trading_day(d)
        except Exception:
            # 回测环境无交易日历或解析失败 → fail-open，不阻塞
            return True

    def _is_new_stock(self, code: str) -> bool:
        """
        判断是否为新股（上市不满 new_stock_days 个交易日）。

        v6.2: 优先用真实上市日期（on_start 从 stock_basic 填充 _listing_dates）
        与当前回测日比较；30 个交易日按 1.5 倍折算自然日（≈45 天）。
        无上市日期数据时回退到缓存行数近似（数据越少上市越晚）。
        """
        new_days = int(self.parameters.get("new_stock_days", 30))

        list_date = self._listing_dates.get(code)
        if list_date and self._last_trade_date:
            try:
                d0 = date.fromisoformat(str(list_date)[:10])
                d1 = date.fromisoformat(str(self._last_trade_date)[:10])
                return (d1 - d0).days < int(new_days * 1.5)
            except ValueError:
                pass  # 日期格式异常 → 回退缓存行数近似

        df = self._data_cache.get(code)
        if df is None or len(df) < 2:
            return True
        return len(df) < new_days

    # =============================================================================
    # v6.10 拉高出货检测（多信号模型）
    # =============================================================================
    #
    # 四个独立信号，每个基于不同的数据维度：
    #
    #   S1 — 放量见顶 (Volume Climax):
    #     最后一次涨停的成交量是否显著放大（相对于前几次涨停均量）。
    #     逻辑：真正的强势股放量均匀，出货股在最后一根涨停上倾泻筹码。
    #
    #   S2 — 出货日 (Distribution Day):
    #     连板后是否出现放量下跌 + 大振幅的出货日。
    #     逻辑：拉高后必然有出货动作——高量 + 收阴 + 宽振幅是标准出货特征。
    #
    #   S3 — 抛物线衰竭 (Parabolic Exhaustion):
    #     是否有 ≥3 个连续涨停（抛物线式上涨），且当前已从高位回落。
    #     逻辑：连续涨停是不可持续的，回落确认了衰竭而非健康回调。
    #
    #   S4 — 高位异常量 (High-Position Volume Anomaly):
    #     近 5 日的日均换手（以量代理）是否为近 60 日最高的区间。
    #     逻辑：高位异常放量 ≈ 聪明钱在出货给追涨的散户。
    #
    # 决策表:
    #   0 信号 → 正常候选，放行
    #   1 信号 → 边缘情况，放行但 verbose 日志记录
    #   2+ 信号 → 拉高出货确认，拦截
    #
    # =============================================================================

    def _detect_pump_and_dump(self, code: str):
        """
        多信号拉高出货检测。

        Returns:
            (score, reasons): score ∈ [0, 4], reasons = 命中的信号描述列表。
            调用方按 pd_signal_threshold（默认 2）决定是否拦截。
        """
        if not bool(self.parameters.get("pump_dump_filter_enabled", True)):
            return 0, []

        df = self._data_cache.get(code)
        if df is None or len(df) < 25:
            return 0, []

        try:
            closes = df["close"].values.astype(np.float64)
            volumes = df["vol"].values.astype(np.float64)
            opens = df["open"].values.astype(np.float64)
            highs = df["high"].values.astype(np.float64)

            score = 0
            reasons: List[str] = []

            # ---- 标记近 10 日的涨停日（索引从末尾倒数）----
            limit_up_indices = []
            for i in range(-10, 0):
                prev_c = closes[i - 1]
                cur_c = closes[i]
                if prev_c > 0 and (cur_c / prev_c - 1.0) >= 0.095:
                    limit_up_indices.append(i)

            # 没有涨停 → 不触发任何信号
            if not limit_up_indices:
                return 0, []

            # ============================================================
            # S1: 放量见顶 — 末次涨停量是否异常放大
            # ============================================================
            if len(limit_up_indices) >= 2:
                last_up_idx = limit_up_indices[-1]  # 最近一次涨停
                prev_up_indices = limit_up_indices[:-1]  # 之前的涨停
                last_up_vol = volumes[last_up_idx]
                prev_up_vols = [volumes[i] for i in prev_up_indices]
                avg_prev_vol = float(np.mean(prev_up_vols)) if prev_up_vols else last_up_vol

                ratio = float(self.parameters.get("pd_vol_climax_ratio", 1.5))
                if avg_prev_vol > 0 and last_up_vol / avg_prev_vol > ratio:
                    score += 1
                    reasons.append(f"S1:放量见顶(末次量/前均={last_up_vol/avg_prev_vol:.1f})")

            # ============================================================
            # S2: 出货日 — 连板后出现放量下跌 + 大振幅
            # ============================================================
            avg_vol_20 = float(np.mean(volumes[-20:])) if len(volumes) >= 20 else 0
            last_up_idx = limit_up_indices[-1]
            # 检查最后一次涨停之后的所有交易日
            for i in range(last_up_idx + 1, 0):  # 从涨停次日到今天
                day_vol = volumes[i]
                day_close = closes[i]
                day_open = opens[i]
                day_high = highs[i]
                day_range = (day_high - day_close) / day_close if day_close > 0 else 0

                vol_ratio = float(self.parameters.get("pd_distribution_vol_ratio", 1.5))
                range_pct = float(self.parameters.get("pd_distribution_range_pct", 0.05))

                if (avg_vol_20 > 0 and day_vol > avg_vol_20 * vol_ratio
                        and day_close < day_open
                        and day_range > range_pct):
                    score += 1
                    reasons.append(f"S2:出货日(量{day_vol/avg_vol_20:.1f}x 振幅{day_range:.1%})")
                    break  # 一个出货日就够

            # ============================================================
            # S3: 抛物线衰竭 — 连续 ≥N 个涨停 + 从高点回落 > 阈值
            # ============================================================
            consecutive_needed = int(self.parameters.get("pd_parabolic_consecutive", 3))
            # 找最近的连续涨停序列
            streak = 1
            for j in range(len(limit_up_indices) - 1, 0, -1):
                if limit_up_indices[j] == limit_up_indices[j - 1] + 1:
                    streak += 1
                else:
                    break

            if streak >= consecutive_needed:
                # 计算从这段涨停的最高点的回落
                streak_start = limit_up_indices[-streak] if streak <= len(limit_up_indices) else limit_up_indices[0]
                # 涨停期间的最高价
                peak_in_streak = float(np.max(highs[streak_start:]))
                current = closes[-1]
                dd_from_peak = (peak_in_streak - current) / peak_in_streak if peak_in_streak > 0 else 0

                dd_threshold = float(self.parameters.get("pd_parabolic_dd_threshold", 0.05))
                if dd_from_peak > dd_threshold:
                    score += 1
                    reasons.append(f"S3:抛物线衰竭({streak}连板 回落{dd_from_peak:.1%})")

            # ============================================================
            # S4: 高位异常量 — 近 5 日均量是否为近 60 日最高区间
            # ============================================================
            if len(volumes) >= 60 and limit_up_indices:
                recent_avg_vol = float(np.mean(volumes[-5:]))
                historical_vols = volumes[-60:-5]  # 排除最近 5 天
                pct_rank = float(np.mean(historical_vols < recent_avg_vol)) if len(historical_vols) > 0 else 0

                # 近 5 日均量处于近 60 日的 top 10% → 异常
                if pct_rank > 0.90:
                    score += 1
                    reasons.append(f"S4:高位异常量(量能分位{pct_rank:.0%})")

            return score, reasons

        except Exception:
            return 0, []

    def _get_price(self, code: str) -> float:
        df = self._data_cache.get(code)
        if df is not None and len(df) > 0:
            return float(df["close"].iloc[-1])
        return 0.0
    def _build_dataframe_cache(self) -> None:
        """将 raw_cache 中的原始 bar 数据一次性转为 DataFrame。

        v6.10: 替代逐 bar pd.concat，消除 O(n²) 内存拷贝。
        仅处理有新数据且未转为 DataFrame 的股票。
        """
        if not self._raw_cache:
            return
        cols = ["close", "volume", "amount", "open", "high", "low"]
        for ts_code, rows in self._raw_cache.items():
            if not rows:
                continue
            df = pd.DataFrame(rows, columns=cols)
            if ts_code in self._data_cache and len(self._data_cache[ts_code]) > 0:
                # 已有 DataFrame（预热数据），追加
                existing = self._data_cache[ts_code]
                df = pd.concat([existing, df], ignore_index=True)
            self._data_cache[ts_code] = df
        self._raw_cache.clear()  # 清空原始缓存，下次 bar 会重新累积

    def _append_data(self, ts_code: str, bar: BarData) -> None:
        # 新鲜度守卫：记录每只股票最后一根实时 bar 的日期。
        bar_date = str(getattr(bar, "trade_date", "") or getattr(bar, "datetime", ""))[:10]
        if bar_date:
            self._bar_dates[ts_code] = bar_date

        # v6.10: 原始数据存入 list of tuples，避免逐 bar pd.concat 的 O(n^2) 拷贝。
        # 在 _build_dataframe_cache() 中一次性转为 DataFrame。
        if ts_code not in self._raw_cache:
            self._raw_cache[ts_code] = []
        self._raw_cache[ts_code].append((
            float(bar.close), float(bar.volume), float(bar.amount or 0),
            float(getattr(bar, "open", bar.close)),
            float(getattr(bar, "high", bar.close)),
            float(getattr(bar, "low", bar.close)),
        ))
        # 限制缓存（最多保留 250 行）
        if len(self._raw_cache[ts_code]) > 250:
            self._raw_cache[ts_code] = self._raw_cache[ts_code][-250:]

    @staticmethod
    def _gen_id() -> str:
        import uuid
        return str(uuid.uuid4())

    def _make_exit_signal(
        self,
        ts_code: str,
        reason: str = "",
        signal_type: SignalType = SignalType.EXIT,
        order_mode: str = "open",
        trigger_price: Optional[float] = None,
    ) -> TradingSignal:
        price = self._get_price(ts_code)
        # 卖出数量交由引擎 Sizer 按 Broker 真实持仓计算：
        #   quantity=0 → select_sizer 选 CloseAllSizer（全平, 卖出 pos.quantity）
        #   quantity=0 且 half_exit=True → HalfCloseSizer（卖出真实持仓一半）
        # 策略不再自算股数, 从根上消除"意图股数 ≠ 实际持仓"发散（买多少即卖多少）。
        #
        # v6.11 执行模式：
        #   - 止损 (STOP_LOSS) → order_mode="trigger", trigger_price=止损价（日内触及即成交）
        #   - 其他出场 (止盈/半仓轮动/到期) → order_mode="close"（当日收盘价成交）
        return TradingSignal(
            id=self._gen_id(),
            strategy_id=self.name,
            strategy_name=self.name,
            ts_code=ts_code,
            signal_type=signal_type,
            direction=SignalDirection.CLOSE_LONG,
            price=price,
            quantity=0,
            amount=0.0,
            confidence=0.80,
            reason=reason,
            timestamp=datetime.now(),
            order_mode=order_mode,
            trigger_price=trigger_price,
        )
