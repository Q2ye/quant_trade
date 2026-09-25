# -*- coding: utf-8 -*-
"""回填停复牌历史（`stock_suspend_info`）。

## 背景

`01_数据质量标准.md` §四 要求「`vol=0` 须先用 `stock_suspend_info` 区分『停牌』与『数据缺失』」，
但 2026-09-19 五门实测已记录：**该要求在回测场景下无法执行**（表内仅 4 个月历史）。

**根因**（读码实证，非推测）：`sync_service._sync_suspend_info` 在无日期入参时
```
start_date = end_date - timedelta(days=30)     # sync_service.py:4600-4601
```
→ 日终每天只覆盖最近 30 天，**历史永不累积**。任务本身没坏。

**后果**：148 只「数据提前结束」的标的里，退市与长期停牌混在一起分不开（如信威集团连停 730 个交易日）。

## ⚠️ 两个实测陷阱（本脚本已处理）

1. **`suspend_d` 单次返回上限 5,000 行，且静默截断**
   实测：2018-01 一次拉恰好 5,000；分 4 周合计 **5,017** ⇒ 必须分块 + 每块断言。
2. **`trade_date` 是 `TIMESTAMPTZ`，存的是「业务日 00:00 Asia/Shanghai」**
   实测：`raw = 2026-05-07 16:00Z` → 业务日 = `2026-05-08`。
   ⇒ 写入**显式**构造 +08:00，不裸插 `date`（裸插会依赖 session TZ）。
   ⇒ 读取一律用 `(trade_date AT TIME ZONE 'Asia/Shanghai')::date`。

## 口径

    来源 : Tushare `suspend_d(start_date, end_date)` → ts_code, trade_date, suspend_timing, suspend_type
    分块 : 按自然周（连续 7 天窗口）；若某块返回 == 5000 → 自动降级为按日重拉该块
    写入 : `ON CONFLICT (ts_code, trade_date, suspend_type) DO NOTHING` —— **不覆盖任何已有行**
    幂等 : 可反复重跑，新增恒为 0

⚠️ **本表当前无任何读取方**（全局唯一写入方是 sync）→ 本脚本不修复正在坏的功能，
   它的价值是**解锁**「停牌 / 数据缺失 / 退市」三分类，以及为事件型策略准备输入。

## 用法（CWD=quant_server）

    # 小样本先行（52 次调用）——验证脚本端到端
    python scripts/data/backfill_suspend_info.py --start 20240101 --end 20241231

    # 全量：dry-run（拉取 + 缓存 + 统计，**不写库**）
    python scripts/data/backfill_suspend_info.py

    # 写库（复用缓存，不重复消耗配额）
    python scripts/data/backfill_suspend_info.py --apply

    # 只跑五门验证（不拉取、不写库）
    python scripts/data/backfill_suspend_info.py --verify
"""
import argparse
import asyncio
import logging
import os
import pickle
import sys
import tempfile
import uuid
from datetime import date, datetime, timedelta, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

try:
    sys.stdout.reconfigure(encoding="utf-8")  # type: ignore[union-attr]
    sys.stderr.reconfigure(encoding="utf-8")  # type: ignore[union-attr]
except Exception:
    pass

import pandas as pd  # noqa: E402

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
logger = logging.getLogger(__name__)

SLEEP = 0.35                     # Tushare 限频间隔（对齐 backfill_delisted_stocks.py）
API_CAP = 5000                   # suspend_d 单次返回上限（实测确认）
DEFAULT_START = "20160101"
CST = timezone(timedelta(hours=8))   # 上海自 1991 年起无夏令时，固定 +08:00 精确

CACHE_PATH = os.path.join(tempfile.gettempdir(), "suspend_backfill_cache.pkl")


# ────────────────────────── 工具 ──────────────────────────
def _get_db_config() -> dict:
    from shared.config.config_manager import config
    db = config.settings.DATABASE
    return {"host": db.HOST, "port": int(db.PORT), "user": db.USER,
            "password": db.PASSWORD, "database": db.NAME}


def _to_date(v: Any) -> Optional[date]:
    """Tushare 日期（'YYYYMMDD' / datetime64）→ date；无效返回 None。"""
    if v is None:
        return None
    if isinstance(v, datetime):
        return v.date()
    if isinstance(v, date):
        return v
    s = str(v).strip()[:10].replace("-", "")
    if len(s) != 8 or not s.isdigit():
        return None
    try:
        return date(int(s[:4]), int(s[4:6]), int(s[6:8]))
    except ValueError:
        return None


def _txt(v: Any) -> Optional[str]:
    """→ str；缺失/无效 → None（pandas sanitizer 会把缺失变成 float 0.0/NaN）。"""
    if v is None or isinstance(v, float):
        return None
    s = str(v).strip()
    return s if s and s.lower() not in ("nan", "none") else None


def _to_cst(d: date) -> datetime:
    """业务日 → 库内约定值：该日 00:00 Asia/Shanghai。"""
    return datetime(d.year, d.month, d.day, tzinfo=CST)


def _week_chunks(start: date, end: date) -> List[Tuple[date, date]]:
    """按连续 7 天窗口切分。"""
    out, cur = [], start
    while cur <= end:
        stop = min(cur + timedelta(days=6), end)
        out.append((cur, stop))
        cur = stop + timedelta(days=1)
    return out


# ────────────────────────── 拉取 ──────────────────────────
async def fetch_all(src, start: date, end: date, max_weeks: int = 0) -> Tuple[pd.DataFrame, Dict[str, Any]]:
    """分块拉取；撞 5000 上限的块自动降级按日。"""
    chunks = _week_chunks(start, end)
    if max_weeks:
        chunks = chunks[:max_weeks]
    frames: List[pd.DataFrame] = []
    calls = fallback_chunks = 0
    stats = {"calls": 0, "fallback_chunks": 0, "empty_chunks": 0, "failed_chunks": 0}

    for i, (ws, we) in enumerate(chunks, 1):
        try:
            df = await asyncio.to_thread(
                src.get_suspended, start_date=ws.strftime("%Y%m%d"), end_date=we.strftime("%Y%m%d"))
            calls += 1
            await asyncio.sleep(SLEEP)
        except Exception as e:
            logger.warning("块 %s~%s 拉取失败: %s: %s", ws, we, type(e).__name__, e)
            stats["failed_chunks"] += 1
            continue

        if df is None or df.empty:
            stats["empty_chunks"] += 1
            continue

        if len(df) >= API_CAP:
            # ⚠️ 撞 5000 上限 → 该块被截断，降级按日重拉
            fallback_chunks += 1
            logger.info("  块 %s~%s 返回 %d（撞上限）→ 降级按日重拉", ws, we, len(df))
            day = ws
            while day <= we:
                try:
                    ddf = await asyncio.to_thread(
                        src.get_suspended, start_date=day.strftime("%Y%m%d"),
                        end_date=day.strftime("%Y%m%d"))
                    calls += 1
                    await asyncio.sleep(SLEEP)
                    if ddf is not None and not ddf.empty:
                        if len(ddf) >= API_CAP:
                            logger.warning("    ⚠️ 单日 %s 仍返回 %d（进一步截断，需人工介入）", day, len(ddf))
                        frames.append(ddf)
                except Exception as e:
                    logger.warning("    单日 %s 失败: %s", day, type(e).__name__)
                    stats["failed_chunks"] += 1
                day += timedelta(days=1)
        else:
            frames.append(df)

        if i % 50 == 0 or i == len(chunks):
            logger.info("  进度 %d/%d 块，累计调用 %d 次，累计行 %d",
                        i, len(chunks), calls, sum(len(f) for f in frames))

    stats["calls"] = calls
    stats["fallback_chunks"] = fallback_chunks
    if not frames:
        return pd.DataFrame(), stats
    return pd.concat(frames, ignore_index=True), stats


def _normalize(df: pd.DataFrame) -> List[Dict[str, Any]]:
    """→ 待写记录（去重 + 时区显式 + 字段清洗）。"""
    if df.empty:
        return []
    seen: set = set()
    records: List[Dict[str, Any]] = []
    for row in df.to_dict("records"):
        code = _txt(row.get("ts_code"))
        td = _to_date(row.get("trade_date"))
        st = _txt(row.get("suspend_type"))
        if not code or td is None or st not in ("S", "R"):
            continue
        key = (code, td, st)
        if key in seen:            # Tushare 分块边界可能重复
            continue
        seen.add(key)
        records.append({
            "id": str(uuid.uuid4()),
            "ts_code": code,
            "trade_date": _to_cst(td),
            "suspend_timing": _txt(row.get("suspend_timing")),
            "suspend_type": st,
        })
    return records


async def write_records(conn, records: List[Dict[str, Any]], batch: int = 5000) -> int:
    """批量写库（ON CONFLICT DO NOTHING → 幂等、不覆盖）。"""
    total = 0
    for i in range(0, len(records), batch):
        chunk = records[i:i + batch]
        await conn.executemany("""
            INSERT INTO stock_suspend_info (id, ts_code, trade_date, suspend_timing, suspend_type)
            VALUES ($1, $2, $3, $4, $5)
            ON CONFLICT (ts_code, trade_date, suspend_type) DO NOTHING
        """, [(r["id"], r["ts_code"], r["trade_date"], r["suspend_timing"], r["suspend_type"])
              for r in chunk])
        total += len(chunk)
    return total


# ────────────────────────── 五门验证 ──────────────────────────
async def verify(conn, raw_df: Optional[pd.DataFrame] = None) -> bool:
    """对齐 `01_数据质量标准.md` 五道门。返回是否全绿。"""
    ok = True
    logger.info("=" * 76)
    logger.info("五门验证")

    # 门 1 覆盖
    logger.info("[门1] 覆盖（逐年）")
    y0 = y1 = None
    for r in await conn.fetch("""
            SELECT EXTRACT(YEAR FROM trade_date AT TIME ZONE 'Asia/Shanghai')::int y,
                   COUNT(*) n, COUNT(DISTINCT ts_code) c,
                   SUM(CASE WHEN suspend_type='S' THEN 1 ELSE 0 END) ns,
                   SUM(CASE WHEN suspend_type='R' THEN 1 ELSE 0 END) nr
            FROM stock_suspend_info GROUP BY 1 ORDER BY 1"""):
        logger.info("   %s  行 %8s  标的 %5s  S=%7s  R=%6s",
                    r["y"], f"{int(r['n']):,}", f"{int(r['c'])}",
                    f"{int(r['ns'] or 0):,}", f"{int(r['nr'] or 0):,}")
        y0 = r["y"] if y0 is None else y0
        y1 = r["y"]
    if y0 is None:
        logger.error("   表为空")
        return False

    # 门 2 正确性：取值域 + 无周末
    logger.info("[门2] 正确性")
    r = await conn.fetchrow("""
        SELECT COUNT(*) FILTER (WHERE suspend_type NOT IN ('S','R')) bad_type,
               COUNT(*) FILTER (WHERE trade_date IS NULL) null_date,
               COUNT(*) FILTER (WHERE ts_code IS NULL) null_code
        FROM stock_suspend_info""")
    bad_type, null_date, null_code = int(r["bad_type"]), int(r["null_date"]), int(r["null_code"])
    logger.info("   非法 suspend_type = %d（应 0） | trade_date NULL = %d | ts_code NULL = %d",
                bad_type, null_date, null_code)
    if bad_type or null_date or null_code:
        ok = False

    r = await conn.fetchrow("""
        SELECT COUNT(*) n FROM stock_suspend_info
        WHERE EXTRACT(ISODOW FROM trade_date AT TIME ZONE 'Asia/Shanghai') >= 6""")
    weekend = int(r["n"])
    logger.info("   周末业务日 = %d（应 0）", weekend)
    if weekend:
        ok = False

    # 门 3 时区：与原始 Tushare 数据逐条比对
    logger.info("[门3] 时区（抽样比对原始 Tushare trade_date）")
    if raw_df is not None and not raw_df.empty:
        raw_pairs = set()
        for row in raw_df.to_dict("records"):
            d = _to_date(row.get("trade_date"))
            c = _txt(row.get("ts_code"))
            if d and c:
                raw_pairs.add((c, d))
        db_pairs = {(r["ts_code"], r["d"]) for r in await conn.fetch("""
            SELECT DISTINCT ts_code, (trade_date AT TIME ZONE 'Asia/Shanghai')::date d
            FROM stock_suspend_info""")}
        both = raw_pairs & db_pairs
        logger.info("   原始 %s 条 / 库内 %s 条 / 交集 %s 条",
                    f"{len(raw_pairs):,}", f"{len(db_pairs):,}", f"{len(both):,}")
        if len(raw_pairs) > 0 and len(both) / len(raw_pairs) < 0.99:
            logger.error("   ❌ 交集占比 %.2f%% < 99%% → 时区口径可能不一致", len(both) / len(raw_pairs) * 100)
            ok = False
        else:
            logger.info("   ✅ 时区一致")
    else:
        logger.info("   （无原始数据可比对，跳过）")

    # 门 4 一致性：停牌日的标的在 stock_daily 应无行情行
    logger.info("[门4] 一致性（停牌 S 日 vs stock_daily 无行情行）")
    r = await conn.fetchrow("""
        WITH s AS (SELECT DISTINCT ts_code, (trade_date AT TIME ZONE 'Asia/Shanghai')::date d
                   FROM stock_suspend_info WHERE suspend_type='S')
        SELECT COUNT(*) n FROM s
        JOIN stock_daily dd ON dd.ts_code = s.ts_code AND dd.trade_date = s.d""")
    conflict = int(r["n"])
    r2 = await conn.fetchrow("SELECT COUNT(*) n FROM stock_suspend_info WHERE suspend_type='S'")
    tot_s = int(r2["n"])
    pct = conflict / tot_s * 100 if tot_s else 0.0
    logger.info("   停牌 S 记录 %s 条，其中 stock_daily **仍有行情** 的 %s 条（%.2f%%）",
                f"{tot_s:,}", f"{conflict:,}", pct)
    logger.info("   （注：`suspend_timing` 为盘中临时停牌时当日仍有行情，属正常；须抽查归因）")

    logger.info("[门5] 运行期：回填后请另跑 `scripts/quality/check_all.py`")
    logger.info("=" * 76)
    return ok


# ────────────────────────── 主流程 ──────────────────────────
async def main(args: argparse.Namespace) -> int:
    import asyncpg

    start = _to_date(args.start) or _to_date(DEFAULT_START)
    end = _to_date(args.end) or date.today()
    assert start and end
    conn = await asyncpg.connect(**_get_db_config())
    try:
        if args.verify:
            raw = None
            if os.path.exists(CACHE_PATH):
                with open(CACHE_PATH, "rb") as f:
                    raw = pickle.load(f)
                logger.info("已载入缓存 %s（%d 行）", CACHE_PATH, len(raw))
            return 0 if await verify(conn, raw) else 1

        # ── 取数（优先复用缓存） ──
        raw_df = None
        if os.path.exists(CACHE_PATH) and not args.refresh:
            with open(CACHE_PATH, "rb") as f:
                raw_df = pickle.load(f)
            logger.info("复用缓存 %s（%d 行）—— 不消耗配额。加 --refresh 可强制重拉",
                        CACHE_PATH, len(raw_df))
            stats = {"calls": 0, "fallback_chunks": 0, "empty_chunks": 0, "failed_chunks": 0}
        else:
            from shared.sources.tushare_source import TushareSource
            logger.info("拉取 %s ~ %s（按周分块，上限 %d 行/块）", start, end, API_CAP)
            raw_df, stats = await fetch_all(TushareSource(), start, end, max_weeks=args.max_weeks)
            if raw_df.empty:
                logger.error("未取到任何数据，退出")
                return 1
            with open(CACHE_PATH, "wb") as f:
                pickle.dump(raw_df, f)
            logger.info("原始 %d 行 → 已缓存 %s", len(raw_df), CACHE_PATH)

        records = _normalize(raw_df)
        logger.info("规范化后 %d 条（去重后）", len(records))
        logger.info("  调用 %d 次 | 降级块 %d | 空块 %d | 失败块 %d",
                    stats["calls"], stats["fallback_chunks"],
                    stats["empty_chunks"], stats["failed_chunks"])

        if not args.apply:
            logger.info("=" * 76)
            logger.info("**dry-run：未写任何数据**。确认无误后加 --apply")
            # dry-run 也给出覆盖预览
            yrs: Dict[int, int] = {}
            for r in records:
                yrs[r["trade_date"].year] = yrs.get(r["trade_date"].year, 0) + 1
            for y in sorted(yrs):
                logger.info("   %s  %8s 行", y, f"{yrs[y]:,}")
            return 0

        written = await write_records(conn, records)
        logger.info("写入 %d 条（ON CONFLICT DO NOTHING，新增以库内为准）", written)

        # 幂等性自检：再写一遍，新增应为 0
        r0 = await conn.fetchrow("SELECT COUNT(*) n FROM stock_suspend_info")
        await write_records(conn, records)
        r1 = await conn.fetchrow("SELECT COUNT(*) n FROM stock_suspend_info")
        logger.info("幂等自检：写前 %s → 写后 %s（差 %d，应 0）",
                    f"{int(r0['n']):,}", f"{int(r1['n']):,}", int(r1["n"]) - int(r0["n"]))

        return 0 if await verify(conn, raw_df) else 1
    finally:
        await conn.close()


def _parse_args() -> argparse.Namespace:
    p = argparse.ArgumentParser(description="回填停复牌历史（stock_suspend_info）")
    p.add_argument("--apply", action="store_true", help="实际写库（默认 dry-run）")
    p.add_argument("--verify", action="store_true", help="只跑五门验证，不拉取不写库")
    p.add_argument("--refresh", action="store_true", help="忽略缓存，强制重新拉取")
    p.add_argument("--start", default="", help="起始日 YYYYMMDD（默认 20160101）")
    p.add_argument("--end", default="", help="结束日 YYYYMMDD（默认今天）")
    p.add_argument("--max-weeks", type=int, default=0, help="只拉前 N 周（小样本调试）")
    return p.parse_args()


if __name__ == "__main__":
    raise SystemExit(asyncio.run(main(_parse_args())))
