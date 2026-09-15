# -*- coding: utf-8 -*-
"""写入守则：拦截「即将写入的凭证明文」（PreToolUse hook）。

**退出码 2 = 拦截**（阻断工具调用，并把原因回喂给模型）。

## 为什么要有这个文件（PostToolUse 版不够）

2026-09-15 实测：`PostToolUse` 的 `exit 2` **不会回喂给模型** ——
hook 确实被调用了（用探针文件确认），也确实返回了 2，但模型侧只看到
「文件已创建成功」，没有任何拦截信息。对照 `PreToolUse` 的拦截信息是**立即可见**的。

→ 结论：**要"拦"就得放在 PreToolUse**，且 PreToolUse 阶段文件还没落盘，
所以只能检查 **payload 里即将写入的内容**：
  - `Write` → `tool_input.content`
  - `Edit`  → `tool_input.new_string`（只看新增片段，看不见文件里既有的）
  - `NotebookEdit` → `tool_input.new_source`

`scan_credentials.py`（PostToolUse 版）仍保留：它扫**落盘后的完整文件**，
作为第二道网（能发现 PreToolUse 看不到的既有内容），但它是**顾问式**的。

扫描规则复用 `scan_credentials.scan()`，避免两处正则分叉。
"""
import json
import sys
from pathlib import Path

try:  # Windows 控制台默认 GBK
    sys.stdout.reconfigure(encoding="utf-8")
    sys.stderr.reconfigure(encoding="utf-8")
except Exception:
    pass

sys.path.insert(0, str(Path(__file__).resolve().parent))
from scan_credentials import read_payload, scan, should_scan  # noqa: E402  同目录复用，避免规则分叉

#: 各写工具「即将写入的内容」所在字段
CONTENT_FIELDS = ("content", "new_string", "new_source")


def main() -> int:
    """检查即将写入的内容是否含硬编码凭证。"""
    payload = read_payload()

    tool_input = payload.get("tool_input") or {}
    file_path = str(tool_input.get("file_path") or "")
    if not file_path:
        return 0
    if not should_scan(Path(file_path)):
        return 0

    parts = [str(tool_input.get(f) or "") for f in CONTENT_FIELDS]
    incoming = "\n".join(p for p in parts if p)
    if not incoming:
        return 0

    hits = scan(incoming)
    if not hits:
        return 0

    detail = "\n".join(f"      L{ln}: {k} = {v}" for ln, k, v in hits[:10])
    print(
        f"[scan_incoming] ⛔ 阻止写入 {Path(file_path).name}：即将写入的内容含硬编码凭证\n"
        f"{detail}\n"
        f"      请改为从环境变量/配置读取（CLAUDE.md「安全红线」）。\n"
        f"      注：本检查只看本次写入的片段，不含文件既有内容（后者由 PostToolUse 版兜底）。",
        file=sys.stderr,
    )
    return 2


if __name__ == "__main__":
    sys.exit(main())
