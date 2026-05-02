# -*- coding: utf-8 -*-
"""
验证工具
提供用户名、密码、邮箱、手机号等格式校验函数。
"""

import re
from typing import Tuple, List

# 用户名：3-32 位，字母开头，字母/数字/下划线
_USERNAME_RE = re.compile(r"^[a-zA-Z][a-zA-Z0-9_]{2,31}$")

# 邮箱
_EMAIL_RE = re.compile(r"^[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}$")

# 手机号（中国大陆）
_PHONE_RE = re.compile(r"^1[3-9]\d{9}$")


def validate_username(username: str) -> Tuple[bool, str]:
    """校验用户名格式

    Returns:
        (is_valid, error_message)
    """
    if not username:
        return False, "用户名不能为空"
    if len(username) < 3:
        return False, "用户名长度不能少于 3 位"
    if len(username) > 32:
        return False, "用户名长度不能超过 32 位"
    if not _USERNAME_RE.match(username):
        return False, "用户名必须以字母开头，且只能包含字母、数字和下划线"
    return True, ""


def validate_password(password: str) -> Tuple[bool, List[str]]:
    """校验密码强度

    要求：至少 8 位，包含大写、小写、数字、特殊字符中的至少三类

    Returns:
        (is_valid, error_messages)
    """
    errors = []
    if len(password) < 8:
        errors.append("密码长度不能少于 8 位")
    if len(password) > 128:
        errors.append("密码长度不能超过 128 位")

    categories = 0
    if re.search(r"[A-Z]", password):
        categories += 1
    if re.search(r"[a-z]", password):
        categories += 1
    if re.search(r"[0-9]", password):
        categories += 1
    if re.search(r"[^a-zA-Z0-9]", password):
        categories += 1

    if categories < 3:
        errors.append("密码需包含大写字母、小写字母、数字、特殊字符中的至少三类")

    return len(errors) == 0, errors


def validate_email(email: str) -> Tuple[bool, str]:
    """校验邮箱格式

    Returns:
        (is_valid, error_message)
    """
    if not email:
        return True, ""  # 邮箱为可选字段
    if not _EMAIL_RE.match(email):
        return False, "邮箱格式不正确"
    return True, ""


def validate_phone(phone: str) -> Tuple[bool, str]:
    """校验手机号格式（中国大陆）

    Returns:
        (is_valid, error_message)
    """
    if not phone:
        return True, ""  # 手机号为可选字段
    if not _PHONE_RE.match(phone):
        return False, "手机号格式不正确"
    return True, ""


def validate_pagination(page: int, page_size: int) -> Tuple[int, int]:
    """规范化分页参数

    Returns:
        (sanitized_page, sanitized_page_size)
    """
    page = max(1, page)
    page_size = max(1, min(1000, page_size))
    return page, page_size


def sanitize_filename(filename: str) -> str:
    """清理文件名中的危险字符，防止路径穿越"""
    return re.sub(r"[^\w\-_. ]", "_", filename).strip()
