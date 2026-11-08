# -*- coding: utf-8 -*-
"""收工检查 —— ⓿ 交付预检 + 三道门（本项目「零 CI」的替代品）。

## ⓿ + 三道门

| # | 门 | 命令 | 拦什么 |
|:--|:---|:---|:---|
| 0 | **交付预检** | `scripts/quality/check_delivery.py check --quiet` | 当前 REQ 的 S1–S5 产物没补齐（无 REQ 则 SKIP） |
| 1 | **质量门** | `scripts/quality/audit_strategy.py` | 策略代码：未来函数 / 硬编码凭证 / 除零 / 参数越界 |
| 2 | **回归门** | `pytest -q` | 任何新增失败（2026-09-15 已清至 0 failed / 0 errors，基线 276 passed） |
| 3 | **范围门** | `git diff --name-only`（含未跟踪） | 改动是否超出本次声明的范围 |

## 用法

    cd quant_server && .venv/Scripts/python.exe scripts/quality/check_all.py
    # 范围门需要先声明范围（一行一个路径前缀）：
    #   .claude/current_scope.txt   ← 或 --scope <文件>

## 为什么范围门是"可选"的

它是给「**明确知道本次只该动哪些文件**」时用的硬兜底（研究中称为 CI 层 `git diff` 校验）。
日常探索性改动天然跨多文件，**没有声明范围时该门自动 SKIP 并明确说明**，
而不是假装通过 —— 见下方输出。

退出码：0 = 全过（或仅有 SKIP）；1 = 有门未过。
"""
import argparse
import subprocess
import sys
from pathlib import Path
from typing import List, Optional, Tuple

try:  # Windows 控制台默认 GBK，中文输出会炸
    sys.stdout.reconfigure(encoding="utf-8")
    sys.stderr.reconfigure(encoding="utf-8")
except Exception:
    pass

SCRIPT_DIR = Path(__file__).resolve().parent          # scripts/quality/
# 2026-09-15 移入 quality/ 后 +1 级（原先 SCRIPT_DIR.parent 即 quant_server/）
QUANT_SERVER = SCRIPT_DIR.parent.parent
REPO_ROOT = QUANT_SERVER.parent
DEFAULT_SCOPE = REPO_ROOT / ".claude" / "current_scope.txt"

VENV_PY = QUANT_SERVER / ".venv" / "Scripts" / "python.exe"
PYTHON = str(VENV_PY) if VENV_PY.exists() else sys.executable


def _run(cmd: List[str], cwd: Path, timeout: int = 300) -> Tuple[int, str]:
    """执行子进程，返回 (退出码, 合并输出)。"""
    try:
        p = subprocess.run(cmd, cwd=str(cwd), capture_output=True, text=True,
                           timeout=timeout, encoding="utf-8", errors="replace")
        return p.returncode, (p.stdout or "") + (p.stderr or "")
    except subprocess.TimeoutExpired:
        return 124, f"⏱ 超时（>{timeout}s）"
    except Exception as exc:
        return 125, f"执行失败：{exc}"


def gate_audit() -> Tuple[str, str]:
    """门 1：策略质量门（只取汇总行，避免把上百条除法启发式警告淹没结论）。"""
    rc, out = _run([PYTHON, "scripts/quality/audit_strategy.py"], QUANT_SERVER, timeout=120)
    keep = [
        ln.strip() for ln in out.splitlines()
        if any(ln.startswith(k) for k in ("🔴 阻断", "🟡 警告", "⚪ 豁免", "结论"))
        or ln.strip().startswith("[🔴")
    ]
    return ("PASS" if rc == 0 else "FAIL"), "\n".join(keep) or out.strip()[-200:]


def gate_regression() -> Tuple[str, str]:
    """门 2：回归门（全量 pytest）。"""
    rc, out = _run([PYTHON, "-m", "pytest", "-q", "--no-header",
                    "-p", "no:cacheprovider", "--tb=no"],
                   QUANT_SERVER, timeout=600)
    last = [ln for ln in out.strip().splitlines() if ln.strip()][-1:] or [""]
    return ("PASS" if rc == 0 else "FAIL"), last[0].strip()


def gate_delivery() -> Tuple[str, str]:
    """⓿ 交付预检：当前 REQ 的五份产物是否补齐（无进行中 REQ 则 SKIP）。

    只判「结构」（文件 / 章节 / AC 是否存在），不判内容质量 —— 内容质量归 S4/S5 人看。
    与三道门的关系：它是**前置**，不改三道门的判据；未建 REQ 的旧用法（SKIP）不受影响。
    """
    rc, out = _run([PYTHON, "scripts/quality/check_delivery.py", "check", "--quiet"],
                   QUANT_SERVER, timeout=60)
    status = {0: "PASS", 2: "SKIP"}.get(rc, "FAIL")
    if status == "SKIP":
        return "SKIP", "无进行中 REQ（docs/09-交付记录/.active 为空）—— 本预检跳过"
    return status, out.strip() or f"exit={rc}"


def _changed_files() -> List[str]:
    """已跟踪改动 + 未跟踪（排除 pycache / 二进制）。"""
    rc, out = _run(["git", "status", "--porcelain"], REPO_ROOT, timeout=60)
    if rc != 0:
        return []
    files = []
    for line in out.splitlines():
        if len(line) < 4:
            continue
        path = line[3:].strip()
        if " -> " in path:  # 重命名/复制：status 行是 "旧路径 -> 新路径"，取新路径
            path = path.rsplit(" -> ", 1)[-1]
        path = path.strip().strip('"')
        if "__pycache__" in path or path.endswith((".pyc", ".png", ".jpg")):
            continue
        files.append(path.replace("\\", "/"))
    return files


def gate_scope(scope_file: Optional[Path]) -> Tuple[str, str]:
    """门 3：改动范围校验（无声明则 SKIP）。

    ⚠️ 与 `git status` 全量比对是错的 —— 仓库里长期存在大量未跟踪文件（诊断脚本等），
    那样本门**永远 FAIL，等于不可用**（2026-09-15 实测踩到）。
    正确模型：**声明范围 = 打快照 + 给白名单**，只校验「声明之后新出现的改动」。
    """
    if scope_file is None or not scope_file.exists():
        return "SKIP", (
            f"未声明范围（无 {DEFAULT_SCOPE.relative_to(REPO_ROOT)}）—— 本门跳过\n"
            f"声明方式：`python scripts/quality/check_all.py --declare \".claude/,docs/,quant_server/scripts/\"`"
        )
    prefixes = [
        ln.strip().replace("\\", "/")
        for ln in scope_file.read_text(encoding="utf-8").splitlines()
        if ln.strip() and not ln.strip().startswith("#")
    ]
    if not prefixes:
        return "SKIP", "范围文件为空 —— 本门跳过"

    baseline_file = scope_file.with_name("scope_baseline.txt")
    if not baseline_file.exists():
        return "SKIP", f"缺快照 {baseline_file.name} —— 请重新 --declare"

    baseline = {ln.strip() for ln in baseline_file.read_text(encoding="utf-8").splitlines() if ln.strip()}
    new_changes = sorted(set(_changed_files()) - baseline)
    outside = [f for f in new_changes if not any(f.startswith(p) for p in prefixes)]

    if not new_changes:
        return "PASS", f"声明以来无新改动（基线 {len(baseline)} 个文件，白名单 {len(prefixes)} 条前缀）"
    if not outside:
        return "PASS", f"{len(new_changes)} 个新改动全部在白名单内（{len(prefixes)} 条前缀）"
    return "FAIL", (
        f"{len(new_changes)} 个新改动中有 {len(outside)} 个越界：\n"
        + "\n".join(f"      {f}" for f in outside[:20])
        + f"\n      白名单：{prefixes}"
    )


def declare_scope(prefixes_raw: str, scope_file: Optional[Path] = None) -> int:
    """声明范围：写白名单 + 对当前 git status 打快照。"""
    prefixes = [p.strip().replace("\\", "/") for p in prefixes_raw.split(",") if p.strip()]
    if not prefixes:
        print("用法：--declare \".claude/,docs/\"（逗号分隔的路径前缀）")
        return 2
    scope_file = scope_file or DEFAULT_SCOPE
    scope_file.parent.mkdir(parents=True, exist_ok=True)
    body = "# 本次允许改动的路径前缀（check_all.py --declare 生成）\n" + "\n".join(prefixes) + "\n"
    scope_file.write_text(body, encoding="utf-8")
    snap = "\n".join(_changed_files())
    scope_file.with_name("scope_baseline.txt").write_text(snap + "\n", encoding="utf-8")
    print(f"✅ 已声明范围：{prefixes}")
    print(f"   快照：{len(snap.splitlines()) if snap else 0} 个当前已改动/未跟踪文件（作为基线）")
    print("   之后新增的改动中，超出白名单的会被 ③ 范围门拦下。")
    return 0


def main() -> int:
    """跑 ⓿ 交付预检 + 三道门并汇总。"""
    ap = argparse.ArgumentParser(description="收工检查（交付预检 + 质量门 + 回归门 + 范围门）")
    ap.add_argument("--scope", default=str(DEFAULT_SCOPE), help="范围声明文件路径")
    ap.add_argument("--declare", default=None,
                    help="声明本次允许改动的路径前缀（逗号分隔），并对当前状态打快照")
    args = ap.parse_args()

    if args.declare is not None:
        return declare_scope(args.declare, Path(args.scope))

    print("=" * 72)
    print("收工检查（check_all.py）—— ⓿ 交付预检 + 本项目「零 CI」的三道门")
    print("=" * 72)

    results = [
        ("⓿ 交付预检  check_delivery", *gate_delivery()),
        ("① 质量门  audit_strategy", *gate_audit()),
        ("② 回归门  pytest", *gate_regression()),
        ("③ 范围门  git diff", *gate_scope(Path(args.scope))),
    ]

    failed = 0
    for name, status, detail in results:
        icon = {"PASS": "✅", "FAIL": "⛔", "SKIP": "⚪"}[status]
        print(f"\n{icon} {name}  [{status}]")
        if detail:
            for ln in detail.splitlines():
                print(f"    {ln}")
        if status == "FAIL":
            failed += 1

    print("\n" + "-" * 72)
    if failed:
        print(f"结论：⛔ {failed} 项未过（交付预检或某道门）—— 修复后再提交")
        return 1
    print("结论：✅ 全过（SKIP 项：无 REQ 则交付预检跳过，未声明范围则范围门跳过）")
    return 0


if __name__ == "__main__":
    sys.exit(main())
