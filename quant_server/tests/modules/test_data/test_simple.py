#!/usr/bin/env python3
"""
简单测试脚本 - 验证数据同步服务的基本逻辑
"""

import asyncio
import pytest
from unittest.mock import AsyncMock, MagicMock


class MockDataType:
    STOCK_LIST = "stock_list"


class MockDataSource:
    TUSHARE = "tushare"


class SimpleDataSyncService:
    """简化版数据同步服务"""

    def __init__(self):
        self.session = AsyncMock()
        self.session.commit = AsyncMock()

        self.stock_basic_repo = AsyncMock()
        self.source_factory = MagicMock()

        self.DataType = MockDataType
        self.DataSource = MockDataSource

    async def sync_market_data(self, data_type, **kwargs):
        """同步市场数据"""
        if data_type == self.DataType.STOCK_LIST:
            return await self._sync_stock_list(**kwargs)
        return {"success": False, "error": "未知数据类型"}

    async def _sync_stock_list(self, **kwargs):
        """同步股票列表"""
        try:
            mock_source = self.source_factory.get_source.return_value
            stock_data = await mock_source.get_stock_basic()

            records_added = 0
            records_updated = 0

            for stock in stock_data:
                existing = await self.stock_basic_repo.get_by_ts_code(stock["ts_code"])
                if existing:
                    await self.stock_basic_repo.update(existing.id, stock)
                    records_updated += 1
                else:
                    await self.stock_basic_repo.create(stock)
                    records_added += 1

            await self.session.commit()

            return {
                "success": True,
                "result": {
                    "records_added": records_added,
                    "records_updated": records_updated,
                    "records_failed": 0,
                    "total_items": len(stock_data)
                },
                "message": "股票列表同步完成"
            }

        except Exception as e:
            return {
                "success": False,
                "error": str(e),
                "message": "数据同步失败"
            }


@pytest.mark.asyncio
async def test_sync_success():
    """测试成功同步"""
    print("测试成功同步场景...")

    service = SimpleDataSyncService()

    # 设置mock数据 - 使用AsyncMock
    mock_source = service.source_factory.get_source.return_value
    mock_source.get_stock_basic = AsyncMock(return_value=[
        {"ts_code": "000001.SZ", "name": "平安银行"},
        {"ts_code": "600000.SH", "name": "浦发银行"}
    ])

    # 模拟repository响应 - 使用AsyncMock
    service.stock_basic_repo.get_by_ts_code = AsyncMock(side_effect=[
        None,  # 000001.SZ 不存在
        MagicMock(id=1)  # 600000.SH 已存在
    ])
    service.stock_basic_repo.create = AsyncMock(return_value={"id": 100})
    service.stock_basic_repo.update = AsyncMock(return_value={"id": 1})

    # 执行同步
    result = await service.sync_market_data(data_type=service.DataType.STOCK_LIST)

    # 验证结果
    assert result["success"] is True
    assert result["message"] == "股票列表同步完成"
    assert result["result"]["records_added"] == 1
    assert result["result"]["records_updated"] == 1

    print("成功同步测试通过")


@pytest.mark.asyncio
async def test_sync_failure():
    """测试同步失败"""
    print("测试同步失败场景...")

    service = SimpleDataSyncService()

    # 设置mock数据 - 模拟API调用失败 (使用AsyncMock)
    mock_source = service.source_factory.get_source.return_value
    mock_source.get_stock_basic = AsyncMock(side_effect=Exception("API调用失败"))

    # 模拟repository方法
    service.stock_basic_repo.get_by_ts_code = AsyncMock(return_value=None)

    # 执行同步
    result = await service.sync_market_data(data_type=service.DataType.STOCK_LIST)

    # 验证结果
    assert result["success"] is False
    assert "API调用失败" in result["error"]

    print("同步失败测试通过")


async def main():
    """主测试函数"""
    print("开始数据同步服务测试...\n")

    await test_sync_success()
    await test_sync_failure()

    print("\n所有测试通过！")


if __name__ == "__main__":
    asyncio.run(main())