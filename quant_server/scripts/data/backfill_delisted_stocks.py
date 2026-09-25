# -*- coding: utf-8 -*-
"""回填退市股（基础信息 + 日线 + 复权因子 + 每日指标 + 资金流）。

## 背景

`stock_basic` / `stock_daily` 中退市股为 0 → **个股策略回测含幸存者偏差**。
根因：`sync_service` 调用 `get_stock_basic()` 未传 `list_status` → 默认 'L'
（已在 2026-09-19 修复：改为遍历 L/D/P，且源侧默认值改空=全部）。
本脚本负责**把历史缺口补上**。

实测缺口：**339 只**（D=339 / P=0），其中 **2022+ 退市 193 只（57%）**。
来源：`docs/02-功能设计/数据模块/数据源验证-退市股缺口-2026-09.md`

⚠️ **2026-09-19 扩表**：首轮只回填了 3 张表，实测遗漏：
`stock_daily_basic` 缺 **138 只 / 393,200 行**、`stock_moneyflow` 缺 **324 只 / 1,155,529 行**
→ 用 `total_mv`/`circ_mv` 的策略（微盘）与资金流类策略在退市股上仍拿 NULL，
**幸存者偏差并未真正消除**。故本脚本扩展为 5 张表。
来源：`docs/02-功能设计/数据模块/数据质量五门实测-2026-09-19.md` §1.3

## 口径

    基础信息 : Tushare `stock_basic(list_status='D')` → `stock_basic`
               ⚠️ 强制写 `list_status='D'`（Tushare fields 不含该列，DB 列默认 'L'）
    日线     : Tushare `daily(ts_code=...)`              → `stock_daily`
    复权因子 : Tushare `adj_factor(ts_code=...)`         → `stock_adj_factor`
    每日指标 : Tushare `daily_basic(ts_code=...)`        → `stock_daily_basic`
    资金流   : Tushare `moneyflow(ts_code=...)`          → `stock_moneyflow`

**幂等**：全部 `ON CONFLICT ... DO NOTHING` —— **不覆盖任何已有行**，可反复重跑。

## 用法（CWD=quant_server）

    python scripts/data/backfill_delisted_stocks.py              # dry-run（默认）：只统计不写库
    python scripts/data/backfill_delisted_stocks.py --apply      # 实际写入
    python scripts/data/backfill_delisted_stocks.py --apply --limit 20   # 只跑前 20 只

> ⚠️ **默认 dry-run**（与本目录其他 backfill 脚本的"默认写入"不同）——
> 本次写入 ~77 万行到 `stock_daily`（全系统行情基础表），故默认更保守。
"""
import argparse
import asyncio
import logging
import sys
import uuid
from datetime import date
from pathlib import Path
from typing import Any, Dict, List

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

try:
    sys.stdout.reconfigure(encoding="utf-8")  # type: ignore[union-attr]
    sys.stderr.reconfigure(encoding="utf-8")  # type: ignore[union-attr]
except Exception:
    pass

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
logger = logging.getLogger(__name__)

SLEEP = 0.35          # Tushare 限频间隔
D_START = "19900101"
D_END = "20261231"


def _get_db_config() -> dict:
    try:
        from shared.config.config_manager import config
        db = config.settings.DATABASE
        return {"host": db.HOST, "port": int(db.PORT), "user": db.USER,
                "password": db.PASSWORD, "database": db.NAME}
    except Exception:
        return {"host": "localhost", "port": 5432, "user": "postgres",
                "password": "123456", "database": "quant_signals_dev"}


def _to_date(v: Any) -> Any:
    """Tushare 日期（'YYYYMMDD' 或 datetime）→ date；无效返回 None。"""
    if v is None:
        return None
    s = str(v).strip()
    if not s or s.lower() in ("nan", "none"):
        return None
    s = s[:10].replace("-", "")
    if len(s) != 8 or not s.isdigit():
        return None
    try:
        return date(int(s[:4]), int(s[4:6]), int(s[6:8]))
    except ValueError:
        return None


def _market_from_code(ts_code: Any) -> Any:
    """从 ts_code 推断板块 —— 代码段是板块的权威来源。

    ⚠️ 实测：部分退市股（如 `T600018.SH 上港集箱(退)`）Tushare **不提供 `market`**，
       而 `stock_basic.market` 是 **NOT NULL**，直接插会报
       `NotNullViolationError: null value in column "market"`。

    ⚠️ 2026-09-19：**规则已上提到生产链路**（`modules/data/services/sync_service.py::
       _market_from_ts_code`）—— 同一缺口也曾让 `stock_list` 同步整批失败。
       此处改为**委托**，避免两份实现漂移。
    """
    from modules.data.services.sync_service import _market_from_ts_code
    return _market_from_ts_code(ts_code)


def _txt(v: Any) -> Any:
    """→ str；缺失/无效 → None。

    ⚠️ 实测：Tushare **退市股**的 `area`/`industry` 缺失，经 pandas sanitizer 后
       变成 **float 0.0**（既不是 None、也不是 NaN）——
       直接插入 VARCHAR 列会报 `DataError: expected str, got float`。
    """
    if v is None:
        return None
    if isinstance(v, float):          # 0.0 / NaN 均视为缺失
        return None
    s = str(v).strip()
    return s if s and s.lower() not in ("nan", "none") else None


def _dec(v: Any, nd: int = 3) -> Any:
    """→ Decimal（asyncpg 的 numeric 编码器不接受 float）；NaN/无效 → None。

    ⚠️ 实测：直接传 float 会报
       `DataError: invalid input for query argument $4 ... (expected str, got float)`
    """
    from decimal import Decimal, InvalidOperation
    if v is None:
        return None
    try:
        f = float(v)
    except (TypeError, ValueError):
        return None
    if f != f or f in (float("inf"), float("-inf")):     # NaN / Inf
        return None
    try:
        return Decimal(str(round(f, nd)))
    except InvalidOperation:
        return None


def _int(v: Any) -> Any:
    """→ int；NaN/无效 → None。"""
    if v is None:
        return None
    try:
        f = float(v)
    except (TypeError, ValueError):
        return None
    if f != f:
        return None
    return int(f)


async def main(apply: bool, limit: int = 0) -> int:
    import asyncpg
    from shared.sources.tushare_source import TushareSource

    src = TushareSource()
    conn = await asyncpg.connect(**_get_db_config())
    stats = {"basic": 0, "daily": 0, "adj": 0, "basic_daily": 0,
             "moneyflow": 0, "fail": 0, "stocks": 0}
    try:
        logger.info("拉取退市股列表 ...")
        dlist = await asyncio.to_thread(src.get_stock_basic, "", "D")
        if limit:
            dlist = dlist[:limit]
        logger.info("退市股 %d 只%s", len(dlist), "（已 --limit 截断）" if limit else "")
        if not dlist:
            logger.warning("未取到退市股，退出")
            return 1

        # ---------- [1] stock_basic ----------
        logger.info("[1/5] 写 stock_basic ...")
        basic_rows = []
        for r in dlist:
            ld = _to_date(r.get("list_date"))
            tc, sym, nm = _txt(r.get("ts_code")), _txt(r.get("symbol")), _txt(r.get("name"))
            # NOT NULL 兜底：ts_code/symbol/name/market/list_date 缺任一则跳过
            if not (tc and sym and nm and ld):
                stats["fail"] += 1
                logger.warning("  跳过 %s：NOT NULL 字段缺失（ts_code/symbol/name/list_date）", tc)
                continue
            mk = _txt(r.get("market")) or _market_from_code(tc)
            if _txt(r.get("market")) is None:
                stats["mkt_derived"] = stats.get("mkt_derived", 0) + 1
            basic_rows.append((
                tc, sym, nm,
                _txt(r.get("area")), _txt(r.get("industry")), mk,
                _txt(r.get("exchange")), ld, _to_date(r.get("delist_date")),
                _txt(r.get("is_hs")), "D",                # ⚠️ 强制 'D'
            ))
        if apply and basic_rows:
            await conn.executemany("""
                INSERT INTO stock_basic
                    (ts_code, symbol, name, area, industry, market, exchange,
                     list_date, delist_date, is_hs, list_status)
                VALUES ($1,$2,$3,$4,$5,$6,$7,$8,$9,$10,$11)
                ON CONFLICT (ts_code) DO UPDATE SET
                    list_status = EXCLUDED.list_status,
                    delist_date = COALESCE(EXCLUDED.delist_date, stock_basic.delist_date)
                -- ⚠️ 只覆盖「上市状态 + 退市日」，**不动 area/industry/name 等**
                --    原因：部分标的（如 000004.SZ 国华退）**早已在库但状态过期**
                --    （标 'L'、delist_date 为空），用 DO NOTHING 改不动它们。
                --    实测此类「状态过期」标的 = 14 只（= 前述
                --    「DB 有而 Tushare(L) 无」的那批）。
            """, basic_rows)
        stats["basic"] = len(basic_rows)
        logger.info("  stock_basic: %d 行%s", len(basic_rows), "" if apply else "（dry-run 未写）")

        # ---------- [2] stock_daily [+3] stock_adj_factor ----------
        logger.info("[2/5] 拉日线 + [3/5] 复权因子 + [4/5] 每日指标 + [5/5] 资金流（逐只）...")
        for idx, r in enumerate(dlist, 1):
            code = r.get("ts_code")
            try:
                df = await asyncio.to_thread(src.get_daily, code, "", D_START, D_END)
                await asyncio.sleep(SLEEP)
            except Exception as e:
                logger.warning("  %s 日线失败: %s: %s", code, type(e).__name__, e)
                stats["fail"] += 1
                continue
            if df is None or len(df) == 0:
                continue
            stats["stocks"] += 1

            d_rows = []
            for _, row in df.iterrows():
                td = _to_date(row.get("trade_date"))
                if td is None:
                    continue
                d_rows.append((
                    str(uuid.uuid4()), code, td,
                    _dec(row.get("open")), _dec(row.get("high")), _dec(row.get("low")),
                    _dec(row.get("close")), _dec(row.get("pre_close")),
                    _dec(row.get("change")), _dec(row.get("pct_chg"), 6),
                    _int(row.get("vol")), _dec(row.get("amount"), 4),
                ))
            if apply and d_rows:
                await conn.executemany("""
                    INSERT INTO stock_daily
                        (id, ts_code, trade_date, open, high, low, close, pre_close,
                         change, pct_chg, vol, amount)
                    VALUES ($1,$2,$3,$4,$5,$6,$7,$8,$9,$10,$11,$12)
                    ON CONFLICT (ts_code, trade_date) DO NOTHING
                """, d_rows)
            stats["daily"] += len(d_rows)

            try:
                adf = await asyncio.to_thread(
                    src.get_adj_factor, symbol=code, start_date=D_START, end_date=D_END)
                await asyncio.sleep(SLEEP)
            except Exception as e:
                logger.warning("  %s 复权因子失败: %s", code, type(e).__name__)
                adf = None
            a_rows = []
            if adf is not None and len(adf):
                for _, row in adf.iterrows():
                    td = _to_date(row.get("trade_date"))
                    af = row.get("adj_factor")
                    if td is None or af is None:
                        continue
                    a_rows.append((str(uuid.uuid4()), code, td, _dec(af, 10)))
            if apply and a_rows:
                await conn.executemany("""
                    INSERT INTO stock_adj_factor (id, ts_code, trade_date, adj_factor)
                    VALUES ($1,$2,$3,$4)
                    ON CONFLICT (ts_code, trade_date) DO NOTHING
                """, a_rows)
            stats["adj"] += len(a_rows)

            # ---------- [4] stock_daily_basic ----------
            # ⚠️ 2026-09-19 补：此前只回填 3 张表，实测退市股在
            #    `stock_daily_basic` 仍缺 **138 只 / 393,200 行**、
            #    `stock_moneyflow` 缺 **324 只 / 1,155,529 行**。
            #    → 用 `total_mv`/`circ_mv` 的策略（微盘）与资金流策略
            #      在退市股上仍拿 NULL，**幸存者偏差未真正消除**。
            try:
                bdf = await asyncio.to_thread(
                    src.get_daily_basic, code, "", D_START, D_END)
                await asyncio.sleep(SLEEP)
            except Exception as e:
                logger.warning("  %s 每日指标失败: %s", code, type(e).__name__)
                bdf = None
            b_rows = []
            if bdf is not None and len(bdf):
                for _, row in bdf.iterrows():
                    td = _to_date(row.get("trade_date"))
                    if td is None:
                        continue
                    b_rows.append((
                        str(uuid.uuid4()), code, td,
                        _dec(row.get("close")),
                        _dec(row.get("turnover_rate"), 6), _dec(row.get("turnover_rate_f"), 6),
                        _dec(row.get("volume_ratio"), 6),
                        _dec(row.get("pe"), 6), _dec(row.get("pe_ttm"), 6),
                        _dec(row.get("pb"), 6), _dec(row.get("ps"), 6), _dec(row.get("ps_ttm"), 6),
                        _dec(row.get("dv_ratio"), 6), _dec(row.get("dv_ttm"), 6),
                        _dec(row.get("total_share"), 6), _dec(row.get("float_share"), 6),
                        _dec(row.get("free_share"), 6),
                        _dec(row.get("total_mv"), 6), _dec(row.get("circ_mv"), 6),
                    ))
            if apply and b_rows:
                await conn.executemany("""
                    INSERT INTO stock_daily_basic
                        (id, ts_code, trade_date, close, turnover_rate, turnover_rate_f,
                         volume_ratio, pe, pe_ttm, pb, ps, ps_ttm, dv_ratio, dv_ttm,
                         total_share, float_share, free_share, total_mv, circ_mv)
                    VALUES ($1,$2,$3,$4,$5,$6,$7,$8,$9,$10,$11,$12,$13,$14,$15,$16,$17,$18,$19)
                    ON CONFLICT (ts_code, trade_date) DO NOTHING
                """, b_rows)
            stats["basic_daily"] += len(b_rows)

            # ---------- [5] stock_moneyflow ----------
            try:
                mdf = await asyncio.to_thread(
                    src.get_moneyflow, code, "", D_START, D_END)
                await asyncio.sleep(SLEEP)
            except Exception as e:
                logger.warning("  %s 资金流失败: %s", code, type(e).__name__)
                mdf = None
            m_rows = []
            if mdf is not None and len(mdf):
                for _, row in mdf.iterrows():
                    td = _to_date(row.get("trade_date"))
                    if td is None:
                        continue
                    m_rows.append((
                        str(uuid.uuid4()), code, td,
                        _int(row.get("buy_sm_vol")), _dec(row.get("buy_sm_amount"), 6),
                        _int(row.get("sell_sm_vol")), _dec(row.get("sell_sm_amount"), 6),
                        _int(row.get("buy_md_vol")), _dec(row.get("buy_md_amount"), 6),
                        _int(row.get("sell_md_vol")), _dec(row.get("sell_md_amount"), 6),
                        _int(row.get("buy_lg_vol")), _dec(row.get("buy_lg_amount"), 6),
                        _int(row.get("sell_lg_vol")), _dec(row.get("sell_lg_amount"), 6),
                        _int(row.get("buy_elg_vol")), _dec(row.get("buy_elg_amount"), 6),
                        _int(row.get("sell_elg_vol")), _dec(row.get("sell_elg_amount"), 6),
                        _int(row.get("net_mf_vol")), _dec(row.get("net_mf_amount"), 6),
                    ))
            if apply and m_rows:
                await conn.executemany("""
                    INSERT INTO stock_moneyflow
                        (id, ts_code, trade_date,
                         buy_sm_vol, buy_sm_amount, sell_sm_vol, sell_sm_amount,
                         buy_md_vol, buy_md_amount, sell_md_vol, sell_md_amount,
                         buy_lg_vol, buy_lg_amount, sell_lg_vol, sell_lg_amount,
                         buy_elg_vol, buy_elg_amount, sell_elg_vol, sell_elg_amount,
                         net_mf_vol, net_mf_amount)
                    VALUES ($1,$2,$3,$4,$5,$6,$7,$8,$9,$10,$11,$12,$13,$14,$15,$16,$17,$18,$19,$20,$21)
                    ON CONFLICT (ts_code, trade_date) DO NOTHING
                """, m_rows)
            stats["moneyflow"] += len(m_rows)

            if idx % 25 == 0 or idx == len(dlist):
                logger.info("  进度 %d/%d  日线 %d / 复权 %d / 每日指标 %d / 资金流 %d 行",
                            idx, len(dlist), stats["daily"], stats["adj"],
                            stats["basic_daily"], stats["moneyflow"])

        # ---------- 汇总 ----------
        logger.info("=" * 70)
        logger.info("完成%s", "" if apply else "（**dry-run：未写任何数据**，加 --apply 才写）")
        logger.info("  stock_basic         : %d 行", stats["basic"])
        logger.info("  stock_daily         : %d 行（%d 只标的）", stats["daily"], stats["stocks"])
        logger.info("  stock_adj_factor    : %d 行", stats["adj"])
        logger.info("  stock_daily_basic   : %d 行", stats["basic_daily"])
        logger.info("  stock_moneyflow     : %d 行", stats["moneyflow"])
        logger.info("  失败                : %d", stats["fail"])
        return 0
    finally:
        await conn.close()


def _parse_args() -> argparse.Namespace:
    p = argparse.ArgumentParser(description="回填退市股（基础信息 + 日线 + 复权因子）")
    p.add_argument("--apply", action="store_true", help="实际写入（默认 dry-run）")
    p.add_argument("--limit", type=int, default=0, help="只处理前 N 只（调试用）")
    return p.parse_args()


if __name__ == "__main__":
    args = _parse_args()
    raise SystemExit(asyncio.run(main(apply=args.apply, limit=args.limit)))
