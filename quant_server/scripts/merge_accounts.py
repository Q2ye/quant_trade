# -*- coding: utf-8 -*-
"""
合并账户余额 — 将源账户余额转入共享账户（资金池合并）

用法: 在 quant_server 目录下运行
    .venv/Scripts/python.exe scripts/merge_accounts.py

功能:
  1. 将 SOURCE_ACCOUNT（ETF 原账户 9188e19e）余额转入 TARGET_ACCOUNT（共享池 84d81a14）
  2. 记录 account_transaction（审计轨迹）
  3. 源账户余额清零（保留账户记录）
"""
import uuid
from datetime import datetime

import psycopg2

DB = dict(host="localhost", port=5432, user="postgres",
          password="123456", database="quant_signals_dev")

TARGET_ACCOUNT = "84d81a14-5f0f-4741-b868-92961863ac3a"  # 共享资金池（低吸账户）
SOURCE_ACCOUNT = "9188e19e-8990-496a-ab0e-6de501b778b1"  # ETF 原账户


def main() -> None:
    conn = psycopg2.connect(**DB)
    conn.autocommit = False
    cur = conn.cursor()
    try:
        # 1. 读两账户余额
        cur.execute("SELECT total_balance, available_balance, frozen_balance, user_id FROM accounts WHERE id = %s", (SOURCE_ACCOUNT,))
        src = cur.fetchone()
        cur.execute("SELECT total_balance, available_balance, frozen_balance FROM accounts WHERE id = %s", (TARGET_ACCOUNT,))
        tgt = cur.fetchone()
        if not src or not tgt:
            print("[错误] 账户不存在")
            return

        src_total = float(src[0] or 0)
        src_avail = float(src[1] or 0)
        src_frozen = float(src[2] or 0)
        user_id = src[3]
        tgt_total = float(tgt[0] or 0)
        tgt_avail = float(tgt[1] or 0)
        tgt_frozen = float(tgt[2] or 0)

        transfer = src_total
        print(f"源账户({SOURCE_ACCOUNT[:8]}): total={src_total:,.2f} 可用={src_avail:,.2f}")
        print(f"目标账户({TARGET_ACCOUNT[:8]}): total={tgt_total:,.2f}")
        print(f"本次转入: {transfer:,.2f}")

        # 2. 更新源账户（清零）
        cur.execute(
            "UPDATE accounts SET total_balance=0, available_balance=0, frozen_balance=0, updated_at=%s WHERE id=%s",
            (datetime.now(), SOURCE_ACCOUNT),
        )
        # 3. 更新目标账户（+转入）
        new_total = tgt_total + transfer
        new_avail = tgt_avail + transfer
        cur.execute(
            "UPDATE accounts SET total_balance=%s, available_balance=%s, updated_at=%s WHERE id=%s",
            (new_total, new_avail, datetime.now(), TARGET_ACCOUNT),
        )
        # 4. 记录资金流水（审计）
        cur.execute(
            """
            INSERT INTO account_transactions
            (id, account_id, transaction_type, transaction_date, amount,
             balance_before, balance_after, description, reference_id, reference_type, created_at)
            VALUES (%s,%s,'transfer',%s,%s,%s,%s,%s,%s,'account_merge',%s)
            """,
            (str(uuid.uuid4()), TARGET_ACCOUNT, datetime.now().date(),
             transfer, tgt_total, new_total,
             f"组合资金池合并: 从 {SOURCE_ACCOUNT} 转入",
             SOURCE_ACCOUNT, datetime.now()),
        )
        conn.commit()
        print(f"[OK] 合并完成: 共享池 84d81a14 余额 -> {new_total:,.2f}")
        print(f"[OK] 源账户 9188e19e 余额 -> 0（保留记录，无策略绑定）")
    except Exception as e:
        conn.rollback()
        print(f"[错误] 合并失败，已回滚: {e}")
    finally:
        cur.close()
        conn.close()


if __name__ == "__main__":
    main()
