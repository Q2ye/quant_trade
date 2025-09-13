import os
from dotenv import load_dotenv
from typing import Dict, Any
import logging

logger = logging.getLogger(__name__)

# 加载.env文件
load_dotenv()


class Config:
    """配置管理类"""

    def __init__(self):
        self._config = {}
        self.load_from_env()

    def load_from_env(self):
        """从环境变量加载配置"""
        # 数据库配置
        self._config['database'] = {
            'dialect': os.getenv('DB_DIALECT', 'postgresql'),
            'host': os.getenv('DB_HOST', 'localhost'),
            'port': int(os.getenv('DB_PORT', 5432)),
            'database': os.getenv('DB_NAME', 'quant_platform'),
            'username': os.getenv('DB_USER', 'postgres'),
            'password': os.getenv('DB_PASSWORD', 'password'),
            'echo': os.getenv('DB_ECHO', 'false').lower() == 'true'
        }

        # 数据源配置
        self._config['sources'] = {
            'tushare': {
                'enabled': os.getenv('TUSHARE_ENABLED', 'true').lower() == 'true',
                'token': os.getenv('TUSHARE_TOKEN', ''),
                'max_retries': int(os.getenv('TUSHARE_MAX_RETRIES', 3)),
                'timeout': int(os.getenv('TUSHARE_TIMEOUT', 30))
            },
            'baostock': {
                'enabled': os.getenv('BAOSTOCK_ENABLED', 'true').lower() == 'true',
                'max_retries': int(os.getenv('BAOSTOCK_MAX_RETRIES', 3)),
                'timeout': int(os.getenv('BAOSTOCK_TIMEOUT', 30))
            }
        }

        # 同步设置
        self._config['sync'] = {
            'auto_sync': os.getenv('SYNC_AUTO', 'true').lower() == 'true',
            'sync_time': os.getenv('SYNC_TIME', '02:00'),
            'retention_days': int(os.getenv('SYNC_RETENTION_DAYS', 365))
        }

        # 通知配置
        self._config['notifiers'] = {
            'email': {
                'enabled': os.getenv('EMAIL_ENABLED', 'false').lower() == 'true',
                'smtp_server': os.getenv('EMAIL_SMTP_SERVER', ''),
                'smtp_port': int(os.getenv('EMAIL_SMTP_PORT', 587)),
                'username': os.getenv('EMAIL_USERNAME', ''),
                'password': os.getenv('EMAIL_PASSWORD', ''),
                'from_addr': os.getenv('EMAIL_FROM_ADDR', ''),
                'to_addrs': os.getenv('EMAIL_TO_ADDRS', '').split(',')
            }
        }

        logger.info("配置已从环境变量加载")

    def get(self, key: str, default: Any = None) -> Any:
        """获取配置值"""
        return self._config.get(key, default)

    def __getitem__(self, key: str) -> Any:
        """获取配置值"""
        return self._config[key]

    def __contains__(self, key: str) -> bool:
        """检查配置是否存在"""
        return key in self._config

    def get_config_dict(self) -> Dict[str, Any]:
        """返回配置字典"""
        return self._config


# 创建全局配置实例
config = Config()