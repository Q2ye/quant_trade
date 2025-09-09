# quant_server/api/basket.py
# 篮子接口
from fastapi import APIRouter, Depends, Query, HTTPException, Body
from datetime import date

from quant_server.api.dependencies import get_data_service
from quant_server.db.data_service import DataService

router = APIRouter(prefix="/api/basket", tags=["basket"])

@router.get("")
async def get_baskets(
        page: int = Query(1, ge=1),
        limit: int = Query(20, ge=1, le=100),
        data_service: DataService = Depends(get_data_service)
):
    """获取篮子列表"""
    baskets = data_service.baskets.get_list(offset=(page - 1) * limit, limit=limit)
    total = data_service.baskets.count()

    return {
        "data": baskets,
        "pagination": {
            "page": page,
            "limit": limit,
            "total": total,
            "pages": (total + limit - 1) // limit
        }
    }

@router.post("")
async def create_basket(
        basket_data: dict = Body(...),
        data_service: DataService = Depends(get_data_service)
):
    """创建新篮子"""
    basket_id = data_service.baskets.create(basket_data)
    return {"id": basket_id, "name": basket_data.get("name", "New Basket")}

@router.get("/{id}")
async def get_basket(
        id: str,
        data_service: DataService = Depends(get_data_service)
):
    """获取篮子详情"""
    basket = data_service.baskets.get_by_id(id)
    if not basket:
        raise HTTPException(status_code=404, detail="Basket not found")

    items = data_service.basket_items.get_by_basket(id)

    return {
        "basket": basket,
        "items": items
    }

@router.put("/{id}")
async def update_basket(
        id: str,
        basket_data: dict = Body(...),
        data_service: DataService = Depends(get_data_service)
):
    """更新篮子"""
    updated = data_service.baskets.update(id, basket_data)
    if not updated:
        raise HTTPException(status_code=404, detail="Basket not found")

    return {"updated": True, "id": id}

@router.delete("/{id}")
async def delete_basket(
        id: str,
        data_service: DataService = Depends(get_data_service)
):
    """删除篮子"""
    deleted = data_service.baskets.delete(id)
    if not deleted:
        raise HTTPException(status_code=404, detail="Basket not found")

    return {"deleted": True, "id": id}

@router.get("/{id}/performance")
async def get_basket_performance(
        id: str,
        start_date: date = Query(...),
        end_date: date = Query(...),
        data_service: DataService = Depends(get_data_service)
):
    """获取篮子表现"""
    basket = data_service.baskets.get_by_id(id)
    if not basket:
        raise HTTPException(status_code=404, detail="Basket not found")

    # 这里需要实现篮子表现计算逻辑
    # 暂时返回模拟数据
    return {
        "basket_id": id,
        "period": {
            "start": start_date,
            "end": end_date
        },
        "performance": {
            "total_return": 0.12,
            "annualized_return": 0.18,
            "volatility": 0.15,
            "sharpe_ratio": 1.2
        }
    }