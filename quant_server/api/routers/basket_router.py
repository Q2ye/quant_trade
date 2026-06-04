# -*- coding: utf-8 -*-
"""
篮子管理 API 路由
负责将 HTTP 请求路由到篮子管理业务处理层
位置：quant_server/api/routers/basket_router.py
"""
import logging
from typing import Dict

from fastapi import APIRouter, Depends, HTTPException, status, Query
from sqlalchemy.ext.asyncio import AsyncSession

from api.dependencies.auth import get_current_user
from api.dependencies.database import get_db_session
from modules.trade.schemas_basket import (
    BasketQueryParams,
    CreateBasketRequest,
    UpdateBasketRequest,
    AddItemRequest,
    AdjustWeightRequest,
    BasketPerformanceRequest,
)
from shared.database.repositories.operation.basket.basket_repo import BasketRepository
from shared.database.repositories.operation.basket.basket_item_repo import BasketItemRepository
from shared.database.repositories.types import PaginationParams, FilterCondition, SortCondition
from utils.api_utils.response_formatter import success_response, error_response

logger = logging.getLogger(__name__)

router = APIRouter(tags=["basket"])


# ============================================================
# GET  /basket          — 篮子列表（分页 + 搜索）
# ============================================================
@router.get("")
async def get_baskets(
    page: int = Query(default=1, ge=1, description="页码"),
    page_size: int = Query(default=20, ge=1, le=100, description="每页条数"),
    keyword: str = Query(default=None, description="搜索关键词"),
    current_user: Dict = Depends(get_current_user),
    db_session: AsyncSession = Depends(get_db_session),
):
    try:
        repo = BasketRepository(db_session)
        pagination = PaginationParams(page=page, page_size=page_size)

        if keyword:
            result = await repo.search_baskets(keyword, pagination)
        else:
            result = await repo.get_user_baskets(pagination=pagination)

        return success_response(
            message="篮子列表获取成功",
            data={
                "items": [await _basket_to_dict(repo, b) for b in result.items],
                "total": result.total,
                "page": result.page,
                "page_size": result.page_size,
            },
        )
    except Exception as e:
        logger.error(f"获取篮子列表失败: {e}")
        raise HTTPException(status_code=500, detail=str(e))


# ============================================================
# POST /basket          — 创建篮子
# ============================================================
@router.post("", status_code=201)
async def create_basket(
    body: CreateBasketRequest,
    current_user: Dict = Depends(get_current_user),
    db_session: AsyncSession = Depends(get_db_session),
):
    try:
        repo = BasketRepository(db_session)
        basket_data = {"name": body.name, "description": body.description or ""}
        items_data = [{"ts_code": it.ts_code, "weight": it.weight} for it in (body.items or [])]

        basket = await repo.create_basket_with_items(basket_data, items_data)

        return success_response(
            message="篮子创建成功",
            data=await _basket_to_dict(repo, basket),
        )
    except Exception as e:
        logger.error(f"创建篮子失败: {e}")
        raise HTTPException(status_code=500, detail=str(e))


# ============================================================
# GET  /basket/{id}     — 篮子详情（含成分股）
# ============================================================
@router.get("/{basket_id}")
async def get_basket(
    basket_id: str,
    current_user: Dict = Depends(get_current_user),
    db_session: AsyncSession = Depends(get_db_session),
):
    try:
        repo = BasketRepository(db_session)
        basket = await repo.get_basket_with_items(basket_id)
        if not basket:
            raise HTTPException(status_code=404, detail="篮子不存在")

        return success_response(
            message="篮子详情获取成功",
            data=await _basket_to_dict(repo, basket),
        )
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"获取篮子详情失败: {e}")
        raise HTTPException(status_code=500, detail=str(e))


# ============================================================
# PUT  /basket/{id}     — 更新篮子
# ============================================================
@router.put("/{basket_id}")
async def update_basket(
    basket_id: str,
    body: UpdateBasketRequest,
    current_user: Dict = Depends(get_current_user),
    db_session: AsyncSession = Depends(get_db_session),
):
    try:
        repo = BasketRepository(db_session)
        existing = await repo.get(basket_id)
        if not existing:
            raise HTTPException(status_code=404, detail="篮子不存在")

        basket_data = {}
        if body.name is not None:
            basket_data["name"] = body.name
        if body.description is not None:
            basket_data["description"] = body.description

        items_data = None
        if body.items is not None:
            items_data = [{"ts_code": it.ts_code, "weight": it.weight} for it in body.items]

        basket = await repo.update_basket_with_items(basket_id, basket_data, items_data)

        return success_response(
            message="篮子更新成功",
            data=await _basket_to_dict(repo, basket),
        )
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"更新篮子失败: {e}")
        raise HTTPException(status_code=500, detail=str(e))


# ============================================================
# DELETE /basket/{id}   — 删除篮子
# ============================================================
@router.delete("/{basket_id}")
async def delete_basket(
    basket_id: str,
    current_user: Dict = Depends(get_current_user),
    db_session: AsyncSession = Depends(get_db_session),
):
    try:
        repo = BasketRepository(db_session)
        existing = await repo.get(basket_id)
        if not existing:
            raise HTTPException(status_code=404, detail="篮子不存在")

        await repo.delete_basket_with_items(basket_id)

        return success_response(message="篮子删除成功", data=None)
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"删除篮子失败: {e}")
        raise HTTPException(status_code=500, detail=str(e))


# ============================================================
# POST /basket/{id}/items     — 添加成分股
# ============================================================
@router.post("/{basket_id}/items")
async def add_item(
    basket_id: str,
    body: AddItemRequest,
    current_user: Dict = Depends(get_current_user),
    db_session: AsyncSession = Depends(get_db_session),
):
    try:
        repo = BasketRepository(db_session)
        basket = await repo.get(basket_id)
        if not basket:
            raise HTTPException(status_code=404, detail="篮子不存在")

        item_repo = BasketItemRepository(db_session)
        await item_repo.create({"basket_id": basket_id, "ts_code": body.ts_code, "weight": body.weight})

        basket = await repo.get_basket_with_items(basket_id)
        return success_response(
            message="成分股添加成功",
            data=await _basket_to_dict(repo, basket),
        )
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"添加成分股失败: {e}")
        raise HTTPException(status_code=500, detail=str(e))


# ============================================================
# PUT  /basket/{id}/items/{symbol}  — 调整权重
# ============================================================
@router.put("/{basket_id}/items/{ts_code}")
async def adjust_weight(
    basket_id: str,
    ts_code: str,
    body: AdjustWeightRequest,
    current_user: Dict = Depends(get_current_user),
    db_session: AsyncSession = Depends(get_db_session),
):
    try:
        item_repo = BasketItemRepository(db_session)
        await item_repo.update_item_weight(basket_id, ts_code, body.weight)

        repo = BasketRepository(db_session)
        basket = await repo.get_basket_with_items(basket_id)

        return success_response(
            message="权重调整成功",
            data=await _basket_to_dict(repo, basket),
        )
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"调整权重失败: {e}")
        raise HTTPException(status_code=500, detail=str(e))


# ============================================================
# DELETE /basket/{id}/items/{symbol}  — 移除成分股
# ============================================================
@router.delete("/{basket_id}/items/{ts_code}")
async def remove_item(
    basket_id: str,
    ts_code: str,
    current_user: Dict = Depends(get_current_user),
    db_session: AsyncSession = Depends(get_db_session),
):
    try:
        item_repo = BasketItemRepository(db_session)
        await item_repo.delete_by(basket_id=basket_id, ts_code=ts_code)

        return success_response(message="成分股移除成功", data=None)
    except Exception as e:
        logger.error(f"移除成分股失败: {e}")
        raise HTTPException(status_code=500, detail=str(e))


# ============================================================
# GET  /basket/{id}/performance  — 篮子绩效（占位）
# ============================================================
@router.get("/{basket_id}/performance")
async def get_performance(
    basket_id: str,
    start_date: str = Query(..., description="开始日期"),
    end_date: str = Query(..., description="结束日期"),
    benchmark: str = Query(default=None, description="基准指数"),
    current_user: Dict = Depends(get_current_user),
    db_session: AsyncSession = Depends(get_db_session),
):
    try:
        repo = BasketRepository(db_session)
        basket = await repo.get_basket_with_items(basket_id)
        if not basket:
            raise HTTPException(status_code=404, detail="篮子不存在")

        return success_response(
            message="篮子绩效分析（行情数据源接入中，暂返回占位数据）",
            data={
                "basket_id": basket_id,
                "start_date": start_date,
                "end_date": end_date,
                "total_return": 0,
                "annual_return": 0,
                "max_drawdown": 0,
                "sharpe_ratio": 0,
                "items": [{"ts_code": it.ts_code, "weight": it.weight} for it in basket.items],
            },
        )
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"获取绩效失败: {e}")
        raise HTTPException(status_code=500, detail=str(e))


# ============================================================
# 辅助函数
# ============================================================
async def _basket_to_dict(repo: BasketRepository, basket) -> dict:
    """将 Basket ORM 对象转为字典（含成分股）"""
    items = []
    if basket.items:
        items = [
            {"id": it.id, "ts_code": it.ts_code, "weight": it.weight}
            for it in basket.items
        ]
    return {
        "id": basket.id,
        "name": basket.name,
        "description": getattr(basket, "description", ""),
        "items": items,
        "item_count": len(items),
        "created_at": basket.created_at.isoformat() if basket.created_at else None,
        "updated_at": basket.updated_at.isoformat() if basket.updated_at else None,
    }
