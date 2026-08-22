# -*- coding: utf-8 -*-
"""
系统模块Pydantic模型
API请求/响应模型定义
"""
from typing import Optional, List, Any, Dict

from pydantic import BaseModel, Field


class SystemStatusResponse(BaseModel):
	"""系统状态响应"""
	success: bool = Field(default=True)
	data: Dict[str, Any] = Field(default_factory=dict)


class SystemLogsRequest(BaseModel):
	"""审计日志查询请求（2026-08：由 system_logs 改为 audit_logs 审计日志）"""
	action_type: Optional[str] = Field(default=None, description="操作类型：login/logout/create/update/delete/config_change/security_event/system_event")
	status: Optional[str] = Field(default=None, description="操作状态：success/failed/partial")
	username: Optional[str] = Field(default=None, description="用户名（模糊搜索）")
	start_date: Optional[str] = Field(default=None, description="开始时间（ISO 格式）")
	end_date: Optional[str] = Field(default=None, description="结束时间（ISO 格式）")
	page: int = Field(default=1, ge=1, description="页码")
	page_size: int = Field(default=20, ge=1, le=200, description="每页条数")


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


# ==================== 认证请求/响应 ====================


class LoginRequest(BaseModel):
	"""登录请求"""
	username: str = Field(..., min_length=1, max_length=50)
	password: str = Field(..., min_length=1)


class RegisterRequest(BaseModel):
	"""注册请求"""
	username: str = Field(..., min_length=1, max_length=50)
	password: str = Field(..., min_length=1)
	email: str = Field(default="")
	phone: str = Field(default="")
	real_name: str = Field(default="")


class RefreshTokenRequest(BaseModel):
	"""刷新 Token 请求"""
	refresh_token: str = Field(..., min_length=1)


class ChangePasswordRequest(BaseModel):
	"""修改密码请求"""
	old_password: str = Field(..., min_length=1)
	new_password: str = Field(..., min_length=1)


class AuthResponse(BaseModel):
	"""认证响应"""
	success: bool = Field(default=True)
	data: Optional[Dict[str, Any]] = Field(default=None)


# ==================== 用户管理请求/响应 ====================


class UserCreateRequest(BaseModel):
	"""创建用户请求"""
	username: str = Field(..., min_length=1, max_length=50)
	password: str = Field(..., min_length=1)
	role: str = Field(default="user")
	email: str = Field(default="")
	phone: str = Field(default="")
	real_name: str = Field(default="")


class UserUpdateRequest(BaseModel):
	"""更新用户请求"""
	username: Optional[str] = Field(default=None)
	email: Optional[str] = Field(default=None)
	phone: Optional[str] = Field(default=None)
	real_name: Optional[str] = Field(default=None)
	role: Optional[str] = Field(default=None)
	is_active: Optional[bool] = Field(default=None)


class UserListResponse(BaseModel):
	"""用户列表响应"""
	success: bool = Field(default=True)
	data: Dict[str, Any] = Field(default_factory=dict)


class UserDetailResponse(BaseModel):
	"""用户详情响应"""
	success: bool = Field(default=True)
	data: Optional[Dict[str, Any]] = Field(default=None)


class UserStatisticsResponse(BaseModel):
	"""用户统计响应"""
	success: bool = Field(default=True)
	data: Dict[str, Any] = Field(default_factory=dict)


# ==================== 角色管理请求/响应 ====================


class RoleCreateRequest(BaseModel):
	"""创建角色请求"""
	role_code: str = Field(..., min_length=1, max_length=50)
	role_name: str = Field(..., min_length=1, max_length=100)
	description: str = Field(default="")


class RoleUpdateRequest(BaseModel):
	"""更新角色请求"""
	role_name: Optional[str] = Field(default=None)
	description: Optional[str] = Field(default=None)
	permissions: Optional[list] = Field(default=None)


class RoleListResponse(BaseModel):
	"""角色列表响应"""
	success: bool = Field(default=True)
	data: List[Dict[str, Any]] = Field(default_factory=list)


class RoleDetailResponse(BaseModel):
	"""角色详情响应"""
	success: bool = Field(default=True)
	data: Optional[Dict[str, Any]] = Field(default=None)


# ==================== 新增认证/系统管理请求响应 ====================


class PasswordResetRequest(BaseModel):
	"""密码重置请求"""
	email: str = Field(..., min_length=1, description="注册邮箱")


class PasswordResetConfirmRequest(BaseModel):
	"""密码重置确认请求"""
	token: str = Field(..., min_length=1, description="重置 token")
	newPassword: str = Field(..., min_length=1, description="新密码")


class EmailVerifyRequest(BaseModel):
	"""邮箱验证请求"""
	token: str = Field(..., min_length=1, description="验证 token")


class ResendVerificationRequest(BaseModel):
	"""重新发送验证邮件请求"""
	email: str = Field(..., min_length=1, description="注册邮箱")


class MessageResponse(BaseModel):
	"""通用消息响应"""
	success: bool = Field(default=True)
	message: str = Field(default="")


class TokenInfoResponse(BaseModel):
	"""Token 元信息响应"""
	expiresAt: Optional[int] = Field(default=None, description="过期时间 (Unix timestamp)")
	issuedAt: Optional[int] = Field(default=None, description="签发时间 (Unix timestamp)")
	tokenType: str = Field(default="access", description="Token 类型")
	userId: Optional[str] = Field(default=None, description="用户 ID")


class TokenValidateResponse(BaseModel):
	"""Token 验证响应"""
	isValid: bool = Field(default=False)
	user: Optional[Dict[str, Any]] = Field(default=None)


class CacheClearResponse(BaseModel):
	"""缓存清理响应"""
	cleared: bool = Field(default=True)
	message: str = Field(default="系统缓存已清理")


class ServiceRestartResponse(BaseModel):
	"""服务重启响应"""
	success: bool = Field(default=True)
	message: str = Field(default="")
