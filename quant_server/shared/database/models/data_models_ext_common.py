# -*- coding: utf-8 -*-
"""日频数据底座模型的公共列。

56 张表末尾都有 data_source / fetched_at / created_at / updated_at，
用 mixin 避免在每个模型里重复四列。
"""

from sqlalchemy import Column, DateTime, String
from sqlalchemy.sql import func


class ExtCommonMixin:
    """通用来源与时间戳列（与 DDL 的公共列一致）。"""

    data_source = Column(
        String(16), nullable=False, default="tushare", server_default="tushare"
    )
    fetched_at = Column(DateTime(timezone=True), server_default=func.now())
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now()
    )
