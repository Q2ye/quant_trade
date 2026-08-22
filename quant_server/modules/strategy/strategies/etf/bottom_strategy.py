# -*- coding: utf-8 -*-
"""
LightGBM ETF 底部抄底策略 v4
============================
P1: 分市场自适应参数（牛/熊/震荡）
P2: 凯利公式仓位管理
P3: 量能确认 + 智能时间止损
"""
import logging
import uuid
from datetime import date, datetime
from shared.utils.time_utils import BEIJING_TZ, beijing_now
from pathlib import Path
from typing import Dict, List, Optional, Any

import joblib
import numpy as np

from core.engines.types.entities import BarData
from modules.strategy.constants import StrategyType, SignalDirection, SignalType
from modules.strategy.models import TradingSignal
from modules.strategy.strategies.base.base_strategy import BaseStrategy

logger = logging.getLogger(__name__)


class LightGBMBottomStrategy(BaseStrategy):
    strategy_type = StrategyType.ML

    DEFAULT_PARAMS = {
        "model_path": "",
        "threshold": 0.30,
        "max_single_position": 0.40,
        "max_positions": 5,
        "stop_loss": -0.07,
        "trail_activate": 0.05,
        "trail_distance": 0.08,
        "max_hold_days": 20,
        "cooling_days": 2,
        "min_warmup_bars": 60,
        "feature_list": [],
        # 2026-08-20：过滤创业板/科创板 ETF（159 开头创业板类 9 只已剔除，
        # 暂未接入科创板权限）。保留沪市主板 + 行业 + 跨境 + 黄金 + 债，共 16 只。
        "etf_pool": [
            "510050.SH","510300.SH","510500.SH","510880.SH",
            "512880.SH","512660.SH","512800.SH","512100.SH",
            "518880.SH","513100.SH","513050.SH",
            "511010.SH","511260.SH","510310.SH",
            "512170.SH","516510.SH","512400.SH",
        ],
        "vol_filter_enabled": True,
        "vol_filter_atr_min": 0.015,
        "confirm_enabled": True,
        # v4: 分市场参数 (0=BEAR, 1=RANGE, 2=BULL)
        # P2-1 (修正甲): 熊市升阈值(0.60 只接高赔率底)、震荡中性(0.54 守空仓站位)、牛市升阈值(0.60 不追假底)。
        # 2026-08 实测：震荡降阈值(0.48) 使策略在牛市夹杂震荡段不再严格空仓(前向 -1.96%)，故改中性
        "regime_threshold_adj": {0: 0.06, 1: 0.0, 2: 0.06},
        # 2026-08-20：候选/持仓上限降为 2 只（此前熊5/震3/牛4 太多，分散稀释）
        "regime_max_positions":  {0: 2, 1: 2, 2: 2},
        "regime_stop_loss":     {0: -0.08, 1: -0.06, 2: -0.07},
        "regime_trail_act":     {0: 0.06, 1: 0.04, 2: 0.05},
        "regime_trail_dist":    {0: 0.10, 1: 0.06, 2: 0.08},
        "regime_max_hold":      {0: 25, 1: 14, 2: 20},
        # P3: 量能确认
        "vol_confirm_enabled": True,
        # v9: 大盘 regime 目标仓位（防守策略：熊/震生效，牛市空仓让位进攻）
        "use_market_gate": True,
        # regime 判定带宽（CSI500 vs MA250 偏离阈值，2026-08 参数化）：
        # ±3% 回测验证最优（防守 +30.7%/组合 MDD -23%）；±1% 实测致震荡参与减少→组合 MDD -27% 恶化。
        # 组合中牛市防守让位由 allocator 处理（牛市 defense 0），无需收窄带宽。
        "regime_gate_band": 0.03,
        "market_target_position": {0: 0.55, 1: 0.75, 2: 0.0},
        # DB
        "db_host": "localhost", "db_port": 5432,
        "db_user": "postgres", "db_password": "123456",
        "db_name": "quant_signals_dev",
        # 调试：默认关闭逐 bar 的 P4 缓冲/确认日志（P4/SIG 真实信号不受影响）
        "trace": False,
    }

    def __init__(self, name, strategy_type=None, parameters=None):
        defaults = dict(self.DEFAULT_PARAMS)
        if parameters:
            defaults.update(parameters)
        super().__init__(name=name, strategy_type=strategy_type or StrategyType.ML, parameters=defaults)
        # v9.1 修复：API JSON 参数 dict key 为字符串，统一转 int
        # （否则 .get(regime) 用整数 key 匹配字符串 key dict 全落默认值 → 0 信号）
        for _reg_key in ("market_target_position", "regime_max_positions",
            "regime_stop_loss", "regime_threshold_adj",
            "regime_trail_act", "regime_trail_dist", "regime_max_hold"):
            _reg_dict = self.parameters.get(_reg_key)
            if isinstance(_reg_dict, dict):
                self.parameters[_reg_key] = {int(_rk): _rv for _rk, _rv in _reg_dict.items()}
        self.model = None
        self.feature_names: List[str] = []
        self.scaler_mu: List[float] = []
        self.scaler_sigma: List[float] = []
        self._factor_cache: Dict[str, Dict[str, Dict[str, float]]] = {}
        self._data_cache: Dict[str, List[BarData]] = {}
        self._position_entry: Dict[str, tuple] = {}
        self._track_high: Dict[str, float] = {}
        self._cooling: Dict[str, int] = {}
        self._p4_buffer: Dict[str, dict] = {}  # v3.4: P4 确认缓冲区，独立于 BaseStrategy._pending_signals
        # v3.4: 每日诊断计数器
        self._diag = self._reset_diag()
        self.use_market_gate = bool(self.parameters.get("use_market_gate", True))
        self._csi500_cache: List[tuple] = []  # [(trade_date, close)] 大盘 regime

    def _reset_diag(self) -> dict:
        return {
            "bars_processed": 0, "in_pool": 0, "warmup_skip": 0,
            "no_model": 0, "cooling": 0, "in_position": 0,
            "max_positions": 0, "p4_pending": 0, "p4_confirmed": 0,
            "proba_none": 0, "proba_below": 0, "vol_filter": 0,
            "vol_confirm": 0, "weight_zero": 0, "p4_buffered": 0, "entry_generated": 0,
            "top_probas": [],  # [(ts_code, proba, regime), ...]
        }

    def get_daily_diagnostic(self) -> dict:
        d = dict(self._diag)
        # 只保留 top 5 proba
        d["top_probas"] = sorted(d["top_probas"], key=lambda x: -x[1])[:5]
        self._diag = self._reset_diag()
        return d

    def on_init(self) -> None:
        etf_pool = self.parameters.get("etf_pool") or []
        self._universe = list(etf_pool)
        logger.info("[%s] universe=%d ETFs", self.name, len(self._universe))
        model_path = self.parameters.get("model_path", "")
        if not model_path:
            model_path = self._find_latest_model()
        if not model_path:
            logger.warning("[%s] 未找到模型文件", self.name)
            return
        artifact = joblib.load(model_path)
        self.model = artifact["model"]
        self.feature_names = artifact.get("feature_names", [])
        s = artifact.get("scaler_params", {})
        self.scaler_mu = s.get("mu", [])
        self.scaler_sigma = s.get("sigma", [])
        saved_t = artifact.get("threshold")
        if saved_t is not None and self.parameters["threshold"] == self.DEFAULT_PARAMS["threshold"]:
            t = float(saved_t)
            if not hasattr(self.model, 'predict_proba') and t > 0.80:
                t = t / 2.0
            self.parameters["threshold"] = t
        logger.info("[%s] 模型已加载: %s, features=%d, threshold=%.2f",
                    self.name, Path(model_path).name,
                    len(self.feature_names), self.parameters["threshold"])
        if etf_pool and self.feature_names:
            self._load_factor_cache(etf_pool)
        # 标记 P4 确认缓冲区待恢复（延迟到 load_live_state 之后执行）
        self._confirm_restored = False
        self._load_csi500_cache()

    @staticmethod
    def _find_latest_model() -> str:
        try:
            try:
                base = Path(__file__).resolve().parent.parent.parent.parent.parent
            except NameError:
                base = Path.cwd()
            model_dir = base / "storage" / "models"
            files = sorted(model_dir.glob("etf_bottom_v*.joblib"), reverse=True)
            if files:
                logger.info("自动发现模型: %s", files[0].name)
                return str(files[0])
        except Exception as e:
            logger.warning("自动发现模型失败: %s", e)
        return ""

    def _restore_confirm_buffer(self) -> None:
        """从历史数据重建 P4 确认缓冲区（启动后/重启后调用）

        P4 确认缓冲区保存「昨日通过概率阈值、等待今日收盘价确认」的 ETF。
        重启导致内存丢失后，从 DB 历史 bar + factor 数据重建，
        避免当日 0 信号。
        此方法由 on_bar 首次调用时延迟执行，确保 load_live_state 已注入持仓。

        v3.5: 回测模式下跳过恢复，避免实盘 P4 缓冲区状态泄露到历史回测起点。
        """
        # 回测模式下 P4 缓冲区应从空开始，由回测数据逐日累积
        if self.context and self.context.run_mode.value == "backtest":
            logger.info("[%s] 回测模式，跳过 P4 确认缓冲区恢复", self.name)
            return
        if not self.parameters.get("confirm_enabled", False):
            logger.info('[TRACE] _restore_confirm_buffer: confirm_enabled=False, skip')
            return
        etf_pool = self.parameters.get("etf_pool") or []
        if not etf_pool or self.model is None:
            logger.info('[TRACE] _restore_confirm_buffer: pool=%s model=%s, skip',
                        'empty' if not etf_pool else 'ok', 'yes' if self.model else 'no')
            return
        logger.info('[TRACE] _restore_confirm_buffer 开始: pool=%d model=yes', len(etf_pool))

        import psycopg2
        cfg = {
            "host": self.parameters.get("db_host", "localhost"),
            "port": self.parameters.get("db_port", 5432),
            "user": self.parameters.get("db_user", "postgres"),
            "password": self.parameters.get("db_password", "123456"),
            "database": self.parameters.get("db_name", "quant_signals_dev"),
        }
        try:
            conn = psycopg2.connect(**cfg)
            cur = conn.cursor()
            # 1. 从因子缓存中找到最近有因子数据的交易日（而非 etf_daily 最新日期）
            _sample_cache = self._factor_cache.get(etf_pool[0], {}) if etf_pool else {}
            _cache_dates = sorted(_sample_cache.keys()) if _sample_cache else []
            if not _cache_dates:
                cur.close(); conn.close()
                logger.warning("[%s] P4恢复: 因子缓存为空，跳过", self.name)
                return
            yesterday = _cache_dates[-1]  # 缓存中最新的日期
            # 转为 date 对象（缓存 key 是 'YYYY-MM-DD' 字符串）
            if isinstance(yesterday, str):
                from datetime import datetime as _dt
                yesterday = _dt.strptime(yesterday, "%Y-%m-%d").date()

            # 2. 昨日 bar 的 low（ETF 在 etf_daily 表）
            cur.execute(
                "SELECT ts_code, low FROM etf_daily "
                "WHERE ts_code = ANY(%s) AND trade_date = %s",
                (etf_pool, yesterday),
            )
            bar_map = {r[0]: float(r[1]) for r in cur.fetchall()}
            cur.close(); conn.close()

            if not bar_map:
                logger.warning("[%s] P4恢复: 昨日(%s) 无 bar 数据", self.name, yesterday)
                return

            # 3. 遍历 ETF pool，预测 → 筛选 → 填入确认缓冲区
            # 日终因子可能在启动后才有 → 强制刷新缓存
            self._load_factor_cache(etf_pool)
            # 检查缓存是否刷新到最新
            _sample = etf_pool[0]
            _cache = self._factor_cache.get(_sample, {})
            _dates = sorted(_cache.keys()) if _cache else []
            logger.info('[%s] P4恢复: 因子缓存刷新后 %s 最新日期=%s 总天数=%d',
                        self.name, _sample, _dates[-1] if _dates else 'EMPTY', len(_dates))
            held = set(self._active_positions.keys())
            restored = 0
            skip_none = skip_thr = skip_vol = skip_wt = skip_bar = 0
            for ts_code in etf_pool:
                if ts_code in held or ts_code in self._position_entry:
                    continue
                proba = self._predict(ts_code, yesterday)
                if proba is None:
                    skip_none += 1; continue
                regime = self._get_regime(ts_code, yesterday)
                base_t = self.parameters["threshold"]
                radj = self.parameters.get("regime_threshold_adj", {}).get(regime, 0.0)
                day_t = base_t + radj
                if proba < day_t:
                    skip_thr += 1; continue
                if self.parameters.get("vol_filter_enabled", False):
                    ar = self._get_factor_value(ts_code, yesterday, "atr_ratio_20")
                    if ar is None or ar < self.parameters.get("vol_filter_atr_min", 0.015):
                        skip_vol += 1; continue
                weight = self._calc_weight(regime)
                if weight <= 0.0:
                    skip_wt += 1; continue
                low = bar_map.get(ts_code)
                if low is None:
                    skip_bar += 1; continue
                self._p4_buffer[ts_code] = {
                    "proba": proba, "signal_low": low, "weight": weight,
                }
                restored += 1

            if restored:
                logger.info(
                    "[%s] P4确认缓冲区已恢复: %d 只 ETF (昨日=%s)",
                    self.name, restored, yesterday,
                )
            else:
                logger.info(
                    "[%s] P4恢复: 0只 (昨日=%s) | 跳过: none=%d thr=%d vol=%d wt=%d bar=%d held=%d",
                    self.name, yesterday, skip_none, skip_thr, skip_vol, skip_wt, skip_bar, len(held),
                )
        except Exception as e:
            logger.warning("[%s] P4确认缓冲区恢复失败: %s", self.name, str(e)[:200])

    def _load_csi500_cache(self) -> None:
        """加载 CSI500 日线（大盘 regime 判定用，psycopg2 同步）"""
        import psycopg2
        cfg = {
            "host": self.parameters.get("db_host", "localhost"),
            "port": self.parameters.get("db_port", 5432),
            "user": self.parameters.get("db_user", "postgres"),
            "password": self.parameters.get("db_password", "123456"),
            "database": self.parameters.get("db_name", "quant_signals_dev"),
        }
        try:
            conn = psycopg2.connect(**cfg)
            cur = conn.cursor()
            cur.execute(
                "SELECT trade_date::text, close FROM index_daily "
                "WHERE ts_code='000905.SH' AND trade_date>='2016-01-01' ORDER BY trade_date"
            )
            rows = [(r[0][:10], float(r[1])) for r in cur.fetchall()]
            cur.close(); conn.close()
            self._csi500_cache = rows
            logger.info("[%s] CSI500缓存: %d 行", self.name, len(rows))
        except Exception as e:
            logger.warning("[%s] CSI500加载失败（大盘门降级）: %s", self.name, str(e)[:150])
    def _load_factor_cache(self, etf_pool: list) -> None:
        import psycopg2
        cfg = {
            "host": self.parameters.get("db_host", "localhost"),
            "port": self.parameters.get("db_port", 5432),
            "user": self.parameters.get("db_user", "postgres"),
            "password": self.parameters.get("db_password", "123456"),
            "database": self.parameters.get("db_name", "quant_signals_dev"),
        }
        try:
            conn = psycopg2.connect(**cfg)
            cur = conn.cursor()
            for etf in etf_pool:
                cur.execute(
                    "SELECT factor_code, trade_date::text, factor_value "
                    "FROM factor_data WHERE ts_code=%s AND factor_code=ANY(%s) "
                    "AND trade_date>='2019-01-01' ORDER BY trade_date",
                    (etf, self.feature_names))
                cache: Dict[str, Dict[str, float]] = {}
                for fc, td, fv in cur.fetchall():
                    td = td[:10]
                    cache.setdefault(td, {})[fc] = float(fv) if fv is not None else np.nan
                if cache:
                    self._factor_cache[etf] = cache
            cur.close(); conn.close()
            logger.debug("[%s] 因子缓存: %d ETFs x %d features",
                        self.name, len(self._factor_cache), len(self.feature_names))
        except Exception as e:
            logger.warning("[%s] 因子缓存加载失败: %s", self.name, str(e)[:150])

    def _market_regime(self, trade_date_val) -> int:
        """大盘 regime：CSI500 收盘 vs MA250 ±3% → 0熊/1震荡/2牛（与组合层同口径）"""
        if not self.use_market_gate:
            return 1
        if hasattr(trade_date_val, 'strftime'): td_str = trade_date_val.strftime('%Y-%m-%d')
        elif hasattr(trade_date_val, 'isoformat'): td_str = trade_date_val.isoformat()[:10]
        else: td_str = str(trade_date_val)[:10]
        cached = self._csi500_cache
        if not cached:
            return 1
        closes = [c for d, c in cached if d <= td_str]
        if len(closes) < 250:
            return 1
        ma250 = sum(closes[-250:]) / 250.0
        close = closes[-1]
        band = float(self.parameters.get("regime_gate_band", 0.01))
        if close < ma250 * (1 - band):
            return 0
        elif close > ma250 * (1 + band):
            return 2
        return 1
    def _get_factor_value(self, ts_code: str, trade_date_val, factor_code: str) -> Optional[float]:
        cache = self._factor_cache.get(ts_code, {})
        if not cache: return None
        if hasattr(trade_date_val, 'strftime'): td_str = trade_date_val.strftime('%Y-%m-%d')
        elif hasattr(trade_date_val, 'isoformat'): td_str = trade_date_val.isoformat()[:10]
        else: td_str = str(trade_date_val)[:10]
        for d in sorted(cache.keys(), reverse=True):
            if d <= td_str:
                v = cache[d].get(factor_code)
                return float(v) if v is not None and not (isinstance(v, float) and np.isnan(v)) else None
        return None

    def _get_regime(self, ts_code: str, trade_date_val) -> int:
        val = self._get_factor_value(ts_code, trade_date_val, "market_regime")
        return max(0, min(2, int(val))) if val is not None else 1

    def _predict(self, ts_code: str, trade_date_val) -> Optional[float]:
        try:
            if hasattr(trade_date_val, 'strftime'): td_str = trade_date_val.strftime('%Y-%m-%d')
            elif hasattr(trade_date_val, 'isoformat'): td_str = trade_date_val.isoformat()[:10]
            else: td_str = str(trade_date_val)[:10]
            cache = self._factor_cache.get(ts_code, {})
            if not cache:
                etf_pool = self.parameters.get("etf_pool") or []
                if ts_code not in etf_pool and self.feature_names:
                    self._load_factor_cache([ts_code])
                    cache = self._factor_cache.get(ts_code, {})
            all_dates = sorted(cache.keys(), reverse=True)
            nearest = None
            for d in all_dates:
                if d <= td_str: nearest = d; break
            if nearest is None: return None
            row = cache[nearest]
            fv = [row.get(fn) if row.get(fn) is not None else np.nan for fn in self.feature_names]
            features = np.array(fv, dtype=np.float64).reshape(1, -1)
            nmask = np.isnan(features[0])
            # P2-6: 缺失率 >50% → 跳过（对齐回测脚本 backtest_etf_bottom.py:196 的 >50% NaN→skip），
            # 避免低数据量 ETF 用 0 填充污染概率
            if nmask.mean() > 0.5:
                return None
            if nmask.any(): features[0, nmask] = 0.0
            if self.scaler_mu and self.scaler_sigma:
                features[0] = (features[0] - np.array(self.scaler_mu)) / (np.array(self.scaler_sigma) + 1e-8)
            # 2026-08 修复：旧模型工件按 DataFrame（带特征名）拟合，numpy 输入触发
            # "X does not have valid feature names" 告警且无法按名对齐列序——
            # 用拟合时的特征名重建 DataFrame，兼容新旧两种工件。
            proba_input = features
            _fin = getattr(self.model, "feature_names_in_", None)
            if _fin is not None:
                import pandas as pd
                proba_input = pd.DataFrame(features, columns=_fin)
            if hasattr(self.model, 'predict_proba'):
                return float(self.model.predict_proba(proba_input)[0, 1])
            return float(self.model.predict(proba_input)[0])
        except Exception as e:
            logger.error("[%s] 预测失败: %s", self.name, str(e)[:200])
            return None

    def _calc_weight(self, regime: int) -> float:
        """v9: 目标仓位框架——regime 目标总仓位均分给候选（替代 v5 概率边际，解决资金闲置）"""
        if not self.use_market_gate:
            return 0.05  # 未启用大盘门：保守固定 5%（接近旧概率边际的低仓）
        target = self.parameters.get("market_target_position", {}).get(regime, 0.0)
        if target <= 0:
            return 0.0
        rmax = self.parameters.get("regime_max_positions", {}).get(regime, 3)
        return target / max(rmax, 1)
    def _is_live_mode(self) -> bool:
        """判断是否实盘/模拟盘模式（仅实盘持久化候选，回测不写 signals 表）。"""
        rm = getattr(getattr(self, "context", None), "run_mode", None)
        if rm is None:
            return False
        v = rm.value if hasattr(rm, "value") else rm
        return v in ("live", "paper")

    def _fire_db(self, coro) -> None:
        """在同步策略方法中调度异步 DB 写任务（fire-and-forget）。"""
        try:
            import asyncio
            asyncio.get_running_loop().create_task(coro)
        except RuntimeError:
            logger.debug("事件循环未运行，跳过候选 DB 写入")

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
                await SignalRepository(db).update(sig_id, {"signal_status": status, "reason": reason})
                await db.commit()
        except Exception as e:
            logger.warning(f"候选状态更新失败({status}): {e}")

    async def _persist_candidate(self, code: str, pinfo: dict) -> None:
        """ETF 候选落库：signals 表 pending_confirm（与进攻实盘候选一致，跨重启保留）。"""
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
                _td = getattr(self, "_last_trade_date", None)
                if isinstance(_td, str):
                    try:
                        _td = date.fromisoformat(_td[:10])
                    except ValueError:
                        _td = None
                elif hasattr(_td, "date"):
                    _td = _td.date()
                # 2026-08-19 修复：时刻用 beijing_now().time()（此前 00:00 固定，前端无具体时间）
                _sig_time = datetime.combine(_td, beijing_now().time(), tzinfo=BEIJING_TZ) if _td else beijing_now()
                data = {
                    "strategy_id": sid,
                    "ts_code": code,
                    "direction": "long",
                    "signal_type": "buy",
                    "signal_time": _sig_time,
                    "price": float(pinfo.get("signal_low", 0) or 0),
                    "strength": float(pinfo.get("proba", 0) or 0),
                    "signal_status": "pending_confirm",
                    "reason": "ETF底部候选，待次日收盘确认",
                }
                existing = await repo.get(sig_id)
                if not existing:
                    # 幂等：同代码已存在 pending_confirm 候选 → 复用其行
                    _dups = await repo.get_by_stock(ts_code=code, strategy_id=sid, limit=20)
                    for _d in _dups:
                        if getattr(_d, "signal_status", None) == "pending_confirm":
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
            logger.warning(f"ETF候选持久化失败: {code}: {e}")

    async def _restore_candidates_from_db(self, db=None) -> None:
        """从 signals 表读回 pending_confirm 候选，重建 _p4_buffer（重启恢复）。"""
        sf = getattr(self, "_db_session_factory", None)
        if not sf:
            return
        sid = getattr(getattr(self, "context", None), "strategy_id", "") or self.name
        if not sid:
            return
        try:
            from sqlalchemy import select
            from shared.database.models.business_models import Signal
            async with sf() as db_session:
                rows = (await db_session.execute(select(Signal).where(
                    Signal.strategy_id == sid,
                    Signal.signal_status == "pending_confirm",
                ))).scalars().all()
                restored = 0
                for r in rows:
                    _sd = r.signal_time.strftime("%Y-%m-%d") if r.signal_time else ""
                    # 过期守卫：距候选日超 5 天 → expired
                    if _sd:
                        try:
                            if (date.today() - date.fromisoformat(_sd)).days > 5:
                                await self._mark_candidate_status(r.id, "expired", "过期未确认")
                                continue
                        except (ValueError, TypeError):
                            pass
                    # 2026-08-19 修复：牛市空仓让位——恢复候选时若当前大盘 regime=2（牛市），
                    # 历史滞留候选直接标记 expired，不再恢复进 _p4_buffer。
                    # 此前 L656 牛市门控只拦截"确认"不清理"候选"，导致 8-16 产生的候选
                    # 在牛市永久滞留 pending_confirm（前端一直显示，每次重启重复恢复）。
                    if self.use_market_gate and self._market_regime(date.today()) == 2:
                        await self._mark_candidate_status(r.id, "expired", "牛市空仓让位，候选放弃")
                        if getattr(self, "verbose_logging", False):
                            logger.info(f"[{self.name}] 牛市恢复候选放弃: {r.ts_code}（让位进攻）")
                        continue
                    _proba = float(r.strength or self.parameters["threshold"])
                    self._p4_buffer[r.ts_code] = {
                        "proba": _proba,
                        "signal_low": float(r.price or 0),
                        "weight": self._calc_weight(self._get_regime(r.ts_code, date.today())),
                        "signal_id": r.id,
                        "signal_date": _sd,
                    }
                    restored += 1
                if restored:
                    logger.info(f"[{self.name}] 重启恢复候选 {restored} 只 (pending_confirm)")
        except Exception as e:
            logger.warning(f"ETF候选恢复失败: {e}")

    async def load_live_state(self, db, strategy_id=None, **kwargs):
        """覆写：注入实盘状态后，恢复 pending_confirm 候选 + 重建持仓状态（重启不丢）。"""
        await super().load_live_state(db, strategy_id=strategy_id, **kwargs)
        try:
            await self._restore_candidates_from_db()
        except Exception as e:
            logger.warning(f"[{self.name}] 候选恢复失败: {e}")
        # P1-1 修复: 从框架注入的实盘持仓重建 _position_entry（持仓退出管理入口），
        # 否则重启后已持仓标的的止损/时间/移动止盈全部静默失效，且可能被再次开仓。
        self._rebuild_position_state()

    def _rebuild_position_state(self) -> None:
        """从 _active_positions（DB 真相源）重建 _position_entry。

        - _position_entry: 持仓退出管理唯一入口（on_bar in_position 分支）。
          重启后必须重建，否则止损/时间/移动止盈全部失效 + 重复开仓。
        - _track_high: 不在此处理——框架 _restore_positions_from_db 先设为成本价，
          再由 _recover_running_strategies 用 state_snapshot 覆盖为真实历史高点，
          此处不覆盖以避免丢失峰值。
        - 不在 DB 持仓中的 _position_entry 条目（未成交的幽灵持仓）在此清除。
        """
        held = {
            c for c, lp in self._active_positions.items()
            if lp.quantity > 0 and lp.cost_price > 0
        }
        ghost = sorted(c for c in self._position_entry if c not in held)
        self._position_entry.clear()
        for code in held:
            lp = self._active_positions[code]
            # 无持仓开仓日：从今天起算持有期（保守，避免重启即触发时间止损）
            self._position_entry[code] = (date.today(), lp.cost_price)
        if ghost or held:
            logger.info(
                "[%s] 实盘持仓状态重建: 恢复 %d 只, 清理幽灵 %d 只 (ghost=%s)",
                self.name, len(held), len(ghost), ghost[:5],
            )

    def on_bar(self, bar: BarData) -> List[TradingSignal]:
        # P4 确认缓冲区延迟恢复：实盘候选已由 load_live_state 从 DB 恢复（含 signal_id）；
        # 仅在 _p4_buffer 为空（回测/恢复失败）时历史重建兜底
        if not getattr(self, '_confirm_restored', False):
            self._confirm_restored = True
            if not self._p4_buffer:
                self._restore_confirm_buffer()

        signals: List[TradingSignal] = []
        ts_code = bar.ts_code
        # v6.10: 非 ETF 标的快速跳过——避免在组合回测中处理 5000+ 无关 bar
        _etf_pool_set = getattr(self, '_etf_pool_set', None)
        if _etf_pool_set is None:
            _etf_pool_set = set(self.parameters.get('etf_pool') or [])
            self._etf_pool_set = _etf_pool_set
        if ts_code not in _etf_pool_set:
            return signals
        if not getattr(self, '_trace_once', False):
            self._trace_once = True
            logger.info('[TRACE] on_bar首次执行: ts=%s p4buf=%d pos=%d model=%s pool=%d',
                        ts_code, len(self._p4_buffer), len(self._position_entry),
                        'yes' if self.model else 'no', len(self.parameters.get('etf_pool') or []))
        if ts_code not in self._data_cache:
            self._data_cache[ts_code] = []
        self._data_cache[ts_code].append(bar)
        if len(self._data_cache[ts_code]) > 600:
            self._data_cache[ts_code] = self._data_cache[ts_code][-600:]

        d = self._diag
        d["bars_processed"] += 1
        _pool = self.parameters.get('etf_pool') or []
        if ts_code in _pool and d['bars_processed'] == 1:
            logger.info('[BAR/START] %s: 首次on_bar, p4_buffer=%d, pos=%d, pool=%d',
                        ts_code, len(self._p4_buffer), len(self._position_entry), len(_pool))
        if len(self._data_cache[ts_code]) < self.parameters["min_warmup_bars"]:
            d["warmup_skip"] += 1; return signals
        if self.model is None:
            d["no_model"] += 1; return signals
        if ts_code in self._cooling:
            d["cooling"] += 1
            self._cooling[ts_code] -= 1
            if self._cooling[ts_code] <= 0: del self._cooling[ts_code]
            self._p4_buffer.pop(ts_code, None)
            return signals
        if ts_code in self._position_entry:
            d["in_position"] += 1
            # A方案: 牛市强制清仓——已持仓在牛市确认后立即退出，资金释放给进攻策略。
            # （此前 gate 只拦截新入场，已持仓照常走到止盈，导致牛市里占资金 5-6 个月）
            if self.use_market_gate and self._market_regime(bar.trade_date) == 2:
                es = self._make_exit(ts_code, bar, "牛市清仓让位进攻", SignalType.EXIT)
                if es:
                    signals.append(es)
                    logger.info("[%s] %s 牛市清仓（让位进攻）", self.name, ts_code)
                return signals
            es = self._check_exit(ts_code, bar)
            if es: signals.append(es)
            return signals
        # P1-1 兜底: 框架注入的实盘持仓同样视为已持仓，阻止重复开仓
        #（正常情况下 _position_entry 已由 _rebuild_position_state 重建，此为防御）
        _held_lp = self._active_positions.get(ts_code)
        if _held_lp is not None and _held_lp.quantity > 0:
            return signals

        regime = self._get_regime(ts_code, bar.trade_date)
        # 大盘牛市：防守空仓让位（已有持仓照常退出，组合层资金给进攻策略）
        if self.use_market_gate and self._market_regime(bar.trade_date) == 2:
            self._p4_buffer.pop(ts_code, None)
            return signals
        rmax_pos = self.parameters.get("regime_max_positions", {}).get(regime, 5)
        if len(self._position_entry) >= rmax_pos:
            d["max_positions"] += 1
            self._p4_buffer.pop(ts_code, None)
            return signals

        # P4 确认：昨日通过阈值、今日确认收盘价
        if self.parameters.get("confirm_enabled", False) and ts_code in self._p4_buffer:
            d["p4_pending"] += 1
            pinfo = self._p4_buffer.pop(ts_code)
            if self.parameters.get("trace", False):
                logger.info('[P4/入] %s close=%.4f low=%.4f proba=%.3f → 检查确认',
                            ts_code, bar.close, pinfo['signal_low'], pinfo['proba'])
            # P2-2: 确认时用当前 regime 重算 weight（原用信号日旧 weight，regime 变化后规模失真）
            weight = self._calc_weight(regime)
            if weight <= 0:
                d["weight_zero"] += 1
                logger.warning("[%s] %s P4确认时 weight<=0（regime 已变?），丢弃", self.name, ts_code)
                return signals
            if bar.close > pinfo["signal_low"]:
                if self.parameters.get("vol_confirm_enabled", True):
                    vr = self._get_factor_value(ts_code, bar.trade_date, "volume_ma20_ratio")
                    if vr is not None and vr < 1.0:
                        # 2026-08 修复：量能确认拦截此前静默无痕，现计数+日志便于诊断
                        d["vol_confirm"] += 1
                        logger.info("[%s] %s 量能确认拦截 vol_ratio=%.2f<1.0", self.name, ts_code, vr)
                        return signals
                d["p4_confirmed"] += 1
                # v6.x: 候选转正（promoted）+ 买入信号关联 parent_id（与进攻实盘候选一致）
                _cand_sid = pinfo.get("signal_id")
                # P1 修复: 重放(silent replay)时不转正——重放仅为追平状态，非真实确认
                if _cand_sid and not getattr(self, "_replaying", False):
                    self._fire_db(self._mark_candidate_status(_cand_sid, "promoted", "收盘确认转正"))
                s = self._make_entry(ts_code, bar, pinfo["proba"], weight, regime, parent_id=_cand_sid)
                if s:
                    signals.append(s)
                    logger.info('[P4/SIG] %s ✓确认入场 proba=%.3f wt=%.3f 信号id=%s',
                                ts_code, pinfo['proba'], weight, s.id)
                else:
                    d["weight_zero"] += 1
                    logger.warning("[%s] %s P4确认但入场被拦截", self.name, ts_code)
            return signals

        # 新预测
        try:
            d["in_pool"] += 1
            proba = self._predict(ts_code, bar.trade_date)
            if proba is None:
                d["proba_none"] += 1; return signals
            base_t = self.parameters["threshold"]
            radj = self.parameters.get("regime_threshold_adj", {}).get(regime, 0.0)
            day_t = base_t + radj
            d["top_probas"].append((ts_code, round(proba, 4), regime, round(day_t, 3)))
            if proba < day_t:
                d["proba_below"] += 1; return signals
            if self.parameters.get("vol_filter_enabled", False):
                ar = self._get_factor_value(ts_code, bar.trade_date, "atr_ratio_20")
                if ar is None or ar < self.parameters.get("vol_filter_atr_min", 0.015):
                    d["vol_filter"] += 1; return signals
            weight = self._calc_weight(regime)
            if weight <= 0.0:
                d["weight_zero"] += 1; return signals
            if self.parameters.get("confirm_enabled", False):
                # 2026-08-20：候选入池上限 = regime_max_positions（2 只）。
                # 此前候选无上限，多只累积导致信号列表候选过多。达到上限不再入新候选。
                rmax = self.parameters.get("regime_max_positions", {}).get(regime, 2)
                if len(self._p4_buffer) >= rmax:
                    d["max_positions"] += 1
                    return signals
                d["p4_buffered"] += 1
                # v6.x: 候选 signal_id + 落库（与进攻实盘候选一致），跨重启保留
                _sid = str(uuid.uuid4())
                self._p4_buffer[ts_code] = {
                    "proba": proba, "signal_low": bar.low, "weight": weight, "signal_id": _sid}
                # P1 修复: 重放(silent replay)时不落库候选——重放仅为追平状态，非真实当日
                if not getattr(self, "_replaying", False):
                    self._fire_db(self._persist_candidate(ts_code, self._p4_buffer[ts_code]))
                if self.parameters.get("trace", False):
                    logger.info('[P4/BUF] %s proba=%.4f > thr=%.3f rc=%d → 缓冲待确认(已落库)',
                                ts_code, proba, day_t, regime)
                return signals
            s = self._make_entry(ts_code, bar, proba, weight, regime)
            if s:
                d["entry_generated"] += 1
                signals.append(s)
            else:
                d["weight_zero"] += 1
                logger.warning("[%s] %s 新预测入场被拦截 (weight=%.3f)", self.name, ts_code, weight)
        except Exception as e:
            logger.error("[%s] on_bar error: %s", self.name, str(e)[:100])
        return signals


    def _make_entry(self, ts_code, bar, proba, weight, regime, parent_id=None):
        """生成买入信号。仅当信号有效（weight>0 且金额足够一手）时写入持仓状态。

        P1-2 修复：原实现在计算数量前无条件写入 _position_entry/_track_high，
        当 weight<=0（如牛市恢复的候选）时会留下幽灵持仓——阻塞后续入场、
        计入 max_positions、凭空触发平仓。现改为先校验再写状态，无效返回 None。
        """
        rn = {0: "熊", 1: "震", 2: "牛"}
        # 买入数量 = 可用资金 × 权重 / 价格，按 100 股/手向下取整（至少 1 手）
        capital = float(getattr(self.context, "available_capital", 0) or 0) if self.context else 0.0
        amount = max(capital * float(weight), 0.0)
        price = float(bar.close) if bar.close else 0.0
        quantity = 0
        if price > 0 and amount > 0:
            lot = 100  # A股/ETF 一手 = 100 份
            quantity = max(int(amount / price / lot) * lot, lot)
        # P1-2: 无效信号（权重/金额/数量为 0）不写持仓状态、不产生信号
        if float(weight) <= 0 or amount <= 0 or quantity <= 0:
            logger.warning(
                "[%s] %s 无效入场被拦截: weight=%.2f amount=%.0f qty=%d",
                self.name, ts_code, float(weight), amount, quantity,
            )
            return None
        # 仅有效信号写入入场状态（信号日收盘价；实际成交价由成交回调/对账对齐）
        self._position_entry[ts_code] = (bar.trade_date, bar.close)
        self._track_high[ts_code] = bar.close
        sig = TradingSignal(
            id=str(uuid.uuid4()), strategy_id=self.name, strategy_name=self.name,
            ts_code=ts_code, signal_type=SignalType.ENTRY,
            direction=SignalDirection.LONG, price=bar.close,
            confidence=float(proba),
            reason=f"底{proba:.1%} 仓{weight:.0%} [{rn.get(regime,'?')}]",
            weight=weight,
            quantity=quantity,
            amount=amount,
            timestamp=beijing_now())
        if parent_id:
            sig.parent_id = parent_id  # v6.x: 候选→买入信号 链路关联
        return sig

    def _check_exit(self, ts_code: str, bar: BarData) -> Optional[TradingSignal]:
        entry_date, entry_price = self._position_entry.get(ts_code, (None, None))
        if entry_price is None: return None
        # 修复 2026-08（C8）：entry=0/NaN 防护——此前除零抛异常或 NaN 使持仓永不退出
        if entry_price != entry_price or entry_price <= 0 or bar.close != bar.close or bar.close <= 0:
            return None
        pnl = bar.close / entry_price - 1
        regime = self._get_regime(ts_code, bar.trade_date)
        if ts_code not in self._track_high:
            self._track_high[ts_code] = bar.close
        else:
            self._track_high[ts_code] = max(self._track_high[ts_code], bar.close)
        high = self._track_high[ts_code]
        dd = (high - bar.close) / high if high > 0 else 0
        base_stop = self.parameters.get("regime_stop_loss", {}).get(regime, -0.07)
        ar = self._get_factor_value(ts_code, bar.trade_date, "atr_ratio_20")
        # P2-3(cap): min 修正方向（高波动放宽/低波动不收紧）+ 1.5×base 上限，
        # 避免无上限放宽放大单笔亏损（实测 2022 熊市 -8%→-12.5% 止损推高 MDD）
        dyn_stop = max(min(base_stop, -2.5 * ar), base_stop * 1.5) if ar and ar > 0 else base_stop
        if pnl < dyn_stop:
            rn = {0: "熊", 1: "震", 2: "牛"}
            return self._make_exit(ts_code, bar,
                f"止损{pnl:.1%} [ATR={ar:.1%} {rn.get(regime,'?')}]",
                SignalType.STOP_LOSS)
        max_d = self.parameters.get("regime_max_hold", {}).get(regime, 20)
        hd = self._compute_hold_days(entry_date, bar.trade_date)
        if hd >= max_d and pnl <= 0.02:
            return self._make_exit(ts_code, bar,
                f"到期{hd}d pnl={pnl:.1%}", SignalType.EXIT)
        ta = self.parameters.get("regime_trail_act", {}).get(regime, 0.05)
        td = self.parameters.get("regime_trail_dist", {}).get(regime, 0.08)
        if (high - entry_price) / entry_price >= ta and dd >= td:
            return self._make_exit(ts_code, bar,
                f"止盈{high/entry_price-1:.1%}→回落{dd:.1%}",
                SignalType.TAKE_PROFIT)
        return None

    def _compute_hold_days(self, entry_date, current_date) -> int:
        """持仓天数——日历口径（P2-5 隔离测试：暂回退交易日逻辑）"""
        try:
            if hasattr(current_date, 'date'): current_date = current_date.date()
            if hasattr(entry_date, 'date'): entry_date = entry_date.date()
            if isinstance(entry_date, str): entry_date = date.fromisoformat(entry_date[:10])
            if isinstance(current_date, str): current_date = date.fromisoformat(current_date[:10])
            return max((current_date - entry_date).days, 0)
        except Exception:
            return 0

    def _make_exit(self, ts_code, bar, reason, signal_type) -> TradingSignal:
        self._position_entry.pop(ts_code, None)
        self._track_high.pop(ts_code, None)
        self._cooling[ts_code] = self.parameters["cooling_days"]
        return TradingSignal(
            id=str(uuid.uuid4()), strategy_id=self.name, strategy_name=self.name,
            ts_code=ts_code, signal_type=signal_type,
            direction=SignalDirection.CLOSE_LONG, price=bar.close,
            confidence=1.0, reason=reason, weight=0.0,
            timestamp=beijing_now())

    def get_parameters(self) -> Dict[str, Any]:
        return dict(self.parameters)
