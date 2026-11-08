# -*- coding: utf-8 -*-
"""日频数据底座通用回填脚本。

能力：
- 按 DATA_CONTRACTS 的 6 种模式回填（by_date/by_month/by_range/by_snapshot/
  full_snapshot；by_symbol 当前无表使用）；
- 断点续传：结果写 data_backfill_progress，--resume 跳过 done；
- --verify：逐日比较「接口返回行数」与「库内行数」；
- --estimate：估算 API 调用次数与限流风险，不写库；
- --report：回填后汇总进度与各表行数/最早日期。

默认 dry-run（只打印计划）；加 --apply 才真正写库。

用法：
  cd quant_server
  .venv/Scripts/python.exe scripts/data/backfill_daily_base.py --estimate
  .venv/Scripts/python.exe scripts/data/backfill_daily_base.py --types fx_daily,margin_detail --start 20261103 --end 20261105 --verify --apply
  .venv/Scripts/python.exe scripts/data/backfill_daily_base.py --all --resume --report --apply
"""

from __future__ import annotations

import argparse
import asyncio
import calendar
import os
import sys
from datetime import date, datetime, timedelta
from pathlib import Path
from typing import Dict, List, Optional

import psycopg2
from sqlalchemy import text

try:  # Windows 控制台默认 GBK，中文输出会炸
    sys.stdout.reconfigure(encoding="utf-8")
    sys.stderr.reconfigure(encoding="utf-8")
except Exception:
    pass

SCRIPT_DIR = Path(__file__).resolve().parent
SERVER_DIR = SCRIPT_DIR.parents[1]
REPO_ROOT = SERVER_DIR.parent
ENV_PATH = SERVER_DIR / ".env"

BEGIN_MARK = "-- ===== BEGIN DAILY_DATA_BASE ====="
END_MARK = "-- ===== END DAILY_DATA_BASE ====="

# 契约里的日期列（用于计数与报表）
from modules.data.data_contracts import DATE_COLUMNS as _DATE_COL  # noqa: E402
# 源日期 → 入库日期的偏移（fx_daily 的 GMT +1）
_DATE_SHIFT_DAYS = {"fx_daily": 1}
# 1 次/小时的接口，估算时单独告警
_HOURLY_APIS = {"hk_daily", "us_daily"}
# 特殊表的调用次数修正：固定次数 / 每个交易日的倍数
_FIXED_CALLS = {"macro_rate": 5, "fut_basic": 6, "opt_basic": 7,
               "fut_index_daily": 7, "cb_rating": 1200}
_CALL_MULTIPLIER = {
    "fut_holding": 70, "fut_wsr": 70, "index_ths_member": 1666,
    "stock_moneyflow_ext": 2, "stock_moneyflow_ind": 3,
    "market_daily_info": 2, "stock_hsgt_top10": 2,
}
# 分页（每 5,000 行一页）后的调用倍数；hk/us 不分页
_PAGE_MULTIPLIER = {
    "fund_nav": 5, "stock_cyq_perf": 2, "opt_daily": 4, "opt_basic": 19,
    "stock_moneyflow_ext": 2, "stock_moneyflow_ind": 2,
}


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


def connect_db(env: Dict[str, str]):
    return psycopg2.connect(
        host=env["DB_HOST"], port=env["DB_PORT"], user=env["DB_USER"],
        password=env["DB_PASSWORD"], dbname=env["DB_NAME"], connect_timeout=10,
    )


def parse_day(value: str) -> date:
    value = value.strip()
    for fmt in ("%Y%m%d", "%Y-%m-%d"):
        try:
            return datetime.strptime(value, fmt).date()
        except ValueError:
            continue
    raise argparse.ArgumentTypeError(f"日期格式应为 YYYYMMDD 或 YYYY-MM-DD：{value}")


def trade_days(conn, start: date, end: date) -> List[date]:
    with conn.cursor() as cur:
        cur.execute(
            "SELECT cal_date FROM trade_calendar WHERE exchange = 'SSE' "
            "AND is_open = TRUE AND cal_date BETWEEN %s AND %s ORDER BY cal_date",
            (start, end),
        )
        days = [r[0] for r in cur.fetchall()]
    if days:
        return days
    out: List[date] = []
    cur = start
    while cur <= end:
        if cur.weekday() < 5:
            out.append(cur)
        cur += timedelta(days=1)
    return out


def months(start: date, end: date) -> List[str]:
    out: List[str] = []
    y, m = start.year, start.month
    while (y, m) <= (end.year, end.month):
        out.append(f"{y:04d}{m:02d}")
        m += 1
        if m > 12:
            y, m = y + 1, 1
    return out


def _resolve_types(raw: str) -> List[str]:
    from modules.data.data_contracts import DATA_CONTRACTS

    if not raw or raw == "all":
        return list(DATA_CONTRACTS)
    wanted = [x.strip() for x in raw.split(",") if x.strip()]
    bad = [x for x in wanted if x not in DATA_CONTRACTS]
    if bad:
        raise SystemExit(f"未知 data_type：{bad}")
    return wanted


def _start_for(contract, override: Optional[date]) -> Optional[date]:
    if override:
        return override
    if contract.earliest and contract.earliest != "implementation":
        return parse_day(contract.earliest)
    if contract.backfill_mode == "by_date":
        # 契约未写起点但接口有历史的日频表（fund_share 等），按 2005 起估算
        return date(2005, 1, 1)
    return None


def _month_end(m: str) -> date:
    y, mo = int(m[:4]), int(m[4:])
    return date(y, mo, calendar.monthrange(y, mo)[1])


def _quarter_ends(start: date, end: date) -> List[date]:
    out: List[date] = []
    for year in range(start.year, end.year + 1):
        for mo, day in ((3, 31), (6, 30), (9, 30), (12, 31)):
            dt = date(year, mo, day)
            if start <= dt <= end:
                out.append(dt)
    return out


def estimate(args) -> int:
    from modules.data.data_contracts import DATA_CONTRACTS

    end = args.end or date.today()
    conn = connect_db(load_env(ENV_PATH))
    print("# calls 为估算值；已乘 _CALL_MULTIPLIER 与 _PAGE_MULTIPLIER（每 5,000 行一页）")
    print(f"{'data_type':<24} {'mode':<16} {'calls':>9}  说明")
    try:
        for key in _resolve_types(args.types):
            c = DATA_CONTRACTS[key]
            start = _start_for(c, args.start)
            days = len(trade_days(conn, start or end, end))
            if key in _FIXED_CALLS:
                calls = _FIXED_CALLS[key]
            elif c.backfill_mode == "full_snapshot":
                calls = 1
            elif c.backfill_mode == "by_month":
                calls = len(months(start or end, end))
            elif c.backfill_mode == "by_range":
                calls = 1
            elif c.backfill_mode == "by_range_daily":
                calls = days
            elif c.backfill_mode == "by_quarter":
                calls = len(_quarter_ends(start or end, end))
            else:
                calls = days
            calls *= _CALL_MULTIPLIER.get(key, 1)
            calls *= _PAGE_MULTIPLIER.get(key, 1)
            note = ""
            api = c.api[0] if c.api else ""
            if api in _HOURLY_APIS:
                note = f"WARN {api} 限 1 次/小时，预计 {calls} 小时"
            print(f"{key:<24} {c.backfill_mode:<16} {calls:>9}  {note}")
    finally:
        conn.close()
    return 0


def _written_or_fail(contract, res: Dict) -> int:
    """dense 表接口返回 0 行时按失败处理，避免把限流/权限/空响应当 done。"""
    written = int(res.get("records_added", 0) or 0)
    total_items = int(res.get("total_items", 0) or 0)
    if contract.gate_mode == "dense" and total_items == 0:
        raise RuntimeError("接口返回空（dense 表按失败处理）")
    return written


async def _run(args) -> int:
    from modules.data.constants import DataType
    from modules.data.data_contracts import DATA_CONTRACTS
    from modules.data.services.sync_service import DataSyncService
    from shared.database.repositories.market.ext.progress_repo import (
        DataBackfillProgressRepository,
    )
    from shared.database.session.connection_pool import get_connection_pool

    env = load_env(ENV_PATH)
    token = env.get("DEV_TUSHARE_TOKEN") or env.get("PROD_TUSHARE_TOKEN")
    if token:
        os.environ["TUSHARE_TOKEN"] = token
    conn = connect_db(env)
    end = args.end or date.today()
    types = _resolve_types(args.types)

    pool = get_connection_pool()
    try:
        sf = pool.get_session_factory()
    except RuntimeError:
        await pool.initialize()
        sf = pool.get_session_factory()

    total = {"done": 0, "failed": 0, "skipped": 0, "written": 0}
    async with sf() as session:
        svc = DataSyncService(session=session)
        progress = DataBackfillProgressRepository(session)

        for key in types:
            c = DATA_CONTRACTS[key]
            method = svc._sync_method_map[DataType(key)]
            start = _start_for(c, args.start) or end
            status_map = await progress.get_status_map(key)

            if not args.apply:
                # 默认 dry-run：只打印计划，不调用接口、不写库
                if c.backfill_mode in ("full_snapshot", "by_range"):
                    span = "snapshot" if c.backfill_mode == "full_snapshot" else f"{start}~{end}"
                elif c.backfill_mode == "by_month":
                    span = f"{months(start, end)[0]}~{months(start, end)[-1]}"
                else:
                    span = f"{start}~{end} ({len(trade_days(conn, start, end))} 个交易日)"
                print(f"[dry-run] {key:<24} {c.backfill_mode:<14} {span}")
                total["skipped"] += 1
                continue

            if c.backfill_mode in ("full_snapshot", "by_range"):
                pk = "snapshot" if c.backfill_mode == "full_snapshot" else f"{start}_{end}"
                if args.resume and status_map.get(pk) == "done":
                    total["skipped"] += 1
                    continue
                try:
                    res = await method(start_date=start, end_date=end, ts_codes=None,
                                       task_id="backfill", user_id=None)
                    written = _written_or_fail(c, res)
                    if args.apply:
                        await progress.mark(key, date(1900, 1, 1), pk, "done", written)
                        await session.commit()
                    total["done"] += 1
                    total["written"] += written
                    print(f"[{key}] {c.backfill_mode} {start}~{end} written={written}")
                except Exception as exc:  # noqa: BLE001
                    await session.rollback()
                    total["failed"] += 1
                    if args.apply:
                        await progress.mark(key, date(1900, 1, 1), pk, "failed", 0, str(exc)[:500])
                        await session.commit()
                    print(f"[{key}] FAILED {str(exc)[:160]}")
                continue

            if c.backfill_mode == "by_month":
                fails = 0
                for m in months(start, end):
                    pk = m
                    if args.resume and status_map.get(pk) == "done":
                        total["skipped"] += 1
                        continue
                    try:
                        res = await method(
                            start_date=date(int(m[:4]), int(m[4:]), 1),
                            end_date=_month_end(m), ts_codes=None,
                            task_id="backfill", user_id=None)
                        written = _written_or_fail(c, res)
                        await progress.mark(key, date(1900, 1, 1), pk, "done", written)
                        await session.commit()
                        total["done"] += 1
                        total["written"] += written
                        fails = 0
                    except Exception as exc:  # noqa: BLE001
                        await session.rollback()
                        total["failed"] += 1
                        await progress.mark(key, date(1900, 1, 1), pk, "failed", 0, str(exc)[:500])
                        await session.commit()
                        print(f"[{key}] {m} FAILED {str(exc)[:160]}")
                        fails += 1
                        if fails >= 3:
                            print(f"[{key}] 连续失败 3 次，停止该类型")
                            break
                continue

            if c.backfill_mode in ("by_range_daily", "by_quarter"):
                dates = (_quarter_ends(start, end) if c.backfill_mode == "by_quarter"
                         else trade_days(conn, start, end))
                fails = 0
                for d in dates:
                    pk = d.isoformat()
                    if args.resume and status_map.get(pk) == "done":
                        total["skipped"] += 1
                        continue
                    try:
                        res = await method(start_date=d, end_date=d, ts_codes=None,
                                           task_id="backfill", user_id=None)
                        written = _written_or_fail(c, res)
                        await progress.mark(key, d, "", "done", written)
                        await session.commit()
                        total["done"] += 1
                        total["written"] += written
                        fails = 0
                    except Exception as exc:  # noqa: BLE001
                        await session.rollback()
                        total["failed"] += 1
                        await progress.mark(key, d, "", "failed", 0, str(exc)[:500])
                        await session.commit()
                        print(f"[{key}] {d} FAILED {str(exc)[:160]}")
                        fails += 1
                        if fails >= 3:
                            print(f"[{key}] 连续失败 3 次，停止该类型")
                            break
                continue

            # by_date / by_snapshot
            days = trade_days(conn, start, end)
            if key in _HOURLY_APIS and len(days) > 1:
                print(f"[{key}] SKIP 限 1 次/小时，只允许单日（本次 {len(days)} 天）")
                total["skipped"] += 1
                continue
            fails = 0
            for d in days:
                pk = d.isoformat()
                if args.resume and status_map.get(pk) == "done":
                    total["skipped"] += 1
                    continue
                try:
                    res = await method(start_date=d, end_date=d, ts_codes=None,
                                       task_id="backfill", user_id=None)
                    written = _written_or_fail(c, res)
                    await progress.mark(key, d, "", "done", written)
                    await session.commit()
                    total["done"] += 1
                    total["written"] += written
                    fails = 0
                    if args.verify:
                        await _verify(session, conn, c, d, res)
                    if total["done"] % 20 == 0:
                        print(f"[{key}] {d} ... done={total['done']} written={total['written']}")
                except Exception as exc:  # noqa: BLE001
                    await session.rollback()
                    total["failed"] += 1
                    await progress.mark(key, d, "", "failed", 0, str(exc)[:500])
                    await session.commit()
                    print(f"[{key}] {d} FAILED {str(exc)[:160]}")
                    fails += 1
                    if fails >= 3:
                        print(f"[{key}] 连续失败 3 次，停止该类型")
                        break

    conn.close()
    print(
        f"SUMMARY done={total['done']} failed={total['failed']} "
        f"skipped={total['skipped']} written={total['written']}"
    )
    return 0 if total["failed"] == 0 else 1


async def _verify(session, conn, contract, d: date, res: Dict) -> None:
    api_rows = int(res.get("total_items", 0) or 0)
    if api_rows == 0 and contract.gate_mode == "dense":
        print(f"[verify] {contract.data_type} {d} api=0 EMPTY")
        return
    col = _DATE_COL.get(contract.data_type, "trade_date")
    shift = _DATE_SHIFT_DAYS.get(contract.data_type, 0)
    db_date = d + timedelta(days=shift)
    q = f"SELECT count(*) FROM {contract.table} WHERE {col} = :d"
    db_rows = int((await session.execute(text(q), {"d": db_date})).scalar() or 0)
    flag = "OK" if api_rows == db_rows else "MISMATCH"
    if flag != "OK":
        print(f"[verify] {contract.data_type} {db_date} api={api_rows} db={db_rows} {flag}")


def report(args) -> int:
    from modules.data.data_contracts import DATA_CONTRACTS

    env = load_env(ENV_PATH)
    conn = connect_db(env)
    try:
        with conn.cursor() as cur:
            cur.execute(
                "SELECT data_type, status, count(*) FROM data_backfill_progress "
                "GROUP BY data_type, status ORDER BY data_type, status"
            )
            rows = cur.fetchall()
        print("== progress ==")
        for r in rows:
            print(f"  {r[0]:<24} {r[1]:<8} {r[2]}")
        print("== tables ==")
        for key, c in DATA_CONTRACTS.items():
            col = _DATE_COL.get(key, "trade_date")
            try:
                with conn.cursor() as cur:
                    cur.execute(
                        f"SELECT count(*), min({col}), max({col}) FROM {c.table}"
                    )
                    n, lo, hi = cur.fetchone()
                print(f"  {c.table:<24} rows={n:<10} min={lo} max={hi}")
            except Exception as exc:  # noqa: BLE001
                conn.rollback()
                print(f"  {c.table:<24} ERROR {str(exc)[:120]}")
    finally:
        conn.close()
    return 0


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--types", default="all", help="逗号分隔的 data_type，或 all")
    ap.add_argument("--start", type=parse_day, default=None)
    ap.add_argument("--end", type=parse_day, default=None)
    ap.add_argument("--resume", action="store_true", help="跳过已 done")
    ap.add_argument("--verify", action="store_true", help="逐日比对接口与库内行数")
    ap.add_argument("--estimate", action="store_true", help="只估算调用次数")
    ap.add_argument("--report", action="store_true", help="回填后汇总")
    ap.add_argument("--apply", action="store_true", help="真正写库；默认 dry-run")
    args = ap.parse_args()

    if args.estimate:
        return estimate(args)
    rc = asyncio.run(_run(args))
    if args.report:
        report(args)
    return rc


if __name__ == "__main__":
    sys.exit(main())
