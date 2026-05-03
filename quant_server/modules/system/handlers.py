# -*- coding: utf-8 -*-
"""
系统模块 API 处理函数

SystemHandler 集中管理系统模块的 Service/Repository，作为 API 路由层适配器。
check_system_module_health 保持独立函数（不依赖任何 Service）。
"""

import asyncio
from datetime import datetime, timezone
from typing import Dict, Any

from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from shared.cache.cache_manager import get_cache_manager
from shared.database.repositories.system.auth.user_repo import UserRepository
from modules.system.services.config_service import ConfigService
from modules.system.services.log_service import LogService


class SystemHandler:
    """系统模块处理器"""

    def __init__(self, db: AsyncSession):
        self.db = db
        self.user_repo = UserRepository(db)
        self.config_service = ConfigService(db)
        self.log_service = LogService(db)

    # ==================== 系统状态 ====================

    async def get_system_status(self, _user_id: str) -> Dict[str, Any]:
        """获取系统整体状态概览"""
        try:
            total_users = await self.user_repo.count_users(active_only=False)
            active_users = await self.user_repo.count_users(active_only=True)

            # 数据库连接检查
            db_ok = True
            db_error = None
            try:
                await self.db.execute(text("SELECT 1"))
            except Exception as e:
                db_ok = False
                db_error = str(e)

            # 检查缓存（Redis）连接
            try:
                cache_mgr = get_cache_manager()
                health = await cache_mgr.health_check()
                redis_ok = health.get("redis", False) if health else False
            except (OSError, asyncio.TimeoutError):
                redis_ok = False

            return {
                "success": True,
                "data": {
                    "status": "running" if db_ok else "degraded",
                    "version": "1.0.0",
                    "uptime": self._get_uptime(),
                    "users": {"total": total_users, "active": active_users},
                    "services": {
                        "database": {"connected": db_ok, "error": db_error},
                        "redis": {"connected": redis_ok},
                    },
                    "timestamp": datetime.now(timezone.utc).isoformat(),
                },
            }
        except Exception as e:
            return {"success": False, "data": {"status": "error", "error": str(e)}}

    # ==================== 系统资源 ====================

    @staticmethod
    async def get_system_resources(_user_id: str) -> Dict[str, Any]:
        """获取系统资源使用情况（CPU/内存/磁盘）"""
        try:
            import psutil
            cpu_percent = psutil.cpu_percent(interval=0.5)
            cpu_count = psutil.cpu_count()
            mem = psutil.virtual_memory()
            disk = psutil.disk_usage("/")
            return {
                "success": True,
                "data": {
                    "cpu": {
                        "percent": cpu_percent,
                        "cores": cpu_count,
                    },
                    "memory": {
                        "total_gb": round(mem.total / (1024**3), 1),
                        "used_gb": round(mem.used / (1024**3), 1),
                        "percent": mem.percent,
                    },
                    "disk": {
                        "total_gb": round(disk.total / (1024**3), 1),
                        "used_gb": round(disk.used / (1024**3), 1),
                        "percent": disk.percent,
                    },
                    "timestamp": datetime.now(timezone.utc).isoformat(),
                },
            }
        except ImportError:
            return {
                "success": True,
                "data": {
                    "cpu": {"percent": 0, "cores": 0, "note": "psutil 未安装"},
                    "memory": {"total_gb": 0, "used_gb": 0, "percent": 0, "note": "psutil 未安装"},
                    "disk": {"total_gb": 0, "used_gb": 0, "percent": 0, "note": "psutil 未安装"},
                },
            }

    # ==================== 连接状态 ====================

    async def get_connection_status(self, _user_id: str) -> Dict[str, Any]:
        """获取外部连接状态"""
        connections = {}

        # 数据库
        try:
            start = datetime.now()
            await self.db.execute(text("SELECT 1"))
            latency = (datetime.now() - start).total_seconds() * 1000
            connections["database"] = {"connected": True, "latency_ms": round(latency, 1)}
        except Exception as e:
            connections["database"] = {"connected": False, "error": str(e)}

        # Redis
        try:
            from shared.cache.cache_manager import get_cache_manager
            cache_mgr = get_cache_manager()
            health = await cache_mgr.health_check()
            connections["redis"] = {"connected": health.get("redis", False)}
        except Exception as e:
            connections["redis"] = {"connected": False, "error": str(e)}

        return {"success": True, "data": connections}

    # ==================== 数据库状态 ====================

    async def get_database_status(self, _user_id: str) -> Dict[str, Any]:
        """获取数据库状态统计"""
        try:
            # 数据库大小
            db_size = "未知"
            try:
                size_result = await self.db.execute(
                    text("SELECT pg_size_pretty(pg_database_size(current_database()))")
                )
                db_size = size_result.scalar() or "未知"
            except (OSError, asyncio.TimeoutError):
                pass

            # 活跃连接数
            active_conns = 0
            try:
                conn_result = await self.db.execute(
                    text("SELECT count(*) FROM pg_stat_activity WHERE state = 'active'")
                )
                active_conns = conn_result.scalar() or 0
            except (OSError, asyncio.TimeoutError):
                pass

            # 版本
            version = "未知"
            try:
                ver_result = await self.db.execute(text("SELECT version()"))
                version = ver_result.scalar() or "未知"
            except (OSError, asyncio.TimeoutError):
                pass

            return {
                "success": True,
                "data": {
                    "type": "PostgreSQL",
                    "version": version,
                    "size": db_size,
                    "active_connections": active_conns,
                    "timestamp": datetime.now(timezone.utc).isoformat(),
                },
            }
        except Exception as e:
            return {"success": False, "data": {"error": str(e)}}

    # ==================== 系统日志 ====================

    async def get_system_logs(self, request, user_id: str) -> Dict[str, Any]:
        """获取系统日志（分页）"""
        log_level = getattr(request, 'log_level', None)
        module = getattr(request, 'module', None)
        start_date = getattr(request, 'start_date', None)
        end_date = getattr(request, 'end_date', None)
        page = getattr(request, 'page', 1)
        page_size = getattr(request, 'page_size', 20)

        return await self.log_service.query_logs(
            log_level=log_level,
            module=module,
            user_id=user_id,
            start_date=start_date,
            end_date=end_date,
            page=page,
            page_size=page_size,
        )

    # ==================== 系统设置 ====================

    async def get_system_settings(self, _user_id: str) -> Dict[str, Any]:
        """获取所有系统配置"""
        configs = await self.config_service.get_all_configs()
        settings = {c["config_key"]: c["config_value"] for c in configs}
        return {"success": True, "data": settings}

    async def update_system_settings(self, request, user_id: str) -> Dict[str, Any]:
        """更新系统配置"""
        settings = request.settings if hasattr(request, 'settings') else (request.model_dump().get("settings", {}))
        results = await self.config_service.update_settings(settings, updated_by=user_id)
        return {"success": True, "data": {"updated": len(results)}}

    # ==================== 工具方法 ====================

    @staticmethod
    def _get_uptime() -> str:
        try:
            import psutil
            boot = datetime.fromtimestamp(psutil.boot_time())
            delta = datetime.now() - boot
            days = delta.days
            hours, rem = divmod(delta.seconds, 3600)
            mins, _ = divmod(rem, 60)
            return f"{days}d {hours}h {mins}m"
        except OSError:
            return "未知"


# 模块层适配器函数（供 router 直接调用）


async def get_system_status(session: AsyncSession, user_id: str):
    handler = SystemHandler(session)
    return await handler.get_system_status(user_id)


async def get_system_logs(session: AsyncSession, request, user_id: str):
    handler = SystemHandler(session)
    return await handler.get_system_logs(request, user_id)


async def get_system_settings(session: AsyncSession, user_id: str):
    handler = SystemHandler(session)
    return await handler.get_system_settings(user_id)


async def update_system_settings(session: AsyncSession, request, user_id: str):
    handler = SystemHandler(session)
    return await handler.update_system_settings(request, user_id)


async def get_connection_status(session: AsyncSession, user_id: str):
    handler = SystemHandler(session)
    return await handler.get_connection_status(user_id)


async def get_system_resources(session: AsyncSession, user_id: str):
    handler = SystemHandler(session)
    return await handler.get_system_resources(user_id)


async def get_database_status(session: AsyncSession, user_id: str):
    handler = SystemHandler(session)
    return await handler.get_database_status(user_id)


async def check_system_module_health(session: AsyncSession) -> Dict[str, Any]:
    """检查系统模块健康状态"""
    try:
        from sqlalchemy import text
        await session.execute(text("SELECT 1"))
        return {
            "status": "healthy",
            "module": "system",
            "timestamp": datetime.now(timezone.utc).isoformat(),
        }
    except Exception as e:
        return {
            "status": "unhealthy",
            "module": "system",
            "error": str(e),
            "timestamp": datetime.now(timezone.utc).isoformat(),
        }


# ==================== 认证处理器 ====================


class AuthHandler:
    """认证处理器 — 登录/注册/Token 刷新/密码修改"""

    def __init__(self, db: AsyncSession):
        from modules.system.services.auth_service import AuthService
        self._service = AuthService(db)

    async def login(
        self, username: str, password: str,
        ip_address: str = "", user_agent: str = "",
    ) -> Dict[str, Any]:
        result = await self._service.login(username, password, ip_address, user_agent)
        if result is None:
            raise ValueError("用户名或密码错误")
        return {"success": True, "data": result}

    async def register(
        self, username: str, password: str,
        email: str = "", phone: str = "", real_name: str = "",
        ip_address: str = "", user_agent: str = "",
    ) -> Dict[str, Any]:
        user = await self._service.register(
            username, password, email, phone, real_name, ip_address, user_agent,
        )
        return {"success": True, "data": user}

    async def refresh_token(self, token: str) -> Dict[str, Any]:
        tokens = await self._service.refresh_token(token)
        return {"success": True, "data": tokens}

    async def change_password(
        self, user_id: str, old_password: str, new_password: str,
    ) -> Dict[str, Any]:
        ok = await self._service.change_password(user_id, old_password, new_password)
        if not ok:
            raise ValueError("旧密码错误或用户不存在")
        return {"success": True, "message": "密码修改成功"}


async def login(session: AsyncSession, username: str, password: str,
                ip_address: str = "", user_agent: str = ""):
    handler = AuthHandler(session)
    return await handler.login(username, password, ip_address, user_agent)


async def register_user(session: AsyncSession, username: str, password: str,
                        email: str = "", phone: str = "", real_name: str = "",
                        ip_address: str = "", user_agent: str = ""):
    handler = AuthHandler(session)
    return await handler.register(username, password, email, phone, real_name,
                                  ip_address, user_agent)


async def refresh_token(session: AsyncSession, token: str):
    handler = AuthHandler(session)
    return await handler.refresh_token(token)


async def change_password(session: AsyncSession, user_id: str,
                          old_password: str, new_password: str):
    handler = AuthHandler(session)
    return await handler.change_password(user_id, old_password, new_password)


# ==================== 用户管理处理器 ====================


class UserHandler:
    """用户管理处理器"""

    def __init__(self, db: AsyncSession):
        from modules.system.services.user_service import UserService
        self._service = UserService(db)

    async def list_users(
        self, skip: int = 0, limit: int = 100,
        keyword: str = "", role: str = "",
    ) -> Dict[str, Any]:
        result = await self._service.list_users(
            skip=skip, limit=limit, keyword=keyword, role=role,
        )
        return {"success": True, "data": result}

    async def get_user(self, user_id: str) -> Dict[str, Any]:
        user = await self._service.get_user(user_id)
        if user is None:
            raise ValueError(f"用户不存在: {user_id}")
        return {"success": True, "data": user}

    async def create_user(self, data: dict, operator_id: str = "") -> Dict[str, Any]:
        user = await self._service.create_user(data, operator_id)
        return {"success": True, "data": user}

    async def update_user(self, user_id: str, data: dict,
                          operator_id: str = "") -> Dict[str, Any]:
        user = await self._service.update_user(user_id, data, operator_id)
        if user is None:
            raise ValueError(f"用户不存在: {user_id}")
        return {"success": True, "data": user}

    async def delete_user(self, user_id: str, operator_id: str = "") -> Dict[str, Any]:
        ok = await self._service.delete_user(user_id, operator_id)
        if not ok:
            raise ValueError(f"用户不存在: {user_id}")
        return {"success": True, "message": "用户已删除"}

    async def get_statistics(self) -> Dict[str, Any]:
        stats = await self._service.get_statistics()
        return {"success": True, "data": stats}


async def list_users(session: AsyncSession, skip: int = 0, limit: int = 100,
                     keyword: str = "", role: str = ""):
    handler = UserHandler(session)
    return await handler.list_users(skip=skip, limit=limit,
                                    keyword=keyword, role=role)


async def get_user(session: AsyncSession, user_id: str):
    handler = UserHandler(session)
    return await handler.get_user(user_id)


async def create_user(session: AsyncSession, data: dict, operator_id: str = ""):
    handler = UserHandler(session)
    return await handler.create_user(data, operator_id)


async def update_user(session: AsyncSession, user_id: str, data: dict,
                      operator_id: str = ""):
    handler = UserHandler(session)
    return await handler.update_user(user_id, data, operator_id)


async def delete_user(session: AsyncSession, user_id: str, operator_id: str = ""):
    handler = UserHandler(session)
    return await handler.delete_user(user_id, operator_id)


async def get_user_statistics(session: AsyncSession):
    handler = UserHandler(session)
    return await handler.get_statistics()


# ==================== 角色管理处理器 ====================


class RoleHandler:
    """角色管理处理器"""

    def __init__(self, db: AsyncSession):
        from modules.system.services.role_service import RoleService
        self._service = RoleService(db)

    async def list_roles(self) -> Dict[str, Any]:
        roles = await self._service.list_roles()
        return {"success": True, "data": roles}

    async def get_role(self, role_id: str) -> Dict[str, Any]:
        role = await self._service.get_role(role_id)
        if role is None:
            raise ValueError(f"角色不存在: {role_id}")
        return {"success": True, "data": role}

    async def create_role(self, data: dict) -> Dict[str, Any]:
        role = await self._service.create_role(data)
        return {"success": True, "data": role}

    async def update_role(self, role_id: str, data: dict) -> Dict[str, Any]:
        role = await self._service.update_role(role_id, data)
        if role is None:
            raise ValueError(f"角色不存在: {role_id}")
        return {"success": True, "data": role}

    async def delete_role(self, role_id: str) -> Dict[str, Any]:
        ok = await self._service.delete_role(role_id)
        if not ok:
            raise ValueError(f"角色不存在: {role_id}")
        return {"success": True, "message": "角色已删除"}


async def list_roles(session: AsyncSession):
    handler = RoleHandler(session)
    return await handler.list_roles()


async def get_role(session: AsyncSession, role_id: str):
    handler = RoleHandler(session)
    return await handler.get_role(role_id)


async def create_role(session: AsyncSession, data: dict):
    handler = RoleHandler(session)
    return await handler.create_role(data)


async def update_role(session: AsyncSession, role_id: str, data: dict):
    handler = RoleHandler(session)
    return await handler.update_role(role_id, data)


async def delete_role(session: AsyncSession, role_id: str):
    handler = RoleHandler(session)
    return await handler.delete_role(role_id)
