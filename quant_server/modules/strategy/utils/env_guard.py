# -*- coding: utf-8 -*-
"""Live 策略环境门（单一判据）。

规则：
- ``ENVIRONMENT=production``：``live`` / ``paper`` / ``backtest`` 全部允许；
- ``development`` / ``test`` / ``testing``：**只拦 live**，paper/backtest 照常；
- 环境取自 ``os.getenv("ENVIRONMENT", "development")``，与
  ``shared.database.session.session_manager._assert_environment_safety`` 同源
  （``main.py --mode`` 会写入该变量）。

本模块只做纯判定，不写 DB、不依赖策略实例，便于单测与多入口复用。
"""

from __future__ import annotations

import os
from typing import Any, Optional


def normalize_environment(env: Optional[str] = None) -> str:
    raw = env if env is not None else os.getenv("ENVIRONMENT", "development")
    # 兼容 Environment 枚举（str Enum 的 str() 不是 value）
    raw = getattr(raw, "value", raw)
    return (str(raw or "").strip().lower()) or "development"


def is_production_env(env: Optional[str] = None) -> bool:
    return normalize_environment(env) == "production"


def normalize_run_mode(run_mode: Any) -> str:
    """把 RunMode 枚举/字符串/None 归一为小写字符串；None 按 live（现有默认）。"""
    if run_mode is None:
        return "live"
    value = getattr(run_mode, "value", run_mode)
    return (str(value or "").strip().lower()) or "live"


def can_run_live(run_mode: Any, env: Optional[str] = None) -> bool:
    """paper/backtest 在任何环境可用；live（以及未知/脏值）仅 production。

    未知 run_mode 按 live 处理（保守）：宁可非生产拒绝，也不把一个未知模式
    当成只读的 paper/backtest 放行。
    """
    mode = normalize_run_mode(run_mode)
    if mode in ("paper", "backtest"):
        return True
    return is_production_env(env)


def should_restore_strategy(run_mode: Any, env: Optional[str] = None) -> bool:
    """重启恢复：paper/backtest 可恢复，live 仅 production。"""
    return can_run_live(run_mode, env)


__all__ = [
    "normalize_environment",
    "normalize_run_mode",
    "is_production_env",
    "can_run_live",
    "should_restore_strategy",
]
