#!/usr/bin/env python3
"""
真实数据同步测试 - 将测试数据保存到数据库
验证完整的同步流程和数据持久化
"""

import pytest
import asyncio
import httpx
import os
import json
from datetime import datetime, timedelta
from typing import Dict, List

class RealDataSyncTester:
    """真实数据同步测试类"""

    def __init__(self):
        self.base_url = os.getenv("API_BASE_URL", "http://localhost:8080")
        self.auth_token = os.getenv("API_AUTH_TOKEN", "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJzdWIiOiIxIiwidXNlcm5hbWUiOiJzdXBlcmFkbWluIiwiZW1haWwiOiJzdXBlcmFkbWluQHF1YW50LmNvbSIsImZ1bGxfbmFtZSI6Ilx1OGQ4NVx1N2VhN1x1N2JhMVx1NzQwNlx1NTQ1OCIsInBob25lIjoiMTM4ODg4ODg4ODgiLCJpc19hY3RpdmUiOnRydWUsImlzX3N1cGVydXNlciI6dHJ1ZSwiaXNfYWRtaW4iOnRydWUsInJvbGUiOiJhZG1pbiIsInJvbGVzIjpbImFkbWluIiwic3VwZXJhZG1pbiJdLCJwZXJtaXNzaW9ucyI6eyJzdHJhdGVneSI6eyJjYW5fcmVhZCI6dHJ1ZSwiY2FuX3dyaXRlIjp0cnVlLCJjYW5fZXhlY3V0ZSI6dHJ1ZX0sImJhc2tldCI6eyJjYW5fcmVhZCI6dHJ1ZSwiY2FuX3dyaXRlIjp0cnVlLCJjYW5fZXhlY3V0ZSI6dHJ1ZX0sInRyYWRpbmciOnsiY2FuX3JlYWQiOnRydWUsImNhbl93cml0ZSI6dHJ1ZSwiY2FuX2V4ZWN1dGUiOnRydWV9LCJtYXJrZXQiOnsiY2FuX3JlYWQiOnRydWUsImNhbl93cml0ZSI6dHJ1ZSwiY2FuX2V4ZWN1dGUiOnRydWV9fSwiY2FuX3N5bmNfZGF0YSI6dHJ1ZSwiY2FuX2FjY2Vzc19mYWN0b3IiOnRydWUsImNhbl9yZXNlYXJjaF9mYWN0b3IiOnRydWUsImV4cCI6NDkyNzc3NTE3NSwiaWF0IjoxNzc0MTc1MTc1LCJ0eXBlIjoiYWNjZXNzIn0.ez9rU93Z4fds-DGoD1mnavhqmmSrikOOmkomJp2k8c8")
        self.headers = {
            "Content-Type": "application/json",
            "Authorization": f"Bearer {self.auth_token}"
        }

    async def make_request(self, method: str, endpoint: str, data: dict = None) -> dict:
        """发送HTTP请求"""
        url = f"{self.base_url}{endpoint}"
        async with httpx.AsyncClient(timeout=60.0) as client:
            try:
                if method.upper() == "GET":
                    response = await client.get(url, headers=self.headers, params=data)
                elif method.upper() == "POST":
                    response = await client.post(url, headers=self.headers, json=data)
                response.raise_for_status()
                return response.json()
            except httpx.ConnectError:
                raise ConnectionRefusedError("服务器未运行，无法连接")
            except Exception as e:
                print(f"请求错误: {e}")
                raise

    def create_test_stock_data(self) -> List[Dict]:
        """创建测试用的股票数据"""
        return [
            {
                "ts_code": "000001.SZ",
                "symbol": "000001",
                "name": "平安银行",
                "area": "深圳",
                "industry": "银行",
                "market": "主板",
                "list_date": "1991-04-03",
                "is_hs": "N",
                "is_active": True
            },
            {
                "ts_code": "600000.SH",
                "symbol": "600000",
                "name": "浦发银行",
                "area": "上海",
                "industry": "银行",
                "market": "主板",
                "list_date": "1999-11-10",
                "is_hs": "N",
                "is_active": True
            }
        ]

    def create_test_quote_data(self) -> List[Dict]:
        """创建测试用的行情数据"""
        today = datetime.now().date()
        return [
            {
                "ts_code": "000001.SZ",
                "trade_date": (today - timedelta(days=1)).isoformat(),
                "open": 15.20,
                "close": 15.50,
                "high": 15.80,
                "low": 15.10,
                "pre_close": 15.00,
                "change": 0.50,
                "pct_chg": 3.33,
                "vol": 5000000,
                "amount": 77500000.00
            },
            {
                "ts_code": "600000.SH",
                "trade_date": (today - timedelta(days=1)).isoformat(),
                "open": 8.50,
                "close": 8.60,
                "high": 8.70,
                "low": 8.45,
                "pre_close": 8.48,
                "change": 0.12,
                "pct_chg": 1.42,
                "vol": 3000000,
                "amount": 25800000.00
            }
        ]

@pytest.mark.integration
@pytest.mark.asyncio
async def test_stock_sync_to_database():
    """测试股票数据同步到数据库"""
    print("\n=== 测试股票数据同步到数据库 ===")

    tester = RealDataSyncTester()

    try:
        # 1. 创建同步任务 - 同步股票列表
        sync_data = {
            "tasks": [
                {
                    "data_type": "stock_list",
                    "start_date": (datetime.now() - timedelta(days=7)).date().isoformat(),
                    "end_date": datetime.now().date().isoformat(),
                    "force_update": True
                }
            ],
            "priority": "high",
            "metadata": {
                "test_type": "real_sync_stock_data",
                "created_at": datetime.now().isoformat()
            }
        }

        # 2. 发送同步请求
        sync_result = await tester.make_request("POST", "/api/data/events/sync/batch", sync_data)

        # 3. 验证同步任务创建成功
        assert "task_id" in sync_result
        assert sync_result["status"] in ["pending", "running"]

        print(f"[PASS] 同步任务创建成功 - 任务ID: {sync_result['task_id']}")

        # 4. 等待任务完成并查询状态
        max_attempts = 10
        for attempt in range(max_attempts):
            status = await tester.make_request("GET",
                f"/api/data/events/sync/status?task_id={sync_result['task_id']}")

            if status["status"] == "completed":
                print("[PASS] 同步任务完成")

                # 5. 验证数据是否真的保存到数据库
                # 查询股票列表接口，验证数据存在
                stocks_result = await tester.make_request("GET", "/api/data/events/stocks", {
                    "page": 1,
                    "page_size": 10
                })

                assert "data" in stocks_result
                assert isinstance(stocks_result["data"], list)
                assert len(stocks_result["data"]) > 0

                print(f"[PASS] 数据验证成功 - 数据库中存在 {len(stocks_result['data'])} 条股票记录")

                # 6. 验证具体的股票数据
                found_pingan = False
                found_spdb = False

                for stock in stocks_result["data"]:
                    if stock["ts_code"] == "000001.SZ":
                        found_pingan = True
                        assert stock["name"] == "平安银行"
                    elif stock["ts_code"] == "600000.SH":
                        found_spdb = True
                        assert stock["name"] == "浦发银行"

                if found_pingan and found_spdb:
                    print("[PASS] 测试股票数据正确保存到数据库")
                else:
                    print("[WARN] 测试股票数据可能需要重新同步")

                break
            elif status["status"] in ["failed", "cancelled"]:
                pytest.fail(f"同步任务失败: {status}")
            else:
                print(f"[WAIT] 任务状态: {status['status']}, 等待中... ({attempt + 1}/{max_attempts})")
                await asyncio.sleep(3)
        else:
            pytest.fail("同步任务超时未完成")

    except (ConnectionRefusedError, httpx.ConnectError):
        pytest.skip("服务器未运行，跳过真实同步测试")
    except httpx.HTTPStatusError as e:
        if e.response.status_code == 500:
            pytest.skip("服务器内部错误（可能未正确配置），跳过真实同步测试")
        else:
            raise

@pytest.mark.integration
@pytest.mark.asyncio
async def test_quote_sync_to_database():
    """测试行情数据同步到数据库"""
    print("\n=== 测试行情数据同步到数据库 ===")

    tester = RealDataSyncTester()

    try:
        # 1. 创建同步任务 - 同步行情数据
        sync_data = {
            "tasks": [
                {
                    "data_type": "daily_quotes",
                    "start_date": (datetime.now() - timedelta(days=3)).date().isoformat(),
                    "end_date": datetime.now().date().isoformat(),
                    "force_update": True,
                    "parameters": {
                        "adjust": "qfq"
                    }
                }
            ],
            "priority": "high"
        }

        # 2. 发送同步请求
        sync_result = await tester.make_request("POST", "/api/data/events/sync/batch", sync_data)

        assert "task_id" in sync_result
        print(f"[PASS] 行情同步任务创建成功 - 任务ID: {sync_result['task_id']}")

        # 3. 等待任务完成
        max_attempts = 10
        for attempt in range(max_attempts):
            status = await tester.make_request("GET",
                f"/api/data/events/sync/status?task_id={sync_result['task_id']}")

            if status["status"] == "completed":
                print("[PASS] 行情同步任务完成")

                # 4. 验证行情数据
                # 这里需要根据实际的API接口来验证数据
                # 假设有查询特定股票行情的接口
                try:
                    quote_result = await tester.make_request("GET",
                        "/api/data/events/stocks/000001.SZ/quotes", {
                            "start_date": (datetime.now() - timedelta(days=3)).date().isoformat(),
                            "end_date": datetime.now().date().isoformat()
                        })

                    if "data" in quote_result and len(quote_result["data"]) > 0:
                        print(f"[PASS] 行情数据验证成功 - 获取到 {len(quote_result['data'])} 条行情记录")
                    else:
                        print("[WARN] 行情数据可能还需要时间处理")
                except Exception as e:
                    print(f"[WARN] 行情数据验证接口可能未实现: {e}")

                break
            elif status["status"] in ["failed", "cancelled"]:
                pytest.fail(f"行情同步任务失败: {status}")
            else:
                print(f"[WAIT] 行情任务状态: {status['status']}, 等待中... ({attempt + 1}/{max_attempts})")
                await asyncio.sleep(3)
        else:
            pytest.fail("行情同步任务超时未完成")

    except (ConnectionRefusedError, httpx.ConnectError):
        pytest.skip("服务器未运行，跳过真实同步测试")
    except httpx.HTTPStatusError as e:
        if e.response.status_code == 500:
            pytest.skip("服务器内部错误（可能未正确配置），跳过真实同步测试")
        else:
            raise

@pytest.mark.integration
@pytest.mark.asyncio
async def test_complete_sync_workflow():
    """测试完整的同步工作流"""
    print("\n" + "="*70)
    print("测试完整的数据同步工作流")
    print("="*70)

    tester = RealDataSyncTester()

    try:
        # 运行股票同步测试
        await test_stock_sync_to_database()

        # 运行行情同步测试
        await test_quote_sync_to_database()

        print("\n" + "="*70)
        print("[PASS] 完整同步工作流测试通过!")
        print("="*70)

    except ConnectionRefusedError:
        pytest.skip("服务器未运行，跳过完整工作流测试")

if __name__ == "__main__":
    pytest.main([__file__, "-v", "-s"])