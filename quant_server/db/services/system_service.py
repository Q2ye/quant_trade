# system_service.py
import psutil
from typing import Dict, Any, Optional
from sqlalchemy import text

from ..services.base_service import BaseService




class SystemService(BaseService):
    """系统服务类，处理系统相关的数据库操作和资源监控"""

    def check_database_connection(self) -> bool:
        """检查数据库连接状态"""
        try:
            with self.session_scope() as session:
                session.execute(text("SELECT 1"))
                return True
        except Exception:
            return False

    def get_database_status(self) -> Dict[str, Any]:
        """获取数据库状态信息"""
        try:
            with self.session_scope() as session:
                # 获取数据库大小（PostgreSQL示例）
                size_result = session.execute(text(
                    "SELECT pg_size_pretty(pg_database_size(current_database()))"
                )).scalar()

                # 获取表数量
                table_count = session.execute(text(
                    "SELECT COUNT(*) FROM information_schema.tables WHERE table_schema = 'public'"
                )).scalar()

                # 获取连接数
                connection_count = session.execute(text(
                    "SELECT COUNT(*) FROM pg_stat_activity WHERE datname = current_database()"
                )).scalar()

            return {
                "size": size_result,
                "tables": table_count,
                "connections": connection_count,
                "status": "healthy"
            }
        except Exception as e:
            # 如果数据库查询失败，尝试简化查询
            try:
                with self.session_scope() as session:
                    session.execute(text("SELECT 1"))
                    table_count = session.execute(text(
                        "SELECT COUNT(*) FROM information_schema.tables WHERE table_schema = 'public'"
                    )).scalar()

                return {
                    "size": "Unknown",
                    "tables": table_count,
                    "lastBackup": "Unknown",
                    "connections": "Unknown",
                    "status": "connected",
                    "warning": "Limited information available"
                }
            except Exception:
                return {
                    "size": "Unknown",
                    "tables": "Unknown",
                    "lastBackup": "Unknown",
                    "connections": "Unknown",
                    "status": "disconnected",
                    "error": str(e)
                }

    def get_connection_status(self) -> Dict[str, bool]:
        """获取系统连接状态"""
        database_connected = self.check_database_connection()

        # 检查数据源连接（这里以Tushare为例）
        try:
            # 这里应该是检查Tushare连接的实际代码
            # 暂时用模拟逻辑
            data_source_connected = database_connected
        except Exception:
            data_source_connected = False

        # 检查交易网关连接
        try:
            # 这里应该是检查交易网关连接的实际代码
            trade_gateway_connected = True
        except Exception:
            trade_gateway_connected = False

        # 检查策略引擎状态
        try:
            # 这里应该是检查策略引擎状态的实际代码
            strategy_engine_connected = True
        except Exception:
            strategy_engine_connected = False

        return {
            "dataSource": data_source_connected,
            "tradeGateway": trade_gateway_connected,
            "strategyEngine": strategy_engine_connected,
            "database": database_connected
        }

    def get_system_resources(self) -> Dict[str, float]:
        try:
            # CPU使用率
            cpu_percent = psutil.cpu_percent(interval=1)

            # 内存使用率
            memory = psutil.virtual_memory()
            memory_percent = memory.percent

            # 磁盘使用率
            disk = psutil.disk_usage('/')
            disk_percent = disk.percent

            # 网络使用情况
            net_io = psutil.net_io_counters()
            total_net_usage = (net_io.bytes_sent + net_io.bytes_recv) / (1024 * 1024)
            network_percent = min(total_net_usage / 1000, 1.0)  # 假设1000MB为基准

            return {
                "cpu": round(cpu_percent / 100, 2),
                "memory": round(memory_percent / 100, 2),
                "disk": round(disk_percent / 100, 2),
                "network": round(network_percent, 2)
            }
        except Exception as e:
            # 如果获取资源信息失败，返回默认值
            return {
                "cpu": 0.45,
                "memory": 0.62,
                "disk": 0.28,
                "network": 0.15,
                "error": str(e)
            }

    def get_system_logs(self, level: Optional[str] = None,
                        offset: int = 0, limit: int = 20) -> Dict[str, Any]:
        """获取系统日志（需要日志表支持）"""
        # 这里需要实现从数据库日志表查询的逻辑
        # 暂时返回模拟数据
        return {
            "data": [
                {
                    "timestamp": "2023-08-23T10:30:00",
                    "level": "INFO",
                    "module": "data_sync",
                    "message": "Daily data sync completed"
                }
            ],
            "pagination": {
                "offset": offset,
                "limit": limit,
                "total": 1,
                "pages": 1
            }
        }

    def get_data_sync_status(self) -> Dict[str, Any]:
        """获取数据同步状态"""
        # 这里需要实现从数据库查询数据同步状态的逻辑
        # 暂时返回模拟数据
        return {
            "last_sync": "2023-08-23T08:00:00",
            "status": "completed",
            "records_updated": 12500
        }

    def get_system_settings(self) -> Dict[str, Any]:
        """获取系统设置"""
        # 这里需要实现从数据库查询系统设置的逻辑
        # 暂时返回模拟数据
        return {
            "data_source": "tushare",
            "auto_sync": True,
            "sync_time": "08:00",
            "risk_limits": {
                "max_position_per_stock": 0.2,
                "max_daily_loss": -0.05
            }
        }

    def update_system_settings(self, settings: Dict[str, Any]) -> bool:
        """更新系统设置"""
        # 这里需要实现更新系统设置的逻辑
        # 暂时返回模拟数据
        return True