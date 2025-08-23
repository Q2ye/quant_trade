# quant_server/api/market.py
from fastapi import APIRouter, Depends, Query, HTTPException
from typing import Optional
from datetime import date

from quant_server.api.dependencies import get_data_service
from quant_server.db.data_service import DataService

router = APIRouter(prefix="/api/market", tags=["market"])


@router.get("/stocks")
async def get_stocks(
        page: int = Query(1, ge=1),
        limit: int = Query(20, ge=1, le=100),
        search: Optional[str] = Query(None),
        data_service: DataService = Depends(get_data_service)
):
    """获取股票列表"""
    offset = (page - 1) * limit
    stocks = data_service.stock_basic.get_list(offset=offset, limit=limit, search=search)
    total = data_service.stock_basic.count(search=search)

    return {
        "data": stocks,
        "pagination": {
            "page": page,
            "limit": limit,
            "total": total,
            "pages": (total + limit - 1) // limit
        }
    }


@router.get("/stock/{code}")
async def get_stock_detail(
        code: str,
        data_service: DataService = Depends(get_data_service)
):
    """获取个股详情"""
    stock = data_service.stock_basic.get_by_code(code)
    if not stock:
        raise HTTPException(status_code=404, detail="Stock not found")

    # 获取公司信息
    company = data_service.stock_company.get_by_code(code)

    return {
        "basic": stock,
        "company": company
    }


@router.get("/stock/{code}/history")
async def get_stock_history(
        code: str,
        start_date: date = Query(...),
        end_date: date = Query(...),
        freq: str = Query("D", regex="^(D|W|M|1min|5min|15min|30min|60min)$"),
        data_service: DataService = Depends(get_data_service)
):
    """获取个股历史数据"""
    # 验证股票存在
    stock = data_service.stock_basic.get_by_code(code)
    if not stock:
        raise HTTPException(status_code=404, detail="Stock not found")

    # 根据频率选择不同的服务
    if freq == "D":
        data = data_service.stock_daily.get_by_date_range(code, start_date, end_date)
    elif freq == "W":
        data = data_service.stock_weekly.get_by_date_range(code, start_date, end_date)
    elif freq == "M":
        data = data_service.stock_monthly.get_by_date_range(code, start_date, end_date)
    else:
        data = data_service.stock_minutes.get_by_date_range(code, start_date, end_date, freq)

    return {
        "symbol": code,
        "name": stock.name,
        "data": data
    }


@router.get("/etfs")
async def get_etfs(
        page: int = Query(1, ge=1),
        limit: int = Query(20, ge=1, le=100),
        data_service: DataService = Depends(get_data_service)
):
    """获取ETF列表"""
    offset = (page - 1) * limit
    etfs = data_service.etf_basic.get_list(offset=offset, limit=limit)
    total = data_service.etf_basic.count()

    return {
        "data": etfs,
        "pagination": {
            "page": page,
            "limit": limit,
            "total": total,
            "pages": (total + limit - 1) // limit
        }
    }


@router.get("/etf/{code}")
async def get_etf_detail(
        code: str,
        data_service: DataService = Depends(get_data_service)
):
    """获取ETF详情"""
    etf = data_service.etf_basic.get_by_code(code)
    if not etf:
        raise HTTPException(status_code=404, detail="ETF not found")

    return etf


@router.get("/indexes")
async def get_indexes(data_service: DataService = Depends(get_data_service)):
    """获取指数列表"""
    # 这里需要根据实际情况实现指数获取逻辑
    # 暂时返回空数组，需要根据数据源补充实现
    return {"data": []}


@router.get("/index/{code}")
async def get_index_detail(
        code: str,
        data_service: DataService = Depends(get_data_service)
):
    """获取指数详情"""
    # 这里需要根据实际情况实现指数详情获取逻辑
    # 暂时返回空对象，需要根据数据源补充实现
    return {}