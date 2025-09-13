from pydantic import BaseModel, Field
from typing import Optional, Dict, Any
from datetime import datetime

class StrategyCreate(BaseModel):
    """创建策略的请求模型"""
    name: str = Field(..., description="策略名称")
    description: Optional[str] = Field(None, description="策略描述")
    class_name: str = Field(..., description="策略类名")
    module_path: str = Field(..., description="模块路径")
    parameters: Dict[str, Any] = Field(default_factory=dict, description="策略参数")

    class Config:
        schema_extra = {
            "example": {
                "name": "双均线策略",
                "description": "基于5日和20日均线的趋势跟踪策略",
                "class_name": "DoubleMAStrategy",
                "module_path": "quant_server.strategies.double_ma",
                "parameters": {
                    "fast_period": 5,
                    "slow_period": 20,
                    "capital": 100000
                }
            }
        }

class StrategyResponse(BaseModel):
    """策略响应模型"""
    id: str = Field(..., description="策略ID")
    name: str = Field(..., description="策略名称")
    user_id: int = Field(..., description="用户ID")
    description: Optional[str] = Field(None, description="策略描述")
    class_name: str = Field(..., description="策略类名")
    module_path: str = Field(..., description="模块路径")
    status: str = Field(..., description="策略状态")
    parameters: Dict[str, Any] = Field(..., description="策略参数")
    created_at: datetime = Field(..., description="创建时间")
    updated_at: datetime = Field(..., description="更新时间")

    class Config:
        orm_mode = True
        schema_extra = {
            "example": {
                "id": "a1b2c3d4e5f6g7h8i9j0k1l2m3n4o5p",
                "name": "双均线策略",
                "user_id": 1,
                "description": "基于5日和20日均线的趋势跟踪策略",
                "class_name": "DoubleMAStrategy",
                "module_path": "quant_server.strategies.double_ma",
                "status": "stopped",
                "parameters": {
                    "fast_period": 5,
                    "slow_period": 20,
                    "capital": 100000
                },
                "created_at": "2023-01-01T00:00:00Z",
                "updated_at": "2023-01-01T00:00:00Z"
            }
        }