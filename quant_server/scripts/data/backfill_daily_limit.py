# -*- coding: utf-8 -*-
"""回填 stock_daily_limit（Tushare stk_limit）

用途：涨停价 / 跌停价。stk_limit 接口仅返回 4 列（trade_date / ts_code / up_limit / down_limit），
其余四列（pre_close / up_percent / down_percent / price_range）上游无来源、恒为 NULL。
默认 dry-run；加 `--apply` 才写库。按日拉取（stk_limit 单日全市场约 3.8k~5k 行，
接近接口上限，按日最安全，避免范围查询静默截断）。

用法：
  cd quant_server
  .venv/Scripts/python.exe scripts/data/backfill_daily_limit.py                      # dry-run
  .venv/Scripts/python.exe scripts/data/backfill_daily_limit.py --apply              # 写库
  .venv/Scripts/python.exe scripts/data/backfill_daily_limit.py --start 20200101 --end 20261120 --apply
"""

from __future__ import annotations

import argparse
import json
import math
import time
import uuid
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

DEFAULT_START = "2020-01-01"  # 与 stock_limit_list 对齐（limit_list_d 约 2020-01 起）
DEFAULT_END = None  # 取 trade_calendar 最大开市日
SLEEP_SEC = 0.2
MAX_RETRY = 3

# stk_limit 返回的 4 列（仅这 4 列有值）
SRC_COLS = ["trade_date", "ts_code", "up_limit", "down_limit"]


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


def write_db(env: Dict[str, str]) -> Dict[str, str]:
    """写库连接：public 表写权限在 quant_prod（grant_roles.py：quant_dev 只读 public）。

    quant_dev = public SELECT only；quant_prod = public 读写。
    回填写 public.stock_daily_limit 必须用 PROD_DB_*（quant_prod）。
    """
    return {
        "DB_HOST": env.get("PROD_DB_HOST", env.get("DEV_DB_HOST", "")),
        "DB_PORT": env.get("PROD_DB_PORT", env.get("DEV_DB_PORT", "")),
        "DB_USER": env.get("PROD_DB_USER", env.get("DEV_DB_USER", "")),
        "DB_PASSWORD": env.get("PROD_DB_PASSWORD", env.get("DEV_DB_PASSWORD", "")),
        "DB_NAME": env.get("PROD_DB_NAME", env.get("DEV_DB_NAME", "")),
    }


def connect_db(env: Dict[str, str]):
    return psycopg2.connect(
        host=env["DB_HOST"], port=env["DB_PORT"], user=env["DB_USER"],
        password=env["DB_PASSWORD"], dbname=env["DB_NAME"],
    )


def _num(x: Any) -> Optional[float]:
    if x is None:
        return None
    try:
        v = float(x)
    except (TypeError, ValueError):
        return None
    return None if not math.isfinite(v) else v


def _date(x: Any) -> Optional[date]:
    if x is None:
        return None
    try:
        return pd.Timestamp(str(x)).date()
    except Exception:
        return None


def get_calendar(conn, start: str, end: str) -> pd.DatetimeIndex:
    """交易日历：优先 trade_calendar（SSE 开市日），空则退化为 index_sw_daily。"""
    cur = conn.cursor()
    cur.execute(
        "SELECT cal_date FROM trade_calendar WHERE exchange = 'SSE' "
        "AND is_open = TRUE AND cal_date BETWEEN %s AND %s ORDER BY 1",
        (start, end),
    )
    rows = [r[0] for r in cur.fetchall()]
    if rows:
        return pd.DatetimeIndex(rows)
    cur.execute(
        "SELECT DISTINCT trade_date FROM index_sw_daily WHERE trade_date BETWEEN %s AND %s ORDER BY 1",
        (start, end),
    )
    return pd.DatetimeIndex([r[0] for r in cur.fetchall()])


def fetch_day(pro, d: str) -> pd.DataFrame:
    last_err = None
    for attempt in range(MAX_RETRY):
        try:
            df = pro.stk_limit(trade_date=d)
            time.sleep(SLEEP_SEC)
            return df if df is not None else pd.DataFrame()
        except Exception as e:  # noqa: BLE001
            last_err = e
            time.sleep(2 ** attempt)
    raise RuntimeError(f"stk_limit {d} failed: {last_err}")


def normalize(df: pd.DataFrame) -> List[tuple]:
    """stk_limit → (id, ts_code, trade_date, up_limit, down_limit)。

    其余四列（pre_close/up_percent/down_percent/price_range）无来源，不写入。
    """
    if df is None or df.empty:
        return []
    df = df.copy()
    if "trade_date" in df.columns and "ts_code" in df.columns:
        df = df.drop_duplicates(subset=["ts_code", "trade_date"], keep="last")
    rows: List[tuple] = []
    for _, r in df.iterrows():
        td = _date(r.get("trade_date"))
        code = r.get("ts_code")
        if td is None or not code:
            continue
        up = _num(r.get("up_limit"))
        dn = _num(r.get("down_limit"))
        # Numeric(9,4) 上限 99999.9999，A 股价格远低于此，但保留防御裁剪
        if up is not None and abs(up) > 99999.9999:
            up = 99999.9999 if up > 0 else -99999.9999
        if dn is not None and abs(dn) > 99999.9999:
            dn = 99999.9999 if dn > 0 else -99999.9999
        rows.append((str(uuid.uuid4()), str(code), td, up, dn))
    return rows


def upsert(cur, rows: List[tuple]) -> int:
    if not rows:
        return 0
    sql = """
        INSERT INTO stock_daily_limit (id, ts_code, trade_date, up_limit, down_limit)
        VALUES %s
        ON CONFLICT (ts_code, trade_date) DO UPDATE SET
            up_limit = EXCLUDED.up_limit,
            down_limit = EXCLUDED.down_limit,
            updated_at = CURRENT_TIMESTAMP
    """
    execute_values(cur, sql, rows, page_size=1000)
    return len(rows)


def verify(conn, start: str, end: str) -> Dict[str, Any]:
    cur = conn.cursor()
    out: Dict[str, Any] = {}
    cur.execute(
        "SELECT min(trade_date), max(trade_date), count(*), count(DISTINCT trade_date) "
        "FROM stock_daily_limit WHERE trade_date BETWEEN %s AND %s",
        (start, end),
    )
    out["min_max_rows_dates"] = [str(x) if x is not None else None for x in cur.fetchone()]
    cur.execute(
        "SELECT count(*) FILTER (WHERE up_limit IS NOT NULL), "
        "count(*) FILTER (WHERE down_limit IS NOT NULL), "
        "count(*) FILTER (WHERE pre_close IS NOT NULL OR up_percent IS NOT NULL "
        "                   OR down_percent IS NOT NULL OR price_range IS NOT NULL), count(*) "
        "FROM stock_daily_limit WHERE trade_date BETWEEN %s AND %s",
        (start, end),
    )
    out["up_down_nonnull_extra_nonnull_total"] = [int(x) for x in cur.fetchone()]
    cur.execute(
        "SELECT trade_date, count(*) FROM stock_daily_limit "
        "WHERE trade_date BETWEEN %s AND %s GROUP BY 1 ORDER BY 1",
        (start, end),
    )
    per_day = cur.fetchall()
    out["days_with_rows"] = len(per_day)
    out["max_rows_per_day"] = max((r[1] for r in per_day), default=0)
    out["min_rows_per_day"] = min((r[1] for r in per_day), default=0)
    cur.execute(
        "SELECT to_char(trade_date,'YYYY-MM') m, count(*) n FROM stock_daily_limit "
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
    conn = connect_db(write_db(env))
    try:
        end = args.end
        if not end:
            cur = conn.cursor()
            cur.execute(
                "SELECT max(cal_date) FROM trade_calendar "
                "WHERE exchange='SSE' AND is_open=TRUE AND cal_date <= CURRENT_DATE"
            )
            r = cur.fetchone()[0]
            end = str(r) if r else None
        if not end:
            raise SystemExit("无法确定结束日期")
        cal = get_calendar(conn, args.start, end)
        print(f"[daily_limit] {args.start} ~ {end}; trading days={len(cal)}; "
              f"mode={'APPLY' if args.apply else 'DRY-RUN'}", flush=True)
        if not cal.size:
            raise SystemExit("日历为空")

        total_rows = 0
        failures: List[Dict[str, Any]] = []
        per_month: Dict[str, int] = {}
        t0 = time.time()

        for i, d in enumerate(cal, start=1):
            dstr = pd.Timestamp(d).strftime("%Y%m%d")
            try:
                df = fetch_day(pro, dstr)
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
            "rows_processed": int(total_rows),
            "failures": failures,
            "per_month": [{"month": k, "rows": v} for k, v in sorted(per_month.items())],
        }
        if args.apply:
            summary["verify"] = verify(conn, args.start, end)
        LOG_DIR.mkdir(parents=True, exist_ok=True)
        out_path = LOG_DIR / "backfill_daily_limit_summary.json"
        out_path.write_text(json.dumps(summary, ensure_ascii=False, indent=2), encoding="utf-8")
        print(f"\nsummary: {out_path}")
        print(f"rows_processed={total_rows} failures={len(failures)}")
        if args.apply:
            print("verify:", json.dumps(summary["verify"], ensure_ascii=False)[:1000])
    finally:
        conn.close()


if __name__ == "__main__":
    main()
