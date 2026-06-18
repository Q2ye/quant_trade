# -*- coding: utf-8 -*-
"""
系统模块API路由
基于混合架构设计，负责将HTTP请求路由到系统模块的业务处理层
位置：quant_server/api/routers/system_router.py
系统模块路由
"""
import logging
from typing import Dict

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession

from api.dependencies.auth import get_current_user
# 导入架构依赖
from api.dependencies.database import get_db_session
# 导入系统模块的业务层处理函数
from modules.system.handlers import (
	get_system_status,
	get_system_logs,
	get_system_settings,
	update_system_settings,
	get_connection_status,
	get_system_resources,
	get_database_status,
	check_system_module_health,
	# 认证
	login,
	register_user,
	refresh_token,
	change_password,
	# 用户管理
	list_users,
	get_user,
	create_user,
	update_user,
	delete_user,
	get_user_statistics,
	# 角色管理
	list_roles,
	get_role,
	create_role,
	update_role,
	delete_role,
)
# 导入系统模块的Pydantic模型
from modules.system.schemas import (
	SystemStatusResponse,
	SystemLogsRequest,
	SystemLogsResponse,
	SystemSettingsResponse,
	SystemSettingsUpdateRequest,
	ConnectionStatusResponse,
	SystemResourcesResponse,
	DatabaseStatusResponse,
	# 认证
	LoginRequest,
	RegisterRequest,
	RefreshTokenRequest,
	ChangePasswordRequest,
	AuthResponse,
	# 用户管理
	UserCreateRequest,
	UserUpdateRequest,
	UserListResponse,
	UserDetailResponse,
	UserStatisticsResponse,
	# 角色管理
	RoleCreateRequest,
	RoleUpdateRequest,
	RoleListResponse,
	RoleDetailResponse,
)
# 导入响应格式化工具
from utils.api_utils.response_formatter import success_response, error_response

# 配置日志
logger = logging.getLogger(__name__)

# 创建路由器实例
router = APIRouter(
	tags=["系统管理"],
	responses={
		401: {"description": "认证失败"},
		403: {"description": "权限不足"},
		500: {"description": "服务器内部错误"}
	}
)


# ==================== 系统状态接口 ====================

@router.get("/status", response_model=SystemStatusResponse)
async def get_system_status_api (
		current_user: Dict = Depends(get_current_user),
		db_session: AsyncSession = Depends(get_db_session)
) -> SystemStatusResponse:
	"""
	获取系统状态

	Args:
		current_user: 当前登录用户
		db_session: 数据库会话

	Returns:
		SystemStatusResponse: 系统状态响应
	"""
	try:
		logger.info(f"用户 {current_user.get('username')} 请求系统状态")

		result = await get_system_status(
			session=db_session,
			user_id=current_user.get("id")
		)

		return result

	except HTTPException:
		raise
	except Exception as e:
		logger.error(f"获取系统状态失败: {str(e)}", exc_info=True)
		raise HTTPException(
			status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
			detail=f"获取系统状态失败: {str(e)}"
		)


@router.get("/resources", response_model=SystemResourcesResponse)
async def get_system_resources_api (
		current_user: Dict = Depends(get_current_user),
		db_session: AsyncSession = Depends(get_db_session)
) -> SystemResourcesResponse:
	"""
	获取系统资源使用情况

	Args:
		current_user: 当前登录用户
		db_session: 数据库会话

	Returns:
		SystemResourcesResponse: 系统资源响应
	"""
	try:
		logger.info(f"用户 {current_user.get('username')} 请求系统资源")

		result = await get_system_resources(
			session=db_session,
			user_id=current_user.get("id")
		)

		return result

	except HTTPException:
		raise
	except Exception as e:
		logger.error(f"获取系统资源失败: {str(e)}", exc_info=True)
		raise HTTPException(
			status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
			detail=f"获取系统资源失败: {str(e)}"
		)


@router.get("/connections", response_model=ConnectionStatusResponse)
async def get_connections_api (
		current_user: Dict = Depends(get_current_user),
		db_session: AsyncSession = Depends(get_db_session)
) -> ConnectionStatusResponse:
	"""
	获取系统连接状态

	Args:
		current_user: 当前登录用户
		db_session: 数据库会话

	Returns:
		ConnectionStatusResponse: 连接状态响应
	"""
	try:
		logger.info(f"用户 {current_user.get('username')} 请求连接状态")

		result = await get_connection_status(
			session=db_session,
			user_id=current_user.get("id")
		)

		return result

	except HTTPException:
		raise
	except Exception as e:
		logger.error(f"获取连接状态失败: {str(e)}", exc_info=True)
		raise HTTPException(
			status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
			detail=f"获取连接状态失败: {str(e)}"
		)


@router.get("/database", response_model=DatabaseStatusResponse)
async def get_database_api (
		current_user: Dict = Depends(get_current_user),
		db_session: AsyncSession = Depends(get_db_session)
) -> DatabaseStatusResponse:
	"""
	获取数据库状态

	Args:
		current_user: 当前登录用户
		db_session: 数据库会话

	Returns:
		DatabaseStatusResponse: 数据库状态响应
	"""
	try:
		logger.info(f"用户 {current_user.get('username')} 请求数据库状态")

		result = await get_database_status(
			session=db_session,
			user_id=current_user.get("id")
		)

		return result

	except HTTPException:
		raise
	except Exception as e:
		logger.error(f"获取数据库状态失败: {str(e)}", exc_info=True)
		raise HTTPException(
			status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
			detail=f"获取数据库状态失败: {str(e)}"
		)


# ==================== 系统日志接口 ====================

@router.get("/logs", response_model=SystemLogsResponse)
async def get_system_logs_api (
		request: SystemLogsRequest = Depends(),
		current_user: Dict = Depends(get_current_user),
		db_session: AsyncSession = Depends(get_db_session)
) -> SystemLogsResponse:
	"""
	获取系统日志

	Args:
		request: 系统日志请求参数
		current_user: 当前登录用户
		db_session: 数据库会话

	Returns:
		SystemLogsResponse: 系统日志响应
	"""
	try:
		logger.info(f"用户 {current_user.get('username')} 请求系统日志")

		result = await get_system_logs(
			session=db_session,
			request=request,
			user_id=current_user.get("id")
		)

		return result

	except HTTPException:
		raise
	except Exception as e:
		logger.error(f"获取系统日志失败: {str(e)}", exc_info=True)
		raise HTTPException(
			status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
			detail=f"获取系统日志失败: {str(e)}"
		)


# ==================== 系统设置接口 ====================

@router.get("/settings", response_model=SystemSettingsResponse)
async def get_settings_api (
		current_user: Dict = Depends(get_current_user),
		db_session: AsyncSession = Depends(get_db_session)
) -> SystemSettingsResponse:
	"""
	获取系统设置

	Args:
		current_user: 当前登录用户
		db_session: 数据库会话

	Returns:
		SystemSettingsResponse: 系统设置响应
	"""
	try:
		logger.info(f"用户 {current_user.get('username')} 请求系统设置")

		result = await get_system_settings(
			session=db_session,
			user_id=current_user.get("id")
		)

		return result

	except HTTPException:
		raise
	except Exception as e:
		logger.error(f"获取系统设置失败: {str(e)}", exc_info=True)
		raise HTTPException(
			status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
			detail=f"获取系统设置失败: {str(e)}"
		)


@router.put("/settings", response_model=SystemSettingsResponse)
async def update_settings_api (
		request: SystemSettingsUpdateRequest,
		current_user: Dict = Depends(get_current_user),
		db_session: AsyncSession = Depends(get_db_session)
) -> SystemSettingsResponse:
	"""
	更新系统设置

	Args:
		request: 系统设置更新请求
		current_user: 当前登录用户
		db_session: 数据库会话

	Returns:
		SystemSettingsResponse: 更新后的系统设置响应
	"""
	try:
		logger.info(f"用户 {current_user.get('username')} 更新系统设置")

		# 检查用户是否为管理员角色
		if current_user.get("role") not in ("admin", "super_admin", "superadmin"):
			raise HTTPException(
				status_code=status.HTTP_403_FORBIDDEN,
				detail="只有管理员可以更新系统设置"
			)

		result = await update_system_settings(
			session=db_session,
			request=request,
			user_id=current_user.get("id")
		)

		return result

	except HTTPException:
		raise
	except Exception as e:
		logger.error(f"更新系统设置失败: {str(e)}", exc_info=True)
		raise HTTPException(
			status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
			detail=f"更新系统设置失败: {str(e)}"
		)


# ==================== 模块管理接口 ====================

@router.get("/health")
async def system_module_health_check (
		current_user: Dict = Depends(get_current_user),
		db_session: AsyncSession = Depends(get_db_session)
):
	"""
	系统模块健康检查

	Args:
		current_user: 当前登录用户
		db_session: 数据库会话

	Returns:
		JSONResponse: 健康状态
	"""
	try:
		logger.debug(f"用户 {current_user.get('username')} 请求系统模块健康检查")

		health_status = await check_system_module_health(
			session=db_session,
		)

		return success_response(
			data=health_status,
			message="系统模块健康检查完成"
		)

	except Exception as e:
		logger.error(f"系统模块健康检查失败: {str(e)}", exc_info=True)
		return error_response(
			message="系统模块健康检查失败",
			data={
				"status": "unhealthy",
				"error": str(e)
			},
			status_code=500
		)


# ==================== 认证接口 ====================


@router.post("/auth/login", response_model=AuthResponse)
async def login_api (
		request: LoginRequest,
		db_session: AsyncSession = Depends(get_db_session),
):
	"""用户登录，返回 access_token + refresh_token

	无需认证，使用用户名和密码换取 token 对。
	"""
	try:
		ip = getattr(request, "_ip", "")
		logger.info(f"用户 {request.username} 从 {ip} 登录")
		result = await login(
			session=db_session,
			username=request.username,
			password=request.password,
		)
		return result
	except ValueError as e:
		raise HTTPException(status_code=401, detail=str(e))
	except Exception as e:
		logger.error(f"登录失败: {str(e)}", exc_info=True)
		raise HTTPException(status_code=500, detail=f"登录失败: {str(e)}")


@router.post("/auth/register", response_model=AuthResponse)
async def register_api (
		request: RegisterRequest,
		db_session: AsyncSession = Depends(get_db_session),
):
	"""用户注册"""
	try:
		result = await register_user(
			session=db_session,
			username=request.username,
			password=request.password,
			email=request.email,
			phone=request.phone,
			real_name=request.real_name,
		)
		return result
	except ValueError as e:
		raise HTTPException(status_code=400, detail=str(e))
	except Exception as e:
		logger.error(f"注册失败: {str(e)}", exc_info=True)
		raise HTTPException(status_code=500, detail=f"注册失败: {str(e)}")


@router.post("/auth/refresh", response_model=AuthResponse)
async def refresh_token_api (
		request: RefreshTokenRequest,
		db_session: AsyncSession = Depends(get_db_session),
):
	"""刷新 token 对"""
	try:
		result = await refresh_token(
			session=db_session,
			token=request.refresh_token,
		)
		return result
	except ValueError as e:
		raise HTTPException(status_code=400, detail=str(e))
	except Exception as e:
		logger.error(f"刷新 token 失败: {str(e)}", exc_info=True)
		raise HTTPException(status_code=500, detail=f"刷新 token 失败: {str(e)}")


@router.post("/auth/change-password", response_model=AuthResponse)
async def change_password_api (
		request: ChangePasswordRequest,
		current_user: Dict = Depends(get_current_user),
		db_session: AsyncSession = Depends(get_db_session),
):
	"""修改密码（需登录）"""
	try:
		result = await change_password(
			session=db_session,
			user_id=current_user.get("id"),
			old_password=request.old_password,
			new_password=request.new_password,
		)
		return result
	except ValueError as e:
		raise HTTPException(status_code=400, detail=str(e))
	except Exception as e:
		logger.error(f"修改密码失败: {str(e)}", exc_info=True)
		raise HTTPException(status_code=500, detail=f"修改密码失败: {str(e)}")


# ==================== 用户管理接口 ====================


def _require_admin (current_user: Dict):
	"""检查管理员权限，无权限抛出 403"""
	if current_user.get("role") not in ("admin", "super_admin", "superadmin"):
		raise HTTPException(status_code=403, detail="只有管理员可执行此操作")


@router.get("/users", response_model=UserListResponse)
async def list_users_api (
		skip: int = 0,
		limit: int = 100,
		keyword: str = "",
		role: str = "",
		current_user: Dict = Depends(get_current_user),
		db_session: AsyncSession = Depends(get_db_session),
):
	"""获取用户列表（分页）"""
	try:
		_require_admin(current_user)
		result = await list_users(
			session=db_session, skip=skip, limit=limit,
			keyword=keyword, role=role,
		)
		return result
	except HTTPException:
		raise
	except Exception as e:
		logger.error(f"获取用户列表失败: {str(e)}", exc_info=True)
		raise HTTPException(status_code=500, detail=f"获取用户列表失败: {str(e)}")


@router.get("/users/statistics", response_model=UserStatisticsResponse)
async def user_statistics_api (
		current_user: Dict = Depends(get_current_user),
		db_session: AsyncSession = Depends(get_db_session),
):
	"""获取用户统计"""
	try:
		_require_admin(current_user)
		result = await get_user_statistics(session=db_session)
		return result
	except HTTPException:
		raise
	except Exception as e:
		logger.error(f"获取用户统计失败: {str(e)}", exc_info=True)
		raise HTTPException(status_code=500, detail=f"获取用户统计失败: {str(e)}")


@router.get("/users/{user_id}", response_model=UserDetailResponse)
async def get_user_api (
		user_id: str,
		current_user: Dict = Depends(get_current_user),
		db_session: AsyncSession = Depends(get_db_session),
):
	"""获取用户详情"""
	try:
		_require_admin(current_user)
		result = await get_user(session=db_session, user_id=user_id)
		return result
	except ValueError as e:
		raise HTTPException(status_code=404, detail=str(e))
	except HTTPException:
		raise
	except Exception as e:
		logger.error(f"获取用户详情失败: {str(e)}", exc_info=True)
		raise HTTPException(status_code=500, detail=f"获取用户详情失败: {str(e)}")


@router.post("/users", response_model=UserDetailResponse, status_code=201)
async def create_user_api (
		request: UserCreateRequest,
		current_user: Dict = Depends(get_current_user),
		db_session: AsyncSession = Depends(get_db_session),
):
	"""创建用户（管理员操作）"""
	try:
		_require_admin(current_user)
		data = request.model_dump(exclude_unset=True)
		result = await create_user(
			session=db_session, data=data,
			operator_id=current_user.get("id", ""),
		)
		return result
	except ValueError as e:
		raise HTTPException(status_code=400, detail=str(e))
	except HTTPException:
		raise
	except Exception as e:
		logger.error(f"创建用户失败: {str(e)}", exc_info=True)
		raise HTTPException(status_code=500, detail=f"创建用户失败: {str(e)}")


@router.put("/users/{user_id}", response_model=UserDetailResponse)
async def update_user_api (
		user_id: str,
		request: UserUpdateRequest,
		current_user: Dict = Depends(get_current_user),
		db_session: AsyncSession = Depends(get_db_session),
):
	"""更新用户"""
	try:
		_require_admin(current_user)
		data = {k: v for k, v in request.model_dump().items() if v is not None}
		result = await update_user(
			session=db_session, user_id=user_id, data=data,
			operator_id=current_user.get("id", ""),
		)
		return result
	except ValueError as e:
		raise HTTPException(status_code=404, detail=str(e))
	except HTTPException:
		raise
	except Exception as e:
		logger.error(f"更新用户失败: {str(e)}", exc_info=True)
		raise HTTPException(status_code=500, detail=f"更新用户失败: {str(e)}")


@router.delete("/users/{user_id}", response_model=AuthResponse)
async def delete_user_api (
		user_id: str,
		current_user: Dict = Depends(get_current_user),
		db_session: AsyncSession = Depends(get_db_session),
):
	"""删除用户"""
	try:
		_require_admin(current_user)
		result = await delete_user(
			session=db_session, user_id=user_id,
			operator_id=current_user.get("id", ""),
		)
		return result
	except ValueError as e:
		raise HTTPException(status_code=404, detail=str(e))
	except HTTPException:
		raise
	except Exception as e:
		logger.error(f"删除用户失败: {str(e)}", exc_info=True)
		raise HTTPException(status_code=500, detail=f"删除用户失败: {str(e)}")


# ==================== 角色管理接口 ====================


@router.get("/roles", response_model=RoleListResponse)
async def list_roles_api (
		current_user: Dict = Depends(get_current_user),
		db_session: AsyncSession = Depends(get_db_session),
):
	"""获取角色列表"""
	try:
		_require_admin(current_user)
		result = await list_roles(session=db_session)
		return result
	except HTTPException:
		raise
	except Exception as e:
		logger.error(f"获取角色列表失败: {str(e)}", exc_info=True)
		raise HTTPException(status_code=500, detail=f"获取角色列表失败: {str(e)}")


@router.get("/roles/{role_id}", response_model=RoleDetailResponse)
async def get_role_api (
		role_id: str,
		current_user: Dict = Depends(get_current_user),
		db_session: AsyncSession = Depends(get_db_session),
):
	"""获取角色详情"""
	try:
		_require_admin(current_user)
		result = await get_role(session=db_session, role_id=role_id)
		return result
	except ValueError as e:
		raise HTTPException(status_code=404, detail=str(e))
	except HTTPException:
		raise
	except Exception as e:
		logger.error(f"获取角色详情失败: {str(e)}", exc_info=True)
		raise HTTPException(status_code=500, detail=f"获取角色详情失败: {str(e)}")


@router.post("/roles", response_model=RoleDetailResponse, status_code=201)
async def create_role_api (
		request: RoleCreateRequest,
		current_user: Dict = Depends(get_current_user),
		db_session: AsyncSession = Depends(get_db_session),
):
	"""创建角色"""
	try:
		_require_admin(current_user)
		result = await create_role(
			session=db_session,
			data=request.model_dump(),
		)
		return result
	except ValueError as e:
		raise HTTPException(status_code=400, detail=str(e))
	except HTTPException:
		raise
	except Exception as e:
		logger.error(f"创建角色失败: {str(e)}", exc_info=True)
		raise HTTPException(status_code=500, detail=f"创建角色失败: {str(e)}")


@router.put("/roles/{role_id}", response_model=RoleDetailResponse)
async def update_role_api (
		role_id: str,
		request: RoleUpdateRequest,
		current_user: Dict = Depends(get_current_user),
		db_session: AsyncSession = Depends(get_db_session),
):
	"""更新角色"""
	try:
		_require_admin(current_user)
		data = {k: v for k, v in request.model_dump().items() if v is not None}
		result = await update_role(session=db_session, role_id=role_id, data=data)
		return result
	except ValueError as e:
		raise HTTPException(status_code=404, detail=str(e))
	except HTTPException:
		raise
	except Exception as e:
		logger.error(f"更新角色失败: {str(e)}", exc_info=True)
		raise HTTPException(status_code=500, detail=f"更新角色失败: {str(e)}")


@router.delete("/roles/{role_id}", response_model=AuthResponse)
async def delete_role_api (
		role_id: str,
		current_user: Dict = Depends(get_current_user),
		db_session: AsyncSession = Depends(get_db_session),
):
	"""删除角色"""
	try:
		_require_admin(current_user)
		result = await delete_role(session=db_session, role_id=role_id)
		return result
	except ValueError as e:
		raise HTTPException(status_code=404, detail=str(e))
	except HTTPException:
		raise
	except Exception as e:
		logger.error(f"删除角色失败: {str(e)}", exc_info=True)
		raise HTTPException(status_code=500, detail=f"删除角色失败: {str(e)}")
