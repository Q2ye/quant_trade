# -*- coding: utf-8 -*-
"""
行业多因子评分服务

对 31 个申万一级行业进行多维度打分，输出排序结果。

因子体系：
  - 趋势动量 (45%)：多窗口动量 + 加速度 + 相对强弱
  - 资金量价 (30%)：量比 + 价量配合 + 换手加速度
  - 估值空间 (25%)：PE/PB 分位 + 估值扩张方向

归一化方法：横截面 z-score → sigmoid 映射到 [0, 1]
"""

import logging
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional

import numpy as np
import pandas as pd

logger = logging.getLogger(__name__)


# =============================================================================
# 数据类
# =============================================================================


@dataclass
class ScoringConfig:
    """因子评分配置（所有参数可通过策略参数覆盖）"""

    # 大类权重（之和必须为 1.0）
    trend_weight: float = 0.45
    volume_weight: float = 0.30
    valuation_weight: float = 0.25

    # 趋势动量 — 子因子权重
    momentum_windows: List[int] = field(default_factory=lambda: [20, 60, 120, 250])
    momentum_weights: List[float] = field(default_factory=lambda: [0.15, 0.25, 0.35, 0.25])
    momentum_accel_short: int = 20    # 加速度：短期窗口
    momentum_accel_long: int = 60     # 加速度：中期窗口
    rs_window: int = 60               # 相对强弱窗口
    sub_weight_a1: float = 0.50       # A1 多窗口动量权重
    sub_weight_a2: float = 0.25       # A2 加速度权重
    sub_weight_a3: float = 0.25       # A3 相对强弱权重

    # 资金量价 — 子因子权重
    vol_ratio_short: int = 5          # 量比短期窗口
    vol_ratio_long: int = 60          # 量比长期窗口
    vol_price_window: int = 20        # 价量配合窗口
    turnover_short: int = 5           # 换手短期窗口
    turnover_long: int = 20           # 换手长期窗口
    sub_weight_b1: float = 0.40       # B1 量比权重
    sub_weight_b2: float = 0.35       # B2 价量配合权重
    sub_weight_b3: float = 0.25       # B3 换手加速度权重

    # 估值空间 — 子因子权重
    pe_percentile_years: int = 5      # PE 分位回溯年数
    pb_percentile_years: int = 5      # PB 分位回溯年数
    pe_expansion_window: int = 60     # 估值扩张对比窗口
    valuation_trap_threshold: float = 0.10  # 价值陷阱：PE 分位低于此但动量 < 0
    sub_weight_c1: float = 0.40       # C1 PE 分位权重
    sub_weight_c2: float = 0.35       # C2 PB 分位权重
    sub_weight_c3: float = 0.25       # C3 估值扩张权重

    # RSI（入场/出场辅助判断）
    rsi_period: int = 14

    def validate(self) -> List[str]:
        """校验配置合法性，返回错误列表"""
        errors: List[str] = []
        # 大类权重
        total = self.trend_weight + self.volume_weight + self.valuation_weight
        if abs(total - 1.0) > 0.01:
            errors.append(f"大类权重之和={total:.3f}，应≈1.0")
        # 趋势子权重
        tsub = self.sub_weight_a1 + self.sub_weight_a2 + self.sub_weight_a3
        if abs(tsub - 1.0) > 0.01:
            errors.append(f"趋势子权重之和={tsub:.3f}，应≈1.0")
        # 量价子权重
        vsub = self.sub_weight_b1 + self.sub_weight_b2 + self.sub_weight_b3
        if abs(vsub - 1.0) > 0.01:
            errors.append(f"量价子权重之和={vsub:.3f}，应≈1.0")
        # 估值子权重
        vasub = self.sub_weight_c1 + self.sub_weight_c2 + self.sub_weight_c3
        if abs(vasub - 1.0) > 0.01:
            errors.append(f"估值子权重之和={vasub:.3f}，应≈1.0")
        # 动量窗口与权重
        if len(self.momentum_windows) != len(self.momentum_weights):
            errors.append("动量窗口数与权重数不一致")
        if abs(sum(self.momentum_weights) - 1.0) > 0.01:
            errors.append(f"动量窗口权重之和={sum(self.momentum_weights):.3f}，应≈1.0")
        return errors


@dataclass
class IndustryScore:
    """单个行业的评分结果"""

    industry_code: str             # 申万行业代码，如 "801780.SI"
    industry_name: str             # 申万行业名，如 "银行"
    composite_score: float         # 综合得分 [0, 1]
    score_change: float = 0.0      # 本周得分变化（vs 上周）
    # 大类分解
    trend_score: float = 0.0
    volume_score: float = 0.0
    valuation_score: float = 0.0
    # 子因子原始值（调试用）
    factors: Dict[str, float] = field(default_factory=dict)
    # 因子向量（用于余弦相似度计算）
    factor_vector: Optional[np.ndarray] = None
    # RSI
    rsi: float = 50.0

    def to_factor_vector(self) -> np.ndarray:
        """将大类和子因子值组合为用于相似度计算的向量"""
        vec = np.array([
            self.trend_score,
            self.volume_score,
            self.valuation_score,
        ], dtype=np.float64)
        # 追加子因子
        for key in ["A1", "A2", "A3", "B1", "B2", "B3", "C1", "C2", "C3"]:
            vec = np.append(vec, self.factors.get(key, 0.0))
        self.factor_vector = vec
        return vec


# =============================================================================
# 评分服务
# =============================================================================


class IndustryScoringService:
    """
    申万行业多因子评分引擎。

    无状态纯计算服务。输入各行业日线 DataFrame，输出排序后的 IndustryScore 列表。

    用法:
        service = IndustryScoringService(config)
        scores = service.score_all(industry_data, benchmark_prices)
    """

    def __init__(self, config: Optional[ScoringConfig] = None):
        self.config = config or ScoringConfig()

    # -------------------------------------------------------------------------
    # 公开接口
    # -------------------------------------------------------------------------

    def score_all(
        self,
        industry_data: Dict[str, pd.DataFrame],
        benchmark_prices: Optional[pd.DataFrame] = None,
        prev_scores: Optional[Dict[str, float]] = None,
        factor_override: Optional[Dict[str, Dict[str, float]]] = None,
    ) -> List[IndustryScore]:
        """
        对所有行业评分并排序。

        Args:
            industry_data: {行业代码: DataFrame[close, vol, amount, pe, pb, float_mv]}
                           index 为 trade_date
            benchmark_prices: 基准指数日线 DataFrame（用于相对强弱 A3），
                             columns 含 'close'，index 为 trade_date
            prev_scores: 上周各行业综合得分 {行业代码: 得分}，用于计算边际变化
            factor_override: 调试用：{行业代码: {因子名: 手动值}} 覆写计算值

        Returns:
            按 composite_score 降序排列的 IndustryScore 列表
        """
        if not industry_data:
            logger.warning("行业数据为空，跳过评分")
            return []

        factor_override = factor_override or {}

        # ---- 计算三大类因子 ----
        trend_scores = self._calc_trend_factors(industry_data, benchmark_prices)
        volume_scores = self._calc_volume_factors(industry_data)
        valuation_scores = self._calc_valuation_factors(industry_data)

        # ---- 应用 factor_override ----
        self._apply_overrides(trend_scores, factor_override, "trend")
        self._apply_overrides(volume_scores, factor_override, "volume")
        self._apply_overrides(valuation_scores, factor_override, "valuation")

        # ---- 子因子横截面归一化 ----
        all_sub_factors: Dict[str, Dict[str, float]] = {}  # {行业代码: {因子名: 归一化值}}

        # 收集所有子因子
        for industry_code in industry_data:
            tf = trend_scores.get(industry_code, {})
            vf = volume_scores.get(industry_code, {})
            vlf = valuation_scores.get(industry_code, {})
            all_sub_factors[industry_code] = {
                "A1": tf.get("A1", 0.0),
                "A2": tf.get("A2", 0.0),
                "A3": tf.get("A3", 0.0),
                "B1": vf.get("B1", 0.0),
                "B2": vf.get("B2", 0.0),
                "B3": vf.get("B3", 0.0),
                "C1": vlf.get("C1", 0.0),
                "C2": vlf.get("C2", 0.0),
                "C3": vlf.get("C3", 0.0),
            }

        # 每个子因子独立横截面归一化
        normalized_factors: Dict[str, Dict[str, float]] = {}
        for factor_name in ["A1", "A2", "A3", "B1", "B2", "B3", "C1", "C2", "C3"]:
            values = {
                code: all_sub_factors[code].get(factor_name, 0.0)
                for code in industry_data
            }
            normalized_factors[factor_name] = self._cross_sectional_normalize(values)

        # ---- 加权合成 ----
        results: List[IndustryScore] = []

        for industry_code, df in industry_data.items():
            name = self._extract_industry_name(df)

            # 子因子值（归一化后）
            sub = {
                k: normalized_factors[k].get(industry_code, 0.5)
                for k in ["A1", "A2", "A3", "B1", "B2", "B3", "C1", "C2", "C3"]
            }

            # 大类得分
            cfg = self.config
            trend = (
                cfg.sub_weight_a1 * sub["A1"]
                + cfg.sub_weight_a2 * sub["A2"]
                + cfg.sub_weight_a3 * sub["A3"]
            )
            volume = (
                cfg.sub_weight_b1 * sub["B1"]
                + cfg.sub_weight_b2 * sub["B2"]
                + cfg.sub_weight_b3 * sub["B3"]
            )
            valuation = (
                cfg.sub_weight_c1 * sub["C1"]
                + cfg.sub_weight_c2 * sub["C2"]
                + cfg.sub_weight_c3 * sub["C3"]
            )

            # ---- 价值陷阱惩罚 ----
            pe_percentile_raw = valuation_scores.get(industry_code, {}).get("C1_raw", 0.5)
            momentum_a1_raw = trend_scores.get(industry_code, {}).get("A1_raw", 0.0)
            if pe_percentile_raw < cfg.valuation_trap_threshold and momentum_a1_raw < 0:
                valuation *= 0.3  # 极度便宜但仍在跌 → 估值分打折
                logger.debug(
                    f"价值陷阱检测: {name}({industry_code}) PE分位={pe_percentile_raw:.2%} "
                    f"动量={momentum_a1_raw:.3f} → 估值分打折"
                )

            # 综合得分
            composite = (
                cfg.trend_weight * trend
                + cfg.volume_weight * volume
                + cfg.valuation_weight * valuation
            )

            # RSI
            rsi_val = self._rsi(df["close"].values, cfg.rsi_period)

            # 边际变化
            score_change = 0.0
            if prev_scores and industry_code in prev_scores:
                score_change = composite - prev_scores[industry_code]

            # 原始子因子（调试用）
            raw_factors = {
                "A1": trend_scores.get(industry_code, {}).get("A1_raw", 0.0),
                "A2": trend_scores.get(industry_code, {}).get("A2_raw", 0.0),
                "A3": trend_scores.get(industry_code, {}).get("A3_raw", 0.0),
                "B1": volume_scores.get(industry_code, {}).get("B1_raw", 0.0),
                "B2": volume_scores.get(industry_code, {}).get("B2_raw", 0.0),
                "B3": volume_scores.get(industry_code, {}).get("B3_raw", 0.0),
                "C1": valuation_scores.get(industry_code, {}).get("C1_raw", 0.0),
                "C2": valuation_scores.get(industry_code, {}).get("C2_raw", 0.0),
                "C3": valuation_scores.get(industry_code, {}).get("C3_raw", 0.0),
            }

            score = IndustryScore(
                industry_code=industry_code,
                industry_name=name,
                composite_score=round(composite, 6),
                score_change=round(score_change, 6),
                trend_score=round(trend, 6),
                volume_score=round(volume, 6),
                valuation_score=round(valuation, 6),
                factors=raw_factors,
                rsi=round(rsi_val, 2),
            )
            results.append(score)

        # ---- 排序：综合得分降序 ----
        results.sort(key=lambda x: x.composite_score, reverse=True)

        # ---- 填充因子向量 ----
        for r in results:
            r.to_factor_vector()

        return results

    # -------------------------------------------------------------------------
    # 趋势动量因子（A 类）
    # -------------------------------------------------------------------------

    def _calc_trend_factors(
        self,
        industry_data: Dict[str, pd.DataFrame],
        benchmark_prices: Optional[pd.DataFrame],
    ) -> Dict[str, Dict[str, float]]:
        """
        计算趋势动量子因子：
          A1: 多窗口加权动量
          A2: 动量加速度（R_short − R_long）
          A3: 相对强弱（vs 基准）
        """
        cfg = self.config
        result: Dict[str, Dict[str, float]] = {}

        # 基准动量（用于相对强弱）
        benchmark_momentum = 0.0
        if benchmark_prices is not None and len(benchmark_prices) >= cfg.rs_window:
            bm_closes = benchmark_prices["close"].values
            bm_curr = bm_closes[-1]
            bm_prev = bm_closes[-cfg.rs_window - 1] if len(bm_closes) > cfg.rs_window else bm_closes[0]
            if bm_prev > 0:
                benchmark_momentum = float(bm_curr / bm_prev - 1.0)

        for code, df in industry_data.items():
            closes = df["close"].values
            if len(closes) < max(cfg.momentum_windows) + 1:
                continue

            # A1: 多窗口加权动量
            momentum_values = []
            for w in cfg.momentum_windows:
                if len(closes) >= w + 1 and closes[-w - 1] > 0:
                    momentum_values.append(float(closes[-1] / closes[-w - 1] - 1.0))
                else:
                    momentum_values.append(0.0)
            a1_raw = sum(mv * mw for mv, mw in zip(momentum_values, cfg.momentum_weights))

            # A2: 动量加速度
            r_short = momentum_values[0] if len(momentum_values) > 0 else 0.0
            r_long = momentum_values[1] if len(momentum_values) > 1 else 0.0
            a2_raw = r_short - r_long

            # A3: 相对强弱（行业动量 − 基准动量）
            industry_momentum = 0.0
            if len(closes) >= cfg.rs_window + 1 and closes[-cfg.rs_window - 1] > 0:
                industry_momentum = float(closes[-1] / closes[-cfg.rs_window - 1] - 1.0)
            a3_raw = industry_momentum - benchmark_momentum

            result[code] = {
                "A1_raw": a1_raw,
                "A2_raw": a2_raw,
                "A3_raw": a3_raw,
            }

        return result

    # -------------------------------------------------------------------------
    # 资金量价因子（B 类）
    # -------------------------------------------------------------------------

    def _calc_volume_factors(
        self,
        industry_data: Dict[str, pd.DataFrame],
    ) -> Dict[str, Dict[str, float]]:
        """
        计算资金量价子因子：
          B1: 量比（短期均量 / 长期均量）
          B2: 价量配合度（涨放量 vs 跌缩量）
          B3: 换手率加速度
        """
        cfg = self.config
        result: Dict[str, Dict[str, float]] = {}

        for code, df in industry_data.items():
            if len(df) < cfg.vol_ratio_long + 1:
                continue

            # B1: 量比
            vol_arr = df["vol"].values.astype(float)
            short_vol = np.mean(vol_arr[-cfg.vol_ratio_short:]) if len(vol_arr) >= cfg.vol_ratio_short else np.mean(vol_arr)
            long_vol = np.mean(vol_arr[-cfg.vol_ratio_long:]) if len(vol_arr) >= cfg.vol_ratio_long else 1.0
            b1_raw = float(short_vol / long_vol) if long_vol > 0 else 0.0

            # B2: 价量配合度
            pct_changes = df["pct_change"].values if "pct_change" in df.columns else np.diff(df["close"].values, prepend=df["close"].values[0]) / df["close"].values
            amounts = df["amount"].values.astype(float) if "amount" in df.columns else np.zeros(len(df))

            window = min(cfg.vol_price_window, len(pct_changes), len(amounts))
            up_amount = 0.0
            down_amount = 0.0
            for i in range(len(pct_changes) - window, len(pct_changes)):
                if i >= 0 and i < len(amounts):
                    if i < len(pct_changes) and pct_changes[i] > 0:
                        up_amount += float(amounts[i]) if i < len(amounts) else 0.0
                    else:
                        down_amount += float(amounts[i]) if i < len(amounts) else 0.0

            total_amount = up_amount + down_amount
            b2_raw = float((up_amount - down_amount) / total_amount) if total_amount > 0 else 0.0

            # B3: 换手加速度
            float_mv_arr = df["float_mv"].values.astype(float) if "float_mv" in df.columns else np.full(len(df), 1e12)
            turnover = np.divide(
                amount_arr := amounts.astype(float),
                np.where(float_mv_arr > 0, float_mv_arr, 1e12),
                out=np.zeros_like(amount_arr, dtype=float),
            )
            short_turnover = np.mean(turnover[-cfg.turnover_short:]) if len(turnover) >= cfg.turnover_short else 0.0
            long_turnover = np.mean(turnover[-cfg.turnover_long:]) if len(turnover) >= cfg.turnover_long else 0.0
            b3_raw = float(short_turnover - long_turnover) / max(abs(long_turnover), 1e-12)

            result[code] = {
                "B1_raw": b1_raw,
                "B2_raw": b2_raw,
                "B3_raw": b3_raw,
            }

        return result

    # -------------------------------------------------------------------------
    # 估值空间因子（C 类）
    # -------------------------------------------------------------------------

    def _calc_valuation_factors(
        self,
        industry_data: Dict[str, pd.DataFrame],
    ) -> Dict[str, Dict[str, float]]:
        """
        计算估值空间子因子：
          C1: PE 历史分位（1 − percentile）— 越低越便宜，得分越高
          C2: PB 历史分位 — 同上
          C3: 估值扩张方向（PE 当前 vs 窗口前）
        """
        cfg = self.config
        result: Dict[str, Dict[str, float]] = {}

        for code, df in industry_data.items():
            if len(df) < 1:
                continue

            # 检查 PE/PB 是否存在
            has_pe = "pe" in df.columns and df["pe"].notna().any()
            has_pb = "pb" in df.columns and df["pb"].notna().any()

            # C1: PE 分位
            c1_raw = 0.5  # 默认中等
            if has_pe:
                pe_arr = df["pe"].dropna().values.astype(float)
                pe_arr = pe_arr[pe_arr > 0]  # 负 PE 无意义
                if len(pe_arr) > 0:
                    current_pe = pe_arr[-1]
                    percentile = np.mean(pe_arr <= current_pe)
                    c1_raw = float(1.0 - percentile)  # 越低越便宜 → 得分越高

            # C2: PB 分位
            c2_raw = 0.5
            if has_pb:
                pb_arr = df["pb"].dropna().values.astype(float)
                pb_arr = pb_arr[pb_arr > 0]
                if len(pb_arr) > 0:
                    current_pb = pb_arr[-1]
                    percentile = np.mean(pb_arr <= current_pb)
                    c2_raw = float(1.0 - percentile)

            # C3: 估值扩张（PE 变化方向）
            c3_raw = 0.0
            if has_pe:
                pe_arr = df["pe"].dropna().values.astype(float)
                pe_arr = pe_arr[pe_arr > 0]
                window = min(cfg.pe_expansion_window, len(pe_arr) - 1)
                if window > 0 and len(pe_arr) > window and pe_arr[-window - 1] > 0:
                    c3_raw = float(pe_arr[-1] / pe_arr[-window - 1] - 1.0)

            result[code] = {
                "C1_raw": c1_raw,
                "C2_raw": c2_raw,
                "C3_raw": c3_raw,
            }

        return result

    # -------------------------------------------------------------------------
    # 归一化
    # -------------------------------------------------------------------------

    @staticmethod
    def _cross_sectional_normalize(values: Dict[str, float]) -> Dict[str, float]:
        """
        横截面 z-score → sigmoid 归一化到 [0, 1]。

        31 个行业同时计算，一个行业偏离均值越多，得分越极端。

        Args:
            values: {行业代码: 原始因子值}

        Returns:
            {行业代码: 归一化得分}
        """
        if len(values) < 2:
            return {k: 0.5 for k in values}

        arr = np.array(list(values.values()), dtype=np.float64)
        mean = np.mean(arr)
        std = np.std(arr)

        if std < 1e-8:
            # 所有值几乎相同 → 全给中等分
            return {k: 0.5 for k in values}

        result = {}
        for code, val in values.items():
            z = (val - mean) / std
            # Clip z 到 [-5, 5] 防止 sigmoid 溢出
            z = max(-5.0, min(5.0, z))
            score = 1.0 / (1.0 + np.exp(-z))
            result[code] = round(float(score), 6)

        return result

    # -------------------------------------------------------------------------
    # 工具方法
    # -------------------------------------------------------------------------

    @staticmethod
    def _rsi(closes: np.ndarray, period: int = 14) -> float:
        """计算 RSI"""
        if len(closes) < period + 1:
            return 50.0
        deltas = np.diff(closes[-period - 1:])
        gains = np.sum(deltas[deltas > 0]) if np.any(deltas > 0) else 0.0
        losses = -np.sum(deltas[deltas < 0]) if np.any(deltas < 0) else 0.0
        if losses < 1e-8:
            return 100.0
        rs = gains / losses
        return float(100.0 - 100.0 / (1.0 + rs))

    @staticmethod
    def _extract_industry_name(df: pd.DataFrame) -> str:
        """从 DataFrame 中提取行业名（name 列第一个非空值）"""
        if "name" in df.columns:
            names = df["name"].dropna()
            if len(names) > 0:
                return str(names.iloc[-1])  # 最新一期名称
        return ""

    @staticmethod
    def _apply_overrides(
        scores: Dict[str, Dict[str, float]],
        overrides: Dict[str, Dict[str, float]],
        category: str,
    ) -> None:
        """应用 factor_override 覆写"""
        for code, factors in overrides.items():
            if code not in scores:
                continue
            for fname, fval in factors.items():
                raw_key = f"{fname}_raw"
                if raw_key in scores[code]:
                    scores[code][raw_key] = fval
