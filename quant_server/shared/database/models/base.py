# quant_server/shared/database/models/base.py

from sqlalchemy import Column, DateTime
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.sql import func

# 创建声明性基类
Base = declarative_base()


class BaseMixin:
    """基础混合类，用于所有模型共享的字段和方法"""

    created_at = Column(DateTime, default=func.now(), nullable=False, comment="创建时间")
    updated_at = Column(DateTime, default=func.now(), onupdate=func.now(), nullable=False, comment="更新时间")
