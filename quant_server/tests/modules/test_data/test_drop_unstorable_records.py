# -*- coding: utf-8 -*-
"""`_drop_unstorable_records` 单元测试（纯函数，不连库）。

背景（2026-09-21 根因修复）：
	`index_daily.close` 是 NOT NULL，而 Tushare 对 `395xxx.SZ` 恒返回 NaN close。
	NaN 经既有清洗变成 None → `NotNullViolationError` → `_sync_by_date_batch`
	**该交易日整批回滚**（写入=0），57 个交易日全部失败，index_daily 冻结在 09-18。
	本函数把「整批静默失败」降级为「少数行丢弃 + 告警」。
"""
import logging
import math

import numpy as np
import pytest

from modules.data.services.sync_service import _drop_unstorable_records
from shared.database.models.data_models import IndexDaily


def _rec(ts_code, trade_date, close, **kw):
    """构造一条 index_daily 记录（未列出的可空列保持缺省）。"""
    rec = {"ts_code": ts_code, "trade_date": trade_date, "close": close}
    rec.update(kw)
    return rec


def _mine(caplog):
    """只取**被测模块自身**的日志。

    ⚠️ 不能断言 `caplog.records` 的全局内容：全量跑时它会同时收到其他测试延迟落下的
    记录（实测 `core.engines.base.engine_base` 的「引擎资源清理: test_event_engine」
    在 DEBUG 级别下串进来）→ 断言「级别列表恰好等于 [...]」会**排序相关的假失败**。
    """
    return [r for r in caplog.records if r.name.endswith("sync_service")]


class TestDropUnstorableRecords:
    """按目标表的 NOT NULL 列剔除不可存储记录。"""

    def test_drops_rows_with_nan_close_keeps_others(self, caplog):
        """NaN close（Tushare 的 395xxx.SZ）被丢弃，合法行全部保留。"""
        records = [
            _rec("000300.SH", "20260921", 4507.39),
            _rec("395001.SZ", "20260921", float("nan")),
            _rec("000905.SH", "20260921", 7799.61),
            _rec("395002.SZ", "20260921", np.nan),
        ]
        with caplog.at_level(logging.WARNING):
            kept = _drop_unstorable_records(records, IndexDaily, "指数日线(index_daily)")

        assert [r["ts_code"] for r in kept] == ["000300.SH", "000905.SH"]
        # 告警必须可见（项目规则：禁止静默丢弃）
        assert any("丢弃 2/4" in m for m in [r.getMessage() for r in _mine(caplog)])
        assert any("close" in m for m in [r.getMessage() for r in _mine(caplog)])

    def test_drops_none_close(self, caplog):
        """None 与 NaN 同等处理（清洗链路两种形态都会产出）。"""
        records = [
            _rec("000300.SH", "20260921", 4507.39),
            _rec("395001.SZ", "20260921", None),
        ]
        with caplog.at_level(logging.WARNING):
            kept = _drop_unstorable_records(records, IndexDaily, "t")
        assert len(kept) == 1
        assert kept[0]["ts_code"] == "000300.SH"

    def test_nullable_columns_are_not_dropped(self, caplog):
        """可空列（open/high/low/vol/amount）为 None 不得触发丢弃。"""
        records = [
            _rec("000300.SH", "20260921", 4507.39,
                 open=None, high=None, low=None, vol=None, amount=None),
            _rec("000905.SH", "20260921", 7799.61, vol=float("nan")),
        ]
        kept = _drop_unstorable_records(records, IndexDaily, "t")
        assert kept == records
        assert not _mine(caplog)

    def test_no_drop_returns_input_unchanged(self):
        """无丢弃时原样返回入参（不复制、不打印日志）。"""
        records = [_rec("000300.SH", "20260921", 1.0)]
        assert _drop_unstorable_records(records, IndexDaily, "t") is records

    def test_all_dropped_logs_error(self, caplog):
        """整批不可存储 → ERROR（否则会退化成"零写入"静默）。"""
        records = [_rec("395001.SZ", "20260921", float("nan"))]
        with caplog.at_level(logging.ERROR):
            kept = _drop_unstorable_records(records, IndexDaily, "t")
        assert kept == []
        assert any(r.levelno == logging.ERROR for r in _mine(caplog))
        assert any("全部" in m for m in [r.getMessage() for r in _mine(caplog)])

    def test_all_dropped_logs_only_one_line(self, caplog):
        """全丢时**只发一条**日志（不叠加逐条告警）—— 逐码全量同步曾有 2× 噪声。"""
        records = [_rec("395001.SZ", "20260921", float("nan")),
                   _rec("395002.SZ", "20260921", float("nan"))]
        with caplog.at_level(logging.WARNING):
            _drop_unstorable_records(records, IndexDaily, "t")
        assert len(_mine(caplog)) == 1, [r.getMessage() for r in _mine(caplog)]

    def test_all_dropped_level_is_configurable(self, caplog):
        """逐码路径传 WARNING（单个 code 全历史无价格是**已知形态**，非异常）。"""
        records = [_rec("395001.SZ", "20260921", float("nan"))]
        with caplog.at_level(logging.DEBUG):
            kept = _drop_unstorable_records(
                records, IndexDaily, "指数日线(index_daily)",
                all_dropped_level=logging.WARNING)
        assert kept == []
        assert [r.levelno for r in _mine(caplog)] == [logging.WARNING]

    def test_partial_drop_still_warns_at_warning(self, caplog):
        """只要有行存活，就仍走逐条 WARNING（与全丢分支互斥）。"""
        records = [_rec("000300.SH", "20260921", 1.0),
                   _rec("395001.SZ", "20260921", float("nan"))]
        with caplog.at_level(logging.DEBUG):
            _drop_unstorable_records(records, IndexDaily, "t",
                                     all_dropped_level=logging.WARNING)
        assert [r.levelno for r in _mine(caplog)] == [logging.WARNING]
        assert "丢弃 1/2" in _mine(caplog)[0].getMessage()


class TestPerCodePathDowngradesLevel:
    """接线测试：**逐码路径**（`_process_trade_date_data`）必须传 WARNING。

    只测 helper 的默认级别是不够的 —— 若调用点漏传，逐码全量同步仍会刷一屏 ERROR。
    """

    async def test_per_code_path_logs_warning_not_error(self, caplog):
        from modules.data.services.sync_service import DataSyncService

        class _Repo:
            model = IndexDaily

            def __init__(self):
                self.written = None

            async def bulk_upsert(self, records, chunk_size=1000):
                self.written = records
                return len(records)

        repo = _Repo()
        # 该 code 的全历史都无 close（真实形态：Tushare 对 395xxx 只给 vol/amount）
        data = [{"ts_code": "395001.SZ", "trade_date": "20041213", "close": None},
                {"ts_code": "395001.SZ", "trade_date": "20041214", "close": float("nan")}]

        with caplog.at_level(logging.DEBUG):
            # 用哑对象当 self：该方法只用到 _preprocess_records + helper + repo
            count, _updated = await DataSyncService._process_trade_date_data(
                object(), repo, data, "395001.SZ")

        assert count == 0
        assert repo.written == [], "全丢后不应有行进入 bulk_upsert"
        assert [r.levelno for r in _mine(caplog)] == [logging.WARNING], \
            [r.getMessage() for r in _mine(caplog)]


class TestIndexNoOhlcFilter:
    """`index_daily` 的前置排除：Tushare 不提供 OHLC 的指数不进同步队列。"""

    def test_filters_395_prefix(self):
        from modules.data.services.sync_service import _filter_index_codes_with_ohlc
        codes = ["000300.SH", "395001.SZ", "399006.SZ", "395099.SZ", "000905.SH"]
        assert _filter_index_codes_with_ohlc(codes) == ["000300.SH", "399006.SZ", "000905.SH"]

    def test_keeps_everything_else(self):
        from modules.data.services.sync_service import _filter_index_codes_with_ohlc
        codes = ["000001.SH", "399001.SZ", "000300.SH", "000905.SH", "399006.SZ"]
        assert _filter_index_codes_with_ohlc(codes) == codes

    def test_prefixes_are_configurable_constant(self):
        """排除依据是模块级常量（Tushare 补齐 OHLC 后删掉它即可复位）。"""
        from modules.data.services.sync_service import _INDEX_NO_OHLC_PREFIXES
        assert _INDEX_NO_OHLC_PREFIXES == ("395",)

    @pytest.mark.parametrize("bad_records", [None, [], ()])
    def test_empty_input(self, bad_records):
        assert _drop_unstorable_records(bad_records, IndexDaily, "t") == bad_records

    def test_fail_open_without_model(self, caplog):
        """取不到 model → 原样返回（不改变既有行为）。"""
        records = [_rec("395001.SZ", "20260921", float("nan"))]
        assert _drop_unstorable_records(records, None, "t") is records
        assert _drop_unstorable_records(records, object(), "t") is records
        assert not _mine(caplog)

    def test_missing_required_column_is_not_dropped(self):
        """记录里**没有**该列 → 不判定为空（由 DB 默认值/约束处理，不越权丢弃）。"""
        records = [{"ts_code": "000300.SH", "trade_date": "20260921"}]
        assert _drop_unstorable_records(records, IndexDaily, "t") is records

    def test_inf_close_is_kept(self):
        """Inf 不是 None —— 不在本函数职责内（NOT NULL 不拦 Inf），不得误丢。"""
        records = [_rec("000300.SH", "20260921", float("inf"))]
        assert _drop_unstorable_records(records, IndexDaily, "t") is records

    def test_only_reports_actually_empty_columns(self, caplog):
        """告警只列真正为空的 NOT NULL 列（便于定位上游字段）。"""
        records = [_rec("395001.SZ", "20260921", float("nan"))]
        with caplog.at_level(logging.WARNING):
            _drop_unstorable_records(records, IndexDaily, "指数日线(index_daily)")
        msg = " ".join(r.getMessage() for r in _mine(caplog))
        assert "'close'" in msg
        assert "'ts_code'" not in msg and "'trade_date'" not in msg
