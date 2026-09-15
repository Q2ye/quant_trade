# -*- coding: utf-8 -*-
"""清理今晚实验产生的垃圾回测任务（不提交到 git）。

删除范围（**严格限定**）：
  A. `问题1滚动%` 家族里 非 completed（pending/cancelled）的行
  B. `问题1滚动%` 家族里 同一「臂×起始日」的重复 completed（每个组合保留 1 条，保留最早创建的）
  C. 其它名称含「问题1」的 cancelled/pending 孤儿行

**不触碰**：R² 实验的 5 条证据任务、问题1 单起始日 2 条、以及所有早于今晚的任务。

先备份清单到 logs/_cleanup_manifest.txt，再删除。
用法： python scripts/_cm_cleanup_tasks.py [--apply]
"""
import asyncio
import json
import sys
import time

APPLY = "--apply" in sys.argv
MANIFEST = "logs/_cleanup_manifest.txt"

STARTS = ["2019-06-01", "2020-07-01", "2021-09-14",
          "2022-11-01", "2024-01-02", "2025-01-02"]
KEEP_IDS = {  # R² 实验 + 问题1 单起始日 —— 明确保留
    "020611da", "339dff29", "bf42496f", "844d308e", "d8103e2a", "443b202f", "1ffa613d",
}


def arm_start(name: str):
    if not name.startswith("问题1滚动-"):
        return None
    body = name[len("问题1滚动-"):]
    for s in STARTS:
        if body.endswith("-" + s):
            k = body[: -(len(s) + 1)][0].upper()
            return (k, s) if k in ("A", "B", "C") else None
    return None


async def main() -> None:
    from sqlalchemy import text
    from shared.database.session.connection_pool import get_connection_pool

    pool = get_connection_pool()
    try:
        sf = pool.get_session_factory()
    except RuntimeError:
        await pool.initialize()
        sf = pool.get_session_factory()

    lines = []
    async with sf() as s:
        r = await s.execute(text(
            "SELECT id::text, name, status, created_at::text, result FROM backtest_tasks "
            "WHERE name LIKE '%问题1%' ORDER BY created_at"))
        rows = r.fetchall()

        # 分组：每组保留「最早的 completed 且有 result」的那条
        groups: dict = {}
        for i, n, st, ca, res in rows:
            k = arm_start(n)
            groups.setdefault(k, []).append((i, n, st, ca, res))

        to_delete, to_keep = [], []
        for k, items in groups.items():
            done = [x for x in items if x[2] == "completed" and x[4]]
            others = [x for x in items if x not in done]
            if k is None:                      # 非滚动（如"跨市场-问题1-B_回测_…"）
                for x in items:
                    (to_keep if x[2] == "completed" and x[4] else to_delete).append(x)
                continue
            if done:
                keep = done[0]                 # 已按 created_at 升序
                to_keep.append(keep)
                to_delete.extend(done[1:])
            to_delete.extend(others)

        # 明确保护 KEEP_IDS
        to_delete = [x for x in to_delete if x[0][:8] not in KEEP_IDS]

        # 检查 backtest_comparisons 引用（NO ACTION → 有引用则删不掉）。
        # 注意：该表的外键列是 base_task_id（不是 task_id）；实测 0 行，故实际无引用。
        ids = [x[0] for x in to_delete]
        ref = []
        if ids:
            r = await s.execute(text(
                "SELECT DISTINCT base_task_id::text FROM backtest_comparisons "
                "WHERE base_task_id = ANY(:i)"), {"i": ids})
            ref = [x[0] for x in r.fetchall()]

        lines.append(f"# 清理清单 {time.strftime('%Y-%m-%d %H:%M:%S')}")
        lines.append(f"# 扫描到「问题1」家族任务 {len(rows)} 条")
        lines.append(f"# 保留 {len(to_keep)}  删除 {len(to_delete)}  "
                     f"（其中被 backtest_comparisons 引用的 {len(ref)} 条将跳过）")
        lines.append("")
        lines.append("## 保留（证据）")
        for i, n, st, ca, res in sorted(to_keep, key=lambda x: x[1]):
            m = json.loads(res) if isinstance(res, str) else (res or {})
            lines.append(f"  KEEP {i}  {n:<44} {st:<10} "
                         f"created={ca[:19]}  收益={m.get('total_return')} 笔={m.get('num_trades')}")
        lines.append("")
        lines.append("## 删除")
        for i, n, st, ca, res in sorted(to_delete, key=lambda x: x[1]):
            m = json.loads(res) if isinstance(res, str) else (res or {})
            lines.append(f"  DEL  {i}  {n:<44} {st:<10} "
                         f"created={ca[:19]}  收益={m.get('total_return')} 笔={m.get('num_trades')}")

        print("\n".join(lines))
        open(MANIFEST, "w", encoding="utf-8").write("\n".join(lines) + "\n")
        print(f"\n[清单已写入 {MANIFEST}]")

        if not APPLY:
            print("\n[DRY-RUN] 未删除。加 --apply 执行。")
            await pool.close()
            return

        deletable = [x[0] for x in to_delete if x[0] not in ref]
        if deletable:
            r = await s.execute(text(
                "DELETE FROM backtest_tasks WHERE id = ANY(:i)"), {"i": deletable})
            await s.commit()
            print(f"[APPLY] 已删除 {r.rowcount} 行（子表随 CASCADE 一并清除）")
        if ref:
            print(f"跳过 {len(ref)} 条（被 backtest_comparisons 引用）: {[x[:8] for x in ref]}")

        r = await s.execute(text(
            "SELECT status, count(*) FROM backtest_tasks "
            "WHERE name LIKE '%问题1%' GROUP BY status ORDER BY status"))
        print("\n清理后「问题1」家族剩余:")
        for st, c in r.fetchall():
            print(f"  {st:<12} {c}")

    await pool.close()


if __name__ == "__main__":
    asyncio.run(main())
