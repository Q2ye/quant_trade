# -*- coding: utf-8 -*-
"""
补财务指标（stock_fina_indicators）历史数据脚本

用途：质量分选股器需要 ROE 等财务指标，但 stock_fina_indicators 仅近 1 年数据
（2025-07 起），恐慌抄底回测区间（2019-2025）缺失。本脚本从 Tushare fina_indicator_vip
补齐 2019 至今的历史数据。

用法（quant_server/ 下）：
    .venv/Scripts/python.exe scripts/data/backfill_fina_indicator.py              # 全量
    .venv/Scripts/python.exe scripts/data/backfill_fina_indicator.py --limit 50   # 小规模验证
    .venv/Scripts/python.exe scripts/data/backfill_fina_indicator.py --start 20210101

幂等：bulk_upsert 按 (ts_code, end_date) ON CONFLICT 更新。
"""
import argparse
import asyncio
import logging
import sys
import time
from pathlib import Path

_PROJECT_ROOT = Path(__file__).resolve().parent.parent.parent
if str(_PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(_PROJECT_ROOT))

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
logger = logging.getLogger("backfill_fina")

_END_DATE = "20260822"


def _load_env() -> dict:
    env = {}
    p = Path(__file__).resolve().parents[2] / ".env"
    if p.exists():
        for line in p.read_text(encoding="utf-8", errors="ignore").splitlines():
            line = line.strip()
            if line and not line.startswith("#") and "=" in line:
                k, _, v = line.partition("=")
                env[k.strip()] = v.strip()
    return env


async def main(limit: int, start_date: str) -> None:
    env = _load_env()
    token = env.get("PROD_TUSHARE_TOKEN", "")
    if not token:
        logger.error("PROD_TUSHARE_TOKEN 未配置，无法从 Tushare 补数")
        return

    import tushare as ts

    pro = ts.pro_api(token)

    from sqlalchemy import text
    from sqlalchemy.ext.asyncio import create_async_engine, async_sessionmaker

    from modules.data.services.sync_service import (
        _convert_records_datetime,
        _preprocess_records,
    )
    from shared.database.models.data_models import StockFinaIndicator
    from shared.database.repositories.market.fundamental.fina_indicator_repo import (
        StockFinaIndicatorRepository,
    )

    user = env.get("DB_USER", "postgres")
    password = env.get("DB_PASSWORD", "")
    host = env.get("DB_HOST", "localhost")
    port = env.get("DB_PORT", "5432")
    dbname = env.get("DB_DEV_NAME", "quant_signals_dev")
    url = f"postgresql+asyncpg://{user}:{password}@{host}:{port}/{dbname}"
    engine = create_async_engine(url)
    Session = async_sessionmaker(engine, expire_on_commit=False)

    known_cols = {c.name for c in StockFinaIndicator.__table__.columns}

    async with Session() as session:
        rows = (await session.execute(text("SELECT ts_code FROM stock_basic"))).fetchall()
        codes = [r[0] for r in rows]
        if limit and limit > 0:
            codes = codes[:limit]
        logger.info("开始 %d 只，start=%s end=%s", len(codes), start_date, _END_DATE)

        repo = StockFinaIndicatorRepository(session)
        total = 0
        failed = 0
        empty = 0
        for i, code in enumerate(codes):
            try:
                df = pro.fina_indicator_vip(ts_code=code, start_date=start_date, end_date=_END_DATE)
                if df is None or df.empty:
                    empty += 1
                    continue
                data = _convert_records_datetime(df.to_dict("records"))
                _preprocess_records(
                    data,
                    date_fields=("ann_date", "f_ann_date", "end_date"),
                    known_cols=known_cols,
                )
                # 去重 (ts_code, end_date)：Tushare 偶发重复行
                seen = set()
                deduped = []
                for item in reversed(data):
                    key = (item.get("ts_code"), item.get("end_date"))
                    if key not in seen:
                        seen.add(key)
                        deduped.append(item)
                if deduped:
                    total += await repo.bulk_upsert(deduped)
                if (i + 1) % 50 == 0:
                    await session.commit()
                    logger.info(
                        "进度 %d/%d, 新增累计 %d, 空 %d, 失败 %d",
                        i + 1, len(codes), total, empty, failed,
                    )
            except Exception as e:
                failed += 1
                if failed <= 10:
                    logger.error("%s 失败: %s", code, str(e)[:100])
            time.sleep(0.15)  # Tushare 限频
        await session.commit()
        logger.info("完成: 新增 %d, 空 %d, 失败 %d", total, empty, failed)
    await engine.dispose()


if __name__ == "__main__":
    ap = argparse.ArgumentParser(description="补 stock_fina_indicators 历史 ROE 数据")
    ap.add_argument("--limit", type=int, default=0, help="只处理前 N 只（0=全量）")
    ap.add_argument("--start", default="20190101", help="起始日期 YYYYMMDD")
    args = ap.parse_args()
    asyncio.run(main(limit=args.limit, start_date=args.start))
