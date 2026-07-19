# -*- coding: utf-8 -*-
"""
LightGBM ETF 底部抄底策略
=========================
基于 LightGBM 离线训练的 ETF 底部识别模型，从 factor_data 加载特征，
在 on_bar 中实时预测底部概率，生成交易信号。

策略类型: StrategyType.ML
数据需求: etf_daily + factor_data (预计算65因子) + market_state_daily
预热需求: at least 60 bars per ETF (rolling indicators)
"""

import logging
import uuid
from datetime import date, datetime
from pathlib import Path
from typing import Dict, List, Optional, Any

import joblib
import psycopg2
import numpy as np
from sqlalchemy.dialects.postgresql import asyncpg

from core.engines.types.entities import BarData
from modules.strategy.constants import StrategyType, SignalDirection, SignalType
from modules.strategy.models import TradingSignal
from modules.strategy.strategies.base.base_strategy import BaseStrategy

logger = logging.getLogger(__name__)


class LightGBMBottomStrategy(BaseStrategy):
    """
    LightGBM ETF 底部抄底策略

    离线训练好 LightGBM 模型 → on_init 加载 → on_bar 预测 → 生成信号。

    入场条件:
      1. model.predict_proba(features) ≥ threshold
      2. 不在冷却期
      3. 未持有该 ETF
      4. 持仓数 < max_positions

    出场条件:
      1. 硬止损: pnl < stop_loss
      2. 止盈: pnl ≥ take_profit
      3. 时间止损: 持有 > max_hold_days
    """

    strategy_type = StrategyType.ML

    DEFAULT_PARAMS = {
        "model_path": "",              # 训练好的模型文件路径
        "threshold": 0.30,             # 概率阈值（激进：宁错勿漏）
        "max_single_position": 0.35,   # 单 ETF 最大仓位（集中火力）
        "stop_loss": -0.08,            # 硬止损线 -8%（给波动空间）
        "trail_activate": 0.05,        # trailing stop 启动阈值：浮盈>5%后启动
        "trail_distance": 0.03,        # trailing stop 回撤距离：从高点回落3%离场
        "max_hold_days": 0,            # 最大持有天数（0=不限制，让趋势走完）
        "cooling_days": 2,             # 出场后冷却天数（激进：快速再入场）
        "min_warmup_bars": 60,         # 最少需要的历史 bar 数
        "feature_list": [],            # 特征列表（空=从模型 artifact 读取）
        "db_host": "localhost",
        "db_port": 5432,
        "db_user": "postgres",
        "db_password": "123456",
        "db_name": "quant_signals_dev",
    }

    def __init__(self, name, strategy_type=None, parameters=None):
        defaults = dict(self.DEFAULT_PARAMS)
        if parameters:
            defaults.update(parameters)
        super().__init__(name=name, strategy_type=strategy_type or StrategyType.ML, parameters=defaults)

        # 模型相关
        self.model = None
        self.feature_names: List[str] = []
        self.scaler_mu: List[float] = []
        self.scaler_sigma: List[float] = []

        # 持仓追踪
        self._data_cache: Dict[str, List[BarData]] = {}
        self._position_entry: Dict[str, tuple] = {}  # ts_code → (entry_date, entry_price)
        self._track_high: Dict[str, float] = {}       # ts_code → 持仓期间最高价 (trailing stop用)
        self._cooling: Dict[str, int] = {}            # ts_code → remaining_days

        # DB 连接
        self._db_pool = None

    # ── Lifecycle ─────────────────────────────────────────

    def on_init(self) -> None:
        """加载模型 artifact"""
        model_path = self.parameters["model_path"]
        if not model_path:
            logger.warning("[%s] model_path 为空，策略无法预测", self.name)
            return

        artifact = joblib.load(model_path)
        self.model = artifact["model"]
        self.feature_names = artifact.get("feature_names", [])
        scaler = artifact.get("scaler_params", {})
        self.scaler_mu = scaler.get("mu", [])
        self.scaler_sigma = scaler.get("sigma", [])
        # Use saved threshold if not overridden
        saved_t = artifact.get("threshold")
        if saved_t is not None and self.parameters["threshold"] == self.DEFAULT_PARAMS["threshold"]:
            self.parameters["threshold"] = float(saved_t)

        logger.info(
            "[%s] 模型已加载: %s, features=%d, threshold=%.2f",
            self.name, Path(model_path).name,
            len(self.feature_names), self.parameters["threshold"],
        )

        # Initialize DB connection pool for factor queries (v3.4)
        import psycopg2.pool
                # 预加载所有 ETF 的因子数据到内存缓存 (v3.5)
        self._factor_cache = {}  # {ts_code: {trade_date_str: {factor_code: value}}}
        try:
            conn = self._db_pool.getconn()
            cur = conn.cursor()
            for etf in self.parameters.get('etf_pool', []) or []:
                cur.execute(
                    "SELECT factor_code, trade_date::text, factor_value FROM factor_data WHERE ts_code=%s AND factor_code = ANY(%s) AND trade_date >= '2019-01-01'",
                    (etf, self.feature_names)
                )
                cache = {}
                for row in cur.fetchall():
                    fc, td, fv = row[0], row[1][:10], row[2]
                    if td not in cache:
                        cache[td] = {}
                    cache[td][fc] = float(fv) if fv is not None else None
                self._factor_cache[etf] = cache
            cur.close()
            # factor_cache used — no DB call per bar
            logger.info('[%s] 因子缓存加载完成: %d ETFs', self.name, len(self._factor_cache))
        except Exception as e:
            logger.warning('[%s] 因子缓存加载失败, 回退到实时查询: %s', self.name, str(e)[:100])

            1, 4,
            host=self.parameters.get('db_host','localhost'),
            port=self.parameters.get('db_port',5432),
            user=self.parameters.get('db_user','postgres'),
            password=self.parameters.get('db_password','123456'),
            database=self.parameters.get('db_name','quant_signals_dev'),


    async def _ensure_db(self):
        """懒加载 DB 连接池"""
        if self._db_pool is None:
            self._db_pool = await asyncpg.create_pool(
                host=self.parameters["db_host"],
                port=self.parameters["db_port"],
                user=self.parameters["db_user"],
                password=self.parameters["db_password"],
                database=self.parameters["db_name"],
                min_size=1, max_size=4,
            )

    # ── Bar Processing ──────────────────────────────────

    def on_bar(self, bar: BarData) -> List[TradingSignal]:
        """处理每个 bar，生成交易信号"""
        signals = []
        ts_code = bar.ts_code

        # 1. 缓存 bar
        if ts_code not in self._data_cache:
            self._data_cache[ts_code] = []
        self._data_cache[ts_code].append(bar)

        # 控制缓存大小
        if len(self._data_cache[ts_code]) > 600:
            self._data_cache[ts_code] = self._data_cache[ts_code][-600:]

        # 2. 预热检查
        min_bars = self.parameters["min_warmup_bars"]
        if len(self._data_cache[ts_code]) < min_bars:
            return signals

        if self.model is None:
            return signals

        # 3. 更新冷却期
        if ts_code in self._cooling:
            self._cooling[ts_code] -= 1
            if self._cooling[ts_code] <= 0:
                del self._cooling[ts_code]
            return signals

        # 4. 检查已有持仓 → 出场检查
        if ts_code in self._position_entry:
            exit_signal = self._check_exit(ts_code, bar)
            if exit_signal:
                signals.append(exit_signal)
            return signals

        # 5. 检查入场
        try:
            proba = self._predict(ts_code, bar.trade_date)
            if proba is None:
                return signals

            threshold = self.parameters["threshold"]
            if proba < threshold:
                return signals

            # 6. 仓位映射
            max_pos = self.parameters["max_single_position"]
            weight = max(0.01, (proba - threshold) / (1.0 - threshold)) * max_pos

            signal = TradingSignal(
                id=str(uuid.uuid4()),
                strategy_id=self.name,
                strategy_name=self.name,
                ts_code=ts_code,
                signal_type=SignalType.ENTRY,
                direction=SignalDirection.LONG,
                price=bar.close,
                confidence=float(proba),
                reason=f"底部概率 {proba:.1%}, 权重 {weight:.0%}",
                weight=weight,
                timestamp=bar.trade_time if bar.trade_time else datetime.now(),
            )
            self._position_entry[ts_code] = (bar.trade_date, bar.close)
            self._track_high[ts_code] = bar.close  # 初始化最高价
            signals.append(signal)

        except Exception as e:
            logger.error("[%s] on_bar 异常: %s", self.name, str(e)[:100])

        return signals

    # ── Prediction ──────────────────────────────────────

    # ── Prediction ──────────────────────────────────────

    def _predict(self, ts_code: str, trade_date_val) -> Optional[float]:
        """从 factor_data 表读取预计算特征 → 模型预测 (v3.4)"""
        try:
            td_str = None
            if hasattr(trade_date_val, 'strftime'):
                td_str = trade_date_val.strftime('%Y-%m-%d')
            elif hasattr(trade_date_val, 'isoformat'):
                td_str = trade_date_val.isoformat()[:10]
            else:
                td_str = str(trade_date_val)[:10]

            # 从内存缓存读取特征 (v3.5)
            cache = self._factor_cache.get(ts_code, {})
            # 找最近交易日 <= td_str
            all_dates = sorted(cache.keys(), reverse=True)
            nearest_date = None
            for d in all_dates:
                if d <= td_str:
                    nearest_date = d
                    break
            if nearest_date is None:
                return None
            row = cache[nearest_date]
            feature_vals = [row.get(fn) if row.get(fn) is not None else np.nan for fn in self.feature_names]
            # factor_cache used — no DB call per bar

            features = np.array(feature_vals, dtype=np.float64).reshape(1, -1)

            # 缺失值填充
            nan_mask = np.isnan(features[0])
            if nan_mask.any():
                features[0, nan_mask] = 0.0

            # 标准化
            if self.scaler_mu and self.scaler_sigma:
                features[0] = (features[0] - np.array(self.scaler_mu)) / (
                    np.array(self.scaler_sigma) + 1e-8
                )

            proba = self.model.predict_proba(features)[0, 1]
            return float(proba)

        except Exception as e:
            logger.error("[%s] 预测失败: %s", self.name, str(e)[:200])
            return None


    # ── Exit Logic ──────────────────────────────────────

    def _check_exit(self, ts_code: str, bar: BarData) -> Optional[TradingSignal]:
        """检查出场条件 — trailing stop 版"""
        entry_date, entry_price = self._position_entry.get(ts_code, (None, None))
        if entry_price is None:
            return None

        pnl = bar.close / entry_price - 1

        # 更新持仓最高价
        if ts_code not in self._track_high:
            self._track_high[ts_code] = bar.close
        else:
            self._track_high[ts_code] = max(self._track_high[ts_code], bar.close)
        high = self._track_high[ts_code]
        drawdown_from_high = (high - bar.close) / high if high > 0 else 0

        # ① 硬止损 -8%
        if pnl < self.parameters["stop_loss"]:
            return self._make_exit(ts_code, bar, f"硬止损 {pnl:.1%}", SignalType.STOP_LOSS)

        # ② 时间止损（0=关闭）
        max_days = self.parameters.get("max_hold_days", 0)
        if max_days > 0:
            hold_days = (bar.trade_date - entry_date).days if hasattr(bar.trade_date, "days") else 0
            if hold_days >= max_days:
                return self._make_exit(ts_code, bar, f"时间止损 {hold_days}天", SignalType.EXIT)

        # ③ Trailing stop: 浮盈>5%后启动，从高点回落3%离场
        trail_activate = self.parameters.get("trail_activate", 0.05)
        trail_distance = self.parameters.get("trail_distance", 0.03)
        if (high - entry_price) / entry_price >= trail_activate and drawdown_from_high >= trail_distance:
            return self._make_exit(
                ts_code, bar,
                f"Trailing止盈: 浮盈{high/entry_price-1:.1%}→回落{drawdown_from_high:.1%}",
                SignalType.TAKE_PROFIT,
            )

        return None

    def _make_exit(self, ts_code, bar, reason, signal_type) -> TradingSignal:
        """生成出场信号并设置冷却期"""
        self._position_entry.pop(ts_code, None)
        self._track_high.pop(ts_code, None)
        self._cooling[ts_code] = self.parameters["cooling_days"]

        return TradingSignal(
            id=str(uuid.uuid4()),
            strategy_id=self.name,
            strategy_name=self.name,
            ts_code=ts_code,
            signal_type=signal_type,
            direction=SignalDirection.CLOSE_LONG,
            price=bar.close,
            confidence=1.0,
            reason=reason,
            weight=0.0,  # 出场信号无仓位
            timestamp=bar.trade_time if bar.trade_time else datetime.now(),
        )

    def get_parameters(self) -> Dict[str, Any]:
        return dict(self.parameters)
