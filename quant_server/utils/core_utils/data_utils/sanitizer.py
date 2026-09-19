"""
数值安全清理工具 — v2.4 新增

解决审计发现 H35-H37:
  - PostgreSQL JSONB 拒绝 NaN/Inf
  - json.dumps 默认产生非法 JSON
  - Tushare/Baostock DataFrame to_dict 含 NaN

用法:
  from utils.core_utils.data_utils.sanitizer import sanitize_float, sanitize_dict, df_to_safe_records
"""

import math
from typing import Any, Dict, List, Union

import numpy as np


def sanitize_float(value: float, default: float = 0.0) -> float:
    """清理单个浮点数的 NaN/Inf

    Args:
        value: 待检查的浮点数
        default: NaN/Inf 时返回的默认值

    Returns:
        安全浮点数
    """
    if isinstance(value, float):
        if math.isnan(value) or math.isinf(value):
            return default
    return value


def sanitize_dict(d: Dict[str, Any], default: float = 0.0) -> Dict[str, Any]:
    """递归清理 dict 中所有值的 NaN/Inf

    用于 JSONB 写入前确保数据安全。

    Args:
        d: 待清理的字典（原地修改）
        default: NaN/Inf 替换值

    Returns:
        清理后的字典（同一对象）
    """
    for k, v in d.items():
        if isinstance(v, float):
            d[k] = sanitize_float(v, default)
        elif isinstance(v, dict):
            d[k] = sanitize_dict(v, default)
        elif isinstance(v, list):
            d[k] = [
                sanitize_float(x, default) if isinstance(x, float) else x
                for x in v
            ]
        elif isinstance(v, np.floating):
            fv = float(v)
            d[k] = sanitize_float(fv, default)
    return d


def df_to_safe_records(df, default: Any = None) -> List[Dict[str, Any]]:
    """DataFrame → dict records，自动清理 NaN/Inf

    替换不安全的 df.to_dict('records')，确保结果可直接用于
    JSON 序列化或 PostgreSQL 写入。

    Args:
        df: pandas DataFrame（可为 None 或空）
        default: NaN/Inf **残留**（含 pandas 把 None 又转回 NaN 的情形）的替换值。
                 **默认 `None`** —— 见下方 ⚠️。

    Returns:
        安全的 dict records 列表

    ⚠️ 2026-09-19 根因修复：`default` 原为 **`0.0`**，会把 **None 也替换成 `0.0`** ——
       这对**日期列与文本列是毒的**：
         · `stock_basic.delist_date`（上市股无退市日）→ `0.0`
           → asyncpg 报 `invalid input for query argument: 0.0
             (expected a datetime.date or datetime.datetime instance, got 'float')`
         · `stock_basic.area` / `industry`（退市股缺失）→ `0.0`
           → 写入 VARCHAR 列报 `expected str, got float`
       而且 `0.0` **看起来像合法值**，下游会静默当数据用（比 None 危险）。
       改为默认 `None`：asyncpg 对**任意列类型**都把 `None` 正确地映射为 SQL `NULL`，
       JSON 也把 `None` 序列化为 `null` —— **无需替换成 0**。
       `NaN` 亦映射为 `NULL` 而非 `0`：本项目标准明确「**严禁**用 `0` 填充价格字段，
       参与交易决策」（`docs/06-标准规范/01_数据质量标准.md` §2.4）。
    """
    if df is None:
        return []
    if df.empty:
        return []

    # 用 None 替换 NaN
    df = df.where(df.notna(), None)
    # 用 None 替换 ±Inf
    df = df.replace([np.inf, -np.inf], None)

    records: List[Dict[str, Any]] = df.to_dict('records')

    # 第二轮清理：残留的 NaN/Inf → default
    # ⚠️ 不再把 `None` 替换为 default —— None 本身就是要写入的 SQL NULL。
    #    （`df.where(...)` 对 float 列会把 None 又转回 NaN，故 NaN 分支仍需保留。）
    for r in records:
        for k, v in r.items():
            if v is None:
                continue
            if isinstance(v, float) and (math.isnan(v) or math.isinf(v)):
                r[k] = default

    return records


def safe_json_dumps(data: Any, default: Any = str, **kwargs) -> str:
    """安全的 json.dumps 包装，自动拒绝 NaN/Inf

    用法: 替代所有 json.dumps(data, default=str) 调用

    Args:
        data: 待序列化数据
        default: JSONEncoder default 参数
        **kwargs: 其他 json.dumps 参数

    Returns:
        安全的 JSON 字符串

    Raises:
        ValueError: 数据包含 NaN/Inf 且无法序列化
    """
    import json
    kwargs.setdefault("allow_nan", False)
    kwargs.setdefault("default", default)
    return json.dumps(data, **kwargs)
