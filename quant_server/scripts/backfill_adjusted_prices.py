# -*- coding: utf-8 -*-
"""
回填股票复权价格到 stock_adjusted_prices 预计算表
=====================================================
背景：data_feed_engine 每次回测在线复权（price × adj_factor / latest_factor）
很慢。本脚本用 SQL 批量预计算 qfq 复权价格写入预计算表，
此后回测直接读表，不再在线计算。

算法（与 data_feed_engine.py 在线复权完全一致）：
    qfq_price = raw_price × adj_factor / latest_factor
    其中 latest_factor = 该股票全历史最新一日的复权因子（归一化：最新价=真实市场价）

增量判断：用「最新交易日已覆盖的股票」集合（走 trade_date 分区索引，快）。

容错：每批 try/except，单批失败打印警告并继续下一批，不中断整个任务。

幂等：按 (ts_code, trade_date) upsert。

用法：
    python scripts/backfill_adjusted_prices.py [--mainboard] [--start-date 2021-08-10]

参数：
    --mainboard      只回填主板股票（00/60/002 开头，约 2879 只）。策略 v5.0 只交易主板，
                     不需要科创板(688)/创业板(300)/北交所。默认关（回填全部在市股票）。
    --start-date     只回填该日期之后的行情（默认 1990-01-01 全量）。
                     建议配合回测区间起点，如 2021-08-10，大幅减少数据量。
"""
import os
import sys
import time
import traceback
import argparse
from pathlib import Path

# 用脚本自身路径定位 .env，与 cwd 解耦（后台运行也能找到）
_SCRIPT_DIR = Path(__file__).resolve().parent
env_path = _SCRIPT_DIR.parent / ".env"  # scripts/../.env = quant_server/.env
for line in env_path.read_text(encoding="utf-8").splitlines():
    line = line.strip()
    if line and not line.startswith("#") and "=" in line:
        k, v = line.split("=", 1)
        os.environ.setdefault(k, v)

import psycopg2

BATCH = 500  # 每批股票数

# 主板前缀（与策略 _is_tradable 一致）：000/002/600/603/601/605
ALLOW_PREFIXES = ("000", "002", "600", "603", "601", "605")
FORBID_PREFIXES = ("300", "688", "8", "4", "001", "003")


def get_conn():
    return psycopg2.connect(
        host=os.environ.get("DB_HOST", "localhost"),
        port=int(os.environ.get("DB_PORT", 5432)),
        user=os.environ.get("DB_USER", "postgres"),
        password=os.environ.get("DB_PASSWORD", ""),
        dbname=os.environ.get("DB_NAME", "quant_signals_dev"),
    )


def is_mainboard(ts_code: str) -> bool:
    sc = ts_code.split(".")[0]
    if sc.startswith(FORBID_PREFIXES):
        return False
    return sc.startswith(ALLOW_PREFIXES)


def main():
    parser = argparse.ArgumentParser(description="回填复权价格")
    parser.add_argument("--mainboard", action="store_true",
                        help="只回填主板股票（00/60/002 开头）")
    parser.add_argument("--start-date", default="1990-01-01",
                        help="只回填该日期之后的行情（默认全量）")
    args = parser.parse_args()

    conn = get_conn()
    cur = conn.cursor()

    # 1. 全市场在市股票（可选：只主板）
    cur.execute("SELECT ts_code FROM stock_basic WHERE list_status='L'")
    all_codes = [r[0] for r in cur.fetchall()]
    if args.mainboard:
        all_codes = [c for c in all_codes if is_mainboard(c)]
    print(f"在市股票总数: {len(all_codes)}"
          f"{' (主板子集)' if args.mainboard else ''}", flush=True)

    # 2. 增量：最新交易日已覆盖的股票（走 trade_date 分区，快）
    cur.execute(
        "SELECT DISTINCT ts_code FROM stock_adjusted_prices "
        "WHERE trade_date = (SELECT MAX(trade_date) FROM stock_adjusted_prices)"
    )
    done = {r[0] for r in cur.fetchall()}
    todo = [c for c in all_codes if c not in done]
    print(f"已有复权数据: {len(done)} 只, 待回填: {len(todo)} 只", flush=True)

    if not todo:
        print("全部已回填，无需处理")
        cur.close()
        conn.close()
        return

    t0 = time.time()
    total_rows = 0
    n_batch = (len(todo) + BATCH - 1) // BATCH
    start_date = args.start_date

    for i in range(0, len(todo), BATCH):
        batch = todo[i:i + BATCH]
        placeholders = ",".join(["%s"] * len(batch))
        try:
            cur.execute(f"""
                WITH latest_f AS (
                    SELECT DISTINCT ON (s.ts_code) s.ts_code, s.adj_factor AS latest_factor
                    FROM stock_adj_factor s
                    WHERE s.ts_code IN ({placeholders})
                    ORDER BY s.ts_code, s.trade_date DESC
                ),
                daily AS (
                    SELECT d.ts_code, d.trade_date, d.open, d.high, d.low, d.close,
                           d.pre_close, d.change, d.pct_chg, d.vol, d.amount,
                           COALESCE(f.adj_factor, 1.0) AS factor
                    FROM stock_daily d
                    LEFT JOIN stock_adj_factor f
                        ON d.ts_code = f.ts_code AND d.trade_date = f.trade_date
                    WHERE d.ts_code IN ({placeholders})
                      AND d.trade_date >= %s::date
                ),
                computed AS (
                    SELECT d.ts_code, d.trade_date,
                           d.open  * d.factor / l.latest_factor AS open,
                           d.high  * d.factor / l.latest_factor AS high,
                           d.low   * d.factor / l.latest_factor AS low,
                           d.close * d.factor / l.latest_factor AS close,
                           d.pre_close * d.factor / l.latest_factor AS pre_close,
                           d.change * d.factor / l.latest_factor AS change,
                           d.pct_chg, d.vol, d.amount,
                           d.factor AS adj_factor
                    FROM daily d
                    JOIN latest_f l ON d.ts_code = l.ts_code
                    WHERE l.latest_factor > 0
                )
                INSERT INTO stock_adjusted_prices
                    (ts_code, trade_date, asset_type, adj_type, freq,
                     open, high, low, close, pre_close, change, pct_chg, vol, amount, adj_factor)
                SELECT ts_code, trade_date, 'E', 'qfq', 'D',
                       open, high, low, close, pre_close, change, pct_chg, vol, amount, adj_factor
                FROM computed
                ON CONFLICT (ts_code, trade_date) DO UPDATE SET
                    open = EXCLUDED.open, high = EXCLUDED.high, low = EXCLUDED.low,
                    close = EXCLUDED.close, pre_close = EXCLUDED.pre_close,
                    change = EXCLUDED.change, pct_chg = EXCLUDED.pct_chg,
                    vol = EXCLUDED.vol, amount = EXCLUDED.amount,
                    adj_factor = EXCLUDED.adj_factor, updated_at = CURRENT_TIMESTAMP
            """, batch + batch + [start_date])
            conn.commit()
            total_rows += cur.rowcount
        except Exception as e:
            conn.rollback()
            print(f"  批次 {i//BATCH+1}/{n_batch} 失败，跳过: {e}", flush=True)
            traceback.print_exc()

        if (i // BATCH + 1) % 5 == 0 or i + BATCH >= len(todo):
            elapsed = time.time() - t0
            print(f"  批次 {(i//BATCH)+1}/{n_batch} "
                  f"({min(i+BATCH, len(todo))}/{len(todo)}) 已写入 {total_rows} 行 "
                  f"耗时 {elapsed:.0f}s", flush=True)

    cur.close()
    conn.close()
    print(f"完成: 回填 {len(todo)} 只股票, 共 {total_rows} 行复权数据, 总耗时 {time.time()-t0:.0f}s", flush=True)


if __name__ == "__main__":
    main()
