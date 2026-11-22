# -*- coding: utf-8 -*-
"""手动成交录入 —「记账去向解析」分支测试。

背景（2026-09-17 事故）：手动录入 `512400.SH sell` 报 400「没有持仓，无法卖出」。
根因是记账账户回落到 `accounts[0]`，而 `get_many_by_user_id` 按 `created_at DESC`
排序 → `accounts[0]` 是**最新创建**的账户（跨市场避险），并非持仓所在的
银河实盘账户。持仓按 (account_id, ts_code, strategy_id) 三维唯一，账户错位即查不到。

本测试锁定修复后的解析契约：
  A  传了 strategy_id      → 策略绑定账户优先（既有语义不变）
  B1 未传、恰好 1 笔持仓   → 采用持仓的 (account_id, strategy_id)   ← 本次修复核心
  B2 未传、≥2 笔持仓       → AmbiguousHoldingError（拒绝任选，防账实不符）
  B3 未传、0 笔持仓        → 回退默认账户 + strategy_id=None（既有语义）
  B4 B1 命中但账户不可用   → 回退默认账户，但保留持仓的 strategy_id
  B0 无任何可用账户        → ValueError
"""
import pytest

from modules.trade.services.trade_record_service import (
    AmbiguousHoldingError,
    TradeRecordService,
)

# 与事故现场一致的 ID（账户名沿用真实数据，便于对照日志）
ACC_DEFAULT = "e3b7d893-f507-4966-aa90-534a2c93ef8b"   # 跨市场避险（最新创建 → accounts[0]）
ACC_HOLDING = "84d81a14-5f0f-4741-b868-92961863ac3a"   # 银河实盘账户（持仓实际所在）
ST_HOLDING = "cebe247d-2778-472c-afb7-eb18a11502ab"    # 熊市防守-01-实盘


class FakeAccount:
    def __init__(self, id, account_name):
        self.id = id
        self.account_name = account_name


class FakePosition:
    def __init__(self, account_id, strategy_id, volume, ts_code="512400.SH"):
        self.account_id = account_id
        self.strategy_id = strategy_id
        self.volume = volume
        self.ts_code = ts_code


class FakeResult:
    def __init__(self, rows):
        self._rows = rows

    def fetchall(self):
        return self._rows

    def fetchone(self):
        return self._rows[0] if self._rows else None


class FakeSession:
    """只识别解析逻辑用到的两条 SQL：策略绑定账户查询 + 策略名批量查询。"""

    def __init__(self, bound_account_id=None, strategy_names=None):
        self._bound_account_id = bound_account_id
        self._strategy_names = strategy_names or {}

    async def execute(self, stmt, params=None):
        sql = str(stmt)
        if "SELECT account_id FROM strategies" in sql:
            sid = (params or {}).get("sid")
            if self._bound_account_id and sid:
                return FakeResult([(self._bound_account_id,)])
            return FakeResult([])
        if "id, name FROM strategies" in sql:
            ids = (params or {}).get("ids") or []
            return FakeResult(
                [(k, self._strategy_names[k]) for k in ids if k in self._strategy_names]
            )
        return FakeResult([])


class FakeAccountRepo:
    def __init__(self, accounts):
        self._accounts = accounts

    async def get_many_by_user_id(self, user_id, skip=0, limit=100):
        # 与 AccountRepository 一致：created_at DESC → 索引 0 是"最新创建"的账户
        return list(self._accounts)


class FakePositionRepo:
    def __init__(self, positions):
        self._positions = positions

    async def get_user_positions_by_code(self, user_id, ts_code, min_volume=1):
        return [p for p in self._positions if p.ts_code == ts_code and p.volume >= min_volume]


def _make_service(accounts, positions, bound_account_id=None, strategy_names=None):
    svc = TradeRecordService.__new__(TradeRecordService)
    svc._session = FakeSession(bound_account_id, strategy_names)
    svc._account_repo = FakeAccountRepo(accounts)
    svc._position_repo = FakePositionRepo(positions)
    return svc


DEFAULT_ACCOUNTS = [
    FakeAccount(ACC_DEFAULT, "跨市场避险"),
    FakeAccount(ACC_HOLDING, "银河实盘账户"),
]


class TestResolveAccountAndStrategy:
    # ---- 路径 A ----
    async def test_a_explicit_strategy_uses_bound_account(self):
        """传了 strategy_id → 用策略绑定账户（既有语义，不得回退）"""
        svc = _make_service(
            DEFAULT_ACCOUNTS,
            positions=[],
            bound_account_id=ACC_HOLDING,
            strategy_names={ST_HOLDING: "熊市防守-01-实盘"},
        )
        target = await svc._resolve_account_and_strategy(
            user_id="u1", ts_code="512400.SH", strategy_id=ST_HOLDING,
        )
        assert str(target.account.id) == ACC_HOLDING
        assert target.strategy_id == ST_HOLDING
        assert target.strategy_name == "熊市防守-01-实盘"

    async def test_a_falls_back_when_bound_account_unavailable(self):
        """策略绑定账户不在可用列表 → 回退默认账户，不抛错"""
        svc = _make_service(DEFAULT_ACCOUNTS, positions=[], bound_account_id="deleted-acc")
        target = await svc._resolve_account_and_strategy(
            user_id="u1", ts_code="512400.SH", strategy_id=ST_HOLDING,
        )
        assert str(target.account.id) == ACC_DEFAULT
        assert target.strategy_id == ST_HOLDING

    # ---- 路径 B ----
    async def test_b1_unique_holding_locates_position_account(self):
        """★ 本次修复核心：未传 strategy_id 时按 ts_code 定位到持仓账户，
        而不是 accounts[0]（最新创建的账户）。"""
        svc = _make_service(
            DEFAULT_ACCOUNTS,
            positions=[FakePosition(ACC_HOLDING, ST_HOLDING, 500)],
            strategy_names={ST_HOLDING: "熊市防守-01-实盘"},
        )
        target = await svc._resolve_account_and_strategy(user_id="u1", ts_code="512400.SH")
        assert str(target.account.id) == ACC_HOLDING, "必须落在持仓所在账户而非 accounts[0]"
        assert target.account.id != ACC_DEFAULT
        assert target.strategy_id == ST_HOLDING
        assert target.strategy_name == "熊市防守-01-实盘"

    async def test_b1_manual_holding_without_strategy_keeps_none(self):
        """手工持仓（strategy_id 为空）→ 账户按持仓定位，策略维度保持 None"""
        svc = _make_service(
            DEFAULT_ACCOUNTS,
            positions=[FakePosition(ACC_HOLDING, None, 800)],
        )
        target = await svc._resolve_account_and_strategy(user_id="u1", ts_code="512400.SH")
        assert str(target.account.id) == ACC_HOLDING
        assert target.strategy_id is None
        assert target.strategy_name is None

    async def test_b2_ambiguous_holdings_rejected_with_candidates(self):
        """多笔持仓 → 拒绝，并在 detail 中列出「账户名 / 策略名（股数）」候选"""
        svc = _make_service(
            [
                FakeAccount(ACC_DEFAULT, "跨市场避险"),
                FakeAccount(ACC_HOLDING, "银河实盘账户"),
            ],
            positions=[
                FakePosition(ACC_HOLDING, ST_HOLDING, 500),
                FakePosition(ACC_DEFAULT, "07651265-9e26-4849-89eb-6c5cdba61187", 300),
            ],
            strategy_names={
                ST_HOLDING: "熊市防守-01-实盘",
                "07651265-9e26-4849-89eb-6c5cdba61187": "跨市场动量避险轮动-实盘-2.0",
            },
        )
        with pytest.raises(AmbiguousHoldingError) as exc:
            await svc._resolve_account_and_strategy(user_id="u1", ts_code="512400.SH")
        msg = str(exc.value)
        assert "2 笔持仓" in msg
        assert "银河实盘账户" in msg and "熊市防守-01-实盘" in msg and "500股" in msg
        assert "跨市场避险" in msg and "300股" in msg

    async def test_b3_no_holding_falls_back_to_default_account(self):
        """无持仓 → 保持既有语义：默认账户 + strategy_id=None"""
        svc = _make_service(DEFAULT_ACCOUNTS, positions=[])
        target = await svc._resolve_account_and_strategy(user_id="u1", ts_code="600000.SH")
        assert str(target.account.id) == ACC_DEFAULT
        assert target.strategy_id is None

    async def test_b4_orphan_holding_account_falls_back_but_keeps_strategy(self):
        """持仓所在账户已软删/关闭 → 回退默认账户，但保留持仓的 strategy_id"""
        svc = _make_service(
            DEFAULT_ACCOUNTS,
            positions=[FakePosition("9188e19e-8990-496a-ab0e-6de501b778b1", ST_HOLDING, 500)],
            strategy_names={ST_HOLDING: "熊市防守-01-实盘"},
        )
        target = await svc._resolve_account_and_strategy(user_id="u1", ts_code="512400.SH")
        assert str(target.account.id) == ACC_DEFAULT
        assert target.strategy_id == ST_HOLDING

    # ---- 边界 ----
    async def test_b0_no_available_account_raises(self):
        svc = _make_service([], positions=[])
        with pytest.raises(ValueError) as exc:
            await svc._resolve_account_and_strategy(user_id="u1", ts_code="512400.SH")
        assert "没有可用账户" in str(exc.value)

    async def test_zero_volume_holding_is_ignored(self):
        """volume=0 的幽灵持仓不作为定位依据 → 退化为 B3 默认账户"""
        svc = _make_service(
            DEFAULT_ACCOUNTS,
            positions=[FakePosition(ACC_HOLDING, ST_HOLDING, 0)],
        )
        target = await svc._resolve_account_and_strategy(user_id="u1", ts_code="512400.SH")
        assert str(target.account.id) == ACC_DEFAULT
        assert target.strategy_id is None
