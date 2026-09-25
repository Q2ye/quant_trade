# -*- coding: utf-8 -*-
"""把活库 NUMERIC 列精度**对齐到 `docs/sql/create_table.sql`**（消除窄列溢出）。

## 背景

2026-09-19 实测：全库 **25 个 NUMERIC 列**的**活库精度窄于 DDL**，例如

    stock_daily_basic.volume_ratio   活库 NUMERIC(8,4)  vs  DDL NUMERIC(18,6)
    stock_moneyflow.buy_elg_amount   活库 NUMERIC(12,4) vs  DDL NUMERIC(18,6)

后果：**合法值也会溢出**、且**整批插入失败**。实测触发：

    Tushare `daily_basic` 对 000918.SZ 2009-04-30 返回 volume_ratio = 12,148.94
    （停牌复牌后量比）→ 超出 NUMERIC(8,4) 上限 9999.9999
    → asyncpg.exceptions.NumericValueOutOfRangeError
    → **该批 1000+ 行全部回滚**

根因：活库建表用的是**旧版 DDL**；`create_table.sql` 后来把这类比例列统一放宽到
`NUMERIC(18,6)`，而**本项目无迁移框架**（`CLAUDE.md`：DDL「直接执行」）→ 活库从未被 ALTER。
`CLAUDE.md` 明载「**表结构以 `docs/sql/create_table.sql` 为准**」，故**活库为错的一方**。

## 安全性

`NUMERIC(p,s)` → 更宽的 `NUMERIC(p',s')`（`p'-s' >= p-s`）**只放宽取值范围，不丢数据**。
本脚本**只做加宽**，**绝不收窄**（收窄会丢数据/报错）。

## 用法（CWD=quant_server）

    python scripts/data/sync_numeric_precision_to_ddl.py                 # dry-run（默认）
    python scripts/data/sync_numeric_precision_to_ddl.py --apply
    python scripts/data/sync_numeric_precision_to_ddl.py --apply --table stock_daily_basic
"""
import argparse
import asyncio
import logging
import re
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

try:
    sys.stdout.reconfigure(encoding="utf-8")  # type: ignore[union-attr]
    sys.stderr.reconfigure(encoding="utf-8")  # type: ignore[union-attr]
except Exception:
    pass

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
logger = logging.getLogger(__name__)

DDL_PATH = Path(__file__).resolve().parents[3] / "docs" / "sql" / "create_table.sql"


def _get_db_config() -> dict:
    try:
        from shared.config.config_manager import config
        db = config.settings.DATABASE
        return {"host": db.HOST, "port": int(db.PORT), "user": db.USER,
                "password": db.PASSWORD, "database": db.NAME}
    except Exception:
        return {"host": "localhost", "port": 5432, "user": "postgres",
                "password": "123456", "database": "quant_signals_dev"}


def parse_ddl_numeric(sql: str) -> dict:
    """→ {(table, column): (precision, scale)}"""
    out = {}
    for m in re.finditer(
        r"CREATE\s+TABLE\s+(?:IF\s+NOT\s+EXISTS\s+)?[\"']?(\w+)[\"']?\s*\((.*?)\n\s*\)\s*;",
        sql, re.S | re.I,
    ):
        tbl = m.group(1).lower()
        for line in m.group(2).split("\n"):
            mm = re.match(r"\s*[\"']?(\w+)[\"']?\s+NUMERIC\s*\(\s*(\d+)\s*,\s*(\d+)\s*\)",
                          line, re.I)
            if mm:
                out[(tbl, mm.group(1).lower())] = (int(mm.group(2)), int(mm.group(3)))
    return out


async def collect_drift(conn, only_table: str = "") -> list:
    """→ [(table, column, (p,s)_live, (p,s)_ddl)]，只收**活库更窄**的列。"""
    ddl = parse_ddl_numeric(DDL_PATH.read_text(encoding="utf-8"))
    rows = await conn.fetch("""
        SELECT c.table_name, c.column_name,
               c.numeric_precision p, c.numeric_scale s
        FROM information_schema.columns c
        JOIN information_schema.tables t
          ON t.table_schema = c.table_schema AND t.table_name = c.table_name
        WHERE c.table_schema = 'public' AND t.table_type = 'BASE TABLE'
          AND c.data_type = 'numeric' AND c.numeric_precision IS NOT NULL
    """)
    out = []
    for r in rows:
        if only_table and r["table_name"].lower() != only_table.lower():
            continue
        d = ddl.get((r["table_name"].lower(), r["column_name"].lower()))
        if not d:
            continue
        lv = (int(r["p"]), int(r["s"]))
        # 只加宽：整数位数（p-s）更窄才处理；相等则比 scale
        if (lv[0] - lv[1]) < (d[0] - d[1]):
            out.append((r["table_name"], r["column_name"], lv, d))
    return out


async def _compressed_chunk_count(conn, table: str) -> int:
    try:
        return int(await conn.fetchval(
            "SELECT COUNT(*) FROM timescaledb_information.chunks "
            "WHERE hypertable_name=$1 AND is_compressed=true", table) or 0)
    except Exception:
        return 0


async def _decompress_all(conn, table: str) -> int:
    """解压该表全部已压缩 chunk，返回解压数量。"""
    r = await conn.fetch(
        "SELECT decompress_chunk(c, true) AS x FROM show_chunks($1) c", table)
    return len(r)


async def _recompress_all(conn, table: str) -> int:
    """重新压缩该表未压缩 chunk，返回处理数量。"""
    r = await conn.fetch(
        "SELECT compress_chunk(c, true) AS x FROM show_chunks($1) c", table)
    return len(r)


async def main(apply: bool, only_table: str,
               lock_timeout_ms: int = 10000, retry: int = 3,
               allow_decompress: bool = False) -> int:
    import asyncpg

    conn = await asyncpg.connect(**_get_db_config())
    try:
        drift = await collect_drift(conn, only_table)
        if not drift:
            logger.info("无「活库更窄」的 NUMERIC 列，无需处理（幂等）")
            return 0

        byt = {}
        for t, c, lv, d in drift:
            byt.setdefault(t, []).append((c, lv, d))
        logger.info("发现 %d 列窄于 DDL，涉及 %d 张表：", len(drift), len(byt))
        for t in sorted(byt):
            logger.info("  [%s] %d 列", t, len(byt[t]))
            for c, lv, d in byt[t]:
                logger.info("      %-24s Numeric(%d,%d) → Numeric(%d,%d)",
                            c, lv[0], lv[1], d[0], d[1])

        if not apply:
            logger.info("=" * 70)
            logger.info("**dry-run：未执行任何 ALTER**，加 --apply 才改")
            return 0

        # 2026-09-19：加 `lock_timeout` —— `ALTER ... ALTER COLUMN TYPE` 取
        # ACCESS EXCLUSIVE 锁；运行中的服务若持有 `idle in transaction`，
        # 会**无限期阻塞**（首次尝试即被卡 11 分钟）。改为**超时快速失败 + 重试**。
        try:
            await conn.execute(f"SET lock_timeout = '{lock_timeout_ms}ms'")
            logger.info("lock_timeout = %d ms（超时即重试，不无限等待）", lock_timeout_ms)
        except Exception as e:
            logger.warning("设置 lock_timeout 失败（继续）: %s", e)

        thr = max(1, retry)
        # 按表分组：同一张表只解压/重压一次
        bytbl = {}
        for t, c, lv, d in drift:
            bytbl.setdefault(t, []).append((c, lv, d))

        ok = fail = skip = 0
        idx = 0
        for t in sorted(bytbl):
            cols = bytbl[t]
            need = await _compressed_chunk_count(conn, t)
            decompressed = False
            if need:
                if not allow_decompress:
                    logger.error("  [%s] ❌ 有 %d 个已压缩 chunk → 跳过（需 --allow-decompress）",
                                 t, need)
                    skip += len(cols)
                    idx += len(cols)
                    continue
                logger.info("  [%s] 检测到 %d 个已压缩 chunk → 先解压…", t, need)
                n_dec = await _decompress_all(conn, t)
                decompressed = True
                logger.info("  [%s] 已解压 %d 个 chunk，开始 ALTER", t, n_dec)

            for c, lv, d in cols:
                idx += 1
                sql = f'ALTER TABLE "{t}" ALTER COLUMN "{c}" TYPE NUMERIC({d[0]},{d[1]})'
                done = False
                for attempt in range(1, thr + 1):
                    try:
                        await conn.execute(sql)
                        logger.info("[%d/%d] ✅ %s.%s → Numeric(%d,%d)",
                                    idx, len(drift), t, c, d[0], d[1])
                        ok += 1
                        done = True
                        break
                    except Exception as e:
                        name = type(e).__name__
                        if "LockNotAvailable" in name or "lock timeout" in str(e).lower():
                            logger.warning("[%d/%d] ⏳ %s.%s 等锁超时（%d/%d），重试…",
                                           idx, len(drift), t, c, attempt, thr)
                            await asyncio.sleep(2)
                            continue
                        logger.error("[%d/%d] ❌ %s.%s 失败: %s: %s",
                                     idx, len(drift), t, c, name, str(e)[:160])
                        break
                if not done:
                    fail += 1

            if decompressed:
                logger.info("  [%s] 重新压缩…", t)
                n_rec = await _recompress_all(conn, t)
                logger.info("  [%s] 已重压 %d 个 chunk", t, n_rec)

        logger.info("=" * 70)
        logger.info("完成：成功 %d / 失败 %d / 跳过（压缩阻碍）%d", ok, fail, skip)

        # 复验
        left = await collect_drift(conn, only_table)
        logger.info("复验：仍窄于 DDL 的列 = %d  %s", len(left),
                    "✅ 已对齐" if not left else "⚠️ 仍有残留")
        return 0 if fail == 0 else 1
    finally:
        await conn.close()


def _parse_args() -> argparse.Namespace:
    p = argparse.ArgumentParser(description="对齐活库 NUMERIC 精度到 create_table.sql")
    p.add_argument("--apply", action="store_true", help="实际执行 ALTER（默认 dry-run）")
    p.add_argument("--table", default="", help="只处理指定表")
    p.add_argument("--lock-timeout", type=int, default=10000,
                   help="单条 ALTER 的锁等待上限（毫秒），超时重试。默认 10000")
    p.add_argument("--retry", type=int, default=3, help="单列重试次数。默认 3")
    p.add_argument("--allow-decompress", action="store_true",
                   help="对压缩 hypertable 执行「解压 → ALTER → 重压」（重操作，需停机）")
    return p.parse_args()


if __name__ == "__main__":
    args = _parse_args()
    raise SystemExit(asyncio.run(main(
        apply=args.apply, only_table=args.table,
        lock_timeout_ms=args.lock_timeout, retry=args.retry,
        allow_decompress=args.allow_decompress)))
