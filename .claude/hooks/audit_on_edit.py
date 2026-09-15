# -*- coding: utf-8 -*-
"""策略文件改动后自动跑「策略质量门」（PostToolUse hook）。

由 `.claude/settings.json` 调用。**退出码 2 = 阻断级问题**（会回喂给模型要求修复）。

## 为什么

`quant_server/scripts/audit_strategy.py`（2026-09-15 新建）能机检未来函数 / 硬编码凭证 /
除零 / 参数越界 —— 但**它要人记得跑**。本 hook 把它变成「改了策略就自动跑」，
对齐 `docs/02-功能设计/策略体系/策略实盘准入标准.md` 的 G1 代码门。

范围限定：只对 `quant_server/modules/strategy/strategies/**/*.py` 触发（粒度对齐
`.claude/rules/strategy-gates.md` 的 `paths` 声明），避免无关文件改动也被审计。
"""
import json
import subprocess
import sys
from pathlib import Path

try:  # Windows 控制台默认 GBK，中文提示会变乱码（2026-09-15 补）
    sys.stdout.reconfigure(encoding="utf-8")
    sys.stderr.reconfigure(encoding="utf-8")
except Exception:
    pass

REPO_ROOT = Path(__file__).resolve().parents[2]
QUANT_SERVER = REPO_ROOT / "quant_server"
WATCH_PREFIX = "quant_server/modules/strategy/strategies/"


def main() -> int:
    """若改动的是策略文件，则运行质量门脚本。"""
    # ⚠️ 走 buffer + 显式 UTF-8（见 guard.py `_load_payload` 的说明：Windows 下
    #    sys.stdin 文本模式是 GBK，含中文的 payload 会解析失败 → hook 静默放行）
    try:
        raw = sys.stdin.buffer.read()
        payload = json.loads(raw.decode("utf-8")) if raw else {}
    except Exception:
        try:
            payload = json.loads(raw.decode("utf-8-sig")) if raw else {}
        except Exception:
            return 0

    tool_input = payload.get("tool_input") or {}
    file_path = str(tool_input.get("file_path") or "")
    if not file_path:
        return 0

    try:
        rel = str(Path(file_path).resolve().relative_to(REPO_ROOT)).replace("\\", "/")
    except Exception:
        return 0
    if not rel.startswith(WATCH_PREFIX) or not rel.endswith(".py"):
        return 0

    # ⚠️ 2026-09-15：`audit_strategy.py` 已移入 `scripts/quality/`（scripts 按类分目录）。
    #    本 hook 路径随之更新 —— 若不同步，策略质量门会**静默失效**（找不到脚本即 return 0）。
    script_rel = "scripts/quality/audit_strategy.py"
    script = QUANT_SERVER / script_rel
    if not script.exists():
        print(f"[audit_on_edit] ⚠️ 找不到质量门脚本 {script_rel}，本 hook 跳过", file=sys.stderr)
        return 0

    venv_py = QUANT_SERVER / ".venv" / "Scripts" / "python.exe"
    python = str(venv_py) if venv_py.exists() else sys.executable

    try:
        proc = subprocess.run(
            [python, script_rel, rel[len("quant_server/"):]],
            cwd=str(QUANT_SERVER), capture_output=True, text=True, timeout=60,
            encoding="utf-8", errors="replace",
        )
    except Exception as exc:  # 审计本身失败不阻断编辑，只提示
        print(f"[audit_on_edit] 质量门执行失败（忽略）：{exc}", file=sys.stderr)
        return 0

    if proc.returncode == 0:
        return 0

    print(
        f"[audit_on_edit] ⛔ {rel} 未通过策略质量门（脚本退出码 {proc.returncode}）：\n"
        f"{proc.stdout}\n"
        f"{proc.stderr}\n"
        f"修复后用 `cd quant_server && .venv/Scripts/python.exe scripts/audit_strategy.py` 复核。",
        file=sys.stderr,
    )
    return 2


if __name__ == "__main__":
    sys.exit(main())
