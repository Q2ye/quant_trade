# -*- coding: utf-8 -*-
"""回填 stock_limit_list（Tushare limit_list_d）

用途：行业热度 / 连板 / 封板结构。Tushare 该接口约 2020-01 起，故回填起点为 2020-01-01。
默认 dry-run；加 `--apply` 才写库。按月拉取；若单月行数接近接口上限，自动退化为逐日拉取。

用法：
  cd quant_server
  .venv/Scripts/python.exe scripts/data/backfill_limit_list.py                 # dry-run
  .venv/Scripts/python.exe scripts/data/backfill_limit_list.py --apply         # 写库
  .venv/Scripts/python.exe scripts/data/backfill_limit_list.py --start 20200101 --end 20260918 --apply
"""

from __future__ import annotations

import argparse
import json
import math
import time
from datetime import date
from pathlib import Path
from typing import Any, Dict, List, Optional

import pandas as pd
import psycopg2
from psycopg2.extras import execute_values

SCRIPT_DIR = Path(__file__).resolve().parent
SERVER_DIR = SCRIPT_DIR.parents[1]
ENV_PATH = SERVER_DIR / ".env"
LOG_DIR = SERVER_DIR / "logs"

DEFAULT_START = "2020-01-01"
DEFAULT_END = None  # 取 index_sw_daily 最大日期
SLEEP_SEC = 0.2
MAX_RETRY = 3

COLS = [
    "trade_date", "ts_code", "industry", "name", "close", "pct_chg", "amount",
    "limit_amount", "float_mv", "total_mv", "turnover_ratio", "fd_amount",
    "first_time", "last_time", "open_times", "up_stat", "limit_times", "limit_type",
]


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
        password=env["DB_PASSWORD"], dbname=env["DB_NAME"],
    )


def _str(x: Any) -> Optional[str]:
    if x is None:
        return None
    if isinstance(x, float) and not math.isfinite(x):
        return None
    if isinstance(x, float) and x.is_integer():
        return str(int(x))
    s = str(x).strip()
    return s if s and s.lower() != "nan" else None


def _num(x: Any) -> Optional[float]:
    if x is None:
        return None
    try:
        v = float(x)
    except (TypeError, ValueError):
        return None
    return None if not math.isfinite(v) else v


def _int(x: Any) -> Optional[int]:
    v = _num(x)
    return None if v is None else int(round(v))


def _date(x: Any) -> Optional[date]:
    if x is None:
        return None
    try:
        return pd.Timestamp(str(x)).date()
    except Exception:
        return None


def get_calendar(conn, start: str, end: str) -> pd.DatetimeIndex:
    cur = conn.cursor()
    cur.execute(
        "SELECT DISTINCT trade_date FROM index_sw_daily WHERE trade_date BETWEEN %s AND %s ORDER BY 1",
        (start, end),
    )
    return pd.DatetimeIndex([r[0] for r in cur.fetchall()])


def fetch_day(pro, d: str) -> pd.DataFrame:
    last_err = None
    for attempt in range(MAX_RETRY):
        try:
            df = pro.limit_list_d(trade_date=d, limit=6000)
            time.sleep(SLEEP_SEC)
            return df if df is not None else pd.DataFrame()
        except Exception as e:  # noqa: BLE001
            last_err = e
            time.sleep(2 ** attempt)
    raise RuntimeError(f"limit_list_d {d} failed: {last_err}")


def normalize(df: pd.DataFrame) -> List[tuple]:
    if df is None or df.empty:
        return []
    df = df.copy()
    if "limit" in df.columns and "limit_type" not in df.columns:
        df = df.rename(columns={"limit": "limit_type"})
    # 去重（同一 ts_code/trade_date 只留最后一行）
    if "trade_date" in df.columns and "ts_code" in df.columns:
        df = df.drop_duplicates(subset=["ts_code", "trade_date"], keep="last")
    rows: List[tuple] = []
    for _, r in df.iterrows():
        td = _date(r.get("trade_date"))
        code = _str(r.get("ts_code"))
        if td is None or not code:
            continue
        rows.append((
            td,
            code,
            _str(r.get("industry")),
            _str(r.get("name")),
            _num(r.get("close")),
            _num(r.get("pct_chg")),
            _num(r.get("amount")),
            _num(r.get("limit_amount")),
            _num(r.get("float_mv")),
            _num(r.get("total_mv")),
            _num(r.get("turnover_ratio")),
            _num(r.get("fd_amount")),
            _str(r.get("first_time")),
            _str(r.get("last_time")),
            _int(r.get("open_times")),
            _str(r.get("up_stat")),
            _int(r.get("limit_times")),
            _str(r.get("limit_type")),
        ))
    return rows


def upsert(cur, rows: List[tuple]) -> int:
    if not rows:
        return 0
    sql = """
        INSERT INTO stock_limit_list (
            trade_date, ts_code, industry, name, close, pct_chg, amount,
            limit_amount, float_mv, total_mv, turnover_ratio, fd_amount,
            first_time, last_time, open_times, up_stat, limit_times, limit_type
        ) VALUES %s
        ON CONFLICT (ts_code, trade_date) DO UPDATE SET
            industry = EXCLUDED.industry,
            name = EXCLUDED.name,
            close = EXCLUDED.close,
            pct_chg = EXCLUDED.pct_chg,
            amount = EXCLUDED.amount,
            limit_amount = EXCLUDED.limit_amount,
            float_mv = EXCLUDED.float_mv,
            total_mv = EXCLUDED.total_mv,
            turnover_ratio = EXCLUDED.turnover_ratio,
            fd_amount = EXCLUDED.fd_amount,
            first_time = EXCLUDED.first_time,
            last_time = EXCLUDED.last_time,
            open_times = EXCLUDED.open_times,
            up_stat = EXCLUDED.up_stat,
            limit_times = EXCLUDED.limit_times,
            limit_type = EXCLUDED.limit_type,
            updated_at = CURRENT_TIMESTAMP
    """
    execute_values(cur, sql, rows, page_size=1000)
    return len(rows)


def verify(conn, start: str, end: str) -> Dict[str, Any]:
    cur = conn.cursor()
    out: Dict[str, Any] = {}
    cur.execute(
        "SELECT min(trade_date), max(trade_date), count(*), count(distinct trade_date) FROM stock_limit_list"
    )
    out["db_min_max_rows_dates"] = [str(x) if x is not None else None for x in cur.fetchone()]
    cur.execute(
        "SELECT trade_date, count(*) FROM stock_limit_list GROUP BY 1 ORDER BY 1"
    )
    per_day = cur.fetchall()
    out["days_with_rows"] = len(per_day)
    out["max_rows_per_day"] = max((r[1] for r in per_day), default=0)
    out["min_rows_per_day"] = min((r[1] for r in per_day), default=0)
    cur.execute(
        "SELECT limit_type, count(*) FROM stock_limit_list GROUP BY 1 ORDER BY 2 DESC"
    )
    out["by_limit_type"] = {str(k): int(v) for k, v in cur.fetchall()}
    cur.execute(
        "SELECT count(*) FILTER (WHERE limit_times IS NOT NULL), "
        "count(*) FILTER (WHERE fd_amount IS NOT NULL), count(*) "
        "FROM stock_limit_list"
    )
    out["limit_times_nonnull_fd_nonnull_total"] = [int(x) for x in cur.fetchone()]
    # 逐月计数
    cur.execute(
        "SELECT to_char(trade_date,'YYYY-MM') m, count(*) n FROM stock_limit_list "
        "WHERE trade_date BETWEEN %s AND %s GROUP BY 1 ORDER BY 1",
        (start, end),
    )
    out["by_month"] = [{"month": m, "rows": int(n)} for m, n in cur.fetchall()]
    return out


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--start", default=DEFAULT_START)
    ap.add_argument("--end", default=DEFAULT_END)
    ap.add_argument("--apply", action="store_true", help="写库；默认 dry-run")
    args = ap.parse_args()

    env = load_env(ENV_PATH)
    if not env:
        raise SystemExit(f"未找到 .env: {ENV_PATH}")
    token = env.get("DEV_TUSHARE_TOKEN") or env.get("PROD_TUSHARE_TOKEN")
    if not token:
        raise SystemExit("未找到 Tushare token")
    import tushare as ts

    pro = ts.pro_api(token)
    conn = connect_db(env)
    try:
        end = args.end
        if not end:
            cur = conn.cursor()
            cur.execute("SELECT max(trade_date) FROM index_sw_daily")
            end = str(cur.fetchone()[0])
        cal = get_calendar(conn, args.start, end)
        print(f"[limit_list] {args.start} ~ {end}; trading days={len(cal)}; "
              f"mode={'APPLY' if args.apply else 'DRY-RUN'}", flush=True)
        if not cal.size:
            raise SystemExit("日历为空")

        total_rows = 0
        total_api_rows = 0
        failures: List[Dict[str, Any]] = []
        per_month: Dict[str, int] = {}
        t0 = time.time()

        # 逐日拉取：避免 Tushare 默认行数静默截断（月度分块无法证明未截断）
        for i, d in enumerate(cal, start=1):
            dstr = pd.Timestamp(d).strftime("%Y%m%d")
            try:
                df = fetch_day(pro, dstr)
                total_api_rows += len(df)
                if len(df) >= 6000:
                    failures.append(
                        {"date": dstr, "error": f"rows={len(df)} >= 6000, possible truncation"}
                    )
                rows = normalize(df)
                if args.apply and rows:
                    cur = conn.cursor()
                    try:
                        upsert(cur, rows)
                        conn.commit()
                    except Exception:
                        conn.rollback()
                        raise
                total_rows += len(rows)
                per_month[dstr[:6]] = per_month.get(dstr[:6], 0) + len(rows)
                if i % 50 == 0 or i == len(cal):
                    print(f"  [{i}/{len(cal)}] {dstr} api={len(df)} rows={len(rows)} "
                          f"cum={total_rows} elapsed={time.time()-t0:.0f}s", flush=True)
            except Exception as ex:  # noqa: BLE001
                failures.append({"date": dstr, "error": str(ex)[:200]})
                print(f"  [{i}/{len(cal)}] {dstr} FAILED: {str(ex)[:160]}", flush=True)

        summary: Dict[str, Any] = {
            "start": args.start,
            "end": end,
            "apply": bool(args.apply),
            "trading_days": int(len(cal)),
            "api_rows": int(total_api_rows),
            "rows_processed": int(total_rows),
            "failures": failures,
            "per_month": [{"month": k, "rows": v} for k, v in sorted(per_month.items())],
        }
        if args.apply:
            summary["verify"] = verify(conn, args.start, end)
        LOG_DIR.mkdir(parents=True, exist_ok=True)
        out_path = LOG_DIR / "backfill_limit_list_summary.json"
        out_path.write_text(json.dumps(summary, ensure_ascii=False, indent=2), encoding="utf-8")
        print(f"\nsummary: {out_path}")
        print(f"api_rows={total_api_rows} rows_processed={total_rows} failures={len(failures)}")
        if args.apply:
            print("verify:", json.dumps(summary["verify"], ensure_ascii=False)[:1000])
    finally:
        conn.close()


if __name__ == "__main__":
    main()
