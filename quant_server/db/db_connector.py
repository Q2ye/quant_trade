# db_connector.py
import logging
import os
from typing import Optional

import pandas as pd
from sqlalchemy import create_engine, text
from sqlalchemy.orm import sessionmaker, scoped_session

from quant_server.db.models.models import Base

logger = logging.getLogger(__name__)


def _get_config_from_env() -> dict:
    """从环境变量获取数据库配置"""
    return {
        'type': os.getenv('DB_TYPE', 'pgsql'),
        'host': os.getenv('DB_HOST', 'localhost'),
        'port': int(os.getenv('DB_PORT', '5432')),
        'user': os.getenv('DB_USER', 'postgres'),
        'password': os.getenv('DB_PASSWORD', '123456'),
        'database': os.getenv('DB_NAME', 'quant_signals'),
        'pool_size': int(os.getenv('DB_POOL_SIZE', '10')),
        'max_overflow': int(os.getenv('DB_MAX_OVERFLOW', '5'))
    }


class DbConnector:
    """统一的数据库连接管理器，支持PostgreSQL和MySQL"""

    def __init__(self):
        """
        初始化数据库连接器
        :param config: 数据库配置字典，如果为None则从环境变量读取
        """
        self.config = _get_config_from_env()
        self.engine = None
        self.Session = None
        self.dialect = self.config.get('type', 'pgsql').lower()

    def connect(self) -> bool:
        """建立数据库连接"""
        try:
            # 构建数据库连接URL
            if self.dialect == 'pgsql':
                db_url = (
                    f"postgresql+psycopg2://{self.config['user']}:{self.config['password']}@"
                    f"{self.config['host']}:{self.config['port']}/{self.config['database']}"
                )
            else:  # mysql
                db_url = (
                    f"mysql+pymysql://{self.config['user']}:{self.config['password']}@"
                    f"{self.config['host']}:{self.config['port']}/{self.config['database']}"
                    "?charset=utf8mb4"
                )

            # 创建引擎
            self.engine = create_engine(
                db_url,
                pool_size=self.config.get('pool_size', 10),
                max_overflow=self.config.get('max_overflow', 5),
                pool_recycle=3600,
                echo=os.getenv('DB_ECHO', 'false').lower() == 'true'
            )

            # 创建会话工厂
            self.Session = scoped_session(sessionmaker(
                bind=self.engine,
                autocommit=False,
                autoflush=False
            ))

            logger.info(
                f"已连接到 {self.dialect.upper()} 数据库: "
                f"{self.config['host']}:{self.config['port']}/{self.config['database']}"
            )
            return True
        except Exception as e:
            logger.error(f"数据库连接失败: {str(e)}", exc_info=True)
            return False

    def create_tables(self) -> bool:
        """创建所有数据表"""
        try:
            Base.metadata.create_all(self.engine)
            logger.info("数据库表结构已创建")
            return True
        except Exception as e:
            logger.error(f"创建表结构失败: {str(e)}", exc_info=True)
            return False

    def get_session(self):
        """获取数据库会话"""
        if not self.Session:
            raise RuntimeError("数据库未连接")
        return self.Session()

    def close(self):
        """关闭数据库连接并释放资源"""
        logger.info("正在关闭数据库连接...")
        try:
            if self.Session:
                self.Session.remove()
                logger.debug("已移除所有会话")
            if self.engine:
                self.engine.dispose()
                logger.debug("已释放数据库连接池")
            logger.info("数据库连接已成功关闭")
        except Exception as e:
            logger.error(f"关闭数据库连接时出错: {str(e)}")

    def is_connected(self) -> bool:
        """检查数据库是否已连接"""
        return self.engine is not None

    def execute_query(self, query: str, params: dict = None) -> pd.DataFrame:
        """执行SQL查询并返回DataFrame"""
        if not self.is_connected():
            raise RuntimeError("数据库未连接")

        with self.engine.connect() as conn:
            result = conn.execute(text(query), params or {})
            df = pd.DataFrame(result.fetchall(), columns=result.keys())
            return df

    def health_check(self) -> bool:
        """数据库健康检查"""
        try:
            with self.engine.connect() as conn:
                conn.execute(text("SELECT 1"))
            return True
        except Exception as e:
            logger.error(f"数据库健康检查失败: {str(e)}")
            return False