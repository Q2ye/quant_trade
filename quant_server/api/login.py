import logging  # login.py
from fastapi import APIRouter, HTTPException, status, Query, Depends
from typing import Optional, Dict
from datetime import datetime, timedelta
import hashlib
import secrets
from pydantic import BaseModel
from sqlalchemy.orm import Session

# 添加数据库依赖
from .dependencies import get_db
from ..db.data_service import DataService

router = APIRouter(prefix="/api/auth", tags=["auth"])
logger = logging.getLogger(__name__)


# 使用 Pydantic 模型定义请求体
class LoginRequest(BaseModel):
    username: str
    password: str


class RegisterRequest(BaseModel):
    username: str
    password: str
    role: str = "user"
    email: str = None
    phone: str = None
    real_name: str = None


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


# 令牌存储 (内存中)
active_tokens: Dict[str, Token] = {}


# 工具函数 - 确保这些函数在引用之前定义
def hash_password(password: str) -> str:
    """简单的密码哈希函数"""
    return hashlib.sha256(password.encode()).hexdigest()


def verify_password(plain_password: str, hashed_password: str) -> bool:
    """验证密码"""
    return hash_password(plain_password) == hashed_password


def get_user_by_username(username: str, db: Session) -> Optional[User]:
    """根据用户名从数据库获取用户"""
    try:
        # 使用 DataService 获取用户
        data_service = DataService(db)
        user_record = data_service.sys_user.get_by_username(username)

        if user_record:
            # 将数据库记录转换为 User 对象
            return User(
                id=user_record.id,
                username=user_record.username,
                password=user_record.password_hash,
                role=user_record.role
            )
        return None
    except Exception as e:
        logger.error(f"从数据库获取用户时出错: {str(e)}")
        return None


def get_user_by_id(user_id: int, db: Session) -> Optional[User]:
    """根据用户ID从数据库获取用户"""
    try:
        # 使用 DataService 获取用户
        data_service = DataService(db)
        user_record = data_service.sys_user.get(user_id)

        if user_record:
            # 将数据库记录转换为 User 对象
            return User(
                id=user_record.id,
                username=user_record.username,
                password=user_record.password_hash,
                role=user_record.role
            )
        return None
    except Exception as e:
        logger.error(f"从数据库获取用户时出错: {str(e)}")
        return None


def create_token(user_id: int) -> str:
    """创建新令牌"""
    # 生成随机令牌
    token = secrets.token_urlsafe(32)

    # 设置过期时间 (1小时)
    expires_at = datetime.now() + timedelta(hours=1)

    # 存储令牌
    active_tokens[token] = Token(token, user_id, expires_at)

    return token


def validate_token(token: str, db: Session) -> Optional[User]:
    """验证令牌并返回用户"""
    if token not in active_tokens:
        return None

    token_obj = active_tokens[token]

    # 检查令牌是否过期
    if datetime.now() > token_obj.expires_at:
        # 删除过期令牌
        del active_tokens[token]
        return None

    # 从数据库返回用户
    return get_user_by_id(token_obj.user_id, db)


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
async def login(login_request: LoginRequest, db: Session = Depends(get_db)):
    """用户登录"""
    try:
        user = get_user_by_username(login_request.username, db)

        if not user or not verify_password(login_request.password, user.password):
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="用户名或密码错误",
            )

        # 更新最后登录时间
        data_service = DataService(db)
        data_service.sys_user.update_last_login(user.id)

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
        logger.error(f"登录异常: {repr(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"登录过程中发生错误: {repr(e.detail) if hasattr(e, 'detail') else '未知错误'}"
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
async def get_current_user(token: str = Query(...), db: Session = Depends(get_db)):
    """获取当前用户信息"""
    try:
        user = validate_token(token, db)

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
async def register_user(register_request: RegisterRequest, db: Session = Depends(get_db)):
    """注册新用户"""
    try:
        if get_user_by_username(register_request.username, db):
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="用户名已存在"
            )

        # 创建新用户
        data_service = DataService(db)

        # 哈希密码
        hashed_password = hash_password(register_request.password)

        user_data = {
            "username": register_request.username,
            "password_hash": hashed_password,
            "role": register_request.role,
            "created_at": datetime.now(),
            "updated_at": datetime.now(),
            "is_active": True,
            "email": register_request.email
        }

        user_record = data_service.sys_user.create(user_data)

        return {"message": "用户注册成功", "user_id": user_record.id}
    except Exception as e:
        logger.error(f"注册用户时发生错误: {str(e)}")
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