# config_loader.py
import os
import yaml
import logging
from typing import Dict, Any

logger = logging.getLogger('config_loader')


def load_config(config_path: str) -> Dict[str, Any]:
    """加载YAML配置文件并解析环境变量"""
    try:
        with open(config_path, 'r', encoding='utf-8') as f:
            config_content = f.read()

        # 替换环境变量
        config_content = os.path.expandvars(config_content)

        # 解析YAML
        config = yaml.safe_load(config_content)
        return config
    except Exception as e:
        logger.error(f"加载配置文件失败: {str(e)}")
        return {}


def get_db_config(config: Dict[str, Any]) -> Dict[str, Any]:
    """从配置中提取数据库配置"""
    return config.get('database', {})