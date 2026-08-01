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
        "etf_pool": [
            "510050.SH","510300.SH","510500.SH","159919.SZ","510880.SH",
            "512880.SH","512660.SH","512800.SH","512100.SH",
            "159915.SZ","159949.SZ","518880.SH","513100.SH","513050.SH",
            "511010.SH","511260.SH","510310.SH","159865.SZ","159825.SZ",
            "159781.SZ","512170.SH","159806.SZ","516510.SH",
            "159840.SZ","512400.SH",
        ],
        "vol_filter_enabled": True,
        "vol_filter_atr_min": 0.015,
        "confirm_enabled": True,
        # v4: 分市场参数 (0=BEAR, 1=RANGE, 2=BULL)
        "regime_threshold_adj": {0: -0.02, 1: 0.04, 2: -0.06},
        "regime_max_positions":  {0: 5, 1: 3, 2: 4},
        "regime_stop_loss":     {0: -0.08, 1: -0.06, 2: -0.07},
        "regime_trail_act":     {0: 0.06, 1: 0.04, 2: 0.05},
        "regime_trail_dist":    {0: 0.10, 1: 0.06, 2: 0.08},
        "regime_max_hold":      {0: 25, 1: 14, 2: 20},
        # P3: 量能确认
        "vol_confirm_enabled": True,
        # DB
        "db_host": "localhost", "db_port": 5432,
        "db_user": "postgres", "db_password": "123456",
        "db_name": "quant_signals_dev",
    }

    def __init__(self, name, strategy_type=None, parameters=None):
        defaults = dict(self.DEFAULT_PARAMS)
        if parameters:
            defaults.update(parameters)
        super().__init__(name=name, strategy_type=strategy_type or StrategyType.ML, parameters=defaults)
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

    def _reset_diag(self) -> dict:
        return {
            "bars_processed": 0, "in_pool": 0, "warmup_skip": 0,
            "no_model": 0, "cooling": 0, "in_position": 0,
            "max_positions": 0, "p4_pending": 0, "p4_confirmed": 0,
            "proba_none": 0, "proba_below": 0, "vol_filter": 0,
            "weight_zero": 0, "p4_buffered": 0, "entry_generated": 0,
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
                weight = self._calc_weight(proba, day_t)
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
            if nmask.any(): features[0, nmask] = 0.0
            if self.scaler_mu and self.scaler_sigma:
                features[0] = (features[0] - np.array(self.scaler_mu)) / (np.array(self.scaler_sigma) + 1e-8)
            if hasattr(self.model, 'predict_proba'):
                return float(self.model.predict_proba(features)[0, 1])
            return float(self.model.predict(features)[0])
        except Exception as e:
            logger.error("[%s] 预测失败: %s", self.name, str(e)[:200])
            return None

    def _calc_weight(self, proba: float, threshold: float) -> float:
        """v5: 线性仓位映射（替代凯利——实际盈亏分布非二元，凯利低估赔率）"""
        mp = self.parameters.get("max_single_position", 0.40)
        return max(0.01, (proba - threshold) / (1.0 - threshold)) * mp

    def on_bar(self, bar: BarData) -> List[TradingSignal]:
        # P4 确认缓冲区延迟恢复
        if not getattr(self, '_confirm_restored', False):
            self._confirm_restored = True
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
            es = self._check_exit(ts_code, bar)
            if es: signals.append(es)
            return signals

        regime = self._get_regime(ts_code, bar.trade_date)
        rmax_pos = self.parameters.get("regime_max_positions", {}).get(regime, 5)
        if len(self._position_entry) >= rmax_pos:
            d["max_positions"] += 1
            self._p4_buffer.pop(ts_code, None)
            return signals

        # P4 确认：昨日通过阈值、今日确认收盘价
        if self.parameters.get("confirm_enabled", False) and ts_code in self._p4_buffer:
            d["p4_pending"] += 1
            pinfo = self._p4_buffer.pop(ts_code)
            logger.info('[P4/入] %s close=%.4f low=%.4f proba=%.3f → 检查确认',
                        ts_code, bar.close, pinfo['signal_low'], pinfo['proba'])
            if bar.close > pinfo["signal_low"]:
                if self.parameters.get("vol_confirm_enabled", True):
                    vr = self._get_factor_value(ts_code, bar.trade_date, "volume_ma20_ratio")
                    if vr is not None and vr < 1.0:
                        return signals
                d["p4_confirmed"] += 1
                s = self._make_entry(ts_code, bar, pinfo["proba"], pinfo["weight"], regime)
                signals.append(s)
                logger.info('[P4/SIG] %s ✓确认入场 proba=%.3f wt=%.3f 信号id=%s',
                            ts_code, pinfo['proba'], pinfo['weight'], s.id)
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
            weight = self._calc_weight(proba, day_t)
            if weight <= 0.0:
                d["weight_zero"] += 1; return signals
            if self.parameters.get("confirm_enabled", False):
                d["p4_buffered"] += 1
                self._p4_buffer[ts_code] = {
                    "proba": proba, "signal_low": bar.low, "weight": weight}
                logger.info('[P4/BUF] %s proba=%.4f > thr=%.3f rc=%d → 缓冲待确认',
                            ts_code, proba, day_t, regime)
                return signals
            d["entry_generated"] += 1
            s = self._make_entry(ts_code, bar, proba, weight, regime)
            signals.append(s)
        except Exception as e:
            logger.error("[%s] on_bar error: %s", self.name, str(e)[:100])
        return signals

    def _on_bar_trace(self, ts_code: str, signals: list) -> list:
        if signals:
            logger.info('[BAR/OUT] %s → %d 个信号', ts_code, len(signals))
        return signals

    def _make_entry(self, ts_code, bar, proba, weight, regime):
        self._position_entry[ts_code] = (bar.trade_date, bar.close)
        self._track_high[ts_code] = bar.close
        rn = {0: "熊", 1: "震", 2: "牛"}
        return TradingSignal(
            id=str(uuid.uuid4()), strategy_id=self.name, strategy_name=self.name,
            ts_code=ts_code, signal_type=SignalType.ENTRY,
            direction=SignalDirection.LONG, price=bar.close,
            confidence=float(proba),
            reason=f"底{proba:.1%} 仓{weight:.0%} [{rn.get(regime,'?')}]",
            weight=weight,
            timestamp=bar.trade_time if bar.trade_time else datetime.now())

    def _check_exit(self, ts_code: str, bar: BarData) -> Optional[TradingSignal]:
        entry_date, entry_price = self._position_entry.get(ts_code, (None, None))
        if entry_price is None: return None
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
        dyn_stop = max(base_stop, -2.5 * ar) if ar and ar > 0 else base_stop
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

    @staticmethod
    def _compute_hold_days(entry_date, current_date) -> int:
        try:
            if hasattr(current_date, 'date'): current_date = current_date.date()
            if hasattr(entry_date, 'date'): entry_date = entry_date.date()
            if isinstance(entry_date, str): entry_date = date.fromisoformat(entry_date[:10])
            if isinstance(current_date, str): current_date = date.fromisoformat(current_date[:10])
            return (current_date - entry_date).days
        except Exception: return 0

    def _make_exit(self, ts_code, bar, reason, signal_type) -> TradingSignal:
        self._position_entry.pop(ts_code, None)
        self._track_high.pop(ts_code, None)
        self._cooling[ts_code] = self.parameters["cooling_days"]
        return TradingSignal(
            id=str(uuid.uuid4()), strategy_id=self.name, strategy_name=self.name,
            ts_code=ts_code, signal_type=signal_type,
            direction=SignalDirection.CLOSE_LONG, price=bar.close,
            confidence=1.0, reason=reason, weight=0.0,
            timestamp=bar.trade_time if bar.trade_time else datetime.now())

    def get_parameters(self) -> Dict[str, Any]:
        return dict(self.parameters)
