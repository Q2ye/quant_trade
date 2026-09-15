# -*- coding: utf-8 -*-
"""把磁盘 bottom_strategy.py 同步到 DB 全部副本（默认 dry-run，不带 --apply 只查）。

用途：凭证整改后，DB `strategies.code` 与 `strategy_templates.code_template`
里的明文口令副本必须一并清除 —— 否则实盘/回测仍加载旧代码（策略从 DB 加载）。

用法：
    cd quant_server
    .venv/Scripts/python.exe scripts/_sync_bottom_code.py            # 只查（dry-run）
    .venv/Scripts/python.exe scripts/_sync_bottom_code.py --apply    # 真写

⚠️ 应用前务必确认「与磁盘是否分叉」列 —— 若某副本 has 明显差异，说明它带独立改动，
   直接覆盖会丢改动（应先人工比对）。
"""
import asyncio
import hashlib
import re
import sys
from pathlib import Path

DISK_FILE = "modules/strategy/strategies/etf/bottom_strategy.py"
MARKER = "LightGBMBottomStrategy"

#: 真正的「硬编码凭证」形态 —— 键值对里的字符串字面量。
#: ⚠️ 不能用「包含 db_password 子串」判断：整改后的注释里仍会出现该词（说明性文字），
#:    会造成误报（2026-09-15 修正）。
RE_HARDCODED_CRED = re.compile(
    r"""["'](?:db_)?(?:password|passwd|pwd|token|api_key|secret)["']\s*:\s*["'][^"']+["']"""
    r"""|\.get\(\s*["'](?:db_)?(?:password|passwd|pwd|token|api_key|secret)["']\s*,\s*["'][^"']+["']""",
    re.IGNORECASE,
)


def norm(text: str) -> str:
    """归一化后取哈希（忽略空白差异）。"""
    return hashlib.md5(re.sub(r"\s+", " ", text or "").strip().encode("utf-8")).hexdigest()


def has_hardcoded_cred(text: str) -> bool:
    """是否含真正的硬编码凭证（键值对形态，而非注释里的说明文字）。"""
    return bool(RE_HARDCODED_CRED.search(text or ""))


async def main() -> None:
    """盘点全部副本并与磁盘比对；--apply 时写回。"""
    from sqlalchemy import text

    from shared.database.session.connection_pool import get_connection_pool

    apply = "--apply" in sys.argv
    disk = Path(DISK_FILE).read_text(encoding="utf-8")
    disk_hash = norm(disk)
    print(f"磁盘 {DISK_FILE}: {len(disk)} 字符 / hash={disk_hash[:10]}")
    print(f"模式：{'【APPLY 真写】' if apply else '【dry-run 只查】'}\n")

    pool = get_connection_pool()
    try:
        sf = pool.get_session_factory()
    except RuntimeError:
        await pool.initialize()
        sf = pool.get_session_factory()

    async with sf() as sess:
        rows = (await sess.execute(text(
            "SELECT id, name, status, run_mode, code FROM strategies "
            "WHERE code LIKE :m ORDER BY created_at DESC"
        ), {"m": f"%{MARKER}%"})).fetchall()

        print(f"strategies 副本: {len(rows)} 个")
        to_update = []
        for sid, name, status, run_mode, code in rows:
            h = norm(code)
            same = h == disk_hash
            print(f"  {'✅' if same else '⚠️ '} {name} [{status}/{run_mode}] "
                  f"len={len(code or '')} hash={h[:10]} "
                  f"硬编码凭证={'有' if has_hardcoded_cred(code) else '无'}")
            if not same:
                to_update.append(("strategies", sid, name))
        print()

        tpl_rows = (await sess.execute(text(
            "SELECT id, template_name, code_template FROM strategy_templates WHERE code_template LIKE :m"
        ), {"m": f"%{MARKER}%"})).fetchall()
        print(f"strategy_templates 副本: {len(tpl_rows)} 个")
        for tid, tname, tcode in tpl_rows:
            h = norm(tcode)
            same = h == disk_hash
            print(f"  {'✅' if same else '⚠️ '} {tname} (id={tid[:8]}) hash={h[:10]} "
                  f"硬编码凭证={'有' if has_hardcoded_cred(tcode) else '无'}")
            if not same:
                to_update.append(("strategy_templates", tid, tname))

        print(f"\n需更新：{len(to_update)} 个")
        if not apply:
            print("（dry-run 结束。确认无误后加 --apply 执行）")
            await pool.close()
            return

        for kind, rid, name in to_update:
            if kind == "strategies":
                await sess.execute(text(
                    "UPDATE strategies SET code = :c WHERE id = :i"
                ), {"c": disk, "i": rid})
            else:
                await sess.execute(text(
                    "UPDATE strategy_templates SET code_template = :c WHERE id = :i"
                ), {"c": disk, "i": rid})
            print(f"  ✓ 已更新 {name}")
        await sess.commit()
        print("✅ 全部提交完成")

    await pool.close()


if __name__ == "__main__":
    asyncio.run(main())
