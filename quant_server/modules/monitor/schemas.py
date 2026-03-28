# -*- coding: utf-8 -*-
"""
监控模块Pydantic模型
API请求/响应模型定义
"""
from pydantic import BaseModel, Field
from quant_server.utils.api_utils.pagination_config import PaginationParams

from typing import Optional, List, Any, Dict
from datetime import datetime


class SystemMetricsRequest(BaseModel):
    """系统监控指标请求"""


class SystemMetricsResponse(BaseModel):
    """系统监控指标响应"""
    success: bool = Field(default=True)
    data: Dict[str, Any] = Field(default_factory=dict)


class RiskAlertsRequest(BaseModel):
    """风险告警请求"""
    alert_level: Optional[str] = Field(default=None, description="告警级别")


class RiskAlertsResponse(BaseModel):
    """风险告警响应"""
    success: bool = Field(default=True)
    data: List[Dict[str, Any]] = Field(default_factory=list)
    pagination: Dict[str, int] = Field(default_factory=dict)


class BusinessMetricsRequest(BaseModel):
    """业务指标请求"""
    start_date: Optional[str] = Field(default=None, description="开始日期")
    end_date: Optional[str] = Field(default=None, description="结束日期")


class BusinessMetricsResponse(BaseModel):
    """业务指标响应"""
    success: bool = Field(default=True)
    data: Dict[str, Any] = Field(default_factory=dict)


class AlertHistoryRequest(PaginationParams):
    """告警历史请求"""
    alert_level: Optional[str] = Field(default=None, description="告警级别")


class AlertHistoryResponse(BaseModel):
    """告警历史响应"""
    success: bool = Field(default=True)
    data: List[Dict[str, Any]] = Field(default_factory=list)
    pagination: Dict[str, int] = Field(default_factory=dict)


class AlertRuleRequest(BaseModel):
    """告警规则请求"""
    name: str = Field(..., description="规则名称")
    alert_type: str = Field(..., description="告警类型")
    condition: Dict[str, Any] = Field(..., description="触发条件")
    threshold: float = Field(..., description="阈值")
    alert_level: str = Field(..., description="告警级别")


class AlertRuleResponse(BaseModel):
    """告警规则响应"""
    success: bool = Field(default=True)
    data: Optional[Dict[str, Any]] = Field(default=None)


class ManualAlertRequest(BaseModel):
    """手动告警请求"""
    alert_type: str = Field(..., description="告警类型")
    message: str = Field(..., description="告警消息")
    alert_level: str = Field(default="warning", description="告警级别")


class HealthStatusResponse(BaseModel):
    """健康状态响应"""
    success: bool = Field(default=True)
    data: Dict[str, Any] = Field(default_factory=dict)


class PerformanceStatsRequest(BaseModel):
    """性能统计请求"""
    start_date: Optional[str] = Field(default=None, description="开始日期")
    end_date: Optional[str] = Field(default=None, description="结束日期")


class PerformanceStatsResponse(BaseModel):
    """性能统计响应"""
    success: bool = Field(default=True)
    data: Dict[str, Any] = Field(default_factory=dict)
