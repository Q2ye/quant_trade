# -*- coding: utf-8 -*-
"""定向同步：只把修复后的策略代码写入 strategies.code 的**指定单个实例**（不提交）。

⚠️ 与「UPDATE 全部副本」的范式不同 —— 本脚本只动 --target 指定的那一行，
   其余副本（其它实例 + strategy_templates.code_template）一律不碰，并在同步后
   逐个比对 md5 证明未被改动。

用法：
    python scripts/_sync_cm_targeted.py                 # dry-run，只查
    python scripts/_sync_cm_targeted.py --apply         # 实际写入
"""
import asyncio
import hashlib
import sys

sys.path.insert(0, ".")

SRC = "modules/strategy/strategies/rotation/cross_market_momentum_strategy.py"
TARGET = "07651265-9e26-4849-89eb-6c5cdba61187"
APPLY = "--apply" in sys.argv

# 认定「本策略的代码副本」的条件（用于枚举，不影响写入范围）
COPY_WHERE = ("(class_name = 'CrossMarketMomentumStrategy' OR name LIKE '%跨市场%' "
              "OR name LIKE '%避险轮动%')")


def md5(s: str) -> str:
    return hashlib.md5(s.encode("utf-8")).hexdigest()


async def snapshot(s) -> dict:
    """快照：所有副本 + 模板的 (key -> (长度, md5))。"""
    from sqlalchemy import text

    snap = {}
    r = await s.execute(text(
        f"SELECT id::text, name, status, run_mode, length(code), md5(code) "
        f"FROM strategies WHERE {COPY_WHERE} ORDER BY created_at"))
    for i, n, st, rm, ln, h in r.fetchall():
        snap[("strategies", i)] = (n, st, rm, ln, h)
    r = await s.execute(text(
        "SELECT id::text, template_name, length(code_template), md5(code_template) "
        "FROM strategy_templates ORDER BY created_at"))
    for i, n, ln, h in r.fetchall():
        snap[("strategy_templates", i)] = (n, None, None, ln, h)
    return snap


async def main() -> None:
    from sqlalchemy import text
    from shared.database.session.connection_pool import get_connection_pool

    code = open(SRC, encoding="utf-8").read()
    assert "r2 = max(0.0, r2)" in code, "磁盘代码未含夹零修复，终止"
    assert "np.sum(W * (y - y_bar)" not in code, "磁盘代码仍含被否决的 A 臂公式"
    print(f"源文件 {SRC}")
    print(f"  长度 {len(code)}  md5 {md5(code)}  夹零修复=存在")

    pool = get_connection_pool()
    try:
        sf = pool.get_session_factory()
    except RuntimeError:
        await pool.initialize()
        sf = pool.get_session_factory()

    async with sf() as s:
        before = await snapshot(s)
        print(f"\n=== 同步前：全部副本快照（{len(before)} 项）===")
        print(f"  {'表':<20}{'id':<10}{'名称':<30}{'状态':<10}{'长度':>8}  md5")
        for (t, i), v in before.items():
            n, st, rm, ln, h = v
            mark = "  ★目标" if (t == "strategies" and i == TARGET) else ""
            print(f"  {t:<20}{i[:8]:<10}{str(n)[:28]:<30}{str(st or ''):<10}{ln:>8}  {h}{mark}")

        r = await s.execute(text("SELECT code FROM strategies WHERE id = :i"), {"i": TARGET})
        row = r.fetchone()
        if row is None:
            print("\n  ✗ 目标实例不存在，终止"); return
        cur = row[0] or ""
        print(f"\n目标 {TARGET[:8]}")
        print(f"  DB 现有 : 长度 {len(cur)}  md5 {md5(cur)}")
        print(f"  待写入  : 长度 {len(code)}  md5 {md5(code)}")
        already = cur == code
        print(f"  是否已一致: {already}")

        if not APPLY:
            print("\n[DRY-RUN] 未写入。加 --apply 执行。")
            await pool.close()
            return
        if already:
            print("\n已一致，无需写入。")
            await pool.close()
            return

        await s.execute(text(
            "UPDATE strategies SET code = :c, updated_at = CURRENT_TIMESTAMP WHERE id = :i"),
            {"c": code, "i": TARGET})
        await s.commit()
        print("\n[APPLY] 已 UPDATE 1 行")

        after = await snapshot(s)
        print(f"\n=== 同步后比对 ===")
        changed, unchanged = [], 0
        for k, v in after.items():
            b = before.get(k)
            if b and b[4] != v[4]:
                changed.append((k, b, v))
            else:
                unchanged += 1
        print(f"  变动项: {len(changed)}   未变动项: {unchanged}")
        for k, b, v in changed:
            print(f"    ★ {k[0]}/{k[1][:8]}  md5 {b[4]} → {v[4]}   ({b[3]} → {v[3]} 字符)")

        r = await s.execute(text(
            "SELECT length(code), md5(code) FROM strategies WHERE id = :i"), {"i": TARGET})
        ln, h = r.fetchone()
        ok = (ln == len(code) and h == md5(code))
        print(f"\n  目标校验: 长度 {ln} md5 {h}  → {'✅ 与磁盘逐字节一致' if ok else '❌ 不一致'}")

        only_target = len(changed) == 1 and changed[0][0] == ("strategies", TARGET)
        print(f"  仅动目标: {'✅ 其余副本 md5 全部未变' if only_target else '❌ 有其它副本被改动'}")
        r = await s.execute(text(
            "SELECT status FROM strategies WHERE id = :i"), {"i": TARGET})
        print(f"  目标 status = {r.fetchone()[0]}（未改动）")

    await pool.close()


if __name__ == "__main__":
    asyncio.run(main())
