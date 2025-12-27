"""
数据同步请求模型定义
"""
from datetime import datetime
from typing import Dict, Any, List, Optional
from pydantic import BaseModel, Field
from enum import Enum


class SyncMode(str, Enum):
    """同步模式枚举"""
    SYNC = "sync"    # 同步执行
    ASYNC = "async"  # 异步执行


class SyncPriority(int, Enum):
    """同步优先级枚举"""
    HIGH = 1     # 高优先级（立即执行）
    NORMAL = 2   # 正常优先级（队列执行）
    LOW = 3      # 低优先级（后台执行）


class BaseSyncRequest(BaseModel):
    """基础同步请求模型"""
    days: int = Field(30, ge=1, le=365, description="同步天数")
    start_date: Optional[str] = Field(None, description="开始日期(YYYYMMDD)")
    end_date: Optional[str] = Field(None, description="结束日期(YYYYMMDD)")
    stock_codes: Optional[List[str]] = Field(None, description="指定股票代码列表")
    exchange: Optional[str] = Field(None, description="交易所代码")
    batch_size: int = Field(100, ge=1, le=500, description="批量处理大小")
    priority: SyncPriority = Field(SyncPriority.NORMAL, description="同步优先级")


class BatchSyncRequest(BaseSyncRequest):
    """批量同步请求模型"""
    data_types: List[str] = Field(..., description="需要同步的数据类型列表")
    sync_mode: Optional[SyncMode] = Field(SyncMode.SYNC, description="同步模式")
    enable_clean: bool = Field(True, description="是否启用数据清洗")
    clean_config: Optional[Dict[str, Any]] = Field(None, description="清洗配置")


class DataTypeInfo(BaseModel):
    """数据类型信息模型"""
    code: str = Field(..., description="数据类型代码")
    name: str = Field(..., description="数据类型名称")
    description: str = Field(..., description="数据类型描述")
    estimated_time: int = Field(..., description="预估同步时间(秒)")
    requires_clean: bool = Field(True, description="是否需要数据清洗")
    is_core: bool = Field(False, description="是否为核心数据类型")