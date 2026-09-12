# -*- coding: utf-8 -*-
"""
覆盖度回填脚本 — 修复日频数据表的内部空洞
================================================================================
背景：
    同步逻辑用全局 MAX(trade_date) 判断滞后，无法发现「内部空洞」——即
    两端有数据、中间整段缺失的表（如 stock_daily_basic 深市主板
    2022-03~2026-04 空洞，000001.SZ 全局 max=2026-08-21 被误判为最新）。

原理：
    以 stock_daily（完整日线基准）为日期基准，比较目标表每只股票在窗口内的
    日期覆盖；覆盖 < 阈值 且缺失天数 >= 最小阈值的股票判定为空洞股票。
    对空洞股票取缺失日期段 [min_missing, max_missing]，按 chunk_days 分块
    从 Tushare 回填（幂等 upsert，已存在日期原地更新无害）。

并发：
    Tushare 同步调用沉入线程池（--workers），每个回填任务用独立 async 会话，
    全局限流 <= ~400 次/分钟（Tushare daily_basic/moneyflow 500-600/min 留余量）。

用法（quant_server/ 下）：
    .venv/Scripts/python.exe scripts/backfill_coverage_gaps.py                            # 全量回填 daily_basic + moneyflow
    .venv/Scripts/python.exe scripts/backfill_coverage_gaps.py --table daily_basic
    .venv/Scripts/python.exe scripts/backfill_coverage_gaps.py --workers 4
    .venv/Scripts/python.exe scripts/backfill_coverage_gaps.py --limit 20 --dry-run       # 小规模预检（只检测不回填）

幂等：bulk_upsert 按 (ts_code, trade_date) ON CONFLICT DO UPDATE。
"""
import argparse
import asyncio
import logging
import sys
import threading
import time
from concurrent.futures import ThreadPoolExecutor
from datetime import date, timedelta
from pathlib import Path

_PROJECT_ROOT = Path(__file__).resolve().parent.parent
if str(_PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(_PROJECT_ROOT))

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
logger = logging.getLogger("backfill_coverage")

from sqlalchemy import text
from sqlalchemy.ext.asyncio import create_async_engine, async_sessionmaker

from modules.data.services.sync_service import _convert_records_datetime, _preprocess_records
from shared.database.models.data_models import StockDailyBasic, StockMoneyflow
from shared.database.repositories.market.fundamental.stock_daily_basic_repo import (
    StockDailyBasicRepository,
)
from shared.database.repositories.market.fundamental.stock_moneyflow_repo import (
    StockMoneyflowRepository,
)

# 目标表配置：逻辑名 → (表名, ORM 模型, Repository, Tushare 接口方法名, 排除北交所?)
# moneyflow 排除北交所：Tushare 资金流向接口不含 920xxx.BJ，属数据源覆盖限制，不可回填。
TABLE_CONFIGS = {
    "daily_basic": ("stock_daily_basic", StockDailyBasic, StockDailyBasicRepository, "daily_basic", False),
    "moneyflow": ("stock_moneyflow", StockMoneyflow, StockMoneyflowRepository, "moneyflow", True),
}

# 默认参数
DEFAULT_THRESHOLD = 0.90          # 覆盖 < 90% 判定为空洞
DEFAULT_MIN_MISSING = 20          # 缺失天数 >= 20 才判定（过滤单日噪声）
CHUNK_DAYS = 600                  # 单次拉取最大日历跨度（规避 Tushare 行数上限）
DEFAULT_WORKERS = 4               # 并发线程数

# ---- 线程安全全局限流（跨 worker 共享，<= ~400 次/分钟）----
_RATE_MIN_INTERVAL = 0.15
_rate_lock = threading.Lock()
_rate_last = 0.0


def _throttled_fetch(fn, kwargs: dict):
    """线程安全限流后执行同步 Tushare 调用（tushare API 需关键字参数）"""
    global _rate_last
    with _rate_lock:
        now = time.time()
        wait = _RATE_MIN_INTERVAL - (now - _rate_last)
        if wait > 0:
            time.sleep(wait)
        _rate_last = time.time()
    return fn(**kwargs)


def _load_env() -> dict:
    env = {}
    p = Path(__file__).resolve().parents[1] / ".env"
    if p.exists():
        for line in p.read_text(encoding="utf-8", errors="ignore").splitlines():
            line = line.strip()
            if line and not line.startswith("#") and "=" in line:
                k, _, v = line.partition("=")
                env[k.strip()] = v.strip()
    return env


def _chunk_range(start: date, end: date, days: int):
    """将 [start, end] 按 <=days 日历日切块，返回 [(s, e), ...]"""
    chunks = []
    cur = start
    while cur <= end:
        nxt = min(cur + timedelta(days=days - 1), end)
        chunks.append((cur, nxt))
        cur = nxt + timedelta(days=1)
    return chunks


async def _detect_gap_stocks(session, table: str, window_start: date,
                             threshold: float, min_missing: int, exclude_bj: bool) -> list:
    """检测空洞股票，返回 ts_code 列表。

    两趟聚合（避免全表 JOIN），在 Python 中按 ts_code 比对覆盖：
    stock_daily 基准日期数 vs 目标表日期数。
    exclude_bj=True：排除北交所（数据源不含 BJ 时，如 moneyflow）。
    """
    _bj = "AND ts_code NOT LIKE '%.BJ'" if exclude_bj else ""
    sd = await session.execute(text(
        "SELECT ts_code, COUNT(DISTINCT trade_date) AS nd "
        "FROM stock_daily WHERE trade_date >= :ws {bj} GROUP BY ts_code".format(bj=_bj)),
        {"ws": window_start})
    sd_map = {r[0]: int(r[1]) for r in sd.fetchall()}

    tg = await session.execute(text(
        f"SELECT ts_code, COUNT(DISTINCT trade_date) AS nd "
        f"FROM {table} WHERE trade_date >= :ws GROUP BY ts_code"),
        {"ws": window_start})
    tg_map = {r[0]: int(r[1]) for r in tg.fetchall()}

    gaps = []
    for code, expected in sd_map.items():
        actual = tg_map.get(code, 0)
        if actual < expected * threshold and (expected - actual) >= min_missing:
            gaps.append(code)
    return gaps


async def _get_missing_span(session, table: str, code: str, window_start: date):
    """返回该股在 stock_daily 有、目标表无的日期跨度为 (start, end)，无缺失返回 None。"""
    r = await session.execute(text(
        "SELECT MIN(s.trade_date), MAX(s.trade_date) "
        "FROM stock_daily s LEFT JOIN {t} x ON x.ts_code = s.ts_code AND x.trade_date = s.trade_date "
        "WHERE s.ts_code = :c AND s.trade_date >= :ws AND x.ts_code IS NULL".format(t=table)),
        {"c": code, "ws": window_start})
    row = r.fetchone()
    if not row or row[0] is None:
        return None
    return (row[0].date() if hasattr(row[0], "date") else row[0],
            row[1].date() if hasattr(row[1], "date") else row[1])


async def _backfill_stock(Session, tbl: str, Model, RepoCls, fetch_fn, code: str,
                          window_start: date, pool: ThreadPoolExecutor) -> bool:
    """回填单只股票：独立 async 会话；缺失跨度按 chunk 分块，Tushare 调用沉入共享线程池。"""
    loop = asyncio.get_event_loop()
    known_cols = {c.name for c in Model.__table__.columns}
    try:
        async with Session() as s:
            span = await _get_missing_span(s, tbl, code, window_start)
            if not span:
                return True
            repo = RepoCls(s)
            for cs, ce in _chunk_range(span[0], span[1], CHUNK_DAYS):
                df = await loop.run_in_executor(
                    pool, _throttled_fetch, fetch_fn,
                    {"ts_code": code,
                     "start_date": cs.strftime("%Y%m%d"),
                     "end_date": ce.strftime("%Y%m%d")})
                if df is None or df.empty:
                    continue
                data = _convert_records_datetime(df.to_dict("records"))
                _preprocess_records(data, date_fields=["trade_date"], known_cols=known_cols)
                # 去重 (ts_code, trade_date)：Tushare 偶发重复行
                seen, deduped = set(), []
                for item in reversed(data):
                    key = (item.get("ts_code"), item.get("trade_date"))
                    if key not in seen:
                        seen.add(key)
                        deduped.append(item)
                if deduped:
                    await repo.bulk_upsert(deduped)
            await s.commit()
        return True
    except Exception as e:
        logger.error("[%s] %s 回填失败: %s", tbl, code, str(e)[:150])
        return False


async def main(limit: int, table: str, start: str, dry_run: bool, workers: int) -> None:
    env = _load_env()
    token = env.get("PROD_TUSHARE_TOKEN", "")
    if not token:
        logger.error("PROD_TUSHARE_TOKEN 未配置，无法从 Tushare 补数")
        return

    import tushare as ts
    pro = ts.pro_api(token)

    user = env.get("DB_USER", "postgres")
    password = env.get("DB_PASSWORD", "")
    host = env.get("DB_HOST", "localhost")
    port = env.get("DB_PORT", "5432")
    dbname = env.get("DB_NAME", "quant_signals_dev")
    url = f"postgresql+asyncpg://{user}:{password}@{host}:{port}/{dbname}"
    engine = create_async_engine(url)
    Session = async_sessionmaker(engine, expire_on_commit=False)

    table_names = list(TABLE_CONFIGS.keys()) if table == "all" else [table]
    total_done, total_failed = 0, 0

    async with Session() as session:
        for tname in table_names:
            if tname not in TABLE_CONFIGS:
                logger.warning("未知表 %s，可选：%s", tname, ",".join(TABLE_CONFIGS))
                continue
            tbl, Model, RepoCls, api, exclude_bj = TABLE_CONFIGS[tname]

            # 窗口起点：目标表最小日期 与 2018-01-01 取较大者。
            # 原因：Tushare 各股数据起点不同（如 moneyflow 部分股票 2010 年才有），
            # 若窗口过早会把"数据源本就没有"的区间误判为空洞。2018 起所有日频
            # 接口对全市场覆盖稳定，可安全作为检测基准。
            r = await session.execute(text(f"SELECT MIN(trade_date) FROM {tbl}"))
            w = r.scalar()
            table_min = w.date() if hasattr(w, "date") else w
            default_ws = max(table_min, date(2018, 1, 1))
            window_start = date.fromisoformat(start) if start else default_ws
            logger.info("[%s] 检测窗口起点 %s", tbl, window_start)

            gaps = await _detect_gap_stocks(session, tbl, window_start,
                                            DEFAULT_THRESHOLD, DEFAULT_MIN_MISSING, exclude_bj)
            codes = sorted(gaps)
            if limit and limit > 0:
                codes = codes[:limit]
            logger.info("[%s] 空洞股票 %d 只，本次处理 %d 只", tbl, len(gaps), len(codes))

            if dry_run:
                for code in codes[:20]:
                    span = await _get_missing_span(session, tbl, code, window_start)
                    logger.info("  预检 %s: 缺失跨度 %s ~ %s", code, span[0] if span else "-",
                                span[1] if span else "-")
                continue

            fetch_fn = getattr(pro, api)
            sem = asyncio.Semaphore(workers * 2)
            pool = ThreadPoolExecutor(max_workers=workers, thread_name_prefix="bfill_")
            done, failed = 0, 0

            async def _guard(code):
                nonlocal done, failed
                async with sem:
                    ok = await _backfill_stock(Session, tbl, Model, RepoCls, fetch_fn,
                                               code, window_start, pool)
                    if ok:
                        done += 1
                    else:
                        failed += 1
                    if (done + failed) % 50 == 0:
                        logger.info("[%s] 进度 %d/%d, 成功 %d, 失败 %d",
                                    tbl, done + failed, len(codes), done, failed)

            await asyncio.gather(*[_guard(c) for c in codes])
            pool.shutdown(wait=True)
            logger.info("[%s] 完成: 成功 %d, 失败 %d", tbl, done, failed)
            total_done += done
            total_failed += failed

    await engine.dispose()
    logger.info("全部完成: 成功 %d, 失败 %d", total_done, total_failed)


if __name__ == "__main__":
    ap = argparse.ArgumentParser(description="覆盖度回填：修复内部空洞")
    ap.add_argument("--table", default="all", help="daily_basic | moneyflow | all")
    ap.add_argument("--limit", type=int, default=0, help="只处理前 N 只（0=全量）")
    ap.add_argument("--start", default="", help="检测窗口起点 YYYY-MM-DD（默认取表最小日期与2018取大）")
    ap.add_argument("--dry-run", action="store_true", help="只检测不回填")
    ap.add_argument("--workers", type=int, default=DEFAULT_WORKERS, help="并发线程数（默认4）")
    args = ap.parse_args()
    asyncio.run(main(limit=args.limit, table=args.table, start=args.start,
                     dry_run=args.dry_run, workers=args.workers))
