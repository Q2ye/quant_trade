# -*- coding: utf-8 -*-
"""
文件工具
提供文件读写、路径安全校验、临时文件管理等通用操作。
"""

import os
import tempfile
from pathlib import Path
from typing import Optional


# 项目根目录（向上 4 级从 utils/ 到项目根）
_PROJECT_ROOT = Path(__file__).resolve().parent.parent.parent


def safe_path(filename: str, base_dir: Optional[str] = None) -> Path:
    """安全构造路径，防止路径穿越攻击

    Args:
        filename: 用户提供的文件名
        base_dir: 基础目录，默认为项目根下的 data/ 目录

    Returns:
        规范化后的安全路径

    Raises:
        ValueError: 路径穿越到 base_dir 之外时抛出
    """
    base = Path(base_dir) if base_dir else _PROJECT_ROOT / "data"
    base = base.resolve()

    target = (base / filename).resolve()

    # 确保目标路径在 base 之下
    if not str(target).startswith(str(base)):
        raise ValueError(f"路径穿越检测: {filename}")

    return target


def ensure_dir(dir_path: str) -> Path:
    """确保目录存在，不存在则创建

    Returns:
        Path 对象
    """
    p = Path(dir_path)
    p.mkdir(parents=True, exist_ok=True)
    return p


def get_temp_file(suffix: str = "", prefix: str = "quant_") -> str:
    """创建临时文件并返回路径"""
    fd, path = tempfile.mkstemp(suffix=suffix, prefix=prefix)
    os.close(fd)
    return path


def get_temp_dir(prefix: str = "quant_") -> str:
    """创建临时目录并返回路径"""
    return tempfile.mkdtemp(prefix=prefix)


def read_file_safe(file_path: str, max_size_mb: int = 100) -> str:
    """安全读取文件，防止过大文件占用内存

    Args:
        file_path: 文件路径
        max_size_mb: 最大允许的文件大小（MB）

    Returns:
        文件内容

    Raises:
        ValueError: 文件过大或路径不安全
    """
    p = Path(file_path)
    if not p.exists():
        raise FileNotFoundError(f"文件不存在: {file_path}")
    if not p.is_file():
        raise ValueError(f"路径不是文件: {file_path}")

    size_mb = p.stat().st_size / (1024 * 1024)
    if size_mb > max_size_mb:
        raise ValueError(f"文件过大: {size_mb:.1f}MB（限制 {max_size_mb}MB）")

    return p.read_text(encoding="utf-8")


def write_file_safe(file_path: str, content: str, max_size_mb: int = 100) -> None:
    """安全写入文件

    Raises:
        ValueError: 内容过大
    """
    size_mb = len(content.encode("utf-8")) / (1024 * 1024)
    if size_mb > max_size_mb:
        raise ValueError(f"写入内容过大: {size_mb:.1f}MB（限制 {max_size_mb}MB）")

    p = Path(file_path)
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text(content, encoding="utf-8")
