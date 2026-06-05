# -*- coding: utf-8 -*-
"""
同步耗时记录工具

为数据同步方法提供分节点耗时统计，帮助定位性能瓶颈。
典型用法::

    timer = SyncTimingLogger(logger, "moneyflow")
    async with timer:
        for ts_code in ts_codes:
            async with timer.node("http_fetch"):
                df = await self._run_in_executor(source.get_moneyflow, ...)
            async with timer.node("db_upsert"):
                result = await repo.bulk_upsert(data)
    # 退出 async with 自动输出:
    # [timing_summary] type=moneyflow total=15.3m | http_fetch=12.1m(79.1%) db_upsert=2.4m(15.7%) ...

设计原则：
1. 零侵入：不改变现有日志格式，使用独立的 [timing] 前缀
2. 轻量级：单次 node 开销 ~1μs（perf_counter）
3. 自适应：累积统计，退出时自动汇总；支持 step_summary 阶段性输出
"""

from __future__ import annotations

import time
from contextlib import asynccontextmanager
from logging import Logger
from typing import Dict, List, Optional


class SyncTimingLogger:
    """同步耗时记录工具，提供分节点耗时统计。

    每个同步方法创建一个实例，在各逻辑节点用 ``async with timer.node("xxx"):``
    包裹代码块，退出 async with 时自动输出阶段汇总。

    Attributes:
        _logger: Python Logger 实例
        _data_type: 数据类型标识（如 "moneyflow"、"daily_quotes"）
        _nodes: {node_name: [elapsed_seconds, ...]} 各节点耗时列表
        _start_time: 整体开始时间（perf_counter）
        _processed: 已处理股票数
        _step_interval: 阶段性日志输出间隔（每 N 只股票输出一次，默认 500）
        _slow_threshold: 单个节点超时警告阈值（秒，默认 5.0）
    """

    # ---- 标准节点名（便于跨方法统一分析） ----
    NODE_RESOLVE_DATE = "resolve_date"   # _resolve_sync_date_range DB 查询
    NODE_HTTP_FETCH = "http_fetch"       # _run_in_executor(source.get_xxx) HTTP 拉取
    NODE_CONVERT = "convert"             # _convert_records_datetime pandas→python
    NODE_DB_UPSERT = "db_upsert"         # bulk_upsert / _process_trade_date_data DB 写入
    NODE_COMMIT = "commit"               # session.commit() 事务提交
    NODE_PROGRESS = "progress"           # _update_progress 缓存写入

    def __init__(
        self,
        logger: Logger,
        data_type: str,
        *,
        step_interval: int = 500,
        slow_threshold: float = 5.0,
    ):
        """初始化耗时记录器。

        Args:
            logger: Python Logger 实例
            data_type: 数据类型标识（如 "moneyflow"），用于日志前缀
            step_interval: 阶段性日志输出间隔（每 N 只股票输出一次 step_summary）
            slow_threshold: 单次节点耗时超过此值（秒）时发 WARNING
        """
        self._logger = logger
        self._data_type = data_type
        self._step_interval = step_interval
        self._slow_threshold = slow_threshold

        self._nodes: Dict[str, List[float]] = {}
        self._start_time: float = 0.0
        self._processed: int = 0
        self._last_step_time: float = 0.0

    # ------------------------------------------------------------------
    # async with 协议 — 自动记录总耗时并输出 summary
    # ------------------------------------------------------------------

    async def __aenter__(self) -> "SyncTimingLogger":
        self._start_time = time.perf_counter()
        self._last_step_time = self._start_time
        self._logger.info("[耗时开始] type=%s", self._data_type)
        return self

    async def __aexit__(self, exc_type, exc_val, exc_tb) -> None:
        self.summary()

    # ------------------------------------------------------------------
    # 核心 API: node(name)
    # ------------------------------------------------------------------

    @asynccontextmanager
    async def node(self, name: str, context: str = ""):
        """标记一个逻辑节点，自动记录耗时。

        用法::

            async with timer.node("http_fetch"):
                df = await self._run_in_executor(source.get_daily, ...)

        Args:
            name: 节点名称（推荐使用 SyncTimingLogger.NODE_* 常量）
        """
        t0 = time.perf_counter()
        try:
            yield
        finally:
            elapsed = time.perf_counter() - t0
            self._nodes.setdefault(name, []).append(elapsed)

            # 单次耗时日志（DEBUG 级别，生产环境默认关闭）
            if self._logger.isEnabledFor(10):  # DEBUG
                self._logger.debug(
                    "[耗时节点] type=%s node=%s 耗时=%.3fs ctx=%s",
                    self._data_type, name, elapsed, context,
                )

            # 慢节点警告
            if elapsed > self._slow_threshold:
                self._logger.warning(
                    "[慢节点] type=%s node=%s 耗时=%.2fs (阈值=%.1fs) ctx=%s",
                    self._data_type, name, elapsed, self._slow_threshold, context,
                )

    # ------------------------------------------------------------------
    # 统计与输出
    # ------------------------------------------------------------------

    def step_summary(self, step_count: Optional[int] = None) -> None:
        """阶段性汇总（INFO 级别），在每 N 只股票后调用。

        输出本阶段耗时和各节点累计耗时，用于中途观察趋势。

        Args:
            step_count: 已处理数量（None 则使用内部 _processed）
        """
        if step_count is not None:
            self._processed = step_count

        now = time.perf_counter()
        step_elapsed = now - self._last_step_time
        total_elapsed = now - self._start_time

        lines = [
            f"[耗时阶段] type={self._data_type} 已处理={self._processed} "
            f"阶段={step_elapsed:.1f}s 累计={total_elapsed:.1f}s"
        ]
        for name, times in sorted(self._nodes.items()):
            total_t = sum(times)
            avg_t = total_t / len(times) if times else 0
            pct = (total_t / total_elapsed * 100) if total_elapsed > 0 else 0
            lines.append(
                f"  {name}: 调用={len(times)} 合计={total_t:.1f}s "
                f"平均={avg_t:.3f}s ({pct:.0f}%)"
            )
        self._logger.info("\n".join(lines))

        # 更新阶段起点
        self._last_step_time = now

    def summary(self) -> None:
        """最终汇总（INFO 级别），在 sync with 退出时自动调用。

        输出总耗时和分节点占比，是排查性能瓶颈的主要入口。
        """
        total = time.perf_counter() - self._start_time
        if total < 0.001:
            self._logger.info("[耗时汇总] type=%s 总耗时=%.0fms (极快)",
                              self._data_type, total * 1000)
            return

        # 构建单行摘要
        parts = [
            f"[耗时汇总] type={self._data_type}",
            f"总耗时={total:.1f}s",
        ]
        for name, times in sorted(self._nodes.items()):
            total_t = sum(times)
            pct = (total_t / total * 100) if total > 0 else 0
            parts.append(f"{name}={total_t:.1f}s({pct:.0f}%)")

        self._logger.info(" | ".join(parts))
