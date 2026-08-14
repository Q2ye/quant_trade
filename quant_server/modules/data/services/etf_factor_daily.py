# -*- coding: utf-8 -*-
"""
ETF 日终因子自动计算
====================
日终同步流水线的一部分：raw data sync → 本模块 → strategy run。

流程：
1. 从 etf_daily 表加载 ETF 池最近 250 天数据
2. 跑所有 etf_bottom 分类的注册因子计算器
3. 只取最新一天（today）的因子值
4. 批量 upsert 到 factor_data 表
"""
import logging
import uuid
from datetime import date, datetime, timedelta
from typing import List, Optional

import numpy as np
import pandas as pd

from shared.database.session.session_manager import get_session_manager

logger = logging.getLogger(__name__)

# ETF 池 — 策略用 .SH/.SZ 格式，etf_daily 表存 .OF 格式，需要转换
ETF_POOL_SH_SZ = [
    "510050.SH", "510300.SH", "510500.SH", "159919.SZ", "510880.SH",
    "512880.SH", "512660.SH", "512800.SH", "512100.SH",
    "159915.SZ", "159949.SZ", "518880.SH", "513100.SH", "513050.SH",
    "511010.SH", "511260.SH", "510310.SH", "159865.SZ", "159825.SZ",
    "159781.SZ", "512170.SH", "159806.SZ", "516510.SH",
    "159840.SZ", "512400.SH",
]

# 市场状态因子：从 market_state_daily 映射到每只 ETF
MARKET_STATE_FACTORS = [
    "market_regime", "trend_strength", "momentum_score",
    "breadth_ratio", "volatility_pct",
]


async def compute_etf_factors_daily(
    trade_date: Optional[date] = None,
    etf_pool: Optional[List[str]] = None,
    lookback_days: int = 250,
) -> dict:
    """日终计算 ETF 因子并写入 factor_data。

    应在 raw data sync 完成后、策略运行前调用。

    Returns:
        {"success": bool, "factors_computed": int, "rows_written": int, "message": str}
    """
    from modules.data.factor_calculators import FACTOR_CALCULATORS_MAP

    if trade_date is None:
        trade_date = date.today()
    # etf_daily 表存 .SH/.SZ 格式，直接用策略格式查询
    pool = etf_pool or ETF_POOL_SH_SZ
    factor_names = list(FACTOR_CALCULATORS_MAP.keys())

    sm = get_session_manager()
    async with sm.get_session() as session:
        # ── 1. 加载 ETF 日线数据（raw SQL，绕过 get_by_time_range 的 symbol 过滤 bug）───
        from shared.database.repositories.analysis.factor.factor_data_repo import (
            FactorDataRepository,
        )
        from sqlalchemy import text

        start = trade_date - timedelta(days=lookback_days)
        result = await session.execute(
            text(
                "SELECT ts_code, trade_date, open, high, low, close, pre_close, vol, amount "
                "FROM etf_daily "
                "WHERE ts_code = ANY(:codes) AND trade_date >= :start AND trade_date <= :end "
                "ORDER BY ts_code, trade_date"
            ),
            {
                "codes": pool,
                "start": start,
                "end": trade_date,
            },
        )
        all_rows = []
        for r in result.fetchall():
            all_rows.append({
                "ts_code": r[0],
                "trade_date": r[1],
                "open": float(r[2]) if r[2] else 0.0,
                "high": float(r[3]) if r[3] else 0.0,
                "low": float(r[4]) if r[4] else 0.0,
                "close": float(r[5]) if r[5] else 0.0,
                "pre_close": float(r[6]) if r[6] else 0.0,
                "vol": float(r[7]) if r[7] else 0.0,
                "amount": float(r[8]) if r[8] else 0.0,
            })

        if not all_rows:
            logger.warning("[ETF因子] 无 ETF 日线数据，跳过因子计算")
            return {"success": False, "factors_computed": 0, "rows_written": 0,
                    "message": "无 ETF 日线数据"}

        df = pd.DataFrame(all_rows)
        # 确保当前交易日有数据
        today_mask = pd.to_datetime(df["trade_date"]).dt.date == trade_date
        if not today_mask.any():
            logger.warning("[ETF因子] 今日 %s 无 ETF 数据，跳过", trade_date)
            return {"success": False, "factors_computed": 0, "rows_written": 0,
                    "message": f"{trade_date} 无 ETF 日线数据"}

        # ── 2. 计算所有技术因子 ──
        records = []
        factor_repo = FactorDataRepository(session)

        for factor_name in factor_names:
            calc_fn = FACTOR_CALCULATORS_MAP.get(factor_name)
            if calc_fn is None:
                continue
            try:
                result_series = calc_fn(df, parameters=None)
                if result_series is None or result_series.empty:
                    continue
                # 只取今日数据
                result_df = result_series.to_frame("value")
                result_df["ts_code"] = df["ts_code"].values
                result_df["trade_date"] = df["trade_date"].values
                result_df["factor_name"] = factor_name

                for _, row_data in result_df.iterrows():
                    td = row_data["trade_date"]
                    if hasattr(td, "date"):
                        td = td.date()
                    elif hasattr(td, "to_pydatetime"):
                        td = td.to_pydatetime().date()
                    if td != trade_date:
                        continue
                    val = row_data["value"]
                    if val is None or (isinstance(val, float) and np.isnan(val)):
                        continue
                    records.append({
                        "id": str(uuid.uuid4()),
                        "factor_code": factor_name,
                        "ts_code": row_data["ts_code"],
                        "trade_date": trade_date,
                        "factor_value": float(val),
                    })
            except Exception as e:
                logger.warning("[ETF因子] %s 计算失败: %s", factor_name, str(e)[:120])

        if records:
            await factor_repo.batch_insert_factor_data(records, conflict_strategy="upsert")

        # ── 3. 市场状态因子（从 market_state_daily 映射） ──
        # 使用策略格式 (.SH/.SZ) 写入
        market_records = await _backfill_market_factors(session, ETF_POOL_SH_SZ, trade_date)
        records.extend(market_records)
        if market_records:
            await factor_repo.batch_insert_factor_data(market_records, conflict_strategy="upsert")

        total = len(records)
        logger.info(
            "[ETF因子] 日终计算完成: %d 个因子 × %d 只 ETF → %d 行 (日期=%s)",
            len(factor_names), len(pool), total, trade_date,
        )
        return {
            "success": True,
            "factors_computed": len(factor_names),
            "rows_written": total,
            "message": f"{len(factor_names)} 因子, {total} 行",
        }


async def _backfill_market_factors(
    session, etf_pool: List[str], trade_date: date
) -> List[dict]:
    """从 market_state_daily 读取市场状态并写入 factor_data"""
    from sqlalchemy import text

    result = await session.execute(
        text("""
            SELECT regime, trend_strength, momentum_score,
                   breadth_ratio, volatility_pct
            FROM market_state_daily
            WHERE trade_date = :td
            LIMIT 1
        """),
        {"td": trade_date},
    )
    row = result.fetchone()
    if not row:
        return []

    records = []
    # market_state_daily.regime 是字符串（BULL/BEAR/NEUTRAL），需映射为策略编码
    # 0=熊市, 1=震荡, 2=牛市（与 bottom_strategy._get_regime / regime_threshold_adj 一致）
    _REGIME_TO_NUM = {"BEAR": 0, "NEUTRAL": 1, "BULL": 2}

    def _regime_to_num(v):
        if v is None:
            return 1.0
        try:
            return float(v)
        except (TypeError, ValueError):
            return float(_REGIME_TO_NUM.get(str(v).upper(), 1.0))

    factor_map = {
        "market_regime": _regime_to_num(row[0]),
        "trend_strength": float(row[1]) if row[1] is not None else None,
        "momentum_score": float(row[2]) if row[2] is not None else None,
        "breadth_ratio": float(row[3]) if row[3] is not None else None,
        "volatility_pct": float(row[4]) if row[4] is not None else None,
    }

    for ts_code in etf_pool:
        for fc, fv in factor_map.items():
            if fv is None:
                continue
            records.append({
                "id": str(uuid.uuid4()),
                "factor_code": fc,
                "ts_code": ts_code,
                "trade_date": trade_date,
                "factor_value": float(fv),
            })

    return records
