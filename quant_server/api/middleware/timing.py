# -*- coding: utf-8 -*-
"""API 请求计时中间件 — 零侵入记录每个 HTTP 请求的耗时"""
import time
import logging

from fastapi import Request

logger = logging.getLogger("api.timing")

# 轮询类接口、健康检查等高频请求不打印日志
# 支持精确路径（字符串）和路径前缀（以 * 结尾则用 startswith 匹配）
_SKIP_PATHS: set[str] = {
    "/",                                     # 根路径 404（前端/Vite 代理探测）
    "/favicon.ico",                          # 浏览器图标请求
    "/quantTrade/data/sync/status",
    "/quantTrade/data/factors/research/status",   # 研究进度轮询
    "/quantTrade/system/health",
    "/quantTrade/system/module-health",
    "/quantTrade/backtest/health",
    "/quantTrade/strategy/health",
    "/quantTrade/data/health",
    "/quantTrade/trade/health",
    "/quantTrade/analysis/health",
    "/quantTrade/monitor/health",
    "/quantTrade/account/health",
}

_SKIP_PREFIXES: tuple[str, ...] = (
    "/quantTrade/backtest/tasks/",   # 回测任务详情轮询（含 UUID 路径段）
    "/quantTrade/data/sync/status/", # 指定 task_id 的同步状态轮询
)


def _should_skip(path: str) -> bool:
    if path in _SKIP_PATHS:
        return True
    if path.startswith(_SKIP_PREFIXES):
        return True
    return False


async def timing_middleware(request: Request, call_next):
    """记录每个请求的方法、路径、状态码和耗时（毫秒）"""
    start = time.perf_counter()
    response = await call_next(request)
    elapsed_ms = (time.perf_counter() - start) * 1000
    if not _should_skip(request.url.path):
        logger.info(
            f"{request.method:6s} {request.url.path:50s} → {response.status_code}  {elapsed_ms:7.0f}ms"
        )
    return response
