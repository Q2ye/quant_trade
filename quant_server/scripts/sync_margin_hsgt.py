# -*- coding: utf-8 -*-
"""补数据：北向资金(moneyflow_hsgt) + 两融(margin) 全历史同步。

北向资金从 2014-11(沪港通开通)、两融从 2010-03(融资融券开通) 分段拉到 2026-09。
幂等：ON CONFLICT DO UPDATE。
执行: .venv/Scripts/python.exe scripts/sync_margin_hsgt.py
"""
import asyncio
import pandas as pd
from datetime import date
from sqlalchemy import text
import uuid

from shared.sources.tushare_source import TushareSource


def _year_ranges(start_year: int, start_md: str, end_year: int = 2026) -> list:
    """按年分段（首年从开通日起）。返回 [(start_yyyymmdd, end_yyyymmdd), ...]"""
    ranges = [(f"{start_year}{start_md}", f"{start_year}1231")]
    for y in range(start_year + 1, end_year + 1):
        ranges.append((f"{y}0101", f"{y}1231"))
    return ranges


async def main():
    src = TushareSource()

    # 1. 拉北向资金（分段）
    dfs = []
    for sd, ed in _year_ranges(2014, "1117"):
        df = src.get_moneyflow_hsgt(start_date=sd, end_date=ed)
        if df is not None and not df.empty:
            dfs.append(df)
    hsgt = pd.concat(dfs, ignore_index=True) if dfs else pd.DataFrame()
    print(f"[北向资金] 拉取 {len(hsgt)} 行")

    # 2. 拉两融（分段）
    mgs = []
    for sd, ed in _year_ranges(2010, "0331"):
        try:
            df = src.pro.margin(start_date=sd, end_date=ed)
            if df is not None and not df.empty:
                mgs.append(df)
        except Exception as e:
            print(f"  margin {sd}~{ed} 失败: {str(e)[:80]}")
    margin = pd.concat(mgs, ignore_index=True) if mgs else pd.DataFrame()
    print(f"[两融] 拉取 {len(margin)} 行")

    # 3. 写库
    from shared.database.session.connection_pool import get_connection_pool
    pool = get_connection_pool()
    try:
        sf = pool.get_session_factory()
    except RuntimeError:
        await pool.initialize(); sf = pool.get_session_factory()

    async with sf() as s:
        # 建 margin 表
        await s.execute(text("""
            CREATE TABLE IF NOT EXISTS margin (
                id SERIAL PRIMARY KEY,
                trade_date DATE NOT NULL,
                exchange_id VARCHAR(10),
                rzye NUMERIC, rzmre NUMERIC, rzche NUMERIC,
                rqye NUMERIC, rqmcl NUMERIC, rzrqye NUMERIC, rqyl NUMERIC,
                created_at TIMESTAMPTZ DEFAULT NOW(),
                UNIQUE (trade_date, exchange_id)
            )
        """))
        await s.commit()

        # 写北向资金
        if not hsgt.empty:
            cols = ["trade_date","ggt_ss","ggt_sz","hgt","sgt","north_money","south_money"]
            rows = []
            for _, r in hsgt.iterrows():
                td = r["trade_date"]
                if hasattr(td, "date"): td = td.date()
                elif hasattr(td, "strftime"): td = date.fromisoformat(td.strftime("%Y-%m-%d"))
                else: td = date.fromisoformat(str(td)[:10])
                rows.append((td, *(float(r[c]) if pd.notna(r.get(c)) else None for c in cols[1:])))
            # 批量 upsert
            from sqlalchemy import text as _t
            sql = _t("""
                INSERT INTO stock_moneyflow_hsgt (id,trade_date,ggt_ss,ggt_sz,hgt,sgt,north_money,south_money)
                VALUES (:id,:td,:a,:b,:c,:d,:e,:f)
                ON CONFLICT (trade_date) DO UPDATE SET
                  ggt_ss=EXCLUDED.ggt_ss,ggt_sz=EXCLUDED.ggt_sz,hgt=EXCLUDED.hgt,sgt=EXCLUDED.sgt,
                  north_money=EXCLUDED.north_money,south_money=EXCLUDED.south_money
            """)
            for td, a, b, c, d, e, f in rows:
                await s.execute(sql, {"id":str(uuid.uuid4()),"td":td,"a":a,"b":b,"c":c,"d":d,"e":e,"f":f})
            await s.commit()
            print(f"[北向资金] 写入 {len(rows)} 行")

        # 写两融
        if not margin.empty:
            cols = ["trade_date","exchange_id","rzye","rzmre","rzche","rqye","rqmcl","rzrqye","rqyl"]
            sql = _t("""
                INSERT INTO margin (trade_date,exchange_id,rzye,rzmre,rzche,rqye,rqmcl,rzrqye,rqyl)
                VALUES (:td,:ex,:a,:b,:c,:d,:e,:f,:g)
                ON CONFLICT (trade_date,exchange_id) DO UPDATE SET
                  rzye=EXCLUDED.rzye,rzmre=EXCLUDED.rzmre,rzche=EXCLUDED.rzche,
                  rqye=EXCLUDED.rqye,rqmcl=EXCLUDED.rqmcl,rzrqye=EXCLUDED.rzrqye,rqyl=EXCLUDED.rqyl
            """)
            n = 0
            for _, r in margin.iterrows():
                td = r["trade_date"]
                if hasattr(td, "date"): td = td.date()
                else: td = date.fromisoformat(str(td)[:10])
                vals = [float(r[c]) if pd.notna(r.get(c)) else None for c in cols[2:]]
                await s.execute(sql, {"td":td,"ex":r.get("exchange_id"),"a":vals[0],"b":vals[1],"c":vals[2],"d":vals[3],"e":vals[4],"f":vals[5],"g":vals[6]})
                n += 1
            await s.commit()
            print(f"[两融] 写入 {n} 行")

    await pool.close()
    print("完成")

asyncio.run(main())
