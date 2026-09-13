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
    # 2026-08-30：前端仪表盘 60s 轮询的只读接口（交易驾驶舱/绩效中心自动刷新）
    "/quantTrade/risk/metrics",
    "/quantTrade/strategy",
    "/quantTrade/trade/signals",
    "/quantTrade/trade/orders",
    "/quantTrade/monitor/strategies/health",
}

_SKIP_PREFIXES: tuple[str, ...] = (
    "/quantTrade/backtest/tasks/",   # 回测任务详情轮询（含 UUID 路径段）
    "/quantTrade/data/sync/status/", # 指定 task_id 的同步状态轮询
    "/quantTrade/data/indexes/",     # 指数行情轮询（000001.SH 等）
    # 2026-09-13：回测报告的「逐标的名称解析」——一次打开会产生 N 个请求（N = 标的数），
    # 属只读展示数据，与上面的指数轮询同类。
    "/quantTrade/data/etfs/",        # ETF 详情（报告先试这个）
    "/quantTrade/data/stocks/",      # 股票详情（股票类回测的回退分支）
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
