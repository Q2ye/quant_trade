# sys_user_service.py
from typing import List, Optional, Dict, Any
from datetime import datetime

from sqlalchemy import func
from ..services.base_service import BaseService
from quant_server.db.models.business_models import SysUser, SysPermission


class SysUserService(BaseService):
    """系统用户信息服务"""

    def create(self, data: Dict[str, Any]) -> SysUser:
        """创建新用户记录"""
        with self.session_scope() as session:
            # 检查是否已存在
            existing = session.query(SysUser).filter_by(username=data['username']).first()
            if existing:
                # 更新现有记录
                for key, value in data.items():
                    setattr(existing, key, value)
                return existing

            # 创建新记录
            user = SysUser(**data)
            session.add(user)
            session.flush()
            return user

    def get(self, user_id: int) -> Optional[SysUser]:
        """根据用户ID获取用户信息"""
        with self.session_scope() as session:
            return session.query(SysUser).filter_by(id=user_id).first()

    def get_by_username(self, username: str) -> Optional[SysUser]:
        """根据用户名获取用户信息"""
        with self.session_scope() as session:
            return session.query(SysUser).filter_by(username=username).first()

    def update(self, user_id: int, update_data: Dict[str, Any]) -> Optional[SysUser]:
        """更新用户信息"""
        with self.session_scope() as session:
            user = session.query(SysUser).filter_by(id=user_id).first()
            if user:
                for key, value in update_data.items():
                    setattr(user, key, value)
                return user
            return None

    def delete(self, user_id: int) -> bool:
        """删除用户记录"""
        with self.session_scope() as session:
            user = session.query(SysUser).filter_by(id=user_id).first()
            if user:
                session.delete(user)
                return True
            return False

    def filter(self, **filters) -> List[SysUser]:
        """根据条件过滤用户记录"""
        with self.session_scope() as session:
            query = session.query(SysUser)
            for key, value in filters.items():
                query = query.filter(getattr(SysUser, key) == value)
            return query.all()

    def get_all(self) -> List[SysUser]:
        """获取所有用户记录"""
        with self.session_scope() as session:
            return session.query(SysUser).all()

    def get_active_users(self) -> List[SysUser]:
        """获取活跃用户列表"""
        with self.session_scope() as session:
            return session.query(SysUser).filter_by(is_active=True).all()

    def get_users_by_role(self, role: str) -> List[SysUser]:
        """根据角色获取用户列表"""
        with self.session_scope() as session:
            return session.query(SysUser).filter_by(role=role).all()

    def update_last_login(self, user_id: int) -> Optional[SysUser]:
        """更新用户最后登录时间"""
        with self.session_scope() as session:
            user = session.query(SysUser).filter_by(id=user_id).first()
            if user:
                user.last_login = datetime.now()
                return user
            return None

    def count_by_role(self) -> Dict[str, int]:
        """统计各角色的用户数量"""
        with self.session_scope() as session:
            result = session.query(
                SysUser.role,
                func.count(SysUser.id)
            ).group_by(SysUser.role).all()
            return {role: count for role, count in result}


class SysPermissionService(BaseService):
    """用户权限信息服务"""

    def create(self, data: Dict[str, Any]) -> SysPermission:
        """创建新权限记录"""
        with self.session_scope() as session:
            # 检查是否已存在
            existing = session.query(SysPermission).filter_by(
                user_id=data['user_id'],
                module=data['module']
            ).first()

            if existing:
                # 更新现有记录
                for key, value in data.items():
                    setattr(existing, key, value)
                return existing

            # 创建新记录
            permission = SysPermission(**data)
            session.add(permission)
            session.flush()
            return permission

    def get(self, permission_id: int) -> Optional[SysPermission]:
        """根据权限ID获取权限信息"""
        with self.session_scope() as session:
            return session.query(SysPermission).filter_by(id=permission_id).first()

    def get_user_permissions(self, user_id: int) -> List[SysPermission]:
        """获取用户的所有权限"""
        with self.session_scope() as session:
            return session.query(SysPermission).filter_by(user_id=user_id).all()

    def update(self, permission_id: int, update_data: Dict[str, Any]) -> Optional[SysPermission]:
        """更新权限信息"""
        with self.session_scope() as session:
            permission = session.query(SysPermission).filter_by(id=permission_id).first()
            if permission:
                for key, value in update_data.items():
                    setattr(permission, key, value)
                return permission
            return None

    def delete(self, permission_id: int) -> bool:
        """删除权限记录"""
        with self.session_scope() as session:
            permission = session.query(SysPermission).filter_by(id=permission_id).first()
            if permission:
                session.delete(permission)
                return True
            return False

    def delete_user_permissions(self, user_id: int) -> bool:
        """删除用户的所有权限"""
        with self.session_scope() as session:
            permissions = session.query(SysPermission).filter_by(user_id=user_id).all()
            for permission in permissions:
                session.delete(permission)
            return True

    def has_permission(self, user_id: int, module: str, permission_type: str) -> bool:
        """检查用户是否具有特定权限"""
        with self.session_scope() as session:
            permission = session.query(SysPermission).filter_by(
                user_id=user_id,
                module=module
            ).first()

            if not permission:
                return False

            if permission_type == 'read':
                return permission.can_read
            elif permission_type == 'write':
                return permission.can_write
            elif permission_type == 'execute':
                return permission.can_execute

            return False