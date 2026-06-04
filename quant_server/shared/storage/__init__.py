"""
共享存储模块
提供文件存储、对象存储等基础设施

架构层次：共享资源层
"""
from .file_storage import FileStorage

__all__ = ["FileStorage"]
