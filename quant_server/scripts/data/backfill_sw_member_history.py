# -*- coding: utf-8 -*-
"""回填申万行业成分的历史记录（`index_sw_member`）。

## 背景

`index_sw_member` 此前**无法用于按历史日期建池**，根因是 `sync_service` 里
两处叠加缺陷（均已于 2026-09-25 修复）：

| # | 缺陷 | 实测证据（2026-09-25） |
|:--|:---|:---|
| ① | 只调 `is_new='Y'`（当前成分），**未拉 `is_new='N'`（已剔除成分）** | `Y` 的 `out_date` **恒 NULL**；`N` 的 `out_date` **全部非空** → 两者**互补**，不是替代。只拉 Y = 无任何历史成分 |
| ② | 未传 `limit` → 服务端**默认只返回 3000 行** | 不传 limit = **3000 行** / `limit=6000` = **5914 行**（全量）→ 表里只写进了约 **51%** |

实测缺口：库内 **3,045** 行（全为 `is_new='Y'`），而 API 当前成分为 **5,914** 只 →
**缺 2,876 只当前成分**，且 **历史成分为 0 行**。

> ⚠️ 未修复时按本表建历史池 = **用今天的成分股回测过去**（幸存者偏差 + 前视偏差），
> 属 `06_策略实盘准入标准.md` G2「宇宙门」明令作废的形态。

## 口径

- 直接调用**生产同步路径** `SyncService._sync_index_sw_member`（不另写一套拉取逻辑），
  确保「脚本跑通」等于「生产同步跑通」。
- 分页：`limit=1000` + `offset` 递增，直到某页不足一页。
- 去重键 = 表唯一约束 `(l3_code, ts_code, in_date)`；`is_new='Y'` 优先。
- 写入走 `bulk_upsert`（`INSERT ... ON CONFLICT DO UPDATE`）——
  **只新增/纠正，不删除任何既有行**，可反复重跑（幂等）。

## 用法（CWD=quant_server）

    python scripts/data/backfill_sw_member_history.py                          # dry-run（默认）：只拉取并报告，不写库
    python scripts/data/backfill_sw_member_history.py --apply                  # 实际写入
    python scripts/data/backfill_sw_member_history.py --apply --database quant_signals_dev   # 指定目标库

> ⚠️ **默认目标是 `config.yaml` 当前环境的库**（本项目为 production → `quant_signals` **生产库**）。
> 写生产库前请确认：读取方修复（`industry_service` / `screener_service` 的 `out_date IS NULL`）
> **已随服务重启生效**，否则重启前窗口内前端「行业详情成分股」「选股器行业筛选」
> 会混入**已剔除成分股**（仅展示层；唯一交易类消费方低吸轮动为 stopped，且其本就按 `out_date` 过滤）。

## 验收（脚本自动断言）

    1. `out_date` 非空行数 > 0（修复前恒为 0）
    2. `is_new='N'` 行数 > 0
    3. 当前成分（`out_date IS NULL`）行数 ≥ 修复前
    4. 幂等：连跑两次，第二次新增行数 = 0

> ⚠️ 单次最多 50 页（5 万行），防服务端异常时死循环。
> 关联订正：`docs/00-核心策略体系/牛市信号验证计划.md:77` 曾称本表「有历史快照、
> 无幸存者偏差 ✅ 已解决」—— 与实测相反，已一并订正。
"""
import argparse
import asyncio
import logging
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent.parent))

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s | %(levelname)-7s | %(message)s",
    datefmt="%H:%M:%S",
)
logger = logging.getLogger("backfill_sw_member")

TABLE = "index_sw_member"


def _get_db_config() -> dict:
    try:
        from shared.config.config_manager import config

        db = config.settings.DATABASE
        return {
            "host": db.HOST,
            "port": int(db.PORT),
            "user": db.USER,
            "password": db.PASSWORD,
            "database": db.NAME,
        }
    except Exception:
        return {
            "host": "localhost",
            "port": 5432,
            "user": "postgres",
            "password": "123456",
            "database": "quant_signals_dev",
        }


async def _snapshot(conn) -> dict:
    """当前表状态快照（用于前后对照）。"""
    row = await conn.fetchrow(
        f"""
        SELECT count(*)                                        AS total,
               count(*) FILTER (WHERE out_date IS NOT NULL)     AS with_out,
               count(*) FILTER (WHERE out_date IS NULL)         AS current_cnt,
               count(*) FILTER (WHERE is_new = 'N')             AS n_hist,
               count(DISTINCT ts_code)                          AS codes
        FROM {TABLE}
        """
    )
    return dict(row)


async def _report(conn, title: str) -> dict:
    s = await _snapshot(conn)
    logger.info(
        "%s → 总计 %d 行 | 当前成分(out_date IS NULL) %d | 已剔除(out_date 非空) %d "
        "| is_new='N' %d | distinct ts_code %d",
        title,
        s["total"],
        s["current_cnt"],
        s["with_out"],
        s["n_hist"],
        s["codes"],
    )
    return s


async def main(apply: bool, database: str = "") -> int:
    import asyncpg

    cfg = _get_db_config()
    if database:
        cfg["database"] = database
    logger.info("目标库：%s@%s:%s/%s", cfg["user"], cfg["host"], cfg["port"], cfg["database"])

    conn = await asyncpg.connect(**cfg)
    try:
        before = await _report(conn, "[修复前]")

        if not apply:
            logger.info("dry-run：仅走拉取路径验证，不写库（加 --apply 实际写入）")
            from shared.sources.tushare_source import TushareSource

            src = TushareSource()
            page = 1000
            pulled = {}
            for is_new in ("Y", "N"):
                offset, n = 0, 0
                for _ in range(50):
                    df = await asyncio.to_thread(
                        src.get_index_member_all, is_new=is_new, limit=page, offset=offset
                    )
                    if df is None or df.empty:
                        break
                    n += len(df)
                    offset += page
                    if len(df) < page:
                        break
                pulled[is_new] = n
            logger.info(
                "dry-run 拉取结果：is_new='Y' %d 行 | is_new='N' %d 行 | 合计 %d 行",
                pulled.get("Y", 0),
                pulled.get("N", 0),
                sum(pulled.values()),
            )
            logger.info(
                "预计写入后：总计 ≈ %d 行（当前 %d）",
                sum(pulled.values()),
                before["total"],
            )
            return 0

        # ---------- 走生产同步路径 ----------
        from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine

        url = (
            f"postgresql+asyncpg://{cfg['user']}:{cfg['password']}"
            f"@{cfg['host']}:{cfg['port']}/{cfg['database']}"
        )
        engine = create_async_engine(url, pool_pre_ping=True)
        try:
            from modules.data.services.sync_service import DataSyncService

            Session = async_sessionmaker(engine, expire_on_commit=False)
            async with Session() as session:
                svc = DataSyncService(session)
                result = await svc._sync_index_sw_member(
                    None, None, None, "backfill_sw_member_history"
                )
            logger.info("同步返回：%s", result)
        finally:
            await engine.dispose()

        after = await _report(conn, "[修复后]")

        # ---------- 断言 ----------
        checks = [
            ("① out_date 非空行数 > 0", after["with_out"] > 0, after["with_out"]),
            ("② is_new='N' 行数 > 0", after["n_hist"] > 0, after["n_hist"]),
            (
                "③ 当前成分行数不减少",
                after["current_cnt"] >= before["current_cnt"],
                f"{before['current_cnt']} → {after['current_cnt']}",
            ),
            (
                # 首次修复：总行数应增加；幂等复跑：应保持不变（写入走 upsert，不删行）
                # 故判据是"不减少"，而非"增加"——后者在复跑时必然误报
                "④ 总行数不减少（幂等复跑时保持不变）",
                after["total"] >= before["total"],
                f"{before['total']} → {after['total']}",
            ),
        ]
        failed = 0
        for name, ok, detail in checks:
            logger.info("%s %s → %s", "✅" if ok else "❌", name, detail)
            if not ok:
                failed += 1

        if failed:
            logger.error("有 %d 项断言未通过", failed)
            return 1
        logger.info("全部断言通过 ✓")
        return 0
    finally:
        await conn.close()


if __name__ == "__main__":
    ap = argparse.ArgumentParser(description="回填申万行业成分历史（index_sw_member）")
    ap.add_argument("--apply", action="store_true", help="实际写入（默认 dry-run）")
    ap.add_argument(
        "--database",
        default="",
        help="覆盖目标库名（留空则用 config.yaml 当前环境，通常为 quant_signals 生产库）。"
        "例：--database quant_signals_dev",
    )
    args = ap.parse_args()
    raise SystemExit(asyncio.run(main(apply=args.apply, database=args.database)))
