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
                    "cpu_percent": cpu_percent,
                    "cpu_cores": cpu_count,
                    "memory_percent": mem.percent,
                    "memory_used": mem.used,
                    "memory_total": mem.total,
                    "disk_usage": disk.percent,
                    "disk_total": disk.total,
                    "disk_used": disk.used,
                    "timestamp": datetime.now(timezone.utc).isoformat(),
                },
            }
        except ImportError:
            return {
                "success": True,
                "data": {
                    "cpu_percent": 0,
                    "cpu_cores": 0,
                    "memory_percent": 0,
                    "memory_used": 0,
                    "memory_total": 0,
                    "disk_usage": 0,
                    "disk_total": 0,
                    "disk_used": 0,
                    "note": "psutil 未安装",
                },
            }

    # ==================== 连接状态 ====================

    async def get_connection_status(self, _user_id: str) -> Dict[str, Any]:
        """获取外部连接状态（扁平输出，匹配前端 ConnectionStatus 接口）"""
        connections = {
            "database": False,
            "redis": False,
            "tushare": False,
            "broker": False,
        }

        # 数据库
        try:
            start = datetime.now()
            await self.db.execute(text("SELECT 1"))
            latency = (datetime.now() - start).total_seconds() * 1000
            connections["database"] = True
            connections["database_latency_ms"] = round(latency, 1)
        except Exception:
            connections["database"] = False

        # Redis
        try:
            from shared.cache.cache_manager import get_cache_manager
            cache_mgr = get_cache_manager()
            health = await cache_mgr.health_check()
            connections["redis"] = health.get("redis", False)
        except Exception:
            connections["redis"] = False

        # Tushare（检查所有可能的 token 环境变量）
        try:
            import os
            token = (
                os.getenv("DEV_TUSHARE_TOKEN", "")
                or os.getenv("PROD_TUSHARE_TOKEN", "")
            )
            enabled = os.getenv("PROD_TUSHARE_ENABLED", "true").lower() == "true"
            connections["tushare"] = bool(token) and enabled
        except Exception:
            connections["tushare"] = False

        # 交易网关（模拟模式默认 True）
        try:
            import os
            simulated = os.getenv("SIMULATED_TRADING", "true").lower() == "true"
            connections["broker"] = True  # 模拟模式始终可用
            connections["broker_mode"] = "simulated" if simulated else "live"
        except Exception:
            connections["broker"] = False

        connections["last_check"] = datetime.now(timezone.utc).isoformat()

        return {"success": True, "data": connections}

    # ==================== 数据库状态 ====================

    async def get_database_status(self, _user_id: str) -> Dict[str, Any]:
        """获取数据库状态统计（匹配前端 DatabaseStatus 接口）"""
        try:
            # 数据库大小
            db_size = "未知"
            try:
                size_result = await self.db.execute(
                    text("SELECT pg_size_pretty(pg_database_size(current_database()))")
                )
                db_size = size_result.scalar() or "未知"
            except Exception:
                pass

            # 活跃连接数
            active_conns = 0
            try:
                conn_result = await self.db.execute(
                    text("SELECT count(*) FROM pg_stat_activity WHERE state = 'active'")
                )
                active_conns = conn_result.scalar() or 0
            except Exception:
                pass

            # 版本
            version = "未知"
            try:
                ver_result = await self.db.execute(text("SELECT version()"))
                version = ver_result.scalar() or "未知"
            except Exception:
                pass

            # 总表数
            total_tables = 0
            try:
                tables_result = await self.db.execute(
                    text("SELECT count(*) FROM information_schema.tables WHERE table_schema = 'public'")
                )
                total_tables = tables_result.scalar() or 0
            except Exception:
                pass

            # 股票数据记录数
            stock_data_count = 0
            try:
                stocks_result = await self.db.execute(
                    text("SELECT count(*) FROM stock_basic")
                )
                stock_data_count = stocks_result.scalar() or 0
            except Exception:
                pass

            return {
                "success": True,
                "data": {
                    "type": "PostgreSQL",
                    "version": version,
                    "size": db_size,
                    "active_connections": active_conns,
                    "total_tables": total_tables,
                    "stock_data_count": stock_data_count,
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
        """获取所有系统配置（嵌套结构，匹配前端 SystemSettings 接口）"""
        configs = await self.config_service.get_all_configs()
        flat = {c["config_key"]: c["config_value"] for c in configs}

        # 将扁平配置组织为嵌套结构（与前端 SystemSettings 接口对齐）
        settings = {
            "data_sync": {
                "auto_sync": flat.get("data_sync_auto", True),
                "sync_interval_minutes": flat.get("data_sync_interval", 30),
                "data_sources": flat.get("data_sources", ["tushare", "baostock"]),
            },
            "trading": {
                "commission_rate": float(flat.get("commission_rate", 0.0003)),
                "stamp_tax": float(flat.get("stamp_tax", 0.001)),
                "min_commission": float(flat.get("min_commission", 5.0)),
                "slippage": float(flat.get("slippage", 0.001)),
            },
            "risk": {
                "max_position_ratio": float(flat.get("max_position_ratio", 0.3)),
                "max_daily_loss": float(flat.get("max_daily_loss", 0.05)),
                "max_drawdown": float(flat.get("max_drawdown", 0.2)),
                "enable_auto_stop": flat.get("enable_auto_stop", True),
                "filter_st": flat.get("filter_st", True),
            },
            "notification": {
                "dingtalk_enabled": flat.get("dingtalk_enabled", False),
                "wechat_enabled": flat.get("wechat_enabled", False),
                "email_enabled": flat.get("email_enabled", False),
                "risk_alert_enabled": flat.get("risk_alert_enabled", True),
            },
        }
        return {"success": True, "data": settings}

    async def update_system_settings(self, request, user_id: str) -> Dict[str, Any]:
        """更新系统配置（兼容旧格式 {settings: {...}} 和新格式直接传嵌套结构）"""
        if hasattr(request, 'settings') and request.settings is not None:
            # 旧格式：{"settings": {...}}
            settings_dict = request.settings
        elif hasattr(request, 'settings') and request.settings is None:
            # 新格式：直接传 {"security": {...}, "notification": {...}, ...}
            dumped = request.model_dump(exclude_none=True)
            dumped.pop("settings", None)
            settings_dict = dumped
        else:
            settings_dict = request.model_dump().get("settings", request.model_dump())
        results = await self.config_service.update_settings(settings_dict, updated_by=user_id)
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

    def __init__(self, db: AsyncSession, event_engine=None):
        from modules.system.services.auth_service import AuthService
        self._service = AuthService(db, event_engine=event_engine)

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

    async def logout(self, token: str, user_id: str) -> Dict[str, Any]:
        """登出 —— 将 token 加入黑名单"""
        from ..auth.jwt_handler import blacklist_token
        try:
            blacklist_token(token)
            logger.info(f"用户 {user_id} 登出成功，token 已加入黑名单")
        except Exception as e:
            logger.warning(f"Token 黑名单操作异常: {e}")
        return {"success": True, "message": "登出成功"}

    async def validate_token(
        self, token: str, current_user: Dict[str, Any],
    ) -> Dict[str, Any]:
        """验证 token 有效性"""
        from ..auth.jwt_handler import is_token_blacklisted
        is_blacklisted = is_token_blacklisted(token)
        return {
            "isValid": not is_blacklisted,
            "user": {
                "id": current_user.get("id"),
                "username": current_user.get("username"),
                "role": current_user.get("role"),
            } if not is_blacklisted and current_user else None,
        }

    async def token_info(self, token: str) -> Dict[str, Any]:
        """获取 token 元信息"""
        from shared.security.jwt_handler import get_jwt_manager
        jwt_mgr = get_jwt_manager()
        try:
            payload = jwt_mgr.decode_token_without_verification(token)
            return {
                "expiresAt": payload.get("exp"),
                "issuedAt": payload.get("iat"),
                "tokenType": payload.get("type", "access"),
                "userId": payload.get("sub"),
            }
        except Exception as e:
            raise ValueError(f"无效的 token: {e}")

    async def request_password_reset(self, email: str) -> Dict[str, Any]:
        """请求密码重置"""
        from shared.database.repositories.system.auth.user_repo import UserRepository
        user_repo = UserRepository(self._service._session)
        user = await user_repo.get_user_by_email(email)
        if not user:
            return {"success": True, "message": "如果该邮箱已注册，重置链接已发送"}
        logger.warning("密码重置邮件功能需要配置 SMTP 服务，暂时仅记录请求: %s", email)
        return {"success": True, "message": "如果该邮箱已注册，重置链接已发送"}

    async def confirm_password_reset(self, token: str, new_password: str) -> Dict[str, Any]:
        """确认密码重置（待 SMTP 配置后启用）"""
        raise NotImplementedError("密码重置功能待 SMTP 配置后启用")

    async def verify_email(self, token: str) -> Dict[str, Any]:
        """验证邮箱（待 SMTP 配置后启用）"""
        raise NotImplementedError("邮箱验证功能待 SMTP 配置后启用")

    async def resend_verification(self, email: str) -> Dict[str, Any]:
        """重新发送验证邮件（待 SMTP 配置后启用）"""
        raise NotImplementedError("邮箱验证功能待 SMTP 配置后启用")

    async def cleanup_tokens(self) -> Dict[str, Any]:
        """清理过期黑名单 token"""
        from ..auth.jwt_handler import clear_expired_blacklist
        cleared = clear_expired_blacklist()
        return {"success": True, "message": f"已清理 {cleared} 个过期黑名单条目"}


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


async def logout(session: AsyncSession, token: str, user_id: str):
    handler = AuthHandler(session)
    return await handler.logout(token, user_id)


async def validate_token(session: AsyncSession, token: str,
                         current_user: Dict[str, Any]):
    handler = AuthHandler(session)
    return await handler.validate_token(token, current_user)


async def get_token_info(session: AsyncSession, token: str):
    handler = AuthHandler(session)
    return await handler.token_info(token)


async def request_password_reset(session: AsyncSession, email: str):
    handler = AuthHandler(session)
    return await handler.request_password_reset(email)


async def confirm_password_reset(session: AsyncSession, token: str,
                                 new_password: str):
    handler = AuthHandler(session)
    return await handler.confirm_password_reset(token, new_password)


async def verify_email(session: AsyncSession, token: str):
    handler = AuthHandler(session)
    return await handler.verify_email(token)


async def resend_verification(session: AsyncSession, email: str):
    handler = AuthHandler(session)
    return await handler.resend_verification(email)


async def cleanup_expired_tokens(session: AsyncSession):
    handler = AuthHandler(session)
    return await handler.cleanup_tokens()


async def clear_system_cache(session: AsyncSession) -> Dict[str, Any]:
    """清理系统缓存（配置缓存 + 权限缓存）"""
    try:
        from modules.system.managers.config_manager import get_config_manager
        config_mgr = get_config_manager()
        if config_mgr and hasattr(config_mgr, '_cache'):
            config_mgr._cache.clear()
        return {"cleared": True, "message": "系统缓存已清理"}
    except Exception as e:
        logger.error(f"清理缓存失败: {e}")
        return {"cleared": False, "message": str(e)}


async def restart_system_service(session: AsyncSession,
                                 service: str) -> Dict[str, Any]:
    """重启指定系统服务"""
    restartable = ["data_sync", "strategy_manager", "monitor"]
    if service not in restartable:
        raise ValueError(f"不支持重启的服务: {service}。支持的服务: {restartable}")
    try:
        logger.info(f"请求重启服务: {service}")
        return {"success": True, "message": f"服务 {service} 已发送重启指令"}
    except Exception as e:
        raise RuntimeError(f"重启服务 {service} 失败: {e}")


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
