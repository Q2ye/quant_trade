# -*- coding: utf-8 -*-
"""日频底座取数方法测试（不联网，用 FakePro 记录调用）。"""

from __future__ import annotations

import pandas as pd
import pytest

from shared.sources.tushare_source import TushareSource


class FakePro:
    def __init__(self, df: pd.DataFrame):
        self.df = df
        self.calls: list[tuple[str, dict]] = []

    def query(self, api: str, **kwargs):
        self.calls.append((api, kwargs))
        return self.df.copy()


def _source() -> tuple[TushareSource, FakePro]:
    src = TushareSource.__new__(TushareSource)
    pro = FakePro(pd.DataFrame({"trade_date": ["20261106"], "value": [1.0]}))
    src.pro = pro
    src._connected = True
    return src, pro


# (方法名, kwargs, 期望接口名, 期望 kwargs)
P0B_FUND = [
    ("get_fx_obasic", {}, "fx_obasic", {"exchange": "FXCM"}),
    ("get_fx_daily", {"trade_date": "20261106"}, "fx_daily", {"trade_date": "20261106"}),
    ("get_fund_nav", {"nav_date": "20261106"}, "fund_nav", {"nav_date": "20261106"}),
    ("get_fund_basic", {}, "fund_basic", {"market": "E"}),
    ("get_fund_company", {}, "fund_company", {}),
    ("get_fund_manager", {"ts_code": "000001.OF"}, "fund_manager", {"ts_code": "000001.OF"}),
    ("get_fund_div", {"ts_code": "000001.OF"}, "fund_div", {"ts_code": "000001.OF"}),
    ("get_fund_share", {"trade_date": "20261106"}, "fund_share", {"trade_date": "20261106"}),
    ("get_fund_daily", {"trade_date": "20261106"}, "fund_daily", {"trade_date": "20261106"}),
]

P0B_MACRO = [
    ("get_margin_detail", {"trade_date": "20261106"}, "margin_detail", {"trade_date": "20261106"}),
    ("get_margin_secs", {"trade_date": "20261106"}, "margin_secs", {"trade_date": "20261106"}),
    ("get_new_share", {}, "new_share", {}),
    ("get_index_monthly", {"trade_date": "20261030"}, "index_monthly", {"trade_date": "20261030"}),
    ("get_shibor", {"start_date": "20260901", "end_date": "20261106"}, "shibor",
     {"start_date": "20260901", "end_date": "20261106"}),
    ("get_libor", {}, "libor", {}),
    ("get_hibor", {}, "hibor", {}),
    ("get_us_tbr", {}, "us_tbr", {}),
    ("get_us_tycr", {}, "us_tycr", {}),
    ("get_sf_month", {"start_m": "202608"}, "sf_month", {"start_m": "202608"}),
    ("get_cn_m", {"start_m": "202608"}, "cn_m", {"start_m": "202608"}),
    ("get_cn_pmi", {"start_m": "202608"}, "cn_pmi", {"start_m": "202608"}),
]

P0C = [
    ("get_top_list", {"trade_date": "20261106"}, "top_list", {"trade_date": "20261106"}),
    ("get_top_inst", {"trade_date": "20261106"}, "top_inst", {"trade_date": "20261106"}),
    ("get_cyq_perf", {"trade_date": "20261106"}, "cyq_perf", {"trade_date": "20261106"}),
    ("get_ths_index", {}, "ths_index", {"exchange": "A", "type": "N"}),
    ("get_ths_daily", {"trade_date": "20261106"}, "ths_daily", {"trade_date": "20261106"}),
    ("get_ths_member", {"ts_code": "885000.TI"}, "ths_member", {"ts_code": "885000.TI"}),
    ("get_moneyflow_dc", {"trade_date": "20261106"}, "moneyflow_dc", {"trade_date": "20261106"}),
    ("get_moneyflow_ths", {"trade_date": "20261106"}, "moneyflow_ths", {"trade_date": "20261106"}),
    ("get_moneyflow_ind_dc", {"trade_date": "20261106"}, "moneyflow_ind_dc", {"trade_date": "20261106"}),
    ("get_moneyflow_ind_ths", {"trade_date": "20261106"}, "moneyflow_ind_ths", {"trade_date": "20261106"}),
    ("get_moneyflow_cnt_ths", {"trade_date": "20261106"}, "moneyflow_cnt_ths", {"trade_date": "20261106"}),
    ("get_daily_info", {"trade_date": "20261106"}, "daily_info", {"trade_date": "20261106"}),
    ("get_sz_daily_info", {"trade_date": "20261106"}, "sz_daily_info", {"trade_date": "20261106"}),
]

P1_FUTURES = [
    ("get_block_trade", {"trade_date": "20261106"}, "block_trade", {"trade_date": "20261106"}),
    ("get_index_global", {"trade_date": "20261106"}, "index_global", {"trade_date": "20261106"}),
    ("get_fut_basic", {"exchange": "CFFEX"}, "fut_basic", {"exchange": "CFFEX", "fut_type": "1"}),
    ("get_fut_daily", {"trade_date": "20261106"}, "fut_daily", {"trade_date": "20261106"}),
    ("get_fut_holding", {"trade_date": "20261106", "symbol": "CU", "exchange": "SHFE"},
     "fut_holding", {"trade_date": "20261106", "symbol": "CU", "exchange": "SHFE"}),
    ("get_fut_wsr", {"trade_date": "20261106", "symbol": "CU", "exchange": "SHFE"},
     "fut_wsr", {"trade_date": "20261106", "symbol": "CU", "exchange": "SHFE"}),
    ("get_fut_settle", {"trade_date": "20261106"}, "fut_settle", {"trade_date": "20261106"}),
    ("get_fut_mapping", {"trade_date": "20261106"}, "fut_mapping", {"trade_date": "20261106"}),
    ("get_fut_index_daily", {"ts_code": "NHCI.NH"}, "fut_index_daily", {"ts_code": "NHCI.NH"}),
]

P1_OPTIONS_BONDS = [
    ("get_opt_basic", {}, "opt_basic", {"exchange": "SSE"}),
    ("get_opt_daily", {"trade_date": "20261106"}, "opt_daily", {"trade_date": "20261106"}),
    ("get_cb_basic", {}, "cb_basic", {}),
    ("get_cb_issue", {}, "cb_issue", {}),
    ("get_cb_call", {}, "cb_call", {}),
    ("get_cb_daily", {"trade_date": "20261106"}, "cb_daily", {"trade_date": "20261106"}),
    ("get_cb_share", {}, "cb_share", {}),
    ("get_cb_rating", {}, "cb_rating", {}),
    ("get_hsgt_top10", {"trade_date": "20261106"}, "hsgt_top10",
     {"trade_date": "20261106", "market_type": "1"}),
]

P2 = [
    ("get_pledge_detail", {}, "pledge_detail", {}),
    ("get_repurchase", {}, "repurchase", {}),
    ("get_stk_surv", {}, "stk_surv", {}),
    ("get_kpl_list", {"trade_date": "20261106"}, "kpl_list",
     {"trade_date": "20261106", "tag": "涨停"}),
    ("get_hm_list", {}, "hm_list", {}),
    ("get_eco_cal", {}, "eco_cal", {}),
    ("get_hk_basic", {}, "hk_basic", {"list_status": "L"}),
    ("get_hk_daily", {"trade_date": "20261106"}, "hk_daily", {"trade_date": "20261106"}),
    ("get_us_basic", {}, "us_basic", {}),
    ("get_us_daily", {"trade_date": "20261106"}, "us_daily", {"trade_date": "20261106"}),
    ("get_ggt_daily", {"trade_date": "20261106"}, "ggt_daily", {"trade_date": "20261106"}),
]


def _run_cases(cases):
    for method, kwargs, api, expected_kwargs in cases:
        src, pro = _source()
        df = getattr(src, method)(**kwargs)
        assert isinstance(df, pd.DataFrame), method
        assert pro.calls and pro.calls[0][0] == api, method
        actual = {k: v for k, v in pro.calls[0][1].items()
                  if k not in ("limit", "offset")}
        assert actual == expected_kwargs, method
        if "trade_date" in df.columns:
            assert str(df["trade_date"].dtype).startswith("datetime64"), method


def test_p0b_fund():
    _run_cases(P0B_FUND)


def test_p0b_macro():
    _run_cases(P0B_MACRO)


def test_p0c():
    _run_cases(P0C)


def test_p1_futures():
    _run_cases(P1_FUTURES)


def test_p1_options_bonds():
    _run_cases(P1_OPTIONS_BONDS)


def test_p2():
    _run_cases(P2)


def test_empty_params_are_dropped():
    src, pro = _source()
    src.get_fx_daily(ts_code="", trade_date="20261106", start_date="", end_date=None)
    assert len(pro.calls) == 1
    api, kwargs = pro.calls[0]
    assert api == "fx_daily"
    assert {k: v for k, v in kwargs.items() if k not in ("limit", "offset")} == {
        "trade_date": "20261106"
    }


def test_query_error_raises_not_empty(monkeypatch):
    from shared.sources.tushare_source import TushareQueryError

    src, pro = _source()

    def boom(*args, **kwargs):
        raise RuntimeError("network down")

    monkeypatch.setattr(pro, "query", boom)
    with pytest.raises(TushareQueryError):
        src.get_fx_daily(trade_date="20261106")
