#!/usr/bin/env python3
"""
修复并重新生成一个永久有效的JWT令牌
"""

import sys
import os
from datetime import timedelta

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from quant_server.shared.security.jwt_handler import JWTManager

def generate_permanent_token():
    """生成一个永久有效的开发令牌（100年有效期）"""

    jwt_manager = JWTManager()

    # 超管用户数据（从docs/sql/add_super_admin_user.sql获取）
    user_data = {
        "sub": "1",  # 用户ID
        "username": "superadmin",  # 用户名
        "email": "superadmin@quant.com",  # 邮箱
        "full_name": "超级管理员",  # 全名
        "phone": "13888888888",  # 手机号
        "is_active": True,  # 激活状态
        "is_superuser": True,  # 超级用户
        "is_admin": True,  # 管理员
        "role": "admin",  # 角色
        "roles": ["admin", "superadmin"],  # 角色列表
        "permissions": {
            "strategy": {"can_read": True, "can_write": True, "can_execute": True},
            "basket": {"can_read": True, "can_write": True, "can_execute": True},
            "trading": {"can_read": True, "can_write": True, "can_execute": True},
            "market": {"can_read": True, "can_write": True, "can_execute": True}
        },
        "can_sync_data": True,
        "can_access_factor": True,
        "can_research_factor": True
    }

    # 设置非常长的过期时间（例如100年）
    permanent_delta = timedelta(days=365 * 100)

    # 生成永久有效的令牌
    access_token = jwt_manager.create_access_token(
        user_data,
        expires_delta=permanent_delta
    )

    # 验证新令牌
    try:
        payload = jwt_manager.verify_token(access_token)
        print("=" * 60)
        print("[OK] 永久有效的JWT令牌生成成功")
        print("=" * 60)
        print()
        print(f"Bearer {access_token}")
        print()
        print("令牌信息:")
        print(f"  用户ID: {payload.get('sub')}")
        print(f"  用户名: {payload.get('username')}")
        print(f"  邮箱: {payload.get('email')}")
        print(f"  角色: {payload.get('role')}")
        print(f"  过期时间: {payload.get('exp')} (约100年后)")
        print(f"  令牌类型: {payload.get('type')}")
        print()
        print("[OK] 这个令牌几乎永久有效，适合开发和测试")

        return access_token

    except Exception as e:
        print(f"[ERROR] 令牌验证失败: {str(e)}")
        return None

if __name__ == "__main__":
    generate_permanent_token()