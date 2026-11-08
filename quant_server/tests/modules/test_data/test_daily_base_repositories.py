# -*- coding: utf-8 -*-
"""日频数据底座仓储与模型的一致性测试（不连库）。"""

from shared.database.models.data_models_ext_registry import EXT_MODELS
from shared.database.repositories.market.ext import REPO_CLASSES


def test_repo_count_is_57():
    assert len(REPO_CLASSES) == 57
    assert len({r.__name__ for r in REPO_CLASSES}) == 57


def test_each_repo_maps_to_one_model_and_table():
    tables = {r(None).model.__tablename__ for r in REPO_CLASSES}
    assert tables == set(EXT_MODELS)


def test_each_repo_exposes_bulk_upsert():
    for repo_cls in REPO_CLASSES:
        assert hasattr(repo_cls(None), "bulk_upsert"), repo_cls.__name__
