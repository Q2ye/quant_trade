# -*- coding: utf-8 -*-
import asyncio
from shared.sources.tushare_source import TushareSource

async def main():
    src = TushareSource()
    # 北向资金：早期数据能否拉到
    for sd, ed in [("20141117","20141231"), ("20160101","20160331"), ("20240101","20240630")]:
        df = src.get_moneyflow_hsgt(start_date=sd, end_date=ed)
        print(f"[moneyflow_hsgt {sd}~{ed}] {len(df)} 行" + (f" 首日={df['trade_date'].min()}" if not df.empty else ""))
    # 两融：早期数据
    for sd, ed in [("20100331","20101231"), ("20160101","20160630")]:
        df = src.pro.margin(start_date=sd, end_date=ed)
        print(f"[margin {sd}~{ed}] {len(df)} 行")
    # daily_basic 更早 PE 再确认
    for td in ["20150101","20180101","20181001"]:
        df = src.get_daily_basic(trade_date=td)
        print(f"[daily_basic {td}] {len(df)} 行")

asyncio.run(main())
