# -*- coding: utf-8 -*-
"""实盘决策日志：上下文标记 + 过滤器。

## 为什么要独立一路日志

**实盘决策过程在 DB 里没有对应记录。** `strategy_manager._run_live_strategies` 的
「策略每日运行」与「[策略诊断]」只走 `logger.info`（`strategy_manager.py:1785-1791`），
各策略内部的 `[卖出]止损` / `[VETO]` / F9 守卫 / 走弱期等同样只打日志 —— **均不落库**。
DB 只记「决策**结果**」（`signals` / `positions` / `orders` / `account_daily_performance`），
**不记「决策过程」**。

→ 所以**要回答「某天为什么没买 / 为什么选它 / 哪道门把它拒了」，只能查日志。**
   日志因此不是可选产物，而是决策过程的唯一记录，值得独立成文件长期保留。

## 为什么需要 LiveDecisionFilter（不加会怎样）

策略层 logger 在**回测**时同样大量输出。实测 2026-09-13 单日：

    策略层日志 136,786 行 → 其中 135,501 行来自回测/对照实验
    （`[跨市场-R²夹零-终验]` / `[跨市场-问题1-B/C]` 等 draft 实例逐日刷），
    只有 1,285 行是实盘（且那还是「首次启动」的一次性开销，常态仅 22 行/天）。

没有本过滤器，决策日志会被回测淹没（1.6 KB/天 → 85 KB/天，且全是噪音）。

## 分流点（为什么这样就能区分）

`strategy_manager._run_live_strategies` **只驱动 `run_mode ∈ {live, simulation}`**
的策略（`strategy_manager.py:1685` 附近已核实），故在其调用点置位本标志；
回测走 `backtest_engine` 的另一条路径，不会置位 → 天然排除。

## 用法

    from utils.core_utils.logging_utils.decision_log import live_decision_ctx
    _tok = live_decision_ctx.set(True)
    try:
        ...
    finally:
        live_decision_ctx.reset(_tok)
"""
import contextvars
import logging

#: 实盘/模拟盘驱动期间为 True；回测路径不设置 → 天然排除
live_decision_ctx: contextvars.ContextVar = contextvars.ContextVar(
    "live_decision", default=False
)

#: 决策日志只收「策略层」日志（其余如数据同步/引擎调度不进，避免噪音）
STRATEGY_LOGGER_PREFIX = "modules.strategy"


class LiveDecisionFilter(logging.Filter):
    """只放行「实盘驱动期间」产生的**策略层**日志。

    ⚠️ 不要用 `HandlerFactory.create_module_filter` —— 它判的是 `record.module`
    （由文件路径推出的**模块名**，如 `strategy_manager`），**不是** logger 的点分路径，
    按命名空间过滤会全部落空。故此处直接判 `record.name`。
    """

    def filter(self, record: logging.LogRecord) -> bool:
        """True = 写入决策日志。"""
        if not live_decision_ctx.get():
            return False
        return str(record.name).startswith(STRATEGY_LOGGER_PREFIX)


def mark_live_decision() -> object:
    """置位实盘决策上下文，返回 token（供 `reset` 用）。"""
    return live_decision_ctx.set(True)


def unmark_live_decision(token: object) -> None:
    """复位实盘决策上下文。"""
    try:
        live_decision_ctx.reset(token)
    except (ValueError, LookupError):
        # token 已失效（重复 reset / 跨 context）—— 不致命
        pass
