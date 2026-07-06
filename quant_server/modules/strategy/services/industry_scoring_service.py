# -*- coding: utf-8 -*-
"""
行业多因子评分服务 — V4 主线趋势版

对 31 个申万一级行业进行多维度打分，输出排序结果。

因子体系（V4 权重调整）：
  - 趋势动量 (55%)：多窗口动量 + 加速度 + 相对强弱 → 主线识别核心
  - 资金量价 (30%)：量比 + 价量配合 + 换手加速度 → 量能确认
  - 估值空间 (15%)：PE/PB 历史分位 → 仅做过热过滤，不选方向

归一化方法：横截面 z-score → sigmoid 映射到 [0, 1]

V4 变更（2026-07-04）：
  1. 大类权重 trend/valuation 从 45/25 → 55/15
  2. 动量窗口从 4 窗(250日)改为 3 窗(120日)，偏重中短期
  3. 估值因子从"越便宜越高分"改为"中间中性，两头扣分"
  4. 去掉 C3 估值扩张方向（与主线捕捉无关）
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

    # —— 大类权重（之和必须为 1.0）——
    # V4 变动：趋势主导，估值只做过滤
    trend_weight: float = 0.55      # 从 0.45 → 0.55（主线由动量驱动）
    volume_weight: float = 0.30     # 不变
    valuation_weight: float = 0.15  # 从 0.25 → 0.15（只过滤不选方向）

    # —— 趋势动量 ——
    # A2 动量加速度（R_short − R_long）使用 momentum_windows[0]/[1]
    # 默认 [10, 30, 60]，A2 用前两个窗口计算"短期加速"
    momentum_windows: List[int] = field(default_factory=lambda: [10, 30, 60])
    momentum_weights: List[float] = field(default_factory=lambda: [0.40, 0.35, 0.25])
    momentum_accel_short: int = 20    # 加速度：短期窗口
    momentum_accel_long: int = 60     # 加速度：中期窗口
    rs_window: int = 60               # 相对强弱窗口
    sub_weight_a1: float = 0.50       # A1 多窗口动量权重
    sub_weight_a2: float = 0.25       # A2 加速度权重
    sub_weight_a3: float = 0.25       # A3 相对强弱权重

    # —— 资金量价 ——
    vol_ratio_short: int = 5          # 量比短期窗口
    vol_ratio_long: int = 60          # 量比长期窗口
    vol_price_window: int = 20        # 价量配合窗口
    turnover_short: int = 5           # 换手短期窗口
    turnover_long: int = 20           # 换手长期窗口
    sub_weight_b1: float = 0.40       # B1 量比权重
    sub_weight_b2: float = 0.35       # B2 价量配合权重
    sub_weight_b3: float = 0.25       # B3 换手加速度权重

    # —— 估值空间（V4：只做过热/价值陷阱过滤）——
    pe_percentile_years: int = 5      # PE 分位回溯年数
    pb_percentile_years: int = 5      # PB 分位回溯年数
    sub_weight_c1: float = 0.55       # C1 PE 分位权重（V4 去掉 C3 后重分配）
    sub_weight_c2: float = 0.45       # C2 PB 分位权重

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
        # 估值子权重（V4：只有 C1+C2，没有 C3）
        vasub = self.sub_weight_c1 + self.sub_weight_c2
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
        # 追加子因子（V4：C3 已移除）
        for key in ["A1", "A2", "A3", "B1", "B2", "B3", "C1", "C2"]:
            vec = np.append(vec, self.factors.get(key, 0.0))
        self.factor_vector = vec
        return vec


# =============================================================================
# 评分服务
# =============================================================================


class IndustryScoringService:
    """
    申万行业多因子评分引擎 — V4 版。

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
            benchmark_prices: 基准指数日线 DataFrame（用于相对强弱 A3）
            prev_scores: 上期各行业综合得分 {行业代码: 得分}，用于计算边际变化
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
        all_sub_factors: Dict[str, Dict[str, float]] = {}

        # 收集所有子因子（V4：C3 已去除）
        for industry_code in industry_data:
            tf = trend_scores.get(industry_code, {})
            vf = volume_scores.get(industry_code, {})
            vlf = valuation_scores.get(industry_code, {})
            all_sub_factors[industry_code] = {
                "A1": tf.get("A1_raw", 0.0),
                "A2": tf.get("A2_raw", 0.0),
                "A3": tf.get("A3_raw", 0.0),
                "B1": vf.get("B1_raw", 0.0),
                "B2": vf.get("B2_raw", 0.0),
                "B3": vf.get("B3_raw", 0.0),
                "C1": vlf.get("C1_raw", 0.0),
                "C2": vlf.get("C2_raw", 0.0),
            }

        # 每个子因子独立横截面归一化
        normalized_factors: Dict[str, Dict[str, float]] = {}
        # V4：C3 已去除，共 8 个子因子
        for factor_name in ["A1", "A2", "A3", "B1", "B2", "B3", "C1", "C2"]:
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
                for k in ["A1", "A2", "A3", "B1", "B2", "B3", "C1", "C2"]
            }

            # 大类得分（V4：C3 已去除）
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
            )

            # V4 删除：价值陷阱惩罚（估值不再做方向性判断）

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
          A1: 多窗口加权动量（当前权重 0，保留备用）
          A2: 动量加速度（R_short − R_long），IC = +0.0698，唯一强正因子
          A3: 相对强弱（vs 基准，当前权重 0，保留备用）

        V4：动量窗口从 4 窗改为 3 窗（10/30/60），偏重中短期。
        """
        cfg = self.config
        result: Dict[str, Dict[str, float]] = {}
        min_window = min(cfg.momentum_windows)

        # 基准动量（用于相对强弱）
        benchmark_momentum = 0.0
        if benchmark_prices is not None and len(benchmark_prices) >= cfg.rs_window:
            bm_closes = benchmark_prices["close"].values
            bm_curr = bm_closes[-1]
            bm_prev = bm_closes[-cfg.rs_window - 1] if len(bm_closes) > cfg.rs_window else bm_closes[0]
            if bm_prev > 0:
                benchmark_momentum = float(bm_curr / bm_prev - 1.0)

        for code, df in industry_data.items():
            closes = df["close"].values.astype(np.float64)
            if len(closes) < min_window + 1:
                continue

            # A1: 多窗口加权动量
            available_mvs = []
            available_ws = []
            for w, mw in zip(cfg.momentum_windows, cfg.momentum_weights):
                if len(closes) >= w + 1 and closes[-w - 1] > 0:
                    available_mvs.append(float(closes[-1] / closes[-w - 1] - 1.0))
                    available_ws.append(mw)
            if available_ws:
                total_w = sum(available_ws)
                a1_raw = sum(mv * w / total_w for mv, w in zip(available_mvs, available_ws))
            else:
                a1_raw = 0.0

            # A2: 动量加速度（R_short − R_long）
            # IC = +0.0698（10d-30d，整个 2022-2025 区间），是唯一强正因子
            if len(available_mvs) >= 2:
                r_short = available_mvs[0]
                r_long = available_mvs[1] if len(available_mvs) > 1 else 0.0
            else:
                r_short = available_mvs[0] if available_mvs else 0.0
                r_long = 0.0
            a2_raw = r_short - r_long

            # A3: 相对强弱
            industry_momentum = 0.0
            actual_rs_window = min(cfg.rs_window, len(closes) - 1)
            if actual_rs_window > 0 and closes[-actual_rs_window - 1] > 0:
                industry_momentum = float(closes[-1] / closes[-actual_rs_window - 1] - 1.0)
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
        min_window = min(cfg.vol_ratio_short, cfg.turnover_short)

        for code, df in industry_data.items():
            if len(df) < min_window + 1:
                continue

            # B1: 量比
            vol_arr = df["vol"].values.astype(float)
            short_vol = np.mean(vol_arr[-cfg.vol_ratio_short:]) if len(vol_arr) >= cfg.vol_ratio_short else np.mean(vol_arr)
            actual_long = min(cfg.vol_ratio_long, len(vol_arr))
            long_vol = np.mean(vol_arr[-actual_long:]) if actual_long > 0 else 1.0
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
    # 估值空间因子（C 类）— V4 重写
    # -------------------------------------------------------------------------

    def _calc_valuation_factors(
        self,
        industry_data: Dict[str, pd.DataFrame],
    ) -> Dict[str, Dict[str, float]]:
        """
        计算估值过滤子因子。

        V4 改造（核心变更）：
          估值不再用于"选方向"，只做两件事：
            1. PE/PB 历史分位过高（>95%）→ 过热预警（低分）
            2. PE/PB 过低（<5%）→ 价值陷阱预警（中低分）
            其他 → 中性分（不额外加分也不扣分）

          原来 C3 估值扩张已移除（与主线捕捉无关）。
        """
        result: Dict[str, Dict[str, float]] = {}

        for code, df in industry_data.items():
            if len(df) < 1:
                continue

            has_pe = "pe" in df.columns and df["pe"].notna().any()
            has_pb = "pb" in df.columns and df["pb"].notna().any()

            # C1: PE 分位 — V4 改为两头扣分逻辑
            c1_raw = self._calc_percentile_filter(df, "pe") if has_pe else 0.5

            # C2: PB 分位 — 同上
            c2_raw = self._calc_percentile_filter(df, "pb") if has_pb else 0.5

            result[code] = {
                "C1_raw": c1_raw,
                "C2_raw": c2_raw,
            }

        return result

    def _calc_percentile_filter(self, df: pd.DataFrame, field: str) -> float:
        """
        V4 估值过滤函数：两头扣分，中间中性。

        规则：
          - 估值 > 历史 95 分位 → 0.2（极贵，过热警告）
          - 估值 > 历史 90 分位 → 0.4（偏贵，留意）
          - 估值 < 历史 5 分位 → 0.4（极便宜，价值陷阱警告）
          - 其余 → 0.6（中性，不给额外加分）
        """
        arr = df[field].dropna().values.astype(float)
        arr = arr[arr > 0]  # 负数无意义
        if len(arr) < 20:
            return 0.5

        current = arr[-1]
        percentile = float(np.mean(arr <= current))

        if percentile > 0.95:
            return 0.2   # 极贵，过热警告
        elif percentile > 0.90:
            return 0.4   # 偏贵
        elif percentile < 0.05:
            return 0.4   # 极便宜，价值陷阱警告
        else:
            return 0.6   # 合理区间，中性

    # -------------------------------------------------------------------------
    # 归一化
    # -------------------------------------------------------------------------

    @staticmethod
    def _cross_sectional_normalize(values: Dict[str, float]) -> Dict[str, float]:
        """
        横截面 z-score → sigmoid 归一化到 [0, 1]。

        31 个行业同时计算，一个行业偏离均值越多，得分越极端。
        """
        if len(values) < 2:
            return {k: 0.5 for k in values}

        arr = np.array(list(values.values()), dtype=np.float64)
        mean = np.mean(arr)
        std = np.std(arr)

        if std < 1e-8:
            return {k: 0.5 for k in values}

        result = {}
        for code, val in values.items():
            z = (val - mean) / std
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
                return str(names.iloc[-1])
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
