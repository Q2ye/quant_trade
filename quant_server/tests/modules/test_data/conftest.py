import pytest
from unittest.mock import AsyncMock, MagicMock
from sqlalchemy.ext.asyncio import AsyncSession

from modules.data.services.sync_service import DataSyncService


@pytest.fixture
def mock_async_session():
    """创建模拟的异步数据库会话"""
    session = AsyncMock(spec=AsyncSession)
    session.commit = AsyncMock()
    return session


@pytest.fixture
async def data_sync_service(mock_async_session):
    """创建数据同步服务测试实例"""
    service = DataSyncService(session=mock_async_session)

    # 模拟所有repository
    repo_attrs = [attr for attr in dir(service) if attr.endswith('_repo')]
    for attr_name in repo_attrs:
        mock_repo = AsyncMock()
        setattr(service, attr_name, mock_repo)

    # 模拟缓存
    service._cache = AsyncMock()

    # 模拟数据源工厂
    mock_source = AsyncMock()
    mock_source_factory = MagicMock()
    mock_source_factory.get_source.return_value = mock_source
    service.source_factory = mock_source_factory

    return service


@pytest.fixture
def mock_data_source(data_sync_service):
    """获取模拟的数据源"""
    return data_sync_service.source_factory.get_source.return_value


@pytest.fixture
def sample_stock_data():
    """提供示例股票数据"""
    return [
        {"ts_code": "000001.SZ", "name": "平安银行", "list_date": "19910403"},
        {"ts_code": "600000.SH", "name": "浦发银行", "list_date": "19991110"}
    ]


@pytest.fixture
def sample_daily_quotes():
    """提供示例日行情数据"""
    return [
        {
            "ts_code": "000001.SZ",
            "trade_date": "20240115",
            "open": 10.5,
            "high": 10.8,
            "low": 10.3,
            "close": 10.6,
            "vol": 1000000,
            "amount": 10600000
        }
    ]


@pytest.fixture
def batch_sync_request():
    """提供批量同步请求示例"""
    from modules.data.models import BatchSyncRequest
    from modules.data.constants import DataType

    return BatchSyncRequest(
        data_types=[DataType.STOCK_LIST, DataType.DAILY_QUOTES],
        start_date="2024-01-01",
        end_date="2024-01-31"
    )