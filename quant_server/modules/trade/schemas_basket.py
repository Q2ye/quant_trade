# -*- coding: utf-8 -*-
"""
篮子管理 Pydantic Schema
API 请求/响应模型定义
"""
from typing import Optional, List
from pydantic import BaseModel, Field
from utils.api_utils.pagination_config import PaginationParams


class BasketQueryParams(PaginationParams):
    """篮子列表查询参数"""
    keyword: Optional[str] = Field(default=None, description="搜索关键词")


class BasketItemSchema(BaseModel):
    """篮子成分项"""
    ts_code: str = Field(..., description="股票代码")
    weight: float = Field(..., ge=0, le=1, description="权重(0-1)")


class CreateBasketRequest(BaseModel):
    """创建篮子请求"""
    name: str = Field(..., min_length=1, max_length=100, description="篮子名称")
    description: Optional[str] = Field(default=None, description="篮子描述")
    items: Optional[List[BasketItemSchema]] = Field(default=None, description="初始成分股")


class UpdateBasketRequest(BaseModel):
    """更新篮子请求"""
    name: Optional[str] = Field(default=None, min_length=1, max_length=100, description="篮子名称")
    description: Optional[str] = Field(default=None, description="篮子描述")
    items: Optional[List[BasketItemSchema]] = Field(default=None, description="更新成分股")


class AddItemRequest(BaseModel):
    """添加成分股请求"""
    ts_code: str = Field(..., description="股票代码")
    weight: float = Field(..., ge=0, le=1, description="权重(0-1)")


class AdjustWeightRequest(BaseModel):
    """调整权重请求"""
    weight: float = Field(..., ge=0, le=1, description="新权重(0-1)")


class BasketPerformanceRequest(BaseModel):
    """篮子绩效查询参数"""
    start_date: str = Field(..., description="开始日期 yyyy-MM-dd")
    end_date: str = Field(..., description="结束日期 yyyy-MM-dd")
    benchmark: Optional[str] = Field(default=None, description="基准指数代码")
