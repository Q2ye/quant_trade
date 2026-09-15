# -*- coding: utf-8 -*-
"""写入守则：代码文件里的硬编码凭证扫描（PostToolUse hook）。

由 `.claude/settings.json` 调用。**退出码 2 = 阻断**（回喂给模型要求修复）。

## 为什么重写（2026-09-15）

原实现是 settings.json 里的一行 `python -c`，有两个真实缺陷：

1. **只挂 `PostToolUse` 的 `"Write"` matcher** → **用 `Edit` 往已有 `.py` 里加凭证，扫描根本不触发**。
   （这正是本次会话查出的 4 个 hook 漏洞里最严重的一个。）现改为覆盖全部写工具。
2. **正则要求引号内 ≥8 字符** → 实际那个遗留口令 `"123456"` 只有 6 位，**扫不到**。
   现降为 ≥3 字符。

## 设计取舍（为什么不是"一律 8 字符以上 + 全文件类型"）

- **只扫代码/配置类文件**（`.py` / `.yaml` / `.yml` / `.json` / `.toml` / `.env*`）；
  **`.md` 不扫** —— 文档里合法地会引用反例（如 `strategy-auditor` skill 就写了示例）。
- **跳过注释行**（`#` 之后的内容）—— 说明性文字不算硬编码。
- 仍可能误报（如把示例写在代码字符串里），**此时按提示改为读环境变量即可**，
  不要为此放宽规则 —— 凭证红线的价值高于偶尔的摩擦。
"""
import json
import re
import sys
from pathlib import Path

try:  # Windows 控制台默认 GBK，中文提示会变乱码（2026-09-15 补）
    sys.stdout.reconfigure(encoding="utf-8")
    sys.stderr.reconfigure(encoding="utf-8")
except Exception:
    pass

#: 扫描的文件后缀 / 基名
SCAN_SUFFIXES = (".py", ".yaml", ".yml", ".json", ".toml", ".ini", ".cfg", ".sh")
SCAN_BASENAMES = (".env",)

#: 凭证类键名（后跟引号字符串即视为硬编码；值 ≥3 字符）
RE_CRED = re.compile(
    r"""(token|password|passwd|pwd|secret|api[_-]?key|access[_-]?key|private[_-]?key)"""
    r"""\s*[:=]\s*["']([^"']{3,})["']""",
    re.IGNORECASE,
)

#: 白名单：这些值不算凭证（占位/环境变量引用/空）
PLACEHOLDER = re.compile(
    r"""^(\$\{|os\.environ|getenv|process\.env|env\.|null|none|true|false|changeme|your_|xxx+|\*+|<.+>)$""",
    re.IGNORECASE,
)


def read_payload() -> dict:
    """读 stdin 的 hook payload。

    ⚠️ **必须走 `sys.stdin.buffer` 并显式 UTF-8 解码**（2026-09-15 实测踩坑）：
    Windows 下 `sys.stdin` 文本模式的默认编码是 **GBK**，而 harness 发来的是 UTF-8。
    含中文的 payload（例如代码里带中文注释）会被解成乱码 → `json.load` 抛错 →
    被 except 吞掉 → 返回 `{}` → **hook 静默放行**（守卫形同虚设）。
    症状极具迷惑性：纯 ASCII 的 payload 一切正常，只有带中文的才漏。
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


def should_scan(path: Path) -> bool:
    """该文件是否在扫描范围内。"""
    if path.suffix.lower() in SCAN_SUFFIXES:
        return True
    return any(path.name.startswith(b) for b in SCAN_BASENAMES)


def scan(text: str) -> list:
    """返回 [(行号, 键名, 值预览)]。"""
    hits = []
    for lineno, raw in enumerate(text.splitlines(), start=1):
        # 跳过注释（# 之后的内容）—— 说明性文字不算硬编码
        line = raw.split("#", 1)[0]
        for m in RE_CRED.finditer(line):
            key, val = m.group(1), m.group(2)
            if PLACEHOLDER.match(val.strip()):
                continue
            hits.append((lineno, key, val[:6] + ("…" if len(val) > 6 else "")))
    return hits


def main() -> int:
    """读 payload → 扫文件 → 有命中则阻断。"""
    payload = read_payload()

    file_path = str((payload.get("tool_input") or {}).get("file_path") or "")
    if not file_path:
        return 0
    path = Path(file_path)
    if not should_scan(path) or not path.exists():
        return 0

    try:
        text = path.read_text(encoding="utf-8", errors="replace")
    except Exception:
        return 0

    hits = scan(text)
    if not hits:
        return 0

    detail = "\n".join(f"      L{ln}: {k} = {v}" for ln, k, v in hits[:10])
    print(
        f"[scan_credentials] ⛔ {path.name} 疑似写入硬编码凭证：\n{detail}\n"
        f"      请改为从环境变量/配置读取（见 CLAUDE.md「安全红线」；"
        f"已知遗留 etf/bottom_strategy.py 已于 2026-09-15 迁至 shared.config）。",
        file=sys.stderr,
    )
    return 2


if __name__ == "__main__":
    sys.exit(main())
