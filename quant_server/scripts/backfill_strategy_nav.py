# -*- coding: utf-8 -*-
"""
策略真实净值回填脚本 — 虚拟子账户法重建历史序列
================================================================================
背景：
    strategy_daily_performance.total_return 此前用 allocated_capital（分配资金目标）
    当资产基准，收益/回撤反映的是「资金分配变动」而非策略自身盈亏。本脚本按成交流
    （trades JOIN orders 按 strategy_id）重放，逐日 mark-to-market 重建真实净值，
    并 upsert 回 strategy_daily_performance（total_assets / cash / peak_nav /
    daily_return / total_return / max_drawdown）。

原理（与 PerformanceService.calculate_daily_performance 的虚拟子账户口径一致）：
    对每个策略：
      1. 初始资金 = strategy_runs.allocated_capital（run 启动时分配额度，取最早 >0 的）
      2. 按 trade_time 升序重放成交：buy 扣现金加持仓，sell 加现金减持仓
      3. 在每个已有绩效记录日期（trade_date）上 mark-to-market：
         净值 = 现金 + Σ 持仓 volume × 当日收盘价（stock_daily + etf_daily）
      4. 反推 daily_return / total_return / max_drawdown，覆盖旧值

幂等：按 (strategy_id, trade_date) upsert，重复运行原地覆盖。

用法（quant_server/ 下）：
    .venv/Scripts/python.exe scripts/backfill_strategy_nav.py --dry-run
    .venv/Scripts/python.exe scripts/backfill_strategy_nav.py --strategy-id <id>
"""
import argparse
import asyncio
import logging
import sys
from datetime import date, datetime, time, timedelta
from decimal import Decimal
from pathlib import Path

_PROJECT_ROOT = Path(__file__).resolve().parent.parent
if str(_PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(_PROJECT_ROOT))

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
logger = logging.getLogger("backfill_strategy_nav")

from sqlalchemy import text
from sqlalchemy.ext.asyncio import create_async_engine, async_sessionmaker

from shared.database.models.business_models import StrategyDailyPerformance
from shared.database.repositories.account.asset.strategy_daily_performance_repo import (
    StrategyDailyPerformanceRepository,
)


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


def _db_url(env: dict) -> str:
    env_name = env.get("ENVIRONMENT", "development")
    prefix = "PROD_" if env_name == "production" else ""
    user = env.get(f"{prefix}DB_USER") or env.get("DB_USER", "postgres")
    password = env.get(f"{prefix}DB_PASSWORD") or env.get("DB_PASSWORD", "")
    host = env.get(f"{prefix}DB_HOST") or env.get("DB_HOST", "localhost")
    port = env.get(f"{prefix}DB_PORT") or env.get("DB_PORT", "5432")
    dbname = env.get(f"{prefix}DB_NAME") or env.get("DB_NAME", "quant_signals_dev")
    return f"postgresql+asyncpg://{user}:{password}@{host}:{port}/{dbname}"


def _as_date(v) -> date:
    if v is None:
        return None
    if isinstance(v, datetime):
        return v.date()
    if isinstance(v, date):
        return v
    return None


async def _get_strategy_ids(session, only_id: str) -> list:
    if only_id:
        return [only_id]
    rows = (await session.execute(
        text("SELECT DISTINCT strategy_id FROM strategy_daily_performance "
             "WHERE strategy_id IS NOT NULL ORDER BY strategy_id")
    )).fetchall()
    return [r[0] for r in rows]


async def _get_run_initial(session, strategy_id: str) -> Decimal:
    """run 初始分配资金：取最早一条 allocated_capital > 0 的 run。"""
    rows = (await session.execute(
        text("SELECT allocated_capital FROM strategy_runs "
             "WHERE strategy_id = :sid AND allocated_capital > 0 "
             "ORDER BY started_at ASC LIMIT 1"),
        {"sid": strategy_id},
    )).fetchall()
    if rows and rows[0][0] is not None:
        return Decimal(str(rows[0][0]))
    return Decimal("0")


async def _get_trades(session, strategy_id: str):
    """按时间升序取策略全部成交（含 order.direction）。"""
    rows = (await session.execute(
        text("""
            SELECT t.ts_code, t.price, t.volume, t.commission, t.tax, t.trade_time, o.direction
            FROM trades t JOIN orders o ON t.order_id = o.order_id
            WHERE o.strategy_id = :sid
            ORDER BY t.trade_time ASC, t.ts_code ASC
        """),
        {"sid": strategy_id},
    )).fetchall()
    return rows


async def _get_records(session, strategy_id: str):
    rows = (await session.execute(
        text("SELECT id, trade_date FROM strategy_daily_performance "
             "WHERE strategy_id = :sid ORDER BY trade_date ASC"),
        {"sid": strategy_id},
    )).fetchall()
    return rows


async def _get_close_map(session, symbols: list, start: date, end: date) -> dict:
    """{(ts_code, date_str): Decimal close}，stock_daily + etf_daily 合并。"""
    close_map = {}
    if not symbols:
        return close_map
    syms = tuple(symbols)
    for table in ("stock_daily", "etf_daily"):
        try:
            rows = (await session.execute(
                text(f"SELECT ts_code, trade_date, close FROM {table} "
                     "WHERE ts_code = ANY(:syms) AND trade_date BETWEEN :s AND :e"),
                {"syms": list(syms), "s": start, "e": end},
            )).fetchall()
            for r in rows:
                if r[2] is not None:
                    d = _as_date(r[1])
                    if d is not None:
                        close_map[(r[0], d.isoformat())] = Decimal(str(r[2]))
        except Exception as _e:
            logger.warning(f"{table} 收盘价查询失败: {_e}")
    return close_map


def _apply_trade(cash: Decimal, positions: dict, last_close: dict, t) -> Decimal:
    """按一笔成交更新现金与持仓，返回更新后的现金（Decimal 不可变，须返回）。"""
    ts_code, price, volume = t[0], Decimal(str(t[1])), int(t[2] or 0)
    commission = Decimal(str(t[3] or 0))
    tax = Decimal(str(t[4] or 0))
    direction = t[6]
    fees = commission + tax
    amount = price * volume
    if direction == "buy":
        cash -= (amount + fees)
        positions[ts_code] = positions.get(ts_code, 0) + volume
    elif direction == "sell":
        cash += (amount - fees)
        positions[ts_code] = positions.get(ts_code, 0) - volume
    # 更新该标的最近成交价，用于停牌日 mark-to-market 兜底
    last_close[ts_code] = price
    return cash


async def backfill_strategy(session, strategy_id: str, dry_run: bool) -> int:
    run_initial = await _get_run_initial(session, strategy_id)
    trades = await _get_trades(session, strategy_id)
    records = await _get_records(session, strategy_id)
    if not records:
        logger.info(f"策略 {strategy_id}: 无绩效记录，跳过")
        return 0
    if not trades:
        # 无成交：真实净值恒等于初始资金，总收益/回撤均应为 0（清掉旧 allocated_capital 漂移/幽灵值）
        repo = StrategyDailyPerformanceRepository(session)
        base = run_initial if run_initial > 0 else Decimal("0")
        written = 0
        for rec in records:
            d = _as_date(rec[1])
            if not dry_run:
                await repo.upsert_performance(strategy_id, d, {
                    "daily_return": 0.0,
                    "total_return": 0.0,
                    "max_drawdown": 0.0,
                    "total_assets": round(float(base), 2),
                    "cash": round(float(base), 2),
                    "peak_nav": round(float(base), 2),
                })
            written += 1
        logger.info(f"策略 {strategy_id}: 无成交，置平 {written} 条")
        return written

    # 日期集合 = 已有记录日 ∪ 成交日（补齐成交日缺失的记录，避免卖出已实现盈亏丢失）
    record_dates = [d for d in (_as_date(rec[1]) for rec in records) if d is not None]
    trade_dates = [d for d in (_as_date(t[5]) for t in trades) if d is not None]
    all_dates = sorted(set(record_dates) | set(trade_dates))
    start, end = all_dates[0], all_dates[-1]
    symbols = list({t[0] for t in trades})
    close_map = await _get_close_map(session, symbols, start, end)

    base = run_initial if run_initial > 0 else None
    cash = base if base is not None else Decimal("0")
    positions: dict = {}
    last_close: dict = {}
    trade_idx = 0
    prev_nav = None
    peak = cash
    max_dd = Decimal("0")
    written = 0

    repo = StrategyDailyPerformanceRepository(session)
    for d in all_dates:
        # 处理截至当日的成交
        while trade_idx < len(trades):
            t = trades[trade_idx]
            if _as_date(t[5]) > d:
                break
            cash = _apply_trade(cash, positions, last_close, t)
            trade_idx += 1

        # mark-to-market
        mv = Decimal("0")
        for ts_code, vol in positions.items():
            if vol <= 0:
                continue
            close = close_map.get((ts_code, d.isoformat())) or last_close.get(ts_code)
            if close is None:
                close = Decimal("0")
            mv += Decimal(vol) * close
        nav = cash + mv

        if base is None and nav > 0:
            base = nav
            cash = nav - mv  # 首日兜底：令 total_return 首日为 0
            nav = cash + mv

        if prev_nav is None:
            prev_nav = nav
            daily_return = Decimal("0")
        else:
            daily_return = (nav - prev_nav) / prev_nav if prev_nav > 0 else Decimal("0")
        total_return = (nav - base) / base if base and base > 0 else Decimal("0")

        peak = max(peak, nav)
        dd = (nav - peak) / peak if peak > 0 else Decimal("0")
        max_dd = min(max_dd, dd)

        if not dry_run:
            await repo.upsert_performance(strategy_id, d, {
                "daily_return": round(float(daily_return), 6),
                "total_return": round(float(total_return), 6),
                "max_drawdown": round(float(max_dd), 6),
                "total_assets": round(float(nav), 2),
                "cash": round(float(cash), 2),
                "peak_nav": round(float(peak), 2),
            })
        written += 1
        prev_nav = nav

    return written


async def main(strategy_id: str, dry_run: bool) -> None:
    env = _load_env()
    url = _db_url(env)
    engine = create_async_engine(url)
    Session = async_sessionmaker(engine, expire_on_commit=False)

    async with Session() as session:
        ids = await _get_strategy_ids(session, strategy_id)
        logger.info(f"待回填策略数: {len(ids)}（dry_run={dry_run}）")
        total = 0
        for sid in ids:
            try:
                n = await backfill_strategy(session, sid, dry_run)
                total += n
                logger.info(f"策略 {sid}: 重建 {n} 条绩效记录")
            except Exception as e:
                logger.error(f"策略 {sid} 回填失败: {e}")
        await session.commit()
        logger.info(f"回填完成：共 {total} 条" + ("（dry-run 未写库）" if dry_run else ""))

    await engine.dispose()


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="重建策略真实净值序列")
    parser.add_argument("--strategy-id", default="", help="只回填指定策略（默认全部）")
    parser.add_argument("--dry-run", action="store_true", help="只计算不写库")
    args = parser.parse_args()
    asyncio.run(main(args.strategy_id, args.dry_run))
