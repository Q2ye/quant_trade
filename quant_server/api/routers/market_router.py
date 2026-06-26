# -*- coding: utf-8 -*-
"""Market 模块 API 路由 — Phase 1/2/3"""
from typing import Optional, Dict, List
from fastapi import APIRouter, Depends, HTTPException, Query, Body
from sqlalchemy.ext.asyncio import AsyncSession

from api.dependencies.database import get_db_session
from api.dependencies.auth import get_current_user
from modules.market.handlers import (
    get_dashboard, get_stock_detail_full,
    do_screener, do_industry_tree, do_industry_detail, do_industry_heatmap,
    do_industry_history, do_industry_heatmap_multi, do_industry_trend,
    do_financial_compare, do_financial_statements, do_financial_events,
    do_top_moneyflow, do_hsgt_history, do_stock_moneyflow_detail,
    do_macro, do_index_weights, do_index_valuation, do_etf_shares, do_etf_benchmark,
    do_index_history, do_index_sector_exposure, do_sector_moneyflow,
    do_stock_signals, do_stock_factor_scores, do_limit_analysis,
    do_style_factors, do_sector_turnover,
    do_get_watchlist, do_save_watchlist,
    do_stock_kline_range,
)

logger = __import__("logging").getLogger(__name__)
router = APIRouter(tags=["市场数据"])


# ---- Phase 1 ----
@router.get("/dashboard/overview")
async def dashboard_overview(current_user=Depends(get_current_user), db_session=Depends(get_db_session)):
    try:
        r = await get_dashboard(db_session)
        return {"success": True, "data": r.model_dump()}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@router.get("/stocks/{ts_code}/full")
async def stock_full(ts_code: str, current_user=Depends(get_current_user), db_session=Depends(get_db_session)):
    try:
        r = await get_stock_detail_full(db_session, ts_code.upper())
        if r is None:
            return {"success": True, "data": None, "message": "Not found"}
        return {"success": True, "data": r.model_dump()}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/stocks/{ts_code}/kline")
async def stock_kline_range(
    ts_code: str,
    period: str = Query("daily", pattern="^(daily|weekly|monthly|moneyflow)$"),
    before_date: Optional[str] = Query(None, description="返回该日期之前的数据，不传则取最新"),
    limit: int = Query(500, ge=1, le=2000),
    current_user=Depends(get_current_user),
    db_session=Depends(get_db_session),
):
    """个股 K 线按范围查询 — 用于图表动态加载更早的历史数据"""
    try:
        rows = await do_stock_kline_range(
            db_session, ts_code.upper(), period, before_date, limit,
        )
        return {"success": True, "data": rows}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


# ---- Phase 2 ----
@router.post("/screener")
async def screener_api(body: Dict = Body(...), current_user=Depends(get_current_user), db_session=Depends(get_db_session)):
    try:
        r = await do_screener(db_session, body)
        return {"success": True, "data": r}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@router.get("/industries")
async def industry_tree_api(current_user=Depends(get_current_user), db_session=Depends(get_db_session)):
    try:
        r = await do_industry_tree(db_session)
        return {"success": True, "data": r}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@router.get("/industries/{industry_code}/history")
async def industry_history_api(industry_code: str, limit: int = Query(90), current_user=Depends(get_current_user), db_session=Depends(get_db_session)):
    try:
        r = await do_industry_history(db_session, industry_code, limit)
        return {"success": True, "data": r}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/industries/heatmap")
async def industry_heatmap_api(
    windows: str = Query(default=None, description="时间窗口，逗号分隔，如 1d,5d,10d,20d,30d,60d"),
    current_user=Depends(get_current_user),
    db_session=Depends(get_db_session),
):
    try:
        if windows:
            win_list = [int(w.replace("d", "")) for w in windows.split(",") if w.strip()]
            r = await do_industry_heatmap_multi(db_session, win_list)
        else:
            r = await do_industry_heatmap(db_session)
        return {"success": True, "data": r}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@router.get("/industries/trend")
async def industry_trend_api(
    days: int = Query(default=60, ge=10, le=500, description="回溯天数"),
    current_user=Depends(get_current_user),
    db_session=Depends(get_db_session),
):
    """28 个申万 L1 行业日度趋势数据（用于多线折线图）"""
    try:
        r = await do_industry_trend(db_session, days)
        return {"success": True, "data": r}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/industries/{industry_code}")
async def industry_detail_api(industry_code: str, current_user=Depends(get_current_user), db_session=Depends(get_db_session)):
    try:
        r = await do_industry_detail(db_session, industry_code)
        if not r: raise HTTPException(status_code=404, detail="Not found")
        return {"success": True, "data": r}
    except HTTPException: raise
    except Exception as e: raise HTTPException(status_code=500, detail=str(e))


# ---- Phase 3: Financial ----
@router.post("/financial/indicators")
async def financial_compare_api(body: Dict = Body(...), current_user=Depends(get_current_user), db_session=Depends(get_db_session)):
    try:
        codes = body.get("codes", [])
        r = await do_financial_compare(db_session, codes, body.get("metrics"), body.get("end_date"))
        return {"success": True, "data": r}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@router.get("/stocks/{ts_code}/financial/statements")
async def financial_statements_api(ts_code: str, type: str = Query("income"), limit: int = Query(20), current_user=Depends(get_current_user), db_session=Depends(get_db_session)):
    try:
        r = await do_financial_statements(db_session, ts_code.upper(), type, limit)
        return {"success": True, "data": r}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@router.get("/stocks/{ts_code}/financial/events")
async def financial_events_api(ts_code: str, type: str = Query("forecast"), limit: int = Query(10), current_user=Depends(get_current_user), db_session=Depends(get_db_session)):
    try:
        r = await do_financial_events(db_session, ts_code.upper(), type, limit)
        return {"success": True, "data": r}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


# ---- Phase 3: MoneyFlow ----
@router.get("/moneyflow/top")
async def top_moneyflow_api(direction: str = Query("net_inflow"), limit: int = Query(20), current_user=Depends(get_current_user), db_session=Depends(get_db_session)):
    try:
        r = await do_top_moneyflow(db_session, direction, limit)
        return {"success": True, "data": r}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@router.get("/moneyflow/hsgt")
async def hsgt_history_api(days: int = Query(60), current_user=Depends(get_current_user), db_session=Depends(get_db_session)):
    try:
        r = await do_hsgt_history(db_session, days)
        return {"success": True, "data": r}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@router.get("/stocks/{ts_code}/moneyflow")
async def stock_moneyflow_api(ts_code: str, days: int = Query(60), current_user=Depends(get_current_user), db_session=Depends(get_db_session)):
    try:
        r = await do_stock_moneyflow_detail(db_session, ts_code.upper(), days)
        return {"success": True, "data": r}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

# ---- Phase 4: Macro + Index/ETF ----
@router.get("/macro/{indicator}")
async def macro_api(indicator: str, limit: int = Query(24), current_user=Depends(get_current_user), db_session=Depends(get_db_session)):
    try:
        r = await do_macro(db_session, indicator, limit)
        return {"success": True, "data": r}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@router.get("/indexes/{code}/weights")
async def index_weights_api(code: str, offset: int = Query(0, ge=0), limit: int = Query(50, ge=1, le=200),
                              current_user=Depends(get_current_user), db_session=Depends(get_db_session)):
    try:
        r = await do_index_weights(db_session, code, offset, limit)
        return {"success": True, "data": r}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@router.get("/indexes/{code}/valuation")
async def index_valuation_api(code: str, limit: int = Query(60), current_user=Depends(get_current_user), db_session=Depends(get_db_session)):
    try:
        r = await do_index_valuation(db_session, code, limit)
        return {"success": True, "data": r}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@router.get("/etfs/{code}/shares")
async def etf_shares_api(code: str, limit: int = Query(120), current_user=Depends(get_current_user), db_session=Depends(get_db_session)):
    try:
        r = await do_etf_shares(db_session, code, limit)
        return {"success": True, "data": r}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@router.get("/etfs/{code}/benchmark")
async def etf_benchmark_api(code: str, current_user=Depends(get_current_user), db_session=Depends(get_db_session)):
    try:
        r = await do_etf_benchmark(db_session, code)
        return {"success": True, "data": r}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
@router.get("/indexes/{code}/history")
async def index_history_api(code: str, limit: int = Query(60), current_user=Depends(get_current_user), db_session=Depends(get_db_session)):
    try:
        result = await do_index_history(db_session, code, limit)
        return {"success": True, "data": result}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/indexes/{code}/sector-exposure")
async def index_sector_exposure_api(code: str, current_user=Depends(get_current_user), db_session=Depends(get_db_session)):
    try:
        r = await do_index_sector_exposure(db_session, code)
        return {"success": True, "data": r}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/moneyflow/sector")
async def sector_moneyflow_api(current_user=Depends(get_current_user), db_session=Depends(get_db_session)):
    try:
        r = await do_sector_moneyflow(db_session)
        return {"success": True, "data": r}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


# ---- Phase 6: Signals + Factor Scores ----
@router.get("/stocks/{ts_code}/signals")
async def stock_signals_api(
    ts_code: str,
    recent: int = Query(20, ge=1, le=100),
    current_user=Depends(get_current_user),
    db_session=Depends(get_db_session),
):
    try:
        r = await do_stock_signals(db_session, ts_code.upper(), recent)
        return {"success": True, "data": r}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/stocks/{ts_code}/factor-scores")
async def stock_factor_scores_api(
    ts_code: str,
    current_user=Depends(get_current_user),
    db_session=Depends(get_db_session),
):
    try:
        r = await do_stock_factor_scores(db_session, ts_code.upper())
        return {"success": True, "data": r}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/limit-analysis")
async def limit_analysis_api(
    trade_date: Optional[str] = Query(None),
    exchange: Optional[str] = Query(None),
    board: Optional[str] = Query(None),
    current_user=Depends(get_current_user),
    db_session=Depends(get_db_session),
):
    try:
        r = await do_limit_analysis(db_session, trade_date, exchange, board)
        return {"success": True, "data": r}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/dashboard/style-factors")
async def style_factors_api(current_user=Depends(get_current_user), db_session=Depends(get_db_session)):
    try:
        r = await do_style_factors(db_session)
        return {"success": True, "data": r}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/dashboard/sector-turnover")
async def sector_turnover_api(current_user=Depends(get_current_user), db_session=Depends(get_db_session)):
    try:
        r = await do_sector_turnover(db_session)
        return {"success": True, "data": r}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/user/watchlist")
async def get_watchlist_api(current_user=Depends(get_current_user), db_session=Depends(get_db_session)):
    try:
        r = await do_get_watchlist(db_session, current_user.get("user_id", ""))
        return {"success": True, "data": r}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.put("/user/watchlist")
async def save_watchlist_api(
    body: Dict = Body(...),
    current_user=Depends(get_current_user),
    db_session=Depends(get_db_session),
):
    try:
        codes = body.get("codes", [])
        r = await do_save_watchlist(db_session, current_user.get("user_id", ""), codes)
        return {"success": True, "data": r}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

