# -*- coding: utf-8 -*-
"""清理 `data_quality_checks` 中的「空转 0 分」历史记录。

## 背景

2026-09-19 之前，质检服务只认 3 个类别名（`stock_list` / `daily_quotes` / `factor_data`），
而同步侧传的是 **同步类型名**（`adj_factor` / `etf_daily` / ... 共 53 种）→ **50 种不匹配**
→ `metrics` 全 0 → 每次同步后都写一条 **`total_records = 0` 的"检查了但什么也没查"** 记录。
（根因与修复见 `docs/02-功能设计/数据模块/数据质量检测-修复记录-2026-09.md`）

这些记录**不携带任何信息**（指标全错），且会：
  - 在前端/分析中被误读为「质量很差」
  - 掩盖真实的质量趋势

## 判据

删除满足**全部**条件的行：
  1. `total_records = 0`
  2. `created_at < --before`（默认 `2026-09-19T17:00:00`，即修复落盘前）

> ⚠️ 修复上线后，`total_records = 0` 只会在**表确实为空**时产生 —— 那种记录**不应删**，
> 故用 `--before` 时间界把两者分开。**幂等**：重复执行删除数为 0。
>
> ⚠️ **默认 `--before` 取 `2026-09-19T17:00:00`** —— 因为**修复后的代码从未在运行中的服务里跑过**
> （服务重启发生在本修复落盘之前），所以**表内现有的全部 0 分记录都是旧代码产物**。
> 若日后再次执行，请显式传 `--before` 指明"修复上线时点"。

## 用法（CWD=quant_server）

    python scripts/data/cleanup_stale_quality_checks.py                    # dry-run（默认）
    python scripts/data/cleanup_stale_quality_checks.py --apply            # 实际删除
    python scripts/data/cleanup_stale_quality_checks.py --before 2026-10-01T00:00:00 --apply
"""
import argparse
import asyncio
import logging
import sys
from datetime import datetime
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

try:
    sys.stdout.reconfigure(encoding="utf-8")  # type: ignore[union-attr]
    sys.stderr.reconfigure(encoding="utf-8")  # type: ignore[union-attr]
except Exception:
    pass

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
logger = logging.getLogger(__name__)

DEFAULT_BEFORE = "2026-09-19T17:00:00"


def _get_db_config() -> dict:
    try:
        from shared.config.config_manager import config
        db = config.settings.DATABASE
        return {"host": db.HOST, "port": int(db.PORT), "user": db.USER,
                "password": db.PASSWORD, "database": db.NAME}
    except Exception:
        return {"host": "localhost", "port": 5432, "user": "postgres",
                "password": "123456", "database": "quant_signals_dev"}


async def main(apply: bool, before: str) -> int:
    import asyncpg

    try:
        before_ts = datetime.fromisoformat(before)
    except ValueError:
        logger.error("--before 格式无效（应形如 2026-09-19T00:00:00）: %s", before)
        return 2

    conn = await asyncpg.connect(**_get_db_config())
    try:
        total = await conn.fetchval("SELECT COUNT(*) FROM data_quality_checks")
        logger.info("清理前 data_quality_checks 总行数 = %s", f"{total:,}")

        rows = await conn.fetch("""
            SELECT data_type, COUNT(*) n, MAX(created_at) mx
            FROM data_quality_checks
            WHERE total_records = 0 AND created_at < $1
            GROUP BY data_type ORDER BY n DESC, data_type
        """, before_ts)
        victims = sum(int(r["n"]) for r in rows)
        logger.info("命中「0 分空转」记录: %d 行 / %d 种 data_type（created_at < %s）",
                    victims, len(rows), before_ts)

        # 保留侧的说明：0 分但时间在界之后的（表确实为空）不删
        keep = await conn.fetchval("""
            SELECT COUNT(*) FROM data_quality_checks
            WHERE total_records = 0 AND created_at >= $1
        """, before_ts)
        if keep:
            logger.info("（保留 %d 行为「界之后」的 0 分记录 —— 属表确实为空，不应删）", keep)

        if not rows:
            logger.info("无命中，无需清理（幂等）")
            return 0

        for r in rows[:20]:
            logger.info("   %-26s %5d 行   最新 %s", r["data_type"], int(r["n"]), r["mx"])
        if len(rows) > 20:
            logger.info("   ... 另有 %d 种类型", len(rows) - 20)

        if not apply:
            logger.info("=" * 68)
            logger.info("**dry-run：未删除任何行**，加 --apply 才执行删除")
            return 0

        async with conn.transaction():
            status = await conn.execute("""
                DELETE FROM data_quality_checks
                WHERE total_records = 0 AND created_at < $1
            """, before_ts)
        logger.info("删除结果: %s", status)

        after = await conn.fetchval("SELECT COUNT(*) FROM data_quality_checks")
        logger.info("清理后总行数 = %s（清理前 %s，删除 %s）",
                    f"{after:,}", f"{total:,}", f"{int(total) - int(after):,}")
        return 0
    finally:
        await conn.close()


def _parse_args() -> argparse.Namespace:
    p = argparse.ArgumentParser(description="清理 data_quality_checks 的空转 0 分历史记录")
    p.add_argument("--apply", action="store_true", help="实际删除（默认 dry-run）")
    p.add_argument("--before", default=DEFAULT_BEFORE,
                   help=f"时间界（ISO 格式），早于此的 0 分记录才删。默认 {DEFAULT_BEFORE}")
    return p.parse_args()


if __name__ == "__main__":
    args = _parse_args()
    raise SystemExit(asyncio.run(main(apply=args.apply, before=args.before)))
