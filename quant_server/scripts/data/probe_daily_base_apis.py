# -*- coding: utf-8 -*-
"""日频数据底座接口探针（63 个 Tushare 接口）。

用途：
1. 验证当前 token 对每个接口的访问权限；
2. 抓取每个接口真实返回的字段名，作为 DDL / DATA_CONTRACTS 的依据；
3. 一次实调即可产出可审计的 markdown 报告。

设计要点：
- 不依赖 ``shared.sources``，直接用 ``ts.pro_api(token).query``，避免把探针绑在
  尚未实现的取数方法上；
- 对按日接口，从最近 10 个工作日倒序尝试，直到拿到非空结果（稀疏接口如龙虎榜、
  大宗交易用得上）；
- ``ok`` = 接口可访问（含返回空表），``gap`` = 权限/参数/网络等错误。
  退出码 0 仅当 ``gap=0``。

用法：
  cd quant_server
  .venv/Scripts/python.exe scripts/data/probe_daily_base_apis.py --all
  .venv/Scripts/python.exe scripts/data/probe_daily_base_apis.py --all --out ../docs/.../api_probe.md
"""

from __future__ import annotations

import argparse
import sys
import time
from datetime import date, timedelta
from pathlib import Path
from typing import Any, Dict, List, Optional

SCRIPT_DIR = Path(__file__).resolve().parent
SERVER_DIR = SCRIPT_DIR.parents[1]
REPO_ROOT = SERVER_DIR.parent
ENV_PATH = SERVER_DIR / ".env"
DEFAULT_OUT = (
    REPO_ROOT / "docs" / "09-交付记录" / "REQ-20261108-daily-data-base"
    / "assets" / "api_probe.md"
)

SLEEP_SEC = 0.25
MAX_RETRY = 2
PERMISSION_KEYWORDS = ("权限", "积分", "没有访问", "无权", "not permitted", "permission")
RATE_LIMIT_KEYWORDS = ("频率超限", "访问受限", "每分钟", "每秒")


def load_env(path: Path) -> Dict[str, str]:
    env: Dict[str, str] = {}
    if not path.exists():
        return env
    for line in path.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        k, v = line.split("=", 1)
        env[k.strip()] = v.strip()
    return env


def weekdays_before(end: date, count: int) -> List[str]:
    out: List[str] = []
    cur = end
    while len(out) < count:
        if cur.weekday() < 5:
            out.append(cur.strftime("%Y%m%d"))
        cur -= timedelta(days=1)
    return out


SAMPLE_DATES = weekdays_before(date(2026, 11, 6), 10)
RANGE_START = "20260901"
RANGE_END = "20261106"
MONTH_START = "202608"
MONTH_END = "202610"

# 每个 spec:
#   api     Tushare 接口名
#   table   目标表名（写入报告，便于对契约）
#   kind    catalog / date / range / month / custom
#   params  固定参数；date 模式会追加 date_key，range/month 会追加起止
#   date_key date 模式的日期字段名（默认 trade_date）
#   note    备注
SPECS: List[Dict[str, Any]] = [
    # ---------- P0b 外汇 / 基金 ----------
    {"api": "fx_obasic", "table": "fx_basic", "kind": "catalog", "params": {"exchange": "FXCM"}},
    {"api": "fx_daily", "table": "fx_daily", "kind": "date"},
    {"api": "fund_nav", "table": "fund_nav", "kind": "date", "date_key": "nav_date"},
    {"api": "fund_basic", "table": "fund_basic", "kind": "catalog", "params": {"market": "E"}},
    {"api": "fund_company", "table": "fund_company", "kind": "catalog"},
    {"api": "fund_manager", "table": "fund_manager", "kind": "catalog", "params": {"ts_code": "000001.OF"}},
    {"api": "fund_div", "table": "fund_div", "kind": "custom",
     "params": {"ts_code": "000001.OF"}},
    {"api": "fund_share", "table": "fund_share", "kind": "date"},
    {"api": "fund_daily", "table": "fund_daily_ex", "kind": "date"},
    # ---------- P0b 两融 / 改名 / 新股 / 指数月线 / 宏观 ----------
    {"api": "margin_detail", "table": "stock_margin_detail", "kind": "date"},
    {"api": "margin_secs", "table": "stock_margin_secs", "kind": "date"},
    {"api": "namechange", "table": "stock_namechange", "kind": "range"},
    {"api": "new_share", "table": "stock_new_share", "kind": "range"},
    {"api": "index_monthly", "table": "index_monthly", "kind": "custom",
     "params": {"trade_date": "20261030"}},
    {"api": "shibor", "table": "macro_rate", "kind": "range"},
    {"api": "libor", "table": "macro_rate", "kind": "custom",
     "params": {"start_date": "20200101", "end_date": "20200630"}},
    {"api": "hibor", "table": "macro_rate", "kind": "range"},
    {"api": "us_tbr", "table": "macro_rate", "kind": "range"},
    {"api": "us_tycr", "table": "macro_rate", "kind": "range"},
    {"api": "sf_month", "table": "macro_sf", "kind": "month"},
    {"api": "cn_m", "table": "macro_money", "kind": "month"},
    {"api": "cn_pmi", "table": "macro_pmi", "kind": "month"},
    # ---------- P0c 龙虎榜 / 筹码 / THS / 资金流 / 市场统计 ----------
    {"api": "top_list", "table": "stock_top_list", "kind": "date"},
    {"api": "top_inst", "table": "stock_top_inst", "kind": "date"},
    {"api": "cyq_perf", "table": "stock_cyq_perf", "kind": "date"},
    {"api": "ths_index", "table": "index_ths", "kind": "catalog", "params": {"exchange": "A"}},
    {"api": "ths_daily", "table": "index_ths_daily", "kind": "date"},
    {"api": "ths_member", "table": "index_ths_member", "kind": "custom", "params": {}},
    {"api": "moneyflow_dc", "table": "stock_moneyflow_ext", "kind": "date"},
    {"api": "moneyflow_ths", "table": "stock_moneyflow_ext", "kind": "date"},
    {"api": "moneyflow_ind_dc", "table": "stock_moneyflow_ind", "kind": "date"},
    {"api": "moneyflow_ind_ths", "table": "stock_moneyflow_ind", "kind": "date"},
    {"api": "moneyflow_cnt_ths", "table": "stock_moneyflow_ind", "kind": "date"},
    {"api": "daily_info", "table": "market_daily_info", "kind": "date"},
    {"api": "sz_daily_info", "table": "market_daily_info", "kind": "date"},
    # ---------- P1 大宗 / 全球指数 / 期货 / 期权 / 转债 / 北向十大 ----------
    {"api": "block_trade", "table": "stock_block_trade", "kind": "date"},
    {"api": "index_global", "table": "index_global_daily", "kind": "date"},
    {"api": "fut_basic", "table": "fut_basic", "kind": "catalog",
     "params": {"exchange": "CFFEX", "fut_type": "1"}},
    {"api": "fut_daily", "table": "fut_daily", "kind": "date"},
    {"api": "fut_holding", "table": "fut_holding", "kind": "date",
     "params": {"symbol": "CU", "exchange": "SHFE"}},
    {"api": "fut_wsr", "table": "fut_wsr", "kind": "date",
     "params": {"symbol": "CU", "exchange": "SHFE"}},
    {"api": "fut_settle", "table": "fut_settle", "kind": "date"},
    {"api": "fut_mapping", "table": "fut_mapping", "kind": "date"},
    {"api": "fut_index_daily", "table": "fut_index_daily", "kind": "custom",
     "params": {"ts_code": "NHCI.NH"}},
    {"api": "opt_basic", "table": "opt_basic", "kind": "catalog", "params": {"exchange": "SSE"}},
    {"api": "opt_daily", "table": "opt_daily", "kind": "date"},
    {"api": "cb_basic", "table": "cb_basic", "kind": "catalog"},
    {"api": "cb_issue", "table": "cb_issue", "kind": "range"},
    {"api": "cb_call", "table": "cb_call", "kind": "range"},
    {"api": "cb_daily", "table": "cb_daily", "kind": "date"},
    {"api": "cb_share", "table": "cb_share", "kind": "custom",
     "params": {"end_date": "20260930"}},
    {"api": "cb_rating", "table": "cb_rating", "kind": "custom",
     "params": {"ts_code": "113050.SH"}},
    {"api": "hsgt_top10", "table": "stock_hsgt_top10", "kind": "date",
     "params": {"market_type": "1"}},
    # ---------- P2 事件 / 港美股 ----------
    {"api": "pledge_detail", "table": "stock_pledge_detail", "kind": "range"},
    {"api": "repurchase", "table": "stock_repurchase", "kind": "range"},
    {"api": "stk_surv", "table": "stock_surv", "kind": "range"},
    {"api": "kpl_list", "table": "stock_kpl_list", "kind": "date",
     "params": {"tag": "涨停"}},
    {"api": "hm_list", "table": "stock_hm_list", "kind": "catalog"},
    {"api": "eco_cal", "table": "macro_eco_cal", "kind": "range"},
    {"api": "hk_basic", "table": "hk_basic", "kind": "catalog", "params": {"list_status": "L"}},
    {"api": "hk_daily", "table": "hk_daily", "kind": "custom",
     "params": {"trade_date": "20261106"}},
    {"api": "us_basic", "table": "us_basic", "kind": "catalog"},
    {"api": "us_daily", "table": "us_daily", "kind": "custom",
     "params": {"trade_date": "20261106"}},
    {"api": "ggt_daily", "table": "ggt_daily", "kind": "date"},
]

EXPECTED_TOTAL = 64


def _is_permission_error(msg: str) -> bool:
    low = msg.lower()
    return any(k.lower() in low for k in PERMISSION_KEYWORDS)


def _is_rate_limit_error(msg: str) -> bool:
    return any(k in msg for k in RATE_LIMIT_KEYWORDS)


def _call(pro, spec: Dict[str, Any], extra: Dict[str, Any]) -> Any:
    params = dict(spec.get("params") or {})
    params.update(extra)
    last_exc: Optional[Exception] = None
    for attempt in range(MAX_RETRY + 1):
        try:
            time.sleep(SLEEP_SEC)
            return pro.query(spec["api"], **params)
        except Exception as exc:  # noqa: BLE001 - 探针要把错误分类写进报告
            last_exc = exc
            msg = str(exc)
            # 权限错误与限流都不重试：前者重试无用，后者会触发更长的封禁窗口
            if _is_permission_error(msg) or _is_rate_limit_error(msg):
                raise
            if attempt < MAX_RETRY:
                time.sleep(2.0 * (attempt + 1))
    raise last_exc  # type: ignore[misc]


def probe_one(pro, spec: Dict[str, Any], ths_code: Optional[str]) -> Dict[str, Any]:
    kind = spec["kind"]
    rows = 0
    columns: List[str] = []
    error = ""
    status = "ok"
    attempts: List[str] = []

    param_sets: List[Dict[str, Any]]
    if kind == "catalog":
        param_sets = [{}]
    elif kind == "date":
        key = spec.get("date_key", "trade_date")
        param_sets = [{key: d} for d in SAMPLE_DATES]
    elif kind == "range":
        param_sets = [{"start_date": RANGE_START, "end_date": RANGE_END}]
    elif kind == "month":
        param_sets = [{"start_m": MONTH_START, "end_m": MONTH_END}]
    elif kind == "custom":
        if spec["api"] == "ths_member":
            param_sets = [{"ts_code": ths_code}] if ths_code else [{}]
        else:
            param_sets = [{}]
    else:
        param_sets = [{}]

    for extra in param_sets:
        label = ",".join(f"{k}={v}" for k, v in extra.items()) or "no-params"
        attempts.append(label)
        try:
            df = _call(pro, spec, extra)
        except Exception as exc:  # noqa: BLE001
            msg = str(exc)[:300]
            error = msg
            if _is_permission_error(msg):
                status = "gap"
            elif _is_rate_limit_error(msg):
                status = "rate_limited"
            else:
                status = "error"
            break
        n = 0 if df is None else len(df)
        rows += n
        if df is not None and len(df.columns) > len(columns):
            columns = [str(c) for c in df.columns]
        if n > 0:
            status = "ok"
            error = ""
            break
        status = "empty"
    return {
        "api": spec["api"],
        "table": spec["table"],
        "kind": kind,
        "status": status,
        "rows": rows,
        "fields": columns,
        "attempts": attempts,
        "error": error,
    }


def render_report(results: List[Dict[str, Any]], sample_dates: List[str]) -> str:
    lines = [
        "# 日频数据底座接口探针报告",
        "",
        f"> 生成时间：{time.strftime('%Y-%m-%d %H:%M:%S')}",
        f"> 按日接口取样日期（倒序尝试）：{', '.join(sample_dates)}",
        f"> 区间接口：{RANGE_START} ~ {RANGE_END}；月度接口：{MONTH_START} ~ {MONTH_END}",
        "",
        "| 接口 | 目标表 | 模式 | 状态 | 行数 | 字段 |",
        "|:---|:---|:---|:--:|--:|:---|",
    ]
    for r in results:
        fields = ", ".join(r["fields"]) if r["fields"] else "（无返回字段）"
        lines.append(
            f"| `{r['api']}` | `{r['table']}` | {r['kind']} | {r['status']} | "
            f"{r['rows']} | {fields} |"
        )
    gaps = [r for r in results if r["status"] in ("gap", "error", "rate_limited")]
    if gaps:
        lines += ["", "## 缺口与错误", ""]
        for r in gaps:
            lines.append(f"- `{r['api']}`（{r['table']}）：{r['status']}；{r['error']}")
    return "\n".join(lines) + "\n"


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--all", action="store_true", help="跑全部 63 个接口（当前唯一模式）")
    ap.add_argument("--only", default="", help="只跑指定接口，逗号分隔，调试用")
    ap.add_argument("--out", default=str(DEFAULT_OUT), help="报告输出路径")
    args = ap.parse_args()

    specs = SPECS
    if args.only:
        wanted = {x.strip() for x in args.only.split(",") if x.strip()}
        specs = [s for s in specs if s["api"] in wanted]
    if not args.all and not args.only:
        ap.print_help()
        return 1

    env = load_env(ENV_PATH)
    token = env.get("DEV_TUSHARE_TOKEN") or env.get("PROD_TUSHARE_TOKEN")
    if not token:
        print("未找到 Tushare token（DEV_TUSHARE_TOKEN / PROD_TUSHARE_TOKEN）", file=sys.stderr)
        return 2
    import tushare as ts

    pro = ts.pro_api(token)
    print(f"[probe] specs={len(specs)} expected={EXPECTED_TOTAL}", flush=True)

    results: List[Dict[str, Any]] = []
    ths_code: Optional[str] = None
    for i, spec in enumerate(specs, 1):
        r = probe_one(pro, spec, ths_code)
        if spec["api"] == "ths_index" and r["rows"] > 0:
            # ths_member 需要一个真实指数代码；从 ths_index 的返回里取
            try:
                df = pro.query("ths_index", exchange="A")
                if df is not None and not df.empty:
                    ths_code = str(df.iloc[0]["ts_code"])
            except Exception:  # noqa: BLE001 - 取不到就退回空参数
                ths_code = None
        results.append(r)
        print(
            f"[{i:02d}/{len(specs)}] {r['api']:<20} {r['status']:<5} rows={r['rows']:<6} "
            f"fields={len(r['fields'])}",
            flush=True,
        )

    out_path = Path(args.out)
    out_path.parent.mkdir(parents=True, exist_ok=True)
    out_path.write_text(render_report(results, SAMPLE_DATES), encoding="utf-8")

    ok = sum(1 for r in results if r["status"] in ("ok", "empty"))
    empty = sum(1 for r in results if r["status"] == "empty")
    gap = sum(1 for r in results if r["status"] in ("gap", "error", "rate_limited"))
    print(f"ok={ok} empty={empty} gap={gap} report={out_path}", flush=True)
    return 0 if gap == 0 else 1


if __name__ == "__main__":
    sys.exit(main())
