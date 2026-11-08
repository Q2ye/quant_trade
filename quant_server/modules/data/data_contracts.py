# -*- coding: utf-8 -*-
"""日频数据底座契约（唯一配置源）。

56 张表的表名、接口、主键、PIT 字段、频率、回填模式、门禁模式、档位与
最早日期集中在这里。同步、回填、门禁三处都只读本文件，不再各写一份配置。

设计文档：``docs/02-功能设计/市场模块/日频数据底座补全-设计文档.md``
实测字段：``docs/09-交付记录/REQ-20261108-daily-data-base/assets/api_probe.md``

约定：
- ``data_type`` 是 ``DataType`` 的值（snake_case），与 ``constants.py`` 一一对应；
- ``api`` 为 tuple 时表示多个接口写入同一张表（如 macro_rate 的 5 个利率接口）；
- ``primary_key`` 是 ``ON CONFLICT`` 的冲突目标，不含 surrogate ``id``；
- ``pit_fields`` 为空表示该表无法做严格 as-of，注释里会说明；
- ``earliest`` 为 ``implementation`` 表示接口无历史，只能从实施日起快照。
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Dict, Tuple

BACKFILL_MODES = ("by_date", "by_month", "by_range", "by_symbol",
                  "full_snapshot", "by_snapshot")
GATE_MODES = ("dense", "sparse", "periodic", "derived")
FREQUENCIES = ("daily", "weekly", "monthly", "quarterly", "catalog", "event", "snapshot")
TIERS = ("P0b", "P0c", "P1", "P2")


@dataclass(frozen=True)
class DataContract:
    """单张表的同步/回填/门禁契约。"""

    data_type: str
    table: str
    api: Tuple[str, ...]
    primary_key: Tuple[str, ...]
    frequency: str
    backfill_mode: str
    gate_mode: str
    tier: str
    earliest: str = ""
    pit_fields: Tuple[str, ...] = field(default_factory=tuple)
    partition: bool = False
    note: str = ""


def _c(data_type: str, table: str, api, pk, frequency: str, backfill_mode: str,
       gate_mode: str, tier: str, earliest: str = "", pit=(), partition: bool = False,
       note: str = "") -> DataContract:
    return DataContract(
        data_type=data_type,
        table=table,
        api=(api,) if isinstance(api, str) else tuple(api),
        primary_key=tuple(pk) if isinstance(pk, (list, tuple)) else (pk,),
        frequency=frequency,
        backfill_mode=backfill_mode,
        gate_mode=gate_mode,
        tier=tier,
        earliest=earliest,
        pit_fields=tuple(pit),
        partition=partition,
        note=note,
    )


_CONTRACTS = [
    # ---------------- P0b 外汇 / 基金 ----------------
    _c("fx_basic", "fx_basic", "fx_obasic", ["ts_code"], "catalog",
       "full_snapshot", "periodic", "P0b", note="源字段 traget_spread 改名 target_spread"),
    _c("fx_daily", "fx_daily", "fx_daily", ["ts_code", "trade_date"], "daily",
       "by_date", "dense", "P0b", "2005-01-01", partition=True,
       note="源 GMT 日期 +1 天转北京业务日"),
    _c("fund_nav", "fund_nav", "fund_nav", ["ts_code", "nav_date"], "daily",
       "by_date", "dense", "P0b", "1990-01-01", pit=["ann_date"],
       note="PIT 用 ann_date；QDII 净值滞后；未做超表"),
    _c("stock_margin_detail", "stock_margin_detail", "margin_detail",
       ["trade_date", "ts_code"], "daily", "by_date", "dense", "P0b", "2010-03-31"),
    _c("stock_margin_secs", "stock_margin_secs", "margin_secs",
       ["trade_date", "ts_code"], "daily", "by_date", "dense", "P0b", "2010-03-31"),
    _c("stock_namechange", "stock_namechange", "namechange",
       ["ts_code", "start_date", "name"], "event", "by_range", "sparse", "P0b",
       "1990-01-01", pit=["ann_date"]),
    _c("stock_new_share", "stock_new_share", "new_share", ["ts_code"], "event",
       "by_range", "sparse", "P0b", "1990-01-01", pit=["ipo_date"]),
    _c("index_monthly", "index_monthly", "index_monthly", ["ts_code", "trade_date"],
       "monthly", "by_date", "periodic", "P0b", "1990-01-01"),
    _c("macro_rate", "macro_rate", ("shibor", "libor", "hibor", "us_tbr", "us_tycr"),
       ["trade_date", "source", "currency", "tenor"], "daily", "by_date", "dense",
       "P0b", "2006-01-01", note="宽表按期限拆长表"),
    _c("macro_sf", "macro_sf", "sf_month", ["month"], "monthly", "by_month",
       "periodic", "P0b", "2002-01-01"),
    _c("macro_money", "macro_money", "cn_m", ["month"], "monthly", "by_month",
       "periodic", "P0b", "1990-01-01"),
    _c("macro_pmi", "macro_pmi", "cn_pmi", ["month"], "monthly", "by_month",
       "periodic", "P0b", "2005-01-01", note="常用分项独立列，其余进 raw JSONB"),

    # ---------------- P0c 龙虎榜 / 筹码 / THS / 资金流 / 市场统计 ----------------
    _c("stock_top_list", "stock_top_list", "top_list",
       ["trade_date", "ts_code", "reason"], "daily", "by_date", "sparse", "P0c",
       "2010-01-04"),
    _c("stock_top_inst", "stock_top_inst", "top_inst",
       ["trade_date", "ts_code", "exalter", "side", "reason"], "daily", "by_date",
       "sparse", "P0c", "2010-01-04"),
    _c("stock_cyq_perf", "stock_cyq_perf", "cyq_perf", ["ts_code", "trade_date"],
       "daily", "by_date", "dense", "P0c", "2018-01-01", partition=True),
    _c("index_ths", "index_ths", "ths_index", ["ts_code"], "catalog",
       "full_snapshot", "periodic", "P0c"),
    _c("index_ths_daily", "index_ths_daily", "ths_daily", ["ts_code", "trade_date"],
       "daily", "by_date", "dense", "P0c", "2015-01-01", partition=True),
    _c("index_ths_member", "index_ths_member", "ths_member",
       ["snapshot_date", "index_code", "con_code"], "snapshot", "by_snapshot",
       "sparse", "P0c", "implementation",
       note="NON_PIT：接口无 in/out_date、无 weight，只能前向快照"),
    _c("stock_moneyflow_ext", "stock_moneyflow_ext", ("moneyflow_dc", "moneyflow_ths"),
       ["trade_date", "ts_code", "source"], "daily", "by_date", "dense", "P0c",
       "2024-01-01", partition=True, note="DC/THS 双口径，字段并集"),
    _c("stock_moneyflow_ind", "stock_moneyflow_ind",
       ("moneyflow_ind_dc", "moneyflow_ind_ths", "moneyflow_cnt_ths"),
       ["trade_date", "ts_code", "source"], "daily", "by_date", "sparse", "P0c",
       "2024-01-01"),
    _c("market_daily_info", "market_daily_info", ("daily_info", "sz_daily_info"),
       ["trade_date", "ts_code", "source"], "daily", "by_date", "periodic", "P0c",
       "2010-01-01"),

    # ---------------- P1 大宗 / 全球指数 / 期货 / 期权 / 转债 / 北向十大 ----------------
    _c("stock_block_trade", "stock_block_trade", "block_trade",
       ["trade_date", "ts_code", "price", "vol", "buyer", "seller"], "daily",
       "by_date", "sparse", "P1", "2000-01-01"),
    _c("index_global_daily", "index_global_daily", "index_global",
       ["ts_code", "trade_date"], "daily", "by_date", "dense", "P1", "2000-01-01"),
    _c("fut_basic", "fut_basic", "fut_basic", ["ts_code"], "catalog",
       "full_snapshot", "periodic", "P1", pit=["list_date", "delist_date"]),
    _c("fut_daily", "fut_daily", "fut_daily", ["ts_code", "trade_date"], "daily",
       "by_date", "dense", "P1", "2000-01-04", partition=True),
    _c("fut_holding", "fut_holding", "fut_holding",
       ["trade_date", "symbol", "broker", "exchange"], "daily", "by_date", "sparse",
       "P1", "2018-01-01"),
    _c("fut_wsr", "fut_wsr", "fut_wsr",
       ["trade_date", "symbol", "warehouse", "fut_name", "unit", "exchange"],
       "daily", "by_date", "sparse", "P1", "2018-01-01"),
    _c("fut_settle", "fut_settle", "fut_settle", ["ts_code", "trade_date"], "daily",
       "by_date", "dense", "P1", "2018-01-01"),
    _c("fut_mapping", "fut_mapping", "fut_mapping", ["ts_code", "trade_date"],
       "daily", "by_date", "sparse", "P1", "2018-01-01"),
    _c("fut_index_daily", "fut_index_daily", "fut_index_daily",
       ["ts_code", "trade_date"], "daily", "by_date", "dense", "P1"),
    _c("opt_basic", "opt_basic", "opt_basic", ["ts_code"], "catalog",
       "full_snapshot", "periodic", "P1", pit=["list_date", "delist_date"]),
    _c("opt_daily", "opt_daily", "opt_daily", ["ts_code", "trade_date"], "daily",
       "by_date", "dense", "P1", "2015-02-09", partition=True),
    _c("cb_basic", "cb_basic", "cb_basic", ["ts_code"], "catalog",
       "full_snapshot", "periodic", "P1", pit=["list_date", "delist_date"]),
    _c("cb_issue", "cb_issue", "cb_issue", ["ts_code"], "event", "by_range",
       "sparse", "P1", "2018-01-01", pit=["ann_date"]),
    _c("cb_call", "cb_call", "cb_call", ["ts_code", "call_type", "ann_date"],
       "event", "by_range", "sparse", "P1", "2018-01-01", pit=["ann_date"]),
    _c("cb_daily", "cb_daily", "cb_daily", ["ts_code", "trade_date"], "daily",
       "by_date", "dense", "P1", "2018-01-02", partition=True),
    _c("cb_share", "cb_share", "cb_share", ["ts_code", "end_date"], "event",
       "by_range", "sparse", "P1", "2018-01-01", pit=["publish_date"]),
    _c("cb_rating", "cb_rating", "cb_rating",
       ["ts_code", "rating_date", "rating_com_name"], "event", "by_range", "sparse",
       "P1", "2018-01-01", pit=["ann_date"]),
    _c("stock_hsgt_top10", "stock_hsgt_top10", "hsgt_top10",
       ["trade_date", "ts_code"], "daily", "by_date", "sparse", "P1", "2016-01-01"),

    # ---------------- P2 事件 / 港美股 / 基金 ----------------
    _c("stock_pledge_detail", "stock_pledge_detail", "pledge_detail",
       ["ts_code", "ann_date", "holder_name", "start_date"], "event", "by_range",
       "sparse", "P2", "2020-01-01", pit=["ann_date"]),
    _c("stock_repurchase", "stock_repurchase", "repurchase",
       ["ts_code", "ann_date", "end_date", "proc"], "event", "by_range", "sparse",
       "P2", "2020-01-01", pit=["ann_date"]),
    _c("stock_surv", "stock_surv", "stk_surv",
       ["ts_code", "surv_date", "rece_org"], "event", "by_range", "sparse", "P2",
       "2020-01-01", pit=["surv_date"]),
    _c("stock_kpl_list", "stock_kpl_list", "kpl_list", ["trade_date", "ts_code"],
       "daily", "by_date", "sparse", "P2", "2018-01-01"),
    _c("stock_hm_list", "stock_hm_list", "hm_list", ["name"], "catalog",
       "full_snapshot", "periodic", "P2"),
    _c("macro_eco_cal", "macro_eco_cal", "eco_cal", ["event_date", "currency", "event"],
       "event", "by_range", "sparse", "P2", "2019-01-01"),
    _c("hk_basic", "hk_basic", "hk_basic", ["ts_code"], "catalog",
       "full_snapshot", "periodic", "P2", pit=["list_date", "delist_date"]),
    _c("hk_daily", "hk_daily", "hk_daily", ["ts_code", "trade_date"], "daily",
       "by_date", "dense", "P2", "2005-01-04", note="接口限 1 次/小时"),
    _c("us_basic", "us_basic", "us_basic", ["ts_code"], "catalog",
       "full_snapshot", "periodic", "P2", pit=["list_date", "delist_date"]),
    _c("us_daily", "us_daily", "us_daily", ["ts_code", "trade_date"], "daily",
       "by_date", "dense", "P2", "2005-01-04", note="字段为 pct_change；限 1 次/小时"),
    _c("ggt_daily", "ggt_daily", "ggt_daily", ["trade_date"], "daily", "by_date",
       "dense", "P2", "2014-11-17"),
    _c("fund_basic", "fund_basic", "fund_basic", ["ts_code"], "catalog",
       "full_snapshot", "periodic", "P2", pit=["list_date", "delist_date"]),
    _c("fund_company", "fund_company", "fund_company", ["name"], "catalog",
       "full_snapshot", "periodic", "P2"),
    _c("fund_manager", "fund_manager", "fund_manager",
       ["ts_code", "ann_date", "name", "begin_date"], "event", "by_range", "sparse",
       "P2", pit=["ann_date"]),
    _c("fund_div", "fund_div", "fund_div", ["ts_code", "ann_date", "div_proc"],
       "event", "by_range", "sparse", "P2", pit=["ann_date"],
       note="主键用 ann_date 而非 ex_date（后者可空）"),
    _c("fund_share", "fund_share", "fund_share", ["ts_code", "trade_date"], "daily",
       "by_date", "dense", "P2"),
    _c("fund_daily_ex", "fund_daily_ex", "fund_daily", ["ts_code", "trade_date"],
       "daily", "by_date", "dense", "P2", "2005-01-04",
       note="仅非 ETF；ETF 仍由 etf_daily 承载"),
]

DATA_CONTRACTS: Dict[str, DataContract] = {c.data_type: c for c in _CONTRACTS}
CONTRACTS_BY_TABLE: Dict[str, DataContract] = {c.table: c for c in _CONTRACTS}


def get_contract(data_type: str) -> DataContract:
    """按 DataType 值取契约；不存在时抛 KeyError，调用方负责转成业务错误。"""
    return DATA_CONTRACTS[data_type]


def contracts_by_tier(tier: str) -> Tuple[DataContract, ...]:
    return tuple(c for c in _CONTRACTS if c.tier == tier)


def all_tables() -> Tuple[str, ...]:
    return tuple(c.table for c in _CONTRACTS)
