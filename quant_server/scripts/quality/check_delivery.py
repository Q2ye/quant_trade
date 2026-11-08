#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""交付流程状态机（S1-S5）—— 交付记录的唯一命令行入口。

被引用位置（改动前先看这三处）：
  1. AGENTS.md「开发流程」/ CLAUDE.md「行为约束」—— 常驻指针
  2. docs/06-标准规范/00_交付流程总纲.md §五 —— 流程定义
  3. scripts/quality/check_all.py —— 作为 ⓿ 交付预检调用

⚠️ 本脚本是长期资产，勿删；文件名不要改回 req.py（Python 语境会被读成 requirements）。

用法（CWD = quant_server/）：
    .venv/Scripts/python.exe scripts/quality/check_delivery.py new <slug> --tier T1
    .venv/Scripts/python.exe scripts/quality/check_delivery.py next
    .venv/Scripts/python.exe scripts/quality/check_delivery.py status
    .venv/Scripts/python.exe scripts/quality/check_delivery.py check [REQ] [--quiet]
    .venv/Scripts/python.exe scripts/quality/check_delivery.py scope [--apply]
    .venv/Scripts/python.exe scripts/quality/check_delivery.py use <REQ>

退出码：0 = PASS，1 = FAIL，2 = 无进行中 REQ（SKIP），64 = 参数错误。

机检项：结构 + 章节非空 + AC 有「→」 + 任务表 ≤3 文件 + 反引号路径真实存在
（同一行标「新建」的除外）+ 验收行有 ✅/❌/⊘ 且非空话 + 裁定明确。
"""

from __future__ import annotations

import argparse
import json
import re
import subprocess
import sys
from datetime import date
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[3]
DOCS_ROOT = REPO_ROOT / "docs"
DEFAULT_REQ_ROOT = DOCS_ROOT / "09-交付记录"
TEMPLATE_DIR = DOCS_ROOT / "06-标准规范" / "模板"
QUALITY_DIR = Path(__file__).resolve().parent

STAGES = [
    ("S1", "需求澄清", "01-需求.md",
     ["问题与证据", "目标", "范围", "验收标准", "约束与红线", "假设与未知", "档位"],
     "每条 AC 可执行（命令/操作 → 期望）；有非目标；档位已定"),
    ("S2", "设计", "02-设计.md",
     ["方案概述", "契约", "数据流与依赖", "影响面", "备选方案与取舍", "回滚方案"],
     "契约 + 依赖方向 + 影响面 + 取舍；T2 加回滚"),
    ("S3", "任务拆分", "03-任务.md",
     ["任务表", "执行顺序", "范围声明"],
     "每任务 ≤3 文件 + 独立验收命令 + commit + 顺序；范围已声明"),
    ("S4", "功能测试验证", "04-验证.md",
     ["机器门", "验收逐条", "未覆盖与风险"],
     "AC 逐条「操作 + 实际输出 + 结论」；机器门全绿"),
    ("S5", "代码评审", "05-评审.md",
     ["评审清单", "发现项", "裁定"],
     "按路径规则逐条勾选；发现项带 文件:行；有裁定；作者不自审"),
]

STAGE_HINT = {
    "S1": "写 01-需求.md：先取证，再写可执行的 AC（方法见 docs/06-标准规范/00-1_S1需求澄清.md）",
    "S2": "写 02-设计.md：契约、依赖方向、影响面、备选取舍（见 00-2_S2设计规范.md）",
    "S3": "写 03-任务.md：拆到每任务 ≤3 文件，然后 scope --apply（见 00-3_S3任务拆分.md）",
    "S4": "写 04-验证.md：逐条跑 AC，贴真实输出；再跑 check_all.py（见 00-4_S4S5验证与评审.md）",
    "S5": "写 05-评审.md：交给独立只读 agent / 新会话评审，作者不自审（见 00-4_S4S5验证与评审.md）",
}


def _utf8_stdout() -> None:
    for stream in (sys.stdout, sys.stderr):
        try:
            stream.reconfigure(encoding="utf-8")  # type: ignore[attr-defined]
        except Exception:
            pass


def req_root(args) -> Path:
    return Path(args.root).resolve() if getattr(args, "root", None) else DEFAULT_REQ_ROOT


def read_active(root: Path) -> str:
    f = root / ".active"
    if not f.is_file():
        return ""
    return f.read_text(encoding="utf-8").strip()


def write_active(root: Path, rid: str) -> None:
    root.mkdir(parents=True, exist_ok=True)
    (root / ".active").write_text(rid + "\n", encoding="utf-8")


def load_meta(d: Path) -> dict:
    f = d / "meta.json"
    if not f.is_file():
        return {}
    try:
        return json.loads(f.read_text(encoding="utf-8"))
    except Exception:
        return {}


def save_meta(d: Path, meta: dict) -> None:
    (d / "meta.json").write_text(
        json.dumps(meta, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
    )


def has_placeholder(text: str) -> bool:
    """<...> 视为占位符（模板标记）；真实内容极少出现尖括号。"""
    i = 0
    while True:
        i = text.find("<", i)
        if i < 0:
            return False
        j = text.find(">", i + 1)
        if 0 < j - i <= 80:
            return True
        i += 1


def plain(text: str) -> str:
    for ch in "`*#|>-:：，。、（）： ":
        text = text.replace(ch, "")
    return text.strip()


def is_sep(line: str) -> bool:
    s = line.strip()
    return s.startswith("|") and "-" in s and set(s) <= set("|-: ")


def split_sections(text: str) -> dict:
    sections: dict = {}
    cur = None
    buf: list = []
    for line in text.splitlines():
        if line.startswith("## "):
            if cur is not None:
                sections[cur] = buf
            cur = line[3:].strip()
            buf = []
        elif cur is not None:
            buf.append(line)
    if cur is not None:
        sections[cur] = buf
    return sections


def section_filled(lines: list) -> bool:
    """章节内是否有一处「真人写的内容」：非引用、非注释、无占位符。"""
    i = 0
    while i < len(lines):
        s = lines[i].strip()
        if not s or s.startswith(">") or s.startswith("<!--"):
            i += 1
            continue
        if s.startswith("|"):
            if is_sep(s):
                i += 1
                continue
            nxt = lines[i + 1].strip() if i + 1 < len(lines) else ""
            if is_sep(nxt):
                i += 2
                continue
            cells = [c.strip() for c in s.strip("|").split("|")]
            if cells and all(c and not has_placeholder(c) for c in cells):
                if max(len(c) for c in cells) >= 6:
                    return True
            i += 1
            continue
        if not has_placeholder(s) and len(plain(s)) >= 6:
            return True
        i += 1
    return False


def count_ac(lines: list) -> int:
    n = 0
    for line in lines:
        s = line.strip()
        if s[:1] in ("-", "*"):
            s = s[1:].strip()
        if s.startswith("AC-") and not has_placeholder(s):
            n += 1
    return n


SYMBOLS = ("✅", "❌", "⊘")

ARROWS = ("→", "->", "=>")
WEAK_OUTPUT = {"通过", "正常", "ok", "okay", "已修复", "成功", "没问题", "无问题"}


def first_table(lines: list):
    """取章节里的第一张表，返回 (header, data_rows)。"""
    rows = [ln.strip() for ln in lines if ln.strip().startswith("|")]
    for i, row in enumerate(rows):
        nxt = rows[i + 1] if i + 1 < len(rows) else ""
        if is_sep(nxt):
            header = [c.strip() for c in row.strip("|").split("|")]
            data = []
            for r in rows[i + 2:]:
                if is_sep(r):
                    continue
                data.append([c.strip() for c in r.strip("|").split("|")])
            return header, data
    return [], []


def _col(header: list, *names: str):
    for idx, cell in enumerate(header):
        if any(n in cell for n in names):
            return idx
    return None


NEW_MARKERS = ("新建", "新增", "待建", "新建文件")


def backtick_paths(text: str) -> list:
    """取反引号里的仓库相对路径（跳过命令、URL、占位符、裸文件名）。"""
    out = []
    for m in re.finditer(r"`([^`]+)`", text):
        p = m.group(1).strip()
        if (not p or has_placeholder(p) or " " in p or "://" in p
                or p.startswith("/") or "/" not in p):
            continue
        if "." not in p.rsplit("/", 1)[-1]:
            continue
        out.append(p)
    return out


def missing_paths(paths: list, repo: Path) -> list:
    """仓库根相对为准；同时允许 `quant_server/` 相对（文档里 CWD 常是 quant_server）。"""
    bases = (repo, repo / "quant_server")
    return [p for p in paths if not any((b / p).exists() for b in bases)]


def path_msgs(bad: list) -> list:
    """把不存在的路径收成一条消息（最多列 3 个，保留首次出现顺序）。"""
    seen = []
    for p in bad:
        if p not in seen:
            seen.append(p)
    if not seen:
        return []
    shown = "、".join("`%s`" % p for p in seen[:3])
    more = "（共 %d 个）" % len(seen) if len(seen) > 3 else ""
    return ["路径不存在：%s%s；新建文件请在同一行标注「新建」" % (shown, more)]


def check_s1_paths(text: str, repo: Path) -> list:
    bad = []
    for ac in ac_entries(text.splitlines()):
        if any(mk in ac for mk in NEW_MARKERS):   # 标了「新建」= 允许尚不存在
            continue
        bad += missing_paths(backtick_paths(ac), repo)
    return path_msgs(bad)


def ac_entries(lines: list) -> list:
    out = []
    for line in lines:
        s = line.strip()
        if s[:1] in ("-", "*"):
            s = s[1:].strip()
        if s.startswith("AC-") and not has_placeholder(s):
            out.append(s)
    return out


def check_s1_extra(text: str) -> list:
    """S1 内容规则：AC 必须写成「操作 → 期望」。"""
    msgs = []
    acs = ac_entries(text.splitlines())
    if not acs:
        msgs.append("无有效 AC 条目（- AC-1：操作 → 期望）")
    else:
        bad = [a for a in acs if not any(k in a for k in ARROWS)]
        if bad:
            msgs.append("AC 缺「→」：%s（须写成 操作 → 期望）" % bad[0][:40])
    return msgs


def check_s3_paths(secs: dict, repo: Path) -> list:
    """任务表反引号路径必须存在；同一行标了「新建」的跳过。"""
    _header, rows = first_table(secs.get("任务表", []))
    bad = []
    for cells in rows:
        row = " | ".join(cells)
        if any(mk in row for mk in NEW_MARKERS):
            continue
        bad += missing_paths(backtick_paths(row), repo)
    return path_msgs(bad)


def check_s3_extra(secs: dict) -> list:
    """S3 内容规则：任务表每行 ≤3 个文件，且至少一行有文件路径。"""
    msgs = []
    header, rows = first_table(secs.get("任务表", []))
    if not rows:
        msgs.append("任务表无「反引号路径」行")
        return msgs
    col = _col(header, "文件", "file")
    with_paths = 0
    for cells in rows:
        use = cells[col] if (col is not None and col < len(cells)) else ""
        paths = [p for p in use.split(",")
                 if p.strip().startswith("`") and p.strip().endswith("`")
                 and "/" in p and "." in p.rsplit("/", 1)[-1]]
        if paths:
            with_paths += 1
        if len(paths) > 3:
            msgs.append("任务行涉及 %d 个文件（每任务 ≤3）：%s"
                        % (len(paths), use[:50]))
    if not with_paths:
        msgs.append("任务表无「反引号路径」行")
    return msgs


def check_s4_extra(secs: dict) -> list:
    """S4 内容规则：每行有 ✅/❌/⊘，且「实际输出」不是「通过」这类空话。"""
    msgs = []
    header, rows = first_table(secs.get("验收逐条", []))
    if not rows:
        msgs.append("验收逐条为空（须逐条对照 AC 贴输出）")
        return msgs
    out_col = _col(header, "实际输出", "输出")
    for cells in rows:
        if any(has_placeholder(c) for c in cells):
            continue
        if not any(sym in "".join(cells) for sym in SYMBOLS):
            msgs.append("验收行缺结论符号（✅/❌/⊘）：%s" % (cells[0][:30] if cells else ""))
        if out_col is not None and out_col < len(cells):
            if plain(cells[out_col]).lower() in WEAK_OUTPUT:
                msgs.append("实际输出只写「%s」（须贴原始输出）" % cells[out_col])
    return msgs


def check_s5_extra(secs: dict) -> list:
    """S5 内容规则：裁定必须明确（通过 / 有条件通过 / 退回）。"""
    lines = secs.get("裁定", [])
    if not section_filled(lines):
        return []
    body = "\n".join(lines)
    if not any(k in body for k in ("通过", "退回")):
        return ["裁定须写明：通过 / 有条件通过 / 退回 S2/S3"]
    return []


def extract_paths(lines: list) -> list:
    """只取「涉及文件」列的反引号路径，避免把验收命令里的路径也算进范围。"""
    rows = [ln.strip() for ln in lines if ln.strip().startswith("|")]
    header = None
    data_start = 0
    for i, row in enumerate(rows):
        nxt = rows[i + 1] if i + 1 < len(rows) else ""
        if is_sep(nxt):
            header = [c.strip() for c in row.strip("|").split("|")]
            data_start = i + 2
            break
    col = None
    if header:
        for idx, cell in enumerate(header):
            if "文件" in cell or "file" in cell.lower():
                col = idx
                break
    seen = []
    for row in rows[data_start:]:
        if is_sep(row):
            continue
        cells = [c.strip() for c in row.strip("|").split("|")]
        use = [cells[col]] if (col is not None and col < len(cells)) else cells
        for cell in use:
            for piece in cell.split(","):
                c = piece.strip()
                if len(c) < 4 or not c.startswith("`") or not c.endswith("`"):
                    continue
                p = c[1:-1].strip()
                if has_placeholder(p) or "/" not in p or " " in p:
                    continue
                tail = p.rsplit("/", 1)[-1]
                if "." not in tail:
                    continue
                if p not in seen:
                    seen.append(p)
    return seen


def check_req(d: Path, quiet: bool = False, repo: Path = None) -> int:
    """校验五份产物的结构；返回 0=PASS / 1=FAIL。"""
    rid = d.name
    problems: list = []
    meta = load_meta(d)
    if not meta:
        problems.append("缺 meta.json 或无法解析")

    results = []
    for code, name, fname, headings, _crit in STAGES:
        f = d / fname
        msgs: list = []
        if not f.is_file():
            msgs.append("缺文件")
        else:
            text = f.read_text(encoding="utf-8", errors="replace")
            secs = split_sections(text)
            missing = [h for h in headings if h not in secs]
            if missing:
                msgs.append("缺章节 " + " / ".join(missing))
            empty = [h for h in headings if h in secs and not section_filled(secs[h])]
            if empty:
                msgs.append("未填写 " + " / ".join(empty))
            base = repo or REPO_ROOT
            if code == "S1":
                msgs.extend(check_s1_extra(text))
                msgs.extend(check_s1_paths(text, base))
            if code == "S3":
                msgs.extend(check_s3_extra(secs))
                msgs.extend(check_s3_paths(secs, base))
            if code == "S4":
                msgs.extend(check_s4_extra(secs))
            if code == "S5":
                msgs.extend(check_s5_extra(secs))
        results.append((code, name, fname, msgs))

    if not quiet:
        tier = meta.get("tier", "?")
        print("")
        print("%s  [%s]" % (rid, tier))
        for code, name, fname, msgs in results:
            mark = "✅" if not msgs else "⛔"
            print("  %s %s %s → %s%s" % (mark, code, name, fname, "" if not msgs else "  ｜ " + "；".join(msgs)))

    failed_stages = [r for r in results if r[3]]
    ok = not problems and not failed_stages
    if not quiet:
        if problems:
            for p in problems:
                print("  ⛔ meta: " + p)
        if ok:
            print("  → PASS（结构完整；内容质量仍需人看 04/05）")
        else:
            cur = failed_stages[0][0]
            print("  → FAIL：先补 " + failed_stages[0][2] + " ／ " + STAGE_HINT.get(cur, ""))
    else:
        if ok:
            print("PASS " + rid)
        else:
            if failed_stages:
                first = failed_stages[0]
                print("FAIL %s %s %s" % (rid, first[2], "；".join(first[3])))
            else:
                print("FAIL %s meta.json %s" % (rid, "；".join(problems)))
    return 0 if ok else 1


def current_stage(d: Path) -> str:
    for code, _name, fname, headings, _crit in STAGES:
        f = d / fname
        if not f.is_file():
            return code
        secs = split_sections(f.read_text(encoding="utf-8", errors="replace"))
        if any(h not in secs or not section_filled(secs[h]) for h in headings):
            return code
    return "DONE"


class _Parser(argparse.ArgumentParser):
    """参数错误一律 exit 64 —— 不能与「2 = 无进行中 REQ」撞码。"""

    def error(self, message):  # type: ignore[override]
        self.print_usage(sys.stderr)
        print(f"{self.prog}: 参数错误：{message}", file=sys.stderr)
        raise SystemExit(64)


def resolve(args, root: Path) -> Path:
    rid = getattr(args, "req", None) or read_active(root)
    return root / rid if rid else None


def cmd_new(args, root: Path) -> int:
    slug = "".join(ch if (ch.isalnum() or ch in "-_") else "-" for ch in args.slug).strip("-")
    if not slug:
        print("slug 不能为空")
        return 1
    rid = "REQ-" + date.today().strftime("%Y%m%d") + "-" + slug
    d = root / rid
    if d.exists():
        print("已存在：" + str(d))
        return 1
    if not TEMPLATE_DIR.is_dir():
        print("缺模板目录：" + str(TEMPLATE_DIR))
        return 1
    d.mkdir(parents=True)
    (d / "assets").mkdir()
    for _code, _name, fname, _h, _c in STAGES:
        src = TEMPLATE_DIR / fname
        text = src.read_text(encoding="utf-8")
        text = text.replace("<编号>", rid[4:])
        (d / fname).write_text(text, encoding="utf-8")
    meta = {
        "req": rid,
        "title": args.title or slug,
        "tier": args.tier,
        "status": "S1",
        "created": date.today().isoformat(),
        "updated": date.today().isoformat(),
        "commits": [],
        "scope": [],
    }
    save_meta(d, meta)
    write_active(root, rid)
    print("已创建 " + str(d))
    print("当前阶段 S1（需求澄清）。下一步：填 01-需求.md，然后跑 next")
    return 0


def cmd_use(args, root: Path) -> int:
    d = root / args.req
    if not d.is_dir():
        print("不存在：" + str(d))
        return 1
    write_active(root, args.req)
    print("当前 REQ：" + args.req + "（阶段 " + current_stage(d) + "）")
    return 0


def cmd_next(args, root: Path) -> int:
    d = resolve(args, root)
    if d is None or not d.is_dir():
        print("无进行中 REQ。开新单：")
        print("  .venv/Scripts/python.exe scripts/quality/check_delivery.py new <slug> --tier T1")
        return 2
    meta = load_meta(d)
    st = current_stage(d)
    print("=== %s (%s) ===" % (d.name, meta.get("tier", "?")))
    if st == "DONE":
        print("五阶段结构已齐。收尾：")
        print("  1) check_all.py 全绿   2) 把结论回填 docs/02-功能设计/   3) 在 INDEX.md 标已交付")
        return 0
    for code, name, fname, _h, crit in STAGES:
        if code != st:
            continue
        print("当前阶段：%s %s  →  %s" % (code, name, fname))
        print("出口判据：" + crit)
    print("怎么做：" + STAGE_HINT.get(st, ""))
    if st == "S3":
        print("声明范围：.venv/Scripts/python.exe scripts/quality/check_delivery.py scope --apply")
    if st == "S5":
        print("评审必须由独立只读 agent / 新会话执行，作者不自审")
    return 0


def cmd_status(args, root: Path) -> int:
    if not root.is_dir():
        print("尚无交付记录目录：" + str(root))
        return 2
    dirs = sorted([p for p in root.iterdir() if p.is_dir() and p.name.startswith("REQ-")])
    if not dirs:
        print("尚无 REQ。")
        return 2
    active = read_active(root)
    print("%-40s %-4s %-5s %s" % ("REQ", "档", "阶段", "标题"))
    for d in dirs:
        meta = load_meta(d)
        mark = "*" if d.name == active else " "
        print("%s%-39s %-4s %-5s %s" % (
            mark, d.name, meta.get("tier", "?"), current_stage(d), meta.get("title", "")))
    print("")
    return 0


def cmd_check(args, root: Path) -> int:
    d = resolve(args, root)
    if d is None or not d.is_dir():
        if getattr(args, "req", None):  # 明确点名却不存在 → 是错误，不是 SKIP
            print("不存在：" + str(d))
            return 1
        if not args.quiet:
            print("无进行中 REQ（SKIP）。用 new 开单或用 use 指定。")
        return 2
    repo = Path(args.repo).resolve() if getattr(args, "repo", None) else REPO_ROOT
    return check_req(d, quiet=args.quiet, repo=repo)


def cmd_scope(args, root: Path) -> int:
    d = resolve(args, root)
    if d is None or not d.is_dir():
        print("不存在：" + str(d) if getattr(args, "req", None) else "无进行中 REQ。")
        return 1 if getattr(args, "req", None) else 2
    f = d / "03-任务.md"
    if not f.is_file():
        print("缺 03-任务.md")
        return 1
    paths = extract_paths(split_sections(f.read_text(encoding="utf-8", errors="replace")).get("任务表", []))
    if not paths:
        print("任务表里没有反引号路径。示例：| 1 | 改接口 | `quant_server/api/routers/market_router.py` | `<命令>` |")
        return 1
    joined = ",".join(paths)
    print("范围（%d 个文件）：" % len(paths))
    for p in paths:
        print("  " + p)
    if not args.apply:
        print("")
        print("确认后执行：")
        print("  python scripts/quality/check_all.py --declare \"" + joined + "\"")
        return 0
    cmd = [sys.executable, str(QUALITY_DIR / "check_all.py"), "--declare", joined]
    if getattr(args, "root", None):  # 测试用 root：范围文件也写在那里，不污染仓库 .claude/
        cmd += ["--scope", str(root / "scope.txt")]
    print("→ " + " ".join(cmd))
    return subprocess.call(cmd)


def main() -> int:
    _utf8_stdout()
    # 全局开关挂在每个子命令上（argparse 默认只认子命令**之前**的全局参数，
    # 而实际习惯是写在后面）；SUPPRESS 让「写在前面」的取值不被子命令的默认值覆盖。
    global_opts = _Parser(add_help=False)
    global_opts.add_argument("--root", default=argparse.SUPPRESS,
                             help="交付记录根目录（测试用，默认 docs/09-交付记录）")
    global_opts.add_argument("--req", default=argparse.SUPPRESS,
                             help="指定 REQ（默认读 .active）")
    global_opts.add_argument("--repo", default=argparse.SUPPRESS,
                             help="路径存在性校验的基准目录（测试用，默认仓库根）")

    # 不用 p.set_defaults()：它会改掉父 parser 里动作的 SUPPRESS 默认值，
    # 导致子命令解析时把前面已设好的 --root 覆盖成 None。
    p = _Parser(description="交付流程状态机（S1-S5）", parents=[global_opts])
    sub = p.add_subparsers(dest="cmd")

    sp = sub.add_parser("new", parents=[global_opts], help="开新单")
    sp.add_argument("slug")
    sp.add_argument("--tier", default="T1", choices=["T0", "T1", "T2", "T3"])
    sp.add_argument("--title", default="")

    sub.add_parser("next", parents=[global_opts], help="当前阶段与出口判据")
    sub.add_parser("status", parents=[global_opts], help="全部 REQ 一览")

    sp = sub.add_parser("check", parents=[global_opts], help="结构校验")
    sp.add_argument("req_arg", nargs="?", default=None, metavar="REQ",
                    help="指定 REQ（等价于 --req，位置写法）")
    sp.add_argument("--quiet", action="store_true", help="只打一行结论（供 check_all 调用）")

    sp = sub.add_parser("scope", parents=[global_opts], help="由 03-任务.md 推范围")
    sp.add_argument("req_arg", nargs="?", default=None, metavar="REQ",
                    help="指定 REQ（等价于 --req，位置写法）")
    sp.add_argument("--apply", action="store_true", help="直接调用 check_all --declare")

    sp = sub.add_parser("use", parents=[global_opts], help="切换当前 REQ")
    sp.add_argument("req")

    args = p.parse_args()
    args.root = getattr(args, "root", None)   # SUPPRESS 默认：未给就没有该属性
    args.req = getattr(args, "req", None)
    args.repo = getattr(args, "repo", None)
    if getattr(args, "req_arg", None):  # check/scope 的位置参数优先于 --req
        args.req = args.req_arg
    if not args.cmd:
        p.print_help()
        return 1
    root = req_root(args)
    handlers = {"new": cmd_new, "next": cmd_next, "status": cmd_status,
                "check": cmd_check, "scope": cmd_scope, "use": cmd_use}
    return handlers[args.cmd](args, root)


if __name__ == "__main__":
    sys.exit(main())
