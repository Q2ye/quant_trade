# -*- coding: utf-8 -*-
"""
篮子管理 API 路由
负责将 HTTP 请求路由到交易模块的 BasketHandler 处理层
位置：quant_server/api/routers/basket_router.py
"""
import logging
from typing import Dict

from fastapi import APIRouter, Depends, HTTPException, status, Query
from sqlalchemy.ext.asyncio import AsyncSession

from api.dependencies.auth import get_current_user
from api.dependencies.database import get_db_session
from modules.trade.schemas_basket import (
    CreateBasketRequest,
    UpdateBasketRequest,
    AddItemRequest,
    AdjustWeightRequest,
)
from modules.trade.handlers import (
    get_basket_list,
    get_basket_detail,
    create_basket_item,
    update_basket_item,
    delete_basket_item,
    add_basket_item,
    adjust_basket_weight,
    remove_basket_item,
    get_basket_performance,
)
from utils.api_utils.response_formatter import success_response

logger = logging.getLogger(__name__)

router = APIRouter(tags=["篮子"])


# ============================================================
# GET  /basket          — 篮子列表（分页 + 搜索）
# ============================================================
@router.get("")
async def get_baskets(
    page: int = Query(default=1, ge=1, description="页码"),
    page_size: int = Query(default=20, ge=1, le=100, description="每页条数"),
    keyword: str = Query(default=None, description="搜索关键词"),
    _current_user: Dict = Depends(get_current_user),
    db_session: AsyncSession = Depends(get_db_session),
):
    try:
        result = await get_basket_list(
            session=db_session,
            page=page,
            page_size=page_size,
            keyword=keyword,
        )
        return success_response(message=result["message"], data=result.get("data"))
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"获取篮子列表失败: {e}")
        raise HTTPException(status_code=500, detail=str(e))


# ============================================================
# POST /basket          — 创建篮子
# ============================================================
@router.post("", status_code=201)
async def create_basket(
    body: CreateBasketRequest,
    _current_user: Dict = Depends(get_current_user),
    db_session: AsyncSession = Depends(get_db_session),
):
    try:
        items = None
        if body.items:
            items = [{"ts_code": it.ts_code, "weight": it.weight} for it in body.items]
        result = await create_basket_item(
            session=db_session,
            name=body.name,
            description=body.description or "",
            items=items,
        )
        return success_response(message=result["message"], data=result.get("data"))
    except Exception as e:
        logger.error(f"创建篮子失败: {e}")
        raise HTTPException(status_code=500, detail=str(e))


# ============================================================
# GET  /basket/{id}     — 篮子详情（含成分股）
# ============================================================
@router.get("/{basket_id}")
async def get_basket(
    basket_id: str,
    _current_user: Dict = Depends(get_current_user),
    db_session: AsyncSession = Depends(get_db_session),
):
    try:
        result = await get_basket_detail(session=db_session, basket_id=basket_id)
        return success_response(message=result["message"], data=result.get("data"))
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
    _current_user: Dict = Depends(get_current_user),
    db_session: AsyncSession = Depends(get_db_session),
):
    try:
        items = None
        if body.items is not None:
            items = [{"ts_code": it.ts_code, "weight": it.weight} for it in body.items]
        result = await update_basket_item(
            session=db_session,
            basket_id=basket_id,
            name=body.name,
            description=body.description,
            items=items,
        )
        return success_response(message=result["message"], data=result.get("data"))
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
    _current_user: Dict = Depends(get_current_user),
    db_session: AsyncSession = Depends(get_db_session),
):
    try:
        result = await delete_basket_item(session=db_session, basket_id=basket_id)
        return success_response(message=result["message"], data=result.get("data"))
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
    _current_user: Dict = Depends(get_current_user),
    db_session: AsyncSession = Depends(get_db_session),
):
    try:
        result = await add_basket_item(
            session=db_session,
            basket_id=basket_id,
            ts_code=body.ts_code,
            weight=body.weight,
        )
        return success_response(message=result["message"], data=result.get("data"))
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
    _current_user: Dict = Depends(get_current_user),
    db_session: AsyncSession = Depends(get_db_session),
):
    try:
        result = await adjust_basket_weight(
            session=db_session,
            basket_id=basket_id,
            ts_code=ts_code,
            weight=body.weight,
        )
        return success_response(message=result["message"], data=result.get("data"))
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
    _current_user: Dict = Depends(get_current_user),
    db_session: AsyncSession = Depends(get_db_session),
):
    try:
        result = await remove_basket_item(
            session=db_session,
            basket_id=basket_id,
            ts_code=ts_code,
        )
        return success_response(message=result["message"], data=result.get("data"))
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
    _current_user: Dict = Depends(get_current_user),
    db_session: AsyncSession = Depends(get_db_session),
):
    try:
        result = await get_basket_performance(
            session=db_session,
            basket_id=basket_id,
            start_date=start_date,
            end_date=end_date,
            benchmark=benchmark,
        )
        return success_response(message=result["message"], data=result.get("data"))
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"获取绩效失败: {e}")
        raise HTTPException(status_code=500, detail=str(e))
