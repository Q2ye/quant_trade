# -*- coding: utf-8 -*-
"""
系统模块Pydantic模型
API请求/响应模型定义
"""
from pydantic import BaseModel, Field
from quant_server.utils.api_utils.pagination_config import PaginationParams

from typing import Optional, List, Any, Dict
from datetime import datetime


class SystemStatusResponse(BaseModel):
    """系统状态响应"""
    success: bool = Field(default=True)
    data: Dict[str, Any] = Field(default_factory=dict)


class SystemLogsRequest(BaseModel):
    """系统日志请求"""
    log_level: Optional[str] = Field(default=None, description="日志级别")
    start_date: Optional[str] = Field(default=None, description="开始日期")
    end_date: Optional[str] = Field(default=None, description="结束日期")


class SystemLogsResponse(BaseModel):
    """系统日志响应"""
    success: bool = Field(default=True)
    data: List[Dict[str, Any]] = Field(default_factory=list)
    pagination: Dict[str, int] = Field(default_factory=dict)


class DataSyncRequest(BaseModel):
    """数据同步请求"""
    sync_type: str = Field(..., description="同步类型")
    data_source: Optional[str] = Field(default=None, description="数据源")


class DataSyncResponse(BaseModel):
    """数据同步响应"""
    success: bool = Field(default=True)
    data: Optional[Dict[str, Any]] = Field(default=None)


class SystemSettingsResponse(BaseModel):
    """系统设置响应"""
    success: bool = Field(default=True)
    data: Dict[str, Any] = Field(default_factory=dict)


class SystemSettingsUpdateRequest(BaseModel):
    """系统设置更新请求"""
    settings: Dict[str, Any] = Field(..., description="设置内容")


class ConnectionStatusResponse(BaseModel):
    """连接状态响应"""
    success: bool = Field(default=True)
    data: Dict[str, Any] = Field(default_factory=dict)


class SystemResourcesResponse(BaseModel):
    """系统资源响应"""
    success: bool = Field(default=True)
    data: Dict[str, Any] = Field(default_factory=dict)


class DatabaseStatusResponse(BaseModel):
    """数据库状态响应"""
    success: bool = Field(default=True)
    data: Dict[str, Any] = Field(default_factory=dict)
