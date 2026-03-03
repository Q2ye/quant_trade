# # quant_server/utils/api_utils/openapi.py
# """
# OpenAPI文档定制模块
#
# 提供FastAPI OpenAPI文档的自定义配置，包括：
# - 文档元数据配置
# - 标签和分组管理
# - 安全方案配置
# - 响应模型文档定制
# - 文档过滤器
#
# Author: 量化交易系统团队
# Version: 1.1.0
# """
#
# import logging
# from typing import Dict, Any, List, Optional, Callable
# from enum import Enum
# from functools import wraps
# from datetime import datetime
#
# from fastapi import FastAPI, Request, HTTPException
# from fastapi.openapi.docs import get_swagger_ui_html, get_redoc_html
# from fastapi.openapi.utils import get_openapi
# from fastapi.responses import HTMLResponse, JSONResponse
# from fastapi.staticfiles import StaticFiles
# from fastapi.middleware.cors import CORSMiddleware
# from pydantic import BaseModel, Field
#
# from quant_server.shared.config.settings import Settings
# from quant_server.core.exceptions.error_codes import ErrorCode
# from quant_server.core.exceptions.base import BaseAPIException
#
# logger = logging.getLogger(__name__)
#
#
# class OpenAPITag(str, Enum):
# 	"""OpenAPI标签枚举"""
# 	SYSTEM = "系统管理"
# 	DATA = "数据管理"
# 	STRATEGY = "策略管理"
# 	TRADE = "交易管理"
# 	BACKTEST = "回测管理"
# 	ACCOUNT = "账户管理"
# 	ANALYSIS = "分析管理"
# 	MONITOR = "监控管理"
# 	AUTH = "认证授权"
# 	HEALTH = "健康检查"
# 	UTILS = "工具接口"
# 	WEBSOCKET = "WebSocket"
#
#
# class PermissionLevel(str, Enum):
# 	"""API权限级别"""
# 	PUBLIC = "公开接口"
# 	USER = "用户接口"
# 	ADMIN = "管理员接口"
# 	SYSTEM = "系统接口"
# 	TRADER = "交易员接口"
#
#
# class APIVersion(BaseModel):
# 	"""API版本信息"""
# 	title: str
# 	version: str
# 	description: str
# 	build_date: str
# 	environment: str
#
#
# class ErrorResponse(BaseModel):
# 	"""错误响应模型"""
# 	code: str = Field(..., description="错误代码")
# 	message: str = Field(..., description="错误描述")
# 	detail: Optional[Dict[str, Any]] = Field(None, description="错误详情")
# 	timestamp: str = Field(default_factory=lambda: datetime.now().isoformat(), description="错误发生时间")
#
#
# class PaginationResponse(BaseModel):
# 	"""分页响应模型"""
# 	page: int = Field(..., description="当前页码")
# 	size: int = Field(..., description="每页数量")
# 	total: int = Field(..., description="总记录数")
# 	pages: int = Field(..., description="总页数")
# 	has_prev: bool = Field(..., description="是否有上一页")
# 	has_next: bool = Field(..., description="是否有下一页")
#
#
# class OpenAPIConfig(BaseModel):
# 	"""OpenAPI配置模型"""
#
# 	title: str = "量化交易系统 API"
# 	version: str = "1.0.0"
# 	description: str = """
# # 量化交易系统 API 文档
#
# ## 概述
#
# 量化交易系统是一个基于Python和FastAPI构建的高性能交易系统，采用混合架构设计，支持：
#
# ### 核心功能
# - **数据管理**: 数据同步、清洗、因子计算、质量检查
# - **策略管理**: 策略开发、回测、优化、执行
# - **交易管理**: 订单管理、风险控制、持仓管理、执行优化
# - **回测管理**: 历史回测、参数优化、绩效验证
# - **账户管理**: 账户信息、资金管理、持仓查询
# - **分析管理**: 绩效评估、归因分析、交易分析
# - **监控管理**: 系统监控、风险监控、报警管理
# - **系统管理**: 用户权限、系统配置、任务调度
#
# ### 架构特点
# 1. **混合架构**: 稳定层（分层架构）+ 灵活层（模块化架构）
# 2. **事件驱动**: 全局事件总线实现模块间通信
# 3. **微服务设计**: 模块独立，通过依赖注入获取基础设施
# 4. **高性能**: 异步IO，连接池，缓存优化
#
# ### 技术栈
# - **后端框架**: FastAPI + SQLAlchemy + Pydantic
# - **数据库**: PostgreSQL + Redis
# - **消息队列**: RabbitMQ/Kafka
# - **缓存**: Redis
# - **任务调度**: Celery + APScheduler
# - **监控**: Prometheus + Grafana
# - **部署**: Docker + Kubernetes
#
# ## 权限说明
#
# | 权限级别 | 说明 | 适用接口 |
# |---------|------|----------|
# | PUBLIC | 公开接口，无需认证 | 登录、注册、健康检查 |
# | USER | 普通用户接口，需要登录 | 数据查询、策略查看、账户查询 |
# | ADMIN | 管理员接口，需要管理员权限 | 用户管理、系统配置、数据管理 |
# | SYSTEM | 系统接口，需要系统权限 | 引擎控制、任务调度、监控管理 |
# | TRADER | 交易员接口，需要交易权限 | 订单操作、策略执行、风险控制 |
#
# ## 错误码规范
#
# 所有接口使用统一的错误码格式：
# ```
# json
# {
#     "code": "ERROR_CODE",
#     "message": "错误描述",
#     "detail": "错误详情（可选）",
#     "timestamp": "2023-01-01T00:00:00"
# }
# ```
