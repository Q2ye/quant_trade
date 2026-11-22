# -*- coding: utf-8 -*-
"""决策日志**按月**轮转（`strategy_decision.log.YYYY-MM`）+ 归档脚本适配。

背景（2026-09-21）：决策日志原为天轮转 → 每天一个文件，与策略「周–月频」的查阅粒度不符，
改为按月轮转。本文件把两个易错点钉住：

  ① **轮转只能发生在月边界**。若像 `when='midnight'` 那样每天触发、而 suffix 是 `%Y-%m`
     （当月恒定），第二天 `doRollover` 会因目标名已存在而**直接 return**（CPython
     `# Already rolled over`）→ 本次轮转被跳过且 `rolloverAt` 不再推进 → **此后永不轮转**，
     单文件无限增长、按月分档失效。
  ② **跨月停机后首次写入即轮转，且按「内容所属月」命名**。若只按当前时间算轮转点，
     停机的那个月的内容会被继续追加进当前文件、永不改名 → **两个月串在一个文件里**。

另含 `archive_logs` 对新月名的识别与合并顺序（改轮转不改归档 = 归档静默停摆）。
"""
import importlib.util
import logging
import os
import time
from datetime import date, datetime, timedelta
from pathlib import Path

from utils.core_utils.logging_utils.structured_logger import (
    HandlerFactory,
    LogLevel,
    MonthlyRotatingFileHandler,
)

ARCHIVE_LOGS = Path(__file__).resolve().parents[3] / "scripts" / "ops" / "archive_logs.py"


def _load_archive_logs():
    """按路径加载归档脚本（`scripts/ops/` 无 `__init__.py`，不能直接 import）。

    范式同 `tests/modules/test_strategy/test_bottom_strategy_p1_fixes.py`。
    """
    spec = importlib.util.spec_from_file_location("archive_logs_under_test", ARCHIVE_LOGS)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


def _freeze(monkeypatch, dt: datetime) -> None:
    """冻结 `time.time()`（`structured_logger` 与 `logging.handlers` 共用同一 time 模块）。

    只改 `time.time`，`localtime`/`mktime`/`strftime` 保持真实 —— 二者接收的是被冻结的
    时间戳，故仍自洽。
    """
    ts = dt.timestamp()
    monkeypatch.setattr(time, "time", lambda: ts)


def _emit(handler, msg: str) -> None:
    handler.emit(logging.LogRecord("t", logging.INFO, __file__, 1, msg, None, None))


def _touch(path: Path, dt: datetime) -> None:
    """写入内容并把 mtime 设为给定时间（模拟「该文件最后写入于那个月」）。"""
    path.write_text(f"{dt:%Y-%m-%d %H:%M} 内容\n", encoding="utf-8")
    ts = dt.timestamp()
    os.utime(path, (ts, ts))


class TestMonthlyRotatingFileHandler:
    """按月轮转的核心行为。"""

    def test_compute_rollover_is_next_month_start(self, tmp_path):
        h = MonthlyRotatingFileHandler(str(tmp_path / "x.log"), backupCount=0, encoding="utf-8")
        try:
            got = time.localtime(h.computeRollover(int(datetime(2026, 9, 21, 19, 0).timestamp())))
            assert (got.tm_year, got.tm_mon, got.tm_mday) == (2026, 10, 1)
            assert (got.tm_hour, got.tm_min, got.tm_sec) == (0, 0, 0)
            # 跨年
            got = time.localtime(h.computeRollover(int(datetime(2026, 12, 31, 23, 0).timestamp())))
            assert (got.tm_year, got.tm_mon, got.tm_mday) == (2027, 1, 1)
        finally:
            h.close()

    def test_no_rotation_within_month(self, tmp_path, monkeypatch):
        """当月内反复重启 + 写入，**不得**产生 `YYYY-MM` 文件（用户的核心诉求）。"""
        log = tmp_path / "strategy_decision.log"
        _touch(log, datetime(2026, 9, 21, 19, 33))
        _freeze(monkeypatch, datetime(2026, 9, 25, 19, 0))

        h = MonthlyRotatingFileHandler(str(log), backupCount=0, encoding="utf-8")
        try:
            assert h.rolloverAt > time.time(), "当月内轮转点必须在未来"
            _emit(h, "2026-09-25 决策 B")
        finally:
            h.close()

        assert not (tmp_path / "strategy_decision.log.2026-09").exists()
        assert log.read_text(encoding="utf-8") == (
            "2026-09-21 19:33 内容\n2026-09-25 决策 B\n")

    def test_rotates_on_month_change_named_by_content_month(self, tmp_path, monkeypatch):
        """跨月停机：旧文件按**它自己的月份**命名，不是按当前月。"""
        log = tmp_path / "strategy_decision.log"
        _touch(log, datetime(2026, 10, 30, 19, 0))       # 内容属于 10 月

        _freeze(monkeypatch, datetime(2026, 11, 5, 19, 0))   # 11 月才启动进程
        h = MonthlyRotatingFileHandler(str(log), backupCount=0, encoding="utf-8")
        try:
            assert h.rolloverAt <= time.time(), "文件属于更早的月 → 轮转点应已到期"
            _emit(h, "2026-11-05 决策 B")
        finally:
            h.close()

        assert (tmp_path / "strategy_decision.log.2026-10").read_text(encoding="utf-8") == (
            "2026-10-30 19:00 内容\n")
        assert log.read_text(encoding="utf-8") == "2026-11-05 决策 B\n"

    def test_year_boundary_rotation(self, tmp_path, monkeypatch):
        """12 月内容 → `.2026-12`（跨年时月份推导不越界）。"""
        log = tmp_path / "strategy_decision.log"
        _touch(log, datetime(2026, 12, 20, 19, 0))
        _freeze(monkeypatch, datetime(2027, 1, 3, 19, 0))

        h = MonthlyRotatingFileHandler(str(log), backupCount=0, encoding="utf-8")
        try:
            _emit(h, "2027-01-03 决策 B")
        finally:
            h.close()

        assert (tmp_path / "strategy_decision.log.2026-12").exists()
        assert log.read_text(encoding="utf-8") == "2027-01-03 决策 B\n"

    def test_existing_month_file_skips_rotation_without_deleting(self, tmp_path, monkeypatch):
        """⚠️ 目标名已存在 → 基类 `# Already rolled over` 直接 return：**不删数据、跳过本次轮转**。

        这条行为有两面，测试都要钉住：
          · 它是「`when='midnight'` + suffix=`%Y-%m` 会失效」的真实原因（不是丢数据，是永不轮转）；
          · 它是**使用约束**：不可手工把内容搬进 `logs/…YYYY-MM`，否则挡住月末轮转 → 两个月串档。
        """
        log = tmp_path / "strategy_decision.log"
        _touch(log, datetime(2026, 10, 30, 19, 0))
        existing = tmp_path / "strategy_decision.log.2026-10"
        existing.write_text("既有归档内容\n", encoding="utf-8")

        _freeze(monkeypatch, datetime(2026, 11, 5, 19, 0))
        h = MonthlyRotatingFileHandler(str(log), backupCount=0, encoding="utf-8")
        try:
            assert h.rolloverAt <= time.time(), "文件属于更早的月 → 轮转点应已到期"
            _emit(h, "2026-11-05 决策 B")
            # 本次轮转被跳过 → 轮转点必须被推进到下个月，否则每次写入都白试一遍
            assert h.rolloverAt == h.computeRollover(int(time.time()))
        finally:
            h.close()

        assert existing.read_text(encoding="utf-8") == "既有归档内容\n", "既有文件不得被删除"
        assert log.read_text(encoding="utf-8").endswith("2026-11-05 决策 B\n"), "新内容不丢"

    def test_get_files_to_delete_ignores_legacy_daily_names(self, tmp_path):
        """只清理最旧的**月**文件；历史日轮转件不归本 handler 管（由 archive_logs 归档）。"""
        for n in ("x.log.2026-07-30", "x.log.2026-08-15", "x.log.2026-08", "x.log.2026-09"):
            (tmp_path / n).write_text("t\n", encoding="utf-8")
        h = MonthlyRotatingFileHandler(str(tmp_path / "x.log"), backupCount=1, encoding="utf-8")
        try:
            names = {os.path.basename(p) for p in h.getFilesToDelete()}
        finally:
            h.close()
        assert names == {"x.log.2026-08"}

    def test_factory_defaults(self, tmp_path):
        """工厂：`backup_count` 默认 0（handler 不删文件，保留交给 archive_logs）。"""
        h = HandlerFactory.create_monthly_file_handler(
            str(tmp_path / "d.log"), level=LogLevel.INFO)
        try:
            assert isinstance(h, MonthlyRotatingFileHandler)
            assert h.backupCount == 0
            assert h.suffix == "%Y-%m"
            assert h.name == "monthly_file"
        finally:
            h.close()


class TestArchiveLogsDecisionNaming:
    """归档脚本必须同时认识月名与历史日名，并保持合并顺序。"""

    def test_decision_key_matches_both_namings(self):
        m = _load_archive_logs()
        assert m._decision_key("strategy_decision.log.2026-09") == (2026, 9, m._MONTHLY_SORT_DAY)
        assert m._decision_key("strategy_decision.log.2026-09-18") == (2026, 9, 18)
        assert m._decision_key("strategy_decision.log.2026-09-18.1") == (2026, 9, 18)
        # 非决策日志不得被误认（否则会被按月并进决策归档）
        assert m._decision_key("quant_server.log.2026-09-18") is None
        assert m._decision_key("strategy_decision.log") is None

    def test_monthly_file_sorts_after_daily_files(self):
        """gz 是多成员拼接，成员顺序=阅读顺序：月文件（该月后半段）必须排在日文件之后。"""
        m = _load_archive_logs()
        files = ["strategy_decision.log.2026-09", "strategy_decision.log.2026-09-18",
                 "strategy_decision.log.2026-09-15"]
        files.sort(key=lambda n: m._decision_key(n)[2])
        assert files == ["strategy_decision.log.2026-09-15",
                         "strategy_decision.log.2026-09-18",
                         "strategy_decision.log.2026-09"]

    def test_plan_picks_only_past_months(self, tmp_path, monkeypatch):
        """当月（含月文件与日文件）一律不动 —— 还在追加。"""
        m = _load_archive_logs()
        today = date.today()
        prev = today.replace(day=1) - timedelta(days=1)

        cur_month = f"strategy_decision.log.{today.year:04d}-{today.month:02d}"
        cur_day = f"strategy_decision.log.{today.year:04d}-{today.month:02d}-01"
        prev_month = f"strategy_decision.log.{prev.year:04d}-{prev.month:02d}"
        prev_day = f"strategy_decision.log.{prev.year:04d}-{prev.month:02d}-15"
        for n in (cur_month, cur_day, prev_month, prev_day):
            (tmp_path / n).write_text("x\n", encoding="utf-8")

        monkeypatch.setattr(m, "LOGS", tmp_path)
        picked = {p.name for p in m.plan()["decisions"]}
        assert picked == {prev_month, prev_day}
