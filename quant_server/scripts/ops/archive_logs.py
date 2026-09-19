# -*- coding: utf-8 -*-
"""日志归档与清理（默认为 dry-run，加 --apply 才真动）。

## 为什么需要

`main.py` 的 handler 是 `TimedRotatingFileHandler(when='midnight', backup_count=N)` ——
它只删**自己认识的文件名**。实测漏网两类：

1. **同日多次轮转产生 `.1` 后缀**：`quant_server.log.2026-09-13` 与
   `quant_server.log.2026-09-13.1`（后者 **51M**，是当天最大文件，handler 不管它）；
2. **陈旧残留**：`server.log` / `backfill_*.log`（全仓无引用）、诊断脚本产物 `_*.txt`。

而**实盘决策日志**（`strategy_decision.log`）是**决策过程的唯一记录**（DB 不落库），
必须长期保留 → 按月合并 + gzip，**不删**。

## 用法

    cd quant_server
    .venv/Scripts/python.exe scripts/ops/archive_logs.py            # dry-run（默认）
    .venv/Scripts/python.exe scripts/ops/archive_logs.py --apply    # 真动
    .venv/Scripts/python.exe scripts/ops/archive_logs.py --apply --system-days 120

## 策略

| 对象 | 动作 | 保留 |
|:---|:---|:---|
| `strategy_decision.log.YYYY-MM-DD`（**非当月**） | 按月合并 → `logs/archive/decisions/YYYY-MM.log.gz` | **永久** |
| `quant_server.log.*`（早于 `--system-days`） | **按月归入 `logs/archive/system/YYYY-MM.zip`**（含 handler 漏掉的 `.1` 变体） | 默认 **10 天**（压缩包永久） |
| `_*.txt` / `*.pkl` / `__pycache__` | 删除 | — |
| `server.log` / `backfill_*.log` | 移 `logs/archive/legacy/` | — |
"""
import argparse
import gzip
import re
import shutil
import sys
import zipfile
from datetime import date, datetime
from pathlib import Path
from typing import Dict, List, Tuple

try:  # Windows 控制台默认 GBK，中文输出会炸
    sys.stdout.reconfigure(encoding="utf-8")
    sys.stderr.reconfigure(encoding="utf-8")
except Exception:
    pass

LOGS = Path(__file__).resolve().parents[2] / "logs"
ARCHIVE = LOGS / "archive"

#: 决策日志轮转文件：strategy_decision.log.YYYY-MM-DD（允许 .1 变体）
RE_DECISION = re.compile(r"^strategy_decision\.log\.(\d{4})-(\d{2})-(\d{2})(?:\.\d+)?$")
#: 系统日志轮转文件：quant_server.log.YYYY-MM-DD（允许 .1 变体）
RE_SYSTEM = re.compile(r"^quant_server\.log\.(\d{4})-(\d{2})-(\d{2})(?:\.\d+)?$")
#: 杂项：诊断产物 / 临时件（含 `_*.log` —— 一次性诊断脚本写的日志，非系统日志）
RE_JUNK = re.compile(r"^_.*\.(txt|pkl|log)$")
#: 陈旧残留（全仓无引用）
LEGACY = ("server.log", "backfill_daily_basic.log", "backfill_moneyflow.log")


def _parse(name: str, pat: re.Pattern) -> Tuple[int, int, int] | None:
    """匹配轮转文件，返回 (年, 月, 日)。"""
    m = pat.match(name)
    if not m:
        return None
    return int(m.group(1)), int(m.group(2)), int(m.group(3))


def _gz_append(src: Path, dst: Path) -> int:
    """把 src 追加压缩到 dst（.gz），返回写入字节数。"""
    data = src.read_bytes()
    dst.parent.mkdir(parents=True, exist_ok=True)
    # gzip 多成员格式：多次 write 追加是合法的，解压时自动拼接
    with gzip.open(dst, "ab") as fh:
        fh.write(data)
    return len(data)


def _zip_namelist(zpath: Path) -> set:
    """已归档条目名集合（zip 不存在则为空）。"""
    if not zpath.exists():
        return set()
    try:
        with zipfile.ZipFile(zpath) as zf:
            return set(zf.namelist())
    except Exception as e:  # 压缩包损坏 → 不冒险删源文件
        print(f"   ⚠️ 读取 {zpath.name} 失败（将跳过其源文件删除）: {e}", file=sys.stderr)
        return set()


def _zip_add(zpath: Path, files: List[Path]) -> int:
    """把 files 加入按月压缩包（同名条目跳过 → 幂等）；返回新增条目数。"""
    zpath.parent.mkdir(parents=True, exist_ok=True)
    existing = _zip_namelist(zpath)
    added = 0
    with zipfile.ZipFile(zpath, "a", zipfile.ZIP_DEFLATED) as zf:
        for f in files:
            if f.name in existing:
                continue
            zf.write(f, arcname=f.name)
            added += 1
    return added


def plan() -> Dict[str, List[Path]]:
    """扫描 logs/，返回各类待处理文件。"""
    today = date.today()
    out: Dict[str, List[Path]] = {"decisions": [], "system": [], "junk": [], "legacy": []}
    if not LOGS.exists():
        return out
    for p in sorted(LOGS.iterdir()):
        if p.is_dir():
            if p.name == "__pycache__":
                out["junk"].append(p)
            continue
        if p.name in LEGACY:
            out["legacy"].append(p)
            continue
        if RE_JUNK.match(p.name):
            out["junk"].append(p)
            continue
        d = _parse(p.name, RE_DECISION)
        if d:
            # 只归档「非当月」——当月的还会继续追加
            if (d[0], d[1]) < (today.year, today.month):
                out["decisions"].append(p)
            continue
        d = _parse(p.name, RE_SYSTEM)
        if d:
            out["system"].append(p)
    return out


def run(apply: bool, system_days: int) -> int:
    """执行归档/清理。"""
    todo = plan()
    today = date.today()
    saved = 0

    print("=" * 74)
    print(f"日志归档 {'【APPLY 真写】' if apply else '【dry-run 只查】'}  logs={LOGS}")
    print("=" * 74)

    # ---- 1) 决策日志：按月合并，永久保留 ----
    print(f"\n① 决策日志按月归档（永久保留）：{len(todo['decisions'])} 个")
    by_month: Dict[str, List[Path]] = {}
    for p in todo["decisions"]:
        d = _parse(p.name, RE_DECISION)
        by_month.setdefault(f"{d[0]:04d}-{d[1]:02d}", []).append(p)
    for month, files in sorted(by_month.items()):
        size = sum(f.stat().st_size for f in files)
        dst = ARCHIVE / "decisions" / f"{month}.log.gz"
        print(f"   {month}: {len(files)} 个 / {size/1e6:.2f} MB → {dst.relative_to(LOGS)}")
        if apply:
            for f in files:
                _gz_append(f, dst)
                f.unlink()
            saved += size

    # ---- 2) 系统日志：超过 N 天 → **按月归入压缩包**（不是删除）----
    expired: Dict[str, List[Path]] = {}
    for p in todo["system"]:
        d = _parse(p.name, RE_SYSTEM)
        if (today - date(d[0], d[1], d[2])).days > system_days:
            expired.setdefault(f"{d[0]:04d}-{d[1]:02d}", []).append(p)
    exp_size = sum(f.stat().st_size for fs in expired.values() for f in fs)
    n_exp = sum(len(v) for v in expired.values())
    print(f"\n② 系统日志按月归档（>{system_days} 天 → 压缩包，非删除）：{n_exp} 个 / {exp_size/1e6:.1f} MB")
    for month, files in sorted(expired.items()):
        zpath = ARCHIVE / "system" / f"{month}.zip"
        msize = sum(f.stat().st_size for f in files)
        print(f"   {month}: {len(files)} 个 / {msize/1e6:.1f} MB → {zpath.relative_to(LOGS)}")
        for f in files[:3]:
            print(f"        {f.name}  {f.stat().st_size/1e6:.1f} MB")
        if len(files) > 3:
            print(f"        … 另有 {len(files)-3} 个")
    if apply:
        for month, files in sorted(expired.items()):
            zpath = ARCHIVE / "system" / f"{month}.zip"
            sizes = {f.name: f.stat().st_size for f in files}   # unlink 前先取大小
            added = _zip_add(zpath, files)
            archived = _zip_namelist(zpath)                     # 只读一次
            # 只有**确认已进压缩包**的源文件才移除（zip 读取失败时 archived 为空 → 不动源文件）
            removed = 0
            for f in files:
                if f.name in archived:
                    f.unlink()
                    saved += sizes[f.name]
                    removed += 1
            print(f"   ✓ {month}: 新增 {added} 个条目 / 清理源文件 {removed} 个 → {zpath.name}")

    # ---- 3) 杂项 ----
    junk_size = sum(f.stat().st_size for f in todo["junk"] if f.is_file())
    print(f"\n③ 杂项清理（诊断产物 _*.txt / *.pkl / __pycache__）：{len(todo['junk'])} 项 / {junk_size/1e6:.2f} MB")
    if apply:
        for p in todo["junk"]:
            if p.is_dir():
                shutil.rmtree(p, ignore_errors=True)
            else:
                p.unlink()
        saved += junk_size

    # ---- 4) 陈旧残留 ----
    leg_size = sum(f.stat().st_size for f in todo["legacy"])
    print(f"\n④ 陈旧残留移入 archive/legacy/：{len(todo['legacy'])} 个 / {leg_size/1e6:.3f} MB")
    for p in todo["legacy"]:
        print(f"   {p.name}")
    if apply and todo["legacy"]:
        dst_dir = ARCHIVE / "legacy"
        dst_dir.mkdir(parents=True, exist_ok=True)
        for p in todo["legacy"]:
            shutil.move(str(p), str(dst_dir / p.name))

    print("\n" + "-" * 74)
    if apply:
        print(f"✅ 完成。本次回收/归档约 {saved/1e6:.1f} MB")
    else:
        print("（dry-run 结束。确认无误后加 --apply 执行）")
    return 0


def main() -> int:
    """入口。"""
    ap = argparse.ArgumentParser(description="日志归档与清理（默认 dry-run）")
    ap.add_argument("--apply", action="store_true", help="真写（默认只查）")
    ap.add_argument("--system-days", type=int, default=10,
                    help="系统日志保留天数（**默认 10**，2026-09-17 由 90 改）："
                         "超过则**按月归入压缩包**（不是删除）")
    args = ap.parse_args()
    return run(args.apply, args.system_days)


if __name__ == "__main__":
    sys.exit(main())
