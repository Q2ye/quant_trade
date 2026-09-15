# -*- coding: utf-8 -*-
"""
内置策略模板种子脚本 — 将 StrategyRegistry 发现的策略同步到 strategy_templates 表。

用途：
  - 首次部署 / 新增策略文件后，将策略源码 + 默认参数同步进模板库
  - 幂等：按 template_name + is_builtin 去重，已存在则更新代码/参数
  - 与服务启动时 StrategyManager._on_initialize() 的 seed_builtin_templates()
    共用同一实现（TemplateService.seed_builtin_templates）
  - 2026-08 阶段 4b/4c：用于把恐慌抄底/微盘两个卫星策略同步进模板库（不打完整服务）

用法（quant_server/ 下运行）：
    .venv/Scripts/python.exe scripts/data/seed_builtin_templates.py
    .venv/Scripts/python.exe scripts/data/seed_builtin_templates.py --dry-run
"""
import argparse
import asyncio
import logging
import sys
from pathlib import Path

# 保证从任意 cwd 都能 import shared/ modules/（脚本位于 quant_server/scripts/ 下）
_PROJECT_ROOT = Path(__file__).resolve().parent.parent.parent
if str(_PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(_PROJECT_ROOT))

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
)
logger = logging.getLogger("seed_builtin_templates")


async def _list_registry_entries() -> list:
    """dry-run：仅扫描注册表并返回条目列表，不写库。"""
    from modules.strategy.engines.strategy_registry import StrategyRegistry

    registry = StrategyRegistry()
    if registry.is_empty():
        registry.auto_discover()
    return registry.list_all()


async def main(dry_run: bool) -> int:
    if dry_run:
        entries = await _list_registry_entries()
        print(f"[dry-run] 注册表共 {len(entries)} 个策略：")
        for e in sorted(entries, key=lambda x: x["class_name"]):
            print(
                f"  - {e['class_name']:<28} type={e['strategy_type']:<12} "
                f"module={e['module']}"
            )
        return 0

    from shared.database.session.session_manager import get_session_manager

    sm = get_session_manager()
    if not await sm.initialize():
        logger.error("数据库连接池初始化失败")
        return 1

    try:
        async with sm.get_session() as session:
            from modules.strategy.services.template_service import TemplateService

            svc = TemplateService(session)
            result = await svc.seed_builtin_templates()
            logger.info("模板同步完成: %s", result)
            return 0
    except Exception as e:
        logger.error("模板同步失败: %s", e, exc_info=True)
        return 1
    finally:
        await sm.close()


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="同步内置策略到模板库（幂等）")
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="只扫描并打印注册表，不写库",
    )
    args = parser.parse_args()
    sys.exit(asyncio.run(main(dry_run=args.dry_run)))
