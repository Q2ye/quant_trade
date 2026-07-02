# -*- coding: utf-8 -*-
"""行业多因子评分服务单元测试"""
import numpy as np
import pandas as pd
import pytest

from modules.strategy.services.industry_scoring_service import (
    IndustryScoringService,
    ScoringConfig,
    IndustryScore,
)


class TestScoringConfig:
    """ScoringConfig 参数校验测试"""

    def test_default_config_valid(self):
        cfg = ScoringConfig()
        errors = cfg.validate()
        assert len(errors) == 0, f"默认配置应无校验错误，实际: {errors}"

    def test_invalid_weight_sum(self):
        cfg = ScoringConfig(trend_weight=0.5, volume_weight=0.5, valuation_weight=0.5)
        errors = cfg.validate()
        assert len(errors) > 0
        assert any("大类权重" in e for e in errors)

    def test_invalid_momentum_windows(self):
        cfg = ScoringConfig(momentum_windows=[20, 60], momentum_weights=[0.3, 0.3, 0.4])
        errors = cfg.validate()
        assert len(errors) > 0
        assert any("窗口" in e for e in errors)

    def test_custom_weights_valid(self):
        cfg = ScoringConfig(
            trend_weight=0.40,
            volume_weight=0.35,
            valuation_weight=0.25,
        )
        errors = cfg.validate()
        assert len(errors) == 0


class TestIndustryScoringService:
    """评分服务核心逻辑测试"""

    @pytest.fixture
    def service(self) -> IndustryScoringService:
        return IndustryScoringService(ScoringConfig())

    @pytest.fixture
    def sample_data(self) -> dict:
        """创建 3 个行业的模拟日线数据（300 个交易日）"""
        dates = pd.date_range("2025-01-01", periods=300, freq="B")
        np.random.seed(123)
        data = {}
        configs = [
            ("801780.SI", "银行"),
            ("801150.SI", "医药生物"),
            ("801080.SI", "电子"),
        ]
        for code, name in configs:
            closes = np.cumprod(1 + np.random.randn(300) * 0.02)
            df = pd.DataFrame(
                {
                    "close": closes,
                    "vol": np.random.randint(100000, 500000, 300).astype(float),
                    "amount": np.random.randint(1_000_000, 5_000_000, 300).astype(float),
                    "pe": np.clip(closes * 15, 5, 50),
                    "pb": np.clip(closes * 1.5, 0.5, 5),
                    "float_mv": np.full(300, 1e8),
                    "pct_change": np.diff(closes, prepend=closes[0])
                    / np.maximum(closes, 1e-8),
                    "name": name,
                },
                index=dates,
            )
            data[code] = df
        return data

    def test_score_all_returns_correct_count(self, service, sample_data):
        scores = service.score_all(sample_data)
        assert len(scores) == len(sample_data)

    def test_scores_are_sorted_descending(self, service, sample_data):
        scores = service.score_all(sample_data)
        for i in range(len(scores) - 1):
            assert (
                scores[i].composite_score >= scores[i + 1].composite_score
            ), f"排序错误: #{i+1}得分={scores[i].composite_score} < #{i+2}得分={scores[i+1].composite_score}"

    def test_composite_score_in_range(self, service, sample_data):
        scores = service.score_all(sample_data)
        for s in scores:
            assert 0.0 <= s.composite_score <= 1.0, f"综合得分 {s.composite_score} 不在 [0,1]"
            assert 0.0 <= s.trend_score <= 1.0
            assert 0.0 <= s.volume_score <= 1.0
            assert 0.0 <= s.valuation_score <= 1.0

    def test_rsi_in_range(self, service, sample_data):
        scores = service.score_all(sample_data)
        for s in scores:
            assert 0.0 <= s.rsi <= 100.0, f"RSI {s.rsi} 不在 [0,100]"

    def test_score_change_default_zero(self, service, sample_data):
        """没有 prev_scores 时，score_change 应为 0"""
        scores = service.score_all(sample_data)
        for s in scores:
            assert s.score_change == 0.0

    def test_score_change_calculated(self, service, sample_data):
        """传入 prev_scores 后应计算边际变化"""
        prev = {code: 0.99 for code in sample_data}  # 与当前得分（≈0.5）差异大
        scores = service.score_all(sample_data, prev_scores=prev)
        for s in scores:
            assert s.score_change != 0.0, (
                f"{s.industry_code} score_change 应非零, "
                f"prev={prev.get(s.industry_code)}, current={s.composite_score:.4f}"
            )

    def test_empty_data_handled(self, service):
        """空数据应返回空列表，不崩溃"""
        scores = service.score_all({})
        assert scores == []

    def test_single_industry_handled(self, service):
        """单个行业也应能计算"""
        dates = pd.date_range("2025-01-01", periods=100, freq="B")
        df = pd.DataFrame(
            {
                "close": np.cumprod(1 + np.random.randn(100) * 0.01),
                "vol": np.random.randint(10000, 100000, 100).astype(float),
                "amount": np.random.randint(100000, 1000000, 100).astype(float),
                "pe": np.random.uniform(10, 30, 100),
                "pb": np.random.uniform(1, 3, 100),
                "float_mv": np.full(100, 1e8),
                "pct_change": np.zeros(100),
                "name": "测试行业",
            },
            index=dates,
        )
        scores = service.score_all({"801999.SI": df})
        assert len(scores) == 1
        # 单个行业的归一化结果应为 0.5
        assert abs(scores[0].composite_score - 0.5) < 0.1

    def test_factor_override_applied(self, service, sample_data):
        """手动覆写因子值应在子因子原始值中生效"""
        override = {"801780.SI": {"A1": 0.99}}
        scores = service.score_all(sample_data, factor_override=override)
        bank = next(s for s in scores if s.industry_code == "801780.SI")
        # 覆写后的 A1 原始值应为 0.99
        assert abs(bank.factors.get("A1", 0.0) - 0.99) < 0.01, (
            f"A1 应被覆写为 0.99，实际: {bank.factors.get('A1')}"
        )
        # 其他行业的 A1 不应被覆写
        others = [s for s in scores if s.industry_code != "801780.SI"]
        for s in others:
            assert abs(s.factors.get("A1", 0.0) - 0.99) > 0.01, (
                f"{s.industry_code} 的 A1 不应被覆写, 实际: {s.factors.get('A1')}"
            )

    def test_missing_pe_handled(self, service):
        """PE/PB 列为空时不应崩溃"""
        dates = pd.date_range("2025-01-01", periods=100, freq="B")
        df = pd.DataFrame(
            {
                "close": np.cumprod(1 + np.random.randn(100) * 0.01),
                "vol": np.random.randint(10000, 100000, 100).astype(float),
                "amount": np.random.randint(100000, 1000000, 100).astype(float),
                "float_mv": np.full(100, 1e8),
                "pct_change": np.zeros(100),
                "name": "亏损行业",
                # 故意不包含 pe 和 pb 列
            },
            index=dates,
        )
        scores = service.score_all({"801999.SI": df})
        assert len(scores) == 1
        assert 0.0 <= scores[0].valuation_score <= 1.0

    def test_nan_pe_handled(self, service):
        """PE 为 NaN 时不应崩溃"""
        dates = pd.date_range("2025-01-01", periods=100, freq="B")
        df = pd.DataFrame(
            {
                "close": np.cumprod(1 + np.random.randn(100) * 0.01),
                "vol": np.random.randint(10000, 100000, 100).astype(float),
                "amount": np.random.randint(100000, 1000000, 100).astype(float),
                "pe": np.full(100, np.nan),
                "pb": np.full(100, np.nan),
                "float_mv": np.full(100, 1e8),
                "pct_change": np.zeros(100),
                "name": "数据缺失行业",
            },
            index=dates,
        )
        scores = service.score_all({"801999.SI": df})
        assert len(scores) == 1

    def test_valuation_trap_penalty(self, service):
        """价值陷阱测试：PE 极低 + 动量为负 → 估值分应打折"""
        dates = pd.date_range("2024-01-01", periods=300, freq="B")
        # 构造一个持续下跌的行业
        closes = np.linspace(100, 50, 300)  # 持续下跌
        df = pd.DataFrame(
            {
                "close": closes,
                "vol": np.random.randint(100000, 500000, 300).astype(float),
                "amount": np.random.randint(1_000_000, 5_000_000, 300).astype(float),
                "pe": np.full(300, 5.0),  # PE 很低（分位 ≈ 0）
                "pb": np.full(300, 0.8),
                "float_mv": np.full(300, 1e8),
                "pct_change": np.diff(closes, prepend=closes[0])
                / np.maximum(closes, 1e-8),
                "name": "价值陷阱行业",
            },
            index=dates,
        )
        # 再创建一个正常行业对比
        normal_closes = np.cumprod(1 + np.random.randn(300) * 0.02)
        df2 = pd.DataFrame(
            {
                "close": normal_closes,
                "vol": np.random.randint(100000, 500000, 300).astype(float),
                "amount": np.random.randint(1_000_000, 5_000_000, 300).astype(float),
                "pe": np.clip(normal_closes * 15, 5, 50),
                "pb": np.clip(normal_closes * 1.5, 0.5, 5),
                "float_mv": np.full(300, 1e8),
                "pct_change": np.diff(normal_closes, prepend=normal_closes[0])
                / np.maximum(normal_closes, 1e-8),
                "name": "正常行业",
            },
            index=dates,
        )
        scores = service.score_all(
            {"801999.SI": df, "801998.SI": df2}
        )
        trap = next(s for s in scores if s.industry_name == "价值陷阱行业")
        normal = next(s for s in scores if s.industry_name == "正常行业")
        # 价值陷阱的估值分应低于正常行业
        assert trap.valuation_score <= normal.valuation_score, (
            f"价值陷阱估值分={trap.valuation_score:.4f} 应 ≤ 正常估值分={normal.valuation_score:.4f}"
        )

    def test_rs_with_benchmark(self, service, sample_data):
        """带基准指数的相对强弱计算"""
        dates = pd.date_range("2025-01-01", periods=300, freq="B")
        benchmark = pd.DataFrame(
            {
                "close": np.cumprod(1 + np.random.randn(300) * 0.015),
            },
            index=dates,
        )
        scores = service.score_all(sample_data, benchmark_prices=benchmark)
        assert len(scores) == len(sample_data)
        # A3 因子应存在（有基准时）
        for s in scores:
            assert "A3" in s.factors

    def test_industryscore_to_factor_vector(self):
        """因子向量正确生成"""
        score = IndustryScore(
            industry_code="801780.SI",
            industry_name="银行",
            composite_score=0.75,
            trend_score=0.8,
            volume_score=0.7,
            valuation_score=0.6,
            factors={"A1": 0.1, "A2": 0.05, "A3": 0.02, "B1": 1.2, "B2": 0.3, "B3": 0.01, "C1": 0.8, "C2": 0.7, "C3": 0.05},
        )
        vec = score.to_factor_vector()
        assert vec is not None
        assert len(vec) == 12  # 3 大类 + 9 子因子

    def test_cosine_similarity_calculation(self):
        """余弦相似度的边界情况"""
        s1 = IndustryScore(
            industry_code="801780.SI",
            industry_name="银行",
            composite_score=0.8,
            factors={"A1": 0.9, "A2": 0.0, "A3": 0.0, "B1": 0.0, "B2": 0.0, "B3": 0.0, "C1": 0.9, "C2": 0.0, "C3": 0.0},
        )
        s2 = IndustryScore(
            industry_code="801790.SI",
            industry_name="非银金融",
            composite_score=0.75,
            factors={"A1": 0.85, "A2": 0.0, "A3": 0.0, "B1": 0.0, "B2": 0.0, "B3": 0.0, "C1": 0.85, "C2": 0.0, "C3": 0.0},
        )
        v1 = s1.to_factor_vector()
        v2 = s2.to_factor_vector()
        sim = float(np.dot(v1, v2) / (np.linalg.norm(v1) * np.linalg.norm(v2) + 1e-12))
        assert sim > 0.9, f"相似行业应有高相似度，实际: {sim:.4f}"
