# -*- coding: utf-8 -*-
"""策略代码质量门（机检脚本）。

把 `.claude/skills/strategy-auditor/SKILL.md` 的 🔴 四项落成可执行检查，
使质量门从「靠人读文档」变成「机器可判断」。

用法：
    cd quant_server
    .venv/Scripts/python.exe scripts/audit_strategy.py                  # 扫默认目录
    .venv/Scripts/python.exe scripts/audit_strategy.py <文件或目录>...   # 扫指定路径

退出码：
    0 = 无阻断项（可能有警告）
    1 = 存在阻断项

检查项：
    🔴 A 未来函数       `shift(-N)` / `.iloc[i+N]` / `.iloc[N+i]`
    🔴 B 硬编码凭证     token/password/api_key/secret 等键 + 字符串字面量
    🔴 D 参数越界       止损 ∉ (0,1) / 止损幅度 > 止盈幅度 / 最大持仓 ∉ (0,100] / 仓位 ∉ [0,1]
    🟡 C 除零无保护     除法右侧为变量（启发式，不阻断，避免误报淹没）
    🟡 E 止损符号遗留   `stop_loss` 负数写法（方向易读错，应迁移为 `stop_loss_pct` 正数）
    ⚪ F 豁免           ATR 倍数式止损（`atr_stop_mult`）等合法例外

参见：
    .claude/skills/strategy-auditor/SKILL.md   （判据来源）
    .claude/rules/audit-strategy.md            （止损正数约定）
    docs/02-功能设计/策略体系/策略实盘准入标准.md  （G1 代码门）
"""

from __future__ import annotations

import ast
import re
import sys
from pathlib import Path
from typing import Dict, List, NamedTuple, Optional, Tuple

# ---------------------------------------------------------------- 常量

DEFAULT_TARGET = "modules/strategy/strategies"

#: 必须为字符串字面量的凭证类键名（大小写不敏感，支持子串匹配）
CREDENTIAL_KEYWORDS = (
    "password", "passwd", "pwd", "token", "api_key", "apikey",
    "secret", "access_key", "private_key",
)

#: 允许出现在源码里的占位/非密文值
PLACEHOLDER_HINTS = ("${", "os.environ", "getenv", "None", "''", '""')

#: `shift(-N)` 未来数据
RE_SHIFT_NEGATIVE = re.compile(r"\.shift\(\s*-\s*\d+")

#: `.iloc[i + 1]` / `.iloc[1 + i]` 未来行
RE_ILOC_FUTURE = re.compile(
    r"\.iloc\[\s*(?:[A-Za-z_]\w*\s*\+\s*\d+|\d+\s*\+\s*[A-Za-z_]\w*)\s*\]"
)

#: 止损键（跌幅阈值语义）
STOP_LOSS_POSITIVE_KEYS = ("stop_loss_pct", "hard_stop_pct")
STOP_LOSS_LEGACY_KEYS = ("stop_loss",)
TAKE_PROFIT_KEYS = ("take_profit_pct", "take_profit", "profit_target")
ATR_STOP_KEYS = ("atr_stop_mult", "atr_multiplier", "atr_stop")
MAX_POSITION_KEYS = ("max_positions", "max_holdings", "max_position_num",
                     "normal_holdings_num", "weak_holdings_num")
#: 仓位**比例**键 —— 必须**精确匹配**：曾因用子串匹配把 `position_weight_power`（幂指数 1.5）
#: 误判为「比例不在 [0,1]」而报了假阻断（2026-09-15 修正）。
POSITION_RATIO_KEYS = ("max_single_position", "single_etf_max_position",
                       "max_position_ratio")
#: 幂指数类键名后缀 —— 出现即跳过比例检查（它们是幂次/倍数，不是比例）
EXPONENT_SUFFIXES = ("_power", "_exponent", "_mult", "_multiple", "_ratio_power")


class Issue(NamedTuple):
    """一条检查结果。"""

    level: str          # 🔴 / 🟡 / ⚪
    code: str           # A / B / C / D / E / F
    file: str
    line: int
    message: str


# ---------------------------------------------------------------- 解析工具


def _iter_params_dicts(tree: ast.AST) -> List[Tuple[ast.Dict, int]]:
    """收集所有名为 DEFAULT_PARAMS 的字典字面量（含行号）。"""
    found: List[Tuple[ast.Dict, int]] = []
    for node in ast.walk(tree):
        targets: List[ast.expr] = []
        value: Optional[ast.expr] = None
        if isinstance(node, ast.Assign):
            targets, value = list(node.targets), node.value
        elif isinstance(node, ast.AnnAssign) and node.value is not None:
            targets, value = [node.target], node.value
        if not targets or not isinstance(value, ast.Dict):
            continue
        for t in targets:
            if isinstance(t, ast.Name) and t.id == "DEFAULT_PARAMS":
                found.append((value, node.lineno))
    return found


def _literal_number(node: ast.expr) -> Optional[float]:
    """常量数值（支持负数一元运算）。"""
    if isinstance(node, ast.Constant) and isinstance(node.value, (int, float)):
        return float(node.value)
    if isinstance(node, ast.UnaryOp) and isinstance(node.op, ast.USub):
        inner = _literal_number(node.operand)
        if inner is not None:
            return -inner
    return None


def _scan_credential_literals(tree: ast.AST, rel: str) -> List[Issue]:
    """B：凭证键 + 字符串字面量。"""
    issues: List[Issue] = []
    for node in ast.walk(tree):
        pairs: List[Tuple[ast.expr, ast.expr]] = []
        if isinstance(node, ast.Dict):
            pairs = [(k, v) for k, v in zip(node.keys, node.values) if k is not None]
        for key_node, value_node in pairs:
            if not isinstance(key_node, ast.Constant) or not isinstance(key_node.value, str):
                continue
            key = key_node.value.lower()
            if not any(kw in key for kw in CREDENTIAL_KEYWORDS):
                continue
            if not isinstance(value_node, ast.Constant) or not isinstance(value_node.value, str):
                continue
            if len(value_node.value) < 3 or any(h in repr(value_node.value) for h in PLACEHOLDER_HINTS):
                continue
            issues.append(Issue(
                "🔴", "B", rel, getattr(key_node, "lineno", 0),
                f"硬编码凭证疑似：{key_node.value} = <字符串字面量>",
            ))
    return issues


def _scan_parameters(tree: ast.AST, rel: str) -> List[Issue]:
    """D/E/F：参数越界与遗留符号。"""
    issues: List[Issue] = []
    for params, _base_line in _iter_params_dicts(tree):
        values: Dict[str, Tuple[float, int]] = {}
        for key_node, value_node in zip(params.keys, params.values):
            if not isinstance(key_node, ast.Constant) or not isinstance(key_node.value, str):
                continue
            num = _literal_number(value_node)
            if num is None:
                continue
            values[key_node.value] = (num, getattr(key_node, "lineno", 0))

        # 止损：正数约定
        for key, (val, line) in values.items():
            low = key.lower()
            if any(k in low for k in STOP_LOSS_POSITIVE_KEYS):
                if not (0.0 < val < 1.0):
                    issues.append(Issue(
                        "🔴", "D", rel, line,
                        f"{key} = {val} 不在 (0, 1)：跌幅阈值语义必须为正数且小于 1",
                    ))
            elif any(low == k for k in STOP_LOSS_LEGACY_KEYS):
                if val < 0:
                    issues.append(Issue(
                        "🟡", "E", rel, line,
                        f"{key} = {val} 为负数遗留写法 —— 建议迁移为 "
                        f"{key}_pct = {abs(val)}（正数），判据改 price <= entry*(1-pct)",
                    ))
                elif not (0.0 < val < 1.0):
                    issues.append(Issue(
                        "🔴", "D", rel, line, f"{key} = {val} 不在 (0, 1)",
                    ))
            elif any(k in low for k in ATR_STOP_KEYS):
                issues.append(Issue(
                    "⚪", "F", rel, line,
                    f"{key} = {val}：ATR 倍数式止损，豁免（须在注释标注语义）",
                ))

        # 止损幅度 > 止盈幅度
        stop_vals = [
            abs(v) for k, (v, _l) in values.items()
            if any(s in k.lower() for s in STOP_LOSS_POSITIVE_KEYS + STOP_LOSS_LEGACY_KEYS)
        ]
        tp_vals = [
            abs(v) for k, (v, _l) in values.items()
            if any(t in k.lower() for t in TAKE_PROFIT_KEYS)
        ]
        if stop_vals and tp_vals and min(stop_vals) > max(tp_vals):
            issues.append(Issue(
                "🔴", "D", rel, params.lineno,
                f"止损幅度 {min(stop_vals)} > 止盈幅度 {max(tp_vals)}：结构不合理",
            ))

        # 最大持仓数
        for key, (val, line) in values.items():
            if any(k in key.lower() for k in MAX_POSITION_KEYS):
                if val <= 0 or val > 100:
                    issues.append(Issue(
                        "🔴", "D", rel, line, f"{key} = {val} 不在 (0, 100]",
                    ))
            if any(k == key.lower() for k in POSITION_RATIO_KEYS) and not any(
                key.lower().endswith(s) for s in EXPONENT_SUFFIXES
            ):
                if not (0.0 <= val <= 1.0):
                    issues.append(Issue(
                        "🔴", "D", rel, line, f"{key} = {val} 不在 [0, 1]",
                    ))
    return issues


def _scan_division(tree: ast.AST, rel: str) -> List[Issue]:
    """C：除法右侧为变量（启发式，仅警告）。"""
    issues: List[Issue] = []
    for node in ast.walk(tree):
        if not (isinstance(node, ast.BinOp) and isinstance(node.op, ast.Div)):
            continue
        right = node.right
        if isinstance(right, (ast.Name, ast.Attribute)):
            issues.append(Issue(
                "🟡", "C", rel, getattr(node, "lineno", 0),
                f"除法右侧为变量 `{ast.unparse(right)}` —— 确认有 0/空 守卫",
            ))
    return issues


# ---------------------------------------------------------------- 主扫描


def _audit_file(path: Path, root: Path) -> List[Issue]:
    """单个 .py 文件的全部检查。"""
    rel = str(path.relative_to(root)) if path.is_relative_to(root) else str(path)
    text = path.read_text(encoding="utf-8", errors="replace")
    issues: List[Issue] = []

    # 正则类（处理 ast 不便表达的形态）
    for idx, line in enumerate(text.splitlines(), start=1):
        if RE_SHIFT_NEGATIVE.search(line):
            issues.append(Issue("🔴", "A", rel, idx, "`shift(-N)` 未来数据访问"))
        if RE_ILOC_FUTURE.search(line):
            issues.append(Issue("🔴", "A", rel, idx, "`.iloc[i+N]` 访问未来行"))

    try:
        tree = ast.parse(text)
    except SyntaxError as exc:  # 语法错误本身是阻断
        issues.append(Issue("🔴", "A", rel, exc.lineno or 0, f"语法错误：{exc.msg}"))
        return issues

    issues.extend(_scan_credential_literals(tree, rel))
    issues.extend(_scan_parameters(tree, rel))
    issues.extend(_scan_division(tree, rel))
    return issues


def _collect_targets(args: List[str], root: Path) -> List[Path]:
    """展开待扫描的 .py 文件列表。"""
    files: List[Path] = []
    for arg in args:
        p = (root / arg).resolve() if not Path(arg).is_absolute() else Path(arg)
        if p.is_dir():
            files.extend(sorted(p.rglob("*.py")))
        elif p.suffix == ".py" and p.exists():
            files.append(p)
        else:
            print(f"  ⚠️ 跳过无效路径：{arg}")
    return [f for f in files if "__pycache__" not in f.parts]


def main(argv: List[str]) -> int:
    """入口：扫描 → 打印报告 → 返回退出码。"""
    root = Path(__file__).resolve().parents[1]          # quant_server/
    verbose = "--verbose" in argv or "-v" in argv
    paths = [a for a in argv[1:] if not a.startswith("-")]
    files = _collect_targets(paths or [DEFAULT_TARGET], root)

    print("=" * 72)
    print(f"策略代码质量门报告（机检）— 扫描 {len(files)} 个文件")
    print("=" * 72)

    all_issues: List[Issue] = []
    for f in files:
        all_issues.extend(_audit_file(f, root))

    blockers = [i for i in all_issues if i.level == "🔴"]
    warnings = [i for i in all_issues if i.level == "🟡"]
    exempts = [i for i in all_issues if i.level == "⚪"]
    # C（除零启发式）条数多且误报率高 —— 默认只报汇总，避免淹没真信号
    div_warnings = [i for i in warnings if i.code == "C"]
    other_warnings = [i for i in warnings if i.code != "C"]

    print(f"\n🔴 阻断: {len(blockers)} 项")
    for i in blockers:
        print(f"  [{i.code}] {i.file}:{i.line}  {i.message}")

    print(f"\n🟡 警告: {len(other_warnings)} 项")
    for i in other_warnings:
        print(f"  [{i.code}] {i.file}:{i.line}  {i.message}")

    if div_warnings:
        by_file: Dict[str, int] = {}
        for i in div_warnings:
            by_file[i.file] = by_file.get(i.file, 0) + 1
        print(f"\n🟡 除法守卫（启发式，{len(div_warnings)} 处）—— 用 --verbose 看明细")
        for f, n in sorted(by_file.items(), key=lambda kv: -kv[1]):
            print(f"  {n:>3} 处  {f}")
        if verbose:
            for i in div_warnings:
                print(f"      {i.file}:{i.line}  {i.message}")

    if exempts:
        print(f"\n⚪ 豁免: {len(exempts)} 项")
        for i in exempts:
            print(f"  [{i.code}] {i.file}:{i.line}  {i.message}")

    print("\n" + "-" * 72)
    if blockers:
        print(f"结论：🔴 存在 {len(blockers)} 项阻断 —— 修复后才能回测/上线")
        return 1
    if warnings:
        print(f"结论：⚠️ 无阻断，但有 {len(warnings)} 项警告，建议修复")
        return 0
    print("结论：✅ 通过（无阻断、无警告）")
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv))
