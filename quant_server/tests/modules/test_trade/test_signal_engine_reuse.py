# -*- coding: utf-8 -*-
"""阶段3: signal_engine._persist_signal 单行流转复用分支测试。

验证：买入信号带 parent_id（候选行 id）且该行存在 → update 复用候选行
流转到 pending_manual（不再另起一行）；parent_id 不存在 → create 新建（卖出信号）。
"""
import asyncio
import importlib

import pytest

from modules.trade.engines.signal_engine import SignalEngine


def _make_engine():
    engine = SignalEngine.__new__(SignalEngine)
    engine._session_factory = None  # 测试中覆盖
    return engine


class FakeSession:
    async def __aenter__(self):
        return self

    async def __aexit__(self, *a):
        return False

    def begin(self):
        return self


class FakeRow:
    def __init__(self, id):
        self.id = id


def _patch_repo(repo_obj):
    repo_mod = importlib.import_module(
        "shared.database.repositories.strategy.signal.signal_repo")
    repo_mod.SignalRepository = lambda db: repo_obj
    return repo_mod


class TestPersistReuse:
    def test_reuse_candidate_row_when_parent_id_exists(self):
        """parent_id 指向的候选行存在 → update 复用，不 create"""
        captured = {}

        class FakeRepo:
            async def get(self, sig_id):
                return FakeRow(sig_id) if sig_id == "candidate-row" else None

            async def get_by_stock(self, ts_code, strategy_id, signal_type, limit=50):
                # 2026-09-15 补桩：`_persist_signal` 新增「新信号覆盖同标的历史 pending」逻辑，
                # 会调用 `repo.get_by_stock(...)`。原 FakeRepo 缺此方法 →
                # AttributeError 被 except 吞掉 → `_persist_signal` 返回 None → 断言失败。
                # 本测试关注「无候选行 → create」，故返回空列表。
                return []

            async def update(self, sig_id, data):
                captured["update"] = (sig_id, data)

            async def create(self, data):
                captured["create"] = data
                return FakeRow("new-row")

        engine = _make_engine()
        engine._session_factory = lambda: FakeSession()
        repo_mod = _patch_repo(FakeRepo())
        _orig = repo_mod.SignalRepository

        signal_data = {
            "signal_id": "child-new-id",
            "parent_id": "candidate-row",
            "strategy_id": "strategy-1",
            "ts_code": "603519.SH",
            "signal_type": "entry",
            "direction": "long",
            "price": 17.30,
            "quantity": 100,
            "confidence": 0.75,
            "reason": "买入(收盘确认)",
        }
        db_id = asyncio.run(engine._persist_signal(signal_data))

        # 复用候选行：update 被调用，create 未调用
        assert db_id == "candidate-row"
        assert "update" in captured
        assert captured["update"][0] == "candidate-row"
        assert captured["update"][1]["signal_status"] == "pending_manual"
        assert "create" not in captured

        repo_mod.SignalRepository = _orig

    def test_create_new_when_parent_id_not_exists(self):
        """parent_id 不存在（卖出信号）→ create 新建"""
        captured = {}

        class FakeRepo:
            async def get(self, sig_id):
                return None

            async def get_by_stock(self, ts_code, strategy_id, signal_type, limit=50):
                # 2026-09-15 补桩：`_persist_signal` 新增「新信号覆盖同标的历史 pending」逻辑，
                # 会调用 `repo.get_by_stock(...)`。原 FakeRepo 缺此方法 →
                # AttributeError 被 except 吞掉 → `_persist_signal` 返回 None → 断言失败。
                # 本测试关注「无候选行 → create」，故返回空列表。
                return []

            async def update(self, sig_id, data):
                captured["update"] = (sig_id, data)

            async def create(self, data):
                captured["create"] = data
                return FakeRow("new-row")

        engine = _make_engine()
        engine._session_factory = lambda: FakeSession()
        repo_mod = _patch_repo(FakeRepo())
        _orig = repo_mod.SignalRepository

        signal_data = {
            "signal_id": "sell-new-id",
            "parent_id": None,
            "strategy_id": "strategy-1",
            "ts_code": "512400.SH",
            "signal_type": "exit",
            "direction": "close_long",
            "price": 1.90,
            "quantity": 500,
        }
        db_id = asyncio.run(engine._persist_signal(signal_data))

        # 无候选行：create 新建
        assert db_id == "new-row"
        assert "create" in captured
        assert "update" not in captured

        repo_mod.SignalRepository = _orig
