# -*- coding: utf-8 -*-
"""日频数据底座四类门禁：dense / sparse / periodic / derived。

判据（与主设计 §6 一致）：
- dense：最新日期不落后基准日超过 1 天；最新一日行数 ≥ 近 60 日中位数的 99%；
- sparse：近 60 个交易日内有数据的天数 > 0；< 10% 记 WARN；单日行数超均值 +3σ 记 WARN；
- periodic：目录表非空；月度表最新月份不早于上一月；
- derived：预留（当前 56 张表无 derived 契约）。

用法：
  cd quant_server
  .venv/Scripts/python.exe scripts/quality/check_daily_base.py
  .venv/Scripts/python.exe scripts/quality/check_daily_base.py --table fx_daily
"""

from __future__ import annotations

import argparse
import statistics
import sys
from datetime import date, datetime, timedelta
from pathlib import Path
from typing import Dict, List, Optional, Tuple

import psycopg2
from psycopg2 import sql

SCRIPT_DIR = Path(__file__).resolve().parent
SERVER_DIR = SCRIPT_DIR.parents[1]
ENV_PATH = SERVER_DIR / ".env"

try:
    sys.stdout.reconfigure(encoding="utf-8")
except Exception:
    pass


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
    # 兼容迁移（2026-11-15）：.env 改用 DEV_DB_* / PROD_DB_* 并移除 DB_*；
    # 缺失时按 ENVIRONMENT 回填，旧脚本无需改调用方。旧键存在时不覆盖。
    _name = (env.get("ENVIRONMENT") or "development").lower()
    _pfx = "PROD_DB_" if _name == "production" else "DEV_DB_"
    for _k in ("HOST", "PORT", "USER", "PASSWORD", "NAME"):
        env.setdefault("DB_" + _k, env.get(_pfx + _k, ""))
    return env


def connect_db(env: Dict[str, str]):
    return psycopg2.connect(
        host=env["DB_HOST"], port=env["DB_PORT"], user=env["DB_USER"],
        password=env["DB_PASSWORD"], dbname=env["DB_NAME"], connect_timeout=10,
    )


def judge_dense(latest: Optional[date], expected_latest: date,
                latest_rows: int, median_rows: float) -> Tuple[str, str]:
    if latest is None or latest_rows == 0:
        return "FAIL", "无数据"
    if latest < expected_latest - timedelta(days=1):
        return "FAIL", f"最新 {latest} 落后基准 {expected_latest}"
    if median_rows > 0 and latest_rows < median_rows * 0.99:
        return "FAIL", f"当日 {latest_rows} < 中位数 {median_rows:.0f}×0.99"
    return "PASS", f"最新 {latest}，当日 {latest_rows}，中位 {median_rows:.0f}"


def judge_sparse(days_with_data: int, total_days: int,
                 counts: List[int]) -> Tuple[str, str]:
    if days_with_data == 0:
        return "FAIL", "近 60 日无数据"
    notes = [f"{days_with_data}/{total_days} 天有数据"]
    status = "PASS"
    if total_days and days_with_data < total_days * 0.1:
        status = "WARN"
        notes.append("覆盖率 <10%")
    if len(counts) >= 5:
        mean = statistics.mean(counts)
        std = statistics.pstdev(counts)
        if std > 0 and max(counts) > mean + 3 * std:
            status = "WARN" if status == "PASS" else status
            notes.append(f"单日峰值 {max(counts)} 超均值+3σ（{mean:.0f}+{3*std:.0f}）")
    return status, "；".join(notes)


def judge_periodic(latest_month: Optional[str], expected_month: str) -> Tuple[str, str]:
    if not latest_month:
        return "FAIL", "无数据"
    if latest_month < expected_month:
        return "FAIL", f"最新 {latest_month} 早于应有 {expected_month}"
    return "PASS", f"最新 {latest_month}"


def _prev_month(today: date) -> str:
    y, m = today.year, today.month - 1
    if m == 0:
        y, m = y - 1, 12
    return f"{y:04d}{m:02d}"


def _latest_trade_date(conn, today: date) -> date:
    with conn.cursor() as cur:
        cur.execute(
            "SELECT max(cal_date) FROM trade_calendar "
            "WHERE exchange='SSE' AND is_open=TRUE AND cal_date <= %s", (today,)
        )
        return cur.fetchone()[0] or today


def _daily_counts(conn, table: str, col: str, since: date) -> List[Tuple[date, int]]:
    q = sql.SQL(
        "SELECT {col}, count(*) FROM {tbl} WHERE {col} >= %s GROUP BY {col} ORDER BY {col}"
    ).format(col=sql.Identifier(col), tbl=sql.Identifier(table))
    with conn.cursor() as cur:
        cur.execute(q, (since,))
        return [(r[0], int(r[1])) for r in cur.fetchall()]


def _catalog_count(conn, table: str) -> int:
    q = sql.SQL("SELECT count(*) FROM {tbl}").format(tbl=sql.Identifier(table))
    with conn.cursor() as cur:
        cur.execute(q)
        return int(cur.fetchone()[0] or 0)


def _max_month(conn, table: str) -> Optional[str]:
    q = sql.SQL("SELECT max(month) FROM {tbl}").format(tbl=sql.Identifier(table))
    with conn.cursor() as cur:
        cur.execute(q)
        return cur.fetchone()[0]


def _max_date(conn, table: str, col: str) -> Optional[date]:
    q = sql.SQL("SELECT max({col}) FROM {tbl}").format(
        col=sql.Identifier(col), tbl=sql.Identifier(table))
    with conn.cursor() as cur:
        cur.execute(q)
        return cur.fetchone()[0]


# 源日期 → 入库业务日的偏移（与 backfill_daily_base._DATE_SHIFT_DAYS 保持一致）
DATE_SHIFT_DAYS = {"fx_daily": 1}


def check_one(conn, contract, today: date, expected_latest: date) -> Tuple[str, str]:
    from modules.data.data_contracts import date_column

    # fx_daily 存的是「源 GMT 日 +1」，且源数据 T+1 发布：
    # 周一盘中/盘后只能拿到上周五的数据（存为周六），不能按 A 股当日基准判失败。
    if contract.data_type == "fx_daily":
        d = today - timedelta(days=1)
        while d.weekday() >= 5:  # 回退到上一个工作日
            d -= timedelta(days=1)
        expected_latest = d + timedelta(days=1)
    else:
        expected_latest = expected_latest + timedelta(
            days=DATE_SHIFT_DAYS.get(contract.data_type, 0))

    if contract.gate_mode == "periodic":
        if contract.frequency == "catalog":
            n = _catalog_count(conn, contract.table)
            return ("PASS", f"{n} 行") if n > 0 else ("FAIL", "目录为空")
        if contract.frequency == "monthly":
            col = date_column(contract.data_type)
            if col == "month":
                latest = _max_month(conn, contract.table)
            else:
                latest_date = _max_date(conn, contract.table, col)
                latest = latest_date.strftime("%Y%m") if latest_date else None
            return judge_periodic(latest, _prev_month(today))
        # 日频但按周期校验：退化为新鲜度
        col = date_column(contract.data_type)
        rows = _daily_counts(conn, contract.table, col, today - timedelta(days=60))
        latest = rows[-1][0] if rows else None
        return judge_dense(latest, expected_latest, rows[-1][1] if rows else 0,
                           statistics.median([c for _, c in rows]) if rows else 0)

    col = date_column(contract.data_type)
    rows = _daily_counts(conn, contract.table, col, today - timedelta(days=60))
    if contract.gate_mode == "sparse":
        total = len(rows)
        return judge_sparse(total, 60, [c for _, c in rows])

    if not rows:
        return "FAIL", "近 60 日无数据"
    latest, latest_n = rows[-1]
    median_n = statistics.median([c for _, c in rows])
    return judge_dense(latest, expected_latest, latest_n, median_n)


def run(args) -> int:
    from modules.data.data_contracts import DATA_CONTRACTS

    env = load_env(ENV_PATH)
    conn = connect_db(env)
    today = args.today or date.today()
    expected_latest = _latest_trade_date(conn, today)
    keys = [args.table] if args.table else list(DATA_CONTRACTS)
    failed = 0
    print(f"[gate] today={today} expected_latest={expected_latest} tables={len(keys)}")
    try:
        for key in keys:
            contract = DATA_CONTRACTS.get(key)
            if contract is None:
                print(f"FAIL {key:<24} 未知契约")
                failed += 1
                continue
            try:
                status, detail = check_one(conn, contract, today, expected_latest)
            except Exception as exc:  # noqa: BLE001
                conn.rollback()
                status, detail = "FAIL", f"查询异常：{str(exc)[:160]}"
            if status == "FAIL":
                failed += 1
            print(f"{status:<4} {key:<24} {contract.gate_mode:<8} {detail}")
    finally:
        conn.close()
    print(f"SUMMARY failed={failed}/{len(keys)}")
    return 0 if failed == 0 else 1


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--table", default="", help="只检查指定 data_type")
    ap.add_argument("--today", type=str, default="", help="YYYY-MM-DD，调试用")
    args = ap.parse_args()
    if args.today:
        try:
            args.today = datetime.strptime(args.today, "%Y-%m-%d").date()
        except ValueError:
            raise SystemExit("--today 格式应为 YYYY-MM-DD")
    else:
        args.today = None
    return run(args)


if __name__ == "__main__":
    sys.exit(main())
