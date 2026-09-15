# utils/config_loader.py
"""
从项目根目录的 config.yml 加载配置。
首次调用时读取并缓存；后续调用直接返回缓存。
"""

import os
import yaml

BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
CONFIG_PATH = os.path.join(BASE_DIR, "config.yml")

_config = None


def _load():
    global _config
    if _config is not None:
        return _config
    if not os.path.exists(CONFIG_PATH):
        raise FileNotFoundError(f"配置文件不存在：{CONFIG_PATH}")
    with open(CONFIG_PATH, "r", encoding="utf-8") as f:
        _config = yaml.safe_load(f) or {}
    return _config


def get(key, default=None):
    """读取配置项，不存在则返回默认值"""
    cfg = _load()
    value = cfg.get(key, default)
    return default if value is None else value


def reload():
    """重新加载配置（一般不需要手动调用）"""
    global _config
    _config = None
    return _load()