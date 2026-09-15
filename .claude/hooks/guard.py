# -*- coding: utf-8 -*-
"""Claude Code 写入守卫（PreToolUse hook）。

由 `.claude/settings.json` 调用，读 stdin 的 hook payload（JSON），**退出码 2 = 拦截**。

## 为什么要有这个文件（而不是 settings.json 里的 `python -c`）

2026-09-15 实测原实现有 4 个可绕过的口子，集中修在此处：

| # | 原漏洞 | 现在 |
|:--|:---|:---|
| 1 | PreToolUse matcher 只有 `Write\|Edit` → **`NotebookEdit` 可写 `.env`** | settings.json 的 matcher 扩为全部写工具名 |
| 2 | **`.claude/settings.json` 自身不受保护** → guard 可被自我修改（业界称之为"关键难点 1"） | 保护 `.claude/settings.json`（**单点总开关**）；`.claude/hooks/**` 按用户 2026-09-15 决策**放开**，靠 git diff 人工兜底 |
| 3 | **Bash 写 `.env` 完全不拦**（Bash hook 只匹配 `git push*`） | `pre_bash` 检查 shell 写操作 + Python 写文件形态 |
| 4 | 路径判定用 `endswith` → **挡不住 `.env.local` / 软链 / `..`** | 用 `Path.resolve()` 规范化 + 前缀/基名匹配 |

## 用法

    python .claude/hooks/guard.py pre_write   # Write/Edit/NotebookEdit/... 的 file_path 检查
    python .claude/hooks/guard.py pre_bash    # Bash 命令检查

## 已知残留（如实记录，不假装完备）

- `pre_bash` 是**启发式**：能拦常见 shell 写形态与 `open(...,'w')`，但无法穷尽所有写文件方式
  （例如自写 Python 脚本间接写、`perl -i`、经网络传输等）。**它降低风险，不等于安全边界。**
- 本文件与 `.claude/hooks/**` 按用户 2026-09-15 决策**不设保护**（选项 B）：hooks 的改动会
  出现在 `git diff` 里，由提交时人工 review 兜底。唯一受保护的是 `.claude/settings.json`（总开关）。
"""
import json
import re
import sys
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

try:  # Windows 控制台默认 GBK，中文提示会变乱码
    sys.stdout.reconfigure(encoding="utf-8")
    sys.stderr.reconfigure(encoding="utf-8")
except Exception:
    pass

REPO_ROOT = Path(__file__).resolve().parents[2]

#: 受保护的文件（相对仓库根，正斜杠）
PROTECTED_FILES = {
    ".claude/settings.json",
}
#: 受保护的目录前缀（相对仓库根）
#: ⚠️ 2026-09-15 用户决策（选项 B）：**放开 `.claude/hooks/**`**，只保护
#: `.claude/settings.json`（单点总开关 —— 关掉它所有 hook 一起失效）。
#: 理由：hooks 的具体检查逻辑改动会出现在 `git diff` 里，提交时人工 review 是最终兜底；
#: 而把 hooks 也锁死会让 agent 无法迭代/修复守卫自身（当晚实测撞死锁 3 次）。
PROTECTED_DIRS = (
    ".git/",
)
#: 受保护的文件名前缀（任意目录下）
PROTECTED_BASENAME_PREFIX = (".env",)

#: Bash 写操作 → **目标路径**的抽取正则（目标精确匹配）。
#: 2026-09-15 修正：原实现「命令含 `>`/`tee` 等即视为写」→ `2>&1`、`> /dev/null`、
#: `cat a b > /tmp/x` 这类常见用法全部误报（实测 3/5）。现只判**写入目标**是否受保护。
SHELL_WRITE_TARGET_PATTERNS = (
    r">>?\s*[\"']?([^\s\"'|&;>)]+)",              # > path / >> path
    r"\btee\s+(?:-a\s+)?[\"']?([^\s\"'|&;>)]+)",  # tee path
    r"\b(?:cp|mv|ln)\s+(?:-\w+\s+)*[^\s\"'|&;]+\s+[\"']?([^\s\"'|&;>)]+)",  # cp/mv/ln src dst
    r"\brm\s+(?:-\w+\s+)*[\"']?([^\s\"'|&;>)]+)",  # rm path
    r"\bsed\s+-i[^\s]*\s+(?:.*\s)?[\"']?([^\s\"'|&;>)]+)$",  # sed -i ... path
    r"\btruncate\s+\S+\s+[\"']?([^\s\"'|&;>)]+)",
    r"\bchmod\s+\S+\s+[\"']?([^\s\"'|&;>)]+)",
    r"open\(\s*[\"']([^\"']+)[\"']\s*,\s*[\"'][wa]",  # python open(path,"w")
)
#: Python 写文件形态（`Path.write_text` / `write_bytes` 的目标在 `(...)` 之前，单独抽取）
PY_WRITE_TARGET_PATTERN = r"([^\s\"'()]+)\s*\.\s*write_(?:text|bytes)\("


def _load_payload() -> Dict[str, Any]:
    """读 stdin 的 hook payload。

    ⚠️ **必须走 `sys.stdin.buffer` + 显式 UTF-8 解码**（2026-09-15 实测）：
    Windows 下 `sys.stdin` 文本模式默认编码是 **GBK**，harness 发的是 UTF-8；
    含中文的 payload（代码里带中文注释极常见）会解成乱码 → JSON 解析失败 →
    被 except 吞掉 → 返回 `{}` → **守卫静默放行**。
    本次是在 `scan_incoming.py` 上实测踩到的：同样的写法，纯 ASCII payload 正常、
    带中文的 payload 直接漏过，极具迷惑性。
    """
    try:
        raw = sys.stdin.buffer.read()
    except Exception:
        return {}
    if not raw:
        return {}
    for enc in ("utf-8", "utf-8-sig"):
        try:
            return json.loads(raw.decode(enc))
        except Exception:
            continue
    return {}


def _resolve(path_str: str) -> Optional[Path]:
    """规范化路径（解析 `..`、软链、大小写）。失败返回 None。"""
    if not path_str:
        return None
    try:
        return Path(path_str).resolve()
    except Exception:
        try:
            return Path(path_str).absolute()
        except Exception:
            return None


def _candidate_paths(raw: str, cwd: Optional[str]) -> List[Path]:
    """把可能为相对路径的目标展开为若干候选绝对路径。

    ⚠️ 2026-09-15 修正：原实现只按**进程 cwd** 解析相对路径 —— 而 hook 进程的 cwd
    不保证是仓库根（实测从 `quant_server/` 调用时，`rm .claude/settings.json`
    被解析成 `quant_server/.claude/settings.json` → **漏判放行**）。
    现按「payload cwd」与「仓库根」**双解析，任一命中即视为受保护**（fail-closed）。
    """
    p = Path(raw)
    cands: List[Path] = []
    if p.is_absolute():
        cands.append(p)
    else:
        for base in (cwd, str(REPO_ROOT)):
            if base:
                cands.append(Path(base) / raw)
    out: List[Path] = []
    for c in cands:
        r = _resolve(str(c))
        if r is not None and r not in out:
            out.append(r)
    return out


def _classify(target: Path) -> Optional[str]:
    """判断该路径是否受保护；受保护则返回原因文案。"""
    try:
        rel = target.relative_to(REPO_ROOT)
    except ValueError:
        # 仓库外：本守卫暂不管（见模块 docstring「已知残留」）
        return None
    rel_str = str(rel).replace("\\", "/")

    if rel_str in PROTECTED_FILES:
        return f"受保护文件：{rel_str}"
    for d in PROTECTED_DIRS:
        if rel_str.startswith(d):
            return f"受保护目录：{d}"
    base = target.name
    for p in PROTECTED_BASENAME_PREFIX:
        if base.startswith(p):
            return f"凭证文件（基名以 {p} 开头）：{base}"
    return None


def _block(reason: str, extra: str = "") -> int:
    """打印拦截原因并返回退出码 2。"""
    print(
        f"[guard] ⛔ 拦截：{reason}\n"
        f"{extra}"
        f"[guard] 这是 .claude/hooks/guard.py 定义的写入守卫。"
        f"确需修改请**人工编辑**（guard 不应被 agent 自己改写）。",
        file=sys.stderr,
    )
    return 2


def check_write(payload: Dict[str, Any]) -> int:
    """PreToolUse（写文件类工具）：检查 tool_input.file_path。"""
    tool_input = payload.get("tool_input") or {}
    raw = str(tool_input.get("file_path") or "")
    if not raw:
        return 0
    for target in _candidate_paths(raw, payload.get("cwd")):
        reason = _classify(target)
        if reason:
            return _block(reason, f"      目标：{target}\n")
    return 0


def check_bash(payload: Dict[str, Any]) -> int:
    """PreToolUse（Bash）：检查命令的**写入目标**是否为受保护路径。

    2026-09-15 修正：原实现是「命令里出现受保护字样 + 出现 `>`/`tee` 等即算写」，
    导致 `2>&1`、`> /dev/null`、`cat a b > /tmp/merged.txt` 这类常见用法全部误报
    （实测误报 3/5）。现改为：先从命令中抽取**写入目标**，再看目标是否受保护。
    """
    cmd = str((payload.get("tool_input") or {}).get("command") or "")
    if not cmd:
        return 0

    targets: List[str] = []
    for pat in SHELL_WRITE_TARGET_PATTERNS:
        for m in re.finditer(pat, cmd):
            groups = [g for g in m.groups() if g]
            targets.extend(groups)
    # Path.write_text / write_bytes 形态：目标在 `(...)` 之前
    if any(k in cmd for k in ("write_text(", "write_bytes(")):
        for m in re.finditer(PY_WRITE_TARGET_PATTERN, cmd):
            targets.append(m.group(1))

    for t in targets:
        if t in ("/dev/null", "&1", "&2") or t.startswith("/dev/"):
            continue
        for resolved in _candidate_paths(t, payload.get("cwd")):
            reason = _classify(resolved)
            if reason:
                return _block(
                    f"Bash 写入目标受保护（{reason}）",
                    f"      命令：{cmd[:200]}\n      目标：{t} → {resolved}\n",
                )
    return 0


def main() -> int:
    """入口：按 argv[1] 分派。"""
    mode = sys.argv[1] if len(sys.argv) > 1 else ""
    payload = _load_payload()
    if mode == "pre_write":
        return check_write(payload)
    if mode == "pre_bash":
        return check_bash(payload)
    print(f"[guard] 未知模式：{mode}", file=sys.stderr)
    return 1


if __name__ == "__main__":
    sys.exit(main())
