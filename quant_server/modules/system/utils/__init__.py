# -*- coding: utf-8 -*-
"""
系统工具子包
提供输入验证、文件操作等通用工具函数。

包含模块：
1. validation_utils — 输入验证（用户名、密码、邮箱、手机、分页）
2. file_utils       — 文件操作（安全路径、读写、临时文件）

位置：quant_server/modules/system/utils/__init__.py
"""

from .validation_utils import (
    validate_username,
    validate_password,
    validate_email,
    validate_phone,
    validate_pagination,
    sanitize_filename,
)
from .file_utils import (
    safe_path,
    ensure_dir,
    get_temp_file,
    get_temp_dir,
    read_file_safe,
    write_file_safe,
)

__all__ = [
    "validate_username",
    "validate_password",
    "validate_email",
    "validate_phone",
    "validate_pagination",
    "sanitize_filename",
    "safe_path",
    "ensure_dir",
    "get_temp_file",
    "get_temp_dir",
    "read_file_safe",
    "write_file_safe",
]

__version__ = "1.0.0"
__author__ = "Quant Team"
__description__ = "系统工具函数"
