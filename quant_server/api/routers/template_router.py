# -*- coding: utf-8 -*-
"""
策略模板API路由
负责策略模板的CRUD管理和基于模板创建策略
"""
import logging
from typing import Dict, Optional

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession

from api.dependencies.auth import get_current_user
from api.dependencies.database import get_db_session
from modules.strategy.handlers import (
    get_template_list as _get_template_list,
    get_template_detail as _get_template_detail,
    create_template as _create_template,
    update_template as _update_template,
    delete_template as _delete_template,
    create_strategy_from_template as _create_strategy_from_template,
)
from modules.strategy.schemas import (
    TemplateListRequest,
    TemplateListResponse,
    TemplateDetailResponse,
    TemplateCreateRequest,
    TemplateUpdateRequest,
    TemplateResponse,
    CreateFromTemplateRequest,
    StrategyResponse,
)
from utils.api_utils.response_formatter import success_response, error_response

logger = logging.getLogger(__name__)

router = APIRouter(
    tags=["策略模板"],
    responses={
        401: {"description": "认证失败"},
        403: {"description": "权限不足"},
        500: {"description": "服务器内部错误"}
    }
)


# ==================== 模板 CRUD ====================

@router.get("", response_model=TemplateListResponse)
async def list_templates_api(
    strategy_type: Optional[str] = None,
    page: int = 1,
    page_size: int = 20,
    current_user: Dict = Depends(get_current_user),
    db_session: AsyncSession = Depends(get_db_session),
) -> TemplateListResponse:
    """获取策略模板列表"""
    try:
        from modules.strategy.schemas import TemplateListRequest
        request = TemplateListRequest(
            strategy_type=strategy_type, page=page, page_size=page_size
        )
        result = await _get_template_list(
            session=db_session, request=request, user_id=current_user.get("id")
        )
        return result
    except Exception as e:
        logger.error(f"获取模板列表失败: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail="服务器内部错误，请稍后重试")


@router.get("/{template_id}", response_model=TemplateDetailResponse)
async def get_template_detail_api(
    template_id: str,
    current_user: Dict = Depends(get_current_user),
    db_session: AsyncSession = Depends(get_db_session),
) -> TemplateDetailResponse:
    """获取模板详情"""
    try:
        result = await _get_template_detail(
            session=db_session, template_id=template_id
        )
        return result
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e))
    except Exception as e:
        logger.error(f"获取模板详情失败: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail="服务器内部错误，请稍后重试")


@router.post("", response_model=TemplateResponse, status_code=201)
async def create_template_api(
    request: TemplateCreateRequest,
    current_user: Dict = Depends(get_current_user),
    db_session: AsyncSession = Depends(get_db_session),
) -> TemplateResponse:
    """创建策略模板"""
    try:
        result = await _create_template(
            session=db_session, request=request
        )
        return result
    except Exception as e:
        logger.error(f"创建模板失败: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail="服务器内部错误，请稍后重试")


@router.put("/{template_id}", response_model=TemplateResponse)
async def update_template_api(
    template_id: str,
    request: TemplateUpdateRequest,
    current_user: Dict = Depends(get_current_user),
    db_session: AsyncSession = Depends(get_db_session),
) -> TemplateResponse:
    """更新策略模板"""
    try:
        result = await _update_template(
            session=db_session, template_id=template_id, request=request
        )
        return result
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e))
    except Exception as e:
        logger.error(f"更新模板失败: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail="服务器内部错误，请稍后重试")


@router.delete("/{template_id}", status_code=204)
async def delete_template_api(
    template_id: str,
    current_user: Dict = Depends(get_current_user),
    db_session: AsyncSession = Depends(get_db_session),
):
    """删除策略模板"""
    try:
        await _delete_template(session=db_session, template_id=template_id)
        return success_response(message="模板删除成功", data={"template_id": template_id})
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e))
    except Exception as e:
        logger.error(f"删除模板失败: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail="服务器内部错误，请稍后重试")


# ==================== 基于模板创建策略 ====================

@router.post("/{template_id}/create-strategy", response_model=StrategyResponse, status_code=201)
async def create_strategy_from_template_api(
    template_id: str,
    request: CreateFromTemplateRequest,
    current_user: Dict = Depends(get_current_user),
    db_session: AsyncSession = Depends(get_db_session),
) -> StrategyResponse:
    """基于模板创建策略"""
    try:
        result = await _create_strategy_from_template(
            session=db_session,
            template_id=template_id,
            request=request,
            user_id=current_user.get("id"),
        )
        return result
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e))
    except Exception as e:
        logger.error(f"基于模板创建策略失败: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail="服务器内部错误，请稍后重试")
