# -*- coding: utf-8 -*-
"""行业轮动策略 V2 单元测试"""
import numpy as np
import pandas as pd
import pytest

from core.engines.types.entities import BarData


class TestParameterValidation:
    """策略参数校验"""

    @pytest.fixture
    def strategy_cls(self):
        from importlib import import_module
        # Import directly to avoid package chain
        import importlib.util, os
        path = os.path.join(
            os.path.dirname(__file__),
            "..", "..", "..",
            "modules", "strategy", "strategies", "rotation",
            "industry_rotation_strategy.py",
        )
        spec = importlib.util.spec_from_file_location(
            "ind_rot", os.path.abspath(path)
        )
        mod = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(mod)
        return mod.IndustryRotationStrategy

    def test_default_params_valid(self, strategy_cls):
        s = strategy_cls(name="test")
        errors = s._validate_params()
        assert len(errors) == 0, f"默认参数应无错误: {errors}"

    def test_top_n_out_of_range(self, strategy_cls):
        s = strategy_cls(name="test", parameters={"top_n": 0})
        errors = s._validate_params()
        assert len(errors) > 0

    def test_buffer_rank_must_be_greater_than_top_n(self, strategy_cls):
        s = strategy_cls(name="test", parameters={"top_n": 5, "buffer_rank": 3})
        errors = s._validate_params()
        assert any("buffer_rank" in e.lower() for e in errors)

    def test_rebalance_frequency_out_of_range(self, strategy_cls):
        s = strategy_cls(name="test", parameters={"rebalance_frequency": 30})
        errors = s._validate_params()
        assert len(errors) > 0

    def test_stop_loss_out_of_range(self, strategy_cls):
        s = strategy_cls(name="test", parameters={"stop_loss": 0.05})
        errors = s._validate_params()
        assert len(errors) > 0

    def test_take_profit_out_of_range(self, strategy_cls):
        s = strategy_cls(name="test", parameters={"take_profit": 0.05})
        errors = s._validate_params()
        assert len(errors) > 0

    def test_weight_sum_must_be_one(self, strategy_cls):
        s = strategy_cls(
            name="test",
            parameters={
                "trend_weight": 0.5,
                "volume_weight": 0.5,
                "valuation_weight": 0.5,
            },
        )
        errors = s._validate_params()
        assert any("权重" in e for e in errors)

    def test_custom_params_valid(self, strategy_cls):
        s = strategy_cls(
            name="test",
            parameters={
                "top_n": 5,
                "buffer_rank": 8,
                "rebalance_frequency": 5,
                "stop_loss": -0.08,
                "take_profit": 0.25,
                "trend_weight": 0.45,
                "volume_weight": 0.30,
                "valuation_weight": 0.25,
            },
        )
        errors = s._validate_params()
        assert len(errors) == 0, f"自定义参数应无错误: {errors}"


class TestDataAppend:
    """数据追加测试"""

    @pytest.fixture
    def strategy(self):
        import importlib.util, os
        path = os.path.join(
            os.path.dirname(__file__),
            "..", "..", "..",
            "modules", "strategy", "strategies", "rotation",
            "industry_rotation_strategy.py",
        )
        spec = importlib.util.spec_from_file_location(
            "ind_rot", os.path.abspath(path)
        )
        mod = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(mod)
        return mod.IndustryRotationStrategy(name="test")

    def test_append_industry_data(self, strategy):
        bar = BarData(
            ts_code="801780.SI",
            period="daily",
            open=100.0,
            high=101.0,
            low=99.0,
            close=100.5,
            volume=50000.0,
            amount=5000000.0,
        )
        strategy._append_industry_data("801780.SI", bar)
        assert "801780.SI" in strategy._industry_data_cache
        df = strategy._industry_data_cache["801780.SI"]
        assert len(df) == 1
        assert df["close"].iloc[0] == 100.5
        assert df["vol"].iloc[0] == 50000.0

    def test_append_etf_price(self, strategy):
        bar = BarData(
            ts_code="512800.SH",
            period="daily",
            open=1.20,
            high=1.22,
            low=1.19,
            close=1.21,
            volume=10000.0,
            amount=1210000.0,
        )
        strategy._append_etf_price("512800.SH", bar)
        assert "512800.SH" in strategy._data_cache
        df = strategy._data_cache["512800.SH"]
        assert len(df) == 1
        assert df["close"].iloc[0] == 1.21

    def test_append_multiple_bars(self, strategy):
        """追加多根 bar 应正确累积"""
        for i in range(10):
            bar = BarData(
                ts_code="801780.SI",
                period="daily",
                open=100.0 + i,
                high=101.0 + i,
                low=99.0 + i,
                close=100.5 + i,
                volume=50000.0,
                amount=5000000.0,
            )
            strategy._append_industry_data("801780.SI", bar)
        df = strategy._industry_data_cache["801780.SI"]
        assert len(df) == 10
        assert df["close"].iloc[-1] == 109.5

    def test_cache_size_limit(self, strategy):
        """缓存应限制大小，防止内存无限增长"""
        strategy.parameters["pe_percentile_years"] = 1  # 约 252 天
        for i in range(2000):
            bar = BarData(
                ts_code="801780.SI",
                period="daily",
                open=100.0,
                high=101.0,
                low=99.0,
                close=100.5,
                volume=50000.0,
                amount=5000000.0,
            )
            strategy._append_industry_data("801780.SI", bar)
        df = strategy._industry_data_cache["801780.SI"]
        max_rows = strategy.parameters.get("pe_percentile_years", 5) * 252 + 100
        assert len(df) <= max_rows + 10, f"缓存{len(df)}行应 ≤ {max_rows}"


class TestLifecycle:
    """生命周期测试"""

    @pytest.fixture
    def strategy(self):
        import importlib.util, os
        path = os.path.join(
            os.path.dirname(__file__),
            "..", "..", "..",
            "modules", "strategy", "strategies", "rotation",
            "industry_rotation_strategy.py",
        )
        spec = importlib.util.spec_from_file_location(
            "ind_rot", os.path.abspath(path)
        )
        mod = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(mod)
        return mod.IndustryRotationStrategy(name="test")

    def test_on_init_sets_up_services(self, strategy):
        strategy.on_init()  # 显式调用（测试中不会自动触发）
        assert strategy._scoring_service is not None
        assert strategy._etf_mapper is not None
        assert strategy._scoring_config is not None
        assert len(strategy._universe) > 0

    def test_on_start_clears_state(self, strategy):
        # Add some state
        strategy._bar_count = 100
        strategy._current_holdings["512800.SH"] = "银行"
        strategy._cooling_list["银行"] = 5
        strategy._entry_prices["512800.SH"] = 1.20

        strategy.on_start()

        assert strategy._bar_count == 0
        assert strategy._current_holdings == {}
        assert strategy._cooling_list == {}
        assert strategy._entry_prices == {}

    def test_on_stop_clears_state(self, strategy):
        strategy._current_holdings["512800.SH"] = "银行"
        strategy._industry_data_cache["801780.SI"] = pd.DataFrame()

        strategy.on_stop()

        assert strategy._current_holdings == {}
        assert strategy._industry_data_cache == {}
        assert strategy._entry_prices == {}

    def test_get_parameters(self, strategy):
        strategy.on_init()  # 先初始化
        params = strategy.get_parameters()
        assert "top_n" in params
        assert "trend_weight" in params
        assert params["top_n"] == 5
        assert params["universe_size"] > 0

    def test_get_holdings_empty_initially(self, strategy):
        assert strategy.get_holdings() == []

    def test_get_current_scores_empty_initially(self, strategy):
        assert strategy.get_current_scores() == {}


class TestStopTakeProfit:
    """止损止盈测试"""

    @pytest.fixture
    def strategy(self):
        import importlib.util, os
        path = os.path.join(
            os.path.dirname(__file__),
            "..", "..", "..",
            "modules", "strategy", "strategies", "rotation",
            "industry_rotation_strategy.py",
        )
        spec = importlib.util.spec_from_file_location(
            "ind_rot", os.path.abspath(path)
        )
        mod = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(mod)
        return mod.IndustryRotationStrategy(name="test")

    def test_stop_loss_triggers(self, strategy):
        """浮亏超过 8% 应触发止损"""
        strategy._entry_prices["512800.SH"] = 1.50
        strategy._current_holdings["512800.SH"] = "银行"
        # 模拟价格跌到 1.35（亏损 10%）
        df = pd.DataFrame({"close": [1.50, 1.35]})
        strategy._data_cache["512800.SH"] = df

        signal = strategy._check_stop_take_profit("512800.SH")
        assert signal is not None
        assert signal.signal_type.value == "stop_loss"

    def test_no_stop_loss_when_pnl_ok(self, strategy):
        """浮亏 5% 不应触发止损"""
        strategy._entry_prices["512800.SH"] = 1.50
        strategy._current_holdings["512800.SH"] = "银行"
        df = pd.DataFrame({"close": [1.50, 1.425]})  # -5%
        strategy._data_cache["512800.SH"] = df

        signal = strategy._check_stop_take_profit("512800.SH")
        assert signal is None

    def test_no_entry_price_no_check(self, strategy):
        """没有买入价记录时不检查"""
        df = pd.DataFrame({"close": [1.50, 1.00]})
        strategy._data_cache["512800.SH"] = df
        signal = strategy._check_stop_take_profit("512800.SH")
        assert signal is None
