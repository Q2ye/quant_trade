# -*- coding: utf-8 -*-
"""回填 market_state_daily.above_ma250_pct（全市场站上 MA250 比例，一次性）

用途：为「高波动动量轮动策略」的年线门 regime 判定提供市场宽度信号，
      替代现有 CSI500（000905.SH）收盘 vs MA250 的 regime 判定（CSI500 中盘指数
      看错策略实际持有的主板小盘高波动票，导致 2024-12~2025-08 杀跌段误判牛市满仓）。

口径（与既有 above_ma20_pct / above_ma60_pct 一脉相承，扩展窗口到 250 日）：
  - 每个交易日，统计「前复权收盘 > 前复权收盘的 250 日均值」的股票数 / 有完整
    250 日样本的股票总数 × 100（0~100）。
  - 价格取前复权：stock_daily（未复权 close）× stock_adj_factor（复权因子）。
    因「close > MA250」对单票逐日比较是尺度不变的（qfq = hfq / 最新因子，每票
    恒定缩放），直接用 hfq = close × adj_factor 即可，等价于前复权结果，无需再
    联最新复权因子做前复权归一。
  - 分母仅计入 n>=250 的股票（上市满 250 个交易日、且复权因子完整），与既有
    above_ma20/60 的 n>=60 分母口径一致。

用法（CWD=quant_server）:
    python -m scripts.backfill_breadth_ma250                # 全量回填
    python -m scripts.backfill_breadth_ma250 --dry-run      # 只算不写，打印分布
    python -m scripts.backfill_breadth_ma250 --since 2024-01-01

前置（一次性 DDL，需手工执行）:
    ALTER TABLE market_state_daily ADD COLUMN IF NOT EXISTS above_ma250_pct NUMERIC(6,3);

依赖: asyncpg（数据库直连，与 backfill_above_ma.py / backfill_emotion_metrics.py 同款）
"""
import argparse
import asyncio
import logging
from datetime import date, timedelta
from typing import Dict, Optional

import asyncpg

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
logger = logging.getLogger(__name__)

# 250 个交易日 ≈ 350 自然日，留 400 天缓冲，保证窗口起点有完整前序
_MA_WINDOW = 250
_SCAN_BUFFER_DAYS = 400

# 与 market_state_classifier.CLASSIFIED_BY 一致（当前库内唯一分类器版本）
_CLASSIFIED_BY = "v1.0_ma_regime"


def _get_db_config() -> dict:
    try:
        from shared.config.config_manager import config
        db = config.settings.DATABASE
        return {
            "host": db.HOST, "port": int(db.PORT),
            "user": db.USER, "password": db.PASSWORD,
            "database": db.NAME,
        }
    except Exception:
        return {
            "host": "localhost", "port": 5432, "user": "postgres",
            "password": "123456", "database": "quant_signals_dev",
        }


async def _ensure_column(conn: asyncpg.Connection) -> bool:
    """确认 above_ma250_pct 列存在；不存在则提示 DDL（不自动执行）。"""
    row = await conn.fetchval(
        "SELECT 1 FROM information_schema.columns "
        "WHERE table_name = 'market_state_daily' AND column_name = 'above_ma250_pct'"
    )
    if row:
        return True
    logger.warning(
        "market_state_daily 缺少 above_ma250_pct 列，请先执行 DDL：\n"
        "  ALTER TABLE market_state_daily ADD COLUMN IF NOT EXISTS above_ma250_pct NUMERIC(6,3);"
    )
    return False


async def _load_breadth_ma250(
    conn: asyncpg.Connection, scan_since: date, since: date
) -> Dict[date, float]:
    """计算各交易日「全市场站上 MA250 比例」（0~100，前复权口径）。

    scan_since: 窗口扫描起点（需早于 since 约 400 天，供 250 日均线取完整前序）
    since:      只返回该日期及之后的比例（外层 WHERE 过滤）
    """
    rows = await conn.fetch(
        """
        WITH px AS (
            SELECT sd.ts_code, sd.trade_date,
                   sd.close * af.adj_factor AS hfq_close
            FROM stock_daily sd
            JOIN stock_adj_factor af
              ON af.ts_code = sd.ts_code AND af.trade_date = sd.trade_date
            WHERE sd.trade_date >= $1
        ),
        w AS (
            SELECT ts_code, trade_date, hfq_close,
                   AVG(hfq_close) OVER (PARTITION BY ts_code ORDER BY trade_date
                       ROWS BETWEEN 249 PRECEDING AND CURRENT ROW) AS ma250,
                   COUNT(hfq_close) OVER (PARTITION BY ts_code ORDER BY trade_date
                       ROWS BETWEEN 249 PRECEDING AND CURRENT ROW) AS n
            FROM px
        )
        SELECT trade_date,
               COUNT(*) FILTER (WHERE n >= 250 AND hfq_close > ma250)::float
                   / NULLIF(COUNT(*) FILTER (WHERE n >= 250), 0) * 100 AS above_ma250_pct
        FROM w
        WHERE trade_date >= $2
        GROUP BY trade_date
        ORDER BY trade_date
        """,
        scan_since,
        since,
    )
    return {
        r["trade_date"]: float(r["above_ma250_pct"])
        for r in rows if r["above_ma250_pct"] is not None
    }


async def main(since: Optional[date] = None, dry_run: bool = False) -> int:
    conn = await asyncpg.connect(**_get_db_config())
    try:
        if not await _ensure_column(conn):
            return 1

        # 回填起点：market_state_daily 最早行（或 --since 指定）
        if since is None:
            since = await conn.fetchval(
                "SELECT MIN(trade_date) FROM market_state_daily "
                "WHERE classified_by = $1",
                _CLASSIFIED_BY,
            )
            if not since:
                logger.warning("market_state_daily 无数据，请先运行 classifier 生成行")
                return 1
        scan_since = since - timedelta(days=_SCAN_BUFFER_DAYS)

        logger.info("扫描窗口: %s → %s（MA%d）", scan_since, since, _MA_WINDOW)
        mapping = await _load_breadth_ma250(conn, scan_since, since)
        if not mapping:
            logger.warning("无符合条件的交易日（复权因子/日线覆盖不足）")
            return 1

        logger.info("计算得 %d 个交易日的 above_ma250_pct", len(mapping))
        if dry_run:
            _print_distribution(mapping)
            logger.info("dry-run：未写入数据库")
            return 0

        # 写入：按 trade_date 更新（breadth 为分类器无关的单一市场事实，不限定 classified_by）
        batch = [(d, round(v, 3)) for d, v in mapping.items()]
        await conn.executemany(
            """
            UPDATE market_state_daily
            SET above_ma250_pct = $2
            WHERE trade_date = $1
            """,
            batch,
        )
        total = await conn.fetchval(
            "SELECT COUNT(*) FROM market_state_daily WHERE above_ma250_pct IS NOT NULL"
        )
        logger.info("回填完成：更新 %d 天；above_ma250_pct 已填充共 %d 天", len(batch), total or 0)
        return 0
    finally:
        await conn.close()


def _print_distribution(mapping: Dict[date, float]) -> None:
    """打印分位与极值，供人工校验（dry-run）。"""
    vals = sorted(mapping.values())
    n = len(vals)
    def pct(p: float) -> float:
        if n == 0:
            return 0.0
        return vals[min(n - 1, int(n * p))]
    logger.info(
        "分布: min=%.2f p25=%.2f p50=%.2f p75=%.2f max=%.2f",
        vals[0], pct(0.25), pct(0.5), pct(0.75), vals[-1],
    )
    # 阈值命中率（对应策略 regime：<30 熊 / 30~60 震 / >60 牛）
    bear = sum(1 for v in vals if v < 30)
    bull = sum(1 for v in vals if v > 60)
    logger.info(
        "阈值命中: <30%%(熊) %d 天 = %.1f%% | >60%%(牛) %d 天 = %.1f%%",
        bear, bear / n * 100, bull, bull / n * 100,
    )


def _parse_args() -> argparse.Namespace:
    p = argparse.ArgumentParser(description="回填 market_state_daily.above_ma250_pct")
    p.add_argument("--since", type=str, default=None, help="回填起点日期 YYYY-MM-DD（默认取表内最早行）")
    p.add_argument("--dry-run", action="store_true", help="只计算并打印分布，不写库")
    return p.parse_args()


if __name__ == "__main__":
    args = _parse_args()
    since = date.fromisoformat(args.since) if args.since else None
    raise SystemExit(asyncio.run(main(since=since, dry_run=args.dry_run)))
