# login.py
from fastapi import APIRouter, HTTPException, status, Query
from typing import Optional, Dict
from datetime import datetime, timedelta
import hashlib
import secrets
from pydantic import BaseModel

router = APIRouter(prefix="/api/auth", tags=["auth"])

# 使用 Pydantic 模型定义请求体
class LoginRequest(BaseModel):
    username: str
    password: str

class RegisterRequest(BaseModel):
    username: str
    password: str
    role: str = "user"

# 用户模型
class User:
    def __init__(self, id: int, username: str, password: str, role: str = "user"):
        self.id = id
        self.username = username
        self.password = password
        self.role = role

# 令牌模型
class Token:
    def __init__(self, token: str, user_id: int, expires_at: datetime):
        self.token = token
        self.user_id = user_id
        self.expires_at = expires_at

# 内存存储
users_db = {
    1: User(1, "admin", "admin123", "admin"),
    2: User(2, "user", "user123", "user")
}

# 令牌存储 (内存中)
active_tokens: Dict[str, Token] = {}

# 工具函数
def hash_password(password: str) -> str:
    """简单的密码哈希函数"""
    return hashlib.sha256(password.encode()).hexdigest()

def verify_password(plain_password: str, hashed_password: str) -> bool:
    """验证密码"""
    return hash_password(plain_password) == hashed_password

def get_user_by_username(username: str) -> Optional[User]:
    """根据用户名获取用户"""
    for user in users_db.values():
        if user.username == username:
            return user
    return None

def get_user_by_id(user_id: int) -> Optional[User]:
    """根据用户ID获取用户"""
    return users_db.get(user_id)

def create_token(user_id: int) -> str:
    """创建新令牌"""
    # 生成随机令牌
    token = secrets.token_urlsafe(32)

    # 设置过期时间 (1小时)
    expires_at = datetime.now() + timedelta(hours=1)

    # 存储令牌
    active_tokens[token] = Token(token, user_id, expires_at)

    return token

def validate_token(token: str) -> Optional[User]:
    """验证令牌并返回用户"""
    if token not in active_tokens:
        return None

    token_obj = active_tokens[token]

    # 检查令牌是否过期
    if datetime.now() > token_obj.expires_at:
        # 删除过期令牌
        del active_tokens[token]
        return None

    # 返回用户
    return get_user_by_id(token_obj.user_id)

def cleanup_expired_tokens():
    """清理过期令牌"""
    current_time = datetime.now()
    expired_tokens = [
        token for token, token_obj in active_tokens.items()
        if current_time > token_obj.expires_at
    ]

    for token in expired_tokens:
        del active_tokens[token]

    return len(expired_tokens)

# API 端点
@router.post("/login")
async def login(login_request: LoginRequest):
    """用户登录"""
    try:
        user = get_user_by_username(login_request.username)

        if not user or user.password != login_request.password:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="用户名或密码错误",
            )

        # 创建令牌
        token = create_token(user.id)

        return {
            "message": "登录成功",
            "token": token,
            "user": {
                "id": user.id,
                "username": user.username,
                "role": user.role
            }
        }
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"登录过程中发生错误: {str(e)}"
        )

@router.post("/logout")
async def logout(token: str = Query(...)):
    """用户登出"""
    try:
        if token in active_tokens:
            del active_tokens[token]

        return {"message": "登出成功"}
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"登出过程中发生错误: {str(e)}"
        )

@router.get("/users/me")
async def get_current_user(token: str = Query(...)):
    """获取当前用户信息"""
    try:
        user = validate_token(token)

        if not user:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="无效或过期的令牌",
            )

        return {
            "id": user.id,
            "username": user.username,
            "role": user.role
        }
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"获取用户信息时发生错误: {str(e)}"
        )

@router.post("/register")
async def register_user(register_request: RegisterRequest):
    """注册新用户"""
    try:
        if get_user_by_username(register_request.username):
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="用户名已存在"
            )

        # 创建新用户
        user_id = max(users_db.keys()) + 1 if users_db else 1

        users_db[user_id] = User(
            id=user_id,
            username=register_request.username,
            password=register_request.password,
            role=register_request.role
        )

        return {"message": "用户注册成功", "user_id": user_id}
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"注册用户时发生错误: {str(e)}"
        )

@router.get("/tokens/cleanup")
async def cleanup_tokens():
    """清理过期令牌（管理端点）"""
    try:
        count = cleanup_expired_tokens()
        return {"message": f"清理了 {count} 个过期令牌"}
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"清理令牌时发生错误: {str(e)}"
        )