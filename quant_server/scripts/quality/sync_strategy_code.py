# -*- coding: utf-8 -*-
"""策略代码 磁盘↔DB 一致性巡检 / 同步（长期资产）。

**为什么需要**：策略运行时从 DB `strategies.code` 加载（`exec()`），回测引擎同样如此 ——
**改磁盘 `.py` 不影响实盘/回测**。而磁盘与 DB 会**静默分叉**：
实盘实例可能跑着数周前的代码，开发者却以为刚改完已生效（`docs/review/17` §1-8 实测 3/7 分叉）。

**用法**：

    cd quant_server
    # ① 巡检：列出全部 live 实例的磁盘↔DB 一致性（默认，只读）
    .venv/Scripts/python.exe scripts/quality/sync_strategy_code.py

    # ② 看某个实例的差异明细（只读）
    .venv/Scripts/python.exe scripts/quality/sync_strategy_code.py --diff dc862847

    # ③ 同步：把磁盘写入指定实例的 DB code（**先自动备份**原 code 到 scripts/_bak/）
    .venv/Scripts/python.exe scripts/quality/sync_strategy_code.py --apply dc862847

⚠️ **同步前三问**（本脚本会提示，但不会替你判断）：
    1. 该实例的 `strategy_parameters` 是否有覆盖？若覆盖里含**磁盘已删除的键**，
       同步后那些键会静默失效（回落到 DEFAULT_PARAMS）。
    2. DB 是否有**磁盘没有的独有修复**？有 → **不要覆盖**（先 diff 人工合并）。
    3. 实例名字里的版本号（如 `v1.0-实盘`、`7.1-实盘`）是否与磁盘版本一致？
       **版本不同 = 覆盖会改变实例身份**（例：`跨市场 v1.0-实盘` 不可用当前 2.x 文件覆盖）。
"""

import asyncio
import difflib
import hashlib
import re
import shutil
import sys
from datetime import datetime
from pathlib import Path
from typing import Dict, List, Optional, Tuple

#: 策略类名 → 磁盘文件（相对 quant_server/）
CLASS_TO_FILE: Dict[str, str] = {
    "HighVolMomentumStrategy": "modules/strategy/strategies/rotation/high_vol_momentum_strategy.py",
    "CrossMarketMomentumStrategy": "modules/strategy/strategies/rotation/cross_market_momentum_strategy.py",
    "LightGBMBottomStrategy": "modules/strategy/strategies/etf/bottom_strategy.py",
    "PanicBottomStrategy": "modules/strategy/strategies/panic/panic_bottom_strategy.py",
    "MicrocapStrategy": "modules/strategy/strategies/microcap/microcap_strategy.py",
    "StockLowHighStrategy": "modules/strategy/strategies/reference/stock_low_high_strategy.py",
    "DeepDropReboundStrategy": "modules/strategy/strategies/reference/deep_drop_rebound_strategy.py",
}

# 2026-09-15 移入 quality/ 后指向 scripts/_bak（保持与既有备份同处；.gitignore 已忽略 _bak/）
BAK_DIR = Path(__file__).resolve().parent.parent / "_bak"


def norm(text: str) -> str:
    """归一化后取哈希（忽略空白差异）。"""
    return hashlib.md5(re.sub(r"\s+", " ", text or "").strip().encode("utf-8")).hexdigest()


def diff_stats(disk: str, db: str) -> Tuple[int, int]:
    """返回 (磁盘独有行数, DB 独有行数)。"""
    d = list(difflib.unified_diff(
        disk.splitlines(), db.splitlines(), lineterm="", n=0))
    return (sum(1 for x in d if x.startswith("-") and not x.startswith("---")),
            sum(1 for x in d if x.startswith("+") and not x.startswith("+++")))


def has_unique_fix(disk: str, db: str) -> bool:
    """DB 独有行里是否含"修复类"内容（有 → 禁止覆盖）。"""
    d = list(difflib.unified_diff(
        disk.splitlines(), db.splitlines(), lineterm="", n=0))
    db_only = [x for x in d if x.startswith("+") and not x.startswith("+++")]
    return any(re.search(r"修复|竞态|守卫|guard|hotfix", x, re.I) for x in db_only)


async def load_targets(sess) -> List[Tuple[str, str, str, str]]:
    """取全部 live 实例 (id, name, status, code)。"""
    from sqlalchemy import text
    rows = (await sess.execute(text(
        "SELECT id, name, status, class_name, code FROM strategies "
        "WHERE run_mode='live' ORDER BY status, name"
    ))).fetchall()
    return [(r[0], r[1], r[2], r[3], r[4]) for r in rows]


async def main() -> int:
    """巡检或同步。"""
    from sqlalchemy import text

    from shared.database.session.connection_pool import get_connection_pool

    args = [a for a in sys.argv[1:] if not a.startswith("--")]
    apply_mode = "--apply" in sys.argv
    show_diff = "--diff" in sys.argv
    root = Path(__file__).resolve().parents[2]  # 2026-09-15 移入 quality/ 后 +1 级

    pool = get_connection_pool()
    try:
        sf = pool.get_session_factory()
    except RuntimeError:
        await pool.initialize()
        sf = pool.get_session_factory()

    async with sf() as sess:
        targets = await load_targets(sess)

        # ---- 按策略类全量同步模式（含所有 run_mode 的实例 + strategy_templates）----
        if "--class" in sys.argv:
            idx = sys.argv.index("--class")
            if idx + 1 >= len(sys.argv):
                print("用法：--class <策略类名> [--apply]")
                await pool.close()
                return 2
            cls = sys.argv[idx + 1]
            rel = CLASS_TO_FILE.get(cls)
            if not rel:
                print(f"❌ 未知策略类 {cls}，请先补 CLASS_TO_FILE")
                await pool.close()
                return 2
            disk = (root / rel).read_text(encoding="utf-8")
            disk_hash = norm(disk)
            print(f"策略类：{cls}\n磁盘：{rel}（{len(disk)} 字符）")
            print(f"模式：{'【APPLY 真写】' if apply_mode else '【dry-run 只查】'}\n")

            rows = (await sess.execute(text(
                "SELECT id, name, status, run_mode, code FROM strategies "
                "WHERE class_name = :c ORDER BY created_at DESC"), {"c": cls})).fetchall()
            tpl_rows = (await sess.execute(text(
                "SELECT id, template_name, code_template FROM strategy_templates "
                "WHERE code_template LIKE :m"), {"m": f"%{cls}%"})).fetchall()

            print(f"strategies 副本 {len(rows)} 个 + templates 副本 {len(tpl_rows)} 个")
            todo: List[Tuple[str, str, str]] = []
            for sid, name, status, run_mode, code in rows:
                same = norm(code) == disk_hash
                print(f"  {'✅' if same else '⚠️ '} {name[:32]:<34}{status}/{run_mode}")
                if not same:
                    todo.append(("strategies", sid, name))
            for tid, tname, tcode in tpl_rows:
                same = norm(tcode) == disk_hash
                print(f"  {'✅' if same else '⚠️ '} [模板] {tname[:30]:<30}")
                if not same:
                    todo.append(("strategy_templates", tid, tname))

            print(f"\n需更新：{len(todo)} 个")
            if not apply_mode:
                print("（dry-run 结束。确认无误后加 --apply 执行）")
                await pool.close()
                return 0

            BAK_DIR.mkdir(exist_ok=True)
            for kind, rid, name in todo:
                if kind == "strategies":
                    old = (await sess.execute(text(
                        "SELECT code FROM strategies WHERE id = :i"), {"i": rid})).scalar()
                    (BAK_DIR / f"{rid[:8]}_{datetime.now():%Y%m%d_%H%M%S}_db_before.py"
                     ).write_text(old or "", encoding="utf-8")
                    await sess.execute(text(
                        "UPDATE strategies SET code = :c WHERE id = :i"), {"c": disk, "i": rid})
                else:
                    old = (await sess.execute(text(
                        "SELECT code_template FROM strategy_templates WHERE id = :i"),
                        {"i": rid})).scalar()
                    (BAK_DIR / f"tpl{rid[:8]}_{datetime.now():%Y%m%d_%H%M%S}_db_before.py"
                     ).write_text(old or "", encoding="utf-8")
                    await sess.execute(text(
                        "UPDATE strategy_templates SET code_template = :c WHERE id = :i"),
                        {"c": disk, "i": rid})
                print(f"  ✓ 已更新 {name}")
            await sess.commit()
            print("✅ 全部提交完成（原 code 已备份到 scripts/_bak/）")
            await pool.close()
            return 0

        # ---- 同步模式 ----
        if apply_mode or show_diff:
            if not args:
                print("用法：--apply <策略ID或名称片段> / --diff <策略ID或名称片段>")
                await pool.close()
                return 2
            key = args[0]
            hits = [t for t in targets if key in t[0] or key in t[1]]
            if len(hits) != 1:
                print(f"匹配到 {len(hits)} 个实例，需唯一：")
                for h in hits:
                    print(f"  {h[0]}  {h[1]}")
                await pool.close()
                return 2
            sid, name, status, cls, code = hits[0]
            rel = CLASS_TO_FILE.get(cls or "")
            if not rel:
                print(f"❌ 未知策略类 {cls}，请先补 CLASS_TO_FILE")
                await pool.close()
                return 2
            disk = (root / rel).read_text(encoding="utf-8")
            d_only, b_only = diff_stats(disk, code)
            print(f"实例：{name} [{status}]  id={sid[:8]}")
            print(f"磁盘：{rel}  {len(disk)} 字符")
            print(f"DB  ：{len(code)} 字符")
            print(f"差异：磁盘独有 {d_only} 行 / DB 独有 {b_only} 行")
            print(f"一致性：{'✅ 一致' if norm(disk) == norm(code) else '⚠️ 分叉'}")

            if has_unique_fix(disk, code):
                print("\n🔴 DB 独有行含『修复类』内容 —— **禁止直接覆盖**，先人工合并！")
                await pool.close()
                return 3

            if show_diff:
                print("\n--- diff（- 磁盘 / + DB）---")
                for line in list(difflib.unified_diff(
                        disk.splitlines(), code.splitlines(),
                        "disk", "db", lineterm=""))[:120]:
                    print(line)
                await pool.close()
                return 0

            # 备份 → 写入
            BAK_DIR.mkdir(exist_ok=True)
            bak = BAK_DIR / f"{sid[:8]}_{datetime.now():%Y%m%d_%H%M%S}_db_before.py"
            bak.write_text(code, encoding="utf-8")
            print(f"\n已备份原 DB code → {bak}")
            await sess.execute(text(
                "UPDATE strategies SET code = :c WHERE id = :i"), {"c": disk, "i": sid})
            await sess.commit()
            print(f"✅ 已同步 {name}")
            await pool.close()
            return 0

        # ---- 巡检模式 ----
        print("=" * 78)
        print("磁盘 ↔ DB code 一致性巡检（live 实例）")
        print("=" * 78)
        disk_cache: Dict[str, str] = {}
        bad = 0
        for sid, name, status, cls, code in targets:
            rel = CLASS_TO_FILE.get(cls or "")
            if not rel:
                print(f"  ⚪ {name[:30]:<32}{status:<9}未知策略类 {cls}")
                continue
            if rel not in disk_cache:
                disk_cache[rel] = (root / rel).read_text(encoding="utf-8")
            disk = disk_cache[rel]
            if norm(disk) == norm(code):
                print(f"  ✅ {name[:30]:<32}{status:<9}一致")
                continue
            bad += 1
            d_only, b_only = diff_stats(disk, code)
            flag = "🔴 DB 含独有修复" if has_unique_fix(disk, code) else "⚠️ 分叉"
            print(f"  {flag} {name[:30]:<32}{status:<9}"
                  f"磁盘独有 {d_only} 行 / DB 独有 {b_only} 行")

        print("-" * 78)
        print(f"共 {len(targets)} 个 live 实例，{bad} 个分叉")
        if bad:
            print("⚠️ 分叉不等于都要同步：**实例名带版本号的（如 v1.0-实盘）**"
                  "用当前磁盘文件覆盖会改变其身份 —— 先判断该实例是否还应存在。")
        await pool.close()
        return 1 if bad else 0


if __name__ == "__main__":
    sys.exit(asyncio.run(main()))
