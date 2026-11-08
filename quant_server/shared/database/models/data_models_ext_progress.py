# -*- coding: utf-8 -*-
"""日频数据底座：回填断点续传表模型。"""

from sqlalchemy import BigInteger, Column, Date, String, Text

from .base import Base
from .data_models_ext_common import ExtCommonMixin


class DataBackfillProgress(ExtCommonMixin, Base):
    __tablename__ = "data_backfill_progress"

    data_type = Column(String(40), primary_key=True)
    trade_date = Column(Date, primary_key=True, comment="按日/按月键；按标的用 period_key")
    period_key = Column(String(40), primary_key=True)
    status = Column(String(12), nullable=False)
    rows_written = Column(BigInteger, default=0)
    error = Column(Text)
