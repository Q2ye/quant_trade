# -*- coding: utf-8 -*-
"""日频数据底座同步 provider（56 张表）。

实现方式：契约驱动。
- 45 张常规表走 ``_sync_ext`` 通用引擎：按 ``DATA_CONTRACTS`` 的
  ``backfill_mode`` 生成日期/月/快照序列，调用 ``_EXT_SPECS`` 里的取数函数；
- 11 张多接口/特殊表走独立方法（macro_rate、资金流 3 张、市场统计、
  THS 成分、期货/期权基础、期货持仓/仓单、南华指数、北向十大）。

``DataSyncService`` 通过继承获得这些方法，并在 ``_sync_method_map`` 注册 56 条路由。
"""

from __future__ import annotations

import math
from datetime import date, datetime, timedelta
from typing import Any, Callable, Dict, List, Optional, Tuple

import pandas as pd
from sqlalchemy import select

from modules.data.constants import DataSource
from modules.data.data_contracts import DATA_CONTRACTS, DataContract
from shared.database.repositories.market.ext import REPO_BY_TABLE

_FUT_EXCHANGES = ("CFFEX", "SHFE", "DCE", "CZCE", "INE", "GFEX")
_OPT_EXCHANGES = ("SSE", "SZSE", "CFFEX", "DCE", "CZCE", "SHFE", "INE")
_NANHUA_CODES = ("NHCI.NH", "NHAI.NH", "NHFI.NH", "NHII.NH", "NHMI.NH",
                 "NHNFI.NH", "NHPMI.NH")

# 通用引擎：data_type -> (模式, 取数函数)
# 取数函数签名：
#   by_date       f(source, d)            d = YYYYMMDD
#   by_range      f(source, a, b)         a/b = YYYYMMDD
#   by_month      f(source, a, b)         a/b = YYYYMM
#   full_snapshot f(source)
_EXT_SPECS: Dict[str, Tuple[str, Callable]] = {
    # ---------- P0b ----------
    "fx_basic": ("full_snapshot", lambda s: s.get_fx_obasic()),
    "fx_daily": ("by_date", lambda s, d: s.get_fx_daily(trade_date=d)),
    "fund_nav": ("by_date", lambda s, d: s.get_fund_nav(nav_date=d)),
    "stock_margin_detail": ("by_date", lambda s, d: s.get_margin_detail(trade_date=d)),
    "stock_margin_secs": ("by_date", lambda s, d: s.get_margin_secs(trade_date=d)),
    "stock_namechange": ("by_range", lambda s, a, b: s.get_namechange(start_date=a, end_date=b)),
    "stock_new_share": ("by_range", lambda s, a, b: s.get_new_share(start_date=a, end_date=b)),
    "index_monthly": ("by_date", lambda s, d: s.get_index_monthly(trade_date=d)),
    "macro_sf": ("by_month", lambda s, a, b: s.get_sf_month(start_m=a, end_m=b)),
    "macro_money": ("by_month", lambda s, a, b: s.get_cn_m(start_m=a, end_m=b)),
    "macro_pmi": ("by_month", lambda s, a, b: s.get_cn_pmi(start_m=a, end_m=b)),
    # ---------- P0c ----------
    "stock_top_list": ("by_date", lambda s, d: s.get_top_list(trade_date=d)),
    "stock_top_inst": ("by_date", lambda s, d: s.get_top_inst(trade_date=d)),
    "stock_cyq_perf": ("by_date", lambda s, d: s.get_cyq_perf(trade_date=d)),
    "index_ths": ("full_snapshot", lambda s: s.get_ths_index()),
    "index_ths_daily": ("by_date", lambda s, d: s.get_ths_daily(trade_date=d)),
    # ---------- P1 ----------
    "stock_block_trade": ("by_date", lambda s, d: s.get_block_trade(trade_date=d)),
    "index_global_daily": ("by_date", lambda s, d: s.get_index_global(trade_date=d)),
    "fut_daily": ("by_date", lambda s, d: s.get_fut_daily(trade_date=d)),
    "fut_settle": ("by_date", lambda s, d: s.get_fut_settle(trade_date=d)),
    "fut_mapping": ("by_date", lambda s, d: s.get_fut_mapping(trade_date=d)),
    "opt_daily": ("by_date", lambda s, d: s.get_opt_daily(trade_date=d)),
    "cb_basic": ("full_snapshot", lambda s: s.get_cb_basic()),
    "cb_issue": ("by_range", lambda s, a, b: s.get_cb_issue(start_date=a, end_date=b)),
    "cb_call": ("by_range", lambda s, a, b: s.get_cb_call(start_date=a, end_date=b)),
    "cb_daily": ("by_date", lambda s, d: s.get_cb_daily(trade_date=d)),
    "cb_share": ("by_range", lambda s, a, b: s.get_cb_share(end_date=b)),
    "cb_rating": ("by_range", lambda s, a, b: s.get_cb_rating(rating_date=b)),
    # ---------- P2 ----------
    "stock_pledge_detail": ("by_range", lambda s, a, b: s.get_pledge_detail(start_date=a, end_date=b)),
    "stock_repurchase": ("by_range", lambda s, a, b: s.get_repurchase(start_date=a, end_date=b)),
    "stock_surv": ("by_range", lambda s, a, b: s.get_stk_surv(start_date=a, end_date=b)),
    "stock_kpl_list": ("by_date", lambda s, d: s.get_kpl_list(trade_date=d)),
    "stock_hm_list": ("full_snapshot", lambda s: s.get_hm_list()),
    "macro_eco_cal": ("by_range", lambda s, a, b: s.get_eco_cal(start_date=a, end_date=b)),
    "hk_basic": ("full_snapshot", lambda s: s.get_hk_basic()),
    "hk_daily": ("by_date", lambda s, d: s.get_hk_daily(trade_date=d)),
    "us_basic": ("full_snapshot", lambda s: s.get_us_basic()),
    "us_daily": ("by_date", lambda s, d: s.get_us_daily(trade_date=d)),
    "ggt_daily": ("by_date", lambda s, d: s.get_ggt_daily(trade_date=d)),
    "fund_basic": ("full_snapshot", lambda s: s.get_fund_basic()),
    "fund_company": ("full_snapshot", lambda s: s.get_fund_company()),
    "fund_manager": ("by_range", lambda s, a, b: s.get_fund_manager(ann_date=b)),
    "fund_div": ("by_range", lambda s, a, b: s.get_fund_div(ann_date=b)),
    "fund_share": ("by_date", lambda s, d: s.get_fund_share(trade_date=d)),
    "fund_daily_ex": ("by_date", lambda s, d: s.get_fund_daily(trade_date=d)),
}


def _norm_date(value: Any) -> Optional[date]:
    if value is None:
        return None
    if isinstance(value, datetime):
        return value.date()
    if isinstance(value, date):
        return value
    if isinstance(value, pd.Timestamp):
        return None if pd.isna(value) else value.date()
    return value


def _clean_record(record: Dict[str, Any]) -> Dict[str, Any]:
    for key, value in record.items():
        if isinstance(value, float) and math.isnan(value):
            record[key] = None
        elif isinstance(value, pd.Timestamp):
            record[key] = None if pd.isna(value) else value.date()
        elif value is not None and not isinstance(value, (list, dict)):
            try:
                if pd.isna(value):
                    record[key] = None
            except (TypeError, ValueError):
                pass
    return record


class DailyBaseSyncProvider:
    """日频数据底座同步方法（由 DataSyncService 继承）。"""

    # ---- 初始化 ----

    def _init_daily_base_repos(self) -> None:
        self._ext_repos = {t: cls(self.session) for t, cls in REPO_BY_TABLE.items()}

    def _register_daily_base_sync(self) -> None:
        from functools import partial

        from modules.data.constants import DataType

        special = {
            "macro_rate": self._sync_macro_rate,
            "stock_moneyflow_ext": self._sync_stock_moneyflow_ext,
            "stock_moneyflow_ind": self._sync_stock_moneyflow_ind,
            "market_daily_info": self._sync_market_daily_info,
            "index_ths_member": self._sync_index_ths_member,
            "fut_basic": self._sync_fut_basic,
            "opt_basic": self._sync_opt_basic,
            "fut_holding": self._sync_fut_holding,
            "fut_wsr": self._sync_fut_wsr,
            "fut_index_daily": self._sync_fut_index_daily,
            "stock_hsgt_top10": self._sync_stock_hsgt_top10,
        }
        for key in DATA_CONTRACTS:
            method = special.get(key)
            self._sync_method_map[DataType(key)] = (
                method if method is not None else partial(self._sync_ext, key)
            )

    # ---- 通用工具 ----

    def _ext_source(self):
        return self.source_factory.get_source(DataSource.TUSHARE)

    def _resolve_ext_range(
        self, start_date: Optional[date], end_date: Optional[date]
    ) -> Tuple[date, date]:
        end = end_date or date.today()
        start = start_date or end
        if start > end:
            start, end = end, start
        return start, end

    async def _ext_trade_dates(self, start: date, end: date) -> List[date]:
        if start > end:
            return []
        try:
            days = await self.trade_calendar_repo.get_trade_dates("SSE", start, end)
        except Exception:
            days = []
        if days:
            return days
        out: List[date] = []
        cur = start
        while cur <= end:
            if cur.weekday() < 5:
                out.append(cur)
            cur += timedelta(days=1)
        return out

    @staticmethod
    def _ext_months(start: date, end: date) -> List[str]:
        out: List[str] = []
        y, m = start.year, start.month
        while (y, m) <= (end.year, end.month):
            out.append(f"{y:04d}{m:02d}")
            m += 1
            if m > 12:
                y, m = y + 1, 1
        return out

    def _records_from_df(
        self, df: Optional[pd.DataFrame], transform: Optional[Callable] = None
    ) -> List[Dict[str, Any]]:
        if df is None or df.empty:
            return []
        out: List[Dict[str, Any]] = []
        for row in df.to_dict("records"):
            record = transform(row) if transform else row
            record = {str(k): v for k, v in record.items()}
            out.append(_clean_record(record))
        return out

    async def _upsert_ext(
        self, repo, records: List[Dict[str, Any]], label: str
    ) -> int:
        if not records:
            return 0
        from modules.data.services.sync_service import _drop_unstorable_records

        records = _drop_unstorable_records(records, repo.model, label)
        if not records:
            return 0
        written = await repo.bulk_upsert(records)
        await self.session.commit()
        return written

    def _result(self, label: str, written: int, total: int) -> Dict[str, Any]:
        return {
            "records_added": written,
            "records_updated": 0,
            "records_failed": max(0, total - written),
            "total_items": total,
            "message": f"{label} 同步完成",
        }

    # ---- 通用引擎 ----

    async def _sync_ext(
        self,
        data_type: str,
        start_date: Optional[date] = None,
        end_date: Optional[date] = None,
        ts_codes: Optional[List[str]] = None,
        task_id: Optional[str] = None,
        user_id: Optional[str] = None,
        **kwargs,
    ) -> Dict[str, Any]:
        contract = DATA_CONTRACTS[data_type]
        mode, fetch = _EXT_SPECS[data_type]
        repo = self._ext_repos[contract.table]
        source = self._ext_source()
        start, end = self._resolve_ext_range(start_date, end_date)
        records: List[Dict[str, Any]] = []

        if mode == "by_date":
            for d in await self._ext_trade_dates(start, end):
                if self.cancel_token is not None and self.cancel_token.is_set():
                    break
                df = await self._cancellable_run_in_executor(
                    fetch, source, d.strftime("%Y%m%d")
                )
                records.extend(self._records_from_df(df, self._transform_for(data_type)))
        elif mode == "by_range":
            df = await self._cancellable_run_in_executor(
                fetch, source, start.strftime("%Y%m%d"), end.strftime("%Y%m%d")
            )
            records.extend(self._records_from_df(df, self._transform_for(data_type)))
        elif mode == "by_month":
            for m in self._ext_months(start, end):
                if self.cancel_token is not None and self.cancel_token.is_set():
                    break
                df = await self._cancellable_run_in_executor(fetch, source, m)
                records.extend(self._records_from_df(df, self._transform_for(data_type)))
        elif mode == "full_snapshot":
            df = await self._cancellable_run_in_executor(fetch, source)
            records.extend(self._records_from_df(df, self._transform_for(data_type)))
        else:
            raise ValueError(f"未知回填模式: {mode} ({data_type})")

        written = await self._upsert_ext(repo, records, contract.table)
        return self._result(contract.table, written, len(records))

    def _transform_for(self, data_type: str):
        return _EXT_TRANSFORMS.get(data_type)

    # ---- 特殊表：多接口 ----

    async def _sync_macro_rate(self, start_date=None, end_date=None, ts_codes=None,
                               task_id=None, user_id=None, **kwargs) -> Dict[str, Any]:
        source = self._ext_source()
        start, end = self._resolve_ext_range(start_date, end_date)
        a, b = start.strftime("%Y%m%d"), end.strftime("%Y%m%d")
        repo = self._ext_repos["macro_rate"]
        plans = (
            ("shibor", "CNY", source.get_shibor,
             {"on": "ON", "1w": "1W", "2w": "2W", "1m": "1M", "3m": "3M",
              "6m": "6M", "9m": "9M", "1y": "1Y"}),
            ("libor", None, source.get_libor,
             {"on": "ON", "1w": "1W", "1m": "1M", "2m": "2M", "3m": "3M",
              "6m": "6M", "12m": "12M"}),
            ("hibor", "HKD", source.get_hibor,
             {"on": "ON", "1w": "1W", "2w": "2W", "1m": "1M", "2m": "2M",
              "3m": "3M", "6m": "6M", "12m": "12M"}),
            ("us_tbr", "USD", source.get_us_tbr,
             {"w4_bd": "W4_BD", "w4_ce": "W4_CE", "w8_bd": "W8_BD", "w8_ce": "W8_CE",
              "w13_bd": "W13_BD", "w13_ce": "W13_CE", "w17_bd": "W17_BD",
              "w17_ce": "W17_CE", "w26_bd": "W26_BD", "w26_ce": "W26_CE",
              "w52_bd": "W52_BD", "w52_ce": "W52_CE"}),
            ("us_tycr", "USD", source.get_us_tycr,
             {"m1": "M1", "m2": "M2", "m3": "M3", "m4": "M4", "m6": "M6",
              "y1": "Y1", "y2": "Y2", "y3": "Y3", "y5": "Y5", "y7": "Y7",
              "y10": "Y10", "y20": "Y20", "y30": "Y30"}),
        )
        records: List[Dict[str, Any]] = []
        for src_name, fixed_ccy, fn, tenors in plans:
            df = await self._cancellable_run_in_executor(
                fn, start_date=a, end_date=b
            )
            if df is None or df.empty:
                continue
            for row in df.to_dict("records"):
                d = _norm_date(row.get("date"))
                if d is None:
                    continue
                ccy = row.get("curr_type") or fixed_ccy or "USD"
                for col, tenor in tenors.items():
                    val = row.get(col)
                    if val is None or (isinstance(val, float) and math.isnan(val)):
                        continue
                    records.append({
                        "trade_date": d, "source": src_name, "currency": str(ccy),
                        "tenor": tenor, "value": val,
                    })
        written = await self._upsert_ext(repo, records, "macro_rate")
        return self._result("macro_rate", written, len(records))

    async def _sync_stock_moneyflow_ext(self, start_date=None, end_date=None,
                                        ts_codes=None, task_id=None, user_id=None,
                                        **kwargs) -> Dict[str, Any]:
        source = self._ext_source()
        start, end = self._resolve_ext_range(start_date, end_date)
        repo = self._ext_repos["stock_moneyflow_ext"]
        records: List[Dict[str, Any]] = []
        for d in await self._ext_trade_dates(start, end):
            if self.cancel_token is not None and self.cancel_token.is_set():
                break
            ds = d.strftime("%Y%m%d")
            for src_name, fn in (("dc", source.get_moneyflow_dc),
                                 ("ths", source.get_moneyflow_ths)):
                df = await self._cancellable_run_in_executor(fn, trade_date=ds)
                records.extend(
                    self._records_from_df(df, lambda r, s=src_name: {
                        **r, "source": s, "trade_date": _norm_date(r.get("trade_date")) or d
                    })
                )
        written = await self._upsert_ext(repo, records, "stock_moneyflow_ext")
        return self._result("stock_moneyflow_ext", written, len(records))

    async def _sync_stock_moneyflow_ind(self, start_date=None, end_date=None,
                                        ts_codes=None, task_id=None, user_id=None,
                                        **kwargs) -> Dict[str, Any]:
        source = self._ext_source()
        start, end = self._resolve_ext_range(start_date, end_date)
        repo = self._ext_repos["stock_moneyflow_ind"]
        plans = (("ind_dc", source.get_moneyflow_ind_dc),
                 ("ind_ths", source.get_moneyflow_ind_ths),
                 ("cnt_ths", source.get_moneyflow_cnt_ths))
        records: List[Dict[str, Any]] = []
        for d in await self._ext_trade_dates(start, end):
            if self.cancel_token is not None and self.cancel_token.is_set():
                break
            ds = d.strftime("%Y%m%d")
            for src_name, fn in plans:
                df = await self._cancellable_run_in_executor(fn, trade_date=ds)
                records.extend(
                    self._records_from_df(df, lambda r, s=src_name: {
                        **r, "source": s, "trade_date": _norm_date(r.get("trade_date")) or d
                    })
                )
        written = await self._upsert_ext(repo, records, "stock_moneyflow_ind")
        return self._result("stock_moneyflow_ind", written, len(records))

    async def _sync_market_daily_info(self, start_date=None, end_date=None,
                                      ts_codes=None, task_id=None, user_id=None,
                                      **kwargs) -> Dict[str, Any]:
        source = self._ext_source()
        start, end = self._resolve_ext_range(start_date, end_date)
        repo = self._ext_repos["market_daily_info"]
        records: List[Dict[str, Any]] = []
        for d in await self._ext_trade_dates(start, end):
            if self.cancel_token is not None and self.cancel_token.is_set():
                break
            ds = d.strftime("%Y%m%d")
            sh = await self._cancellable_run_in_executor(source.get_daily_info, trade_date=ds)
            records.extend(self._records_from_df(sh, lambda r: {
                **r, "source": "sse", "exchange": r.get("exchange") or "SSE",
                "trade_date": _norm_date(r.get("trade_date")) or d,
            }))
            sz = await self._cancellable_run_in_executor(source.get_sz_daily_info, trade_date=ds)
            records.extend(self._records_from_df(sz, lambda r: {
                **r,
                "source": "szse", "exchange": "SZSE",
                "ts_name": r.get("ts_name") or r.get("ts_code"),
                "com_count": r.get("com_count") or r.get("count"),
                "trade_date": _norm_date(r.get("trade_date")) or d,
            }))
        written = await self._upsert_ext(repo, records, "market_daily_info")
        return self._result("market_daily_info", written, len(records))

    async def _sync_index_ths_member(self, start_date=None, end_date=None,
                                     ts_codes=None, task_id=None, user_id=None,
                                     **kwargs) -> Dict[str, Any]:
        source = self._ext_source()
        start, end = self._resolve_ext_range(start_date, end_date)
        repo = self._ext_repos["index_ths_member"]
        index_df = await self._cancellable_run_in_executor(source.get_ths_index)
        codes = [] if index_df is None or index_df.empty else list(index_df["ts_code"])
        if not codes:
            return self._result("index_ths_member", 0, 0)
        records: List[Dict[str, Any]] = []
        for d in await self._ext_trade_dates(start, end):
            if self.cancel_token is not None and self.cancel_token.is_set():
                break
            for code in codes:
                df = await self._cancellable_run_in_executor(
                    source.get_ths_member, ts_code=code
                )
                records.extend(self._records_from_df(df, lambda r, c=code, sd=d: {
                    **r, "index_code": c, "snapshot_date": sd,
                }))
        written = await self._upsert_ext(repo, records, "index_ths_member")
        return self._result("index_ths_member", written, len(records))

    # ---- 特殊表：目录需按交易所循环 ----

    async def _sync_fut_basic(self, start_date=None, end_date=None, ts_codes=None,
                              task_id=None, user_id=None, **kwargs) -> Dict[str, Any]:
        source = self._ext_source()
        repo = self._ext_repos["fut_basic"]
        records: List[Dict[str, Any]] = []
        for ex in _FUT_EXCHANGES:
            df = await self._cancellable_run_in_executor(
                source.get_fut_basic, exchange=ex
            )
            records.extend(self._records_from_df(df))
        written = await self._upsert_ext(repo, records, "fut_basic")
        return self._result("fut_basic", written, len(records))

    async def _sync_opt_basic(self, start_date=None, end_date=None, ts_codes=None,
                              task_id=None, user_id=None, **kwargs) -> Dict[str, Any]:
        source = self._ext_source()
        repo = self._ext_repos["opt_basic"]
        records: List[Dict[str, Any]] = []
        for ex in _OPT_EXCHANGES:
            df = await self._cancellable_run_in_executor(
                source.get_opt_basic, exchange=ex
            )
            records.extend(self._records_from_df(df))
        written = await self._upsert_ext(repo, records, "opt_basic")
        return self._result("opt_basic", written, len(records))

    async def _fut_symbol_pairs(self) -> List[Tuple[str, str]]:
        model = self._ext_repos["fut_basic"].model
        rows = (await self.session.execute(
            select(model.symbol, model.exchange).distinct()
        )).all()
        pairs = [(r[0], r[1]) for r in rows if r[0] and r[1]]
        if pairs:
            return pairs
        return [("IF", "CFFEX"), ("CU", "SHFE"), ("M", "DCE"),
                ("SR", "CZCE"), ("SC", "INE")]

    async def _sync_fut_holding(self, start_date=None, end_date=None, ts_codes=None,
                                task_id=None, user_id=None, **kwargs) -> Dict[str, Any]:
        source = self._ext_source()
        start, end = self._resolve_ext_range(start_date, end_date)
        repo = self._ext_repos["fut_holding"]
        pairs = await self._fut_symbol_pairs()
        records: List[Dict[str, Any]] = []
        for d in await self._ext_trade_dates(start, end):
            if self.cancel_token is not None and self.cancel_token.is_set():
                break
            ds = d.strftime("%Y%m%d")
            for symbol, exchange in pairs:
                df = await self._cancellable_run_in_executor(
                    source.get_fut_holding, trade_date=ds,
                    symbol=symbol, exchange=exchange,
                )
                records.extend(self._records_from_df(df, lambda r, ex=exchange: {
                    **r, "exchange": ex,
                }))
        written = await self._upsert_ext(repo, records, "fut_holding")
        return self._result("fut_holding", written, len(records))

    async def _sync_fut_wsr(self, start_date=None, end_date=None, ts_codes=None,
                            task_id=None, user_id=None, **kwargs) -> Dict[str, Any]:
        source = self._ext_source()
        start, end = self._resolve_ext_range(start_date, end_date)
        repo = self._ext_repos["fut_wsr"]
        pairs = await self._fut_symbol_pairs()
        records: List[Dict[str, Any]] = []
        for d in await self._ext_trade_dates(start, end):
            if self.cancel_token is not None and self.cancel_token.is_set():
                break
            ds = d.strftime("%Y%m%d")
            for symbol, exchange in pairs:
                df = await self._cancellable_run_in_executor(
                    source.get_fut_wsr, trade_date=ds,
                    symbol=symbol, exchange=exchange,
                )
                records.extend(self._records_from_df(df, lambda r, ex=exchange: {
                    **r, "exchange": ex,
                }))
        written = await self._upsert_ext(repo, records, "fut_wsr")
        return self._result("fut_wsr", written, len(records))

    async def _sync_fut_index_daily(self, start_date=None, end_date=None,
                                    ts_codes=None, task_id=None, user_id=None,
                                    **kwargs) -> Dict[str, Any]:
        source = self._ext_source()
        start, end = self._resolve_ext_range(start_date, end_date)
        a, b = start.strftime("%Y%m%d"), end.strftime("%Y%m%d")
        repo = self._ext_repos["fut_index_daily"]
        records: List[Dict[str, Any]] = []
        for code in _NANHUA_CODES:
            df = await self._cancellable_run_in_executor(
                source.get_fut_index_daily, ts_code=code,
                start_date=a, end_date=b,
            )
            records.extend(self._records_from_df(df))
        written = await self._upsert_ext(repo, records, "fut_index_daily")
        return self._result("fut_index_daily", written, len(records))

    async def _sync_stock_hsgt_top10(self, start_date=None, end_date=None,
                                     ts_codes=None, task_id=None, user_id=None,
                                     **kwargs) -> Dict[str, Any]:
        source = self._ext_source()
        start, end = self._resolve_ext_range(start_date, end_date)
        repo = self._ext_repos["stock_hsgt_top10"]
        records: List[Dict[str, Any]] = []
        for d in await self._ext_trade_dates(start, end):
            if self.cancel_token is not None and self.cancel_token.is_set():
                break
            ds = d.strftime("%Y%m%d")
            for mt in ("1", "3"):
                df = await self._cancellable_run_in_executor(
                    source.get_hsgt_top10, trade_date=ds, market_type=mt
                )
                records.extend(self._records_from_df(df, lambda r, m=mt: {
                    **r, "market_type": m,
                }))
        written = await self._upsert_ext(repo, records, "stock_hsgt_top10")
        return self._result("stock_hsgt_top10", written, len(records))


# ---- 行级转换（只放非通用的表） ----


def _tf_fx_basic(row: Dict[str, Any]) -> Dict[str, Any]:
    row["target_spread"] = row.pop("traget_spread", None)
    return row


def _tf_fx_daily(row: Dict[str, Any]) -> Dict[str, Any]:
    src = _norm_date(row.get("trade_date"))
    row["source_date"] = src
    if src is not None:
        row["trade_date"] = src + timedelta(days=1)
    return row


def _tf_pmi(row: Dict[str, Any]) -> Dict[str, Any]:
    raw = {k: v for k, v in row.items() if k != "month"}
    row["raw"] = raw
    return row


def _tf_namechange(row: Dict[str, Any]) -> Dict[str, Any]:
    name = row.get("name") or ""
    row["is_st"] = "ST" in name.upper()
    return row


def _tf_hm_list(row: Dict[str, Any]) -> Dict[str, Any]:
    row["description"] = row.pop("desc", None)
    return row


def _tf_eco_cal(row: Dict[str, Any]) -> Dict[str, Any]:
    row["event_date"] = row.pop("date", None)
    row["event_time"] = row.pop("time", None)
    return row


_EXT_TRANSFORMS: Dict[str, Callable] = {
    "fx_basic": _tf_fx_basic,
    "fx_daily": _tf_fx_daily,
    "macro_pmi": _tf_pmi,
    "stock_namechange": _tf_namechange,
    "stock_hm_list": _tf_hm_list,
    "macro_eco_cal": _tf_eco_cal,
}
