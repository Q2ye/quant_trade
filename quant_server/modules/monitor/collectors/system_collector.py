# -*- coding: utf-8 -*-
"""
系统资源采集器

基于 psutil 采集操作系统级指标：CPU、内存、磁盘、网络。
无状态设计，每次调用返回当前快照。
"""

import logging
from typing import Any, Dict, Optional

from quant_server.modules.monitor.events.types import SystemMetricsData

logger = logging.getLogger(__name__)


class SystemCollector:
    """系统资源采集器 — 无状态"""

    _psutil_available: Optional[bool] = None

    @classmethod
    def _check_psutil(cls) -> bool:
        if cls._psutil_available is None:
            try:
                import psutil  # noqa: F401
                cls._psutil_available = True
            except ImportError:
                cls._psutil_available = False
                logger.warning("psutil 未安装，系统资源采集将返回默认值")
        return cls._psutil_available

    @classmethod
    async def collect(cls) -> SystemMetricsData:
        """采集当前系统资源指标"""
        metrics = SystemMetricsData()

        if not cls._check_psutil():
            return metrics

        try:
            import psutil
            import os

            # CPU
            metrics.cpu_usage = round(psutil.cpu_percent(interval=0.1), 2)

            # 内存
            mem = psutil.virtual_memory()
            metrics.memory_usage = round(mem.percent, 2)

            # 磁盘
            disk = psutil.disk_usage("/")
            metrics.disk_usage = round(disk.percent, 2)

            # 网络
            net = psutil.net_io_counters()
            metrics.network_in = round(net.bytes_recv / 1024, 2)
            metrics.network_out = round(net.bytes_sent / 1024, 2)

            # 进程
            process = psutil.Process(os.getpid())
            metrics.thread_count = process.num_threads()

            # 系统进程数
            metrics.process_count = len(psutil.pids())

        except Exception as e:
            logger.error(f"系统资源采集失败: {e}")

        return metrics

    @classmethod
    async def collect_process_info(cls) -> Dict[str, Any]:
        """采集当前进程详细信息"""
        info: Dict[str, Any] = {}

        if not cls._check_psutil():
            return info

        try:
            import psutil
            import os

            process = psutil.Process(os.getpid())

            mem_info = process.memory_info()
            info["memory_rss_mb"] = round(mem_info.rss / 1024 / 1024, 2)
            info["memory_vms_mb"] = round(mem_info.vms / 1024 / 1024, 2)
            info["cpu_percent"] = process.cpu_percent(interval=0.1)
            info["thread_count"] = process.num_threads()
            info["open_files"] = len(process.open_files()) if hasattr(process, 'open_files') else -1
            info["create_time"] = process.create_time()
            info["status"] = process.status()

        except Exception as e:
            logger.error(f"进程信息采集失败: {e}")

        return info
