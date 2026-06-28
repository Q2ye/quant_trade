# -*- coding: utf-8 -*-
"""
策略模块Pydantic模型
API请求/响应模型定义
"""
from typing import Optional, List, Any, Dict

from pydantic import BaseModel, Field

from utils.api_utils.pagination_config import PaginationParams


class StrategyListRequest(PaginationParams):
    """策略列表请求"""
    user_id: Optional[str] = Field(default=None, description="用户ID筛选")
    status: Optional[str] = Field(default=None, description="状态筛选")


class StrategyListResponse(BaseModel):
    """策略列表响应"""
    success: bool = Field(default=True)
    data: List[Dict[str, Any]] = Field(default_factory=list)
    pagination: Dict[str, int] = Field(default_factory=dict)


class StrategyDetailRequest(BaseModel):
    """策略详情请求"""
    include_positions: Optional[bool] = Field(default=None, description="是否包含持仓")


class StrategyDetailResponse(BaseModel):
    """策略详情响应"""
    success: bool = Field(default=True)
    data: Optional[Dict[str, Any]] = Field(default=None)


class StrategyCreateRequest(BaseModel):
    """策略创建请求"""
    name: str = Field(..., description="策略名称")
    description: Optional[str] = Field(default=None, description="策略描述")
    strategy_type: str = Field(default="cta", description="策略类型，默认 cta")
    code: Optional[str] = Field(default=None, description="策略代码")
    parameters: Optional[Dict[str, Any]] = Field(default_factory=dict, description="策略参数")


class StrategyUpdateRequest(BaseModel):
    """策略更新请求"""
    name: Optional[str] = Field(default=None, description="策略名称")
    description: Optional[str] = Field(default=None, description="策略描述")
    code: Optional[str] = Field(default=None, description="策略代码")
    parameters: Optional[Dict[str, Any]] = Field(default=None, description="策略参数")
    status: Optional[str] = Field(default=None, description="策略状态")


class StrategyResponse(BaseModel):
    """策略响应"""
    success: bool = Field(default=True)
    data: Optional[Dict[str, Any]] = Field(default=None)
    message: Optional[str] = Field(default=None)


class StrategyStartRequest(BaseModel):
    """策略启动请求"""
    capital: Optional[float] = Field(default=None, description="初始资金/分配额度")
    parameters: Optional[Dict[str, Any]] = Field(default_factory=dict, description="运行参数")
    run_mode: str = Field(default="live", description="运行模式: backtest/live/paper")
    execution_mode: str = Field(default="semi_auto", description="执行模式: semi_auto-半自动, full_auto-全自动")
    account_id: Optional[str] = Field(default=None, description="绑定的交易账户ID（实盘必选）")


class StrategyStopRequest(BaseModel):
    """策略停止请求"""
    force: bool = Field(default=False, description="是否强制停止")


class StrategyPerformanceRequest(BaseModel):
    """策略绩效请求"""
    start_date: Optional[str] = Field(default=None, description="开始日期")
    end_date: Optional[str] = Field(default=None, description="结束日期")
    benchmark: Optional[str] = Field(default=None, description="基准代码")


class StrategyPerformanceResponse(BaseModel):
    """策略绩效响应"""
    success: bool = Field(default=True)
    data: Optional[Dict[str, Any]] = Field(default=None)
    message: Optional[str] = Field(default=None)


class StrategyStatusResponse(BaseModel):
    """策略状态响应"""
    success: bool = Field(default=True)
    data: Optional[Dict[str, Any]] = Field(default=None)
    message: Optional[str] = Field(default=None)


# ==================== 策略模板 Schemas ====================

class TemplateListRequest(PaginationParams):
    """模板列表请求"""
    strategy_type: Optional[str] = Field(default=None, description="策略类型筛选")


class TemplateListResponse(BaseModel):
    """模板列表响应"""
    success: bool = Field(default=True)
    data: List[Dict[str, Any]] = Field(default_factory=list)
    pagination: Dict[str, int] = Field(default_factory=dict)


class TemplateDetailResponse(BaseModel):
    """模板详情响应"""
    success: bool = Field(default=True)
    data: Optional[Dict[str, Any]] = Field(default=None)


class TemplateCreateRequest(BaseModel):
    """模板创建请求"""
    name: str = Field(..., description="模板名称")
    strategy_type: str = Field(..., description="策略类型")
    code_template: str = Field(..., description="代码模板")
    description: Optional[str] = Field(default="", description="模板描述")
    default_parameters: Optional[Dict[str, Any]] = Field(default_factory=dict, description="默认参数")
    category: Optional[str] = Field(default="custom", description="分类")


class TemplateUpdateRequest(BaseModel):
    """模板更新请求"""
    name: Optional[str] = Field(default=None, description="模板名称")
    description: Optional[str] = Field(default=None, description="模板描述")
    code_template: Optional[str] = Field(default=None, description="代码模板")
    default_parameters: Optional[Dict[str, Any]] = Field(default=None, description="默认参数")
    category: Optional[str] = Field(default=None, description="分类")


class TemplateResponse(BaseModel):
    """模板响应"""
    success: bool = Field(default=True)
    data: Optional[Dict[str, Any]] = Field(default=None)
    message: Optional[str] = Field(default=None)


class CreateFromTemplateRequest(BaseModel):
    """基于模板创建策略请求"""
    name: str = Field(..., description="策略名称")
    custom_parameters: Optional[Dict[str, Any]] = Field(default_factory=dict, description="自定义参数（覆盖模板默认值）")
